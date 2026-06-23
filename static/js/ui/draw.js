/** 主抽取 UI — 均匀随机采样 + 运气规则

 *  生成号码:  硬过滤 → [软过滤] → 池采样 → [运气偏置]
 *  幸运开奖:  位置加权独立抽号 → 硬过滤 → 去重
 */
import { store } from '../store.js';
import { playTick } from '../audio.js';

const delay = ms => new Promise(r => setTimeout(r, ms));

function createBall(num, type, cls) {
  const el = document.createElement('div');
  el.className = `ball ${type} ${cls || ''}`;
  el.textContent = String(num).padStart(2, '0');
  return el;
}

function createPlaceholder() {
  const el = document.createElement('div');
  el.className = 'ball placeholder';
  el.textContent = '?';
  return el;
}

function stageEl() { return document.getElementById('stage'); }
function progressEl() { return document.getElementById('drawProgress'); }
function progressBarEl() { return document.getElementById('progressBar'); }
function drawBtn() { return document.getElementById('drawBtn'); }
function saveBtn() { return document.getElementById('saveBtn'); }
function luckBtn() { return document.getElementById('luckBtn'); }

function restoreButtons() {
  const db = drawBtn(), sb = saveBtn(), lb = luckBtn();
  if (db) db.disabled = false;
  if (sb) sb.disabled = false;
  if (lb) lb.disabled = false;
}

function disableButtons() {
  const db = drawBtn(), sb = saveBtn(), lb = luckBtn();
  if (db) db.disabled = true;
  if (sb) sb.disabled = true;
  if (lb) lb.disabled = true;
}

function updateProgress(text, pct) {
  const el = progressEl(), bar = progressBarEl();
  if (el) el.textContent = text;
  if (bar) bar.style.width = (pct || 0) + '%';
}

function clearProgress() {
  const el = progressEl(), bar = progressBarEl();
  if (el) el.textContent = '';
  if (bar) bar.style.width = '0%';
}

export function renderPlaceholders() {
  const stage = stageEl();
  stage.innerHTML = '';
  for (let d = 0; d < store.drawCount; d++) {
    const row = document.createElement('div');
    row.className = 'draw-row';
    row.id = 'row-' + d;
    const label = document.createElement('span');
    label.className = 'draw-label';
    label.textContent = '#' + (d + 1);
    row.appendChild(label);
    for (let i = 0; i < 6; i++) row.appendChild(createPlaceholder());
    row.appendChild(createPlaceholder());
    stage.appendChild(row);
  }
}

// ============ 选项 ============

export function updateAdvFilter() {
  store.useAdvFilter = document.getElementById('advFilterToggle').checked;
}

export function updateDiversity() {
  store.useDiversity = document.getElementById('diversityToggle').checked;
}

export function updateGreedy() {
  store.useGreedy = document.getElementById('greedyToggle').checked;
  if (store.useGreedy) {
    document.getElementById('diversityToggle').checked = true;
    store.useDiversity = true;
  }
}

export function updateLiuBlue() {
  store.useLiuBlue = document.getElementById('liuBlueToggle').checked;
}
export function updateCaileleBlue() {
  store.useCaileleBlue = document.getElementById('caileleBlueToggle').checked;
}
export function updateGongyiBlue() {
  store.useGongyiBlue = document.getElementById('gongyiBlueToggle').checked;
}
export function updateWumingBlue() {
  store.useWumingBlue = document.getElementById('wumingBlueToggle').checked;
}

