---
title: 产品演示视频怎么收：cad 栏目破零、DSH 线接上、以及厂商自述的边界
date: 2026-11-24
summary: **① 这条是「能查到一手、且基本对得上」的一型，和前两条不同**：A023 是一手论文把视频文案几乎全推翻，A024 是单源报道 + 自编举例，A029 则是**厂商官网 / 手册 / 活动回顾都能查到
tags: 归纳, 归类规则, CAD, 厂商自述, 资料入库
---
以下为基于 [A029](http://yb.woa.com/3x1QBfsbpa6) 的归纳延伸：视频与解析稿都没有讨论取证方法。因与 [T065](../apps/DPE%20数字样机：视频三场景%20×%20厂商一手材料逐条对照.html)（事实对照）、[T066](../apps/一手口径：DPE%20到底做什么、哪些数字只是厂商快照.html)（一手口径）性质不同 → 并列成卡。

**② cad 栏目终于有了第二条**：[T010](../apps/CAD%20子栏目：归集范围与后续整理约定.html) 建栏目时只有 [A003](https://mp.weixin.qq.com/s/Jc-MFavK3WVRkDTjTLMT6Q)（六个开源 CAD 项目），GCAD01 挂了很久「需要更多 CAD + AI 项目」。[A029](http://yb.woa.com/3x1QBfsbpa6) 补上的是**国产商业 Web3D 数字样机**这一型——与 [A003](https://mp.weixin.qq.com/s/Jc-MFavK3WVRkDTjTLMT6Q) 的开源 MCP / Skill 工具链正好两端（开源桌面插件 vs 商业浏览器平台）。GCAD01 从「只有一条」降级为「已有两条，仍缺 AutoCAD / 浩辰 / 中望之外的引擎与图纸审查案例」；**GCAD02 不降级**：这次案例虽多，但全部脱敏、无真实图纸与验收标准，仍缺工程边界复盘。

**③ 本库两条独立线第一次接上**：[A026](https://mp.weixin.qq.com/s/TUMmu9eeJyEaWsitwfCMmQ)（DSH 必装 10 插件）/ [A027](https://mp.weixin.qq.com/s/gJJJaFpsDD2m3qlXGMcxvA)（只装 4 个）讲的是 DeepSeek Harness 的插件生态，[A029](http://yb.woa.com/3x1QBfsbpa6) 的一手报道明写 **DPE 接入 WorkBuddy 与 DeepSeek Harness，拆装动画 / 剖切 / 交互课件可封装为 DSH 插件**，WorkBuddy 与 DSH 用户用的是同一套 DPE 能力内核、只是运行时不同。⚠️ 但**不能据此把 DPE 写成 DSH 插件**、也不能把 DSH 插件清单回改成 DPE 功能——一边是运行时插件生态，一边是被接入的工业平台，层次不同，只在 related 与速查里挂接。[T053](../agents/跨主题附图：UHP%20·%20HarnessRouter%20想统一%20Agent%20后端的接入方式.html) 的 UHP / HarnessRouter 想统一的是「产品后端 ↔ 多 Harness」，又比这两者高一层。

**④ 「自研」与「外挂」要分开写**：产品文反复强调「纯国产自研三维渲染内核 / 模型解析算法 / 流形布尔引擎」，但官方直播课明说图生 3D 接的是 Tripo、Hyper3D 这类生成服务。本库的处理是**逐能力标来源**：渲染内核、STP 解析、遮挡排序写「自研」，图生 3D 写「接外部生成服务」，不因为整篇宣传「国产自研」就把每个能力都算成自研。以后收到同类产品演示，沿用这条。

**⑤ 证据等级与缺口回写**：写「厂商官方材料可查 · 全为发布方自述，缺第三方独立评测与真实工程验收」。新增 **G26**（官网 / 手册 / API 清单 / 试用环境未正式收录），cad 板块追加 GCAD03–GCAD05（独立复现与真实图纸验收、API/MCP 清单与版本对照、脱敏案例背后的真实项目口径）；G07 内容待补 11 → 12、G08 视频 5 → 6，G10 / G11 同步；维护约定第 33 条固化产品演示类规则。

一句话结论：这条视频作为**产品资料**信息不全（没给厂商、没给版本、图表数值取不到），但作为**样本**补上了本库缺的一型——**商业工业软件的产品演示稿怎么拆**：先回官网 / 手册确认功能，再把「高还原度」「强大能力」这类话术降级，把外挂服务、商业授权、脱敏案例和厂商自述数字全部标清，最后留一条「缺独立复现」的口子。

> 整理说明：归纳卡片，非原文观点；归类、互照与规则为本库整理方法，不代表厂商、视频作者或转述媒体立场。

## 来源

- A003《六个 CAD Skill，装完就能直接画!》 · 2026-11-24 · https://mp.weixin.qq.com/s/Jc-MFavK3WVRkDTjTLMT6Q
- A026《DeepSeek Harness必装10大插件，早装早享受》 · 2026-11-26 · https://mp.weixin.qq.com/s/TUMmu9eeJyEaWsitwfCMmQ
- A027《DSH 装 4 个插件（再装就是给每次对话加税）》 · 2026-11-26 · https://mp.weixin.qq.com/s/gJJJaFpsDD2m3qlXGMcxvA
- A029《DPE 数字样机工具演示（照片转 3D、四轴协同拧紧工作站）》 · 2026-11-26 · http://yb.woa.com/3x1QBfsbpa6
