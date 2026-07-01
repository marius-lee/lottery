/** 双色球 — 入口 */
import { store, subscribe, notify, updateData } from './store.js';
import { loadDefaultData } from './data.js';
import { fetchLatestData } from './data.js';
import { startDraw, saveCurrentDraw, restoreButtons, renderPlaceholders } from './ui/draw.js';
import { togglePanel, toggleOfficialHistory, toggleUserHistory } from './ui/panels.js';
import { switchAnalysisTab } from './ui/analysis.js';
import { switchChart } from './chart.js';
import { runAutoCompare } from './ui/compare.js';
import { refreshReviewPanel } from './ui/review.js';
import { fetchSignals } from './ui/signals.js';

// ── 全局暴露 (HTML onclick/onchange 需要挂在 window) ──
window.startDraw = startDraw;
window.saveCurrentDraw = saveCurrentDraw;
window.togglePanel = togglePanel;
window.toggleOfficialHistory = toggleOfficialHistory;
window.toggleUserHistory = toggleUserHistory;
window.fetchLatestData = fetchLatestData;
window.switchAnalysisTab = switchAnalysisTab;
window.switchChart = switchChart;
window.runAutoCompare = runAutoCompare;
window.refreshReviewPanel = refreshReviewPanel;

window.updateDrawCount = function() {
  var sel = document.getElementById('drawCount');
  if (sel) store.drawCount = parseInt(sel.value, 10);
  renderPlaceholders();
};

window.updateMaxOverlap = function() {
  var sel = document.getElementById('maxOverlap');
  if (sel) {
    var v = parseInt(sel.value, 10);
    store.maxOverlap = isNaN(v) ? null : v;
  }
};

// ── 初始化 ──
document.addEventListener('DOMContentLoaded', function() {
  loadDefaultData();
  fetchSignals();
  renderPlaceholders();
  restoreButtons();
  window.updateDrawCount();
  window.updateMaxOverlap();
});

subscribe('data-changed', function() {
  fetchSignals();
  renderPlaceholders();
});
