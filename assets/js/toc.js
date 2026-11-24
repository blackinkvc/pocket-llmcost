/* 首屏右侧的二级目录：有子项的一级条目只负责展开 / 收起，滚动时高亮当前区块。
   要点：整行点击 = 展开，不跳转。跳走之后目录滚出视野，展开就没意义了。 */
(function () {
  var toc = document.querySelector('.toc');
  if (!toc) return;

  var allBtn = toc.querySelector('.toc-all');

  function groups() {
    return [].slice.call(toc.querySelectorAll('.toc-g'));
  }

  function setOpen(g, on) {
    g.classList.toggle('is-open', on);
    var b = g.querySelector('.toc-t');
    if (b) b.setAttribute('aria-expanded', on ? 'true' : 'false');
  }

  /* 全部按钮的文案跟着实际状态走：手动收起一组之后，它不该还写着「收起全部」 */
  function syncAll() {
    if (!allBtn) return;
    var gs = groups();
    var open = gs.filter(function (g) { return g.classList.contains('is-open'); }).length;
    var allOn = gs.length > 0 && open === gs.length;
    allBtn.dataset.open = allOn ? '1' : '0';
    allBtn.textContent = allOn ? '收起全部' : '展开全部';
    allBtn.hidden = gs.length === 0;
  }

  toc.addEventListener('click', function (e) {
    var all = e.target.closest('.toc-all');
    if (all) {
      /* 用 data 记状态，别靠按钮文字判断：「展开全部」里也有「全部」两个字 */
      var openAll = all.dataset.open !== '1';
      groups().forEach(function (g) { setOpen(g, openAll); });
      syncAll();
      return;
    }

    var t = e.target.closest('.toc-t');
    if (t) {
      e.preventDefault();
      setOpen(t.closest('.toc-g'), !t.closest('.toc-g').classList.contains('is-open'));
      syncAll();
    }
  });

  syncAll();

  /* 滚动高亮：进到哪个块，就把对应的二级条目点亮，并展开它所在的组。
     组标题本身不是链接（点了只展开），所以它的高亮由「组里有命中的条目」推导。 */
  var links = [].slice.call(toc.querySelectorAll('a[href^="#"]'));
  var pairs = [];
  links.forEach(function (a) {
    var id = a.getAttribute('href').slice(1);
    var el = id ? document.getElementById(id) : null;
    if (el) pairs.push([el, a]);
  });
  if (!pairs.length || !('IntersectionObserver' in window)) return;

  function paint(link) {
    links.forEach(function (a) { a.classList.remove('is-on'); });
    if (link) link.classList.add('is-on');
    groups().forEach(function (g) {
      var hit = !!g.querySelector('a.is-on');
      g.classList.toggle('has-on', hit);
      /* 只展开、不收起：滚过去又滚回来时，别让用户刚点开的那组自己合上 */
      if (hit && !g.classList.contains('is-open')) setOpen(g, true);
    });
    syncAll();
  }

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
    paint(link);
  }, { rootMargin: '-20% 0px -60% 0px', threshold: [0, 0.4, 1] });

  pairs.forEach(function (p) { io.observe(p[0]); });
})();
