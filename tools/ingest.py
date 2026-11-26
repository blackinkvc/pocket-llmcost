#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「资料库型」HTML 拆开，按栏目归进各板块的报告里。

资料库 HTML 的特征：页面里有一个 `const DATA = {...}`，里面是

    sections  栏目表（id / name / parent）
    topics    知识点（id / section / title / tags / points / sources / note）
    articles  原文清单（id / title / url / date / section / summary）
    tools     工具台账（id / cats / name / func / review / source）

本脚本不做「另一个资料库页面」，只做三件事：

    1. 每个知识点 → content/<板块>/报告/<标题>.md（frontmatter 与全站报告一致）
    2. 每个板块的工具 → 一篇「工具台账」报告（按主分类只进一个板块，不重复挂）
    3. 记台账 content/_inbox/ledger.json：哪个源文件的哪条写进了哪个文件、内容哈希是多少

以后补了新的同类 HTML，丢进 content/_inbox/ 再跑一次即可；已经写过的条目按台账
原地更新，人工改过的（哈希对不上）默认跳过、不覆盖。

用法：
    python3 tools/ingest.py content/_inbox/xxx.html            # 入库
    python3 tools/ingest.py content/_inbox/xxx.html --dry      # 只看打算怎么做
    python3 tools/ingest.py --status                           # 看台账里已入的源
