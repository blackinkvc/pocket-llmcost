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
import re
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

# ── 一行说明：功能 / 特点 ───────────────────────────────────
# 这里是唯一手工维护的文案。作者、地址、许可、评分、托管方式一律从接口取，
# 不写在这一节里——写死的东西会跟数据打架，而接口给的是当下的事实。
CLI_PROFILE = {
    "@openai/codex": (
        "在终端里读仓库、改代码、跑命令与测试，可作为 MCP 客户端接入外部工具。",
        "沙箱默认开（macOS Seatbelt / Linux Landlock）；额度并入 ChatGPT 订阅，也能换 API key 按量付费。",
    ),
    "@anthropic-ai/claude-code": (
        "长任务编码 Agent：改文件、跑 Bash、开子 Agent，支持 MCP 与 hooks。",
        "闭源分发，只有 npm 包；上下文压缩与计划模式是长任务的强项，按订阅或 API 计费。",
    ),
    "opencode-ai": (
        "终端 TUI 编码 Agent，可接多家云端模型，也能指向本地推理服务。",
        "MIT 开源，客户端与服务端分离，能自带 provider；不走订阅制，花多少取决于你接的模型。",
    ),
    "@github/copilot": (
        "在终端里调 Copilot 编码 Agent，直接读写 GitHub 仓库、开 PR。",
        "绑定 GitHub 账号与 Copilot 席位，企业策略集中下发；闭源，能力边界跟着订阅档位走。",
    ),
    "@google/gemini-cli": (
        "终端 Agent，自带 Google 搜索接地、MCP 扩展与脚本调用。",
        "Apache-2.0 开源，个人 Google 账号有较大免费额度；生态里多个工具是它的分支（Qwen Code 就在其中）。",
    ),
    "@qwen-code/qwen-code": (
        "Gemini CLI 的分支，改成适配 Qwen 系列模型的终端 Agent。",
        "面向 Qwen3-Coder 调优，国内网络可直连；沿用上游的扩展与 MCP 机制，升级也跟上游走。",
    ),
    "@tencent-ai/codebuddy-code": (
        "终端编码 Agent，接腾讯云的模型与工程能力。",
        "闭源，走国内计费与合规路径；与 CodeBuddy IDE 共用一套账号和额度。",
    ),
    "@musistudio/claude-code-router": (
        "把 Claude Code 的请求转发到其它模型或供应商，带 Web 管理界面。",
        "不用改 Claude Code 本体就能换模型、按路由分流；MIT 开源，规则自己写。",
    ),
    "@sourcegraph/amp": (
        "Sourcegraph 的编码 Agent 命令行版。",
        "包已改名为 `@ampcode/cli`，这一行统计的是旧包——数字里含没迁移的 CI 与镜像。",
    ),
    "@charmland/crush": (
        "终端编码 Agent，带 LSP 感知与会话管理。",
        "Go 写的单二进制，界面是 Charm 的 TUI 风格；FSL 许可：源码可见，但不许拿去做竞品。",
    ),
    "@continuedev/cli": (
        "把 Continue 的配置化助手搬进终端，能跑 headless 与 CI 任务。",
        "与 Continue 插件共用 `~/.continue` 的配置和模型表，同一份配置在 IDE 与流水线里复用。",
    ),
    "@iflow-ai/iflow-cli": (
        "终端 Agent，接心流的模型与工作流。",
        "国内团队出品，文档以中文为主；模型走自家网关，换别家要改配置。",
    ),
}

# npm 的 repository 字段有的包干脆没填（opencode-ai 就是）。这里只兜底
# 接口确实取不到的，能从 npm / 市场拿到的地址一律不写死。
CLI_HOME = {
    "opencode-ai": "https://github.com/sst/opencode",
}

