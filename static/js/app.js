/** 双色球 — 入口 */
import { store, subscribe, notify, updateData } from './store.js';
import { fetchData } from './ui/data.js';
import { startDraw, saveCurrentDraw, restoreButtons } from './ui/draw.js';
import { renderPanels } from './ui/panels.js';
import { fetchSignals } from './ui/signals.js';
import { renderReview } from './ui/review.js';

// 全局暴露
window.startDraw = startDraw;
window.saveCurrentDraw = saveCurrentDraw;
window.updateMaxOverlap = function(v) { store.maxOverlap = v; };

// 初始化
document.addEventListener('DOMContentLoaded', function() {
  fetchData();
  fetchSignals();
  renderPanels();
  renderReview();
  restoreButtons();

  var nSelect = document.getElementById('drawCountSelect');
  if (nSelect) {
    nSelect.addEventListener('change', function() {
      store.drawCount = parseInt(nSelect.value, 10);
    });
  }
});

subscribe('data-changed', function() {
  fetchSignals();
  renderReview();
  renderPanels();
});
