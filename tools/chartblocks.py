#!/usr/bin/env python3
"""板块里的图：前沿台阶、分数 × 单价、90 天走势。

单独一个文件，不并进 build_section.py——这里只加图，不碰榜的渲染，
两个窗口同时改生成器时冲突面小得多。

三种块由 content/<板块>/section.json 的 boards[] 声明：

    {"kind": "frontier", "file": "天梯榜.csv"}     台账日期 × 分数 → 前沿台阶
    {"kind": "plot", "file": "data/scores.json"}   分数 × 单价 → 性价比散点
    {"kind": "lines", "file": "data/npm-series.json"} 每日下载 → 90 天走势

数据一律读板块里已有的原始文件，不另存一份派生 JSON：同一件事只留一处
口径，原始数据更新了图跟着变，不会出现「图和榜对不上」。
"""

import datetime as dt
import json
import math

import research as R
import regions

# 图上不用写死颜色：皮肤和深色主题接管 --t1/--t3/--orange，跟着页面变。
T1, T2, T3 = "var(--t1)", "var(--t2)", "var(--t3)"
ORANGE, PURPLE, GREEN, RED = "var(--orange)", "var(--purple)", "var(--green)", "var(--red)"
CARD = "var(--card)"

# 画框：左留刻度、上留轴名、下留日期，右边不留——图例和说明在 HTML 里排。
W, H = 720, 400
X0, X1, Y0, Y1 = 52, 696, 348, 26

# 折线用色：前 6 条按顺序取，后面的走灰色
LINE_COLORS = [ORANGE, PURPLE, T1, GREEN, RED, T3]


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def num(v):
    v = float(v)
    if abs(v - round(v)) < 0.05:
        return "%d" % round(v)
    return "%.1f" % v


def wan(n):
    """中文量级：万 / 亿，图上标签和表里都用这个。"""
    n = float(n)
    if n >= 1e8:
        return "%.2f 亿" % (n / 1e8)
    if n >= 1e4:
        v = n / 1e4
        return ("%.0f 万" % v) if v >= 10 else ("%.1f 万" % v)
    return "%d" % round(n)


class Axis:
    """值 → 像素。log 时先取对数，两端夹住，免得越界的点飞出画框。"""

    def __init__(self, a, b, lo, hi, log=False):
        self.a, self.b, self.log = a, b, log
        if log:
            lo, hi = math.log10(lo), math.log10(hi)
        self.lo, self.hi = float(lo), float(hi)

    def __call__(self, v):
        t = math.log10(v) if self.log else float(v)
        t = max(min(t, self.hi), self.lo)
        return self.a + (t - self.lo) / (self.hi - self.lo) * (self.b - self.a)


def _grid(x_tick_px, y_tick_px):
    g = "".join('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d"/>' % (x, Y1, x, Y0)
                for x in x_tick_px)
    g += "".join('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f"/>' % (X0, y, X1, y)
                 for y in y_tick_px)
    return g


def _xlabels(pairs, y=Y0 + 18):
    return "".join('<text class="ch-tk" x="%.1f" y="%d" text-anchor="middle">%s</text>'
                   % (x, y, esc(t)) for x, t in pairs)


def _ylabels(pairs):
    return "".join('<text class="ch-tk" x="%d" y="%.1f" text-anchor="end">%s</text>'
                   % (X0 - 8, y + 3.4, esc(t)) for y, t in pairs)


def _axistext(x_t, y_t):
    return ('<text class="ch-ax-t" x="%d" y="%d" text-anchor="end">%s</text>'
            '<text class="ch-ax-t" x="%d" y="%d" text-anchor="start">%s</text>'
            % (X1, H - 8, esc(x_t), X0, 16, esc(y_t)))


def _head(entry, idx, num_, fallback):
    return ('  <section class="blk" id="board-%d">\n'
            '    <div class="blk-head">\n'
            '      <span class="blk-num">%s</span>\n'
            '      <h2>%s</h2>\n'
            '      <span class="blk-note is-long">%s</span>\n'
            '    </div>\n'
            % (idx + 1, num_, esc(entry.get("title", fallback)),
               R.inline(entry.get("note", ""))))


