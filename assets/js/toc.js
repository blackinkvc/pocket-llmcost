/* 首屏右侧的二级目录：小三角展开 / 收起，滚动时高亮当前区块 */
(function () {
  var toc = document.querySelector('.toc');
  if (!toc) return;

  var allBtn = toc.querySelector('.toc-all');

  function groups() {
    return [].slice.call(toc.querySelectorAll('.toc-g'));
  }

  function setOpen(g, on) {
    g.classList.toggle('is-open', on);
    var b = g.querySelector('.toc-caret');
    if (b) b.setAttribute('aria-expanded', on ? 'true' : 'false');
  }

  toc.addEventListener('click', function (e) {
    var caret = e.target.closest('.toc-caret');
    if (caret) {
      var g = caret.closest('.toc-g');
      setOpen(g, !g.classList.contains('is-open'));
      return;
    }
    if (e.target === allBtn) {
      /* 用 data 记状态，别靠按钮文字判断：「展开全部」里也有「全部」两个字 */
      var openAll = allBtn.dataset.open !== '1';
      groups().forEach(function (g) { setOpen(g, openAll); });
      allBtn.dataset.open = openAll ? '1' : '0';
      allBtn.textContent = openAll ? '收起全部' : '展开全部';
    }
  });

  /* 滚动高亮：进到哪个块，就把对应的一级条目点亮；二级条目在组内时顺手展开该组 */
  var links = [].slice.call(toc.querySelectorAll('a[href^="#"]'));
  var pairs = [];
  links.forEach(function (a) {
    var id = a.getAttribute('href').slice(1);
    var el = id ? document.getElementById(id) : null;
    if (el) pairs.push([el, a]);
  });
  if (!pairs.length || !('IntersectionObserver' in window)) return;

  var on = new Map();
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) {
      on.set(en.target, en.isIntersecting ? en.intersectionRatio : 0);
    });
    var best = null, top = 0;
    on.forEach(function (v, el) { if (v > top) { top = v; best = el; } });
    if (!best) return;
    var link = null;
    pairs.forEach(function (p) { if (p[0] === best) link = p[1]; });
    if (!link) return;
    links.forEach(function (a) { a.classList.remove('is-on'); });
    link.classList.add('is-on');
    var g = link.closest('.toc-g');
    if (g && !g.classList.contains('is-open')) setOpen(g, true);
  }, { rootMargin: '-20% 0px -60% 0px', threshold: [0, 0.4, 1] });

  pairs.forEach(function (p) { io.observe(p[0]); });
})();
