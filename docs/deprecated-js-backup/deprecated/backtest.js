/** 回测系统 — 单注回测 + 滚动回测 */
import { store, notify } from './store.js';
import { RED_EXPECTED_HITS, BLUE_HIT_PROB, WEIGHT_MIN, WEIGHT_MAX } from './constants.js';

export function runBacktest(reds, blue) {
  const total = Math.min(300, store.DATA.length);
  const hits = [];
  let maxHit = 0, minHit = 6, sumHit = 0;
  const dist = [0, 0, 0, 0, 0, 0, 0];

  store.DATA.slice(-total).forEach(r => {
    const realReds = r.slice(1, 7);
    let match = 0;
    reds.forEach(n => { if (realReds.includes(n)) match++; });
    hits.push(match);
    sumHit += match;
    if (match > maxHit) maxHit = match;
    if (match < minHit) minHit = match;
    dist[match]++;
  });

  const blueHits = store.DATA.slice(-total).filter(r => r[7] === blue).length;
  return {
    avg: (sumHit / hits.length).toFixed(2),
    max: maxHit, min: minHit, dist, total, blueHits,
  };
}

export function runRollingBacktest() {
  const windowSize = parseInt(document.getElementById('btWindow').value) || 30;
  const status = document.getElementById('btStatus');
  const resultsDiv = document.getElementById('backtestResults');
  status.textContent = '回测中...';
  status.style.color = '#c88000';

  setTimeout(async () => {
    // Use builtin sync strategies for backtest (advanced ML strategies require API)
    const { runBuiltinStrategies } = await import('./strategy/registry.js');

    const strategyNames = [
      '频率', '遗漏', '趋势', '间隔', '黄金分割', '同尾', '相似期',
      '位置', '共现', '马尔可夫蓝', '温度', '混沌', '指数优化',
    ];

    const results = {};
    strategyNames.forEach(name => {
      results[name] = { redHits: [], blueHits: 0, totalTests: 0 };
    });

    const origData = [...store.DATA];
    const testStart = Math.max(windowSize, 30);
    const testCount = Math.min(50, store.DATA.length - testStart - 1);

    for (let t = 0; t < testCount; t++) {
      const cutoff = store.DATA.length - windowSize - t - 1;
      if (cutoff < 10) break;

      // Temporarily set DATA to window
      const origStoreData = store.DATA;
      store.DATA = origData.slice(0, cutoff);
      const actual = origData[cutoff];
      if (!actual) { store.DATA = origStoreData; continue; }

      const strats = runBuiltinStrategies();

      strats.forEach(s => {
        if (!strategyNames.includes(s.name)) return;
        try {
          const actualReds = actual.slice(1, 7);
          const hits = s.reds.filter(n => actualReds.includes(n)).length;
          results[s.name].redHits.push(hits);
          if (s.blue === actual[7]) results[s.name].blueHits++;
          results[s.name].totalTests++;
        } catch (e) { /* skip */ }
      });

      store.DATA = origStoreData;
    }
    store.DATA = origData;

    // Render results
    let html = '<table class="bt-table"><thead><tr><th>策略</th><th>测试期数</th><th>场均红球命中</th><th>蓝球命中率</th><th>最高命中</th><th>推荐权重</th></tr></thead><tbody>';

    const allAvgs = [];
    strategyNames.forEach(name => {
      const r = results[name];
      if (r.totalTests === 0) return;
      const avgRed = r.redHits.reduce((a, b) => a + b, 0) / r.totalTests;
      allAvgs.push({ name, avg: avgRed });
    });

    if (allAvgs.length > 0) {
      const redBaseline = RED_EXPECTED_HITS;
      const blueBaseline = BLUE_HIT_PROB;
      const wMin = WEIGHT_MIN, wMax = WEIGHT_MAX;
      allAvgs.forEach(a => {
        store.redWeights[a.name] = Math.max(wMin, Math.min(wMax, Math.round((a.avg / redBaseline) * 10) / 10));
        const blueRate = (results[a.name].blueHits / results[a.name].totalTests);
        store.blueWeights[a.name] = Math.max(wMin, Math.min(wMax, Math.round((blueRate / blueBaseline) * 10) / 10));
      });
    }

    strategyNames.forEach(name => {
      const r = results[name];
      if (r.totalTests === 0) return;
      const avgRed = (r.redHits.reduce((a, b) => a + b, 0) / r.totalTests).toFixed(2);
      const blueRate = (r.blueHits / r.totalTests * 100).toFixed(1);
      const maxHit = Math.max(...r.redHits);
      const sw = store.redWeights[name] || 1.0;
      const badgeClass = sw >= 1.2 ? 'badge-green' : sw >= 0.8 ? 'badge-gold' : 'badge-red';
      html += `<tr><td>${name}</td><td>${r.totalTests}</td><td class="highlight">${avgRed}</td><td>${blueRate}%</td><td>${maxHit}</td><td><span class="badge ${badgeClass}">${sw.toFixed(1)}</span></td></tr>`;
    });

    html += '</tbody></table>';
    html += `<div style="font-size:10px;color:#999;margin-top:6px;">基于近${windowSize}期滑动窗口，回测${testCount}个历史节点。权重已自动更新。</div>`;
    resultsDiv.innerHTML = html;
    status.textContent = '完成';
    status.style.color = '#33aa33';

    // Persist
    persistBacktestResults(results, strategyNames, windowSize);
    notify('backtest-complete', results);

    // ML backtest
    runMLBacktest(windowSize);
    // Advanced models backtest
    runAdvancedBacktest(windowSize);
  }, 100);
}