# ───────────────────── 一、前沿台阶（分数 × 发布日） ─────────────────────
def _ledger_points(sec, entry):
    """台账里同时有发布日期和 AA 综合分的条目。

    两边都得有：只有日期没分数，点不上去；只有分数没日期，排不出顺序。
    """
    sp = sec.dir / "data" / "scores.json"
    if not sp.exists():
        return [], ""
    try:
        d = json.loads(sp.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [], ""
    score = {}
    for m in d.get("models", {}).values():
        s = (m.get("aa") or {}).get("intelligence_index")
        if s is not None:
            score[(m.get("name") or "").strip()] = s
    _, rows = sec.board({"file": entry.get("file", "天梯榜.csv")})

    out = []
    for r in rows:
        name = (r.get("名称") or "").strip()
        when = (r.get("时间") or "").strip()
        s = score.get(name)
        if s is None or len(when) < 10:
            continue
        try:
            day = dt.date.fromisoformat(when[:10])
        except ValueError:
            continue
        out.append({
            "n": name, "d": day, "s": s,
            "open": "开放" in (r.get("权重") or ""),
            "r": regions.normalize(r.get("区域")) or regions.guess(
                r.get("机构"), name, default=""),
        })
    out.sort(key=lambda p: p["d"])
    return out, (d.get("generated_at") or "")[:10]


def block_frontier(sec, entry, idx, total, num_):
    """能力分排到发布日上：台阶是那一刻的最高分，两点之间是「没被超过」的日子。

    Epoch AI 的 ECI 图就是这个读法——把不同基准合成一个指数，按发布日画，
    看点不看平均线：谁在什么时候把天花板抬了多少。这里只用台账里有 AA
    综合分的那一条，没分的模型不补、不估，所以台阶会缺级，缺级本身也是
    一个事实（这一档我们没抓到分）。
    """
    pts, asof = _ledger_points(sec, entry)
    if len(pts) < 5:
        return ('  <section class="blk" id="board-%d">\n'
                '    <div class="blk-head"><span class="blk-num">%s</span><h2>%s</h2>'
                '<span class="blk-note">待补充</span></div>\n'
                '    <p class="blk-empty">台账里同时有发布日与分数的条目不足 5 条。</p>\n'
                '  </section>\n' % (idx + 1, num_, esc(entry.get("title", "分数 × 发布日"))))

    d0, d1 = pts[0]["d"].toordinal(), pts[-1]["d"].toordinal()
    xa = Axis(X0, X1, d0 - 6, d1 + 16)
    smin, smax = min(p["s"] for p in pts), max(p["s"] for p in pts)
    ylo = math.floor(smin / 10) * 10
    yhi = math.ceil(smax / 10) * 10 + 2
    ya = Axis(Y0, Y1, ylo, yhi)

    # 月份网格：每月 1 号一条，标签只写两位月份
    months, m = [], dt.date(pts[0]["d"].year, pts[0]["d"].month, 1)
    while m <= pts[-1]["d"]:
        if m >= pts[0]["d"] - dt.timedelta(days=6):
            months.append((xa(m.toordinal()), "%02d" % m.month))
        m = dt.date(m.year + (m.month == 12), m.month % 12 + 1, 1)

    yticks = list(range(ylo, yhi + 1, 10))
    grid = _grid([x for x, _ in months], [ya(v) for v in yticks])
    xlab = _xlabels(months)
    ylab = _ylabels([(ya(v), "%d" % v) for v in yticks])

    def step_d(seq):
        pp = [(xa(p["d"].toordinal()), ya(p["s"])) for p in seq]
        d = "M%.1f %.1f" % pp[0]
        for (x0_, y0_), (x1_, y1_) in zip(pp, pp[1:]):
            d += " H%.1f V%.1f" % (x1_, y1_)
        return d, pp

    # 前沿 = 一条只升不降的记录线；开放前沿单独一条，两条之差就是「落后多少」
    def records(seq):
        out, best = [], -1
        for p in seq:
            if p["s"] > best:
                best = p["s"]
                out.append(p)
        return out

    front = records(pts)
    f_open = records([p for p in pts if p["open"]])

    body = ""
    if len(f_open) > 1:
        pd, pp = step_d(f_open)
        body += '<path class="ch-step-open" d="%s"/>' % pd
        body += ('<line class="ch-step-open" x1="%.1f" y1="%.1f" x2="%d" y2="%.1f"/>'
                 % (pp[-1][0], pp[-1][1], X1, pp[-1][1]))
    pd, fpp = step_d(front)
    body += '<path class="ch-step" d="%s"/>' % pd
    # 最后一个记录到现在一直没被超过：用点线续到右边，别让读者以为线断了
    body += ('<line class="ch-keep" x1="%.1f" y1="%.1f" x2="%d" y2="%.1f"/>'
             % (fpp[-1][0], fpp[-1][1], X1, fpp[-1][1]))

    dots = []
    for p in pts:
        x, y = xa(p["d"].toordinal()), ya(p["s"])
        tip = "%s · %s 分 · %s · %s" % (
            p["n"], num(p["s"]), p["d"].isoformat(), "开放权重" if p["open"] else "闭源")
        cls = "ch-ring" if p["open"] else "ch-dot"
        dots.append('<circle class="%s" cx="%.1f" cy="%.1f" r="%.1f">'
                    '<title>%s</title></circle>' % (cls, x, y, 4.6 if p["open"] else 3.4,
                                                    esc(tip)))

    # 标签只给三处：起点、抬得最狠的一级、最后一级，再加开放阵营的最高分。
    # 24 个点全标会糊成一片，其余靠 hover 与下面的表。
    marks = []
    jump, best_j = None, -1
    for prev, cur in zip(front, front[1:]):
        if cur["s"] - prev["s"] > best_j:
            best_j, jump = cur["s"] - prev["s"], cur
    picks = [front[0], front[-1]]
    if jump and jump not in picks:
        picks.append(jump)
    if f_open:
        top_open = max(f_open, key=lambda p: p["s"])
        if all(top_open["n"] != p["n"] for p in picks):
            picks.append(top_open)
    for p in picks:
        x, y = xa(p["d"].toordinal()), ya(p["s"])
        anchor, dx = ("end", -8) if x > X1 - 120 else ("start", 8)
        marks.append(_lb(x + dx, y - 11, anchor, "%s %s" % (p["n"], num(p["s"]))))

    gain = front[-1]["s"] - front[0]["s"]
    days = (front[-1]["d"] - front[0]["d"]).days or 1
    rate = gain / days * 100
    open_gap = front[-1]["s"] - max((p["s"] for p in f_open), default=front[-1]["s"])

    svg = ('      <svg class="ch-svg" viewBox="0 0 %d %d" role="img" '
           'aria-label="能力分随发布日抬升的台阶">\n'
           '        <g class="ch-grid">%s</g>\n'
           '        <g class="ch-axis">%s%s%s</g>\n'
           '        <g class="ch-step">%s</g>\n'
           '        <g class="ch-pts">%s</g>\n'
           '        <g class="ch-marks">%s</g>\n'
           '      </svg>' % (W, H, grid, xlab, ylab,
                             _axistext("发布日期 →", "AA 综合分 ↑"),
                             body, "\n          ".join(dots), "".join(marks)))

    rows = []
    prev = None
    for p in front:
        delta = "" if prev is None else ("+%s" % num(p["s"] - prev["s"])
                                         if p["s"] > prev["s"] else "持平")
        rows.append("""        <li>
          <span class="ch-l-date">%s</span>
          <b>%s</b>
          <span class="ch-l-v">%s</span>
          <span class="ch-l-d">%s</span>
          <span class="ch-l-r">%s</span>
        </li>""" % (p["d"].strftime("%m-%d"), esc(p["n"]), num(p["s"]), delta,
                    "开放" if p["open"] else "闭源"))
        prev = p

    return ("%s"
            '    <div class="ch-wrap">\n'
            '      <div class="ch-top">\n'
            '        <span class="ch-flag">%s 天 +%s 分 · 折 %s 分 / 100 天</span>\n'
            '        <span class="ch-key"><i class="ch-k-dot"></i>闭源</span>\n'
            '        <span class="ch-key"><i class="ch-k-ring"></i>开放权重</span>\n'
            '        <span class="ch-key"><i class="ch-k-step"></i>前沿台阶</span>\n'
            '        <span class="ch-key"><i class="ch-k-open"></i>开放前沿</span>\n'
            '        <span class="ch-asof">%s 个点 · 截至 %s</span>\n'
            '      </div>\n'
            '%s\n'
            '    </div>\n'
            '    <ul class="ch-list">\n%s\n    </ul>\n'
            '    <p class="ch-foot">%s</p>\n'
            '  </section>\n'
            % (_head(entry, idx, num_, "分数 × 发布日"),
               days, num(gain), num(rate), len(pts), esc(asof or pts[-1]["d"].isoformat()),
               svg, "\n".join(rows),
               R.inline(entry.get("foot") or
                        ("台阶只连台账里录了分的那 %d 个模型，漏收的发布不会出现在上面；"
                         "最后一段点线表示到抓数这天仍没被超过。开放阵营的最高分比全部前沿低 %s 分。"
                         % (len(pts), num(open_gap))))))


# ───────────────────── 二、分数 × 单价（性价比散点） ─────────────────────
def _price_points(sec):
    """每个有 AA 综合分、且有挂牌价的模型一个点。

    横轴用**混合价**：75% 输入 + 25% 输出，照 Epoch AI 比成本时的口径。
    直接用输出价会把「输入便宜、输出贵」的推理模型摁到右边，而实际账单
    大头往往在输入。两个价都没有的（免费档）不进图——对数轴上没有 0 的位置。
    """
    p = sec.dir / "data" / "scores.json"
    if not p.exists():
        return [], 0, ""
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [], 0, ""
    out, free = [], 0
    for m in d.get("models", {}).values():
        s = (m.get("aa") or {}).get("intelligence_index")
        if s is None:
            continue
        pi = float(m.get("price_in") or 0) * 1e6
        po = float(m.get("price_out") or 0) * 1e6
        if pi <= 0 and po <= 0:
            free += 1
            continue
        out.append({
            "n": (m.get("name") or "").strip(), "v": m.get("vendor") or "",
            "s": s, "p": 0.75 * pi + 0.25 * po,
            "r": regions.guess(m.get("vendor"), m.get("name"), default=""),
        })
    return out, free, (d.get("generated_at") or "")[:10]


def _lb(x, y, anchor, txt, w=0):
    """标签自带一块底板。

    只靠白描边遮不住：网格线会从字缝里穿过去，看着像被划掉一道。
    """
    w = w or (len(txt) * 5.6 + 8)
    bx = x if anchor == "start" else x - w
    return ('<rect class="ch-lb-bg" x="%.1f" y="%.1f" width="%.1f" height="13" rx="2.5"/>'
            '<text class="ch-lb" x="%.1f" y="%.1f" text-anchor="%s">%s</text>'
            % (bx, y - 9.8, w, x, y, anchor, esc(txt)))


def _place_labels(items, box, x_of, y_of):
    """标签避让：先试右上，再左上、右下、左下，四个位置都压着就跳过。

    自动布局只用来兜底，不追求紧致——错位的标签比少一个标签更糟。
    """
    placed, out = [], []
    for it in items:
        x, y = x_of(it), y_of(it)
        w = (len(it["n"]) * 5.4 + 8)
        # 靠右边界的点先试往左摆，不然标签会伸出画框；上下各留 9px，
        # 免得文字贴着前沿那根虚线（描边遮得住线，遮不住压线的观感）
        cand = ([(-6, -12, "end"), (6, -12, "start"), (-6, 17, "end"), (6, 17, "start")]
                if x > X1 - 110 else
                [(6, -12, "start"), (-6, -12, "end"), (6, 17, "start"), (-6, 17, "end")])
        for dx, dy, anc in cand:
            bx = x + dx if anc == "start" else x + dx - w
            by = y + dy - 9
            if any(not (bx + w < b[0] or bx > b[2] or by + 11 < b[1] or by > b[3])
                   for b in box):
                continue
            box.append((bx, by, bx + w, by + 11))
            out.append(_lb(x + dx, y + dy, anc, it["n"], w))
            break
    return out


def block_plot(sec, entry, idx, total, num_):
    """分数 × 单价：同样的分，最便宜的在哪；贵的那几倍买到了什么。

    虚线是性价比前沿——对每一档能力，取达到它的最低价。前沿上的点都在
    「再便宜就够不到这个分」的位置上，线以下没有点、线以右全是同分更贵的。
    """
    pts, free, asof = _price_points(sec)
    if len(pts) < 8:
        return ('  <section class="blk" id="board-%d">\n'
                '    <div class="blk-head"><span class="blk-num">%s</span><h2>%s</h2>'
                '<span class="blk-note">待补充</span></div>\n'
                '    <p class="blk-empty">同时有分数与价格的模型不足 8 个。</p>\n'
                '  </section>\n' % (idx + 1, num_, esc(entry.get("title", "分数 × 单价"))))

    # 同价位的点按分数升序：前沿从低到高扫，同一价钱的几档能力才会被逐级记上
    pts.sort(key=lambda r: (r["p"], r["s"]))
    xa = Axis(X0, X1, pts[0]["p"] * 0.82, pts[-1]["p"] * 1.22, log=True)
    smax = max(p["s"] for p in pts)
    ylo = math.floor(min(p["s"] for p in pts) / 10) * 10
    yhi = math.ceil(smax / 10) * 10 + 2
    ya = Axis(Y0, Y1, ylo, yhi)

    xt = [t for t in (0.03, 0.1, 0.3, 1, 3, 10, 30, 100)
          if pts[0]["p"] * 0.8 <= t <= pts[-1]["p"] * 1.25]
    yt = list(range(ylo, yhi + 1, 10))
    grid = _grid([xa(t) for t in xt], [ya(v) for v in yt])
    xlab = _xlabels([(xa(t), ("$%g" % t)) for t in xt])
    ylab = _ylabels([(ya(v), "%d" % v) for v in yt])

    # 前沿：价格从低到高扫一遍，分数刷出新高就记一笔
    front, best = [], -1.0
    for p in pts:
        if p["s"] > best:
            best = p["s"]
            front.append(p)

    pp = [(xa(p["p"]), ya(p["s"])) for p in front]
    d = "M%.1f %.1f" % pp[0]
    for (x0_, y0_), (x1_, y1_) in zip(pp, pp[1:]):
        d += " H%.1f V%.1f" % (x1_, y1_)

    dots = []
    for p in pts:
        dots.append('<circle class="ch-dot is-%s" cx="%.1f" cy="%.1f" r="4">'
                    '<title>%s · %s 分 · 混合价 $%s / 百万 token · %s</title></circle>'
                    % ("cn" if p["r"] == "国内" else ("fk" if p["r"] == "国外" else "na"),
                       xa(p["p"]), ya(p["s"]), esc(p["n"]), num(p["s"]),
                       ("%.2f" % p["p"]) if p["p"] < 10 else ("%.0f" % p["p"]),
                       esc(p["v"])))

    # 只标三级台阶与最高分：全标会压成一片，其余靠 hover
    picks = [front[0]]
    prev = front[0]["s"]
    for p in front[1:]:
        if p["s"] - prev >= 3 or p is front[-1]:
            picks.append(p)
        prev = max(prev, p["s"])
    top = max(pts, key=lambda r: r["s"])
    if all(top["n"] != p["n"] for p in picks):
        picks.append(top)
    # 把每个点先占成一个小方块：标签只在空白处落脚，压住点比少一个标签更糟
    box = [(xa(p["p"]) - 5, ya(p["s"]) - 5, xa(p["p"]) + 5, ya(p["s"]) + 5) for p in pts]
    marks = _place_labels(picks, box, lambda p: xa(p["p"]), lambda p: ya(p["s"]))

    svg = ('      <svg class="ch-svg" viewBox="0 0 %d %d" role="img" '
           'aria-label="模型综合分与混合单价的散点">\n'
           '        <g class="ch-grid">%s</g>\n'
           '        <g class="ch-axis">%s%s%s</g>\n'
           '        <g class="ch-step"><path class="ch-front" d="%s"/></g>\n'
           '        <g class="ch-pts">%s</g>\n'
           '        <g class="ch-marks">%s</g>\n'
           '      </svg>' % (W, H, grid, xlab, ylab,
                         _axistext("混合单价 · $ / 百万 token（对数）→", "AA 综合分 ↑"),
                         d, "\n          ".join(dots), "".join(marks)))

    # 一个便宜的、一个最贵的：差价买到多少分，一句话说清
    cheap = max((p for p in pts if p["s"] >= smax - 5), key=lambda p: -p["p"])
    flag = "%s 分 $%s · 最高分 %s 分 $%s" % (
        num(cheap["s"]), ("%.2f" % cheap["p"]) if cheap["p"] < 10 else ("%.0f" % cheap["p"]),
        num(top["s"]), ("%.2f" % top["p"]) if top["p"] < 10 else ("%.0f" % top["p"]))

    order = sorted(pts, key=lambda r: -r["s"])[:int(entry.get("list", 12))]
    lis = "".join("""        <li>
          <i class="ch-lo is-%s"></i><b>%s</b>
          <span class="ch-l-v">%s</span>
          <span class="ch-l-p">$%s</span>
          <span class="ch-l-r">%s</span>
        </li>""" % ("cn" if p["r"] == "国内" else ("fk" if p["r"] == "国外" else "na"),
                    esc(p["n"]), num(p["s"]),
                    ("%.2f" % p["p"]) if p["p"] < 10 else ("%.1f" % p["p"]),
                    esc(p["v"]))
        for p in order)

    return ("%s"
            '    <div class="ch-wrap">\n'
            '      <div class="ch-top">\n'
            '        <span class="ch-flag">%s</span>\n'
            '        <span class="ch-key"><i class="ch-k-dot is-cn"></i>国内</span>\n'
            '        <span class="ch-key"><i class="ch-k-dot is-fk"></i>国外</span>\n'
            '        <span class="ch-key"><i class="ch-k-dot is-na"></i>未标注</span>\n'
            '        <span class="ch-key"><i class="ch-k-front"></i>性价比前沿</span>\n'
            '        <span class="ch-asof">%s 个点 · 免费档 %d 个不在图上 · 截至 %s</span>\n'
            '      </div>\n'
            '%s\n'
            '    </div>\n'
            '    <ul class="ch-list">\n%s\n    </ul>\n'
            '    <p class="ch-foot">%s</p>\n'
            '  </section>\n'
            % (_head(entry, idx, num_, "分数 × 单价"), esc(flag),
               len(pts), free, esc(asof), svg, lis,
               R.inline(entry.get("foot") or
                        "横轴取对数：$0.05 到 $%s 差 %d 倍，线性轴上低价那一段会挤成一根线。"
                        % ("%.0f" % pts[-1]["p"], round(pts[-1]["p"] / pts[0]["p"])))))


# ───────────────────── 三、90 天走势（每日下载） ─────────────────────
def _ma(vals, k=7):
    """7 日移动平均。窗口不满就按已有的算，所以头 6 天是半截均值。"""
    out, s = [], 0.0
    for i, v in enumerate(vals):
        s += v
        if i >= k:
            s -= vals[i - k]
        out.append(s / min(i + 1, k))
    return out


def block_lines(sec, entry, idx, total, num_):
    """一周下载量的 90 天形状：谁在涨、谁在掉、掉的是不是换包。

    画 7 日均值而不是日值——日值每 7 天一个锯齿，12 条叠上去全是毛刺，
    看不出趋势。锯齿本身是有意思的（周末掉一半），所以写在脚注里。
    """
    raw = sec.npm_series()
    if not raw:
        return ('  <section class="blk" id="board-%d">\n'
                '    <div class="blk-head"><span class="blk-num">%s</span><h2>%s</h2>'
                '<span class="blk-note">待补充</span></div>\n'
                '    <p class="blk-empty">缺 <code>data/npm-series.json</code>，跑一次抓取再重建。</p>\n'
                '  </section>\n' % (idx + 1, num_, esc(entry.get("title", "90 天走势"))))

    _, rows = sec.board({"file": entry.get("csv", "榜/使用量-cli.csv")})
    items = []
    for r in rows:
        pkg = (r.get("包名") or "").strip()
        if pkg not in raw:
            continue
        ser = raw[pkg]
        if len(ser) < 21:
            continue
        items.append({
            "n": (r.get("名称") or pkg).strip(), "pkg": pkg, "ser": ser,
            "r": regions.normalize(r.get("区域")) or regions.guess(
                r.get("厂商"), r.get("名称"), default=""),
        })
    if not items:
        return ""

    dates = sorted({d for it in items for d in it["ser"]})
    for it in items:
        it["vals"] = [it["ser"].get(d, 0) for d in dates]
        it["last"] = _ma(it["vals"])[-1]
        # 首尾都取整 7 天均值：窗口一样长，30% 的周末锯齿才不会被算成涨跌
        head = sum(it["vals"][:7]) / 7.0
        it["chg"] = it["last"] / head - 1 if head else 0
    items.sort(key=lambda it: -it["last"])

    top_n = int(entry.get("top", 6))
    top, rest = items[:top_n], items[top_n:]

    vmax = max((max(it["vals"]) for it in top), default=1)
    vmin = min(v for it in items for v in it["vals"] if v > 0) if items else 1
    ya = Axis(Y0, Y1, max(10, vmin * 0.7), vmax * 1.6, log=True)
    xa = Axis(X0, X1, 0, len(dates) - 1)

    yt = [t for t in (10, 100, 1000, 1e4, 1e5, 1e6, 1e7)
          if max(10, vmin * 0.7) <= t <= vmax * 1.6]
    grid = _grid([], [ya(t) for t in yt])
    ylab = _ylabels([(ya(t), wan(t) if t >= 1e4 else ("%d" % t)) for t in yt])

    step = max(1, (len(dates) - 1) // 5)
    idxs = list(range(0, len(dates), step))
    last = len(dates) - 1
    if idxs[-1] != last:
        # 末尾两个刻度差不到一周就会叠字，直接拿最后一天顶掉前一个
        if last - idxs[-1] < 8:
            idxs[-1] = last
        else:
            idxs.append(last)
    xlab = _xlabels([(xa(i), dates[i][5:]) for i in idxs])

    lines, keys = [], []
    for i, it in enumerate(rest):
        pts = " ".join("%.1f,%.1f" % (xa(j), ya(v)) for j, v in enumerate(_ma(it["vals"])))
        lines.append('<polyline class="ch-line is-rest" points="%s"/>' % pts)
    for i, it in enumerate(top):
        c = LINE_COLORS[i % len(LINE_COLORS)]
        pts = " ".join("%.1f,%.1f" % (xa(j), ya(v)) for j, v in enumerate(_ma(it["vals"])))
        lines.append('<polyline class="ch-line" points="%s" style="stroke:%s"/>' % (pts, c))
        keys.append((it, c))

    svg = ('      <svg class="ch-svg" viewBox="0 0 %d %d" role="img" '
           'aria-label="命令行工具每日下载量的 90 天走势">\n'
           '        <g class="ch-grid">%s</g>\n'
           '        <g class="ch-axis">%s%s%s</g>\n'
           '        <g class="ch-lines">%s</g>\n'
           '      </svg>' % (W, H, grid, xlab, ylab,
                         _axistext("最近 %d 天 →" % len(dates), "每周下载 · 7 日均 ↑"),
                         "\n          ".join(lines)))

    key_html = "".join(
        '<span class="ch-key"><i style="background:%s"></i>%s<b>%s</b></span>'
        % (c, esc(it["n"]), wan(it["last"])) for it, c in keys)
    if rest:
        key_html += ('<span class="ch-key is-rest"><i class="ch-k-rest"></i>'
                     '<b class="ch-rest-n">其余 %d 条</b>%s</span>'
                     % (len(rest), "、".join(it["n"] for it in rest[:3]) +
                        ("…" if len(rest) > 3 else "")))

    # 「涨最多 / 跌最多」只在上图的前 6 条里挑：其余那几条最小的包一共几百次下载，
    # 百分比全是噪声，挂到标题上会盖掉真正的走势。
    gain = max(top, key=lambda it: it["chg"])
    lose = min(top, key=lambda it: it["chg"])
    flag = "%s %+.0f%% · %s %+.0f%%" % (gain["n"], gain["chg"] * 100,
                                        lose["n"], lose["chg"] * 100)

    # 周末效应：在最大的三条里挑锯齿最明显的那条当例子——排第一的那条
    # 反而最平（CI 占比高），拿它举例会把「锯齿」说小。
    foot, best_gap = "", 0.0
    for it in items[:3]:
        wk = {}
        for i, d in enumerate(dates):
            wk.setdefault(dt.date.fromisoformat(d).weekday(), []).append(it["vals"][i])
        mid = sum(sum(wk[i]) / len(wk[i]) for i in (1, 2, 3) if wk.get(i)) / 3
        sun = sum(wk.get(6, [0])) / max(len(wk.get(6, [])), 1)
        if mid and sun and (1 - sun / mid) > best_gap:
            best_gap = 1 - sun / mid
            foot = ("曲线是 7 日均值；未平滑的日值每 7 天一个锯齿——%s 周中约 %s，周日只有 %s，"
                    "跌掉 %d%%。锯齿属于拿开发机跑 CI 的那部分流量，不是产品在掉。"
                    % (it["n"], wan(mid), wan(sun), round(best_gap * 100)))
    if not foot:
        foot = "曲线是 7 日均值，口径与上面的榜一致：npm 每日下载，不等于活跃用户。"

    lis = "".join("""        <li>
          <i class="ch-lo is-%s"></i><b>%s</b>
          <span class="ch-l-v">%s</span>
          <span class="ch-l-d %s">%+.0f%%</span>
        </li>""" % ("cn" if it["r"] == "国内" else ("fk" if it["r"] == "国外" else "na"),
                    esc(it["n"]), wan(it["last"]),
                    "is-up" if it["chg"] >= 0 else "is-down", it["chg"] * 100)
        for it in items)

    return ("%s"
            '    <div class="ch-wrap">\n'
            '      <div class="ch-top">\n'
            '        <span class="ch-flag">%s</span>\n'
            '        <span class="ch-asof">%s → %s · 7 日均</span>\n'
            '      </div>\n'
            '      <div class="ch-keys">%s</div>\n'
            '%s\n'
            '    </div>\n'
            '    <ul class="ch-list">\n%s\n    </ul>\n'
            '    <p class="ch-foot">%s%s</p>\n'
            '  </section>\n'
            % (_head(entry, idx, num_, "90 天走势"), esc(flag),
               dates[0], dates[-1], key_html, svg, lis,
               R.inline(entry.get("foot", "")),
               (" " + esc(foot)) if foot else ""))
