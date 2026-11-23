"""插件页的公共外壳：一份 CSS + 一份 JS，服务端现挂。

这个文件是从口袋（pocket）的 `cuntu/pgkit.py` 拆出来的：Token 价格追踪单独
成仓库后，不能再指望口袋代码目录里的模块，所以壳、皮肤转发、卡片清单一起随
插件走。**改样式要改 `kit/shell.css`，不要在这里写内联样式。**

做三件事：
  1. `/__shell.css`、`/__shell.js`、`/__filter.*`：把 kit/ 下的文件发出去；
  2. `/__appearance.css`、`/__wall/*.jpg`：中台生成的皮肤与壁纸，这边只转发
     （生成逻辑只该有一份，在 pocket/appearance.py）；
  3. `/api/cards`：告诉中台这个插件有哪些卡、默认多大，供「钉到首页」用。

装在口袋里时读 `POCKET_ROOT`（或同目录的 paths.py）找皮肤；单独运行时找不到
就用 classic，页面本身不受影响。
"""

from __future__ import annotations

import json
import os
import urllib.parse
from pathlib import Path

KIT_DIR = Path(__file__).resolve().parent / "kit"

_ASSETS = {
    "/__shell.css": ("shell.css", "text/css; charset=utf-8"),
    "/__shell.js": ("shell.js", "application/javascript; charset=utf-8"),
    "/__filter.css": ("filter.css", "text/css; charset=utf-8"),
    "/__filter.js": ("filter.js", "application/javascript; charset=utf-8"),
}

# 注入到 </head> 前。顺序要紧：CSS 要在页面自己的 <style> 之后
# （同名变量才盖得住），JS 用 defer 等 DOM 就绪。
# 一律用相对地址：主页的反代把插件页挂在 /px/<插件>/ 下，
# 写成 /__shell.css 会去口袋根目录找（404），相对路径才会落到插件自己身上。
#
# 那段内联脚本必须排在最前面、且不能 defer：这五个页面里写的是
# `api('/api/state')` 这种带前导斜杠的地址，挂在反代下会打到口袋根目录去
# （404）。页面脚本自己做相对化要改二十多处、以后再写又忘，不如在 window 上
# 兜一次：以 / 开头的请求一律降成 ./，直接访问时解析结果不变。
_SHIM = (
    '<script>(function(){'
    'var f=window.fetch;'
    'if(f)window.fetch=function(u,o){try{'
    'if(typeof u==="string"&&u.charAt(0)==="/"&&u.charAt(1)!=="/")u="."+u;'
    '}catch(e){}return f.call(this,u,o)};'
    'var x=XMLHttpRequest.prototype.open;'
    'XMLHttpRequest.prototype.open=function(m,u){try{'
    'if(typeof u==="string"&&u.charAt(0)==="/"&&u.charAt(1)!=="/")u="."+u;'
    '}catch(e){}return x.call(this,m,u,arguments[2],arguments[3],arguments[4])};'
    '})();</script>\n'
)

_SNIPPET = (
    _SHIM
    + '<link rel="stylesheet" href="__shell.css">\n'
    + '<link rel="stylesheet" href="__filter.css">\n'
    # filter.js 不能 defer：页面里是 parse 到脚本就立刻 FLT.mount(...)，
    # defer 要等整页解析完才执行，那会儿页面脚本早跑过了，FLT 还是 undefined。
    # 本地小文件，阻塞几毫秒换「随取随用」，值。
    + '<script src="__filter.js"></script>\n'
    + '<script src="__shell.js" defer></script>\n'
)


# ---------------------------------------------------------------- 皮肤（2026-11-22）
# 皮肤和强调色由工作台那边的设置面板写入 <数据根>/_工作台/appearance.json，
# 同目录生成好 appearance.css。**这里只当转发者**：
#   读 json → 把 data-skin 挂到 <html>；发 css → 原样吐文件字节。
# 不在这边重新生成，因为生成逻辑只能有一份（在 pocket/appearance.py），
# 两边各算一遍迟早分叉 —— 当初五个页面配色分家就是这么来的。
APPEARANCE_DIR = "_工作台"
APPEARANCE_JSON = "appearance.json"
APPEARANCE_CSS = "appearance.css"

# 壁纸（2026-11-22 晚）：真源在 pocket/appearance.py，这里只照着认名字 ——
# 白名单必须跟那边 PRESET_BGS 一致，否则插件页会 404 而主站正常（很难查）。
WALL_DIR = "wallpapers"
WALL_KEYS = ("dawn", "mist", "glass", "dusk", "moss", "graphite", "custom")
SKIN_DEFAULT_BG = {"classic": "", "g1": "dawn", "g2": "mist", "g3": "glass"}


