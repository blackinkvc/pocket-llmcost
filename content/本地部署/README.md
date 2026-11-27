# 本地部署

站点 `local.html` 的来源。由 `python3 tools/build_section.py` 生成，改这里、不改 HTML。

## 文件对应关系

| 文件 | 变成页面上的什么 |
|---|---|
| `简介.md` | 首屏：一句话定位、三条结论（`## 三条结论` 渲染成结论框）、其余 `##` 段落变成下方说明卡 |
| `引擎.csv` | 02.1 推理栈：13 套引擎按「从零到第一个 token 要多久」排 |
| `显存档位.csv` | 02.2 显存档位：8 档规模，FP16 / INT8 / INT4 三列粗算 |
| `量化档位.csv` | 02.3 量化取舍：位宽、体积、代价、什么时候用 |
| `硬件落点.csv` | 02.4 硬件路线：容量 × 带宽 × 参考价 |
| `常见失败.csv` | 02.5 排查清单：现象 → 症状 → 根因 → 处理 |
| `报告/*.md` | 03 报告区：五篇，frontmatter 写 title / date / summary / tags / rel / kicker |

表文件名与 `section.json` 里 `boards[].file` 对应；加减表要同步改 `boards` 数组
（`short` 是二级导航里的短名，`fields` 把 CSV 列名映射到卡片字段）。

## 口径

- **不写实测 tok/s。** 本机没有可复现的文本基准；速度只给「带宽 ÷ 每 token 字节数」的算术上限，
  并标明是算的不是测的。
- **价格只给量级。** 2026 年 DRAM 缺货，同配置隔月报价就变，表里标「失真」。
- **查不到的字段留空**，不替它猜。

## 改完

```bash
python3 tools/build_section.py --only local --dry   # 预览
python3 tools/build_section.py                      # 真跑（会重算全站资源指纹）
python3 tools/check_links.py
```
