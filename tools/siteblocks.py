#!/usr/bin/env python3
"""算力中心的三张图：增长曲线、客户榜、单体规模。

和 chartblocks.py 分开，是因为这三张图共用一套「MW → EFLOPS」的折算
（见 sites.py），不和基模那套分数口径混在一个文件里。

    {"kind": "growth", "data": "算力中心"}     2024–2030 累计算力，按区域堆叠
    {"kind": "customers", "data": "算力中心"}  谁在租：MW / EF / 站点数
    {"kind": "scale", "data": "算力中心"}      Top 18 单体：总容量与已投运
"""

import sites as S
from chartblocks import (Axis, _axistext, _grid, _head, _lb, _place_labels,
                         _xlabels, _ylabels, esc, num, wan)
from chartblocks import GREEN, ORANGE, PURPLE, RED, T1, T3
from chartblocks import H, W, X0, X1, Y0, Y1
import research as R

RC = {"中国": ORANGE, "美国": PURPLE, "东南亚": GREEN, "其他": RED}
REGIONS = ["中国", "美国", "东南亚", "其他"]


def _yrs(sites):
    ys = [x["y1"] or x["y0"] for x in sites if not x["agg"] and x["mw"]]
    ys += [x["y0"] for x in sites if not x["agg"] and x["y0"]]
    return min(ys or [2024]), max(ys or [2030])


