/** 武器库面板 — 组合数学 + 统计检验 + 信息论 */

const API = {
  nist: '/api/nist/test',
  condentropy: '/api/cond-entropy/analyze',
  exactcover: '/api/exact-cover/compare',
  diffset: '/api/diffset/table',
  bandit: '/api/bandit/summary',
  wheeling: '/api/wheeling/compare',
  kelly: '/api/kelly',
  sprt: '/api/sprt/monitor',
  fdr: '/api/fdr/filter',
  mi: '/api/mi/analyze',
  changepoint: '/api/changepoint/detect',
};

const panelEl = document.getElementById('arsenalPanel');
if (panelEl) {
  panelEl.addEventListener('panel-shown', () => loadNist());
}

// ═══ Tab switching ═══
// switchArsenalTab defined below

function T(tag, attrs, ...children) {
  const el = document.createElement(tag);
  if (attrs) Object.entries(attrs).forEach(([k,v]) => { if(v != null) el[k]=v; });
  children.forEach(c => { if(c != null) el.append(typeof c==='string'?document.createTextNode(c):c); });
  return el;
}

// ═══ Wheeling ═══
async function loadWheeling() {
  const el = document.getElementById('arsenalWheelingContent');
  if(!el) return;
  el.innerHTML = '<div style="color:#FBBF24;padding:12px;">加载 La Jolla 覆盖库...</div>';

  try {
    const r = await fetch(API.wheeling);
    const d = await r.json();
    if(!d.ok){ el.innerHTML='<div style="color:#EF4444;">加载失败</div>'; return; }

    let h = '<div style="font-size:12px;color:#94A3B8;margin-bottom:8px;">';
    h += '<b>已知最优覆盖注数</b> — La Jolla + Bluskov 2011<br>';
    h += '<span style="font-size:10px;">4-if-6 guarantee: 若V个号包含全部6个中奖号 → ≥1注中≥4红</span>';
    h += '</div>';

    h += '<table class="bt-table" style="font-size:10px;"><thead><tr>';
    h += '<th>池大小V</th><th>最少注数</th><th>P(6红全在V)</th><th>成本/期</th><th>保证</th>';
    h += '</tr></thead><tbody>';

    (d.table||[]).forEach(row => {
      h += '<tr>' +
        '<td><b>' + row.v + '</b></td>' +
        '<td>' + row.min_tickets + '</td>' +
        '<td>' + row.p_6_in_v_pct + '%</td>' +
        '<td>' + row.cost_per_draw + '</td>' +
        '<td>' + row.guarantee + '</td>' +
        '</tr>';
    });
    h += '</tbody></table>';
    h += '<div style="margin-top:8px;font-size:9px;color:#64748B;">';
    h += 'V=8:4注 ¥8/期 | V=10:5注 ¥10/期 | V=12:6注 ¥12/期 — 已知最优, 数学证明<br>';
    h += '来源: ccrwest.org, Bluskov "Combinatorial Lottery Systems" (CRC 2011)';
    h += '</div>';
    h += '<button class="btn-small" onclick="applyWheeling()" style="margin-top:8px;background:rgba(34,197,94,0.12);color:#22C55E;border-color:rgba(34,197,94,0.2);">🧮 使用轮次表出号</button>';
    el.innerHTML = h;
  } catch(e) { el.innerHTML = '<div style="color:#EF4444;">请求失败</div>'; }
}

window.applyWheeling = async function() {
  var stage = document.getElementById('stage');
  var n = parseInt(document.getElementById('drawCount')?.value || 3);
  stage.innerHTML = '<div style="text-align:center;padding:20px;color:#22C55E;">🧮 轮次表覆盖 — 已知最优保证...</div>';
  try {
    var r = await fetch('/api/ensemble/draw?n=' + n + '&method=ensemble&fdr=0');
    var d = await r.json();
    if(!d.ok){ stage.innerHTML = '<div style="color:#EF4444;">'+ (d.msg||'失败') +'</div>'; return; }
    stage.innerHTML = '<div style="font-size:10px;text-align:center;padding:6px;border-radius:6px;background:rgba(34,197,94,0.1);color:#4ADE80;"><b>🧮 轮次表覆盖</b> · ' + (d.covering?.method||'') + ' · 成本¥' + (d.cost_rmb||0) + '</div>';
    renderTickets(stage, d);
    document.getElementById('saveBtn').disabled = false;
  } catch(e){ stage.innerHTML = '<div style="color:#EF4444;">请求失败</div>'; }
};

