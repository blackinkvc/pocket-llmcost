#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
track.py —— API / 套餐 / 本地部署 三维度价格追踪 + 准确性交叉校验 + 图表看板

和上一版 credit_audit.py 的关系：
  上一版解决「套餐积分 → token」的单点折算；这一版把它作为 audit-plans 子命令保留，
  主体改为「三条数据线的持续跟踪」，并引入开源方案与社区追踪作为交叉校验源。

核心设计：
  1) 三张主表（data/*.csv）每行都带 source_url / verified_at / source_type / price_version，
     口径字段（币种、峰谷、促销、缓存价、是否第三方托管）单独成列，避免混比。
  2) observations = 内置社区观测 + 开源数据快照（AICostBudget / Liutasil501 / LiteLLM /
     LLMTracker / pricemon / OpenRouter）。verify 逐条比对，输出 confirmed / single_source /
     stale / unverified / conflict / incomparable，并生成 diff 变更日志。
  3) chart 生成自包含 HTML + 独立 SVG：API 价对比、套餐 vs API 回本临界、
     本地部署成本 vs 利用率、数据准确性面板、三路径单位成本对照。

纯标准库，Python 3.8+。联网只用于 fetch；离线可用内置快照跑完 verify 与 chart。

用法：
  python3 track.py init                 # 生成基线快照
  python3 track.py fetch --only aicostbudget,liutasil,llmtracker
  python3 track.py verify               # 准确性检查 + 调价 diff
  python3 track.py chart                # 生成 out/dashboard.html 与 4 张 SVG
  python3 track.py report               # Markdown 汇总
  python3 track.py all                  # init → verify → chart → report
  python3 track.py audit-plans usage.csv --model glm-5.2   # 复用上一版折算引擎
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

# 代码和数据分家：代码跟着这个仓库走，数据留在外面（可以备份、可以同步、
# 可以在两台机器上共用一个目录）。数据目录按这个顺序找：
#   1. 环境变量 LLMCOST_DIR（中台的启动脚本会写死它）
#   2. ~/.pocket-llmcost（单独跑、什么都不配时的默认值）
# 别把 data/ 放进仓库：git pull 会和每天落点写进去的历史打架。
CST = timezone(timedelta(hours=8))


def default_root() -> str:
    env = (os.environ.get("LLMCOST_DIR") or "").strip()
    if env:
        return os.path.expanduser(env)
    return os.path.join(os.path.expanduser("~"), ".pocket-llmcost")


ROOT = default_root()
DATA = os.path.join(ROOT, "data")
SNAP = os.path.join(DATA, "snapshots")
OUT = os.path.join(ROOT, "out")
# 仓库自带的种子数据（公开价目的一份快照）。第一次跑时补进数据目录，
# 让新装的人打开就有东西看，而不是一张空表。
SEED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed")


def today() -> str:
    """今天（北京时间）。原版把日期写死成 2026-11-19，跑几天后新鲜度就全错了。"""
    return datetime.now(CST).strftime("%Y-%m-%d")


# 模块级常量保持原版的写法（下面几十处直接用 TODAY），但每次 compute 前会刷新一次，
# 服务常驻跨天也不用重启。
TODAY = today()

STATUS_ORDER = ["conflict", "unverified", "stale", "incomparable",
                "uncovered", "single_source", "confirmed"]
STATUS_CN = {
    "confirmed": "多源一致",
    "single_source": "单源待补",
    "stale": "数据过期",
    "unverified": "缺来源/核验日期",
    "conflict": "数值冲突",
    "incomparable": "口径不可比",
    "uncovered": "无交叉观测",
}
# ---- 图表配色：墨色为主，朱砂点睛，三种语义色（蓝=套餐 / 绿=本地 / 赭=事件）
C_INK = "#17191b"
C_TXT = "#3f454c"
C_MUTE = "#8a9098"
C_RULE = "#e6e2d8"
C_RULE2 = "#f1eee6"
C_ACC = "#a33a26"
C_BAR = "#6a6f76"
SERIES = ["#33536e", "#a33a26", "#3f6b53", "#8a6a4e", "#5c5470",
          "#2f6b70", "#6b6f76", "#94706a"]

STATUS_COLOR = {
    "confirmed": "#3f6b53", "single_source": "#8d6417", "stale": "#9c6b2f",
    "unverified": "#9aa1a6", "conflict": "#a33a26", "incomparable": "#6a5583",
    "uncovered": "#9aa1a6",
}


# ---------------------------------------------------------------------------
# 通用
# ---------------------------------------------------------------------------

def ensure_dirs():
    for d in (DATA, SNAP, OUT):
        os.makedirs(d, exist_ok=True)
    seed_data()


def seed_data() -> int:
    """把仓库里的种子文件补进数据目录，只补缺、不覆盖。

    为什么只补缺：seed/ 是发布那一刻的快照，用户跑几天后 data/ 里已经长出
    自己的历史，拿旧快照盖回去等于把这几天的记录删了。
    返回补了几个文件（给 --json 之类的调试用）。
    """
    if not os.path.isdir(SEED):
        return 0
    n = 0
    for name in sorted(os.listdir(SEED)):
        src = os.path.join(SEED, name)
        dst = os.path.join(DATA, name)
        if os.path.isfile(src) and not os.path.exists(dst):
            try:
                shutil.copy2(src, dst)
                n += 1
            except OSError:
                pass
    return n


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def num(v, default=None):
    try:
        s = str(v).strip()
        return float(s) if s else default
    except (ValueError, TypeError):
        return default


def norm_key(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def parse_date(s):
    s = (s or "").strip()[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=CST)
    except ValueError:
        return None


def days_old(s):
    d = parse_date(s)
    if not d:
        return 9999
    return max(0, (datetime.now(CST) - d).days)


def day_axis(d0, d1, x0, x1, min_gap=40.0, must=()):
    """横轴按天排刻度，返回 [(date, x, major, labeled)]。

    画线用 grid，写字用 labels，两者分开：
    - grid = 每周一 + 每月 1 号 + 观测日，线一律画出来（周的节奏看得见）；
    - labels 走优先级，冲突时低优先级让位：
      0. 首末两天（右端不标，读者就不知道线画到哪天为止），
      1. 观测日（图上真正有信息的那几天），
      2. 从起点起每 7 天（保证间距有规律，不会一处 4 天一处 12 天），
      3. 每月 1 号。
    原来只标 08-19 / 09-19 / 10-19 / 11-19，看着像月度数据，
    真正该读的「9 月 19 号涨到 108」反而没标；现在观测日必标。
    """
    span = max(1, (d1 - d0).days)
    dx = (x1 - x0) / span
    at = lambda day: x0 + (day - d0).days * dx

    must_days = {d for d in (parse_date(x) for x in must) if d and d0 <= d <= d1}
    must_days.update({d0, d1})

    grid = set(must_days)
    day = d0
    while day <= d1:
        if day.weekday() == 0 or day.day == 1:
            grid.add(day)
        day += timedelta(days=1)

    # 首末两天优先级最高：右端日期被一个相邻观测日挤掉，读者就不知道线画到哪天为止
    cands = [(0, d0), (0, d1)]
    cands += [(1, d) for d in sorted(must_days - {d0, d1})]
    cands += [(2, d0 + timedelta(days=7 * k)) for k in range(1, span // 7 + 1)]
    cands += [(3, d) for d in grid if d.day == 1]
    cands.sort()

    labels = []
    for pri, d in cands:
        if not (d0 <= d <= d1) or any(d == x[0] for x in labels):
            continue
        x = at(d)
        if all(abs(x - lx) >= min_gap for _, lx in labels):
            labels.append((d, x))
    marked = {d for d, _ in labels}

    return [(d, at(d), d.day == 1, d in marked) for d in sorted(grid | marked)]


def fmt(v, digits=2):
    return ("%%.%df" % digits) % v if isinstance(v, (int, float)) else "—"


def load_sources():
    with open(os.path.join(DATA, "sources.json"), "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 观测收集：内置社区观测 + 开源数据快照 + fetch 新拉的文件
# ---------------------------------------------------------------------------

OBS_FIELDS = ["source_id", "provider", "model", "metric", "value", "currency",
              "unit", "scope", "price_kind", "captured_at", "url", "note"]


def _obs(source_id, provider, model, metric, value, currency="USD", unit="1M tokens",
         scope="first_party", price_kind="standard", captured_at=TODAY, url="", note=""):
    if value is None or value == "":
        return None
    return dict(source_id=source_id, provider=provider, model=model, metric=metric,
                value=float(value), currency=currency, unit=unit, scope=scope,
                price_kind=price_kind, captured_at=captured_at, url=url, note=note)


def parse_aicostbudget(path, source_id="aicostbudget"):
    out = []
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    stamp = (d.get("last_verified_at") or d.get("generated_at") or TODAY)[:10]
    for m in d.get("models", []):
        p, pid, mid = m.get("pricing") or {}, m.get("provider_id", ""), m.get("model_id", "")
        url = m.get("official_source_url") or ""
        for k, field in (("input", "input"), ("output", "output"), ("cache_hit", "cached_input")):
            o = _obs(source_id, pid, mid, k, p.get(field), p.get("currency", "USD"),
                     "1M tokens", "first_party", "standard", stamp, url,
                     "AICostBudget 真实快照；模型 %s" % mid)
            if o:
                out.append(o)
    return out


def parse_liutasil(path, source_id="liutasil"):
    out = []
    for r in read_csv(path):
        # 只取 text 类：image / video / embedding / tts 的计价单位不同，不参与 token 比对
        if (r.get("category") or "").lower() != "text":
            continue
        scope = "first_party" if (r.get("provider_type") or "") == "first_party" else "reseller"
        stamp = (r.get("last_confirmed") or TODAY)[:10]
        for k, col in (("input", "input_usd_per_1m_tokens"),
                       ("output", "output_usd_per_1m_tokens"),
                       ("cache_hit", "cached_input_usd_per_1m_tokens")):
            o = _obs(source_id, r.get("provider_id", ""), r.get("model_slug", ""), k,
                     r.get(col), "USD", "1M tokens", scope, "standard", stamp,
                     r.get("source_url", ""), "provider=%s confidence=%s" %
                     (r.get("provider_id", ""), r.get("confidence", "")))
            if o:
                out.append(o)
    return out


def parse_litellm(path, source_id="litellm"):
    out = []
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    for mid, m in d.items():
        if not isinstance(m, dict) or mid == "sample_spec":
            continue
        prov = m.get("litellm_provider", "")
        # LiteLLM 的 key 常带 provider/区域前缀（如 us.anthropic.claude-sonnet-5），
        # 取最后一段还原成主表使用的模型名，否则永远匹配不上。
        clean = mid.split("/")[-1].split(".")[-1]
        # 区域端点 / 第三方托管（azure/eu、kyma、us-gov、bedrock…）是渠道价差，
        # 不能当官方直连价参与一致性判定，否则会把 +20% 的区域加价误报成调价。
        low = mid.lower()
        channel_marks = ("azure", "bedrock", "vertex", "us-gov", "us.", "eu/",
                         "global.", "jp.", "au.", "kyma", "databricks", "fireworks",
                         "together", "deepinfra", "novita", "gmi", "nebius")
        scope = "reseller" if any(mk in low for mk in channel_marks) else "first_party"
        for k, field in (("input", "input_cost_per_token"),
                         ("output", "output_cost_per_token"),
                         ("cache_hit", "cache_read_input_token_cost")):
            v = num(m.get(field))
            o = _obs(source_id, prov, clean, k, v * 1e6 if v is not None else None,
                     "USD", "1M tokens", scope, "standard", TODAY,
                     "https://github.com/BerriAI/litellm",
                     "LiteLLM price map ×1e6；原始 key=%s；%s" %
                     (mid, "渠道/区域端点" if scope == "reseller" else "官方条目"))
            if o:
                out.append(o)
    return out


def parse_pricemon(path, source_id="pricemon"):
    out = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return out
    for m in d.get("data", []):
        cur = m.get("currency", "CNY")
        for k, field in (("input", "input"), ("output", "output"), ("cache_hit", "cacheRead")):
            o = _obs(source_id, m.get("vendor", ""), m.get("modelId", ""), k,
                     m.get(field), cur, "1M tokens", "first_party",
                     "promo" if m.get("note") and "活动" in m.get("note") else "standard",
                     (m.get("updatedAt") or TODAY)[:10], m.get("sourceUrl", ""),
                     m.get("note", ""))
            if o:
                out.append(o)
    return out


def parse_openrouter(path, source_id="openrouter"):
    out = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return out
    for m in d.get("data", [])[:400]:
        p = m.get("pricing") or {}
        mid = m.get("id", "")
        for k, field in (("input", "prompt"), ("output", "completion")):
            v = num(p.get(field))
            o = _obs(source_id, "openrouter", mid, k, v * 1e6 if v is not None else None,
                     "USD", "1M tokens", "reseller", "standard", TODAY,
                     "https://openrouter.ai/api/v1/models", "OpenRouter 聚合报价")
            if o:
                out.append(o)
    return out


def parse_llmtracker_changelog(path):
    """变更日志不参与数值比对，只作为「别人也追踪到调价」的证据。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return []
    return [{"model_id": c.get("model_id"), "change_type": c.get("change_type"),
             "generated_at": d.get("generated_at", "")} for c in d.get("changes", [])]


def collect_observations():
    obs = []
    builtin = os.path.join(DATA, "observations_builtin.csv")
    for r in read_csv(builtin):
        o = _obs(r.get("source_id", ""), r.get("provider", ""), r.get("model", ""),
                 r.get("metric", ""), r.get("value"), r.get("currency", "USD"),
                 r.get("unit", ""), r.get("scope", "first_party"),
                 r.get("price_kind", "standard"), r.get("captured_at", TODAY),
                 r.get("url", ""), r.get("note", ""))
        if o:
            obs.append(o)

    # 快照按 <source_id>_* 命名，fetch 与手工保存的文件用同一套解析器
    parsers = {
        "aicostbudget": (parse_aicostbudget, "*.json"),
        "liutasil": (parse_liutasil, "*.csv"),
        "litellm": (parse_litellm, "*.json"),
        "pricemon": (parse_pricemon, "*.json"),
        "openrouter": (parse_openrouter, "*.json"),
    }
    import glob
    loaded, external_changes = [], []
    for sid, (fn, pat) in parsers.items():
        for p in sorted(glob.glob(os.path.join(SNAP, sid + "_" + pat))):
            if "observations" in p:
                continue
            try:
                got = fn(p)
                obs.extend(got)
                loaded.append((os.path.basename(p), len(got)))
            except Exception as e:
                loaded.append((os.path.basename(p), "ERROR %s" % e))
    for p in sorted(glob.glob(os.path.join(SNAP, "llmtracker_*.json"))):
        try:
            ch = parse_llmtracker_changelog(p)
            external_changes.extend(ch)
            loaded.append((os.path.basename(p), "%d 条外部调价事件" % len(ch)))

        except Exception as e:
            loaded.append((os.path.basename(p), "ERROR %s" % e))

    # 同一来源+模型+指标+数值去重（防止快照与内置表重复）
    seen, uniq = set(), []
    for o in obs:
        k = (o["source_id"], norm_key(o["model"]), o["metric"], round(o["value"], 6),
             o["currency"], o["price_kind"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(o)
    return uniq, loaded, external_changes


# ---------------------------------------------------------------------------
# fetch：在线拉取开源源，失败优雅降级
# ---------------------------------------------------------------------------

def _slim_litellm(raw):
    """LiteLLM 全量 7000+ 条目，只保留主表涉及模型，避免把 5MB 文件塞进快照。"""
    import glob as _glob
    d = json.loads(raw.decode("utf-8"))
    keys = {norm_key(r["model"]) for r in read_csv(os.path.join(DATA, "api_prices.csv"))}
    sel = {}
    for mid, m in d.items():
        if not isinstance(m, dict):
            continue
        n = norm_key(mid.split("/")[-1].split(".")[-1])
        if any(k in n or (len(n) > 6 and n in k) for k in keys):
            sel[mid] = m
    if "sample_spec" in d:
        sel["sample_spec"] = d["sample_spec"]
    return json.dumps(sel, ensure_ascii=False).encode("utf-8")


def fetch_sources(only=None, include_heavy=False, timeout=25):
    cfg = load_sources()
    status = []
    ua = "Mozilla/5.0 (compatible; llm-cost-tracker/1.0; +local research)"
    import glob
    for s in cfg["sources"]:
        sid, url = s["id"], s.get("fetch_url", "")
        if not url:
            continue
        if only and sid not in only:
            continue
        ext = {  # 按源固定，不能从 URL 后缀猜（OpenRouter /api/v1/models 返回 JSON）
            "aicostbudget": ".json", "litellm": ".json", "llmtracker": ".json",
            "pricemon": ".json", "openrouter": ".json", "liutasil": ".csv",
        }.get(sid, ".json")
        dest = os.path.join(SNAP, "%s_%s%s" % (sid, TODAY, ext))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua,
                                                       "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if (resp.headers.get("Content-Encoding") or "").lower() == "gzip":
                    import gzip
                    raw = gzip.decompress(raw)
            if sid == "litellm":
                raw = _slim_litellm(raw)
            with open(dest, "wb") as f:
                f.write(raw)
            status.append({"id": sid, "status": "ok", "bytes": len(raw), "path": dest})
        except Exception as e:
            cached = glob.glob(os.path.join(SNAP, sid + "_*"))
            status.append({"id": sid,
                           "status": "fallback_cached" if cached else "failed",
                           "reason": "%s: %s" % (type(e).__name__, e),
                           "cached_files": [os.path.basename(p) for p in cached][:3]})
    with open(os.path.join(OUT, "fetch_status.json"), "w", encoding="utf-8") as f:
        json.dump({"at": datetime.now(CST).isoformat(), "results": status}, f,
                  ensure_ascii=False, indent=2)
    for r in status:
        print("  [%s] %s %s" % (r["status"].upper(), r["id"],
                                r.get("bytes", r.get("reason", ""))))
    return status


# ---------------------------------------------------------------------------
# 成本计算
# ---------------------------------------------------------------------------

def to_cny(row, field, fx):
    v = num(row.get(field))
    if v is None:
        return None
    return v * fx if (row.get("currency") or "CNY").upper() == "USD" else v


def api_costs(cfg, fx):
    out = []
    for r in read_csv(os.path.join(DATA, "api_prices.csv")):
        out.append({
            "provider": r["provider"], "model": r["model"], "display": r["display"],
            "currency": r["currency"], "input": num(r["input"]), "output": num(r["output"]),
            "cache_hit": num(r.get("cache_hit")),
            "batch_off": num(r.get("batch_off")),
            "input_cny": to_cny(r, "input", fx), "output_cny": to_cny(r, "output", fx),
            "cache_cny": to_cny(r, "cache_hit", fx),
            "price_kind": r["price_kind"], "scope": r["provider_scope"],
            "peak": r.get("peak_offpeak") or "no", "promo_until": r.get("promo_until") or "",
            "price_version": r.get("price_version") or "",
            "source_url": r["source_url"], "verified_at": r["verified_at"],
            "source_type": r["source_type"], "note": r["note"],
            "key": (norm_key(r["provider"]), norm_key(r["model"])),
        })
    return out


def plan_effective(r, cache_ratio, output_ratio, fx):
    """把套餐折算成「元 / 百万 token」；不可折算返回 (None, 原因)。"""
    total = num(r.get("total_credits"), 0) or 0
    monthly = num(r.get("monthly_cny"), 0) or 0
    kind = (r.get("unit_kind") or "").strip()
    A, C, B = num(r.get("coeff_A")), num(r.get("coeff_C")), num(r.get("coeff_B"))
    miss = max(0.0, 1 - cache_ratio - output_ratio)

    if kind == "credits" and all(v is not None for v in (A, C, B)) and (A + C + B) > 0:
        per_m_credits = A * miss + C * cache_ratio + B * output_ratio
        if total <= 0:
            return None, "credits 总额度为空"
        cny_per_credit = monthly / total
        return per_m_credits * cny_per_credit, "三档系数折算"

    if kind in ("requests", "AFP", "fixed_tokens") and total > 0:
        tpc = num(r.get("token_per_credit"), 0) or 0
        total_tokens = total * tpc
        if total_tokens <= 0:
            return None, "缺少每单位额度可换 token 数"
        return monthly / (total_tokens / 1e6), "固定额度折算（缓存不打折）"

    if kind == "percent":
        return None, "官方只给消耗百分比，无 token 明细，不可直接折算"

    if kind == "credits_formula":
        return None, "积分公式公开但系数未录入，需抓包拟合（见 audit-plans）"

    if kind == "credits":
        return None, "缺少三档系数，需 audit-plans 拟合或手工录入"
    return None, "未知计费单位"


def plan_costs(cfg, cache_ratio, output_ratio, fx):
    out = []
    for r in read_csv(os.path.join(DATA, "plans.csv")):
        c, why = plan_effective(r, cache_ratio, output_ratio, fx)
        out.append({
            "platform": r["platform"], "plan": r["plan"],
            "monthly_cny": num(r["monthly_cny"], 0),
            "total_credits": num(r["total_credits"], 0),
            "unit_kind": r["unit_kind"], "window": r["window_rule"],
            "cny_per_1m": c, "convertible": c is not None, "why": why,
            "source_url": r["source_url"], "verified_at": r["verified_at"],
            "source_type": r["source_type"], "note": r["note"],
            "limit_5h": r["limit_5h"], "promo_until": r["promo_until"],
        })
    return out


def local_cost(r, utilization, fx=None):
    """(月折旧 + 月电费) / (利用率 × 月秒数 × tok/s) × 1e6  → 元/百万 token"""
    hw = num(r.get("hardware_cny"), 0) or 0
    years = num(r.get("depreciation_years"), 3) or 3
    power = num(r.get("power_w"), 0) or 0
    price = num(r.get("electricity_cny_kwh"), 0.55) or 0.55
    tok = num(r.get("tok_s"), 0) or 0
    if tok <= 0 or utilization <= 0:
        return None
    monthly_kwh = power / 1000.0 * 24 * 30
    monthly_fixed = hw / (years * 12) + monthly_kwh * price
    monthly_tokens = tok * 3600 * 24 * 30 * utilization
    return monthly_fixed / (monthly_tokens / 1e6)


def local_costs():
    return [dict(r) for r in read_csv(os.path.join(DATA, "local_rigs.csv"))]


# ---------------------------------------------------------------------------
# verify：多源交叉 + provenance + freshness + 口径隔离 + diff
# ---------------------------------------------------------------------------

def verify_data(cfg, obs, loaded, external_changes=None):
    pol = cfg["accuracy_policy"]
    fx = cfg["fx_usd_cny"]
    tol = pol["conflict_tolerance"]
    stale_days = pol["stale_days"]
    api = api_costs(cfg, fx)
    plans = plan_costs(cfg, 0.95, 0.005, fx)
    rigs = local_costs()

    results = []
    for row in api:
        kinds = set((row["price_kind"] or "standard").replace("+", ",").split(","))
        flags, notes, agreeing, conflicts, spreads = [], [], [], [], []
        model_key = row["key"][1]
        matched = 0   # 有任何一条观测命中该模型（含币种/口径不一致）

        for o in obs:
            if o["metric"] not in ("input", "output", "cache_hit"):
                continue
            # 精确匹配模型名：避免 glm-5-3 误命中 glm-5-3-flash 之类的前缀串扰
            if norm_key(o["model"]) != model_key:
                continue
            matched += 1
            if o["currency"] != row["currency"]:
                notes.append("币种不同（%s vs %s），不混比：%s" %
                             (row["currency"], o["currency"], o["source_id"]))
                flags.append("incomparable")
                continue
            okind = set((o["price_kind"] or "standard").replace("+", ",").split(","))
            if not (okind & kinds):
                notes.append("口径不同（%s vs %s），不参与比对：%s" %
                             (row["price_kind"], o["price_kind"], o["source_id"]))
                flags.append("incomparable")
                continue
            main_v = num(row.get(o["metric"]))
            if main_v is None or main_v == 0:
                continue
            rel = abs(o["value"] - main_v) / main_v
            if o["scope"] == "reseller":
                spreads.append({"source": o["source_id"], "metric": o["metric"],
                                "value": o["value"], "main": main_v, "rel": rel,
                                "note": o["note"]})
                continue
            if rel > tol:
                conflicts.append({"source": o["source_id"], "metric": o["metric"],
                                  "value": o["value"], "main": main_v, "rel": rel,
                                  "note": o["note"], "url": o["url"]})
            else:
                agreeing.append(o["source_id"])

        # provenance
        if not row["source_url"] or not row["verified_at"] or not row["source_type"]:
            flags.append("unverified")
        if days_old(row["verified_at"]) > stale_days:
            flags.append("stale")
        n_sources = len(set(agreeing))
        if conflicts:
            flags.append("conflict")
        elif n_sources >= pol["min_sources_for_confirmed"]:
            flags.append("confirmed")
        elif n_sources == 1:
            flags.append("single_source")
        elif matched == 0:
            flags.append("uncovered")

        # 总体状态按「信息价值」判定：有同口径一致来源时优先显示一致/单源，
        # 口径不可比只作为附注，避免把「有 1 个来源对上了」误报成不可比。
        if conflicts:
            overall = "conflict"
        elif "unverified" in flags:
            overall = "unverified"
        elif "stale" in flags:
            overall = "stale"
        elif n_sources >= pol["min_sources_for_confirmed"]:
            overall = "confirmed"
        elif n_sources == 1:
            overall = "single_source"
        elif matched > 0:
            overall = "incomparable"
        else:
            overall = "uncovered"
        results.append({
            "provider": row["provider"], "model": row["model"], "display": row["display"],
            "currency": row["currency"], "output": row["output"],
            "output_cny": row["output_cny"], "price_kind": row["price_kind"],
            # 明细列也带上：页面要显示输入价 / 缓存价，不能只留输出价
            "input": row["input"], "input_cny": row["input_cny"],
            "cache_hit": row["cache_hit"], "cache_cny": row["cache_cny"],
            "scope": row["scope"], "peak": row["peak"],
            "promo_until": row["promo_until"], "price_version": row["price_version"],
            "source_type": row["source_type"], "note": row["note"],
            "verified_at": row["verified_at"], "source_url": row["source_url"],
            "status": overall, "all_flags": sorted(set(flags), key=lambda s: STATUS_ORDER.index(s)),
            "agreeing_sources": sorted(set(agreeing)), "n_sources": n_sources,
            "n_matched": matched, "conflicts": conflicts,
            "reseller_spreads": spreads, "notes": notes[:6],
        })

    # 套餐/本地的准确性：以「是否有来源 + 是否过期 + 是否标注为估算」为准
    aux = []
    for p in plans:
        st = "confirmed"
        why = []
        if not p["source_url"] or not p["verified_at"]:
            st, why = "unverified", ["缺来源或核验日期"]
        elif days_old(p["verified_at"]) > stale_days:
            st, why = "stale", ["超过 %d 天未复核" % stale_days]
        if "community" in (p["source_type"] or ""):
            why.append("含社区实测/推算，非官方承诺")
        if p["promo_until"]:
            d = parse_date(p["promo_until"])
            if d and d < datetime.now(CST):
                why.append("活动已到期：%s" % p["promo_until"])
        aux.append({"kind": "plan", "name": "%s · %s" % (p["platform"], p["plan"]),
                    "status": st, "convertible": p["convertible"],
                    "cny_per_1m": p["cny_per_1m"], "why": "；".join(why) or "—",
                    "source_url": p["source_url"], "verified_at": p["verified_at"]})
    for r in rigs:
        st = "confirmed"
        why = []
        if "estimate" in (r.get("source_type") or "") or "community" in (r.get("source_type") or ""):
            why.append("社区实测/估算，非受控基准")
        if not r.get("source_url") or not r.get("verified_at"):
            st = "unverified"
        if days_old(r.get("verified_at")) > stale_days:
            st = "stale"
        aux.append({"kind": "local", "name": r["rig"], "status": st, "convertible": True,
                    "cny_per_1m": local_cost(r, num(r.get("utilization"), 0.3) or 0.3),
                    "why": "；".join(why) or "—", "source_url": r.get("source_url"),
                    "verified_at": r.get("verified_at")})

    # diff：与上一份主表快照比对。
    # 注意排除「今天这份」——原版拿 snaps[-1] 比，第一次跑完当天快照就变成自己，
    # 之后再跑永远 diff 为空，调价日志形同虚设。
    import glob
    snaps = sorted(p for p in glob.glob(os.path.join(SNAP, "api_prices_*.csv"))
                   if not p.endswith("api_prices_%s.csv" % TODAY))
    changes = []
    if snaps:
        old = {(norm_key(r["provider"]), norm_key(r["model"])): r for r in read_csv(snaps[-1])}
        cur = {(norm_key(r["provider"]), norm_key(r["model"])): r for r in read_csv(os.path.join(DATA, "api_prices.csv"))}
        for k, r in cur.items():
            if k not in old:
                changes.append({"type": "新增", "model": r["model"], "detail": "新纳入追踪", "at": TODAY})
                continue
            for f in ("input", "output", "cache_hit"):
                a, b = num(old[k].get(f)), num(r.get(f))
                if a is not None and b is not None and abs(a - b) > 1e-9:
                    changes.append({"type": "调价", "model": r["model"],
                                    "detail": "%s %s → %s %s" % (f, a, b, r["currency"]), "at": TODAY})
        for k, r in old.items():
            if k not in cur:
                changes.append({"type": "下线", "model": r.get("model", ""), "detail": "已移出追踪", "at": TODAY})
    # 保存本次基线
    base = read_csv(os.path.join(DATA, "api_prices.csv"))
    write_csv(os.path.join(SNAP, "api_prices_%s.csv" % TODAY), base, list(base[0].keys()))
    with open(os.path.join(OUT, "changelog.md"), "w", encoding="utf-8") as f:
        f.write("# 价格变更日志（对齐 pricemon /api/changes 与 LLMTracker changelog 思路）\n\n")
        f.write("基线快照：`data/snapshots/api_prices_%s.csv`\n\n" % TODAY)
        if changes:
            f.write("| 类型 | 模型 | 变化 | 日期 |\n|---|---|---|---|\n")
            for c in changes:
                f.write("| %s | %s | %s | %s |\n" % (c["type"], c["model"], c["detail"], c["at"]))
        else:
            f.write("本轮与上一基线无差异。\n")
        f.write("\n> 别人的追踪：LLMTracker 每 6 小时产出 `data/changelog/latest.json`；"
                "pricemon `/api/changes` 与公众号「LLM API 价格日报」每日记录调价/上下架/活动截止。"
                "本表只在本地快照之间做 diff，联网 diff 请跑 `fetch` 后查看 out/fetch_status.json。\n")

    counts = {s: sum(1 for r in results if r["status"] == s) for s in STATUS_ORDER}
    data = {
        "generated_at": datetime.now(CST).isoformat(),
        "data_date": TODAY,
        "fx_usd_cny": fx,
        "policy": pol,
        "counts": counts,
        "api": results,
        "aux": aux,
        "observations_total": len(obs),
        "snapshot_files": loaded,
        "external_changes": external_changes or [],
        "source_coverage": {},
        "changes": changes,
        "plans": plans,
        "rigs": rigs,
    }
    for s in cfg["sources"]:
        sid = s["id"]
        data["source_coverage"][sid] = {
            "name": s["name"], "weight": s["weight"], "kind": s["kind"],
            "covers": s["covers"],
            "n_obs": sum(1 for o in obs if o["source_id"] == sid),
            "n_events": len(external_changes or []) if sid == "llmtracker" else 0,
        }
    data["timeline"] = build_timeline(obs, data)
    data["history"] = build_price_history(data)
    data["panorama"] = build_price_panorama(data)
    with open(os.path.join(OUT, "accuracy.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def write_accuracy_report(d):
    lines = ["# 三维度数据准确性检查报告", "",
             "数据截止：**%s**（静态快照）｜统一口径：每百万 token｜USD→CNY 按 %.1f 仅作可比换算"
             % (d["data_date"], d["fx_usd_cny"]),
             "",
             "> 校验源：LiteLLM / AICostBudget / Liutasil501 ai-api-prices / MrUnreal LLMTracker / "
             "pricemon.net / OpenRouter / llmprice.gitlab.io / 模真真 B 站实测 / 公众号价格日报 / "
             "llmstatus.io / 本地实测汇总。口径不一致（促销、峰谷、第三方托管、币种）不参与数值比对。",
             "", "## 一、总体", "",
             "| 状态 | 条数 | 含义 |", "|---|---:|---|"]
    for s in STATUS_ORDER:
        lines.append("| %s | %d | %s |" % (STATUS_CN[s], d["counts"][s], {
            "confirmed": "≥2 个独立来源数值一致", "single_source": "只有 1 个来源，需补交叉",
            "stale": "超过 %d 天未复核" % d["policy"]["stale_days"],
            "unverified": "缺来源链接 / 核验日期 / 来源类型",
            "conflict": "偏差 > %.0f%%" % (d["policy"]["conflict_tolerance"] * 100),
            "incomparable": "观测与主表口径（峰谷/促销/币种）不一致，已隔离",
            "uncovered": "本轮开源源未收录该模型，仅官方一手来源，需补交叉",
        }[s]))
    lines += ["", "观测总数：**%d** 条；本轮载入的开源快照：" % d["observations_total"], ""]
    for name, n in d["snapshot_files"]:
        label = n if isinstance(n, str) else "%d 条" % n
        lines.append("- `%s` → %s" % (name, label))
    lines += ["", "## 二、API 逐条核验", "",
              "| 厂商 / 模型 | 输出价 | 口径 | 状态 | 一致来源 | 冲突 / 说明 |",
              "|---|---:|---|---|---|---|"]
    for r in d["api"]:
        detail = []
        for c in r["conflicts"][:2]:
            detail.append("**%s %s %s vs 主表 %s（偏差 %.0f%%）**" %
                          (c["source"], c["metric"], c["value"], c["main"], c["rel"] * 100))
        for s in r["reseller_spreads"][:2]:
            delta = (s["value"] / s["main"] - 1) * 100
            if abs(delta) < 2:
                detail.append("%s 渠道同价（%s=%s）" % (s["source"], s["metric"], s["value"]))
            else:
                detail.append("渠道价差 %s %s=%s（%+.0f%%）" %
                              (s["source"], s["metric"], s["value"], delta))
        if r["notes"]:
            detail.append(r["notes"][0])
        lines.append("| %s %s | %s %s | %s | %s | %s | %s |" %
                     (r["provider"], r["display"], fmt(r["output"]), r["currency"],
                      r["price_kind"], STATUS_CN[r["status"]],
                      ", ".join(r["agreeing_sources"]) or "—",
                      "；".join(detail) or "—"))
    lines += ["", "### 需要人工复核的冲突", ""]
    conf = [r for r in d["api"] if r["conflicts"]]
    if conf:
        for r in conf:
            for c in r["conflicts"]:
                lines.append("- **%s %s**：主表 %s %s，%s 记 %s（偏差 %.1f%%）。%s ｜ [来源](%s)" %
                             (r["provider"], r["display"], c["metric"], c["main"],
                              c["source"], c["value"], c["rel"] * 100,
                              c["note"], c["url"] or r["source_url"]))
        lines += ["", "> 冲突不等于「主表错」。常见原因：数据源版本滞后、官方 9/1 调价未被上游同步、"
                  "同一模型名跨版本复用、国际 USD 价与国内 CNY 价。处理顺序：回官方页 → 记录生效日 → "
                  "更新 price_version → 写 changelog。"]
    else:
        lines.append("本轮无数值冲突。")
    lines += ["", "## 三、套餐与本地部署", "",
              "| 类型 | 名称 | 状态 | 可折算 | 元/百万 token | 备注 |",
              "|---|---|---|---|---:|---|"]
    for a in d["aux"]:
        lines.append("| %s | %s | %s | %s | %s | %s |" %
                     (a["kind"], a["name"], STATUS_CN[a["status"]],
                      "是" if a["convertible"] else "否",
                      fmt(a["cny_per_1m"]) if a["cny_per_1m"] else "—", a["why"]))
    lines += ["", "## 四、别人追踪到的调价（外部变更日志）", ""]
    if d.get("external_changes"):
        lines += ["| 来源时间 | 模型 | 事件 |", "|---|---|---|"]
        for c in d["external_changes"][:12]:
            lines.append("| %s | %s | %s |" %
                         (esc(c.get("generated_at", ""))[:19],
                          esc(c.get("model_id", "")), esc(c.get("change_type", ""))))
        lines.append("")
        lines.append("> 来自 MrUnreal/LLMTracker 每 6 小时的 `changelog/latest.json`；"
                     "pricemon `/api/changes` 与公众号日报同理。本地 diff 见 `out/changelog.md`。")
    else:
        lines.append("本轮未取到外部变更日志（运行 `fetch --only llmtracker` 后重跑；"
                     "受限网络下该源可能超时，属正常降级）。")
    lines += ["", "## 五、来源覆盖", "",
              "| 来源 | 类型 | 权重 | 覆盖 | 价格观测 | 外部事件 |", "|---|---|---:|---|---:|---:|"]
    for sid, s in d["source_coverage"].items():
        lines.append("| %s | %s | %.2f | %s | %d | %d |" %
                     (s["name"], s["kind"], s["weight"], "/".join(s["covers"]),
                      s["n_obs"], s.get("n_events", 0)))
    lines += ["", "## 六、局限", "",
              "- 静态快照不能证明此刻价格或可用性；实时性依赖 `fetch` 与官方状态页订阅。",
              "- 第三方托管渠道（Bedrock / Azure / GMI / Databricks）与官方直连价不可混比，已单列为渠道价差。",
              "- 促销价、峰谷价、缓存价与标准价分列，禁止取最小值直接排序。",
              "- 套餐中 `percent` / `credits_formula` 两类无 token 明细，明确标为不可折算，不编造汇率。",
              "- 本地部署的 tok/s 来自个人实测样本，非受控基准；折旧/电费/利用率为假设值。",
              "- 部分在线源在受限网络下会 403 / 超时，见 `out/fetch_status.json`；失败不影响离线校验与出图。",
              ""]
    with open(os.path.join(OUT, "accuracy_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SVG 绘图（纯标准库，自包含）
# ---------------------------------------------------------------------------

FONT = "'WenQuanYi Micro Hei','PingFang SC','Microsoft YaHei',system-ui,sans-serif"


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def clip_text(s, size=12.5, max_px=210):
    """按估算宽度截断（中文≈1em，西文≈0.55em）。SVG 没有 text-overflow。"""
    out, w = "", 0.0
    for ch in str(s):
        cw = size * (1.0 if ord(ch) > 0x2E80 else 0.55)
        if w + cw > max_px:
            return out.rstrip() + "…"
        out += ch
        w += cw
    return out


def svg_doc(w, h, body, title="", attrs=""):
    """统一图表的字体 / 配色基线。背景透明，交给卡片的纸色衬底。"""
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="100%%" '
            'role="img" aria-label="%s" style="font-family:%s"%s>'
            '<style>text{font-family:%s;font-variant-numeric:tabular-nums}'
            '.t{font-size:12.5px;fill:%s}'
            '.s{font-size:11px;fill:%s}'
            '.b{font-size:13px;fill:%s;font-weight:600}'
            '.h{font-size:15px;fill:%s;font-weight:600}'
            '.v{font-size:12.5px;fill:%s;font-weight:600}'
            '</style>%s</svg>') % (w, h, esc(title), FONT, attrs,
                                   FONT, C_TXT, C_MUTE, C_INK, C_INK, C_INK, body)


def text(x, y, s, cls="t", anchor="start", extra=""):
    return '<text x="%.1f" y="%.1f" text-anchor="%s" class="%s" %s>%s</text>' % (
        x, y, anchor, cls, extra, esc(s))


def rect(x, y, w, h, fill, rx=2, extra=""):
    return '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" rx="%s" %s/>' % (
        x, y, max(0, w), max(0, h), fill, rx, extra)


def line(x1, y1, x2, y2, stroke="#e8edf2", width=1, dash=""):
    d = ' stroke-dasharray="%s"' % dash if dash else ""
    return '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%s"%s/>' % (
        x1, y1, x2, y2, stroke, width, d)


def step_points(pairs):
    """折线 → 阶梯线：价格是阶梯量，两次观测之间不变。

    直接连斜线会画出「这半个月里价格匀速下滑」这种不存在的现象，
    也会让「哪天变的」变成「大概那阵子变的」。竖线拐点就落在观测日当天。
    """
    out, prev = [], None
    for x, y in pairs:
        if prev is not None:
            out.append((x, prev))
        out.append((x, y))
        prev = y
    return out


def polyline(points, stroke, width=2, dash=""):
    # 原版这里 return 的字符串被拆成两行、% 又落在第二行上：结果每条折线都输出成
    # `<polyline points="%s" ...`，把后面的 <circle> 一起吞进坏标签 —— 所有折线图
    # 只剩圆点没有线。合成一行再格式化。
    d = ' stroke-dasharray="%s"' % dash if dash else ""
    p = " ".join("%.1f,%.1f" % (x, y) for x, y in points)
    return ('<polyline points="%s" fill="none" stroke="%s" stroke-width="%s" '
            'stroke-linejoin="round" stroke-linecap="round"%s/>'
            % (p, stroke, width, d))


def chart_api_prices(d):
    """图1：API 输出价（统一 CNY，对数横轴）。

    三条编码各管一件事，互不抢戏：条长 = 价格，条色 = 数据可信度，
    数值贴在条末。数值单独摆一列会离条形一百多像素，读到一半要横跳。
    """
    rows = sorted([r for r in d["api"] if r["output_cny"]], key=lambda r: r["output_cny"])
    rowh, top = 30, 32
    w = 960
    h = top + len(rows) * rowh + 44
    x0, xb = 254, 610          # 条形区
    xs = 700                   # 状态列（左对齐，跟着条形区右边界留一段呼吸）
    lo, hi = math.log10(0.3), math.log10(600)
    sx = lambda v: x0 + (math.log10(max(0.3, min(600, v))) - lo) / (hi - lo) * (xb - x0)
    b = [text(24, 16, "元 / 百万输出 token（对数轴）", "s")]
    for v in (1, 3, 10, 30, 100, 300):
        x = sx(v)
        b += [line(x, top - 10, x, top + len(rows) * rowh - 6, C_RULE),
              text(x, top - 16, "%g" % v, "s", "middle")]
    for i, r in enumerate(rows):
        y = top + i * rowh
        col = STATUS_COLOR[r["status"]]
        mark = (' <tspan fill="%s">※</tspan>' % C_ACC) if r["price_kind"] != "standard" else ""
        disp, prov = r["display"], r["provider"]
        # 「DeepSeek DeepSeek V4.1 Flash」这种重复前缀纯属占地方
        name = disp if disp.lower().startswith(prov.lower()) else prov + " " + disp
        if len(name) > 26:                     # 截断要留个省略号，不然像被截掉的错字
            name = name[:25] + "…"
        b.append('<text x="24" y="%.1f" class="t">%s%s</text>'
                 % (y + 19, esc(name), mark))
        end = max(x0 + 3, sx(r["output_cny"]))
        b.append(rect(x0, y + 7, end - x0, 15, col, 2, 'opacity="0.82"'))
        b.append(text(end + 7, y + 19, "%.2f" % r["output_cny"], "v", "start"))
        b.append(text(xs, y + 19, STATUS_CN[r["status"]], "s", "start",
                      'fill="%s"' % col))
    b.append(text(24, h - 12, "条长＝价格，条色＝数据可信度；※ 非标准价（峰谷 / 促销 / 含缓存）"
                  "不可与标准价直接取最小值排序；USD 按 %.1f 换算仅供可比" % d["fx_usd_cny"], "s"))
    return svg_doc(w, h, "".join(b), "API 输出价对比")


def chart_plan_vs_api(d):
    """图2：月用量 vs 成本，套餐固定费 + 超额，标出与 API 打平的临界点。"""
    plans = [p for p in d["plans"] if p["convertible"] and p["cny_per_1m"]]
    api_sorted = sorted([r["output_cny"] for r in d["api"] if r["output_cny"]])
    api_line = api_sorted[2] if len(api_sorted) > 2 else (api_sorted[0] if api_sorted else 4.0)
    cheap_api = api_sorted[0] if api_sorted else 1.44
    w, h = 960, 432
    x0, x1, y0, y1 = 68, 664, 376, 42
    lx = 690
    lo, hi = math.log10(1), math.log10(100000)   # 百万 token / 月
    YMAX = 900
    sx = lambda mt: x0 + (math.log10(max(1, min(100000, mt))) - lo) / (hi - lo) * (x1 - x0)
    sy = lambda c: y0 - min(YMAX, c) / YMAX * (y0 - y1)
    b = [text(24, 18, "元 / 月", "s"),
         text(x1, 18, "月用量（百万 token，对数轴）→", "s", "end")]
    for c in (0, 200, 400, 600, 800):
        y = sy(c)
        b += [line(x0, y, x1, y, C_RULE), text(x0 - 10, y + 4, "%d" % c, "s", "end")]
    for mt in (1, 10, 100, 1000, 10000, 100000):
        x = sx(mt)
        b += [line(x, y1, x, y0, C_RULE2), text(x, y0 + 18, "%g" % mt, "s", "middle")]
    # API 基准线
    b.append(polyline([(sx(1), sy(api_line * 1)), (sx(100000), sy(api_line * 100000))],
                      C_ACC, 2, "6 4"))
    b.append(polyline([(sx(1), sy(cheap_api * 1)), (sx(100000), sy(cheap_api * 100000))],
                      "#c9a99c", 1.4, "3 4"))
    crosses = []
    for i, p in enumerate(plans[:7]):
        col = SERIES[i % len(SERIES)]
        eff = p["cny_per_1m"]
        pts = []
        for mt in (1, 3, 10, 30, 100, 300, 1000, 3000, 10000, 30000, 100000):
            cost = p["monthly_cny"] + max(0, mt - (p["monthly_cny"] / eff if eff else 0)) * eff
            if cost >= YMAX:      # 超出纵轴就截断，别画成一条假的水平线
                break
            pts.append((sx(mt), sy(cost)))
        if len(pts) >= 2:
            b.append(polyline(pts, col, 1.9))
        if eff < api_line:
            inc = p["monthly_cny"] / max(1e-9, api_line - eff)
            crosses.append((p, inc))
            if 1 <= inc <= 100000:
                b.append(line(sx(inc), y1, sx(inc), y0, "#c0bab0", 1, "2 4"))
        ly = y1 + 6 + i * 42
        b.append(line(lx, ly, lx + 13, ly, col, 2.4))
        b.append(text(lx + 19, ly + 4, p["plan"][:19], "t"))
        b.append(text(lx + 19, ly + 18, "%s · 月费 ¥%s · %.3f 元/百万"
                      % (p["platform"][:10], fmt(p["monthly_cny"], 0), eff), "s"))
    ly = y1 + 6 + min(7, len(plans)) * 42 + 2
    b.append(line(lx, ly, lx + 13, ly, C_ACC, 2, "5 3"))
    b.append(text(lx + 19, ly + 4, "按量 API 基准", "t"))
    b.append(text(lx + 19, ly + 18, "%.2f 元/百万输出（另条浅色=最低价 API）" % api_line, "s"))
    b.append(text(24, h - 12, "实线=套餐（月费打底，超额按套餐等效单价计）；竖虚线=与 API 打平的临界用量；"
                  "限额 / 到期不在数学里", "s"))
    return svg_doc(w, h, "".join(b), "套餐与 API 成本临界点"), crosses


def chart_local(d):
    """图3：本地部署每百万 token 成本 vs 利用率，叠加 API 基准。

    8 条曲线，右侧独立图例（色块 + 名字 + 吞吐/利用率），曲线区不再被文字压住。
    """
    rigs = d["rigs"]
    api_sorted = sorted([r["output_cny"] for r in d["api"] if r["output_cny"]])
    api_line = api_sorted[2] if len(api_sorted) > 2 else 4.0
    w, h = 960, 442
    x0, x1, y0, y1 = 68, 590, 372, 42
    lx = 616
    YMAX = 60
    sx = lambda u: x0 + u * (x1 - x0)
    sy = lambda c: y0 - min(YMAX, c) / YMAX * (y0 - y1)
    b = [text(24, 18, "元 / 百万 token", "s"),
         text(x1, 18, "设备利用率 →", "s", "end")]
    for c in (0, 10, 20, 30, 40, 50, 60):
        y = sy(c)
        b += [line(x0, y, x1, y, C_RULE), text(x0 - 10, y + 4, "%d" % c, "s", "end")]
    for u in (0.1, 0.3, 0.5, 0.7, 0.9):
        x = sx(u)
        b += [line(x, y1, x, y0, C_RULE2), text(x, y0 + 18, "%d%%" % (u * 100), "s", "middle")]
    api_y = sy(min(YMAX, api_line))
    b += [line(x0, api_y, x1, api_y, C_ACC, 1.6, "6 4")]
    for i, r in enumerate(rigs[:8]):
        col = SERIES[i % len(SERIES)]
        pts = []
        for k in range(1, 41):
            u = k / 40.0
            c = local_cost(r, u)
            if c and c <= YMAX:
                pts.append((sx(u), sy(c)))
        if len(pts) >= 2:
            b.append(polyline(pts, col, 1.8))
        u0 = num(r.get("utilization"), 0.3) or 0.3
        c0 = local_cost(r, u0)
        if c0 and c0 <= YMAX:
            b.append('<circle cx="%.1f" cy="%.1f" r="3.2" fill="%s" stroke="#fff" stroke-width="1"/>'
                     % (sx(u0), sy(c0), col))
        ly = y1 + 4 + i * 38
        b.append(line(lx, ly, lx + 13, ly, col, 2.6))
        b.append(text(lx + 19, ly + 4, r["rig"][:19], "t"))
        b.append(text(lx + 19, ly + 17, "%s · %.0f tok/s · 利用率 %.0f%%"
                      % (r.get("model") or "", num(r.get("tok_s"), 0) or 0, u0 * 100), "s"))
    ly = y1 + 4 + min(8, len(rigs)) * 38 + 4
    b.append(line(lx, ly, lx + 13, ly, C_ACC, 2, "4 3"))
    b.append(text(lx + 19, ly + 4, "低价 API 基准", "t"))
    b.append(text(lx + 19, ly + 17, "%.2f 元/百万输出" % api_line, "s"))
    b.append(text(24, h - 12, "圆点=表中假设利用率；曲线=3~4 年折旧 + 电费摊到实际吞吐；纵轴上限 60；"
                  "运维 / 网络 / 机房 / 资本占用未计入", "s"))
    return svg_doc(w, h, "".join(b), "本地部署成本与利用率")


def chart_accuracy(d):
    """图4：来源覆盖 + 状态分布 + 冲突清单。"""
    cov = sorted(d["source_coverage"].items(),
                 key=lambda kv: -(kv[1]["n_obs"] + kv[1].get("n_events", 0)))
    x0, x1, top, rowh = 236, 552, 44, 24
    h = max(360, top + len(cov) * rowh + 46)
    w = 960
    b = []
    total_of = lambda v: v["n_obs"] + v.get("n_events", 0)
    maxn = max(1, max(total_of(v) for _, v in cov))
    b.append(text(24, 18, "来源 / 本轮观测与外部事件数（√ 缩放）", "s"))
    for i, (sid, s) in enumerate(cov):
        y = top + i * rowh
        b.append(text(24, y + 13, clip_text(s["name"], 12.5, 204), "t"))
        n = total_of(s)
        frac = math.sqrt(n / maxn) if n else 0
        b.append(rect(x0, y + 3, max(1, frac * (x1 - x0)), 13, C_BAR, 2, 'opacity="0.7"'))
        b.append(text(x1 + 10, y + 13, "%d" % n, "s"))
        b.append(text(x1 + 58, y + 13, "w=%.2f" % s["weight"], "s", "start", 'fill="%s"' % C_MUTE))
    # 右栏：堆叠条 + 图例
    rx, rw = 664, 258
    tot = max(1, sum(d["counts"].values()))
    b.append(text(rx, 18, "主表状态 · %d 条" % tot, "s"))
    xx = rx
    for s in STATUS_ORDER:
        n = d["counts"][s]
        wseg = rw * n / tot
        if n:
            b.append(rect(xx, 28, max(2, wseg - 1), 10, STATUS_COLOR[s], 1))
        xx += wseg
    yy = 66
    for s in STATUS_ORDER:
        n = d["counts"][s]
        b.append('<circle cx="%.1f" cy="%.1f" r="3" fill="%s"/>' % (rx + 3, yy - 4, STATUS_COLOR[s]))
        b.append(text(rx + 14, yy, STATUS_CN[s], "s"))
        b.append(text(rx + rw, yy, "%d" % n, "s", "end", 'fill="%s"' % C_TXT))
        yy += 21
    yy += 14
    b.append(text(rx, yy, "待人工复核", "b"))
    yy += 22
    conf = [r for r in d["api"] if r["conflicts"]]
    for r in conf[:4]:
        b.append(text(rx, yy, "· %s" % r["display"][:22], "s", "start", 'fill="%s"' % C_ACC))
        b.append(text(rx, yy + 13, "%s · %d 处偏差" % (r["provider"], len(r["conflicts"])),
                      "s", "start", 'fill="%s"' % C_MUTE))
        yy += 30
    if not conf:
        b.append(text(rx, yy, "本轮无冲突", "s"))
    b.append(text(24, h - 12,
                  "规则：口径不一致不参与数值比对；≥2 独立来源一致=多源一致；偏差 >%.0f%%=冲突；"
                  ">%d 天未复核=过期" % (d["policy"]["conflict_tolerance"] * 100,
                                        d["policy"]["stale_days"]), "s"))
    return svg_doc(960, h, "".join(b), "数据准确性来源覆盖")


def chart_summary(d):
    """图5：三条路径的单位成本对照（最低 / 中位 / 最高）。哑铃图。"""
    api = sorted([r["output_cny"] for r in d["api"] if r["output_cny"]])
    plans = sorted([p["cny_per_1m"] for p in d["plans"] if p["convertible"] and p["cny_per_1m"]])
    local = []
    for r in d["rigs"]:
        c = local_cost(r, num(r.get("utilization"), 0.3) or 0.3)
        if c:
            local.append(c)
    local.sort()
    groups = [
        ("API 按量", api[0] if api else 0, api[len(api) // 2] if api else 0, api[-1] if api else 0),
        ("订阅套餐", plans[0] if plans else 0, plans[len(plans) // 2] if plans else 0,
         plans[-1] if plans else 0),
        ("本地部署", local[0] if local else 0, local[len(local) // 2] if local else 0,
         min(60, local[-1]) if local else 0),
    ]
    w, h = 960, 292
    x0, x1, top = 150, 856, 64
    lo, hi = math.log10(0.001), math.log10(600)
    sx = lambda v: x0 + (math.log10(max(0.001, min(600, v))) - lo) / (hi - lo) * (x1 - x0)
    b = [text(24, 20, "元 / 百万 token（对数轴）", "s")]
    for v in (0.01, 0.1, 1, 10, 100):
        x = sx(v)
        b += [line(x, top - 20, x, top + 2 * 72 + 12, C_RULE),
              text(x, top - 26, "%g" % v, "s", "middle")]
    colors = [C_ACC, SERIES[0], "#3f6b53"]
    for i, (name, lo_v, mid_v, hi_v) in enumerate(groups):
        y = top + i * 72 + 22
        b.append(text(24, y + 4, name, "b"))
        if hi_v > 0:
            b.append(line(sx(lo_v), y, sx(hi_v), y, colors[i], 2.4, ""))
            # 两端标在线上方、中位标在线下方：三个标签永远不会撞
            for v, lab, dy in ((lo_v, "最低", -11), (mid_v, "中位", 20), (hi_v, "最高", -11)):
                cx = sx(v)
                b.append('<circle cx="%.1f" cy="%.1f" r="4.2" fill="%s"/>' % (cx, y, colors[i]))
                txt = ("%.2f" % v).rstrip("0").rstrip(".") if v >= 0.01 else "<0.01"
                b.append(text(cx, y + dy, "%s %s" % (lab, txt), "s", "middle"))
        else:
            b.append(text(x0, y + 4, "无可折算数据", "s"))
    b.append(text(24, h - 14, "套餐按三档系数 / 固定额度折算；本地按 3~4 年折旧 + 电费 + 表中利用率；"
                  "三者质量与延迟不等价，仅比单位成本", "s"))
    return svg_doc(w, h, "".join(b), "三路径单位成本对照")


def write_svg(name, content):
    p = os.path.join(OUT, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    return p


# ---------------------------------------------------------------------------
# 时间轴：按日期的折线（真实观测点 + 已知调价事件 + 主表快照版本）
# ---------------------------------------------------------------------------

def build_timeline(obs, d):
    import glob
    daily = {}
    for o in obs:
        day = (o.get("captured_at") or "")[:10]
        if day:
            daily[day] = daily.get(day, 0) + 1

    # 每个 USD 模型在各观测日期的 output 价中位数（真实的「别人那天记了多少」）
    per = {}
    for o in obs:
        if o["metric"] != "output" or o["currency"] != "USD" or o["scope"] != "first_party":
            continue
        day = (o.get("captured_at") or "")[:10]
        if not day:
            continue
        per.setdefault(norm_key(o["model"]), {}).setdefault(day, []).append(o["value"])
    # 只画主表本身以 USD 计价的模型：避免把「主表 CNY + 开源 USD 国际价」
    # 混成一条看似同口径的线（例如 GLM-5.3-Flash 国内外双价）。
    main_keys = {norm_key(r["model"]): "%s %s" % (r["provider"], r["display"])
                 for r in d["api"] if r["currency"] == "USD"}
    chosen = []
    for k, days in per.items():
        if k not in main_keys or len(days) < 2:
            continue
        s = {day: sorted(v)[len(v) // 2] for day, v in days.items() if v}
        chosen.append((main_keys[k], s))
    chosen.sort(key=lambda x: -len(x[1]))
    chosen = chosen[:5]

    events = [dict(r) for r in read_csv(os.path.join(DATA, "price_events.csv"))]
    versions = []
    for p in sorted(glob.glob(os.path.join(SNAP, "api_prices_*.csv"))):
        versions.append({"date": os.path.basename(p).replace("api_prices_", "").replace(".csv", ""),
                         "n": len(read_csv(p)), "file": os.path.basename(p)})

    # Liutasil 数据集按 first_seen 月的累计收录模型数（真实字段）
    cumulative = []
    files = sorted(glob.glob(os.path.join(SNAP, "liutasil_*.csv")))
    if files:
        months = {}
        for r in read_csv(files[-1]):
            m = (r.get("first_seen") or "")[:7]
            if re.match(r"^\d{4}-\d{2}$", m):
                months[m] = months.get(m, 0) + 1
        acc = 0
        for m in sorted(months):
            acc += months[m]
            cumulative.append({"month": m, "n": acc, "new": months[m]})

    dates = sorted(set(daily) | {e["date"] for e in events} |
                   {v["date"] for v in versions})
    return {"daily": daily, "series": chosen, "events": events,
            "versions": versions, "cumulative": cumulative, "dates": dates,
            "external_events": d.get("external_changes", [])}


def chart_price_timeline(d, tl):
    """图6 · 代表性模型 output 价按观测日期的折线（等距日期轴）+ 调价事件竖线。"""
    dates = tl["dates"]
    series = tl["series"]
    w, h = 960, 410
    x0, x1, y0, y1 = 68, 654, 336, 44
    lx = 678
    lo, hi = math.log10(0.1), math.log10(60)
    sx = lambda i: x0 + i * (x1 - x0) / max(1, len(dates) - 1)
    sy = lambda v: y0 - (math.log10(max(0.1, min(60, v))) - lo) / (hi - lo) * (y0 - y1)
    b = [text(24, 18, "USD / 百万输出 token（对数轴）", "s")]
    for v in (0.2, 0.5, 1, 2, 5, 10, 20, 50):
        y = sy(v)
        b += [line(x0, y, x1, y, C_RULE), text(x0 - 10, y + 4, "%g" % v, "s", "end")]
    step = max(1, int(math.ceil(len(dates) / 12.0)))
    for i, day in enumerate(dates):
        x = sx(i)
        b.append(line(x, y1, x, y0, C_RULE2))
        if i % step == 0:
            b.append(text(x, y0 + 18, day[5:], "s", "middle"))
    # 调价 / 到期：只画竖虚线，细则看下面的表
    seen = set()
    for e in tl["events"]:
        if e["type"] in ("调价", "活动到期", "渠道调价", "限免到期") and e["date"] in dates:
            if e["date"] in seen:
                continue
            seen.add(e["date"])
            x = sx(dates.index(e["date"]))
            b.append(line(x, y1, x, y0, "#b98a3e", 1, "3 3"))
    for j, (name, s) in enumerate(series):
        col = SERIES[j % len(SERIES)]
        pts = [(sx(dates.index(day)), sy(v)) for day, v in sorted(s.items()) if day in dates]
        if len(pts) >= 2:
            b.append(polyline(pts, col, 1.9))
        for x, y in pts:
            b.append('<circle cx="%.1f" cy="%.1f" r="3" fill="%s" stroke="#fffdf9" '
                     'stroke-width="1"/>' % (x, y, col))
        ly = y1 + 8 + j * 44
        b.append(line(lx, ly, lx + 13, ly, col, 2.4))
        b.append(text(lx + 19, ly + 4, clip_text(name, 12.5, 196), "t"))
        b.append(text(lx + 19, ly + 18, "%d 个观测日" % len(pts), "s"))
    ly = y1 + 8 + min(5, len(series)) * 44 + 6
    b.append(line(lx, ly, lx + 13, ly, "#b98a3e", 1, "3 3"))
    b.append(text(lx + 19, ly + 4, "调价 / 到期", "t"))
    b.append(text(24, h - 12, "口径：仅主表以 USD 计价的模型；CNY 国内模型、促销 / 峰谷价、第三方渠道价不入此图，"
                  "见事件表与图 1", "s"))
    return svg_doc(w, h, "".join(b), "模型价格按日期变化")


def chart_activity_timeline(d, tl):
    """图7 · 上：每日观测条数（对数）；下：开源数据集累计收录模型数。两个 panel 各自独立横轴。"""
    daily = tl["daily"]
    dates = sorted(daily)
    cum = tl["cumulative"]
    w, h = 960, 456
    x0, x1 = 72, 900
    b = []
    # ---- 上 panel
    uy0, uy1 = 200, 68
    lo, hi = math.log10(1), math.log10(max(10, max(daily.values()) if daily else 10) * 1.4)
    sx = lambda i: x0 + i * (x1 - x0) / max(1, len(dates) - 1)
    sy = lambda v: uy0 - (math.log10(max(1, v)) - lo) / (hi - lo) * (uy0 - uy1)
    b.append(text(24, 44, "每日交叉校验观测条数（对数）", "s"))
    for v in (1, 10, 100, 1000, 10000):
        if v > 10 ** hi:
            break
        y = sy(v)
        b += [line(x0, y, x1, y, C_RULE), text(x0 - 10, y + 4, "%g" % v, "s", "end")]
    pts = [(sx(dates.index(day)), sy(n)) for day, n in sorted(daily.items()) if day in dates]
    if len(pts) >= 2:
        b.append(polyline(pts, SERIES[0], 2))
    for (day, n) in sorted(daily.items()):
        if day not in dates:
            continue
        x, y = sx(dates.index(day)), sy(n)
        b.append('<circle cx="%.1f" cy="%.1f" r="3.6" fill="%s"/>' % (x, y, SERIES[0]))
        b.append(text(x, y - 11, format(int(n), ","), "s", "middle", 'fill="%s"' % SERIES[0]))
    step = max(1, int(math.ceil(len(dates) / 14.0)))
    for i, day in enumerate(dates):
        if i % step == 0:
            b.append(text(sx(i), uy0 + 18, day[5:], "s", "middle"))
    # ---- 分隔
    b.append(line(24, 236, x1, 236, C_RULE))
    # ---- 下 panel：纵轴从数据下沿起算，否则增长被压成一条水平线
    b.append(text(24, 268, "累计收录模型数（按 first_seen 月）", "s"))
    if cum:
        vals = [c["n"] for c in cum]
        vmin, vmax = min(vals) * 0.94, max(vals) * 1.02
        dy0, dy1 = 402, 286
        sx2 = lambda i: x0 + i * (x1 - x0) / max(1, len(cum) - 1)
        sy2 = lambda v: dy0 - (v - vmin) / max(1e-9, vmax - vmin) * (dy0 - dy1)
        b.append(polyline([(sx2(i), sy2(c["n"])) for i, c in enumerate(cum)], "#3f6b53", 2))
        for i, c in enumerate(cum):
            x, y = sx2(i), sy2(c["n"])
            b += ['<circle cx="%.1f" cy="%.1f" r="3.6" fill="#3f6b53"/>' % (x, y),
                  text(x, y - 11, "%s → %s" % (format(int(c["new"]), ","), format(int(c["n"]), ",")),
                       "s", "middle", 'fill="#3f6b53"'),
                  text(x, dy0 + 18, c["month"], "s", "middle")]
    else:
        b.append(text(x0, 340, "本轮没有可用的收录数据", "s"))
    b.append(text(24, h - 14, "上=有观测的日期（等距）、下=数据集收录月份，两者不共用横轴；"
                  "观测来自本地快照，非实时爬虫流量", "s"))
    return svg_doc(w, h, "".join(b), "追踪活跃度时间轴")


# ---------------------------------------------------------------------------
# 价格史：把「一个当下价」变成「一条时间上的价格点」
#   data/price_history.csv 每行 = 某模型在某一天的价格点，basis 说明这个点是怎么来的：
#     official 官方页当期记录 / event 由已登记调价事件回溯 / carry 窗口内无变化按现值回溯
#     / snapshot 每日快照自动落点。回溯点必须显式标出来，否则历史图会显得比事实更硬。
# ---------------------------------------------------------------------------

HISTORY_FILE = os.path.join(DATA, "price_history.csv")
BASIS_CN = {"official": "官方现价", "event": "按事件回溯", "carry": "现值回溯",
            "snapshot": "自动快照"}
BASIS_COLOR = {"official": "#3f6b53", "event": "#a33a26", "carry": "#9aa1a6",
               "snapshot": "#33536e"}


def load_price_history():
    rows = []
    for r in read_csv(HISTORY_FILE):
        day = (r.get("date") or "").strip()[:10]
        out = num(r.get("output"))
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", day) or out is None:
            continue
        rows.append({
            "date": day, "provider": r.get("provider", ""), "model": r.get("model", ""),
            "currency": (r.get("currency") or "CNY").strip(),
            "input": num(r.get("input")), "output": out,
            "cache_hit": num(r.get("cache_hit")),
            "price_kind": (r.get("price_kind") or "standard").strip(),
            "basis": (r.get("basis") or "carry").strip(),
            "source_id": r.get("source_id", ""), "source_url": r.get("source_url", ""),
            "note": r.get("note", ""),
        })
    return rows


def _quantile(vals, q):
    if not vals:
        return None
    s = sorted(vals)
    if len(s) == 1:
        return s[0]
    pos = (len(s) - 1) * q
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def build_price_history(d):
    """月度价格点 → 每模型的序列 + 变动点 + 全盘中位水位。"""
    rows = load_price_history()
    fx = num(d.get("fx_usd_cny"), 7.2) or 7.2
    display = {norm_key(r["model"]): r["display"] for r in d.get("api", [])}
    if not rows:
        return {"dates": [], "models": [], "changes": [], "levels": [],
                "summary": {"n_models": 0, "n_dates": 0, "n_changed": 0, "n_points": 0},
                "fx": fx}

    to_cny = lambda r: (r["output"] or 0) * (fx if r["currency"] == "USD" else 1.0)
    dates = sorted({r["date"] for r in rows})
    per = {}
    for r in rows:
        per.setdefault(r["model"], []).append(r)

    models = []
    for model, rs in per.items():
        rs.sort(key=lambda x: x["date"])
        series = [(r["date"], round(to_cny(r), 3)) for r in rs]
        first, last = series[0][1], series[-1][1]
        chg = (last - first) / first if first else 0.0
        models.append({
            "model": model,
            "display": display.get(norm_key(model), model),
            "provider": rs[-1]["provider"],
            "currency": rs[-1]["currency"],
            "price_kind": rs[-1]["price_kind"],
            "series": series,
            "input": [r["input"] for r in rs],
            "output": [r["output"] for r in rs],
            "first_cny": first, "last_cny": last, "chg": chg,
            "basis": rs[-1]["basis"], "note": rs[-1]["note"],
            "n_points": len(series),
        })
    models.sort(key=lambda m: (m["chg"], -m["last_cny"]))

    # 相邻价格点之间有变化 → 一条变动记录（这才是「追踪」的产出）
    changes = []
    for m in models:
        rs = sorted([r for r in rows if r["model"] == m["model"]], key=lambda x: x["date"])
        for a, b in zip(rs, rs[1:]):
            if abs((a["output"] or 0) - (b["output"] or 0)) < 1e-9:
                continue
            pct = (b["output"] - a["output"]) / a["output"] if a["output"] else 0
            changes.append({"date": b["date"], "model": m["model"], "display": m["display"],
                            "field": "output", "from": a["output"], "to": b["output"],
                            "currency": b["currency"], "pct": pct,
                            "basis": b["basis"], "note": b["note"]})
    changes.sort(key=lambda c: c["date"])

    # 全盘价格水位：每个日期所有模型输出价（折 CNY）的几何均值 + 四分位
    # 用几何均值而不是中位数：15 个离散价位的中位数会退化成「某个模型的现价」，
    # 一个模型调价就整条线不动，看不出水位变化。
    levels = []
    for day in dates:
        vals = [to_cny(r) for r in rows if r["date"] == day and to_cny(r) > 0]
        if not vals:
            continue
        gmean = math.exp(sum(math.log(v) for v in vals) / len(vals))
        levels.append({"date": day, "n": len(vals),
                       "p25": round(_quantile(vals, 0.25), 3),
                       "p50": round(_quantile(vals, 0.5), 3),
                       "p75": round(_quantile(vals, 0.75), 3),
                       "gmean": round(gmean, 3)})

    moved = [m for m in models if abs(m["chg"]) > 1e-9]
    lvl_chg = ((levels[-1]["gmean"] - levels[0]["gmean"]) / levels[0]["gmean"]
               if len(levels) > 1 and levels[0]["gmean"] else 0)
    return {
        "dates": dates, "models": models, "changes": changes, "levels": levels, "fx": fx,
        "summary": {
            "n_models": len(models), "n_dates": len(dates), "n_points": len(rows),
            "n_changed": len(moved), "n_up": sum(1 for m in moved if m["chg"] > 0),
            "n_down": sum(1 for m in moved if m["chg"] < 0),
            "span_from": dates[0], "span_to": dates[-1],
            "level_from": levels[0]["gmean"] if levels else None,
            "level_to": levels[-1]["gmean"] if levels else None,
            "level_chg": lvl_chg,
            "basis_count": {b: sum(1 for r in rows if r["basis"] == b) for b in BASIS_CN},
        },
    }


def chart_api_history(hist, d):
    """图9 · 上：全盘月价格水位 + 四分位带；下：期间真有变动的模型（输入/输出两条线）。"""
    w, h = 960, 486
    dates = hist["dates"]
    levels = hist["levels"]
    moved = [m for m in hist["models"] if abs(m["chg"]) > 1e-9][:2]
    b = [text(24, 18, "输出价折人民币 / 每百万 token（对数轴）", "s")]
    if not dates or not levels:
        b.append(text(24, 60, "还没有价格史数据：填充 data/price_history.csv 后重算", "s"))
        return svg_doc(w, h, "".join(b), "API 价格史")

    x0, x1, y0, y1 = 82, 912, 214, 52
    lo, hi = math.log10(1.5), math.log10(90)
    # 横轴按「天」定位，不按点的序号：四次观测之间其实隔着 31 / 30 / 31 天，
    # 用序号排版会把「十月那次调价」画到正中间，读起来像每月一号都变价。
    d0, d1 = parse_date(dates[0]), parse_date(dates[-1])
    span = max(1, (d1 - d0).days)
    sx = lambda day: x0 + (parse_date(day) - d0).days / span * (x1 - x0)
    sy = lambda v: y0 - (math.log10(max(1.5, min(90, v))) - lo) / (hi - lo) * (y0 - y1)
    for v in (2, 3, 5, 10, 20, 50):
        y = sy(v)
        b += [line(x0, y, x1, y, C_RULE), text(x0 - 10, y + 4, "%g" % v, "s", "end")]

    # 逐日刻度和「价格走势」那张图用同一套：月初粗线、每周一细线，观测日必标
    for day, x, major, labeled in day_axis(d0, d1, x0, x1, must=[l["date"] for l in levels]):
        b.append(line(x, y1, x, y0, C_RULE if major else C_RULE2))
        if labeled:
            b.append(text(x, y0 + 18, day.strftime("%m-%d"), "s", "middle",
                          "" if major else 'fill="%s"' % C_MUTE))

    # 四分位带：整体价格分布有没有整体上移/下移。同样走阶梯，别画成缓坡
    pts_hi = step_points([(sx(l["date"]), sy(l["p75"])) for l in levels])
    pts_lo = step_points([(sx(l["date"]), sy(l["p25"])) for l in levels])
    poly = " ".join("%.1f,%.1f" % p for p in pts_hi + list(reversed(pts_lo)))
    b.append('<polygon points="%s" fill="#33536e" fill-opacity="0.09" stroke="none"/>' % poly)
    # P75 / P25 只在首末两点标，中间重复四个同样数字只会挤占轴标
    last = len(levels) - 1
    for i in (0, last):
        l = levels[i]
        anchor = "start" if i == 0 else ("end" if i == last else "middle")
        dx = 4 if i == 0 else (-4 if i == last else 0)
        b.append(text(sx(l["date"]) + dx, sy(l["p75"]) - 7, "P75 %g" % l["p75"], "s", anchor,
                      'fill="%s"' % C_MUTE))
        b.append(text(sx(l["date"]) + dx, sy(l["p25"]) + 14, "P25 %g" % l["p25"], "s", anchor,
                      'fill="%s"' % C_MUTE))
    b.append(polyline(step_points([(sx(l["date"]), sy(l["gmean"])) for l in levels]),
                      C_ACC, 2.4))
    for i, l in enumerate(levels):
        x, y = sx(l["date"]), sy(l["gmean"])
        anchor = "start" if i == 0 else ("end" if i == last else "middle")
        dx = 8 if i == 0 else (-8 if i == last else 0)
        b += ['<circle cx="%.1f" cy="%.1f" r="4" fill="%s" stroke="#fffdf9" stroke-width="1.5">'
              '<title>%s · 几何均值 %.2f 元（%d 个模型）</title></circle>'
              % (x, y, C_ACC, l["date"], l["gmean"], l["n"]),
              text(x + dx, y - 12, "均值 %.1f 元" % l["gmean"], "t", anchor,
                   'fill="%s"' % C_ACC)]
    b.append(text(x0, 40, "全盘价格水位：%d 个模型输出价的几何均值与四分位" % levels[0]["n"], "s"))
    s = hist["summary"]
    b.append(text(x1, 40, "期间水位 %+.1f%%　有变动的模型 %d / %d"
                  % (s["level_chg"] * 100, s["n_changed"], s["n_models"]), "s", "end"))

    # ---- 下半：真有变动的模型，画输出价一条线（输入价口径另见「API 价格」页）
    b.append(line(24, 244, 936, 244, C_RULE))
    if not moved:
        b.append(text(24, 290, "这段时间里 %d 个模型的官方价一个都没动。" % s["n_models"], "t"))
    for j, m in enumerate(moved):
        px0 = 66 + j * 462
        px1 = px0 + 384
        p_y0, p_y1 = 400, 286
        outs = [v for _, v in m["series"]]
        lo2, hi2 = min(outs) * 0.7, max(outs) * 1.3
        sy2 = lambda v: p_y0 - (v - lo2) / max(1e-9, hi2 - lo2) * (p_y0 - p_y1)
        b.append(text(px0, 268, "%s · %s" % (m["provider"], m["display"]), "t"))
        sign = "涨" if m["chg"] > 0 else "跌"
        col = C_ACC if m["chg"] > 0 else "#3f6b53"
        b.append(text(px1, 268, "%s %.0f%%" % (sign, abs(m["chg"]) * 100), "t", "end",
                      'fill="%s"' % col))
        b.append(line(px0, p_y0, px1, p_y0, C_RULE))
        # 子图也用真实日期间距：两次观测隔了 31 天还是 2 天，长度不一样
        sdays = [parse_date(day) for day, _ in m["series"]]
        sspan = max(1, (sdays[-1] - sdays[0]).days)
        px = lambda day: px0 + (parse_date(day) - sdays[0]).days / sspan * (px1 - px0)
        raw = [(px(day), sy2(v)) for day, v in m["series"]]
        b.append(polyline(step_points(raw), col, 2.2))
        last_lbl = None
        for i, (((day, v), (x, y))) in enumerate(zip(m["series"], raw)):
            b.append('<circle cx="%.1f" cy="%.1f" r="3.4" fill="%s">'
                     '<title>%s · %s %g 元</title></circle>'
                     % (x, y, col, day, m["display"], v))
            if i in (0, len(m["series"]) - 1):
                b.append(text(x, y - 9, "%g" % v, "t", "middle", 'fill="%s"' % col))
            # 日期标签隔太近就跳过一个：一天之内连调两次的情形，两个标签会叠
            if last_lbl is None or x - last_lbl >= 34:
                b.append(text(x, p_y0 + 16, day[5:], "s", "middle"))
                last_lbl = x
        b.append(text(px0, p_y0 + 34, m["note"][:52], "s"))

    # 脚注拆两行：之前一整句排下来超出 960 的 viewBox，右半句直接被裁掉
    b.append(text(24, h - 28, "横轴逐日（月初粗线、每周一细线），阶梯线在观测日拐弯 —— 变价落在哪天就是哪天。"
                  "灰底带 P25–P75，朱砂线几何均值；下半只画期间真变动过的模型", "s"))
    b.append(text(24, h - 12, "回溯点已在数据里标 basis，未标 official 的不是当日实录；"
                  "圆点指上去能读出确切日期与价格", "s"))
    return svg_doc(w, h, "".join(b), "API 价格三个月走势")


# ---------------------------------------------------------------------------
# 平台全景：同一个模型在不同平台的价格，画在同一根时间轴上
#   platforms.csv + price_points.csv 由 llmcost_platforms.py 生成
#   三条信息决定它能不能读：颜色=模型、线型=平台类型、虚线=第三方报价
# ---------------------------------------------------------------------------

PLATFORM_FILE = os.path.join(DATA, "platforms.csv")
POINT_FILE = os.path.join(DATA, "price_points.csv")

# 15 个模型固定配色。顺序按 model 名排序取色，价格变动不会让颜色漂移
MODEL_COLORS = [
    "#a33a26", "#33536e", "#3f6b53", "#8a6a4e", "#5c5470",
    "#7a6a2f", "#2f6b73", "#8c4a5f", "#4a6b3a", "#6b5a8a",
    "#a06a2f", "#3a5a8a", "#7b4a3a", "#4f6b6b", "#8a5a7a",
]
# 官方实线在最上层；云厂商点线、第三方短虚线在下层，避免盖住主参考线
KIND_STYLE = {"official": ("", 2.3, 1.0), "cloud": ("1 3", 1.3, 0.55),
              "aggregator": ("4 3", 1.3, 0.5)}
KIND_CN = {"official": "厂商自营", "cloud": "云厂商托管", "aggregator": "第三方托管"}


def load_price_points():
    rows = []
    for r in read_csv(POINT_FILE):
        day = (r.get("date") or "").strip()[:10]
        out = num(r.get("output"))
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", day) or out is None or out <= 0:
            continue
        rows.append({
            "date": day, "platform_id": (r.get("platform_id") or "").strip(),
            "model": (r.get("model") or "").strip(), "tier": (r.get("tier") or "standard").strip(),
            "currency": (r.get("currency") or "CNY").strip(),
            "input": num(r.get("input")), "output": out,
            "basis": (r.get("basis") or "").strip(), "note": r.get("note", ""),
        })
    return [r for r in rows if r["platform_id"] and r["model"]]


def build_price_panorama(d):
    """价格库 → 每条线一个 (模型, 平台, 口径) 序列 + 平台差价汇总。"""
    pts = load_price_points()
    plats = {r["platform_id"]: r for r in read_csv(PLATFORM_FILE)}
    api = {r["model"]: r for r in d.get("api", [])}
    fx = num(d.get("fx_usd_cny"), 7.2) or 7.2
    empty = {"lines": [], "models": [], "platforms": [], "dates": [],
             "summary": {"n_lines": 0, "n_models": 0, "n_platforms": 0, "n_points": 0,
                         "spread_median": None, "spread_max": None, "fx": fx}}
    if not pts:
        return empty

    def to_cny(r):
        return (r["output"] or 0) * fx if r["currency"] == "USD" else (r["output"] or 0)

    groups = {}
    for p in pts:
        groups.setdefault((p["model"], p["platform_id"], p["tier"]), []).append(p)

    lines = []
    for (model, pid, tier), rs in groups.items():
        rs.sort(key=lambda x: x["date"])
        series = {}
        for r in rs:                      # 同日重复只留最后一条（去重已在建库时做过，双保险）
            series[r["date"]] = round(to_cny(r), 3)
        series = sorted(series.items())
        if not series:
            continue
        meta = plats.get(pid) or {}
        disp = (api.get(model) or {}).get("display") or model
        lines.append({
            "model": model, "display": disp, "platform": pid,
            "platform_name": meta.get("name") or pid,
            "kind": meta.get("kind") or "aggregator",
            "tier": tier, "currency": rs[-1]["currency"],
            "series": [list(x) for x in series],
            "last": series[-1][1], "basis": rs[-1]["basis"],
        })

    # 模型汇总：官方价、最便宜/最贵平台、价差
    models = []
    for model in sorted({l["model"] for l in lines}):
        ls = [l for l in lines if l["model"] == model]
        offs = [l for l in ls if l["kind"] == "official"]
        # 有标准价就用标准价做基准；只有低谷价（DeepSeek）时才退回低谷
        off = next((l for l in offs if l["tier"] == "standard"), offs[0] if offs else None)
        off_low = next((l for l in offs if l["tier"] == "offpeak"), None)
        # 价差只在第三方平台之间比：把官方低谷价混进来会把「口径差」算成「渠道差」
        pool = [l for l in ls if l["kind"] != "official"] or ls
        lo = min(pool, key=lambda l: l["last"])
        hi = max(pool, key=lambda l: l["last"])
        n_third = len({l["platform"] for l in pool})
        models.append({
            "model": model, "display": ls[0]["display"],
            "n_platforms": len({l["platform"] for l in ls}),
            "official": off["last"] if off else None,
            "official_name": off["platform_name"] if off else "",
            "official_tier": off["tier"] if off else "",
            "official_low": off_low["last"] if off_low else None,
            "min": lo["last"], "min_name": lo["platform_name"], "min_platform": lo["platform"],
            "min_kind": lo["kind"],
            "max": hi["last"], "max_name": hi["platform_name"], "max_platform": hi["platform"],
            "max_kind": hi["kind"],
            "spread": (hi["last"] / lo["last"]) if (lo["last"] and n_third >= 2) else None,
            "n_third": n_third,
            "currency": ls[0]["currency"],
        })

    # 平台汇总：覆盖几个模型、相对官方价的溢价中位数
    plats_out = []
    for pid in sorted({l["platform"] for l in lines}):
        ls = [l for l in lines if l["platform"] == pid]
        meta = plats.get(pid) or {}
        ratios = []
        for l in ls:
            off = next((x for x in lines if x["model"] == l["model"]
                        and x["kind"] == "official" and x["tier"] == l["tier"]), None)
            if off and off["last"]:
                ratios.append(l["last"] / off["last"])
        plats_out.append({
            "id": pid, "name": meta.get("name") or pid, "kind": meta.get("kind") or "aggregator",
            "n_models": len({l["model"] for l in ls}),
            "n_points": sum(len(l["series"]) for l in ls),
            "ratio_median": round(_quantile(ratios, 0.5), 3) if ratios else None,
            "ratio_min": round(min(ratios), 3) if ratios else None,
            "ratio_max": round(max(ratios), 3) if ratios else None,
        })

    spreads = [m["spread"] for m in models if m.get("spread")]
    dates = sorted({r["date"] for r in pts})
    return {
        "lines": lines, "models": models, "platforms": plats_out, "dates": dates, "fx": fx,
        "summary": {
            "n_lines": len(lines), "n_models": len(models), "n_platforms": len(plats_out),
            "n_points": len(pts), "span_from": dates[0], "span_to": dates[-1],
            "spread_median": round(_quantile(spreads, 0.5), 2) if spreads else None,
            "spread_max": round(max(spreads), 2) if spreads else None,
            "fx": fx,
            "by_kind": {k: sum(1 for l in lines if l["kind"] == k) for k in KIND_CN},
        },
    }


def chart_price_panorama(pano, d):
    """图10：一条时间轴上的全部报价。颜色=模型，线型=平台类型，透明度=主次。

    91 条线不做筛选一定糊。这里的分工是：官方线粗实线打底（读趋势），
    平台线细虚线铺在后面（读差价），点右侧图例只看一个模型。
    """
    w, h = 1000, 668
    lines = pano["lines"]
    b = [text(24, 20, "输出价，折人民币 / 每百万 token（对数轴）", "s")]
    if not lines:
        b.append(text(24, 60, "还没有平台价格：先跑 python3 llmcost_platforms.py", "s"))
        return svg_doc(w, h, "".join(b), "平台价格全景", ' data-pano="1"')

    s = pano["summary"]
    b.append(text(24, 40, "%d 个模型 · %d 个平台 · %d 条报价线　同模型换平台最多差 %.1f 倍"
                  % (s["n_models"], s["n_platforms"], s["n_lines"], s["spread_max"] or 1),
                  "s", "start", 'fill="%s"' % C_MUTE))

    x0, x1, y0, y1 = 76, 690, 600, 88
    lgd_x = 706
    dates = pano["dates"]
    d0, d1 = parse_date(dates[0]), parse_date(dates[-1])
    span = max(1, (d1 - d0).days)
    sx = lambda day: x0 + (parse_date(day) - d0).days / span * (x1 - x0)

    vals = [v for l in lines for _, v in l["series"]]
    ticks = [t for t in (0.5, 1, 2, 3, 5, 10, 20, 30, 50, 100, 200, 300)
             if min(vals) * 0.75 <= t <= max(vals) * 1.35]
    v_lo = min(min(vals) * 0.8, ticks[0] if ticks else 1)
    v_hi = max(max(vals) * 1.2, ticks[-1] if ticks else 10)
    lo, hi = math.log10(v_lo), math.log10(v_hi)
    sy = lambda v: y0 - (math.log10(max(v_lo, min(v_hi, v))) - lo) / (hi - lo) * (y0 - y1)

    for t in ticks:
        y = sy(t)
        b += [line(x0, y, x1, y, C_RULE), text(x0 - 10, y + 4, "%g" % t, "s", "end")]

    # 横轴逐日：月初一道粗线，每周一一格细线，标签写 MM-DD ——
    # 这样「09 月 19 号涨到 108」这种跳变点，眼睛能对着某一天读，而不是只有一个月份。
    # 官方线的观测日属于 must：它周围 4 天内的周一自动让开，免得两个标签叠在一起
    off_days = sorted({day for l in lines if l["kind"] == "official" for day, _ in l["series"]})
    for day, x, major, labeled in day_axis(d0, d1, x0, x1, must=off_days):
        b.append(line(x, y1, x, y0, C_RULE if major else C_RULE2))
        if labeled:
            b.append(text(x, y0 + 18, day.strftime("%m-%d"), "s", "middle",
                          "" if major else 'fill="%s"' % C_MUTE))

    # 第三方快照比官方价起步晚：在起点画一道竖虚线，免得读者以为左边那段"没数据"是漏画
    third_first = min((l["series"][0][0] for l in lines if l["kind"] != "official"), default=None)
    if third_first and (parse_date(third_first) - d0).days > 7:
        xg = sx(third_first)
        b += ['<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" stroke-width="1" '
              'stroke-dasharray="2 4"/>' % (xg, y1 - 6, xg, y0, C_RULE2),
              text(xg + 6, y1 + 2, "第三方平台收录起点 %s" % third_first[5:], "s", "start",
                   'fill="%s"' % C_MUTE)]

    # 颜色按模型名固定，价格变了也不会换色
    color_of = {m: MODEL_COLORS[i % len(MODEL_COLORS)]
                for i, m in enumerate(sorted({l["model"] for l in lines}))}

    # 先画平台线（在下），再画官方线（在上）
    order = sorted(lines, key=lambda l: (l["kind"] == "official", l["model"], l["platform"]))
    for l in order:
        col = color_of[l["model"]]
        dash, wd, op = KIND_STYLE.get(l["kind"], KIND_STYLE["aggregator"])
        # 价格是阶梯量：两次观测之间价格不变，直到观测到新价。
        # 直接连斜线会画出「价格在半个月里匀速下滑」这种不存在的现象。
        pts = step_points([(sx(day), sy(v)) for day, v in l["series"]])
        extra = (' data-model="%s" data-platform="%s" data-kind="%s" data-tier="%s"'
                 % (esc(l["model"]), esc(l["platform"]), esc(l["kind"]), esc(l["tier"])))
        if len(pts) == 1:
            b.append('<circle cx="%.1f" cy="%.1f" r="2.4" fill="%s" opacity="%.2f"%s/>'
                     % (pts[0][0], pts[0][1], col, op, extra))
        else:
            geo = " ".join("%.1f,%.1f" % p for p in pts)
            if l["kind"] == "official":     # 白色外描边：交叉处把下面的线压断，主线才看得清
                b.append('<polyline points="%s" fill="none" stroke="#fbf9f3" stroke-width="%.1f" '
                         'stroke-linejoin="round" stroke-linecap="round" data-model="%s"/>'
                         % (geo, wd + 2.2, esc(l["model"])))
            b.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="%s" '
                     'stroke-linejoin="round" stroke-linecap="round" opacity="%.2f"%s%s/>'
                     % (geo, col, wd, op,
                        (' stroke-dasharray="%s"' % dash) if dash else "", extra))
        if l["kind"] == "official":
            for day, v in l["series"]:
                # <title> 让每个观测点都能悬停读出「哪天 · 多少钱」，
                # 静态图上看不清的日级细节，鼠标一放就出来
                b.append('<circle cx="%.1f" cy="%.1f" r="3.1" fill="%s" '
                         'stroke="#fffdf9" stroke-width="1.2"%s>'
                         '<title>%s · %s %g 元</title></circle>'
                         % (sx(day), sy(v), col, extra, esc(day), esc(l["display"]), v))
        else:
            # 平台线不画点（97 条线一点就糊成毛边），但要留透明命中区：
            # 第三方报价变动频繁，能悬停读出「哪一天、哪个平台、多少钱」才算精确到天
            for day, v in l["series"]:
                b.append('<circle cx="%.1f" cy="%.1f" r="3.2" fill="transparent"%s>'
                         '<title>%s · %s @ %s %g 元</title></circle>'
                         % (sx(day), sy(v), extra, esc(day), esc(l["display"]),
                            esc(l["platform"]), v))

    # 末端不标价：15 个模型的价位挤在 2–110 元之间，标签必然叠。
    # 当前价放进右侧图例的一列，读数和线还能对上号。
    b.append(text(lgd_x, 64, "模型（点一下只看它）", "s"))
    rows = sorted(pano["models"], key=lambda m: -(m["official"] or 0))
    ly = 84
    for m in rows:
        col = color_of[m["model"]]
        b.append('<g data-legend="%s" style="cursor:pointer">' % esc(m["model"]))
        b.append(rect(lgd_x, ly - 6, 11, 3, col, 1.5))
        b.append(text(lgd_x + 17, ly, clip_text(m["display"], 12.5, 148), "t"))
        if m["official"] is not None:
            b.append(text(lgd_x + 212, ly, "%g" % round(m["official"], 2), "t", "end",
                          'fill="%s"' % col))
        b.append(text(w - 22, ly, "%d" % m["n_platforms"], "s", "end", 'fill="%s"' % C_MUTE))
        b.append('</g>')
        ly += 24
    b.append(text(lgd_x + 212, 64, "当前价", "s", "end"))
    b.append(text(w - 22, 64, "平台", "s", "end"))

    # 脚注拆两行，避免超出 1000 的 viewBox 被裁
    b.append(text(24, h - 30, "实线=厂商自营，短虚线=第三方托管，点线=云厂商；横轴逐日（月初粗线、每周一细线），"
                  "圆点是观测点，指上去看具体日期", "s"))
    b.append(text(24, h - 14, "快照只覆盖 09-28 之后，此前的平台点为空是没数据、不是没变价；"
                  "阶梯在观测日拐弯，变价落在哪天就是哪天", "s"))
    return svg_doc(w, h, "".join(b), "平台价格全景", ' data-pano="1"')


def append_history_point(d):
    """每日快照时给价格史补点：价格变了立刻记，否则每 25 天记一次。

    幂等：同一天同一个模型只留一行，重跑不会长重复行。
    """
    if not os.path.exists(HISTORY_FILE):
        return 0
    rows = read_csv(HISTORY_FILE)
    if not rows:
        return 0
    cols = list(rows[0].keys())
    latest = {}
    for r in rows:
        m, day = r.get("model", ""), (r.get("date") or "")[:10]
        if not m or not day:
            continue
        if m not in latest or day > latest[m]["date"]:
            latest[m] = r
    added = 0
    for r in d.get("api", []):
        prev = latest.get(r["model"])
        if not prev:
            continue
        prev_day = (prev.get("date") or "")[:10]
        if prev_day == TODAY:
            continue
        pd = parse_date(prev_day)
        gap = (parse_date(TODAY) - pd).days if pd else 999
        changed = abs((num(prev.get("output"), 0) or 0) - (num(r.get("output"), 0) or 0)) > 1e-9
        if not (changed or gap >= 25):
            continue
        rows.append({
            "date": TODAY, "provider": r["provider"], "model": r["model"],
            "currency": r["currency"], "input": r.get("input", ""),
            "output": r.get("output", ""), "cache_hit": r.get("cache_hit", ""),
            "unit": "1M tokens", "price_kind": r.get("price_kind", "standard"),
            "basis": "snapshot", "source_id": r.get("source_type", "official"),
            "source_url": r.get("source_url", ""),
            "note": ("检测到调价：输出 %s → %s" % (prev.get("output"), r.get("output"))
                     if changed else "例行月度落点"),
        })
        latest[r["model"]] = rows[-1]
        added += 1
    if added:
        rows.sort(key=lambda x: ((x.get("date") or ""), (x.get("provider") or ""),
                              (x.get("model") or "")))
        write_csv(HISTORY_FILE, rows, cols)
    return added


# ---------------------------------------------------------------------------
# 任务换算：1 百万 token / 1 块钱 能做什么
# ---------------------------------------------------------------------------

def task_data(d):
    tasks = []
    for r in read_csv(os.path.join(DATA, "task_examples.csv")):
        n = num(r["tokens_per_run"], 0) or 0
        tasks.append({"task": r["task"], "category": r["category"], "tokens": n,
                      "cache": r["cache_hint"], "note": r["note"],
                      "runs_per_1m": int(1e6 / n) if n else 0})

    api = sorted([r for r in d["api"] if r["output_cny"]], key=lambda r: r["output_cny"])
    bands = []

    def add(label, cost, basis, note):
        if cost and cost > 0:
            short = label.split(" · ")[-1]
            short = short.split("(")[0].strip()
            bands.append({"label": label, "short": short, "cost": cost, "basis": basis,
                          "tokens_per_yuan": 1e6 / cost, "note": note})

    if api:
        std = [r for r in api if r["price_kind"] == "standard"]
        cheapest = (std or api)[0]
        add("最低标准 API · %s" % cheapest["display"], cheapest["output_cny"],
            "输出价（保守口径）", cheapest.get("note", ""))
        mid = api[len(api) // 2]
        add("中位 API · %s" % mid["display"], mid["output_cny"],
            "输出价（保守口径）", mid.get("note", ""))
        add("高价 API · %s" % api[-1]["display"], api[-1]["output_cny"],
            "输出价（保守口径）", api[-1].get("note", ""))
    plans = [p for p in d["plans"] if p["convertible"] and p["cny_per_1m"]]
    wb = [p for p in plans if p["platform"] == "WorkBuddy"]
    if wb:
        add("套餐 · %s" % wb[1]["plan"] if len(wb) > 1 else "套餐 · %s" % wb[0]["plan"],
            (wb[1] if len(wb) > 1 else wb[0])["cny_per_1m"],
            "三档系数折算综合价", "95% 缓存命中口径；积分当月清零")
    promo = [p for p in plans if p["promo_until"] and p["cny_per_1m"]]
    if promo:
        p = min(promo, key=lambda x: x["cny_per_1m"])
        add("限时套餐 · %s" % p["plan"], p["cny_per_1m"],
            "固定额度折算", "⚠ 限时价至 %s；%s 硬约束，实际用不满" %
            (p["promo_until"], ("每 5 小时 %s 次" % p["limit_5h"]) if p["limit_5h"] else "有窗口限额"))
    rig = [r for r in d["rigs"] if num(r.get("hardware_cny"), 0) == 0]
    if rig:
        c = local_cost(rig[0], num(rig[0].get("utilization"), 0.3) or 0.3)
        add("本地 · 已有 %s" % rig[0]["rig"][:18], c, "折旧+电费折算",
            "无硬件采购成本；需设备持续填满负载")

    matrix = []
    for t in tasks:
        row = {"task": t["task"], "tokens": t["tokens"], "runs_per_1m": t["runs_per_1m"],
               "cells": []}
        for b in bands:
            n = b["tokens_per_yuan"] / t["tokens"] if t["tokens"] else 0
            row["cells"].append(n)
        matrix.append(row)
    return {"tasks": tasks, "bands": bands, "matrix": matrix}


def chart_task_budget(d, td):
    """图8 · 1 元在各价格档能买到的 token 数（对数横轴）。墨色深浅=从便宜到贵。"""
    bands = td["bands"]
    rowh, top = 46, 40
    w = 960
    h = top + len(bands) * rowh + 44
    x0, x1 = 300, 792
    lo, hi = math.log10(1e3), math.log10(1e9)
    sx = lambda v: x0 + (math.log10(max(1e3, min(1e9, v))) - lo) / (hi - lo) * (x1 - x0)
    b = [text(24, 18, "1 元能买到的 token 数（对数轴）", "s")]
    tick_cn = {1e3: "1 千", 1e4: "1 万", 1e5: "10 万", 1e6: "100 万",
               1e7: "1000 万", 1e8: "1 亿", 1e9: "10 亿"}
    for v in (1e3, 1e4, 1e5, 1e6, 1e7, 1e8, 1e9):
        x = sx(v)
        b += [line(x, top - 12, x, top + len(bands) * rowh - 12, C_RULE),
              text(x, top - 18, tick_cn[v], "s", "middle")]
    ramp = ["#2c3136", "#3a3f45", "#4a4f55", "#5b6066", "#6c7177", "#7d8288"]
    for i, band in enumerate(bands):
        y = top + i * rowh
        col = ramp[i % len(ramp)]
        b.append(text(24, y + 12, band["label"][:26], "t"))
        b.append(text(24, y + 27, band["basis"], "s"))
        xe = sx(band["tokens_per_yuan"])
        b.append(rect(x0, y + 2, max(2, xe - x0), 18, col, 2, 'opacity="0.9"'))
        lab = "%s token" % format(int(band["tokens_per_yuan"]), ",")
        if xe - x0 > 118:
            b.append(text(xe - 8, y + 15, lab, "s", "end", 'fill="#fffdf9"'))
        else:
            b.append(text(xe + 8, y + 15, lab, "s", "start"))
        b.append(text(x1 + 12, y + 15, "%.3g 元/百万" % band["cost"], "v", "start"))
    b.append(text(24, h - 12, "限时套餐档是数学上限：受 5 小时 / 周限额与活动到期约束，实际往往用不满；"
                  "缓存命中率高时真实成本可比输出价低一个数量级", "s"))
    return svg_doc(w, h, "".join(b), "1 元可买到的 token 数")


def _runs_label(n):
    if n >= 1000:
        return "%s 次" % format(int(n), ",")
    if n >= 10:
        return "%.0f 次" % n
    if n >= 1:
        return "%.1f 次" % n
    if n >= 0.01:
        return "%.2f 次" % n
    return "不足 0.01 次"


def task_cards_html(d, td):
    tasks, bands = td["tasks"], td["bands"]
    # 卡片 A：1 百万 token
    rows_a = []
    for t in tasks:
        frac = math.log10(max(1, t["runs_per_1m"])) / math.log10(1e6) if t["runs_per_1m"] else 0
        rows_a.append(
            "<tr><td><b>%s</b><div class='sub'>%s</div></td>"
            "<td class='num'>%s</td><td class='num'><b>%s</b></td>"
            "<td><div class='minibar' style='width:%.1f%%'></div></td>"
            "<td class='sub'>%s</td></tr>" %
            (esc(t["task"]), esc(t["category"]), format(int(t["tokens"]), ","),
             esc(_runs_label(t["runs_per_1m"])), max(2, frac * 100), esc(t["note"])))
    card_a = (
        "<div class='card'><h2>⑪ 1 百万 token 能完成什么</h2>"
        "<p class='desc'>1M token 是固定物理量，与价格无关。下表按<b>单次任务 token 估算</b>"
        "给出可跑次数；估算已含系统提示词、上下文重发与典型返工，缓存命中率高时实际能跑更多。</p>"
        "<div class='scroll'><table class='dt'><thead><tr><th>任务</th><th class='num'>单次 token 估算</th>"
        "<th class='num'>1M token 可跑</th><th>相对量级</th><th>说明</th></tr></thead><tbody>%s</tbody></table></div>"
        "<p class='desc' style='margin-top:10px'>直观对照：约等于 <b>500 次短问答</b>、"
        "<b>22 份 20 页 PDF 摘要</b>、<b>2～3 次深度研究</b>，或<b>一整轮 20 轮长对话</b>。"
        "注意长对话每轮重发历史，token 会随轮次滚雪球。</p></div>" % "".join(rows_a))

    # 卡片 B：1 块钱
    th = "".join("<th class='num'>%s<div class='sub'>%.3g 元/百万</div></th>" %
                 (esc(b["label"]), b["cost"]) for b in bands)
    rows_b = []
    for r in td["matrix"]:
        cells = "".join("<td class='num'>%s</td>" % esc(_runs_label(v)) for v in r["cells"])
        rows_b.append("<tr><td><b>%s</b><div class='sub'>%s token/次</div></td>%s</tr>" %
                      (esc(r["task"]), format(int(r["tokens"]), ","), cells))
    band_notes = "".join("<li><b>%s</b>：%s。%s</li>" %
                         (esc(b["label"]), esc(b["basis"]), esc(b["note"])) for b in bands)
    card_b = (
        "<div class='card'><h2>⑫ 1 块钱能完成什么</h2>"
        "<p class='desc'>按各价格档的「元 / 百万 token」反算 1 元可买到的 token，再除以任务估算。"
        "<b>各档口径不同</b>（输出价 / 套餐综合价 / 折旧电价），只作量级对照，不可直接下单。</p>"
        "<div class='scroll'><table class='dt'><thead><tr><th>任务</th>%s</tr></thead>"
        "<tbody>%s</tbody></table></div>"
        "<p class='desc' style='margin-top:12px'><b>价格档口径</b></p><ul>%s</ul>"
        "<p class='desc'>⚠ 三个最容易误读的点：① 输出价是<b>保守口径</b>，"
        "缓存命中 95%% 时真实成本可能低一个数量级；② 限时套餐档是数学上限，"
        "受 5 小时 / 周限额与活动到期约束；③ 本地档假设设备已存在且负载填满，"
        "未计运维与资本占用。</p></div>" % (th, "".join(rows_b), band_notes))
    return card_a + card_b


# ---------------------------------------------------------------------------
# 同一组数据的多个表格视图（可排序 / 筛选 / 搜索，纯原生 JS）
# ---------------------------------------------------------------------------

def table_views_html(d, tl):
    def td(v, cls=""):
        return "<td class='%s'>%s</td>" % (cls, esc("—" if v in (None, "") else v))

    # 视图 1：API
    api_rows = []
    for r in d["api"]:
        flag = " ".join(r["all_flags"])
        cells = "".join([
            td(r["provider"]), td(r["display"]),
            td(fmt(r["output"], 2), "num"), td(fmt(r["output_cny"], 2), "num"),
            td(r["currency"]), td(r["price_kind"]),
            "<td><span class='pill' style='background:%s'>%s</span></td>" %
            (STATUS_COLOR[r["status"]], STATUS_CN[r["status"]]),
            td(", ".join(r["agreeing_sources"]) or "—"), td(r["verified_at"]),
        ])
        api_rows.append(
            "<tr data-status='%s' data-search='%s'>%s</tr>" %
            (esc(r["status"]),
             esc((r["provider"] + " " + r["display"] + " " + r["model"] + " " + flag).lower()),
             cells))
    api_table = (
        "<table class='dt' data-view='api'><thead><tr>"
        "<th data-sort='0'>厂商</th><th data-sort='1'>模型</th>"
        "<th data-sort='2' data-type='num' class='num'>输出价</th>"
        "<th data-sort='3' data-type='num' class='num'>折合 CNY</th>"
        "<th data-sort='4'>币种</th><th data-sort='5'>口径</th>"
        "<th data-sort='6'>准确性</th><th data-sort='7'>一致来源</th>"
        "<th data-sort='8'>核验日期</th></tr></thead><tbody>%s</tbody></table>" %
        "".join(api_rows))

    # 视图 2：套餐
    plan_rows = []
    for p in d["plans"]:
        plan_rows.append(
            "<tr data-search='%s'>%s%s%s%s%s%s%s%s%s%s</tr>" %
            (esc((p["platform"] + " " + p["plan"] + " " + p["unit_kind"]).lower()),
             td(p["platform"]), td(p["plan"]), td(fmt(p["monthly_cny"], 2), "num"),
             td(format(int(p["total_credits"]), ",") if p["total_credits"] else "—", "num"),
             td(p["unit_kind"]),
             td(fmt(p["cny_per_1m"], 4) if p["cny_per_1m"] else "不可折算", "num"),
             td(p["limit_5h"] or "—"), td(p["promo_until"] or "—"),
             td(p["source_type"]), td(p["why"] if not p["convertible"] else p["note"][:40])))
    plan_table = (
        "<table class='dt' data-view='plans'><thead><tr>"
        "<th data-sort='0'>平台</th><th data-sort='1'>套餐</th>"
        "<th data-sort='2' data-type='num' class='num'>月费(元)</th>"
        "<th data-sort='3' data-type='num' class='num'>实得额度</th>"
        "<th data-sort='4'>计费单位</th>"
        "<th data-sort='5' data-type='num' class='num'>元/百万 token</th>"
        "<th>5h 限额</th><th>活动到期</th><th>来源类型</th><th>备注</th>"
        "</tr></thead><tbody>%s</tbody></table>" % "".join(plan_rows))

    # 视图 3：本地
    local_rows = []
    for r in d["rigs"]:
        c = local_cost(r, num(r.get("utilization"), 0.3) or 0.3)
        local_rows.append(
            "<tr data-search='%s'>%s%s%s%s%s%s%s%s%s%s</tr>" %
            (esc((r["rig"] + " " + r["model"] + " " + r["quant"]).lower()),
             td(r["rig"]), td(r["model"]), td(r["quant"]),
             td(format(int(num(r["hardware_cny"], 0) or 0), ","), "num"),
             td(r["depreciation_years"] + " 年", "num"),
             td(r["power_w"] + " W", "num"),
             td(r["tok_s"] + " tok/s", "num"),
             td("%.0f%%" % ((num(r["utilization"], 0.3) or 0.3) * 100), "num"),
             td(fmt(c, 2) if c else "—", "num"), td(r["note"][:44])))
    local_table = (
        "<table class='dt' data-view='local'><thead><tr>"
        "<th data-sort='0'>方案</th><th data-sort='1'>模型</th><th data-sort='2'>量化</th>"
        "<th data-sort='3' data-type='num' class='num'>一次性采购(元)</th>"
        "<th>折旧</th><th>整机功耗</th><th>实测吞吐</th>"
        "<th data-sort='8' data-type='num' class='num'>假设利用率</th>"
        "<th data-sort='9' data-type='num' class='num'>元/百万 token</th><th>备注</th>"
        "</tr></thead><tbody>%s</tbody></table>" % "".join(local_rows))

    # 视图 4：来源覆盖
    src_rows = []
    src_meta = {x["id"]: x.get("url", "") for x in load_sources()["sources"]}
    for sid, s in d["source_coverage"].items():
        src_rows.append("<tr data-search='%s'>%s%s%s%s%s%s%s</tr>" %
                        (esc((s["name"] + " " + sid).lower()),
                         td(s["name"]), td(s["kind"]), td(fmt(s["weight"], 2), "num"),
                         td("/".join(s["covers"])), td(s["n_obs"], "num"),
                         td(s.get("n_events", 0), "num"),
                         "<td><a href='%s' target='_blank' rel='noopener'>%s</a></td>" %
                         (esc(src_meta.get(sid, "")), esc(sid))))
    src_table = (
        "<table class='dt' data-view='sources'><thead><tr>"
        "<th data-sort='0'>来源</th><th data-sort='1'>类型</th>"
        "<th data-sort='2' data-type='num' class='num'>权重</th><th>覆盖维度</th>"
        "<th data-sort='4' data-type='num' class='num'>价格观测</th>"
        "<th data-sort='5' data-type='num' class='num'>外部事件</th><th>链接</th>"
        "</tr></thead><tbody>%s</tbody></table>" % "".join(src_rows))

    # 视图 5：事件 / 变更（本地事件 + 外部 changelog）
    ev_rows = []
    for e in sorted(tl["events"], key=lambda x: x["date"]):
        ev_rows.append("<tr data-search='%s'>%s%s%s%s%s</tr>" %
                       (esc((e["date"] + e["model"] + e["type"] + e["detail"]).lower()),
                        td(e["date"]), td(e["type"]), td(e["model"]),
                        td(e["detail"]), td(e["source_id"])))
    for c in tl["external_events"]:
        ev_rows.append("<tr data-search='%s'>%s%s%s%s%s</tr>" %
                       (esc((c.get("model_id", "") + c.get("change_type", "")).lower()),
                        td((c.get("generated_at") or "")[:10]), td(c.get("change_type", "")),
                        td(c.get("model_id", "")),
                        td("LLMTracker 追踪到的模型事件"), td("llmtracker")))
    ev_table = (
        "<table class='dt' data-view='events'><thead><tr>"
        "<th data-sort='0'>日期</th><th data-sort='1'>类型</th><th data-sort='2'>模型 / 对象</th>"
        "<th>说明</th><th data-sort='4'>来源</th></tr></thead><tbody>%s</tbody></table>" %
        "".join(ev_rows))

    tabs = [("api", "API 价格", len(d["api"])), ("plans", "套餐折算", len(d["plans"])),
            ("local", "本地部署", len(d["rigs"])), ("sources", "来源覆盖", len(d["source_coverage"])),
            ("events", "调价 / 事件", len(ev_rows))]
    tab_html = "".join(
        "<button class='tab%s' data-tab='%s'>%s <span class='cnt'>%d</span></button>" %
        (" active" if i == 0 else "", k, label, n) for i, (k, label, n) in enumerate(tabs))
    status_chips = "".join(
        "<button class='chip' data-status='%s' style='border-color:%s;color:%s'>%s %d</button>" %
        (s, STATUS_COLOR[s], STATUS_COLOR[s], STATUS_CN[s], d["counts"][s])
        for s in STATUS_ORDER if d["counts"][s])

    return """
<div class="card"><h2>⑥ 同一组数据的多个表格视图</h2>
<p class="desc">五个视图共用底层的三张主表与核验结果。点击表头排序、用状态胶囊筛选、输入关键词即时过滤；
「显示 N / M 行」随筛选变化。数据来自 <code>out/accuracy.json</code>，无外部依赖。</p>
<div class="toolbar"><div class="tabs">__TABS__</div>
<input id="q" type="search" placeholder="搜索当前视图…" autocomplete="off">
<span class="cnt" id="shown"></span></div>
<div class="chips" id="chips">__CHIPS__<button class="chip ghost" data-status="all">全部</button></div>
<div class="scroll">
<div class="table-view" data-view="api">__API__</div>
<div class="table-view" data-view="plans" hidden>__PLANS__</div>
<div class="table-view" data-view="local" hidden>__LOCAL__</div>
<div class="table-view" data-view="sources" hidden>__SOURCES__</div>
<div class="table-view" data-view="events" hidden>__EVENTS__</div>
</div></div>
<script>
(function(){
  var views=[].slice.call(document.querySelectorAll('.table-view'));
  var tabs=[].slice.call(document.querySelectorAll('.tab'));
  var q=document.getElementById('q'), shown=document.getElementById('shown');
  var chips=document.getElementById('chips');
  var active='api', activeStatus='all';
  function current(){return views.filter(function(v){return v.dataset.view===active;})[0];}
  function apply(){
    var view=current(), rows=[].slice.call(view.querySelectorAll('tbody tr')), n=0;
    var term=(q.value||'').trim().toLowerCase();
    rows.forEach(function(r){
      var ok=true;
      if(active==='api' && activeStatus!=='all' && r.dataset.status!==activeStatus) ok=false;
      if(ok && term && (r.dataset.search||r.textContent).toLowerCase().indexOf(term)<0) ok=false;
      r.hidden=!ok; if(ok) n++;
    });
    var total=rows.length;
    shown.textContent='显示 '+n+' / '+total+' 行';
    var chipBox=chips; chipBox.style.display = (active==='api')?'flex':'none';
  }
  tabs.forEach(function(t){t.addEventListener('click',function(){
    tabs.forEach(function(x){x.classList.remove('active');});
    t.classList.add('active'); active=t.dataset.tab;
    views.forEach(function(v){v.hidden = v.dataset.view!==active;});
    activeStatus='all'; q.value=''; apply();
  });});
  chips.addEventListener('click',function(e){
    var b=e.target.closest('.chip'); if(!b) return;
    activeStatus=b.dataset.status;
    [].slice.call(chips.querySelectorAll('.chip')).forEach(function(x){x.classList.remove('on');});
    b.classList.add('on'); apply();
  });
  q.addEventListener('input',apply);
  views.forEach(function(v){
    [].slice.call(v.querySelectorAll('th[data-sort]')).forEach(function(th){
      th.style.cursor='pointer'; th.title='点击排序';
      th.addEventListener('click',function(){
        var idx=parseInt(th.dataset.sort,10), isNum=th.dataset.type==='num';
        var tb=v.querySelector('tbody'), rows=[].slice.call(tb.querySelectorAll('tr'));
        var asc=th.dataset.asc!=='1'; th.dataset.asc=asc?'1':'0';
        rows.sort(function(a,b){
          var x=a.cells[idx].textContent.replace(/[,%\\s元\\/百万tokW年次]/g,'');
          var y=b.cells[idx].textContent.replace(/[,%\\s元\\/百万tokW年次]/g,'');
          var nx=parseFloat(x), ny=parseFloat(y);
          var cmp=(isNum && !isNaN(nx) && !isNaN(ny))?(nx-ny):x.localeCompare(y,'zh-CN');
          return asc?cmp:-cmp;
        });
        rows.forEach(function(r){tb.appendChild(r);});
      });
    });
  });
  apply();
})();
</script>
""".replace("__TABS__", tab_html).replace("__CHIPS__", status_chips) \
   .replace("__API__", api_table).replace("__PLANS__", plan_table) \
   .replace("__LOCAL__", local_table).replace("__SOURCES__", src_table) \
   .replace("__EVENTS__", ev_table)


def chart_ladder(lb, d):
    """图：横轴输出价（对数），纵轴 LMArena 综合 Elo。

    编码只回答一个问题：这个价，换到多少分。所以
    - 实心点 = Pareto 前沿（不存在比它更便宜且更强的）；
    - 空心点 = 已被别人支配，右下方向的点就是「又贵又弱」；
    - 朱砂阶梯 = 前沿本身，沿着它往上走，就是「加钱能买到多少分」。
    """
    rows = [r for r in ((lb or {}).get("rows") or []) if r.get("score")]
    if not rows:
        return svg_doc(1000, 260, text(30, 60, "还没有榜单数据：先跑 python3 llmcost_leaderboard.py", "s"),
                       "模型天梯榜")
    # 配色跟全景图用同一套排法（按 model 名排序取色），同一模型在两个图里颜色一致
    universe = sorted({str(r.get("model")) for r in (d.get("api") or [])}) or \
        sorted({str(r["model"]) for r in rows})
    color_of = {m: MODEL_COLORS[i % len(MODEL_COLORS)] for i, m in enumerate(universe)}
    w, h = 1000, 500
    x0, x1, y0, y1 = 76, 724, 56, 408
    lo, hi = math.log10(1.0), math.log10(130)
    sx = lambda v: x0 + (math.log10(max(1.0, min(130, v))) - lo) / (hi - lo) * (x1 - x0)
    scores = [r["score"] for r in rows]
    # 纵轴只留必要的余量：多留一格 20 分，点就会挤成一条横线
    ylo = math.floor((min(scores) - 6) / 10) * 10
    yhi = math.ceil((max(scores) + 6) / 10) * 10
    sy = lambda v: y1 - (v - ylo) / (yhi - ylo) * (y1 - y0)

    b = [text(24, 24, "元 / 百万输出 token（对数轴）× LMArena 综合 Elo", "s"),
         text(24, 41, "实心＝没人比它更便宜又更强；空心＝已被支配", "s", "start",
              'fill="%s"' % C_MUTE)]
    for v in (1, 2, 5, 10, 20, 50, 100):
        x = sx(v)
        b += [line(x, y0, x, y1, C_RULE), text(x, y1 + 20, "%g" % v, "s", "middle")]
    v = ylo
    while v <= yhi:
        y = sy(v)
        b += [line(x0, y, x1, y, C_RULE), text(x0 - 12, y + 4, "%d" % v, "s", "end")]
        v += 20

    # 前沿阶梯：沿价格升序，先走横线再跳纵线（和价格全景一致的画法）
    front = sorted([r for r in rows if r.get("pareto")], key=lambda r: r["price"])
    if len(front) > 1:
        pts = []
        for i, r in enumerate(front):
            if i:
                pts.append((sx(r["price"]), sy(front[i - 1]["score"])))
            pts.append((sx(r["price"]), sy(r["score"])))
        b.append(polyline(pts, C_ACC, 1.8, "5 4"))
    if front:
        b.append(text(sx(front[0]["price"]) + 34, sy(front[0]["score"]) + 15,
                      "前沿：加钱能买到的分", "s", "start", 'fill="%s"' % C_ACC))

    for r in rows:
        cx, cy = sx(r["price"]), sy(r["score"])
        col = color_of.get(r["model"], C_MUTE)
        if r.get("pareto"):
            b.append('<circle cx="%.1f" cy="%.1f" r="7" fill="%s" stroke="#fffdf9" '
                     'stroke-width="2.4"/>' % (cx, cy, col))
        else:
            b.append('<circle cx="%.1f" cy="%.1f" r="5.4" fill="#fffdf9" stroke="%s" '
                     'stroke-width="2" opacity="0.8"/>' % (cx, cy, col))

    # 前沿点直接标名（只有 3 个，标得开）；其余靠右侧图例，避免十几个标签互相压。
    # 上下交替：相邻两个前沿点分数只差 6 分（约 20px），都往上标必然叠在一起。
    # 起点给到 cx+14：圆点半径 7 + 描边 1.2，再留 6px 空隙，否则文字看着贴在点上。
    for i, r in enumerate(front):
        cx, cy = sx(r["price"]), sy(r["score"])
        above = (i % 2 == 0)
        # 纸色描边做出「挖空」效果：朱砂阶梯线会从标签下方穿过，不挖空就压字
        b.append(text(cx + 14, cy + (-12 if above else 19),
                      clip_text(r["display"], 11, 150), "v", "start",
                      'fill="%s" stroke="#fffdf9" stroke-width="3.6" '
                      'paint-order="stroke" stroke-linejoin="round"' % C_ACC))

    # 右侧图例：色块 / 名 / 价 / 分，按分数倒序
    lx, ly = 784, 60
    b += [text(lx, ly - 14, "模型", "s"), text(lx + 160, ly - 14, "价", "s", "end"),
          text(lx + 216, ly - 14, "Elo", "s", "end")]
    for i, r in enumerate(sorted(rows, key=lambda x: -x["score"])):
        y = ly + i * 24
        col = color_of.get(r["model"], C_MUTE)
        b.append('<circle cx="%.1f" cy="%.1f" r="4.6" fill="%s"%s/>'
                 % (lx + 5, y - 4, col if r.get("pareto") else "#fffdf9",
                    "" if r.get("pareto") else ' stroke="%s" stroke-width="1.8"' % col))
        b.append(text(lx + 16, y, clip_text(r["display"], 11.5, 132), "s"))
        b.append(text(lx + 160, y, "%.2f" % r["price"], "s", "end"))
        b.append(text(lx + 216, y, "%.0f" % r["score"], "v", "end"))
    b.append(text(24, h - 12, "Elo 为 LMArena 人类偏好对战评分，同一模型的档位（High / Max）取分最高者；"
                  "分数不可跨维度比较（视觉 / Agent 各用各的标尺）。", "s"))
    return svg_doc(w, h, "".join(b), "模型天梯榜 · 价格与实力")


def render_charts(d, crosses=None, pano=None, lb=None):
    """九张图的 SVG 字符串，键是不带 .svg 的文件名。

    跟 chart() 的区别：只算不写盘 —— pocket 里那张页面是按请求现算的。
    """
    tl = d.get("timeline") or build_timeline([], d)
    td = task_data(d)
    hist = d.get("history") or build_price_history(d)
    pano = pano or d.get("panorama") or build_price_panorama(d)
    p2, xc = chart_plan_vs_api(d)
    return {
        "api_prices": chart_api_prices(d),
        "plan_vs_api": p2,
        "local_cost": chart_local(d),
        "accuracy": chart_accuracy(d),
        "summary": chart_summary(d),
        "price_timeline": chart_price_timeline(d, tl),
        "activity_timeline": chart_activity_timeline(d, tl),
        "api_history": chart_api_history(hist, d),
        "price_panorama": chart_price_panorama(pano, d),
        "task_budget": chart_task_budget(d, td),
        "ladder": chart_ladder(lb, d),
    }, xc


def sync_platform_db():
    """从 price_history + 最新第三方快照重建平台价格库。

    放在 core 里，是为了让 `llmcost.py --snapshot` 一条命令把三处数据都刷新；
    失败不致命 —— 平台页停在上一版，其他卡片不受影响。
    """
    try:
        base = os.path.dirname(os.path.abspath(__file__))
        if base not in sys.path:
            sys.path.insert(0, base)
        import llmcost_platforms as _plat
        return _plat.build(write=True, verbose=False)
    except Exception:                                # noqa: BLE001
        return None


def compute(save=True):
    """跑一遍完整链路：观测 → 核验 → 时间轴 → 价格史。返回 (d, crosses)。

    save=False 时不落 accuracy.json / 报告，只算数（服务端刷新用）。
    save=True 时顺手把本月价格点写进 price_history.csv —— 明年的「三个月数据」
    就是今天这些自动落点长出来的。
    """
    global TODAY
    TODAY = today()          # 常驻进程跨天也不用重启
    ensure_dirs()
    cfg = load_sources()
    obs, loaded, ext = collect_observations()
    d = verify_data(cfg, obs, loaded, ext)
    if save:
        n = append_history_point(d)
        if n:
            d["history"] = build_price_history(d)
        # 官方价补点之后才重建平台库，否则今天的新价进不了「平台价格」页
        sync_platform_db()
        d["panorama"] = build_price_panorama(d)
        write_accuracy_report(d)
    _, crosses = chart_plan_vs_api(d)
    return d, crosses


def chart(d, crosses):
    p1 = chart_api_prices(d)
    p2, crosses = chart_plan_vs_api(d)
    p3 = chart_local(d)
    p4 = chart_accuracy(d)
    p5 = chart_summary(d)
    tl = d.get("timeline") or build_timeline([], d)
    td = task_data(d)
    p6 = chart_price_timeline(d, tl)
    p7 = chart_activity_timeline(d, tl)
    p8 = chart_task_budget(d, td)
    hist = d.get("history") or build_price_history(d)
    p9 = chart_api_history(hist, d)
    pano = d.get("panorama") or build_price_panorama(d)
    p10 = chart_price_panorama(pano, d)
    files = [write_svg("chart_api_prices.svg", p1), write_svg("chart_plan_vs_api.svg", p2),
             write_svg("chart_local_cost.svg", p3), write_svg("chart_accuracy.svg", p4),
             write_svg("chart_summary.svg", p5),
             write_svg("chart_price_timeline.svg", p6),
             write_svg("chart_activity_timeline.svg", p7),
             write_svg("chart_api_history.svg", p9),
             write_svg("chart_price_panorama.svg", p10),
             write_svg("chart_task_budget.svg", p8)]

    timeline_cards = (
        "<div class='card'><h2>⑦ 按日期的折线图</h2>"
        "<p class='desc'>折线只连接<b>该日确有观测</b>的点，不做逐日插值；日期轴等距显示（非按天数比例）。"
        "竖虚线是已知的调价 / 活动到期事件。随着 <code>init</code> 每天累积主表快照，"
        "这张图会自动长出真实的价格版本轨迹。</p>" + p6 +
        "<div style='margin-top:14px'></div>" + p7 +
        "<p class='desc' style='margin-top:10px'>事件明细可在下方「⑥ 多视图表格 → 调价 / 事件」里按日期排序、"
        "搜索；外部 47 条来自 LLMTracker 每 6 小时的 changelog。</p></div>" +
        "<div class='card'><h2>⑧ 三个月的价格史</h2>"
        "<p class='desc'>每行数据 = 某模型在某一天的价格点，来自 <code>data/price_history.csv</code>。"
        "上半看全盘水位（几何均值 + 四分位带），下半只看期间真有过调价的模型 —— "
        "大多数模型三个月里其实一次都没动，这件事本身就是结论。</p>" + p9 + "</div>" +
        "<div class='card'><h2>⑨ 平台价格全景</h2>"
        "<p class='desc'>同一个模型在不同平台是<b>不同的商品</b>：颜色是模型、线型是平台类型"
        "（实线=厂商自营，短虚线=第三方托管，点线=云厂商）。价格库来自 "
        "<code>data/platforms.csv</code> + <code>data/price_points.csv</code>，"
        "由 <code>llmcost_platforms.py</code> 从官方历史与第三方快照合成。</p>" + p10 +
        "<p class='desc' style='margin-top:10px'>两条读图守则：① 阶梯线表示价格在两次观测之间不变，"
        "斜线会画出不存在的渐变；② 云厂商比官方便宜，先怀疑它没跟上调价 —— "
        "快照里 Azure 的 Claude 还停在 10 美元，而官方 09-01 已调到 15。</p></div>" +
        "<div class='card'><h2>⑩ 1 块钱的购买力</h2>"
        "<p class='desc'>各价格档按自身口径折算，横向不可直接比「谁更划算」——"
        "输出价是保守口径，套餐是综合价，本地是折旧+电费。</p>" + p8 + "</div>")
    extra_cards = (table_views_html(d, tl) + timeline_cards + task_cards_html(d, td))

    counts = d["counts"]
    conf_rows = []
    for r in d["api"]:
        for c in r["conflicts"]:
            conf_rows.append("<tr><td>%s %s</td><td>%s</td><td>%s</td><td>%s</td>"
                             "<td>%.1f%%</td><td>%s</td></tr>" %
                             (esc(r["provider"]), esc(r["display"]), esc(c["metric"]),
                              fmt(c["main"]), fmt(c["value"]), c["rel"] * 100, esc(c["note"])))
    def cross_item(p, inc):
        warn = []
        if p.get("promo_until"):
            warn.append("限时价至 %s" % p["promo_until"])
        if p.get("limit_5h"):
            warn.append("每 5 小时仅 %s 次" % p["limit_5h"])
        tail = "；⚠ " + "、".join(warn) + "，实际可能用不满" if warn else ""
        return ("<li><b>%s</b>：约 <b>%s 百万 token/月</b> 与 API 打平"
                "（折合 %.4f 元/百万）%s</li>" %
                (esc(p["plan"]), format(int(inc), ","), p["cny_per_1m"], tail))
    cross_rows = "".join(cross_item(p, inc) for p, inc in crosses[:6]) or \
        "<li>本轮无可用临界点（套餐等效单价高于 API 基准或不可折算）</li>"

    html = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>大模型三维度成本追踪看板</title>
<style>
:root{--bg:#f5f7fa;--card:#fff;--ink:#1d2733;--sub:#6b7684;--line:#e8edf2;--blue:#2f6fd0}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font-family:'WenQuanYi Micro Hei','PingFang SC','Microsoft YaHei',system-ui,sans-serif}
.wrap{max-width:1040px;margin:0 auto;padding:28px 20px 60px}
header h1{font-size:24px;margin:0 0 6px}header p{color:var(--sub);font-size:13px;margin:0 0 22px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:22px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.kpi b{display:block;font-size:22px;margin-bottom:4px}.kpi span{font-size:12px;color:var(--sub)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin-bottom:18px}
.card h2{font-size:16px;margin:0 0 4px}.card .desc{font-size:12px;color:var(--sub);margin:0 0 14px}
svg{display:block}.tag{display:inline-block;font-size:11px;padding:2px 8px;border-radius:10px;margin-right:6px}
table{width:100%;border-collapse:collapse;font-size:12px}th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line)}
th{color:var(--sub);font-weight:600}td:nth-child(n+3){font-variant-numeric:tabular-nums}
ul{font-size:13px;line-height:1.9;padding-left:20px}
.foot{font-size:12px;color:var(--sub);line-height:1.8}
code{background:#eef2f6;padding:1px 5px;border-radius:4px;font-size:11px}
</style></head><body><div class="wrap">
<header><h1>大模型三维度成本追踪看板</h1>
<p>API 按量 · 订阅套餐 · 本地部署 ｜ 数据快照 __DATE__ ｜ 多源交叉校验：__OBS__ 条观测 / __NSRC__ 个来源 ｜ USD→CNY __FX__ 仅作可比换算</p></header>
<div class="kpis">
<div class="kpi"><b>__NAPI__</b><span>追踪 API 模型</span></div>
<div class="kpi"><b>__NPLAN__</b><span>追踪套餐</span></div>
<div class="kpi"><b>__NRIG__</b><span>本地硬件方案</span></div>
<div class="kpi"><b style="color:#1f9d6b">__OK__</b><span>多源一致</span></div>
<div class="kpi"><b style="color:#d3453b">__BAD__</b><span>冲突 / 过期 / 缺源</span></div>
<div class="kpi"><b style="color:#7c6bd6">__UNCOV__</b><span>无交叉观测 / 口径不可比</span></div>
<div class="kpi"><b>__NDAYS__</b><span>有观测的日期</span></div>
<div class="kpi"><b style="color:#d99a1c">__NEVENT__</b><span>调价 / 活动事件</span></div>
</div>
<div class="card"><h2>① API 价格</h2><p class="desc">统一到元/百万输出 token，对数轴；右侧圆点代表数据准确性状态。非标准价（峰谷/促销）标 ※。</p>__SVG1__</div>
<div class="card"><h2>② 套餐 vs API 回本临界</h2><p class="desc">月费打底 + 超额按套餐等效单价；竖虚线为与 API 基准打平的用量。percent / 积分公式类套餐不给 token 明细，已排除并标注不可折算。</p>__SVG2__
<ul>__CROSS__</ul></div>
<div class="card"><h2>③ 本地部署成本</h2><p class="desc">横轴利用率，纵轴每百万 token 成本（硬件折旧 + 电费，未计运维/机房/资本占用）。红色虚线为低价 API 基准。</p>__SVG3__</div>
<div class="card"><h2>④ 数据准确性</h2><p class="desc">参考 LiteLLM / AICostBudget / Liutasil501 / LLMTracker / pricemon / OpenRouter / 模真真 / 公众号日报 / llmstatus / 本地实测。口径不一致不参与数值比对。</p>__SVG4__
<h3 style="font-size:13px;margin-top:16px">待人工复核的冲突</h3>
<table><thead><tr><th>模型</th><th>指标</th><th>主表</th><th>他源</th><th>偏差</th><th>可能原因</th></tr></thead><tbody>__CONF__</tbody></table>
<p class="desc" style="margin-top:10px">冲突不等于主表错误：常见于上游版本滞后、官方调价未同步、跨版本同名、国际 USD 与国内 CNY 口径。处理顺序：回官方页 → 记生效日 → 更新 price_version → 写 changelog。</p></div>
<div class="card"><h2>⑤ 三条路径单位成本对照</h2><p class="desc">最低 / 中位 / 最高并列；三者质量、延迟、合规属性不等价，仅比单位成本。</p>__SVG5__</div>
__EXTRA_CARDS__
<div class="card"><h2>数据口径与使用边界</h2><div class="foot">
· 本看板是<strong>静态快照</strong>，不是实时报价器或健康仪表盘；实时性靠 <code>fetch</code> 与官方状态页订阅。<br>
· 每条主表记录带 <code>source_url</code> / <code>verified_at</code> / <code>source_type</code> / <code>price_version</code>；调价 diff 见 <code>out/changelog.md</code>。<br>
· 第三方托管渠道价（Bedrock / Azure / GMI / Databricks）单列为渠道价差，不与官方直连价混比。<br>
· 国内 CNY 报价的同币种交叉源偏少（开源价格库以 USD 为主）；「无交叉观测 / 口径不可比」不等于价格错误，只说明本轮没找到可比来源，需补 pricemon CNY 接口或公众号日报。<br>
· 极低价套餐多来自限时活动且带 5 小时 / 周限额，回本临界点只是数学值，实际可能用不满。<br>
· 促销价、峰谷价、缓存价分列，禁止取最小值直接排序；套餐中 <code>percent</code> / <code>credits_formula</code> 明确标为不可折算。<br>
· 本地 tok/s 来自个人实测样本（非受控基准）；折旧年限、电价、利用率均为假设，详见 <code>out/accuracy_report.md</code>。<br>
· 命令：<code>init</code> / <code>fetch</code> / <code>verify</code> / <code>chart</code> / <code>report</code> / <code>diff</code> / <code>audit-plans</code>；联网失败见 <code>out/fetch_status.json</code>。
</div></div>
</div></body></html>"""
    EXTRA_CSS = """
.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:10px}
.tabs{display:flex;gap:6px;flex-wrap:wrap}
.tab{border:1px solid var(--line);background:#fff;color:var(--sub);border-radius:8px;
padding:7px 12px;font-size:12px;cursor:pointer;font-family:inherit}
.tab.active{background:#2f6fd0;color:#fff;border-color:#2f6fd0}
.tab .cnt{font-size:11px;color:var(--sub)}.tab.active .cnt{color:#dce8fb}
.cnt{font-size:11px;color:var(--sub)}
#q{border:1px solid var(--line);border-radius:8px;padding:7px 10px;font-size:12px;
min-width:190px;font-family:inherit}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}
.chip{border:1px solid;border-radius:14px;background:#fff;font-size:11px;
padding:3px 10px;cursor:pointer;font-family:inherit}
.chip.ghost{color:var(--sub);border-color:var(--line)}
.chip.on{background:#eef4fd;font-weight:700}
.scroll{overflow-x:auto}
.dt{min-width:820px;font-size:12px}
.dt th{white-space:nowrap;user-select:none}
.dt th[data-sort]:hover{color:#2f6fd0}
.dt td{vertical-align:top}
.dt td:nth-child(n+3){font-variant-numeric:tabular-nums}
.sub{font-size:10px;color:var(--sub);font-weight:400}
.num{text-align:right;font-variant-numeric:tabular-nums}
.pill{display:inline-block;color:#fff;border-radius:10px;padding:2px 8px;font-size:11px}
.minibar{height:9px;background:linear-gradient(90deg,#2f6fd0,#7c6bd6);
border-radius:5px;min-width:3px}
a{color:#2f6fd0;text-decoration:none}a:hover{text-decoration:underline}
"""
    html = html.replace("</style>", EXTRA_CSS + "</style>", 1)

    repl = {
        "__EXTRA_CARDS__": extra_cards,
        "__NDAYS__": str(len(tl.get("daily", {}))),
        "__NEVENT__": str(len(tl.get("events", [])) + len(tl.get("external_events", []))),
        "__DATE__": d["data_date"], "__OBS__": str(d["observations_total"]),
        "__NSRC__": str(len(d["source_coverage"])), "__FX__": fmt(d["fx_usd_cny"], 1),
        "__NAPI__": str(len(d["api"])), "__NPLAN__": str(len(d["plans"])),
        "__NRIG__": str(len(d["rigs"])), "__OK__": str(counts["confirmed"]),
        "__BAD__": str(counts["conflict"] + counts["stale"] + counts["unverified"]),
        "__UNCOV__": str(counts["uncovered"] + counts["incomparable"]),
        "__SVG1__": p1, "__SVG2__": p2, "__SVG3__": p3, "__SVG4__": p4, "__SVG5__": p5,
        "__CROSS__": cross_rows,
        "__CONF__": "".join(conf_rows) or "<tr><td colspan='6'>本轮无数值冲突</td></tr>",
    }
    for k, v in repl.items():
        html = html.replace(k, v)
    path = os.path.join(OUT, "dashboard.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path, files


# ---------------------------------------------------------------------------
# report / init / audit-plans
# ---------------------------------------------------------------------------

def write_report(d, crosses):
    lines = ["# 大模型三维度成本追踪（API / 套餐 / 本地部署）", "",
             "数据截止 **%s**｜USD→CNY %.1f 仅作可比换算｜观测 %d 条 / 来源 %d 个"
             % (d["data_date"], d["fx_usd_cny"], d["observations_total"], len(d["source_coverage"])),
             "", "## 结论", ""]
    api = sorted([r["output_cny"] for r in d["api"] if r["output_cny"]])
    plans = sorted([p["cny_per_1m"] for p in d["plans"] if p["convertible"] and p["cny_per_1m"]])
    local = [c for c in (local_cost(r, num(r.get("utilization"), 0.3) or 0.3) for r in d["rigs"]) if c]
    lines.append("- API 输出价（换算 CNY）从 **%.2f** 到 **%.2f** 元/百万 token，跨 %.0f 倍。"
                 % (api[0], api[-1], api[-1] / api[0]) if api else "- 无 API 数据")
    if plans:
        lines.append("- 可折算套餐等效 **%.2f–%.2f** 元/百万 token；%d 个套餐因只给百分比/积分公式明确标为不可折算。"
                     % (plans[0], plans[-1], sum(1 for p in d["plans"] if not p["convertible"])))
    if local:
        lines.append("- 本地方案按表中利用率估算 **%.2f–%.2f** 元/百万 token；已有旧设备（硬件成本记 0）显著拉低下限。"
                     % (min(local), min(60, max(local))))
    lines += ["- 准确性：多源一致 **%d** 条，冲突 **%d** 条，过期 **%d** 条，单源待补 **%d** 条。详见 `out/accuracy_report.md`。"
             % (d["counts"]["confirmed"], d["counts"]["conflict"], d["counts"]["stale"],
                d["counts"]["single_source"]), "",
             "## 套餐回本临界（与 API 基准打平的月用量）", ""]
    if crosses:
        for p, inc in crosses:
            lines.append("- %s · %s：约 **%s 百万 token/月**（套餐折合 %.2f 元/百万）"
                         % (p["platform"], p["plan"], format(int(inc), ","), p["cny_per_1m"]))
    else:
        lines.append("- 本轮无可用临界点。")
    lines += ["", "> 临界点 = 月费 ÷（API 单价 − 套餐等效单价），仅在套餐等效单价低于 API 时成立；"
              "且未计入 5 小时 / 周限额、缓存命中率变化、积分当月清零与活动到期。"
              "火山 9.9 元档等极低价来自限时活动且受「每 5 小时 1200 次」硬约束，"
              "数学上的回本点在现实里往往根本用不满，不要直接拿来下单。", "",
             "> 国内 CNY 报价与海外 USD 报价不混比：LiteLLM / AICostBudget / Liutasil501 以 USD 为主，"
              "国内模型主要靠 pricemon 日报与公众号价格日报提供同币种观测，覆盖仍偏薄（见「无交叉观测 / 口径不可比」）。", "",
             "## 三条数据线的追踪口径", "",
             "| 维度 | 主表 | 关键口径字段 | 主要交叉源 |", "|---|---|---|---|",
             "| API | `data/api_prices.csv` | 币种 / 峰谷 / 促销 / 缓存 / first_party vs reseller | LiteLLM、AICostBudget、Liutasil501、pricemon、OpenRouter |",
             "| 套餐 | `data/plans.csv` | 计费单位 / 三档系数 / 窗口 / 限时活动 | llmprice.gitlab.io、模真真 B 站、公众号日报、官方文档 |",
             "| 本地 | `data/local_rigs.csv` | 折旧 / 电价 / tok_s / 利用率 /  quantized 规格 | 什么值得买实测汇总、llm-speed、arguslm 自托管实测 |",
             "", "## 开源方案与别人追踪的对照", "",
             "| 能力 | 现成方案 | 本工具的对应实现 |", "|---|---|---|"]
    for sid, s in d["source_coverage"].items():
        lines.append("| %s | %s（%s） | %s |" %
                     ("/".join(s["covers"]), s["name"], s["kind"],
                      "observations 交叉源" if s["n_obs"] else "仅登记，未取到数据"))
    tl = d.get("timeline", {})
    lines += ["", "## 时间轴、平台价格与任务换算（看板 ⑥～⑫）", "",
              "- 有观测的日期 **%d** 天：%s；每日观测条数见 `chart_activity_timeline.svg`。"
              % (len(tl.get("daily", {})), "、".join(sorted(tl.get("daily", {})))),
              "- 价格折线覆盖 **%d** 个 USD 一手报价模型；已知事件 **%d** 条 + LLMTracker 外部事件 **%d** 条，"
              "在 `price_events.csv` 与看板「调价 / 事件」视图中可按日期排序。"
              % (len(tl.get("series", [])), len(tl.get("events", [])),
                 len(tl.get("external_events", []))),
              "- 看板提供 5 个可排序/筛选/搜索的表格视图、2 张按日期折线图，以及"
              "「1 百万 token / 1 块钱能完成什么」两张任务换算卡片（任务估算见 `task_examples.csv`）。",
              "- 时间轴是观测点而非逐日报价，任务 token 为估算；详见 README「局限」。", "",
             "## 价格史（三个月回溯）", ""]
    hst = d.get("history") or {}
    hs = hst.get("summary") or {}
    if hs.get("n_models"):
        lines += [
            "- 覆盖 **%s → %s**（%d 个价格日期 × %d 个模型 = %d 个价格点），数据在 "
            "`data/price_history.csv`。" % (hs["span_from"], hs["span_to"], hs["n_dates"],
                                            hs["n_models"], hs["n_points"]),
            "- 期间真有调价 **%d** 个模型（涨 %d / 跌 %d），其余 %d 个官方价一次没动；"
            "全盘输出价水位（几何均值）%s → %s 元，变化 **%+.1f%%**。"
            % (hs["n_changed"], hs["n_up"], hs["n_down"],
               hs["n_models"] - hs["n_changed"], fmt(hs["level_from"], 2),
               fmt(hs["level_to"], 2), hs["level_chg"] * 100),
            "- 每个价格点都带 `basis`：official（官网当期实录）%d 个 / event（由已登记调价事件回溯）"
            "%d 个 / carry（窗口内无调价、按现值回溯的推定值）%d 个 / snapshot（每日快照自动落点）%d 个。"
            % (hs["basis_count"].get("official", 0), hs["basis_count"].get("event", 0),
               hs["basis_count"].get("carry", 0), hs["basis_count"].get("snapshot", 0)),
            "- 变动明细：", ""]
        for c in hst.get("changes") or []:
            lines.append("  - %s %s：输出价 %s → %s %s（%+.0f%%）｜%s"
                         % (c["date"], c["display"], fmt(c["from"], 2), fmt(c["to"], 2),
                            c["currency"], c["pct"] * 100, c["note"]))
        lines += ["", "- 每天 `--snapshot` 自动补点：价格变了当场记，未变则每 25 天记一次；"
                  "同一天同一模型只留一行，重跑不会长重复行。", ""]
    else:
        lines += ["- 还没有价格史数据（`data/price_history.csv` 为空）。", ""]

    pano = d.get("panorama") or {}
    ps = pano.get("summary") or {}
    lines += ["## 平台价格库（同一模型的多平台报价）", ""]
    if ps.get("n_platforms"):
        lines += [
            "- 覆盖 **%d 个平台 / %d 个模型 / %d 条报价线 / %d 个价格点**：官方 %d 条、"
            "云厂商 %d 条、第三方托管 %d 条。数据在 `data/platforms.csv` 与 "
            "`data/price_points.csv`。" % (ps["n_platforms"], ps["n_models"], ps["n_lines"],
                                          ps["n_points"], ps["by_kind"].get("official", 0),
                                          ps["by_kind"].get("cloud", 0),
                                          ps["by_kind"].get("aggregator", 0)),
        ]
        if ps.get("spread_max"):
            lines.append("- 同模型换平台的最大价差 **%.1f 倍**（中位 %.1f 倍）。"
                         "只比第三方之间：官方低谷价是另一个商品口径，混进去会把口径差算成渠道差。"
                         % (ps["spread_max"], ps["spread_median"] or 1))
        # 只排「覆盖 ≥3 个模型」的平台：只有 1 个模型的平台，中位数就是它自己，
        # 会被一个滞后的 Claude 报价顶到榜首，看着像捡漏。
        ranked = sorted([p for p in pano["platforms"]
                         if p.get("ratio_median") is not None and p["n_models"] >= 3],
                        key=lambda x: x["ratio_median"])
        if ranked:
            lines.append("- 相对官方最便宜：%s；最贵：%s。" % (
                "、".join("%s（%+.0f%%）" % (p["name"], (p["ratio_median"] - 1) * 100)
                         for p in ranked[:3]),
                "、".join("%s（%+.0f%%）" % (p["name"], (p["ratio_median"] - 1) * 100)
                         for p in ranked[-3:])))
        lines += ["- 读图守则：① 阶梯线，不是斜线 —— 两次观测之间价格不变；"
                  "② 云厂商（Azure / Bedrock / Vertex）跟随官方调价有滞后，"
                  "看到它比官方便宜，先怀疑没跟上，而不是捡到便宜。",
                  "- 同平台快照与一手官方价冲突时以官方为准（快照数据集对调价有滞后，"
                  "Anthropic 的 Claude 仍停在 10 美元）；被跳过的记录数见建库脚本输出。", ""]
    else:
        lines += ["- 还没有平台价格库（先跑 `llmcost_platforms.py`）。", ""]
    lines += ["## 变更日志", ""]
    if d["changes"]:
        for c in d["changes"]:
            lines.append("- %s %s：%s" % (c["type"], c["model"], c["detail"]))
    else:
        lines.append("- 与上一基线无差异（首次运行会建立基线）。")
    lines += ["", "## 使用", "",
              "```bash", "python3 track.py fetch --only aicostbudget,liutasil,llmtracker",
              "python3 track.py all", "python3 track.py audit-plans usage.csv --model glm-5.2",
              "```", "",
              "局限与冲突清单见 `out/accuracy_report.md`；图表见 `out/dashboard.html` 与 `out/*.svg`。", ""]
    text = "\n".join(lines)
    with open(os.path.join(OUT, "tracking_report.md"), "w", encoding="utf-8") as f:
        f.write(text)
    return text


def cmd_init(_args):
    ensure_dirs()
    base = read_csv(os.path.join(DATA, "api_prices.csv"))
    write_csv(os.path.join(SNAP, "api_prices_%s.csv" % TODAY), base, list(base[0].keys()))
    print("基线快照已建立：data/snapshots/api_prices_%s.csv（%d 条 API 记录）" % (TODAY, len(base)))
    return 0


def cmd_fetch(args):
    ensure_dirs()
    only = set(args.only.split(",")) if args.only else None
    print("拉取开源数据源：")
    fetch_sources(only, args.include_heavy, args.timeout)
    return 0


def _prepare():
    ensure_dirs()
    cfg = load_sources()
    obs, loaded, ext = collect_observations()
    d = verify_data(cfg, obs, loaded, ext)
    write_accuracy_report(d)
    return d


def cmd_verify(_args):
    d = _prepare()
    print("核验完成：观测 %d 条；" % d["observations_total"] +
          " / ".join("%s %d" % (STATUS_CN[s], d["counts"][s]) for s in STATUS_ORDER))
    print("报告：out/accuracy_report.md ｜ 变更：out/changelog.md ｜ 数据：out/accuracy.json")
    n_rec = sum(1 for r in d["api"] if r["conflicts"])
    n_hit = sum(len(r["conflicts"]) for r in d["api"])
    if n_rec:
        print("⚠ %d 条记录存在冲突（共 %d 处观测偏差，多为上游版本滞后/口径差异），详见报告。"
              % (n_rec, n_hit))
    return 0


def cmd_chart(_args):
    d = _prepare()
    _, crosses = chart_plan_vs_api(d)
    path, files = chart(d, crosses)
    print("看板：%s" % path)
    for p in files:
        print("  SVG：%s" % os.path.basename(p))
    return 0


def cmd_report(_args):
    d = _prepare()
    _, crosses = chart_plan_vs_api(d)
    write_report(d, crosses)
    print("汇总：out/tracking_report.md")
    return 0


def cmd_diff(_args):
    d = _prepare()
    print("变更 %d 条：" % len(d["changes"]))
    for c in d["changes"]:
        print("  %s %s — %s" % (c["type"], c["model"], c["detail"]))
    return 0


def cmd_all(_args):
    cmd_init(None)
    cmd_verify(None)
    cmd_chart(None)
    cmd_report(None)
    return 0


def cmd_audit_plans(args):
    """复用上一版 credit_audit.py 的 FWL 拟合，把抓包明细反推成套餐三档系数。"""
    sys.path.insert(0, ROOT)
    try:
        import credit_audit as ca
    except ImportError:
        raise SystemExit("缺少 credit_audit.py（上一版折算引擎），请放在同一目录")
    rows, q = ca.load_rows(args.usage, args.plan_credits)
    fit = [r for r in rows if r["fittable"]]
    if args.model:
        fit = [r for r in fit if args.model.lower() in (r["model"] or "").lower()]
    if len(fit) < 8:
        raise SystemExit("可拟合样本 %d 条，至少需要 8 条含 token 明细的记录" % len(fit))
    res = ca.fit_coeffs(fit)
    print("\n=== 套餐三档系数（积分 / 百万 token）===")
    print("  A 未命中输入 = %.2f ｜ C 缓存命中 = %.2f ｜ B 输出 = %.2f ｜ 起步 d = %.5f"
          % (res["A_miss_per_1m"], res["C_hit_per_1m"], res["B_completion_per_1m"],
             res["fixed_per_request"]))
    print("  留出集平均相对误差 %.2f%%" %
          (res["holdout"]["mean_rel_err"] * 100 if res["holdout"] else float("nan")))
    if res["collinear_warning"]:
        print("  ⚠ " + res["collinear_warning"])
    if args.write_back:
        path = os.path.join(DATA, "plans.csv")
        rows_p = read_csv(path)
        hit = False
        for p in rows_p:
            if args.plan.lower() in (p.get("plan") or "").lower():
                p["coeff_A"] = "%.2f" % res["A_miss_per_1m"]
                p["coeff_C"] = "%.2f" % res["C_hit_per_1m"]
                p["coeff_B"] = "%.2f" % res["B_completion_per_1m"]
                p["source_type"] = "official+self_fitted"
                p["verified_at"] = TODAY
                p["note"] = (p.get("note", "") + "；系数由 audit-plans 抓包拟合回写").strip("；")
                hit = True
        if not hit:
            raise SystemExit("没找到套餐：%s" % args.plan)
        write_csv(path, rows_p, list(rows_p[0].keys()))
        print("  已回写 data/plans.csv → %s；重跑 verify/chart 即可生效" % args.plan)
    return 0


def build_parser():
    p = argparse.ArgumentParser(description="API / 套餐 / 本地部署 三维度追踪 + 准确性校验 + 图表",
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=__doc__.split("用法：")[-1])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init", help="建立主表基线快照"); s.set_defaults(func=cmd_init)
    s = sub.add_parser("fetch", help="在线拉取开源价格源（失败自动降级）")
    s.add_argument("--only", help="逗号分隔的 source_id，如 aicostbudget,liutasil,llmtracker")
    s.add_argument("--include-heavy", action="store_true",
                   help="兼容参数；LiteLLM 现经 gzip + 主表精选，默认已包含")
    s.add_argument("--timeout", type=int, default=25)
    s.set_defaults(func=cmd_fetch)
    s = sub.add_parser("verify", help="多源交叉校验 + 调价 diff"); s.set_defaults(func=cmd_verify)
    s = sub.add_parser("chart", help="生成 dashboard.html 与 5 张 SVG"); s.set_defaults(func=cmd_chart)
    s = sub.add_parser("report", help="生成 Markdown 汇总"); s.set_defaults(func=cmd_report)
    s = sub.add_parser("diff", help="只看变更"); s.set_defaults(func=cmd_diff)
    s = sub.add_parser("all", help="init → verify → chart → report"); s.set_defaults(func=cmd_all)
    s = sub.add_parser("audit-plans", help="用上一版折算引擎拟合套餐三档系数")
    s.add_argument("usage", help="抓包/明细 CSV")
    s.add_argument("--model")
    s.add_argument("--plan-credits", type=float, default=None)
    s.add_argument("--plan", default="", help="配合 --write-back 指定要回写的套餐名")
    s.add_argument("--write-back", action="store_true")
    s.set_defaults(func=cmd_audit_plans)
    return p


def main():
    args = build_parser().parse_args()
    sys.exit(args.func(args) or 0)


if __name__ == "__main__":
    main()
