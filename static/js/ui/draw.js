/** 出号 UI — gap + position 信号融合出号 */
import { store, subscribe, notify } from '../store.js';

function stageEl() { return document.getElementById('stage'); }
function progressTextEl() { return document.getElementById('drawProgress'); }
function progressBarEl() { return document.getElementById('progressBar'); }
function drawBtn() { return document.getElementById('drawBtn'); }
function saveBtn() { return document.getElementById('saveBtn'); }

// === 占位符 ===

function createPlaceholder() {
  var el = document.createElement('div');
  el.className = 'ball placeholder';
  el.textContent = '?';
  return el;
}

export function renderPlaceholders() {
  var stage = stageEl();
  if (!stage) return;
  stage.innerHTML = '';
  for (var i = 0; i < store.drawCount; i++) {
    var row = document.createElement('div');
    row.className = 'draw-row';
    row.id = 'row-' + i;
    var label = document.createElement('span');
    label.className = 'draw-label';
    label.textContent = '#' + (i + 1);
    row.appendChild(label);
    for (var j = 0; j < 7; j++) row.appendChild(createPlaceholder());
    stage.appendChild(row);
  }
}

// === 进度 ===

function updateProgress(text, pct) {
  var el = progressTextEl(), bar = progressBarEl();
  if (el) el.textContent = text;
  if (bar) bar.style.width = (pct || 0) + '%';
}

function clearProgress() {
  var el = progressTextEl(), bar = progressBarEl();
  if (el) el.textContent = '';
  if (bar) bar.style.width = '0%';
}

export function restoreButtons() {
  var db = drawBtn(), sb = saveBtn();
  if (db) db.disabled = false;
  if (sb) sb.disabled = false;
}

function disableButtons() {
  var db = drawBtn(), sb = saveBtn();
  if (db) db.disabled = true;
  if (sb) sb.disabled = true;
}

// === 出号 ===

export async function startDraw() {
  disableButtons();
  clearProgress();
  stageEl().innerHTML = '';
  await drawTickets();
}

async function drawTickets() {
  updateProgress('生成中...', 20);
  var params = '?n=' + store.drawCount;
  if (store.maxOverlap != null) params += '&max_overlap=' + store.maxOverlap;
  params += '&constraint_level=normal';

  var data;
  try {
    var r = await fetch('/api/micro/tickets' + params);
    data = await r.json();
  } catch (e) {
    stageEl().innerHTML = '<div style="color:#cc3333;padding:20px;">生成失败，请重试</div>';
    clearProgress(); restoreButtons(); return;
  }
  if (!data || !data.ok || !data.tickets || data.tickets.length === 0) {
    stageEl().innerHTML = '<div style="color:#cc3333;padding:20px;">生成失败</div>';
    clearProgress(); restoreButtons(); return;
  }

  updateProgress('', 90);
  var apiTickets = data.tickets.slice(0, store.drawCount);

  // 渲染
  var stage = stageEl();
  stage.innerHTML = '';
  for (var i = 0; i < apiTickets.length; i++) {
    var t = apiTickets[i];
    var row = document.createElement('div');
    row.className = 'draw-row';
    var label = document.createElement('span');
    label.className = 'draw-label';
    label.textContent = '#' + (i + 1);
    row.appendChild(label);
    for (var j = 0; j < 6; j++) {
      var ball = document.createElement('div');
      ball.className = 'ball red';
      ball.textContent = String(t.reds[j]).padStart(2, '0');
      row.appendChild(ball);
    }
    var blue = document.createElement('div');
    blue.className = 'ball blue';
    blue.textContent = String(t.blue).padStart(2, '0');
    row.appendChild(blue);
    stage.appendChild(row);
  }

  store.lastDrawResults = { tickets: apiTickets, info: data };
  notify('draw-complete', apiTickets);

  clearProgress();
  restoreButtons();
}

// === 保存 ===

export function saveCurrentDraw() {
  var results = store.lastDrawResults;
  if (!results || !results.tickets) return;
  fetch('/api/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tickets: results.tickets.map(function(t) { return { reds: t.reds, blue: t.blue }; }),
      strategy: 'Gap+Position',
    }),
  }).then(function(r) { return r.json(); })
  .then(function(d) {
    if (d.ok) {
      var sb = saveBtn();
      if (sb) { sb.disabled = true; sb.textContent = '已保存'; }
      notify('data-changed');
    }
  });
}
