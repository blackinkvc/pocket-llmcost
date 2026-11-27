# AI.TRACK · 监控台 + Token 价格追踪

> **在线站点**：<https://blackinkvc.github.io/pocket-llmcost/>
> **实例 01 · 生图实验**：<https://blackinkvc.github.io/pocket-llmcost/lab/>
> **Token 价格追踪**：<https://blackinkvc.github.io/pocket-llmcost/llmcost/>
> **小工具下载**：<https://blackinkvc.github.io/pocket-llmcost/llmcost/download.html>

一个仓库装两样东西：**一套只读的静态台账站**（GitHub Pages 直接发），
**一个能算账的本地小应用**（Python 标准库，免安装依赖）。
静态站里「价格」那五页就是本地应用的数据快照；本机跑着服务时，那几页会自动切到实时数据。

## 两套东西的关系

| | 静态站（九板块 + 实例 01） | 本地应用（Token 价格追踪） |
| --- | --- | --- |
| 怎么跑 | GitHub Pages，纯 HTML/CSS/JS | `python3 llmcost.py --serve`，或下载的可执行包 |
| 有什么 | 基模 / Agent / 公司 / 硬件 / 模板 / 应用 / 原理与历史 / 本地部署 / 实例 | 18 张卡的算价看板，五页呈现 |
| 数据 | 人工维护的快照 | 读 CSV 现场算；每天由 Action 落一份快照给线上用 |
| 依赖 | 无 CDN、无框架、无字体 | 纯标准库，Python ≥ 3.9，断网可用 |

## 门户九板块（只读台账）

| 页面 | 内容 |
| --- | --- |
| `index.html` | 门户：九板块入口、近期信号、读法、实例与工具入口 |
| `models.html` | 基模：有出处的能力分榜 + 2026-11 的模型台账（31 条），三层时间口径分开写 |
| `agents.html` | Agent：7 个每日抓取的榜（CLI / IDE 各带功能、特点、仓库地址、许可与评分），MCP 调用量与开源热度两榜，生态规模三张分开的表 |
| `companies.html` | 公司：产业链站位 27 家（上游到下游）、两份能独立读完的全文（产业链报告 / 人物关系库） |
| `hardware.html` | 硬件：数据中心 18 卡 / 本地 9 机型 / IDC 出货三张表，加 prefill-decode 与显存账两篇报告 |
| `templates.html` | 模板：六套骨架（选型矩阵 / 成本估算单 / 工具定义 / 评测设计卡 / 部署核对单 / 结论沉淀），每套一篇可复制全文 |
| `apps.html` | 应用：六类 23 个产品按首次可用月份排，附「形态决定天花板」「编码 Agent 为什么先跑通」两篇 |
| `principles.html` | 原理 · 历史：17 个机制的索引表（点标题进报告）+ 4 张概念卡 + 14 篇报告，含 1943–2025 四段时间线 |
| `history.html` | 跳转页：带锚点转到 `principles.html#e1`，旧链接不断 |
| `local.html` | 本地部署：13 套引擎 + 8 档显存 + 量化档位 + 硬件落点 + 排查清单五张表，附 5 篇报告 |
| `cases.html` | 实例索引：01 已上线，02–06 占位与字段规范 |

## 板块内容怎么改（`content/`）

除首页外，板块页统一成三段：**简介 → 天梯榜卡片 → 报告**。内容不在 HTML 里，在 `content/<板块>/`：

```
content/基模/
  section.json   标题、副标题、标签、右栏指标、翻页
  简介.md        板块一：说明 + 三条结论
  天梯榜.csv     板块二：一行一张卡片
  报告/*.md      板块三：一篇一个文件，生成独立页
```

改完跑 `python3 tools/build_section.py`（`--only models` 只重建一个，`--dry` 出到 `.preview/`）。
细节见 [`content/README.md`](content/README.md)。

三类板块不走这套：

| 板块 | 为什么 |
| --- | --- |
| 实例 | 讲自己做的东西的**迭代过程** + 硬件实测，字段和「天梯榜」不是一回事 |
| 研究 | 研究项目的**管理看板**，状态由 `research/items/` 推导，已有流水线 |
| 价格 | **实时追踪**，要抓数、要快照、要能现场重算，数据在 `seed/` |

## 实例 01（`lab/`）

