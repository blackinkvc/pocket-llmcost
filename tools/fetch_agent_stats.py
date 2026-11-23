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
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
SEC = ROOT / "content" / "agent"
BOARD_DIR = SEC / "榜"
DATA_DIR = SEC / "data"

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
    ("@continuedev/cli", "Continue CLI", "Continue"),
    ("@musistudio/claude-code-router", "Claude Code Router", "社区"),
]

# IDE 插件：扩展 ID → (展示名, 厂商)
VSIX = [
    ("GitHub.copilot", "GitHub Copilot", "GitHub"),
    ("anthropic.claude-code", "Claude Code for VS Code", "Anthropic"),
    ("saoudrizwan.claude-dev", "Cline", "Cline"),
    ("Continue.continue", "Continue", "Continue"),
    ("Codeium.codeium", "Windsurf Plugin", "Windsurf"),
    ("RooVeterinaryInc.roo-cline", "Roo Code", "Roo"),
    ("sourcegraph.cody-ai", "Cody", "Sourcegraph"),
]

SMITHERY_TOP = 15
SMITHERY_PAGES = 1
SMITHERY_PAGE_SIZE = 50


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
def fetch_npm():
    rows = []
    for pkg, name, vendor in CLI:
        url = "https://api.npmjs.org/downloads/point/last-week/%s" % pkg
        d = get(url)
        n = d.get("downloads")
        if n is None:
            raise ValueError("npm 返回没有 downloads：%s" % pkg)
        rows.append({"名称": name, "包名": pkg, "厂商": vendor, "周下载": n,
                     "期间": "%s ~ %s" % (d.get("start", ""), d.get("end", ""))})
    rows.sort(key=lambda x: -x["周下载"])
    return rows


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
            rows.append({"名称": name, "扩展ID": ext, "厂商": vendor,
                         "安装量": old[ext].get("安装量", ""),
                         "时间": old[ext].get("时间", "")})
            print("      ↺ 沿用旧值：%s" % name)
    if len(rows) < 4:
        raise ValueError("只拿到 %d 个插件，放弃本次写入" % len(rows))
    rows.sort(key=lambda x: -x["安装量"])
    return rows


def fetch_smithery():
    seen, servers = set(), []
    for p in range(1, SMITHERY_PAGES + 1):
        try:
            d = get("https://api.smithery.ai/servers?page=%d&pageSize=%d" % (p, SMITHERY_PAGE_SIZE),
                    timeout=35)
        except Exception as e:  # noqa: BLE001
            print("  · 第 %d 页跳过：%s" % (p, e))
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
    total = 0
    d1 = get("https://api.smithery.ai/servers?page=1&pageSize=1")
    total = (d1.get("pagination") or {}).get("totalCount", 0)
    servers.sort(key=lambda x: -x["调用量"])
    return servers[:SMITHERY_TOP], total, len(servers)


def fetch_counts(smithery_total):
    gh_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    gh_headers = {"Accept": "application/vnd.github+json"}
    if gh_token:
        gh_headers["Authorization"] = "Bearer " + gh_token
    rows = []

    rows.append({"平台": "Smithery", "类型": "MCP 服务器", "数量": smithery_total,
                 "来源": "smithery.ai 接口 totalCount"})

    try:
        d = get("https://api.github.com/search/repositories?q=topic:mcp-server&per_page=1",
                headers=gh_headers)
        rows.append({"平台": "GitHub", "类型": "MCP 仓库（topic:mcp-server）",
                     "数量": d.get("total_count", 0), "来源": "GitHub Search API"})
    except Exception as e:  # noqa: BLE001
        print("  ! GitHub 仓库数失败：%s" % e)

    try:
        d = get("https://api.github.com/repos/anthropics/skills/contents/skills",
                headers=gh_headers)
        n = len(d) if isinstance(d, list) else 0
        rows.append({"平台": "Anthropic Skills 仓库", "类型": "官方 Skill",
                     "数量": n, "来源": "github.com/anthropics/skills"})
    except Exception as e:  # noqa: BLE001
        print("  ! skills 目录数失败：%s" % e)

    try:
        payload = {"filters": [{"criteria": [{"filterType": 8, "value": "Microsoft.VisualStudio.Code"}],
                                "pageNumber": 1, "pageSize": 1}], "flags": 914}
        d = post("https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery", payload)
        meta = d["results"][0].get("resultMetadata", [])
        total = 0
        for m in meta:
            for item in m.get("metadataItems", []):
                if item.get("name") == "TotalCount":
                    total = item.get("count", 0)
        rows.append({"平台": "VS Code 市场", "类型": "扩展（全部）",
                     "数量": total, "来源": "Marketplace extensionquery"})
    except Exception as e:  # noqa: BLE001
        print("  ! VS Code 扩展总数失败：%s" % e)

    rows.sort(key=lambda x: -x["数量"])
    return rows


# ── 写盘 ───────────────────────────────────────────────────
def write_csv(path, rows, cols, when):
    import csv
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for i, r in enumerate(rows, 1):
            r = dict(r)
            r["排名"] = i
            r.setdefault("时间", when)
            w.writerow({k: r.get(k, "") for k in cols})
    print("  ✓ %s（%d 行）" % (path.relative_to(ROOT), len(rows)))


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

    print("→ 抓 Agent 榜单")

    # 1) CLI 工具周下载
    try:
        rows = fetch_npm()
        boards["使用量-cli.csv"] = {"source": "npm registry（last-week）", "updated_at": when}
        if not args.check:
            write_csv(BOARD_DIR / "使用量-cli.csv", rows,
                      ["排名", "名称", "包名", "厂商", "周下载", "期间"], when)
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
                      ["排名", "名称", "扩展ID", "厂商", "安装量", "时间"], when)
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
                      ["排名", "名称", "标识", "调用量", "官方", "说明", "时间"], when)
        for r in rows[:3]:
            print("      %-22s %12s" % (r["名称"], format(r["调用量"], ",")))
            print("      （样本 %d 条 / 平台共 %d）" % (sample, smithery_total))
    except Exception as e:  # noqa: BLE001
        failures.append("smithery: %s" % e)
        print("  ✗ Smithery 失败：%s" % e)

    # 4) 生态规模
    try:
        rows = fetch_counts(smithery_total)
        if rows:
            boards["生态规模.csv"] = {"source": "各平台公开接口", "updated_at": when}
            if not args.check:
                write_csv(BOARD_DIR / "生态规模.csv", rows,
                          ["排名", "平台", "类型", "数量", "来源", "时间"], when)
            for r in rows[:3]:
                print("      %-22s %12s" % (r["平台"], format(r["数量"], ",")))
    except Exception as e:  # noqa: BLE001
        failures.append("counts: %s" % e)
        print("  ✗ 生态规模失败：%s" % e)

    print("完成：%d 个榜，%d 处失败" % (len(boards), len(failures)))
    if failures:
        for f in failures:
            print("  ·", f)
        return 1

    if not args.check:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        payload = {"generated_at": when, "date": day, "boards": boards, "failures": failures}
        (DATA_DIR / "stats.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("  ✓ content/agent/data/stats.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
