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

export function updateSoft() {
  store.useSoft = document.getElementById('softToggle').checked;
}

export function updateLuck() {
  store.useLuck = document.getElementById('luckToggle').checked;
}

export function updateDiversity() {
  store.useDiversity = document.getElementById('diversityToggle').checked;
}

export function updateGreedy() {
  store.useGreedy = document.getElementById('greedyToggle').checked;
  // 贪心模式自动启用分散红球
  if (store.useGreedy) {
    document.getElementById('diversityToggle').checked = true;
    store.useDiversity = true;
  }
}

export function updateFivePeriod() {
  store.useFivePeriod = document.getElementById('fivePeriodToggle').checked;
}

export function updateBacktest() {
  store.useBacktest = document.getElementById('backtestToggle').checked;
}

export function updateParamFilter() {
  store.useParamFilter = document.getElementById('paramFilterToggle').checked;
}

// ============ API 调用 ============

async function drawTickets(luckMode) {
  // luckMode: '' (无), '&luck=1' (blend), '&luck=2' (pure)
  updateProgress('生成中...', 20);
  const soft = store.useSoft && luckMode !== '&luck=2' ? '&soft=1' : '';
  const diversity = store.useGreedy && luckMode !== '&luck=2'
    ? '&max_overlap=2&div=1'
    : (store.useDiversity && luckMode !== '&luck=2' ? '&max_overlap=2' : '');
  const fivePeriod = store.useFivePeriod && luckMode !== '&luck=2' ? '&five_period=1' : '';
  const backtest = store.useBacktest && luckMode !== '&luck=2' ? '&backtest=1' : '';
  const paramF = store.useParamFilter && luckMode !== '&luck=2' ? '&param=1' : '';
  const bundle = store.bundledPair ? `&bundle_a=${store.bundledPair[0]}&bundle_b=${store.bundledPair[1]}` : '';
  let data;
  try {
    const r = await fetch('/api/micro/tickets?n=' + store.drawCount + soft + diversity + fivePeriod + backtest + paramF + bundle + luckMode);
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

  const isLuck = data.luck_mode && data.luck_mode !== 'off';
  if (isLuck) {
    infoRow.style.background = '#2d1b0e';
    infoRow.style.color = '#fbbf24';
  } else {
    infoRow.style.background = 'rgba(255,255,255,0.06)';
    infoRow.style.color = '#94a3b8';
  }
  const algo = data.algorithm || '';

  if (data.luck_mode === 'pure') {
    // 纯运气模式: 信息栏简化
    infoRow.innerHTML = `🧿 运气开奖 · ${algo} · 近${data.luck_window || 10}期位置加权`;
  } else {
    const rs = data.rule_status || {};
    const h2 = rs.h2_arithmetic?.excluded || 0;
    const h3 = rs.h3_historical?.excluded || 0;
    const s1 = rs.s1_consecutive?.violations?.length ? '⚠连号' : '✓连号';
    const s4 = rs.s4_max_gap?.violations?.length ? '⚠间距' : '✓间距';
    const luckTag = data.luck_mode === 'blend'
      ? ` + 运气[近${data.luck_window}期位置偏置]`
      : ` (运气规则关闭)`;
    const softTag = data.soft_filter
      ? ` + 软[${s1} ${s4} 位置] 排除${(data.soft_excluded||0).toLocaleString()}`
      : ` (软过滤关闭)`;
    const poolStr = data.pool_valid_reds != null
      ? ` → 有效池 ${data.pool_valid_reds.toLocaleString()} 红球`
      : '';
    infoRow.innerHTML = `硬过滤[等差${h2} 历史${h3}]${luckTag}${softTag}${poolStr}`;
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

  const luckMode = store.useLuck ? '&luck=1' : '';
  drawTickets(luckMode).finally(() => clearTimeout(safety));
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
