/** 吴明算法面板 — 4本书统一入口
 *
 *  蓝球大法(~2006): 背离率+大小极值+4区间+除4余数
 *  核心秘密(2006): 5期重号+9期冷号+6区间排除
 *  揭秘双色球(2010): 追/杀框架+倍投+顺时针+循环振荡
 *  细节战法(2006): 位置战法+重号战法+蓝球三大公理
 */
window._showWuMingPanel = function(){
  var el = document.getElementById('wumingContent');
  if(!el) return;
  el.innerHTML = '<div style="color:#FFFFFF;padding:8px;">加载中...</div>';

  // 并行加载所有数据
  Promise.all([
    fetch('/api/wuming/period5').then(r=>r.json()),
    fetch('/api/wuming/cold9').then(r=>r.json()),
    fetch('/api/wuming/zone6').then(r=>r.json()),
    fetch('/api/wuming/repeats').then(r=>r.json()),
  ]).then(function(results){
    render(results[0], results[1], results[2], results[3]);
  }).catch(function(){
    el.innerHTML = '<div style="color:#EF4444;padding:16px;">数据加载失败</div>';
  });

  function render(p5, c9, z6, rp){
    var h = '<div class="weier-container">';
    h += '<h5 style="color:#3B82F6;font-size:16px;margin:0 0 6px 0;">📖 吴明·四书集成</h5>';

    // ═══ 红球区域 ═══
    h += '<div style="margin-bottom:8px;padding:6px 10px;border-radius:6px;background:rgba(239,68,68,0.04);">';
    h += '<span style="font-size:14px;color:#EF4444;font-weight:600;">🔴 红球方法</span>';
    h += '<div style="font-size:16px;color:#FFFFFF;margin-top:4px;line-height:1.6;">';

    if(p5 && p5.ok){
      h += '<span style="display:inline-block;margin:2px;padding:2px 6px;border-radius:3px;background:rgba(59,130,246,0.08);">5期热号池: <b>'+p5.pool_size+'个</b> '+p5.direction+' '+p5.recommend+'</span> ';
    }
    if(c9 && c9.ok){
      h += '<span style="display:inline-block;margin:2px;padding:2px 6px;border-radius:3px;background:rgba(59,130,246,0.08);">9期冷号: <b>'+c9.count+'个</b> [前3: '+(c9.cold_numbers||[]).slice(0,3).map(function(c){return c.number}).join(',')+'] 63%转化率</span> ';
    }
    if(z6 && z6.ok){
      h += '<span style="display:inline-block;margin:2px;padding:2px 6px;border-radius:3px;background:rgba(59,130,246,0.08);">6区间排除: 空区'+JSON.stringify(z6.empty_zones)+' 杀<b>'+z6.killed_count+'个</b></span> ';
    }
    if(rp && rp.ok){
      h += '<span style="display:inline-block;margin:2px;padding:2px 6px;border-radius:3px;background:rgba(59,130,246,0.08);">重号: <b>'+rp.repeat_count+'个</b> 建议'+rp.recommend+' 极值'+rp.extreme+'</span> ';
    }
    h += '</div></div>';

    // ═══ 蓝球区域 ═══
    h += '<div style="margin-bottom:8px;padding:6px 10px;border-radius:6px;background:rgba(59,130,246,0.04);">';
    h += '<span style="font-size:14px;color:#3B82F6;font-weight:600;">🔵 蓝球方法</span>';
    h += '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:6px;">';
    h += '<label style="font-size:14px;color:#E2E8F0;cursor:pointer;display:flex;align-items:center;gap:3px;"><input type="checkbox" id="wumDeviation" checked><span>背离率(蓝球大法)</span></label>';
    h += '<label style="font-size:14px;color:#E2E8F0;cursor:pointer;display:flex;align-items:center;gap:3px;"><input type="checkbox" id="wumClockwise"><span>顺时针(揭秘)</span></label>';
    h += '<label style="font-size:14px;color:#E2E8F0;cursor:pointer;display:flex;align-items:center;gap:3px;"><input type="checkbox" id="wumBSD"><span>大小单双尾(揭秘)</span></label>';
    h += '</div></div>';

    // ═══ 出号 ═══
    h += '<div style="display:flex;align-items:center;gap:8px;">';
    h += '<span style="font-size:14px;color:#FFFFFF;">红球:</span>';
    h += '<label style="font-size:16px;color:#E2E8F0;cursor:pointer;"><input type="checkbox" id="wumRedMethods" checked> 5期热号+9冷号+6区间</label>';
    h += '<button class="btn btn-draw" onclick="window._wumingDraw()" style="font-size:15px;padding:6px 16px;margin-left:auto;">吴明出号</button>';
    h += '</div>';

    h += '<div id="wumingResult" style="margin-top:10px;"></div>';
    h += '</div>';
    el.innerHTML = h;
  };
};