export function updateBacktest() {
  store.useBacktest = document.getElementById('backtestToggle').checked;
}
export function updateColorFilter() {
  store.useColorFilter = document.getElementById('colorFilterToggle').checked;
}
export function updateBlock9Filter() {
  store.useBlock9Filter = document.getElementById('block9FilterToggle').checked;
}
export function updateSpreadFilter() {
  store.useSpreadFilter = document.getElementById('spreadFilterToggle').checked;
}
export function updateAcFilter() {
  store.useAcFilter = document.getElementById('acFilterToggle').checked;
}
export function updatePengChannelFilter() {
  store.usePengChannelFilter = document.getElementById('pengChannelFilterToggle').checked;
}
export function updateGapFilter() {
  store.useGapFilter = document.getElementById('gapFilterToggle').checked;
}
export function updateOmissionFilter() {
  store.useOmissionFilter = document.getElementById('omissionFilterToggle').checked;
}
export function updateWumingClockwise() {
  store.useWumingClockwise = document.getElementById('wumingClockwiseToggle').checked;
}
export function updateWumingBSD() {
  store.useWumingBSD = document.getElementById('wumingBSDToggle').checked;
}
export function updateXiaBlue() {
  store.useXiaBlue = document.getElementById('xiaBlueToggle').checked;
}

export function updateTwelveValue() {
  store.useTwelveValue = document.getElementById('twelveValueToggle').checked;
}
export function updateEightValue() {
  store.useEightValue = document.getElementById('eightValueToggle').checked;
}

export function updateGridSelection() {
  store.useGridSelection = document.getElementById('gridSelectionToggle').checked;
}

// ============ API 调用 ============

async function drawTickets(luckMode) {
  // luckMode: '' (无), '&luck=1' (blend), '&luck=2' (pure)
  updateProgress('生成中...', 20);
  const advFilter = store.useAdvFilter && luckMode !== '&luck=2' ? '&adv_filter=1' : '';
  const diversity = store.useGreedy && luckMode !== '&luck=2'
    ? '&max_overlap=2&div=1'
    : (store.useDiversity && luckMode !== '&luck=2' ? '&max_overlap=2' : '');
  const liuB = store.useLiuBlue && luckMode !== '&luck=2' ? '&liu_blue=1' : '';
  const caileleB = store.useCaileleBlue && luckMode !== '&luck=2' ? '&cailele_blue=1' : '';
  const gongyiB = store.useGongyiBlue && luckMode !== '&luck=2' ? '&gongyi_blue=1' : '';
  const wumingB = store.useWumingBlue && luckMode !== '&luck=2' ? '&wuming_blue=1' : '';
  const backtest = store.useBacktest && luckMode !== '&luck=2' ? '&backtest=1' : '';
  const colorF = store.useColorFilter ? '&color_filter=1' : '';
  const block9F = store.useBlock9Filter ? '&block9_filter=1' : '';
  const spreadF = store.useSpreadFilter ? '&spread_filter=1' : '';
  const acF = store.useAcFilter ? '&ac_filter=1' : '';
  const pengChannelF = store.usePengChannelFilter ? '&peng_channel=1' : '';
  const gapF = store.useGapFilter ? '&gap_filter=1' : '';
  const omissionF = store.useOmissionFilter ? '&omission_filter=1' : '';
  const wumClock = store.useWumingClockwise ? '&wuming_clockwise=1' : '';
  const wumBSD = store.useWumingBSD ? '&wuming_bsd=1' : '';
  let data;
  try {
    const r = await fetch('/api/micro/tickets?n=' + store.drawCount + advFilter + diversity + liuB + caileleB + gongyiB + wumingB + backtest + colorF + block9F + wumClock + wumBSD + spreadF + acF + pengChannelF + gapF + omissionF + luckMode);
    data = await r.json();
  } catch (e) {
    stageEl().innerHTML = '<div style="color:#cc3333;padding:20px;">生成失败，请重试</div>';
    clearProgress();
    restoreButtons();
    return;
  }
  if (!data || !data.ok || !data.tickets || data.tickets.length === 0) {
    stageEl().innerHTML = '<div style="color:#cc3333;padding:20px;">生成失败</div>';
    clearProgress();
    restoreButtons();
    return;
  }

  const apiTickets = data.tickets.slice(0, store.drawCount);
  const results = apiTickets.map(t => ({ reds: t.reds, blue: t.blue, score: 5, fails: {} }));

  store.lastDrawResults = results;
  const stage = stageEl();
  stage.innerHTML = '';

  // 信息栏
  const infoRow = document.createElement('div');
  infoRow.style.cssText = 'font-size:10px;margin-bottom:8px;text-align:center;padding:4px 8px;border-radius:6px;';

  infoRow.style.background = 'rgba(255,255,255,0.06)';
  infoRow.style.color = '#94a3b8';
  const algo = data.algorithm || '';

  if (data.luck_mode === 'pure') {
    infoRow.style.background = '#2d1b0e';
    infoRow.style.color = '#fbbf24';
    infoRow.innerHTML = `🧿 运气开奖 · ${algo} · 近${data.luck_window || 10}期位置加权`;
  } else {
    const rs = data.rule_status || {};
    const h2 = rs.h2_arithmetic?.excluded || 0;
    const h3 = rs.h3_historical?.excluded || 0;
    const softTag = data.soft_filter
      ? ` + 高级过滤 排除${(data.soft_excluded||0).toLocaleString()}`
      : '';
    const poolStr = data.pool_valid_reds != null
      ? ` → 有效池 ${data.pool_valid_reds.toLocaleString()} 红球`
      : '';
    infoRow.innerHTML = `硬过滤[等差${h2} 历史${h3}]${softTag}${poolStr} · ${algo}`;
  }
  stage.appendChild(infoRow);

  // 票面
  for (let d = 0; d < results.length; d++) {
    const row = document.createElement('div');
    row.className = 'draw-row';
    const label = document.createElement('span');
    label.className = 'draw-label';
    label.textContent = '#' + (d + 1);
    row.appendChild(label);
    results[d].reds.forEach(n => row.appendChild(createBall(n, 'red', 'landed')));
    row.appendChild(createBall(results[d].blue, 'blue', 'landed'));
    stage.appendChild(row);
  }

  updateProgress('完成', 100);
  await delay(300);
  clearProgress();
  restoreButtons();
}