def _pocket_root() -> Path | None:
    """找中台的数据根。找不到就返回 None（= 这插件是单独跑的，不套皮肤）。

    顺序：POCKET_ROOT 环境变量 → 同目录 paths.py（装在口袋里时才有）→
    从数据目录往上三级找 `_工作台/appearance.json` → 猜 ~/Documents/AI项目。
    最后那步只为兼容老装机，猜不到就不猜 —— 硬编码别人的目录，换个用户就失效。
    """
    env = (os.environ.get("POCKET_ROOT") or "").strip()
    if env:
        return Path(os.path.expanduser(env))
    try:
        import paths                                    # noqa: PLC0415
        return Path(paths.data_root())
    except Exception:                                   # noqa: BLE001
        pass

    start = (os.environ.get("LLMCOST_DIR") or "").strip()
    if start:
        p = Path(os.path.expanduser(start))
        for _ in range(4):                              # 13-算价 → 根 → 上两级
            if (p / APPEARANCE_DIR / APPEARANCE_JSON).exists():
                return p
            if p.parent == p:
                break
            p = p.parent

    guess = Path.home() / "Documents" / "AI项目"
    if (guess / APPEARANCE_DIR).is_dir():
        return guess
    return None


def _appearance_paths():
    root = _pocket_root()
    if root is None:
        return None, None
    d = Path(root) / APPEARANCE_DIR
    return d / APPEARANCE_JSON, d / APPEARANCE_CSS


def appearance_settings() -> dict:
    """读设置。读不到就返回 classic（= 完全不动，页面还是它本来的样子）。"""
    js, _ = _appearance_paths()
    if js is None:
        return {"skin": "classic", "accent": ""}
    try:
        data = json.loads(js.read_text(encoding="utf-8"))
        skin = str((data or {}).get("skin") or "classic")
        accent = str((data or {}).get("accent") or "")
    except (OSError, ValueError):
        skin, accent = "classic", ""
    if skin not in ("classic", "g1", "g2", "g3"):
        skin = "classic"
    return {"skin": skin, "accent": accent}


def _appearance_snippet() -> str:
    """<link> + 一行内联脚本。

    脚本必须是内联同步的，不能 defer、更不能 fetch：皮肤决定底色和圆角，
    晚一帧就是一次白闪（跟工作台 <head> 里那段主题脚本同一个理由）。
    在内联脚本里只做一件事 —— 挂属性，具体规则全在 css 里。
    """
    a = appearance_settings()
    return (
        '<link rel="stylesheet" href="__appearance.css">\n'
        '<script>(function(){document.documentElement.dataset.skin='
        + json.dumps(a["skin"]) + ';})();</script>\n'
    )


