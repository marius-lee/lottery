/** 彭浩算法面板 — 五均线号码通道 + 波动三要素 + 方向预测 (2010) */
window._showPengPanel = function(){
  var el = document.getElementById('pengContent');
  if(!el) return;
  PU.showLoading(el);

  // 并行加载通道+方向数据
  var p1 = fetch('/api/peng/channel').then(function(r){return r.json()});
  var p2 = fetch('/api/peng/direction').then(function(r){return r.json()});
  Promise.all([p1, p2]).then(function(results){
    render(results[0], results[1]);
  }).catch(function(){
    PU.showError(el, '数据加载失败');
  });

  function render(ch, di){
    var h = '<div class="weier-container">';

    // ═══ 极端值告警区 ═══
    if(ch && ch.ok && ch.positions){
      var pos6 = ch.positions.pos_5;  // 红六球
      var pos0 = ch.positions.pos_0;  // 红一球
      h += '<div style="margin-bottom:10px;padding:6px 10px;background:rgba(239,68,68,0.08);border-radius:6px;font-size:14px;">';
      h += '<span style="color:#FBBF24;font-weight:600;">⚠ 极端值规则 [彭浩 Ch4 表4-8]</span><br>';
      if(pos6 && pos6.current >= 30){
        h += '<span style="color:#EF4444;">▸ 红六球='+pos6.current+' (≥30) → 下期</span><span style="color:#22C55E;font-weight:700;"> 82.1%概率向下</span><br>';
      }
      if(pos0 && pos0.current <= 3){
        h += '<span style="color:#EF4444;">▸ 红一球='+pos0.current+' (≤3) → 下期</span><span style="color:#EF4444;font-weight:700;"> 72.7%概率向上</span><br>';
      }
      if((!pos6 || pos6.current < 30) && (!pos0 || pos0.current > 3)){
        h += '<span style="color:#94A3B8;">当前无极端值触发</span>';
      }
      h += '</div>';
    }

    // ═══ 通道显示区 ═══
    h += '<h5 style="color:#3B82F6;font-size:16px;margin:8px 0;">📊 五均线号码通道 [彭浩 Ch3 §2]</h5>';
    h += '<div style="font-size:16px;color:#64748B;margin-bottom:6px;">18期MA + 3σ/√σ · 通道准确率=±1范围内概率 · 绿色=正常 黄色=警戒 红色=越界</div>';

    if(ch && ch.ok && ch.positions){
      for(var i=0; i<7; i++){
        var p = ch.positions['pos_'+i];
        if(!p || !p.ok) continue;
        var atEdge = (p.current >= p.upper || p.current <= p.lower);
        var nearEdge = (p.current >= p.mid_upper || p.current <= p.mid_lower) && !atEdge;
        var bg = atEdge ? 'rgba(239,68,68,0.06)' : (nearEdge ? 'rgba(251,191,36,0.06)' : 'rgba(34,197,94,0.04)');
        var color = atEdge ? '#EF4444' : (nearEdge ? '#FBBF24' : '#22C55E');
        h += '<div style="margin:4px 0;padding:6px 8px;border-radius:4px;background:'+bg+';font-size:14px;">';
        h += '<span style="font-weight:600;color:'+color+';min-width:50px;display:inline-block;">'+p.position_name+'</span> ';
        h += '<span style="font-weight:700;color:#E2E8F0;font-size:14px;">'+String(p.current).padStart(2,'0')+'</span> ';
        h += '<span style="color:#64748B;">通道:</span> ';
        h += '<span style="color:#EF4444;">'+p.lower+'</span> ';
        h += '<span style="color:#FBBF24;">'+p.mid_lower+'</span> ';
        h += '<span style="color:#3B82F6;">['+p.ma+']</span> ';
        h += '<span style="color:#FBBF24;">'+p.mid_upper+'</span> ';
        h += '<span style="color:#22C55E;">'+p.upper+'</span> ';
        h += '<span style="color:#64748B;">σ='+p.sigma+' 准确率='+Math.round(p.accuracy_1*100)+'%</span>';
        if(atEdge) h += ' <span style="color:#EF4444;font-weight:700;">⚠越界</span>';
        h += '</div>';
      }
    } else {
      h += '<div style="color:#EF4444;font-size:14px;">'+(ch&&ch.msg||'加载失败')+'</div>';
    }

    // ═══ 方向预测区 ═══
    h += '<h5 style="color:#A78BFA;font-size:16px;margin:12px 0 8px 0;">🎯 方向预测 [彭浩 Ch3 §4]</h5>';
    h += '<div style="font-size:16px;color:#64748B;margin-bottom:6px;">三方向: ↓下=本期<上期  →平=本期=上期  ↑上=本期>上期 | 九方向: 三期组合 | 反转形态(~30%): 下上/上下</div>';

    if(di && di.ok && di.positions){
      h += '<div style="display:flex;flex-wrap:wrap;gap:6px;">';
      for(var i=0; i<7; i++){
        var d = di.positions['pos_'+i];
        if(!d) continue;
        var name = ['红一','红二','红三','红四','红五','红六','蓝球'][i];
        var d3 = d.current_3_dir;
        var d9 = d.current_9_dir;
        var arrow = d3==='上' ? '↑' : (d3==='下' ? '↓' : '→');
        var arrowColor = d3==='上' ? '#EF4444' : (d3==='下' ? '#22C55E' : '#94A3B8');
        var next = d.predicted_next;
        var nextArrow = next==='上' ? '↑' : (next==='下' ? '↓' : '?');
        var rev = d9==='下上' || d9==='上下';
        h += '<div style="padding:4px 8px;border-radius:4px;background:rgba(168,85,247,0.06);font-size:14px;text-align:center;min-width:60px;">';
        h += '<div style="color:#94A3B8;">'+name+'</div>';
        h += '<div style="font-size:18px;color:'+arrowColor+';">'+arrow+'</div>';
        h += '<div style="color:#E2E8F0;">'+d3+' '+nextArrow+'</div>';
        h += '<div style="font-size:15px;color:#64748B;">'+d9+(rev?' ⚡':'')+'</div>';
        h += '</div>';
      }
      h += '</div>';
      // 反转告警
      var hasReversal = false;
      for(var i=0; i<7; i++){
        var dd = di.positions['pos_'+i];
        if(dd && (dd.current_9_dir==='下上' || dd.current_9_dir==='上下')){
          if(!hasReversal){ h += '<div style="margin-top:6px;font-size:16px;">'; hasReversal=true; }
          h += '<span style="color:#FBBF24;">⚡ 反转形态: '+['红一','红二','红三','红四','红五','红六','蓝球'][i]+'('+dd.current_9_dir+') </span>';
        }
      }
      if(hasReversal) h += '</div>';
    } else {
      h += '<div style="color:#EF4444;font-size:14px;">'+(di&&di.msg||'加载失败')+'</div>';
    }

    // ═══ 出号区 ═══
    h += '<div style="margin-top:14px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;">';
    h += '<span style="font-size:15px;color:#94A3B8;font-weight:600;">出号选项:</span>';
    h += '<label style="font-size:14px;color:#E2E8F0;cursor:pointer;display:flex;align-items:center;gap:3px;">';
    h += '<input type="checkbox" id="pengUseChannel" checked><span>通道约束</span></label>';
    h += '<label style="font-size:14px;color:#E2E8F0;cursor:pointer;display:flex;align-items:center;gap:3px;">';
    h += '<input type="checkbox" id="pengUseDirection" checked><span>方向加权</span></label>';
    h += '<label style="font-size:14px;color:#E2E8F0;cursor:pointer;display:flex;align-items:center;gap:3px;">';
    h += '<input type="checkbox" id="pengUseExtreme" checked><span>极端值规则</span></label>';
    h += '<button class="btn btn-draw" onclick="window._pengDraw()" style="font-size:15px;padding:6px 16px;margin-left:auto;">彭浩出号</button>';
    h += '</div>';

    h += '<div id="pengResult" style="margin-top:12px;"></div>';

    h += '</div>';
    el.innerHTML = h;
  }
};

/** 彭浩出号 */
window._pengDraw = async function(){
  var resultEl = document.getElementById('pengResult');
  if(!resultEl) return;
  PU.showWarn(resultEl, '分析中...');

  var params = '?n=' + (window.store?.drawCount||3) +
    '&channel=' + (document.getElementById('pengUseChannel')?.checked?1:0) +
    '&direction=' + (document.getElementById('pengUseDirection')?.checked?1:0) +
    '&extreme=' + (document.getElementById('pengUseExtreme')?.checked?1:0);

  var data = await PU.drawTickets('/api/peng/tickets' + params, resultEl);
  if(!data) return;

  var h = '<div style="font-size:16px;color:'+PU.GRAY+';margin-bottom:6px;">'+
    data.algorithm+' · '+data.periods_used+'期</div>';
  h += '<div style="display:flex;gap:12px;flex-wrap:wrap;">';
  h += PU.renderTicketCards(data.tickets);
  h += '</div>';
  resultEl.innerHTML = h;
};
