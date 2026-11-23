# Token 价格追踪

大模型 **API 按量价 / 订阅套餐 / 本地部署** 三个维度算成本的本地小应用。
给「口袋」中台（pocket）当插件用，也能单独 `python3 llmcost.py --serve` 跑。

- 纯标准库，不装任何第三方包，断网可用
- 一个页面 18 张卡：本轮结论、价格快照、模型天梯榜、价格 × 实力、价格走势、全盘水位、调价日志、API 价目、订阅套餐、本地部署、任务换算、数据校验……
- 多源交叉校验：同一条价格有官方页、开源价目库、社区追踪三个来源，能对上的标「多源一致」，只有一家的标「单源待补」，冲突的点名说哪几家不一致
- 榜单数据来自 [LMArena](https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset)（HuggingFace）与 [Vectara 幻觉率榜](https://github.com/vectara/hallucination-leaderboard)（GitHub）

## 装

```bash
git clone https://github.com/Pamphile0117/pocket-llmcost.git
cd pocket-llmcost
./install.sh
```

`install.sh` 做三件事，可以重复执行：

1. 把仓库放到 `<中台数据根>/_插件/llmcost`（已有就 `git pull`）
2. 在 `<中台数据根>/_工作台/plugins.json` 里登记一条 `llmcost`（同 id 覆盖内置那一行，所以中台不用改代码、也不用重启）
3. 拉起来，等 `/api/ping` 通了再报成功

常用参数：

| 参数 | 作用 |
| --- | --- |
| `--update` | 更新：`git pull --ff-only` + 重启服务 |
| `--restart` | 只重启（换成本仓库这版代码时用） |
| `--code DIR` | 代码放哪儿（默认 `<数据根>/_插件/llmcost`） |
| `--data DIR` | 数据放哪儿（默认 `<数据根>/13-算价`） |
| `--no-launch` | 只装不启动 |

装完打开 <http://127.0.0.1:8776/>。中台左侧那颗「Token 价格追踪」药丸会自动出现，刷新页面即可，不用重启口袋。

不用中台也行：

```bash
python3 llmcost.py --serve            # 默认 8776
python3 llmcost.py --serve --port 9000
python3 llmcost.py --snapshot         # 落一份看板 + 报告到 out/
python3 llmcost.py --json | head      # 打包好的数据打到 stdout
python3 llmcost.py --version
```

要求 Python ≥ 3.9，无第三方依赖。

## 代码和数据分家

代码跟着仓库走，数据留在外面 —— 这样 `git pull` 永远不会和每天写进去的历史打架。

数据目录按顺序找：`$LLMCOST_DIR` → 同目录 `.llmcost-dir`（install.sh 写的）→
`~/Documents/AI项目/13-算价` → `~/.pocket-llmcost`。

```
data/
  api_prices.csv          API 按量价（币种 / 峰谷 / 促销 / 缓存价 / 一手来源）
  plans.csv               订阅套餐（计费单位 + 三档系数 + 限额 + 活动到期）
  local_rigs.csv          本地硬件（采购价 / 折旧 / 功耗 / tok/s / 利用率）
  task_examples.csv       「跑一次任务大概多少 token」的换算例子
  sources.json            交叉校验源清单（12 个）
  price_history.csv       官方价的历史观测点
  price_points.csv        平台价历史（第三方渠道）
  platforms.csv           平台台账
  price_events.csv        已知调价事件
  observations_builtin.csv 内置观测记录
  leaderboard.csv         LMArena 榜单（模型天梯榜）
  hallucination.csv       Vectara 幻觉率
  snapshots/              每天一份主表快照，用来算「今天哪儿变了」
out/                      报告与 SVG（--snapshot 才生成）
```

**第一次跑会把仓库里的 `seed/` 补进数据目录**（只补缺、不覆盖）。`seed/` 是发布
那一刻的公开价目快照，所以新装的人打开就有东西看；价格会过期，页面上每张表都
标了「核验日」，超过阈值会标成「数据过期」。

## 刷新数据

```bash
python3 llmcost_leaderboard.py      # 重新拉 LMArena + 幻觉率榜 → data/leaderboard.csv
python3 llmcost_platforms.py        # 重建平台价库（保留日常累积的点）
python3 llmcost.py --snapshot       # 重算并落报告
```

榜单抓的是 `hf-mirror.com`（HuggingFace 镜像）与 GitHub API；国内网络下这个镜像
比 `huggingface.co` 稳。抓不到就保留上一次的文件，不会把已有数据清空。

## 它在中台里长什么样

- 「＋插件」弹窗的清单里归在 **其他插件** 那一档（`"group": "other"`）
- 页面上的 18 张卡可以单独钉到中台首页（`/api/cards` 报清单，`w/h` 与页面
  `data-w/data-h` 逐字一致）
- 皮肤、壁纸、字体跟中台同一套：`pgkit.py` 转发中台生成的 `appearance.css`，
  读不到就退回 classic，页面本身不受影响

## 目录

```
llmcost.py             HTTP 服务（:8776）+ 数据打包
llmcost_core.py        算账核心：校验 / 出表 / 画 SVG / 写报告
llmcost_ui.html        整个前端（单文件，18 张卡）
llmcost_leaderboard.py 抓 LMArena + 幻觉率榜，合并到价格表
llmcost_platforms.py   平台价库（官方历史 + 第三方快照）
pgkit.py               公共壳 / 皮肤转发 / 卡片清单（从口袋拆出来的）
lease.py               按需服务租约：页面关掉进程自己退
kit/                   shell.css / shell.js / filter.css / filter.js
seed/                  种子数据（公开价目快照）
run.command            双击启动（macOS）
install.sh             安装 / 更新
plugin.json            给中台看的清单（id / 端口 / 入口 / 分组 / 版本）
```

## 口径说明（重要）

- **分数是 LMArena 的 text 综合 Elo，不同维度之间不可比**；`agent` 那一维是胜率，不是 Elo。
- 价格默认按 **输出价 / 百万 token** 排；输入价、缓存价另见「API 价目」。
- 美元价按 `sources.json` 里的 `fx_usd_cny` 换算，只用于图表可比，不是结算汇率。
- 「前沿」用的是 Pareto：A 支配 B = A 不比 B 贵、且分不低于 B。只在实心点上画阶梯。
- 标「单源待补」的是只有一家来源对上的价格，当线索看，别当定论。

## 许可

个人项目，未附许可证。要用请开 issue 说一声。