def _appearance_bg_bytes() -> bytes:
    """老路由：当前生效的那张壁纸（兼容还在跑旧 CSS 的页面）。

    不存在就返回空（路由给 404）—— CSS 里 --wall 本来就是可选层，
    没有它整套样式仍然是纯渐变，页面不会花。"""
    js_path, _ = _appearance_paths()   # 返回的是两个文件路径，壁纸跟它们同目录
    if js_path is None:
        return b""
    try:
        data = json.loads(js_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    skin = str((data or {}).get("skin") or "classic")
    bg = str((data or {}).get("bg") or "auto")
    if bg == "auto":
        bg = SKIN_DEFAULT_BG.get(skin, "")
    if not bg:
        return b""
    try:
        return (js_path.parent / WALL_DIR / (bg + ".jpg")).read_bytes()
    except OSError:
        return b""


def _wall_bytes(name: str) -> bytes:
    """按 key 取壁纸。key 只认预设 + custom（挡 ../ 这类拼串）。"""
    if name not in WALL_KEYS:
        return b""
    js_path, _ = _appearance_paths()
    if js_path is None:
        return b""
    try:
        return (js_path.parent / WALL_DIR / (name + ".jpg")).read_bytes()
    except OSError:
        return b""


def _appearance_css_bytes() -> bytes:
    _, css = _appearance_paths()
    if css is None:
        return b"/* standalone: no appearance.css */\n"
    try:
        return css.read_bytes()
    except OSError:
        # 还没有设置过：给一份空样式，别让页面 404（404 会在控制台留红字）
        return b"/* appearance.css not generated yet */\n"

# 每个插件页里有哪些卡：id 与页面上的 data-card 一一对应。
# (id, 名字, 默认几列, 默认几行) —— 行 = 56px + 16 间距，6 行约 416px。
#
# 巡检（inspect）2026-11-21 从这里撤掉：工作台 ?v=ops 才是它唯一的脸，
# 8774 不再有自己的页面（/ 已经 302 回工作台），它的卡也就不该出现在
# 主页「＋插件卡片」的清单里 —— 否则能 pin 出一张只会跳走的空卡。
CARDS = {
    # 页面上的 data-card 与这里的 id 一一对应。w/h 必须和 llmcost_ui.html 里的
    # data-w/data-h 逐字一致：这里决定钉到中台首页后的格子大小，页面里决定插件
    # 自己怎么排；两处不一致就会出现「钉过去被裁一半」——改尺寸时两边一起改。
    "llmcost": [
        ("verdict", "本轮结论", 2, 6),
        ("snapshot", "价格快照", 2, 6),
        ("stats", "数据规模", 4, 3),
        ("ladder", "模型天梯榜", 4, 10),
        ("value", "价格与实力", 4, 11),
        ("trend", "价格走势", 4, 14),
        ("level", "全盘水位", 4, 11),
        ("moves", "调价日志", 2, 5),
        ("matrix", "月度价格矩阵", 2, 9),
        ("apitable", "API 价目", 4, 10),
        ("apichart", "API 输出价排名", 4, 12),
        ("panotable", "模型 × 平台", 2, 11),
        ("platrank", "平台排行", 2, 11),
        ("plans", "订阅套餐", 4, 7),
        ("local", "本地部署", 4, 9),
        ("tasks", "任务换算", 4, 7),
        ("verify", "数据校验", 4, 9),
        ("timeline", "调价事件", 4, 8),
    ],
}


def cards_payload(pid: str) -> dict:
    rows = CARDS.get(pid) or []
    return {"ok": True, "app": pid,
            "cards": [{"id": c[0], "name": c[1], "w": c[2], "h": c[3]} for c in rows]}


def route(h, pid: str = "") -> bool:
    """处理 /__shell.css、/__shell.js、/__filter.css、/__filter.js、/api/cards；
    不是这些就返回 False。

    直接写 wfile，不依赖各服务自己那套 _send / _bytes（五个服务的签名不一样，
    硬套要写五遍 if，还要跟着它们改）。
    """
    try:
        path = urllib.parse.urlparse(getattr(h, "path", "") or "").path
    except Exception:                                   # noqa: BLE001
        return False

    if path == "/api/cards":
        return _emit(h, 200, json.dumps(cards_payload(pid), ensure_ascii=False).encode("utf-8"),
                     "application/json; charset=utf-8")

    # 皮肤样式：由工作台生成，这边原样转发（见上面「皮肤」那段注释）
    if path == "/__appearance.css":
        return _emit(h, 200, _appearance_css_bytes(),
                     "text/css; charset=utf-8", cache="no-cache")

    # 皮肤壁纸。能缓存一天：每张按 key 固定文件名，换图会换 key，
    # 自定义那张靠前端加 ?v= 破缓存。
    if path == "/__appearance-bg.jpg":
        body = _appearance_bg_bytes()
        if body:
            return _emit(h, 200, body, "image/jpeg", cache="public, max-age=86400")
        return _emit(h, 404, b"no wallpaper", "text/plain; charset=utf-8")

    if path.startswith("/__wall/") and path.endswith(".jpg"):
        body = _wall_bytes(path[len("/__wall/"):-4])
        if body:
            return _emit(h, 200, body, "image/jpeg", cache="public, max-age=86400")
        return _emit(h, 404, b"no wallpaper", "text/plain; charset=utf-8")

    asset = _ASSETS.get(path)
    if not asset:
        return False
    name, ctype = asset
    try:
        body = (KIT_DIR / name).read_bytes()
    except OSError:
        return _emit(h, 404, b"shell asset missing", "text/plain; charset=utf-8")
    # no-cache：改完 CSS 刷新就见效，别让浏览器拿旧的
    return _emit(h, 200, body, ctype, cache="no-cache")


def _emit(h, code: int, body: bytes, ctype: str, cache: str = "no-store") -> bool:
    try:
        h.send_response(code)
        h.send_header("Content-Type", ctype)
        h.send_header("Content-Length", str(len(body)))
        h.send_header("Cache-Control", cache)
        h.end_headers()
        if getattr(h, "command", "GET") != "HEAD":
            h.wfile.write(body)
    except (BrokenPipeError, ConnectionResetError):
        pass
    return True


def inject(html: str) -> str:
    """把公共壳 + 皮肤挂到页面里。找不到 </head> 就塞到最前面（旧页面也不至于白屏）。

    皮肤排在壳之后：同样是 `:root[data-theme=...]` 这一档的规则，
    后写的赢，皮肤必须压得住 shell.css 里那套默认值。
    """
    snip = _SNIPPET + _appearance_snippet()
    low = html.lower()
    i = low.rfind("</head>")
    if i >= 0:
        return html[:i] + snip + html[i:]
    return snip + html
