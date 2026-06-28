/** 内联UI函数 — 作者面板 + 红球/蓝球生成 + 合并 + 高级按钮
 *
 *  非模块脚本 (<script src>), 通过 window.store 访问全局状态.
 *  原因: 部分函数在模块加载前需可用 (onclick 属性).
 */
window.store = window.store || {};

// ═══════════════════════════════════════════════════════════════
// 作者面板
// ═══════════════════════════════════════════════════════════════

var _authorHandlers = {
  weier: function(){ window._showWeierPanel&&window._showWeierPanel(); },
  zhang: function(){ window._showZhangPanel&&window._showZhangPanel(); },
  lizhilin: function(){ window._showLiZhiLinPanel&&window._showLiZhiLinPanel(); },
  peng: function(){ window._showPengPanel&&window._showPengPanel(); },
  jiangjialin: function(){ window._showJiangJiaLinPanel&&window._showJiangJiaLinPanel(); },
  wuming: function(){ window._showWuMingPanel&&window._showWuMingPanel(); },
  lixiangchun: function(){ window._showLiXiangChunPanel&&window._showLiXiangChunPanel(); },
  liudajun: function(){ window._showLiuDaJunPanel&&window._showLiuDaJunPanel(); },
  zeng: function(){ window._showZengPanel&&window._showZengPanel(); },
  yang: function(){ window._showYangPanel&&window._showYangPanel(); },
  experiments: function(){ window.runExperiments&&window.runExperiments(); }
};

window.switchAuthor = function(author){
  if(!author) return;
  window.store.currentAuthor = author;
  document.getElementById('authorSelect').value = author;
  var tabBtns = document.querySelectorAll('.panel-tab[role=tab]');
  tabBtns.forEach(function(b){ b.classList.remove('active'); });
  var panels = document.querySelectorAll('.content-panel');
  panels.forEach(function(p){ p.classList.remove('show'); });
  var panelEl = document.getElementById(author+'Panel');
  if(panelEl) panelEl.classList.add('show');
  if(_authorHandlers[author]) _authorHandlers[author]();
};

// ═══════════════════════════════════════════════════════════════
// 红球生成
// ═══════════════════════════════════════════════════════════════

window._lastReds = [];
window._lastBlues = [];

// generateReds — 已废弃，请使用「出号」按钮 (startDraw)
window.generateReds = function(){ window.startDraw&&window.startDraw(); };

// ═══════════════════════════════════════════════════════════════
// 蓝球生成
// ═══════════════════════════════════════════════════════════════

// generateBlues — 已废弃，请使用「出号」按钮 (startDraw)
window.generateBlues = function(){ window.startDraw&&window.startDraw(); };

// ═══════════════════════════════════════════════════════════════
// 合并红蓝
// ═══════════════════════════════════════════════════════════════

// mergeTickets — 已废弃，请使用「出号」按钮 (startDraw)
window.mergeTickets = function(){ window.startDraw&&window.startDraw(); };

// ═══════════════════════════════════════════════════════════════
// 辅助渲染
// ═══════════════════════════════════════════════════════════════

function renderTickets(stage, d){
  var tickets = d.tickets || [];
  var redsList = [], bluesList = [];
  tickets.forEach(function(t, i){
    var row = document.createElement('div');
    row.style.cssText = 'display:flex;align-items:center;gap:6px;justify-content:center;margin-bottom:6px;';
    row.innerHTML = '<span style="color:#64748B;font-size:11px;min-width:20px;">#'+(i+1)+'</span>';
    t.reds.forEach(function(rn){
      var b = document.createElement('span');
      b.className = 'ball red';
      b.textContent = String(rn).padStart(2,'0');
      row.appendChild(b);
    });
    var bb = document.createElement('span');
    bb.className = 'ball blue';
    bb.textContent = String(t.blue).padStart(2,'0');
    row.appendChild(bb);
    stage.appendChild(row);
    redsList.push(t.reds);
    bluesList.push(t.blue);
  });
  window._lastReds = redsList;
  window._lastBlues = bluesList;
  window._lastMergeResult = {reds: redsList, blues: bluesList, n: tickets.length};
}

// ═══════════════════════════════════════════════════════════════

// ═══════════════════════════════════════════════════════════════
// 引擎按钮 (占位 — 后端模块开发中)
// ═══════════════════════════════════════════════════════════════

// ═══════════════════════════════════════════════════════════════
// 高级引擎按钮 — 4个独立出号策略
// ═══════════════════════════════════════════════════════════════

