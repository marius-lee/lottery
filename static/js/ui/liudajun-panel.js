/** 刘大军仪表盘 — 三书聚合 (2010+2011+2014)

 *  2010《双色球擒号绝技》: 定尾选号法, 重合码 {1,3,6,8}
 *  2011《双色球蓝球中奖绝技》: 三效应, 冷热判定, 五期断蓝
 *  2014《双色球终极战法》: 断区转换法
 */
window._showLiuDaJunPanel = function(){
  var el = document.getElementById('liudajunContent');
  if(!el) return;

  var h = '<div class="weier-container">';
  h += '<h5 style="color:#FBBF24;font-size:16px;margin:0 0 2px 0;">📊 刘大军 趋势分析 [2010-2014]</h5>';
  h += '<div style="font-size:16px;color:#FFFFFF;margin-bottom:10px;">定尾选号+重合码{1,3,6,8}+三效应连锁+五期断蓝+断区转换</div>';

  // 定尾信号区
  h += '<div id="ljdSignal" style="font-size:14px;">';
  h += '<span style="color:#FFFFFF;">定尾信号加载中...</span>';
  h += '</div>';

  // 过滤 + 出号
  h += '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;align-items:center;">';
  h += '<span style="font-size:16px;color:#FFFFFF;">过滤:</span>';
  h += '<label style="font-size:16px;color:#E2E8F0;cursor:pointer;display:flex;align-items:center;gap:2px;"><input type="checkbox" id="ljdCoincidence"><span>🔗重合码</span></label>';
  h += '<button class="btn btn-draw" onclick="window._ljdDraw()" style="font-size:14px;padding:5px 16px;margin-left:auto;">刘大军综合出号</button>';
  h += '</div>';

  h += '<div id="ljdResult" style="margin-top:10px;"></div>';
  h += '</div>';
  el.innerHTML = h;

  window._ljdLoadSignals();
};

window._ljdLoadSignals = async function(){
  var el = document.getElementById('ljdSignal');
  if(!el) return;
  try {
    var r = await fetch('/api/liudajun/position-tails?window=50');
    var d = await r.json();
  } catch(e){
    el.innerHTML = '<span style="color:#EF4444;">信号加载失败</span>';
    return;
  }

  var h = '';

  // ── 重合码状态 ──
  if(d.coincidence_status){
    var cs = d.coincidence_status;
    h += '<div style="padding:6px 8px;border-radius:4px;background:rgba(255,255,255,0.03);margin-bottom:6px;">';
    h += '<span style="color:#FFFFFF;">上期尾数: </span>';
    h += '<span style="color:#E2E8F0;">'+cs.tails.join(' ')+'</span>';
    h += '<span style="color:#FFFFFF;"> | 重合码{1,3,6,8}: </span>';
    if(cs.has_coincidence){
      h += '<span style="color:#34D399;">✓ '+cs.matched.join(' ')+'</span>';
    } else {
      h += '<span style="color:#EF4444;">✗ 缺失！下期大概率回补</span>';
    }
    h += '</div>';
  }

  // ── 每位置推荐尾数 ──
  h += '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:4px;margin-bottom:4px;">';
  (d.positions||[]).forEach(function(p){
    var rec = p.coincidence.length > 0 ? p.coincidence : p.recommended.slice(0,3);
    h += '<div style="padding:4px 6px;border-radius:3px;background:rgba(255,255,255,0.03);">';
    h += '<div style="color:#FFFFFF;font-size:15px;">'+p.name+'</div>';
    rec.forEach(function(t){
      var isCoin = [1,3,6,8].indexOf(t) >= 0;
      h += '<span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;font-weight:700;font-size:16px;margin:1px;'+(isCoin?'background:rgba(251,191,36,0.2);color:#FBBF24;':'background:rgba(148,163,184,0.1);color:#FFFFFF;')+'">'+t+'</span>';
    });
    h += '</div>';
  });
  h += '</div>';

  // ── 尾数热度 ──
  h += '<div style="font-size:15px;color:#475569;">';
  h += '热度: <span style="color:#34D399;">热</span>=高频 <span style="color:#FBBF24;">温</span>=中频 <span style="color:#FFFFFF;">冷</span>=低频 ';
  h += '| 黄色数字=重合码{1,3,6,8}';
  h += '</div>';

  el.innerHTML = h;
};

window._ljdDraw = async function(){
  var el = document.getElementById('ljdResult');
  if(!el) return;
  el.innerHTML = '<div style="color:#FBBF24;padding:8px;">综合出号中...</div>';

  var n = (window.store && window.store.drawCount) || 3;
  var params = ['n=' + n];
  if(document.getElementById('ljdCoincidence')?.checked) params.push('coincidence_filter=1');

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

  var h = '<div style="font-size:16px;color:#FFFFFF;margin-bottom:4px;">算法: '+data.algorithm+'</div>';
  h += '<div style="display:flex;gap:10px;flex-wrap:wrap;">';
  (data.tickets||[]).forEach(function(t){
    var reds = t.reds.map(function(x){return String(x).padStart(2,'0')}).join(' ');
    h += '<div style="padding:10px 14px;border-radius:8px;background:rgba(251,191,36,0.08);text-align:center;min-width:160px;">';
    h += '<div style="font-size:15px;font-weight:700;color:#EF4444;letter-spacing:2px;">'+reds+'</div>';
    h += '<div style="font-size:15px;font-weight:700;color:#3B82F6;margin-top:2px;">'+String(t.blue||'?').padStart(2,'0')+'</div>';
    h += '</div>';
  });
  h += '</div>';
  el.innerHTML = h;
};
