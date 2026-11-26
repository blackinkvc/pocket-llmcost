---
title: H01 · Anthropic 把 Messages API 从 Python 移植到 Rust：40%–50% 与 70% 并列
date: 2026-11-26
summary: **归类决定**：视频归「**实例**」主板块（工程复盘），related 挂 agent / model / infra / ai4s，**不新建栏目**；
tags: Anthropic, Claude, Messages API, Python→Rust, 资料入库
---
**页面 / 视频可见信息**：短链 http://yb.woa.com/8Abur0ylFHZ ，11 秒，用户附「【视频解析内容-模型总结信息】」自动解析稿；**视频本体、逐帧画面、字幕、封面、发布账号、发布日期、地点、互动数字全部取不到** → 标「内容待补」+「非逐帧取证」（同 [A020](http://yb.woa.com/DjfzMFlnxuO) / [A023](http://yb.woa.com/HvYlY3lwbsr) / [A024](http://yb.woa.com/4AK3r0d8UHO) / [A030](http://yb.woa.com/14N0XXeQcgj)）。解析稿 5 段按原样全量留档：标题「CPU直降70%，全程零停机」+ 图表左列「Anthropic Messages API / Zero downtime / Python -> Rust」+ CPU 下降折线图；00:02–00:04 推特评论「that's incredible」+ X.com；00:04–00:06 三个无标签柱状图「90万」「200+」「15万」；00:06–00:08 Action 1（AOT 编译器和内存管理）/ Action 2（服务分离和无状态业务逻辑）/ Action 3（重构语言层 (A) & 核心 DSL）/ Action 4（引入新的编译器和运行时）；00:08–00:11 文案「打满1800亿参数模型、完成端到端增量训练、智能体插件支持」+「AI 三个痛点：算力消耗大、成本高昂、AI 行业标准缺失」。

**一手已证实（外部，单列不并入解析稿）**：InfoQ / 新浪财经 2026-10-29 转述 Anthropic 平台工程负责人 **Katelyn Lesse** 的 X 长文（10-26）与 Latent Space 播客（10-27）—— 团队原本没有 Rust 工程师，因 Python 单体 CPU 效率低、CPU 容量需提前规划，借 Claude 把 **Messages API 移植到 Rust**；**CPU 资源消耗减少约 40%–50%**、**首 Token 延迟改善约 10%–20%**（更长工作负载改善更大）；用 **Shadow Traffic 影子流量**让 Python / Rust 两套实现处理等价请求、对比输出后逐步切流；刻意不新增功能，Katelyn 称其为「移植（Port）」；人类定系统架构、迁移策略与验证，Claude 承担代码实现。同期长文另提四类新工程问题（成千上万 Agent 调度、身份认证 vs 授权与 OBO、提示词注入爆炸半径与「大脑 / 双手」分离、Kill Switch 与 OTel 跨 Agent 追踪），单列不并入数字口径。

**媒体转述层（非一手）**：网易号 2026-11-25 给「每请求 CPU 骤减约 **70%**、内存狂降超 **80%**、中位数 TTFT 缩短约 **20%**、全程零停机、不冻结新功能；2026 年 5 月合并代码 >80% 由 Claude 编写；Claude 一周写出初稿」。工程难点：700+ 集成测试与 Python 耦合、断言被削弱；20 个二元选项 > 百万组合；模型输出非确定性；隐私限制不能看客户真实请求。解法「单次推理、双端比对」+ Checkpointing / Fingerprinting + 三重验证循环（Inner / Outer / Memory Loop）+ 忒修斯之船。⚠️ 这是自媒体转述，不是 Anthropic 官方工程博客。

⚠️ **口径冲突并列不调和**：① **CPU 40%–50%（一手访谈）vs 70%（自媒体 / 视频标题）** —— 不取平均、不覆盖成「最新」（同 [A037](https://mp.weixin.qq.com/s/QQbMio_My7u1i_ladamVkw) Star 四口径、[A039](https://mp.weixin.qq.com/s/tESp7Od1YgtSHT9tEPLK2w) 两期跨口径）；② 内存 >80% 一手未提；③ TTFT 10%–20% 区间 vs 约 20% 中位数点值也不合并；④ 上线时点「上周刚全面上线」（10 月下旬）vs「11 月 25 日宣布完成」；⑤「全程零停机」一手只写「影子流量逐步切流」。

⚠️ **图面独有 / 解析稿错置**：90万 / 200+ / 15万 三个柱状图**无标签、含义与单位未给** → 不解读、不补数值；Action 1–4 与一手的影子测试 / 逐字节比对 / 三重验证循环对不上，按图面独有留档；末段「1800 亿参数模型 / 端到端增量训练 / 智能体插件 / AI 行业标准缺失」与 Rust API 移植主题明显错配，沿用 [A020](http://yb.woa.com/DjfzMFlnxuO) / [A023](http://yb.woa.com/HvYlY3lwbsr) 的「解析稿语义错置」标注，不并入事实层。

**证据等级**：「视频自动解析稿 · 无逐帧画面 / 字幕 / 封面 / 元信息 · 一手访谈（媒体编辑整理）核到 40%–50% 与影子流量方法 · 自媒体 70% / 80% 与解析稿标题属转述层 · 缺 Anthropic 官方工程博客、原始 benchmark 表、测量口径（每请求 / 服务整体）、请求量、服务版本号与抓取时间（G45）」。⚠️ 两版数字都**不能判定孰对孰错**。

**补齐清单回写 · 打勾不删**：本条一次性补上 **GA01**（多 Agent 协作真实工程案例）、**GC01**（目标→方案→踩坑→量化结果四段齐全的落地复盘）、**GC04 / GC06**（转述偏差与解析稿错乱复核流程又添一例）、**G08**（样本形态与一手页样本）、**G14**（外部验证样本）→ 打 ✅；**G45** 新开缺口（官方博客与 benchmark 表）。原缺口 text / note 一字不改、条目一条不删，补记挂在 `DATA.gaps.review`。见 H01 / [T098](../apps/H02%20·%20H03%20·%20「OpenAI%20破解数学」与「Claude%20解决黎曼猜想」.html) / [T099](../apps/第二十三批归纳：第五页、三条事件与「补好打勾、别删条目」.html) / 维护约定第 43 条。

> 整理说明：事实整理卡。解析稿按用户提供的 5 段时间轴逐字摘录；一手访谈与自媒体转述分层留档、两版 CPU 数字并列不调和；图面无标签数字不解读。不代表 Anthropic、Claude 或任一媒体立场。

## 来源

- A040《Anthropic 将核心 API 从 Python 重写为 Rust 的性能对比（视频解析稿）》 · 2026-11-26 · http://yb.woa.com/8Abur0ylFHZ
