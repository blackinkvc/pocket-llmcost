/* ============================================================
   skinboot.js —— 皮肤 / 深浅的「第一帧」
   ------------------------------------------------------------
   必须在 <head> 里同步执行：皮肤是靠 <html data-skin> 上的 CSS 变量换的，
   等 DOMContentLoaded 再挂，页面会先闪一下默认皮肤再看清正确的那个。

   两级设置，就近优先：
     1) 单页覆盖  localStorage['aitrack.skin.<页面键>'] = '1' | '2'
     2) 全站统一  localStorage['aitrack.skin']         = '1' | '2'
     3) 都没有    → 皮肤 1（默认统一，不再让某一页自带一套皮）
   页面键取路径去掉 index.html / .html，例如 models / llmcost/prices。

   深浅色同一套键：aitrack.theme = auto | light | dark，
   顺手镜像到 lc_theme / cuntu_theme，让价格看板原来的主题脚本读到同一个值。
   ============================================================ */
(function () {
  var R = document.documentElement;
  var K = { skin: 'aitrack.skin', page: 'aitrack.skin.', theme: 'aitrack.theme' };

  function ls(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function put(k, v) {
    try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch (e) {}
  }
  function pageKey() {
    var p = location.pathname
      .replace(/index\.html$/, '')
      .replace(/\.html$/, '')
      .replace(/^\/+|\/+$/g, '');
    return p || 'home';
  }
  function resolveSkin() {
    var pv = ls(K.page + pageKey());
    if (pv === '1' || pv === '2') return { skin: pv, scope: 'page' };
    var g = ls(K.skin);
    if (g === '1' || g === '2') return { skin: g, scope: 'global' };
    return { skin: '1', scope: 'default' };
  }
  function resolveTheme() {
    var m = ls(K.theme);
    if (m !== 'light' && m !== 'dark') m = 'auto';
    var dark = m === 'dark' || (m === 'auto' && window.matchMedia
      && window.matchMedia('(prefers-color-scheme:dark)').matches);
    return { mode: m, dark: !!dark };
  }

  function apply() {
    var s = resolveSkin(), t = resolveTheme();
    R.setAttribute('data-skin', s.skin);
    R.setAttribute('data-theme', t.dark ? 'dark' : 'light');
    try {
      localStorage.setItem('lc_theme', t.mode);
      localStorage.setItem('cuntu_theme', t.mode);
    } catch (e) {}
    return { skin: s.skin, scope: s.scope, theme: t.mode, dark: t.dark };
  }

  window.SKIN = {
    KEY: K,
    pageKey: pageKey,
    state: apply,
    set: function (v, scope) {
      if (scope !== 'page') put(K.skin, v);
      put(K.page + pageKey(), scope === 'page' ? v : null);
      return apply();
    },
    follow: function () { put(K.page + pageKey(), null); return apply(); },
    setTheme: function (m) { put(K.theme, m); return apply(); },
    reset: function () {
      put(K.skin, null); put(K.theme, null); put(K.page + pageKey(), null);
      return apply();
    }
  };

  if (window.matchMedia) {
    var mq = window.matchMedia('(prefers-color-scheme:dark)');
    var on = function () { if ((ls(K.theme) || 'auto') === 'auto') apply(); };
    if (mq.addEventListener) mq.addEventListener('change', on);
    else if (mq.addListener) mq.addListener(on);
  }

  apply();
})();
