/* 由 tools/build_pages.py 从 llmcost_ui.html 抽出，别手改 */
/* ============================================================
   Token 价格追踪 · 纯原生 JS，数据来自 /api/data
   一卡一问：每张卡自己渲染，互不依赖（某张算不出来不拖垮整页）
   ============================================================ */

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

var S = null;                  // 服务端 payload
var FLT = {status:new Set(), q:'', esrc:''};   // API 状态筛选 / 关键词 / 事件来源
var SORT = {};                 // 每张表的排序状态：{key, dir}
var TB = {};                   // 表格注册表（表 id → 规格），供表头点击用

function $(id){ return document.getElementById(id); }
function esc(s){
  return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
  });
}
function num(v, d){ return (v === null || v === undefined || v === '' || isNaN(v)) ? (d === undefined ? null : d) : Number(v); }
function money(v, n){ var x = num(v); return x === null ? '—' : (n === 0 ? Math.round(x) : x.toFixed(n === undefined ? 2 : n)); }
function int(v){ var x = num(v); return x === null ? '—' : Math.round(x).toLocaleString('en-US'); }
function mult(v){ if(!v) return '—'; if(v >= 1e8) return (v/1e8).toFixed(1)+' 亿'; if(v >= 1e4) return Math.round(v/1e4)+' 万'; return String(Math.round(v)); }
function pct(v){ return num(v) === null ? '—' : Math.round(v*100) + '%'; }
var PK = {standard:'标准价', offpeak:'峰谷价', 'offpeak+promo':'峰谷+促销', promo:'促销价',
          cache:'含缓存', peak:'峰时价'};
var SRCT = {official:'官方', community_measured:'社区实测', community_estimate:'社区估算',
            'official+community':'官方+社区', measured:'实测', estimate:'估算', doc:'文档'};
function cn(map, v){ return map[v] || v; }

/* ---------- 主题 ---------- */
function isDark(){ return document.documentElement.dataset.theme === 'dark'; }
function chartSvg(name){
  var c = (S && S.charts) || {};
  return (isDark() ? (c[name+'_dark'] || c[name]) : c[name]) || '';
}
$('btnTheme').onclick = function(){ if (window.PB) PB.toggleTheme(); };
if (window.PB) PB.onTheme(function(){ if (S) render(); });

/* ---------- 取数 ---------- */
function load(force){
  $('btnRefresh').disabled = true;
  $('btnRefresh').setAttribute('aria-busy', 'true');
  if (force) $('sub').textContent = '重新核验中…';
  fetch(dataUrl(force), {cache:'no-store'})
    .then(function(r){ return r.json(); })
    .then(function(p){
      if (!p.ok) throw new Error(p.error || '算不出来');
      if (p._snapshot) SNAP_AT = p._snapshot.generated_at || '';
      S = p; render(); summary();
    })
    .catch(function(e){
      $('b-verdict').innerHTML = '<div class="empty">读不到数据：' + esc(e.message || e)
        + '<br>服务是仓库里的 <code>llmcost.py</code>，数据目录见 <code>$LLMCOST_DIR</code>（默认 <code>~/.pocket-llmcost</code>）。</div>';
    })
    .then(function(){ $('btnRefresh').disabled = false;
      $('btnRefresh').removeAttribute('aria-busy'); });
}
$('btnRefresh').onclick = function(){ load(true); };

function summary(){
  var m = S.meta, c = S.counts;
  $('sub').innerHTML = '核验 <b>' + int(m.obs) + '</b> 条观测 · <b>' + m.n_sources + '</b> 个来源'
    + '<span class="dot"></span>' + c.confirmed + ' 一致 / ' + c.conflict + ' 冲突 / '
    + (c.single_source + c.uncovered) + ' 待补'
    + '<span class="dot"></span>' + srcTag()
    + ' · 数据日 ' + esc(m.date) + ' · USD→CNY ' + m.fx;
}

/* ---------- 通用：图 ---------- */
function chart(name, hint, label){
  return (hint ? '<p class="hint">' + hint + '</p>' : '')
    + '<div class="chart-hint">← 左右滑动看完整图 →</div>'
    + '<div class="chart" data-chart="' + name + '" tabindex="0" role="group" aria-label="'
    + esc(label || name) + '">' + chartSvg(name) + '</div>';
}

/* ---------- 通用表格 ----------
   spec = {id, cols:[{k,label,cls,fmt,sort}], rows, empty}
   点表头排序、点同一列反向 —— 排序状态存在 SORT[id] 里，重新渲染不丢 */
function table(spec){
  TB[spec.id] = spec;
  var st = SORT[spec.id] || null;
  var rows = spec.rows.slice();
  if (st && st.k){
    var col = spec.cols.filter(function(c){ return c.k === st.k; })[0] || {};
    rows.sort(function(a, b){
      var x = a[st.k], y = b[st.k];
      if (col.num){ x = num(x, -Infinity); y = num(y, -Infinity); }
      else { x = String(x == null ? '' : x); y = String(y == null ? '' : y); }
      if (x < y) return st.dir === 'asc' ? -1 : 1;
      if (x > y) return st.dir === 'asc' ? 1 : -1;
      return 0;
    });
  }
  if (!rows.length) return '<div class="empty">' + esc(spec.empty || '没有符合条件的行') + '</div>';
  var head = spec.cols.map(function(c){
    var arrow = st && st.k === c.k ? '<span class="ar">' + (st.dir === 'asc' ? '▲' : '▼') + '</span>' : '';
    return '<th class="' + (c.cls || '') + (c.sort === false ? ' nosort' : '')
      + '" data-t="' + spec.id + '" data-k="' + c.k + '">' + c.label + arrow + '</th>';
  }).join('');
  var body = rows.map(function(r){
    return '<tr>' + spec.cols.map(function(c){
      var v = c.fmt ? c.fmt(r[c.k], r) : (r[c.k] == null ? '—' : r[c.k]);
      return '<td class="' + (c.cls || '') + '">' + v + '</td>';
    }).join('') + '</tr>';
  }).join('');
  return '<div class="tscroll"><table class="dt"><thead><tr>' + head + '</tr></thead>'
    + '<tbody>' + body + '</tbody></table></div>'
    + (spec.foot ? '<div class="foot mt">' + spec.foot + '</div>' : '');
}

/* 表头点击：全局委托，避免每次渲染重绑 */
document.addEventListener('click', function(e){
  var th = e.target.closest && e.target.closest('th[data-k]');
  if (!th) return;
  var id = th.getAttribute('data-t'), k = th.getAttribute('data-k');
  var spec = TB[id]; if (!spec) return;
  var col = spec.cols.filter(function(c){ return c.k === k; })[0];
  if (col && col.sort === false) return;
  var st = SORT[id];
  SORT[id] = (st && st.k === k)
    ? {k:k, dir: st.dir === 'asc' ? 'desc' : 'asc'}
    : {k:k, dir: (col && col.num) ? 'desc' : 'asc'};
  render();
});

/* ---------- 状态胶囊 ---------- */
function pill(status){
  var nm = (S.status_cn || {})[status] || status;
  return '<span class="pill s-' + status + '"><i></i>' + esc(nm) + '</span>';
}
function statusOf(r){ return pill(r.status); }
function arrowTag(d){
  if (Math.abs(d) < 1e-9) return '<span class="sm" style="display:inline">持平</span>';
  var up = d > 0;
  return '<span class="tag ' + (up ? 'bad' : 'ok') + '">' + (up ? '↑ 涨 ' : '↓ 跌 ')
    + Math.abs(d * 100).toFixed(0) + '%</span>';
}

/* ============================ 每张卡自己的渲染 ============================ */
var VIEW = {};

