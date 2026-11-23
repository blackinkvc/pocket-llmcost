/* ============================================================
   board.js — 榜单的「国内 / 国外 / 全部」切换与时间跨度滑块
   数据由 tools/build_section.py 内嵌在每榜的
   <script type="application/json" data-spec="…"> 里，不额外请求。
   ============================================================ */
(function () {
  'use strict';
  document.documentElement.classList.add('has-js');

  var REGION_LABEL = { all: '全部', cn: '国内', intl: '国外' };
  var DOW = null;

  /* ---------- 数字格式化：和生成器里的 human_num 同一套口径 ---------- */
  function fmt(n) {
    var a = Math.abs(n);
    var s;
    if (a >= 1e8) s = trim(n / 1e8) + ' 亿';
    else if (a >= 1e5) s = trim(n / 1e4, 1) + ' 万';
    else if (a >= 1e4) s = trim(n / 1e4, 2) + ' 万';
    else if (a >= 1000) s = Math.round(n).toLocaleString('en-US');
    else if (a >= 10) s = trim(n, 0);
    else s = n.toFixed(1);
    return s.trim();
  }
  function trim(v, digits) {
    var s = v.toFixed(digits === undefined ? 2 : digits);
    return s.replace(/\.?0+$/, '');
  }
  function pct(v) {
    var s = Math.abs(v).toFixed(1).replace(/\.0$/, '');
    return (v > 0 ? '▲ ' : v < 0 ? '▼ ' : '') + s + '%';
  }
  // 「338.4 万次/天」「126 次/天」：量级和单位连写，纯数字与单位之间留空格
  function withUnit(v, unit, suffix) {
    var s = fmt(v);
    if (!unit) return s;
    var sep = /[万亿]$/.test(s) ? '' : ' ';
    return s + sep + '<small>' + unit + (suffix || '') + '</small>';
  }
  function dayDiff(a, b) {
    return Math.round((Date.parse(b) - Date.parse(a)) / 864e5);
  }
  function shift(iso, n) {
    return new Date(Date.parse(iso + 'T00:00:00Z') + n * 864e5).toISOString().slice(0, 10);
  }

  /* ---------- 一个榜 ---------- */
  function Board(root) {
    this.root = root;
    this.id = root.getAttribute('data-board');
    this.spec = readSpec(this.id);
    this.cards = [].slice.call(root.querySelectorAll('.bd-card'));
    this.ctrl = document.querySelector('.bd-ctrl[data-ctrl="' + this.id + '"]');
    this.seg = this.ctrl ? this.ctrl.querySelector('.seg') : null;
    this.range = this.ctrl ? this.ctrl.querySelector('input[type=range]') : null;
    this.out = this.ctrl ? this.ctrl.querySelector('.span-out') : null;
    this.note = this.ctrl ? this.ctrl.querySelector('.bd-ctrl-note') : null;
    this.region = 'all';
    this.span = this.spec && this.spec.slider ? this.spec.slider['default'] : 0;
    this.order = this.cards.map(function (c) { return c.getAttribute('data-k'); });
  }

  function readSpec(id) {
    var el = document.querySelector('script[data-spec="' + id + '"]');
    if (!el) return null;
    try { return JSON.parse(el.textContent); } catch (e) { return null; }
  }

  Board.prototype.init = function () {
    var self = this;
    if (this.seg) {
      this.seg.addEventListener('click', function (e) {
        var b = e.target.closest('button[data-region]');
        if (!b) return;
        self.region = b.getAttribute('data-region');
        [].forEach.call(self.seg.querySelectorAll('button'), function (x) {
          x.classList.toggle('on', x === b);
        });
        self.apply();
      });
    }
    if (this.range) {
      this.fitRange();
      this.range.addEventListener('input', function () {
        self.span = parseInt(self.range.value, 10) || 0;
        self.apply();
      });
      [].forEach.call(this.ctrl.querySelectorAll('.span-ticks button'), function (b) {
        b.addEventListener('click', function () {
          self.span = parseInt(b.getAttribute('data-span'), 10) || 0;
          self.range.value = self.span;
          self.apply();
        });
      });
    }
    this.apply();
  };

  /* 按当前窗口算每个人一个值 */
  Board.prototype.compute = function () {
    var spec = this.spec;
    if (!spec || !spec.series) return null;
    var days = this.span;
    // 用数据里的最新日期做锚点，不依赖「今天」（抓取可能滞后一天）
    var latest = '';
    Object.keys(spec.series).forEach(function (k) {
      Object.keys(spec.series[k]).forEach(function (d) { if (d > latest) latest = d; });
    });
    if (!latest) return null;
    var from = shift(latest, -(days - 1));
    var prevFrom = shift(from, -days), prevTo = shift(from, -1);
    var mode = spec.mode || 'flow';
    var res = { from: from, to: latest, days: days, values: {} };

    function slice(k, a, b) {
      return Object.keys(spec.series[k]).filter(function (d) { return d >= a && d <= b; }).sort();
    }
    function stat(k, pts) {
      if (!pts.length) return null;
      var vals = pts.map(function (d) { return spec.series[k][d]; });
      if (mode === 'flow') {
        return { v: vals.reduce(function (x, y) { return x + y; }, 0) / vals.length, n: vals.length };
      }
      // 累计值：窗口内日均新增。快照还没拉开差距（平台没刷新）时不能给 0——
      // 那会让「有 8 万次调用的服务器」显示成 0.0 次/天，读起来像没人用。
      var gap = dayDiff(pts[0], pts[pts.length - 1]);
      if (vals.length < 2 || gap <= 0 || vals[vals.length - 1] <= vals[0]) {
        return { v: null, n: vals.length };
      }
      return { v: (vals[vals.length - 1] - vals[0]) / gap, n: vals.length };
    }

    Object.keys(spec.series).forEach(function (k) {
      var pts = slice(k, from, latest);
      var cur = stat(k, pts);
      if (!cur) return;
      var first = spec.series[k][pts[0]];
      var last = spec.series[k][pts[pts.length - 1]];
      // 变化率以前一个等长窗口为基准，比「首尾两天直接比」稳（能避开周末效应）
      var prev = stat(k, slice(k, prevFrom, prevTo));
      var delta = null;
      if (prev && prev.v !== null && isFinite(prev.v) && prev.v !== 0 &&
          cur.v !== null && isFinite(cur.v)) {
        delta = (cur.v - prev.v) / Math.abs(prev.v);
      }
      res.values[k] = { v: cur.v, n: cur.n, first: first, last: last, delta: delta };
    });
    return res;
  };

  /* 历史天数不足 90 天时，把滑块上限收到实际天数，免得拖了没反应 */
  Board.prototype.fitRange = function () {
    var spec = this.spec;
    if (!spec || !spec.series || spec.mode === 'date') return;
    var seen = {};
    Object.keys(spec.series).forEach(function (k) {
      Object.keys(spec.series[k]).forEach(function (d) { seen[d] = 1; });
    });
    var ds = Object.keys(seen).sort();
    if (!ds.length) { this.range.parentNode.hidden = true; return; }
    var avail = dayDiff(ds[0], ds[ds.length - 1]) + 1;
    var ticks = this.ctrl.querySelectorAll('.span-ticks button');
    if (avail <= 1) {
      // 刚开站，只有一天快照：滑块没有意义，藏起来
      this.range.parentNode.hidden = true;
      return;
    }
    if (avail < 90) {
      this.range.max = String(avail);
      [].forEach.call(ticks, function (b) {
        var n = parseInt(b.getAttribute('data-span'), 10);
        if (n > avail) b.hidden = true;
      });
      if (this.span > avail) {
        this.span = avail;
        this.range.value = String(avail);
      }
    }
  };

  Board.prototype.apply = function () {
    var spec = this.spec;
    var mode = spec ? spec.mode : 'region';
    var calc = mode === 'flow' || mode === 'stock' ? this.compute() : null;
    var unit = spec && spec.unit ? spec.unit : '';
    var i;
    var self = this;

    /* 1) 区域过滤 */
    var shown = 0, hiddenRegion = 0, unlabeled = 0;
    this.cards.forEach(function (c) {
      var r = c.getAttribute('data-region') || '';
      if (self.region !== 'all' && !r) unlabeled++;
      var ok = self.region === 'all' || r === (self.region === 'cn' ? '国内' : '国外');
      c.hidden = !ok;
      if (ok) shown++;
    });

    /* 2) 时间过滤（日期型榜单：按 YYYY-MM 截断） */
    if (mode === 'date' && this.span) {
      var anchor = this.spec.anchor || '';
      var lim = monthsAgo(anchor, this.span);
      this.cards.forEach(function (c) {
        if (c.hidden) return;
        var d = c.getAttribute('data-date') || '';
        if (d && d < lim) { c.hidden = true; shown--; }
      });
      this._lim = lim;
    }

    /* 3) 写值 + 排序 */
    var stale = 0;
    if (calc) {
      this.cards.forEach(function (c) {
        var k = c.getAttribute('data-k');
        var val = c.querySelector('.bd-val');
        if (!val) return;
        var rec = calc.values[k];
        var base = c.getAttribute('data-base');
        var dl = c.querySelector('.bd-delta');
        if (rec && rec.v !== null && isFinite(rec.v)) {
          var sign = mode === 'stock' && rec.v > 0 ? '+' : '';
          val.innerHTML = sign + withUnit(rec.v, unit, '/天');
          val.classList.remove('is-stale');
          if (dl) {
            dl.textContent = rec.delta === null ? '' : pct(rec.delta * 100);
            dl.className = 'bd-delta' +
              (rec.delta === null ? '' : rec.delta > 0 ? ' up' : rec.delta < 0 ? ' down' : '');
          }
        } else if (rec && rec.n === 1) {
          // 历史只有一天：显示抓到的累计值，为什么没有日均由下方说明行统一交代
          val.innerHTML = withUnit(rec.last, unit, '');
          val.classList.add('is-stale');
          stale++;
          if (dl) { dl.textContent = ''; dl.className = 'bd-delta'; }
        } else if (base) {
          val.innerHTML = withUnit(parseFloat(base), unit, '');
          val.classList.add('is-stale');
          stale++;
          if (dl) { dl.textContent = ''; dl.className = 'bd-delta'; }
        }
      });

      var sorted = this.cards.slice().sort(function (a, b) {
        var ra = calc.values[a.getAttribute('data-k')];
        var rb = calc.values[b.getAttribute('data-k')];
        var va = ra && ra.v !== null ? ra.v : -1;
        var vb = rb && rb.v !== null ? rb.v : -1;
        if (va === vb) {
          return self.order.indexOf(a.getAttribute('data-k')) - self.order.indexOf(b.getAttribute('data-k'));
        }
        return vb - va;
      });
      sorted.forEach(function (c) { self.root.appendChild(c); });
    }

    /* 4) 重编号：先把看得见的排前面（前三名高亮依赖 DOM 位置），再编号 */
    var vis = [], hid = [];
    [].forEach.call(this.root.children, function (c) {
      (c.hidden ? hid : vis).push(c);
    });
    if (hid.length) {
      vis.concat(hid).forEach(function (c) { self.root.appendChild(c); });
    }
    var n = 0;
    vis.forEach(function (c) {
      var rk = c.querySelector('.bd-rank');
      if (rk) rk.textContent = String(++n);
    });

    /* 5) 空态 */
    var empty = this.root.parentNode.querySelector('.bd-empty-tip');
    if (!shown && empty) empty.hidden = false;
    else if (empty) empty.hidden = true;

    /* 6) 说明行 */
    if (this.ctrl) {
      var bits = [];
      if (spec && spec.slider) {
        bits.push(spec.mode === 'date'
          ? '截到近 ' + this.span + ' 个月'
          : this._spanText(calc));
      }
      if (spec && spec.mode === 'flow') bits.push('值＝窗口内日均，不是总数');
      if (spec && spec.mode === 'stock') {
        bits.push(stale ? stale + ' 条快照还没拉开差距，先显示累计值' : '值＝窗口内日均新增');
      }
      if (calc) {
        var nd = 0;
        Object.keys(calc.values).forEach(function (k) {
          if (calc.values[k].delta !== null && calc.values[k].delta !== undefined) nd++;
        });
        if (nd) bits.push('箭头＝对比前一个等长窗口');
      }
      if (this.region !== 'all' && unlabeled) bits.push(unlabeled + ' 条未标注归属，未计入');
      if (!shown) bits.push('这一档没有数据');
      if (this.note) this.note.textContent = bits.join(' · ');
      if (this.out) {
        this.out.textContent = spec && spec.mode === 'date'
          ? '近 ' + this.span + ' 个月'
          : '近 ' + this.span + ' 天';
      }
      [].forEach.call(this.ctrl.querySelectorAll('.span-ticks button'), function (b) {
        b.classList.toggle('on', parseInt(b.getAttribute('data-span'), 10) === self.span);
      });
    }
  };

  Board.prototype._spanText = function (calc) {
    if (!calc) return '';
    return calc.from + ' → ' + calc.to;
  };

  function monthsAgo(anchor, months) {
    var y = parseInt(anchor.slice(0, 4), 10);
    var m = parseInt(anchor.slice(5, 7), 10) - (months - 1);
    while (m <= 0) { m += 12; y -= 1; }
    return y + '-' + (m < 10 ? '0' + m : m);
  }

  /* ---------- 启动 ---------- */
  function boot() {
    [].forEach.call(document.querySelectorAll('.board[data-board]'), function (el) {
      new Board(el).init();
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
