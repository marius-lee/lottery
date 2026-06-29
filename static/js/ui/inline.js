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



// ═══════════════════════════════════════════════════════════════
// 已归档红球过滤策略 — 来自彩票书籍 (2003-2010)
// ═══════════════════════════════════════════════════════════════

var _filterInfo = {
  color: {
    title: '三色分解 (吴长坤 2010)',
    desc: '33红球按波色分红(12个)/蓝(10个)/绿(11个)三类，要求6红含全部三色。<br>'
        + '原书声称95%可过，近500期实测<B style="color:#EF4444;">81.4%</b>——意味着<B style="color:#EF4444;">排除18.6%可能中奖组合</b>。<br>'
        + '<B style="color:#FBBF24;">无效原因:</b> 无统计依据证明下一期必然三色俱全。是典型的事后拟合书规则。'
  },
  block9: {
    title: '方块9杀号 (吴长坤 2010 Ch6§1)',
    desc: '33红球行列图上13个3×3方块，上期空方块本期继续杀。<br>'
        + '原书声称80%有空方块，实测<B style="color:#EF4444;">68%</b>——即<B style="color:#EF4444;">32%的概率误杀</b>。<br>'
        + '<B style="color:#FBBF24;">无效原因:</b> 空方块不持续的概率为32%。每次勾选，有1/3概率主动排除有效号码。'
  },
  pengchan: {
    title: '彭浩通道 (彭浩 2010 Ch5§3)',
    desc: '6个红球位置各自限制在MA9+MA18双通道范围内。<br>'
        + 'MA(移动平均)本身是滞后指标——通道基于过去，开奖是未来。<br>'
        + '<B style="color:#FBBF24;">无效原因:</b> MA通道不能预测下一期号码落在哪里。纯technical analysis迁移到彩票的误用。'
  },
  spread: {
    title: '跨度过滤 (李相春 2003 p55-57)',
    desc: '红球跨度指数spread=(max-min)/(33-6)×10，排除&lt;3或&gt;10。<br>'
        + '<B style="color:#FBBF24;">无效原因:</b> 跨度指数是描述性统计，无预测力。2003年书籍公式，未经过统计检验。'
  },
  ac: {
    title: 'AC值过滤 (李相春 2003 / 刘大军 2010)',
    desc: '算术复杂性Arithmetic Complexity，排除AC值&lt;4或&gt;10。<br>'
        + '<B style="color:#FBBF24;">无效原因:</b> AC值是组合的数学性质，但无法用于预测。所有组合AC值均匀分布在4-10区间内，过滤无意义。'
  },
  omission: {
    title: '遗漏比过滤 (彩天使 2009 p90)',
    desc: '排除遗漏比&gt;5的极寒号码组合。<br>'
        + '<B style="color:#FBBF24;">无效原因:</b> 排除冷号=赌徒谬误的反面。号码独立，上期未出不意味本期不会出。排除冷号降低覆盖。'
  },

  "liuBlue": {
    title: '刘大军 五期断蓝 (2011)',
    desc: '近5期蓝球均值±4作为选号范围，范围外排除。<br>'
        + '<b style="color:#FBBF24;">无效原因:</b> 均值是描述性统计，没有预测力。任何落在均值±4外的蓝球都是"不该出"的——但事实上它们确实会出。'
  },
  "wumingBlue": {
    title: '吴明 蓝球分析 (2006)',
    desc: '背离率(遗漏/16>400%→关注)、大小极值(连出5期→反转)、4区间极值(连出3期→反转)、除4余数极值。<br>'
        + '<b style="color:#FBBF24;">无效原因:</b> 极值反转=赌徒谬误。号码独立，上一期出了不等于下一期不会出。'
  },
  "wumingClockwise": {
    title: '吴明 顺时针法 (2010)',
    desc: '16蓝球按4个顺时针区域排列(1-12-11-10等)，上期蓝球所在区域排除。<br>'
        + '<b style="color:#FBBF24;">无效原因:</b> 顺时针排列是人工构造的空间布局，与号码出现概率无关。纯主观分类。'
  },
  "wumingBSD": {
    title: '吴明 大小单双尾 (2010)',
    desc: '16蓝球按大/小 × 单/双 × 尾数 交叉分类为4组，上期所在组排除。<br>'
        + '<b style="color:#FBBF24;">无效原因:</b> 分类方案是主观设计的。任何4组×4个的划分都会产生"37.5%排除率"的错觉。'
  },
  "caileleBlue": {
    title: '彩乐乐 蓝球 (2017)',
    desc: '奇偶形态(max连续6/5期)、大小形态(max连续5/4期)、尾数驱码(查表排除)。<br>'
        + '<b style="color:#FBBF24;">无效原因:</b> 连续检测+"查表"是最典型的彩票书籍模式——任意规则，无统计基础。'
  },
  "gongyiBlue": {
    title: '公益时报 蓝球 (2010)',
    desc: '期次转换法(双重012路码型→排除) + 代码对称法(除5余数对称→回补)。<br>'
        + '<b style="color:#FBBF24;">无效原因:</b> 012路/除5余数是纯数学变换。任何变换都不会改变号码独立同分布的性质。'
  },
  "xiaBlue": {
    title: '夏氏 加减法 (2013)',
    desc: '|蓝_{t-1} - 蓝_t| ± 4 = 预测范围。声称90%准确率。<br>'
        + '<b style="color:#FBBF24;">无效原因:</b> ±4范围覆盖8-9个号码(=50-56%池)，"准确率"不过是大概率事件的同义反复。任何方法声称>50%都是池子大而已。'
  },
  gap: {
    title: '间距过滤 (李相春 2004 p114-119)',
    desc: '最大间距5-17 + 平均间距4-7约束。<br>'
        + '<B style="color:#FBBF24;">无效原因:</b> 间距是纯描述性统计，落入任何区间的概率均匀。排除边缘区间只降低覆盖度。'
  }
};

