#!/usr/bin/env python3
"""算力中心的读数层：四张区域榜 → 一个统一的站点列表。

为什么要有这一层：这四张表的口径天生合不起来——美国写 MW，中国写「万卡 /
万台服务器 / GW」，东南亚一半是「州域合计」这种组合口径。要画图就得先落到
一个共同的分母上，但**原始文字不能改**，读者要看业主原话。

所以：CSV 里保留原话（容量列），另加七列数值（MW / 现网MW / 投运 / 满产 /
代际 / 客户 / 分区）。数值列是研究出来的第二份口径，不是从文字里猜出来的，
这一点在页面上要说清。图和表都读这一层，避免「图和榜对不上」。

算力折算：EFLOPS = MW × 0.9 × 代际系数。0.9 的来历是 Colossus 1——300 MW
园区、约 23 万张 H100/H200/GB200 混合，折 280 EFLOPS，即 0.93 EF/MW。
代际系数按每瓦性能比 H100 抬多少：Blackwell 约 1.5、GB300 约 2.2、Rubin 约 2.6，
昇腾约 0.8，T2/TPU 约 1.0。这是**量级尺**，不是能租到的算力：实际达成率
通常只有 30–50%，上架率也没扣。
"""

import csv
import json

# 代际：标签、系数（相对 H100 的每瓦算力）
GEN = {
    "h100": ("H100 / H200", 0.9, "2022–2024"),
    "blackwell": ("GB200 / B200", 1.5, "2025–2026"),
    "gb300": ("GB300 / B300", 2.2, "2026–2027"),
    "rubin": ("Rubin", 2.6, "2027–2028"),
    "ascend": ("昇腾 910B / 910C", 0.8, "2023–2026"),
    "trainium": ("Trainium2", 1.0, "2025–2026"),
    "tpu": ("TPU v5e–v7", 1.0, "2023–2026"),
    "mix": ("混合代际", 1.2, "—"),
    "unknown": ("未披露", 1.0, "—"),
}

EF_PER_MW = 0.9          # H100 代每 MW 园区的折算系数，按 Colossus 1 校准

REGION = {"cn": "中国", "us": "美国", "sea": "东南亚"}
REGION_ORDER = ["中国", "美国", "东南亚", "其他"]

FILES = [
    ("算力中心-中国.csv", "中国"),
    ("算力中心-美国.csv", "美国"),
    ("算力中心-东南亚.csv", "东南亚"),
    ("算力中心-海外其他.csv", "其他"),
]