// ═══ Kelly ═══
async function loadKelly() {
  const el = document.getElementById('arsenalKellyContent');
  if(!el) return;
  el.innerHTML = '<div style="color:#FBBF24;padding:12px;">Kelly计算中...</div>';

  try {
    const r = await fetch(API.kelly);
    const d = await r.json();
    if(!d.ok){ el.innerHTML='<div style="color:#EF4444;">失败</div>'; return; }

    const ev = d.ev, k = d.kelly, p = d.plan;
    let h = '<div style="font-size:11px;line-height:1.7;">';
    h += '<b style="color:#4ADE80;">💰 Kelly 最优投注比例</b><br>';
    h += '<span style="font-size:10px;color:#64748B;">Kelly 1956, Thorp 1997: 最大化对数效用的最优投注比例</span><br><br>';

    h += '<b>当前策略 EV:</b><br>';
    h += '池V=' + (ev.pool_v||15) + ', 覆盖' + (ev.coverage_pct||36) + '%, 蓝' + (ev.blue_pct||38) + '%<br>';
    h += '每注EV: <span style="color:' + (ev.net_ev>=0?'#22C55E':'#EF4444') + '">¥' + ev.net_ev + '</span><br>';
    h += 'EV/成本: <span style="color:' + (ev.ev_cost_ratio>=1?'#22C55E':'#EF4444') + '">' + ev.ev_cost_ratio + 'x</span><br>';
    h += 'P(头奖): ≈' + ev.p_jackpot_approx.toExponential(2) + '<br><br>';

    h += '<b>Kelly 推荐:</b> ' + k.verdict + '<br>';
    h += '全Kelly注数: ' + (k.full_kelly_tickets||0) + '<br>';
    h += '1/2 Kelly: ' + (k.half_kelly_tickets||0) + '<br>';
    h += '1/4 Kelly (保守): <b style="color:#FBBF24;">' + (k.quarter_kelly_tickets||0) + '</b> 注/期<br>';
    h += '理由: ' + k.reason + '<br><br>';

    h += '<b>¥5000本金规划:</b><br>';
    h += '每期成本: ¥' + (p.cost_per_draw||0) + '<br>';
    h += '可持续: ' + (p.max_sustainable_draws||0) + '期 (' + (p.max_sustainable_years||0) + '年)<br>';
    h += '评估: <span style="color:#EF4444;">' + (p.ruin_assessment||'') + '</span><br>';
    h += '</div>';
    h += '<div style="margin-top:8px;font-size:9px;color:#64748B;">Kelly 1956, Bell System Tech. J. | MacLean, Thorp, Ziemba "Kelly Capital Growth Investment Criterion" 2011</div>';
    el.innerHTML = h;
  } catch(e) { el.innerHTML = '<div style="color:#EF4444;">请求失败</div>'; }
}

