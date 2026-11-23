#!/usr/bin/env python3
"""发布前自检：站点所有 html 里的本地 href/src 是否都能找到对应文件。

只查本地相对引用，跳过 http(s)、mailto、data:、以及纯锚点。
发现断链退出码 1，publish.sh 会因此中止。
"""
import pathlib
import re
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKIP_DIRS = {"build", ".git", "node_modules", "__pycache__", ".preview"}
# 脚本/样式里的 src="..." 是拼出来的（模板串、字符串相加），不是真实引用
NON_HTML = re.compile(r"<(script|style)\b[\s\S]*?</\1>", re.I)


def main():
    pages = sorted(p for p in ROOT.rglob("*.html")
                   if not (set(p.parts) & SKIP_DIRS) and not p.name.startswith("._"))
    bad, n = [], 0
    for p in pages:
        raw = p.read_text(encoding="utf-8", errors="ignore")
        html = NON_HTML.sub("", raw)
        # 前面必须是空白：否则 data-src="aa" 里的 src="aa" 会被当成真实引用
        for m in re.finditer(r'(?<=[\s"\'])(?:href|src)="([^"#?]+)"', html):
            u = m.group(1).strip()
            if not u or u.startswith(("http://", "https://", "//", "mailto:", "data:", "javascript:")):
                continue
            if "${" in u or "' +" in u or '"+' in u:      # JS 拼接的占位
                continue
            n += 1
            # 中文文件名在 href 里是百分号编码的，找文件前要先解回来
            u = urllib.parse.unquote(u)
            if not (p.parent / u).resolve().exists():
                bad.append("%s -> %s" % (p.relative_to(ROOT), u))
    print("页面 %d 个，本地引用 %d 条，断链 %d 条" % (len(pages), n, len(bad)))
    if bad:
        for b in bad[:20]:
            print("  ✗", b)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