def _f(v):
    """CSV 里的空串 / '—' / 带逗号的数字，统一成 float 或 None。"""
    s = (v or "").strip().replace(",", "")
    if not s or s in ("-", "—", "未公布", "未披露"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _i(v):
    s = (v or "").strip()
    return int(s) if s.isdigit() else None


def region_of(zone):
    if not zone or zone == "-":
        return ""
    return REGION.get(zone.split("-")[0], "其他")


def ef(mw, gen):
    """MW → EFLOPS。gen 不认识就按 H100 代算，不悄悄丢行。"""
    if not mw:
        return 0.0
    return mw * EF_PER_MW * GEN.get(gen, GEN["unknown"])[1]


def load(sec):
    """读板块下四张算力中心表，返回站点列表（含算力在内的一切派生值）。

    agg=True 的是「全国组合 / 州域合计」这类组合行：它们是若干单体之和，
    加进任何合计都会重复计数，所以单独标出来，图里排除、表里照常显示。
    """
    out = []
    for fn, reg in FILES:
        p = sec.dir / fn
        if not p.exists():
            continue
        with p.open(encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                name = (r.get("站点") or "").strip()
                if not name:
                    continue
                mw = _f(r.get("MW"))
                live = _f(r.get("现网MW")) or 0.0
                gen = (r.get("代际") or "").strip() or "unknown"
                zone = (r.get("分区") or "").strip()
                cust = [c.strip() for c in (r.get("客户") or "").split("/") if c.strip()]
                out.append({
                    "n": name,
                    "owner": (r.get("业主") or "").strip(),
                    "city": (r.get("城市") or "").strip(),
                    "cap": (r.get("容量") or r.get("容量MW") or "").strip(),
                    "status": (r.get("状态") or "").strip(),
                    "chip": (r.get("芯片") or "").strip(),
                    "note": (r.get("备注") or "").strip(),
                    "mw": mw, "live": min(live, mw) if mw else live,
                    "y0": _i(r.get("投运")), "y1": _i(r.get("满产")),
                    "gen": gen, "cust": cust, "zone": zone, "src": fn,
                    "region": reg if reg != "其他" else "其他",
                    "agg": zone == "-",
                    "ef": ef(mw, gen), "ef_live": ef(min(live, mw) if mw else live, gen),
                })
    return out


def totals(sites):
    """只统计单体、且有 MW 的：组合行会重复计数，没公布容量的进不了合计。"""
    s = [x for x in sites if not x["agg"] and x["mw"]]
    return {
        "n": len(s), "mw": sum(x["mw"] or 0 for x in s),
        "live": sum(x["live"] or 0 for x in s),
        "ef": sum(x["ef"] for x in s), "ef_live": sum(x["ef_live"] for x in s),
        "agg": [x for x in sites if x["agg"]],
    }


def by_zone(sites):
    d = {}
    for x in sites:
        if x["agg"] or not x["zone"] or not x["mw"]:
            continue
        z = d.setdefault(x["zone"], {"mw": 0.0, "live": 0.0, "ef": 0.0,
                                     "ef_live": 0.0, "n": 0, "sites": [],
                                     "cust": {}, "region": x["region"]})
        z["mw"] += x["mw"]
        z["live"] += x["live"] or 0
        z["ef"] += x["ef"]
        z["ef_live"] += x["ef_live"]
        z["n"] += 1
        z["sites"].append(x)
        for c in x["cust"]:
            z["cust"][c] = z["cust"].get(c, 0.0) + (x["mw"] or 0)
    for z in d.values():
        z["sites"].sort(key=lambda s: -(s["mw"] or 0))
    return d


def by_region(sites):
    d = {k: {"mw": 0.0, "live": 0.0, "ef": 0.0, "n": 0} for k in REGION_ORDER}
    for x in sites:
        if x["agg"] or not x["mw"]:
            continue
        r = d.setdefault(x["region"], {"mw": 0.0, "live": 0.0, "ef": 0.0, "n": 0})
        r["mw"] += x["mw"]
        r["live"] += x["live"] or 0
        r["ef"] += x["ef"]
        r["n"] += 1
    return d


def by_cust(sites):
    """客户维度：一个客户在几个站点、多少 MW、折多少 EF。

    「未披露」不丢，单独一档——它恰好说明有多少容量还没公布租户。
    """
    d = {}
    for x in sites:
        if x["agg"] or not x["mw"]:
            continue
        names = x["cust"] or ["未披露"]
        # 一个站点多个客户时按等分记：宁可均分，也不假设谁占大头
        for c in names:
            v = d.setdefault(c, {"mw": 0.0, "ef": 0.0, "n": 0, "live": 0.0,
                                 "regions": {}})
            v["mw"] += x["mw"] / len(names)
            v["live"] += (x["live"] or 0) / len(names)
            v["ef"] += x["ef"] / len(names)
            v["n"] += 1
            v["regions"][x["region"]] = v["regions"].get(x["region"], 0) + 1
    return d


def gw(mw):
    """容量写法：≥1 GW 用 GW，其余用 MW。"""
    if not mw:
        return "—"
    if mw >= 1000:
        return "%.1f GW" % (mw / 1000.0)
    return "%d MW" % round(mw)


def efs(v):
    """算力写法：上万用「万」，避免一行里挤六位数。"""
    if not v:
        return "—"
    if v >= 10000:
        return "%.2f 万" % (v / 10000.0)
    if v >= 1000:
        return "{:,.0f}".format(v)
    return "%.0f" % v


def dump(sec):
    sites = load(sec)
    t = totals(sites)
    print("站点 %d（组合 %d）  %.1f GW  已投运 %.1f GW  %.0f EF / %.0f EF 现网"
          % (t["n"], len(t["agg"]), t["mw"] / 1000, t["live"] / 1000,
             t["ef"], t["ef_live"]))
    for r, v in by_region(sites).items():
        print("  %-6s %2d 站 %6.1f GW  %6.0f EF" % (r, v["n"], v["mw"] / 1000, v["ef"]))
    print("-- 客户 --")
    for c, v in sorted(by_cust(sites).items(), key=lambda kv: -kv[1]["mw"])[:14]:
        print("  %-16s %2d 站 %7.1f GW %6.0f EF" % (c, v["n"], v["mw"] / 1000, v["ef"]))


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "tools")
    import build_section as B
    for s in B.discover():
        if s.slug == "hardware":
            dump(s)