window.ensembleDraw = async function(){
  var stage = document.getElementById('stage');
  var btn = document.getElementById('ensembleBtn');
  var n = parseInt(document.getElementById('drawCount')?.value || 3);
  if(btn) btn.disabled = true;
  stage.innerHTML = '<div style="text-align:center;padding:20px;color:#A78BFA;">🧠 智能覆盖 — 组合覆盖设计 + 贪心多样化...</div>';
  var ac = new AbortController();
  var timer = setTimeout(function(){ ac.abort(); }, 15000);
  try {
    var r = await fetch('/api/ensemble/draw?n=' + n, {signal: ac.signal});
    clearTimeout(timer);
    var d = await r.json();
    if(!d.ok){ stage.innerHTML = '<div style="color:#EF4444;text-align:center;padding:20px;">' + (d.msg||'失败') + '</div>'; if(btn) btn.disabled = false; return; }
    var infoHtml = '<div style="font-size:10px;text-align:center;padding:6px;margin-bottom:8px;border-radius:6px;background:rgba(124,58,237,0.1);color:#A78BFA;">';
    infoHtml += '<b>🧠 ' + (d.algorithm||'智能覆盖') + '</b>';
    if(d.coverage_pct) infoHtml += ' · 覆盖率' + d.coverage_pct + '%';
    infoHtml += ' · 成本¥' + (d.cost_rmb||0);
    infoHtml += '</div>';
    stage.innerHTML = infoHtml;
    renderTickets(stage, d);
    var saveBtn = document.getElementById('saveBtn');
    if(saveBtn) saveBtn.disabled = false;
  } catch(e){ clearTimeout(timer); stage.innerHTML = '<div style="color:#EF4444;text-align:center;padding:20px;">' + (e.name==='AbortError'?'引擎超时 (15s)':'引擎请求失败') + '</div>'; }
  if(btn) btn.disabled = false;
};

window.biasDraw = async function(){
  var stage = document.getElementById('stage');
  var btn = document.getElementById('biasBtn');
  var n = parseInt(document.getElementById('drawCount')?.value || 3);
  if(btn) btn.disabled = true;
  stage.innerHTML = '<div style="text-align:center;padding:20px;color:#F97316;">🎯 偏差增强 — Dirichlet后验 + Thompson采样 + Gumbel-Max...</div>';
  var ac = new AbortController();
  var timer = setTimeout(function(){ ac.abort(); }, 15000);
  try {
    var r = await fetch('/api/bias/draw?n=' + n, {signal: ac.signal});
    var d = await r.json();
    if(!d.ok){ stage.innerHTML = '<div style="color:#EF4444;text-align:center;padding:20px;">' + (d.msg||'失败') + '</div>'; if(btn) btn.disabled = false; return; }
    var infoHtml = '<div style="font-size:10px;text-align:center;padding:6px;margin-bottom:8px;border-radius:6px;background:rgba(220,38,38,0.1);color:#F97316;">';
    infoHtml += '<b>🎯 ' + (d.algorithm||'偏差增强') + '</b>';
    if(d.coverage_pct) infoHtml += ' · 覆盖率' + d.coverage_pct + '%';
    infoHtml += ' · 成本¥' + (d.cost_rmb||0);
    // 偏差分数 (top 5)
    if(d.bias_scores){
      var scores = d.bias_scores;
      var keys = Object.keys(scores).slice(0,5);
      infoHtml += '<br><span style="font-size:9px;">热号: ' + keys.map(function(k){return k+'('+scores[k].toFixed(3)+')';}).join(' ') + '</span>';
    }
    infoHtml += '</div>';
    stage.innerHTML = infoHtml;
    renderTickets(stage, d);
    window._lastMergeResult = {reds: (d.tickets||[]).map(function(t){return t.reds;}), blues: (d.tickets||[]).map(function(t){return t.blue;}), n: d.tickets.length};
    var saveBtn = document.getElementById('saveBtn');
    if(saveBtn) saveBtn.disabled = false;
  } catch(e){ clearTimeout(timer); stage.innerHTML = '<div style="color:#EF4444;text-align:center;padding:20px;">' + (e.name==='AbortError'?'引擎超时 (15s)':'引擎请求失败') + '</div>'; }
  if(btn) btn.disabled = false;
};

window.blDraw = async function(){
  var stage = document.getElementById('stage');
  var btn = document.getElementById('blBtn');
  var n = parseInt(document.getElementById('drawCount')?.value || 3);
  if(btn) btn.disabled = true;
  stage.innerHTML = '<div style="text-align:center;padding:20px;color:#22D3EE;">⚖️ B-L融合 — 多方法观点贝叶斯融合...</div>';
  var ac = new AbortController();
  var timer = setTimeout(function(){ ac.abort(); }, 15000);
  try {
    var r = await fetch('/api/bl/draw?n=' + n, {signal: ac.signal});
    var d = await r.json();
    if(!d.ok){ stage.innerHTML = '<div style="color:#EF4444;text-align:center;padding:20px;">' + (d.msg||'失败') + '</div>'; if(btn) btn.disabled = false; return; }
    var infoHtml = '<div style="font-size:10px;text-align:center;padding:6px;margin-bottom:8px;border-radius:6px;background:rgba(8,145,178,0.1);color:#22D3EE;">';
    infoHtml += '<b>⚖️ ' + (d.algorithm||'B-L融合') + '</b>';
    if(d.coverage_pct) infoHtml += ' · 覆盖率' + d.coverage_pct + '%';
    infoHtml += ' · 成本¥' + (d.cost_rmb||0);
    // 方法权重
    if(d.method_weights){
      var mw = d.method_weights;
      var mk = Object.keys(mw).slice(0,3);
      infoHtml += '<br><span style="font-size:9px;">置信度: ' + mk.map(function(k){return k+':'+mw[k].toFixed(3);}).join(' ') + '</span>';
    }
    infoHtml += '</div>';
    stage.innerHTML = infoHtml;
    renderTickets(stage, d);
    window._lastMergeResult = {reds: (d.tickets||[]).map(function(t){return t.reds;}), blues: (d.tickets||[]).map(function(t){return t.blue;}), n: d.tickets.length};
    var saveBtn = document.getElementById('saveBtn');
    if(saveBtn) saveBtn.disabled = false;
  } catch(e){ clearTimeout(timer); stage.innerHTML = '<div style="color:#EF4444;text-align:center;padding:20px;">' + (e.name==='AbortError'?'引擎超时 (15s)':'引擎请求失败') + '</div>'; }
  if(btn) btn.disabled = false;
};

