"""平台价格库：把「谁在卖、卖多少」拆成两张表。

背景
----
原来的 api_prices.csv 只回答一个问题：厂商官方卖多少。但同一个模型在不同平台
是**不同的商品** —— 硅基流动的 deepseek-v4-pro、Azure 的 claude-sonnet-5，
价格、上下架、合规都不一样。只画一条官方线，看不出「换个平台买省多少」。

两张表（都在 13-算价/data/）
---------------------------
platforms.csv     平台注册表：platform_id / 中文名 / 是厂商自营还是转售 / 区域
price_points.csv  价格点：一行 = 某天某平台上某模型的一个价格

basis 是这张表的良心
-------------------
official      官网当期实录（有页面、有日期）
event         由已登记的调价事件回溯
carry         窗口内查不到调价、按现值往回填的**推定值**
snapshot      第三方快照的单点实测
snapshot_flat 快照覆盖期内恒定（first_seen 与 last_changed 相同，可证）
daily         日常快照自动落的点

跑法
----
    python3 llmcost_platforms.py            # 重建种子（保留日常累积的 daily 点）
    python3 llmcost_platforms.py --report   # 只打印统计，不写文件

重跑是幂等的：种子部分覆盖写，daily 部分原样保留。
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
DEFAULT_ROOT = Path(os.environ.get("LLMCOST_DIR") or (Path.home() / ".pocket-llmcost"))

PLATFORM_COLS = ["platform_id", "name", "name_en", "kind", "vendor", "region", "source_url", "note"]
POINT_COLS = ["date", "platform_id", "model", "tier", "currency", "input", "output", "cache_hit",
              "unit", "basis", "source", "note"]

# 「低谷价」这种口径不是折扣，是另一个商品：同一平台同一模型，白天和夜间两个价。
# 混在一条线上会画成「调价」，所以单独一列，图上单独一条线。
TIER_CN = {"standard": "标准价", "offpeak": "低谷价"}
MODEL_TIER = {"deepseek-v4-1-flash": "offpeak", "deepseek-v4-pro": "offpeak"}

# provider → (platform_id, 中文名, 英文名, kind, vendor, region)
# kind: official 厂商自营 / aggregator 第三方推理托管 / cloud 云厂商托管
PLATFORM_META: dict[str, tuple] = {
    # —— 厂商自营 ——
    "OpenAI": ("openai", "OpenAI", "OpenAI", "official", "OpenAI", "global"),
    "Anthropic": ("anthropic", "Anthropic", "Anthropic", "official", "Anthropic", "global"),
    "Google": ("google", "Google Gemini", "Google Gemini API", "official", "Google", "global"),
    "Google Gemini API": ("google", "Google Gemini", "Google Gemini API", "official", "Google", "global"),
    "xAI": ("xai", "xAI", "xAI", "official", "xAI", "global"),
    "Mistral": ("mistral", "Mistral", "Mistral AI", "official", "Mistral AI", "global"),
    "Mistral AI": ("mistral", "Mistral", "Mistral AI", "official", "Mistral AI", "global"),
    "DeepSeek": ("deepseek", "DeepSeek 官方", "DeepSeek", "official", "DeepSeek", "cn"),
    "Alibaba": ("aliyun", "阿里云百炼", "Alibaba Cloud Model Studio", "official", "Alibaba", "cn"),
    "Volcengine": ("volcengine", "火山引擎（豆包）", "Volcengine Ark", "official", "ByteDance", "cn"),
    "Moonshot": ("moonshot", "月之暗面", "Moonshot AI", "official", "Moonshot AI", "cn"),
    "Zhipu": ("zhipu", "智谱 AI", "Zhipu", "official", "Zhipu", "cn"),
    "Tencent": ("tencent", "腾讯混元", "Tencent Hunyuan", "official", "Tencent", "cn"),
    "Baidu": ("baidu", "百度智能云", "Baidu Qianfan", "official", "Baidu", "cn"),
    "MiniMax": ("minimax", "MiniMax", "MiniMax", "official", "MiniMax", "cn"),
    # —— 云厂商托管 ——
    "Amazon Bedrock": ("bedrock", "亚马逊 Bedrock", "Amazon Bedrock", "cloud", "AWS", "global"),
    "Microsoft Azure AI Foundry": ("azure", "微软 Azure", "Azure AI Foundry", "cloud", "Microsoft", "global"),
    "Google Cloud Vertex AI": ("vertex", "谷歌 Vertex", "Google Cloud Vertex AI", "cloud", "Google", "global"),
    "Databricks": ("databricks", "Databricks", "Databricks", "cloud", "Databricks", "global"),
    "Nebius Token Factory": ("nebius", "Nebius", "Nebius Token Factory", "cloud", "Nebius", "global"),
    "Cloudflare Workers AI": ("cloudflare", "Cloudflare", "Workers AI", "cloud", "Cloudflare", "global"),
    # —— 第三方推理托管（聚合/转售）——
    "SiliconFlow": ("siliconflow", "硅基流动", "SiliconFlow", "aggregator", "SiliconFlow", "cn"),
    "DeepInfra": ("deepinfra", "DeepInfra", "DeepInfra", "aggregator", "DeepInfra", "global"),
    "Together AI": ("together", "Together AI", "Together AI", "aggregator", "Together", "global"),
    "Fireworks AI": ("fireworks", "Fireworks AI", "Fireworks AI", "aggregator", "Fireworks", "global"),
    "Novita AI": ("novita", "Novita AI", "Novita AI", "aggregator", "Novita", "global"),
    "GMI Cloud": ("gmi", "GMI Cloud", "GMI Cloud", "aggregator", "GMI", "global"),
    "Baseten": ("baseten", "Baseten", "Baseten", "aggregator", "Baseten", "global"),
    "W&B Inference (CoreWeave)": ("coreweave", "CoreWeave", "W&B Inference", "aggregator", "CoreWeave", "global"),
    "FriendliAI": ("friendli", "FriendliAI", "FriendliAI", "aggregator", "FriendliAI", "global"),
    "Chutes": ("chutes", "Chutes", "Chutes", "aggregator", "Chutes", "global"),
    "Replicate": ("replicate", "Replicate", "Replicate", "aggregator", "Replicate", "global"),
}

KIND_CN = {"official": "官方", "aggregator": "第三方托管", "cloud": "云厂商"}

# 同一家厂商的人民币站与海外站不是一个商品：币种不同、定价也不同。
# 快照里这几家记的是美元价，必须与主表的人民币价分平台存放 ——
# 合并后同一天会出现两个价，图上只能二选一，等于伪造了一个「调价」。
INTL_META: dict[str, tuple] = {
    "Alibaba Cloud Model Studio": ("aliyun-intl", "阿里云百炼 国际站",
                                   "Alibaba Cloud Model Studio", "official", "Alibaba", "global"),
    "Moonshot AI": ("moonshot-intl", "月之暗面 国际站",
                    "Moonshot AI (global)", "official", "Moonshot AI", "global"),
    "Z.ai": ("zhipu-intl", "智谱 AI 国际站", "Z.ai", "official", "Zhipu", "global"),
    "MiniMax": ("minimax-intl", "MiniMax 国际站", "MiniMax (global)", "official", "MiniMax", "global"),
}


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], cols: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def platform_of(provider: str, snapshot: bool = False) -> tuple:
    """拿不到映射就地生成一个，别让新平台静默丢掉。

    快照来源先查 INTL_META：这里的 provider 名与主表重名，但卖的是海外站。
    """
    if snapshot and provider in INTL_META:
        return INTL_META[provider]
    hit = PLATFORM_META.get(provider)
    if hit:
        return hit
    pid = "".join(ch if ch.isalnum() else "-" for ch in provider.lower()).strip("-")
    return (pid or "unknown", provider, provider, "aggregator", provider, "global")


def latest_snapshot(data: Path) -> Path | None:
    files = sorted((data / "snapshots").glob("liutasil_*.csv"))
    return files[-1] if files else None


def build(root: Path | None = None, write: bool = True, verbose: bool = True) -> dict:
    """重建 platforms.csv / price_points.csv，返回统计。

    保留上一次文件里 basis=daily 的行（日常快照累积的，不是种子，不能冲掉）。
    """
    root = Path(root or DEFAULT_ROOT)
    data = root / "data"

    main = read_csv(data / "api_prices.csv")
    hist = read_csv(data / "price_history.csv")
    snap_path = latest_snapshot(data)
    snap = read_csv(snap_path) if snap_path else []

    models = {r["model"]: r for r in main}
    platforms: dict[str, dict] = {}
    points: dict[tuple, dict] = {}

    def add_point(p: dict) -> None:
        # 同一天、同平台、同模型、同口径只能有一个价；口径不同是两条线
        key = (p["date"], p["platform_id"], p["model"], p.get("tier") or "standard")
        points[key] = p

    def touch(provider: str, note: str = "", snapshot: bool = False) -> str:
        pid, name, name_en, kind, vendor, region = platform_of(provider, snapshot)
        if pid not in platforms:
            platforms[pid] = {"platform_id": pid, "name": name, "name_en": name_en,
                              "kind": kind, "vendor": vendor, "region": region,
                              "source_url": "", "note": note}
        return pid

    # ---- 1. 官方历史（price_history.csv 已经带 basis）----
    official_pairs: set[tuple[str, str]] = set()
    for r in hist:
        if r.get("model") not in models:
            continue
        pid = touch(r["provider"])
        official_pairs.add((pid, r["model"]))
        add_point({"date": r["date"], "platform_id": pid, "model": r["model"],
                   "tier": MODEL_TIER.get(r["model"], "standard"),
                   "currency": r["currency"], "input": r["input"], "output": r["output"],
                   "cache_hit": r.get("cache_hit", ""), "unit": r.get("unit") or "1M tokens",
                   "basis": r.get("basis") or "official", "source": "price_history.csv",
                   "note": r.get("note", "")})
    n_official = len(points)

    # ---- 2. 第三方快照 ----
    # 只认口径可比的记录：有 token 输入/输出价，且模型在主表里
    n_snap = 0
    n_skipped = 0
    by_slug: dict[str, dict] = {}
    for r in snap:
        if not r.get("input_usd_per_1m_tokens") or not r.get("output_usd_per_1m_tokens"):
            continue
        if r["model_slug"] not in models:
            continue
        by_slug.setdefault(r["model_slug"], {})[r["provider"]] = r

    for model, providers in by_slug.items():
        for provider, r in providers.items():
            pid = touch(provider, snapshot=True)
            # 主表已经有一手官方价的平台，不再采信快照的同平台记录：
            # 这个数据集对官方调价有滞后（Anthropic 还停在 10 USD），
            # 混进来会让官方线在 10/15 之间来回跳，看起来像调了两次价。
            if (pid, model) in official_pairs:
                n_skipped += 1
                continue
            first = (r.get("first_seen") or "")[:10]
            changed = (r.get("last_changed") or "")[:10]
            seen = (r.get("last_confirmed") or r.get("first_seen") or "")[:10]
            if not seen:
                continue
            usd = {"currency": "USD", "input": r["input_usd_per_1m_tokens"],
                   "output": r["output_usd_per_1m_tokens"],
                   "cache_hit": r.get("cached_input_usd_per_1m_tokens") or ""}
            note = "快照 %s 实测" % seen
            pnote = (r.get("price_note") or "").strip()
            if pnote:
                note += "；" + pnote
            # 口径提示：DeepSeek 主表记的是低谷价，快照是标准价（翻倍）
            if model.startswith("deepseek-") and provider == "DeepSeek":
                note += "；与主表低谷价口径不同（快照为标准价）"
            if changed and first and changed != first:
                note += "；%s 改过价，之前的价格未知" % changed
                start, basis = changed, "snapshot"
            elif first and changed == first:
                start, basis = first, "snapshot_flat"
            else:
                start, basis = seen, "snapshot"
            for day in {start, seen}:
                add_point({"date": day, "platform_id": pid, "model": model,
                           "tier": "standard", "unit": "1M tokens", "basis": basis,
                           "source": snap_path.name, "note": note, **usd})
                n_snap += 1

    # ---- 3. 保留上次的 daily 点 ----
    old = read_csv(data / "price_points.csv")
    kept = 0
    for r in old:
        if (r.get("basis") or "") == "daily":
            row = {c: r.get(c, "") for c in POINT_COLS}
            row["tier"] = row.get("tier") or "standard"
            add_point(row)
            kept += 1

    rows = sorted(points.values(), key=lambda p: (p["date"], p["model"], p["platform_id"]))
    used = {p["platform_id"] for p in points.values()}
    plats = sorted([p for p in platforms.values() if p["platform_id"] in used],
                   key=lambda p: ({"official": 0, "cloud": 1, "aggregator": 2}[p["kind"]], p["platform_id"]))

    if write:
        write_csv(data / "platforms.csv", plats, PLATFORM_COLS)
        write_csv(data / "price_points.csv", rows, POINT_COLS)

    stats = {"platforms": len(plats), "points": len(rows), "official_points": n_official,
             "snapshot_points": n_snap, "kept_daily": kept, "skipped_official": n_skipped,
             "models": len({r["model"] for r in rows}),
             "dates": sorted({r["date"] for r in rows}),
             "by_kind": {k: sum(1 for p in plats if p["kind"] == k) for k in KIND_CN},
             "span": [rows[0]["date"], rows[-1]["date"]] if rows else []}
    if verbose:
        print("平台 %d（官方 %d / 云厂商 %d / 第三方 %d）" % (
            stats["platforms"], stats["by_kind"]["official"],
            stats["by_kind"]["cloud"], stats["by_kind"]["aggregator"]))
        print("价格点 %d：官方 %d + 快照 %d + 保留日常 %d（同平台快照跳过 %d）" % (
            stats["points"], n_official, n_snap, kept, n_skipped))
        print("模型 %d 个，日期 %s → %s" % (stats["models"], stats["span"][0] if stats["span"] else "-",
                                          stats["span"][-1] if stats["span"] else "-"))
    return stats


if __name__ == "__main__":
    build(write="--report" not in sys.argv)
