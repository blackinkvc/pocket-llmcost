# 研究

这里是**研究项目的管理看板**，不是内容仓库。数据不放在这个文件夹里，
原因是它已经有一套跑通的流水线，两边各存一份必然对不上。

## 数据的真实位置

| 东西 | 位置 |
|---|---|
| 每条研究的元信息与草稿 | `research/items/<slug>/meta.yml` + `draft.md` |
| 已定稿的研究 | `research/published/<slug>.md` |
| 原始资料（图片、网页、PDF） | `research/items/<slug>/raw/` |
| 投料区（我往里扔文件的地方） | `/Volumes/AI仓库/AI行业研究/` |
| 生成的页面 | `research/index.html`、`research/status.html`、`research/<slug>.html` |

## 状态怎么算

不用手工改状态，看文件就知道：

- `published/<slug>.md` 存在 → **已上线**
- `items/<slug>/draft.md` 存在 → **待审核**
- 只有 `raw/` → **整理中**

## 命令

```bash
python3 tools/research.py sync               # 收投料区的新文件
python3 tools/research.py build              # 重建看板与详情页
python3 tools/research.py approve <slug>     # 审核通过，转成 published
```

这条流水线跟 `content/` 里其他板块是**两套东西**：那边是「我写给读者看的知识」，
这边是「我正在做、还没定稿的研究」。合并不划算，反而会让状态变模糊。
