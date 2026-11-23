/* ============================================================
   shell.js —— 让插件页拥有和主页一样的「调整」能力
   ------------------------------------------------------------
   职责只有四件：
     1. 按 data-w / data-h 把卡片摆到 main.pg 的四列网格里（窄屏自动收列）
     2. 给每张卡加缩放手柄（8 向）+ 卡头上的折叠按钮
     3. 顶栏注入「调整」按钮：进入后可以拖卡片换位置、改大小、
        右下角浮条里「重置布局」；松开就存进 localStorage
     4. ?embed=<卡片id> 时只显示那一张（主页 iframe 用），并把高度回报给父页

   约定：<main class="pg"><section data-card="id" data-title="名字"
         data-w="2" data-h="6"> … </section></main>
   data-w 是「跨几列」（窄屏会自己收），data-h 是「几行」，一行 = --row(56) + 16 间距。
   ============================================================ */
(function () {
  'use strict';

  var pg = document.querySelector('main.pg') || document.querySelector('.pg');
  if (!pg) return;

  var DIRS = ['n', 's', 'w', 'e', 'nw', 'ne', 'sw', 'se'];
  var TIP = {n: '拖上边：改高', s: '拖下边：改高', w: '拖左边：改宽', e: '拖右边：改宽',
             nw: '拖左上角：同时改宽高', ne: '拖右上角：同时改宽高',
             sw: '拖左下角：同时改宽高', se: '拖右下角：同时改宽高'};
  var CUR = {n: 'ns-resize', s: 'ns-resize', w: 'ew-resize', e: 'ew-resize',
             nw: 'nwse-resize', se: 'nwse-resize', ne: 'nesw-resize', sw: 'nesw-resize'};
  var MAXW = 4, MAXH = 40;

  var q = new URLSearchParams(location.search);
  var EMBED = q.get('embed') || '';
  var THEME = q.get('theme') || '';
  if (EMBED && THEME) document.documentElement.dataset.theme = (THEME === 'dark' ? 'dark' : 'light');

  var KEY = 'shell_layout:' + (document.body.dataset.pg || location.pathname);

  /* ---------- 深浅色：全站一个键 ----------
     以前每页各存各的（dash_theme / hw_theme / dv_theme / lc_theme / gh_theme /
     game_theme / shell_theme:<path>），在设备页切了深色，回关注页又是浅色 ——
     用户看到的是「这站的深浅色不听话」。
     现在统一 cuntu_theme：读的时候新的优先、老键兜底（顺手迁移一次）；
     谁改 dataset.theme 都行（各页自己的按钮不用动），这里用 MutationObserver
     把它记到同一个键上。 */
  var THEME_KEY = 'cuntu_theme';
  var THEME_LEGACY = ['dash_theme', 'hw_theme', 'dv_theme', 'lc_theme', 'gh_theme',
    'game_theme', 'shell_theme:' + (document.body.dataset.pg || location.pathname),
    'shell_theme:' + location.pathname];

  /* localStorage 按「源」隔离：8775 / 8778 / 8780 各算一个源，一个键名统一不了它们。
     cookie 只按域名、不按端口 —— 同一台机器上所有端口共用一份，所以主题存 cookie。 */
  function cookieGet(k) {
    try {
      var m = document.cookie.match(new RegExp('(?:^|; )' + k + '=([^;]*)'));
      return m ? decodeURIComponent(m[1]) : null;
    } catch (e) { return null; }
  }
  function cookieSet(k, v) {
    try { document.cookie = k + '=' + encodeURIComponent(v) + '; path=/; max-age=31536000; SameSite=Lax'; } catch (e) { }
  }

  function themeSaved() {
    var c = cookieGet(THEME_KEY);
    if (c === 'dark' || c === 'light') return c;
    var v = null;
    try { v = localStorage.getItem(THEME_KEY); } catch (e) { }
    if (v === 'dark' || v === 'light') return v;
    for (var i = 0; i < THEME_LEGACY.length; i++) {
      try {
        var o = localStorage.getItem(THEME_LEGACY[i]);
        if (o === 'dark' || o === 'light') {
          try { localStorage.setItem(THEME_KEY, o); } catch (e2) { }
          cookieSet(THEME_KEY, o);                                  // 迁移：以后只认 cookie
          return o;
        }
      } catch (e3) { }
    }
    return null;
  }
  function themeStore(v) {
    cookieSet(THEME_KEY, v);
    try { localStorage.setItem(THEME_KEY, v); } catch (e) { }
  }

  /* 有的页（游戏、界面评审）根本没有 .pg 网格，pg 会是 null。
     这一层壳在这些页上只做主题开关，别让 cards() 把它们整个脚本炸掉。 */
  function cards() {
    if (!pg) return [];
    return [].slice.call(pg.children).filter(function (c) { return c.dataset && c.dataset.card; });
  }
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function readJSON(k) { try { return JSON.parse(localStorage.getItem(k) || 'null'); } catch (e) { return null; } }
  function writeJSON(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { } }

  /* 列宽 / 列数 / 行高从计算样式里读：窄屏断点变了不用在 JS 里再抄一遍 */
  function metrics() {
    var cs = getComputedStyle(pg);
    var cols = (cs.gridTemplateColumns || '').split(' ').filter(Boolean)
      .map(function (v) { return parseFloat(v); }).filter(function (v) { return v > 0; });
    var row = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--row')) || 56;
    return {colW: cols[0] || 200, gap: parseFloat(cs.columnGap) || 16,
            n: cols.length || 1, row: Math.round(row)};
  }

  /* ---------- 摆位置 ---------- */
  function paint() {
    if (!pg) return;
    var m = metrics();
    cards().forEach(function (c) {
      var w = clamp(parseInt(c.dataset.w, 10) || 2, 1, Math.min(m.n, MAXW));
      var h = clamp(parseInt(c.dataset.h, 10) || 6, 1, MAXH);
      c.style.setProperty('--w', w);
      c.style.setProperty('--hcell', h);
    });
  }

  function setSize(c, w, h) {
    c.dataset.w = String(w); c.dataset.h = String(h);
    /* 手调过就把 data-hset 打上：页面自己的窄屏兜底高度（写死 height 的那几条）
       全部带 :not([data-hset])，用户调过之后一律让位，否则某些宽度下手柄白拖 */
    c.dataset.hset = '1';
    c.style.setProperty('--w', w);
    c.style.setProperty('--hcell', h);
  }

  /* ---------- 存档 ---------- */
  function snapshot() {
    return {v: 1, at: Date.now(), cards: cards().map(function (c) {
      return {id: c.dataset.card, w: parseInt(c.dataset.w, 10) || 2,
              h: parseInt(c.dataset.h, 10) || 6, fold: c.classList.contains('fold') ? 1 : 0};
    })};
  }
  function save() { writeJSON(KEY, snapshot()); }

  function restore() {
    var s = readJSON(KEY);
    if (!s || s.v !== 1 || !s.cards) return;
    var map = {};
    cards().forEach(function (c) { map[c.dataset.card] = c; });
    var keep = [], known = {};
    s.cards.forEach(function (r) {
      var c = map[r.id];
      if (!c) return;                       // 这一页已经没有这张卡了，跳过
      known[r.id] = 1;
      if (r.w) c.dataset.w = String(clamp(r.w, 1, MAXW));
      if (r.h) { c.dataset.h = String(clamp(r.h, 1, MAXH)); c.dataset.hset = '1'; }
      c.classList.toggle('fold', !!r.fold);
      keep.push(c);
    });
    // 后加的卡（存档里没它）排在最后，别冒到最前面去
    cards().forEach(function (c) { if (!known[c.dataset.card]) keep.push(c); });
    keep.forEach(function (c) { pg.appendChild(c); });
  }

  /* ---------- 卡头：折叠按钮 + 没有卡头就造一个 ---------- */
  function headerOf(c) { return c.querySelector(':scope > .card-h, :scope > .pane-h, :scope > header'); }

  /* 卡头里的「裸标题」包一层 span。
     写法是 <div class="card-h"><i>…</i>内容库<span class="r">…</span></div>，
     中间那句是没有标签的文本节点 —— flex 布局里它是匿名子项，默认可以被压到
     一字宽，420px 下「内容库」就竖着排成三行了。包成 span 才有 nowrap 的资格。 */
  function wrapTitleText(h) {
    if (!h || h.dataset.txwrapped === '1') return;
    var nodes = [].slice.call(h.childNodes).filter(function (n) {
      return n.nodeType === 3 && n.textContent.trim();
    });
    if (!nodes.length) { h.dataset.txwrapped = '1'; return; }
    nodes.forEach(function (n) {
      var s = document.createElement('span');
      s.className = 'card-ht';
      s.textContent = n.textContent.trim();
      h.replaceChild(s, n);
    });
    h.dataset.txwrapped = '1';
  }

  function addChrome(c) {
    var h = headerOf(c);
    if (!h && c.dataset.title) {
      h = document.createElement('div');
      h.className = 'card-h';
      h.innerHTML = '<span>' + String(c.dataset.title) + '</span>';
      c.insertBefore(h, c.firstChild);
    }
    wrapTitleText(h);
    // 拖动手柄摆在卡头最左。没有卡头就不放（那种卡整块都能拖，见下面的 pointerdown）。
    // 整页只有一张卡时也不放：拖了也没地方去，留个抓手只会让人以为能挪。
    if (h && cards().length > 1 && !h.querySelector('.shell-grip')) {
      var gp = document.createElement('span');
      gp.className = 'shell-grip';
      gp.title = '按住拖：换个位置';
      gp.setAttribute('aria-hidden', 'true');
      gp.innerHTML = '<svg viewBox="0 0 12 12" aria-hidden="true">'
        + '<circle cx="4" cy="2.6" r="1.15"/><circle cx="8" cy="2.6" r="1.15"/>'
        + '<circle cx="4" cy="6" r="1.15"/><circle cx="8" cy="6" r="1.15"/>'
        + '<circle cx="4" cy="9.4" r="1.15"/><circle cx="8" cy="9.4" r="1.15"/></svg>';
      h.insertBefore(gp, h.firstChild);
    }
    if (h && !h.querySelector('.shell-fold')) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'shell-fold';
      b.title = '收起 / 展开这张卡';
      b.setAttribute('aria-label', '收起或展开');
      b.innerHTML = '<svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg>';
      b.addEventListener('click', function (e) {
        e.stopPropagation();
        c.classList.toggle('fold');
        save();
      });
      h.appendChild(b);
    }
    if (!c.querySelector(':scope > .rsz')) {
      var g = document.createElement('div');
      g.className = 'rsz';
      g.setAttribute('aria-hidden', 'true');
      g.innerHTML = DIRS.map(function (d) {
        return '<i class="rz-' + d + '" data-rzdir="' + d + '" title="' + TIP[d] + '"></i>';
      }).join('');
      c.appendChild(g);
      g.addEventListener('pointerdown', startResize);
    }
  }

  /* ---------- 缩放手柄 ---------- */
  var rz = null, rzTip = null;

  function startResize(e) {
    var hd = e.target.closest('[data-rzdir]');
    var c = hd && hd.closest('[data-card]');
    if (!c) return;
    e.preventDefault(); e.stopPropagation();
    var r = c.getBoundingClientRect(), m = metrics(), step = m.row + m.gap;
    rz = {c: c, hd: hd, dir: hd.dataset.rzdir, x0: e.clientX, y0: e.clientY,
          w0: r.width, h0: r.height, colW: m.colW, gap: m.gap, row: m.row,
          maxW: Math.min(m.n, MAXW),
          maxH: Math.max(4, Math.min(MAXH, Math.ceil((window.innerHeight - 40) / step)))};
    hd.classList.add('on');
    c.classList.add('rszing');
    document.body.classList.add('rszing');
    document.body.style.setProperty('cursor', CUR[rz.dir] || 'nwse-resize', 'important');
    if (!rzTip) { rzTip = document.createElement('div'); rzTip.className = 'rztip'; rzTip.hidden = true; document.body.appendChild(rzTip); }
    rzTip.hidden = false;
    paintTip(e.clientX, e.clientY);
    window.addEventListener('pointermove', onResize, true);
    window.addEventListener('pointerup', endResize, true);
    window.addEventListener('pointercancel', endResize, true);
  }

  function onResize(e) {
    if (!rz) return;
    var c = rz.c, d = rz.dir, dx = e.clientX - rz.x0, dy = e.clientY - rz.y0;
    var w = parseInt(c.dataset.w, 10) || 2, h = parseInt(c.dataset.h, 10) || 6;
    var stepX = rz.colW + rz.gap, stepY = rz.row + rz.gap;
    if (d.indexOf('e') >= 0) w = clamp(Math.round((rz.w0 + dx + rz.gap) / stepX), 1, rz.maxW);
    if (d.indexOf('w') >= 0) w = clamp(Math.round((rz.w0 - dx + rz.gap) / stepX), 1, rz.maxW);
    if (d.indexOf('s') >= 0) h = clamp(Math.round((rz.h0 + dy + rz.gap) / stepY), 1, rz.maxH);
    if (d.indexOf('n') >= 0) h = clamp(Math.round((rz.h0 - dy + rz.gap) / stepY), 1, rz.maxH);
    if (w !== (parseInt(c.dataset.w, 10) || 2) || h !== (parseInt(c.dataset.h, 10) || 6)) {
      setSize(c, w, h);
      paintTip(e.clientX, e.clientY);
    }
  }

  function paintTip(x, y) {
    if (!rzTip || !rz) return;
    rzTip.textContent = (parseInt(rz.c.dataset.w, 10) || 2) + ' 列 × ' + (parseInt(rz.c.dataset.h, 10) || 6) + ' 行';
    rzTip.style.left = (x + 14) + 'px';
    rzTip.style.top = (y + 16) + 'px';
  }

  function endResize() {
    window.removeEventListener('pointermove', onResize, true);
    window.removeEventListener('pointerup', endResize, true);
    window.removeEventListener('pointercancel', endResize, true);
    if (rz) {
      rz.hd.classList.remove('on');
      rz.c.classList.remove('rszing');
    }
    document.body.classList.remove('rszing');
    document.body.style.removeProperty('cursor');
    if (rzTip) rzTip.hidden = true;
    if (rz) save();
    rz = null;
  }

  /* ---------- 拖卡片换位置（只在调整态） ----------
     起手：卡头那颗手柄，或者卡头/卡片上任何不是按钮、不是缩放手柄的地方。
     为什么以前「拖不动」：卡头里排满了按钮和胶囊，上边沿又被 rz-n 那条 14px
     的缩放手柄压着，能落手的空白几乎没有 —— 点下去十次有九次在改大小。
     现在有一条明确的路：手柄。 */
  var drag = null;

  function markDrop(t, after) {
    cards().forEach(function (c) { c.classList.remove('drop-l', 'drop-r'); });
    if (t) t.classList.add(after ? 'drop-r' : 'drop-l');
  }
  function clearDrop() { cards().forEach(function (c) { c.classList.remove('drop-l', 'drop-r'); }); }

  /* 把 src 挪到 tgt 的前/后。已经在那个位置就别动 ——
     鼠标停在哪两张卡的交界上，来回插会让卡片自己抖个不停。 */
  function moveNear(src, tgt, after) {
    var list = cards();
    var si = list.indexOf(src), ti = list.indexOf(tgt);
    if (si < 0 || ti < 0) return false;
    if (after ? si === ti + 1 : si === ti - 1) return false;
    pg.insertBefore(src, after ? tgt.nextSibling : tgt);
    return true;
  }

  document.addEventListener('pointerdown', function (e) {
    if (!document.body.classList.contains('editing')) return;
    if (e.button !== undefined && e.button !== 0) return;
    var grip = e.target.closest && e.target.closest('.shell-grip');
    // 手柄之外，按钮 / 输入框 / 缩放手柄 / 折叠钮都不是「起手拖」的地方
    if (!grip && e.target.closest('.rsz, .shell-fold, button, a, input, select, textarea, label')) return;
    var c = e.target.closest('[data-card]');
    if (!c || c.parentElement !== pg) return;
    drag = {c: c, x: e.clientX, y: e.clientY, moved: false, id: e.pointerId};
  });

  document.addEventListener('pointermove', function (e) {
    if (!drag) return;
    if (drag.id !== undefined && e.pointerId !== undefined && e.pointerId !== drag.id) return;
    if (!drag.moved) {
      if (Math.abs(e.clientX - drag.x) + Math.abs(e.clientY - drag.y) < 6) return;
      drag.moved = true;
      drag.c.classList.add('dragsrc');
      document.body.style.setProperty('cursor', 'grabbing', 'important');
    }
    var el = document.elementFromPoint(e.clientX, e.clientY);
    var t = el && el.closest ? el.closest('[data-card]') : null;
    if (!t || t === drag.c || t.parentElement !== pg) {
      drag.tgt = null; clearDrop(); return;
    }
    var r = t.getBoundingClientRect();
    // 两轴各自归一化再比：全宽堆叠的卡只有上下有意义，一行并排的看左右。
    // 直接拿 x 比中点会让「上下摞着的卡」永远判成插到后面。
    var ddx = Math.abs(e.clientX - (r.left + r.width / 2)) / Math.max(1, r.width / 2);
    var ddy = Math.abs(e.clientY - (r.top + r.height / 2)) / Math.max(1, r.height / 2);
    var after = (ddx > ddy) ? (e.clientX > r.left + r.width / 2)
                            : (e.clientY > r.top + r.height / 2);
    // 拖动过程中只标落点，不真的插进去 —— 边拖边插会让卡片在手下反复跳，
    // 想放在哪都要重新瞄准。松手那一刻才落位。
    drag.tgt = t; drag.after = after;
    markDrop(t, after);
  });

  function endCardDrag() {
    if (!drag) return;
    var d = drag;
    drag = null;
    d.c.classList.remove('dragsrc');
    clearDrop();
    document.body.style.removeProperty('cursor');
    if (d.moved && d.tgt && moveNear(d.c, d.tgt, d.after)) save();
    else if (d.moved) save();     // 位置没变也存一次：折叠/尺寸状态可能刚被动过
  }
  document.addEventListener('pointerup', endCardDrag);
  document.addEventListener('pointercancel', endCardDrag);

  /* ---------- 顶栏「调整」+ 底部浮条 ---------- */
  /* 游戏页、界面评审页也套了这层壳，但页面里一张 [data-card] 都没有 ——
     顶栏那颗「调整」点了什么都不会发生。没卡就不出这颗按钮和浮条。
     卡是页面自己画的（有的等数据回来才画），所以监听一下 pg，有了再补。 */
  function hasCards() { return cards().length > 0; }

  function buildUI() {
    var hd = document.querySelector('header') || document.querySelector('.top');
    if (hd && !hd.querySelector('.shell-adjust') && hasCards()) {
      var inner = hd.querySelector('.in, .hd') || hd;
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'icobtn shell-adjust';
      // 跟主页那颗一模一样：图标、提示文字都对齐，用户不用在两个页面里学两套
      b.title = '调整卡片大小 / 布局';
      b.setAttribute('aria-label', '调整卡片大小 / 布局');
      b.setAttribute('aria-pressed', 'false');
      b.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1.6"/><rect x="14" y="3" width="7" height="7" rx="1.6"/><rect x="3" y="14" width="7" height="7" rx="1.6"/><rect x="14" y="14" width="7" height="7" rx="1.6"/></svg>';
      b.addEventListener('click', function () { toggleEdit(); });
      inner.appendChild(b);
    }
    // 页面自己没做主题开关的（关注页原来只有深色），这里补一颗；键全站统一
    if (hd && !document.querySelector('#btnTheme, [data-theme-toggle]')) {
      var tb = document.createElement('button');
      tb.type = 'button';
      tb.className = 'icobtn';
      tb.id = 'btnTheme';
      tb.title = '切换深浅色';
      tb.setAttribute('aria-label', '切换深浅色');
      tb.innerHTML = '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><path d="M12 4v16"/><path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor" stroke="none"/></svg>';
      tb.addEventListener('click', function () {
        var dark = document.documentElement.dataset.theme !== 'dark';
        document.documentElement.dataset.theme = dark ? 'dark' : 'light';
        themeStore(dark ? 'dark' : 'light');
      });
      var host = hd.querySelector('.in, .hd') || hd;
      var adj = document.querySelector('.shell-adjust');
      if (adj) host.insertBefore(tb, adj); else host.appendChild(tb);
    }

    if (hasCards() && !document.querySelector('.shell-bar')) {
      var bar = document.createElement('div');
      bar.className = 'shell-bar';
      bar.innerHTML = '<b>拖边 / 角改大小 · 抓卡头左边六点拖动换位置</b>'
        + '<button type="button" class="btn" data-shell="reset">恢复默认</button>'
        + '<button type="button" class="btn done" data-shell="done">完成</button>';
      bar.addEventListener('click', function (e) {
        var t = e.target.closest('[data-shell]');
        if (!t) return;
        if (t.dataset.shell === 'reset') {
          try { localStorage.removeItem(KEY); } catch (err) { }
          location.reload();
        } else {
          toggleEdit(false);
        }
      });
      document.body.appendChild(bar);
    }
  }

  function toggleEdit(force) {
    var on = (force === undefined) ? !document.body.classList.contains('editing') : !!force;
    document.body.classList.toggle('editing', on);
    var b = document.querySelector('.shell-adjust');
    if (b) b.setAttribute('aria-pressed', on ? 'true' : 'false');
    if (!on) save();
  }

  /* ---------- 单卡嵌入 ---------- */
  function embedMode() {
    document.body.classList.add('embed');
    var hit = null;
    cards().forEach(function (c) {
      c.classList.toggle('embed-on', c.dataset.card === EMBED);
      c.classList.remove('fold');
      if (c.dataset.card === EMBED) hit = c;
    });
    if (!hit) document.body.innerHTML = '<div style="padding:16px;font-size:12px;color:#888">这张卡不存在：' + EMBED + '</div>';
    function report() {
      var h = Math.ceil(document.documentElement.scrollHeight);
      try { parent.postMessage({type: 'shell:height', id: EMBED, h: h}, '*'); } catch (e) { }
    }
    if (window.ResizeObserver) new ResizeObserver(report).observe(document.body);
    window.addEventListener('load', report);
    setTimeout(report, 60); setTimeout(report, 400);
    document.addEventListener('click', function () {
      // 单卡里点开的东西（比如弹层）会撑高，报一次
      setTimeout(report, 30);
    });
  }

  /* ---------- 起 ---------- */
  // 全站一个主题键：先把存过的套上，再盯着 data-theme 的变化把它记回去
  try {
    var savedTheme = themeSaved();
    if (savedTheme) document.documentElement.dataset.theme = savedTheme;
    if (window.MutationObserver) {
      new MutationObserver(function () {
        var t = document.documentElement.dataset.theme;
        if (t === 'dark' || t === 'light') themeStore(t);
      }).observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
    }
  } catch (e) { }

  cards().forEach(addChrome);
  if (EMBED) { embedMode(); return; }
  restore();
  paint();
  buildUI();
  if (pg && !hasCards()) {
    // 卡是页面自己画的（等数据回来才渲染）：等它们出现再把「调整」补上
    var moCards = new MutationObserver(function () {
      if (!hasCards()) return;
      moCards.disconnect();
      buildUI();
      restore(); paint();
    });
    moCards.observe(pg, {childList: true});
  }
  window.addEventListener('resize', function () { if (!rz) paint(); });
  window.SHELL = {paint: paint, save: save, cards: cards};
})();
