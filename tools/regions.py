#!/usr/bin/env python3
"""判断一条记录属于国内还是国外。

榜单要能按「全部 / 国内 / 国外」切换，但 CSV 里未必有区域列，所以这里
用一张关键词表兜底：先匹配国内机构，再匹配国外机构，都对不上就返回空
字符串（页面显示为「未标注」，不硬猜）。

关键词只放**确定归属**的名字，宁可漏判也不要把国内的算成国外。新增条目
时如果判断错了，直接在 CSV 里补一列「区域」覆盖即可。
"""

import re

# 国内：机构名、产品名、平台名
CN = [
    "阿里", "阿里巴巴", "Alibaba", "阿里云", "Qwen", "通义", "千问", "Qoder", "灵码",
    "腾讯", "Tencent", "混元", "Hunyuan", "CodeBuddy", "CodeFuse", "蚂蚁", "Ant Group",
    "字节", "ByteDance", "豆包", "Doubao", "火山引擎", "Trae", "即梦", "可灵", "Kling",
    "百度", "Baidu", "文心", "ERNIE", "Comate", "飞桨", "Paddle",
    "智谱", "Zhipu", "GLM", "CodeGeeX", "ChatGLM",
    "月之暗面", "Moonshot", "Kimi", "DeepSeek", "深度求索",
    "MiniMax", "商汤", "SenseTime", "日日新", "科大讯飞", "讯飞", "iFlytek", "星火",
    "阶跃", "StepFun", "上海AI实验室", "上海人工智能实验室", "InternLM", "书生", "浦语",
    "百川", "Baichuan", "零一万物", "01.AI", "Yi-", "小米", "Xiaomi", "MiMo",
    "华为", "Huawei", "盘古", "Pangu", "昇腾", "Ascend", "MindSpore", "CANN",
    "面壁", "MiniCPM", "OpenBMB", "昆仑万维", "天工", "Skywork", "心流", "iFlow",
    "智源", "BAAI", "ModelScope", "魔搭", "无问芯穹", "生数", "Vidu", "硅基流动", "SiliconFlow",
    "旷视", "Megvii", "网易", "NetEase", "有道", "美团", "Meituan", "滴滴", "DiDi",
    "淘天", "钉钉", "DingTalk", "飞书", "Lark", "金山", "WPS", "石墨", "语雀",
    "寒武纪", "Cambricon", "摩尔线程", "MooreThreads", "壁仞", "燧原", "天数智芯", "沐曦",
    "海光", "Hygon", "中科曙光", "浪潮", "Inspur", "新华三", "H3C", "联想", "Lenovo",
    "摩尔", "太极", "麒麟", "统信", "UOS", "openKylin", "深度科技", "Deepin",
    "智元", "宇树", "Unitree", "云深处", "傅利叶", "优必选", "UBTECH",
    "快手", "Kuaishou", "小红书", "Xiaohongshu", "REDnote", "知乎", "Zhihu", "B站", "哔哩哔哩", "Bilibili",
    "中国", "China", "国产",
]

# 国外：机构名、产品名、平台名
FOREIGN = [
    "OpenAI", "Anthropic", "Claude", "微软", "Microsoft 365", "AMD", "Anysphere", "Suno", "Google", "DeepMind", "Gemini", "Meta", "Llama",
    "Microsoft", "GitHub", "Copilot", "Azure", "Mistral", "xAI", "Grok", "Cohere",
    "Amazon", "AWS", "awslabs", "Bedrock", "NVIDIA", "Apple", "SST", "OpenCode", "Cursor",
    "Windsurf", "Codeium", "Sourcegraph", "Cody", "Roo", "Cline", "Continue", "Augment",
    "Charm", "Crush", "Hugging Face", "HuggingFace", "Smithery", "Vercel", "Replit",
    "Chrome", "Chromium", "ChromeDevTools",
    "Zed", "JetBrains", "Salesforce", "IBM", "Databricks", "Perplexity", "Groq",
    "Cerebras", "Together", "Fireworks", "Stability", "Midjourney", "Runway", "Pika",
    "Luma", "ElevenLabs", "Scale", "Anyscale", "Modal", "Replicate", "Tavily", "Brave",
    "Exa", "Firecrawl", "Apify", "Cloudflare", "Supabase", "Neon", "LangChain",
    "LlamaIndex", "Pinecone", "Weaviate", "Qdrant", "Chroma", "MongoDB", "Elastic",
    "Notion", "Slack", "Atlassian", "Figma", "Stripe", "Twilio", "Linear", "Asana",
    "Airtable", "Zoom", "Box", "Dropbox", "Spotify", "Linux Foundation", "Apache",
    "Mozilla", "Red Hat", "Canonical", "Ubuntu", "Docker", "GitLab", "Atlassian",
    "Bolt", "Lovable", "Devin", "Cognition", "Adept", "Inflection", "Character",
    "RunPod", "Lambda", "CoreWeave", "vLLM", "Ollama", "LM Studio", "llama.cpp", "ggml",
    "Aider", "Tabby", "Tabnine", "Morph", "Magic", "Poolside", "Fireworks AI",
    "VS Code", "VSCode", "Visual Studio", "Marketplace", "Open VSX", "npm",
    "PyPI", "Hugging Face Hub", "Docker Hub",
]

_RE_CACHE = {}


def _hit(text, words):
    low = text.lower()
    for w in words:
        wl = w.lower()
        if not wl:
            continue
        if wl.isascii():
            pat = _RE_CACHE.get(wl)
            if pat is None:
                pat = re.compile(r"(?<![a-z0-9])" + re.escape(wl) + r"(?![a-z0-9])")
                _RE_CACHE[wl] = pat
            if pat.search(low):
                return w
        elif wl in low:
            return w
    return None


def guess(*fields, default=""):
    """按若干字段（机构、厂商、平台、包名……）推断区域，返回 国内 / 国外 / ''。"""
    text = " ".join(str(f) for f in fields if f)
    if not text.strip():
        return default
    if _hit(text, CN):
        return "国内"
    if _hit(text, FOREIGN):
        return "国外"
    return default


def normalize(v):
    """把 CSV 里各种写法统一成 国内 / 国外 / 空。"""
    s = (v or "").strip().lower()
    if s in ("国内", "cn", "china", "中国", "国产", "domestic"):
        return "国内"
    if s in ("国外", "海外", "intl", "international", "foreign", "global", "海外/国外"):
        return "国外"
    return ""


if __name__ == "__main__":
    for t in ["OpenAI", "阿里", "Anthropic", "腾讯", "CodeBuddy", "Claude Code",
              "GitHub Copilot", "通义灵码", "MiniMax", "Mistral", "智谱", "Smithery"]:
        print("%-18s %s" % (t, guess(t) or "未标注"))
