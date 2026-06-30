/** 杨情友仪表盘 — 决战双色球 (2014)

 *  五行编码: 水1,6/火2,7/木3,8/金4,9/土5,0
 *  位置字头排除: 第一位不取20-29, 第三位不取30-33, 第六位不取01-09
 *  减码100%: 17条硬规则
 */
window._showYangPanel = function(){
  var el = document.getElementById('yangContent');
  if(!el) return;

  var h = '<div class="weier-container">';
  h += '<h5 style="color:#F59E0B;font-size:16px;margin:0 0 2px 0;">🎯 杨情友 决战双色球 [2014]</h5>';
  h += '<div style="font-size:16px;color:#64748B;margin-bottom:10px;">五行编码+位置字头排除+17条减码规则 · 独创方法论</div>';
  h += '<div id="yangSignal" style="font-size:14px;"><span style="color:#64748B;">加载中...</span></div>';
  h += '</div>';
  el.innerHTML = h;
  window._yangLoad();
};

window._yangLoad = async function(){
  var el = document.getElementById('yangSignal');
  if(!el) return;
  try {
    var r = await fetch('/api/data');
    var d = await r.json();
  } catch(e){ el.innerHTML = '<span style="color:#EF4444;">加载失败</span>'; return; }

  if(!d || !d.data || !d.data.length){ el.innerHTML = '无数据'; return; }
  var latest = d.data[d.data.length-1];
  var reds = latest.slice(1,7);
  var blue = latest[7];

  // ── 五行分布 ──
  var wxMap = {'水':[1,6],'火':[2,7],'木':[3,8],'金':[4,9],'土':[5,0]};
  var wxCount = {'水':0,'火':0,'木':0,'金':0,'土':0};
  var wxNums = {'水':[],'火':[],'木':[],'金':[],'土':[]};
  reds.forEach(function(n){
    var t = n % 10;
    for(var k in wxMap){
      if(wxMap[k].indexOf(t) >= 0){ wxCount[k]++; wxNums[k].push(n); break; }
    }
  });
  // 蓝球五行
  var bt = blue % 10;
  var blueWx = '';
  for(var k in wxMap){ if(wxMap[k].indexOf(bt) >= 0){ blueWx = k; break; } }

  var h = '';
  h += '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;">';
  h += '<div style="padding:6px 10px;border-radius:4px;background:rgba(255,255,255,0.03);font-size:16px;min-width:200px;">';
  h += '<div style="color:#F59E0B;font-weight:600;margin-bottom:3px;">🔮 上期五行分布 ('+latest[0]+')</div>';
  var order = ['木','火','土','金','水'];
  var chain = [];
  order.forEach(function(k){
    if(wxCount[k] > 0){
      h += '<span style="color:#E2E8F0;">'+k+':'+wxCount[k]+'个</span> ';
      wxNums[k].forEach(function(n){ h += '<span style="color:#FFFFFF;">'+n+'</span> '; });
      chain.push(k);
    }
  });
  // 五行生克提示
  h += '<br><span style="color:#64748B;">相生: 水→木→火→土→金→水</span>';
  if(chain.length >= 2){
    var sheng = [];
    for(var i=0; i<chain.length-1; i++){
      var idx = order.indexOf(chain[i]);
      if(idx >= 0 && order[(idx+1)%5] === chain[i+1]) sheng.push(chain[i]+'→'+chain[i+1]);
    }
    if(sheng.length > 0) h += '<br><span style="color:#34D399;">✓ 相生链: '+sheng.join(', ')+'</span>';
  }
  h += '</div>';

  // 位置字头检查
  var s = reds.slice().sort(function(a,b){return a-b;});
  var posWarn = [];
  if(s[0] >= 20 && s[0] <= 29) posWarn.push('①2字头('+s[0]+')异常');
  if(s[2] >= 30) posWarn.push('③3字头('+s[2]+')异常');
  if(s[5] <= 9) posWarn.push('⑥0字头('+s[5]+')异常');

  h += '<div style="padding:6px 10px;border-radius:4px;background:rgba(255,255,255,0.03);font-size:16px;">';
  h += '<div style="color:#F59E0B;font-weight:600;margin-bottom:3px;">📍 位置字头</div>';
  h += '<span style="color:#E2E8F0;">①'+s[0]+'</span> ';
  h += '<span style="color:#E2E8F0;">②'+s[1]+'</span> ';
  h += '<span style="color:#E2E8F0;">③'+s[2]+'</span> ';
  h += '<span style="color:#E2E8F0;">④'+s[3]+'</span> ';
  h += '<span style="color:#E2E8F0;">⑤'+s[4]+'</span> ';
  h += '<span style="color:#E2E8F0;">⑥'+s[5]+'</span>';
  if(posWarn.length > 0){
    h += '<br><span style="color:#EF4444;">⚠ '+posWarn.join(', ')+'</span>';
  } else {
    h += '<br><span style="color:#34D399;">✓ 位置字头正常</span>';
  }
  h += '<br><span style="color:#64748B;">规则: ①不取20-29 | ③不取30-33 | ⑥不取01-09</span>';
  h += '</div>';
  h += '</div>';

  // 过滤+出号
  h += '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;align-items:center;">';
  h += '<span style="font-size:16px;color:#FFFFFF;">过滤:</span>';
  h += '<label style="font-size:16px;color:#E2E8F0;cursor:pointer;display:flex;align-items:center;gap:2px;"><input type="checkbox" id="yangPosDigit" checked><span>📍位置字头排除</span></label>';
  h += '<button class="btn btn-draw" onclick="window._yangDraw()" style="font-size:14px;padding:5px 16px;margin-left:auto;">杨情友综合出号</button>';
  h += '</div>';
  h += '<div id="yangResult" style="margin-top:10px;"></div>';

  h += '<div style="font-size:15px;color:#475569;margin-top:6px;">';
  h += '五行编码+位置字头排除+17条减码规则 · 杨情友 2014';
  h += '</div>';
  el.innerHTML = h;
};