同一台机器、同一批参考图、串行出图。142 行生成台账 × 26 列、128 份候选边车、
10 张 A/B 对照、8K 海报实验与 H3 实测。判定口径只看服装版型、配色材质、配饰、
发型轮廓、体型、义体位置，不看脸。

| 页面 | 内容 |
| --- | --- |
| `lab/index.html` | 实验档案首页：方案总览、总量指标、口径摘要 |
| `lab/scheme-*.html` | 六套管线：SDXL 基线、Z-Image Turbo / Base、双采、latent 放大、Krea 2、MOSS |
| `lab/compare.html` | 横向对比：同 prompt / 同 seed 并排 |
| `lab/gallery.html` | 案例库：按方案筛选的图墙 |
| `lab/bench-h3.html` | H3 实测看板 |

根目录下旧的 `scheme-*.html`、`compare.html`、`gallery.html`、`bench-h3.html`
保留为跳转页，外链不会失效。

## Token 价格追踪（`llmcost/`）

18 张卡拆成五页，数据来自 `llmcost/data/data.json`（由 Action 每天重算）：

| 页面 | 内容 |
| --- | --- |
| `llmcost/index.html` | 总览：本轮结论、价格快照、数据规模、全盘水位 |
| `llmcost/ranking.html` | 榜单：模型天梯榜、价格 × 实力、API 输出价排名 |
| `llmcost/prices.html` | 价目：API 价目、平台矩阵与排行、订阅套餐、本地部署、任务换算 |
| `llmcost/trend.html` | 走势：价格曲线、月度矩阵、调价日志、调价事件 |
| `llmcost/method.html` | 口径：多源交叉校验、来源清单 |
| `llmcost/download.html` | 下载：站内小工具清单、按系统给包、校验和、装完打不开怎么办 |

**数据源自动切换**：页面先探一下 `http://127.0.0.1:8776/api/ping`，
通了就用本机实时数据并在顶部标 `LIVE`，不通就读仓库里的快照（标注生成时间）。
本地服务只放行 GitHub Pages 与本机来源的跨域读取，别的网站读不到。

## 装小工具

> 网站本身不打包、不提供下载——九板块、研究、实例都是网页。
> 能装到本机的只有一件小工具：**价格追踪看板**（`llmcost`），它是从墨山中台拆出来的独立插件。

### 下可执行包（不用装 Python）

