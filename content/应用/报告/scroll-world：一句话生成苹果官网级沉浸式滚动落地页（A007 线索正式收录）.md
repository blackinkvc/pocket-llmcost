---
title: scroll-world：一句话生成苹果官网级沉浸式滚动落地页（A007 线索正式收录）
date: 2026-11-25
summary: 公众号「青鱼学AI」（meta author 同名，user_name gh_6359b1690954），发布于 2026-11-24 18:26，标题《AI 时代如何做苹果官网级别的沉浸式落地页》。
tags: scroll-world, 3D网页, AI Agent 技能, 帧锁定, 资料入库
---
**归位说明（重要）**：这正是 [A007](https://m.bilibili.com/video/BV1C5yXzUEXx?-Arouter=story&buvid=XX2353E2D26B8BEBF3F706AE92650CEEF0D13&from_spmid=main.ugc-video-detail-vertical.0.0&is_story_h5=true&mid=V8WXIlSc0stuHT2m%2FUNOmA%3D%3D&p=1&plat_id=143&share_from=ugc&share_medium=android&share_plat=android&share_session_id=0211ab0e-7ef4-4549-90c4-896ae7bd5312&share_source=WEIXIN&share_tag=s_i&spmid=main.ugc-video-detail-verticalspace.0.0&timestamp=1795526321&unique_k=OcI8VmN&up_id=3546829037766974) 视频卡 [T017](../apps/让%20AI%20把%203D%20网页特效改成品牌色：页面可见信息与待核实线索.html) 里第 ③ 条「scroll-world 开源方案」外部线索。现在你发来链接，它作为独立资料正式落进「实例 › 3D · 创意网页」子栏目，同时挂 Skill（AI Agent 技能）/ Agent / 实例。但**这不等于确认视频讲的就是它**：视频标题是「把现成 3D 网页特效改成品牌色」，本文是「一句话生成滚动式 3D 世界落地页」，主题相邻不等价；[T017](../apps/让%20AI%20把%203D%20网页特效改成品牌色：页面可见信息与待核实线索.html) 的可见信息、留白与「内容待补」状态一律不动。

五页逐页整理（图面信息全量，不放原文）：

- 01/05 封面：「AI 时代，做一个苹果官网级别的沉浸式落地页」；scroll-world · **开源三个月拿下 11.1k Star**；Claude Code 直接装 / MIT 免费商用；画面是等距微缩城市夜景
- 02/05 以前请团队，现在一句话：传统做法「专业团队：3D 建模 · 动画 · 剪辑 · 前端，六位数起，周期按月算」vs scroll-world「一次 AI 对话：访谈 → 生成 → 组装，全自动，≈$27 素材成本，当天出页面」；效果同源：Apple 发布页的滚动叙事 + Emons 官网的微缩世界，一镜到底
- 03/05 AI 视频拼接必跳帧？帧锁定治好了它：① 每段 AI 视频都是独立渲染（同一提示词生成两次，像素也不一致，硬拼必「跳一下」）② 抽出相邻视频的真实首尾帧（用 ffmpeg 从成片里取，绝不用原始静帧图）③ 过渡片段以真实帧为起点终点（AI 只负责生成中间的过渡过程）④ 接缝像素级一致（再叠几帧交叉淡化兜底，观众完全看不出拼接）；页脚一句「宁可不用，不出废品：做不到帧锁定的模型，直接被拒绝进链」
- 04/05 聊聊钱，素材成本明明白白：俯冲视频·8 秒 $2.99（1080p · **Seedance 2.0**）；过渡视频·5 秒 $1.87（1080p · 按量计费）；6 场景全链 ≈$27（6 段俯冲 + 5 段过渡）；720p 版 ≈$11（性价比之选）；「先报价，后花钱：Agent 实测单价报总额，你批准了才生成」（预算审批）；页脚 scroll-world 04/05
- 05/05 上手 · 三步装好就能用：① 装插件 `/plugin marketplace add oso95/scroll-world` ② 说一句话「给我的奶茶店做一个滚动式 3D 世界落地页」③ 确认预算，等生成（静帧 + 视频链 + 滚动引擎，整站交付）；github.com/oso95/scroll-world；MIT 协议 · 30 美元上下做出一个成品页；FOLLOW · 评论区聊聊你想做什么世界

纯文字摘要补充了图里没有的工程细节（按原文整理）：工作方式像一支乙方团队——先访谈确定主题、品牌色、美术方向、镜头风格和 **5-7 个场景的动线** → 调度 AI 图像模型生成风格统一的**等距微缩世界静帧** → 用图生视频模型生成每段「俯冲进入」和场景间「过渡衔接」镜头 → 配上一个 **448 行、零依赖的滚动引擎**把整站装配成可直接上线的网页，**不绑定任何前端框架**；灵魂技术「帧锁定」首尾帧取自相邻视频真实渲染帧、接缝像素级一致；还解决了移动端竖屏适配、iOS 白屏、快滑冻结等工程坑；成本 6 场景 1080p 全链约 27-30 美元、720p 约 11 美元、支持先花 **3 美元跑 480p 草稿的预览模式**；GitHub 地址 https://github.com/oso95/scroll-world。

⚠️ 成本口径并列不调和：图 02/05 与 04/05 写「≈$27」、05/05 写「30 美元上下」、文字版写「27-30 美元」，都是约数；3 美元 480p 预览只在文字版出现、图面无。「六位数报价的商业方案」没有具体参照对象。

⚠️ 原文没给、一律不补：Star 数与 MIT 许可未去 GitHub 核实；Seedance 2.0 的厂商、单价来源与是否含其他费用未说明；448 行滚动引擎的文件名 / 实现细节未展开（[T017](../apps/让%20AI%20把%203D%20网页特效改成品牌色：页面可见信息与待核实线索.html) 线索里提到的 scrub-engine.js 与本文未对照）；「5-7 个场景」与成本表里的「6 场景」未解释关系；示例句里的奶茶店是演示主题不是落地案例；没有真实客户、上线页面 URL 或效果数据。

与本库其他卡的互照：[T021](../agents/Unity%20MCP：把%20MCP%20从「连工具」推到「直接操作游戏引擎」.html) 的 Unity MCP、[T022](../agents/Game%20Dev%20Agent%20Skills：74%20个技能包把三大引擎交给%20AI.html) 的 Game Dev Agent Skills 都是「把 AI 接进创作工具」，scroll-world 是「把创作流程整体交给 Agent 编排」；[T017](../apps/让%20AI%20把%203D%20网页特效改成品牌色：页面可见信息与待核实线索.html) 的视频线索、本卡的独立资料、P36 的待核实条目三者并存，正好演示了「线索 → 独立收录 → 仍不冒充原视频内容」这条链。

> 整理说明：[A007](https://m.bilibili.com/video/BV1C5yXzUEXx?-Arouter=story&buvid=XX2353E2D26B8BEBF3F706AE92650CEEF0D13&from_spmid=main.ugc-video-detail-vertical.0.0&is_story_h5=true&mid=V8WXIlSc0stuHT2m%2FUNOmA%3D%3D&p=1&plat_id=143&share_from=ugc&share_medium=android&share_plat=android&share_session_id=0211ab0e-7ef4-4549-90c4-896ae7bd5312&share_source=WEIXIN&share_tag=s_i&spmid=main.ugc-video-detail-verticalspace.0.0&timestamp=1795526321&unique_k=OcI8VmN&up_id=3546829037766974) 的第 ③ 条线索升级为独立台账，但视频内容未据此改写；成本三种约数并列。图面信息已并入速查表 P85–P86。

## 来源

- A015《AI 时代如何做苹果官网级别的沉浸式落地页（scroll-world）》 · 2026-11-25 · https://mp.weixin.qq.com/s/_DI8rxczyjpas4362-Ub9Q
