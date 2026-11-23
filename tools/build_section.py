#!/usr/bin/env python3
"""从 content/<板块>/ 生成三板块页面。

    content/基模/section.json   板块元信息
    content/基模/简介.md        板块一：简介（frontmatter + 正文 + 结论）
    content/基模/天梯榜.csv     板块二：天梯榜卡片，一行一张
    content/基模/报告/*.md      板块三：报告，一篇一个文件

用法：
    python3 tools/build_section.py              # 全部重建
    python3 tools/build_section.py --only models
    python3 tools/build_section.py --check      # 只检查数据
    python3 tools/build_section.py --dry        # 写到 .preview/，不动正式页面
"""

import argparse
import csv
import datetime as dt
import json
import pathlib
import re
import sys
import urllib.parse

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
CONTENT = ROOT / "content"

sys.path.insert(0, str(HERE))
import research as R  # noqa: E402  复用 md 渲染与导航定义
import regions  # noqa: E402  区域推断（国内 / 国外）


# ───────────────────────── 基础解析 ─────────────────────────
def read(p):
    return p.read_text(encoding="utf-8")


def split_front(text):
    """--- 之间是 key: value 元信息，其余是正文。"""
    meta, body = {}, text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            head = text[3:end].strip()
            body = text[end + 4:].lstrip("\n")
            for line in head.splitlines():
                if not line.strip() or line.strip().startswith("#") or ":" not in line:
                    continue
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip("\"'")
    return meta, body


def parse_pairs(s):
    """'知识基线=2025-11, 收录条目=18 条' → [(k, v), ...]"""
    out = []
    for chunk in (s or "").split(","):
        if "=" in chunk:
            k, v = chunk.split("=", 1)
            out.append((k.strip(), v.strip()))
    return out


