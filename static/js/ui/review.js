/** 复盘面板 UI — 预测历史跟踪 */
import { store, subscribe } from '../store.js';

export function refreshReviewPanel() {
  const summary = document.getElementById('reviewSummary');
  const tbody = document.getElementById('reviewTbody');
  const count = document.getElementById('reviewCount');
  if (!summary || !tbody || !count) return;

  summary.innerHTML = '<span style="color:#cc8800;">加载中...</span>';

  var results = {statsData: null, entriesData: null, claimsData: {ok: false}};
  var errors = [];

  Promise.all([
    fetch('/api/prediction-log?stats=1')
      .then(function(r){
        if(!r.ok) throw new Error('stats HTTP ' + r.status);
        return r.text();
      })
      .then(function(txt){
        try { results.statsData = JSON.parse(txt); }
        catch(e){ throw new Error('stats JSON parse: ' + e.message + ' [' + txt.slice(0,200) + ']'); }
        if(!results.statsData.ok) throw new Error('stats API not ok');
      })
      .catch(function(e){ errors.push('stats: ' + e.message); }),

    fetch('/api/prediction-log?limit=200')
      .then(function(r){
        if(!r.ok) throw new Error('entries HTTP ' + r.status);
        return r.text();
      })
      .then(function(txt){
        try { results.entriesData = JSON.parse(txt); }
        catch(e){ throw new Error('entries JSON parse: ' + e.message + ' [' + txt.slice(0,200) + ']'); }
        if(!results.entriesData.ok) throw new Error('entries API not ok');
      })
      .catch(function(e){ errors.push('entries: ' + e.message); }),

    fetch('/api/claims/summary')
      .then(function(r){
        if(!r.ok) throw new Error('claims HTTP ' + r.status);
        return r.text();
      })
      .then(function(txt){
        try { results.claimsData = JSON.parse(txt); }
        catch(e){ throw new Error('claims JSON parse: ' + e.message + ' [' + txt.slice(0,200) + ']'); }
      })
      .catch(function(e){ errors.push('claims: ' + e.message); }),
  ]).then(function(){
    if(errors.length > 0){
      summary.innerHTML = '<span style="color:#EF4444;">加载失败: ' + errors.join(' | ') + '</span>';
      return;
    }
    if(!results.statsData || !results.entriesData){
      summary.innerHTML = '<span style="color:#c33;">加载失败</span>';
      return;
    }
    var statsData = results.statsData;
    var entriesData = results.entriesData;
    var claimsData = results.claimsData || {ok: false};

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

    // 兑奖统计
    if (claimsData.ok && claimsData.total_claimed > 0) {
      statsHtml += '<div style="margin-top:6px;padding:8px 12px;border-radius:6px;background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.15);">';
      statsHtml += '<div style="font-size:11px;color:#22C55E;font-weight:600;margin-bottom:4px;">✅ 自动兑奖统计 — ' + claimsData.total_claimed + ' 注已兑奖</div>';
      // 命中分布
      var hd = claimsData.hit_distribution || {};
      var barMax = Math.max.apply(null, Object.values(hd)) || 1;
      statsHtml += '<div style="display:flex;gap:4px;flex-wrap:wrap;">';
      Object.keys(hd).sort().forEach(function(k){
        var v = hd[k];
        var pct = Math.round(v / barMax * 100);
        statsHtml += '<div style="flex:1;min-width:40px;text-align:center;font-size:9px;color:#FFFFFF;">' + k + '<div style="height:4px;border-radius:2px;background:rgba(255,255,255,0.08);margin-top:2px;"><div style="height:100%;width:'+pct+'%;background:#22C55E;border-radius:2px;"></div></div><span style="color:#E2E8F0;">'+v+'</span></div>';
      });
      statsHtml += '</div>';
      // 策略排名
      var ss = claimsData.strategy_stats || [];
      if (ss.length > 0) {
        statsHtml += '<div style="margin-top:6px;font-size:10px;color:#FFFFFF;">策略TOP5:</div>';
        ss.sort(function(a,b){return b.wins - a.wins || b.avg_red - a.avg_red}).slice(0,5).forEach(function(s){
          var cls = s.avg_red > 1.09 ? 'color:#22C55E;' : 'color:#FFFFFF;';
          statsHtml += '<div style="margin:1px 0;">' + s.strategy + ': <span style="'+cls+'">均' + s.avg_red + '红</span> 蓝率' + (s.blue_rate*100).toFixed(0) + '%(' + s.total + '注) <span style="color:#FBBF24;">' + s.wins + '中奖</span></div>';
        });
      }
      statsHtml += '</div>';
    }
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
  });
}  // end refreshReviewPanel


// ── 回测执行 ──