到 [Releases](https://github.com/blackinkvc/pocket-llmcost/releases/latest) 拿对应平台的包：

| 平台 | 文件 |
| --- | --- |
| macOS · Apple 芯片 | `llmcost-macos-arm64.zip` |
| macOS · Intel | `llmcost-macos-x64.zip` |
| Windows · 64 位 | `llmcost-windows-x64.zip` |
| Linux · x86_64 | `llmcost-linux-x64.tar.gz` |

解开直接运行 `llmcost`（Windows 是 `llmcost.exe`），浏览器自动打开 <http://127.0.0.1:8776/>。

未签名：macOS 首次打开要右键 → 打开，或 `xattr -dr com.apple.quarantine <路径>`；
Windows 弹 SmartScreen 选「更多信息 → 仍要运行」。

### 源码 + 口袋中台插件

```bash
git clone https://github.com/blackinkvc/pocket-llmcost.git
cd pocket-llmcost
./install.sh
```

`install.sh` 做三件事，可重复执行：把仓库放到 `<中台数据根>/_插件/llmcost`、
在 `_工作台/plugins.json` 里登记一条 `llmcost`、拉起来等 `/api/ping` 通了再报成功。

常用参数：`--update` 更新、`--restart` 只重启、`--code DIR` / `--data DIR` 换位置、`--no-launch` 只装不启动。

### 不用中台也行

```bash
python3 llmcost.py --serve            # 默认 8776
python3 llmcost.py --serve --port 9000
python3 llmcost.py --snapshot         # 落一份看板 + 报告到 out/
python3 llmcost.py --json | head      # 打包好的数据打到 stdout
python3 llmcost.py --version
```

## 研究怎么进来（`research/`）

研究页（`research/index.html`）是**两张列表**：上面是「任务进度表」，一条研究占一行，
四段进度（投料 → 整理 → 审核 → 上线）直接显示卡在哪一步；下面是「规划表」，写还欠哪些题、
每道题要回答什么。进度表的数据来自 `items/`，规划表来自两处：

- `research/plan.yml`：我登记的研究规划，一条一个任务，`phase` 取 `doing` / `next` / `queued`。
- 各板块 `content/<板块>/报告/*.md` 里 frontmatter 带 `status: todo` 的报告：提纲已立、正文待写，
  自动进规划表，不用在 plan.yml 里重复登记。写完把 `status: todo` 删掉就挪回板块页。

一条研究有四个状态，状态**由文件推出来**，不靠手填：

| 状态 | 判据 | 站点表现 |
|---|---|---|
| 整理中 | `items/<slug>/` 有 meta，没有 draft | 占位页：标题 + 摘要 + 原始资料清单，`noindex` |
| 待审核 | 存在 `items/<slug>/draft.md` | 同上，看板里多一个「通过审核」按钮 |
| 已上线 | 存在 `published/<slug>.md` | 完整文章页，可被索引，进列表页 |

**投料区在仓库外**：`/Volumes/AI仓库/AI行业研究/`。它的子文件夹就是站点板块——`基模` `agent` `公司` `硬件` `模板` `应用` `原理` `历史` `本地部署` `实例`（原理与历史已合并成一页，两个文件夹都能收），另有 `_其他`（拿不准先丢这）和 `_已收录`（脚本自动归档，别手动放）。**放在哪个文件夹，条目就归哪个板块**：研究页与看板上会显示板块标签，点它跳回对应站点页。

外置盘没挂载时自动退回仓库内 `research/inbox/`（没有板块归属）；要换位置用 `RESEARCH_DROPZONE=/path/to/zone`。原件收走后进 `<板块>/_已收录/<日期>/`，所以投料区平时是空的，空就代表都收完了。

```bash
# 1) 投料：把 md / pdf / 截图 / 整个文件夹丢进投料区的板块文件夹，然后
python3 tools/research.py sync

# 2) 整理：让 AI 按 research/templates/research.md 写 items/<slug>/draft.md，
#    顺便把 meta.yml 补上 draft_at；slug 想更好看就改
python3 tools/research.py rename r-20261123-02 multi-agent-orchestration

# 3) 审核：open research/status.html，点「通过审核」
#    → 打开一个标题为 approve: <slug> 的 issue → Submit
#    → .github/workflows/approve.yml 校验是仓库主本人发的，定稿、重建、提交、回评、关单

# 本地不想走 issue 也可以直接定稿
python3 tools/research.py approve multi-agent-orchestration
```

**审核按钮为什么不直接写仓库**：GitHub Pages 是纯静态，页面上的 `fetch` 没有身份，
任何"点一下就改仓库"的实现都得把 token 塞进浏览器。这里用 issue 当审核通道——
用你 GitHub 已有的登录态，token 不进浏览器也不进仓库，每次审核还在 issue 里留了痕。

`research/*.html`、`research/index.html`、`research/status.html` 都是**生成物**，
手改会在下次 `build` 时被覆盖：改内容改 `items/<slug>/draft.md`，改样式改
`research/assets/research.css`，改文案改 `tools/research.py` 里的模板串。

## 发布一条命令

```bash
./tools/preview.sh                 # 本地起 8099 预览，自动打开浏览器
./tools/publish.sh "改了什么"       # 重建子页 → 断链自检 → 提交 → 推 GitHub
./tools/publish.sh --dry           # 只看会传哪些文件，不动远端
./tools/publish.sh "刷新快照" --refresh   # 顺带重算 llmcost 的 data.json
```

推送走 GitHub REST API（本机到 github.com 的 git 传输被代理挡死），**增量**：
内容没变的文件不重传，日常改几页只花几个 API 调用。凭证从 macOS 钥匙串读，
只存一次：

```bash
security add-generic-password -s pocket-llmcost-gh-token -a "$USER" -w ghp_你的token -U
```

## 数据怎么刷新

- **线上快照**：`.github/workflows/snapshot.yml` 每天 02:17 UTC 跑一次
  `tools/make_snapshot.py`，数据有变化才提交；也可以在 Actions 页面手动触发。
  GitHub 的定时任务在仓库 60 天无活动后会自动停，点一次就恢复。
- **本地数据**：`llmcost_leaderboard.py` 拉 LMArena + 幻觉率榜，
  `llmcost_platforms.py` 重建平台价库，`llmcost.py --snapshot` 重算。
- **改页面**：`llmcost/` 下五页由 `tools/build_pages.py` 从 `llmcost_ui.html`
  按卡拆分生成；只改样式调 `llmcost/assets/lc-site.css`。

## 目录

```
index.html … templates.html    门户九板块（静态，无构建；history.html 是跳转页）
content/                       板块内容源：一个文件夹一个板块
  基模/                        已切换（样板）：简介 / 天梯榜 / 报告
  agent/                       已切换：七个实时榜（npm / VS Code / Smithery 调用 / GitHub star / 仓库数 / 上架量 / 扩展存量）
  公司/                        已切换：站位榜 + 两份外来全文（全文/ 里存原件，构建时复制进 companies/）
  硬件/ 模板/ 应用/ 本地部署/    已切换：2026-11 快照，各带 2–6 篇报告
  实例/ 研究/ 价格/             只放说明，数据仍在各自流水线里
tools/build_section.py         从 content/ 生成板块页（三板块结构）
tools/fetch_agent_stats.py     抓 Agent 榜单（每天由 Actions 跑）
tools/fetch_model_ledger.py    重建模型台账（事实列取自 OpenRouter 目录）
lab/                           实例 01 生图实验
research/                      研究板块
  inbox/                       备用投料区（外置盘没挂载时用；文件会被搬走）
  items/<slug>/                meta.yml + raw/ + draft.md
  published/                   定稿（有它才算上线）
  templates/research.md        标准模板
  index.html / status.html    生成物：研究总览 / 进度看板
tools/research.py              研究流水线：sync / build / approve / rename / list
assets/css, assets/img/        站点样式与图（WebP，单张 ≤ 300 KB）

llmcost/                       价格追踪子站（五页 + 下载页）
  assets/lc.css                18 张卡的内容样式（从 llmcost_ui.html 抽出）
  assets/lc-engine.js          渲染引擎（含数据源切换）
  assets/lc-site.css           子站适配层（顶栏、二级 tab、下载页）
  data/data.json               线上读的快照（Action 每天重算）

llmcost.py                     HTTP 服务（:8776）+ 数据打包
llmcost_core.py                算账核心：校验 / 出表 / 画 SVG / 写报告
llmcost_ui.html                小工具的单页界面（五页由它拆分而来）
llmcost_leaderboard.py         抓 LMArena + 幻觉率榜
llmcost_platforms.py           平台价库
pgkit.py / lease.py            中台公共壳 / 按需服务租约
kit/                           中台共用样式与脚本
seed/                          种子价目（新装就有东西看）
tools/make_snapshot.py         生成线上快照
tools/build_pages.py           把单页拆成五页
build/llmcost.spec             PyInstaller 打包配置
install.sh / run.command       安装 / 双击启动
plugin.json                    中台清单（id / 端口 / 入口 / 分组 / 版本）
```

## 数据口径

- **快照而不是实时**：门户与实例页是人工维护的知识快照（基模基线 2026-11，公司数据截至 2026-11-18）；
  价格五页由 Action 每日重算，页面标生成时间，过期会标红。
- **三态写法**：真值直接写；本该有值但未采集写 `—` / `null`；结构上不存在写 `n/a`。
- **不抄跑分**：没有出处的 benchmark 分数不收录。
- **价格口径**：默认按输出价 / 百万 token 排；美元价按 `sources.json` 的
  `fx_usd_cny` 换算，只用于图表可比，不是结算汇率；标「单源待补」的当线索看。
- **代码和数据分家**：可执行包只带代码与种子价目，用户数据留在
  `$LLMCOST_DIR` → `~/Documents/AI项目/13-算价` → `~/.pocket-llmcost`，升级不覆盖。

## 隐私与收录

- 页面不出现本机绝对路径与用户名（快照里 `meta.root` 已被剥掉）。
- 不收录可能涉及成人向、露骨或明确版权角色的图；只用原创科幻角色的技术对照与静物样张。
- 不发布台账中的个人路径字段与本地数据库。

## 许可

站点文案与排版：CC BY 4.0。图片为个人项目测试产物，仅用于技术展示，不授权商用或二次分发。
代码部分为个人项目，未附许可证，要用请开 issue 说一声。
