/* ---------- 筛选条（公共壳） ----------
   页面只负责「有哪些 chip、怎么算命中」，DOM、搜索防抖、脱焦保持、清空、
   计数、窄屏折行都在这份里。用法：

     const flt = FLT.mount($('spaceFlt'), {
       search: {ph:'搜名字 / 品牌 / 型号', aria:'…'},   // 不要搜索框就传 null
       clear: '清空筛选',                               // 不要清空按钮就传 null
       onSearch(q){ … 自己存 q，然后 paint … },
       onPick(k){ … 自己切条件，然后 paint … },
       onClear(){ … 全清，然后 paint … }
     });
     flt.paint({ q:'', active:false, count:'筛出 <b>2</b> / 28 台', chips:[
       {k:'*', label:'全部', n:28, on:true},
       {k:'p|家里', label:'家里', n:1},
       {sep:true},
       {k:'on', label:'只在线', n:4, on:true},
     ]});

   两条硬规矩：
   1. 搜索框那一层**只在 mount 时建一次**，paint 不重建 —— 一重建就丢焦点，
      60 秒的自动刷新正好赶上用户在打字，字刚打一半光标就飞了。
   2. paint 里同步 input.value 只在它**没有焦点**时做，否则会把正在输入的字顶掉。 */
(function () {
  'use strict';

  var S_ICO = '<svg viewBox="0 0 16 16" aria-hidden="true">'
    + '<circle cx="7" cy="7" r="4.4"/><path d="M10.3 10.3 14 14"/></svg>';

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function attr(k) { return String(k).replace(/["\\]/g, ''); }
  function color(c) {
    return /^[#\w(),.%\s-]+$/.test(String(c || '')) ? String(c) : '';
  }

  function chipHTML(c) {
    if (c.sep) return '<span class="flt-sep"></span>';
    var on = !!c.on;
    return '<button type="button" class="chip" data-fltk="' + esc(attr(c.k)) + '"'
      + ' data-on="' + (on ? 1 : 0) + '" aria-pressed="' + (on ? 'true' : 'false') + '"'
      + (c.title ? ' title="' + esc(c.title) + '"' : '') + '>'
      + (c.dot ? '<s style="background:' + esc(color(c.dot)) + '"></s>' : '')
      + esc(c.label)
      + (c.n ? '<em class="n">' + esc(c.n) + '</em>' : '')
      + '</button>';
  }

  function mount(host, opt) {
    if (!host) return null;
    if (host.__flt) return host.__flt;
    opt = opt || {};
    host.classList.add('flt');

    var qw = null, qIn = null, ch, cn, cx;

    if (opt.search) {
      qw = document.createElement('label');
      qw.className = 'flt-q';
      qw.innerHTML = S_ICO
        + '<input type="search" autocomplete="off" spellcheck="false">'
        + '<button type="button" class="clr" aria-label="清空搜索">×</button>';
      qIn = qw.querySelector('input');
      qIn.placeholder = opt.search.ph || '搜索';
      if (opt.search.aria) qIn.setAttribute('aria-label', opt.search.aria);
      host.appendChild(qw);

      qIn.addEventListener('input', function () {
        if (opt.onSearch) opt.onSearch(qIn.value.trim());
      });
      // Esc 只清搜索，别顺手把别处的弹层也关了
      qIn.addEventListener('keydown', function (e) {
        if (e.key !== 'Escape' || !qIn.value) return;
        e.stopPropagation();
        qIn.value = '';
        if (opt.onSearch) opt.onSearch('');
      });
    }

    ch = document.createElement('div');
    ch.className = 'flt-ch';
    host.appendChild(ch);

    cn = document.createElement('span');
    cn.className = 'flt-n';
    host.appendChild(cn);

    if (opt.clear) {
      cx = document.createElement('button');
      cx.type = 'button';
      cx.className = 'flt-x';
      cx.textContent = opt.clear;
      cx.hidden = true;
      host.appendChild(cx);
    }

    // 一条委托管全部点击：chip 是开关，点完要还焦点（chip 被重画过，原节点没了）
    host.addEventListener('click', function (e) {
      var t = e.target;
      if (qIn && t.closest && t.closest('.clr')) {
        qIn.value = '';
        if (opt.onSearch) opt.onSearch('');
        qIn.focus({ preventScroll: true });
        return;
      }
      if (cx && t.closest && t.closest('.flt-x')) {
        if (opt.onClear) opt.onClear();
        return;
      }
      var b = t.closest && t.closest('[data-fltk]');
      if (!b) return;
      var k = b.getAttribute('data-fltk');
      if (opt.onPick) opt.onPick(k);
      var again = ch.querySelector('[data-fltk="' + k.replace(/["\\]/g, '') + '"]');
      if (again && document.activeElement !== again) again.focus({ preventScroll: true });
    });

    var api = {
      el: host,
      input: qIn,
      q: function () { return qIn ? qIn.value.trim() : ''; },
      focusChip: function (k) {
        var e2 = ch.querySelector('[data-fltk="' + attr(k) + '"]');
        if (e2) e2.focus({ preventScroll: true });
      },
      paint: function (st) {
        st = st || {};
        if (qIn) {
          var q = st.q || '';
          if (document.activeElement !== qIn && qIn.value !== q) qIn.value = q;
          qw.classList.toggle('has', !!(st.q || q));
        }
        // 传了 chips 才重建；没传说明只是改搜索词/计数，chip 一个都没变，
        // 别为了刷一个数字把整排按钮重新插一遍。
        if (st.chips) ch.innerHTML = st.chips.map(chipHTML).join('');
        cn.innerHTML = st.count || '';
        if (cx) cx.hidden = !st.active;
        return api;
      }
    };
    host.__flt = api;
    return api;
  }

  window.FLT = { mount: mount, esc: esc };
})();