// ═══ SPRT ═══
async function loadSprt() {
  const el = document.getElementById('arsenalSprtContent');
  if(!el) return;
  el.innerHTML = '<div style="color:#FBBF24;padding:12px;">SPRT分析中...</div>';

  try {
    const r = await fetch(API.sprt);
    const d = await r.json();
    if(!d.ok){ el.innerHTML='<div style="color:#EF4444;">失败</div>'; return; }

    const s = d.sprt, e = d.expected_sample_size || {};
    let h = '<div style="font-size:11px;line-height:1.7;">';
    h += '<b style="color:#A78BFA;">📊 序贯概率比检验 (SPRT)</b><br>';
    h += '<span style="font-size:10px;color:#64748B;">Wald 1945: 实时检测策略是否偏离随机基线</span><br><br>';

    h += '<b>状态:</b> <span style="color:' + (s.status==='significant'?'#22C55E':'#FBBF24') + '">' + s.interpretation + '</span><br>';
    h += '观测期数: ' + s.n + '<br>';
    h += '累计LLR: ' + s.llr + '<br>';
    h += '上界(H0拒绝): ' + s.threshold_upper + ' | 下界(H0接受): ' + s.threshold_lower + '<br>';
    h += '命中率: ' + (s.hit_rate*100).toFixed(1) + '%<br><br>';

    h += '<b>期望样本量:</b><br>';
    h += '若H0真 (无差异): ~' + (e.expected_under_null||'?') + '期可做判断<br>';
    h += '若H1真 (有差异): ~' + (e.expected_under_alt||'?') + '期可做判断<br>';
    h += '</div>';
    h += '<div style="margin-top:8px;font-size:9px;color:#64748B;">Wald 1945, "Sequential Tests of Statistical Hypotheses"</div>';
    el.innerHTML = h;
  } catch(e) { el.innerHTML = '<div style="color:#EF4444;">请求失败</div>'; }
}

// ═══ FDR ═══
async function loadFdr() {
  const el = document.getElementById('arsenalFdrContent');
  if(!el) return;
  el.innerHTML = '<div style="color:#FBBF24;padding:12px;">FDR分析中...</div>';

  try {
    const r = await fetch(API.fdr);
    const d = await r.json();
    if(!d.ok){ el.innerHTML='<div style="color:#EF4444;">失败</div>'; return; }

    const bh = d.bh_results || {};
    let h = '<div style="font-size:11px;line-height:1.7;">';
    h += '<b style="color:#F97316;">🔬 FDR 多重比较校正</b><br>';
    h += '<span style="font-size:10px;color:#64748B;">Benjamini-Hochberg 1995: ' + (bh.n_total||0) + ' tests, q=0.05</span><br><br>';

    h += '<b>显著方法 (' + (bh.n_significant||0) + '/' + (bh.n_total||0) + '):</b><br>';
    if(bh.interpretation) h += '<span style="font-size:10px;color:#64748B;">' + bh.interpretation + '</span><br>';
    
    (bh.significant||[]).slice(0, 15).forEach(function(s){
      h += '<div style="font-size:10px;padding:2px 0;">' +
        '<span style="color:#22C55E;">' + s.name + '</span> ' +
        '<span style="color:#64748B;">p=' + s.p_value + ' ≤ BH=' + s.bh_threshold + '</span>' +
        '</div>';
    });

    h += '<br><b>移除方法:</b> ' + (d.removed_methods||[]).join(', ') + '<br>';
    h += '<b>保留权重:</b><br>';
    Object.entries(d.filtered_weights||{}).forEach(function(kv){
      h += '<span style="font-size:10px;color:#94A3B8;">' + kv[0] + ': ' + kv[1].toFixed(4) + '</span> ';
    });
    h += '</div>';
    h += '<div style="margin-top:8px;font-size:9px;color:#64748B;">Benjamini & Hochberg 1995, JRSS-B 57(1):289-300</div>';
    el.innerHTML = h;
  } catch(e) { el.innerHTML = '<div style="color:#EF4444;">请求失败: '+e.message+'</div>'; }
}

