/* 能力分榜：切来源（AA / LMArena）与维度，按当前维度的分重排。
   卡片上带着所有维度的值（data-v-<src>-<dim>），切的时候不请求网络。
   没有该维度分数的模型直接隐藏 —— 不拿 0 占位。 */
(function () {
  'use strict';

  function fmt(n) {
    if (Math.abs(n) >= 1e4) {
      return (n / 1e4).toFixed(2).replace(/\.?0+$/, '') + ' 万';
    }
    return Math.abs(n % 1) < 1e-9 ? String(Math.round(n)) : n.toFixed(1);
  }

  function init() {
    var board = document.querySelector('[data-scores]');
    if (!board) return;

    var cards = [].slice.call(board.children);
    var limit = parseInt(board.getAttribute('data-limit') || '30', 10);
    var srcBtns = [].slice.call(document.querySelectorAll('.rk-src button'));
    var groups = [].slice.call(document.querySelectorAll('.rk-dims'));
    var countEl = document.querySelector('.rk-count');
    var state = { src: '', dim: '' };

    function groupOf(src) {
      for (var i = 0; i < groups.length; i++) {
        if (groups[i].getAttribute('data-for') === src) return groups[i];
      }
      return null;
    }

    function currentDim(src) {
      var g = groupOf(src);
      var b = g && g.querySelector('button.on');
      return b ? b.getAttribute('data-dim').split(':')[1] : '';
    }

    function valueOf(card, src, dim) {
      var s = card.getAttribute('data-v-' + src + '-' + dim);
      if (s === null || s === '') return null;
      var n = parseFloat(s);
      return isFinite(n) ? n : null;
    }

    function apply() {
      var src = state.src, dim = state.dim;
      if (!src || !dim) return;

      var shown = [];
      cards.forEach(function (c) {
        var v = valueOf(c, src, dim);
        var val = c.querySelector('.bd-val');
        if (v === null) {
          c.hidden = true;
          if (val) val.hidden = true;
          return;
        }
        c.__v = v;
        if (!val) {
          val = document.createElement('span');
          val.className = 'bd-val';
          c.querySelector('.bd-top').appendChild(val);
        }
        val.hidden = false;
        val.innerHTML = src === 'arena'
          ? fmt(v) + '<small>Elo</small>'
          : fmt(v);
        shown.push(c);
      });

      shown.sort(function (a, b) { return b.__v - a.__v; });

      var n = 0;
      shown.forEach(function (c) {
        var rk = c.querySelector('.bd-rank');
        if (n < limit) {
          n += 1;
          c.hidden = false;
          if (rk) rk.textContent = String(n);
        } else {
          c.hidden = true;
        }
        board.appendChild(c);
      });
      // 没有分的挪到最后，别在 DOM 里夹在中间
      cards.forEach(function (c) { if (c.hidden) board.appendChild(c); });

      if (countEl) {
        countEl.textContent = shown.length > limit
          ? '显示前 ' + limit + ' / 共 ' + shown.length + ' 条有分'
          : shown.length + ' 条有分';
      }
    }

    function pickSrc(src) {
      state.src = src;
      srcBtns.forEach(function (b) {
        b.classList.toggle('on', b.getAttribute('data-src') === src);
      });
      groups.forEach(function (g) {
        g.hidden = g.getAttribute('data-for') !== src;
      });
      var g = groupOf(src);
      if (!g) return;
      var b = g.querySelector('button.on') || g.querySelector('button');
      if (b) {
        g.querySelectorAll('button').forEach(function (x) {
          x.classList.toggle('on', x === b);
        });
        state.dim = b.getAttribute('data-dim').split(':')[1];
      }
      apply();
    }

    srcBtns.forEach(function (b) {
      b.addEventListener('click', function () { pickSrc(b.getAttribute('data-src')); });
    });

    groups.forEach(function (g) {
      g.addEventListener('click', function (e) {
        var b = e.target.closest ? e.target.closest('button') : null;
        if (!b || !g.contains(b)) return;
        g.querySelectorAll('button').forEach(function (x) {
          x.classList.toggle('on', x === b);
        });
        state.dim = b.getAttribute('data-dim').split(':')[1];
        apply();
      });
    });

    var firstSrc = srcBtns.filter(function (b) { return b.classList.contains('on'); })[0]
      || srcBtns[0];
    var fallback = groups.filter(function (g) { return !g.hidden; })[0];
    var startSrc = firstSrc ? firstSrc.getAttribute('data-src')
      : (fallback ? fallback.getAttribute('data-for') : 'aa');
    pickSrc(startSrc);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