/* ① 本轮结论 */
VIEW.verdict = function(){
  var m = S.meta, c = S.counts, p = S.pick || {};
  var ch = p.cheapest_std || p.cheapest;
  var std = S.api.filter(function(r){ return r.output_cny && (r.price_kind || 'standard') === 'standard'; });
  var hi = std.slice().sort(function(a, b){ return b.output_cny - a.output_cny; })[0];
  var ratio = (ch && hi && ch.cny) ? Math.round(hi.output_cny / ch.cny) : 0;
  var claim = ch
    ? '最便宜的标准档是 <b>' + esc(ch.display) + '</b>；最贵的 <b>' + esc(hi ? hi.display : '—')
      + '</b> 每百万输出要 <b>' + money(hi ? hi.output_cny : null) + ' 元</b>，是它的 <b>' + ratio + ' 倍</b>。'
      + '同一个「输出 token」口径，价差到这个量级 —— 先定选型，再谈提示词优化。'
      + ((ch && ch.status && ch.status !== 'confirmed')
          // 标签另起一行：原先夹在句子中间，窄屏会在标签和「，」之间断行，逗号跑到行首
          ? '<br><span class="tag warn">'
            + esc((S.status_cn || {})[ch.status] || ch.status) + '</span>'
            + ' 这条最低价只有一个来源对上，等第二个来源再当定论。'
          : '')
    : '本轮没有可用的 API 记录。';
  var bp = p.best_plan, expired = bp && bp.promo && bp.promo < m.date;
  var CV = {confirmed:'--ok', single_source:'--warn', stale:'--warn', conflict:'--bad',
            incomparable:'--vio', unverified:'--ink3', uncovered:'--ink3'};
  var tot = Math.max(1, S.api.length);
  var segs = S.status_order.filter(function(s){ return c[s]; }).map(function(s){
    return '<i style="width:' + (c[s] / tot * 100) + '%;background:var(' + (CV[s] || '--ink3') + ')"></i>';
  }).join('');
  return {
    meta: '数据日 ' + esc(String(m.date).slice(5)) + ' · ' + (m.ms || 0) + ' ms',
    body: '<div class="big">' + (ch ? money(ch.cny) : '—') + '<small>元 / 百万输出 token</small></div>'
      + '<div class="claim">' + claim + '</div>'
      + '<div class="facts">'
        + '<div><div class="side-k">套餐最快回本</div>'
          + '<div class="side-v">' + (bp ? mult(bp.break_even) + '<small>百万 / 月</small>' : '—') + '</div>'
          + '<div class="side-f">' + (bp ? esc(bp.platform + ' · ' + bp.plan) + '，月费 ¥' + money(bp.monthly, 1)
              : '本轮没有可折算套餐')
            + (expired ? ' · <span style="color:var(--bad)">活动已到期</span>'
                       : (bp && bp.promo ? ' · 限时到 ' + esc(bp.promo) : '')) + '</div></div>'
        + '<div><div class="side-k">数据可核验度</div>'
          + '<div class="side-v">' + c.confirmed + '<small>/ ' + S.api.length + ' 多源一致</small></div>'
          + '<div class="sbar">' + segs + '</div>'
          + '<div class="side-f">' + c.conflict + ' 条冲突 · ' + c.single_source + ' 条单源 · '
            + c.incomparable + ' 条口径不可比 · 观测 ' + int(m.obs) + ' 条</div></div>'
      + '</div>'
      + (function(){
          var lb = S.leaderboard || {}, bv = (lb.summary || {}).best_value;
          if (!bv) return '';
          return '<div class="pick">按单位成本选：<b>' + esc(bv.display) + '</b> '
            + money(bv.price, 2) + ' 元 / 百万输出，LMArena 综合 <b>' + Math.round(bv.score)
            + ' 分</b>（第 ' + bv.rank + ' 名）—— 往上加钱能买到的分，见「价格 × 实力」卡。</div>';
        })()
  };
};

/* ② 价格快照：跟工作台那张 Token 价格追踪卡同一套字段 */
VIEW.snapshot = function(){
  var sn = S.snapshot || {};
  if (!sn.at) return {meta: '', body: '<div class="empty">快照还没生成。</div>'};
  var hs = sn.history || {}, pf = sn.platforms || {}, ct = sn.counts || {};
  var cheap = sn.cheapest || {}, bp = sn.best_plan || {};
  var topTxt = (hs.top || []).map(function(x){
    return esc(x.name) + ' ' + (x.pct > 0 ? '↑' : '↓') + Math.abs(x.pct) + '%';
  }).join('、');
  var rows = [
    ['最低价', esc(cheap.name || '—') + ' · <b>' + money(cheap.cny) + '</b> 元/百万'
      + (cheap.status && cheap.status !== 'confirmed'
          ? '<span class="sm">' + esc((S.status_cn || {})[cheap.status] || cheap.status) + '</span>' : '')],
    ['回本点', esc(bp.name || '—') + (bp.cny != null ? ' · <b>' + money(bp.cny, 3) + '</b> 元/百万' : '')
      + (bp.monthly ? '<span class="sm">月费 ¥' + money(bp.monthly, 1) + ' · 打平 ' + mult(bp.break_even) + ' 百万/月</span>' : '')],
    ['核验', '<b>' + (ct.confirmed || 0) + '</b>/' + (sn.n_api || 0) + ' 多源一致'
      + (ct.conflict ? ' · <span style="color:var(--bad)">' + ct.conflict + ' 条冲突</span>' : '')
      + '<span class="sm">' + int(sn.obs) + ' 条观测 · ' + (sn.n_sources || 0) + ' 个来源</span>'],
    ['价格史', esc(String(hs.from || '').slice(5)) + ' → ' + esc(String(hs.to || '').slice(5))
      + ' · ' + (hs.n_dates || 0) + ' 期 ' + (hs.n_models || 0) + ' 模型'
      + (hs.n_changed ? ' · <b>' + hs.n_changed + ' 次调价</b>' : ' · 一个都没动')
      + (topTxt ? '<span class="sm">' + topTxt + '</span>' : '')],
    ['平台', (pf.n || 0) + ' 个平台'
      + (pf.spread_max ? ' · 同模型最大差 <b>' + pf.spread_max + '×</b>' : '')
      + (pf.spread_median ? '<span class="sm">中位 ' + pf.spread_median + '×</span>' : '')]
  ];
  return {
    meta: '数据 ' + esc(String(sn.at).slice(5)) + (S.meta.age > 1 ? '（' + S.meta.age + ' 天前）' : ''),
    body: '<div class="kv">' + rows.map(function(r){
        return '<div class="row"><div class="k">' + r[0] + '</div><div class="v">' + r[1] + '</div></div>';
      }).join('') + '</div>'
      + ((sn.conflicts || []).length
          ? '<div class="foot mt">待复核：'
            + sn.conflicts.slice(0, 2).map(function(x){
                return esc(x.name) + ' ' + esc(x.metric) + ' 与上游差 <b style="color:var(--bad)">'
                  + x.rel + '%</b>';
              }).join('；') + '。</div>'
          : '<div class="foot mt">本轮没有数值冲突。</div>')
      + '<div class="foot mt">与工作台那张「Token 价格追踪」卡同源（都读 <code>out/accuracy.json</code>）。</div>'
  };
};

/* ③ 数据规模与质量 */
VIEW.stats = function(){
  var c = S.counts, m = S.meta;
  var cells = [
    {k:'追踪 API 模型', v:S.api.length, f:'统一到元 / 百万 token', cls:''},
    {k:'订阅套餐', v:S.plans.length, f:S.plans.filter(function(x){return x.convertible;}).length + ' 个可折算', cls:''},
    {k:'本地方案', v:S.rigs.length, f:'折旧 + 电费折算', cls:''},
    {k:'调价事件', v:S.events.length, f:'含外部 ' + S.events.filter(function(e){return e.src==='LLMTracker';}).length + ' 条', cls:''},
    {k:'多源一致', v:c.confirmed, f:'≥2 个独立来源对上', cls:'ok'},
    {k:'数值冲突', v:c.conflict, f:'待回官方页复核', cls:c.conflict ? 'bad' : ''},
    {k:'单源待补', v:c.single_source + c.uncovered, f:'还缺第二个来源', cls:'warn'},
    {k:'口径不可比', v:c.incomparable, f:'促销 / 峰谷 / 托管', cls:'vio'}
  ];
  return {
    meta: int(m.obs) + ' 条观测 · ' + m.n_sources + ' 个来源',
    body: '<div class="strip">' + cells.map(function(x){
      return '<div class="cell ' + x.cls + '"><div class="k">' + x.k + '</div><b>' + int(x.v)
        + '</b><div class="f">' + esc(x.f) + '</div></div>';
    }).join('') + '</div>'
  };
};