// ═══ MI ═══
async function loadMi() {
  const el = document.getElementById('arsenalMiContent');
  if(!el) return;
  el.innerHTML = '<div style="color:#FBBF24;padding:12px;">互信息计算中 (~0.5s)...</div>';

  try {
    const r = await fetch(API.mi);
    const d = await r.json();
    if(!d.ok){ el.innerHTML='<div style="color:#EF4444;">失败</div>'; return; }

    const mi = d.mi_analysis || {};
    let h = '<div style="font-size:11px;line-height:1.7;">';
    h += '<b style="color:#EC4899;">🔗 互信息 — 号码对非独立共现</b><br>';
    h += '<span style="font-size:10px;color:#64748B;">Cover & Thomas 2006: ' + (mi.interpretation||'') + '</span><br><br>';

    h += '<b>MI显著阈值:</b> ' + mi.mi_threshold + ' (' + mi.n_bootstrap + ' bootstrap, α=' + mi.alpha + ')<br>';
    h += '<b>Top 非独立号码对:</b><br>';
    (mi.top_all||[]).slice(0,10).forEach(function(p){
      h += '<div style="font-size:10px;padding:2px 0;">' +
        '<span style="color:#E2E8F0;">#' + String(p[0]).padStart(2,'0') + '</span> — ' +
        '<span style="color:#E2E8F0;">#' + String(p[1]).padStart(2,'0') + '</span> ' +
        '<span style="color:#F472B6;">MI=' + p[2] + '</span> ' +
        '<span style="color:#64748B;">共现' + p[3] + '次</span>' +
        '</div>';
    });

    h += '<br><b>显著号码对 (' + (mi.significant_pairs||[]).length + '):</b><br>';
    (mi.significant_pairs||[]).slice(0,10).forEach(function(p){
      h += '<div style="font-size:10px;color:#A78BFA;">#' + p[0] + '—#' + p[1] + ' MI≥' + mi.mi_threshold + '</div>';
    });

    if(d.mi_hot_numbers){
      h += '<br><b>MI增强热号 Top 10:</b><br>';
      h += '<div style="display:flex;gap:4px;flex-wrap:wrap;">';
      d.mi_hot_numbers.slice(0,10).forEach(function(p){
        h += '<span style="font-size:9px;padding:2px 6px;border-radius:4px;background:rgba(236,72,153,0.1);color:#F472B6;">' + p[0] + '(' + p[1].toFixed(3) + ')</span>';
      });
      h += '</div>';
    }
    h += '</div>';
    h += '<div style="margin-top:8px;font-size:9px;color:#64748B;">Cover & Thomas 2006, "Elements of Information Theory" 2nd ed.</div>';
    el.innerHTML = h;
  } catch(e) { el.innerHTML = '<div style="color:#EF4444;">请求失败</div>'; }
}

// ═══ Changepoint ═══
async function loadChangepoint() {
  const el = document.getElementById('arsenalChangepointContent');
  if(!el) return;
  el.innerHTML = '<div style="color:#FBBF24;padding:12px;">变点检测中...</div>';

  try {
    const r = await fetch(API.changepoint);
    const d = await r.json();
    if(!d.ok){ el.innerHTML='<div style="color:#EF4444;">失败</div>'; return; }

    let h = '<div style="font-size:11px;line-height:1.7;">';
    h += '<b style="color:#22D3EE;">📈 贝叶斯变点检测</b><br>';
    h += '<span style="font-size:10px;color:#64748B;">Fearnhead 2006: 检测开奖机制结构性变化</span><br><br>';

    h += '<b>总数据:</b> ' + d.total_draws + '期, 窗口=' + d.window + ', 推荐窗口=' + d.recommended_window + '期<br>';
    h += '<span style="color:#94A3B8;">建议: ' + (d.recommendation||'') + '</span><br><br>';

    h += '<b>红球变点 (后验概率>0.3):</b><br>';
    (d.detected_red||[]).slice(0,8).forEach(function(c){
      h += '<div style="font-size:10px;color:#EF4444;">期' + c.period + ': BF=' + c.bf + ' P=' + c.posterior_prob + ' [' + c.evidence + ']</div>';
    });

    h += '<br><b>红蓝均支持 (确证):</b><br>';
    (d.confirmed_both||[]).forEach(function(c){
      h += '<div style="font-size:10px;color:#22C55E;font-weight:600;">期' + c.period + ': BF=' + c.bf + ' P=' + c.posterior_prob + '</div>';
    });

    h += '<br><b>已知变化点:</b><br>';
    Object.entries(d.known_changepoints||{}).forEach(function(kv){
      h += '<span style="font-size:9px;color:#64748B;">' + kv[0] + ' (期' + kv[1] + ') </span>';
    });
    h += '</div>';
    h += '<button class="btn-small" onclick="applyMiDraw()" style="margin-top:8px;background:rgba(236,72,153,0.12);color:#F472B6;border-color:rgba(236,72,153,0.2);">🔗 MI增强出号</button>';
    el.innerHTML = h;
  } catch(e) { el.innerHTML = '<div style="color:#EF4444;">请求失败</div>'; }
}