VSIX_PROFILE = {
    "GitHub.copilot": (
        "补全、内联对话、Chat 面板、Agent 模式，能读工作区并开 PR。",
        "装机量最大，企业按席位结算；模型可在 OpenAI / Anthropic / Google 之间切。",
    ),
    "anthropic.claude-code": (
        "把 Claude Code 会话嵌进编辑器，带 diff 预览，和终端共享同一份配置。",
        "本质是 CLI 的前端，装它的人多半已经在用 CLI；闭源。",
    ),
    "saoudrizwan.claude-dev": (
        "自主改文件、跑命令、开浏览器，每一步都能审批。",
        "开源 + 自带 key（BYOK），不是订阅制；扩展 ID 还留着 claude-dev 的旧名。",
    ),
    "Continue.continue": (
        "补全 + 对话 + Agent，模型与规则都写在配置文件里。",
        "开源，可接 Ollama / vLLM 等本地服务；团队能统一发一份配置。",
    ),
    "Codeium.codeium": (
        "补全与 Cascade 入口。",
        "插件是导流入口，完整体验在自家 IDE 里；扩展 ID 仍是 Codeium 的旧名。",
    ),
    "Alibaba-Cloud.tongyi-lingma": (
        "中文补全、注释生成、仓库级问答与单测。",
        "国内装机最高的编码插件；个人免费，企业版接阿里云。",
    ),
    "RooVeterinaryInc.roo-cline": (
        "Cline 的分支，按 Architect / Code / Debug 等角色模式分工。",
        "模式和自定义 prompt 更细，适合把流程拆成多个角色；成本仍取决于你接的模型。",
    ),
    "aminer.codegeex": (
        "补全、注释翻译、跨语言代码生成。",
        "智谱出品，有免费额度；多语言互译是它最早打的功能点。",
    ),
    "sourcegraph.cody-ai": (
        "基于代码图索引的问答、补全与批量编辑。",
        "强在跨仓库检索（Sourcegraph 的索引）；免费档额度小，企业向定价。",
    ),
    "Augment.vscode-augment": (
        "补全 + 对话 + Agent，主打大仓库的上下文检索。",
        "企业向、按席位收费；上下文引擎是它唯一的卖点，也是最贵的部分。",
    ),
    "BaiduComate.comate": (
        "补全、单测生成、代码解释，可接企业内部知识库。",
        "国内合规与私有化部署选项多；与百度智能云打包卖。",
    ),
}

# 生态规模按口径拆表：仓库数只看 GitHub，扩展数只看 IDE 市场，
# 上架数只看托管平台。三个口径互不换算，也就不放进同一张表里相加。
GH_TOPIC = "mcp-server"
GH_LANGS = [("TypeScript", "typescript"), ("Python", "python"),
            ("JavaScript", "javascript"), ("Go", "go"),
            ("Rust", "rust"), ("Java", "java")]

# 语言的「特点」不是排名信息，是对这一档里都是些什么项目的判断
GH_LANG_NOTE = {
    "Python": "数据与科研类服务器的主场：数据库、爬取、科学计算都在这儿。",
    "TypeScript": "IDE、前端与官方参考实现集中，npm 一键装，起步成本最低。",
    "JavaScript": "老仓库多，不少是 TypeScript 之前的写法，新项目少往这里放。",
    "Go": "云与基础设施类偏多，单二进制好分发，适合常年挂着的服务。",
    "Rust": "追求单文件、低内存的服务器在往这儿迁，数量少但增长快。",
    "Java": "企业内网集成（数据库、ERP、消息队列）居多，公开热度低。",
    "其他 / 未标注语言": "作者没选主语言，或仓库本身是文档与清单型。",
}

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


# ── 元数据小工具 ───────────────────────────────────────────
def clean_repo(u):
    """把 npm / 市场里的仓库地址洗干净：去掉 git+ 、git@ 、.git 、#readme。"""
    u = (u or "").strip()
    if not u:
        return ""
    u = u.replace("git+", "").replace("ssh://git@", "https://").replace("git@", "")
    u = re.sub(r"^https://[^/]*@", "https://", u)
    u = re.sub(r"#.*$", "", u)      # 只去锚点；?itemName=... 是市场页的正文
    u = re.sub(r"\.git$", "", u)
    return u if u.startswith("http") else ""


def lic_label(s):
    """npm 的许可字段五花八门，归一到「能不能看源码」这个粒度。"""
    s = (s or "").strip()
    if not s:
        return "未标注"
    if s.upper().startswith("SEE LICENSE"):
        return "专有"
    return re.sub(r"-MIT$", "", s)


_PROBE = {}


def probe(url):
    """外链到底通不通：只用来挡掉确定死了的地址（404 / 410）。

    超时、被封、403 一律当「不知道」——网络抖动不该让一条好链接消失，
    但 GitHub 上已经没有这个仓库、市场页也下架了，就不该再挂上去。
    """
    if not url:
        return "dead"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36",
            "Accept": "text/html,*/*"})
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read(1024)
            return "ok" if r.status < 400 else "unknown"
    except urllib.error.HTTPError as e:
        return "dead" if e.code in (404, 410) else "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def resolve_addresses(rows, key="_cands"):
    """并发探活，再按候选顺序落地址。

    串行探活会把这支脚本从 1 分钟拖到 4 分钟，所以先收齐 URL 一起查，
    每个 URL 只查一次（同一批里常有重复）。
    """
    urls = sorted({u for r in rows for u in map(clean_repo, r.get(key, [])) if u})
    if urls:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            for u, st in zip(urls, pool.map(probe, urls)):
                _PROBE[u] = st
    for r in rows:
        cands = [u for u in map(clean_repo, r.get(key, [])) if u]
        if cands:                    # 没有候选的是沿用的旧行，保留它原来的地址
            r["地址"] = next((u for u in cands if _PROBE.get(u) != "dead"), "")
        r.pop(key, None)


