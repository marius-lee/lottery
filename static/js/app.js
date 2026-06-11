/** 应用入口 — 初始化 + 事件绑定
 *
 *  面板模块已自管理生命周期：各模块独立订阅 panel-shown 事件
 *  和 data-changed 事件，不再经 panels.js 中转。
 */
import { store, subscribe } from './store.js';
import { loadFromServer, fetchLatestData } from './data.js';
import { renderPlaceholders, proceedWithDraw, proceedWithLuckDraw, updateSoft } from './ui/draw.js';
import { togglePanel, resetHistoryPanels, toggleOfficialHistory, toggleUserHistory, saveCurrentDraw } from './ui/panels.js';
import { switchAnalysisTab } from './ui/analysis.js';
import { switchChart } from './chart.js';
import { runAutoCompare } from './ui/compare.js';
import { refreshRecommend } from './ui/recommend.js';
import { refreshReviewPanel } from './ui/review.js';
// Side-effect imports: 模块级代码自注册 panel-shown 和 data-changed 监听
import './ui/omission.js';

// ========== Draw Flow (简化: 直接微投资组合) ==========

function startDraw() {
  proceedWithDraw();
}

function startLuckDraw() {
  proceedWithLuckDraw();
}

function updateDrawCount() {
  store.drawCount = parseInt(document.getElementById('drawCount').value);
  renderPlaceholders();
}

// ========== Observer: data changes → UI refresh ==========

subscribe('data-changed', () => {
  renderPlaceholders();
  resetHistoryPanels();
});

// ========== Init ==========

function init() {
  loadFromServer().then(loaded => {
    if (!loaded) {
      const el = document.getElementById('dataMsg');
      if (el) { el.textContent = '未加载数据，请点「更新数据」初始化'; el.style.color = '#cc8800'; }
    }
  });

  Object.assign(window, {
    startDraw, startLuckDraw, updateDrawCount, updateSoft,
    togglePanel, toggleOfficialHistory, toggleUserHistory, saveCurrentDraw,
    runAutoCompare, fetchLatestData,
    switchAnalysisTab, switchChart, refreshRecommend, refreshReviewPanel,
  });

  renderPlaceholders();
}

init();