window.applyMiDraw = async function() {
  var stage = document.getElementById('stage');
  var n = parseInt(document.getElementById('drawCount')?.value || 3);
  stage.innerHTML = '<div style="text-align:center;padding:20px;color:#EC4899;">🔗 互信息增强 — 检测非独立号码对...</div>';
  try {
    var r = await fetch('/api/ensemble/draw?n=' + n + '&method=mi');
    var d = await r.json();
    if(!d.ok){ stage.innerHTML = '<div style="color:#EF4444;">'+ (d.msg||'失败') +'</div>'; return; }
    stage.innerHTML = '<div style="font-size:10px;text-align:center;padding:6px;border-radius:6px;background:rgba(236,72,153,0.1);color:#F472B6;"><b>🔗 MI增强</b> · 成本¥' + (d.cost_rmb||0) + '</div>';
    renderTickets(stage, d);
    document.getElementById('saveBtn').disabled = false;
  } catch(e){ stage.innerHTML = '<div style="color:#EF4444;">请求失败</div>'; }
};

// ═══ Archived Engines ═══
async function loadEngines() {
  const el = document.getElementById('arsenalEnginesContent');
  if(!el) return;

  let h = '<div style="font-size:11px;line-height:1.7;color:#94A3B8;">';
  h += '<b>已归档的选号策略</b> — 均用不同统计方法选热号, 底层统一贪心覆盖设计.<br>';
  h += '<span style="font-size:10px;">OOS回测确认无方法显著优于基线; 保留供参考/对比.</span>';
  h += '</div>';

  h += '<div style="display:grid;gap:6px;margin-top:8px;">';

  // Bias
  h += '<div style="padding:8px;border-radius:6px;background:rgba(255,255,255,0.02);border:1px solid rgba(124,58,237,0.08);">';
  h += '<b style="font-size:12px;">🎯 偏差采样</b> <span style="font-size:9px;color:#64748B;">Dirichlet后验→Thompson→Gumbel-Max</span><br>';
  h += '<span style="font-size:9px;color:#475569;">文献: Thompson 1933; Gumbel 1954. 对彩票无证明优势.</span><br>';
  h += '<button class="btn-small" onclick="applyArchivedEngine(\'bias\')" style="margin-top:4px;">试用</button>';
  h += '</div>';

  // B-L
  h += '<div style="padding:8px;border-radius:6px;background:rgba(255,255,255,0.02);border:1px solid rgba(124,58,237,0.08);">';
  h += '<b style="font-size:12px;">⚖️ B-L加权</b> <span style="font-size:9px;color:#64748B;">多方法观点贝叶斯融合</span><br>';
  h += '<span style="font-size:9px;color:#475569;">文献: Black & Litterman 1992. 对频率数据无证明优势.</span><br>';
  h += '<button class="btn-small" onclick="applyArchivedEngine(\'bl\')" style="margin-top:4px;">试用</button>';
  h += '</div>';

  // Position
  h += '<div style="padding:8px;border-radius:6px;background:rgba(255,255,255,0.02);border:1px solid rgba(124,58,237,0.08);">';
  h += '<b style="font-size:12px;">📐 分位采样</b> <span style="font-size:9px;color:#64748B;">每位置独立最优方法+约束采样</span><br>';
  h += '<span style="font-size:9px;color:#475569;">6位置独立建模. OOS无显著提升.</span><br>';
  h += '<button class="btn-small" onclick="applyArchivedEngine(\'pos\')" style="margin-top:4px;">试用</button>';
  h += '</div>';

  h += '</div>';
  el.innerHTML = h;
}

