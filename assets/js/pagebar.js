/* ============================================================
   pagebar.js —— 页面工具条的行为
   ------------------------------------------------------------
   三件事：
     1. 深浅色 / 刷新 / 外观设置三颗按钮（看板页多一颗「核验报告」由引擎自己管）
     2. 「外观设置」浮层：切皮肤、选应用范围（全站 / 仅本页）、切深浅
     3. 把换皮肤后的收尾动作广播出去（看板页的图要重画才跟得上）

   皮肤值只在 skinboot.js 里读写，这里不直接碰 localStorage，
   免得两个文件各记一套键、切页就打架。
   ============================================================ */
(function () {
  var D = document;
  var R = D.documentElement;
  var SK = window.SKIN;
  if (!SK) return;

  var THEME_LISTENERS = [];
  var pop = null, gearBtn = null;

  function el(tag, cls, html) {
    var n = D.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  }

  /* ---------- 1. 深浅 ---------- */
  function setTheme(mode) {
    SK.setTheme(mode);
    syncThemeIcon();
    syncPop();
    for (var i = 0; i < THEME_LISTENERS.length; i++) {
      try { THEME_LISTENERS[i](mode); } catch (e) {}
    }
  }
  function toggleTheme() {
    setTheme(R.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
  }
  function syncThemeIcon() {
    var b = D.querySelector('[data-pb="theme"]');
    if (b) b.setAttribute('title', R.getAttribute('data-theme') === 'dark' ? '切回浅色' : '切到深色');
  }

  /* ---------- 2. 设置浮层 ---------- */
  var POP_HTML =
    '<div class="pb-pop-h"><b>外观设置</b>' +
      '<button class="pb-x" type="button" aria-label="收起设置">×</button></div>' +

    '<p class="pb-lb">皮肤</p>' +
    '<div class="pb-skins">' +
      '<button class="pb-skin" type="button" data-skin="1" aria-pressed="false">' +
        '<span class="pb-prev" data-skin-prev="1"><b class="pb-aa">Aa</b><i class="pb-acc"></i></span>' +
        '<b>皮肤 1 · 监控台</b><span>冷灰纸 · 橙点缀 · 黑体</span>' +
      '</button>' +
      '<button class="pb-skin" type="button" data-skin="2" aria-pressed="false">' +
        '<span class="pb-prev" data-skin-prev="2"><b class="pb-aa">Aa</b><i class="pb-acc"></i></span>' +
        '<b>皮肤 2 · 研究简报</b><span>纸感底 · 朱砂 · 宋体</span>' +
      '</button>' +
    '</div>' +

    '<div class="pb-row"><span class="pb-lb">应用</span>' +
      '<div class="pb-seg" data-seg="scope">' +
        '<button type="button" data-v="all">全站</button>' +
        '<button type="button" data-v="page">仅本页</button>' +
      '</div></div>' +
    '<p class="pb-note"></p>' +

    '<div class="pb-row"><span class="pb-lb">深浅</span>' +
      '<div class="pb-seg" data-seg="theme">' +
        '<button type="button" data-v="auto">跟随系统</button>' +
        '<button type="button" data-v="light">浅</button>' +
        '<button type="button" data-v="dark">深</button>' +
      '</div></div>' +

    '<div class="pb-foot"><button class="pb-reset" type="button">恢复默认</button></div>';

  function buildPop() {
    pop = el('div', 'pb-pop');
    pop.setAttribute('role', 'dialog');
    pop.setAttribute('aria-label', '外观设置');
    pop.hidden = true;
    pop.innerHTML = POP_HTML;
    D.body.appendChild(pop);

    pop.addEventListener('click', function (e) {
      var t = e.target.closest ? e.target.closest('button') : null;
      if (!t || !pop.contains(t)) return;

      if (t.classList.contains('pb-x')) { close(); return; }

      if (t.hasAttribute('data-skin')) {
        var scope = SK.state().scope === 'page' ? 'page' : 'global';
        SK.set(t.getAttribute('data-skin'), scope);
        syncPop();
        announce();
        return;
      }
      var seg = t.parentNode.getAttribute && t.parentNode.getAttribute('data-seg');
      if (seg === 'scope') {
        var v = t.getAttribute('data-v');
        SK.set(SK.state().skin, v === 'page' ? 'page' : 'global');
        syncPop();
        announce();
        return;
      }
      if (seg === 'theme') { setTheme(t.getAttribute('data-v')); return; }
      if (t.classList.contains('pb-reset')) {
        SK.reset();
        syncPop();
        announce();
      }
    });
  }

  function syncPop() {
    if (!pop) return;
    var st = SK.state();
    var scope = st.scope === 'page' ? 'page' : 'all';

    pop.querySelectorAll('.pb-skin').forEach(function (b) {
      b.setAttribute('aria-pressed', b.getAttribute('data-skin') === st.skin ? 'true' : 'false');
    });
    pop.querySelectorAll('[data-seg="scope"] button').forEach(function (b) {
      b.setAttribute('aria-pressed', b.getAttribute('data-v') === scope ? 'true' : 'false');
    });
    pop.querySelectorAll('[data-seg="theme"] button').forEach(function (b) {
      b.setAttribute('aria-pressed', b.getAttribute('data-v') === st.theme ? 'true' : 'false');
    });

    var note = pop.querySelector('.pb-note');
    var name = '皮肤 ' + st.skin;
    if (st.scope === 'page') {
      note.innerHTML = '本页<b>单独</b>用' + name + '，其余页面跟着全站走。想回到统一，点上面的「全站」。';
    } else if (st.scope === 'global') {
      note.innerHTML = '全站统一用' + name + '。想只给这一页换皮，先选皮肤、再点「仅本页」。';
    } else {
      note.innerHTML = '默认就是' + name + '。改过一次后，这里会记住你的选择。';
    }
    syncThemeIcon();
  }

  /* 换完皮肤：图是后端生成的 SVG，配色写在字符串里，
     跟着 CSS 变量走不动，交给页面自己决定要不要重画。 */
  function announce() {
    try {
      D.dispatchEvent(new CustomEvent('pb:skin', { detail: SK.state() }));
    } catch (e) {}
  }

  function place() {
    if (!pop || pop.hidden || !gearBtn) return;
    var r = gearBtn.getBoundingClientRect();
    pop.style.left = '0px'; pop.style.top = '0px';
    var w = pop.offsetWidth, h = pop.offsetHeight;
    var left = Math.min(Math.max(8, r.right - w), window.innerWidth - w - 8);
    var top = r.bottom + 6;
    if (top + h > window.innerHeight - 8) top = Math.max(8, r.top - h - 6);
    pop.style.left = left + 'px';
    pop.style.top = top + 'px';
  }

  function open() {
    if (!pop) buildPop();
    syncPop();
    pop.hidden = false;
    place();
    if (gearBtn) gearBtn.setAttribute('aria-expanded', 'true');
    var first = pop.querySelector('.pb-skin[aria-pressed="true"]') || pop.querySelector('button');
    if (first) first.focus({ preventScroll: true });
  }
  function close() {
    if (!pop || pop.hidden) return;
    pop.hidden = true;
    if (gearBtn) { gearBtn.setAttribute('aria-expanded', 'false'); gearBtn.focus({ preventScroll: true }); }
  }
  function toggle(btn) {
    gearBtn = btn;
    if (pop && !pop.hidden) close(); else open();
  }

  /* ---------- 3. 绑定 ---------- */
  function bind() {
    D.querySelectorAll('[data-pb]').forEach(function (b) {
      var act = b.getAttribute('data-pb');
      if (act === 'theme') b.addEventListener('click', toggleTheme);
      else if (act === 'reload') b.addEventListener('click', function () { location.reload(); });
      else if (act === 'setup') {
        b.addEventListener('click', function (e) { e.stopPropagation(); toggle(b); });
      }
    });
    syncThemeIcon();

    D.addEventListener('click', function (e) {
      if (!pop || pop.hidden) return;
      if (pop.contains(e.target)) return;
      if (e.target.closest && e.target.closest('[data-pb="setup"]')) return;
      close();
    });
    D.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') close();
    });
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, { passive: true });
  }

  window.PB = {
    toggleTheme: toggleTheme,
    setTheme: setTheme,
    onTheme: function (fn) { if (typeof fn === 'function') THEME_LISTENERS.push(fn); },
    openSetup: function () { var b = D.querySelector('[data-pb="setup"]'); toggle(b); }
  };

  if (D.readyState === 'loading') D.addEventListener('DOMContentLoaded', bind);
  else bind();
})();
