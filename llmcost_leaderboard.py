"""模型天梯榜：把公开榜单收成一张长表，跟价格并到同一个视角里。

为什么要有这张表
----------------
价格表只回答「多少钱」，不回答「值不值」。同一份输出，2.8 元/百万和 108 元/百万
差 38 倍，但 Elo 只差 40 分 —— 这种话必须有榜单数据才说得出口，凭印象写就是编。

两个源，分工不同
--------------
LMArena（HuggingFace: lmarena-ai/leaderboard-dataset）
    真人盲测偏好对战，Elo（Bradley-Terry）评分。取 text / vision / webdev /
    agent / document 五个维度的最新快照。这是「听谁的」。
Vectara 幻觉率榜（GitHub: vectara/hallucination-leaderboard）
    摘要任务的幻觉率、引用准确率、作答率。这是「敢不敢信」。
    直接读 README 里的表格，每次抓都拿最新那版。

产物（13-算价/data/）
--------------------
leaderboard.csv    长表：date,dimension,model,org,license,score,rank,votes,source
hallucination.csv  幻觉率：model,rate,citation,answer,source
lb_meta.json       抓取元信息：源地址、快照日、条数

跑法
----
    python3 llmcost_leaderboard.py            # 抓网络 + 写表（抓不到就保留旧表）
    python3 llmcost_leaderboard.py --report   # 只打印现状，不写文件

网络：huggingface.co 与 raw.githubusercontent.com 在本机不通，
走 hf-mirror.com（HF 官方镜像）与 api.github.com（GitHub 公开 API），
两者都是可直连的，不依赖代理。
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
DEFAULT_ROOT = Path(os.environ.get("LLMCOST_DIR")
                    or (Path.home() / ".pocket-llmcost"))
DATA = DEFAULT_ROOT / "data"

HF_BASE = ("https://hf-mirror.com/datasets/lmarena-ai/leaderboard-dataset"
           "/resolve/main/%s/latest-00000-of-00001.parquet")
HF_DATASET = "lmarena-ai/leaderboard-dataset"
GH_README = "https://api.github.com/repos/vectara/hallucination-leaderboard/readme"

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) llmcost-leaderboard/1.0"}

# 维度 → (文件, 表内 category)。只取这几类，别把 426 个模型 × 20 个细分类全搬回来。
TEXT_CATS = {
    "text": "overall",
    "coding": "coding",
    "chinese": "chinese",
    "creative": "creative_writing",
    "expert": "expert",
}
OTHER = {"vision": ("vision", "overall"), "webdev": ("webdev", "overall"),
         "agent": ("agent", "overall"), "document": ("document", "overall")}

DIM_CN = {"text": "综合", "coding": "代码", "chinese": "中文", "creative": "写作",
          "expert": "专家问答", "vision": "视觉", "webdev": "前端", "agent": "Agent",
          "document": "长文档"}
DIM_ORDER = ["text", "coding", "chinese", "creative", "expert",
             "vision", "webdev", "agent", "document"]


# ---------------------------------------------------------------- 取数

def _get(url: str, timeout: int = 90, accept: str = "") -> bytes:
    """取一个 URL。先按环境代理走，代理不通（本机 64252 对 api.github.com 会 502）
    再退回直连 —— curl 能通而 urllib 不通，就是这层代理的差别。"""
    headers = dict(UA)
    if accept:
        headers["Accept"] = accept
    last: Exception | None = None
    for direct in (False, True):
        opener = (urllib.request.build_opener(urllib.request.ProxyHandler({}))
                  if direct else urllib.request.build_opener())
        try:
            with opener.open(urllib.request.Request(url, headers=headers),
                             timeout=timeout) as r:
                return r.read()
        except Exception as e:                    # noqa: BLE001
            last = e
    raise last  # type: ignore[misc]


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _parquet_rows(raw: bytes) -> list[dict]:
    """parquet → dict 列表。pyarrow 是软依赖：没有就明确报出来，不静默降级。"""
    try:
        import pyarrow.parquet as pq           # noqa: PLC0415
    except ImportError:
        raise SystemExit("缺 pyarrow：pip3 install pyarrow（只为读 HF 的 parquet）")
    return pq.read_table(io.BytesIO(raw)).to_pylist()


def fetch_lmarena(verbose: bool = True) -> list[dict]:
    """抓 LMArena 五个维度的最新快照，只留 TEXT_CATS + OTHER 里点名的分类。"""
    rows: list[dict] = []
    for dim, cat in TEXT_CATS.items():
        raw = _get(HF_BASE % "text")
        for r in _parquet_rows(raw):
            if r.get("category") != cat:
                continue
            rows.append({"date": r.get("leaderboard_publish_date"), "dimension": dim,
                         "model": r.get("model_name"), "org": r.get("organization") or "",
                         "license": r.get("license") or "",
                         "score": r.get("rating"), "rank": r.get("rank"),
                         "votes": r.get("vote_count"), "source": "LMArena"})
        if verbose:
            print("  text/%-12s %d 行" % (cat, sum(1 for x in rows if x["dimension"] == dim)))
    for dim, (f, cat) in OTHER.items():
        raw = _get(HF_BASE % f)
        n0 = len(rows)
        for r in _parquet_rows(raw):
            if r.get("category") != cat:
                continue
            rows.append({"date": r.get("leaderboard_publish_date"), "dimension": dim,
                         "model": r.get("model_name"), "org": r.get("organization") or "",
                         "license": r.get("license") or "",
                         "score": r.get("rating") or r.get("score"),
                         "rank": r.get("rank"),
                         "votes": r.get("vote_count") or r.get("observation_count"),
                         "source": "LMArena"})
        if verbose:
            print("  %-17s %d 行" % (f + "/" + cat, len(rows) - n0))
    return rows


def fetch_hallucination(verbose: bool = True) -> list[dict]:
    """Vectara 幻觉率榜：README 里的 markdown 表格。

    表头是 |Model|Hallucination Rate|Factual Consistency Rate|Answer Rate|Avg Summary Length|，
    单位带 %，长度带词数 —— 解析时只认「数字 + %」的行，别把说明段落吃进来。
    """
    txt = _get(GH_README, accept="application/vnd.github.raw").decode("utf-8", "replace")
    out = []
    for ln in txt.splitlines():
        ln = ln.strip()
        if not ln.startswith("|") or "%" not in ln:
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if len(cells) < 4 or not cells[0] or cells[0].lower().startswith("model"):
            continue
        nums = []
        for c in cells[1:4]:
            m = re.match(r"^([\d.]+)\s*%", c)
            nums.append(float(m.group(1)) if m else None)
        if nums[0] is None:
            continue
        out.append({"model": cells[0], "rate": nums[0], "citation": nums[1],
                    "answer": nums[2], "source": "Vectara"})
    if verbose:
        print("  hallucination   %d 行" % len(out))
    return out


# ---------------------------------------------------------------- 写表

LB_COLS = ["date", "dimension", "model", "org", "license", "score", "rank", "votes", "source"]
HL_COLS = ["model", "rate", "citation", "answer", "source"]


def build(write: bool = True, verbose: bool = True) -> dict:
    if verbose:
        print("抓 LMArena（hf-mirror）…")
    lb = fetch_lmarena(verbose)
    if verbose:
        print("抓 Vectara 幻觉率榜（api.github.com）…")
    try:
        hl = fetch_hallucination(verbose)
    except Exception as e:                       # 幻觉率是加分项，抓不到不拖垮榜单
        print("  ! 幻觉率榜抓取失败：%s（保留旧表）" % e)
        hl = []
    meta = {"fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "hf_dataset": HF_DATASET, "gh_repo": "vectara/hallucination-leaderboard",
            "n_rows": len(lb), "n_halluc": len(hl),
            "dates": sorted({str(r["date"]) for r in lb if r.get("date")})[-3:]}
    if write:
        DATA.mkdir(parents=True, exist_ok=True)
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=LB_COLS)
        w.writeheader()
        for r in sorted(lb, key=lambda x: (DIM_ORDER.index(x["dimension"]),
                                           x["rank"] or 9999)):
            w.writerow({k: r.get(k) for k in LB_COLS})
        _atomic_write(DATA / "leaderboard.csv", buf.getvalue().encode("utf-8"))
        if hl:
            buf = io.StringIO()
            w = csv.DictWriter(buf, fieldnames=HL_COLS)
            w.writeheader()
            for r in sorted(hl, key=lambda x: x["rate"]):
                w.writerow({k: r.get(k) for k in HL_COLS})
            _atomic_write(DATA / "hallucination.csv", buf.getvalue().encode("utf-8"))
        _atomic_write(DATA / "lb_meta.json",
                      json.dumps(meta, ensure_ascii=False, indent=1).encode("utf-8"))
        if verbose:
            print("写出 leaderboard.csv（%d 行）/ hallucination.csv（%d 行）" % (len(lb), len(hl)))
    return meta


# ---------------------------------------------------------------- 读表 + 匹配

def load() -> tuple[list[dict], list[dict], dict]:
    def rd(name):
        p = DATA / name
        if not p.exists():
            return []
        with p.open(encoding="utf-8") as f:
            return list(csv.DictReader(f))
    meta = {}
    mp = DATA / "lb_meta.json"
    if mp.exists():
        try:
            meta = json.loads(mp.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    return rd("leaderboard.csv"), rd("hallucination.csv"), meta


def _norm(s: str) -> str:
    """型号归一：去括号档位、去日期尾巴、去分隔符、转小写。

    "DeepSeek-V4.1-Flash-20260910 (Max)" → "deepseekv4.1flash"
    "Claude Sonnet 5 (High)"             → "claudesonnet5"
    """
    s = str(s or "")
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[-_ ]*(20\d{6})$", " ", s.strip())
    # 点号也去掉：价格表写 "deepseek-v4-1-flash"，榜单写 "DeepSeek-V4.1-Flash"，
    # 两种写法必须归一到同一个 key，否则幻觉率那条永远匹配不上。
    s = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", s)
    return s.lower()


def _tier(s: str) -> str:
    m = re.search(r"\(([^)]*)\)", str(s or ""))
    return m.group(1) if m else ""


def index(rows: list[dict]) -> dict:
    """把长表折成 {dimension: {norm_name: [entry...]}}。同名多档位（High/Max）都留着。"""
    idx: dict[str, dict[str, list]] = {}
    for r in rows:
        try:
            score = float(r["score"])
        except (TypeError, ValueError):
            continue
        e = {"model": r["model"], "org": r.get("org") or "", "score": score,
             "rank": int(float(r["rank"])) if r.get("rank") not in (None, "") else None,
             "votes": int(float(r["votes"])) if r.get("votes") not in (None, "") else 0,
             "tier": _tier(r["model"]), "date": r.get("date") or ""}
        idx.setdefault(r["dimension"], {}).setdefault(_norm(r["model"]), []).append(e)
    for dim in idx:
        for k in idx[dim]:
            idx[dim][k].sort(key=lambda x: -x["score"])
    return idx


def _is_cjk(s: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in str(s))


def match(name: str, idx_dim: dict) -> tuple[dict | None, str]:
    """价格表里的型号 → 榜单里的型号。

    先精确归一匹配；不中再退一步做「同门」匹配（前缀命中、且长度差不超过 4 个字符，
    避免 "GLM-5" 把 "GLM-5.3" 抢走）。仍然没有就老实返回 None，让界面上显「未上榜」。
    中文名（豆包 / 混元）与外文榜单对不上，不做音译猜谜。
    """
    n = _norm(name)
    if not n:
        return None, "empty"
    if n in idx_dim:
        return idx_dim[n][0], "exact"
    if _is_cjk(name):
        return None, "cjk"
    for k, entries in idx_dim.items():
        if not k:
            continue
        if abs(len(k) - len(n)) <= 4 and (k.startswith(n) or n.startswith(k)):
            return entries[0], "family"
    return None, "none"


def join_prices(api_rows: list[dict]) -> dict:
    """价格表的每一行去榜单里找位置，顺带算「贵不贵 × 强不强」的象限。"""
    rows, hl_rows, meta = load()
    if not rows:
        return {"ready": False}
    idx = index(rows)
    halluc = {}
    for h in hl_rows:
        try:
            rec_h = {"rate": float(h["rate"]),
                     "citation": float(h["citation"] or 0),
                     "answer": float(h["answer"] or 0),
                     "model": h["model"]}
        except (TypeError, ValueError):
            continue
        # 两个 key 都登记：全路径（openai/gpt-6-sol）和裸型号（gpt-6-sol）
        for key in {_norm(h["model"]), _norm(str(h["model"]).split("/")[-1])}:
            halluc.setdefault(key, rec_h)

    out = []
    for r in api_rows:
        price = r.get("output_cny")
        if not price:
            continue
        rec = {"model": r.get("model"), "display": r.get("display"),
               "provider": r.get("provider"), "price": round(float(price), 3),
               "dims": {}, "arena": None, "rank": None, "score": None,
               "tier": "", "votes": 0, "halluc": None, "match": "none"}
        per_dim_score = {}
        for dim in DIM_ORDER:
            m, kind = match(r.get("display") or r.get("model"), idx.get(dim, {}))
            if m:
                per_dim_score[dim] = m
                rec["dims"][dim] = {"name": m["model"], "score": round(m["score"], 1),
                                    "rank": m["rank"], "tier": m["tier"],
                                    "unit": "winrate" if dim == "agent" else "elo"}
                if kind == "exact" and rec["match"] != "exact":
                    rec["match"] = "exact"
                elif kind == "family" and rec["match"] == "none":
                    rec["match"] = "family"
        main = per_dim_score.get("text")
        if main:
            rec.update({"arena": main["model"], "rank": main["rank"],
                        "score": round(main["score"], 1), "tier": main["tier"],
                        "votes": main["votes"]})
        # 幻觉率榜是 "厂商/型号" 全路径，价格表只有型号：按去掉前缀的名字再试一次
        cand = [r.get("model"), r.get("display")]
        hm = None
        for c in cand:
            if not c:
                continue
            hm = (halluc.get(_norm(c))
                  or halluc.get(_norm(str(c).split("/")[-1])))
            if hm:
                break
        if hm:
            rec["halluc"] = {"rate": hm["rate"], "citation": hm["citation"],
                             "answer": hm["answer"], "model": hm["model"]}
        out.append(rec)

    # 「值不值」不做复合指数（加权权重怎么定都是编的），用支配关系：
    # A 支配 B = A 不比 B 贵且分不比 B 低。没人支配的点才是可选方案（Pareto 前沿）。
    sc = [x for x in out if x["score"]]
    for x in out:
        x["pareto"] = False
        x["dominated_by"] = None
    for x in sc:
        for y in sc:
            if x is y:
                continue
            if y["price"] <= x["price"] * 1.001 and y["score"] >= x["score"] - 0.05:
                if (y["price"] < x["price"] * 0.999 or y["score"] > x["score"] + 0.05):
                    x["dominated_by"] = y["display"]
                    break
        else:
            x["pareto"] = True
    frontier = sorted([x for x in sc if x["pareto"]], key=lambda x: x["price"])
    for x in frontier:
        x["pareto"] = True

    if sc:
        top = max(sc, key=lambda x: x["score"])
        priciest = max(sc, key=lambda x: x["price"])
        cheapest = min(sc, key=lambda x: x["price"])
        best = min(frontier, key=lambda x: x["price"]) if frontier else cheapest
    else:
        top = priciest = cheapest = best = None

    top_board = []
    seen = set()
    for e in (idx.get("text", {}) or {}).values():
        if e and e[0]["model"] not in seen:
            seen.add(e[0]["model"])
            top_board.append(e[0])
    top_board.sort(key=lambda x: x["rank"] or 9999)

    return {
        "ready": True,
        "meta": {
            "fetched_at": meta.get("fetched_at") or "",
            "hf_dataset": meta.get("hf_dataset") or HF_DATASET,
            "gh_repo": meta.get("gh_repo") or "vectara/hallucination-leaderboard",
            "date": max((r.get("date") or "" for r in rows), default=""),
            "dates": meta.get("dates") or [],
            "n_models": len(seen), "n_rows": len(rows), "n_halluc": len(halluc),
        },
        "dims": [{"k": k, "label": DIM_CN[k]} for k in DIM_ORDER],
        "top": [{"rank": x["rank"], "model": x["model"], "org": x["org"],
                 "score": round(x["score"], 1), "votes": x["votes"]} for x in top_board[:20]],
        "rows": out,
        "summary": {
            "n_matched": len(sc), "n_total": len(out),
            "frontier": [{"display": x["display"], "price": x["price"],
                          "score": x["score"], "rank": x["rank"]} for x in frontier],
            "n_dominated": sum(1 for x in sc if not x["pareto"]),
            "best_value": ({"display": best["display"], "price": best["price"],
                            "score": best["score"], "rank": best["rank"]} if best else None),
            "strongest": ({"display": top["display"], "price": top["price"],
                           "score": top["score"], "rank": top["rank"]} if top else None),
            "priciest": ({"display": priciest["display"], "price": priciest["price"],
                          "score": priciest["score"],
                          "dominated_by": priciest["dominated_by"]} if priciest else None),
            "cheapest": ({"display": cheapest["display"], "price": cheapest["price"],
                          "score": cheapest["score"]} if cheapest else None),
        },
    }


def main(argv: list[str]) -> int:
    if "--report" in argv or "--dry-run" in argv:
        rows, hl, meta = load()
        print("榜单：%d 行" % len(rows))
        if meta:
            print("  抓取时间 %s | 快照日 %s | HF %s"
                  % (meta.get("fetched_at"), meta.get("dates"), meta.get("hf_dataset")))
        for dim in DIM_ORDER:
            n = sum(1 for r in rows if r["dimension"] == dim)
            if n:
                print("  %-9s %3d 个型号" % (dim, n))
        print("幻觉率：%d 行" % len(hl))
        return 0
    build(write=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