window.applyArchivedEngine = async function(type) {
  var stage = document.getElementById('stage');
  var n = parseInt(document.getElementById('drawCount')?.value || 3);
  var labels = {bias:'偏差采样', bl:'B-L加权', pos:'分位采样'};
  var urls = {bias:'/api/bias/draw', bl:'/api/bl/draw', pos:'/api/position/draw'};
  stage.innerHTML = '<div style="text-align:center;padding:20px;color:#94A3B8;">' + (labels[type]||'') + '...</div>';
  try {
    var r = await fetch((urls[type]||'') + '?n=' + n);
    var d = await r.json();
    if(!d.ok){ stage.innerHTML = '<div style="color:#EF4444;">'+ (d.msg||'失败') +'</div>'; return; }
    stage.innerHTML = '<div style="font-size:10px;text-align:center;padding:6px;border-radius:6px;background:rgba(120,120,120,0.1);color:#94A3B8;"><b>' + (d.algorithm||labels[type]) + '</b> · 成本¥' + (d.cost_rmb||0) + '</div>';
    renderTickets(stage, d);
    document.getElementById('saveBtn').disabled = false;
  } catch(e){ stage.innerHTML = '<div style="color:#EF4444;">请求失败</div>'; }
};


// ═══════════════════════════════════════════════════════════
// NIST 随机性检验
// ═══════════════════════════════════════════════════════════

window.API_NIST = '/api/nist/test';

async function loadNist() {
  var el = document.getElementById('arsenalNistContent');
  if (!el) return;
  el.innerHTML = '<div style="color:#94A3B8;padding:20px;text-align:center;">NIST SP 800-22 检验运行中...</div>';
  try {
    var r = await fetch(window.API_NIST);
    var d = await r.json();
    if (!d.ok) { el.innerHTML = '<div style="color:#EF4444;">数据不足, 需>100期</div>'; return; }
    var rows = d.results.map(function(item) {
      var color = item.passed ? '#22C55E' : '#EF4444';
      return '<tr><td>' + item.test + '</td>' +
        '<td style="color:' + color + ';">' + (item.passed ? '通过' : '⚠ 未通过') + '</td>' +
        '<td>' + item.p_value + '</td>' +
        '<td>' + (item.detail || '') + '</td></tr>';
    }).join('');
    el.innerHTML =
      '<div style="color:#FBBF24;margin-bottom:8px;font-size:12px;">' + d.verdict + '</div>' +
      '<div style="font-size:10px;color:#64748B;margin-bottom:8px;">通过 ' + d.passed + '/' + d.total + ' (' + d.pass_rate_pct + '%) | ' +
        (d.bias_weighting_advice || '') + '</div>' +
      '<table style="font-size:10px;width:100%;border-collapse:collapse;">' +
      '<thead><tr style="color:#94A3B8;"><th>检验</th><th>状态</th><th>p值</th><th>详情</th></tr></thead>' +
      '<tbody>' + rows + '</tbody></table>';
  } catch(e) {
    el.innerHTML = '<div style="color:#EF4444;">加载失败</div>';
  }
}

// ═══════════════════════════════════════════════════════════
// 条件熵号码池
// ═══════════════════════════════════════════════════════════

