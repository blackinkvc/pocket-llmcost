#!/usr/bin/env python3
"""把 llmcost_ui.html 拆成 llmcost/ 下的 5 个子页 + 下载页。

产物：
  llmcost/assets/lc.css        单文件页里的 <style>
  llmcost/assets/lc-engine.js  单文件页里的 <script>（数据源改成「本地优先 / 快照兜底」）
  llmcost/<page>.html          每页只放自己那几张卡的 <section>

可重复执行：每次从 app/llmcost_ui.html 重新生成，不会叠加。
"""
import re
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "llmcost_ui.html"
OUT = ROOT / "llmcost"

PAGES = [
    ("index", "总览", "结论、快照、水位", ["verdict", "snapshot", "stats", "level"]),
    ("ranking", "榜单", "天梯榜、价格 × 实力", ["ladder", "value", "apichart"]),
    ("prices", "价目", "API / 订阅 / 本地 / 平台", ["apitable", "plans", "local", "tasks", "panotable", "platrank"]),
    ("trend", "走势", "曲线、矩阵、调价", ["trend", "matrix", "moves", "timeline"]),
    ("method", "口径", "多源校验与出处", ["verify"]),
]

PRICE_LABEL = "AI 天梯榜 &amp; 价格追踪"

SITE_NAV = [
    ("../index.html", "首页"),
    ("../models.html", "基模"),
    ("../agents.html", "Agent"),
    ("../companies.html", "公司"),
    ("../hardware.html", "硬件"),
    ("../templates.html", "模板"),
    ("../apps.html", "应用"),
    ("../principles.html", "原理 · 历史"),
    ("../local.html", "本地部署"),
    ("../cases.html", "实例"),
    ("../research/index.html", "研究"),
    ("index.html", PRICE_LABEL),
]


def cut(src, start, end):
    i = src.index(start) + len(start)
    j = src.index(end, i)
    return src[i:j]


def with_span(html):
    """shell.js 没加载，--w 不会有人设。把 data-w 转成内联变量，网格才按设计占格。"""
    m = re.search(r'data-w="(\d)"', html)
    w = m.group(1) if m else "2"
    return html.replace('<section class="card"',
                        '<section style="--w:%s" class="card"' % w, 1)


