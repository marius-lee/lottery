/** 武器库面板 — 组合数学 + 统计检验 + 信息论 */
import { store, subscribe } from '../store.js';

const API = {
  wheeling: '/api/wheeling/compare',
  kelly: '/api/kelly',
  sprt: '/api/sprt/monitor',
  fdr: '/api/fdr/filter',
  mi: '/api/mi/analyze',
  changepoint: '/api/changepoint/detect',
};

const panelEl = document.getElementById('arsenalPanel');
if (panelEl) {
  panelEl.addEventListener('panel-shown', () => loadWheeling());
}

// ═══ Tab switching ═══
window.switchArsenalTab = function(tab, el) {
  document.querySelectorAll('#arsenalPanel .tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('#arsenalPanel .tab-content').forEach(c => c.classList.remove('active'));
  if (el) el.classList.add('active');
  const content = document.getElementById('tab-arsenal-' + tab);
  if (content) content.classList.add('active');
  
  switch(tab) {
    case 'wheeling': loadWheeling(); break;
    case 'kelly': loadKelly(); break;
    case 'sprt': loadSprt(); break;
    case 'fdr': loadFdr(); break;
    case 'mi': loadMi(); break;
    case 'changepoint': loadChangepoint(); break;
  }
};

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
    el.innerHTML = h;
  } catch(e) { el.innerHTML = '<div style="color:#EF4444;">请求失败</div>'; }
}

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
    el.innerHTML = h;
  } catch(e) { el.innerHTML = '<div style="color:#EF4444;">请求失败</div>'; }
}
