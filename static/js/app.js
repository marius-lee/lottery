/** 应用入口 — 初始化 + 事件绑定
 *
 *  面板模块已自管理生命周期：各模块独立订阅 panel-shown 事件
 *  和 data-changed 事件，不再经 panels.js 中转。
 */
import { store, subscribe } from './store.js';
import { loadFromServer, fetchLatestData } from './data.js';
import { renderPlaceholders, proceedWithDraw, proceedWithLuckDraw, startCoveringDraw, startWeierDraw, startZhangDraw, updateAdvFilter, updateDiversity, updateGreedy, updateBacktest, updateFreqBlue, updateBlueMode, updateRedMode, updateTMode, updateMultiPeriod, toggleBanditMode, updateTwelveValue, updateEightValue, updateGridSelection, updateFivePeriod, updatePatternRules, fetchBiasStatus, updateVOverride } from './ui/draw.js';
import { togglePanel, resetHistoryPanels, toggleOfficialHistory, toggleUserHistory, saveCurrentDraw, toggleTraditionalFilters } from './ui/panels.js';

import { switchAnalysisTab } from './ui/analysis.js';
import { switchChart } from './chart.js';
import { runAutoCompare } from './ui/compare.js';
import { refreshRecommend } from './ui/recommend.js';
import { refreshReviewPanel, runBacktest } from './ui/review.js';
import { fetchMonitor, toggleMonitorDetail, toggleAutoKelly } from './ui/monitor.js';
import './ui/arsenal.js';  // 武器库 — 组合数学+统计检验
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
  const bdc = document.getElementById('bannerDrawCount');
  if (bdc) bdc.textContent = store.drawCount;
  renderPlaceholders();
  fetchMonitor();
}

// ========== Observer: data changes → UI refresh ==========

subscribe('data-changed', () => {
  renderPlaceholders();
  fetchMonitor();
  resetHistoryPanels();
});

// ========== Init ==========

function init() {
  window.store = store;
  loadFromServer().then(loaded => {
    if (!loaded) {
      const el = document.getElementById('dataMsg');
      if (el) { el.textContent = '未加载数据，请点「更新数据」初始化'; el.style.color = '#cc8800'; }
    }
  });

  Object.assign(window, {
    startDraw, startLuckDraw, startCoveringDraw, startWeierDraw, startZhangDraw,
    updateDrawCount, updateAdvFilter, updateDiversity, updateGreedy, updateBacktest,
    updateFreqBlue, updateBlueMode, updateRedMode, updateTMode, updateMultiPeriod, toggleBanditMode,
    updateTwelveValue, updateEightValue, updateGridSelection, updateFivePeriod, updatePatternRules,
    togglePanel, toggleOfficialHistory, toggleUserHistory, saveCurrentDraw, toggleTraditionalFilters,
    fetchBiasStatus, updateVOverride,
    runAutoCompare, fetchLatestData,
    switchAnalysisTab, switchChart, refreshRecommend, refreshReviewPanel,
    runBacktest, fetchMonitor, toggleMonitorDetail, toggleAutoKelly,
  });

  renderPlaceholders();
  updateFreqBlue();  // 初始化蓝球radio禁用状态
  fetchMonitor();
  fetchBiasStatus();  // 偏差信号面板

  // 蓝球遗漏警报 (吴明2010 博彩基本公式)
  fetch('/api/wuming/blue-alert').then(r => r.json()).then(d => {
    if (!d.ok) return;
    const warned = d.alerts.filter(a => a.alert);
    if (warned.length === 0) return;
    const el = document.getElementById('blueAlertBar');
    if (!el) return;
    el.style.display = 'block';
    el.innerHTML = '⚠ 蓝球告警 [吴明2010] 理论极值107期: ' +
      warned.map(a => `${String(a.blue).padStart(2,'0')}(缺${a.omission}期/${a.pct_to_extreme}%)`).join(' · ');
  }).catch(() => {});
}

init();
