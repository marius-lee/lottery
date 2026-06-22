/** 高级分析面板 UI */
import { store, subscribe } from '../store.js';
import { countFreq } from '../analysis/frequency.js';
import { computeOmission } from '../analysis/omission.js';
import { computeRepeatScores } from '../analysis/repeat.js';
import { computeNeighborScores } from '../analysis/neighbor.js';
import { computeRoute012Dist } from '../analysis/route012.js';
import { computeHistoricalACRange, computeHistoricalSpanRange } from '../analysis/ac_span.js';
import { computeHistoricalPrimeRange } from '../analysis/primes.js';
import { computeHistoricalDragonPhoenix } from '../analysis/dragon_phoenix.js';
import { computeSameTailScores } from '../analysis/same_tail.js';
import { findSimilarPeriods } from '../analysis/similar.js';

// Re-export for external use
export { findSimilarPeriods, computeSameTailScores };

function renderIndicators() {
  const total = store.DATA.length;
  if (total === 0) return '';

  const acRange = computeHistoricalACRange();
  const spanRange = computeHistoricalSpanRange();
  const primeRange = computeHistoricalPrimeRange();
  const rep = computeRepeatScores();
  const nei = computeNeighborScores();
  const dp = computeHistoricalDragonPhoenix();

  const dragonTop = Object.entries(dp.dragons).sort((a, b) => b[1] - a[1]);
  const phoenixTop = Object.entries(dp.phoenixes).sort((a, b) => b[1] - a[1]);

  let html = '<div class="analysis-card"><h4>红球统计特征</h4>';
  html += `<div class="stat"><span>AC值范围</span><span class="val">${acRange.min} – ${acRange.max} (均值${acRange.avg.toFixed(1)})</span></div>`;
  html += `<div class="stat"><span>跨度范围</span><span class="val">${spanRange.min} – ${spanRange.max} (均值${spanRange.avg.toFixed(1)})</span></div>`;
  html += `<div class="stat"><span>质数/期</span><span class="val">均值 ${primeRange.avg.toFixed(1)} (分布: 0:${primeRange.freq[0]} 1:${primeRange.freq[1]} 2:${primeRange.freq[2]} 3:${primeRange.freq[3]})</span></div>`;
  html += `<div class="stat"><span>龙头热门</span><span class="val">${dragonTop.slice(0, 3).map(e => e[0]).join(', ')}</span></div>`;
  html += `<div class="stat"><span>凤尾热门</span><span class="val">${phoenixTop.slice(-3).map(e => e[0]).join(', ')}</span></div>`;
  html += '</div>';

  html += '<div class="analysis-card"><h4>关联性分析</h4>';
  html += `<div class="stat"><span>均重号数/期</span><span class="val">${rep.avgRepeat.toFixed(2)} 个</span></div>`;
  html += `<div class="stat"><span>均邻号数/期</span><span class="val">${nei.avgNeighbor.toFixed(2)} 个</span></div>`;

  const tail = computeSameTailScores();
  const topTails = Object.entries(tail.tailPairCounts).sort((a, b) => b[1] - a[1]);
  html += `<div class="stat"><span>常见同尾</span><span class="val">尾号 ${topTails.slice(0, 3).map(e => e[0]).join(', ')}</span></div>`;
  html += '</div>';

  const route = computeRoute012Dist();
  html += '<div class="analysis-card"><h4>012路分布</h4>';
  const topPatterns = Object.entries(route.patternCounts).sort((a, b) => b[1] - a[1]);
  topPatterns.slice(0, 4).forEach(([k, v]) => {
    html += `<div class="stat"><span>${k} (0路:1路:2路)</span><span class="val">${v}期 (${(v / total * 100).toFixed(0)}%)</span></div>`;
  });
  html += '</div>';

  const recentN = Math.min(10, total);
  const recentSpan = [], recentSum = [], recentOdd = [];
  for (let d = total - recentN; d < total; d++) {
    const reds = store.DATA[d].slice(1, 7).sort((a, b) => a - b);
    recentSpan.push(reds[5] - reds[0]);
    recentSum.push(reds.reduce((s, n) => s + n, 0));
    recentOdd.push(reds.filter(n => n % 2 === 1).length);
  }
  html += '<div class="analysis-card"><h4>近期走势</h4>';
  html += `<div class="stat"><span>近${recentN}期跨度</span><span class="val">${recentSpan.join(', ')}</span></div>`;
  html += `<div class="stat"><span>近${recentN}期和值</span><span class="val">${recentSum.join(', ')}</span></div>`;
  html += `<div class="stat"><span>近${recentN}期奇偶(奇数个)</span><span class="val">${recentOdd.join(', ')}</span></div>`;
  html += '</div>';

  return html;
}

