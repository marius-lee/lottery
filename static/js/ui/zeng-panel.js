/** 曾献忠仪表盘 — 曾氏模块理论 (2014)

 *  衡值轮盘: 33为圆心, 4圈×4线环状结构
 *  内部运动: 四大定律 (标准值/正常值/边缘值/极端值)
 *  外部运动: 三大遗传定律 + V/O追踪系统
 *  邻距+质号连续: 补充分析维度
 */
window._showZengPanel = function(){
  var el = document.getElementById('zengContent');
  if(!el) return;

  var h = '<div class="weier-container">';
  h += '<h5 style="color:#A78BFA;font-size:16px;margin:0 0 2px 0;">🎯 曾献忠 曾氏模块 [2014]</h5>';
  h += '<div style="font-size:16px;color:#64748B;margin-bottom:10px;">数学建模方法论 · 内外双层追踪 · 衡值轮盘+四大定律+V/O系统</div>';
  h += '<div id="zengSignal" style="font-size:14px;"><span style="color:#64748B;">加载中...</span></div>';
  h += '</div>';
  el.innerHTML = h;
  window._zengLoad();
};

window._zengLoad = async function(){
  var el = document.getElementById('zengSignal');
  if(!el) return;
  try {
    var r = await fetch('/api/zeng/dashboard');
    var d = await r.json();
  } catch(e){ el.innerHTML = '<span style="color:#EF4444;">加载失败</span>'; return; }

  var h = '';

  // ── 衡值轮盘 + 邻距/质号 ──
  var wh = d.wheel || {};
  h += '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;">';
  h += '<div style="padding:6px 10px;border-radius:4px;background:rgba(255,255,255,0.03);font-size:16px;min-width:160px;">';
  h += '<div style="color:#A78BFA;font-weight:600;margin-bottom:3px;">📐 衡值轮盘</div>';
  if(wh.lines){
    h += '<span style="color:#FFFFFF;">线:</span> ';
    for(var k in wh.lines) h += '<span style="color:#E2E8F0;">'+k+':'+wh.lines[k]+'</span> ';
    h += '<br><span style="color:#FFFFFF;">圈:</span> ';
    for(var k in wh.circles) h += '<span style="color:#E2E8F0;">'+k+':'+wh.circles[k]+'</span> ';
    if(wh.pairs && wh.pairs.length) {
      h += '<br><span style="color:#FBBF24;">互补对:</span> ';
      wh.pairs.forEach(function(p){ h += '<span style="color:#E2E8F0;">'+p[0]+'+'+p[1]+'=33</span> '; });
    }
    h += '<br><span style="color:'+(wh.zero_count>=7?'#EF4444':wh.zero_count>=3?'#FBBF24':'#34D399')+';">零项:'+wh.zero_count+'/8 '+(wh.zero_count>=7?'极端边缘':'')+'</span>';
  }
  h += '</div>';

  h += '<div style="padding:6px 10px;border-radius:4px;background:rgba(255,255,255,0.03);font-size:16px;">';
  h += '<span style="color:#A78BFA;">邻距:</span> <span style="color:#E2E8F0;">'+(d.linju||[]).join(' ')+'</span>';
  h += '<br><span style="color:#A78BFA;">质号连续:</span> <span style="color:#E2E8F0;">'+d.prime_run+'个</span>';
  h += '</div>';
  h += '</div>';

  // ── 模块A信息 ──
  var ma = d.module_a || {};
  h += '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;">';
  h += '<div style="padding:6px 10px;border-radius:4px;background:rgba(255,255,255,0.03);font-size:16px;">';
  h += '<div style="color:#A78BFA;font-weight:600;margin-bottom:2px;">📦 模块A (奇3大3)</div>';
  h += '<span style="color:#FFFFFF;">样本:'+ma.sample_size+'期</span> | 年均'+ma.avg_per_year+'次';
  if(ma.collections){
    var hh = ma.collections.hot || [];
    var cc = ma.collections.cold || [];
    h += '<br><span style="color:#34D399;">热:</span> ';
    hh.forEach(function(n){ h += '<span style="color:#34D399;margin:0 1px;">'+n+'</span>'; });
    h += '<br><span style="color:#EF4444;">冷:</span> ';
    (cc.slice(0,8)).forEach(function(n){ h += '<span style="color:#F87171;margin:0 1px;">'+n+'</span>'; });
  }
  h += '</div>';

  // 模块B
  var mb = d.module_b || {};
  h += '<div style="padding:6px 10px;border-radius:4px;background:rgba(255,255,255,0.03);font-size:16px;">';
  h += '<div style="color:#A78BFA;font-weight:600;margin-bottom:2px;">📦 模块B (奇3大3 区间2:2:2)</div>';
  h += '<span style="color:#FFFFFF;">样本:'+mb.sample_size+'期</span> | 年均'+mb.avg_per_year+'次';
  h += '</div>';
  h += '</div>';

  // ── 四大定律 ──
  var laws = d.laws_summary || {};
  if(Object.keys(laws).length > 0){
    h += '<div style="padding:6px 10px;border-radius:4px;background:rgba(255,255,255,0.03);font-size:16px;margin-bottom:8px;">';
    h += '<div style="color:#A78BFA;font-weight:600;margin-bottom:3px;">⚖ 内部运动 四大定律</div>';
    for(var k in laws){
      var l = laws[k];
      var color = l.zone === 'standard' ? '#34D399' : (l.zone === 'normal' ? '#FBBF24' : (l.zone === 'edge' ? '#F97316' : '#EF4444'));
      h += '<div style="margin-bottom:2px;"><span style="color:#FFFFFF;">'+k+':</span> ';
      h += '<span style="color:'+color+';">'+l.law+' → '+l.action+'</span></div>';
    }
    h += '</div>';
  }

  // ── 外部遗传 V/O系统 ──
  var ext = d.external_genetic || {};
  var items = ext.items || {};
  if(Object.keys(items).length > 0){
    h += '<div style="padding:6px 10px;border-radius:4px;background:rgba(255,255,255,0.03);font-size:16px;margin-bottom:6px;">';
    h += '<div style="color:#A78BFA;font-weight:600;margin-bottom:3px;">🔍 外部运动 V/O追踪</div>';
    h += '<span style="color:#34D399;">V(保留):'+ext.v_count+'</span> | <span style="color:#EF4444;">O(排除):'+ext.o_count+'</span>';
    for(var k in items){
      var it = items[k];
      var sc = it.status === 'V' ? '#34D399' : (it.status === '~' ? '#FBBF24' : '#EF4444');
      h += '<div><span style="color:#FFFFFF;">'+k+':</span> <span style="color:'+sc+';">'+it.status+'</span> ';
      h += '<span style="color:#64748B;">期:'+it.expected+' vs 实:'+it.actual+'</span></div>';
    }
    h += '</div>';
  }

  // 出号区
  h += '<div style="display:flex;align-items:center;gap:8px;margin-top:12px;">';
  h += '<span style="font-size:16px;color:#FFFFFF;">模块A(奇3大3) · 热号优先+衡值轮盘均衡+排除极端冷号</span>';
  h += '<button class="btn btn-draw" onclick="window._zengDraw()" style="font-size:14px;padding:5px 16px;margin-left:auto;">曾氏模块出号</button>';
  h += '</div>';
  h += '<div id="zengResult" style="margin-top:10px;"></div>';

  h += '<div style="font-size:15px;color:#475569;">曾氏模块理论: 内因+外因双层追踪 · 排除法预测 · 彩票=混沌数学运动</div>';
  el.innerHTML = h;
};

