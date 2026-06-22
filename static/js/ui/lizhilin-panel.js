/** 李志林算法面板 (各方法独立勾选, 与原书一致) */
window._showLiZhiLinPanel = function(){
  var el = document.getElementById('lizhilinContent');
  if(!el) return;
  el.innerHTML = '<div style="color:#94A3B8;padding:8px;">加载中...</div>';

  fetch('/api/lizhilin/tickets?n=0&dan8=1&dan3=1&trans=1&kill=1&btail=1&bten=0&bperiod=0').then(function(r){return r.json()}).then(function(d){
    render(d);
  }).catch(function(){
    el.innerHTML = '<div style="color:#EF4444;padding:16px;">加载失败</div>';
  });

  function render(d){
    var h = '<div class="weier-container">';

    // ═══ 红球方法 ═══
    h += '<div style="margin-bottom:8px;">';
    h += '<span style="font-size:12px;color:#94A3B8;font-weight:600;">红球方法:</span>';
    h += '<label style="margin-left:8px;font-size:11px;color:#E2E8F0;cursor:pointer;">';
    h += '<input type="checkbox" id="lzlDan8" checked onchange="window._lzlUpdate()">八招定胆</label>';
    h += '<label style="margin-left:6px;font-size:11px;color:#E2E8F0;cursor:pointer;">';
    h += '<input type="checkbox" id="lzlDan3" checked onchange="window._lzlUpdate()">定胆3招</label>';
    h += '<label style="margin-left:6px;font-size:11px;color:#E2E8F0;cursor:pointer;">';
    h += '<input type="checkbox" id="lzlTrans" checked onchange="window._lzlUpdate()">带出表</label>';
    h += '<label style="margin-left:6px;font-size:11px;color:#E2E8F0;cursor:pointer;">';
    h += '<input type="checkbox" id="lzlKill" checked onchange="window._lzlUpdate()">27杀号</label>';
    h += '</div>';

    // ═══ 蓝球方法 ═══
    h += '<div style="margin-bottom:10px;">';
    h += '<span style="font-size:12px;color:#94A3B8;font-weight:600;">蓝球方法:</span>';
    h += '<label style="margin-left:8px;font-size:11px;color:#E2E8F0;cursor:pointer;">';
    h += '<input type="checkbox" id="lzlBtail" checked onchange="window._lzlUpdate()">12种尾数杀号</label>';
    h += '<label style="margin-left:6px;font-size:11px;color:#E2E8F0;cursor:pointer;">';
    h += '<input type="checkbox" id="lzlBten" onchange="window._lzlUpdate()">十招杀蓝</label>';
    h += '<label style="margin-left:6px;font-size:11px;color:#E2E8F0;cursor:pointer;">';
    h += '<input type="checkbox" id="lzlBperiod" onchange="window._lzlUpdate()">期号排除</label>';
    h += '</div>';

    h += '<div style="display:flex;gap:8px;margin-bottom:12px;align-items:center;">';
    h += '<button class="btn btn-draw" id="lzlDrawBtn" onclick="window._lzlDraw()" style="font-size:12px;padding:6px 16px;">李志林出号</button>';
    h += '<span id="lzlStatus" style="font-size:11px;color:#94A3B8;"></span>';
    h += '</div>';

    h += '<div id="lzlResult"></div>';

    // 候选明细
    if(d && d.ok){
      if(d.dan_pool && d.dan_pool.length){
        h += '<details style="margin-bottom:6px;"><summary style="color:#A78BFA;font-size:11px;cursor:pointer;">🎯 定胆候选: '+d.dan_pool.length+'个</summary>';
        h += '<div style="font-size:10px;color:#A78BFA;margin-top:4px;">'+d.dan_pool.map(function(n){return String(n).padStart(2,'0')}).join(' ')+'</div></details>';
      }
      if(d.trans_pool && d.trans_pool.length){
        h += '<details style="margin-bottom:6px;"><summary style="color:#F59E0B;font-size:11px;cursor:pointer;">🔗 带出表候选: '+d.trans_pool.length+'个</summary>';
        h += '<div style="font-size:10px;color:#F59E0B;margin-top:4px;">'+d.trans_pool.map(function(n){return String(n).padStart(2,'0')}).join(' ')+'</div></details>';
      }
      if(d.kill_excluded && d.kill_excluded.length){
        h += '<details style="margin-bottom:6px;"><summary style="color:#EF4444;font-size:11px;cursor:pointer;">🗑 27杀号排除: '+d.kill_excluded.length+'个</summary>';
        h += '<div style="font-size:10px;color:#EF4444;margin-top:4px;">'+d.kill_excluded.map(function(n){return String(n).padStart(2,'0')}).join(' ')+'</div></details>';
      }
      if(d.red_pool){
        h += '<div style="margin-bottom:8px;font-size:10px;color:#10B981;">📐 红球候选池: '+d.red_pool_size+'个</div>';
      }

      // 蓝球方法明细
      if(d.blue_methods){
        var bms = d.blue_methods;
        if(bms.tail12 && bms.tail12.survived !== undefined){
          h += '<details style="margin-bottom:6px;"><summary style="color:#3B82F6;font-size:11px;cursor:pointer;">🔵 12种尾数杀号: '+bms.tail12.survived.length+'蓝</summary>';
          h += '<div style="font-size:10px;color:#3B82F6;margin-top:4px;">'+bms.tail12.survived.map(function(n){return String(n).padStart(2,'0')}).join(' ')+'</div></details>';
        }
        if(bms.ten_kill && bms.ten_kill.survived !== undefined){
          h += '<details style="margin-bottom:6px;"><summary style="color:#06B6D4;font-size:11px;cursor:pointer;">🟦 十招杀蓝: '+bms.ten_kill.survived.length+'蓝</summary>';
          h += '<div style="font-size:10px;color:#06B6D4;margin-top:4px;">'+bms.ten_kill.survived.map(function(n){return String(n).padStart(2,'0')}).join(' ')+'</div></details>';
        }
        if(bms.period && bms.period.survived !== undefined){
          h += '<details style="margin-bottom:6px;"><summary style="color:#0EA5E9;font-size:11px;cursor:pointer;">🔹 期号排除: '+bms.period.survived.length+'蓝</summary>';
          h += '<div style="font-size:10px;color:#0EA5E9;margin-top:4px;">'+bms.period.survived.map(function(n){return String(n).padStart(2,'0')}).join(' ')+'</div></details>';
        }
      }
    }

    h += '<div style="font-size:9px;color:#64748B;padding:6px;background:rgba(255,255,255,0.03);border-radius:6px;">';
    h += '📊 李志林《彩票赢家·双色球选号技巧》山西科学技术出版社 2012 | 各方法独立, 蓝球取勾选方法的交集';
    h += '</div>';
    h += '</div>';
    el.innerHTML = h;
  }
};

