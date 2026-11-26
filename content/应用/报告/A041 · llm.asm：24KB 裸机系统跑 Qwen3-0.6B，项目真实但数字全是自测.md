---
title: A041 · llm.asm：24KB 裸机系统跑 Qwen3-0.6B，项目真实但数字全是自测
date: 2026-11-27
summary: **归类决定**：视频归「**实例**」主板块（开源项目工程实践 / 极限工程复盘），related 挂 hardware（推理加速 / 大页 / 内存带宽 / AVX2）、model（Qwen3-0.6B /
tags: llm.asm, alesha-pro, Alexey Fateev, 纯汇编 x86-64 NASM, 资料入库
---
**视频可见信息**：短链 http://yb.woa.com/DIYXFqhbxul ，29 秒，用户附「【视频解析内容-模型总结信息】」自动解析稿；**视频本体、逐帧画面、字幕、封面、发布账号、发布日期、地点、互动数字全部取不到** → 标「内容待补」+「非逐帧取证」（同 [A020](http://yb.woa.com/DjfzMFlnxuO) / [A023](http://yb.woa.com/HvYlY3lwbsr) / [A024](http://yb.woa.com/4AK3r0d8UHO) / [A030](http://yb.woa.com/14N0XXeQcgj) / [A040](http://yb.woa.com/8Abur0ylFHZ)）。解析稿 3 段按原样全量留档：① 00:00–00:04「彻底删掉Linux！极客用纯汇编 手搓24KB系统跑千问，比llama.cpp快54%」+ 男声「当所有人都在卷显卡时，有位硬核大神直接把linux都删了」；② 00:04–00:19 终端窗口 `llm.asm` + 右侧七条指标「开源在GitHub/Linux，零C/Rust依赖」「人工编写纯汇编代码仅24KB」「74/104毫秒极速开机进入对话」「极致极致极致内存占用多轮对话天」「支持llama.cpp推理框架」「12年老机器甚至无盘都能跑8万/月」「一招绝技：LLM全量映射进物理内存」；③ 00:19–00:29「Qwen3-0.6B权重直接映射进物理内存」+「开机只要74毫秒，插上键盘就能多轮对话，在同款CPU上比llama.cpp最高快出54%，连2014年的无盘老机器都能流畅飙到每秒78个token」。

**一手已核实（外部，单列不并入解析稿）**：GitHub **alesha-pro/llm.asm**，作者 **Alexey Fateev（@superalesha）**，**MIT license**；一篇公众号称 11-25 露面、两天 545 ★（**图面快照，未回 GitHub 一手页核实**）。100% 纯 x86-64 NASM、零 C / C++ / Rust / libc / libm / 运行时依赖，三项目合计 **17,252 行**：`01-qwen3-inference` Linux 静态 ELF **14,712 B**、`02-baremetal-os` 裸机 OS **24,252 B**（FAST_Q8=1；FP32 legacy 23,612 B）、`03-minigpt-train` 从零训练 Mini-GPT **32,944 B**。裸机版 stripped 后 .text 17,143 B / .rodata 2,772 B / .bss 2.1 MiB；Multiboot 1 魔数 0x2BADB002 → 四级页表 → 64 位长模式 → APIC 唤醒所有核 → 2 MiB 大页把 **614 MiB Q8_0 权重**（v2 fp16 scales；v1 fp32 为 649 MiB）**零拷贝映射进物理内存** → 449 MiB KV Cache 与暂存区 → VGA 80×25 / PS/2 / 串口多轮对话（ctx 默认 2048，满则重置 KV Cache）。门槛：CPU 必须 **AVX2 + FMA + F16C**，编译需 nasm / binutils / qemu-system-x86，模型自行从 Hugging Face 下载再导出 .asmbin。

**性能对标 · 作者自测（不是独立实测）**：同一台 **AMD EPYC 7642**，llama.cpp（Q8_0，-ngl 0，CPU only，34 token prompt / 64 token 生成 / 三次平均）—— 1 线程 **23.67 vs 16.63（+42%）**、4 线程 **78.89 vs 51.08（+54%）**、8 线程 **118.08 vs 80.79（+46%）**、16 线程 **134.94 vs 103.03（+31%，峰值 136.6）**；16 线程后受内存带宽限制，24 / 32 核反降到约 132.4。14.7KB Linux 版 1–40 线程快 **18%–36%**（40 线程 126.8 tok/s），裸机大页再榨约 **10%**；`FAST_Q8=1`（INT8×INT8 AVX2+F16C）之前单线程慢 2.9 倍、全线程输给 llama.cpp。输出 1–32 vCPU 逐位一致、64 个 greedy token 全匹配 PyTorch FP32（余弦 0.99965），`scripts/verify_os.py` 五个 prompt 与 Phase 1 逐字节比对，`make os-iso` 产约 661 MiB 的 BIOS+UEFI 混合 ISO。

