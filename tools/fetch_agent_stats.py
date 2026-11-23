#!/usr/bin/env python3
"""抓 Agent 板块的实时榜单数据。

数据源都是公开、免密钥的接口：

    npm registry        命令行工具的周下载量
    VS Code Marketplace IDE 插件的累计安装量
    Smithery            MCP 服务器的调用量（useCount）与托管总数
    GitHub Search API   MCP 相关仓库数（topic:mcp-server）

抓到的结果写进 content/agent/榜/*.csv 和 content/agent/data/stats.json，
再由 tools/build_section.py 渲染成页面。任何一个源失败都不影响其它源，
失败的那个保留上一次的 CSV，只在 stats.json 里记一笔。

用法：
    python3 tools/fetch_agent_stats.py            # 抓一遍并写文件
    python3 tools/fetch_agent_stats.py --check    # 只打印，不写文件

GitHub 有速率限制，本地跑可以设 GITHUB_TOKEN 环境变量提高额度；
GitHub Actions 里用自带的 ${{ secrets.GITHUB_TOKEN }} 即可。
"""

import argparse
import concurrent.futures
import datetime as dt
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
SEC = ROOT / "content" / "agent"
BOARD_DIR = SEC / "榜"
DATA_DIR = SEC / "data"

sys.path.insert(0, str(ROOT / "tools"))
import regions  # noqa: E402  区域判定

# 历史快照保留天数：页面上的时间跨度滑块最长 90 天
HISTORY_DAYS = 90

UA = "Mozilla/5.0 (compatible; ai-track-stats/1.0)"

# ── 榜单配置 ───────────────────────────────────────────────
# 命令行工具：包名 → 展示名
CLI = [
    ("@openai/codex", "Codex CLI", "OpenAI"),
    ("@anthropic-ai/claude-code", "Claude Code", "Anthropic"),
    ("opencode-ai", "OpenCode", "SST"),
    ("@github/copilot", "Copilot CLI", "GitHub"),
    ("@google/gemini-cli", "Gemini CLI", "Google"),
    ("@qwen-code/qwen-code", "Qwen Code", "阿里"),
    ("@tencent-ai/codebuddy-code", "CodeBuddy Code", "腾讯"),
    ("@continuedev/cli", "Continue CLI", "Continue"),
    ("@musistudio/claude-code-router", "Claude Code Router", "社区"),
    ("@sourcegraph/amp", "Amp CLI", "Sourcegraph"),
    ("@charmland/crush", "Crush", "Charm"),
    ("@iflow-ai/iflow-cli", "iFlow CLI", "心流"),
]

# IDE 插件：扩展 ID → (展示名, 厂商)
VSIX = [
    ("GitHub.copilot", "GitHub Copilot", "GitHub"),
    ("anthropic.claude-code", "Claude Code for VS Code", "Anthropic"),
    ("saoudrizwan.claude-dev", "Cline", "Cline"),
    ("Continue.continue", "Continue", "Continue"),
    ("Codeium.codeium", "Windsurf Plugin", "Windsurf"),
    ("Alibaba-Cloud.tongyi-lingma", "通义灵码 / Qoder", "阿里云"),
    ("RooVeterinaryInc.roo-cline", "Roo Code", "Roo"),
    ("aminer.codegeex", "CodeGeeX", "智谱"),
    ("sourcegraph.cody-ai", "Cody", "Sourcegraph"),
    ("Augment.vscode-augment", "Augment", "Augment"),
    ("BaiduComate.comate", "文心快码 Comate", "百度"),
]

SMITHERY_TOP = 15
SMITHERY_PAGES = 1
SMITHERY_PAGE_SIZE = 50

# 生态规模按口径拆表：仓库数只看 GitHub，扩展数只看 IDE 市场，
# 上架数只看托管平台。三个口径互不换算，也就不放进同一张表里相加。
GH_TOPIC = "mcp-server"
GH_LANGS = [("TypeScript", "typescript"), ("Python", "python"),
            ("JavaScript", "javascript"), ("Go", "go"),
            ("Rust", "rust"), ("Java", "java")]