def escape(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def slug_quote(name):
    return urllib.parse.quote(name)


# ───────────────────────── 板块装载 ─────────────────────────
class Section:
    def __init__(self, folder):
        self.dir = folder
        cfg_path = folder / "section.json"
        if not cfg_path.exists():
            raise FileNotFoundError(cfg_path)
        self.cfg = json.loads(read(cfg_path))
        self.slug = self.cfg["slug"]
        self.name = self.cfg["name"]
        self.page = self.cfg["page"]
        self.intro_md = folder / "简介.md"
        self.reports_dir = folder / self.cfg.get("reports", {}).get("dir", "报告")
        # 板块二可以是一个榜，也可以是多个榜
        if self.cfg.get("boards"):
            self.boards = self.cfg["boards"]
        elif self.cfg.get("board"):
            self.boards = [self.cfg["board"]]
        else:
            self.boards = [{"title": "天梯榜", "file": "天梯榜.csv"}]

    # 板块一
    def intro(self):
        if not self.intro_md.exists():
            return {"meta": {}, "lede": "", "sections": []}
        meta, body = split_front(read(self.intro_md))
        body = body.strip()
        if body.startswith("## "):
            idx = 0
        else:
            idx = body.find("\n## ")
        lede = body[:idx].strip() if idx > 0 else ""
        rest = body[idx:].strip() if idx >= 0 else ""
        sections = []
        for chunk in re.split(r"^##[ \t]+", rest, flags=re.M):
            chunk = chunk.strip()
            if not chunk:
                continue
            lines = chunk.splitlines()
            sections.append((lines[0].strip(), "\n".join(lines[1:]).strip()))
        return {"meta": meta, "lede": lede, "sections": sections}

    # 板块二：一个榜
    def board(self, entry):
        path = self.dir / entry.get("file", "天梯榜.csv")
        if not path.exists():
            return [], []
        with path.open(encoding="utf-8-sig", newline="") as f:
            rd = csv.DictReader(f)
            rows = [r for r in rd if any((v or "").strip() for v in r.values())]
            cols = rd.fieldnames or []
        def rank_key(r):
            try:
                return (0, float(r.get("排名") or 10 ** 6))
            except ValueError:
                return (1, 0)
        rows.sort(key=rank_key)
        return cols, rows

    # 抓取元信息（更新时间 / 来源 / 样本量），没有就返回空
    def stats(self):
        p = self.dir / "data" / "stats.json"
        if not p.exists():
            return {}
        try:
            return json.loads(read(p))
        except json.JSONDecodeError:
            return {}

    # 每日快照：{榜文件名: {日期: {名称: 值}}}
    def history(self):
        p = self.dir / "data" / "history.json"
        if not p.exists():
            return {}
        try:
            return json.loads(read(p))
        except json.JSONDecodeError:
            return {}

    # npm 的每日下载量：{包名: {日期: 值}}（npm 接口直接给时间序列）
    def npm_series(self):
        p = self.dir / "data" / "npm-series.json"
        if not p.exists():
            return {}
        try:
            return json.loads(read(p)).get("series", {})
        except json.JSONDecodeError:
            return {}

    # 板块三
    def reports(self):
        if not self.reports_dir.exists():
            return []
        out = []
        for p in sorted(self.reports_dir.glob("*.md")):
            if p.name.startswith((".", "_")) or p.name == "README.md":
                continue
            meta, body = split_front(read(p))
            out.append({
                "path": p,
                "slug": p.stem,
                "url": "%s/%s.html" % (self.slug, slug_quote(p.stem)),
                "title": meta.get("title") or p.stem,
                "date": meta.get("date") or dt.date.fromtimestamp(p.stat().st_mtime).isoformat(),
                "summary": meta.get("summary", ""),
                "tags": [t.strip() for t in meta.get("tags", "").split(",") if t.strip()],
                "body": body,
            })
        out.sort(key=lambda x: x["date"], reverse=True)
        return out


# ───────────────────────── 页面壳 ─────────────────────────
def footer_html(prefix=""):
    return """<footer class="footer">
  <div class="wrap footer-grid">
    <div>
      <h5>定位</h5>
      <p>AI 发展监控台：把基模、Agent、公司、硬件、模板、应用、原理与历史、本地部署拆成可核对的台账。人工维护，不自动抓取。</p>
      <p class="fine">带 <b>*</b> 的条目为待核实细节；空值与「—」表示未采集，不用推测值填充。</p>
    </div>
    <div>
      <h5>数据口径</h5>
      <p class="fine">知识基线：2025-11 公开资料<br>2026 年新增进展：待补充<br>时间统一 YYYY-MM<br>评测分数：无出处不收录</p>
      <p class="fine">页面不含本机路径、账号与未公开数据。</p>
    </div>
    <div>
      <h5>站点地图</h5>
      <div class="footer-links">
        <a href="%(p)smodels.html">基模</a><a href="%(p)sagents.html">Agent</a>
        <a href="%(p)scompanies.html">公司</a><a href="%(p)shardware.html">硬件</a>
        <a href="%(p)stemplates.html">模板</a><a href="%(p)sapps.html">应用</a>
        <a href="%(p)sprinciples.html">原理 · 历史</a><a href="%(p)slocal.html">本地部署</a>
        <a href="%(p)scases.html">实例索引</a><a href="%(p)slab/index.html">实例 01 · 生图</a>
      </div>
    </div>
  </div>
</footer>""" % {"p": prefix}


def topbar_html(active, prefix=""):
    nav = R.nav_html(active, prefix=prefix or "")
    right = '<a class="btn is-primary" href="%sprinciples.html#e1">时间线</a>' % prefix
    return """<header class="topbar">
  <div class="topbar-in">
    <a class="brand" href="%sindex.html">
      <b>AI.TRACK</b><span class="sep">/</span><span class="sub">AI 发展监控台</span>
    </a>
    <nav class="mainnav">
      %s
    </nav>
    <div class="topbar-right">
      <span class="meta">%s</span>
      %s
    </div>
  </div>
</header>""" % (prefix, nav, dt.date.today().isoformat(), right)


def doc_head(title, desc, active, prefix=""):
    p = prefix
    return """<!DOCTYPE html>
<!-- 生成物：由 tools/build_section.py 从 content/ 生成，手改会被覆盖 -->
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title>
<meta name="description" content="%s">
<link rel="stylesheet" href="%sassets/css/site.css">
<link rel="stylesheet" href="%sassets/css/section.css">
<script src="%sassets/js/board.js" defer></script>
</head>
<body>

%s
""" % (escape(title), escape(desc), p, p, p, topbar_html(active, p))


# ───────────────────────── 三个板块 ─────────────────────────
def block_intro(sec, data, prefix=""):
    meta = data["meta"]
    cfg = sec.cfg
    chips = meta.get("chips") or ", ".join(cfg.get("chips", []))
    chips_html = "".join(
        '<span class="chip %s">%s</span>' % (cls, escape(c.strip()))
        for c, cls in zip([c.strip() for c in chips.split(",") if c.strip()],
                           (cfg.get("chip_class") or ["purple", "green", "orange"]) * 4)
    )
    spec = parse_pairs(meta.get("spec")) or [tuple(x) for x in cfg.get("spec", [])]
    spec_html = "".join(
        '<div class="spec-row"><dt>%s</dt><dd>%s</dd></div>' % (escape(k), escape(v))
        for k, v in spec
    ) or '<div class="spec-row"><dt>指标</dt><dd class="null">待补充</dd></div>'

    lede_html = ""
    if data["lede"]:
        lede_html = R.md_to_html(data["lede"]).strip()
        if lede_html.startswith("<p>") and lede_html.count("<p>") == 1:
            lede_html = lede_html.replace("<p>", '<p class="ph-lede">', 1)
        else:
            lede_html = '<div class="ph-lede">%s</div>' % lede_html

    verdict_html = ""
    extra_html = ""
    for title, body in data["sections"]:
        if title in ("结论", "三条结论"):
            items = re.findall(r"^\s*[-*]\s+(.+)$", body, flags=re.M)
            if items:
                lis = []
                for it in items:
                    m = re.match(r"^\*\*(.+?)\*\*[，,：:]?\s*(.*)$", it)
                    if m:
                        lis.append("<li><b>%s</b><span>%s</span></li>" % (R.inline(m.group(1)), R.inline(m.group(2))))
                    else:
                        lis.append("<li><span>%s</span></li>" % R.inline(it))
                verdict_html += ('<div class="verdict-box"><p class="vb-label">%s / VERDICT</p>'
                                 '<ol>%s</ol></div>') % (escape(title), "".join(lis))
                continue
        extra_html += ('<div class="intro-extra"><h3>%s</h3>%s</div>'
                       % (escape(title), R.md_to_html(body)))

    return """  <p class="crumb"><a href="%sindex.html">首页</a><span class="sep">/</span><span>%s</span><span class="sep">/</span><span>%s</span></p>

  <section class="page-head" id="intro">
    <div class="ph-grid">
      <div>
        <div class="card-top" style="margin-bottom:14px;justify-content:flex-start;gap:10px">
          %s
        </div>
        <h1 class="ph-title">%s</h1>
        <p class="ph-sub">%s</p>
        %s
      </div>
      <aside class="spec-card">
        <div class="spec-head"><span>SNAPSHOT</span><span>MANUAL</span></div>
        <dl class="spec-body" style="margin:0">
          %s
        </dl>
      </aside>
    </div>
    %s
    %s
  </section>
""" % (prefix, cfg.get("num", ""), escape(sec.name),
       chips_html,
       escape(meta.get("title") or sec.name),
       escape(meta.get("sub") or cfg.get("sub", "")),
       lede_html, spec_html, verdict_html, extra_html)


def human_num(v):
    """把大数字压成中文习惯的写法：7495 万 / 1.2 亿。"""
    s = (v or "").strip().replace(",", "")
    if not re.fullmatch(r"-?\d+(\.\d+)?", s):
        return escape(s)
    try:
        n = float(s)
    except ValueError:
        return escape(s)
    if abs(n) >= 1e8:
        return ("%.2f" % (n / 1e8)).rstrip("0").rstrip(".") + " 亿"
    if abs(n) >= 1e5:
        return ("%.1f" % (n / 1e4)).rstrip("0").rstrip(".") + " 万"
    if abs(n) >= 1e4:
        # 一万多的数字只留一位小数会把 19558 压成「2 万」，误差太大
        return ("%.2f" % (n / 1e4)).rstrip("0").rstrip(".") + " 万"
    return format(int(n), ",")


def board_mode(entry, rows):
    """这一榜支持哪些交互。

    flow   — 数值是流水（周下载、调用次数），窗口内取日均
    stock  — 数值是累计（安装量、仓库数），窗口内取日均新增
    date   — 没有数值，只有 YYYY-MM，按时间截断
    region — 只有归属可筛选，其余不动
    """
    if entry.get("mode"):
        return entry["mode"]
    k_val = (entry.get("fields") or {}).get("value")
    if not k_val:
        return "date" if any((r.get("时间") or "").count("-") == 1 for r in rows) else "region"
    return "stock"


def board_series(sec, entry, rows, mode):
    """把序列整理成 {卡片键: {日期: 值}}，键要和卡片上写的一致。"""
    f = entry.get("fields") or {}
    k_name = f.get("name", "名称")
    out = {}
    if mode == "npm":
        raw = sec.npm_series()
        for r in rows:
            pkg, name = (r.get("包名") or "").strip(), (r.get(k_name) or "").strip()
            if pkg in raw and name:
                out[name] = raw[pkg]
        return out
    hist = sec.history().get(pathlib.Path(entry.get("file", "")).name, {})
    for day, kv in hist.items():
        for k, v in kv.items():
            out.setdefault(k, {})[day] = v
    return out


def block_board(sec, entry, rows, stat, idx, total, series=None):
    bcfg = entry
    title = bcfg.get("title", "天梯榜")
    note = bcfg.get("note", "")
    unit = bcfg.get("unit", "")
    unit_static = bcfg.get("unit_static", unit)
    f = bcfg.get("fields", {})
    k_rank = f.get("rank", "排名")
    k_name = f.get("name", "名称")
    k_meta = f.get("meta", ["机构", "权重", "取向"])
    k_note = f.get("note", "一句话")
    k_when = f.get("when", "时间")
    k_val = f.get("value")
    if isinstance(k_meta, str):
        k_meta = [k_meta]

    mode = board_mode(bcfg, rows)
    bid = "b%d" % (idx + 1)

    cards, n_cn, n_intl, n_none = [], 0, 0, 0
    for r in rows:
        rank = (r.get(k_rank) or "").strip()
        name = (r.get(k_name) or "").strip()
        metas = [(r.get(k) or "").strip() for k in k_meta]
        metas = [m for m in metas if m]
        note_txt = (r.get(k_note) or "").strip()
        when = (r.get(k_when) or "").strip()
        val = (r.get(k_val) or "").strip() if k_val else ""

        reg = regions.normalize(r.get("区域"))
        if not reg:
            reg = regions.guess(r.get("厂商"), r.get("平台"), r.get("机构"),
                                r.get("公司"), r.get("标识"), name)
        if reg == "国内":
            n_cn += 1
        elif reg == "国外":
            n_intl += 1
        else:
            n_none += 1

        if val:
            right = '<span class="bd-val">%s%s</span>' % (
                human_num(val), '<small>%s</small>' % escape(unit_static) if unit_static else "")
        elif when:
            right = '<span class="bd-when">%s</span>' % escape(when)
        else:
            right = ""

        date_attr = ""
        if mode == "date" and re.match(r"^\d{4}-\d{2}", when):
            date_attr = ' data-date="%s"' % escape(when[:7])
        cards.append("""<article class="bd-card" data-k="%s" data-region="%s" data-base="%s"%s>
        <span class="bd-rank">%s</span>
        <div class="bd-main">
          <div class="bd-top"><h3>%s</h3>%s</div>
          <p class="bd-meta">%s%s</p>
          <p class="bd-note">%s</p>
        </div>
      </article>""" % (
            escape(name), reg, escape(val), date_attr,
            escape(rank) or "·",
            escape(name),
            right,
            " · ".join(escape(m) for m in metas),
            '<span class="bd-delta"></span>' if (k_val and mode in ("flow", "stock", "npm")) else "",
            R.inline(note_txt),
        ))
    empty = ('<p class="blk-empty">这一榜还没填。往 <code>content/%s/%s</code> 里加一行，就跑一次。</p>'
             % (sec.dir.name, bcfg.get("file", "天梯榜.csv")))

    # 更新时间 / 来源 / 样本量：有抓取记录才显示
    stamp = ""
    if stat:
        ts = (stat.get("updated_at") or "")[:16].replace("T", " ")
        src = stat.get("source", "")
        bits = [x for x in (("更新 " + ts) if ts else "", src) if x]
        if stat.get("sample"):
            bits.append("样本 " + stat["sample"])
        if bits:
            stamp = '<span class="blk-stamp">%s</span>' % escape(" · ".join(bits))

    # 控件：区域三档 + 时间跨度滑块（没有时间序列时只留区域）
    has_series = bool(series) and mode in ("flow", "stock", "npm")
    if mode == "npm":
        mode = "flow"
    ctrl = ""
    spec = None
    if len(rows) > 1:
        seg = ""
        for key, label, num in (("all", "全部", len(rows)), ("cn", "国内", n_cn),
                                ("intl", "国外", n_intl)):
            seg += ('<button type="button" data-region="%s"%s>%s<i>%d</i></button>'
                    % (key, ' class="on"' if key == "all" else "", label, num))
        span_html = ""
        if has_series:
            span_html = """
      <div class="span">
        <span class="span-label">时间跨度</span>
        <output class="span-out">近 %(def)d 天</output>
        <input type="range" min="1" max="%(max)d" step="1" value="%(def)d"
               aria-label="时间跨度（天）">
        <div class="span-ticks">%(ticks)s</div>
      </div>""" % {
                "max": 90, "def": 7,
                "ticks": "".join('<button type="button" data-span="%d">%d 天</button>' % (d, d)
                                 for d in (7, 30, 90)),
            }
        elif mode == "date":
            span_html = """
      <div class="span">
        <span class="span-label">时间跨度</span>
        <output class="span-out">近 24 个月</output>
        <input type="range" min="1" max="24" step="1" value="24"
               aria-label="时间跨度（月）">
        <div class="span-ticks">%(ticks)s</div>
      </div>""" % {
                "ticks": "".join('<button type="button" data-span="%d">%d 个月</button>' % (d, d)
                                 for d in (3, 12, 24)),
            }
        default_note = ("拖动滑块改变统计窗口，榜单按新值重排。"
                        if has_series else
                        "按发布时间截断，滑块取近 N 个月。" if mode == "date" else
                        "按所属机构筛选，未标注归属的条目不计入国内 / 国外。")
        ctrl = """    <div class="bd-ctrl" data-ctrl="%s">
      <div class="seg" role="group" aria-label="按归属筛选">%s</div>%s
      <p class="bd-ctrl-note">%s</p>
    </div>
""" % (bid, seg, span_html, default_note)

        anchor = ""
        if mode == "date":
            dates = sorted({(r.get(k_when) or "")[:7] for r in rows
                            if re.match(r"^\d{4}-\d{2}", r.get(k_when) or "")})
            anchor = dates[-1] if dates else ""
        spec = {
            "mode": mode, "unit": unit, "slider": {"default": 7 if has_series else 24},
            "series": series if has_series else {},
        }
        if anchor:
            spec["anchor"] = anchor

    num = "02" if total == 1 else "02.%d" % (idx + 1)
    spec_html = ""
    if spec:
        spec_html = ('    <script type="application/json" data-spec="%s">%s</script>\n'
                     % (bid, json.dumps(spec, ensure_ascii=False, separators=(",", ":"))))
    return """  <section class="blk" id="board%s">
    <div class="blk-head">
      <span class="blk-num">%s</span>
      <h2>%s</h2>
      <span class="blk-note">%s</span>
    </div>
%s    <div class="board" data-board="%s">
      %s
    </div>
    <p class="bd-empty-tip" hidden>这一档还没有数据。换成「全部」看完整榜单。</p>
    %s
    %s
%s  </section>
""" % ("" if total == 1 else "-%d" % (idx + 1), num, escape(title), R.inline(note),
       ctrl, bid,
       "\n      ".join(cards), stamp, "" if cards else empty, spec_html)


def block_reports(sec, reports):
    items = []
    for r in reports:
        tags = "".join('<span class="post-tag">%s</span>' % escape(t) for t in r["tags"])
        items.append("""<a class="post-item" href="%s">
        <div class="post-when"><time>%s</time>%s</div>
        <div class="post-main">
          <h3>%s</h3>
          <p>%s</p>
        </div>
        <span class="post-go">读 →</span>
      </a>""" % (r["url"], escape(r["date"]), tags,
                 escape(r["title"]), R.inline(r["summary"])))
    empty = ('<p class="blk-empty">还没有报告。往 <code>content/%s/报告/</code> 扔一个 '
             '<code>.md</code>，frontmatter 写 title / date / summary，就跑一次。</p>' % sec.dir.name)
    return """  <section class="blk" id="reports">
    <div class="blk-head">
      <span class="blk-num">03</span>
      <h2>%s</h2>
      <span class="blk-note">%s</span>
    </div>
    <div class="posts">
      %s
    </div>
    %s
  </section>
""" % (escape(sec.cfg.get("reports", {}).get("title", "报告")),
       ("共 %d 篇" % len(reports)) if reports else "待补充",
       "\n      ".join(items), "" if items else empty)


def pager_html(sec, prefix=""):
    cfg = sec.cfg
    prev = cfg.get("prev") or ["index.html", "首页 · 九个板块"]
    nxt = cfg.get("next") or ["index.html", "首页 · 九个板块"]
    return """  <nav class="pager">
    <a href="%s%s"><span class="pg-l">← PREV</span><span class="pg-t">%s</span></a>
    <a class="next" href="%s%s"><span class="pg-l">NEXT →</span><span class="pg-t">%s</span></a>
  </nav>
""" % (prefix, prev[0], escape(prev[1]), prefix, nxt[0], escape(nxt[1]))


def subnav_html(sec, prefix="", report_page=False):
    cfg = sec.cfg
    n_b = len(cfg.get("boards") or [])
    b_anchor = "#board" if n_b <= 1 else "#board-1"
    if report_page:
        return """<div class="subnav">
  <div class="subnav-in">
    <span class="sn-label">%s</span>
    <a href="%s%s">← 回「%s」</a>
    <a href="%s%s">天梯榜</a>
    <a href="%s%s#reports">报告</a>
  </div>
</div>
""" % (escape(cfg.get("en", "")),
       prefix + sec.page, "", escape(sec.name),
       prefix + sec.page, b_anchor,
       prefix + sec.page, "")
    n_boards = len(cfg.get("boards") or [])
    board_anchor = "#board" if n_boards <= 1 else "#board-1"
    return """<div class="subnav">
  <div class="subnav-in">
    <span class="sn-label">%s</span>
    <a href="#intro">简介</a>
    <a href="%s">%s</a>
    <a href="#reports">报告</a>
    <span class="sn-sep"></span>
    <a href="%sprinciples.html">原理 · 历史</a>
    <a href="%slocal.html">怎么本地跑</a>
  </div>
</div>
""" % (escape(cfg.get("en", "")), board_anchor,
       escape(cfg["boards"][0].get("title", "天梯榜") if n_boards == 1 else "天梯榜"),
       prefix, prefix)


# ───────────────────────── 生成 ─────────────────────────
def build_section(sec, out_dir, prefix=""):
    intro = sec.intro()
    reports = sec.reports()
    stats = sec.stats().get("boards", {})

    desc = intro["meta"].get("desc") or sec.cfg.get("desc", "")
    blocks, counts = [], []
    for i, entry in enumerate(sec.boards):
        _, rows = sec.board(entry)
        stat = stats.get(pathlib.Path(entry.get("file", "")).name, {})
        mode = entry.get("mode") or board_mode(entry, rows)
        series = board_series(sec, entry, rows, mode)
        blocks.append(block_board(sec, entry, rows, stat, i, len(sec.boards), series))
        counts.append(len(rows))

    body = "".join([
        subnav_html(sec, prefix),
        '<main class="wrap">\n\n',
        block_intro(sec, intro, prefix),
        "".join(blocks),
        block_reports(sec, reports),
        pager_html(sec, prefix),
        "</main>\n\n",
        footer_html(prefix),
        "\n</body>\n</html>\n",
    ])
    html = doc_head("%s · AI.TRACK" % sec.name, desc, sec.name, prefix) + body

    out = out_dir / sec.page
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print("  ✓ %-24s %s · %d 报告" % (sec.page, "/".join(str(c) for c in counts), len(reports)))

    # 报告页
    for r in reports:
        rout = out_dir / sec.slug / (r["slug"] + ".html")
        rout.parent.mkdir(parents=True, exist_ok=True)
        r_prefix = prefix + "../"
        rbody = "".join([
            doc_head(r["title"] + " · " + sec.name, r["summary"], sec.name, r_prefix),
            subnav_html(sec, r_prefix, report_page=True),
            '<main class="wrap post-wrap">\n',
            '  <p class="crumb"><a href="%sindex.html">首页</a><span class="sep">/</span>'
            '<a href="%s%s">%s</a><span class="sep">/</span><span>报告</span></p>\n'
            % (r_prefix, r_prefix, sec.page, escape(sec.name)),
            '  <article class="post">\n',
            '    <p class="post-meta">%s%s</p>\n' % (
                escape(r["date"]),
                (" · " + " · ".join(escape(t) for t in r["tags"])) if r["tags"] else ""),
            '    <h1 class="post-title">%s</h1>\n' % escape(r["title"]),
            ('    <p class="post-lede">%s</p>\n' % R.inline(r["summary"])) if r["summary"] else "",
            '    <div class="post-body">\n%s\n    </div>\n' % R.md_to_html(r["body"]),
            '  </article>\n',
            '  <nav class="pager"><a href="%s%s"><span class="pg-l">← BACK</span>'
            '<span class="pg-t">%s · 全部报告</span></a></nav>\n'
            % (r_prefix, sec.page, escape(sec.name)),
            '</main>\n\n',
            footer_html(r_prefix),
            "\n</body>\n</html>\n",
        ])
        rout.write_text(rbody, encoding="utf-8")
    return counts, len(reports)


def discover():
    out = []
    for d in sorted(CONTENT.iterdir()):
        if not d.is_dir() or not (d / "section.json").exists():
            continue
        out.append(Section(d))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="只重建某个板块（按 slug 或文件夹名）")
    ap.add_argument("--check", action="store_true", help="只检查数据，不写文件")
    ap.add_argument("--dry", action="store_true", help="输出到 .preview/，不动正式页面")
    args = ap.parse_args()

    secs = discover()
    if args.only:
        secs = [s for s in secs if args.only in (s.slug, s.dir.name)]
        if not secs:
            sys.exit("没有这个板块：%s" % args.only)

    if args.check:
        print("板块 %d 个" % len(secs))
        for s in secs:
            intro = s.intro()
            reps = s.reports()
            counts = [len(s.board(b)[1]) for b in s.boards]
            print("  %-8s → %-18s 简介:%s  榜:%s  报告:%d" % (
                s.dir.name, s.page,
                "有" if intro["lede"] else "缺",
                "/".join(str(c) for c in counts), len(reps)))
        return

    if args.dry:
        out_dir, prefix = ROOT / ".preview", "../"
        print("→ 输出到 .preview/（正式页面未改动）")
    else:
        out_dir, prefix = ROOT, ""

    for s in secs:
        if not s.intro_md.exists():
            print("  · 跳过 %-8s（还缺 简介.md，页面保持原样）" % s.dir.name)
            continue
        build_section(s, out_dir, prefix)
    print("完成")


if __name__ == "__main__":
    main()