/* ④ 模型天梯榜：LMArena（HF）+ 幻觉率（GitHub），落到我们跟踪的 15 个模型上 */
VIEW.ladder = function(){
  var lb = S.leaderboard || {};
  if (!lb.ready){
    return {meta:'', body:'<div class="empty">还没有榜单数据：跑一次 <code>python3 llmcost_leaderboard.py</code>，'
      + '从 HuggingFace 的 LMArena 数据集与 GitHub 的幻觉率榜抓一份。</div>'};
  }
  var rows = (lb.rows || []).slice().sort(function(a, b){
    if (a.score && b.score) return b.score - a.score;
    return (a.score ? -1 : 1) - (b.score ? -1 : 1) || a.price - b.price;
  });
  var dim = function(r, k){
    var d = (r.dims || {})[k];
    if (!d) return '<span class="mut">—</span>';
    if (d.unit === 'winrate') return '<span class="mut">#' + d.rank + '</span>';
    return '<b>' + Math.round(d.score) + '</b><span class="sm">#' + d.rank + '</span>';
  };
  var t = table({
    id:'ladder', rows:rows, empty:'',
    cols:[
      {k:'display', label:'模型', fmt:function(v, r){
          return '<span class="nm">' + esc(v) + '</span><span class="sm">'
            + esc(r.arena || '未上榜：' + (r.match === 'cjk' ? '中文名与外文榜对不上' : '榜上没有这个型号'))
            + (r.tier ? ' · ' + esc(r.tier) : '') + '</span>';
        }},
      {k:'rank', label:'综合', cls:'r', num:true, fmt:function(v, r){
          return r.score ? '<b>' + Math.round(r.score) + '</b><span class="sm">#' + (r.rank || '—') + '</span>'
            : '<span class="mut">未上榜</span>';
        }},
      /* 价格紧跟分数：这张卡要回答的就是「这个分要多少钱」，
         手机上一屏只露得下三四列，价格必须排在前面，不能被挤出屏幕。
         单位写在表头一次，行里只留数字，15 行重复「元 / 百万」是噪音 */
      {k:'price', label:'输出价<span class="thu">元 / 百万</span>', cls:'r', num:true, fmt:function(v){
          return money(v, 2);
        }},
      {k:'coding', label:'代码', cls:'r', sort:false, fmt:function(v, r){ return dim(r, 'coding'); }},
      {k:'chinese', label:'中文', cls:'r', sort:false, fmt:function(v, r){ return dim(r, 'chinese'); }},
      {k:'vision', label:'视觉', cls:'r', sort:false, fmt:function(v, r){ return dim(r, 'vision'); }},
      {k:'webdev', label:'前端', cls:'r', sort:false, fmt:function(v, r){ return dim(r, 'webdev'); }},
      {k:'halluc', label:'幻觉率', cls:'r', num:true, fmt:function(v, r){
          return r.halluc ? '<b>' + r.halluc.rate.toFixed(1) + '%</b>'
            + '<span class="sm">引用 ' + Math.round(r.halluc.citation) + '%</span>'
            : '<span class="mut">—</span>';
        }},
      {k:'pareto', label:'前沿', sort:false, fmt:function(v, r){
          return r.pareto ? '<span class="tag ok">在</span>'
            : (r.dominated_by ? '<span class="sm" style="display:inline">被 ' + esc(r.dominated_by) + ' 支配</span>' : '');
        }}
    ],
    foot:'榜：<b>' + esc(lb.meta.hf_dataset) + '</b>（快照 ' + esc(String(lb.meta.date).slice(0, 10))
      + '，' + (lb.meta.n_models || 0) + ' 个型号在综合榜）。幻觉率：<b>' + esc(lb.meta.gh_repo)
      + '</b>，只覆盖到 ' + (lb.meta.n_halluc || 0) + ' 个型号，我们这 15 个里只有少数有数。'
  });
  var s = lb.summary || {}, top = (lb.top || []).slice(0, 3);
  return {
    meta: (s.n_matched || 0) + ' / ' + (s.n_total || 0) + ' 个在榜',
    body: (top.length ? '<p class="hint">综合榜天花板：' + top.map(function(x){
        return '<b>' + esc(x.model) + '</b> ' + Math.round(x.score);
      }).join(' · ') + '。下面是<b>我们跟踪的 ' + (s.n_total || 0) + ' 个</b>各自的位置 —— '
      + '同一模型的 High / Max 档取分最高者。</p>' : '')
      + t
  };
};

/* ⑤ 价格 × 实力：散点 + 前沿一句话 */
VIEW.value = function(){
  var lb = S.leaderboard || {};
  if (!lb.ready || !(lb.summary || {}).frontier){
    return {meta:'', body:'<div class="empty">还没有榜单数据，先跑 <code>python3 llmcost_leaderboard.py</code>。</div>'};
  }
  var s = lb.summary, f = s.frontier || [];
  var line;
  if (f.length){
    var steps = [];
    for (var i = 1; i < f.length; i++){
      steps.push('加 <b>' + money(f[i].price - f[i - 1].price, 0) + ' 元</b>换 <b>'
        + (f[i].score - f[i - 1].score).toFixed(1) + ' 分</b>');
    }
    line = '前沿只有 <b>' + f.length + ' 个</b>：' + f.map(function(x){
        return esc(x.display) + '（' + money(x.price, 2) + ' 元 / ' + Math.round(x.score) + ' 分）';
      }).join(' → ')
      + (steps.length ? '；沿它往上走，' + steps.join('、') : '') + '。';
  } else {
    line = '没有可比的价格 / 分数配对。';
  }
  var worst = s.priciest && s.priciest.dominated_by
    ? '<br>最贵的 <b>' + esc(s.priciest.display) + '</b> 花 ' + money(s.priciest.price, 0)
      + ' 元，分反而被 <b>' + esc(s.priciest.dominated_by) + '</b> 压着。' : '';
  return {
    meta: (s.n_matched || 0) + ' 个可比 · ' + (s.n_dominated || 0) + ' 个被支配',
    body: '<p class="hint">' + line + worst + '</p>'
      + chart('ladder', '', '价格与实力的散点图')
  };
};

/* ⑥ 价格走势（平台全景） */
VIEW.trend = function(){
  var p = S.panorama || {}, sm = p.summary || {};
  if (!(p.lines || []).length){
    return {meta:'', body:'<div class="empty">价格库还是空的：先跑 <code>python3 llmcost_platforms.py</code>。</div>'};
  }
  return {
    meta: (sm.n_models||0) + ' 模型 · ' + (sm.n_platforms||0) + ' 平台 · ' + (sm.n_lines||0) + ' 条线',
    body: chart('price_panorama',
      '一根时间轴，' + (sm.n_models || 0) + ' 个模型 × ' + (sm.n_platforms || 0)
      + ' 个平台的输出价（对数轴）。<b>颜色是模型，线型是平台类型</b>：实线厂商自营、短虚线第三方、'
      + '点线云厂商。横轴<b>逐日</b>：月初粗线、每周一一格细线，观测日直接标日期，'
      + '阶梯在观测日拐弯 —— 哪天变的价就是哪天；圆点指上去能读出确切日期与价格。点右侧图例只看一个模型。',
      '平台价格全景')
  };
};

/* ⑦ 全盘水位 */
VIEW.level = function(){
  var h = S.history || {}, sm = h.summary || {};
  if (!(h.models || []).length){
    return {meta:'', body:'<div class="empty">还没有价格史：把月度点填进 <code>data/price_history.csv</code>。</div>'};
  }
  return {
    meta: (sm.span_from || '') + ' → ' + (sm.span_to || '') + ' · ' + (sm.n_changed || 0) + ' 次调价',
    body: chart('api_history',
      '上：全盘输出价水位（几何均值）与 P25–P75 分布带；下：期间真有过调价的模型。'
      + '横轴逐日、阶梯线，拐点就在观测日当天 —— 不是「大概那阵子」。'
      + '三个月里 ' + (sm.n_models || 0) + ' 个模型只有 <b>' + (sm.n_changed || 0)
      + ' 个</b>动过价，全盘水位 <b>' + (sm.level_chg >= 0 ? '+' : '')
      + (sm.level_chg * 100).toFixed(1) + '%</b> —— 大多数没动，这本身就是结论。',
      '全盘水位')
  };
};

/* ⑧ 调价日志 */
VIEW.moves = function(){
  var h = S.history || {};
  var t = table({
    id:'histchg', rows:h.changes || [], empty:'这段时间没有模型调价',
    cols:[
      {k:'date', label:'生效日', fmt:function(v){ return '<span class="nm">' + esc(v) + '</span>'; }},
      {k:'display', label:'模型', fmt:function(v, r){
          return esc(v) + '<span class="sm">' + esc(r.model) + '</span>'; }},
      {k:'from', label:'原价 → 现价', cls:'r', num:true, fmt:function(v, r){
          return '<span style="white-space:nowrap">' + money(r.from, 2) + ' → <b>' + money(r.to, 2)
            + '</b> <span class="sm" style="display:inline">' + esc(r.currency) + '</span></span>'; }},
      {k:'pct', label:'幅度', cls:'r', num:true, fmt:function(v){
          return '<span style="white-space:nowrap">' + arrowTag(v) + '</span>'; }},
      {k:'basis', label:'依据', sort:false, fmt:function(v){
          var B = {official:'官方现价', event:'按事件回溯', carry:'现值回溯', snapshot:'自动快照'};
          return '<span class="tag ' + (v === 'official' ? 'ok' : (v === 'event' ? 'warn' : '')) + '">'
            + esc(B[v] || v) + '</span>'; }}
    ],
    foot:'只有这几种记录才算「追踪」的产出：一条带生效日与依据的调价，比一张当下价目表有用。'
  });
  return {meta: (h.changes || []).length + ' 条', body: t};
};

