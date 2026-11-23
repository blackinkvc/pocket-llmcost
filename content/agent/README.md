# Agent

页面 `agents.html` 由本文件夹生成，**榜单数据每天自动抓**。

## 结构

```
content/agent/
  section.json        板块元信息 + 四个榜的列映射
  简介.md             ① 简介：说明 + 三条结论 + 榜的口径
  榜/                 ② 榜单数据（脚本写，别手改）
    使用量-cli.csv      npm 上周下载量
    使用量-ide.csv      VS Code 市场安装量
    mcp服务器.csv       Smithery 调用量
    生态规模.csv        MCP / Skill / 插件数量
  data/stats.json     抓取时间、来源、样本量（页面上的「更新于」就是它）
  报告/*.md           ③ 报告：能力栈、协议、评测、风险
```

## 数据怎么更新

```bash
python3 tools/fetch_agent_stats.py       # 抓一遍，写 榜/ 和 data/stats.json
python3 tools/build_section.py --only agents
```

GitHub Actions 每天 09:23（北京时间）跑同样两条命令，有变化就自己提交。
抓取失败的那一个榜会保留上一次的 CSV，只在 `stats.json` 里记一笔，页面不会空。

## 四个榜的口径（重要）

| 榜 | 来源 | 口径 | 不能用来做什么 |
| --- | --- | --- | --- |
| 使用量 · CLI | api.npmjs.org | 上周下载次数 | 不代表活跃用户，机器重装会重复计数 |
| 使用量 · IDE | VS Code Marketplace | 累计安装量 | 卸载不扣减，老插件天然占优 |
| MCP 服务器 | api.smithery.ai | 平台记录的 `useCount`，取默认排序前 50 位的前 15 | 不是全网排名，跨平台不可比 |
| 生态规模 | 各平台接口 | 仓库数 / 上架数 / 扩展数 | 口径不同，不能相加 |

## 加人或删人

改 `tools/fetch_agent_stats.py` 顶部的 `CLI` / `VSIX` 列表，重新抓一次即可。
加进来的名字会按数值自动排位，不用手工改 CSV。
