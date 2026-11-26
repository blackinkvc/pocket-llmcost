---
title: 一手口径：GeoLibre 是什么、真实安装链路、以及那些对不上的数字
date: 2026-11-26
summary: ⚠️ **本卡全部来自 GitHub 仓库 / README、项目官网与第三方说明，不是视频画面，也不是对该视频的背书**。单列一卡是为了把「视频演示了什么」和「真实项目是什么」彻底分开。
tags: GeoLibre, opengeos, Qiusheng Wu, MIT, 资料入库
---
**项目身份**：**GeoLibre**（不是 GisLibre / GISHub），仓库 `opengeos/GeoLibre`，MIT 协议，主语言 TypeScript（约 90.5%，另有 Rust 1.7% 做桌面 / 移动宿主、Python 6% 管 Jupyter 包装），2026-05-27 建仓，作者 **Qiusheng Wu（吴秋生）**。定位「lightweight, cloud-native GIS platform」：浏览器 / Windows / macOS / Linux 桌面 / Android / iOS / Jupyter / R 里跑同一套工作台，工程文件 `.geolibre.json`（另有资料写 `.geolibre`），主打**数据留在本地、不上传云端**。官网 geolibre.app，在线版 web.geolibre.app，共享 share.geolibre.app，插件 plugins.geolibre.app。

**技术栈（按 README 原文）**：**Tauri v2 + React + TypeScript + MapLibre GL JS + DuckDB-WASM Spatial + deck.gl**；四种可切换渲染引擎 MapLibre GL JS（默认）/ Mapbox GL JS / CesiumJS / ArcGIS Maps SDK for JavaScript；基于 WebAssembly 的 Whitebox Next Gen 地理处理工具箱（浏览器内运行，无需 Python 侧车）；Pyodide / Jupyter 桥接；可导出独立离线 HTML 工程。⚠️ **没有 Electron**，也没有 `install.py`。

**真实安装 / 分发链路（并列，不调和）**：

- **从源码**：`git clone https://github.com/opengeos/GeoLibre.git && cd GeoLibre && npm install && npm run dev`，需 Node.js 22+，桌面构建另需 Rust
- **零安装**：直接打开 `https://web.geolibre.app/`（无需注册 / API Key）；网页版有明确边界——本地对话框、MBTiles、工程存盘、本地 Python 侧车与 Whitebox 栅格工具在网页版不可用或隐藏
- **桌面 / 移动**：Release 页安装包（Win / macOS / Linux）、Mac App Store（沙箱版会砍掉 Python 侧引擎、本地 Jupyter、Earth Engine 登录与外部插件安装）、Google Play、flatpak、AUR、Microsoft Store
- **Notebook**：`pip install geolibre` 或 `conda install -c conda-forge geolibre`（anywidget 桥接，非独立 GIS 内核）；R 包走 `pak::pak("opengeos/geolibre-r")`
- **容器**：`docker run --rm -p 8080:80 ghcr.io/opengeos/geolibre:latest`

⚠️ **数字口径并列留档（全部社媒转述 / 不同时点快照，按 [T038](../apps/数字的七类证据性质：演示%20·%20报价%20·%20示意%20·%20可核验计数%20·%20正文未载的图面结果.html) 第四类标「可核验但未核验」）**：

- **Star**：2k（开源约两个月，2026-05-27 建仓后）→ 3.7k → 4.3k → 4.7k → 6.7k（2026-08-27 v2.8.0 前后）→ 8k → 8.7k → **GitHub API 实测 8815**（收录日 2026-11-26）。全是不同抓取日，不调和、不写成「当前 Star」之外的结论
- **体积**：社媒「主程序仅 **200KB**」；第三方对比表 GeoLibre 桌面 **120MB** / 安卓 **40MB**，QGIS **500MB+ / 几百兆 / 3GB** 三说，ArcGIS Pro **3GB+**；另有博客写 `geolibre-cli.wasm` 约 **24MB**、DuckDB-WASM **40MB / 35MB**（超 Cloudflare 25MiB 限制需走 CDN）。**200KB 与 120MB 不是同一口径，不互相否定也不合并**
- **工具数**：**700+ / 1000+ / 1066**（细分 矢量 313 / 栅格 256 / 遥感 154 / 水文 100 / 地形 99 / LiDAR 65 / 转换 49 / 网络 26 / 投影 4）；**版本** v2.8.0（2026-08-27）；**平台** 浏览器 / 桌面 / 手机 / Jupyter / R；QGIS 官方当前 4.2.3（2026-09-25）/ LTR 3.44.15

**第三方主动划的边界（要一起收）**：GEOPERA 明写「**Can GeoLibre replace QGIS? For many jobs, yes… QGIS still wins on plugin depth and unusual workflows. Most people will run both**」；国内对比表也写「不替代 ArcGIS / QGIS，而是填补零安装、跨设备、轻量化、隐私优先的空白」。Toolclove 注明 README 自述「项目主要在 AI 模型辅助下、经人工审阅构建，请用户自行核对结果」，且 Mapbox / ArcGIS 引擎需自备凭据。⚠️ 所以「刷爆 Github」「QGIS 当场尴尬」「彻底颠覆行业」都是社媒标题，不是项目方结论。

**一句话**：真实项目是**开源、可查、可 `npm run dev` 跑起来的浏览器 GIS 工作台**；视频里那条 `git clone GisLabs/GISHub → python3 install.py → QGIS installed successfully` 的链路，与它**没有任何一条对得上**。本库收的是「原型是什么 + 演示错在哪」，不是「照视频装一遍」。

> 整理说明：一手口径整理卡，来自 GitHub 仓库 / README、项目官网与第三方说明；未在本机跑通安装、未实测体积与 Star 抓取日以外的数值，不冒充视频画面。

## 来源

- A030《GITHUB 开源项目安装演示（200KB 的 GIS / GISHub / QGIS installed successfully）》 · 2026-11-26 · http://yb.woa.com/14N0XXeQcgj
