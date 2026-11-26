---
title: 「200KB 的 GIS」安装演示：六段命令 × 一手仓库逐条对照
date: 2026-11-26
summary: **归类决定**：归「**实例**」主板块（case），**不新建栏目**。这条是「开源项目安装演示视频 + 自动解析稿 + 一手核验」，主体是资料可信度取证
tags: GeoLibre, GISHub, 合成演示终端, 假命令, 资料入库
---
**页面可见信息（第六次空壳页）**：短链 http://yb.woa.com/14N0XXeQcgj → `channels.weixin.qq.com/finder-preview/pages/sph?id=AaauDDvoOl`，HTML 依旧只有 `<title>视频号</title>`。视频号名称、发布时间、地点、互动数字、封面 URL、字幕全部取不到 → 台账标 partial（内容待补）。与 [A018](http://yb.woa.com/62oPBlyl0U0) / [A020](http://yb.woa.com/DjfzMFlnxuO) / [A023](http://yb.woa.com/HvYlY3lwbsr) / [A024](http://yb.woa.com/4AK3r0d8UHO) / [A029](http://yb.woa.com/3x1QBfsbpa6) 同形态，已是**第六次**。用户给的是「@@GITHUB开源项目安装演示@@ +【视频解析内容-模型总结信息】+ 00:00–00:06 六段时间轴」标准自动解析稿，按原样全量记、标「非逐帧取证」。

**解析稿六段全量**（按原样，不润色）：① 00:00–00:01 深色主题终端，顶部黄色横幅「**200KB的GIS刷爆Github 浏览器秒开、手机桌面全跑 QGIS 3GB安装包当场尴尬**」，终端执行 `git clone https://github.com/GisLabs/GISHub.git`，右侧弹出「**GisLibre-GitHub Trending**」浮动面板，列出多个热门开源 GIS 项目及 Star 数量；② 00:01–00:02 克隆成功，`cd GISHub`、`ls`、`python3 install.py`；③ 00:02–00:03 下载依赖 `Installing TauriReactTypescriptGUI...`、`Installing MaplibreRender...`、`Installing MapboxGL...`；④ 00:03–00:04 `Installing Electron...`、`Installing Node.js...`、`Installing Python...`；⑤ 00:04–00:05 `QGIS installed successfully.` + `Run: qgis`；⑥ 00:05–00:06 `Press any key to exit...`。

