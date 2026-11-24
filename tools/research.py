#!/usr/bin/env python3
"""研究条目流水线。四个动作：

    python3 tools/research.py sync            扫 inbox，登记新条目 → 出占位页 → 刷看板
    python3 tools/research.py build           只重建页面（改了样式/模板后用）
    python3 tools/research.py approve <slug>  把 draft.md 定稿上线
    python3 tools/research.py list            命令行看待审队列

状态不靠人填，由文件推导：
    published/ 里有 <slug>.md        → published（完稿，站点完整页）
    items/<slug>/draft.md 存在       → review   （AI 整理完，等审核）
    否则                             → stub     （只有标题与摘要，占位页）

「网页点按钮」的实现：review 条目在看板上渲染一个链接，点开是标题预填好的
GitHub issue（approve: <slug>），提交后由 .github/workflows/approve.yml 执行定稿。
不往浏览器里塞任何 token。
"""
import datetime
import html as H
import os
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RES = ROOT / "research"
ITEMS = RES / "items"
INBOX = RES / "inbox"
PUB = RES / "published"
TPL = RES / "templates" / "research.md"

# 投料区：目录名即站点板块。默认在仓库旁边的外置盘上，没挂载就退回仓库内 research/inbox。
DROPZONE = pathlib.Path(os.environ.get("RESEARCH_DROPZONE") or "/Volumes/AI仓库/AI行业研究")

# (文件夹名, channel, 站点页, 显示名)；文件夹比较时忽略大小写（exFAT 大小写不敏感）
SECTIONS = [
    ("基模",     "models",     "models.html",         "基模"),
    ("agent",    "agents",     "agents.html",         "Agent"),
    ("公司",     "companies",  "companies.html",      "公司"),
    ("硬件",     "hardware",   "hardware.html",       "硬件"),
    ("模板",     "templates",  "templates.html",      "模板"),
    ("应用",     "apps",       "apps.html",           "AI+行业"),
    # 原理与历史已合并成一页，两个文件夹都能收，指向同一页
    ("原理",     "principles", "principles.html",     "原理 · 历史"),
    ("历史",     "history",    "principles.html#e1",  "原理 · 历史"),
    ("本地部署", "local",      "local.html",          "本地部署"),
    ("实例",     "cases",      "cases.html",          "实例"),
    ("_其他",    "misc",       "",                    "其他"),
]
SECTION_ALIAS = {"基础模型": "models", "智能体": "agents", "agents": "agents",
                 "models": "models", "apps": "apps", "cases": "cases",
                 "AI+行业": "apps", "行业": "apps"}
CHANNEL_LABEL = {c: label for _, c, _, label in SECTIONS}
CHANNEL_PAGE = {c: page for _, c, page, _ in SECTIONS}
CHANNEL_LABEL[""] = ""

OWNER_REPO = os.environ.get("GH_SLUG") or "blackinkvc/pocket-llmcost"
GH_BASE = "https://github.com/" + OWNER_REPO

NAV = [
    ("index.html", "首页"), ("models.html", "基模"), ("agents.html", "Agent"),
    ("companies.html", "公司"), ("hardware.html", "硬件"), ("templates.html", "模板"),
    ("apps.html", "AI+行业"), ("principles.html", "原理 · 历史"), ("local.html", "本地部署"),
    ("cases.html", "实例"), ("research/index.html", "研究"),
    ("llmcost/index.html", "AI 天梯榜 &amp; 价格追踪"),
]

ST_RANK = {"published": 0, "review": 1, "stub": 2}
ST_LABEL = {"published": "已上线", "review": "待审核", "stub": "整理中"}
TODAY = datetime.date.today().isoformat()

JUNK_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}


def is_junk(name):
    """exFAT/外置盘上 macOS 会生成 ._xxx 伴生文件，内容不是文本，别当资料读。"""
    return name.startswith("._") or name in JUNK_NAMES


# ───────────────────────── meta.yml（极简 YAML，不引第三方库） ─────────────────────────
def parse_meta(path):
    d = {}
    if not path.exists():
        return d
    key = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if re.match(r"^\s+-\s+", line) and key:
            d.setdefault(key, []).append(line.split("-", 1)[1].strip())
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            key, val = key.strip(), val.strip()
            if val.startswith("[") and val.endswith("]"):
                d[key] = [x.strip().strip("\"'") for x in val[1:-1].split(",") if x.strip()]
            elif val == "":
                d[key] = []
            else:
                d[key] = val.strip("\"'")
    return d