# 开源热度榜：topic:mcp-server 被大量「泛 AI 项目」自贴（n8n、gemini-cli 都在里面），
# 直接按 star 排第一行会是工作流平台。所以多加一个「名字里带 mcp」的限制，
# 再滤掉教程、清单、框架——这些不是能装起来用的服务器。
GH_STAR_QUERY = "topic:mcp-server mcp in:name archived:false"
GH_STAR_TOP = 15
GH_STAR_NOISE = ("awesome", "for-beginners", "curriculum", "course", "tutorial",
                 "cheatsheet", "handbook", "cookbook", "list of", "collection of",
                 "framework", "boilerplate", "template", "starter kit")
GH_STAR_SHORT = {"mcp", "mcp-server", "mcp-servers", "servers", "server", "mcp-server-"}


def load_old(filename, key):
    """读上一次的 CSV，用来在个别源失败时沿用旧值。"""
    import csv as _csv
    path = BOARD_DIR / filename
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {r[key]: r for r in _csv.DictReader(f) if r.get(key)}


def now_iso():
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def get(url, headers=None, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def post(url, payload, headers=None, timeout=25):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"User-Agent": UA,
                                          "Content-Type": "application/json",
                                          "Accept": "application/json;api-version=7.2-preview.1",
                                          **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ── 各数据源 ───────────────────────────────────────────────
def fetch_npm(days=HISTORY_DAYS):
    """拉最近 N 天的每日下载量。

    npm 的 range 接口本身就是时间序列，所以这一榜不需要靠每日快照攒历史，
    直接给页面 90 天真实曲线，滑块选多长窗口都是真数据。
    """
    # npm 的「今天」经常还没结算完，当天值偏低甚至为 0，所以窗口截止到昨天
    end = dt.date.today() - dt.timedelta(days=1)
    start = end - dt.timedelta(days=days - 1)
    rows, series, miss = [], {}, []

    def one(item):
        pkg, name, vendor = item
        url = "https://api.npmjs.org/downloads/range/%s:%s/%s" % (start, end, pkg)
        last = None
        for attempt in range(3):
            try:
                return item, get(url, timeout=30), None
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(1.5 * (attempt + 1))
        return item, None, last

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for (pkg, name, vendor), d, err in pool.map(one, CLI):
            if err is not None or not isinstance(d, dict) or not d.get("downloads"):
                miss.append("%s(%s)" % (pkg, err or "空"))
                continue
            daily = {x["day"]: int(x.get("downloads") or 0) for x in d["downloads"]}
            series[pkg] = daily
            last7 = sorted(daily)[-7:]
            rows.append({"名称": name, "包名": pkg, "厂商": vendor,
                         "周下载": sum(daily[k] for k in last7),
                         "期间": "%s ~ %s" % (last7[0], last7[-1]) if last7 else ""})

    if miss:
        print("  · npm 缺 %d 个：%s" % (len(miss), ", ".join(miss)))
        old = load_old("使用量-cli.csv", "包名")
        old_series = load_npm_series()
        got = {r["包名"] for r in rows}
        for pkg, name, vendor in CLI:
            if pkg in got or pkg not in old:
                continue
            try:
                val = int(float(old[pkg].get("周下载") or 0))
            except (TypeError, ValueError):
                val = 0
            rows.append({"名称": name, "包名": pkg, "厂商": vendor,
                         "周下载": val, "期间": old[pkg].get("期间", "")})
            if pkg in old_series:
                series[pkg] = old_series[pkg]
                print("      ↺ 沿用旧值与旧曲线：%s" % name)
            else:
                print("      ↺ 沿用旧值：%s" % name)
    if len(rows) < 5:
        raise ValueError("只拿到 %d 个包，放弃本次写入" % len(rows))
    rows.sort(key=lambda x: -x["周下载"])
    return rows, series


def fetch_vsix():
    rows, miss = [], []
    for ext, name, vendor in VSIX:
        payload = {"filters": [{"criteria": [{"filterType": 7, "value": ext}],
                                "pageNumber": 1, "pageSize": 1}], "flags": 914}
        try:
            d = post("https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery",
                     payload, timeout=40)
            exts = d.get("results", [{}])[0].get("extensions", [])
            if not exts:
                raise ValueError("查不到")
            stats = {s["statisticName"]: s["value"] for s in exts[0].get("statistics", [])}
            rows.append({"名称": name, "扩展ID": ext, "厂商": vendor,
                         "安装量": int(stats.get("install", 0))})
        except Exception as e:  # noqa: BLE001
            miss.append("%s(%s)" % (name, e))
    if miss:
        print("  · 插件缺 %d 个：%s" % (len(miss), ", ".join(miss)))
        old = load_old("使用量-ide.csv", "扩展ID")
        got = {r["扩展ID"] for r in rows}
        for ext, name, vendor in VSIX:
            if ext in got or ext not in old:
                continue
            try:                       # CSV 读回来是字符串，不转 int 排序会炸
                val = int(float(old[ext].get("安装量") or 0))
            except (TypeError, ValueError):
                val = 0
            rows.append({"名称": name, "扩展ID": ext, "厂商": vendor,
                         "安装量": val,
                         "时间": old[ext].get("时间", "")})
            print("      ↺ 沿用旧值：%s" % name)
    if len(rows) < 4:
        raise ValueError("只拿到 %d 个插件，放弃本次写入" % len(rows))
    rows.sort(key=lambda x: -x["安装量"])
    return rows


def fetch_smithery():
    seen, servers = set(), []
    for p in range(1, SMITHERY_PAGES + 1):
        d = None
        for attempt in range(3):
            try:
                d = get("https://api.smithery.ai/servers?page=%d&pageSize=%d" % (p, SMITHERY_PAGE_SIZE),
                        timeout=45)
                break
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    print("  · 第 %d 页跳过：%s" % (p, e))
                else:
                    time.sleep(2 * (attempt + 1))
        if not d:
            continue
        for s in d.get("servers", []):
            qn = s.get("qualifiedName")
            if not qn or qn in seen:
                continue
            seen.add(qn)
            desc = (s.get("description") or "").replace("\n", " ").strip()
            if len(desc) > 80:
                desc = desc[:78].rstrip() + "…"
            servers.append({"名称": s.get("displayName") or qn,
                            "标识": qn,
                            "说明": desc,
                            "调用量": int(s.get("useCount") or 0),
                            "官方": "是" if s.get("bySmithery") else ""})
    total = get("https://api.smithery.ai/servers?page=1&pageSize=1", timeout=45)
    total = (total.get("pagination") or {}).get("totalCount", 0)
    if not servers:
        raise ValueError("一页都没拿到")
    servers.sort(key=lambda x: -x["调用量"])
    return servers[:SMITHERY_TOP], total, len(servers)


def gh_headers():
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    h = {"Accept": "application/vnd.github+json"}
    if tok:
        h["Authorization"] = "Bearer " + tok
    return h


def gh_count(q, retries=3):
    """GitHub Search 的 total_count。未认证额度只有每分钟 10 次，退避要狠一点。"""
    last = None
    for i in range(retries):
        try:
            d = get("https://api.github.com/search/repositories?q=%s&per_page=1" % q,
                    headers=gh_headers())
            n = d.get("total_count")
            if isinstance(n, int):
                return n
            last = "没有 total_count"
        except Exception as e:  # noqa: BLE001
            last = e
        if i < retries - 1:
            print("  · GitHub 退避重试（%s）：%s" % (q, last))
            time.sleep(12 * (i + 1))
    raise ValueError("GitHub 查询失败（%s）：%s" % (q, last))


def fetch_gh_stars():
    """开源热度：GitHub star 数。和 Smithery 的调用量是两件事——
    一个是「有人收藏」，一个是「平台记录过被调用」，两张榜互不包含。
    """
    # per_page 别开大：GitHub 的 search 接口翻 50 条经常 504，25 条稳定得多
    url = ("https://api.github.com/search/repositories?q=%s&sort=stars&order=desc&per_page=25"
           % urllib.parse.quote(GH_STAR_QUERY, safe=":"))
    last = None
    d = None
    for i in range(4):
        try:
            d = get(url, headers=gh_headers(), timeout=45)
            break
        except Exception as e:  # noqa: BLE001  504 是常态，重试即可
            last = e
            if i < 3:
                print("  · GitHub 搜索重试：%s" % e)
                time.sleep(8 * (i + 1))
    if not d:
        raise ValueError("GitHub 搜索失败：%s" % last)

    rows, skipped = [], []
    for r in d.get("items", []):
        name = (r.get("name") or "").strip()
        full = (r.get("full_name") or "").strip()
        desc = (r.get("description") or "").replace("\n", " ").strip()
        blob = (name + " " + desc).lower()
        hit = next((w for w in GH_STAR_NOISE if w in blob), None)
        if hit:
            skipped.append("%s(%s)" % (full, hit))
            continue
        stars = int(r.get("stargazers_count") or 0)
        if not stars:
            continue
        owner = full.split("/")[0] if "/" in full else ""
        # 有些仓库名就叫 mcp / mcp-server（awslabs/mcp、BrowserMCP/mcp），
        # 单看标题分不出是谁的，退回 owner/name
        label = full if len(name) < 6 or name.lower() in GH_STAR_SHORT else name
        rows.append({"名称": label, "仓库": full,
                     # 只拿 owner 和仓库名判断归属：描述里几乎都提 Claude / OpenAI，
                     # 拿描述去猜会把中文作者的仓库判成国外
                     "区域": regions.guess(owner, name),
                     "星标": stars,
                     "说明": desc[:70] + "…" if len(desc) > 70 else desc})
        if len(rows) >= GH_STAR_TOP:
            break
    if len(rows) < 5:
        raise ValueError("只筛出 %d 个，放弃本次写入" % len(rows))
    return rows, skipped


def fetch_eco_repos():
    """MCP 服务器仓库：同一个话题下按实现语言拆开。

    口径只有一个 ——「GitHub 上打了 topic:mcp-server 的公开仓库数」，
    仓库只归属一种主语言，所以各行相加就是话题总数。这是它和
    「仓库数 / 上架数 / 扩展数混在一张表」的区别：这张表能加。
    """
    total = gh_count("topic:" + GH_TOPIC)
    rows, seen = [], 0
    for label, lang in GH_LANGS:
        time.sleep(6)          # 未认证时每分钟 10 次，留足间隔
        n = gh_count("topic:%s+language:%s" % (GH_TOPIC, lang))
        rows.append({"语言": label, "仓库数": n})
        seen += n
    rest = total - seen
    if rest > 0:
        rows.append({"语言": "其他 / 未标注语言", "仓库数": rest})
    for r in rows:
        r["占比"] = "%.1f%%" % (r["仓库数"] * 100.0 / total) if total else ""
    rows.sort(key=lambda x: -x["仓库数"])
    return rows, total


def fetch_eco_markets():
    """IDE 扩展市场存量：各市场自己报的扩展总数，一行一个市场。"""
    rows = []
    payload = {"filters": [{"criteria": [{"filterType": 8, "value": "Microsoft.VisualStudio.Code"}],
                            "pageNumber": 1, "pageSize": 1}], "flags": 914}
    d = post("https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery", payload)
    total = 0
    for m in d["results"][0].get("resultMetadata", []):
        for item in m.get("metadataItems", []):
            if item.get("name") == "TotalCount":
                total = item.get("count", 0)
    if not total:
        raise ValueError("VS Code 市场没返回 TotalCount")
    rows.append({"市场": "VS Code 市场", "区域": "国外", "扩展数": total,
                 "来源": "Marketplace extensionquery"})

    try:
        d = get("https://open-vsx.org/api/-/search?size=1", timeout=30)
        n = int(d.get("totalSize") or 0)
        if n:
            rows.append({"市场": "Open VSX", "区域": "国外", "扩展数": n,
                         "来源": "open-vsx.org /api/-/search"})
    except Exception as e:  # noqa: BLE001
        print("  ! Open VSX 总数失败：%s" % e)

    rows.sort(key=lambda x: -x["扩展数"])
    return rows


def fetch_eco_hosted(smithery_total):
    """MCP 托管平台的上架量。只有 Smithery 把总数放在免密钥接口里。"""
    if not smithery_total:
        raise ValueError("没拿到 Smithery 总数")
    return [{"平台": "Smithery", "区域": "国外", "类型": "MCP 服务器（上架）",
             "上架数": smithery_total, "来源": "api.smithery.ai pagination.totalCount"}]


# ── 写盘 ───────────────────────────────────────────────────
def write_csv(path, rows, cols, when):
    import csv
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for i, r in enumerate(rows, 1):
            r = dict(r)
            r["排名"] = i
            # 区域：CSV 里显式写了就用，否则按厂商 / 平台 / 标识推断，推不出留空
            if "区域" in cols and not r.get("区域"):
                r["区域"] = regions.guess(r.get("厂商"), r.get("平台"),
                                          r.get("标识"), r.get("名称"))
            r.setdefault("时间", when)
            w.writerow({k: r.get(k, "") for k in cols})
    print("  ✓ %s（%d 行）" % (path.relative_to(ROOT), len(rows)))


def load_history():
    p = DATA_DIR / "history.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def load_npm_series():
    """上一次抓到的 npm 每日序列，个别包请求失败时用它兜底。"""
    p = DATA_DIR / "npm-series.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("series", {})
    except json.JSONDecodeError:
        return {}


def snapshot(history, board_file, rows, key_field, val_field, day):
    """把今天的值压进历史：{榜文件: {日期: {名称: 值}}}，只留最近 90 天。"""
    board = history.setdefault(board_file, {})
    board[day] = {r[key_field]: int(r[val_field]) for r in rows
                  if r.get(key_field) and str(r.get(val_field, "")).isdigit()}
    cutoff = (dt.date.fromisoformat(day) - dt.timedelta(days=HISTORY_DAYS - 1)).isoformat()
    for d in [d for d in board if d < cutoff]:
        del board[d]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只打印，不写文件")
    args = ap.parse_args()

    when = now_iso()
    day = when[:10]
    boards, failures = {}, []
    stats_path = DATA_DIR / "stats.json"
    if stats_path.exists():
        try:
            boards = json.loads(stats_path.read_text(encoding="utf-8")).get("boards", {})
        except json.JSONDecodeError:
            boards = {}
    history = load_history()

    print("→ 抓 Agent 榜单")

    # 1) CLI 工具下载量（npm range：90 天真实每日序列）
    try:
        rows, series = fetch_npm()
        boards["使用量-cli.csv"] = {"source": "npm registry（range，最近 90 天）", "updated_at": when}
        if not args.check:
            write_csv(BOARD_DIR / "使用量-cli.csv", rows,
                      ["排名", "名称", "包名", "厂商", "区域", "周下载", "期间"], when)
            (DATA_DIR / "npm-series.json").write_text(
                json.dumps({"generated_at": when, "days": HISTORY_DAYS, "series": series},
                           ensure_ascii=False) + "\n", encoding="utf-8")
            print("  ✓ content/agent/data/npm-series.json（%d 个包 × 最长 %d 天）"
                  % (len(series), HISTORY_DAYS))
        for r in rows[:3]:
            print("      %-22s %12s" % (r["名称"], format(r["周下载"], ",")))
    except Exception as e:  # noqa: BLE001
        failures.append("npm: %s" % e)
        print("  ✗ npm 失败：%s" % e)

    # 2) IDE 插件安装量
    try:
        rows = fetch_vsix()
        boards["使用量-ide.csv"] = {"source": "VS Code Marketplace", "updated_at": when}
        if not args.check:
            write_csv(BOARD_DIR / "使用量-ide.csv", rows,
                      ["排名", "名称", "扩展ID", "厂商", "区域", "安装量", "时间"], when)
            snapshot(history, "使用量-ide.csv", rows, "名称", "安装量", day)
        for r in rows[:3]:
            print("      %-22s %12s" % (r["名称"], format(r["安装量"], ",")))
    except Exception as e:  # noqa: BLE001
        failures.append("vsix: %s" % e)
        print("  ✗ VS Code 市场失败：%s" % e)

    # 3) Smithery MCP 服务器
    smithery_total = 0
    try:
        rows, smithery_total, sample = fetch_smithery()
        boards["mcp服务器.csv"] = {"source": "Smithery useCount", "updated_at": when,
                                   "sample": "%d / %d" % (sample, smithery_total)}
        if not args.check:
            write_csv(BOARD_DIR / "mcp服务器.csv", rows,
                      ["排名", "名称", "标识", "区域", "调用量", "官方", "说明", "时间"], when)
            snapshot(history, "mcp服务器.csv", rows, "名称", "调用量", day)
        for r in rows[:3]:
            print("      %-22s %12s" % (r["名称"], format(r["调用量"], ",")))
            print("      （样本 %d 条 / 平台共 %d）" % (sample, smithery_total))
    except Exception as e:  # noqa: BLE001
        failures.append("smithery: %s" % e)
        print("  ✗ Smithery 失败：%s" % e)

    # 4) 开源热度：GitHub star
    try:
        rows, skipped = fetch_gh_stars()
        boards["mcp-star.csv"] = {"source": "GitHub Search API（按 star 排序）",
                                  "updated_at": when}
        if not args.check:
            write_csv(BOARD_DIR / "mcp-star.csv", rows,
                      ["排名", "名称", "仓库", "区域", "星标", "说明", "时间"], when)
            snapshot(history, "mcp-star.csv", rows, "仓库", "星标", day)
        if skipped:
            print("  · 滤掉 %d 个非服务器：%s" % (len(skipped), "、".join(skipped[:4])))
        for r in rows[:3]:
            print("      %-30s %12s" % (r["仓库"], format(r["星标"], ",")))
    except Exception as e:  # noqa: BLE001
        failures.append("gh-stars: %s" % e)
        print("  ✗ GitHub star 榜失败：%s" % e)

    # 5) 生态规模：三个口径三张表，各自算各自的
    #    4a 仓库数（GitHub topic + 语言）
    try:
        rows, total = fetch_eco_repos()
        boards["生态-mcp仓库.csv"] = {"source": "GitHub Search API", "updated_at": when,
                                      "sample": "topic:%s 共 %d" % (GH_TOPIC, total)}
        if not args.check:
            write_csv(BOARD_DIR / "生态-mcp仓库.csv", rows,
                      ["排名", "语言", "仓库数", "占比", "时间"], when)
            snapshot(history, "生态-mcp仓库.csv", rows, "语言", "仓库数", day)
        for r in rows[:3]:
            print("      %-22s %12s  %s" % (r["语言"], format(r["仓库数"], ","), r["占比"]))
    except Exception as e:  # noqa: BLE001
        failures.append("eco-repos: %s" % e)
        print("  ✗ MCP 仓库数失败：%s" % e)

    #    4b 扩展数（IDE 市场自己报的存量）
    try:
        rows = fetch_eco_markets()
        boards["生态-ide市场.csv"] = {"source": "各市场公开接口", "updated_at": when}
        if not args.check:
            write_csv(BOARD_DIR / "生态-ide市场.csv", rows,
                      ["排名", "市场", "区域", "扩展数", "来源", "时间"], when)
            snapshot(history, "生态-ide市场.csv", rows, "市场", "扩展数", day)
        for r in rows:
            print("      %-22s %12s" % (r["市场"], format(r["扩展数"], ",")))
    except Exception as e:  # noqa: BLE001
        failures.append("eco-markets: %s" % e)
        print("  ✗ IDE 市场存量失败：%s" % e)

    #    4c 上架数（托管平台）
    try:
        rows = fetch_eco_hosted(smithery_total)
        boards["生态-mcp平台.csv"] = {"source": "api.smithery.ai", "updated_at": when}
        if not args.check:
            write_csv(BOARD_DIR / "生态-mcp平台.csv", rows,
                      ["排名", "平台", "区域", "类型", "上架数", "来源", "时间"], when)
            snapshot(history, "生态-mcp平台.csv", rows, "平台", "上架数", day)
        for r in rows:
            print("      %-22s %12s" % (r["平台"], format(r["上架数"], ",")))
    except Exception as e:  # noqa: BLE001
        failures.append("eco-hosted: %s" % e)
        print("  ✗ 平台上架量失败：%s" % e)

    print("完成：%d 个榜，%d 处失败" % (len(boards), len(failures)))
    for f in failures:
        print("  ·", f)

    # 单个源失败不阻塞其它榜：CSV 里失败的那一榜还是上一次的值，
    # stats.json 里会记一笔 failures，页面照常生成。
    if not args.check:
        if not DATA_DIR.exists():
            DATA_DIR.mkdir(parents=True, exist_ok=True)
        # 榜被拆掉或改名后，stats / history 里会留下去不掉的旧键，
        # 这里统一按「CSV 还在不在」清理一遍。
        alive = {p.name for p in BOARD_DIR.glob("*.csv")}
        boards = {k: v for k, v in boards.items() if k in alive}
        history = {k: v for k, v in history.items() if k in alive}
        payload = {"generated_at": when, "date": day, "boards": boards, "failures": failures}
        (DATA_DIR / "stats.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("  ✓ content/agent/data/stats.json")
        # 历史快照：给时间跨度滑块用。每天一条，最多留 90 天。
        (DATA_DIR / "history.json").write_text(
            json.dumps(history, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8")
        span = sorted({d for b in history.values() for d in b})
        print("  ✓ content/agent/data/history.json（%d 天：%s → %s）"
              % (len(span), span[0] if span else "-", span[-1] if span else "-"))
    # 少于两个榜成功才算失败，返回非零让 CI 标红
    return 0 if len(boards) >= 2 else 1


if __name__ == "__main__":
    sys.exit(main())
