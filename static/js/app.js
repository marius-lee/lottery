/** 应用入口 */
import { store, subscribe } from './store.js';
import { loadFromServer, fetchLatestData } from './data.js';
import { renderPlaceholders, proceedWithDraw, updateAdvFilter, updateMaxOverlap, updateDiversity, updateGreedy, updateFreqBlue } from './ui/draw.js';
import { togglePanel, resetHistoryPanels, toggleOfficialHistory, toggleUserHistory, saveCurrentDraw } from './ui/panels.js';
import { switchAnalysisTab } from './ui/analysis.js';
import { switchChart } from './chart.js';
import { runAutoCompare } from './ui/compare.js';
import { refreshReviewPanel } from './ui/review.js';
import './ui/omission.js';
import './ui/signals.js';

function startDraw() {
  proceedWithDraw();
}

function updateDrawCount() {
  store.drawCount = parseInt(document.getElementById('drawCount').value);
  const bdc = document.getElementById('bannerDrawCount');
  if (bdc) bdc.textContent = store.drawCount;
  renderPlaceholders();
}

subscribe('data-changed', () => {
  renderPlaceholders();
  resetHistoryPanels();
});

function init() {
  window.store = store;
  loadFromServer().then(loaded => {
    if (!loaded) {
      const el = document.getElementById('dataMsg');
      if (el) { el.textContent = '未加载数据，请点「更新数据」初始化'; el.style.color = '#cc8800'; }
    }
  });

  Object.assign(window, {
    startDraw, updateDrawCount,
    updateAdvFilter, updateMaxOverlap, updateDiversity, updateGreedy, updateFreqBlue,
    togglePanel, toggleOfficialHistory, toggleUserHistory, saveCurrentDraw,
    runAutoCompare, fetchLatestData,
    switchAnalysisTab, switchChart, refreshReviewPanel,
  });

  renderPlaceholders();
  updateFreqBlue();
}

init();