def dump_meta(d, path):
    order = ["title", "summary", "channel", "tags", "origin", "created_at", "draft_at",
             "published_at", "sources", "note"]
    lines = []
    for k in order:
        if k not in d or d[k] in (None, "", []):
            continue
        v = d[k]
        if isinstance(v, list):
            lines.append("%s: [%s]" % (k, ", ".join(str(x) for x in v)))
        else:
            lines.append("%s: %s" % (k, v))
    for k, v in d.items():
        if k not in order and v not in (None, "", []):
            lines.append("%s: %s" % (k, v))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ───────────────────────── 从原始资料里抽标题与摘要 ─────────────────────────
def first_heading(text):
    for line in text.splitlines():
        m = re.match(r"^#\s+(.+)", line.strip())
        if m:
            return m.group(1).strip()
    return None


def first_para(text):
    for block in re.split(r"\n\s*\n", text):
        b = block.strip()
        if not b or b.startswith(("#", ">", "```", "-", "*", "|", "!")) or re.match(r"^\d+\.", b):
            continue
        return re.sub(r"[*_`\[\]]|\([^)]*\)", "", b).strip()
    return ""


def read_text_of(p):
    if p.is_dir():
        for cand in sorted(p.rglob("*.md")):
            if is_junk(cand.name):
                continue
            return cand.read_text(encoding="utf-8", errors="ignore")
        for cand in sorted(p.rglob("*.txt")):
            if is_junk(cand.name):
                continue
            return cand.read_text(encoding="utf-8", errors="ignore")
        for cand in sorted(p.rglob("*.htm*")):
            if not is_junk(cand.name):
                return html_title_summary(cand)[1]
        return ""
    if p.suffix.lower() in (".md", ".markdown", ".txt"):
        return p.read_text(encoding="utf-8", errors="ignore")
    return ""


def strip_tags(s):
    s = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", H.unescape(s)).strip()


def html_title_summary(p):
    """HTML 投料也要能抽出像样的标题与摘要，否则占位页只有文件名。"""
    s = p.read_text(encoding="utf-8", errors="ignore")
    t = re.search(r"<title[^>]*>([\s\S]*?)</title>", s, re.I)
    title = re.sub(r"\s+", " ", H.unescape(strip_tags(t.group(1)))).strip() if t else None
    summary = ""
    for m in re.finditer(r"<p[^>]*>([\s\S]*?)</p>", s, re.I):
        cand = strip_tags(m.group(1))
        if len(cand) > 40:
            summary = cand
            break
    if not summary:
        body = re.sub(r"<(header|nav|h1)[\s\S]*?</\1>", " ", s, flags=re.I)
        summary = strip_tags(body)[:120]
    if title and summary.startswith(title):        # 兜底路径常把标题再抄一遍
        summary = summary[len(title):].lstrip(" ·-|/／").strip()
    return title, summary


def trim(s, n=88):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[:n].rstrip() + "…"


# ───────────────────────── slug ─────────────────────────
def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if len(s) >= 5:
        return s[:48].strip("-")
    return None


def unique_slug(name, taken):
    s = slugify(name)
    if s and s not in taken:
        return s
    if s:
        i = 2
        while "%s-%d" % (s, i) in taken:
            i += 1
        return "%s-%d" % (s, i)
    base = "r-" + TODAY.replace("-", "")
    i = 1
    while "%s-%02d" % (base, i) in taken:
        i += 1
    return "%s-%02d" % (base, i)


# ───────────────────────── markdown → html（够模板用，不追求完整） ─────────────────────────
def inline(t):
    t = H.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" rel="noopener">\1</a>', t)
    t = re.sub(r"(?<![=\"'])(https?://[^\s<)]+)", r'<a href="\1" rel="noopener">\1</a>', t)
    return t