window._yangDraw = async function(){
  var el = document.getElementById('yangResult');
  if(!el) return;
  el.innerHTML = '<div style="color:#FBBF24;padding:8px;">出号中...</div>';
  var n = (window.store && window.store.drawCount) || 3;
  var params = ['n='+n];
  if(document.getElementById('yangPosDigit')?.checked) params.push('position_digit_filter=1');

  var ctrl = new AbortController();
  var t = setTimeout(function(){ ctrl.abort(); }, 30000);
  try {
    var r = await fetch('/api/micro/tickets?'+params.join('&'), {signal:ctrl.signal});
    clearTimeout(t);
    var data = await r.json();
  } catch(e){ clearTimeout(t); el.innerHTML = '<div style="color:#EF4444;">'+(e.name==='AbortError'?'超时':'失败')+'</div>'; return; }
  if(!data||!data.ok){ el.innerHTML = '<div style="color:#EF4444;">'+(data.msg||'失败')+'</div>'; return; }

  var h = '<div style="font-size:16px;color:#FFFFFF;margin-bottom:4px;">'+data.algorithm+'</div>';
  h += '<div style="display:flex;gap:10px;flex-wrap:wrap;">';
  (data.tickets||[]).forEach(function(tk){
    var rs = tk.reds.map(function(x){return String(x).padStart(2,'0')}).join(' ');
    h += '<div style="padding:10px 14px;border-radius:8px;background:rgba(245,158,11,0.08);text-align:center;min-width:160px;">';
    h += '<div style="font-size:15px;font-weight:700;color:#EF4444;letter-spacing:2px;">'+rs+'</div>';
    h += '<div style="font-size:15px;font-weight:700;color:#3B82F6;margin-top:2px;">'+String(tk.blue||'?').padStart(2,'0')+'</div>';
    h += '</div>';
  });
  h += '</div>';
  el.innerHTML = h;
};
