# 应用

结构已就位，**页面还没切换**（还缺 `简介.md`，生成器会跳过）。

补齐三样就能切：

1. `简介.md` —— 一段说明 + 三条结论（frontmatter 写 sub / chips / spec）
2. `天梯榜.csv` —— 表头已按本板块原有的表列好，把行搬进来
3. `报告/*.md` —— 把原来长页里的章节拆成一篇篇，frontmatter 写 title / date / summary / tags

跑 `python3 tools/build_section.py --only apps --dry` 预览，确认后再去掉 `--dry`。
