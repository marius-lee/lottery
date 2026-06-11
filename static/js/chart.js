/** Canvas走势图 */
import { store } from './store.js';

let currentChart = 'sum';

export function switchChart(type, el) {
  currentChart = type;
  if (el) {
    el.parentElement.querySelectorAll('.panel-toggle').forEach(b => b.classList.remove('active'));
    el.classList.add('active');
  }
  renderChart();
}

export function renderChart() {
  const canvas = document.getElementById('trendCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);

  if (store.DATA.length < 2) {
    ctx.fillStyle = '#999'; ctx.font = '14px sans-serif';
    ctx.textAlign = 'center'; ctx.fillText('数据不足', W / 2, H / 2);
    return;
  }

  const pad = { top: 25, right: 30, bottom: 35, left: 45 };
  const pw = W - pad.left - pad.right;
  const ph = H - pad.top - pad.bottom;

  let series = [], label = '';
  store.DATA.forEach(r => {
    if (currentChart === 'sum') {
      series.push(r.slice(1, 7).reduce((s, n) => s + n, 0));
    } else if (currentChart === 'span') {
      const s = r.slice(1, 7).sort((a, b) => a - b);
      series.push(s[5] - s[0]);
    } else if (currentChart === 'odd') {
      series.push(r.slice(1, 7).filter(n => n % 2 === 1).length);
    } else if (currentChart === 'zone') {
      const reds = r.slice(1, 7);
      const z1 = reds.filter(n => n <= 11).length;
      const z2 = reds.filter(n => n >= 12 && n <= 22).length;
      const z3 = reds.filter(n => n >= 23).length;
      series.push(z1 * 100 + z2 * 10 + z3);
    }
  });

  if (currentChart === 'sum') label = '红球和值';
  else if (currentChart === 'span') label = '红球跨度';
  else if (currentChart === 'odd') label = '奇数个数';
  else if (currentChart === 'zone') label = '三区比 (1:2:3)';

  const min = Math.min(...series), max = Math.max(...series);
  const range = max - min || 1;
  const N = series.length;

  // Grid
  ctx.strokeStyle = '#eee'; ctx.lineWidth = 0.5;
  for (let i = 0; i <= 5; i++) {
    const y = pad.top + ph * i / 5;
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(W - pad.right, y); ctx.stroke();
    ctx.fillStyle = '#999'; ctx.font = '9px sans-serif'; ctx.textAlign = 'right';
    ctx.fillText((max - range * i / 5).toFixed(currentChart === 'zone' ? 0 : 1), pad.left - 5, y + 3);
  }

  // Line
  ctx.strokeStyle = '#c41e3a'; ctx.lineWidth = 1.5; ctx.beginPath();
  const stepX = pw / (N - 1);
  series.forEach((v, idx) => {
    const x = pad.left + stepX * idx;
    const y = pad.top + ph - (v - min) / range * ph;
    if (idx === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // MA10
  const ma10 = [];
  for (let i = 0; i < N; i++) {
    const start = Math.max(0, i - 9);
    let sum = 0;
    for (let j = start; j <= i; j++) sum += series[j];
    ma10.push(sum / (i - start + 1));
  }
  ctx.strokeStyle = '#4488ff'; ctx.lineWidth = 1; ctx.setLineDash([3, 3]); ctx.beginPath();
  ma10.forEach((v, idx) => {
    const x = pad.left + stepX * idx;
    const y = pad.top + ph - (v - min) / range * ph;
    if (idx === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke(); ctx.setLineDash([]);

  // Labels
  ctx.fillStyle = '#c41e3a'; ctx.font = '11px sans-serif'; ctx.textAlign = 'left';
  ctx.fillText('─ ' + label, pad.left, 14);
  ctx.fillStyle = '#4488ff'; ctx.font = '9px sans-serif';
  ctx.fillText('--- 10期均线', pad.left + 100, 14);

  // X-axis
  ctx.fillStyle = '#999'; ctx.font = '8px sans-serif'; ctx.textAlign = 'center';
  const step = Math.max(1, Math.floor(N / 6));
  for (let i = 0; i < N; i += step) {
    const x = pad.left + stepX * i;
    ctx.fillText(String(store.DATA[i][0]).slice(-4), x, H - 5);
  }
}