def main():
    src = SRC.read_text(encoding="utf-8")

    css = cut(src, "<style>", "</style>").strip()

    # 主题初始化脚本（head 里那个）
    head_scripts = re.findall(r"<script>(.*?)</script>", src, re.S)
    theme_js = head_scripts[0].strip()

    # 正文所有卡
    cards = {}
    for m in re.finditer(r'<section class="card" data-card="([\w-]+)"[\s\S]*?</section>', src):
        cards[m.group(1)] = with_span(m.group(0).strip())
    assert len(cards) == 18, "卡片数不对：%d" % len(cards)

    # 主脚本
    js = src[src.rindex("<script>"):]
    js = js[len("<script>"):js.index("</script>")].strip()

    # 弹层
    modal = src[src.index('</main>'):src.rindex("<script>")].strip()

    for p in (OUT, OUT / "assets", OUT / "data"):
        if not p.is_dir():
            p.mkdir(parents=True)

    (OUT / "assets" / "lc.css").write_text(
        "/* 由 tools/build_pages.py 从 llmcost_ui.html 抽出，别手改 */\n" + css + "\n",
        encoding="utf-8")

    js = patch_engine(js)
    (OUT / "assets" / "lc-engine.js").write_text(
        "/* 由 tools/build_pages.py 从 llmcost_ui.html 抽出，别手改 */\n" + js + "\n",
        encoding="utf-8")

    for slug, label, desc, ids in PAGES:
        body = "\n\n".join(cards[i] for i in ids)
        (OUT / ("%s.html" % slug)).write_text(
            page(slug, label, desc, body, theme_js, modal), encoding="utf-8")

    (OUT / "download.html").write_text(
        page("download", "下载", "站内小工具，可单独装到本机", download_body(cards), theme_js, modal),
        encoding="utf-8")

    print("生成 %d 页 + 样式 %d KB + 引擎 %d KB" % (
        len(PAGES) + 1,
        len((OUT / "assets" / "lc.css").read_text(encoding="utf-8")) // 1024,
        len((OUT / "assets" / "lc-engine.js").read_text(encoding="utf-8")) // 1024))


def patch_engine(js):
    """数据源：先探本机 :8776，通了用实时，不通读仓库快照。"""
    inject = """
/* ---------- 数据源：本地服务优先，其次仓库快照 ---------- */
var LC_API = 'http://127.0.0.1:8776';
var LC_SNAP = 'data/data.json';
var MODE = 'snapshot';
var SNAP_AT = '';

function dataUrl(force){
  if (MODE === 'live') return LC_API + '/api/data' + (force ? '?force=1' : '');
  return LC_SNAP + '?v=' + Date.now();
}
function probeLive(){
  if (location.protocol === 'file:') return Promise.resolve(false);
  return new Promise(function(res){
    var done = false;
    var fin = function(v){ if (!done){ done = true; res(v); } };
    var ctl = window.AbortController ? new AbortController() : null;
    var t = setTimeout(function(){
      if (ctl) { try{ ctl.abort(); }catch(e){} }
      fin(false);
    }, 1200);
    var opt = {cache:'no-store'};
    if (ctl) opt.signal = ctl.signal;
    fetch(LC_API + '/api/ping', opt)
      .then(function(r){ clearTimeout(t); fin(r.ok); })
      .catch(function(){ clearTimeout(t); fin(false); });
  });
}
function srcTag(){
  return MODE === 'live'
    ? '<b class="live">LIVE</b> 本机 :8776'
    : '快照 ' + esc(SNAP_AT || '—');
}
"""
    js = js.replace("var S = null;", inject + "\nvar S = null;", 1)

    # load()：换成动态数据源 + 记录快照时间 + 标记来源
    js = js.replace(
        "fetch('/api/data' + (force ? '?force=1' : ''), {cache:'no-store'})",
        "fetch(dataUrl(force), {cache:'no-store'})", 1)
    js = js.replace(
        "      if (!p.ok) throw new Error(p.error || '算不出来');\n"
        "      S = p; render(); summary();",
        "      if (!p.ok) throw new Error(p.error || '算不出来');\n"
        "      if (p._snapshot) SNAP_AT = p._snapshot.generated_at || '';\n"
        "      S = p; render(); summary();", 1)

    # 摘要里带数据来源
    js = js.replace(
        "    + '<span class=\"dot\"></span>数据日 ' + esc(m.date)",
        "    + '<span class=\"dot\"></span>' + srcTag()\n"
        "    + ' · 数据日 ' + esc(m.date)", 1)

    # 报告弹层：快照模式下没有 REPORT.md
    js = js.replace(
        "  fetch('/api/report?name=REPORT.md', {cache:'no-store'})",
        "  if (MODE !== 'live'){\n"
        "    $('mBody').innerHTML = '<p>核验报告由本地服务生成，快照站上没有这份文件。</p>'\n"
        "      + '<p class=\"foot\">装到本机后点这个按钮，或命令行跑 <code>python3 llmcost.py --snapshot</code>。</p>';\n"
        "    return;\n"
        "  }\n"
        "  fetch('/api/report?name=REPORT.md', {cache:'no-store'})", 1)

    # 启动：先探活再取数
    js = js.replace(
        "load(false);",
        "probeLive().then(function(ok){\n"
        "  MODE = ok ? 'live' : 'snapshot';\n"
        "  load(false);\n"
        "});", 1)
    return js


def nav_html(active):
    items = "".join(
        '<a%s href="%s">%s</a>' % (' class="is-active"' if label == active else "", href, label)
        for href, label in SITE_NAV)
    return ('<header class="topbar"><div class="topbar-in">'
            '<a class="brand" href="../index.html"><b>AI.TRACK</b>'
            '<span class="sep">/</span><span class="sub">AI 天梯榜 &amp; 价格追踪</span></a>'
            '<nav class="mainnav">%s</nav>'
            '<div class="topbar-right"><span class="meta">快照站</span></div>'
            '</div></header>' % items)


def tabs_html(slug):
    all_pages = PAGES + [("download", "下载", "", [])]
    out = []
    for s, label, _d, _i in all_pages:
        cur = ' aria-current="page"' if s == slug else ""
        out.append('<a href="%s.html"%s>%s</a>' % (s, cur, label))
    return '<nav class="tabs" aria-label="AI 天梯榜 &amp; 价格追踪">%s</nav>' % "".join(out)


def page(slug, label, desc, body, theme_js, modal):
    return """<!doctype html>
<!-- 生成物：由 tools/build_pages.py 从 llmcost_ui.html 生成，手改会被覆盖 -->
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<title>{label} · AI 天梯榜 &amp; 价格追踪 · AI.TRACK</title>
<meta name="description" content="大模型 API 按量价、订阅套餐、本地部署三个维度的成本台账。{desc}">
<script>{theme_js}</script>
<link rel="stylesheet" href="../assets/css/site.css">
<link rel="stylesheet" href="../kit/shell.css">
<link rel="stylesheet" href="assets/lc.css">
<link rel="stylesheet" href="assets/lc-site.css">
</head>
<body>

<a class="skip" href="#pg">跳到卡片</a>

{nav}

<div class="top"><div class="in">
  <div class="sum" id="sub" aria-live="polite">读取中…</div>
  <div class="grow"></div>
  <button class="icobtn" id="btnReport" title="看核验报告" aria-label="看核验报告">
    <svg viewBox="0 0 24 24"><path d="M6 3.5h9l4 4V20a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1z"/><path d="M14.5 3.5V8H19"/><path d="M8.5 13h7M8.5 16.5h5"/></svg>
  </button>
  <button class="icobtn" id="btnTheme" title="切换深浅色" aria-label="切换深浅色">
    <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4.4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6L17 7M7 17l-1.4 1.4"/></svg>
  </button>
  <button class="icobtn" id="btnRefresh" title="重新取数" aria-label="重新取数">
    <svg viewBox="0 0 24 24"><path d="M20 12a8 8 0 1 1-2.6-5.9"/><path d="M20 4.5V10h-5.5"/></svg>
  </button>
  {tabs}
</div></div>

<main class="pg" id="pg">

{body}

</main>

<footer class="lcfoot">
  <a href="../index.html">AI.TRACK</a> · <a href="index.html">AI 天梯榜 &amp; 价格追踪</a>
  · <a href="method.html">口径</a> · <a href="download.html">下载小工具</a>
  <span>数据来自多源交叉校验，快照不定期刷新；过期项以页面标注为准。</span>
</footer>

{modal}

<script src="assets/lc-engine.js"></script>
</body>
</html>
""".replace("{label}", label).replace("{desc}", desc).replace("{theme_js}", theme_js) \
   .replace("{nav}", nav_html(PRICE_LABEL)).replace("{tabs}", tabs_html(slug)) \
   .replace("{body}", body).replace("{modal}", modal)


def download_body(cards):
    return DOWNLOAD_HTML


DOWNLOAD_HTML = """
<div class="dl-wrap">

  <section class="dl-hero">
    <p class="dl-note">站内小工具 · 不是整站下载</p>
    <h1>这里只装一件：价格追踪看板</h1>
    <p><b>网站本身不打包、也不提供下载</b>——九个板块、行业研究、实例这些都是网页，有网就能看。
      能从站上装到本机的，只有这一件小工具：<b>价格追踪看板</b>。
      它原本是「墨山中台」里的一个插件，单独拿出来也能跑。</p>
    <p>线上这五页是<b>快照</b>：价格、榜单、走势都是生成那一刻的样子，只读。装到本机才有完整能力——
      点「重新核验」现场算一遍、写自己的价目表、装回中台当插件、断网也能用。</p>
    <div class="dl-quick">
      <a class="dl-btn" id="dlMain" href="https://github.com/blackinkvc/pocket-llmcost/releases/latest" rel="noopener">
        <b>下载</b><span id="dlMainHint">自动识别系统…</span>
      </a>
      <a class="dl-btn is-ghost" href="https://github.com/blackinkvc/pocket-llmcost" rel="noopener">源码仓库</a>
    </div>
    <p class="dl-note">未签名的可执行文件，首次打开会被系统拦一下，见下方「装完打不开」。</p>
  </section>

  <section class="dl-grid">

    <article class="dl-card">
      <h2>站上有哪些小工具</h2>
      <table class="dl-table">
        <thead><tr><th>小工具</th><th>干什么</th><th>状态</th></tr></thead>
        <tbody>
          <tr><td><code>llmcost</code><br>价格追踪看板</td><td>模型 API 按量价 / 订阅套餐 / 本地部署，三维度算成本，带多源交叉校验和 LMArena 榜单</td><td>可下载</td></tr>
          <tr><td colspan="2">更多小工具陆续从墨山中台里拆出来</td><td>计划中</td></tr>
        </tbody>
      </table>
      <p class="dl-foot">只有<b>小工具</b>能装到本机。网站（行业研究、实例、台账）本身不打包，
        它就是网页，看完关掉即可。</p>
    </article>

    <article class="dl-card">
      <h2>选一个包</h2>
      <table class="dl-table">
        <thead><tr><th>平台</th><th>文件</th><th>需要 Python</th></tr></thead>
        <tbody>
          <tr><td>macOS · Apple 芯片</td><td><code>llmcost-macos-arm64.zip</code></td><td>不要</td></tr>
          <tr><td>macOS · Intel</td><td><code>llmcost-macos-x64.zip</code></td><td>不要</td></tr>
          <tr><td>Windows · 64 位</td><td><code>llmcost-windows-x64.zip</code></td><td>不要</td></tr>
          <tr><td>Linux · x86_64</td><td><code>llmcost-linux-x64.tar.gz</code></td><td>不要</td></tr>
          <tr><td>任意平台源码</td><td><code>llmcost-src.zip</code></td><td>要 3.9+</td></tr>
        </tbody>
      </table>
      <p class="dl-foot">三个可执行包都是单文件，解开双击就跑，不写注册表、不装服务；源码包要 Python 3.9+。
        想当中台插件用、或者要改代码，下源码包。</p>
    </article>

    <article class="dl-card">
      <h2>装完打不开</h2>
      <p><b>macOS</b> 会提示「无法验证开发者」。两条路：</p>
      <pre><code>右键点图标 → 打开 → 再点「打开」</code></pre>
      <p>或者命令行摘掉隔离标记：</p>
      <pre><code>xattr -dr com.apple.quarantine /Applications/llmcost.app</code></pre>
      <p><b>Windows</b> 会弹 SmartScreen：「更多信息」→「仍要运行」。</p>
      <p class="dl-foot">这是因为没买签名证书，不是包有问题。校验和见下。</p>
    </article>

    <article class="dl-card">
      <h2>跑起来是什么样</h2>
      <p>双击后浏览器自动打开 <code>http://127.0.0.1:8776/</code>，就是这五页的完整版。
        关掉浏览器窗口，后台进程会自己退（租约机制），不用管它。</p>
      <p>数据存在本机 <code>~/Documents/AI项目/13-算价</code>，代码和数据分家，
        升级时直接换包就行，不会覆盖你填的价格。</p>
      <p class="dl-foot">首次运行会把内置的公开价目快照补进数据目录，只补缺、不覆盖。</p>
    </article>

    <article class="dl-card">
      <h2>命令行也能用</h2>
      <pre><code>./llmcost --serve            # 起服务，默认 8776
./llmcost --serve --port 9000
./llmcost --snapshot         # 落一份看板和报告到 out/
./llmcost --json | head      # 打包好的数据打到 stdout</code></pre>
      <p class="dl-foot">源码包的用法见仓库 README，<code>./install.sh</code> 一键装进中台。</p>
    </article>

    <article class="dl-card">
      <h2>版本与校验</h2>
      <table class="dl-table">
        <tbody>
          <tr><td>最新版本</td><td id="dlVer">—</td></tr>
          <tr><td>发布日期</td><td id="dlDate">—</td></tr>
          <tr><td>页面数据生成于</td><td id="dlSnap">—</td></tr>
          <tr><td>SHA256</td><td><code id="dlSha">见 Release 说明</code></td></tr>
        </tbody>
      </table>
      <p class="dl-foot">下载后用 <code>shasum -a 256 文件名</code>（Windows：<code>certutil -hashfile 文件名 SHA256</code>）对一遍。</p>
    </article>

    <article class="dl-card">
      <h2>装到本机 / 就在线上看</h2>
      <table class="dl-table">
        <thead><tr><th>能力</th><th>线上（网页）</th><th>本机（小工具）</th></tr></thead>
        <tbody>
          <tr><td>看价目 / 榜单 / 走势</td><td>有（快照）</td><td>有</td></tr>
          <tr><td>重新核验、现场算账</td><td>—</td><td>有</td></tr>
          <tr><td>改价目、加自己的套餐</td><td>—</td><td>有</td></tr>
          <tr><td>刷新 LMArena 榜单</td><td>—</td><td>有</td></tr>
          <tr><td>口袋中台插件</td><td>—</td><td>有</td></tr>
          <tr><td>断网可用</td><td>要看缓存</td><td>有</td></tr>
        </tbody>
      </table>
      <p class="dl-foot">线上页面如果检测到本机 <code>:8776</code> 在跑，会自动切到实时数据并标 <b>LIVE</b>。</p>
    </article>

  </section>
</div>

<script>
(function(){
  var ua = navigator.userAgent, plat = navigator.platform || '';
  var mac = /Mac/.test(plat) || /Mac OS X/.test(ua);
  var win = /Win/.test(plat) || /Windows/.test(ua);
  var base = 'https://github.com/blackinkvc/pocket-llmcost/releases/latest/download/';
  var a = document.getElementById('dlMain');
  var hintEl = document.getElementById('dlMainHint');

  function set(file, hint){
    a.href = base + file;
    hintEl.textContent = hint + ' · ' + file;
  }

  if (mac){
    set('llmcost-macos-arm64.zip', 'macOS · Apple 芯片');
    /* Chrome 的 UA 冻结成 Intel，Apple 芯片也会报 Macintosh；能拿到高熵值就纠正 */
    if (navigator.userAgentData && navigator.userAgentData.getHighEntropyValues){
      navigator.userAgentData.getHighEntropyValues(['architecture']).then(function(v){
        if (v && v.architecture === 'x86'){
          set('llmcost-macos-x64.zip', 'macOS · Intel');
        }
      }).catch(function(){});
    }
  } else if (win){
    set('llmcost-windows-x64.zip', 'Windows · 64 位');
  } else {
    set('llmcost-linux-x64.tar.gz', 'Linux · x86_64');
  }

  /* 快照时间：只说明这五页的数据是什么时候生成的，跟「发版」无关 */
  fetch('data/data.json', {cache:'no-store'})
    .then(function(r){ return r.json(); })
    .then(function(p){
      var s = p._snapshot || {};
      document.getElementById('dlSnap').textContent = s.generated_at || '—';
    })
    .catch(function(){});

  /* 版本与发布日期只认真实的 Release，别拿快照日期冒充。
     两条路：先读仓库里的 data/release.json（发版时由 CI 写入，墙内也能看），
     没有再问 GitHub API，都不通就说「尚未发布」。 */
  var verEl = document.getElementById('dlVer');
  var dateEl = document.getElementById('dlDate');
  var shaEl = document.getElementById('dlSha');

  function showPending(){
    verEl.textContent = '尚未发布';
    dateEl.textContent = '尚未发布';
    shaEl.textContent = '—';
    hintEl.textContent = '尚未发布，先看源码';
    a.href = 'https://github.com/blackinkvc/pocket-llmcost';
    a.classList.add('is-pending');
  }

  function showRelease(tag, date, sha){
    if (!tag) { showPending(); return; }
    verEl.textContent = tag;
    dateEl.textContent = date || '—';
    if (sha) shaEl.textContent = sha.slice(0, 12) + '…（完整值见 Release）';
  }

  fetch('data/release.json', {cache:'no-store'})
    .then(function(r){ if (!r.ok) throw new Error('none'); return r.json(); })
    .then(function(d){ showRelease(d.tag, d.published_at, d.sha256); })
    .catch(function(){
      return fetch('https://api.github.com/repos/blackinkvc/pocket-llmcost/releases/latest', {cache:'no-store'})
        .then(function(r){ if (!r.ok) throw new Error('none'); return r.json(); })
        .then(function(rel){
          showRelease(rel.tag_name, (rel.published_at || '').slice(0, 10), '');
        })
        .catch(showPending);
    });
})();
</script>
"""


if __name__ == "__main__":
    main()