/* ⑨ 月度价格矩阵 */
VIEW.matrix = function(){
  var h = S.history || {}, dates = h.dates || [], models = h.models || [];
  if (!models.length) return {meta:'', body:'<div class="empty">还没有价格史。</div>'};
  var cols = [
    {k:'display', label:'模型', fmt:function(v, r){
        return '<span class="nm">' + esc(v) + '</span><span class="sm">' + esc(r.currency) + '</span>'; }}
  ];
  dates.forEach(function(d, i){
    cols.push({k:'d' + i, label:d.slice(5), cls:'r', num:true, fmt:function(v, row){
      var s = row.series, cur = null, prev = null;
      for (var k = 0; k < s.length; k++){
        if (s[k][0] === d) cur = s[k][1];
        else if (s[k][0] < d) prev = s[k][1];
      }
      if (cur === null) return '<span class="mut">—</span>';
      var moved = (prev !== null && Math.abs(cur - prev) > 1e-9);
      var col = moved ? (cur > prev ? 'var(--bad)' : 'var(--ok)') : '';
      return '<span style="' + (moved ? 'color:' + col + ';font-weight:600' : '') + '">'
        + money(cur, 2) + (moved ? (cur > prev ? ' ▲' : ' ▼') : '') + '</span>';
    }});
  });
  cols.push({k:'chg', label:'期间', cls:'r', num:true, fmt:function(v, r){
    return '<span style="white-space:nowrap">' + arrowTag(r.chg) + '</span>'; }});
  return {
    meta: models.length + ' 行 × ' + dates.length + ' 期',
    body: table({id:'histmx', rows:models, cols:cols,
      foot:'值 = 输出价折人民币 / 百万 token（USD 按 1 美元 ' + (h.fx || '—')
        + ' 元换算）；红色涨、绿色跌（A 股口径），没变的不上色。'})
  };
};

/* ⑩ API 价目明细 */
VIEW.apitable = function(){
  var rows = S.api.filter(function(r){
    if (FLT.status.size && !FLT.status.has(r.status)) return false;
    if (FLT.q){
      var q = FLT.q.toLowerCase();
      if ((r.provider + ' ' + r.display + ' ' + r.model + ' ' + (r.note || '')).toLowerCase().indexOf(q) < 0) return false;
    }
    return true;
  });
  var chips = '<div class="chips"><button class="chip" data-st="" aria-pressed="' + (!FLT.status.size)
    + '">全部 <em>' + S.api.length + '</em></button>'
    + S.status_order.filter(function(s){ return S.counts[s]; }).map(function(s){
        return '<button class="chip" data-st="' + s + '" aria-pressed="' + FLT.status.has(s) + '">'
          + '<i></i>' + esc(S.status_cn[s]) + ' <em>' + S.counts[s] + '</em></button>';
      }).join('') + '</div>';
  var t = table({
    id:'api', rows:rows, empty:'没有符合筛选的模型',
    cols:[
      {k:'provider', label:'厂商', fmt:function(v){ return '<span class="nm">' + esc(v) + '</span>'; }},
      {k:'display', label:'模型', fmt:function(v, r){
          var tags = '';
          if ((r.price_kind || 'standard') !== 'standard') tags += '<span class="tag warn">※ ' + esc(cn(PK, r.price_kind)) + '</span>';
          if (r.scope && r.scope !== 'first_party') tags += '<span class="tag">第三方渠道</span>';
          if (r.promo_until) tags += '<span class="tag warn">促销至 ' + esc(r.promo_until) + '</span>';
          return esc(v) + tags + '<span class="sm">' + esc(r.model) + '</span>';
        }},
      {k:'output_cny', label:'输出价', cls:'r', num:true, fmt:function(v, r){
          return '<b>' + money(v) + '</b><span class="sm">' + money(r.output, 3) + ' ' + esc(r.currency) + '</span>';
        }},
      {k:'input_cny', label:'输入价', cls:'r', num:true, fmt:function(v){ return money(v); }},
      {k:'cache_cny', label:'缓存命中', cls:'r', num:true, fmt:function(v){ return v == null ? '—' : money(v); }},
      {k:'status', label:'准确性', sort:false, fmt:function(v, r){
          var extra;
          if (r.conflicts.length) extra = '<span class="sm" style="color:var(--bad)">' + r.conflicts.length + ' 处偏差 &gt;'
            + Math.round(S.meta.policy.conflict_tolerance * 100) + '%</span>';
          else if (r.n_sources) extra = '<span class="sm">' + esc(r.agreeing_sources.join('、')) + '</span>';
          else if (r.n_matched) extra = '<span class="sm">有观测但口径不同</span>';
          else extra = '<span class="sm">无交叉观测</span>';
          return statusOf(r) + extra;
        }},
      {k:'verified_at', label:'核验', cls:'r', fmt:function(v, r){
          return esc(v) + '<span class="sm">' + (r.age > 0 ? r.age + ' 天前' : '今天') + '</span>';
        }}
    ]
  });
  return {
    meta: rows.length + ' / ' + S.api.length + ' 行',
    body: '<div class="bar">' + chips + '<div class="grow"></div>'
      + '<label class="search"><span style="color:var(--ink3);font-size:12px">⌕</span>'
      + '<input id="apiQ" placeholder="厂商 / 模型 / 备注" value="' + esc(FLT.q) + '"></label></div>'
      + t
  };
};

/* ⑪ API 输出价排名图 */
VIEW.apichart = function(){
  return {
    meta: S.api.length + ' 个模型 · 对数轴',
    body: chart('api_prices',
      '按输出价升序。<b>条长读价格、条色读数据可信度</b>：多源一致是灰蓝，单源偏黄，冲突偏红；'
      + '<span class="tag">※</span> 表示峰谷价或促销价，不能和标准价直接取最小值排序。',
      'API 输出价对比')
  };
};

/* ⑫ 模型 × 平台报价 */
VIEW.panotable = function(){
  var p = S.panorama || {}, models = p.models || [], lines = p.lines || [];
  if (!lines.length) return {meta:'', body:'<div class="empty">价格库还是空的。</div>'};
  var KM = {official:'官方', cloud:'云厂商', aggregator:'第三方'};
  var badge = function(k){
    var cls = k === 'official' ? 'ok' : (k === 'cloud' ? 'warn' : '');
    return '<span class="tag ' + cls + '">' + (KM[k] || k) + '</span>';
  };
  var byModel = {};
  lines.forEach(function(l){ (byModel[l.model] = byModel[l.model] || []).push(l); });
  var rows = models.map(function(m, i){
    var ls = (byModel[m.model] || []).slice().sort(function(a, b){ return a.last - b.last; });
    var xid = 'px' + i;
    var sp = (m.spread == null) ? '<span class="mut">单平台</span>'
      : (m.spread <= 1.03 ? '<span class="mut">基本持平</span>'
         : '<b style="color:var(--bad)">' + m.spread.toFixed(1) + '×</b>');
    var official = m.official != null ? money(m.official, 2)
      + (m.official_low != null && m.official_low !== m.official
          ? '<span class="sm">低谷 ' + money(m.official_low, 2) + '</span>' : '')
      : '<span class="mut">—</span>';
    var minNote = (m.min_kind === 'cloud' && m.official && m.min < m.official * 0.97)
      ? '<span class="sm" style="color:var(--warn)">可能未跟进调价</span>' : '';
    var main = '<tr class="xrow" data-x="' + xid + '" tabindex="0" role="button"'
      + ' aria-expanded="false" aria-controls="' + xid + '"'
      + ' aria-label="展开 ' + esc(m.display) + ' 在各平台的报价">'
      + '<td><span class="nm">' + esc(m.display) + '</span><span class="sm">'
        + esc(m.model) + '</span></td>'
      + '<td class="r">' + official + '</td>'
      + '<td class="r">' + money(m.min, 2) + '<span class="sm">' + esc(m.min_name) + '</span>' + minNote + '</td>'
      + '<td class="r">' + money(m.max, 2) + '<span class="sm">' + esc(m.max_name) + '</span></td>'
      + '<td class="r">' + sp + '</td>'
      + '<td class="r">' + m.n_platforms + '</td></tr>';
    var detail = '<tr class="xbody" id="' + xid + '" style="display:none"><td colspan="6">'
      + '<table class="dt sub"><thead><tr><th>平台</th><th>类型</th><th class="r">当前价</th>'
      + '<th class="r">相对官方</th><th class="r">观测</th></tr></thead><tbody>'
      + ls.map(function(l){
          var ratio = (m.official && l.last && l.kind !== 'official') ? l.last / m.official : null;
          var rc = ratio == null ? '<span class="mut">基准</span>'
            : (ratio > 1.001 ? '<span style="color:var(--bad)">+' + ((ratio - 1) * 100).toFixed(0) + '%</span>'
              : (ratio < 0.999 ? '<span style="color:var(--ok)">' + ((ratio - 1) * 100).toFixed(0) + '%</span>'
                : '<span class="mut">同价</span>'));
          return '<tr><td>' + esc(l.platform_name) + '</td><td>' + badge(l.kind) + '</td>'
            + '<td class="r">' + money(l.last, 2) + '</td><td class="r">' + rc + '</td>'
            + '<td class="r">' + l.series.length + ' 点</td></tr>';
        }).join('')
      + '</tbody></table></td></tr>';
    return main + detail;
  }).join('');
  return {
    meta: models.length + ' 个模型',
    body: '<div class="tscroll"><table class="dt"><thead><tr>'
      + '<th>模型</th><th class="r">官方价</th><th class="r">最便宜</th><th class="r">最贵</th>'
      + '<th class="r">价差</th><th class="r">平台</th></tr></thead><tbody>' + rows
      + '</tbody></table></div>'
      + '<div class="foot mt">价差只比<b>第三方之间</b>；官方低谷价是另一个商品口径，混进来会把口径差算成渠道差。</div>'
  };
};

