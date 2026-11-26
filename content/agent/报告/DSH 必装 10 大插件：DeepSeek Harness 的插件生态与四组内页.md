---
title: DSH 必装 10 大插件：DeepSeek Harness 的插件生态与四组内页
date: 2026-11-26
summary: 公众号「**呜合ai智能体**」，2026-11-16 20:07；标题《DeepSeek Harness必装10大插件，早装早享受》。
tags: DeepSeek Harness, dsh, 插件生态, dsh-market, 资料入库
---
**封面 / 总览页 10 个插件**（按图面编号原样记）：01 **dsh-market**（插件市场）、02 **open-design**、03 **modlens**（视觉解析镜头）、04 **dsh-vision-toolkit**、05 **Transparent-UI**、06 **auto-memory**、07 **Co-Engram**、08 **dsh-taskboard**、09 **permissions**、10 **agent-teams**。封面另标 **7.2K★ 精选列表、14 类插件、88K★ open-design**（三个数字字段含义未逐一标明，按图面并列留、不强行对应）。

**四组内页的分层逻辑**（图面标题 + 条目）：

- **插件前置三道关卡：选购 | 匹配 | 安全核验**——dsh-market（把市场内嵌进设置页，支持检索与一键安装；配中文说明与 `dsh plugin profile web add dsh-market` 一类命令）、dsh-plugin-recommend（按工作场景推荐配置，内置 100+ 插件目录，自动生成 `dsh add` 对应安装命令）、dsh-plugin-audit（安全健康打分体系 0–100 / A–D 级，自动静态扫描隐藏风险、高危隐患直接告警）。图面强调「上线前一定要完成安全审计」
- **视觉能力赋能：让文本 Agent 看懂图像信息**——modlens（视觉插件，DSH 双重工作流 2.7K★，支持截图 / 轴测图 / 画面内容逆推、把图像理解结果输出为可交付的设计产物）、dsh-vision-toolkit（视觉工具包 592★，内置 59 项工具，UI 界面直接对标校验）、open-design（开发 Claude 辅助设计组件，88K★，把视觉稿转成 HTML UI 设计稿，代码 / 生产力提升、产出二次校验）。图面结论：截图、设计稿、视觉验收、UI 界面问题，全部汇入同一条 Agent 工作流
- **插件体系 / 记忆 / 任务编排**——CORE「Everything is a Plugin」（工程、记忆、工具、UI 界面全部支持插拔扩展）、ECOSYSTEM「插件生态快速扩容」（官方 Awesome-DSH 精选单 2.7K★ / 收录 14+ 类开源插件资源）、HOW「插件部署方式」；记忆插件 dsh-auto-memory（自动记忆，三层记忆机制：内容自动注入、每日轮转归档摘要、目标与约束回灌，支持 Agent 长周期继承记忆）与 Co-Engram（团队记忆，自动同步 Markdown 文档至团队共享记忆库，支持 ODE 更新、内容聚合，和 Claude Code / OpenAI Codex 打通）；任务编排 dsh-taskboard（任务看板）、dsh-agent-teams（Agent 协作，智能体协调能力 1.5T+、多 Agent 团队、关联人任务编排、协作关系可视化）、dsh-permissions（权限引擎，Claude Code 权限模型 hard / deny / allow 三级策略）、dsh-scheduled-tasks（定时任务）
- **自定义 DSH：界面美化 / 流程增强 / 安全规范**——DSH-Transparent-UI 玻璃主题、工作流增强包（dsh-memory、dsh-auto-memory、dsh-taskboard、dsh-side-panel 等界面组件、dsh-tbase 数据层、dsh-super 路由与自动挂载）、安装前置检查清单（安装前按来源 / 权限 / 接口逐项核对、装完按清单逐项回归，安全责任由使用者自己把控）

⚠️ **口径边界（很重要）**：① 标题说「10 大插件」，但内页实际出现的插件名**远不止 10 个**（dsh-plugin-recommend / dsh-plugin-audit / dsh-vision-toolkit / dsh-auto-memory / dsh-permissions / dsh-scheduled-tasks / dsh-side-panel 等），封面 10 个与内页不是一套完整清单，**并列保留、不调和、不替作者补第 11 个**；② 图面 Star 数（7.2K / 2.7K / 592 / 88K / 1.5T+）字段含义混乱、「1.5T+」疑为排版或单位错乱，按图面原样留、标来源不明；③ 仓库地址、作者、许可、安装命令全文、版本号一律未给；④ 这是**作者整理的推荐清单**，不是官方目录、不是第三方评测；⑤ 同批 [A027](https://mp.weixin.qq.com/s/gJJJaFpsDD2m3qlXGMcxvA) 明确反对「装 10 个」，见 [T063](../agents/DSH%20只装%204%20个：插件不是「放着不用就不花钱」，以及三种口径并列.html)。

**与本库的互照**：[T031](../agents/DeepSeek%20Harness（dsh）两个月重度实测：迁移决策、五页图全量与对比数字.html) 里 [A012](https://mp.weixin.qq.com/s/A2fnlab0SoLoAGQJwlmZyg) 作者原话是「下载 dsh、**把所有插件都装上**，再去破个甲」，与本卡「必装 10 大」是同一取向；[T053](../agents/跨主题附图：UHP%20·%20HarnessRouter%20想统一%20Agent%20后端的接入方式.html) 的 UHP / HarnessRouter 想统一的是「产品后端 ↔ 多个 Harness」，而 DSH 插件生态是「**一个 Harness 内部怎么扩能力**」——层次相反，别混。[A024](http://yb.woa.com/4AK3r0d8UHO) 的 Epochal Time Portal 提供 MCP 服务器供智能体接入，也和 DSH 插件同属「Agent 外接能力」，但一个是历史环境、一个是编码工具链。

> 整理说明：事实整理卡，插件名与数值均按图面记录；未核实仓库与 Star 数，未把推荐清单写成官方目录。

## 来源

- A026《DeepSeek Harness必装10大插件，早装早享受》 · 2026-11-26 · https://mp.weixin.qq.com/s/TUMmu9eeJyEaWsitwfCMmQ
