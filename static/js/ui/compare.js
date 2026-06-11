/** 开奖对比 + 自动修正 UI
 *
 * note: weightAdjustments 的 store 写入已移除——前端策略系统已归档，
 * 权重持久化由后端 /api/compare 直接写入 SQLite 完成。
 */
import { store } from '../store.js';

export function runAutoCompare() {
  const resultDiv = document.getElementById('compareResult');
  const statusEl = document.getElementById('compareStatus');
  if (!resultDiv || !statusEl) return;
  statusEl.textContent = '';

  if (store.DATA.length === 0) {
    resultDiv.innerHTML = '<span style="color:#c88000;">暂无官方数据。请先点「更新数据」。</span>';
    return;
  }

  const latestPeriod = store.DATA[store.DATA.length - 1][0];
  const actualReds = store.DATA[store.DATA.length - 1].slice(1, 7);
  const actualBlue = store.DATA[store.DATA.length - 1][7];

  statusEl.textContent = `最新期号: ${latestPeriod}`;
  resultDiv.innerHTML = `<span style="color:#c88000;">⏳ 第${latestPeriod}期 官方号码: ${actualReds.join(' ')} + ${String(actualBlue).padStart(2, '0')} → 对比中...</span>`;

  fetch('/api/compare', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ period: latestPeriod, reds: actualReds, blue: actualBlue }),
  })
    .then(r => r.json())
    .then(data => {
      if (!data.ok) { resultDiv.innerHTML = `<span style="color:#cc3333;">错误: ${data.msg}</span>`; return; }
      if (data.pickCount === 0) {
        resultDiv.innerHTML = `<span style="color:#c88000;">第${latestPeriod}期官方已开奖，但你未保存该期的生成号码。下次记得先点「确定保存」再等开奖。</span>`;
        return;
      }
      renderCompareResult(data, resultDiv);
    })
    .catch(e => {
      resultDiv.innerHTML = `<span style="color:#cc3333;">对比失败: ${e.message}</span>`;
    });
}

function renderCompareResult(data, resultDiv) {
  let html = `<div style="font-weight:bold;color:#333;margin-bottom:6px;">📊 第${data.period}期对比分析 (${data.pickCount}注)</div>`;

  html += '<table class="bt-table"><thead><tr><th>#</th><th>推荐号码</th><th>策略</th><th>红球命中</th><th>蓝球</th><th>奖级</th></tr></thead><tbody>';
  data.picks.forEach((p, idx) => {
    let prize = '';
    if (p.red_hits === 6 && p.blue_hit) prize = '🏆一等奖!';
    else if (p.red_hits === 6) prize = '🥈二等奖';
    else if (p.red_hits === 5 && p.blue_hit) prize = '🥉三等奖';
    else if ((p.red_hits === 5) || (p.red_hits === 4 && p.blue_hit)) prize = '四等奖';
    else if ((p.red_hits === 4) || (p.red_hits === 3 && p.blue_hit)) prize = '五等奖';
    else if (p.blue_hit) prize = '六等奖';
    const bg = p.red_hits >= 4 ? 'background:#ffe0e0;' : p.blue_hit ? 'background:#e0f0ff;' : '';
    html += `<tr style="${bg}"><td>${idx + 1}</td>`;
    html += `<td style="font-family:monospace;"><span style="color:#cc4444;">${p.reds.join(' ')}</span> <span style="color:#3366cc;">${String(p.blue).padStart(2, '0')}</span></td>`;
    html += `<td>${p.strategy}</td>`;
    html += `<td style="font-weight:bold;color:${p.red_hits >= 4 ? '#c41e3a' : '#333'};">${p.red_hits}个</td>`;
    html += `<td>${p.blue_hit ? '✅' : '❌'}</td>`;
    html += `<td>${prize}</td></tr>`;
  });
  html += '</tbody></table>';

  html += '<div style="font-weight:bold;color:#333;margin:12px 0 6px;">📈 各策略表现</div>';
  html += '<table class="bt-table"><thead><tr><th>策略</th><th>注数</th><th>场均红球</th><th>蓝球命中</th><th>命中率</th></tr></thead><tbody>';
  const perf = data.strategyPerformance;
  const stratNames = Object.keys(perf).sort((a, b) => {
    const sa = (perf[a].red_hits_sum / perf[a].tries) + (perf[a].blue_hits / perf[a].tries * 10);
    const sb = (perf[b].red_hits_sum / perf[b].tries) + (perf[b].blue_hits / perf[b].tries * 10);
    return sb - sa;
  });
  stratNames.forEach(s => {
    const avgRed = (perf[s].red_hits_sum / perf[s].tries).toFixed(2);
    const blueRate = (perf[s].blue_hits / perf[s].tries * 100).toFixed(0);
    html += `<tr><td>${s}</td><td>${perf[s].tries}</td><td style="font-weight:bold;">${avgRed}</td><td>${perf[s].blue_hits}/${perf[s].tries} (${blueRate}%)</td><td>${perf[s].hits}/${perf[s].tries}</td></tr>`;
  });
  html += '</tbody></table>';

  html += '<div style="font-weight:bold;color:#333;margin:12px 0 6px;">🔧 权重自动修正</div>';
  html += '<table class="bt-table"><thead><tr><th>策略</th><th>新权重</th><th>趋势</th></tr></thead><tbody>';
  const adj = data.weightAdjustments;
  Object.keys(adj).sort((a, b) => adj[b] - adj[a]).forEach(s => {
    const trend = adj[s] >= 1.1 ? '📈' : adj[s] <= 0.7 ? '📉' : '➡️';
    html += `<tr><td>${s}</td><td style="font-weight:bold;">${adj[s].toFixed(2)}</td><td>${trend}</td></tr>`;
  });
  html += '</tbody></table>';

  html += `<div style="margin-top:12px;padding:8px;background:#f0fff0;border-radius:8px;font-size:11px;color:#33aa33;">✅ 完成。最佳策略: <b>${stratNames[0]}</b>。权重已自动更新并持久化。</div>`;

  resultDiv.innerHTML = html;
}
