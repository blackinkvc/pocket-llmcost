# 价格

这里是**实时价格追踪**，也就是导航里的「AI 天梯榜 & 价格追踪」。
它不是三板块结构，是一套有数据源、有快照、能现场重算的小应用，所以不接 `content/` 生成器。

## 数据的真实位置

| 东西 | 位置 |
|---|---|
| 种子价目（API / 套餐 / 平台 / 硬件） | `seed/*.csv` |
| 价格历史与事件 | `seed/price_history.csv`、`seed/price_events.csv` |
| 线上快照 | `llmcost/data/data.json`（由 Actions 每日生成） |
| 页面 | `llmcost/index.html`、`prices.html`、`ranking.html`、`trend.html`、`method.html` |
| 本地版小工具源码 | `llmcost.py`、`llmcost_ui.html` |

## 为什么单独放

价格是**会变的数据**，别的板块是**会说清出处的话**。前者要定时抓、要快照、要能重算，
后者要人写、要审、要留档。流程不一样，硬塞进同一个模板只会两头都别扭。

改价目：编辑 `seed/*.csv` → `python3 tools/make_snapshot.py` → 推上去，页面的快照就更新。
