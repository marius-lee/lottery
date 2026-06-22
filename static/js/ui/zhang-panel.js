/** 张委铭算法面板 — 三种方法独立工作流 (2017版, 不劫持主「生成号码」按钮)

 *  围号选号法   (Ch7§1): 18种低胜率杀号→~12个红球候选+位置策略选号
 *  后区围号选号法 (Ch8§1): 10种低胜率后区杀号→~8个蓝球候选
 *  行列网格     (Ch7§2): 3×11网格自动断区→缩小候选池
 */
window._showZhangPanel = function(){
  var el = document.getElementById('zhangContent');
  if(!el) return;
  el.innerHTML = '<div style="color:#94A3B8;padding:8px;">加载中...</div>';

  // 并行加载三种方法的数据
  var p1 = fetch('/api/zhang/twelve-value?n=0').then(function(r){return r.json()});
  var p2 = fetch('/api/zhang/eight-value?n=0').then(function(r){return r.json()});
  var p3 = fetch('/api/zhang/grid?n=0').then(function(r){return r.json()});
  Promise.all([p1, p2, p3]).then(function(results){
    render(results[0], results[1], results[2]);
  }).catch(function(){
    el.innerHTML = '<div style="color:#EF4444;padding:16px;">数据加载失败，请确认服务器已启动</div>';
  });

  function render(tv, ev, gd){
    var h = '<div class="weier-container">';

    // ═══ 定胆区 (Ch5, 独立于选号方法) ═══
    h += '<div style="margin-bottom:12px;padding:8px 10px;background:rgba(168,85,247,0.06);border-radius:6px;">';
    h += '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">';
    h += '<span style="font-size:12px;color:#A78BFA;font-weight:600;">🎯 定胆 (Ch5):</span>';
    h += '<label style="font-size:11px;color:#E2E8F0;cursor:pointer;display:flex;align-items:center;gap:3px;">';
    h += '<input type="checkbox" id="zhangUseDan1" onchange="window._zhangUpdateBtn()">';
    h += '<span>一四定胆法(1码,21.57%)</span></label>';
    h += '<label style="font-size:11px;color:#E2E8F0;cursor:pointer;display:flex;align-items:center;gap:3px;">';
    h += '<input type="checkbox" id="zhangUseDan2" onchange="window._zhangUpdateBtn()">';
    h += '<span>定2胆最优法(2码,~4.3%)</span></label>';
    h += '<span id="zhangDanDetail" style="font-size:10px;color:#64748B;">加载中...</span>';
    h += '</div></div>';

    // ═══ 选号方法 + 出号按钮 (Ch7, Ch8) ═══
    h += '<div style="display:flex;gap:12px;margin-bottom:12px;flex-wrap:wrap;align-items:center;">';
    h += '<span style="font-size:12px;color:#94A3B8;font-weight:600;">选号方法:</span>';

    h += '<label style="font-size:12px;color:#E2E8F0;cursor:pointer;display:flex;align-items:center;gap:4px;">';
    h += '<input type="checkbox" id="zhangUse12" checked onchange="window._zhangUpdateBtn()">';
    h += '<span>🎯围号选号(Ch7)</span></label>';

    h += '<label style="font-size:12px;color:#E2E8F0;cursor:pointer;display:flex;align-items:center;gap:4px;">';
    h += '<input type="checkbox" id="zhangUseGrid" onchange="window._zhangUpdateBtn()">';
    h += '<span>🔲行列网格(Ch7)</span></label>';

    h += '<label style="font-size:12px;color:#E2E8F0;cursor:pointer;display:flex;align-items:center;gap:4px;">';
    h += '<input type="checkbox" id="zhangUse8" onchange="window._zhangUpdateBtn()">';
    h += '<span>🎱后区围号(Ch8)</span></label>';

    h += '<button class="btn btn-draw" id="zhangDrawBtn" onclick="window._zhangDraw()" style="font-size:12px;padding:6px 16px;">张委铭出号</button>';
    h += '<span id="zhangStatus" style="font-size:11px;color:#94A3B8;"></span>';
    h += '</div>';

    h += '<div id="zhangResult"></div>';

    // ═══ 围号红球 候选明细 ═══
    h += '<div style="margin-bottom:16px;">';
    h += '<h5 style="color:#A78BFA;font-size:13px;margin:0 0 8px 0;">🎯 围号红球 · 18种杀号→候选</h5>';
    if(tv && tv.ok){
      h += '<div style="font-size:11px;color:#94A3B8;margin-bottom:4px;">';
      h += '候选池('+tv.candidate_count+'个): ';
      (tv.candidates||[]).forEach(function(n){
        h += '<span style="display:inline-block;padding:2px 6px;margin:1px;border-radius:4px;background:rgba(168,85,247,0.2);color:#A78BFA;font-weight:700;">'+String(n).padStart(2,'0')+'</span>';
      });
      h += '</div>';
      if(tv.first8){
        h += '<div style="font-size:10px;color:#10B981;margin-bottom:2px;">前8(P1-P2): '+tv.first8.map(function(n){return String(n).padStart(2,'0')}).join(' ')+'</div>';
      }
      h += '<div style="font-size:9px;color:#64748B;">位置策略: P1-2→前8 | P3-4→池+邻±1 | P5→避池 | P6→30-33</div>';
      h += '<details style="margin-top:4px;"><summary style="font-size:10px;color:#64748B;cursor:pointer;">18种方法明细</summary>';
      h += '<table class="bt-table" style="font-size:10px;margin-top:4px;"><thead><tr><th>方法</th><th>杀号</th></tr></thead><tbody>';
      Object.keys(tv.method_details||{}).forEach(function(k){
        h += '<tr><td>'+k+'</td><td style="color:#cc4444;">'+String(tv.method_details[k]).padStart(2,'0')+'</td></tr>';
      });
      h += '</tbody></table></details>';
    } else { h += '<div style="color:#EF4444;font-size:11px;">'+(tv&&tv.msg||'加载失败')+'</div>'; }
    h += '</div>';

    // ═══ 围号蓝球 候选明细 ═══
    h += '<div style="margin-bottom:16px;">';
    h += '<h5 style="color:#3B82F6;font-size:13px;margin:0 0 8px 0;">🎱 围号蓝球 · 11种后区杀号→候选</h5>';
    if(ev && ev.ok){
      h += '<div style="font-size:11px;color:#94A3B8;margin-bottom:4px;">';
      h += '候选池('+ev.candidate_count+'个): ';
      (ev.candidates||[]).forEach(function(n){
        h += '<span style="display:inline-block;padding:3px 8px;margin:2px;border-radius:6px;background:rgba(59,130,246,0.2);color:#3B82F6;font-weight:700;">'+String(n).padStart(2,'0')+'</span>';
      });
      h += '</div>';
      h += '<div style="font-size:10px;color:#FBBF24;margin-bottom:2px;">';
      h += (ev.use_recommendation||'') + ' | 连续出错: '+ev.consecutive_errors+'次</div>';
      h += '<div style="font-size:9px;color:#64748B;">出错规律: 1次→52%正 | 2→23% | 3→13% | 4→6.4% | 5+→5.4%</div>';
      h += '<details style="margin-top:4px;"><summary style="font-size:10px;color:#64748B;cursor:pointer;">11种方法明细</summary>';
      h += '<table class="bt-table" style="font-size:10px;margin-top:4px;"><thead><tr><th>方法</th><th>杀号</th></tr></thead><tbody>';
      Object.keys(ev.method_details||{}).forEach(function(k){
        h += '<tr><td>'+k+'</td><td style="color:#3366cc;">'+String(ev.method_details[k]).padStart(2,'0')+'</td></tr>';
      });
      h += '</tbody></table></details>';
    } else { h += '<div style="color:#EF4444;font-size:11px;">'+(ev&&ev.msg||'加载失败')+'</div>'; }
    h += '</div>';

    // ═══ 行列网格 候选明细 ═══
    h += '<div style="margin-bottom:16px;">';
    h += '<h5 style="color:#F59E0B;font-size:13px;margin:0 0 8px 0;">🔲 行列网格 · 3×11自动断区</h5>';
    if(gd && gd.ok && gd.grid){
      var g = gd.grid;
      h += '<div style="font-size:11px;color:#F59E0B;margin-bottom:4px;"><b>'+g.mode_desc+'</b></div>';
      var br = (g.break_rows||[]).join(',') || '无';
      var bc = (g.break_cols||[]).join(',') || '无';
      h += '<div style="font-size:10px;color:#94A3B8;margin-bottom:2px;">断行: ['+br+'] | 断列: ['+bc+']</div>';
      h += '<div style="font-size:11px;margin-bottom:4px;">剩余'+g.remaining_count+'个: ';
      (g.remaining_numbers||[]).forEach(function(n){
        h += '<span style="display:inline-block;padding:2px 6px;margin:1px;border-radius:4px;background:rgba(245,158,11,0.2);color:#F59E0B;font-weight:700;">'+String(n).padStart(2,'0')+'</span>';
      });
      h += '</div>';
      h += '<div style="font-size:9px;color:#64748B;">行规则: 本期断→下期93%不断 | 列连续断1-2次→继续断 | ≥3次→停止</div>';
      h += '<div style="font-size:8px;color:#64748B;">参考: 0r6c·15号·41% | 0r5c·18号·22% | 0r7c·12号·16% | 1r6c·10号·9.5% | 1r7c·8号·2.5% (原书表7-35)</div>';
    } else { h += '<div style="color:#EF4444;font-size:11px;">'+(gd&&gd.msg||'加载失败')+'</div>'; }
    h += '</div>';

    // ═══ 数据手册 (可点击展开) ═══
    h += '<div style="margin-top:16px;">';
    h += '<h5 style="color:#94A3B8;font-size:13px;margin:0 0 8px 0;">📖 数据手册 (原书统计表, 点击展开)</h5>';
    h += '<div id="zhangRefContent" style="font-size:10px;color:#64748B;">加载中...</div>';
    h += '</div>';

    // ═══ 统计来源 ═══
    h += '<div style="font-size:9px;color:#64748B;padding:6px 8px;background:rgba(255,255,255,0.03);border-radius:6px;">';
    h += '📊 张委铭《双色球杀号定胆选号方法与技巧超级大全》经济管理出版社 2015 | 统计周期: 2003001-2015023 共1768期 | 全量枚举';
    h += '</div>';

    h += '</div>';
    el.innerHTML = h;
    window._zhangUpdateBtn();

    // 异步加载定胆详情
    fetch('/api/zhang/dan1').then(function(r){return r.json()}).then(function(d1){
      fetch('/api/zhang/dan2').then(function(r){return r.json()}).then(function(d2){
        var di = document.getElementById('zhangDanDetail');
        if(!di) return;
        var dh = '';
        if(d1&&d1.ok){
          dh += ' 一四定胆→<b style=\"color:#A78BFA;\">'+String(d1.dan).padStart(2,'0')+'</b>';
          dh += '<span style=\"color:#64748B;\">('+d1.method_used+')</span>';
        }
        if(d2&&d2.ok){
          dh += ' 定2胆→<b style=\"color:#F59E0B;\">'+d2.dan2.map(function(n){return String(n).padStart(2,'0')}).join('+')+'</b>';
          dh += '<span style=\"color:#64748B;\">(组合'+d2.combo_name+')</span>';
        }
        di.innerHTML = dh;
      }).catch(function(){});
    }).catch(function(){});

    // 异步加载数据手册
    fetch('/static/data/zhang-weiming-reference.json').then(function(r){return r.json()}).then(function(ref){
      var rc = document.getElementById('zhangRefContent');
      if(!rc) return;
      renderReference(rc, ref);
    }).catch(function(){
      var rc = document.getElementById('zhangRefContent');
      if(rc) rc.innerHTML = '<span style="color:#EF4444;">数据手册加载失败</span>';
    });
  }

  function renderReference(el, ref){
    var h = '';

    // 位置差值表
    if(ref.position_differences){
      h += '<details style="margin-bottom:6px;"><summary style="cursor:pointer;color:#A78BFA;font-size:11px;">📐 '+ref.position_differences._title+'</summary>';
      h += '<div style="font-size:9px;color:#64748B;margin:4px 0 8px;">'+ref.position_differences._usage+'</div>';
      var diffs = ref.position_differences;
      ['p5_minus_p3','p6_minus_p3','p5_minus_p4','p6_minus_p4','p6_minus_p5'].forEach(function(key){
        var d = diffs[key];
        if(!d) return;
        h += '<div style="margin-bottom:6px;padding:4px 6px;background:rgba(255,255,255,0.02);border-radius:4px;">';
        h += '<b style="color:#E2E8F0;">'+d.label+'</b> ';
        h += '<span style="color:#10B981;">常用'+d.common_range[0]+'-'+d.common_range[1]+' ('+d.common_pct+')</span> ';
        h += '<span style="color:#EF4444;">避开'+d.avoid_range[0]+'-'+d.avoid_range[1]+' ('+d.avoid_pct+')</span> ';
        h += '<span style="color:#FBBF24;">最高: '+d.top_value+' ('+d.top_pct+'%)</span><br>';
        // 简要分布
        var sorted = Object.entries(d.distribution).sort(function(a,b){return b[1]-a[1];}).slice(0,8);
        h += '<span style="color:#64748B;">分布: '+sorted.map(function(e){return e[0]+'→'+e[1]+'次';}).join(' | ')+'</span>';
        if(d.note_1) h += '<br><span style="color:#F59E0B;">'+d.note_1+'</span>';
        if(d.note_2) h += '<br><span style="color:#F59E0B;">'+d.note_2+'</span>';
        if(d.note_3) h += '<br><span style="color:#F59E0B;">'+d.note_3+'</span>';
        h += '</div>';
      });
      h += '</details>';
    }

    // 连号统计
    if(ref.consecutive_patterns){
      h += '<details style="margin-bottom:6px;"><summary style="cursor:pointer;color:#F59E0B;font-size:11px;">🔗 '+ref.consecutive_patterns._title+'</summary>';
      var cp = ref.consecutive_patterns;
      h += '<div style="font-size:10px;color:#94A3B8;margin-top:4px;">';
      h += '连号组数: 1组51.9% | 0组34.3% | 2组13.5% | 3组0.3%<br>';
      h += '两连号: 平均1.45期/次(1218次) | 三连号: 9.71期/次(169次)<br>';
      h += '最频: 56型(第5-6位连号) > 12型(第1-2位)<br>';
      h += '<span style="color:#10B981;">'+cp.advice+'</span>';
      h += '</div></details>';
    }

    // 定2胆
    if(ref.dan2_top_pairs){
      h += '<details style="margin-bottom:6px;"><summary style="cursor:pointer;color:#3B82F6;font-size:11px;">✌ '+ref.dan2_top_pairs._title+'</summary>';
      h += '<div style="font-size:9px;color:#64748B;margin:4px 0;">'+ref.dan2_top_pairs._usage+'</div>';
      h += '<div style="display:flex;flex-wrap:wrap;gap:4px;max-height:200px;overflow-y:auto;">';
      ref.dan2_top_pairs.pairs.forEach(function(p, i){
        var bg = i<15 ? 'rgba(59,130,246,0.15)' : 'rgba(255,255,255,0.03)';
        h += '<span style="padding:2px 6px;border-radius:4px;background:'+bg+';color:#94A3B8;white-space:nowrap;">';
        h += '#'+(i+1)+' '+p.combo.map(function(n){return String(n).padStart(2,'0')}).join('+');
        h += ' <span style="color:#64748B;">'+p.count+'次</span></span>';
      });
      h += '</div>';
      var cold = ref.dan2_top_pairs.coldest_pairs;
      if(cold) h += '<div style="font-size:9px;color:#EF4444;margin-top:4px;">最冷: '+cold.map(function(p){return p.combo.join('+')+'('+p.count+'次)';}).join(', ')+'</div>';
      h += '</details>';
    }

    // 定3胆
    if(ref.dan3_top_triples){
      h += '<details style="margin-bottom:6px;"><summary style="cursor:pointer;color:#8B5CF6;font-size:11px;">🤟 '+ref.dan3_top_triples._title+'</summary>';
      h += '<div style="font-size:9px;color:#64748B;margin:4px 0;">'+ref.dan3_top_triples._usage+'</div>';
      h += '<div style="display:flex;flex-wrap:wrap;gap:4px;max-height:160px;overflow-y:auto;">';
      ref.dan3_top_triples.triples.forEach(function(p, i){
        h += '<span style="padding:2px 6px;border-radius:4px;background:rgba(139,92,246,0.1);color:#94A3B8;white-space:nowrap;font-size:9px;">';
        h += ''+p.combo.map(function(n){return String(n).padStart(2,'0')}).join('+');
        h += ' ('+p.count+')</span>';
      });
      h += '</div></details>';
    }

    // 伴生现象
    if(ref.cooccurrence){
      h += '<details style="margin-bottom:6px;"><summary style="cursor:pointer;color:#EC4899;font-size:11px;">💞 '+ref.cooccurrence._title+'</summary>';
      h += '<div style="font-size:9px;color:#64748B;margin:4px 0;">'+ref.cooccurrence._usage+'<br>'+ref.cooccurrence._note+'</div>';
      var nums = ['01','02','03','04','05','06'];
      nums.forEach(function(n){
        var data = ref.cooccurrence[n];
        if(!data) return;
        h += '<div style="margin:3px 0;padding:3px 6px;background:rgba(255,255,255,0.02);border-radius:4px;">';
        h += '<b style="color:#E2E8F0;">胆码 '+n+':</b> ';
        h += '<span style="color:#10B981;">选 '+data.top_companions.map(function(c){return c[0]+'('+c[1]+')';}).join(', ')+'</span> ';
        var av = Array.isArray(data.avoid) ? data.avoid.join(',') : data.avoid;
        h += '<span style="color:#EF4444;">避 '+av+' ('+data.avoid_count+')</span>';
        h += '</div>';
      });
      h += '</details>';
    }

    // 重号统计
    if(ref.repeat_stats){
      h += '<details style="margin-bottom:6px;"><summary style="cursor:pointer;color:#10B981;font-size:11px;">🔄 '+ref.repeat_stats._title+'</summary>';
      var rs = ref.repeat_stats;
      h += '<div style="font-size:10px;color:#94A3B8;margin-top:4px;">';
      h += '重号个数: 1个43.2% | 0个27.9% | 2个23.8% | 3个4.6% | 4+个<0.6%<br>';
      h += '重号位置: 第1位18.7% | 第2位18.3% | 第3位17.9% | 第4位17.5% | 第5位17.3% | 第6位17.0%<br>';
      h += '<span style="color:#FBBF24;">'+rs.advice+'</span>';
      h += '</div></details>';
    }

    // 蓝球基本统计
    if(ref.blue_basic_stats){
      h += '<details style="margin-bottom:6px;"><summary style="cursor:pointer;color:#06B6D4;font-size:11px;">🔵 '+ref.blue_basic_stats._title+'</summary>';
      var bs = ref.blue_basic_stats;
      h += '<div style="font-size:10px;color:#94A3B8;margin-top:4px;">';
      h += '奇偶: 奇51.1% | 偶48.9% → '+bs.odd_even.advice+'<br>';
      h += '大小: 大52.4% | 小47.6% → '+bs.big_small.advice+'<br>';
      h += '重号: 出现7.1%, 连出2次后→'+bs.repeat.advice+'<br>';
      h += '</div></details>';
    }

    // Ch6 技术指标 (2017版)
    if(ref.ch6_technical_indicators_2017){
      var ch6 = ref.ch6_technical_indicators_2017;
      h += '<details style="margin-bottom:6px;"><summary style="cursor:pointer;color:#F59E0B;font-size:11px;">📊 '+ch6._title+'</summary>';
      h += '<div style="font-size:9px;color:#64748B;margin:4px 0;">'+ch6._usage+'</div>';

      // 重号
      if(ch6.repeat){
        h += '<div style="margin:3px 0;padding:3px 6px;background:rgba(255,255,255,0.02);border-radius:4px;">';
        h += '<b style="color:#10B981;">重号 '+ch6.repeat.overall_probability+'%</b> ';
        h += '<span style="color:#EF4444;">'+ch6.repeat.key_finding+'</span><br>';
        h += '<span style="color:#94A3B8;">A1:'+ch6.repeat.by_count['1个重号(A1)']+'% A0:'+ch6.repeat.by_count['0个重号(A0)']+'% A2:'+ch6.repeat.by_count['2个重号(A2)']+'%</span> ';
        h += '<span style="color:#FBBF24;">A6-6 & A1-1 各~11% (最高频细分)</span>';
        h += '</div>';
      }
      // 连号
      if(ch6.consecutive){
        h += '<div style="margin:3px 0;padding:3px 6px;background:rgba(255,255,255,0.02);border-radius:4px;">';
        h += '<b style="color:#10B981;">连号 '+ch6.consecutive.overall_probability+'%</b> ';
        h += '<span style="color:#EF4444;">'+ch6.consecutive.key_finding+'</span><br>';
        h += '<span style="color:#94A3B8;">'+ch6.consecutive.advice+'</span>';
        h += '</div>';
      }
      // 质合
      if(ch6.prime_composite){
        h += '<div style="margin:3px 0;padding:3px 6px;background:rgba(255,255,255,0.02);border-radius:4px;">';
        h += '<b style="color:#FBBF24;">质合比3:3 → 范围缩至26.42%</b> ';
        h += '<span style="color:#94A3B8;">'+ch6.prime_composite.detail+'</span>';
        h += '</div>';
      }
      // 隔期码
      if(ch6.skip_code){
        h += '<div style="margin:3px 0;padding:3px 6px;background:rgba(255,255,255,0.02);border-radius:4px;">';
        h += '<b style="color:#EF4444;">隔期码 '+ch6.skip_code.key_finding+'</b> ';
        h += '<span style="color:#64748B;">(选对0个:506, 1个:874, 2个:506, 3+:116)</span>';
        h += '</div>';
      }
      // 除3余数
      if(ch6.route012){
        h += '<div style="margin:3px 0;padding:3px 6px;background:rgba(255,255,255,0.02);border-radius:4px;">';
        h += '<b style="color:#64748B;">除3余数:</b> 2路34.0% | 1路33.4% | 0路32.6% → '+ch6.route012.verdict;
        h += '</div>';
      }
      h += '</details>';
    }

    el.innerHTML = h;
  }
};

