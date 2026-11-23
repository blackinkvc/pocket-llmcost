# Agent

页面 `agents.html` 由本文件夹生成，**榜单数据每天自动抓**。

## 结构

```
content/agent/
  section.json        板块元信息 + 六个榜的列映射
  简介.md             ① 简介：说明 + 三条结论 + 榜的口径
  榜/                 ② 榜单数据（脚本写，别手改）
    使用量-cli.csv      npm 上周下载量
    使用量-ide.csv      VS Code 市场安装量
    mcp服务器.csv       Smithery 调用量
    生态-mcp仓库.csv    GitHub topic 下的仓库数（按语言拆）
    生态-mcp平台.csv    MCP 平台的上架量
    生态-ide市场.csv    IDE 扩展市场存量
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

## 六个榜的口径（重要）

| 榜 | 来源 | 口径 | 不能用来做什么 |
| --- | --- | --- | --- |
| 使用量 · CLI | api.npmjs.org | 上周下载次数 | 不代表活跃用户，版本发布与 CI 会重复拉包放大 |
| 使用量 · IDE | VS Code Marketplace | 累计安装量 | 卸载不扣减，老插件天然占优 |
| MCP 服务器 · 调用量 | api.smithery.ai | 平台记录的 `useCount`，取默认排序前 50 位的前 15 | 不是全网排名，跨平台不可比 |
| MCP 仓库 · 按语言 | GitHub Search API | `topic:mcp-server` 下的公开仓库数，按主语言拆 | 话题靠作者自贴，不是所有 MCP 项目 |
| MCP 平台 · 上架量 | api.smithery.ai | 平台登记的服务器条数 | 不是全网数量，不能和仓库数相减 |
| IDE 市场 · 存量 | Marketplace / open-vsx.org | 各市场自己报的扩展总数 | 不是使用量，两边可能重复上架 |

**生态的三张表是刻意拆开的**：仓库数、上架数、扩展数是三种口径，
加在一起没有任何含义。谁想把它们塞回一张表，就是在造一个不存在的总量。

## 加人或删人

改 `tools/fetch_agent_stats.py` 顶部的 `CLI` / `VSIX` 列表，重新抓一次即可。
加进来的名字会按数值自动排位，不用手工改 CSV。
