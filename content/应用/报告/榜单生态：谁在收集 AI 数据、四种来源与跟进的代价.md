---
title: 榜单生态：谁在收集 AI 数据、四种来源与跟进的代价
date: 2026-11-25
summary: **跟进的代价按节奏分六档**（榜单雷达页 C 区有完整表）：每小时重算（AA / Arena 的 Elo）→ 随提交更新（HF / SWE-bench / GAIA / METR）→ 每周每月看 Changelog
tags: 榜单, 评测基准, 数据收集方, 证据等级, 资料入库
---
以下为基于 [A019](https://artificialanalysis.ai/video/leaderboard/image-to-video)（榜单截图）与 [A018](http://yb.woa.com/62oPBlyl0U0)（战绩展示视频）的归纳延伸，并落到新建的「🏆 榜单雷达」页（DATA.boards，20 个头部榜单 L01–L20）。两篇原文都没讨论「榜单该怎么追」，本卡与 [T032](../apps/观点型资料的证据等级：个人实测怎么收进库才不会被当成事实.html) / [T038](../apps/数字的七类证据性质：演示%20·%20报价%20·%20示意%20·%20可核验计数%20·%20正文未载的图面结果.html) / [T040](../apps/官宣%20·%20内部评测类资料：怎么收才不会把「自证闭环」写成「第三方验证」.html) / [T042](../apps/战绩展示类视频：公开%20PoC、二值判定与「转述的转述」怎么标证据等级.html) 主题不同 → 并列成卡，共同构成资料可信度标注体系。

**四类数据收集方**（这是「谁在收集」最该先分清的一层）：

- ① **人类盲测投票**：Artificial Analysis 的 Video / Image / Speech Arena 用经筛选与身份核验的私有评审者、Arena（原 LMArena）用社区匿名双盲对战；数据来自「人在具体提示词下更喜欢哪一段」，不是模型能力绝对值。AA 还要求每条提示词人工审核、最短播放 8 秒、约 1/5 会话做质量检查，不通过就整会话作废
- ② **社区提交 + 统一跑分**：Hugging Face Open LLM Leaderboard v2、SWE-bench、GAIA 官方测试集榜；数据来自提交者把模型/系统交上来，平台用公开 harness 跑出可复现分数。可审计，但存在择优提交与训练污染
- ③ **厂商自报**：模型卡、技术报告、发布方官宣（[A017](https://mp.weixin.qq.com/s/CJoJ6Ch2nOAZqX5EKb2shA) MatMaster、[A018](http://yb.woa.com/62oPBlyl0U0) MIM）；数字由利益方自己测，第三方基准与厂商自报常差几十 Elo 分或多倍效率，必须分开记
- ④ **联盟同行评议**：MLCommons / MLPerf，working group 定规则、LoadGen 统一管时钟、其他提交者可挑战结果后才发布；最接近工程测量，但只在同轮次、同 scenario、同 division 内可比

**最容易踩的三个坑**：

- **快照当实时**：[A019](https://artificialanalysis.ai/video/leaderboard/image-to-video) 那张图是公众号转载的四跳转述（官方 → 转载 → 截图 → 本库），且 AA 的 Elo 每小时重算；同一模型 83 天内可差 137 分与 3 个名次。所以截图必须带「抓取时间 + 版本/轮次 + 筛选条件」三要素，且旧快照只追加不覆盖（规则 M02 / M07）
- **镜像站伪更新**：Aider Polyglot 官方榜靠志愿者 PR、自 2025-08 冻结，镜像站 2026-09 仍标「updated」。镜像刷新时间 ≠ 源数据新鲜度（规则 M04）
- **口径混比**：SWE-bench Verified 与 Pro、Terminal-Bench 2.0 与 4.0、GAIA 的 bare / scaffolded / 系统级、AA 的含音频与无音频分池、MLPerf 的 Closed / Open —— 版本、脚手架、指标三件缺一件，分差就不能解读成能力差（规则 M03）

**由此沉淀的落库约定**：新增第三页「🏆 榜单雷达」而不是塞进现有板块；20 个榜单按 L 编号，每条写清运营主体、数据从哪来、更新节奏、可跟进渠道（官网 / Changelog / GitHub / 公开数据集 / PDF / xlsx / 公众号）与读榜 caveat。以后你发榜单截图或链接，我按 L 编号并入、挂 A 编号台账、追加快照并回写补齐清单；主题相近合并、不同主题顺延 L21 起。

⚠️ 本卡与榜单雷达页都只写结构信息与方法，不复制榜单原文；所有具体分数留在 [A019](https://artificialanalysis.ai/video/leaderboard/image-to-video) 台账与页面 A 区样本表，且一律标「快照 / 未去原页复核」。20 个榜单里多数还没有你发来的原始链接，属于框架先行，已在页面 F 区 B02 如实标注。

> 整理说明：归纳卡片，非原文观点；运营主体与评测方法以官方页为准，未核实的更新频率按官方表述写「周期性 / 按版本」，不凭印象补。

## 来源

- A019《AA-Video-I2V v2.1 图生视频（含音频）Elo 榜单截图》 · 2026-11-25 · https://artificialanalysis.ai/video/leaderboard/image-to-video
- A018《MiniMax 密码分析战绩展示（内部模型 MIM）》 · 2026-11-25 · http://yb.woa.com/62oPBlyl0U0
