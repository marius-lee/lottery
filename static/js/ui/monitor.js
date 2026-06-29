/** 策略监控面板 — SPRT + Kelly + EV 三位一体
 *
 *  从 /api/monitor 获取实时监测数据并渲染到 monitorBar
 *  深度集成: SPRT轨迹可视化 + Kelly注数建议 + 闭环注数调整
 */

import { store } from '../store.js';

// ═══════════════════════════════════════════════════════════
// API — 返回数据供 draw.js 消费
// ═══════════════════════════════════════════════════════════

var _lastMonitorData = null;

export async function fetchMonitor() {
  var healthEl = document.getElementById('monitorHealth');
  if (!healthEl) return null;
  healthEl.textContent = '加载中...';
  healthEl.style.color = '#4ADE80';

  try {
    var n = store.drawCount || 3;
    var resp = await fetch('/api/monitor?n=' + n + '&v=15&blue=6&cap=5000');
    var d = await resp.json();

    if (!d.ok) {
      healthEl.textContent = '监控不可用';
      healthEl.style.color = '#EF4444';
      return null;
    }

    _lastMonitorData = d;
    renderMonitorBar(d);
    renderMonitorDetail(d);

    // 闭环: 将 Kelly 推荐注数写回 store
    var s = d.status || {};
    if (s.recommended_tickets != null) {
      store.kellyRecommendedN = s.recommended_tickets;
    }

    return d;
  } catch (e) {
    if (healthEl) {
      healthEl.textContent = '监控连接失败';
      healthEl.style.color = '#EF4444';
    }
    return null;
  }
}

/** 同步获取已缓存的 Kelly 推荐注数 (不发起网络请求) */
export function getKellyRecommendedN() {
  if (_lastMonitorData) {
    var s = _lastMonitorData.status || {};
    return s.recommended_tickets || 0;
  }
  return store.kellyRecommendedN || 0;
}

// ═══════════════════════════════════════════════════════════
// Render — Monitor Bar (compact, matches declaration bar style)
// ═══════════════════════════════════════════════════════════

function renderMonitorBar(d) {
  var healthEl = document.getElementById('monitorHealth');
  var samplesEl = document.getElementById('monitorSamples');
  var autoEl = document.getElementById('autoKellyLabel');
  var s = d.status || {};
  var hs = d.hit_stats || {};

  var health = s.health || '未知';
  var color = '#4ADE80';
  if (health.indexOf('高于') >= 0 || health.indexOf('信号') >= 0) color = '#22C55E';
  else if (health.indexOf('低于') >= 0) color = '#EF4444';
  else if (health.indexOf('偏高') >= 0) color = '#FBBF24';

  if (healthEl) {
    healthEl.innerHTML = '状态: <span style="font-weight:600;">' + health + '</span>';
    healthEl.style.color = color;
  }

  var rn = hs.red ? hs.red.n : 0;
  var bn = hs.blue ? hs.blue.n : 0;
  var recN = s.recommended_tickets || 0;
  var kellyStr = 'Kelly建议' + recN + '注';
  if (recN === 0) kellyStr = 'Kelly: 停投';

  if (samplesEl) {
    samplesEl.textContent = '红球' + rn + '期 | 蓝球' + bn + '期 | ' + kellyStr;
    samplesEl.style.color = '#4ADE80';
  }

  // Auto-Kelly toggle
  if (autoEl) {
    autoEl.textContent = store.useAutoKelly ? '自动' : '手动';
    autoEl.style.color = store.useAutoKelly ? '#22C55E' : '#4ADE80';
  }
}

// ═══════════════════════════════════════════════════════════
// Render — Detail Panel (expanded)
// ═══════════════════════════════════════════════════════════

