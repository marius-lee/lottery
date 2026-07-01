/** 出号 UI — gap + position 信号融合出号 */
import { store, subscribe } from '../store.js';

// 进度条
var _progressTimer = null;
function progressEl() { return document.getElementById('progressBar'); }
function stageEl() { return document.getElementById('ticketStage'); }
function infoRowEl() { return document.getElementById('drawInfo'); }

export function updateProgress(msg, pct) {
  var el = progressEl();
  if (!el) return;
  el.style.width = Math.min(100, pct) + '%';
  el.textContent = msg + ' ' + pct + '%';
}

export function clearProgress() {
  var el = progressEl();
  if (el) { el.style.width = '0%'; el.textContent = ''; }
}

export function restoreButtons() {
  document.getElementById('drawBtn').disabled = false;
  document.getElementById('saveBtn').disabled = true;
}

// === 出号 ===

export async function startDraw() {
  var btn = document.getElementById('drawBtn');
  btn.disabled = true;
  document.getElementById('saveBtn').disabled = true;
  stageEl().innerHTML = '';
  infoRowEl().innerHTML = '';

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

  updateProgress('渲染...', 90);
  var apiTickets = data.tickets.slice(0, store.drawCount);
  var results = apiTickets.map(function(t) { return { reds: t.reds, blue: t.blue, score: 5, fails: {} }; });

  store.lastDrawResults = { tickets: results, info: data };
  notify('draw-complete', results);
  renderTickets(results, data);
  updateProgress('', 100);
  restoreButtons();
}

function renderTickets(tickets, data) {
  var poolStr = data.pool_valid_reds ? ' 组合池有效' + data.pool_valid_reds.toLocaleString() : '';
  var blueMethod = data.blue_method || '间隔分析蓝球';
  infoRowEl().innerHTML = '硬过滤[排除历史]' + poolStr + ' · ' + blueMethod + ' · ' + (data.algorithm || '');

  var html = tickets.map(function(t, i) {
    var redsHtml = t.reds.map(function(num) {
      return '<span class="ball ball-red">' + num + '</span>';
    }).join('');
    return '<div class="ticket-row">'
      + '<span class="ticket-num">' + (i + 1) + '</span>'
      + redsHtml
      + '<span class="ball ball-blue">' + t.blue + '</span>'
      + '</div>';
  }).join('');
  stageEl().innerHTML = html;
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
      document.getElementById('saveBtn').disabled = true;
      document.getElementById('saveBtn').textContent = '已保存';
      notify('data-changed');
    }
  });
}

// === 选区无状态变化 — 不再需要 toggle 函数 ===

subscribe('data-changed', function() {
  // auto-refresh signals on data change
  import('./signals.js').then(function(m) { m.fetchSignals(); });
});
