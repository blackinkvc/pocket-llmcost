#!/usr/bin/env python3
"""重建「模型台账」：content/基模/天梯榜.csv

台账不是能力排名，是「这一年谁发了什么」的收录表，所以排序按发布时间倒序，
编号只是收录序号。事实列（发布时间 / 上下文 / 权重是否开放）一律从
OpenRouter 的模型目录现取，不手填；判断列（机构 / 取向 / 一句话）在下面的
LEDGER 里人工维护 —— 这两类内容混在一起写，最后一定会分不清哪个是查到的。

权重是否开放，按「有没有挂 Hugging Face 仓库」判断。这是可核查的近似：
厂商把权重放到 HF 上就会带 hugging_face_id，没放就没有。少数只在自家
仓库发布的会判成闭源，属于已知误差，写在榜单的 note 里。

用法：
    python3 tools/fetch_model_ledger.py            # 抓取并写 CSV
    python3 tools/fetch_model_ledger.py --check     # 只打印，不写盘
"""

import argparse
import csv
import datetime as dt
import json
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "content" / "基模" / "天梯榜.csv"
API = "https://openrouter.ai/api/v1/models"

# (OpenRouter id, 机构, 区域, 取向, 一句话)
# 收代表作，不收同机构的小改版；一句话只写能对着目录验的事实，不做评价。
LEDGER = [
    ("google/gemini-4-neon", "Google", "国外", "中价 · 编码 Agent",
     "Gemini 4 的中间档：速度为先，主打仓库级编码与终端 Agent。"),
    ("openai/gpt-6.2-astra", "OpenAI", "国外", "旗舰 · 工程与科研",
     "GPT-6.2 系列旗舰，面向真实工程、专业工作与科学研究。"),
    ("qwen/qwen4-max", "阿里", "国内", "旗舰 · 全模态",
     "阿里旗舰，文本 / 图像 / 视频进，1M 上下文，默认开推理。"),
    ("tencent/hy4-flash", "腾讯", "国内", "低成本 · 代码助手",
     "Hy4 的轻量版，参数约为旗舰的四分之一，指向代码助手与 Agent。"),
    ("google/gemini-4-hydrogen", "Google", "国外", "高吞吐 · 路由",
     "Gemini 4 的走量档：为高吞吐 Agent 与多模型路由压低单价。"),
    ("google/gemini-4-carbon", "Google", "国外", "前沿 · 编码推理",
     "Gemini 4 前沿档，编码 / Agent / 复杂推理，五模态输入。"),
    ("baidu/ernie-5.5-flash-preview:free", "百度", "国内", "快速档 · 开放权重",
     "文心 5.5 的快速预览版，280B 总参，这一代先放出 flash 档。"),
    ("anthropic/claude-fable-5.2", "Anthropic", "国外", "旗舰 · 长任务编码",
     "面向最难的技术任务，编码、推理、视觉三项都高于 Fable 5.1。"),
    ("meta/muse-ember", "Meta", "国外", "小模型 · Agent 子任务",
     "Meta 最小最省的一档，专给 Agent 天天重复的工具调用与路由。"),
    ("thinkingmachines/inkling-2-small", "Thinking Machines", "国外", "开放 · MoE 推理",
     "594B 总参 / 17B 激活的开放 MoE 推理模型。"),
    ("google/gemini-omni-1.2-flash", "Google", "国外", "视频生成",
     "原生视频生成与编辑，单条最长 15 秒。"),
    ("tencent/hy4", "腾讯", "国内", "旗舰 · Agent",
     "混元 4 正式版，重点补 Agent 与长周期生产力任务。"),
    ("moonshotai/kimi-k3.1-pro", "月之暗面", "国内", "开放 · 长周期编码",
     "K3 的后训练版，1M 上下文，长周期编码与多模态任务。"),
    ("minimax/minimax-m3.1-flash", "MiniMax", "国内", "低成本 · Agent",
     "M3 的快速档，重点补复杂 Agent、编码与安全方向。"),
    ("deepseek/deepseek-v4.1-flash-1017", "DeepSeek", "国内", "低成本 · 稀疏 MoE",
     "V4.1 Flash 的 10·17 快照，稀疏 MoE，走 deepseek-flash 接口。"),
    ("nvidia/nemotron-3.5-super-vl", "NVIDIA", "国外", "开放 · 视觉语言",
     "120B 总参 / 12B 激活，吃文档、GUI 截图与视频。"),
    ("meta/muse-spark-open", "Meta", "国外", "开放 · 编码",
     "面向 Agent 编码工作流训练的开放权重模型。"),
    ("google/gemini-4-argon", "Google", "国外", "推理旗舰",
     "Google 的推理旗舰，主打复杂软件工程与数学科学问题。"),
    ("meta/muse-wonder", "Meta", "国外", "前沿 · 推理",
     "Meta 前沿推理档，文本 / 图 / 视频 / 音频 / PDF 都能进。"),
    ("anthropic/claude-haiku-5.5", "Anthropic", "国外", "小模型 · 高频任务",
     "小模型档，面向摘要、子 Agent 与浏览器操作这类高频低成本任务。"),
    ("mistralai/mistral-large-4-0", "Mistral", "国外", "开放 · 多模态",
     "Mistral 的前沿多模态，1M 上下文，欧洲阵营的主力。"),
    ("inclusionai/ling-3.1-flash", "蚂蚁 inclusionAI", "国内", "开放 · 混合推理",
     "560B 总参 / 25B 激活的混合推理 MoE。"),
    ("z-ai/glm-5.3-prime", "智谱", "国内", "高速版",
     "GLM-5.3 的高速版，靠推理加速把输出吞吐提到 1.5–2 倍。"),
    ("anthropic/claude-opus-5.5", "Anthropic", "国外", "旗舰 · 长程 Agent",
     "上代旗舰，强在大仓库的多步改动与代码审查。"),
    ("x-ai/grok-4.7", "xAI", "国外", "旗舰 · 编码",
     "xAI 旗舰，主打长跑软件工程与自我检查。"),
    ("xiaomi/mimo-v2.6-pro", "小米", "国内", "开放 · 全模态",
     "小米的超 1T 参数旗舰，文本 / 图 / 音频 / 视频进。"),
    ("z-ai/glm-5.3", "智谱", "国内", "开放 · 编码 Agent",
     "面向复杂软件工程与长周期 Agent 的推理模型。"),
    ("deepseek/deepseek-v4-pro-0813", "DeepSeek", "国内", "开放 · 大 MoE",
     "V4 Pro 的正式版（GA），大规模 MoE。"),
    ("qwen/qwen3.8-2.4t-a95b", "阿里", "国内", "开放 · 旗舰权重",
     "Qwen3.8 Max 的开放权重版：2.4T 总参 / 95B 激活。"),
    ("moonshotai/kimi-k3", "月之暗面", "国内", "开放 · 2.8T",
     "2.8T 参数的开放多模态推理模型。"),
    ("minimax/minimax-m3", "MiniMax", "国内", "开放 · 多模态",
     "M3 多模态底座，1M 上下文，面向长周期 Agent。"),
]


