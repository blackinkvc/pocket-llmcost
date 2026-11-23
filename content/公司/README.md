# 公司

已切换成生成页（`companies.html` 由 `tools/build_section.py` 从本目录渲染）。

## 目录

```
section.json      板块元信息 + 站位榜的列映射 + fulltext（整篇 HTML 的登记）
简介.md           ① 简介：说明 + 三条结论 + 读法 + 取舍
天梯榜.csv        ② 产业链站位 27 行（人工维护，数字都抄自下面两份全文）
全文/             ③ 两份独立写好的 HTML 原件，构建时原样复制到 companies/
```

## 两份全文怎么进页面

`section.json` 的 `fulltext` 数组一项对应一篇：

```json
{"file": "全文/xxx.html", "title": "…", "date": "2026-11-18",
 "summary": "…", "tags": ["产业链"]}
```

构建时只做三件事，别的都不动：

1. 把文件复制到 `companies/<原文件名>.html` —— **文件名不能改**，两份全文之间是用文件名互链的；
2. 往它自己的顶栏插一个「← 回公司」（相对路径 `../companies.html`，在 `research/` 下同样成立）；
3. 往 `</head>` 前插一条窄屏规则 `p,li,blockquote,td{overflow-wrap:anywhere}`。原文件在 390px 下会被引用里的长 URL 撑宽 318px，这条是修这个。

全文**只存一份**原件在 `全文/`，`companies/` 与 `research/` 里的副本都是构建产物，改了会被覆盖。
研究板块那边由 `research/items/<同名>/meta.yml` 的 `full:` 指向同一份原件。

## 口径

- 站位榜的序号是产业链**从上到下**的顺序，不是市值或收入排名。
- 台积电标「中国台湾」，不并入国内 / 国外，所以这张榜没做区域切换。
- 任何 GPU 张数只在全文里以「保有量 / 出货量 / 规划容量」三种口径出现，本站不估算、不倒推。

原文件更新后重跑：

```bash
python3 tools/build_section.py --only companies && python3 tools/research.py build
```
