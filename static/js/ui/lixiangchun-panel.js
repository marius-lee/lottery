/** 李相春统一仪表盘 — 三书聚合 (2003+2004+2009)

 *  2003《彩票小额投注必读》: 散度/偏度/AC值/DHR/三浪/双底
 *  2004《手把手教你玩彩票》: 间距分析 + SSQ校准
 *  2009《新编绝算双色球》: 遗漏比趋势分析

 *  过滤条件归属李相春Tab, 不从红球区借用.
 */
window._showLiXiangChunPanel = function(){
  var el = document.getElementById('lixiangchunContent');
  if(!el) return;

  var h = '<div class="weier-container">';
  h += '<h5 style="color:#34D399;font-size:16px;margin:0 0 2px 0;">📊 李相春趋势分析 [2003-2009]</h5>';
  h += '<div style="font-size:16px;color:#FFFFFF;margin-bottom:10px;">三书聚合: 散度+偏度+AC+间距+遗漏比+三浪+DHR+双底</div>';

  // 信号区 (异步加载)
  h += '<div id="lxDashboard" style="font-size:14px;">';
  h += '<span style="color:#FFFFFF;">信号加载中...</span>';
  h += '</div>';

  // 过滤开关
  h += '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;align-items:center;">';
  h += '<span style="font-size:16px;color:#FFFFFF;">过滤:</span>';
  h += '<label style="font-size:16px;color:#E2E8F0;cursor:pointer;display:flex;align-items:center;gap:2px;"><input type="checkbox" id="lxSpread" checked><span>📏散度</span></label>';
  h += '<label style="font-size:16px;color:#E2E8F0;cursor:pointer;display:flex;align-items:center;gap:2px;"><input type="checkbox" id="lxAC" checked><span>🔢AC值</span></label>';
  h += '<label style="font-size:16px;color:#E2E8F0;cursor:pointer;display:flex;align-items:center;gap:2px;"><input type="checkbox" id="lxGap"><span>↔️间距</span></label>';
  h += '<label style="font-size:16px;color:#E2E8F0;cursor:pointer;display:flex;align-items:center;gap:2px;"><input type="checkbox" id="lxOmission"><span>📉遗漏比</span></label>';
  h += '<button class="btn btn-draw" onclick="window._lxIntegratedDraw()" style="font-size:14px;padding:5px 16px;margin-left:auto;">综合出号</button>';
  h += '</div>';

  h += '<div id="lxResult" style="margin-top:10px;"></div>';
  h += '</div>';
  el.innerHTML = h;

  window._lxLoadDashboard();
};