def npm_meta(pkg):
    """npm 包自带的许可与仓库地址。取不到就留空，不猜。"""
    try:
        d = get("https://registry.npmjs.org/%s/latest"
                % urllib.parse.quote(pkg, safe="@"), timeout=20)
    except Exception:  # noqa: BLE001
        return {}
    repo = d.get("repository")
    if isinstance(repo, dict):
        repo = repo.get("url")
    return {"许可": lic_label(d.get("license")),
            "地址": clean_repo(repo) or clean_repo(d.get("homepage"))}


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

    def base(pkg, name, vendor, old=None):
        """一行卡片的基础字段：人工文案 + 上一次取到的许可/地址。"""
        fn, ft = CLI_PROFILE.get(pkg, ("", ""))
        old = old or {}
        return {"名称": name, "包名": pkg, "厂商": vendor,
                "功能": fn, "特点": ft,
                "许可": old.get("许可", ""),
                "地址": old.get("地址", "") or CLI_HOME.get(pkg, "")}

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for (pkg, name, vendor), d, err in pool.map(one, CLI):
            if err is not None or not isinstance(d, dict) or not d.get("downloads"):
                miss.append("%s(%s)" % (pkg, err or "空"))
                continue
            daily = {x["day"]: int(x.get("downloads") or 0) for x in d["downloads"]}
            series[pkg] = daily
            last7 = sorted(daily)[-7:]
            row = base(pkg, name, vendor)
            meta = npm_meta(pkg)            # 许可 / 地址 以 npm 当下返回为准
            row["许可"] = meta.get("许可") or row["许可"]
            row["地址"] = meta.get("地址") or row["地址"]
            row.update({"周下载": sum(daily[k] for k in last7),
                        "期间": "%s ~ %s" % (last7[0], last7[-1]) if last7 else ""})
            rows.append(row)

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
            row = base(pkg, name, vendor, old[pkg])
            row.update({"周下载": val, "期间": old[pkg].get("期间", "")})
            rows.append(row)
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

    def base(ext, name, vendor, old=None):
        fn, ft = VSIX_PROFILE.get(ext, ("", ""))
        old = old or {}
        return {"名称": name, "扩展ID": ext, "厂商": vendor,
                "功能": fn, "特点": ft,
                "评分": old.get("评分", ""), "地址": old.get("地址", "")}

    for ext, name, vendor in VSIX:
        payload = {"filters": [{"criteria": [{"filterType": 7, "value": ext}],
                                "pageNumber": 1, "pageSize": 1}], "flags": 914}
        try:
            d = post("https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery",
                     payload, timeout=40)
            exts = d.get("results", [{}])[0].get("extensions", [])
            if not exts:
                raise ValueError("查不到")
            e = exts[0]
            stats = {s["statisticName"]: s["value"] for s in e.get("statistics", [])}
            # 市场把仓库地址放在版本的 properties 里，不是顶层字段
            props = {p["key"]: p["value"] for p in (e.get("versions") or [{}])[0].get("properties", [])}
            src = (props.get("Microsoft.VisualStudio.Services.Links.Source")
                   or props.get("Microsoft.VisualStudio.Services.Links.GitHub") or "")
            home = (props.get("Microsoft.VisualStudio.Services.Links.Learn")
                    or props.get("Microsoft.VisualStudio.Services.Links.Getstarted") or "")
            rating, votes = stats.get("averagerating") or 0, int(stats.get("ratingcount") or 0)
            row = base(ext, name, vendor)
            row.update({
                "安装量": int(stats.get("install", 0)),
                # 仓库 → 官网 → 上架页：Cody 的仓库已经删了，市场页才活得下来
                "_cands": [src, home,
                           "https://marketplace.visualstudio.com/items?itemName=" + ext],
                # 评价人数太少时不算「评价」，宁可不显示
                "评分": ("%.1f★ / %d 评" % (rating, votes)) if votes >= 20 and rating else "",
            })
            rows.append(row)
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
            row = base(ext, name, vendor, old[ext])
            row.update({"安装量": val})
            rows.append(row)
            print("      ↺ 沿用旧值：%s" % name)
    resolve_addresses(rows)
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
            # 说明里混着 markdown 链接，卡片上留文字不留地址
            desc = re.sub(r"\[([^\]]+)\]\((?:https?://[^)]+)\)", r"\1", desc)
            desc = re.sub(r"^[#>*\s]+", "", desc)          # 开头常带 # 标题记号
            desc = re.sub(r"\s+", " ", desc)
            if len(desc) > 150:
                cut = desc[:150]
                sp = cut.rfind(" ")
                desc = (cut[:sp] if sp > 90 else cut).rstrip(" ,.;:、，。") + "…"
            servers.append({"名称": s.get("displayName") or qn,
                            "标识": qn,
                            "说明": desc,
                            "调用量": int(s.get("useCount") or 0),
                            "官方": "是" if s.get("bySmithery") else "",
                            # remote = 平台代跑，不用本地装；否则要自己部署
                            "形态": "远程托管" if s.get("remote") else "需自部署",
                            "认证": "已认证" if s.get("verified") else "",
                            "上架": (s.get("createdAt") or "")[:7],
                            # 平台的 homepage 不少是死链（gmail 那条 404），
                            # 标识写成 owner/repo 的退一步找 GitHub
                            "_cands": [s.get("homepage"),
                                       ("https://github.com/" + qn) if qn.count("/") == 1 else ""]})
    total = get("https://api.smithery.ai/servers?page=1&pageSize=1", timeout=45)
    total = (total.get("pagination") or {}).get("totalCount", 0)
    if not servers:
        raise ValueError("一页都没拿到")
    servers.sort(key=lambda x: -x["调用量"])
    sample = len(servers)          # 样本量：截断前的条数，页面上的「样本 50 / 共 20743」
    servers = servers[:SMITHERY_TOP]
    resolve_addresses(servers)
    return servers, total, sample


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
        lic = ((r.get("license") or {}).get("spdx_id") or "").strip()
        # 有些仓库名就叫 mcp / mcp-server（awslabs/mcp、BrowserMCP/mcp），
        # 单看标题分不出是谁的，退回 owner/name
        label = full if len(name) < 6 or name.lower() in GH_STAR_SHORT else name
        rows.append({"名称": label, "仓库": full,
                     # 只拿 owner 和仓库名判断归属：描述里几乎都提 Claude / OpenAI，
                     # 拿描述去猜会把中文作者的仓库判成国外
                     "区域": regions.guess(owner, name),
                     "语言": r.get("language") or "",
                     "许可": "" if lic.upper() in ("NOASSERTION", "OTHER") else lic,
                     "星标": stars,
                     "地址": r.get("html_url") or ("https://github.com/" + full),
                     "说明": desc[:110] + "…" if len(desc) > 110 else desc})
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
        rows.append({"语言": label, "仓库数": n, "备注": GH_LANG_NOTE.get(label, "")})
        seen += n
    rest = total - seen
    if rest > 0:
        rows.append({"语言": "其他 / 未标注语言", "仓库数": rest,
                     "备注": GH_LANG_NOTE.get("其他 / 未标注语言", "")})
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
                 "备注": "微软官方市场，所有发布者都在这儿上架；条目含主题、语言包等非工具类扩展。",
                 "来源": "Marketplace extensionquery"})

    try:
        d = get("https://open-vsx.org/api/-/search?size=1", timeout=30)
        n = int(d.get("totalSize") or 0)
        if n:
            rows.append({"市场": "Open VSX", "区域": "国外", "扩展数": n,
                         "备注": "面向 VSCodium / Theia 等非微软 IDE 的开放市场，条目少，但不受微软条款约束。",
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
             "上架数": smithery_total,
             "备注": "免密钥接口直接给总数；上架里有相当一部分是平台代跑的远程服务器，装都不用装。",
             "来源": "api.smithery.ai pagination.totalCount"}]


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
                      ["排名", "名称", "厂商", "包名", "许可", "区域", "周下载", "功能", "特点", "地址", "期间"], when)
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
                      ["排名", "名称", "厂商", "扩展ID", "评分", "区域", "安装量", "功能", "特点", "地址", "时间"], when)
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
                      ["排名", "名称", "标识", "区域", "调用量", "官方", "形态", "认证", "上架", "说明", "地址", "时间"], when)
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
                      ["排名", "名称", "仓库", "区域", "语言", "许可", "星标", "说明", "地址", "时间"], when)
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
                      ["排名", "语言", "仓库数", "占比", "备注", "时间"], when)
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
                      ["排名", "市场", "区域", "扩展数", "备注", "来源", "时间"], when)
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
                      ["排名", "平台", "区域", "类型", "上架数", "备注", "来源", "时间"], when)
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
