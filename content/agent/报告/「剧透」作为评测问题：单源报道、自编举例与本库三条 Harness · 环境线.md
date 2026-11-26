---
title: 「剧透」作为评测问题：单源报道、自编举例与本库三条 Harness / 环境线
date: 2026-11-25
summary: **② 证据等级怎么定**：一手是**公司官方公告 + 工程文档 + 可试用的 API/MCP**，比 A023（PNAS 论文 + 公开代码）软、比 A018（纯官宣无代码）硬；
tags: 归纳, 转述链, 数据泄漏, 回放评测, 资料入库
---
以下为基于 [A024](http://yb.woa.com/4AK3r0d8UHO) 的归纳延伸：视频与解析稿没有讨论取证方法。因与 [T058](../agents/Epochal%20·%20时光门户：视频六场景%20×%20一手口径逐条对照.html)（事实对照）、[T059](../agents/一手口径：Time%20Portal%20怎么防剧透，以及「0.98」到底量了什么.html)（一手口径）性质不同 → 并列成卡。

**① 这批又添两类新偏差**（[T046](../apps/带时间轴的视频自动解析稿：四类错乱与怎么标证据等级.html) 四类之外）：

- **单源报道写成事实**：「1 亿美元」是 Bloomberg 引匿名知情人士 + 公司不置评；到视频里变成「自掏腰包投资」的确定叙述。以后遇到金额 / 融资 / 估值，必须写明「谁报的、引谁的话、官方认不认」，不能只抄数字
- **自编举例替代官方实验**：解析稿用「拨回 2008 年金融危机前夕」讲机制，读起来完全合理，但一手公开示例是 1995/1997 年国际象棋，正式自测是 347 题 + 0.98。**举例不落在专名 / 数字 / 语义 / 机构名单任何一类，却悄悄换掉了证据本身**。核对时要问一句：这个例子在官方材料里出现过吗？

**③ 「剧透」与本库三条线**：[A023](http://yb.woa.com/HvYlY3lwbsr) 的 MIT 气候论文说「**训练数据本身可能是泛化天花板**」；[A024](http://yb.woa.com/4AK3r0d8UHO) 说「**训练数据里已经写好了结局**，所以预测能力练不出来」；[A022](https://mp.weixin.qq.com/s/udXF9FEP6SCyeqIxo0YqWA) 的 RAG 工程说「**权限过滤要尽早做，不要等内容进了 Prompt 再删**」。三者都在处理同一件事——**信息该在什么条件下、以什么顺序供给模型**。以后收到「数据泄漏 / 回溯测试 / 时间点基准 / 防 hindsight」类资料，可在这三卡下挂 related，不必新开栏目。

**④ 与既有 Harness / 环境卡的互照**：[T031](../agents/DeepSeek%20Harness（dsh）两个月重度实测：迁移决策、五页图全量与对比数字.html)（[A012](https://mp.weixin.qq.com/s/A2fnlab0SoLoAGQJwlmZyg)）是**个人重度实测**一个编码 Harness；[T053](../agents/跨主题附图：UHP%20·%20HarnessRouter%20想统一%20Agent%20后端的接入方式.html)（[A022](https://mp.weixin.qq.com/s/udXF9FEP6SCyeqIxo0YqWA) 跨主题附图）是**统一接入多个 Harness 的概念**（UHP / HarnessRouter，尚无规范与仓库）；[A026](https://mp.weixin.qq.com/s/TUMmu9eeJyEaWsitwfCMmQ) / [A027](https://mp.weixin.qq.com/s/gJJJaFpsDD2m3qlXGMcxvA) 本批补上 DSH 的**插件生态**；[A024](http://yb.woa.com/4AK3r0d8UHO) 的 Time Portal 是**给智能体套一层冻结了时间的运行环境**。四者分别是「用 / 接 / 装 / 圈」，层次不同，恰好把「Agent 运行环境」这条线补成了一串。别把 UHP 当成 Time Portal 的一部分，也别把 DSH 插件当成 Epochal 产品。

**⑤ 缺口回写**：新增 **G23**（Epochal 官网公告 / 工程文档 / Bloomberg 原文未正式收录），agent 板块追加 GA 系列待补（347 题清单与独立复现、归档数据授权、参数化泄漏的处理办法、训练截止日之后题目的准确率）；G07 内容待补 10 → 11、G08 视频 4 → 5，G10 / G11 同步。维护约定第 32 条固化「单源报道标信源 + 举例回一手查 + 同批多链接逐条判主题」。

一句话结论：这条视频作为**产品资料**信息不全（漏了 7 万亿 URL、三 API、347 题与全部边界），但作为**样本**很典型——它演示了「单源融资数字被写成事实」「一个顺口的例子把官方实验整个替换掉」两种新污染。收进来不是因为「AI 已经能预测未来」，而是因为本库需要一条「**宣传口径 → 官方文档 → 自测口径 → 未验证边界**」四层拆开的案例。

> 整理说明：归纳卡片，非原文观点；分类与规则为本库整理方法，不代表 Epochal、视频作者或转述媒体立场。

## 来源

- A012《我宣布 DSH 已经彻底甩开 Claude code 了》 · 2026-11-25 · https://mp.weixin.qq.com/s/A2fnlab0SoLoAGQJwlmZyg
- A022《1000 万份文档，RAG 系统到底怎么扛？》 · 2026-11-25 · https://mp.weixin.qq.com/s/udXF9FEP6SCyeqIxo0YqWA
- A023《「MIT神操作」假数据训练 AI 气候模型（视频解析稿）》 · 2026-11-25 · http://yb.woa.com/HvYlY3lwbsr
- A024《Epochal 公司及其「预测未来」AI 项目解析（时光门户 Time Portal）》 · 2026-11-26 · http://yb.woa.com/4AK3r0d8UHO
