# _inbox —— 资料投递区

以后新攒的「资料库型 HTML」放这里，一条命令就能拆进各板块的报告里。

## 什么样的文件能进来

页面里带一个 `const DATA = {…}` 的单文件 HTML（就是平时在浏览器里双击打开、
左边能选栏目、右边能看知识点的那种）。`DATA` 里至少要有：

| 键 | 内容 | 用在哪 |
|---|---|---|
| `sections` | 栏目表（`id` / `name` / `parent`） | 决定这条资料进哪个板块 |
| `topics` | 知识点（`section` / `title` / `tags` / `points` / `sources`） | 一条生成一篇报告 |
| `articles` | 原文清单（`id` / `title` / `url` / `date`） | 报告末尾的「来源」 |
| `tools` | 工具台账（`cats` / `name` / `func` / `review`） | 每个栏目一篇工具台账 |

`gaps` / `templates` / `events` / `boards` 是资料库自己的账（缺口、模板库、事件页、
榜单说明），站点没有对应板块，不入站。

## 一条命令

```bash
python3 tools/ingest.py content/_inbox/新资料.html      # 入库（写 md）
python3 tools/build_section.py                          # 重建成页面
python3 tools/check_links.py                            # 断链自检
```

先看打算怎么做、不写盘：`--dry`；台账里都有哪些源：`--status`。

## 落到哪儿

栏目 → 板块的对照表在 `tools/ingest.py` 顶部的 `SITE_MAP`，现在是：

```
model → 基模        agent / skill / mcp / memory → agent
hardware → 硬件     infra → 公司
rag / roadmap → 原理  template → 模板
kb / case / cad / web3d / game / ai4s → 应用
```

**不新建页面**：资料拆进已有的九个板块，读者在原来的页面上按标签筛。
所有入库报告的 `tags` 里都带一个 `资料入库`，在报告区的筛选项里能一键筛出来。

新资料出现没见过的栏目时，跑到这里加一行；没登记的会被列进「未映射」，不会乱塞。

## 台账（`ledger.json`）

记「哪个源文件的哪一条 → 写进了哪个 md、内容哈希是多少」。三个作用：

- **重跑幂等**：同一个 HTML 再跑一次，是原地更新，不会生成「（2）」。
- **不覆盖人工修改**：md 的哈希和台账对不上，说明你手改过，默认跳过并提示；
  确实要覆盖加 `--force`。
- **可追责**：哪篇报告是从哪份资料来的，翻台账能查。

## 写进去的样子

报告 frontmatter 跟全站一致（`title` / `date` / `summary` / `tags`），正文是
知识点原样搬过来：段落照排、条目照排，末尾一节「来源」写明 A0xx 编号、标题、
日期与原文链接。资料里的 `T0xx` / `A0xx` 会互相链到站内报告或原文，点得动。

工具台账按栏目各一篇，按 `cats` 首项定归属——**一件工具只进一个板块**，不在
七个页面重复挂；表里不排名，作者 / 平台 / 开源没写出来的就是原文没给。
