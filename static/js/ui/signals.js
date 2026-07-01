/** 多算法信号面板 — gap + position 融合结果 */
import { store, subscribe } from '../store.js';

var _cachedBacktest = null;

export function fetchSignals() {
  var el = document.getElementById('signalsContent');
  if (!el) return;
  el.innerHTML = '<span style="color:#999;">加载中...</span>';

  Promise.all([
    fetch('/api/signals').then(function(r) { return r.json(); }),
    _cachedBacktest
      ? Promise.resolve(_cachedBacktest)
      : fetch('/api/backtest').then(function(r) { return r.json(); }).then(function(d) { _cachedBacktest = d; return d; })
  ]).then(function(arr) {
    var sigs = arr[0], bt = arr[1];
    if (!sigs.ok) { el.innerHTML = '<span style="color:#EF4444;">信号获取失败</span>'; return; }
    renderSignals(sigs, bt, el);
  }).catch(function() {
    el.innerHTML = '<span style="color:#EF4444;">连接失败</span>';
  });
}

function renderSignals(sigs, bt, el) {
  var alg = sigs.algorithms || {};
  var hot = sigs.hot_numbers || [];
  var btResults = (bt && bt.ok) ? bt.results : {};

  var html = '';

  // 🔴 红球偏热 (融合结果)
  html += '<div style="margin-bottom:6px;">';
  html += '<span style="color:#EF4444;font-weight:600;font-size:var(--sig-label);">🔴 红球</span> ';
  if (hot.length === 0) {
    html += '<span style="color:#999;font-size:var(--sig-hint);">无偏热信号</span>';
  } else {
    hot.forEach(function(item) {
      var num = item[0], w = item[1];
      var intensity = Math.min(1, (w - 1.05) / 0.3);
      var hue = 40 - intensity * 30;
      html += '<span style="display:inline-block;width:var(--sig-ball-diam);height:var(--sig-ball-diam);line-height:var(--sig-ball-diam);text-align:center;'
        + 'border-radius:50%;background:hsl(' + hue + ',80%,' + (50 + intensity*15) + '%);'
        + 'color:#000;font-weight:700;font-size:var(--sig-ball);margin:3px;"'
        + ' title="权重 ' + w.toFixed(3) + '">' + num + '</span>';
    });
  }
  html += '</div>';

  // 🔵 蓝球偏热
  var blueHot = sigs.blue_hot || [];
  html += '<div style="margin-bottom:6px;">';
  html += '<span style="color:#3B82F6;font-weight:600;font-size:var(--sig-label);">🔵 蓝球</span> ';
  if (blueHot.length === 0) {
    html += '<span style="color:#999;font-size:var(--sig-hint);">无偏热信号</span>';
  } else {
    blueHot.forEach(function(item) {
      var num = item[0], w = item[1];
      var intensity = Math.min(1, (w - 1.05) / 0.3);
      html += '<span style="display:inline-block;width:var(--sig-ball-diam);height:var(--sig-ball-diam);line-height:var(--sig-ball-diam);text-align:center;'
        + 'border-radius:50%;background:hsl(220,70%,' + (45 + intensity*20) + '%);'
        + 'color:#fff;font-weight:700;font-size:var(--sig-ball);margin:3px;"'
        + ' title="权重 ' + w.toFixed(3) + '">' + num + '</span>';
    });
  }
  html += '</div>';

  // 算法卡片
  var algoOrder = ['gap_analysis', 'position'];
  var algoNames = {
    gap_analysis: '间隔分析', position: '位置概率',
  };

  html += '<div style="display:flex;gap:4px;flex-wrap:wrap;">';
  algoOrder.forEach(function(key) {
    var info = alg[key];
    if (!info || info.error) return;

    var btData = btResults[key];
    var lift = (btData && btData.lift != null) ? btData.lift : null;

    var color, icon;
    if (lift == null) { color = '#999'; icon = '?'; }
    else if (lift > 1.01) { color = '#22C55E'; icon = '▲'; }
    else if (lift >= 0.99) { color = '#FBBF24'; icon = '→'; }
    else { color = '#EF4444'; icon = '▼'; }

    var liftStr = lift ? ' lift=' + lift.toFixed(3) : '';

    html += '<span style="display:inline-block;padding:3px 6px;border-radius:4px;'
      + 'background:rgba(139,92,246,0.04);border:1px solid rgba(139,92,246,0.08);'
      + 'font-size:var(--sig-card);color:' + color + ';margin-bottom:1px;">'
      + icon + ' ' + (algoNames[key] || key) + liftStr + '</span>';
  });
  html += '</div>';

  el.innerHTML = html;
}

subscribe('data-changed', fetchSignals);
fetchSignals();