// 更新按钮文字
window._zhangUpdateBtn = function(){
  var btn = document.getElementById('zhangDrawBtn');
  if(!btn) return;
  var u12 = document.getElementById('zhangUse12');
  var u8 = document.getElementById('zhangUse8');
  var ug = document.getElementById('zhangUseGrid');
  var ud1 = document.getElementById('zhangUseDan1');
  var ud2 = document.getElementById('zhangUseDan2');
  var sel = [];
  if(u12&&u12.checked) sel.push('围号');
  if(ug&&ug.checked) sel.push('网格');
  if(u8&&u8.checked) sel.push('蓝围');
  if(ud1&&ud1.checked) sel.push('+定1胆');
  if(ud2&&ud2.checked) sel.push('+定2胆');
  var hasMethod = (u12&&u12.checked) || (ug&&ug.checked) || (u8&&u8.checked);
  btn.textContent = sel.length ? '出号: '+sel.join(' ') : '请选择方法';
  btn.disabled = !hasMethod;
};

// 出号
window._zhangDraw = function(){
  var st = document.getElementById('zhangStatus');
  var re = document.getElementById('zhangResult');
  if(st) st.textContent = '分析中...';
  if(re) re.innerHTML = '';

  var u12 = document.getElementById('zhangUse12');
  var u8 = document.getElementById('zhangUse8');
  var ug = document.getElementById('zhangUseGrid');
  var ud1 = document.getElementById('zhangUseDan1');
  var ud2 = document.getElementById('zhangUseDan2');
  var use12 = u12&&u12.checked;
  var use8 = u8&&u8.checked;
  var useGrid = ug&&ug.checked;
  var useDan1 = ud1&&ud1.checked;
  var useDan2 = ud2&&ud2.checked;

  // 必须有选号方法(围号/网格/蓝围)才能出号; 定胆是选号方法的增强器
  if(!use12 && !use8 && !useGrid){
    if(st) st.textContent = '请至少选择一个选号方法';
    return;
  }

  var n = 3;
  var selEl = document.getElementById('drawCount');
  if(selEl) n = parseInt(selEl.value) || 3;

  // 收集定胆号码 (原书Ch5: 定胆+选号可叠加)
  function collectDans(callback){
    var dans = [];
    var pending = 0;
    if(useDan1){
      pending++;
      fetch('/api/zhang/dan1').then(function(r){return r.json()}).then(function(d){
        if(d&&d.ok) dans.push(d.dan);
        if(--pending === 0) callback(dans);
      }).catch(function(){ if(--pending === 0) callback(dans); });
    }
    if(useDan2){
      pending++;
      fetch('/api/zhang/dan2').then(function(r){return r.json()}).then(function(d){
        if(d&&d.ok) dans = dans.concat(d.dan2);
        if(--pending === 0) callback(dans);
      }).catch(function(){ if(--pending === 0) callback(dans); });
    }
    if(pending === 0) callback(dans);
  }

  collectDans(function(dans){
    var danParam = dans.length ? '&dan='+dans.join(',') : '';

    // 构建端点: 优先围号, 其次网格, 蓝围始终独立
    var endpoint;
    if(use12 && use8 && !useGrid) endpoint = '/api/zhang/combined?n='+n+danParam;
    else if(use12) endpoint = '/api/zhang/twelve-value?n='+n+danParam;
    else if(useGrid) endpoint = '/api/zhang/grid?n='+n;
    else endpoint = '/api/zhang/eight-value?n='+n;

    fetch(endpoint).then(function(r){return r.json()}).then(function(d){
      if(!d || !d.ok){ if(st) st.textContent = d&&d.msg||'失败'; return; }
      if(st) st.textContent = d.tickets.length+'注 · ¥'+(d.tickets.length*2);

      var rh = '<div style="margin-top:12px;">';
      rh += '<div style="font-size:10px;color:#94A3B8;margin-bottom:8px;">算法: '+d.algorithm;
      if(dans.length){
        rh += ' <span style="color:#A78BFA;">🔒胆码:'+dans.join(',')+'</span>';
      }
      rh += '</div>';
      if(d.weihao){
        rh += '<div style="font-size:10px;color:#A78BFA;">围号候选('+d.weihao.candidate_count+'个): '+(d.weihao.candidates||[]).slice(0,12).join(' ')+'</div>';
      }
      if(d.weihao_blue){
        rh += '<div style="font-size:10px;color:#3B82F6;">蓝围候选('+d.weihao_blue.candidate_count+'个): '+(d.weihao_blue.candidates||[]).join(' ')+' | '+d.weihao_blue.use_recommendation+'</div>';
      }
      if(d.grid){
        rh += '<div style="font-size:10px;color:#F59E0B;">'+d.grid.mode_desc+' | 剩余'+d.grid.remaining_count+'号</div>';
      }
      rh += '<table class="bt-table" style="margin-top:6px;"><thead><tr><th>#</th><th>红球</th><th>蓝球</th></tr></thead><tbody>';
      d.tickets.forEach(function(t,i){
        rh += '<tr><td>'+(i+1)+'</td><td style="color:#cc4444;">'+(t.reds||[]).join(' ')+'</td><td style="color:#3366cc;">'+String(t.blue||'?').padStart(2,'0')+'</td></tr>';
      });
      rh += '</tbody></table></div>';
      if(re) re.innerHTML = rh;
    }).catch(function(e){
      if(st) st.textContent = '请求失败: '+e;
    });
  });
};