export function runBacktest(){
  var summary = document.getElementById('reviewSummary');
  var old = summary ? summary.innerHTML : '';
  if (summary) summary.innerHTML = '<span style="color:#FBBF24;">回测运行中 (13个方法, 约1-3秒)...</span>';
  
  fetch('/api/backtest/run?window=50').then(function(r){ return r.json(); }).then(function(d){
    if (!d.ok) {
      if (summary) summary.innerHTML = '<span style="color:#EF4444;">回测失败: ' + (d.msg || '') + '</span>';
      return;
    }
    // Build results HTML
    var html = '<div style="margin-bottom:6px;padding:4px 8px;border-radius:4px;background:rgba(34,197,94,0.1);font-size:10px;">';
    html += '<b>回测完成</b> · 窗口' + d.window_size + '期 · 基线R@15=' + d.baseline_expected_hit + '红 · 数据共' + d.total_draws + '期';
    html += '</div><div style="max-height:280px;overflow-y:auto;"><table class="bt-table" style="width:100%;table-layout:fixed;">';
    html += '<thead><tr><th style="width:40%;">方法</th><th style="width:20%;">均值</th><th style="width:20%;">最佳</th><th style="width:20%;">测试</th></tr></thead><tbody>';
    (d.methods||[]).sort(function(a,b){return b.avg_red_hit - a.avg_red_hit}).forEach(function(m){
      var cls = m.avg_red_hit > d.baseline_expected_hit ? 'style="color:#22C55E;"' : '';
      html += '<tr><td>' + m.name + '</td><td ' + cls + '>' + m.avg_red_hit + '</td><td>' + m.max_hit + '</td><td>' + m.test_count + '</td></tr>';
    });
    html += '</tbody></table></div>';
    // Show weights too
    html += '<div style="margin-top:6px;font-size:9px;color:#FFFFFF;">';
    html += '<span style="color:#FBBF24;">▲</span> = 优于随机基线 · 吴明系列返回0需排查';
    html += '</div>';
    if (summary) summary.innerHTML = old + '<hr style="border-color:rgba(255,255,255,0.04);margin:8px 0;">' + html;
  }).catch(function(){
    if (summary) summary.innerHTML = '<span style="color:#EF4444;">回测请求失败</span>';
  });
};

export function runExperiments(){
  var stage = document.getElementById('stage');
  if (stage) stage.innerHTML = '<div style="text-align:center;padding:20px;color:#FFFFFF;">A/B实验模块已归档 — 待重建</div>';
};




export function loadKellyInfo(){
  var el = document.getElementById('backtestResults');
  if(!el) return;
  var html = '<div style="margin-bottom:8px;padding:6px 10px;border-radius:6px;background:rgba(34,197,94,0.06);border:1px solid rgba(34,197,94,0.1);font-size:10px;color:#FFFFFF;">';
  html += '<b>💰 Kelly最优建议</b> · 已归档 (负EV场景最优投注=0)';
  html += '</div>';
  el.innerHTML += html;
}

export function loadParticleState(){
  var el = document.getElementById('backtestResults');
  if(!el) return;
  var html = '<div style="margin-bottom:8px;padding:6px 10px;border-radius:6px;background:rgba(139,92,246,0.06);font-size:10px;color:#FFFFFF;">';
  html += '<b>🎯 粒子滤波</b> · 已归档至 ml/_deprecated/ — OOS无显著提升';
  html += '</div>';
  el.innerHTML = html;
}

export function loadBanditState(){
  var stage = document.getElementById('stage');
  if(!stage) return;
  stage.innerHTML = '<div style="padding:8px;font-size:10px;color:#FFFFFF;">🎰 策略Bandit · 已归档至 ml/_deprecated/ — 无独立验证</div>';
}

export function loadFdrFilter(){
  var el = document.getElementById('backtestResults');
  if(!el) return;
  var html = '<div style="margin-top:4px;font-size:10px;padding:4px 8px;border-radius:4px;background:rgba(34,197,94,0.04);color:#FFFFFF;">';
  html += '<b>📊 FDR筛选</b> · 已归档 — 5方法无需多重比较校正';
  html += '</div>';
  el.innerHTML += html;
}

export function loadEntropyHotness(){
  var el = document.getElementById('backtestResults');
  if(!el) return;
  var html = '<div style="margin-top:4px;font-size:10px;padding:4px 8px;border-radius:4px;background:rgba(168,85,247,0.04);color:#FFFFFF;">';
  html += '<b>🔢 熵值选号</b> · 已归档至 ml/_deprecated/ — 无独立验证';
  html += '</div>';
  el.innerHTML = html;
}

// Backward compat
window.runBacktest = runBacktest;
window.runExperiments = runExperiments;

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