def get(url, timeout=45):
    req = urllib.request.Request(url, headers={
        "User-Agent": "ai-track-ledger/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def ctx_label(n):
    """上下文长度写成人读得懂的量级。

    厂商报的上下文字节数有两种习惯：2 的幂（131072）和整数（200000）。
    这里在 K / M 两边各算一次，取「离整数最近」的那个写法，于是
    131072 → 128K（2 的幂），500000 → 500K（整数），不会出现 488K 这种。
    """
    if not n:
        return ""
    best = None
    for unit, base in (("M", 1048576), ("M", 1000000), ("K", 1024), ("K", 1000)):
        v = n / base
        if v < 1:
            continue
        gap = abs(v - round(v))
        if unit == "K" and round(v) >= 1000:
            v, gap = v / 1024, abs(v / 1024 - round(v / 1024))
            unit = "M"
        if best is None or gap < best[0]:
            best = (gap, round(v, 1), unit)
    if best is None:
        return str(n)
    _, v, unit = best
    return ("%g" % v) + unit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    data = get(API)["data"]
    by_id = {m["id"]: m for m in data}

    rows, missing = [], []
    for mid, org, region, kind, line in LEDGER:
        m = by_id.get(mid)
        if not m:
            missing.append(mid)
            continue
        day = dt.datetime.fromtimestamp(m["created"], dt.timezone.utc).strftime("%Y-%m-%d")
        name = (m.get("name") or mid).split(": ", 1)[-1]
        name = name.replace(" (free)", "").strip()
        rows.append({
            "名称": name,
            "机构": org,
            "区域": region,
            "权重": "开放" if m.get("hugging_face_id") else "闭源",
            "取向": kind,
            "上下文": ctx_label(m.get("context_length")),
            "一句话": line,
            "时间": day,
        })

    rows.sort(key=lambda r: (r["时间"], r["名称"]), reverse=True)
    for i, r in enumerate(rows, 1):
        r["排名"] = i

    cols = ["排名", "名称", "机构", "区域", "权重", "取向", "上下文", "一句话", "时间"]
    if missing:
        print("  ! 目录里找不到这些 id，已跳过：%s" % ", ".join(missing))
    for r in rows:
        print("  %2s %s %-26s %-12s %-4s %-18s %-6s %s" % (
            r["排名"], r["时间"], r["名称"][:26], r["机构"], r["权重"],
            r["取向"][:18], r["上下文"], r["一句话"][:30]))
    print("共 %d 行 · 开放权重 %d 行 · 最新 %s" % (
        len(rows), sum(1 for r in rows if r["权重"] == "开放"), rows[0]["时间"] if rows else "-"))

    if args.check:
        return
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print("写入 %s" % OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
