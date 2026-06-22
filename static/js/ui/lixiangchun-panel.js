/** 李相春面板 — 趋势分析+散度/偏度/三浪 (2003)

 *  选号理论: 趋势分析是制胜武器 (第3章, 11种短期+4中期+6长期)
 *  独特算法: 散度(集中度)/偏度(偏移度)/DHR(重复率)/三浪(冷热反转)
 *  组号: 旋转矩阵 = 覆盖设计 (系统已有)
 */
window._showLiXiangChunPanel = function(){
  var el = document.getElementById('lixiangchunContent');
  if(!el) return;

  var h = '<div class="weier-container">';
  h += '<h5 style="color:#34D399;font-size:13px;margin:0 0 4px 0;">📊 李相春·趋势分析 [2003]</h5>';
  h += '<div style="font-size:10px;color:#64748B;margin-bottom:10px;">散度(集中度)+偏度(偏移度)+AC值(复杂度)+三浪(冷热反转) · 小额投注方法论</div>';

  // 三浪信号摘要区
  h += '<div id="lxSanlangSummary" style="margin-bottom:10px;padding:8px;border-radius:6px;background:rgba(255,255,255,0.03);font-size:11px;">';
  h += '<span style="color:#64748B;">三浪信号加载中...</span>';
  h += '</div>';

  // 生成按钮
  h += '<div style="display:flex;align-items:center;gap:8px;">';
  h += '<span style="font-size:10px;color:#94A3B8;">散度3-10 · 偏度2-12 · AC≥6 · 避开升三浪</span>';
  h += '<button class="btn btn-draw" onclick="window._lxDraw()" style="font-size:12px;padding:6px 20px;margin-left:auto;">李相春出号</button>';
  h += '</div>';

  h += '<div id="lxResult" style="margin-top:10px;"></div>';
  h += '</div>';
  el.innerHTML = h;

  // 异步加载三浪信号
  window._lxLoadSanlang();
};

window._lxLoadSanlang = async function(){
  var el = document.getElementById('lxSanlangSummary');
  if(!el) return;
  try {
    var r = await fetch('/api/lixiangchun/sanlang');
    var d = await r.json();
    var h = '';
    if(d.jiang && d.jiang.length > 0){
      h += '<div style="margin-bottom:4px;">';
      h += '<span style="color:#34D399;">▼ 降三浪 (即将活跃): </span>';
      d.jiang.forEach(function(n){
        h += '<span style="display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:50%;background:#059669;color:#fff;font-weight:700;font-size:11px;margin:0 2px;">'+n+'</span>';
      });
      h += '</div>';
    } else {
      h += '<div style="color:#64748B;margin-bottom:4px;">▼ 降三浪: 暂无信号</div>';
    }
    if(d.sheng && d.sheng.length > 0){
      h += '<div>';
      h += '<span style="color:#EF4444;">▲ 升三浪 (建议避开): </span>';
      d.sheng.forEach(function(n){
        h += '<span style="display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:50%;background:#DC2626;color:#fff;font-weight:700;font-size:11px;margin:0 2px;">'+n+'</span>';
      });
      h += '</div>';
    } else {
      h += '<div style="color:#64748B;">▲ 升三浪: 暂无信号</div>';
    }
    el.innerHTML = h;
  } catch(e){
    el.innerHTML = '<span style="color:#EF4444;">三浪加载失败</span>';
  }
};

window._lxDraw = async function(){
  var el = document.getElementById('lxResult');
  if(!el) return;
  el.innerHTML = '<div style="color:#FBBF24;padding:8px;">趋势分析中...</div>';

  var n = (window.store && window.store.drawCount) || 3;

  try {
    var r = await fetch('/api/lixiangchun/generate?n='+n);
    var data = await r.json();
  } catch(e){
    el.innerHTML = '<div style="color:#EF4444;padding:8px;">出号失败</div>';
    return;
  }
  if(!data || !data.ok){
    el.innerHTML = '<div style="color:#EF4444;padding:8px;">'+(data.msg||'生成失败')+'</div>';
    return;
  }

  var stats = data.stats || {};
  var h = '<div style="font-size:10px;color:#94A3B8;margin-bottom:4px;">';
  h += '候选池: '+stats.candidate_pool_size+'号';
  if(stats.avoid_sheng && stats.avoid_sheng.length) h += ' | 避开升三浪: '+stats.avoid_sheng.join(',');
  if(stats.prefer_jiang && stats.prefer_jiang.length) h += ' | 优先降三浪: '+stats.prefer_jiang.join(',');
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