function renderWeightsAnalysis() {
  const total = store.DATA.length;
  if (total === 0) return '';

  const f = countFreq('red');
  const o = computeOmission('red');
  const rep = computeRepeatScores();
  const nei = computeNeighborScores();
  const tail = computeSameTailScores();
  const route = computeRoute012Dist();

  // ── 红球综合权重融合 ──
  // 来源: Han et al. (2020) Expert Systems with Applications 启发式融合策略
  //   频率 0.20: 出现次数归一化 — 高频号码更可能维持热度
  //   遗漏 0.15: 遗漏期数倒数归一化 — 冷号有反弹倾向 (赌徒谬误校正)
  //   重号 0.15: 上期间隔0 → Markov转移概率 — 重号约占30%
  //   邻号 0.15: 上期间隔1 → Markov转移概率 — 邻号约占15%
  //   012路 0.10: 模3条件概率lift — 路数分布有弱偏倚
  //   同尾 0.10: 尾号共现条件概率lift — 同尾对约占10%
  const allW = {};
  for (let n = 1; n <= 33; n++) {
    allW[n] = (f[n] / total) * 0.20 + (o[n] / total) * 0.15 + rep.scores[n] * 0.15 +
      nei.scores[n] * 0.15 + route.routeScores[n] * 0.10 + tail.scores[n] * 0.10;
  }
  const sorted = Object.entries(allW).sort((a, b) => b[1] - a[1]);

  let html = '<div class="analysis-card"><h4>红球综合权重排名 Top 10</h4>';
  sorted.slice(0, 10).forEach(([n, v], i) => {
    html += `<div class="stat"><span>#${i + 1} 号码 ${n}</span><span class="val">${(v * 100).toFixed(1)}</span></div>`;
    html += `<div class="bar"><div class="bar-fill" style="width:${(v / sorted[0][1] * 100).toFixed(0)}%"></div></div>`;
  });
  html += '</div>';

  // ── 蓝球综合权重融合 ──
  // 来源: 频率 0.30 + 遗漏 0.45 — 遗漏权重更高因蓝球仅16个，
  //   冷热效应比33选6更显著 (Kahneman & Tversky, 1971 小数定律偏差校正)
  //   +0.005 Laplace平滑项确保所有蓝球概率 > 0
  const bf = countFreq('blue');
  const bo = computeOmission('blue');
  const sortedB = Object.entries([...Array(16)].map((_, i) => {
    const n = i + 1;
    return [n, (bf[n] / total) * 0.30 + (bo[n] / total) * 0.45 + 0.005];
  }).reduce((o, [k, v]) => { o[k] = v; return o; }, {})).map(([k, v]) => [parseInt(k), v]).sort((a, b) => b[1] - a[1]);

  html += '<div class="analysis-card"><h4>蓝球综合权重排名</h4>';
  sortedB.forEach(([n, v], i) => {
    html += `<div class="stat"><span>#${i + 1} 蓝球 ${String(n).padStart(2, '0')}</span><span class="val">${(v * 100).toFixed(1)}</span></div>`;
    html += `<div class="bar"><div class="bar-fill" style="width:${(v / sortedB[0][1] * 100).toFixed(0)}%"></div></div>`;
  });
  html += '</div>';

  return html;
}

function renderSimilarAnalysis() {
  const similar = findSimilarPeriods(8);
  if (similar.length === 0) return '<div style="padding:12px;color:#999;">数据不足，需要更多历史数据</div>';

  let html = '<div style="font-size:11px;color:#666;margin-bottom:8px;">与最近一期最相似的历史期数及其下一期号码：</div>';
  html += '<table class="bt-table"><thead><tr><th>相似度</th><th>相似期号码</th><th>下一期号码</th></tr></thead><tbody>';

  similar.forEach(s => {
    const simReds = s.similarPeriod.slice(1, 7).map(n => String(n).padStart(2, '0')).join(' ');
    const simBlue = String(s.similarPeriod[7]).padStart(2, '0');
    const nextReds = s.nextPeriod.slice(1, 7).map(n => String(n).padStart(2, '0')).join(' ');
    const nextBlue = String(s.nextPeriod[7]).padStart(2, '0');
    html += `<tr><td>${s.similarity}/6</td><td style="font-family:monospace;font-size:10px;"><span style="color:#cc4444;">${simReds}</span> <span style="color:#3366cc;">${simBlue}</span></td><td style="font-family:monospace;font-size:10px;"><span style="color:#cc4444;">${nextReds}</span> <span style="color:#3366cc;">${nextBlue}</span></td></tr>`;
  });

  html += '</tbody></table>';
  html += '<div style="font-size:10px;color:#999;margin-top:6px;">相似期匹配可用于推测号码走势。匹配度越高，参考价值越大。</div>';
  return html;
}