**一手交叉校验（仅用于标注偏差，不冒充视频画面）**：GitHub API 直接查仓库 / 组织 / README 原文；GeoLibre 官网 geolibre.app 与在线版 web.geolibre.app；AlternativeTo、GEOPERA、Toolclove 的第三方说明；多家公众号与视频号的同话题转述；QGIS 官方下载页（当前 4.2.3 / LTR 3.44.15）。链接留 [A030](http://yb.woa.com/14N0XXeQcgj).leadUrl，**不另建台账**（G27）。

**逐条对照**（视频画面 / 一手口径 / 差在哪）：

- **① 仓库地址是假的**：`GisLabs/GISHub` GitHub API 实测 **404 不存在**；`GisLabs` 组织确实存在（2011-12-03 建），但名下只有 1 个 `OAuth-2.0` 仓库，与 GIS 无关。视频里 `cd GISHub` 自然也跟着错。⚠️ 本库第一次遇到「**克隆命令指向一个不存在的仓库**」，不是拼写错，是整条命令编的
- **② 项目名两处都错**：视频写「**GisLibre**」（面板）/「**GISHub**」（仓库与目录）；一手是 **GeoLibre**，仓库 `opengeos/GeoLibre`，MIT，TypeScript（90.5%），2026-05-27 建仓，作者 **Qiusheng Wu（吴秋生）**，田纳西大学诺克斯维尔分校地理与可持续发展系副教授兼研究生项目主任、Amazon Scholar，也是 leafmap / geemap / segment-geospatial 的作者。**按画面原样留 + 并列一手名，不替视频改名**
- **③ 安装脚本不存在**：官方 README 的从源码安装是 `git clone https://github.com/opengeos/GeoLibre.git && cd GeoLibre && npm install && npm run dev`（Node.js 22+，桌面构建另需 Rust）；**没有 `install.py`**。Python 侧只有 `pip install geolibre` / `conda install -c conda-forge geolibre`，是把整套界面嵌进 Jupyter 的 anywidget 桥接包，不是安装器。另有 Docker `ghcr.io/opengeos/geolibre:latest`、桌面安装包、Mac App Store、flatpak / AUR 等分发渠道
- **④ 安装日志是把技术栈拼成依赖名**：`TauriReactTypescriptGUI`、`MaplibreRender`、`MapboxGL`、`Electron` 都不是包名——一手技术栈是 **Tauri v2 + React + TypeScript + MapLibre GL JS + DuckDB-WASM Spatial + deck.gl**，渲染引擎可切换 MapLibre（默认）/ Mapbox GL JS / CesiumJS / ArcGIS Maps SDK（后两者需自备 token）。⚠️ **Electron 根本不在技术栈里**（Tauri 与 Electron 是两条互斥的桌面打包路线）；「Installing Node.js / Python」也不是包管理器会打印的进度。整段标「**合成进度条 · 非真实 npm / pip 输出**」
- **⑤ 结尾是语义反转，最该拎出来**：视频横幅说「QGIS 3GB 安装包当场尴尬」，主题是**用轻量 GIS 替代/绕开 QGIS**；装完却弹 `QGIS installed successfully.` + `Run: qgis`，把要替代的对象写成了安装产物。GeoLibre 不叫 qgis、没有 `qgis` 启动命令，官方入口是 web.geolibre.app 或 `npm run dev`；它确实能**导入** .qgs / .qgz 与 ArcGIS Pro .aprx / .mapx 工程文件，但那是**导入工程**不是**安装 QGIS**。⚠️ 别拿「能打开 QGIS 工程」把这句圆回来
- **⑥ 浮动面板留白**：「GisLibre-GitHub Trending」面板名错（应为 GeoLibre / GitHub Trending），解析稿只说「列出多个热门开源 GIS 项目及其 Star 数量」，**一个项目名、一个数字都没给** → 只记面板名，不补条目、不补 Star、不臆造榜单。同话题视频号写过「登顶 GitHub Trending、4.3k 星」，但那是**另一条转述**，不回填进这块面板
- **⑦ 横幅数字是社媒口径**：「200KB 主程序」「QGIS 3GB」来自同话题短视频文案；一手 / 第三方对比表给的是 GeoLibre 桌面 **120MB** / 安卓 **40MB**、QGIS **500MB+（也有几百兆 / 3GB 两说）**、ArcGIS Pro **3GB+**；QGIS 官网下载页只列版本与平台，不给体积。全部按 [T038](../apps/数字的七类证据性质：演示%20·%20报价%20·%20示意%20·%20可核验计数%20·%20正文未载的图面结果.html) 第四类「可核验但未核验」并列留档，不调和

**转述链与证据等级**：真实开源项目（GitHub README + 官网 + 第三方说明）→ 社媒短视频文案（200KB / 3GB / 4.3k 星）→ **合成终端演示画面**（仓库名、命令、日志、成功提示全换过）→ 标准自动解析稿 → 用户提供 → 本库。⚠️ 这次**中间的「演示画面」不是转述，是造出来的证据**：[A023](http://yb.woa.com/HvYlY3lwbsr) 是转述里凭空多出一所大学，[A029](http://yb.woa.com/3x1QBfsbpa6) 是演示话术夸大，[A030](http://yb.woa.com/14N0XXeQcgj) 连命令都是假的。写法是「**一手项目可查且开源 · 视频里的安装流程不可执行、不作为任何项目事实**」。

⚠️ **未给 / 不补**：视频号名称与时间、逐帧画面与字幕、浮动面板里的项目名与 Star 数、GisLabs/GISHub 仓库是否存在以外的任何信息、QGIS 安装包官方体积、GeoLibre 各分发包的实测体积、`install.py` 的可能来源。见 [T069](../apps/一手口径：GeoLibre%20是什么、真实安装链路、以及那些对不上的数字.html) / [T070](../apps/合成演示终端：第五类错乱、命令级核验与本库取证规则再扩一层.html) / G27 / G28。

> 整理说明：事实整理卡。视频侧只记解析稿可见文字；GitHub API / README 等一手仅用于标注偏差，未冒充视频画面，未把外部资料改写成独立台账。

## 来源

- A030《GITHUB 开源项目安装演示（200KB 的 GIS / GISHub / QGIS installed successfully）》 · 2026-11-26 · http://yb.woa.com/14N0XXeQcgj