// ============ 入口点 ============

export function proceedWithDraw() {
  disableButtons();
  store.lastDrawResults = null;
  renderPlaceholders();

  const safety = setTimeout(() => {
    restoreButtons();
    clearProgress();
  }, 30000);

  drawTickets('').finally(() => clearTimeout(safety));
}

export function proceedWithLuckDraw() {
  disableButtons();
  store.lastDrawResults = null;
  renderPlaceholders();

  const safety = setTimeout(() => {
    restoreButtons();
    clearProgress();
  }, 30000);

  drawTickets('&luck=2').finally(() => clearTimeout(safety));
}

// ============ 微尔算法 ============

export async function startWeierDraw() {
  disableButtons();
  store.lastDrawResults = null;
  renderPlaceholders();
  updateProgress('微尔算法分析中...', 10);

  const safety = setTimeout(() => {
    restoreButtons();
    clearProgress();
  }, 60000);

  let data;
  try {
    const r = await fetch('/api/weier/generate');
    data = await r.json();
  } catch (e) {
    stageEl().innerHTML = '<div style="color:#cc3333;padding:20px;">微尔算法失败，请重试</div>';
    clearProgress(); restoreButtons(); clearTimeout(safety); return;
  }
  if (!data || !data.ok) {
    stageEl().innerHTML = `<div style="color:#cc3333;padding:20px;">${data?.msg || '生成失败'}</div>`;
    clearProgress(); restoreButtons(); clearTimeout(safety); return;
  }

  const results = data.tickets.map(t => ({ reds: t.reds, blue: t.blue, score: 5, fails: {} }));
  store.lastDrawResults = results;
  const stage = stageEl();
  stage.innerHTML = '';

  // 条件检测信息栏
  const infoRow = document.createElement('div');
  infoRow.style.cssText = 'font-size:10px;margin-bottom:8px;text-align:left;padding:8px 12px;border-radius:6px;background:rgba(5,150,105,0.1);color:#4ade80;line-height:1.6;';
  let logHtml = `<b>微尔算法 · 8步条件过滤</b> `;
  if (data.filter_log) {
    const exact = data.filter_log.exact_pool_size || '';
    logHtml += `| ${exact} → ${data.filter_log.final_count || data.tickets.length}注`;
  }
  if (data.warning) {
    logHtml += `<br><span style="color:#FBBF24;">⚠ ${data.warning}</span>`;
  }
  if (data.filter_log && data.filter_log.original_filtered_count) {
    logHtml += `<br>原过滤池${data.filter_log.original_filtered_count}注, 降级采样${data.tickets.length}注`;
  }
  infoRow.innerHTML = logHtml;
  stage.appendChild(infoRow);

  // 票面
  for (let d = 0; d < results.length; d++) {
    const row = document.createElement('div');
    row.className = 'draw-row';
    const label = document.createElement('span');
    label.className = 'draw-label';
    label.textContent = '#' + (d + 1);
    row.appendChild(label);
    results[d].reds.forEach(n => row.appendChild(createBall(n, 'red', 'landed')));
    row.appendChild(createBall(results[d].blue, 'blue', 'landed'));
    stage.appendChild(row);
  }

  updateProgress('完成', 100);
  await delay(300);
  clearProgress(); restoreButtons(); clearTimeout(safety);
}