window.switchTraditionalFilter = function(filter){
  // Deactivate all tab buttons
  var tabBtns = document.querySelectorAll('#traditionalPanel .tab-btn');
  tabBtns.forEach(function(b){ b.classList.remove('active'); });
  if(event && event.target) event.target.classList.add('active');
  
  var info = _filterInfo[filter];
  var infoPanel = document.getElementById('filterInfoPanel');
  var content = document.getElementById('traditionalContent');
  var store = document.getElementById('authorPanelStore');
  
  if(!info || !infoPanel || !content) return;
  
  // Hide author panels
  ['weier','zhang','lizhilin','peng','jiangjialin','wuming','lixiangchun','liudajun','zeng'].forEach(function(a){
    var panel = document.getElementById(a + 'Panel');
    if(panel) panel.classList.remove('show');
  });
  
  // Hide all author panels
  ['weier','zhang','lizhilin','peng','jiangjialin','wuming','lixiangchun','liudajun','zeng'].forEach(function(a){
    var panel = document.getElementById(a + 'Panel');
    if(panel) panel.classList.remove('show');
  });
  
  // Move any author panel back to storage
  var currentPanel = content.querySelector('.content-panel');
  if(currentPanel && store){
    currentPanel.classList.remove('show');
    store.appendChild(currentPanel);
  }
  
  infoPanel.style.display = 'block';
  infoPanel.innerHTML = '<b style="color:#FBBF24;">' + info.title + '</b><br><br>' + info.desc
    + '<br><br><span style="font-size:10px;color:#64748B;">此策略已从主界面移除。'
    + '来自彩票书籍的启发性规则，未经统计检验，'
    + '无一能通过OOS(样本外)验证产生超越随机的预测优势。</span>';
};