# ───────────────────── 一、算力随时间的增长 ─────────────────────
def block_growth(sec, entry, idx, total, num_):
    """累计算力按年摊开：一条实线是已经在跑的，一条虚线是把在建规划都算上。

    为什么用对数纵轴：2024 到 2029 差两个数量级（千级 EF 到十万级 EF），
    线性轴上前四年会压成一条贴地的线，读者只能看到最后一根竖杆。对数轴上
    斜率就是增速，哪一年开始变陡一眼能看出来。

    为什么不堆叠：堆叠面积在对数轴上没有意义（对数的和不是和的对数）。
    区域构成改用图下方一根 100% 条，只讲最后一年的构成，比在每条线上叠颜色清楚。
    """
    sites = S.load(sec)
    t = S.totals(sites)
    if not t["n"]:
        return _empty(entry, idx, num_, "算力中心表里还没有带 MW 的行。")

    y_lo, y_hi = _yrs(sites)
    years = list(range(y_lo, max(y_hi, y_lo + 3) + 1))
    now = 2026

    live = {y: {r: 0.0 for r in REGIONS} for y in years}
    full = {y: {r: 0.0 for r in REGIONS} for y in years}
    for x in sites:
        if x["agg"] or not x["mw"]:
            continue
        r = x["region"] if x["region"] in RC else "其他"
        for y in years:
            if x["y0"] and x["y0"] <= y:
                live[y][r] += x["ef_live"]
            # 含规划那条按「到这一年已经上线多少」算：满产年份到了算全额，
            # 只上了一部分的算现网那一段。否则 2025 会出现虚线低于实线——
            # 因为 Abilene、Rainier 那年已经上电、满产却排在 2026。
            if x["y1"] and x["y1"] <= y:
                full[y][r] += x["ef"]
            elif x["y0"] and x["y0"] <= y:
                full[y][r] += x["ef_live"]

    tot_full = [sum(full[y].values()) for y in years]
    tot_live = [sum(live[y].values()) for y in years]
    hi = max(tot_full) * 1.35
    lo = max(min([v for v in tot_live if v > 0] or [100]) * 0.45, 50)
    ya = Axis(Y0, Y1, lo, hi, log=True)
    xa = Axis(X0, X1, years[0] - 0.12, years[-1] + 0.12)

    yt = [v for v in (100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000)
          if lo <= v <= hi]
    grid = _grid([xa(y) for y in years], [ya(v) for v in yt])
    xlab = _xlabels([(xa(y), str(y)) for y in years])
    ylab = _ylabels([(ya(v), wan(v)) for v in yt])

    def step(vals, ys=None):
        pp = [(xa(y), ya(max(v, 1))) for y, v in zip(ys or years, vals)]
        d = "M%.1f %.1f" % pp[0]
        for (x0_, y0_), (x1_, y1_) in zip(pp, pp[1:]):
            d += " H%.1f V%.1f" % (x1_, y1_)
        return d, pp

    # 已投运只画到「现在」为止：2027 年以后没有实测值，把最后一年平推过去
    # 会被读成「之后不再增长」，那是另一种错。
    lyears = [y for y in years if y <= now]
    d_live, pp_live = step(tot_live[:len(lyears)], lyears)
    d_full, _ = step(tot_full, years)
    area = ("%s L%.1f %d L%.1f %d Z"
            % (d_live, pp_live[-1][0], Y0, pp_live[0][0], Y0))

    # 两个区域的单线：全球那条只回答「多少」，区域线回答「涨在哪」
    reg_lines = []
    for r, col in (("美国", PURPLE), ("中国", ORANGE)):
        vals = [full[y][r] for y in years]
        if max(vals) < 1:
            continue
        d, _ = step(vals)
        reg_lines.append('<path class="sc-l" d="%s" style="stroke:%s"/>' % (d, col))

    # 端点数值：只标最后一年与「现在」，中间全标会压成一串
    marks = []
    # 现在那个点的标签放下面：上面紧挨着「含规划」那条虚线的台阶，会压字
    for y, v, anc, dx, dy in ((years[-1], tot_full[-1], "end", -6, -8),
                              (now, tot_live[years.index(now)], "end", -7, 14)):
        marks.append('<circle cx="%.1f" cy="%.1f" r="2.6" style="fill:%s"/>'
                     % (xa(y), ya(max(v, 1)), T1))
        marks.append('<text class="sc-lb" x="%.1f" y="%.1f" text-anchor="%s">%s</text>'
                     % (xa(y) + dx, ya(max(v, 1)) + dy, anc,
                        wan(v) if v >= 10000 else "{:,.0f}".format(v)))

    nowx = xa(now)
    nowl = ('<line class="sc-now" x1="%.1f" y1="%d" x2="%.1f" y2="%d"/>'
            '<text class="sc-now-t" x="%.1f" y="%d" text-anchor="middle">现在</text>'
            % (nowx, Y1, nowx, Y0, nowx, Y1 - 6))

    svg = ('      <svg class="ch-svg" viewBox="0 0 %d %d" role="img" '
           'aria-label="全球算力中心累计折算算力，2024 到 %d">\n'
           '        <g class="ch-grid">%s</g>\n'
           '        <path class="sc-fill" d="%s"/>\n'
           '        <g class="sc-lines">%s</g>\n'
           '        <path class="sc-dash" d="%s"/>\n'
           '        <g class="sc-marks">%s%s</g>\n'
           '        <g class="ch-axis">%s%s%s</g>\n'
           '      </svg>'
           % (W, H, years[-1], grid, area, "".join(reg_lines), d_full,
              nowl, "".join(marks),
              xlab, ylab, _axistext("投运年份 →", "累计折算算力 · EFLOPS（对数）↑")))

    # 最后一年的构成：一根 100% 条 + 一句人话
    comp = [(r, full[years[-1]][r]) for r in REGIONS]
    csum = sum(v for _, v in comp) or 1
    bar = "".join('<i style="width:%.1f%%;background:%s"></i>'
                  % (v / csum * 100, RC[r]) for r, v in comp if v)
    comp_txt = "、".join("%s %.0f%%" % (r, v / csum * 100)
                        for r, v in sorted(comp, key=lambda kv: -kv[1]) if v)

    flag = "%d 满产 %s EF · %d 满产 %s EF（%.1f 倍）" % (
        now, wan(tot_full[years.index(now)]) if now in years else "—",
        years[-1], wan(tot_full[-1]), tot_full[-1] / max(tot_full[years.index(now)], 1))

    order = sorted([x for x in sites if not x["agg"] and x["mw"]],
                   key=lambda x: -(x["y1"] or x["y0"] or 0))[:8]
    lis = "".join("""        <li>
          <i class="ch-lo is-%s"></i><b>%s</b>
          <span class="ch-l-date">%s</span>
          <span class="ch-l-v">%s</span>
          <span class="ch-l-p">%s<small>EF</small></span>
        </li>""" % ("cn" if x["region"] == "中国" else
                     "fk" if x["region"] == "美国" else "na",
                     esc(x["n"]), (x["y1"] or x["y0"] or "—"),
                     S.gw(x["mw"]), S.efs(x["ef"])) for x in order)

    return ("%s"
            '    <div class="ch-wrap">\n'
            '      <div class="ch-top">\n'
            '        <span class="ch-flag">%s</span>\n'
            '        <span class="ch-key"><i class="sc-k-solid"></i>全球 · 已投运</span>\n'
            '        <span class="ch-key"><i class="sc-k-dash"></i>全球 · 含在建与规划</span>\n'
            '        <span class="ch-key"><i style="background:%s"></i>美国 · 含规划</span>\n'
            '        <span class="ch-key"><i style="background:%s"></i>中国 · 含规划</span>\n'
            '        <span class="ch-asof">截至 %d 已投运 %s EF</span>\n'
            '      </div>\n'
            '%s\n'
            '      <div class="sc-comp"><b>%d 年的构成</b>'
            '<span class="sc-comp-bar">%s</span><span class="sc-comp-t">%s</span></div>\n'
            '    </div>\n'
            '    <ul class="ch-list">\n%s\n    </ul>\n'
            '    <p class="ch-foot">%s</p>\n'
            '  </section>\n'
            % (_head(entry, idx, num_, "算力随时间的增长"), esc(flag), PURPLE, ORANGE,
               now, wan(tot_live[years.index(now)]) if now in years else "—",
               svg, years[-1], bar, comp_txt, lis,
               R.inline(entry.get("foot") or
                        "两条线的差就是「已经宣布、还没有电」的部分。")))