/* ⑫b 同模型 · 跨渠道价差
   不按平台排、也不按模型列表排，而是把「同一个模型在几家买」摊成一条价格带：
   点越散 = 换渠道越值得比价。数字只给最低价与价差，逐家明细点开看。 */
VIEW.chanmap = function(){
  var p = S.panorama || {}, models = p.models || [], lines = p.lines || [];
  if (!lines.length) return {meta:'', body:'<div class="empty">价格库还是空的。</div>'};
  var KM = {official:'厂商自营', cloud:'云厂商', aggregator:'第三方'};
  var lg = function(v){ return Math.log(v) / Math.LN10; };
  var vals = lines.map(function(l){ return +l.last; }).filter(function(v){ return v > 0; });
  var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals);
  /* 轴端点取 1/2/5×10ⁿ 的整档：刻度落在整数上，点不会贴着边框 */
  var nice = function(v, up){
    var e = Math.floor(lg(v)), m = v / Math.pow(10, e), n;
    if (up) n = m <= 1 ? 1 : (m <= 2 ? 2 : (m <= 5 ? 5 : 10));
    else n = m >= 5 ? 5 : (m >= 2 ? 2 : 1);
    return n * Math.pow(10, e);
  };
  var d0 = nice(lo, false), d1 = nice(hi, true), span = lg(d1) - lg(d0);
  var px = function(v){ return (lg(v) - lg(d0)) / span * 100; };
  var ticks = [];
  for (var e = Math.round(lg(d0)); e <= Math.round(lg(d1)); e++){
    [1, 2, 5].forEach(function(k){
      var v = k * Math.pow(10, e);
      if (v > d0 * 0.999 && v < d1 * 0.999) ticks.push(v);
    });
  }
  var grids = ticks.map(function(v){
    return '<i class="cm-gl" style="left:' + px(v).toFixed(2) + '%"></i>';
  }).join('');

  var byModel = {};
  lines.forEach(function(l){ (byModel[l.model] = byModel[l.model] || []).push(l); });
  var rows = models.slice().sort(function(a, b){
    var x = a.spread || 0, y = b.spread || 0;
    if (Math.abs(y - x) > 1e-9) return y - x;
    return (b.n_platforms || 0) - (a.n_platforms || 0);
  });

  var body = rows.map(function(m, i){
    var ls = (byModel[m.model] || []).slice().sort(function(a, b){ return a.last - b.last; });
    /* 同价的渠道合并成一个点：一格里七八家都卖 8.64，画七个点只会糊成一条 */
    var cl = {}, order = [];
    ls.forEach(function(l){
      var k = (+l.last).toFixed(3);
      if (!cl[k]){ cl[k] = {v: +l.last, ls: []}; order.push(k); }
      cl[k].ls.push(l);
    });
    var cs = order.map(function(k){ return cl[k]; });
    var lowv = cs.length ? cs[0].v : 0;
    var dots = cs.map(function(c){
      var kinds = {};
      c.ls.forEach(function(l){ kinds[l.kind] = 1; });
      var kind = kinds.official ? 'official' : (kinds.cloud ? 'cloud' : 'aggregator');
      var offpeak = c.ls.some(function(l){ return l.tier && l.tier !== 'standard'; });
      var cls = 'cm-pt k-' + kind + (offpeak ? ' t-offpeak' : '')
        + (cs.length > 1 && c.v === lowv ? ' low' : '');
      var tip = c.ls.map(function(l){
        return l.platform_name + ' ¥' + money(l.last, 2) + '（' + (KM[l.kind] || l.kind)
          + (l.tier && l.tier !== 'standard' ? ' · 谷时价' : '') + '）';
      }).join('\n');
      var pos = px(c.v).toFixed(2);
      return '<i class="' + cls + '" style="left:' + pos + '%" title="' + esc(tip) + '"></i>'
        + (c.ls.length > 1 ? '<span class="cm-n" style="left:' + pos + '%">×'
            + c.ls.length + '</span>' : '');
    }).join('');
    var nn = cs.length ? cs[0].ls.map(function(l){ return l.platform_name; }) : [];
    var minName = nn.length
      ? nn[0] + (nn.length > 1 ? ' 等 ' + nn.length + ' 家' : '') : '—';
    /* 最低价落在谷时价上要标出来：那是另一个商品，别让人以为白天也能买到 */
    if (cs.length && cs[0].ls.every(function(l){ return l.tier && l.tier !== 'standard'; })){
      minName += ' · 谷时';
    }
    var sp = m.spread;
    var spTxt = sp == null ? (ls.length > 1 ? '—' : '单家')
      : (sp <= 1.02 ? '持平' : sp.toFixed(1) + '×');
    var xid = 'cm' + i;
    var det = ls.map(function(l){
      /* 只跟标准价的官方价比：官方低谷价是另一个商品，拿来当基准会把口径差算成渠道差 */
      var rel = (m.official && m.official_tier === 'standard'
        && l.kind !== 'official' && (!l.tier || l.tier === 'standard'))
        ? l.last / m.official : null;
      var d = (rel == null || Math.abs(rel - 1) <= 0.005) ? ''
        : '<span style="color:var(--' + (rel > 1 ? 'bad' : 'ok') + ')">'
          + (rel > 1 ? '+' : '') + Math.round((rel - 1) * 100) + '%</span>';
      return '<span class="c' + (cs.length > 1 && l.last === lowv ? ' low' : '') + '">'
        + '<i class="k-' + l.kind + '"></i>' + esc(l.platform_name)
        + ' <b>¥' + money(l.last, 2) + '</b>' + (d ? ' ' + d : '')
        + (l.tier && l.tier !== 'standard'
            ? '<span class="tag warn" style="margin-left:1px">谷时</span>' : '')
        + '</span>';
    }).join('');
    return '<div class="cm-row" data-x="' + xid + '" tabindex="0" role="button"'
      + ' aria-expanded="false" aria-controls="' + xid + '">'
      + '<div class="cm-nm">' + esc(m.display) + '<span class="sm">' + esc(m.model)
        + (ls.length > 1 ? ' · ' + ls.length + ' 家' : ' · 仅 1 家') + '</span></div>'
      + '<div class="cm-track">' + grids + dots + '</div>'
      + '<div class="cm-min">¥' + money(lowv, 2) + '<span class="sm">' + esc(minName) + '</span></div>'
      + '<div class="cm-sp' + (sp >= 2 ? ' wide' : '') + '">' + spTxt + '</div>'
      + '</div>'
      + '<div class="cm-det" id="' + xid + '" style="display:none"><div class="set">' + det + '</div></div>';
  }).join('');

  var axis = '<div class="cm-axis"><div>模型</div><div class="cm-scale">'
    + ticks.map(function(v){
        return '<span style="left:' + px(v).toFixed(2) + '%">¥' + (v >= 1 ? Math.round(v) : v) + '</span>';
      }).join('')
    + '</div><div class="h">最低价<span style="font-size:9px;opacity:.8"> 元/百万</span></div>'
    + '<div class="h sp">价差</div></div>';

  var legend = '<div class="cm-legend">'
    + '<span><i class="o"></i>厂商自营</span><span><i class="c"></i>云厂商</span>'
    + '<span><i class="a"></i>第三方</span><span><i class="low"></i>这一行最便宜</span>'
    + '<span><i class="d"></i>谷时价（另一口径）</span>'
    + '<span style="margin-left:auto">横轴取对数</span></div>';

  var smy = p.summary || {};
  var top = rows.filter(function(m){ return m.spread; })[0];
  var hint = '<p class="hint">同一个模型，各家卖的不是一个价：' + models.length + ' 个模型在 '
    + (smy.n_platforms || 0) + ' 个渠道上有 ' + lines.length + ' 条报价，价差中位 <b>'
    + (smy.spread_median || '—') + '×</b>'
    + (top ? '，最悬殊的是 <b>' + esc(top.display) + ' ' + top.spread.toFixed(1) + '×</b>' : '')
    + '。点一行展开逐家报价。</p>';

  var wb = (S.plans || []).filter(function(x){
    return /WorkBuddy/.test(x.platform) && x.convertible;
  }).sort(function(a, b){ return a.cny_per_1m - b.cny_per_1m; });
  var subs = '<div class="cm-subs">'
    + '<div class="k">订阅制渠道<span>按会员额度计费，没有按量价，不进上面这条价格带</span></div>'
    + '<div class="r2">'
    + wb.map(function(x){
        return '<span class="c">' + esc(x.platform) + ' '
          + esc(String(x.plan).replace(/\(.*$/, '')) + ' <b>¥' + money(x.cny_per_1m, 2) + '</b></span>';
      }).join('')
    + '<span class="c mut">Trae <b>未公布按量价</b></span>'
    + '</div>'
    + '<div class="f">WorkBuddy 那三个数是三档系数折算出的<b>等效单价</b>（元 / 百万 token），'
    + '随缓存命中率与输入输出比浮动，只用来判断「订阅到底省不省」，别和上面的按量 API 直接比大小。'
    + 'Trae 只有订阅档位、查不到 per-token 价，缺可比口径，暂不收录。</div>'
    + '</div>';

  var foot = '<div class="foot mt">点 = 一家渠道，同价合并、右侧 ×n 是家数；绿圈 = 这一行最低价。'
    + '官方谷时价与标准价不是同一商品，价差只按标准价算，逐家明细见「模型 × 平台报价」。</div>';

  return {
    meta: models.length + ' 模型 · ' + lines.length + ' 条渠道报价',
    body: hint + legend + '<div class="cm">' + axis + body + '</div>' + subs + foot
  };
};