// ============ 覆盖设计 (Tier 3) ============

export async function startCoveringDraw() {
  disableButtons();
  store.lastDrawResults = null;
  renderPlaceholders();
  updateProgress('覆盖设计优化中...', 10);

  const safety = setTimeout(() => {
    restoreButtons();
    clearProgress();
  }, 60000);

  let data;
  try {
    const n = store.drawCount >= 3 ? store.drawCount : 3;
    const r = await fetch('/api/covering-diverse?v=15&t=4&n=' + n);
    data = await r.json();
  } catch (e) {
    stageEl().innerHTML = '<div style="color:#cc3333;padding:20px;">覆盖设计生成失败，请重试</div>';
    clearProgress();
    restoreButtons();
    clearTimeout(safety);
    return;
  }

  if (!data || !data.ok || !data.tickets) {
    stageEl().innerHTML = '<div style="color:#cc3333;padding:20px;">' +
      (data?.msg || '覆盖设计生成失败') + '</div>';
    clearProgress();
    restoreButtons();
    clearTimeout(safety);
    return;
  }

  const results = data.tickets.map(t => ({ reds: t.reds, blue: t.blue, score: 5, fails: {} }));
  store.lastDrawResults = results;
  const stage = stageEl();
  stage.innerHTML = '';

  // 覆盖元数据栏
  const infoRow = document.createElement('div');
  infoRow.style.cssText = 'font-size:10px;margin-bottom:8px;text-align:center;padding:4px 8px;border-radius:6px;background:rgba(34,197,94,0.1);color:#4ade80;';
  if (data.covering) {
    const cov = data.covering;
    infoRow.innerHTML = `覆盖设计(v=${cov.v},t=${cov.t}) · 覆盖率≥${(cov.estimated_coverage_pct||0).toFixed(0)}% · ${cov.guarantee || ''}`;
  } else {
    infoRow.textContent = '覆盖设计';
  }
  stage.appendChild(infoRow);

  // 票面
  for (let d = 0; d < results.length; d++) {
    const row = document.createElement('div');
    row.className = 'draw-row';
    const label = document.createElement('span');
    label.className = 'draw-label';
    label.textContent = '#' + (d + 1);
    row.appendChild(label);
    results[d].reds.forEach(n => row.appendChild(createBall(n, 'red', 'landed')));
    row.appendChild(createBall(results[d].blue, 'blue', 'landed'));
    stage.appendChild(row);
  }

  updateProgress('完成', 100);
  await delay(300);
  clearProgress();
  restoreButtons();
  clearTimeout(safety);
}

// ============ 张委铭算法 ============