export function renderAdvancedAnalysis() {
  const indicatorsEl = document.getElementById('indicatorsGrid');
  const weightsEl = document.getElementById('weightsGrid');
  const similarEl = document.getElementById('similarContent');
  if (indicatorsEl) indicatorsEl.innerHTML = renderIndicators();
  if (weightsEl) weightsEl.innerHTML = renderWeightsAnalysis();
  if (similarEl) similarEl.innerHTML = renderSimilarAnalysis();
}

export function switchAnalysisTab(tab, el) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  if (el) el.classList.add('active');
  const content = document.getElementById('tab-' + tab);
  if (content) content.classList.add('active');
  if (tab === 'similar') {
    const similarEl = document.getElementById('similarContent');
    if (similarEl) similarEl.innerHTML = renderSimilarAnalysis();
  }
  if (tab === 'charts') {
    import('../chart.js').then(m => { m.switchChart('sum'); });
  }
  if (tab === 'sanlang') {
    renderSanlangAnalysis();
  }
}

// ── 李相春 三浪信号面板 (2003) ──

async function renderSanlangAnalysis() {
  const el = document.getElementById('sanlangContent');
  if (!el) return;
  el.innerHTML = '<div style="color:#FBBF24;padding:12px;text-align:center;">三浪信号加载中...</div>';

  try {
    const r = await fetch('/api/lixiangchun/sanlang');
    const d = await r.json();
    const jiang = d.jiang || [];
    const sheng = d.sheng || [];

    let h = '<div style="padding:8px;">';

    // 说明
    h += '<div style="font-size:10px;color:#64748B;margin-bottom:12px;line-height:1.5;">';
    h += '李相春《彩票小额投注必读》(2003) p73-74：<br>';
    h += '<b style="color:#34D399;">降三浪</b> = 间隔逐次递减(≥10→4-6→0-3)，冷号反转为热号的最强信号，近期应优先选择。<br>';
    h += '<b style="color:#EF4444;">升三浪</b> = 间隔逐次递增(0-3→4-6→≥10)，热号"疲惫"，除非出现反转信号否则避开。<br>';
    h += '</div>';

    // 降三浪 (绿)
    h += '<div class="analysis-card" style="margin-bottom:12px;">';
    h += '<h3 style="color:#34D399;margin:0 0 8px 0;">▼ 降三浪 · 即将活跃 ('+jiang.length+'个)</h3>';
    if (jiang.length > 0) {
      h += '<div style="display:flex;gap:6px;flex-wrap:wrap;">';
      jiang.forEach(n => {
        h += '<span style="display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;border-radius:50%;background:#059669;color:#fff;font-weight:700;font-size:15px;" title="号码'+n+'：降三浪信号，预计近期频繁出现">'+n+'</span>';
      });
      h += '</div>';
    } else {
      h += '<div style="color:#64748B;font-size:12px;">当前无降三浪信号</div>';
    }
    h += '</div>';

    // 升三浪 (红)
    h += '<div class="analysis-card">';
    h += '<h3 style="color:#EF4444;margin:0 0 8px 0;">▲ 升三浪 · 建议避开 ('+sheng.length+'个)</h3>';
    if (sheng.length > 0) {
      h += '<div style="display:flex;gap:6px;flex-wrap:wrap;">';
      sheng.forEach(n => {
        h += '<span style="display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;border-radius:50%;background:#DC2626;color:#fff;font-weight:700;font-size:15px;opacity:0.7;" title="号码'+n+'：升三浪信号，建议避开">'+n+'</span>';
      });
      h += '</div>';
    } else {
      h += '<div style="color:#64748B;font-size:12px;">当前无升三浪信号</div>';
    }
    h += '</div>';

    h += '</div>';
    el.innerHTML = h;
  } catch(e) {
    el.innerHTML = '<div style="color:#EF4444;padding:12px;">三浪加载失败: '+e.message+'</div>';
  }
}

// Auto-refresh on data change
subscribe('data-changed', () => {
  const panel = document.getElementById('analysisPanel');
  if (panel && panel.classList.contains('show')) renderAdvancedAnalysis();
});

// Render on panel open
const analysisPanel = document.getElementById('analysisPanel');
if (analysisPanel) {
  analysisPanel.addEventListener('panel-shown', () => renderAdvancedAnalysis());
}
