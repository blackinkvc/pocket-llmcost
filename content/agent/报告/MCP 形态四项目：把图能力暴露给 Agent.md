---
title: MCP 形态四项目：把图能力暴露给 Agent
date: 2026-11-24
summary: A005 里 8 个项目有 4 个形态是 MCP，共同点是用标准协议把建好的图/记忆暴露给 Agent 查询。与 T004（连接层三件套）不同，这里讲的是具体 MCP 服务做什么，故同板块并列。
tags: MCP, 知识图谱, WASM, 团队记忆, 资料入库
---
- GitNexus（abhigyanpatwari/GitNexus，46.2k★，GRAPH / WASM / TRENDING，+4.6 万/日）：零服务器的代码智能引擎。仓库丢进浏览器，WASM 本地建图，LadybugDB 落盘持久化，再用 17 个 MCP 工具（query / impact / trace / rename / cypher / pdg_query）把图暴露给 Agent——代码从头到尾不出本机。TypeScript / PolyForm 非商用 / Tree-sitter / 建仓 2025-08-02 / 本月仍在更新。架构：GIT REPO → BROWSER（WASM 建图 / LadybugDB 落盘）→ 17 MCP → AGENT（Claude / Cursor）。限制：浏览器模式约 5,000 文件上限、PolyForm 非商用。痛点：Agent 靠猜调用关系（改一处炸一片、事前看不出爆炸半径）、代码不能出库时 SaaS 型方案出局、npm 11.x 下 npx 会崩（npm 自身 bug，非项目问题）。指标 46.2k★ / 17 MCP 工具 / 非商用
- codebase-memory-mcp（DeusData/codebase-memory-mcp，41.0k★，FASTEST / 亚毫秒）：纯 C 单文件二进制、零运行时依赖。RAM-first 流水线（LZ4 压缩 + 内存 SQLite + 融合 Aho-Corasick），Linux 内核 28M 行 / 75K 文件 3 分钟全量索引，结构查询亚毫秒返回，15 个 MCP 工具。C / MIT / 161 语言 / Hybrid LSP 语义解析 10 种 / arXiv:2603.27277 / 6768 测试 / 内置 3D 图 UI。5 次查询 3.4k token vs 逐文件 41.2 万。痛点：大仓库索引慢、语言运行时依赖重、一次查询几十次 grep。指标 41.0k★ / 161 语言 / 3 min / MIT
- code-review-graph（tirth8205/code-review-graph，31.0k★，REVIEW / −71× token）：Tree-sitter 建结构图并增量跟踪变更，MCP 只喂该读的上下文；实测 flask 全量语料 143,594 token vs 图查询 2,196 token（71.0 倍）；一条 install 自动配置 Codex / Claude Code / Cursor 等 15 个平台。Python 3.10+ / MIT / 增量更新 / GitHub Action / 建仓 2026-02-26。痛点：评审反复重读代码烧 token、diff 看得见但波及面看不见、多平台各写一套 MCP 配置。指标 31.0k★ / −71.0× / 15 平台 / MIT
- TencentDB-Agent-Memory（TencentCloud/TencentDB-Agent-Memory，25.1k★，VENDOR / −61.4% token）：团队级记忆中枢。符号化短期记忆（冗长工具日志压成 Mermaid 符号）+ 分层长期记忆（对话蒸馏成 persona / scene），对话、文档、代码统一蒸馏为四类资产：Chat Memory / Skill / LLM-Wiki / Code-Graph，治理后跨 Agent 共享。TypeScript / MIT / Node ≥ 22.16 / 接 OpenClaw、Hermes 网关 / 建仓 2026-04-07 / 腾讯云官方 / 长会话连续 50 任务实测 −61.4% token、+51.5% 通过率。痛点：Agent 每次失忆、上下文越跑越重、记忆是扁平向量堆。指标 25.1k★ / −61.4% / +51.5% / MIT

四个项目对应四种不同的「给 Agent 装记忆/地图」路线：本地零服务器（GitNexus）、极致性能与超大仓（codebase-memory-mcp）、按变更增量喂上下文（code-review-graph）、团队级跨 Agent 共享（TencentDB）。选型三问（[T012](../agents/知识图谱%20·%20上下文工程：8%20个项目全景与选型三问.html)）里的「代码能出库吗」「团队要共享索引吗」正好把前两者和后两者分开。

> 整理说明：许可证里 GitNexus 是 PolyForm 非商用，其余三个 MIT；这一点只在图片里写明，别按「开源」一概而论。

## 来源

- A005《写代码 or 做内容，都有必要建「知识图谱」》 · 2026-11-24 · https://mp.weixin.qq.com/s/EXkEIXCZ25pIMZaRwp0njA