/* ⑬ 平台排行 */
VIEW.platrank = function(){
  var p = S.panorama || {};
  var plats = (p.platforms || []).slice().sort(function(a, b){ return b.n_models - a.n_models; });
  if (!plats.length) return {meta:'', body:'<div class="empty">还没有平台库。</div>'};
  var ratioTxt = function(v){
    if (v == null) return '<span class="mut">—</span>';
    var d = (v - 1) * 100;
    if (Math.abs(d) < 0.5) return '<span class="mut">持平</span>';
    return '<span style="color:' + (d > 0 ? 'var(--bad)' : 'var(--ok)') + '">'
      + (d > 0 ? '+' : '') + d.toFixed(0) + '%</span>';
  };
  var KM = {official:'官方', cloud:'云厂商', aggregator:'第三方'};
  var t = table({
    id:'panoplat', rows:plats, empty:'',
    cols:[
      {k:'name', label:'平台', fmt:function(v, r){
          return '<span class="nm">' + esc(v) + '</span><span class="sm">' + esc(KM[r.kind] || r.kind) + '</span>'; }},
      {k:'n_models', label:'模型', cls:'r', num:true, fmt:function(v){ return v; }},
      {k:'ratio_median', label:'相对官方', cls:'r', num:true, fmt:function(v){ return ratioTxt(v); }},
      {k:'ratio_min', label:'最便宜', cls:'r', num:true, fmt:function(v){ return ratioTxt(v); }}
    ],
    foot:'相对官方 = 该平台当前输出价 ÷ 同模型官方价，取中位。只有 1 个模型的平台，中位就是它自己。'
  });
  return {meta: plats.length + ' 个平台', body: t};
};

/* ⑭ 套餐与回本点 */
VIEW.plans = function(){
  var planRows = S.plans.map(function(p){
    return Object.assign({}, p, {expired: !!(p.promo_until && p.promo_until < S.meta.date)});
  });
  var cross = table({
    id:'cross', rows:S.crosses, empty:'本轮没有打平点（套餐等效单价高于 API 基准或不可折算）',
    cols:[
      {k:'plan', label:'套餐', fmt:function(v, r){
          var t = (r.promo && r.promo < S.meta.date) ? '<span class="tag bad">已到期</span>' : '';
          return '<span class="nm">' + esc(v) + '</span>' + t
            + '<span class="sm">' + esc(r.platform || '') + '</span>';
        }},
      {k:'monthly', label:'月费', cls:'r', num:true, fmt:function(v){ return '¥' + money(v, 0); }},
      {k:'cny_per_1m', label:'等效单价', cls:'r', num:true, fmt:function(v){ return money(v, 4); }},
      {k:'break_even', label:'打平点', cls:'r', num:true, fmt:function(v){
          return '<b>' + mult(v) + '</b><span class="sm">百万 / 月</span>'; }}
    ]
  });
  var pt = table({
    id:'plans', rows:planRows, empty:'套餐表是空的',
    cols:[
      {k:'platform', label:'平台', fmt:function(v){ return '<span class="nm">' + esc(v) + '</span>'; }},
      {k:'plan', label:'套餐', fmt:function(v, r){
          var t = '';
          if (r.expired) t += '<span class="tag bad">到期 ' + esc(r.promo_until) + '</span>';
          else if (r.promo_until) t += '<span class="tag warn">限时 ' + esc(r.promo_until) + '</span>';
          return esc(v) + t + '<span class="sm">' + esc(r.window || '') + '</span>';
        }},
      {k:'monthly_cny', label:'月费', cls:'r', num:true, fmt:function(v){ return '¥' + money(v, 0); }},
      {k:'cny_per_1m', label:'折算', cls:'r', num:true, fmt:function(v, r){
          return r.convertible ? '<b>' + money(v, 3) + '</b><span class="sm">元 / 百万</span>'
            : '<span class="tag">不可折算</span>';
        }},
      {k:'limit_5h', label:'限额', cls:'r', fmt:function(v){ return v ? esc(v) + ' 次/5h' : '—'; }}
    ]
  });
  return {
    meta: S.plans.length + ' 个 · ' + S.plans.filter(function(p){return p.convertible;}).length + ' 可折算',
    body: '<div class="split">'
      + '<div class="blk"><h3>回本临界点</h3>' + cross + '</div>'
      + '<div class="blk"><h3>套餐明细</h3>' + pt + '</div></div>'
      + '<div class="foot mt">打平点 = 套餐等效单价低于 API 基准所需的最小月用量。数学值，'
      + '不含 5 小时 / 周限额的现实约束 —— 这几条限额比单价更能决定它到底好不好用。</div>'
  };
};

/* ⑮ 本地部署 */
VIEW.local = function(){
  var t = table({
    id:'rigs', rows:S.rigs, empty:'本地硬件表是空的',
    cols:[
      {k:'rig', label:'硬件', fmt:function(v, r){
          return '<span class="nm">' + esc(v) + '</span><span class="sm">' + esc(r.model) + ' · ' + esc(r.quant) + '</span>';
        }},
      {k:'hardware', label:'采购价', cls:'r', num:true, fmt:function(v){
          return v > 0 ? '¥' + int(v) : '<span class="tag">已有设备</span>';
        }},
      {k:'years', label:'折旧', cls:'r', num:true, fmt:function(v){ return v + ' 年'; }},
      {k:'power', label:'功耗', cls:'r', num:true, fmt:function(v, r){ return v + ' W<span class="sm">电 ¥' + r.kwh + '/度</span>'; }},
      {k:'tok_s', label:'实测', cls:'r', num:true, fmt:function(v){ return v + '<span class="sm">tok/s</span>'; }},
      {k:'util', label:'利用率', cls:'r', num:true, fmt:function(v, r){
          return pct(v) + '<span class="sm">满负载 ' + money(r.cost_full, 3) + '</span>';
        }},
      {k:'cost', label:'折算', cls:'r', num:true, fmt:function(v){
          return '<b>' + money(v, 3) + '</b><span class="sm">元 / 百万</span>';
        }},
      {k:'note', label:'说明', cls:'wide', sort:false, fmt:function(v, r){
          return '<span class="sm" style="font-size:11.5px">' + esc(v || '—') + '</span>'
            + (r.url ? '<a class="sm" href="' + esc(r.url) + '" target="_blank" rel="noopener">来源</a>' : '');
        }}
    ],
    foot:'成本 =（月折旧 + 月电费）÷（利用率 × 月秒数 × tok/s）× 1e6。未计运维、网络与资本占用；'
      + 'tok/s 是个人实测样本，不是受控基准。'
  });
  return {meta: S.rigs.length + ' 套', body: t};
};

