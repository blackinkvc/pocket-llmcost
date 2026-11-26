---
title: 从「卖 GPU」到「AI 工厂」：正文大纲、图面年表与官方口径的边界
date: 2026-11-17
summary: ⚠️ **本卡是口径与边界整理，不是英伟达产品评测**。A038 给了 8 页很完整的产品年表和一句很漂亮的收束，但数字与结论分属三种性质；先分层，再谈能拿来做什么。
tags: 口径边界, GeForce 256年份冲突, 1999vs2001, B300≠GB300, 资料入库
---
**正文层 = 图面大纲，不是规格表**：6 段 547 字符只给「图形处理 → 通用计算 → AI 专用计算 → 整机基础设施」的方向，点名 CUDA(2006) / AlexNet(2012) / Volta V100 / A100·H100·H200 / Grace CPU·GH200·GB200·GB300 / NVLink·NVSwitch·ConnectX·BlueField / Vera Rubin。**没有任何算力、显存容量、带宽、制程、功耗、价格或发布时间表**。⚠️ 不能拿它补 GH01 / GH02 / GH03 的工程细节缺口，也不把它写成 NVIDIA 官方路线图。

⚠️ **图内硬矛盾：GeForce 256 年份**：P1 标「**2001，首款GPU**」、P2 时间线标「**1999**」，NVIDIA 官方时间线是 **1999 年 8 月**（「the industry's first graphics processing unit (GPU)」）。→ 两处图面口径并列留档、**不替作者校正、不取一个**；但明确标注「2001 与官方不符」。⚠️ 与 [A035](https://mp.weixin.qq.com/s/yjAqx2IHAhFewtkBdpI8zw)「31.5 GB 既是候选又是可选」、[A036](https://mp.weixin.qq.com/s/o_C93hkiSzFeap_0YyfXKg)「31.5 万张自洽但口径未论证」都不同：这次是**同一套图内两页直接冲突，且其中一页可被一手页证伪**。

**核实范围三层，互不补全**：① **一手已证实**（NVIDIA 官网 / 财报）：GeForce 256 = 1999 年首款 GPU；Vera Rubin 全面投产、NVL72 = 72 Rubin GPU + 36 Vera CPU + ConnectX-9 SuperNIC + BlueField-4 DPU、Quantum-X800 / Spectrum-X、七款新芯片；**NVIDIA Groq 3 LPX 是英伟达产品**（LPU 与 Rubin GPU 协同）。② **图面口径 · 未回一手核实**：六阶段年份区间（1999—2016 / 2017—2019 / 2020—2023 / 2023—2025 / 2024—2026 / 2026）、各代具体年份（P100 2016、T4 2019、A100 2020、H100 2022、H200 2023、GH200 2024上半年、GB200 2024下半年、GB300 2025）、HBM2→HBM4 序列、NVLink 6、B200、Token 效率、每页「本页核心结论」。③ **作者收束句**：「从卖一颗GPU，升级为提供整套AI工厂基础设施」是营销主线，不是本库结论。⚠️ **产品名被证实 ≠ 年份表被证实**。

⚠️ **LPU 归属：先验被一手页推翻**：本库初判「P7 把 Groq / LPU 放进英伟达体系是跨厂商混入」，回一手后 NVIDIA 官网确有「NVIDIA Groq 3 LPX」产品页（「專為 NVIDIA Vera Rubin 打造的互動式 AI 推論加速器」「整合 NVIDIA Rubin GPU 與 LPU 的極致效能」）→ **按官网记为英伟达产品线，不判错、不删**。这是本库第一次「核实结果纠正自己的预判」，也说明**不能凭旧知识给新资料定性**。图面「Groq 3 LPX」vs 官网「NVIDIA Groq 3 LPX」措辞并列。

⚠️ **B300 ≠ GB300**：[A036](https://mp.weixin.qq.com/s/o_C93hkiSzFeap_0YyfXKg) 的「183 万张 **B300**」是**显卡型号**（用于 HPL 双性能等效换算），[A038](https://mp.weixin.qq.com/s/Zj_XNUG315-AJ7fQY-Qshg) 的「**GB300**」是 **Grace CPU + Blackwell GPU 的超级芯片**。两者不同层级、不同语境，**不合并、不互相补、不拿 [A036](https://mp.weixin.qq.com/s/o_C93hkiSzFeap_0YyfXKg) 的换算口径来读 GB300**。同类易混还有图面 P7 的「B200」（正文未提）与 [A036](https://mp.weixin.qq.com/s/o_C93hkiSzFeap_0YyfXKg) 的 B300。

**反向词清单（别误列进图面独有）**：正文里就有 Volta V100 / Tensor Core / A100 / H100 / H200 / HBM / Grace CPU / GH200 / GB200 / GB300 / NVLink / NVSwitch / ConnectX / BlueField / Vera Rubin / DPU / AI工厂 / CUDA / AlexNet / 2006 / 2012。⚠️ 验零第三类噪音「1999」命中 10 次全是 XML 命名空间 `http://www.w3.org/1999/xlink`；加上 [A036](https://mp.weixin.qq.com/s/o_C93hkiSzFeap_0YyfXKg) SVG 圆弧坐标、[A037](https://mp.weixin.qq.com/s/QQbMio_My7u1i_ladamVkw) JS 框架变量，共三类样本。

**与库内三条线索的并列关系**：① [A036](https://mp.weixin.qq.com/s/o_C93hkiSzFeap_0YyfXKg)「183 万张 B300 等效换算」是算力规模口径，本条是产品代际，**不互相补**；② [T030](../hardware/从%20Blackbird%20看「算力交付周期」：为什么模块化是%20AI%20基建的关键变量.html)「Blackbird 模块化算力交付周期」是基建形态，本条是芯片/互连，**不同层**；③ GM05 已记「**Qwen4-Max**」、[A017](https://mp.weixin.qq.com/s/CJoJ6Ch2nOAZqX5EKb2shA) 界面写「Qwen4.0-Max」，[A039](https://mp.weixin.qq.com/s/tESp7Od1YgtSHT9tEPLK2w) 图面写「**Qwen4 Max**」—— **第三种写法**，并列不调和、不回改 GM05。

**证据等级**：「**公众号图卡 · 一手页面与 21 张图面可查 · 正文是图面大纲、非规格表 · 产品名与平台形态经 NVIDIA 官网核实 · 图面年份表 / 结论句 / 内部矛盾未回一手核实 · 无原创声明、0 标签、无制图方与数据来源**」。

**一句话**：这条的价值是「一条把 GPU→超级芯片→机架系统→AI 工厂串起来的产品代际主线」+「本库第一次由一手页纠正自己的预判」；凡是想从它读出各代产品的官方发布年份、算力/显存规格、或把「AI 工厂」当成已定义工程指标的，都属于越界。

> 整理说明：口径与边界整理卡，非原文观点；三层证据分层、内部矛盾并列不调和、先验纠正与反向词剔除为本库整理方法，不代表 NVIDIA 或公众号立场。

## 来源

- A036《全球超算TOP10：第一名相当于183万张B300》 · 2026-11-17 · https://mp.weixin.qq.com/s/o_C93hkiSzFeap_0YyfXKg
- A038《英伟达芯片进化史：从一颗GPU到一座AI工厂》 · 2026-11-17 · https://mp.weixin.qq.com/s/Zj_XNUG315-AJ7fQY-Qshg
- A039《11月AI大模型天梯图：SSS档直接翻倍！》 · 2026-11-19 · https://mp.weixin.qq.com/s/tESp7Od1YgtSHT9tEPLK2w
