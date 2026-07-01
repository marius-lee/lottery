/** 出号 UI — 近期偏差加权出号 */
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

function restoreButtons() {
  const db = drawBtn(), sb = saveBtn();
  if (db) db.disabled = false;
  if (sb) sb.disabled = false;
}

function disableButtons() {
  const db = drawBtn(), sb = saveBtn();
  if (db) db.disabled = true;
  if (sb) sb.disabled = true;
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

// === 选项更新 ===

export function updateAdvFilter() {
  store.useAdvFilter = document.getElementById('advFilterToggle').checked;
}

export function updateMaxOverlap() {
  const v = document.getElementById('maxOverlap').value;
  store.maxOverlap = v === 'none' ? null : parseInt(v);
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

export function updateFreqBlue() {
  store.useFreqBlue = document.getElementById('freqBlueToggle').checked;
}

// === API 调用 ===

async function drawTickets() {
  updateProgress('生成中...', 20);
  const advFilter = store.useAdvFilter ? '&adv_filter=1' : '';
  const overlapParam = store.maxOverlap != null ? '&max_overlap=' + store.maxOverlap : '';
  const diversity = store.useGreedy
    ? '&div=1' + (store.maxOverlap == null ? '&max_overlap=2' : overlapParam)
    : (store.useDiversity ? (store.maxOverlap != null ? overlapParam : '&max_overlap=2') : overlapParam);
  const freqBlue = store.useFreqBlue ? '&freq_blue=1' : '';
  const constraintLevel = store.constraintLevel || 'normal';

  let data;
  try {
    const r = await fetch('/api/micro/tickets?n=' + store.drawCount + advFilter + diversity + freqBlue + '&constraint_level=' + constraintLevel);
    data = await r.json();
  } catch (e) {
    stageEl().innerHTML = '<div style="color:#cc3333;padding:20px;">生成失败，请重试</div>';
    clearProgress(); restoreButtons(); return;
  }
  if (!data || !data.ok || !data.tickets || data.tickets.length === 0) {
    stageEl().innerHTML = '<div style="color:#cc3333;padding:20px;">生成失败</div>';
    clearProgress(); restoreButtons(); return;
  }

  const apiTickets = data.tickets.slice(0, store.drawCount);
  const results = apiTickets.map(t => ({ reds: t.reds, blue: t.blue, score: 5, fails: {} }));
  store.lastDrawResults = results;
  const stage = stageEl();
  stage.innerHTML = '';

  // 信息栏
  const infoRow = document.createElement('div');
  infoRow.style.cssText = 'font-size:11px;margin-bottom:8px;text-align:center;padding:4px 8px;border-radius:6px;background:rgba(255,255,255,0.06);color:#FFFFFF;';
  const rs = data.rule_status || {};
  const h2 = rs.h2_arithmetic?.excluded || 0;
  const h3 = rs.h3_historical?.excluded || 0;
  const softTag = data.soft_filter ? ` + 高级过滤 排除${(data.soft_excluded||0).toLocaleString()}` : '';
  const poolStr = data.pool_valid_reds != null ? ` → 有效池 ${data.pool_valid_reds.toLocaleString()} 红球` : '';
  const blueMethod = data.blue_method ? ` · ${data.blue_method}` : '';
  infoRow.innerHTML = `硬过滤[排除${h2+h3}组合]${softTag}${poolStr}${blueMethod} · ${data.algorithm || ''}`;
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

  // 偏差摘要
  if (data.recent_bias) {
    const biasRow = document.createElement('div');
    biasRow.style.cssText = 'font-size:10px;margin-top:6px;text-align:center;color:#A78BFA;';
    const hot = data.recent_bias.slice(0, 8).map(i => '#' + i).join(' ');
    biasRow.textContent = '偏热号码: ' + hot;
    stage.appendChild(biasRow);
  }

  updateProgress('完成', 100);
  await delay(300);
  clearProgress();
  restoreButtons();
}

export async function proceedWithDraw() {
  disableButtons();
  store.lastDrawResults = null;
  renderPlaceholders();
  const safety = setTimeout(() => { restoreButtons(); clearProgress(); }, 30000);
  await drawTickets().finally(() => clearTimeout(safety));
}
