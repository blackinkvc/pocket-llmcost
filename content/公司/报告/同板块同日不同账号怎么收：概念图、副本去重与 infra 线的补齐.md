---
title: 同板块同日不同账号怎么收：概念图、副本去重与 infra 线的补齐
date: 2026-11-25
summary: **① 同板块、同一天、只差 10 小时，也不合并**：A013（AI托肯说，2026-11-25 09:40）与 A031（AI落地-万物生，2026-11-25 19:30）都在 infra 栏目
tags: 归纳, 归类规则, 同板块不同账号, 正文即图片, 资料入库
---
以下为基于 [A031](https://mp.weixin.qq.com/s/xgudQE7ZRdteA0TmYpG4ig) 的归纳延伸：原文没有讨论取证方法。因与 [T071](../companies/一图看懂%20AI%20产业链（2026版）：四层冰山与五类落地场景.html)（图面事实）、[T072](../companies/四层框架的边界：装饰数字、版本标签与「概念分层%20≠%20商业核算」.html)（口径边界）性质不同 → 并列成卡。

**② 去重方向要和 [A022](https://mp.weixin.qq.com/s/udXF9FEP6SCyeqIxo0YqWA) 反着来**：[A022](https://mp.weixin.qq.com/s/udXF9FEP6SCyeqIxo0YqWA) 的 9 张长图是「**同版式不同页**」，aHash 会误判成同组，必须再跑像素差、逐张读完、不能丢；[A031](https://mp.weixin.qq.com/s/xgudQE7ZRdteA0TmYpG4ig) 是「**同一张图的 4 份副本**」（jpeg / png / 带水印 png / 压缩 jpeg，像素差 0.15–1.36），dhash 反而因压缩差了几位，逐张确认内容全同后**按一组计数**。两次都说明：**感知哈希 + 像素差两层都得跑，但结论可能相反**，不能只看哈希分组就决定留几张。裁剪副本（方图截到 Agent 层、横图截到 Token 层）按 [A013](https://mp.weixin.qq.com/s/vTN1C2sOudQJvDoXD970nA) 三层法归入「头像 / 占位 / 裁剪」，不重复计数。

**③ 封面形态又多一型**：[A013](https://mp.weixin.qq.com/s/vTN1C2sOudQJvDoXD970nA) 有独立 820×820 科技感封面，[A022](https://mp.weixin.qq.com/s/udXF9FEP6SCyeqIxo0YqWA) 有封面全景 + 4 份副本，[A031](https://mp.weixin.qq.com/s/xgudQE7ZRdteA0TmYpG4ig) 则是 `og:image` = `cdn_url` = 正文主图，**封面即主图、没有单独封面**。以后图片型资料要先判「封面 / 正文图 / 裁剪 / 头像占位」四层，别默认一定存在独立封面。

**④ 账号名多写法要并列**：图上胶囊「AI落地-生万物」、图脚水印「公众号 · AI落地-万物生」、页面 nick_name「AI落地-万物生」三种字序；`author` 为空、`source_url` 为空、地点未给。沿用 [A021](https://xhslink.cn/o/29yppgYjLUn) 的处理（作者名两种写法并列），不校正、不替读者选，也不拿 nick_name 去覆盖图面文字。

**⑤ infra 线现在有三层框架了**：概念分层（[A031](https://mp.weixin.qq.com/s/xgudQE7ZRdteA0TmYpG4ig)）／企业名单（[A013](https://mp.weixin.qq.com/s/vTN1C2sOudQJvDoXD970nA) → [T033](../companies/中国%2015%20家%20AI%20Infra%20企业：五大技术阵营、产品标签与五大商业方向.html)）／商业核算（[A013](https://mp.weixin.qq.com/s/vTN1C2sOudQJvDoXD970nA) → [T034](../companies/页面附载的跨主题图组：Token%20工厂「五站销路%20·%20渠道矩阵%20·%20三本账」.html)）。缺的是把三者**摆在一起对照**的一份东西：同一个 Token 在三层里分别是什么、同一家公司在哪一层被点到、四层里哪几层在库里还没有可核验的数值。新增 G30 挂这个缺口；GI05–GI07 补「概念图的来源与版本依据」「四层的可核验数值」「概念图 ↔ 企业名单 ↔ 三本账对照表」。

**⑥ 缺口回写**：新增 **G29**（概念框架图的数据来源、版本依据与制图方）、**G30**（infra 三层框架对照）；infra 板块追加 GI05–GI07；G10 / G11 同步（账号名三种写法、author 为空、00123 装饰数字、2026 版无依据）；[T023](../apps/取证记录：二十三批资料的可见边界与补全来源.html) 扩到十五批共 25 条取证；[T038](../apps/数字的七类证据性质：演示%20·%20报价%20·%20示意%20·%20可核验计数%20·%20正文未载的图面结果.html) 结果段补「装饰数字 / 版本标签」一类；维护约定第 35 条固化「一图看懂」类收法。⚠️ [A031](https://mp.weixin.qq.com/s/xgudQE7ZRdteA0TmYpG4ig) 正文与图都完整，**不进 G07 内容待补、也不进 G08 视频样本**。

一句话结论：这篇作为**产业数据**价值为零（一个可核验数字都没有），但作为**框架样本**补上了 infra 栏目缺的一层——「概念速览」；收它的意义是把「科普图 / 企业盘点 / 商业账本」三种东西分开摆好，免得以后拿一张冰山图去回答「谁在赚钱」。

> 整理说明：归纳卡片，非原文观点；并列规则、去重方向与缺口回写为本库整理方法，不代表公众号或制图方立场。

## 来源

- A013《中国的15家顶级 AI Infra 企业》 · 2026-11-25 · https://mp.weixin.qq.com/s/vTN1C2sOudQJvDoXD970nA
- A022《1000 万份文档，RAG 系统到底怎么扛？》 · 2026-11-25 · https://mp.weixin.qq.com/s/udXF9FEP6SCyeqIxo0YqWA
- A025《十个热门 Skills，价值要放回具体任务看（GitHub Skills 飙升榜 TOP 10）》 · 2026-11-26 · https://mp.weixin.qq.com/s/6SkEqqZzXKECkn1gHRnnfQ
- A031《一图看懂AI产业链（2026版）》 · 2026-11-25 · https://mp.weixin.qq.com/s/xgudQE7ZRdteA0TmYpG4ig
