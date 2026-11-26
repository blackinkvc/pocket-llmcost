---
title: 跨主题附图：UHP / HarnessRouter 想统一 Agent 后端的接入方式
date: 2026-11-25
summary: ⚠️ **归属说明（必读）**：这张 1086×1086 方图出现在 A022（千万级 RAG 架构）的页面图片里，但**讲的完全是另一件事**——「MCP 之后，Agent 后端也要统一了？」
tags: UHP, HarnessRouter, Agent Harness, 协议, 资料入库
---
**图面全量内容**：副标题「UHP（**Unified Harness Protocol**）想统一的，不是模型本身，而是**产品接入不同 Agent Harness 的方式**」。

- **以前**：产品后端需要分别适配多套 Harness —— 一个「产品后端」分别向下连 **Codex / Claude Code / Gemini CLI** 三个（图示）
- **现在**：通过 **UHP / HarnessRouter** 统一接入多种 Harness —— 产品后端 → UHP / HarnessRouter → Codex / Claude Code / Gemini CLI / …（省略号，可扩展）
- **三个价值**：① **一次接入**——上层产品只对接一套接口；② **多 Harness 复用**——可接入 Codex、Claude Code、Gemini CLI 等；③ **更易扩展**——新增 Harness 不必重写整套后端

**与 MCP 板块的关系**：MCP 是「模型上下文协议：工具 / 资源 / 提示的连接标准与安全边界」；UHP 面向的是**产品后端 ↔ Agent Harness（编码助手运行时）的接入层**，两者都在做「统一接口、避免 N×M 适配」，但**层次与对象不同**，所以按同板块不同主题并列成卡，不与 [T004](../agents/连接层三件套：代码索引、MCP·ACP%20协议与隔离沙盒.html)（Unity MCP）、[T021](../agents/Unity%20MCP：把%20MCP%20从「连工具」推到「直接操作游戏引擎」.html) 等合并。related 挂 agent / case。

⚠️ **一律不补**：UHP 是否为公开标准、规范文档 / 仓库 / 作者 / 发布方、HarnessRouter 是产品还是概念、是否开源、与 MCP 的官方关系、图里省略号代表的其他 Harness、这张图对应的原文链接。图面只给了概念图，本库按「**概念线索**」记录，不写成已发布的协议，也不据此改写 MCP 板块任何既有结论。

**取证补记**：26 张原图里，图 23 / 24 是封面全景的**裁剪放大副本**（分别截到 A/B/C 段与 A/B 段），图 0/2/3/4 是同一封面的 4 份副本，图 1 是公众号头像「AI Agent 领域」，图 26 是 200×200 默认占位图；这些都不重复计数。真正带独家信息的是 **9 张正文长图 + 1 张封面全景 + 这张跨主题方图**。详见 [T023](../apps/取证记录：二十三批资料的可见边界与补全来源.html) 第十批。

> 整理说明：跨主题附图整理卡，不放文章原文；归属与边界已写明，所有未给信息一律留白。若之后收到 UHP 原文链接，新建台账并入本卡，不改动 [A022](https://mp.weixin.qq.com/s/udXF9FEP6SCyeqIxo0YqWA)。

## 来源

- A022《1000 万份文档，RAG 系统到底怎么扛？》 · 2026-11-25 · https://mp.weixin.qq.com/s/udXF9FEP6SCyeqIxo0YqWA