def md_to_html(text):
    out, lines, i = [], text.splitlines(), 0
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if s.startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(H.escape(lines[i]))
                i += 1
            out.append("<pre><code>%s</code></pre>" % "\n".join(buf))
            i += 1
            continue
        if not s:
            i += 1
            continue
        if re.match(r"^(-{3,}|\*{3,})$", s):
            out.append("<hr>")
            i += 1
            continue
        m = re.match(r"^(#{2,4})\s+(.+)", s)
        if m:
            lv = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (lv, inline(m.group(2)), lv))
            i += 1
            continue
        if s.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(inline(lines[i].strip().lstrip(">").strip()))
                i += 1
            out.append("<blockquote>%s</blockquote>" % "<br>".join(buf))
            continue
        if re.match(r"^[-*]\s+", s):
            buf = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                buf.append("<li>%s</li>" % inline(re.sub(r"^\s*[-*]\s+", "", lines[i])))
                i += 1
            out.append("<ul>%s</ul>" % "".join(buf))
            continue
        if s.startswith("|"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                buf.append(lines[i].strip())
                i += 1
            def cells(row):
                return [c.strip() for c in row.strip().strip("|").split("|")]
            if len(buf) >= 2 and re.match(r"^\|?[\s:|-]+\|?$", buf[1]):
                head = cells(buf[0])
                body = [cells(r) for r in buf[2:]]
                th = "".join("<th>%s</th>" % inline(c) for c in head)
                trs = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c) for c in row)
                              for row in body)
                out.append('<div class="md-table"><table><thead><tr>%s</tr></thead>'
                           '<tbody>%s</tbody></table></div>' % (th, trs))
            else:
                out.append("<p>%s</p>" % inline(" ".join(buf)))
            continue
        if re.match(r"^\d+\.\s+", s):
            buf = []
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
                buf.append("<li>%s</li>" % inline(re.sub(r"^\s*\d+\.\s+", "", lines[i])))
                i += 1
            out.append("<ol>%s</ol>" % "".join(buf))
            continue
        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^(#{1,4}\s|[-*]\s|\d+\.\s|>|```|-{3,}|\|)", lines[i].strip()):
            buf.append(inline(lines[i].strip()))
            i += 1
        out.append("<p>%s</p>" % " ".join(buf))
    return "\n".join(out)


# ───────────────────────── 页面壳 ─────────────────────────
def nav_html(active, prefix="../"):
    parts = []
    for href, label in NAV:
        h = prefix + href
        cls = ' class="is-active"' if label == active else ""
        parts.append('<a%s href="%s">%s</a>' % (cls, h, label))
    return "\n      ".join(parts)


def shell(title, desc, body, active="研究", noindex=False, prefix="../"):
    robots = '<meta name="robots" content="noindex,follow">' if noindex else ""
    return """<!DOCTYPE html>
<!-- 生成物：由 tools/research.py 从 research/items 生成，手改会被覆盖 -->
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title>
<meta name="description" content="%s">
%s
<link rel="stylesheet" href="%sassets/css/site.css">
<link rel="stylesheet" href="assets/research.css">
</head>
<body>

<header class="topbar">
  <div class="topbar-in">
    <a class="brand" href="%sindex.html">
      <b>AI.TRACK</b><span class="sep">/</span><span class="sub">AI 发展监控台</span>
    </a>
    <nav class="mainnav">
      %s
    </nav>
    <div class="topbar-right">
      <span class="meta">%s</span>
      <a class="btn is-primary" href="%sresearch/status.html">研究看板</a>
    </div>
  </div>
</header>

<main class="rs-wrap">
%s
</main>

<footer class="rs-foot">
  <a href="%sresearch/index.html">研究总览</a>
  <a href="%sresearch/status.html">进度看板</a>
  <a href="inbox/README.md">怎么投料</a>
  <span>生成于 %s</span>
</footer>

</body>
</html>
""" % (H.escape(title), H.escape(desc), robots,
       prefix,                                  # site.css
       prefix,                                  # brand
       nav_html(active, prefix),
       TODAY,                                   # 顶栏日期
       prefix,                                  # 研究看板按钮
       body,
       prefix, prefix,                          # 页脚：研究总览 / 进度看板
       TODAY)                                   # 生成时间


# ───────────────────────── 条目状态 ─────────────────────────
# 外来的整篇 HTML 没做窄屏适配：引用来源里那 20 条长 URL 不能断行，
# 390px 下把页面撑宽 318px（原文件在手机上也一样，不是拷进来才坏的）。
# 只补一条断行规则，其余样式一概不动——改别人的版式，等于替他改稿。
FULLTEXT_PATCH = ('<style data-injected="fulltext">'
                  '@media(max-width:720px){'
                  'p,li,blockquote,td{overflow-wrap:anywhere}'
                  '}</style>')


def dress_fulltext(html, back=""):
    """给外来全文补两样东西：回站内的入口、窄屏下不撑破表格的规则。"""
    if back and '<div class="nav">' in html and back not in html:
        html = html.replace('<div class="nav">', '<div class="nav">' + back, 1)
    if 'data-injected="fulltext"' not in html and "</head>" in html:
        html = html.replace("</head>", FULLTEXT_PATCH + "</head>", 1)
    return html


def full_source(slug, meta):
    """整篇 HTML 的成品条目：meta 里写 full，指向已经写好的独立页面。

    路径先按仓库根目录解析（全文统一放在 content/<板块>/全文/，只存一份），
    找不到再退回条目自己的 raw/ 目录。
    """
    name = (meta.get("full") or "").strip()
    if not name:
        return None
    for p in (ROOT / name, ITEMS / slug / "raw" / name):
        if p.is_file():
            return p
    return None


def status_of(slug, meta=None):
    meta = meta or parse_meta(ITEMS / slug / "meta.yml")
    if full_source(slug, meta):
        return "published"
    if (PUB / ("%s.md" % slug)).exists():
        return "published"
    if (ITEMS / slug / "draft.md").exists():
        return "review"
    return "stub"


def raw_files(slug):
    d = ITEMS / slug / "raw"
    if not d.exists():
        return []
    return sorted(p for p in d.rglob("*") if p.is_file() and not is_junk(p.name))


def load_items():
    items = []
    if not ITEMS.exists():
        return items
    for d in sorted(ITEMS.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        meta = parse_meta(d / "meta.yml")
        raw = raw_files(d.name)
        items.append({
            "slug": d.name,
            "title": meta.get("title") or d.name,
            "summary": meta.get("summary") or "",
            "tags": meta.get("tags") or [],
            "channel": meta.get("channel") or "",
            "created_at": meta.get("created_at") or "",
            "draft_at": meta.get("draft_at") or "",
            "published_at": meta.get("published_at") or "",
            "note": meta.get("note") or "",
            "raw": raw,
            "full": full_source(d.name, meta),
            "status": status_of(d.name, meta),
        })
    items.sort(key=lambda x: (ST_RANK[x["status"]], x["created_at"] or "", x["title"]))
    return items


def approve_url(slug, title):
    from urllib.parse import quote
    t = quote("approve: %s" % slug)
    b = quote("审核通过《%s》。\n\n点 Submit 后由 Actions 定稿上线，关掉这个 issue 即可。\n\nslug: %s"
              % (title, slug))
    return "%s/issues/new?title=%s&body=%s" % (GH_BASE, t, b)


def channel_chip(ch, prefix="../", link=True):
    """板块标签。卡整张是 <a>，里面不能再套 <a>（浏览器会拆标签），所以卡片里传 link=False。"""
    label = CHANNEL_LABEL.get(ch or "", "")
    if not label:
        return ""
    page = CHANNEL_PAGE.get(ch or "")
    if page and link:
        return '<a class="rs-chip" href="%s%s">%s</a>' % (prefix, page, H.escape(label))
    return '<span class="rs-chip">%s</span>' % H.escape(label)


# ───────────────────────── 渲染：单条 ─────────────────────────
def render_item(it):
    st = it["status"]
    badge = '<span class="rs-badge is-%s">%s</span>' % (st, ST_LABEL[st])
    meta_bits = []
    if it["created_at"]:
        meta_bits.append("投料 %s" % it["created_at"])
    if it["draft_at"]:
        meta_bits.append("整理 %s" % it["draft_at"])
    if it["published_at"]:
        meta_bits.append("上线 %s" % it["published_at"])
    if it["raw"]:
        meta_bits.append("原始资料 %d 份" % len(it["raw"]))
    tags = "".join('<span class="rs-tag">%s</span>' % H.escape(t) for t in it["tags"])

    head = ['<header class="rs-head">',
            '<div class="rs-crumb"><a href="index.html">研究</a> / %s</div>' % H.escape(it["title"]),
            "<h1>%s</h1>" % H.escape(it["title"]),
            '<div class="rs-metabar">%s%s %s</div>' % (badge, channel_chip(it["channel"]),
                                                       '<span class="rs-sep">·</span>'.join(meta_bits)),
            '<div class="rs-tags">%s</div>' % tags,
            "</header>"]

    # 定稿页正文开头就是「一句话结论」，再放摘要框会重复一遍
    dup_lead = st == "published" and (PUB / ("%s.md" % it["slug"])).read_text(
        encoding="utf-8").lstrip().split("\n", 1)[-1].lstrip().startswith(">")
    if it["summary"] and not dup_lead:
        head.append('<p class="rs-summary">%s</p>' % H.escape(it["summary"]))

    if st == "published":
        body_md = (PUB / ("%s.md" % it["slug"])).read_text(encoding="utf-8")
        body_md = re.sub(r"^#\s+.+\n", "", body_md, count=1)
        art = ['<article class="rs-body">', md_to_html(body_md), "</article>"]
        if it["raw"]:
            art.append(render_raw_block(it))
    else:
        note = ("AI 已整理出草稿，正在等作者审核。" if st == "review"
                else "作者已投料，正在整理成标准稿。")
        art = ['<div class="rs-pending">',
               '<p class="rs-pending-t">%s</p>' % note,
               "<p>这里现在只有标题和摘要。完整内容包括：结论、关键事实、怎么做、反方与不确定处、来源。</p>",
               "</div>"]
        # 原件是网页时给个直达入口，否则读者点进来只能看到一段摘要
        html_raw = [p for p in it["raw"] if p.suffix.lower() in (".html", ".htm")]
        if html_raw:
            art.append('<p class="rs-rawopen">原件可以直接看：%s</p>' % "".join(
                '<a href="%s%s" target="_blank" rel="noopener">%s →</a>'
                % (raw_base(it), p.relative_to(ITEMS / it["slug"] / "raw").as_posix(),
                   H.escape(p.stem)) for p in html_raw))
        if it["raw"]:
            art.append(render_raw_block(it))

    return shell("%s · 研究 · AI.TRACK" % it["title"], it["summary"] or it["title"],
                 "\n".join(head + art), noindex=(st != "published"))


def raw_base(it):
    return "items/%s/raw/" % it["slug"]


def render_raw_block(it):
    lis = []
    for p in it["raw"]:
        rel = p.relative_to(ITEMS / it["slug"] / "raw").as_posix()
        if p.suffix.lower() in (".html", ".htm"):
            # HTML 原件本身就是网页，Pages 会直接当页面发出去，点开就能看
            name = ('<a class="rs-fn is-open" href="%s%s" target="_blank" rel="noopener">%s'
                    '<span class="rs-open">打开</span></a>' % (raw_base(it), rel, H.escape(p.name)))
        else:
            name = '<span class="rs-fn">%s</span>' % H.escape(p.name)
        lis.append('<li>%s<span class="rs-fs">%s</span></li>' % (name, human_size(p.stat().st_size)))
    lis = "".join(lis)
    return ('<section class="rs-raw"><h2>原始资料</h2>'
            '<ul class="rs-rawlist">%s</ul>'
            '<p class="rs-hint">原件在仓库里：<a href="%s/tree/main/research/items/%s/raw" rel="noopener">'
            'research/items/%s/raw</a></p></section>'
            % (lis, GH_BASE, it["slug"], it["slug"]))


def human_size(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return "%.0f %s" % (n, u) if u == "B" else "%.1f %s" % (n, u)
        n /= 1024.0
    return "%.1f TB" % n


# ───────────────────────── 渲染：总览 ─────────────────────────
def render_index(items):
    pub = [x for x in items if x["status"] == "published"]
    pend = [x for x in items if x["status"] != "published"]

    def card(it):
        st = it["status"]
        cls = "rs-card" + ("" if st == "published" else " is-pending")
        tags = "".join('<span class="rs-tag">%s</span>' % H.escape(t) for t in it["tags"][:4])
        return ('<a class="%s" href="%s.html">'
                '<div class="rs-card-top"><span class="rs-badge is-%s">%s</span>%s%s</div>'
                '<h2>%s</h2><p>%s</p></a>'
                % (cls, it["slug"], st, ST_LABEL[st],
                   channel_chip(it["channel"], link=False), tags,
                   H.escape(it["title"]), H.escape(it["summary"] or "（摘要待补）")))

    body = ['<header class="rs-head"><div class="rs-crumb">研究</div>',
            '<h1>研究</h1>',
            '<p class="rs-lead">自己做完、并且敢署名的一份份研究。'
            '已完成 %d 份，另有 %d 份在整理或待审——进度全在<a href="status.html">看板</a>上。</p></header>'
            % (len(pub), len(pend))]
    if pub:
        body.append('<section class="rs-sec"><h2 class="rs-sec-t">已完成（%d）</h2><div class="rs-grid">%s</div></section>'
                    % (len(pub), "".join(card(x) for x in pub)))
    if pend:
        body.append('<section class="rs-sec"><h2 class="rs-sec-t">整理中（%d）</h2>'
                    '<p class="rs-hint">这些标题是我已经在做、还没定稿的。点进去能看到摘要和已经收进来的原始资料。</p>'
                    '<div class="rs-grid">%s</div></section>' % (len(pend), "".join(card(x) for x in pend)))
    if not items:
        body.append('<div class="rs-empty">还没有登记任何研究。往投料区 <code>AI行业研究/&lt;板块&gt;/</code> '
                    '丢一个文件，跑 <code>python3 tools/research.py sync</code> 就有了。</div>')

    return shell("研究 · AI.TRACK",
                 "AI 研究的自有产出：已完成 %d 份，整理中 %d 份。每条都附结论、证据、反方观点与原始资料。"
                 % (len(pub), len(pend)),
                 "\n".join(body))


# ───────────────────────── 渲染：看板 ─────────────────────────
def render_status(items):
    n_pub = sum(1 for x in items if x["status"] == "published")
    n_rev = sum(1 for x in items if x["status"] == "review")
    n_stub = sum(1 for x in items if x["status"] == "stub")
    month = TODAY[:7]
    n_new = sum(1 for x in items if (x["created_at"] or "").startswith(month))

    kpis = [("本地积累", len(items), "条研究"), ("已上线", n_pub, "网友可读"),
            ("待审核", n_rev, "等你点头"), ("整理中", n_stub, "只有摘要"),
            ("本月新增", n_new, month.replace("-", " 年 ") + " 月")]
    kpi_html = "".join('<div class="rs-kpi"><b>%s</b><span>%s</span><em>%s</em></div>'
                       % (v, H.escape(k), H.escape(s)) for k, v, s in kpis)

    rows = []
    for it in items:
        st = it["status"]
        if st == "published":
            act = '<a class="rs-inline-btn" href="%s.html">阅读</a>' % it["slug"]
        elif st == "review":
            act = ('<a class="rs-inline-btn is-approve" href="%s" target="_blank" rel="noopener">通过审核</a>'
                   % H.escape(approve_url(it["slug"], it["title"])))
        else:
            act = '<span class="rs-muted">等待整理</span>'
        rows.append('<tr class="is-%s"><td><a href="%s.html">%s</a></td><td><span class="rs-badge is-%s">%s</span></td>'
                    '<td class="rs-col-sec">%s</td>'
                    '<td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
                    % (st, it["slug"], H.escape(it["title"]), st, ST_LABEL[st],
                       H.escape(CHANNEL_LABEL.get(it["channel"], "") or "—"),
                       "".join(H.escape(t) + " " for t in it["tags"][:3]) or "—",
                       it["created_at"] or "—", it["draft_at"] or "—", it["published_at"] or "—", act))

    body = ['<header class="rs-head"><div class="rs-crumb"><a href="index.html">研究</a> / 看板</div>',
            '<h1>研究进度看板</h1>',
            '<p class="rs-lead">这个页面公开我自己的一份「进度表」：本地攒了哪些研究、整理到哪一步、'
            '哪些已经上线。标「待审核」的是 AI 已经整理完、我还没点头的。</p></header>',
            '<section class="rs-kpis">%s</section>' % kpi_html]
    if rows:
        body.append('<section class="rs-sec"><div class="rs-tablewrap"><table class="rs-table">'
                    '<thead><tr><th>标题</th><th>状态</th><th>板块</th><th>标签</th><th>投料</th>'
                    '<th>整理</th><th>上线</th><th>操作</th></tr></thead>'
                    '<tbody>%s</tbody></table></div></section>' % "".join(rows))
    else:
        body.append('<div class="rs-empty">还没有条目。</div>')

    body.append('<section class="rs-sec rs-howto"><h2 class="rs-sec-t">这张表是怎么跑的</h2>'
                '<ol class="rs-steps">'
                '<li><b>投料</b>：把资料按板块丢进投料区 <code>AI行业研究/&lt;板块&gt;/</code>，跑 <code>sync</code> → 立刻出现「整理中」占位页。</li>'
                '<li><b>整理</b>：AI 按固定模板写出结论、证据、做法、反方观点，落到草稿。</li>'
                '<li><b>审核</b>：我点「通过审核」→ 定稿上线，状态从「待审核」变「已上线」。</li>'
                '</ol><p class="rs-hint">状态不是我手填的，是脚本按仓库里的文件推出来的：'
                '有定稿文件才算上线。<a href="%s/blob/main/tools/research.py" rel="noopener">看看实现</a>。</p></section>'
                % GH_BASE)

    return shell("研究进度看板 · AI.TRACK",
                 "公开的研究进度表：本地积累 %d 条，已上线 %d 条，待审核 %d 条，整理中 %d 条。"
                 % (len(items), n_pub, n_rev, n_stub),
                 "\n".join(body))


# ───────────────────────── 动作 ─────────────────────────
def build():
    RES.mkdir(parents=True, exist_ok=True)
    (RES / "assets" / "research").mkdir(parents=True, exist_ok=True)
    PUB.mkdir(parents=True, exist_ok=True)
    items = load_items()
    keep = {x["slug"] for x in items}
    for p in RES.glob("*.html"):
        if is_junk(p.name):
            continue
        if p.stem not in keep and p.stem not in ("index", "status"):
            p.unlink()
            print("  清理孤儿页 %s" % p.name)
    for it in items:
        out = RES / ("%s.html" % it["slug"])
        if it["full"]:
            # 已经写好的独立页面：原样拷过来，只往它的顶栏插一个回站内的入口。
            # 文件名保持原样——这类全文之间常常用文件名互链，改名就断。
            html = it["full"].read_text(encoding="utf-8")
            page = CHANNEL_PAGE.get(it["channel"]) or "index.html"
            back = ('<a href="../%s">← 回%s</a>'
                    % (page, H.escape(CHANNEL_LABEL.get(it["channel"], "站内"))))
            out.write_text(dress_fulltext(html, back), encoding="utf-8")
            print("  拷入全文 %s" % out.name)
            continue
        out.write_text(render_item(it), encoding="utf-8")
    (RES / "index.html").write_text(render_index(items), encoding="utf-8")
    (RES / "status.html").write_text(render_status(items), encoding="utf-8")
    print("研究 %d 条（上线 %d / 待审 %d / 整理中 %d）→ research/ 4 类页面已重建"
          % (len(items),
             sum(1 for x in items if x["status"] == "published"),
             sum(1 for x in items if x["status"] == "review"),
             sum(1 for x in items if x["status"] == "stub")))


def find_by_origin(origin):
    if not ITEMS.exists():
        return None
    for d in ITEMS.iterdir():
        if d.is_dir() and parse_meta(d / "meta.yml").get("origin") == origin:
            return d.name
    return None


def dropzone():
    """投料区根目录；没挂载就返回 None，退回仓库内 research/inbox。"""
    return DROPZONE if DROPZONE.is_dir() else None


def section_dirs(root):
    """把投料区的实际目录名映射成 channel。兼容大小写不敏感与旧目录名。"""
    have = {p.name.lower(): p for p in root.iterdir() if p.is_dir()}
    out, known = [], set()
    for name, ch, _page, _label in SECTIONS:
        p = have.get(name.lower())
        if p:
            out.append((p, ch))
            known.add(p.name.lower())
    known.add("_已收录")
    for key, p in sorted(have.items()):
        if key not in known and not p.name.startswith((".", "_")):
            out.append((p, SECTION_ALIAS.get(key, "misc")))
    return out


def collect_entries():
    """返回 ([(路径, channel, 所属板块目录)], 投料区说明)。"""
    dz = dropzone()
    if dz:
        entries = []
        for d, ch in section_dirs(dz):
            for p in sorted(d.iterdir()):
                if p.name.startswith((".", "_")):
                    continue
                entries.append((p, ch, d))
        return entries, "投料区 %s" % dz
    if INBOX.is_dir():
        return ([(p, "", INBOX) for p in sorted(INBOX.iterdir())
                 if not p.name.startswith(".") and p.name != "README.md"],
                "仓库内 research/inbox")
    return [], "没有投料区"


def sync():
    INBOX.mkdir(parents=True, exist_ok=True)
    ITEMS.mkdir(parents=True, exist_ok=True)
    entries, where = collect_entries()
    print("%s（%d 个待收）" % (where, len(entries)))
    taken = {d.name for d in ITEMS.iterdir() if d.is_dir()} if ITEMS.exists() else set()
    added = 0
    for p, ch, secdir in entries:
        if p.is_file() and p.stat().st_size > 20 * 1024 * 1024:
            print("  跳过（>20MB，压缩后再投）：%s" % p.name)
            continue
        existing = find_by_origin(p.name)
        slug = existing or unique_slug(p.stem if p.is_file() else p.name, taken)
        d = ITEMS / slug
        raw = d / "raw"
        raw.mkdir(parents=True, exist_ok=True)
        # 标题与摘要：HTML 单独解析，md/txt 走正文首段
        if p.is_file() and p.suffix.lower() in (".html", ".htm"):
            title, summary = html_title_summary(p)
        else:
            text = read_text_of(p)
            title = first_heading(text) if text else None
            summary = first_para(text)
        title = title or (p.stem if p.is_file() else p.name)
        meta_path = d / "meta.yml"
        meta = parse_meta(meta_path)
        meta.setdefault("title", title)
        if not meta.get("summary"):
            meta["summary"] = trim(summary) or "（摘要待补）"
        meta.setdefault("tags", [])
        if ch:
            meta["channel"] = ch
        meta["origin"] = p.name
        meta.setdefault("created_at", TODAY)
        # 先复制进仓库，再决定原件怎么处理
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and not is_junk(f.name):
                    target = raw / f.relative_to(p)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(f), str(target))
        else:
            shutil.copy2(str(p), str(raw / p.name))
        if secdir != INBOX:                       # 外置盘投料区：原件归档，投料区保持干净
            arch = secdir / "_已收录" / TODAY
            arch.mkdir(parents=True, exist_ok=True)
            dest = arch / p.name
            i = 2
            while dest.exists():
                dest = arch / ("%s-%d%s" % (p.stem, i, p.suffix))
                i += 1
            shutil.move(str(p), str(dest))
        elif p.is_dir():                          # 仓库内 inbox：保持旧行为，直接搬走
            shutil.rmtree(p, ignore_errors=True)
        else:
            p.unlink()
        meta["sources"] = len([x for x in raw.rglob("*") if x.is_file() and not is_junk(x.name)])
        dump_meta(meta, meta_path)
        taken.add(slug)
        added += 1
        print("  登记 %-30s [%s] ← %s" % (slug, CHANNEL_LABEL.get(ch, "其他") or "未分类", p.name))
    if added:
        print("新增 %d 条" % added)
    else:
        print("投料区没有新东西")
    build()


def approve(slug):
    d = ITEMS / slug
    if not d.is_dir():
        sys.exit("没有这个条目：%s" % slug)
    draft = d / "draft.md"
    if not draft.exists():
        sys.exit("%s 还没有 draft.md，没法定稿" % slug)
    PUB.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(draft, PUB / ("%s.md" % slug))
    meta = parse_meta(d / "meta.yml")
    meta["published_at"] = TODAY
    dump_meta(meta, d / "meta.yml")
    print("✓ %s 已定稿 → research/published/%s.md" % (slug, slug))
    build()


def rename(old, new):
    """给条目换一个可读 slug（中文文件名自动生成的 r-YYYYMMDD-NN 换成英文短名）。"""
    src = ITEMS / old
    dst = ITEMS / new
    if not src.is_dir():
        sys.exit("没有这个条目：%s" % old)
    if dst.exists():
        sys.exit("目标已存在：%s" % new)
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", new):
        sys.exit("slug 只能是小写字母、数字和连字符：%s" % new)
    shutil.move(str(src), str(dst))
    pub_old = PUB / ("%s.md" % old)
    if pub_old.exists():
        shutil.move(str(pub_old), str(PUB / ("%s.md" % new)))
    (RES / ("%s.html" % old)).unlink(missing_ok=True)
    print("✓ %s → %s" % (old, new))
    build()


def cmd_list():
    items = load_items()
    if not items:
        print("还没有条目")
        return
    for it in items:
        print("%-9s %-30s %s" % ("[" + it["status"] + "]", it["slug"], it["title"]))
    print("\n待审核：%d" % sum(1 for x in items if x["status"] == "review"))


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "build"
    if cmd == "sync":
        sync()
    elif cmd == "build":
        build()
    elif cmd == "approve":
        if len(args) < 2:
            sys.exit("用法：python3 tools/research.py approve <slug>")
        approve(args[1])
    elif cmd == "list":
        cmd_list()
    elif cmd == "rename":
        if len(args) < 3:
            sys.exit("用法：python3 tools/research.py rename <旧slug> <新slug>")
        rename(args[1], args[2])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
