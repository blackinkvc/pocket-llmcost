---
title: Archify：一句正文、三页长图与「让 Agent 出数据、程序画图」的分工
date: 2026-09-03
summary: **归类决定**：归「**Skill**」主板块（可复用能力单元 / Agent Skill），related 挂 agent / case / roadmap，**不新建栏目**。
tags: Archify, tt-a1i/archify, Agent Skill, 类型化 JSON, 资料入库
---
**页面可见信息**：公众号「**AI情报库**」（`nick_name` / 水印），`author`「**云隐**」，`alias`「**YYZG_2020**」，`user_name` gh_950f7e290456，`create_time` **2026-09-03 05:45**、`ori_create_time` 1788385514，`appmsg_type: 10002`（同 [A034](https://mp.weixin.qq.com/s/iMnx_LuS2x5Znk2MkhdjTg)，区别于 [A035](https://mp.weixin.qq.com/s/yjAqx2IHAhFewtkBdpI8zw)/[A036](https://mp.weixin.qq.com/s/o_C93hkiSzFeap_0YyfXKg) 的 9），`can_share: '0'`，`source_url` 为空、地点未给，**无 `_copyright_stat` / 无「原创」标**、**0 个「微信广告」广告位**、**0 个话题标签**（`wx_topic_link` / `topic-id` 都 0 次）。⚠️ 这是**库内发布最早的一条**（比 [A033](https://mp.weixin.qq.com/s/ryLsLKE6YTtK7nMQLjdMqQ) 的 2026-09-07 还早 4 天，倒序收录）。头像 272×272 是黑底金节点网络 + 档案图标、**无文字**。

**正文全量（1 句 100 字符，按原样）**：「**这**是 GitHub 上 **tt-a1i/archify** 的 Agent Skill。它让 Agent 先产出**类型化 JSON**，再由程序完成 **Schema、引用和布局检查**，生成**可交互 HTML 与多种导出**。」⚠️ **`content_noencode` 缺「这」字**（「是 GitHub 上…」）—— 继 [A036](https://mp.weixin.qq.com/s/o_C93hkiSzFeap_0YyfXKg)「最新一期 / 新一期」之后的**缺字型**一字之差，与 og:description 并列留档、不调和、不替作者补字。**0 个话题标签**。

**图面逐字 · P1「ARCHIFY SKILL / 架构图，终于能验了」**：顶部「**39,284 Stars** ｜ 本周 **+22,095** ｜ **2026.09.01 快照**」；浏览器地址栏 **archify.dev**（Dark / Light / Export 按钮）；下方两卡「**它是什么**：把代码库或系统描述变成可交互系统图」「**它解决什么**：不只『画得像』，还要**减少虚构拓扑**」；「**工作流**：代码 / 描述 → 类型化 JSON → 确定性校验 → **HTML · SVG · PNG**」；底部五类图「**架构图 / 工作流图 / 时序图 / 数据流图 / 生命周期图**」。内嵌架构示意：Security & Identity（Auth Service OAuth2 / OIDC、JWT / Access Token、Validate Token）→ Frontend（Web App React / TypeScript，HTTPS）→ Backend Services（API Service REST / GraphQL、User Service、Billing Service）→ Message Bus（Event Bus RabbitMQ / Kafka）→ Workers（Email Worker / Report Worker）；Database（PostgreSQL Primary Database）；Cloud Infrastructure（VPC / Load Balancer / Object Storage）。⚠️ 这是**演示截图快照**，不是真实系统拓扑。

**图面逐字 · P2「ARCHIFY | 核心机制 / 为什么它不只是『让AI画图』」**：旧问题三条「自然语言直接变图 / 模型可能补出不存在的关系 / 复杂图还会重叠、断线、难复核」；五步 **01 读取语义**（Agent 理解代码库或系统描述）→ **02 生成类型化 JSON**（节点、连线、分区、布局都有结构）→ **03 Schema 校验**（检查类型、引用和必填信息）→ **04 布局规则检查**（发现重叠、越界和不可读结构）→ **05 确定性渲染**（编译成独立 HTML 与 SVG）；底部「**关键分工**：**AI 负责**理解与表达语义 ｜ **程序负责**校验与渲染」。

**图面逐字 · P3「ARCHIFY | 生成之后 / 一张图，还能继续追」**：三张演示界面小图 `Cache Miss Request Sequence` / `Production Deployment Ownership` / `Agent Tool Call Workflow`（内含 `PATH MAP / LENS`、`Web App → API → Postgres` 路径等，全部**演示截图快照**）；右侧三能力「**路径追踪**：沿已写入的连线查看最短路径」「**语义镜头**：按角色和区域聚焦已写入关系」「**引导叙事**：把复杂系统拆成可播放章节」；「**四个核心优点**：可验证（检查类型、引用与布局规则）/ 可交互（搜索、聚焦、上下游与路线）/ 可复核（可绑定经过版本校验的源码链接）/ 可分享（单文件 HTML，并导出 PNG / SVG / WebM）」；底部「**边界**：**它验证图中声明，不替代运行时监控**」。水印版右下「**公众号 · AI情报库**」。

⚠️ **三层证据分开**：① **一手已证实（外部，单列不并入正文）**：回一手核到 **GitHub 仓库 tt-a1i/archify 真实存在** —— 当前 **95.4k stars** / 6.5k forks / 232 watchers / 1,762 commits、描述「Turn any idea, plan, or codebase into a beautiful interactive diagram. An agent skill for Claude Code, Codex, and more.」、**Apache-2.0**（保留历史 MIT grants）、官网 **archify.si**、topics 含 agent-skills / claude-code / codex / diagrams-as-code / dsh-plugin；第三方教程另给 `npx skills add tt-a1i/archify -g`、`npx skills use tt-a1i/archify@archify --agent codex` 与五类图、Node CLI 校验命令。② **图面快照（未回一手核实）**：39,284 Stars / 本周 +22,095 / 2026.09.01 快照。③ **演示界面截图**：P1 架构示意与 P3 三张小图。⚠️ **核实的是「仓库存在 + 当前状态」，不是图面 9-01 的历史快照** —— GitHub 当前 95.4k 既不能证 39,284、也不能证伪（时点不同）。

⚠️ **图面独有词回 HTML 验零（全部 0 次）**：39,284 / 22,095 / 2026.09.01 / archify.dev、「它是什么」「它解决什么」「还要减少虚构拓扑」、工作流四步、五类图名、核心机制五步、「关键分工 AI负责·程序负责」、生成之后三能力、四个核心优点、边界句、三个演示界面标题、水印。⚠️ **反向**：「类型化 JSON」「架构图」「可交互」正文里就有（6 / 5 / 6 次），**不是图面独有**。**验零第二类噪音**：`Dark`(24) / `Live`(9) / `Export`(12) / `API`(401) 命中全是微信页面 **JS 框架变量名 / 函数名**（`iconTopSimplifyUrlDark` / `setLivePlaceHolder` / `wapExportToken` / `JSAPIEventCallbackMap`），不是图面按钮文字；继 [A036](https://mp.weixin.qq.com/s/o_C93hkiSzFeap_0YyfXKg)「SVG path 圆弧坐标」之后第二类。

**图片取证（11 张 → 7 组）**：三页 1024×1536 长图各 1 组带 **2 份副本**（无水印 png + 带「公众号 · AI情报库」水印 png，像素差 0.19 / 0.21 / 0.20，**沿用 [A033](https://mp.weixin.qq.com/s/ryLsLKE6YTtK7nMQLjdMqQ)「每页成对水印」：无水印读内容、水印版补号名**）；第 1 页 1024×1365 裁剪版 ×2（**完全同 md5 / 差 0.00**，`og:image` 用它，截掉顶部「ARCHIFY SKILL」与底部五类图图标下半）、1024×1024 方裁、272×272 头像、200×200 占位。⚠️ 与 [A032](https://mp.weixin.qq.com/s/c5DlBqp_XiL_HQhjGTf95w)/[A034](https://mp.weixin.qq.com/s/iMnx_LuS2x5Znk2MkhdjTg)/[A035](https://mp.weixin.qq.com/s/yjAqx2IHAhFewtkBdpI8zw)/[A036](https://mp.weixin.qq.com/s/o_C93hkiSzFeap_0YyfXKg) 的「同一主图多份副本」不同，这次是**三张不同内容的页各带一份水印副本**；裁剪版不能当完整页用。

**证据等级**：「**公众号极简 Skill 推荐卡 · 一手页面与 11 张图面可查 · 正文仅 1 句但给出完整 owner/repo · 仓库存在与当前状态经 GitHub 一手页核实 · 图面 39,284 Stars / +22,095 / 2026.09.01 快照未回一手核实 · 内嵌界面为演示截图 · 无原创声明、无话题标签、无榜单原页链接、无制图方**」。⚠️ 这是本库**首次核实到「完整 owner/repo 真实存在」**，但核实范围只到仓库与当前状态。见 [T090](../agents/39,284%20→%2062.9k%20·%206.7万%20→%2095.4k.html) / [T091](../apps/第八型取证范式：完整%20owner·repo%20能核什么、不能核什么，以及两类验零噪音.html) / G41 / G42。

> 整理说明：事实整理卡。正文按 og:description / content_noencode 逐字摘录（含缺字差异），三页长图按图面逐页抄录；外部一手核实结果、图面快照与演示界面分层留档，不互相补全。

## 来源

- A037《Archify Skill会验架构图》 · 2026-09-03 · https://mp.weixin.qq.com/s/QQbMio_My7u1i_ladamVkw