async function loadCondentropy() {
  var el = document.getElementById('arsenalCondentropyContent');
  if (!el) return;
  el.innerHTML = '<div style="color:#94A3B8;padding:20px;text-align:center;">条件熵分析中...</div>';
  try {
    var r = await fetch('/api/cond-entropy/analyze');
    var d = await r.json();
    if (!d.ok) { el.innerHTML = '<div style="color:#EF4444;">数据不足</div>'; return; }
    var redTags = d.red_top15.map(function(n) { return '<span class="ball-red">' + n + '</span>'; }).join(' ');
    var blueTags = d.blue_top6.map(function(n) { return '<span class="ball-blue">' + n + '</span>'; }).join(' ');
    var clustersHtml = (d.red_clusters || []).map(function(c, i) {
      return '<div style="margin-bottom:2px;"><b>簇' + (i+1) + ':</b> ' + c.join(',') + '</div>';
    }).join('');
    el.innerHTML =
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px 16px;">' +
      '<div><b style="color:#A78BFA;">基线熵</b></div><div>' + d.baseline_entropy + '</div>' +
      '<div><b style="color:#A78BFA;">熵降低</b></div><div style="color:#22C55E;">' + d.entropy_reduction_pct + '%</div>' +
      '<div><b style="color:#A78BFA;">红球Top15</b></div><div>' + redTags + '</div>' +
      '<div><b style="color:#A78BFA;">蓝球Top6</b></div><div>' + blueTags + '</div>' +
      '</div>' +
      '<div style="margin-top:8px;"><b style="color:#A78BFA;">互信息聚类 (5簇)</b></div>' +
      '<div style="font-size:10px;color:#94A3B8;">' + clustersHtml + '</div>' +
      '<div style="margin-top:8px;font-size:9px;color:#64748B;">' + (d.note || '') + '</div>';
  } catch(e) {
    el.innerHTML = '<div style="color:#EF4444;">加载失败</div>';
  }
}

// ═══════════════════════════════════════════════════════════
// 精确覆盖
// ═══════════════════════════════════════════════════════════

async function loadExactcover() {
  var el = document.getElementById('arsenalExactcoverContent');
  if (!el) return;
  el.innerHTML = '<div style="color:#94A3B8;padding:20px;text-align:center;">精确覆盖比较中...</div>';
  try {
    var r = await fetch('/api/exact-cover/compare?n=3');
    var d = await r.json();
    if (!d.ok) { el.innerHTML = '<div style="color:#EF4444;">失败</div>'; return; }
    var rows = d.results.map(function(r) {
      return '<tr><td>v=' + r.v + '</td><td>' + r.n + '注</td>' +
        '<td style="color:#22C55E;">' + r.coverage_pct + '%</td>' +
        '<td>' + r.source + '</td><td>' + r.covered_t + '/' + r.total_t + '</td></tr>';
    }).join('');
    el.innerHTML =
      '<div style="color:#A78BFA;margin-bottom:8px;">精确覆盖 — La Jolla已知最优表</div>' +
      '<table style="font-size:10px;width:100%;">' +
      '<thead><tr style="color:#94A3B8;"><th>V</th><th>注数</th><th>覆盖率</th><th>来源</th><th>覆盖t元组</th></tr></thead>' +
      '<tbody>' + rows + '</tbody></table>' +
      '<div style="margin-top:8px;font-size:9px;color:#64748B;">' + (d.note || '') + '</div>';
  } catch(e) {
    el.innerHTML = '<div style="color:#EF4444;">加载失败</div>';
  }
}

// ═══════════════════════════════════════════════════════════
// 差集构造
// ═══════════════════════════════════════════════════════════

async function loadDiffset() {
  var el = document.getElementById('arsenalDiffsetContent');
  if (!el) return;
  el.innerHTML = '<div style="color:#94A3B8;padding:20px;text-align:center;">差集构造分析中...</div>';
  try {
    var r = await fetch('/api/diffset/table');
    var d = await r.json();
    if (!d.ok) { el.innerHTML = '<div style="color:#EF4444;">失败</div>'; return; }
    var rows = d.results.map(function(r) {
      return '<tr><td>v=' + r.v + '</td><td>' + r.n_blocks + '块</td>' +
        '<td style="color:#A78BFA;">' + r.coverage_2_pct + '%</td>' +
        '<td>' + r.pairs_covered + '/' + r.pairs_total + '</td></tr>';
    }).join('');
    el.innerHTML =
      '<div style="color:#A78BFA;margin-bottom:8px;">差集构造 — 数论保证 (Singer + Hadamard)</div>' +
      '<table style="font-size:10px;width:100%;">' +
      '<thead><tr style="color:#94A3B8;"><th>V</th><th>块数</th><th>2-覆盖</th><th>已覆盖对/总对</th></tr></thead>' +
      '<tbody>' + rows + '</tbody></table>' +
      '<div style="margin-top:8px;font-size:9px;color:#64748B;">' + (d.note || '') + '</div>';
  } catch(e) {
    el.innerHTML = '<div style="color:#EF4444;">加载失败</div>';
  }
}