⚠️ **口径冲突并列不调和**：① 无盘 VM（2014 年 12 核 Xeon E5-2670 v3 / 2 GiB / **0 GB 磁盘**）—— 作者 X 帖「**78 tok/s decode + 最高 111.5 tok/s prefill、内核 95 ms**」vs README 与中文转述「**55.4 tok/s**」，两版并列、不取平均、不覆盖，视频把 78 安到老机器上；② 开机 **74–94 ms** / 95 ms 内核 / 84.88 ms 冷启动（16vCPU）/ <5 s 到提示符 / 解析稿「**74/104 毫秒**」五种口径并列，104 无一手对应；③「最高快 **54%**」是 **4 线程**特定值，不是全面快 54%；④ 中文技术号自述「**我没在真机上跑过……所有命令和数字都抄自 README**」，另一篇写「作者给出的基准是自测数据，**独立第三方复现仍然有限**」—— 这两句是本库判定证据等级的关键，按原话留档。

⚠️ **解析稿语义错置 / 图面独有（沿用 [A020](http://yb.woa.com/DjfzMFlnxuO) / [A023](http://yb.woa.com/HvYlY3lwbsr) / [A040](http://yb.woa.com/8Abur0ylFHZ) 的处理）**：① 用户标注「24KB 裸机 **Linux** 系统」与画面「**彻底删掉 Linux**」**自相矛盾** —— 一手是「无 Linux / 无 Windows」的裸机 Multiboot 内核，**标题简写不是结论**；②「人工编写纯汇编**代码**仅 24KB」→ 24,252 B 是**编译后的二进制**（.text 仅 17,143 B），源码是三项目合计 17,252 行，**二进制大小 ≠ 源码大小**；③「**支持 llama.cpp 推理框架**」→ 项目零依赖、不调用 llama.cpp，llama.cpp 只是 Q8_0 CPU **对标基线**（同 [A040](http://yb.woa.com/8Abur0ylFHZ)「1800 亿参数」的语义错置）；④「开源在 GitHub/Linux」把仓库与 Linux 版揉成一个短语，一手是仓库 + 01/02/03 三个子目录；⑤「极致极致极致内存占用多轮对话天」「12年老机器甚至无盘都能跑 **8万/月**」是 ASR 重复与语义破碎，**8万/月 无标签、无单位、不解读、不补数值**（同 [A040](http://yb.woa.com/8Abur0ylFHZ) 的 90万 / 200+ / 15万）；⑥「零 C/Rust 依赖」按原样留，一手其实还零 libc / libm / C++ / 任何运行时依赖，不替作者补全。

**证据等级与边界**：「视频自动解析稿 · 无逐帧画面 / 字幕 / 封面 / 元信息 · 回一手核到完整 owner/repo 与 MIT license、README 转述、作者 X 帖、多篇中英技术号，**项目真实但全部性能数字为作者自测** · 本库未克隆、未装 nasm/binutils/qemu、未导出 .asmbin、未跑 `make os-check` / `verify_os.py`、未构建 ISO、未在 QEMU 或真机实跑、未核 545★ 快照、未做独立第三方复现」。⚠️ 不把「比 llama.cpp 快 54%」写成结论，不把「24KB 系统」写成「24KB 代码」，不把 0.6B 模型的能力边界写成产品可用性。

**补齐清单回写 · 本批 0 个 ✅**：◐ 部分推进 **G03**（Q8_0 / FAST_Q8 INT8×INT8 / 2MiB 大页 / KV Cache 449MiB 把「量化与推理框架实操」从名词落成可读工程链路）、**GC10**（核到完整 owner/repo + MIT license，与 [A037](https://mp.weixin.qq.com/s/QQbMio_My7u1i_ladamVkw) 同级；[A035](https://mp.weixin.qq.com/s/yjAqx2IHAhFewtkBdpI8zw) Cleanzo 仍未核）、**G28**（24,252 / 23,612 / 14,712 / 32,944 B 精确字节数 + 545★ 单期图面快照）、**GM02**（0.6B「中文长句胡言乱语，写代码基本靠猜」的能力边界）；新开 **G47**（本库自跑）、**G48**（独立第三方复现与四层口径）。⚠️ 沿用上一批「**不为了好看批量打勾**」：项目真实不等于缺口补完，第二十三批的 8 个 ✅ 原样保留、一条不删。见 [T101](../apps/第二十四批归纳：二进制不等于源码、自测不等于复现、0%20个%20✅%20也是结论.html) / 补齐清单 F 区 / 维护约定第 44 条。

> 整理说明：事实整理卡。解析稿按用户提供的 3 段时间轴逐字摘录；一手为 GitHub 仓库 README 的转述与作者 X 帖，非本库实跑；标题简写、二进制大小、对标基线、无盘 VM 两版速度与多种开机时间全部并列留档、不调和。不代表项目作者、llama.cpp 或任一媒体立场。

## 来源

- A041《极客打造 24KB 裸机系统跑 Qwen3-0.6B（llm.asm 视频解析稿）》 · 2026-11-27 · http://yb.woa.com/DIYXFqhbxul
