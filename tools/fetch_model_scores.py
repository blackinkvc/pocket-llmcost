#!/usr/bin/env python3
"""抓基模的能力分：只收有公开出处、能复核的分数。

来源是 OpenRouter 的公开 models 接口，它把两条来源聚合进了 benchmarks：
  · artificial_analysis.intelligence_index —— Artificial Analysis 的综合智能指数
  · design_arena[].elo / rank             —— LMArena 设计竞技场（按类目）

为什么不用厂商自测的 SWE-bench / GPQA：口径不一、样本不公开，横向排会把人带偏。
这里宁可榜短，也不把不同口径的数字塞进同一列。

输出：
  content/基模/榜/能力分.csv       —— AA 指数前 N（页面默认显示 / 无 JS 时显示）
  content/基模/data/scores.json    —— 全量：AA 各子指数 + LMArena 各类目 Elo
"""
import argparse
import csv
import datetime as dt
import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
SEC = ROOT / "content" / "基模"
BOARD_DIR = SEC / "榜"
DATA_DIR = SEC / "data"

API = "https://openrouter.ai/api/v1/models"
UA = "Mozilla/5.0 (compatible; AITrack/1.0)"
TOP_N = 20

# 子指数 → 页面上叫法。只放真的有数的，空的留着也没用
SUB = [
    ("intelligence_index", "综合"),
    ("engineering_index", "工程"),
    ("cyber_index", "安全"),
    ("finance_and_accounting_index", "财税"),
    ("legal_index", "法律"),
    ("healthcare_and_medical_index", "医疗"),
    ("economics_index", "经济"),
    ("strategy_and_ops_index", "战略"),
    ("multilingual_index", "多语"),
]

CAT = [
    ("website", "网站"),
    ("codecategories", "代码"),
    ("uicomponent", "UI 组件"),
    ("dataviz", "数据可视化"),
    ("gamedev", "游戏"),
    ("3d", "3D"),
    ("svg", "SVG"),
    ("asciiart", "ASCII"),
]

VENDOR = [
    ("anthropic", "Anthropic"), ("openai", "OpenAI"), ("google", "Google"),
    ("meta", "Meta"), ("meta-llama", "Meta"), ("qwen", "阿里"), ("deepseek", "DeepSeek"),
    ("moonshotai", "月之暗面"), ("z-ai", "智谱"), ("minimax", "MiniMax"),
    ("x-ai", "xAI"), ("mistralai", "Mistral"), ("nvidia", "NVIDIA"),
    ("amazon", "Amazon"), ("microsoft", "微软"), ("cohere", "Cohere"),
    ("baidu", "百度"), ("bytedance", "字节"), ("tencent", "腾讯"),
    ("01-ai", "零一万物"), ("inclusionai", "蚂蚁"), ("stepfun", "阶跃"),
    ("sensetime", "商汤"), ("thinkingmachines", "Thinking Machines"),
]


def get(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def vendor_of(mid):
    head = mid.split("/", 1)[0].lower()
    for k, v in VENDOR:
        if head == k:
            return v
    return head


def clean_name(name):
    """'Anthropic: Claude Fable 5.2' → ('Claude Fable 5.2', 'Anthropic')"""
    if ":" in name:
        pre, post = name.split(":", 1)
        return post.strip(), pre.strip()
    return name.strip(), ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只打印，不写文件")
    args = ap.parse_args()

    now = dt.datetime.now().replace(microsecond=0)
    when = now.isoformat()
    day = when[:10]

    try:
        d = get(API)
    except Exception as exc:                                   # noqa: BLE001
        print("抓 OpenRouter 失败：%s" % exc, file=sys.stderr)
        return 1

    models = {}
    for m in d.get("data") or []:
        mid = m.get("id") or ""
        if not mid or mid.endswith(":batch"):                  # 批量版同分，重复
            continue
        b = m.get("benchmarks") or {}
        aa = b.get("artificial_analysis") or {}
        arena = b.get("design_arena") or []
        if not aa and not arena:
            continue
        name, _ = clean_name(m.get("name") or mid)
        models[mid] = {
            "id": mid,
            "name": name,
            "vendor": vendor_of(mid),
            "aa": {k: aa.get(k) for k, _ in SUB if aa.get(k) is not None},
            "arena": {a.get("category"): {"elo": a.get("elo"), "rank": a.get("rank"),
                                          "win": a.get("win_rate")}
                      for a in arena if a.get("category")},
            "ctx": m.get("context_length"),
            "price_in": (m.get("pricing") or {}).get("prompt"),
            "price_out": (m.get("pricing") or {}).get("completion"),
        }

    # 主榜：AA 综合指数
    ranked = [(v["aa"]["intelligence_index"], k) for k, v in models.items()
              if v["aa"].get("intelligence_index") is not None]
    ranked.sort(key=lambda x: -x[0])
    print("模型总数 %d，AA 综合分 %d 条，LMArena %d 条"
          % (len(models), len(ranked), sum(1 for v in models.values() if v["arena"])))

    if args.check:
        for i, (sc, mid) in enumerate(ranked[:TOP_N], 1):
            print("%2d. %-46s %5.1f  %s" % (i, models[mid]["name"][:44], sc, models[mid]["vendor"]))
        return 0

    for d_ in (BOARD_DIR, DATA_DIR):
        if not d_.exists():
            d_.mkdir(parents=True, exist_ok=True)

    # CSV：只写主榜，给无 JS 的降级显示
    cols = ["排名", "名称", "机构", "分数", "来源", "时间"]
    rows = []
    for i, (sc, mid) in enumerate(ranked[:TOP_N], 1):
        v = models[mid]
        rows.append({"排名": i, "名称": v["name"], "机构": v["vendor"],
                     "分数": sc, "来源": "Artificial Analysis", "时间": day})
    with (BOARD_DIR / "能力分.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print("  ✓ content/基模/榜/能力分.csv（%d 行）" % len(rows))

    payload = {
        "generated_at": when,
        "source": "OpenRouter / Artificial Analysis / LMArena",
        "sub": [{"key": k, "label": lbl} for k, lbl in SUB],
        "cats": [{"key": k, "label": lbl} for k, lbl in CAT],
        "models": models,
    }
    (DATA_DIR / "scores.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print("  ✓ content/基模/data/scores.json（%d 个模型）" % len(models))
    return 0


if __name__ == "__main__":
    sys.exit(main())
