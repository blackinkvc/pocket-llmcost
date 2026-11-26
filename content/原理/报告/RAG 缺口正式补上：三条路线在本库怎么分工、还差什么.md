---
title: RAG 缺口正式补上：三条路线在本库怎么分工、还差什么
date: 2026-11-25
summary: **① 第 4 步 RAG 的三次状态变化**（T028 学习路线映射已同步）：「完全没有独立栏目」（A010 阶段，只有 T025 阶段三的 Chunking / Embedding /
tags: RAG, 缺口回写, 参数化记忆, 企业知识库, 资料入库
---
以下为基于 [A022](https://mp.weixin.qq.com/s/udXF9FEP6SCyeqIxo0YqWA) 的归纳延伸：原文只讲工程架构，没有讨论本库的栏目分工。因与 [T049](../principles/千万级%20RAG%20系统架构全景与规模账：从%201000%20万文档到%202%20亿%20Chunks.html)–[T052](../principles/生产保障四层：质量评测、可观测性、索引重建、安全与权限.html)（事实整理）性质不同 → 并列成卡。目的很实际：把补齐清单里挂了很久的 G18 正式关掉，并说清「关掉之后还剩什么」。

**② 三条路线不要混**：

- **传统 RAG 工程（本栏目 / [A022](https://mp.weixin.qq.com/s/udXF9FEP6SCyeqIxo0YqWA)）**：历史原文留在外部，每轮检索后塞进上下文；工程重点是摄取、索引、混合召回、重排、评测与运维
- **参数化记忆（memory / [A020](http://yb.woa.com/DjfzMFlnxuO)）**：把历史编码进模型内部记忆状态，后续回答**无需在上下文保留历史原文**；官方自己承认「需要精细证据检索的超长历史任务上纯文本检索系统仍占优」
- **企业知识库选型（kb / [A008](https://yb.tencent.com/s/8oKggmiksd3U)）**：从需求侧算规模档位、成本与适用性评级；与本栏目是**需求侧 vs 供给侧**的关系，[A008](https://yb.tencent.com/s/8oKggmiksd3U) 的报告本体至今未提供（内容待补），两边暂时还接不上具体数字

**③ 一个有意思的对照**：[A020](http://yb.woa.com/DjfzMFlnxuO) 的 MemT 用 13M 固定记忆状态换「不重塞历史」，[A022](https://mp.weixin.qq.com/s/udXF9FEP6SCyeqIxo0YqWA) 的 2 亿 Chunks 要 820GB 起、还要 2–3 副本和 shadow index 双份；前者省的是**每轮 token**，后者花的是**一次性存储 + 持续索引**。两条路线不是谁替代谁，而是「短期事实 / 用户偏好进权重，需审计 / 撤回 / 多人共享留外部」这一分工的工程侧写照（[T045](../agents/MemT-1.0%20系列技术整理：四层参数、记忆模块、训练法与可维护性边界.html) 已写过原则，这里补上了外部那侧的真实量级）。

**④ 关掉 G18 之后，真正还缺的是这些**（已写进补齐清单 rag 板块）：可复现的部署与配置（docker-compose / 索引参数 / 实测 QPS 与 P95）、具名产品与版本（向量库 / Embedding / Reranker / OCR）、真实规模账单与硬件配置、Golden Set 与评测脚本、切块策略的对照实验、以及**把这套架构和 [A008](https://yb.tencent.com/s/8oKggmiksd3U) 企业知识库三档选型对上号**。换句话说：现在有了一张很完整的**架构图**，但还没有一份能照着跑起来的**工程包**。

**⑤ 对后续收录的约定**：以后收到 RAG 实操 / 部署 / 评测 / 向量库选型类资料，按同主题并入 [T049](../principles/千万级%20RAG%20系统架构全景与规模账：从%201000%20万文档到%202%20亿%20Chunks.html)–[T052](../principles/生产保障四层：质量评测、可观测性、索引重建、安全与权限.html) 对应层（不新建重复卡）；收到参数化记忆或外部记忆方案，归 memory 并更新 [T045](../agents/MemT-1.0%20系列技术整理：四层参数、记忆模块、训练法与可维护性边界.html) 的对照；收到 UHP / HarnessRouter 原文，归 mcp 并入 [T053](../agents/跨主题附图：UHP%20·%20HarnessRouter%20想统一%20Agent%20后端的接入方式.html)。每篇都同步回写 [T028](../principles/12%20步路线%20→%20本资料库栏目映射与当前缺口.html) 第 4 步与本页清单。

一句话结论：本库从「Agent / Skill / MCP 偏重、RAG 全空」走到「RAG 两条路线都有整理稿」只用了两篇资料，但**架构知识 ≠ 可复现能力**；下一个该补的是能跑的代码与真实数字，而不是再来一张全景图。

> 整理说明：归纳卡片，非原文观点；缺口判断基于本库截至 2026-11-25 的收录状态，随新资料变化需更新。G18 已由 [A022](https://mp.weixin.qq.com/s/udXF9FEP6SCyeqIxo0YqWA) 关闭并降级，详细清单以「补齐清单」页为准。

## 来源

- A010《不知道AI大模型该怎么学？这篇直接看起来！》 · 2026-11-25 · https://mp.weixin.qq.com/s/lL02F4CnmC-KEkBw8G4dZA
- A020《MemTensor 与 NVIDIA 联合发布记忆原生模型 MemT-1.0-Pro（视频解析稿）》 · 2026-11-25 · http://yb.woa.com/DjfzMFlnxuO
- A022《1000 万份文档，RAG 系统到底怎么扛？》 · 2026-11-25 · https://mp.weixin.qq.com/s/udXF9FEP6SCyeqIxo0YqWA
