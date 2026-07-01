/** 双色球 — 出号 / 保存 / 复盘 */
import { store, subscribe, notify, updateData } from './store.js';
import { loadDefaultData, fetchLatestData } from './data.js';
import { startDraw, saveCurrentDraw, restoreButtons, renderPlaceholders } from './ui/draw.js';
import { refreshReviewPanel } from './ui/review.js';
import { fetchSignals } from './ui/signals.js';

// ── window bindings ──
window.startDraw = startDraw;
window.saveCurrentDraw = saveCurrentDraw;
window.fetchLatestData = fetchLatestData;
window.refreshReviewPanel = refreshReviewPanel;

window.updateDrawCount = function() {
  var sel = document.getElementById('drawCount');
  if (sel) { store.drawCount = parseInt(sel.value, 10); renderPlaceholders(); }
};

window.updateMaxOverlap = function() {
  var sel = document.getElementById('maxOverlap');
  if (sel) {
    var v = parseInt(sel.value, 10);
    store.maxOverlap = isNaN(v) ? null : v;
  }
};

// ── init ──
document.addEventListener('DOMContentLoaded', function() {
  loadDefaultData();
  fetchSignals();
  renderPlaceholders();
  restoreButtons();
  window.updateDrawCount();
  window.updateMaxOverlap();
  refreshReviewPanel();
});

subscribe('data-changed', function() {
  fetchSignals();
  renderPlaceholders();
  refreshReviewPanel();
});
