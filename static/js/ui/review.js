/** 复盘面板 — 基于 user_picks + draws 直接计算命中 */
import { store, subscribe } from '../store.js';

export function refreshReviewPanel() {
  const summary = document.getElementById('reviewSummary');
  const tbody = document.getElementById('reviewTbody');
  const count = document.getElementById('reviewCount');
  if (!summary || !tbody || !count) return;

  summary.innerHTML = '<span style="color:#cc8800;">加载中...</span>';

  // 从 user_picks + draws 直接计算命中
  fetch('/api/user-picks')
    .then(r => r.json())
    .then(picksJson => {
      const picks = picksJson.picks || [];
      const draws = store.DATA || [];

      // 构建期号→开奖号码 map
      const drawMap = {};
      draws.forEach(d => {
        drawMap[d[0]] = { reds: new Set(d.slice(1, 7)), blue: d[7] };
      });

      // 计算每注命中
      const results = [];
      const stratStats = {};
      picks.forEach(p => {
        const draw = drawMap[p.period];
        if (!draw) {
          results.push({ ...p, red_hits: -1, blue_hit: -1, actual_reds: null });
          return;
        }
        const userReds = new Set([p.r1, p.r2, p.r3, p.r4, p.r5, p.r6]);
        const rh = [...userReds].filter(r => draw.reds.has(r)).length;
        const bh = p.blue === draw.blue ? 1 : 0;
        results.push({
          ...p,
          red_hits: rh,
          blue_hit: bh,
          actual_reds: [...draw.reds].sort((a,b) => a-b)
        });
        const strat = p.strategy || 'unknown';
        if (!stratStats[strat]) stratStats[strat] = { total: 0, red_sum: 0, blue_sum: 0, max_hit: 0 };
        stratStats[strat].total++;
        stratStats[strat].red_sum += rh;
        stratStats[strat].blue_sum += bh;
        stratStats[strat].max_hit = Math.max(stratStats[strat].max_hit, rh);
      });

      // 统计摘要
      let statsHtml = '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:8px;">';
      if (Object.keys(stratStats).length === 0) {
        statsHtml += '<span style="color:#999;">暂无数据。生成号码后点击「保存」，开奖后再点「开奖对比」即可自动记录。</span>';
      } else {
        Object.keys(stratStats).sort().forEach(src => {
          const s = stratStats[src];
          const avgR = (s.red_sum / s.total).toFixed(2);
          const blueR = (s.blue_sum / s.total * 100).toFixed(0);
          statsHtml += `<div style="background:rgba(59,130,246,0.06);border:1px solid rgba(59,130,246,0.12);border-radius:8px;padding:6px 12px;min-width:130px;">
            <div style="font-weight:bold;color:#60A5FA;font-size:11px;">${src}</div>
            <div style="font-size:10px;color:#FFFFFF;">测试: ${s.total} 次</div>
            <div style="font-size:10px;color:#EF4444;">均红球: ${avgR}</div>
            <div style="font-size:10px;color:#3B82F6;">蓝球率: ${blueR}%</div>
            <div style="font-size:10px;color:#FFFFFF;">最高: ${s.max_hit}红</div>
          </div>`;
        });
      }
      statsHtml += '</div>';
      summary.innerHTML = statsHtml;

      // 明细表格
      let html = '';
      results.forEach(e => {
        const predStr = [e.r1, e.r2, e.r3, e.r4, e.r5, e.r6]
          .map(n => String(n).padStart(2, '0')).join(' ');
        const actualStr = e.actual_reds
          ? e.actual_reds.map(n => String(n).padStart(2, '0')).join(' ')
          : '待开奖';
        const cls = e.red_hits >= 4 ? 'highlight' : '';
        const bi = e.blue_hit === 1 ? '✅' : e.blue_hit === 0 ? '❌' : '—';
        html += `<tr><td>${e.period}</td>
          <td style="font-family:monospace;font-size:10px;"><span style="color:#EF4444;">${predStr}</span> <span style="color:#3B82F6;">${String(e.blue).padStart(2,'0')}</span></td>
          <td style="font-family:monospace;font-size:10px;">${actualStr} ${e.actual_reds ? '<span style="color:#3B82F6;">'+String(drawMap[e.period].blue).padStart(2,'0')+'</span>' : ''}</td>
          <td class="${cls}">${e.red_hits >= 0 ? e.red_hits + '个' : '—'}</td>
          <td>${bi}</td></tr>`;
      });
      tbody.innerHTML = html;
      count.textContent = `共 ${results.length} 条记录`;
    })
    .catch(e => {
      summary.innerHTML = `<span style="color:#EF4444;">加载失败: ${e.message}</span>`;
    });
}

export function runBacktest() {
  const summary = document.getElementById('reviewSummary');
  if (summary) summary.innerHTML = '<span style="color:#FBBF24;">回测功能已移除</span>';
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