/* ⑯ 1 块钱能干什么 */
VIEW.tasks = function(){
  var td = S.tasks || {tasks:[], bands:[], matrix:[]};
  var oneM = table({
    id:'onem', rows:td.tasks, empty:'没有任务样本',
    cols:[
      {k:'task', label:'任务', fmt:function(v){
          return '<span class="nm">' + esc(v) + '</span>'; }},
      {k:'tokens', label:'单次 token', cls:'r', num:true, fmt:function(v){ return int(v); }},
      {k:'runs_per_1m', label:'1M token 能跑', cls:'r', num:true, fmt:function(v){
          return '<b>' + int(v) + '</b> 次'; }}
    ]
  });
  var shortOf = function(b){
    var s = b.short || String(b.label).split(' · ').pop();
    return s.replace(/\(.*$/, '').slice(0, 16);
  };
  var head = '<tr><th>任务</th>' + td.bands.map(function(b){
    return '<th class="r">' + esc(shortOf(b)) + '<span class="sm" style="font-weight:400">'
      + money(b.cost, 3) + ' 元/M</span></th>';
  }).join('') + '</tr>';
  var body = td.matrix.map(function(row){
    return '<tr><td><span class="nm">' + esc(row.task) + '</span></td>'
      + row.cells.map(function(n){
          return '<td class="r">' + (n >= 1 ? '<b>' + mult(n) + '</b>' : '<span class="mut">'
            + n.toFixed(2) + '</span>') + '</td>';
        }).join('') + '</tr>';
  }).join('');
  return {
    meta: td.bands.length + ' 档 × ' + td.tasks.length + ' 任务',
    body: '<div class="split">'
      + '<div class="blk"><h3>1 百万 token 能完成什么</h3>' + oneM + '</div>'
      + '<div class="blk"><h3>1 块钱能完成什么</h3>'
      + '<div class="tscroll"><table class="dt"><thead>' + head + '</thead><tbody>' + body
      + '</tbody></table></div></div></div>'
      + '<div class="foot mt">各档<b>口径不同</b>：API 是输出价、套餐是综合价、本地是折旧+电费，'
      + '不能混着比「谁更划算」。任务 token 是估算，Agent 类受工具调用轮数影响可达数倍。</div>'
  };
};

/* ⑰ 数据校验 */
VIEW.verify = function(){
  var srcRows = S.status_order.filter(function(s){ return S.counts[s]; }).map(function(s){
    return {s:s, n:S.counts[s],
      why:({confirmed:'≥2 个独立来源数值一致',
            single_source:'只有 1 个来源对上，需补交叉',
            stale:'超过 ' + S.meta.policy.stale_days + ' 天未复核',
            unverified:'缺来源链接 / 核验日期 / 来源类型',
            conflict:'偏差 > ' + Math.round(S.meta.policy.conflict_tolerance * 100) + '%',
            incomparable:'观测与主表口径不一致，已隔离',
            uncovered:'本轮开源源未收录该模型'}[s] || '')};
  });
  var dist = table({
    id:'dist', rows:srcRows, empty:'',
    cols:[
      {k:'s', label:'状态', sort:false, fmt:function(v, r){ return pill(r.s); }},
      {k:'n', label:'条', cls:'r', num:true, fmt:function(v){ return '<b>' + v + '</b>'; }},
      {k:'why', label:'判定规则', sort:false, fmt:function(v){
          return '<span class="sm" style="font-size:11.5px">' + esc(v) + '</span>'; }}
    ]
  });
  var ids = Object.keys(S.sources || {});
  var srcTable = table({
    id:'srcs', rows:ids.map(function(id){
      var s = S.sources[id], m = (S.source_meta || {})[id] || {};
      return {id:id, name:s.name, kind:s.kind, weight:s.weight, covers:(s.covers || []).join(' / '),
              n_obs:s.n_obs, n_events:s.n_events, url:m.url || ''};
    }), empty:'',
    cols:[
      {k:'name', label:'来源', fmt:function(v, r){ return '<span class="nm">' + esc(v) + '</span>'
          + '<span class="sm">' + esc(r.kind) + ' · 权重 ' + r.weight + '</span>'; }},
      {k:'n_obs', label:'观测', cls:'r', num:true, fmt:function(v){ return int(v); }},
      {k:'n_events', label:'事件', cls:'r', num:true, fmt:function(v){ return v || '—'; }},
      {k:'url', label:'', sort:false, fmt:function(v){ return v
          ? '<a href="' + esc(v) + '" target="_blank" rel="noopener">打开</a>' : '—'; }}
    ]
  });
  var conflictRows = [];
  S.api.forEach(function(r){ r.conflicts.forEach(function(c){ conflictRows.push({r:r, c:c}); }); });
  var cs = table({
    id:'conf', rows:conflictRows, empty:'本轮无数值冲突',
    cols:[
      {k:'m', label:'模型', fmt:function(v, row){ return '<span class="nm">' + esc(row.r.display) + '</span>'
          + '<span class="sm">' + esc(row.c.metric) + '</span>'; }},
      {k:'main', label:'主表', cls:'r', num:true, fmt:function(v, row){
          return money(row.c.main, 3) + ' ' + esc(row.r.currency); }},
      {k:'value', label:'他源', cls:'r', num:true, fmt:function(v, row){
          return money(row.c.value, 3) + '<span class="sm">' + esc(row.c.source) + '</span>'; }},
      {k:'rel', label:'偏差', cls:'r', num:true, fmt:function(v, row){
          return '<span class="pill s-conflict">' + Math.round(row.c.rel * 100) + '%</span>'; }}
    ]
  });
  return {
    meta: ids.length + ' 个来源 · ' + S.counts.confirmed + ' 条一致',
    body: '<div class="split">'
      + '<div class="blk"><h3>状态分布</h3>' + dist + '</div>'
      + '<div class="blk"><h3>本轮的核验源</h3>' + srcTable + '</div></div>'
      + '<div class="blk mt"><h3>数值冲突</h3>' + cs + '</div>'
      + '<div class="foot mt">冲突是<b>待复核线索</b>，不是结论：常见成因是上游版本滞后、'
      + '官方调价未同步、跨版本同名、国际 / 国内双口径。</div>'
  };
};

/* ⑱ 调价 / 活动事件 */
VIEW.timeline = function(){
  var all = S.events.filter(function(e){
    if (FLT.esrc && e.src !== FLT.esrc) return false;
    if (FLT.q){
      var q = FLT.q.toLowerCase();
      if ((e.model + ' ' + e.type + ' ' + e.detail + ' ' + e.src).toLowerCase().indexOf(q) < 0) return false;
    }
    return true;
  });
  var LIMIT = 40;
  var rows = all.slice(0, LIMIT);
  var srcs = {};
  S.events.forEach(function(e){ srcs[e.src] = (srcs[e.src] || 0) + 1; });
  var chips = '<div class="chips"><button class="chip" data-es="" aria-pressed="' + (!FLT.esrc) + '">全部 <em>'
    + S.events.length + '</em></button>' + Object.keys(srcs).map(function(k){
      return '<button class="chip" data-es="' + esc(k) + '" aria-pressed="' + (FLT.esrc === k) + '">'
        + esc(k) + ' <em>' + srcs[k] + '</em></button>';
    }).join('') + '</div>';
  var t = table({
    id:'events', rows:rows, empty:'没有符合筛选的事件',
    cols:[
      {k:'date', label:'日期', fmt:function(v){ return '<span class="nm">' + esc(v || '—') + '</span>'; }},
      {k:'type', label:'类型', fmt:function(v){
          return '<span class="tag' + (/到期|下线|弃用/.test(v) ? ' bad' : (/调价|限时/.test(v) ? ' warn' : ''))
            + '">' + esc(v) + '</span>'; }},
      {k:'model', label:'模型', fmt:function(v){ return esc(v); }},
      {k:'detail', label:'说明', cls:'wide', fmt:function(v, r){
          return '<span class="sm" style="font-size:11.5px">' + esc(v) + '</span>'
            + (r.url ? '<a class="sm" href="' + esc(r.url) + '" target="_blank" rel="noopener">出处</a>' : '');
        }}
    ]
  });
  return {
    meta: all.length + ' / ' + S.events.length + ' 条',
    body: '<div class="bar">' + chips + '<div class="grow"></div>'
      + '<label class="search"><span style="color:var(--ink3);font-size:12px">⌕</span>'
      + '<input id="evQ" placeholder="模型 / 说明" value="' + esc(FLT.q) + '"></label></div>'
      + t
      + '<div class="foot mt">外部事件来自 LLMTracker 每 6 小时的 changelog，只作线索、未并入主表；'
      + '本地快照 diff 是自己观测到的变化。</div>'
  };
};

/* ---------- 渲染 ---------- */
function render(){
  if (!S) return;
  Object.keys(VIEW).forEach(function(id){
    var box = $('b-' + id), meta = $('m-' + id);
    if (!box) return;
    try{
      var r = VIEW[id]() || {};
      box.innerHTML = r.body || '';
      if (meta) meta.innerHTML = r.meta || '';
    }catch(err){
      box.innerHTML = '<div class="empty">这张卡算不出来：' + esc(err.message || err) + '</div>';
      if (meta) meta.innerHTML = '';
    }
  });
  bind();
  bindPano();
}

/* 每次渲染后绑一次局部事件（筛选 / 搜索），别用 document 级委托堆监听 */
function bind(){
  Array.prototype.forEach.call(document.querySelectorAll('[data-st]'), function(b){
    b.onclick = function(){
      var s = b.getAttribute('data-st');
      if (!s) FLT.status.clear();
      else if (FLT.status.has(s)) FLT.status.delete(s);
      else FLT.status.add(s);
      render();
    };
  });
  Array.prototype.forEach.call(document.querySelectorAll('[data-es]'), function(b){
    b.onclick = function(){
      var s = b.getAttribute('data-es');
      FLT.esrc = (FLT.esrc === s) ? '' : s;
      render();
    };
  });
  Array.prototype.forEach.call(document.querySelectorAll('.xrow'), function(tr){
    /* 展开行语义上是个按钮：补 role / tabindex / aria-expanded，
       否则键盘和读屏用户永远看不到「每个平台的具体报价」 */
    var toggle = function(){
      var body = $(tr.getAttribute('data-x'));
      if (!body) return;
      var open = body.style.display !== 'none';
      body.style.display = open ? 'none' : '';
      tr.classList.toggle('open', !open);
      tr.setAttribute('aria-expanded', String(!open));
    };
    tr.onclick = toggle;
    tr.onkeydown = function(e){
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar'){
        e.preventDefault();
        toggle();
      }
    };
  });
  /* 价格带的行：点开看这一行每家的确切报价 */
  Array.prototype.forEach.call(document.querySelectorAll('.cm-row'), function(el){
    var det = $(el.getAttribute('data-x'));
    if (!det) return;
    var toggle = function(){
      var open = det.style.display !== 'none';
      det.style.display = open ? 'none' : '';
      el.classList.toggle('open', !open);
      el.setAttribute('aria-expanded', String(!open));
    };
    el.onclick = toggle;
    el.onkeydown = function(e){
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar'){
        e.preventDefault();
        toggle();
      }
    };
  });
  var q1 = $('apiQ'), q2 = $('evQ');
  [[q1, 'api'], [q2, 'ev']].forEach(function(pair){
    var el = pair[0];
    if (!el) return;
    var t = null;
    el.oninput = function(){
      clearTimeout(t);
      var v = el.value;
      t = setTimeout(function(){ FLT.q = v.trim(); render(); focusBack(pair[1], v); }, 260);
    };
  });
}
function focusBack(which, v){
  var el = which === 'api' ? $('apiQ') : $('evQ');
  if (!el) return;
  el.focus();
  try{ el.setSelectionRange(v.length, v.length); }catch(e){}
}

