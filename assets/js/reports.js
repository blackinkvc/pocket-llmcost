/* 报告卡：按标签筛。
   没有 JS 时全部可见（hidden 只在点过之后才加），不影响阅读。 */
(function () {
  'use strict';

  function init() {
    var bar = document.querySelector('.rpt-bar');
    var grid = document.querySelector('.rpt-grid');
    if (!bar || !grid) return;

    var chips = [].slice.call(bar.querySelectorAll('.rpt-chip'));
    var items = [].slice.call(grid.querySelectorAll('.rpt-item'));
    var hint = bar.querySelector('.rpt-hint');

    function apply(tag) {
      var n = 0;
      items.forEach(function (it) {
        var tags = (it.getAttribute('data-tags') || '').split(',');
        var show = !tag || tags.indexOf(tag) >= 0;
        it.hidden = !show;
        if (show) n++;
      });
      chips.forEach(function (c) {
        c.classList.toggle('on', (c.getAttribute('data-tag') || '') === tag);
      });
      if (hint) {
        hint.textContent = tag ? n + ' 篇' : '';
        hint.hidden = !tag;
      }
    }

    chips.forEach(function (c) {
      c.addEventListener('click', function () {
        apply(c.getAttribute('data-tag') || '');
      });
    });

    // 从别处带 #tag-机制 进来时直接筛上
    var m = /^#tag-(.+)$/.exec(location.hash);
    if (m) apply(decodeURIComponent(m[1]));
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