window._zengDraw = async function(){
  var el = document.getElementById('zengResult');
  if(!el) return;
  el.innerHTML = '<div style="color:#FBBF24;padding:8px;">模块分析中...</div>';

  var n = (window.store && window.store.drawCount) || 3;
  var ctrl = new AbortController();
  var t = setTimeout(function(){ ctrl.abort(); }, 30000);

  try {
    var r = await fetch('/api/zeng/generate?n='+n+'&odd=3&big=3', {signal: ctrl.signal});
    clearTimeout(t);
    var data = await r.json();
  } catch(e){
    clearTimeout(t);
    el.innerHTML = '<div style="color:#EF4444;">'+(e.name==='AbortError'?'超时':'出号失败')+'</div>';
    return;
  }
  if(!data||!data.ok){ el.innerHTML = '<div style="color:#EF4444;">'+(data.msg||'失败')+'</div>'; return; }

  var mi = data.module_info || {};
  var la = data.laws_applied || {};
  var h = '<div style="font-size:16px;color:#FFFFFF;margin-bottom:4px;">';
  h += data.algorithm+' · 样本'+mi.sample_size+'期 · 热号池'+mi.hot_count+'个';
  if(la.avoid_extreme_cold && la.avoid_extreme_cold.length) h += ' · 避开:'+la.avoid_extreme_cold.join(',');
  h += '</div>';
  h += '<div style="display:flex;gap:10px;flex-wrap:wrap;">';
  (data.tickets||[]).forEach(function(tk){
    var rs = tk.reds.map(function(x){return String(x).padStart(2,'0')}).join(' ');
    h += '<div style="padding:10px 14px;border-radius:8px;background:rgba(168,85,247,0.08);text-align:center;min-width:160px;">';
    h += '<div style="font-size:15px;font-weight:700;color:#EF4444;letter-spacing:2px;">'+rs+'</div>';
    h += '<div style="font-size:15px;font-weight:700;color:#3B82F6;margin-top:2px;">'+String(tk.blue||'?').padStart(2,'0')+'</div>';
    h += '</div>';
  });
  h += '</div>';
  el.innerHTML = h;
};