window._wumingDraw = async function(){
  var el = document.getElementById('wumingResult');
  if(!el) return;
  el.innerHTML = '<div style="color:#FBBF24;padding:8px;">吴明综合出号中...</div>';

  var n = window.store?.drawCount || 3;
  // 收集蓝球参数
  var bParams = [];
  if(document.getElementById('wumDeviation')?.checked) bParams.push('wuming_blue=1');
  if(document.getElementById('wumClockwise')?.checked) bParams.push('wuming_clockwise=1');
  if(document.getElementById('wumBSD')?.checked) bParams.push('wuming_bsd=1');

  // 红球通过策略面板的现有checkbox
  var redParams = ['n='+n];
  if(document.getElementById('wumRedMethods')?.checked) redParams.push('color_filter=1');

  try {
    // 先取红球
    var rr = await fetch('/api/red/pick?' + redParams.join('&'));
    var reds = await rr.json();
    // 再取蓝球
    var br = await fetch('/api/blue/pick?' + (bParams.length ? bParams.join('&') : ''));
    var blues = await br.json();

    if(!reds.ok){
      el.innerHTML = '<div style="color:#EF4444;padding:8px;">'+ (reds.msg||'红球生成失败') + '</div>';
      return;
    }

    var redTickets = reds.reds || [];
    var blueCandidates = blues.candidates || blues.candidates===undefined ? (blues.candidates||[]) : [];
    // 如果无策略, 随机选n个蓝球
    if(bParams.length === 0){
      var pool = Array.from({length:16}, (_,i)=>i+1);
      for(var i=0; i<Math.min(n,16); i++){
        var idx = Math.floor(Math.random() * pool.length);
        blueCandidates.push(pool.splice(idx,1)[0]);
      }
    }

    var h = '<div style="font-size:16px;color:#FFFFFF;margin-bottom:4px;">红球池: '+reds.pool_valid_reds+'注 | 蓝球候选: '+blueCandidates.length+'个</div>';
    h += '<div style="display:flex;gap:10px;flex-wrap:wrap;">';
    for(var i=0; i<Math.min(redTickets.length, n); i++){
      var blue = blueCandidates[i % blueCandidates.length] || '?';
      h += '<div style="padding:10px 14px;border-radius:8px;background:rgba(59,130,246,0.06);text-align:center;">';
      h += '<div style="font-size:16px;font-weight:700;color:#EF4444;letter-spacing:2px;">' + redTickets[i].map(function(x){return String(x).padStart(2,'0')}).join(' ') + '</div>';
      h += '<div style="font-size:16px;font-weight:700;color:#3B82F6;margin-top:2px;">'+String(blue).padStart(2,'0')+'</div>';
      h += '</div>';
    }
    h += '</div>';
    el.innerHTML = h;
  } catch(e){
    el.innerHTML = '<div style="color:#EF4444;padding:8px;">出号失败</div>';
  }
};