window.switchTraditionalPanel = function(panelName){
  // Deactivate all tab buttons
  var tabBtns = document.querySelectorAll('#traditionalPanel .tab-btn');
  tabBtns.forEach(function(b){ b.classList.remove('active'); });
  if(event && event.target) event.target.classList.add('active');
  
  var content = document.getElementById('traditionalContent');
  var filterInfo = document.getElementById('filterInfoPanel');
  var store = document.getElementById('authorPanelStore');
  if(!content) return;
  
  // Hide filter info
  if(filterInfo) filterInfo.style.display = 'none';
  
  // Move any currently displayed panel back to storage
  var currentPanel = content.querySelector('.content-panel');
  if(currentPanel && store){
    currentPanel.classList.remove('show');
    store.appendChild(currentPanel);
  }
  
  // Get the requested panel
  var targetPanel = document.getElementById(panelName + 'Panel');
  if(!targetPanel) return;
  
  // Store original parent if not already stored
  if(!targetPanel._originalParent){
    targetPanel._originalParent = targetPanel.parentElement;
  }
  
  // Show panel and move into traditionalContent
  targetPanel.classList.add('show');
  targetPanel.dispatchEvent(new CustomEvent('panel-shown'));
  content.appendChild(targetPanel);
};

window.switchTraditionalTab = function(author, btn){
  // Deactivate all tab buttons in traditional panel
  var tabBtns = document.querySelectorAll('#traditionalPanel .tab-btn');
  tabBtns.forEach(function(b){ b.classList.remove('active'); });
  if(btn) btn.classList.add('active');
  
  var targetContent = document.getElementById('traditionalContent');
  var store = document.getElementById('authorPanelStore');
  if(!targetContent || !store) return;
  
  // Move currently displayed panel back to storage
  var currentPanel = targetContent.querySelector('.content-panel');
  if(currentPanel){
    currentPanel.classList.remove('show');
    store.appendChild(currentPanel);
  }
  
  // Move selected panel from wherever it is to traditionalContent
  var targetPanel = document.getElementById(author + 'Panel');
  if(!targetPanel) return;
  
  targetPanel.classList.add('show');
  // If panel is not already in targetContent, move it there
  if(targetPanel.parentElement !== targetContent){
    targetContent.appendChild(targetPanel);
  }
  
  // Call the author handler to load panel content
  if(_authorHandlers[author]) _authorHandlers[author]();
  // Dispatch panel-shown
  targetPanel.dispatchEvent(new CustomEvent('panel-shown'));
  window.store.currentAuthor = author;
};

window.switchAuthor = function(author){
  // [已迁移] 传统方法面板统一收纳入「传统方法」tab
  // 此函数保留向后兼容，委托给 switchTraditionalTab
  if(!author) return;
  window.switchTraditionalTab(author);
  // 确保传统方法面板可见
  var tradPanel = document.getElementById('traditionalPanel');
  if(tradPanel && !tradPanel.classList.contains('show')){
    document.getElementById('traditionalToggle').click();
  }
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
    var infoHtml = '<div style="font-size:10px;text-align:center;padding:6px;margin-bottom:8px;border-radius:6px;background:rgba(124,58,237,0.1);color:#A78BFA;line-height:1.5;">';
    infoHtml += '<b>🧠 ' + (d.algorithm||'聚合覆盖') + '</b>';
    infoHtml += ' · 成本¥' + (d.cost_rmb||0);
    if(d.covering && d.covering.v){
      infoHtml += '<br><span style="font-size:9px;">红池' + d.covering.v + '→' + d.covering.hot_numbers.length + '号 | ';
      infoHtml += 't=' + d.covering.t + '覆盖' + (d.covering.estimated_coverage_pct||0).toFixed(0) + '%</span>';
    }
    infoHtml += '</div>';
    stage.innerHTML = infoHtml;
    renderTickets(stage, d);
    var saveBtn = document.getElementById('saveBtn');
    if(saveBtn) saveBtn.disabled = false;
  } catch(e){ clearTimeout(timer); stage.innerHTML = '<div style="color:#EF4444;text-align:center;padding:20px;">' + (e.name==='AbortError'?'超时 (15s)':'请求失败') + '</div>'; }
  if(btn) btn.disabled = false;
};

