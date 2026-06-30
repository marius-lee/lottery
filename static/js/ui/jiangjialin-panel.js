/** 蒋加林算法面板 — 排列型思维 (2010)
 *
 *  位间隔过滤 (Ch4): 与对照期同位置差值分布过滤
 *  位跨度过滤 (Ch5): 相邻位差值分布过滤
 *  位形态过滤 (Ch6): 单双/高低/除3 三套并行
 *  超级缩水 (Ch7): 中6保5
 *  蓝球方法 (Ch9): 除3归类+斜边码+同尾码
 */
window._showJiangJiaLinPanel = function(){
  var el = document.getElementById('jiangjialinContent');
  if(!el) return;
  var h = '<div class="weier-container">';
  h += '<h5 style="color:#A78BFA;font-size:16px;margin:0 0 8px 0;">📐 蒋加林·排列型思维 [2010]</h5>';
  h += '<div style="font-size:16px;color:#64748B;margin-bottom:8px;">将33选6按6个位置逐一分析 · 位间隔→位跨度→位形态 多级过滤</div>';

  h += '<div style="display:flex;gap:8px;margin-bottom:8px;flex-wrap:wrap;">';
  h += '<label style="font-size:14px;color:#E2E8F0;cursor:pointer;display:flex;align-items:center;gap:3px;">';
  h += '<input type="checkbox" id="jjGap" checked><span>位间隔过滤</span></label>';
  h += '<label style="font-size:14px;color:#E2E8F0;cursor:pointer;display:flex;align-items:center;gap:3px;">';
  h += '<input type="checkbox" id="jjSpan" checked><span>位跨度过滤</span></label>';
  h += '<label style="font-size:14px;color:#E2E8F0;cursor:pointer;display:flex;align-items:center;gap:3px;">';
  h += '<input type="checkbox" id="jjPattern" checked><span>位形态过滤</span></label>';
  h += '<label style="font-size:14px;color:#E2E8F0;cursor:pointer;display:flex;align-items:center;gap:3px;">';
  h += '<input type="checkbox" id="jjShrink" checked><span>超级缩水</span></label>';
  h += '</div>';

  h += '<div style="display:flex;align-items:center;gap:8px;">';
  h += '<span style="font-size:14px;color:#FFFFFF;">蓝球:</span>';
  h += '<select id="jjBlueMode" style="font-size:14px;padding:4px 8px;border-radius:4px;background:#1E1E36;color:#E2E8F0;border:1px solid rgba(255,255,255,0.1);">';
  h += '<option value="mod3">除3余数归类</option>';
  h += '<option value="diagonal">斜边码</option>';
  h += '<option value="sametail">同尾码</option>';
  h += '<option value="random">随机</option>';
  h += '</select>';
  h += '<button class="btn btn-draw" onclick="window._jjDraw()" style="font-size:15px;padding:6px 16px;margin-left:auto;">蒋加林出号</button>';
  h += '</div>';

  h += '<div id="jjResult" style="margin-top:10px;"></div>';
  h += '</div>';
  el.innerHTML = h;
};

window._jjDraw = async function(){
  var el = document.getElementById('jjResult');
  if(!el) return;
  el.innerHTML = '<div style="color:#FBBF24;padding:8px;">排列型思维分析中...</div>';

  var n = window.store?.drawCount || 3;
  var gap = document.getElementById('jjGap')?.checked ? 1 : 0;
  var span = document.getElementById('jjSpan')?.checked ? 1 : 0;
  var pattern = document.getElementById('jjPattern')?.checked ? 1 : 0;
  var shrink = document.getElementById('jjShrink')?.checked ? 1 : 0;
  var blue = document.getElementById('jjBlueMode')?.value || 'mod3';

  try {
    var r = await fetch('/api/jiangjialin/tickets?n='+n+'&gap='+gap+'&span='+span+'&pattern='+pattern+'&shrink='+shrink+'&blue='+blue);
    var data = await r.json();
  } catch(e){
    el.innerHTML = '<div style="color:#EF4444;padding:8px;">出号失败</div>';
    return;
  }
  if(!data || !data.ok){
    el.innerHTML = '<div style="color:#EF4444;padding:8px;">'+(data?.msg||'')+'</div>';
    return;
  }

  var h = '<div style="font-size:16px;color:#FFFFFF;margin-bottom:4px;">候选池: '+data.candidate_count+' → 过滤后: '+data.after_filter+'</div>';
  h += '<div style="display:flex;gap:10px;flex-wrap:wrap;">';
  (data.tickets||[]).forEach(function(t){
    var reds = t.reds.map(function(x){return String(x).padStart(2,'0')}).join(' ');
    h += '<div style="padding:10px 14px;border-radius:8px;background:rgba(168,85,247,0.08);text-align:center;">';
    h += '<div style="font-size:16px;font-weight:700;color:#EF4444;letter-spacing:2px;">'+reds+'</div>';
    h += '<div style="font-size:16px;font-weight:700;color:#3B82F6;margin-top:2px;">'+String(t.blue||'?').padStart(2,'0')+'</div>';
    h += '</div>';
  });
  h += '</div>';
  el.innerHTML = h;
};