function renderMonitorDetail(d) {
  var detailEl = document.getElementById('monitorDetail');
  if (!detailEl) return;

  var s = d.status || {};
  var hs = d.hit_stats || {};
  var sprt = d.sprt || {};
  var kelly = d.kelly || {};
  var ka = kelly.ev_analysis || {};
  var kp = kelly.capital_plan || {};

  var evNet = ka.net_ev != null ? ka.net_ev.toFixed(2) : '0.00';
  var evRatio = ka.ev_cost_ratio != null ? ka.ev_cost_ratio.toFixed(2) : '0.00';
  var pJackpot = ka.p_jackpot_approx != null ? ka.p_jackpot_approx.toExponential(2) : 'N/A';
  var susYears = s.sustainable_years || 0;
  var costPerDraw = s.cost_per_draw || 0;
  var signalColor = sprt.has_signal ? '#22C55E' : '#FBBF24';
  var recN = s.recommended_tickets || 0;

  var redSpark = buildSparkline(sprt.red_history || [], '#EF4444');
  var blueSpark = buildSparkline(sprt.blue_history || [], '#3B82F6');

  detailEl.innerHTML =
    '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px 16px;">' +

    '<div><b style="color:#A78BFA;">SPRT 序贯检验</b></div>' +
    '<div></div>' +
    '<div style="color:#94A3B8;">红球 LLR</div>' +
    '<div style="color:#E2E8F0;">' + (sprt.red_summary || '—') + '</div>' +
    '<div style="color:#94A3B8;">蓝球 LLR</div>' +
    '<div style="color:#E2E8F0;">' + (sprt.blue_summary || '—') + '</div>' +
    '<div style="color:#94A3B8;">结论</div>' +
    '<div style="color:' + signalColor + ';">' + (sprt.verdict || '—') + '</div>' +
    (redSpark ? '<div style="color:#94A3B8;">红球轨迹</div><div>' + redSpark + '</div>' : '') +
    (blueSpark ? '<div style="color:#94A3B8;">蓝球轨迹</div><div>' + blueSpark + '</div>' : '') +

    '<div><b style="color:#A78BFA;margin-top:6px;">Kelly 资金分配</b></div>' +
    '<div></div>' +
    '<div style="color:#94A3B8;">每注EV</div>' +
    '<div style="color:#E2E8F0;">¥' + evNet + ' (比率 ' + evRatio + ')</div>' +
    '<div style="color:#94A3B8;">头奖概率</div>' +
    '<div style="color:#E2E8F0;">~' + pJackpot + '</div>' +
    '<div style="color:#94A3B8;">推荐注数</div>' +
    '<div style="color:#22C55E;font-weight:600;">' + recN + ' 注/期</div>' +
    '<div style="color:#94A3B8;">蓝球提升</div>' +
    '<div style="color:#E2E8F0;">' + (kelly.blue_lift || 1) + 'x vs 随机</div>' +
    '<div style="color:#94A3B8;">结论</div>' +
    '<div style="color:#EF4444;">' + (kelly.verdict || '负EV') + '</div>' +

    '<div><b style="color:#A78BFA;margin-top:6px;">资本规划</b></div>' +
    '<div></div>' +
    '<div style="color:#94A3B8;">本金</div>' +
    '<div style="color:#E2E8F0;">¥' + (s.capital || 5000).toLocaleString() + '</div>' +
    '<div style="color:#94A3B8;">每期成本</div>' +
    '<div style="color:#E2E8F0;">¥' + costPerDraw + ' / 期</div>' +
    '<div style="color:#94A3B8;">可持续</div>' +
    '<div style="color:#E2E8F0;">' + susYears + ' 年</div>' +
    '<div style="color:#94A3B8;">破产评估</div>' +
    '<div style="color:#EF4444;">' + (kp.ruin_assessment || '必然破产') + '</div>' +

    '<div><b style="color:#A78BFA;margin-top:6px;">历史命中</b></div>' +
    '<div></div>' +
    '<div style="color:#94A3B8;">红球均/预期</div>' +
    '<div style="color:#E2E8F0;">' + (hs.red ? hs.red.mean : 0) + ' / ' + (hs.red ? hs.red.expected : 0) + '</div>' +
    '<div style="color:#94A3B8;">蓝球率/预期</div>' +
    '<div style="color:#E2E8F0;">' + (hs.blue ? hs.blue.rate : 0) + '% / ' + (hs.blue ? hs.blue.expected : 0) + '%</div>' +
    '<div style="color:#94A3B8;">红球lift</div>' +
    '<div style="color:#E2E8F0;">' + (hs.red ? (hs.red.lift || 1).toFixed(2) : '1.00') + 'x</div>' +
    '<div style="color:#94A3B8;">蓝球lift</div>' +
    '<div style="color:#E2E8F0;">' + (hs.blue ? (hs.blue.lift || 1).toFixed(2) : '1.00') + 'x</div>' +

    '<div style="grid-column:1/-1;margin-top:6px;color:#64748B;font-size:9px;">' +
      (d.note || '') + '</div>' +

    '</div>';
}

// ═══════════════════════════════════════════════════════════
// SPRT Trajectory Sparkline
// ═══════════════════════════════════════════════════════════

function buildSparkline(history, color) {
  if (!history || history.length < 2) return '';
  var pts = history.map(function(h) { return h.llr; });
  var min = Math.min.apply(null, pts);
  var max = Math.max.apply(null, pts);
  var range = max - min || 1;
  var w = 100, h = 24;
  var coords = pts.map(function(v, i) {
    return Math.round(i / (pts.length - 1) * w) + ',' +
           Math.round((1 - (v - min) / range) * h);
  });

  var upperY = Math.round((1 - (2.8904 - min) / range) * h);
  var lowerY = Math.round((1 - (-2.2513 - min) / range) * h);

  return '<svg width="' + w + '" height="' + h + '" style="vertical-align:middle;">' +
    '<line x1="0" y1="' + upperY + '" x2="' + w + '" y2="' + upperY + '" stroke="#22C55E" stroke-width="0.5" stroke-dasharray="2,2"/>' +
    '<line x1="0" y1="' + lowerY + '" x2="' + w + '" y2="' + lowerY + '" stroke="#EF4444" stroke-width="0.5" stroke-dasharray="2,2"/>' +
    '<polyline points="' + coords.join(' ') + '" fill="none" stroke="' + color + '" stroke-width="1.2"/>' +
    '</svg>';
}

// ═══════════════════════════════════════════════════════════
// Toggle
// ═══════════════════════════════════════════════════════════

export function toggleMonitorDetail() {
  var el = document.getElementById('monitorDetail');
  if (!el) return;
  if (el.style.display === 'none' || el.style.display === '') {
    el.style.display = 'block';
  } else {
    el.style.display = 'none';
  }
}

/** 切换 Auto-Kelly 模式: 开启后每次出号前自动查询监控调整注数 */
export function toggleAutoKelly() {
  store.useAutoKelly = !store.useAutoKelly;
  fetchMonitor();
  var msg = document.getElementById('dataMsg');
  if (msg) {
    msg.textContent = store.useAutoKelly ? 'Kelly 自动模式: 注数由监控推荐' : '手动模式: 注数由你决定';
    msg.style.color = '#A78BFA';
    setTimeout(function() { msg.textContent = ''; }, 3000);
  }
}