export async function startZhangDraw() {
  disableButtons();
  store.lastDrawResults = null;
  renderPlaceholders();
  updateProgress('张委铭算法分析中...', 10);

  const safety = setTimeout(() => {
    restoreButtons();
    clearProgress();
  }, 60000);

  // 决定调用哪个端点
  let endpoint;
  if (store.useGridSelection) {
    endpoint = '/api/zhang/grid?n=' + store.drawCount;
  } else if (store.useTwelveValue && store.useEightValue) {
    endpoint = '/api/zhang/combined?n=' + store.drawCount;
  } else if (store.useTwelveValue) {
    endpoint = '/api/zhang/twelve-value?n=' + store.drawCount;
  } else if (store.useEightValue) {
    endpoint = '/api/zhang/eight-value?n=' + store.drawCount;
  } else {
    stageEl().innerHTML = '<div style="color:#FBBF24;padding:20px;">请先在策略面板勾选张委铭选项（十二值红球/八值蓝球/行列网格）</div>';
    clearProgress(); restoreButtons(); clearTimeout(safety); return;
  }

  let data;
  try {
    const r = await fetch(endpoint);
    data = await r.json();
  } catch (e) {
    stageEl().innerHTML = '<div style="color:#cc3333;padding:20px;">张委铭算法失败，请重试</div>';
    clearProgress(); restoreButtons(); clearTimeout(safety); return;
  }
  if (!data || !data.ok) {
    stageEl().innerHTML = `<div style="color:#cc3333;padding:20px;">${data?.msg || '生成失败'}</div>`;
    clearProgress(); restoreButtons(); clearTimeout(safety); return;
  }

  const results = data.tickets.map(t => ({ reds: t.reds, blue: t.blue, score: 5, fails: {} }));
  store.lastDrawResults = results;
  const stage = stageEl();
  stage.innerHTML = '';

  // 信息栏
  const infoRow = document.createElement('div');
  infoRow.style.cssText = 'font-size:10px;margin-bottom:8px;text-align:left;padding:8px 12px;border-radius:6px;background:rgba(168,85,247,0.1);color:#A78BFA;line-height:1.6;';

  let infoHtml = '<b>张委铭 · ' + (data.algorithm || '') + '</b><br>';

  if (data.twelve_value) {
    const tv = data.twelve_value;
    infoHtml += `十二值红球: ${tv.candidate_count}个候选 [${(tv.candidates||[]).slice(0,12).join(' ')}${tv.candidate_count>12?'...':''}]<br>`;
    infoHtml += `策略: P1-2→前8, P3-4→池+邻, P5→避池选邻, P6→30-33<br>`;
    infoHtml += `<span style="color:#94A3B8;">原书1767期: avg${tv.stats.avg_hits_per_period}个/期, ≥4占${tv.stats.pct_ge_4}%</span><br>`;
  }
  if (data.grid) {
    const g = data.grid;
    infoHtml += `行列网格: ${g.mode_desc}<br>`;
    infoHtml += `断行: [${(g.break_rows||[]).join(',')||'无'}] 断列: [${(g.break_cols||[]).join(',')}]<br>`;
    infoHtml += `<span style="color:#94A3B8;">剩余${g.remaining_count}个号码: ${(g.remaining_numbers||[]).slice(0,15).join(' ')}${g.remaining_count>15?'...':''}</span><br>`;
  }
  if (data.eight_value) {
    const ev = data.eight_value;
    infoHtml += `八值蓝球: ${ev.candidate_count}个候选 [${(ev.candidates||[]).join(' ')}]<br>`;
    infoHtml += `<span style="color:#FBBF24;">${ev.use_recommendation} (连续错${ev.consecutive_errors}次)</span> `;
    infoHtml += `<span style="color:#94A3B8;">| 原书: ${ev.stats.success_rate_pct}%成功率 vs 理论${ev.stats.theoretical_rate_pct}%</span><br>`;
  }

  infoRow.innerHTML = infoHtml;
  stage.appendChild(infoRow);

  // 票面
  for (let d = 0; d < results.length; d++) {
    const row = document.createElement('div');
    row.className = 'draw-row';
    const label = document.createElement('span');
    label.className = 'draw-label';
    label.textContent = '#' + (d + 1);
    row.appendChild(label);
    results[d].reds.forEach(n => row.appendChild(createBall(n, 'red', 'landed')));
    row.appendChild(createBall(results[d].blue, 'blue', 'landed'));
    stage.appendChild(row);
  }

  updateProgress('完成', 100);
  await delay(300);
  clearProgress(); restoreButtons(); clearTimeout(safety);
}
