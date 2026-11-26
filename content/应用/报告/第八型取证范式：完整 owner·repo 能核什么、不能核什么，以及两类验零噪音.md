---
title: 第八型取证范式：完整 owner/repo 能核什么、不能核什么，以及两类验零噪音
date: 2026-09-03
summary: **① 八型齐了，这次是「一句正文」的极限**：og:description 与 content_noencode 都只有 **1 句 100 字符**（A035 是 933 字符、A034 是 18400 字藏在
tags: 归纳, 第八型, 一句正文, 多页成对水印长图, 资料入库
---
以下为基于 [A037](https://mp.weixin.qq.com/s/QQbMio_My7u1i_ladamVkw) 的归纳延伸：原文没有讨论取证与归类方法。因与 [T089](../agents/Archify：一句正文、三页长图与「让%20Agent%20出数据、程序画图」的分工.html)（事实）、[T090](../agents/39,284%20→%2062.9k%20·%206.7万%20→%2095.4k.html)（口径边界）性质不同 → 并列成卡，归 case（与 [T023](../apps/取证记录：二十三批资料的可见边界与补全来源.html) / [T038](../apps/数字的七类证据性质：演示%20·%20报价%20·%20示意%20·%20可核验计数%20·%20正文未载的图面结果.html) / [T085](../apps/同号同系列第二条怎么收：按主用途分栏、搜索词不算仓库、演示数值单列.html) / [T088](../apps/第七型取证范式：有一手页时怎么收、核实成功也不能把全表升格.html) 同栏目讲取证方法）。

**② 完整 owner/repo 改变了「能不能核」，但没改变「核到了什么」**：[A035](https://mp.weixin.qq.com/s/yjAqx2IHAhFewtkBdpI8zw) 只有搜索词 + 作者名 → 不拼 URL、不回一手核实。[A037](https://mp.weixin.qq.com/s/QQbMio_My7u1i_ladamVkw) 给的是 **`tt-a1i/archify`**，按 [A036](https://mp.weixin.qq.com/s/o_C93hkiSzFeap_0YyfXKg) 之后的新范式回一手核实 → **GitHub 仓库真实存在**（95.4k stars / Apache-2.0 / archify.si / 1,762 commits）。⚠️ 但**核实范围只到「仓库存在 + 当前状态」**：图面 39,284 Stars / 本周 +22,095 / 2026.09.01 快照、P1 架构示意、P3 三张演示界面**一个都没核上**。GitHub 当前 95.4k 与 9-01 的 39,284 时点不同，既不能证也不能证伪。**仓库存在 ≠ 快照已核** —— 这是 [A036](https://mp.weixin.qq.com/s/o_C93hkiSzFeap_0YyfXKg)「核实成功也不把全表升格」在单项目场景的翻版。

**③ Star 数第一次能排成时间序列**：39,284（2026.09.01 图面）→ 62.9k（quibbler）→ 6.7 万（youtol）→ 95.4k（GitHub 当前）。四个口径**并列不调和、只追加不覆盖、不取平均、不写成规格**（呼应 GSK06 / GS04 / [A028](https://mp.weixin.qq.com/s/tEwu2LbeQiSij2Sz_CN8Tw)）。⚠️ 与 [T061](../agents/GitHub%20Skills%20本周飙升榜%20TOP%2010：热度是入口，价值要放回具体任务.html) / [A025](https://mp.weixin.qq.com/s/6SkEqqZzXKECkn1gHRnnfQ)（2026-11-06 近 7 日增长榜，最高 +10.1k）也是**不同期、口径相近**的并列关系；不拿 +22,095 去补榜单，也不拿榜单去质疑它。**[A025](https://mp.weixin.qq.com/s/6SkEqqZzXKECkn1gHRnnfQ) / [T061](../agents/GitHub%20Skills%20本周飙升榜%20TOP%2010：热度是入口，价值要放回具体任务.html) / GS04 / GSK06 一条都不回改** —— [A037](https://mp.weixin.qq.com/s/QQbMio_My7u1i_ladamVkw) 是「第一次给单个 Skill 项目补上可点的一手仓库」，但**仍不是榜单多期快照**。

**④ 验零噪音凑齐两类**：[A036](https://mp.weixin.qq.com/s/o_C93hkiSzFeap_0YyfXKg) 发现「83.33」命中 10 次全是 **SVG path 圆弧坐标**；[A037](https://mp.weixin.qq.com/s/QQbMio_My7u1i_ladamVkw) 发现 `Dark`(24) / `Live`(9) / `Export`(12) / `API`(401) 命中全是**微信页面 JS 框架变量名 / 函数名**（`iconTopSimplifyUrlDark` / `setLivePlaceHolder` / `wapExportToken` / `JSAPIEventCallbackMap`），不是图面按钮文字。⚠️ 加上 [A035](https://mp.weixin.qq.com/s/yjAqx2IHAhFewtkBdpI8zw)「别把正文词误列进验零清单」，验零现在有三条硬规矩：**数字/英文命中先看上下文、反向词别误列、框架变量与样式坐标不算正文**。另「类型化 JSON / 架构图 / 可交互」正文里就有（6/5/6 次），不是图面独有。

**⑤ 每页成对水印长图要两版都读**：11 张去重 7 组，三页 1024×1536 长图**各带一份无水印 + 一份带「公众号 · AI情报库」水印**（差 0.19 / 0.21 / 0.20）→ 沿用 [A033](https://mp.weixin.qq.com/s/ryLsLKE6YTtK7nMQLjdMqQ) 的「无水印读内容、水印版补号名」。⚠️ 与 [A032](https://mp.weixin.qq.com/s/c5DlBqp_XiL_HQhjGTf95w)/[A034](https://mp.weixin.qq.com/s/iMnx_LuS2x5Znk2MkhdjTg)/[A035](https://mp.weixin.qq.com/s/yjAqx2IHAhFewtkBdpI8zw)/[A036](https://mp.weixin.qq.com/s/o_C93hkiSzFeap_0YyfXKg) 的「同一主图多份副本」不同：这是**三张不同内容的页各带一份水印**，不能按「主图副本」合并成一组。另第 1 页还有 1024×1365 裁剪版 ×2（完全同 md5，`og:image` 用它）与 1024×1024 方裁，**都会截掉标题或底部五类图行**，不能当完整页用（呼应 [A036](https://mp.weixin.qq.com/s/o_C93hkiSzFeap_0YyfXKg)「裁剪版不能当主证据」）。

**⑥ 图内嵌界面沿用 [A035](https://mp.weixin.qq.com/s/yjAqx2IHAhFewtkBdpI8zw) 的「演示数据」**：P1 架构示意（Auth Service / API Service / Event Bus / PostgreSQL…）与 P3 三张小图（Cache Miss Request Sequence / Production Deployment Ownership / Agent Tool Call Workflow）都是**示例产物截图**，不是真实系统拓扑、不是项目实测。⚠️ 与 [A030](http://yb.woa.com/14N0XXeQcgj)「合成演示终端 / 假命令」也不同：那次是**画面本身被造出来**，这次是**正常的产品界面示例**，别套「命令 / 仓库 / 依赖名逐条回一手」的流程。图面「边界：它验证图中声明，不替代运行时监控」是作者自述，不是本库结论。

**⑦ 归类与旧卡边界**：归 **skill** 主板块（可复用能力单元），related 挂 agent / case / roadmap，**不新建栏目**（沿用 [A030](http://yb.woa.com/14N0XXeQcgj) 起的克制）；不因为产物是可交互 HTML 就进模板库，也不因为图里画了系统拓扑就归 infra / case 主板块。⚠️ GS04 / GSK06 的「一手页与多期快照」**仍未补上**：本条只有一个项目的一个仓库页，不是榜单多期序列；只在 G41 / G42 记进展，旧卡文字不动。

**⑧ 缺口回写**：[T023](../apps/取证记录：二十三批资料的可见边界与补全来源.html) 扩到二十一批共 31 条取证；[T038](../apps/数字的七类证据性质：演示%20·%20报价%20·%20示意%20·%20可核验计数%20·%20正文未载的图面结果.html) 结果段补「一句正文 / 完整 owner/repo / Star 时间序列 / JS 框架变量验零噪音」；新增 **G41**（2026-09-01 图面 39,284 快照与 +22,095 周增长、榜单原页链接与抓取时间、多期快照）、**G42**（Archify 安装 / 校验 / 五类图的本库自跑验证，以及 archify.dev ↔ archify.si ↔ 仓库地址、MIT ↔ Apache-2.0 的口径对照）；skill 板块补 **GSK07 / GSK08**；G10 / G11 同步（缺「这」字、Star 四口径、域名三写、许可两写、0 标签、10002、最早发布）；维护约定第 41 条固化。⚠️ 页面与 11 张图都完整，**不进 G07 内容待补、不进 G08 视频样本**。

一句话结论：这条把库的取证又推了一格 —— **从「有没有一手页」到「一手页能核到哪一层」**。完整 owner/repo 让仓库存在可被证实，但图面那个 39,284 仍只是 9-01 的快照。最容易被漏的不是摘要太短，而是**核到仓库之后，顺手把图上的 Star 数也当成已核实**。

> 整理说明：归纳卡片，非原文观点；八型划分、核实范围界定、Star 时间序列与两类验零噪音为本库整理方法，不代表 GitHub、公众号或任一第三方站点立场。

## 来源

- A025《十个热门 Skills，价值要放回具体任务看（GitHub Skills 飙升榜 TOP 10）》 · 2026-11-26 · https://mp.weixin.qq.com/s/6SkEqqZzXKECkn1gHRnnfQ
- A028《麦田：多平台发布｜免费开源（补 A014 的仓库 / 协议 / Star 与运行条件）》 · 2026-11-26 · https://mp.weixin.qq.com/s/tEwu2LbeQiSij2Sz_CN8Tw
- A033《Vibe Coding必看，别再让AI凭感觉做动效了（8 个高级动效网站）》 · 2026-09-07 · https://mp.weixin.qq.com/s/ryLsLKE6YTtK7nMQLjdMqQ
- A034《大模型时代的本体与知识图谱关系与区别》 · 2026-11-25 · https://mp.weixin.qq.com/s/iMnx_LuS2x5Znk2MkhdjTg
- A035《Cleanzo 安全清理｜免费开源》 · 2026-11-22 · https://mp.weixin.qq.com/s/yjAqx2IHAhFewtkBdpI8zw
- A036《全球超算TOP10：第一名相当于183万张B300》 · 2026-11-17 · https://mp.weixin.qq.com/s/o_C93hkiSzFeap_0YyfXKg
- A037《Archify Skill会验架构图》 · 2026-09-03 · https://mp.weixin.qq.com/s/QQbMio_My7u1i_ladamVkw
