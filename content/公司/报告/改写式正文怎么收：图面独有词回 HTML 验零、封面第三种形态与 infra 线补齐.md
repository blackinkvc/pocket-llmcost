---
title: 改写式正文怎么收：图面独有词回 HTML 验零、封面第三种形态与 infra 线补齐
date: 2026-11-20
summary: **① 「正文看着完整」才是最危险的一种**：A031 正文只有 6 句引子，谁都知道要去读图；A032 的 og:description 把四个环节逐条写了一遍、还带图标与「｜」副标题，看起来图里的话正文全有。
tags: 归纳, 改写式正文, 图面独有信息, HTML验零, 资料入库
---
以下为基于 [A032](https://mp.weixin.qq.com/s/c5DlBqp_XiL_HQhjGTf95w) 的归纳延伸：原文没有讨论取证方法。因与 [T074](../companies/Token%20经济全景：词元工厂为枢纽的四环节闭环（图面逐字）.html)（图面事实）、[T075](../companies/「词元工厂」的四种口径：地方产业生态%20vs%20出厂账本%20vs%20企业名单%20vs%20概念四层.html)（口径边界）性质不同 → 并列成卡。

**② 正文改写 ≠ 转述错误，按并列留档**：「调配 / 按需组织资源」「统一提供 / 统一供给」「应用优化 / 应用改进」「提高任务效率 / 任务提效」「数据授权 / 数据底座·授权治理」都不是 OCR 错字，也不是像 [A030](http://yb.woa.com/14N0XXeQcgj) 那样的合成造假，而是**同一内容的两种措辞**。处理沿用 [T016](../apps/图片取证记录：两篇口径冲突与可见边界.html) / [T038](../apps/数字的七类证据性质：演示%20·%20报价%20·%20示意%20·%20可核验计数%20·%20正文未载的图面结果.html) 的口径冲突写法：逐条并列、不校正、不调和、**不用正文替换图面文字**。⚠️ 别顺手把正文里更顺口的那句写进速查表当图面事实。

**③ 封面形态凑齐三种了**：[A013](https://mp.weixin.qq.com/s/vTN1C2sOudQJvDoXD970nA) 有独立 820×820 科技感封面（与正文主图不同图）；[A031](https://mp.weixin.qq.com/s/xgudQE7ZRdteA0TmYpG4ig) 的 `og:image` = `cdn_url` = 正文主图（封面即主图）；[A032](https://mp.weixin.qq.com/s/c5DlBqp_XiL_HQhjGTf95w) 的 `cdn_url` 是 **1086×1086 裁剪方图**，截掉了大标题「Token 经济全景」和底部「价值放大」行，且与 `appmsg_link.cover_url` 是同一文件（md5 全同）。以后图片型资料要先判「独立封面 / 封面即主图 / 封面是主图裁剪」三种，再判主图副本与二次裁剪，**别默认封面一定完整**。

**④ 去重结论第三次不同**：[A022](https://mp.weixin.qq.com/s/udXF9FEP6SCyeqIxo0YqWA) 是「同版式不同页」（9 张长图必须逐张读、不能丢）；[A031](https://mp.weixin.qq.com/s/xgudQE7ZRdteA0TmYpG4ig) 是主图 4 份副本 + 2 张裁剪；[A032](https://mp.weixin.qq.com/s/c5DlBqp_XiL_HQhjGTf95w) 是主图 **3 份副本**（png / 带水印 png / jpeg）+ 方图裁剪 **2 个 URL 同一文件** + 头像 + 占位 = 7 张 → **4 组**。三次都说明：感知哈希 + 像素差两层都得跑，且**水印版要单独读一遍**（[A032](https://mp.weixin.qq.com/s/c5DlBqp_XiL_HQhjGTf95w) 的水印是「公众号 · 人工智能闲笔」，正好补上账号名证据）。

**⑤ 账号名差异又多一型**：[A031](https://mp.weixin.qq.com/s/xgudQE7ZRdteA0TmYpG4ig) 是字序不同（生万物 / 万物生），[A032](https://mp.weixin.qq.com/s/c5DlBqp_XiL_HQhjGTf95w) 是**用字不同**——nick_name / 水印 / 头像「人工智能**闲笔**」，`author`「**ai简笔**」。都不校正、都不替读者选，`author` 也不覆盖 nick_name。另：[A032](https://mp.weixin.qq.com/s/c5DlBqp_XiL_HQhjGTf95w) `source_url` 为空、地点未给、无制图方，但**正文与图都完整**，所以不进 G07 内容待补、不进 G08 视频样本。

**⑥ infra 线从三层变四层，G30 要跟着改**：原 G30 写「[A031](https://mp.weixin.qq.com/s/xgudQE7ZRdteA0TmYpG4ig) 概念分层 / [A013](https://mp.weixin.qq.com/s/vTN1C2sOudQJvDoXD970nA) 企业名单 / [A013](https://mp.weixin.qq.com/s/vTN1C2sOudQJvDoXD970nA) 三本账」三层对照，现在加上 [A032](https://mp.weixin.qq.com/s/c5DlBqp_XiL_HQhjGTf95w)「地方 Token 产业生态闭环」→ 改成**四层对照**，且补一句「词元工厂 = Token 工厂 的中文名，但不推断同一发布方」。新增 G31（改写式正文与图面独有信息的核验清单）、G32（「地方」范围与本地交付的可核验口径）；infra 板块追加 GI08–GI10；G10 / G11 同步（闲笔 / 简笔两种用字、5 处图面独有词、封面裁剪形态）；[T023](../apps/取证记录：二十三批资料的可见边界与补全来源.html) 扩到十六批共 26 条取证；[T038](../apps/数字的七类证据性质：演示%20·%20报价%20·%20示意%20·%20可核验计数%20·%20正文未载的图面结果.html) 结果段补「改写式正文」一类；维护约定第 36 条固化。

一句话结论：这篇作为**产业数据**价值为零（一个可核验数字都没有），但作为**取证样本**补上了本库缺的一型 —— **正文把图改写得很完整、反而更容易漏掉图里半张信息**；收它的意义是立一条硬规矩：图面关键词必须回 HTML 验零，零命中的单独列出来，别让「读起来很全」的正文替你读完那张图。

> 整理说明：归纳卡片，非原文观点；验零命中、并列留档与缺口回写为本库整理方法，不代表公众号或制图方立场。

## 来源

- A013《中国的15家顶级 AI Infra 企业》 · 2026-11-25 · https://mp.weixin.qq.com/s/vTN1C2sOudQJvDoXD970nA
- A022《1000 万份文档，RAG 系统到底怎么扛？》 · 2026-11-25 · https://mp.weixin.qq.com/s/udXF9FEP6SCyeqIxo0YqWA
- A031《一图看懂AI产业链（2026版）》 · 2026-11-25 · https://mp.weixin.qq.com/s/xgudQE7ZRdteA0TmYpG4ig
- A032《一图看懂Token经济的4个关键环节》 · 2026-11-20 · https://mp.weixin.qq.com/s/c5DlBqp_XiL_HQhjGTf95w
