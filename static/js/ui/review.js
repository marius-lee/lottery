/** 复盘面板 UI — 预测历史跟踪 */
import { store, subscribe } from '../store.js';

export function refreshReviewPanel() {
  const summary = document.getElementById('reviewSummary');
  const tbody = document.getElementById('reviewTbody');
  const count = document.getElementById('reviewCount');
  if (!summary || !tbody || !count) return;

  summary.innerHTML = '<span style="color:#cc8800;">加载中...</span>';

  Promise.all([
    fetch('/api/prediction-log?stats=1').then(r => r.json()),
    fetch('/api/prediction-log?limit=200').then(r => r.json()),
  ]).then(([statsData, entriesData]) => {
    if (!statsData.ok || !entriesData.ok) {
      summary.innerHTML = '<span style="color:#c33;">加载失败</span>';
      return;
    }

    const stats = statsData.stats;
    let statsHtml = '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:8px;">';
    if (Object.keys(stats).length === 0) {
      statsHtml += '<span style="color:#999;">暂无数据。保存选号并等开奖后，点击"开奖对比"即可自动记录。</span>';
    } else {
      Object.keys(stats).sort().forEach(src => {
        const s = stats[src];
        statsHtml += `<div style="background:#f0f0ff;border-radius:8px;padding:6px 12px;min-width:130px;"><div style="font-weight:bold;color:#3366cc;font-size:11px;">${src}</div><div style="font-size:10px;">测试: ${s.total} 次</div><div style="font-size:10px;color:#c41e3a;">均红球: ${s.avg_red}</div><div style="font-size:10px;color:#3366cc;">蓝球率: ${s.blue_rate}%</div><div style="font-size:10px;">最高: ${s.max_hit}红</div></div>`;
      });
    }
    statsHtml += '</div>';
    summary.innerHTML = statsHtml;

    const entries = entriesData.entries;
    let html = '';
    entries.forEach(e => {
      const predReds = JSON.parse(e.reds_json || '[]');
      const actualReds = e.actual_reds_json ? JSON.parse(e.actual_reds_json) : null;
      const predStr = predReds.map(n => String(n).padStart(2, '0')).join(' ');
      const actualStr = actualReds ? actualReds.map(n => String(n).padStart(2, '0')).join(' ') : '待开奖';
      const cls = e.red_hits >= 4 ? 'highlight' : '';
      const bi = e.blue_hit === 1 ? '✅' : e.blue_hit === 0 ? '❌' : '—';
      html += `<tr><td>${e.period}</td><td>${e.source}</td><td style="font-family:monospace;font-size:10px;"><span style="color:#cc4444;">${predStr}</span></td><td style="font-family:monospace;font-size:10px;">${actualStr}</td><td class="${cls}">${e.red_hits >= 0 ? e.red_hits + '个' : '—'}</td><td>${bi}</td></tr>`;
    });
    tbody.innerHTML = html;
    count.textContent = `共 ${entries.length} 条记录`;

    // Sparkline
    const canvas = document.getElementById('reviewTrendCanvas');
    if (!canvas) return;
    if (entries.length >= 3) {
      canvas.style.display = 'block';
      const ctx = canvas.getContext('2d');
      const W = canvas.width, H = canvas.height;
      ctx.clearRect(0, 0, W, H);

      const recent = entries.slice(0, 30).reverse();
      const hits = recent.map(e => e.red_hits);
      const maxHit = Math.max(...hits, 6);
      const padding = 10;

      ctx.strokeStyle = '#e0e0e0'; ctx.lineWidth = 0.5;
      for (let g = 0; g <= maxHit; g++) {
        const gy = H - padding - (g / maxHit) * (H - 2 * padding);
        ctx.beginPath(); ctx.moveTo(padding, gy); ctx.lineTo(W - padding, gy); ctx.stroke();
        ctx.fillStyle = '#999'; ctx.font = '8px sans-serif';
        ctx.fillText(g + '红', 2, gy + 3);
      }

      if (hits.length > 1) {
        const stepX = (W - 2 * padding) / (hits.length - 1);
        ctx.strokeStyle = '#3366cc'; ctx.lineWidth = 2; ctx.beginPath();
        hits.forEach((h, i) => {
          const x = padding + i * stepX;
          const y = H - padding - (h / maxHit) * (H - 2 * padding);
          i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        });
        ctx.stroke();

        hits.forEach((h, i) => {
          const x = padding + i * stepX;
          const y = H - padding - (h / maxHit) * (H - 2 * padding);
          ctx.fillStyle = h >= 4 ? '#c41e3a' : h >= 2 ? '#3366cc' : '#999';
          ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI * 2); ctx.fill();
        });

        const avg = hits.reduce((a, b) => a + b, 0) / hits.length;
        const avgY = H - padding - (avg / maxHit) * (H - 2 * padding);
        ctx.strokeStyle = '#cc8800'; ctx.lineWidth = 1; ctx.setLineDash([3, 3]);
        ctx.beginPath(); ctx.moveTo(padding, avgY); ctx.lineTo(W - padding, avgY); ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = '#cc8800';
        ctx.fillText('均' + avg.toFixed(1), W - 35, avgY - 4);
      }
    } else {
      canvas.style.display = 'none';
    }
  }).catch(() => {
    summary.innerHTML = '<span style="color:#c33;">加载失败，请确认服务器已运行</span>';
  });
}

// Auto-refresh on data change
subscribe('data-changed', () => {
  const panel = document.getElementById('reviewPanel');
  if (panel && panel.classList.contains('show')) refreshReviewPanel();
});

// Render on panel open
const reviewPanel = document.getElementById('reviewPanel');
if (reviewPanel) {
  reviewPanel.addEventListener('panel-shown', () => refreshReviewPanel());
}