/* 平台全景图：点图例只看一个模型。线的 opacity 是 attribute，
   聚焦时用 style 覆盖、取消时清空 style 让它回落到 attribute，不用记住原值。 */
function bindPano(){
  Array.prototype.forEach.call(document.querySelectorAll('.chart svg[data-pano]'), function(svg){
    if (svg.dataset.bound) return;
    svg.dataset.bound = '1';
    var paint = function(model){
      Array.prototype.forEach.call(svg.querySelectorAll('[data-model]'), function(el){
        if (!model) el.style.opacity = '';
        else el.style.opacity = (el.getAttribute('data-model') === model) ? '1' : '0.12';
      });
      Array.prototype.forEach.call(svg.querySelectorAll('[data-legend]'), function(el){
        el.style.opacity = (!model || el.getAttribute('data-legend') === model)
          ? '' : '0.28';
      });
    };
    svg.addEventListener('click', function(e){
      var g = e.target.closest('[data-legend],[data-model]');
      if (!g) return;
      var m = g.getAttribute('data-legend') || g.getAttribute('data-model');
      svg.dataset.focus = svg.dataset.focus === m ? '' : m;
      paint(svg.dataset.focus);
    });
    svg.addEventListener('keydown', function(e){
      if (e.key === 'Escape'){ svg.dataset.focus = ''; paint(''); }
    });
  });
}

/* ---------- 报告弹层 ---------- */
function mdToHtml(md){
  var out = [], inList = false, inTable = false;
  md.split('\n').forEach(function(ln){
    var l = ln.replace(/\r$/, '');
    if (/^\s*$/.test(l)){ if (inList){ out.push('</ul>'); inList = false; }
      if (inTable){ out.push('</table>'); inTable = false; } return; }
    var t = esc(l)
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
    if (/^\|/.test(l)){
      if (/^\|[\s:-]+\|/.test(l)) return;
      if (!inTable){ out.push('<table>'); inTable = true; }
      var cells = l.split('|').slice(1, -1).map(function(c){ return c.trim(); });
      var tag = /^(模型|日期|类型|来源|指标)/.test(cells[0]) ? 'th' : 'td';
      out.push('<tr>' + cells.map(function(c){
        return '<' + tag + '>' + esc(c).replace(/`([^`]+)`/g, '<code>$1</code>') + '</' + tag + '>';
      }).join('') + '</tr>');
      return;
    }
    if (inTable){ out.push('</table>'); inTable = false; }
    if (/^#{1,3} /.test(l)){
      if (inList){ out.push('</ul>'); inList = false; }
      var n = l.match(/^#+/)[0].length;
      out.push('<h' + n + '>' + t.replace(/^#+\s*/, '') + '</h' + n + '>');
      return;
    }
    if (/^[-*] /.test(l)){
      if (!inList){ out.push('<ul>'); inList = true; }
      out.push('<li>' + t.replace(/^[-*]\s*/, '') + '</li>');
      return;
    }
    if (inList){ out.push('</ul>'); inList = false; }
    if (/^> /.test(l)){ out.push('<blockquote>' + t.replace(/^&gt;\s*/, '') + '</blockquote>'); return; }
    out.push('<p>' + t + '</p>');
  });
  if (inList) out.push('</ul>');
  if (inTable) out.push('</table>');
  return out.join('');
}
$('btnReport').onclick = function(){
  $('modal').classList.add('on');
  $('mTitle').textContent = '核验报告';
  $('mBody').innerHTML = '<p>读取中…</p>';
  if (MODE !== 'live'){
    $('mBody').innerHTML = '<p>核验报告由本地服务生成，快照站上没有这份文件。</p>'
      + '<p class="foot">装到本机后点这个按钮，或命令行跑 <code>python3 llmcost.py --snapshot</code>。</p>';
    return;
  }
  fetch('/api/report?name=REPORT.md', {cache:'no-store'})
    .then(function(r){ return r.ok ? r.text() : Promise.reject(new Error('HTTP ' + r.status)); })
    .then(function(t){ $('mBody').innerHTML = mdToHtml(t); })
    .catch(function(e){ $('mBody').innerHTML = '<p>读不到报告：' + esc(e.message || e)
      + '</p><p class="foot">文件在 <code>13-算价/out/REPORT.md</code>。</p>'; });
};
$('mClose').onclick = function(){ $('modal').classList.remove('on'); };
$('modal').onclick = function(e){ if (e.target === $('modal')) $('modal').classList.remove('on'); };
document.addEventListener('keydown', function(e){
  if (e.key === 'Escape') $('modal').classList.remove('on');
});

probeLive().then(function(ok){
  MODE = ok ? 'live' : 'snapshot';
  load(false);
});