function persistBacktestResults(results, strategyNames, windowSize) {
  const btResults = strategyNames
    .filter(name => results[name].totalTests > 0)
    .map(name => {
      const r = results[name];
      return {
        name,
        avg_red_hit: parseFloat((r.redHits.reduce((a, b) => a + b, 0) / r.totalTests).toFixed(2)),
        blue_hit_rate: parseFloat((r.blueHits / r.totalTests * 100).toFixed(1)),
        max_hit: Math.max(...r.redHits),
        test_count: r.totalTests,
        weight: store.redWeights[name] || 1.0,
      };
    });

  fetch('/api/backtest-results', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ results: btResults, windowSize }),
  }).catch(() => {});

  fetch('/api/strategy-weights', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ weights: store.redWeights, performance: store.strategyPerformance }),
  }).catch(() => {});
}

export function runMLBacktest(windowSize) {
  fetch('/api/ml/backtest-result', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ windowSize, testCount: 50 }),
  })
    .then(r => r.json())
    .then(data => {
      if (!data.ok) return;
      const table = document.querySelector('#backtestResults .bt-table');
      if (!table) return;
      const tbody = table.querySelector('tbody');
      const existingRow = tbody.querySelector('[data-strategy="AI集成"]');
      const sw = data.weight;
      const badge = `<span class="badge ${sw >= 1.2 ? 'badge-green' : sw >= 0.8 ? 'badge-gold' : 'badge-red'}">${sw.toFixed(1)}</span>`;
      const row = document.createElement('tr');
      row.setAttribute('data-strategy', 'AI集成');
      row.innerHTML = `<td>AI集成 <span style="font-size:8px;color:#999;">ML</span></td><td>${data.test_count}</td><td class="highlight">${data.avg_red_hit.toFixed(2)}</td><td>${data.blue_hit_rate.toFixed(1)}%</td><td>${data.max_hit}</td><td>${badge}</td>`;
      if (existingRow) tbody.replaceChild(row, existingRow);
      else tbody.appendChild(row);
      store.redWeights['AI集成'] = data.weight;
      store.blueWeights['AI集成'] = data.weight;

      fetch('/api/strategy-weights', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ weights: store.redWeights, performance: store.strategyPerformance }),
      }).catch(() => {});
    }).catch(() => {});
}

export function runAdvancedBacktest(windowSize) {
  fetch(`/api/ml/backtest/advanced?window=${windowSize}&tests=50`)
    .then(r => r.json())
    .then(data => {
      if (!data.ok || !data.results) return;
      const table = document.querySelector('#backtestResults .bt-table');
      if (!table) return;
      const tbody = table.querySelector('tbody');

      Object.entries(data.results).forEach(([name, r]) => {
        if (r.error) return;
        const sw = r.weight;
        const badge = `<span class="badge ${sw >= 1.2 ? 'badge-green' : sw >= 0.8 ? 'badge-gold' : 'badge-red'}">${sw.toFixed(1)}</span>`;
        const existingRow = tbody.querySelector(`[data-strategy="${name}"]`);
        const row = document.createElement('tr');
        row.setAttribute('data-strategy', name);
        row.innerHTML = `<td>${name} <span style="font-size:8px;color:#999;">高级</span></td><td>${r.test_count}</td><td class="highlight">${r.avg_red_hit}</td><td>${r.blue_hit_rate}%</td><td>${r.max_hit}</td><td>${badge}</td>`;
        if (existingRow) tbody.replaceChild(row, existingRow);
        else tbody.appendChild(row);

        // Update store weights
        store.redWeights[name] = r.weight;
        store.blueWeights[name] = r.weight;
      });

      // Persist updated weights
      fetch('/api/strategy-weights', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ weights: store.redWeights, performance: store.strategyPerformance }),
      }).catch(() => {});
    }).catch(() => {});
}