# ───────────────────── 二、谁在租 ─────────────────────
def block_customers(sec, entry, idx, total, num_):
    """按客户汇总：一个客户在几个站、多少容量、折多少算力。

    条形按 MW 切，不按 EF——这一张讲的是「谁占了多少电」；算力跟在后面，
    因为同一份电在不同代际的芯片上折出来的算力能差两倍多。深色那段是已投运。
    """
    sites = S.load(sec)
    cust = S.by_cust(sites)
    if not cust:
        return _empty(entry, idx, num_, "没有带客户的站点。")

    # 主区域：一个客户常横跨几国，取容量最大的那一个来上色
    main = {}
    for x in sites:
        if x["agg"] or not x["mw"]:
            continue
        for c in (x["cust"] or ["未披露"]):
            v = main.setdefault(c, {})
            v[x["region"]] = v.get(x["region"], 0) + (x["mw"] or 0)
    for c, d in main.items():
        main[c] = max(d, key=d.get) if d else "其他"

    rows = sorted(cust.items(), key=lambda kv: -kv[1]["mw"])
    top_n = int(entry.get("top", 12))
    top, rest = rows[:top_n], rows[top_n:]
    vmax = top[0][1]["mw"] if top else 1
    tot = sum(v["mw"] for _, v in rows) or 1

    lis = []
    for i, (c, v) in enumerate(top):
        col = RC.get(main.get(c, "其他"), RED)
        none = c == "未披露"
        lis.append("""        <li class="%s">
          <span class="sc-c-r">%d</span>
          <b>%s</b>
          <span class="sc-c-bar"><i style="width:%.1f%%;background:%s"></i>\
<i class="sc-c-live" style="width:%.1f%%;background:%s"></i></span>
          <span class="sc-c-mw">%s</span>
          <span class="sc-c-ef">%s<small>EF</small></span>
          <span class="sc-c-n">%d 站</span>
        </li>""" % ("is-none" if none else "", i + 1, esc(c),
                    max(v["mw"] / vmax * 100, 1.2), col,
                    v["live"] / v["mw"] * 100 if v["mw"] else 0, col,
                    S.gw(v["mw"]), "{:,.0f}".format(v["ef"]), v["n"]))

    rest_txt = ""
    if rest:
        rest_txt = ('<p class="sc-rest">另有 %d 家合计 %s：%s</p>'
                    % (len(rest), S.gw(sum(v["mw"] for _, v in rest)),
                       "、".join("%s %s" % (esc(c), S.gw(v["mw"])) for c, v in rest[:6])
                       + ("…" if len(rest) > 6 else "")))

    t1, v1 = top[0]
    flag = "%s 一家 %s · 前 %d 家占 %.0f%%" % (
        esc(t1), S.gw(v1["mw"]), min(top_n, len(rows)),
        sum(v["mw"] for _, v in top) / tot * 100)

    return ("%s"
            '    <div class="sc-wrap">\n'
            '      <div class="ch-top">\n'
            '        <span class="ch-flag">%s</span>\n'
            '        <span class="ch-key"><i style="background:%s"></i>中国</span>\n'
            '        <span class="ch-key"><i style="background:%s"></i>美国</span>\n'
            '        <span class="ch-key"><i style="background:%s"></i>东南亚</span>\n'
            '        <span class="ch-key"><i style="background:%s"></i>其他</span>\n'
            '        <span class="ch-key"><i class="sc-k-live"></i>已投运</span>\n'
            '        <span class="ch-asof">按站点标注的租户汇总 · 多租户站点等分</span>\n'
            '      </div>\n'
            '      <ol class="sc-cust">\n%s\n      </ol>\n'
            '      %s\n'
            '    </div>\n'
            '    <p class="ch-foot">%s</p>\n'
            '  </section>\n'
            % (_head(entry, idx, num_, "谁在租"), esc(flag),
               ORANGE, PURPLE, GREEN, RED, "\n".join(lis), rest_txt,
               R.inline(entry.get("foot") or "")))