window._lxLoadDashboard = async function(){
  var el = document.getElementById('lxDashboard');
  if(!el) return;
  try {
    var r = await fetch('/api/lixiangchun/dashboard');
    var d = await r.json();
  } catch(e){
    el.innerHTML = '<span style="color:#EF4444;">信号加载失败</span>';
    return;
  }

  var h = '';

  // ── 三浪信号 ──
  var sl = d.sanlang || {};
  h += '<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:8px;">';

  h += '<div style="flex:1;min-width:140px;padding:8px;border-radius:6px;background:rgba(5,150,105,0.08);">';
  h += '<div style="color:#34D399;font-weight:600;margin-bottom:4px;">▼ 降三浪 · 即将活跃</div>';
  if(sl.jiang && sl.jiang.length > 0){
    sl.jiang.forEach(function(n){
      h += '<span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;background:#059669;color:#fff;font-weight:700;font-size:15px;margin:1px;">'+n+'</span>';
    });
  } else { h += '<span style="color:#FFFFFF;">暂无</span>'; }
  h += '</div>';

  h += '<div style="flex:1;min-width:140px;padding:8px;border-radius:6px;background:rgba(220,38,38,0.06);">';
  h += '<div style="color:#EF4444;font-weight:600;margin-bottom:4px;">▲ 升三浪 · 建议避开</div>';
  if(sl.sheng && sl.sheng.length > 0){
    sl.sheng.forEach(function(n){
      h += '<span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;background:#DC2626;color:#fff;font-weight:700;font-size:15px;margin:1px;opacity:0.7;">'+n+'</span>';
    });
  } else { h += '<span style="color:#FFFFFF;">暂无</span>'; }
  h += '</div>';

  h += '<div style="flex:1;min-width:120px;padding:8px;border-radius:6px;background:rgba(251,191,36,0.06);">';
  h += '<div style="color:#FBBF24;font-weight:600;margin-bottom:4px;">🔻 活跃期结束</div>';
  if(sl.hot_end && sl.hot_end.length > 0){
    sl.hot_end.forEach(function(n){
      h += '<span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;background:#B45309;color:#fff;font-weight:700;font-size:15px;margin:1px;">'+n+'</span>';
    });
  } else { h += '<span style="color:#FFFFFF;">暂无</span>'; }
  h += '</div>';
  h += '</div>';

  // ── 散度/偏度 + DHR + 双底 ──
  h += '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:6px;">';

  var st = d.spread_trend || {};
  var sk = d.skewness_trend || {};
  h += '<div style="padding:6px 10px;border-radius:4px;background:rgba(255,255,255,0.03);font-size:16px;">';
  h += '<span style="color:#FFFFFF;">📏 散度: </span>';
  h += '<span style="color:'+(st.zone==='normal'?'#34D399':'#FBBF24')+';font-weight:600;">'+st.current+'</span>';
  h += '<span style="color:#FFFFFF;"> (正常'+st.normal_range+')</span>';
  h += '<br><span style="color:#FFFFFF;">📐 偏度: </span>';
  h += '<span style="color:'+(sk.zone==='normal'?'#34D399':'#FBBF24')+';font-weight:600;">'+sk.current+'</span>';
  h += '<span style="color:#FFFFFF;"> (正常'+sk.normal_range+')</span>';
  if(sk.bound) h += '<span style="color:#475569;"> 上限='+sk.bound+'</span>';
  h += '</div>';

  h += '<div style="padding:6px 10px;border-radius:4px;background:rgba(255,255,255,0.03);font-size:16px;">';
  h += '<span style="color:#FFFFFF;">📌 粘滞号 (DHR低→易重复):</span><br>';
  if(d.dhr_sticky && d.dhr_sticky.length > 0){
    d.dhr_sticky.forEach(function(x){
      h += '<span style="display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;background:rgba(59,130,246,0.2);color:#60A5FA;font-weight:600;font-size:16px;margin:1px;" title="DHR='+x.dhr+'">'+x.num+'</span>';
    });
  } else { h += '<span style="color:#FFFFFF;">-</span>'; }
  h += '<br><span style="color:#FFFFFF;">📉 孤立号 (DHR高→勿追):</span><br>';
  if(d.dhr_avoid && d.dhr_avoid.length > 0){
    d.dhr_avoid.forEach(function(x){
      h += '<span style="display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;background:rgba(239,68,68,0.1);color:#F87171;font-weight:600;font-size:16px;margin:1px;" title="DHR='+x.dhr+'">'+x.num+'</span>';
    });
  } else { h += '<span style="color:#FFFFFF;">-</span>'; }
  h += '</div>';

  h += '<div style="padding:6px 10px;border-radius:4px;background:rgba(255,255,255,0.03);font-size:16px;">';
  h += '<span style="color:#FFFFFF;">⏱ 双底/三底预测:</span><br>';
  if(d.shuangdi && d.shuangdi.length > 0){
    d.shuangdi.forEach(function(x){
      h += '<span style="color:#A78BFA;">'+x.num+'</span><span style="color:#FFFFFF;">→约'+x.predicted_gap+'期后</span> ';
    });
  } else { h += '<span style="color:#FFFFFF;">暂无</span>'; }
  h += '</div>';
  h += '</div>';

  // ── 遗漏比摘要 ──
  var ratios = d.omission_ratios || {};
  var extreme = [];
  for(var k in ratios){ if(ratios[k] > 5) extreme.push(k); }
  h += '<div style="font-size:16px;color:#FFFFFF;">';
  h += '📉 遗漏比: ';
  if(extreme.length > 0){
    h += '<span style="color:#EF4444;">极寒带(OR>5): '+extreme.join(', ')+'</span>';
  } else {
    h += '<span style="color:#34D399;">无极端冷号</span>';
  }
  h += '</div>';

  el.innerHTML = h;
};

window._lxIntegratedDraw = async function(){
  var el = document.getElementById('lxResult');
  if(!el) return;
  el.innerHTML = '<div style="color:#FBBF24;padding:8px;">综合出号中...</div>';

  var n = (window.store && window.store.drawCount) || 3;
  // 读取Tab内李相春专属过滤开关
  var params = ['n=' + n];
  if(document.getElementById('lxSpread')?.checked) params.push('spread_filter=1');
  if(document.getElementById('lxAC')?.checked) params.push('ac_filter=1');
  if(document.getElementById('lxGap')?.checked) params.push('gap_filter=1');
  if(document.getElementById('lxOmission')?.checked) params.push('omission_filter=1');

  var controller = new AbortController();
  var timeout = setTimeout(function(){ controller.abort(); }, 30000);

  try {
    var r = await fetch('/api/micro/tickets?' + params.join('&'), {signal: controller.signal});
    clearTimeout(timeout);
    var data = await r.json();
  } catch(e){
    clearTimeout(timeout);
    el.innerHTML = '<div style="color:#EF4444;padding:8px;">' + (e.name === 'AbortError' ? '请求超时' : '出号失败') + '</div>';
    return;
  }
  if(!data || !data.ok){
    el.innerHTML = '<div style="color:#EF4444;padding:8px;">'+(data.msg||'生成失败')+'</div>';
    return;
  }

  var h = '<div style="font-size:16px;color:#FFFFFF;margin-bottom:4px;">';
  h += '算法: '+data.algorithm+' · 池: '+(data.pool_valid_reds||'随机').toLocaleString()+'注';
  h += '</div>';

  h += '<div style="display:flex;gap:10px;flex-wrap:wrap;">';
  (data.tickets||[]).forEach(function(t){
    var reds = t.reds.map(function(x){return String(x).padStart(2,'0')}).join(' ');
    h += '<div style="padding:10px 14px;border-radius:8px;background:rgba(52,211,153,0.08);text-align:center;min-width:160px;">';
    h += '<div style="font-size:15px;font-weight:700;color:#EF4444;letter-spacing:2px;">'+reds+'</div>';
    h += '<div style="font-size:15px;font-weight:700;color:#3B82F6;margin-top:2px;">'+String(t.blue||'?').padStart(2,'0')+'</div>';
    h += '</div>';
  });
  h += '</div>';
  el.innerHTML = h;
};