window._lzlUpdate = function(){
  // 仅用于视觉反馈, 实际参数在出号时读取
};

window._lzlDraw = function(){
  var st = document.getElementById('lzlStatus');
  var re = document.getElementById('lzlResult');
  if(st) st.textContent = '出号中...';

  var n = 3;
  var sel = document.getElementById('drawCount');
  if(sel) n = parseInt(sel.value) || 3;

  function checked(id){ var e=document.getElementById(id); return e&&e.checked ? 1 : 0; }
  var params = '?n='+n;
  params += '&dan8='+checked('lzlDan8');
  params += '&dan3='+checked('lzlDan3');
  params += '&trans='+checked('lzlTrans');
  params += '&kill='+checked('lzlKill');
  params += '&btail='+checked('lzlBtail');
  params += '&bten='+checked('lzlBten');
  params += '&bperiod='+checked('lzlBperiod');

  fetch('/api/lizhilin/tickets'+params).then(function(r){return r.json()}).then(function(d){
    if(!d || !d.ok){ if(st) st.textContent = d&&d.msg||'失败'; return; }
    if(st) st.textContent = d.tickets.length+'注 · ¥'+(d.tickets.length*2);

    var rh = '<div style="margin-top:12px;">';
    rh += '<div style="font-size:10px;color:#94A3B8;margin-bottom:8px;">'+d.algorithm+' | 红池'+d.red_pool_size+'号 | 蓝池'+d.blue_candidates.length+'号</div>';
    rh += '<table class="bt-table"><thead><tr><th>#</th><th>红球</th><th>蓝球</th></tr></thead><tbody>';
    d.tickets.forEach(function(t,i){
      rh += '<tr><td>'+(i+1)+'</td><td style="color:#cc4444;">'+(t.reds||[]).join(' ')+'</td><td style="color:#3366cc;">'+String(t.blue||'?').padStart(2,'0')+'</td></tr>';
    });
    rh += '</tbody></table></div>';
    if(re) re.innerHTML = rh;
  }).catch(function(e){
    if(st) st.textContent = '请求失败: '+e;
  });
};