# ───────────────────── 三、单体规模 ─────────────────────
def _cut(s, n):
    s = s or ""
    return s if len(s) <= n else s[:n - 1] + "…"


def block_scale(sec, entry, idx, total, num_):
    """单体规模榜：一根条两种长度——浅色是「公布的总容量」，深色是「已经上电的」。

    为什么不用一列数字：这一层最容易读错的就是把规划当现网。同一根条上画出
    两者的差，比在备注里写「在建」直观。右端两列分别是容量与折算算力。
    """
    sites = [x for x in S.load(sec) if not x["agg"] and x["mw"]]
    if len(sites) < 6:
        return _empty(entry, idx, num_, "带 MW 的站点不足 6 个。")
    sites.sort(key=lambda x: -x["mw"])
    top_n = int(entry.get("top", 18))
    rows = sites[:top_n]
    vmax = max(x["mw"] for x in rows)

    SW = 900
    BX0, BX1 = 250, 700
    RH, TOP = 30, 48
    h = TOP + len(rows) * RH + 34
    xa = Axis(BX0, BX1, 0, vmax)

    step = 2000 if vmax > 6000 else (1000 if vmax > 2000 else 500)
    ticks = [t for t in range(0, int(vmax) + step, step) if t <= vmax]
    if len(ticks) > 6:
        ticks = ticks[::2]
    grid = "".join('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d"/>' % (xa(t), TOP - 12, xa(t), TOP + len(rows) * RH)
                   for t in ticks)
    tick_t = "".join('<text class="ch-tk" x="%.1f" y="%d" text-anchor="middle">%s</text>'
                     % (xa(t), TOP - 18, S.gw(t) if t else "0") for t in ticks)

    body = []
    for i, x in enumerate(rows):
        y = TOP + i * RH
        col = RC.get(x["region"], RED)
        w = max(xa(x["mw"]) - BX0, 1.5)
        wl = xa(x["live"]) - BX0 if x["live"] else 0
        # 客户后面跟满产年份：这一榜最容易读错的除了「规划当现网」，就是「什么时候」。
        cust = "%s · %s" % (" · ".join(x["cust"]) or "未披露",
                            x["y1"] or x["y0"] or "未定")
        # 一根条两层：整条是满产容量（淡），前一段是已上电（实）。
        # 淡的那层用同色系，读者不会以为是「另一种东西」。
        body.append(
            '<g><title>%s · %s · 满产 %s · 现网 %s · %s</title>'
            '<text class="sc-n" x="8" y="%d">%s</text>'
            '<text class="sc-c" x="8" y="%d">%s</text>'
            '<rect class="sc-bg" x="%d" y="%d" width="%.1f" height="10" rx="2.5"/>'
            '<rect class="sc-bar" x="%d" y="%d" width="%.1f" height="10" rx="2.5" style="fill:%s"/>'
            % (esc(x["n"]), esc(cust), S.gw(x["mw"]), S.gw(x["live"]), esc(x["status"]),
               y + 12, esc(_cut(x["n"], 22)), y + 26, esc(_cut(cust, 30)),
               BX0, y + 4, w, BX0, y + 4, w, col)
            + ('<rect x="%d" y="%d" width="%.1f" height="10" rx="2.5" style="fill:%s"/>'
               % (BX0, y + 4, wl, col) if wl else "")
            + '<text class="sc-v" x="812" y="%d" text-anchor="end">%s</text>'
              '<text class="sc-e" x="890" y="%d" text-anchor="end">%s</text></g>'
              % (y + 13, S.gw(x["mw"]), y + 13, "{:,.0f}".format(x["ef"])))

    svg = ('      <svg class="ch-svg sc-svg" viewBox="0 0 %d %d" role="img" '
           'aria-label="单体算力中心的容量与折算算力排行">\n'
           '        <g class="ch-grid">%s</g>\n'
           '        <text class="ch-ax-t" x="8" y="14">站点 · 客户</text>\n'
           '        <text class="ch-ax-t" x="812" y="14" text-anchor="end">容量</text>\n'
           '        <text class="ch-ax-t" x="890" y="14" text-anchor="end">算力</text>\n'
           '        %s\n        <g class="sc-rows">%s</g>\n      </svg>'
           % (SW, h, grid, tick_t, "\n        ".join(body)))

    flag = "%s %s · 前 %d 站占全部容量 %.0f%%" % (
        esc(_cut(rows[0]["n"], 16)), S.gw(rows[0]["mw"]), len(rows),
        sum(x["mw"] for x in rows) / sum(x["mw"] for x in sites) * 100)

    lis = "".join("""        <li>
          <i class="ch-lo is-%s"></i><b>%s</b>
          <span class="ch-l-v">%s</span>
          <span class="ch-l-p">%s<small>EF</small></span>
        </li>""" % ("cn" if x["region"] == "中国" else "fk" if x["region"] == "美国" else "na",
                     esc(x["n"]), S.gw(x["mw"]), "{:,.0f}".format(x["ef"])) for x in rows)

    return ("%s"
            '    <div class="sc-wrap">\n'
            '      <div class="ch-top">\n'
            '        <span class="ch-flag">%s</span>\n'
            '        <span class="ch-key"><i class="sc-k-all"></i>公布总容量</span>\n'
            '        <span class="ch-key"><i class="sc-k-live"></i>已投运</span>\n'
            '        <span class="ch-key"><i style="background:%s"></i>中国</span>\n'
            '        <span class="ch-key"><i style="background:%s"></i>美国</span>\n'
            '        <span class="ch-key"><i style="background:%s"></i>其他</span>\n'
            '      </div>\n'
            '%s\n'
            '    </div>\n'
            '    <ul class="ch-list">\n%s\n    </ul>\n'
            '    <p class="ch-foot">%s</p>\n'
            '  </section>\n'
            % (_head(entry, idx, num_, "单体规模"), esc(flag),
               ORANGE, PURPLE, RED, svg, lis,
               R.inline(entry.get("foot") or
                        "浅色那条是业主公布的满产容量，深色是已经上电的部分。"
                        "组合口径（全国合计、州域合计）不进这张榜，否则同一个机柜会被数两次。")))