window.posDraw = async function(){
  var stage = document.getElementById('stage');
  var btn = document.getElementById('posBtn');
  var n = parseInt(document.getElementById('drawCount')?.value || 3);
  if(btn) btn.disabled = true;
  stage.innerHTML = '<div style="text-align:center;padding:20px;color:#A3E635;">📐 分位策略 — 每位置独立最优方法...</div>';
  var ac = new AbortController();
  var timer = setTimeout(function(){ ac.abort(); }, 15000);
  try {
    var r = await fetch('/api/position/draw?n=' + n, {signal: ac.signal});
    var d = await r.json();
    if(!d.ok){ stage.innerHTML = '<div style="color:#EF4444;text-align:center;padding:20px;">' + (d.msg||'失败') + '</div>'; if(btn) btn.disabled = false; return; }
    var infoHtml = '<div style="font-size:10px;text-align:center;padding:6px;margin-bottom:8px;border-radius:6px;background:rgba(101,163,13,0.1);color:#A3E635;">';
    infoHtml += '<b>📐 ' + (d.algorithm||'分位策略') + '</b>';
    infoHtml += ' · 成本¥' + (d.cost_rmb||0);
    // 每位置方法
    if(d.position_methods){
      var pm = d.position_methods;
      infoHtml += '<br><span style="font-size:9px;">';
      for(var p=1;p<=6;p++){
        var key = 'P'+p;
        if(pm[key]) infoHtml += key+':'+pm[key]+' ';
      }
      infoHtml += '</span>';
    }
    infoHtml += '</div>';
    stage.innerHTML = infoHtml;
    renderTickets(stage, d);
    window._lastMergeResult = {reds: (d.tickets||[]).map(function(t){return t.reds;}), blues: (d.tickets||[]).map(function(t){return t.blue;}), n: d.tickets.length};
    var saveBtn = document.getElementById('saveBtn');
    if(saveBtn) saveBtn.disabled = false;
  } catch(e){ clearTimeout(timer); stage.innerHTML = '<div style="color:#EF4444;text-align:center;padding:20px;">' + (e.name==='AbortError'?'引擎超时 (15s)':'引擎请求失败') + '</div>'; }
  if(btn) btn.disabled = false;
};

// 智能引擎 (5算法协同)
// ═══════════════════════════════════════════════════════════════

window.advancedDraw = async function(){
  var stage = document.getElementById('stage');
  var status = document.getElementById('mergeStatus');
  var btn = document.getElementById('advBtn');
  var n = parseInt(document.getElementById('drawCount')?.value || 3);

  if(btn) btn.disabled = true;
  stage.innerHTML = '<div style="text-align:center;padding:20px;color:#EC4899;">🧬 智能引擎 — 粒子滤波+熵值选号+Kelly注数</div>';
  if(status) status.innerHTML = '';

  var ac = new AbortController();
  var timer = setTimeout(function(){ ac.abort(); }, 15000);
  try {
    var r = await fetch('/api/advanced/generate?n=' + n, {signal: ac.signal});
    var d = await r.json();
    if(!d.ok){
      stage.innerHTML = '<div style="color:#EF4444;text-align:center;padding:20px;">' + (d.msg || '引擎启动失败') + '</div>';
      if(btn) btn.disabled = false;
      return;
    }
    var infoHtml = '<div style="font-size:10px;margin-bottom:8px;text-align:center;padding:6px 10px;border-radius:6px;background:rgba(236,72,153,0.1);color:#F472B6;line-height:1.6;">';
    infoHtml += '<b>🧬 ' + (d.algorithm || '智能引擎') + '</b> · 成本¥' + (d.cost_rmb||0);
    infoHtml += '</div>';
    stage.innerHTML = infoHtml;
    renderTickets(stage, d);
    var saveBtn = document.getElementById('saveBtn');
    if(saveBtn) saveBtn.disabled = false;
  } catch(e) {
    clearTimeout(timer);
    stage.innerHTML = '<div style="color:#EF4444;text-align:center;padding:20px;">' + (e.name==='AbortError'?'引擎超时 (15s)':'引擎请求失败') + '</div>';
  }
  if(btn) btn.disabled = false;
};
