---
title: Skill 形态三项目：把资料与代码变成可复用能力
date: 2026-11-24
summary: A005 的详情页是逐项目拆的，这里把 SKILL 形态的三个（外加 CLI 形态的 openwiki）合并成一张，因为它们讲的是同一件事：把散资料/陌生代码固化成能被 Agent 复用的结构。
tags: 知识图谱, Skill, graphify, 图片信息, 资料入库
---
- graphify（Graphify-Labs/graphify，112.1k★ 榜首，+…/日）：一个 Claude Code skill。代码之外 PDF / 截图 / 白板照片 / SQL schema 全用视觉模型抽概念入同一张图；本地确定性 AST 解析，每条边可解释，不用向量库，SHA256 缓存只重算改动文件。Python 3.10+ / Apache-2.0 / 建仓 2026-04-03 / 注意 PyPI 包名是 graphifyy。架构：CODE+PDF+截图+白板+SQL → 混合抽取（AST 确定性 + 视觉抽概念）→ ONE GRAPH（graph.json 持久 / SHA256 缓存）→ −71.5× token（Karpathy /raw 读原文 vs 读图文件）。命令 /graphify、--watch 自动同步。痛点：/raw 文件夹越堆越乱、非代码资料进不了传统 AST 图谱、每次重读全量。指标 112.1k★ / 10.9k forks / −71.5× / Apache-2.0
- Understand-Anything（Egonex-AI/Understand-Anything，80.9k★，TOP 3，+2.9k 星/日）：多 Agent 流水线建图，给「结构视图（代码怎么组织）」+「业务域视图（代码映射到业务）」双视图；引导式导览按依赖顺序带你读代码，还能把 Karpathy 式 LLM wiki 转成带社区聚类的力导向图。TypeScript / MIT / Claude Code 插件 / 通吃 8 种编码 CLI（Claude Code、Codex、Cursor、Copilot、Gemini CLI 等）/ 含 Live Demo。核心句「能教人的图，胜过好看的图」。痛点：20 万行新库不知从哪读起、图好看但不教人、wiki 与源码两张皮。指标 80.9k★ / 6.8k forks / 2 种视图 / MIT
- archify（总览卡，28.8k★）：代码库先转成类型化 JSON，验证器校验通过才渲染成架构图，模型幻觉会被拦下。SKILL / JavaScript / MIT / #架构变更评审 #可验证输出 #对外讲结构。注意：这篇 7 张详情卡里没有 archify 的独立页，信息只有总览这一格
- openwiki（langchain-ai/openwiki，15.8k★，OFFICIAL / LangChain 官方）：Deep Agents 文档 Agent 写并维护 wiki；可恢复的页面任务架构（begin → submit_plan → next_page → submit_page → finish）带持久化有序队列；Grounded Claims 把每条事实钉回版本化源码证据，源码一变就知道哪些结论要确认、重写或作废。TypeScript / MIT / 13 家模型商 / 9 个连接器 / OKF v0.2 / 建仓 2026-06-22 / GitHub Actions 自更新。痛点：文档写完就过期、AI 写的 wiki 不知真假、CI 里跑一半断了要重来。指标 15.8k★ / 13 模型商 / 9 连接器 / MIT

四个项目串起来看是一条「沉淀链」：graphify 把多模态资料入图 → Understand-Anything 让图能教人 → archify 让图可验证 → openwiki 让图带证据自维护。与 [T001](../agents/科研分析路线规划%20Skill：工作流与输入输出契约.html)/[T002](../agents/从该案例提炼：Skill%20设计的三条可复用原则.html)（单个 Skill 的输入输出契约）不同，这里讲的是 Skill 如何组织长期资产，故同板块并列。

> 整理说明：仓库全名、建仓日期、架构链路、指标与「解决什么问题」三段均来自图片，纯文字版完全没有。graphify 与 [A006](https://mp.weixin.qq.com/s/YxMmpdanLUPpL9voQjCHDg) 的 ④ graphify 同名但星数与定位不同，见 [T016](../apps/图片取证记录：两篇口径冲突与可见边界.html)。

## 来源

- A005《写代码 or 做内容，都有必要建「知识图谱」》 · 2026-11-24 · https://mp.weixin.qq.com/s/EXkEIXCZ25pIMZaRwp0njA
