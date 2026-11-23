#!/usr/bin/env python3
"""Token 价格追踪（:8776）—— 大模型 API / 套餐 / 本地部署 三维度成本追踪。

口袋（pocket）中台里的一个插件，代码独立成仓库，中台只管「怎么起」和「怎么打开」。
纯标准库，离线可用；联网只在 `--snapshot` / `llmcost_leaderboard.py` 那几步。

数据在数据目录（不是代码目录）里，按这个顺序找：
    1. 环境变量 LLMCOST_DIR
    2. ~/.pocket-llmcost

    data/api_prices.csv      API 按量价（带币种 / 峰谷 / 促销 / 缓存价 / 一手来源）
    data/plans.csv           订阅套餐（计费单位 + 三档系数 + 限额 + 活动到期）
    data/local_rigs.csv      本地硬件（采购价 / 折旧 / 功耗 / tok/s / 利用率）
    data/sources.json        12 个交叉校验源（开源价格库、社区追踪、价格日报）
    data/leaderboard.csv     LMArena 榜单（模型天梯榜用，llmcost_leaderboard.py 生成）
    data/snapshots/          每天一份主表快照，用来算调价 diff
    out/                     报告与独立 SVG（跑 --snapshot 才生成）

第一次跑会把仓库里的 `seed/` 拷进数据目录，所以开出来不是空表。

启动：python3 llmcost.py --serve --no-open [--port 8776]
其它：--snapshot（落看板与报告） / --json（打包结果打到 stdout） / --version
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import traceback
import urllib.parse
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import lease
import pgkit

BASE = Path(__file__).resolve().parent
UI_FILE = BASE / "llmcost_ui.html"
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

import llmcost_core as core   # noqa: E402
import llmcost_leaderboard as lbmod   # noqa: E402

DEFAULT_PORT = 8776
CACHE_TTL = 180.0             # 秒：算一遍 0.1 秒，但没必要每个请求都算

_STATE: dict = {"at": 0.0, "payload": None, "error": ""}
_LOCK = threading.Lock()


def version() -> str:
    """版本号只写一处：plugin.json。中台按它判断要不要提示更新。"""
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugin.json"),
                  encoding="utf-8") as f:
            return str(json.load(f).get("version") or "0.0.0")
    except (OSError, ValueError):
        return "0.0.0"


def _ui_fp() -> str:
    """界面文件的指纹（mtime + 字节数）。

    已经打开的标签页不会自己变 —— 前端拿这个值比对，发现服务端换了界面就
    带着当前页签重载。只 stat 一次，不读文件，轮询再密也不心疼。
    """
    try:
        st = UI_FILE.stat()
        return "%x.%x" % (int(st.st_mtime), st.st_size)
    except OSError:
        return "0"


# ---------------------------------------------------------------- 数据打包

def _events(d: dict) -> list[dict]:
    """本地已知事件 + LLMTracker 外部 changelog + 本地快照 diff，合成一张表。"""
    rows: list[dict] = []
    tl = d.get("timeline") or {}
    for e in tl.get("events") or []:
        rows.append({"date": e.get("date") or "", "model": e.get("model") or "",
                     "type": e.get("type") or "", "detail": e.get("detail") or "",
                     "src": "本地登记", "url": e.get("source_url") or ""})
    cn = {"new_model": "新增", "price_change": "调价", "removed": "下线",
          "updated": "更新", "deprecated": "弃用"}
    for e in tl.get("external_events") or []:
        rows.append({"date": str(e.get("generated_at") or "")[:10],
                     "model": e.get("model_id") or "",
                     "type": cn.get(e.get("change_type") or "", e.get("change_type") or ""),
                     "detail": "LLMTracker 每 6 小时的 changelog", "src": "LLMTracker",
                     "url": "https://github.com/MrUnreal/LLMTracker"})
    for c in d.get("changes") or []:
        rows.append({"date": c.get("at") or "", "model": c.get("model") or "",
                     "type": c.get("type") or "", "detail": c.get("detail") or "",
                     "src": "本地 diff", "url": ""})
    rows.sort(key=lambda r: (r["date"], r["src"]), reverse=True)
    return rows


def _rig_rows(d: dict) -> list[dict]:
    out = []
    for r in d.get("rigs") or []:
        util = core.num(r.get("utilization"), 0.3) or 0.3
        out.append({
            "rig": r.get("rig"), "model": r.get("model"), "quant": r.get("quant"),
            "hardware": core.num(r.get("hardware_cny"), 0) or 0,
            "years": core.num(r.get("depreciation_years"), 3) or 3,
            "power": core.num(r.get("power_w"), 0) or 0,
            "kwh": core.num(r.get("electricity_cny_kwh"), 0.55) or 0.55,
            "tok_s": core.num(r.get("tok_s"), 0) or 0,
            "util": util,
            "cost": core.local_cost(r, util),
            "cost_full": core.local_cost(r, 1.0),
            "url": r.get("source_url") or "", "at": r.get("verified_at") or "",
            "kind": r.get("source_type") or "", "note": r.get("note") or "",
        })
    out.sort(key=lambda r: (r["cost"] is None, r["cost"] or 0))
    return out


def _crosses(crosses: list) -> list[dict]:
    out = []
    today = core.TODAY
    for p, inc in crosses or []:
        promo = p.get("promo_until") or ""
        out.append({
            "plan": p.get("plan"), "platform": p.get("platform"),
            "monthly": p.get("monthly_cny"), "cny_per_1m": p.get("cny_per_1m"),
            "break_even": int(inc), "limit_5h": p.get("limit_5h") or "",
            "promo": promo, "expired": bool(promo and promo < today),
        })
    out.sort(key=lambda x: x["cny_per_1m"] or 9e9)
    return out


# 深色模式换色：图是核心画的，配色写死在 SVG 里（它本来是给静态看板用的）。
# 这里只换「背景 / 文字 / 网格」这些主题中性色，状态色（红绿蓝紫）保持原样。
_DARK_MAP = {
    "background:#fff": "background:transparent",
    # 规则线 / 底色
    "#e6e2d8": "#2c2e32", "#f1eee6": "#24262a", "#eef2f6": "#2c2e32",
    "#f2f5f8": "#24262a", "#f4f7fa": "#24262a", "#e8edf2": "#2c2e32",
    # 文字
    "#17191b": "#ecebe6", "#3f454c": "#b9bfc7", "#8a9098": "#868d95",
    "#8692a0": "#868d95", "#9aa1a6": "#868d95",
    # 主色 / 条形
    "#a33a26": "#d9785f", "#3a3f45": "#b7bdc5",
    "stroke=\"#fff\"": "stroke=\"#191b1e\"", "#fffdf9": "#191b1e",
    # 语义色
    "#33536e": "#7ea7cd", "#3f6b53": "#79b795", "#8a6a4e": "#c3a084",
    "#5c5470": "#a79ec2", "#2f6b70": "#7bb8bd", "#6b6f76": "#9aa1a8",
    # 平台全景的 15 个模型色（暗底要提亮，否则中低明度色糊成一片）
    "#7a6a2f": "#c4ae63", "#2f6b73": "#6fb6bd", "#8c4a5f": "#cf8fa4",
    "#4a6b3a": "#8dbb76", "#6b5a8a": "#ab9ac8", "#a06a2f": "#d7a267",
    "#3a5a8a": "#86a9d6", "#7b4a3a": "#c49584", "#4f6b6b": "#8fb5b5",
    "#8a5a7a": "#c78fae",
    # 官方线的纸色外描边：暗色下要跟卡片底一致，否则是一圈亮线
    "#fbf9f3": "#191b1e",
    "#94706a": "#c39b95", "#8d6417": "#cfa257", "#9c6b2f": "#c98f52",
    "#6a5583": "#a894c6", "#b98a3e": "#c9a05a", "#c9a99c": "#8a6a60",
    # 1 元购买力的墨色梯度（暗底反相）
    "#2c3136": "#dcdad4", "#4a4f55": "#a8a6a0", "#5b6066": "#8e8c86",
    "#6c7177": "#787670", "#7d8288": "#64625d",
}


def darkify(svg: str) -> str:
    for a, b in _DARK_MAP.items():
        svg = svg.replace(a, b)
    return svg


def _snapshot(d: dict, api: list[dict], plan_x: list[dict], pano: dict) -> dict:
    """工作台那张「Token 价格追踪」卡的同源数据。

    工作台是直接读 out/accuracy.json 自己算五个数字的，这里从同一份 payload 重算一遍。
    故意保持同一套字段名（cheapest / best_plan / counts / history / platforms），
    两边对不上时一眼就能看出是快照旧了还是算法变了。
    """
    hist = d.get("history") or {}
    hs = hist.get("summary") or {}
    moves = sorted(hist.get("changes") or [], key=lambda c: -abs(c.get("pct") or 0))
    ps = pano.get("summary") or {}
    pool = [r for r in api if r.get("output_cny")]
    std = [r for r in pool if (r.get("price_kind") or "standard") == "standard"]
    cheap = min(std or pool, key=lambda r: r["output_cny"]) if (std or pool) else None
    bp = next((x for x in plan_x if not x.get("expired")), plan_x[0] if plan_x else None)
    conf = []
    for r in api:
        for c in (r.get("conflicts") or [])[:1]:
            conf.append({"name": r.get("display") or r.get("model") or "",
                         "provider": r.get("provider") or "",
                         "metric": c.get("metric") or "",
                         "rel": round(float(c.get("rel") or 0) * 100)})
    return {
        "at": str(d.get("data_date") or "")[:10],
        "n_api": len(api), "n_plans": len(d.get("plans") or []),
        "n_rigs": len(d.get("rigs") or []),
        "obs": int(d.get("observations_total") or 0),
        "n_sources": len(d.get("source_coverage") or {}),
        "counts": d.get("counts") or {},
        "cheapest": ({"name": cheap["display"], "cny": cheap["output_cny"],
                      "status": cheap.get("status")} if cheap else None),
        "best_plan": ({"name": bp.get("plan"), "platform": bp.get("platform"),
                       "cny": bp.get("cny_per_1m"), "monthly": bp.get("monthly"),
                       "break_even": bp.get("break_even"), "promo": bp.get("promo")}
                      if bp else None),
        "conflicts": conf[:4],
        "history": {"from": str(hs.get("span_from") or "")[:10],
                    "to": str(hs.get("span_to") or "")[:10],
                    "n_dates": hs.get("n_dates") or 0, "n_models": hs.get("n_models") or 0,
                    "n_changed": hs.get("n_changed") or 0,
                    "level_chg": round(float(hs.get("level_chg") or 0) * 100, 1),
                    "top": [{"name": c.get("display") or c.get("model") or "",
                             "pct": round(float(c.get("pct") or 0) * 100),
                             "date": str(c.get("date") or "")[:10]} for c in moves[:2]]},
        "platforms": {"n": ps.get("n_platforms") or 0,
                      "spread_max": ps.get("spread_max") or 0,
                      "spread_median": ps.get("spread_median") or 0},
    }


def build_payload(charts: bool = True) -> dict:
    t0 = time.time()
    d, crosses = core.compute(save=False)
    api = d["api"]
    # 输出价已统一成 CNY（USD×7.2，仅作可比换算），表里两列都给，省得来回算
    for r in api:
        r["age"] = core.days_old(r.get("verified_at"))
        r["status_cn"] = core.STATUS_CN.get(r["status"], r["status"])
    # 榜单先算：图表要拿它画「价格 × Elo」，而它自己只读 CSV，不占多少时间
    try:
        lb = lbmod.join_prices(api)
    except Exception as e:                           # noqa: BLE001
        lb = {"ready": False, "error": "%s: %s" % (type(e).__name__, e)}
    charts_map = {}
    if charts:
        charts_map, _ = core.render_charts(d, crosses, lb=lb)
        # 深色一套现算（45 KB 的差距，本地开无所谓，省得前端做滤镜糊掉字）
        charts_map.update({k + "_dark": darkify(v) for k, v in list(charts_map.items())})

    cheapest = min((r for r in api if r.get("output_cny")),
                   key=lambda r: r["output_cny"], default=None)
    cheapest_std = min((r for r in api if r.get("output_cny")
                        and (r.get("price_kind") or "standard") == "standard"),
                       key=lambda r: r["output_cny"], default=None)
    plan_x = _crosses(crosses)
    return {
        "ok": True,
        "meta": {
            "date": d["data_date"], "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ms": int((time.time() - t0) * 1000),
            "fx": d["fx_usd_cny"], "obs": d["observations_total"],
            "n_sources": len(d["source_coverage"]),
            "policy": d["policy"],
            "snapshots": [[n, c if isinstance(c, str) else "%d 条" % c]
                          for n, c in (d.get("snapshot_files") or [])],
            "root": core.ROOT,
            "changes": d.get("changes") or [],
        },
        "counts": d["counts"],
        "status_order": core.STATUS_ORDER,
        "status_cn": core.STATUS_CN,
        "status_color": core.STATUS_COLOR,
        "api": api,
        "plans": d["plans"],
        "rigs": _rig_rows(d),
        "aux": d.get("aux") or [],
        "sources": d["source_coverage"],
        "source_meta": {s["id"]: {"url": s.get("url"), "note": s.get("note"),
                                  "update": s.get("update")}
                        for s in core.load_sources()["sources"]},
        "events": _events(d),
        "crosses": plan_x,
        "timeline": {
            "dates": d["timeline"].get("dates") or [],
            "daily": d["timeline"].get("daily") or {},
            "series": d["timeline"].get("series") or [],
            "versions": d["timeline"].get("versions") or [],
            "cumulative": d["timeline"].get("cumulative") or [],
        },
        "history": d.get("history") or {},
        "panorama": d.get("panorama") or {},
        "snapshot": _snapshot(d, api, plan_x, d.get("panorama") or {}),
        "leaderboard": lb,
        "tasks": core.task_data(d),
        "charts": charts_map,
        "pick": {
            "cheapest": ({"display": cheapest["display"], "cny": cheapest["output_cny"],
                          "status": cheapest["status"]} if cheapest else None),
            "cheapest_std": ({"display": cheapest_std["display"],
                              "cny": cheapest_std["output_cny"],
                              "status": cheapest_std["status"]} if cheapest_std else None),
            "best_plan": (next((x for x in plan_x if not x["expired"]), plan_x[0] if plan_x else None)),
        },
    }


def cached_payload(force: bool = False) -> dict:
    """带 TTL 的缓存。并发的请求只算一次（_LOCK 里判时间戳）。"""
    with _LOCK:
        fresh = (_STATE["payload"] is not None
                 and time.time() - _STATE["at"] < CACHE_TTL)
        if fresh and not force:
            return _STATE["payload"]
        try:
            p = build_payload()
            _STATE.update({"at": time.time(), "payload": p, "error": ""})
            return p
        except Exception as e:                       # noqa: BLE001
            _STATE["error"] = "%s: %s" % (type(e).__name__, e)
            if _STATE["payload"]:                    # 算挂了也别把上次的结果弄丢
                return _STATE["payload"]
            raise


# ---------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    server_version = "llmcost/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):                  # 只留启动那几行，别把日志刷满
        pass

    # —— 小工具 ——
    def _send(self, code: int, body: bytes, ctype: str, cache: str = "no-store"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _text(self, s: str, code: int = 200):
        self._send(code, s.encode("utf-8"), "text/plain; charset=utf-8")

    # —— 路由 ——
    def do_GET(self):                                # noqa: N802
        if pgkit.route(self, "llmcost") or lease.route(self):
            return
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path in ("/", "/index.html"):
            try:
                html = UI_FILE.read_text(encoding="utf-8")
            except OSError as e:
                return self._text("界面文件缺失：%s" % e, 500)
            return self._send(200, pgkit.inject(lease.inject(html)).encode("utf-8"),
                              "text/html; charset=utf-8")
        if u.path == "/api/ping":
            return self._json({"ok": True, "app": "llmcost", "at": _STATE["at"],
                               "ui": _ui_fp(), "error": _STATE["error"]})
        if u.path == "/api/data":
            try:
                p = cached_payload(force=q.get("force", ["0"])[0] in ("1", "true"))
            except Exception as e:                   # noqa: BLE001
                return self._json({"ok": False, "error": "%s" % e}, 500)
            return self._json(p)
        if u.path == "/api/report":
            name = (q.get("name") or ["accuracy"])[0]
            f = {"accuracy": core.OUT + "/accuracy_report.md",
                 "tracking": core.OUT + "/tracking_report.md",
                 "changelog": core.OUT + "/changelog.md"}.get(name)
            if not f or not os.path.exists(f):
                return self._text("这份报告还没生成：跑一次 `python3 llmcost.py --snapshot`", 404)
            with open(f, encoding="utf-8") as fh:
                return self._text(fh.read())
        return self._text("没有这个地址", 404)

    def do_POST(self):                               # noqa: N802
        if pgkit.route(self, "llmcost") or lease.route(self):
            return
        u = urllib.parse.urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        if n:
            try:
                self.rfile.read(n)
            except OSError:
                pass
        if u.path == "/api/refresh":
            t0 = time.time()
            try:
                p = cached_payload(force=True)
            except Exception as e:                   # noqa: BLE001
                return self._json({"ok": False, "error": "%s" % e}, 500)
            return self._json({"ok": True, "ms": int((time.time() - t0) * 1000),
                               "meta": p["meta"], "counts": p["counts"]})
        return self._text("没有这个地址", 404)


def probe(port: int) -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/api/ping" % port,
                                    timeout=0.6) as r:
            return json.loads(r.read().decode("utf-8")).get("app") == "llmcost"
    except Exception:                                # noqa: BLE001
        return False


def serve(port: int = DEFAULT_PORT, open_browser: bool = True) -> int:
    global DEFAULT_PORT
    bound = None
    for p in range(port, port + 12):
        if probe(p):                                 # 已经在跑：直接开页面
            print("Token 价格追踪已经在 %d 跑着了" % p)
            if open_browser:
                webbrowser.open("http://127.0.0.1:%d/" % p)
            return 0
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", p), Handler)
            bound = p
            break
        except OSError:
            continue
    if not bound:
        print("端口 %d–%d 都被占了，起不来" % (port, port + 11))
        return 1
    DEFAULT_PORT = bound
    httpd.daemon_threads = True
    print("Token 价格追踪挂在 http://127.0.0.1:%d/ （数据 %s）" % (bound, core.ROOT))

    # 先把数算好再开页面，免得第一眼是空白；算挂了也不耽误服务起来
    def warm():
        try:
            cached_payload()
            print("首轮计算完成：%d 条观测" % (_STATE["payload"] or {}).get("meta", {})
                  .get("obs", 0))
        except Exception:                            # noqa: BLE001
            traceback.print_exc()
    threading.Thread(target=warm, daemon=True).start()
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open("http://127.0.0.1:%d/" % bound)).start()
    lease.install("llmcost", stop=httpd.shutdown)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n收到中断，退出")
    return 0


def snapshot() -> int:
    """把看板 / 8 张 SVG / 三份报告落一份到 out/（离线存档、发给别人看都行）。"""
    d, crosses = core.compute(save=True)
    _, files = core.chart(d, crosses)
    core.write_report(d, crosses)
    print("看板：%s" % os.path.join(core.OUT, "dashboard.html"))
    for p in files:
        print("  SVG：%s" % os.path.basename(p))
    print("报告：accuracy_report.md / tracking_report.md / changelog.md")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Token 价格追踪 · 大模型成本追踪")
    ap.add_argument("--serve", action="store_true", help="起 HTTP 服务（默认动作）")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--no-open", action="store_true", help="不自动开浏览器")
    ap.add_argument("--snapshot", action="store_true", help="落一份看板与报告到 out/")
    ap.add_argument("--json", action="store_true", help="把打包结果打到 stdout")
    ap.add_argument("--version", action="store_true", help="打印版本号（读同目录 plugin.json）")
    a = ap.parse_args(argv)
    if a.version:
        print(version())
        return 0
    if a.snapshot:
        return snapshot()
    if a.json:
        print(json.dumps(build_payload(charts=False), ensure_ascii=False, indent=1, default=str))
        return 0
    return serve(a.port, not a.no_open)


if __name__ == "__main__":
    sys.exit(main())