// [已归档] 偏差增强 — Thompson采样无预测优势
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
    infoHtml += '<b>🎯 ' + (d.algorithm||'偏差采样') + '</b>';
    if(d.coverage_pct) infoHtml += ' · 覆盖率' + d.coverage_pct + '%';
    infoHtml += ' · 成本¥' + (d.cost_rmb||0);
    // 偏差分数 (top 5)
    if(d.bias_scores){
      var scores = d.bias_scores;
      var keys = Object.keys(scores).slice(0,5);
      infoHtml += '<br><span style="font-size:9px;">采样权重: ' + keys.map(function(k){return k+'('+scores[k].toFixed(3)+')';}).join(' ') + '</span>';
    }
    infoHtml += '</div>';
    stage.innerHTML = infoHtml;
    renderTickets(stage, d);
    window._lastMergeResult = {reds: (d.tickets||[]).map(function(t){return t.reds;}), blues: (d.tickets||[]).map(function(t){return t.blue;}), n: d.tickets.length};
    var saveBtn = document.getElementById('saveBtn');
    if(saveBtn) saveBtn.disabled = false;
  } catch(e){ clearTimeout(timer); stage.innerHTML = '<div style="color:#EF4444;text-align:center;padding:20px;">' + (e.name==='AbortError'?'超时 (15s)':'请求失败') + '</div>'; }
  if(btn) btn.disabled = false;
};

// B-L融合 — 多方法评分+FDR校正+覆盖设计
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
    infoHtml += '<b>⚖️ ' + (d.algorithm||'B-L加权') + '</b>';
    if(d.coverage_pct) infoHtml += ' · 覆盖率' + d.coverage_pct + '%';
    infoHtml += ' · 成本¥' + (d.cost_rmb||0);
    // FDR显著方法
    if(d.fdr_significant !== undefined){
      infoHtml += '<br><span style="font-size:9px;">FDR显著: ' + d.fdr_significant + '个方法</span>';
    }
    // 方法权重
    if(d.method_weights){
      var mw = d.method_weights;
      var mk = Object.keys(mw).slice(0,3);
      infoHtml += '<br><span style="font-size:9px;">权重: ' + mk.map(function(k){return k+':'+mw[k].toFixed(3);}).join(' ') + '</span>';
    }
    infoHtml += '</div>';
    stage.innerHTML = infoHtml;
    renderTickets(stage, d);
    window._lastMergeResult = {reds: (d.tickets||[]).map(function(t){return t.reds;}), blues: (d.tickets||[]).map(function(t){return t.blue;}), n: d.tickets.length};
    var saveBtn = document.getElementById('saveBtn');
    if(saveBtn) saveBtn.disabled = false;
  } catch(e){ clearTimeout(timer); stage.innerHTML = '<div style="color:#EF4444;text-align:center;padding:20px;">' + (e.name==='AbortError'?'超时 (15s)':'请求失败') + '</div>'; }
  if(btn) btn.disabled = false;
};

// 分位策略 — 6位置独立最优方法+覆盖组合
window.positionDraw = async function(){
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
    infoHtml += '<b>📐 ' + (d.algorithm||'分位采样') + '</b>';
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
  } catch(e){ clearTimeout(timer); stage.innerHTML = '<div style="color:#EF4444;text-align:center;padding:20px;">' + (e.name==='AbortError'?'超时 (15s)':'请求失败') + '</div>'; }
  if(btn) btn.disabled = false;
};

// 智能引擎 (5算法协同)
// ═══════════════════════════════════════════════════════════════


;
