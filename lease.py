"""按需服务的「租约」：页面开着就活着，页面一关进程自己退。

为什不按「多久没请求」判：媒体墙放片子时可能好几分钟不发一个请求
（`<video>` 缓冲完就在那儿等），按请求时间算一定会误杀正在看的片子。
所以判据是**页面还在不在** —— 页面里注入的一小段脚本每 15 秒打一次心跳，
关标签时再补一个 bye。

三种情况：
  · 关标签 / 切走      → bye → 最后一个租约消失 → 静默 DRAIN 秒后退出
    （刷新会先 bye 再 load：页面的第一个请求会把静默计时顶回去，
     紧接着 load 时的首跳心跳就把租约补上，不会被误杀）
  · 强杀 / 断网 / 睡眠 → 心跳停 → 租约过期（TTL 秒）→ 退出
  · 起了却一直没人开    → 最后一次请求后 IDLE 秒退出

退出走 `os._exit(0)`：launchd 的 KeepAlive 只认「非零退出」，正常退出不拉起 ——
按需服务本来就该是这个语义，崩了才会被重新拉起。

用法（每个服务三处）：
    import lease
    ...
    def do_GET(self):
        if lease.route(self): return          # /__lease.js、/__ping、/__bye
        ...
    html = lease.inject(html)                 # 页面末尾挂上心跳脚本
    ...
    lease.install("media", stop=srv.shutdown)  # 起服务之后、serve_forever 之前
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.parse

TTL = 180.0      # 心跳最久能断多久。浏览器后台标签页的定时器会被限流到 1 次/分，
                 # 留三分钟不至于把「切到别的标签看会儿」判成「已经关了」。
DRAIN = 6.0      # 最后一个页面关掉后再等一会儿（刷新会先 bye 再 load）
IDLE = 120.0     # 从来没被打开过：最后一次请求后多久收工
TICK = 3.0       # 看门狗多久看一眼

S = {
    "sid": "",
    "stop": None,
    "lease": {},          # 页面 id -> 到期时间
    "last": 0.0,          # 最后一次任何 HTTP 请求
    "seen": False,        # 有没有页面真的挂过租约
    "empty": 0.0,         # 租约表变空的时刻
    "fired": False,
    "busy": None,         # 后台任务还在跑就别退（刮削、跑批之类）
}
_LK = threading.Lock()
_ON = False

# 页面里跑的那一小段。setInterval 不跟页面可见性走：切到别的标签也算「页面还开着」，
# 回来还能接着用；只有真的关了/跳走了才 bye。
# bfcache 回来的页面（event.persisted）要重新领一个租约，原来的已经 bye 掉了。
JS = r"""
(function () {
  var h = '';
  var t = 0;
  function newId() {
    h = Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
  }
  function beat() {
    try {
      var u = '__ping?h=' + h;
      if (window.fetch) {
        fetch(u, { cache: 'no-store', keepalive: true }).catch(function () {});
      } else {
        var x = new XMLHttpRequest(); x.open('GET', u, true); x.send();
      }
    } catch (e) {}
  }
  function start() {
    newId(); beat();
    clearInterval(t);
    t = setInterval(beat, 15000);
  }
  function bye() {
    clearInterval(t);
    try {
      if (navigator.sendBeacon) navigator.sendBeacon('__bye?h=' + h);
      else fetch('__bye?h=' + h, { keepalive: true }).catch(function () {});
    } catch (e) {}
  }
  start();
  addEventListener('pagehide', bye);
  addEventListener('pageshow', function (e) { if (e.persisted) start(); });
})();
"""
TAG = '<script src="__lease.js"></script>'


def install(sid: str, stop=None, busy=None) -> None:
    """起看门狗。

    stop 传服务器的 shutdown（线程里调，别在请求线程里调）；
    busy 传一个「还有后台活在跑吗」的取函数 —— 有活就不退，别把刮削刮一半切断。
    """
    global _ON
    S["sid"] = sid
    S["stop"] = stop
    S["busy"] = busy
    S["last"] = time.time()
    S["lease"] = {}
    S["seen"] = False
    S["empty"] = 0.0
    if _ON:
        return
    _ON = True
    threading.Thread(target=_watch, name="lease", daemon=True).start()


def route(handler) -> bool:
    """处理 /__lease.js、/__ping、/__bye。返回 True 表示已经回复过了。

    普通请求也顺手记一笔「还活着」—— 用来兜住「进程起了但页面还没注入脚本」的那几秒，
    以及刷新时还没等到首跳心跳的间隙。
    """
    u = urllib.parse.urlparse(handler.path)
    path = u.path
    if path == "/__lease.js":
        _send(handler, JS.encode("utf-8"), "application/javascript; charset=utf-8")
        return True
    if path in ("/__ping", "/__bye"):
        hid = (urllib.parse.parse_qs(u.query).get("h") or [""])[0][:64]
        now = time.time()
        # sendBeacon 走的是 POST，body 得读掉，不然 keep-alive 连接里会剩半截请求
        try:
            n = int(handler.headers.get("Content-Length") or 0)
            if n > 0:
                handler.rfile.read(min(n, 4096))
        except (TypeError, ValueError, OSError):
            pass
        with _LK:
            S["last"] = now
            if path == "/__ping":
                S["seen"] = True
                if hid:
                    S["lease"][hid] = now + TTL
            else:
                S["lease"].pop(hid, None)
                S["last"] = now      # bye 本身也算一次动静，DRAIN 从头算
        _send(handler, b'{"ok":true}', "application/json; charset=utf-8")
        return True
    if path == "/__lease/state":
        with _LK:
            now = time.time()
            live = {k: round(v - now) for k, v in S["lease"].items() if v > now}
            d = {"sid": S["sid"], "seen": S["seen"], "leases": live,
                 "idle": round(now - S["last"]), "ttl": TTL, "drain": DRAIN, "idle_max": IDLE}
        _send(handler, json.dumps(d, ensure_ascii=False).encode("utf-8"),
              "application/json; charset=utf-8")
        return True
    with _LK:
        S["last"] = time.time()
    return False


def inject(html: str) -> str:
    """在页面末尾挂上心跳脚本。已经挂过就不重复挂。"""
    if not isinstance(html, str) or "__lease.js" in html:
        return html
    i = html.rfind("</body>")
    if i < 0:
        return html + TAG
    return html[:i] + TAG + html[i:]


def inject_bytes(body: bytes) -> bytes:
    try:
        return inject(body.decode("utf-8")).encode("utf-8")
    except UnicodeDecodeError:
        return body


def _send(handler, body: bytes, ctype: str, code: int = 200) -> None:
    try:
        handler.send_response(code)
        handler.send_header("Content-Type", ctype)
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Cache-Control", "no-store")
        handler.end_headers()
        handler.wfile.write(body)
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass


def _watch() -> None:
    while True:
        time.sleep(TICK)
        now = time.time()
        with _LK:
            if S["fired"]:
                return
            if callable(S["busy"]):
                try:
                    if S["busy"]():
                        S["empty"] = 0.0
                        S["last"] = now
                        continue
                except Exception:                   # noqa: BLE001
                    pass
            for k in [k for k, v in S["lease"].items() if v <= now]:
                S["lease"].pop(k, None)
            if S["lease"]:
                S["empty"] = 0.0
                continue
            # 租约表空着：从「最后一次动静」和「变空时刻」里取更晚的那个，
            # 静默够 DRAIN 秒才算真没人了（刷新时页面会马上再发一次请求）。
            if not S["empty"]:
                S["empty"] = now
            quiet = now - max(S["last"], S["empty"])
            if S["seen"]:
                if quiet >= DRAIN:
                    S["fired"] = True
                    why = "页面都关了"
            elif now - S["last"] >= IDLE:
                S["fired"] = True
                why = "起了没人用"
        if S["fired"]:
            _bye(why)
            return


def _bye(why: str) -> None:
    try:
        print(f"[lease] {S['sid'] or '服务'} 收工（{why}）", flush=True)
    except (OSError, ValueError):
        pass
    stop = S["stop"]
    if callable(stop):
        try:
            threading.Thread(target=stop, daemon=True).start()
            time.sleep(0.8)
        except Exception:                       # noqa: BLE001
            pass
    os._exit(0)
