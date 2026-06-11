/** 推荐面板 UI */
import { store, subscribe } from '../store.js';

export function refreshRecommend() {
  const container = document.getElementById('recommendContent');
  if (!container) return;
  container.innerHTML = '<span style="color:#cc8800;">加载中...</span>';

  fetch('/api/recommend')
    .then(r => r.json())
    .then(data => {
      if (!data.ok) { container.innerHTML = '<span style="color:#c33;">加载失败</span>'; return; }

      const mlBadge = data.hasML
        ? '<span style="color:#33aa33;font-size:10px;">(AI双模型)</span>'
        : '<span style="color:#999;font-size:10px;">(仅策略)</span>';
      let html = `<div style="margin-bottom:12px;">${mlBadge}</div>`;

      html += '<div style="margin-bottom:12px;"><b style="color:#c41e3a;">🔴 红球 Top 12</b>';
      html += '<div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:6px;">';
      data.reds.forEach(r => {
        const pct = Math.round(r.score * 100);
        const bg = pct >= 80 ? '#c41e3a' : pct >= 60 ? '#e8666e' : '#f0a0a0';
        html += `<div style="background:${bg};color:#fff;border-radius:6px;padding:4px 8px;text-align:center;min-width:44px;"><div style="font-size:16px;font-weight:bold;">${String(r.n).padStart(2, '0')}</div><div style="font-size:8px;">${pct}%</div></div>`;
      });
      html += '</div></div>';

      html += '<div style="margin-bottom:12px;"><b style="color:#3366cc;">🔵 蓝球 Top 4</b>';
      html += '<div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:6px;">';
      data.blues.forEach(b => {
        const pct = Math.round(b.score * 100);
        const bg = pct >= 70 ? '#3366cc' : pct >= 50 ? '#6688dd' : '#a0b8f0';
        html += `<div style="background:${bg};color:#fff;border-radius:6px;padding:4px 8px;text-align:center;min-width:44px;"><div style="font-size:16px;font-weight:bold;">${String(b.n).padStart(2, '0')}</div><div style="font-size:8px;">${pct}%</div></div>`;
      });
      html += '</div></div>';

      html += '<div><b style="color:#c88000;">💰 复式购买建议</b>';
      html += '<table class="bt-table" style="margin-top:6px;width:100%;">';
      html += '<thead><tr><th>方案</th><th>号码</th><th>蓝球</th><th>注数</th><th>金额</th></tr></thead><tbody>';
      data.suggestions.forEach(s => {
        let redsStr, bluesStr;
        if (s.bankers) {
          redsStr = `<span style="color:#c41e3a;">胆:${s.bankers.map(n => `<b>${String(n).padStart(2, '0')}</b>`).join(' ')}</span> <span style="color:#cc8888;">拖:${s.drags.map(n => String(n).padStart(2, '0')).join(' ')}</span>`;
        } else {
          redsStr = s.reds.map(n => String(n).padStart(2, '0')).join(' ');
        }
        bluesStr = s.blues ? s.blues.map(n => String(n).padStart(2, '0')).join(' ') : String(s.blue).padStart(2, '0');
        const highlight = s.cost <= 200 ? ' style="font-weight:bold;"' : '';
        html += `<tr${highlight}><td>${s.type}</td><td style="font-family:monospace;font-size:10px;">${redsStr}</td><td style="font-family:monospace;font-size:10px;color:#3366cc;">${bluesStr}</td><td>${s.tickets}注</td><td>¥${s.cost}</td></tr>`;
      });
      html += '</tbody></table>';
      html += '<div style="font-size:9px;color:#999;margin-top:4px;">复式=C(N,6)×M | 胆拖=胆码必选+拖码补位，更省钱。建议预算 ¥50-200。</div>';
      html += '</div>';

      container.innerHTML = html;
    })
    .catch(() => { container.innerHTML = '<span style="color:#c33;">加载失败，请确认服务器已运行</span>'; });
}

// Auto-refresh on data change
subscribe('data-changed', () => {
  const panel = document.getElementById('recommendPanel');
  if (panel && panel.classList.contains('show')) refreshRecommend();
});

// Render on panel open
const recommendPanel = document.getElementById('recommendPanel');
if (recommendPanel) {
  recommendPanel.addEventListener('panel-shown', () => refreshRecommend());
}