"""

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import datetime as dt

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
CONTENT = ROOT / "content"
INBOX = CONTENT / "_inbox"
LEDGER_PATH = INBOX / "ledger.json"

# ───────────────────────── 栏目 → 板块 ─────────────────────────
# 左：资料库里的 section.id；右：content/ 下的板块文件夹。
# 资料库有 17 个栏目，站点只有 9 个板块，所以是多对一；**不新建页面**。
# 以后新资料出现没见过的栏目，跑到这里加一行就行；没登记的会被列进「未映射」。
SITE_MAP = {
    "model":    "基模",      # 架构 / 训练 / 评测 / 开源生态
    "agent":    "agent",     # 规划、工具调用、长程任务
    "skill":    "agent",     # 技能封装本来就是 Agent 生态的一层
    "mcp":      "agent",     # 协议层，Agent 页已有 MCP 榜
    "memory":   "agent",     # 记忆是 Agent 的状态管理
    "hardware": "硬件",      # 算力 / 显存 / 机房
    "infra":    "公司",      # 产业与公司图谱，公司页正缺这类内容
    "rag":      "原理",      # 检索链路的机制
    "roadmap":  "原理",      # 学习路线 = 机制的前置阅读
    "template": "模板",      # 可直接复用的素材
    "kb":       "应用",      # 企业落地 / 选型成本
    "case":     "应用",      # 落地案例
    "cad":      "应用",
    "web3d":    "应用",
    "game":     "应用",
    "ai4s":     "应用",
}

# 明确不入站的内容（资料库自己的账，不是知识）
SKIP_NOTE = "gaps / templates / events / boards 是资料库自己的缺口清单、模板库、事件页与榜单说明，属库内账目，没有对应板块，不入站。"

INGEST_TAG = "资料入库"   # 所有入库报告的公共标签，页面上可一键筛出来


# ───────────────────────── 小工具 ─────────────────────────
def sha1(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def read(p):
    return p.read_text(encoding="utf-8")


def one_line(s, n=None):
    s = re.sub(r"\s+", " ", (s or "")).strip()
    if n and len(s) > n:
        cut = s[:n]
        # 断在标点或空格上，别把词切一半
        for sep in ("。", "；", "，", " ", "、"):
            k = cut.rfind(sep)
            if k > n * 0.6:
                return cut[:k + 1].rstrip("，、 ")
        return cut + "…"
    return s


def slugify(title, taken):
    """标题 → 文件名。中文保留，只清掉 URL 里有歧义的符号。"""
    s = title.strip()
    s = re.sub(r"[\\/:*?\"<>|#%]+", "·", s)
    s = re.sub(r"·{2,}", "·", s)
    s = s.strip(" ·.")
    s = re.sub(r"\s+", " ", s)
    if len(s) > 48:
        cut = s[:48]
        # 断在标点上，别把标题切半截；找不到合适的标点才硬截
        for sep in ("：", "·", "—", " ", "，", "、", "｜"):
            k = cut.rfind(sep)
            if k > 28:
                cut = cut[:k]
                break
        s = cut.rstrip(" ·—，、｜")
    base, n = s, 2
    while s in taken:
        s = "%s（%d）" % (base, n)
        n += 1
    taken.add(s)
    return s


# ───────────────────────── 解析源文件 ─────────────────────────
NODE_EXTRACT = r'''
const fs = require("fs");
const s = fs.readFileSync(process.argv[1], "utf8");
const start = s.indexOf("const DATA");
if (start < 0) { console.error("没找到 const DATA"); process.exit(2); }
let j = s.indexOf("{", start), depth = 0, q = null, esc = false, out = null;
for (let k = j; k < s.length; k++) {
  const c = s[k];
  if (q) {
    if (esc) esc = false;
    else if (c === "\\") esc = true;
    else if (c === q) q = null;
    continue;
  }
  if (c === '"' || c === "'" || c === "`") { q = c; continue; }
  if (c === "{") depth++;
  else if (c === "}") { depth--; if (depth === 0) { out = s.slice(j, k + 1); break; } }
}
if (!out) { console.error("DATA 括号没闭合"); process.exit(3); }
const DATA = eval("(" + out + ")");
process.stdout.write(JSON.stringify(DATA));
'''


def extract_data(path):
    try:
        r = subprocess.run(["node", "-e", NODE_EXTRACT, str(path)],
                           capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        sys.exit("需要 node 来解析资料库 HTML（页面里的 DATA 是 JS 对象字面量）。")
    if r.returncode != 0:
        sys.exit("解析失败：%s" % (r.stderr.strip() or r.returncode))
    return json.loads(r.stdout)


# ───────────────────────── 台账 ─────────────────────────
def load_ledger():
    if LEDGER_PATH.exists():
        try:
            return json.loads(read(LEDGER_PATH))
        except json.JSONDecodeError:
            print("! ledger.json 坏了，按空台账继续（不会覆盖旧文件，只是认不出）")
    return {"sources": {}, "items": {}}


def save_ledger(led):
    INBOX.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(led, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                           encoding="utf-8")


# ───────────────────────── 正文拼装 ─────────────────────────
def render_points(points, linkify, skip=None):
    blocks = []
    for p in points or []:
        if isinstance(p, str):
            if skip is not None and p is skip:
                continue
            blocks.append(linkify(p.strip()))
        elif isinstance(p, dict) and p.get("list"):
            items = ["- " + linkify(str(x).strip()) for x in p["list"] if str(x).strip()]
            if items:
                blocks.append("\n".join(items))
    return "\n\n".join(blocks)


def source_block(arts):
    if not arts:
        return ""
    lines = ["## 来源", ""]
    for a in arts:
        head = "- %s《%s》" % (a["id"], one_line(a.get("title", "")))
        if a.get("date"):
            head += " · " + a["date"]
        if a.get("url"):
            head += " · " + a["url"]
        lines.append(head)
    return "\n".join(lines)


def report_md(topic, arts, linkify):
    # 摘要取第一条够长的正文段；同一段不再在正文里重复一遍
    # 摘要取第一条像「正文」的段落：跳过一开头就在交代资料形态 / 来源 / 口径的元信息句，
    # 那些留在正文里，别让卡片第一行读起来像登记表
    meta_lead = ("资料形态", "资料类型", "资料来源", "来源", "原文", "口径", "本篇", "本卡", "以下为")
    lead, summary = None, ""
    for cand in [x for x in (topic.get("points") or []) if isinstance(x, str)]:
        if len(cand.strip()) > 30 and not cand.strip().startswith(meta_lead):
            lead = cand
            summary = one_line(cand, 110)
            break
    if lead is None:
        for cand in [x for x in (topic.get("points") or []) if isinstance(x, str)]:
            if len(cand.strip()) > 20:
                lead = cand
                summary = one_line(cand, 110)
                break
    body = [render_points(topic.get("points"), linkify, skip=lead)]
    note = (topic.get("note") or "").strip()
    if note:
        body.append("> 整理说明：" + linkify(note))
    sb = source_block(arts)
    if sb:
        body.append(sb)
    body = [b for b in body if b]
    tags = []
    for t in (topic.get("tags") or []):
        t = str(t).strip()
        if t and t not in tags:
            tags.append(t)
    tags = tags[:4]
    if INGEST_TAG not in tags:
        tags.append(INGEST_TAG)
    date = min([a["date"] for a in arts if a.get("date")] or ["2026-01-01"])
    fm = [
        "---",
        "title: %s" % one_line(topic.get("title", "")),
        "date: %s" % date,
        "summary: %s" % summary,
        "tags: %s" % ", ".join(tags),
        "---",
        "",
    ]
    return "\n".join(fm) + "\n\n".join(body).strip() + "\n"


def tools_md(rows, site_name, date, span=""):
    def brief(v, n=42):
        v = one_line(v, n)
        if not v or v.startswith("原文未注明") or v.startswith("不适用"):
            return ""
        return v

    lines = [
        "---",
        "title: 工具台账 · %s（%d 件）" % (site_name, len(rows)),
        "date: %s" % date,
        "summary: 资料入库时归到「%s」的 %d 个条目：工具、基准、框架、组件都算，"
                   "记名称、功能、开源情况与原文点评。只进一个板块（按资料里的分类首项），不排名。"
                   % (site_name, len(rows)),
        "tags: 工具, %s" % INGEST_TAG,
        "---",
        "",
        "台账收的是原文里被点名、值得单独记一笔的东西——工具、基准、框架、组件都算。"
        "按资料原文照录：**作者 / 平台 / 开源没写出来的，就是原文没给，不替它猜**；"
        "功能与点评都是原文一句话，没有二次评价。想按主题看这些工具各自解决什么问题，"
        "翻本页其它带「%s」标签的报告。" % INGEST_TAG + (span and " " + span or ""),
        "",
    ]
    for t in rows:
        lines.append("### " + one_line(t.get("name", ""), 60))
        lines.append("")
        func = one_line(t.get("func", ""), 90)
        if func:
            lines.append(func)
            lines.append("")
        meta = []
        for k, label in (("author", "作者"), ("platform", "平台"), ("open", "开源")):
            v = brief(t.get(k, ""))
            if v:
                meta.append("%s：%s" % (label, v))
        if meta:
            lines.append("— " + " · ".join(meta))
            lines.append("")
        review = one_line(t.get("review", ""), 160)
        if review:
            lines.append("> " + review)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# ───────────────────────── 主流程 ─────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="资料库 HTML 路径")
    ap.add_argument("--dry", action="store_true", help="只打印计划，不写文件")
    ap.add_argument("--force", action="store_true", help="人工改过的也覆盖")
    ap.add_argument("--no-tools", action="store_true", help="不生成工具台账")
    ap.add_argument("--status", action="store_true", help="只看台账")
    args = ap.parse_args()

    led = load_ledger()
    if args.status:
        if not led["sources"]:
            print("台账是空的。")
        for name, s in sorted(led["sources"].items()):
            print("%-28s %s 收 %s 条 / 工具 %s 件 / 原文 %s 篇  → %s" % (
                name, s.get("at", "")[:10], s.get("topics", 0), s.get("tools", 0),
                s.get("articles", 0), ", ".join("%s:%d" % (k, v) for k, v in s.get("sections", {}).items())))
        return

    if not args.files:
        ap.error("给一个资料库 HTML；或 --status 看台账")

    for f in args.files:
        p = pathlib.Path(f)
        if not p.exists():
            sys.exit("没有这个文件：%s" % p)
        ingest(p, led, args)

    if not args.dry:
        save_ledger(led)
        print("\n台账已更新：content/_inbox/ledger.json")
        print("接下来跑：python3 tools/build_section.py  （重建成页面）")


def ingest(path, led, args):
    data = extract_data(path)
    src = path.name
    sections = {s["id"]: s for s in data.get("sections") or []}
    articles = {a["id"]: a for a in data.get("articles") or []}
    topics = data.get("topics") or []
    tools = data.get("tools") or []

    print("\n源：%s" % src)
    print("  %d 个栏目 / %d 条知识点 / %d 篇原文 / %d 件工具" % (
        len(sections), len(topics), len(articles), len(tools)))

    # 先算出每条的落点（板块 + 文件名 + URL），正文里的 T### / A### 才能互相链上
    taken = {}
    plan = []
    for t in sorted(topics, key=lambda x: x.get("id", "")):
        site = SITE_MAP.get(t.get("section"))
        if not site:
            plan.append({"t": t, "site": None})
            continue
        plan.append({"t": t, "site": site, "dir": CONTENT / site / "报告"})

    # 文件名要在「该板块已有的名字」之上排重
    for site in {x["site"] for x in plan if x["site"]}:
        names = set()
        rdir = CONTENT / site / "报告"
        if rdir.exists():
            names |= {p.stem for p in rdir.glob("*.md")}
        taken[site] = names

    url_of = {}
    for x in plan:
        if not x["site"]:
            continue
        x["slug"] = slugify(x["t"].get("title", x["t"]["id"]), taken[x["site"]])
        url_of[x["t"]["id"]] = (x["site"], x["slug"])
    # 排重时把「本轮已占用」算进去，但已有的 md 若属于台账管理的条目，同一标题
    # 会被加个（2）—— 靠台账里的 path 兜住：命中台账就沿用原文件名。
    for x in plan:
        if not x["site"]:
            continue
        rec = led["items"].get("%s#%s" % (src, x["t"]["id"]))
        if rec and rec.get("path"):
            x["slug"] = pathlib.Path(rec["path"]).stem
            url_of[x["t"]["id"]] = (x["site"], x["slug"])

    def linkify(text):
        def t_sub(m):
            tid = m.group(0)
            if tid not in url_of:
                return tid
            site, slug = url_of[tid]
            return "[%s](../%s/%s.html)" % (tid, folder_slug(site), quote_zh(slug))
        def a_sub(m):
            aid = m.group(0)
            a = articles.get(aid)
            if not a or not a.get("url"):
                return aid
            return "[%s](%s)" % (aid, a["url"])
        text = re.sub(r"\bT\d{3}\b", t_sub, text)
        text = re.sub(r"\bA\d{3}\b", a_sub, text)
        return text

    stats = {"new": 0, "update": 0, "same": 0, "skip": 0, "dup": 0}
    skipped = []
    for x in plan:
        t = x["t"]
        if not x["site"]:
            stats["skip"] += 1
            skipped.append("%s 栏目未映射（%s）" % (t["id"], t.get("section")))
            continue
        arts = [articles[s] for s in (t.get("sources") or []) if s in articles]
        md = report_md(t, arts, linkify)
        out = x["dir"] / (x["slug"] + ".md")
        key = "%s#%s" % (src, t["id"])
        rec = led["items"].get(key)
        h = sha1(md)

        action = "new"
        if out.exists():
            cur = sha1(read(out))
            if rec is None:
                # 同名文件不是台账写的：不去碰它
                stats["dup"] += 1
                skipped.append("%s 已有同名报告 %s/%s.md（非本工具写入，跳过）"
                               % (t["id"], x["site"], x["slug"]))
                continue
            if cur == rec.get("hash"):
                action = "same" if cur == h else "update"
            else:
                if not args.force:
                    stats["skip"] += 1
                    skipped.append("%s 本地改过 %s/%s.md（不动，要覆盖加 --force）"
                                   % (t["id"], x["site"], x["slug"]))
                    continue
                action = "update"
        stats[action] += 1

        if not args.dry:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(md, encoding="utf-8")
            led["items"][key] = {"section": x["site"], "path": str(out.relative_to(ROOT)),
                                 "hash": h, "title": one_line(t.get("title", ""))}
        if action == "new" and stats["new"] <= 3:
            print("   · %s → %s/%s.md" % (t["id"], x["site"], x["slug"]))

    # 工具台账：一个栏目一篇（同一页可能来两个栏目，比如 Agent 页收了 agent / skill / mcp / memory）
    made = {}
    if tools and not args.no_tools:
        by_group = {}
        for t in tools:
            cats = t.get("cats") or []
            if not cats:
                continue
            site = SITE_MAP.get(cats[0])
            if not site:
                continue
            by_group.setdefault((site, cats[0]), []).append(t)
        dates = sorted(a.get("date") for a in articles.values() if a.get("date"))
        dmin = dates[0] if dates else "2026-01-01"
        dmax = dates[-1] if dates else "2026-01-01"
        span = "台账收的是 %s 至 %s 的原文。" % (dmin, dmax)
        for (site, secid), rows in sorted(by_group.items()):
            sname = (sections.get(secid) or {}).get("name") or secid
            key = "%s#tools:%s:%s" % (src, site, secid)
            rec = led["items"].get(key)
            if rec and rec.get("path"):       # 重跑沿用原文件名，别越跑越多「（2）」
                slug = pathlib.Path(rec["path"]).stem
            else:
                slug = slugify("工具台账 · " + sname, taken.setdefault(site, set()))
            out = CONTENT / site / "报告" / (slug + ".md")
            h = sha1(tools_md(rows, sname, dmin, span))
            if out.exists() and rec and sha1(read(out)) != rec.get("hash") and not args.force:
                print("  ! 工具台账「%s」本地改过，跳过" % sname)
                continue
            if not args.dry:
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(tools_md(rows, sname, dmin, span), encoding="utf-8")
                led["items"][key] = {"section": site, "path": str(out.relative_to(ROOT)),
                                     "hash": h, "title": "工具台账 · " + sname}
            made[site] = made.get(site, 0) + len(rows)

    led["sources"][src] = {
        "at": dt.datetime.now().isoformat(timespec="seconds"),
        "sha1": sha1(read(path)),
        "path": str(path),
        "topics": len(topics), "tools": len(tools), "articles": len(articles),
        "sections": {},
    }
    for x in plan:
        if x["site"]:
            led["sources"][src]["sections"][x["site"]] = \
                led["sources"][src]["sections"].get(x["site"], 0) + 1

    print("  ✓ 新增 %d · 更新 %d · 未变 %d · 跳过 %d · 同名不动 %d%s" % (
        stats["new"], stats["update"], stats["same"], stats["skip"], stats["dup"],
        "（--dry 没写盘）" if args.dry else ""))
    if made:
        print("  工具台账：" + "、".join("%s %d 件" % (k, v) for k, v in sorted(made.items())))
    if skipped:
        print("  · 没进站的 %d 条：" % len(skipped))
        for s in skipped[:12]:
            print("      - " + s)
        if len(skipped) > 12:
            print("      …还有 %d 条，见台账" % (len(skipped) - 12))
    print("  · 不入站：%s" % SKIP_NOTE)


def folder_slug(site):
    cfg = CONTENT / site / "section.json"
    if cfg.exists():
        try:
            return json.loads(read(cfg))["slug"]
        except (json.JSONDecodeError, KeyError):
            pass
    return site


def quote_zh(s):
    """链接里只编码会截断 markdown 的字符，中文原样留给浏览器去转。"""
    return s.replace(" ", "%20").replace("(", "%28").replace(")", "%29")


if __name__ == "__main__":
    main()