// ═══════════════════════════════════════════════════════════
// Bandit 在线学习
// ═══════════════════════════════════════════════════════════

async function loadBandit() {
  var el = document.getElementById('arsenalBanditContent');
  if (!el) return;
  el.innerHTML = '<div style="color:#94A3B8;padding:20px;text-align:center;">Bandit策略学习中...</div>';
  try {
    // 先出号
    var sr = await fetch('/api/bandit/select?n=3');
    var sd = await sr.json();
    // 再取摘要
    var br = await fetch('/api/bandit/summary');
    var bd = await br.json();
    if (!bd.ok) { el.innerHTML = '<div style="color:#EF4444;">失败</div>'; return; }
    var armsHtml = bd.arms.map(function(a) {
      var bar = a.trials > 0 ? '<span style="display:inline-block;width:' + Math.min(a.trials*5,80) + 'px;background:#A78BFA;height:6px;border-radius:3px;"></span>' : '';
      return '<tr><td>' + a.name + '</td><td>' + a.trials + '</td>' +
        '<td>' + (a.mean_score || 0).toFixed(3) + '</td>' +
        '<td>' + bar + '</td></tr>';
    }).join('');
    el.innerHTML =
      '<div style="color:#A78BFA;margin-bottom:8px;">Thompson抽样 — 在线学习最优策略</div>' +
      '<div style="font-size:10px;color:#22C55E;margin-bottom:8px;">最佳: ' + bd.best_arm + ' (均值 ' + (bd.best_mean||0).toFixed(3) + ') | 总试验: ' + bd.total_trials + '</div>' +
      '<table style="font-size:10px;width:100%;">' +
      '<thead><tr style="color:#94A3B8;"><th>策略</th><th>试验</th><th>均值</th><th></th></tr></thead>' +
      '<tbody>' + armsHtml + '</tbody></table>' +
      '<div style="margin-top:8px;font-size:9px;color:#64748B;">' + (bd.note || '') + '</div>';
  } catch(e) {
    el.innerHTML = '<div style="color:#EF4444;">加载失败: ' + e.message + '</div>';
  }
}

// ═══════════════════════════════════════════════════════════
// Tab routing update
// ═══════════════════════════════════════════════════════════

window.switchArsenalTab = function(tab, el) {
  // Call the original or do it inline
  document.querySelectorAll('#arsenalPanel .tab-btn').forEach(function(b) { b.classList.remove('active'); });
  document.querySelectorAll('#arsenalPanel .tab-content').forEach(function(c) { c.classList.remove('active'); });
  if (el) el.classList.add('active');
  var content = document.getElementById('tab-arsenal-' + tab);
  if (content) content.classList.add('active');

  switch(tab) {
    case 'nist': loadNist(); break;
    case 'condentropy': loadCondentropy(); break;
    case 'exactcover': loadExactcover(); break;
    case 'diffset': loadDiffset(); break;
    case 'bandit': loadBandit(); break;
    case 'wheeling': loadWheeling(); break;
    case 'kelly': loadKelly(); break;
    case 'sprt': loadSprt(); break;
    case 'fdr': loadFdr(); break;
    case 'mi': loadMi(); break;
    case 'changepoint': loadChangepoint(); break;
    case 'engines': loadEngines(); break;
  }
};
