/** 微尔算法8步条件选择面板
 *
 *  流程: 加载遗漏值→渲染8步条件→用户勾选→提交过滤→显示结果
 */

// 预加载条件数据
fetch('/api/weier/conditions').then(function(r){return r.json()}).then(function(d){
  if(d.ok){ window._weierData = d; }
}).catch(function(){});

window._showWeierPanel = function(){
  var el = document.getElementById('weierContent');
  if(!el) return;
  el.innerHTML = '<div style="color:#FFFFFF;padding:8px;">加载中...</div>';

  var clsTag = function(o){ return o<=10?'<span style="color:#10B981;font-size:16px;">热</span>':o<=18?'<span style="color:#FBBF24;font-size:16px;">温</span>':'<span style="color:#EF4444;font-size:16px;">冷</span>'; };

  function render(data){
    var h = '<div class="weier-container">';
    h += '<div style="display:flex;gap:8px;margin-bottom:12px;">';
    h += '<button class="btn btn-draw" onclick="window._runWeierFilter()" style="font-size:15px;padding:6px 16px;">开始过滤</button>';
    h += '<button class="btn btn-save" onclick="window._clearWeier()" style="font-size:15px;padding:6px 16px;background:#FFFFFF;">清除选择</button>';
    h += '<span id="weierStatus" style="font-size:14px;color:#FFFFFF;align-self:center;"></span></div>';

    // 第1-3步
    function ratioRow(label, items, stepNum) {
      var r = '<div class="weier-row"><span class="weier-label">'+label+'位</span>';
      for(var i=0;i<items.length;i++){
        var it=items[i], id='s'+stepNum+'_'+label+'_'+it.ratio.replace(':','_');
        r += '<label class="weier-chk"><input type="checkbox" id="'+id+'" data-step="step1" data-col="'+label+'" data-val="'+it.ratio+'"><span>'+it.ratio+'</span><span class="weier-om">'+(it.omission>=99?'∞':it.omission)+'</span>'+clsTag(it.omission)+'</label>';
      }
      return r+'</div>';
    }
    function simpleRow(name, vals, stepNum) {
      var r = '<div class="weier-row"><span class="weier-label">'+name+'</span>';
      for(var i=0;i<vals.length;i++) r += '<label class="weier-chk"><input type="checkbox" data-step="step'+stepNum+'" data-col="'+name+'" data-val="'+vals[i]+'"><span>'+vals[i]+'</span></label>';
      return r+'</div>';
    }

    h += '<div class="weier-step"><h5>第1步 位比值 A轮 (相邻位)</h5>';
    ['1-2','2-3','3-4','4-5','5-6'].forEach(function(l){ h+=ratioRow(l,data.conditions[l],1); });
    h += '</div>';

    h += '<div class="weier-step"><h5>第2步 位比值 B轮 (跳1位)</h5>';
    ['1-3','1-4','1-5','1-6'].forEach(function(l){ h+=ratioRow(l,data.conditions[l],2); });
    h += '</div>';

    h += '<div class="weier-step"><h5>第3步 位比值 C轮 (跳2位)</h5>';
    ['2-4','2-5','2-6','3-5','3-6'].forEach(function(l){ h+=ratioRow(l,data.conditions[l],3); });
    h += '</div>';

    h += '<div class="weier-step"><h5>第4步 高尾 (0=无 1=一个 2=两个)</h5>';
    ['12位','34位','56位','25位','16位'].forEach(function(n){ h+=simpleRow(n,['0','1','2'],4); });
    h += '</div>';

    h += '<div class="weier-step"><h5>第5步 位间距奇偶 (1=奇 2=偶)</h5>';
    ['12位距','34位距','56位距'].forEach(function(n){ h+=simpleRow(n,['1','2'],5); });
    h += '</div>';

    h += '<div class="weier-step"><h5>第6步 大小和值奇偶 (1=奇 2=偶)</h5>';
    ['大和值','小和值'].forEach(function(n){ h+=simpleRow(n,['1','2'],6); });
    h += '</div>';

    h += '<div class="weier-step"><h5>第7步 首尾和/差/尾数和 012路</h5>';
    ['首尾和','首尾差','尾数和'].forEach(function(n){ h+=simpleRow(n,['0','1','2'],7); });
    h += '</div>';

    h += '<div class="weier-step"><h5>第8步 位尾数和012路</h5>';
    ['12位尾和','34位尾和','56位尾和'].forEach(function(n){ h+=simpleRow(n,['0','1','2'],8); });
    h += '</div>';

    h += '<div id="weierResult"></div></div>';
    el.innerHTML = h;
  }

  if(window._weierData){ render(window._weierData); }
  else{ fetch('/api/weier/conditions').then(function(r){return r.json()}).then(function(d){
      if(d.ok){window._weierData=d; render(d);} else{el.innerHTML='加载失败';}
    }).catch(function(){el.innerHTML='加载失败';}); }
};

window._runWeierFilter = function(){
  var st = document.getElementById('weierStatus'); if(st) st.textContent = '过滤中...';
  var cond = {};
  var cbs = document.querySelectorAll('.weier-chk input:checked');
  for(var i=0;i<cbs.length;i++){
    var cb = cbs[i], step = cb.dataset.step, col = cb.dataset.col, val = cb.dataset.val;
    if(!cond[step]) cond[step] = {};
    if(!cond[step][col]) cond[step][col] = [];
    cond[step][col].push(val);
  }
  fetch('/api/weier/manual',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cond)})
    .then(function(r){return r.json()}).then(function(d){
      if(d.ok){
        if(st) st.textContent = d.tickets.length+'注, ¥'+d.cost_rmb;
        var re = document.getElementById('weierResult');
        if(re){
          var h = '<div style="margin-top:12px;max-height:400px;overflow-y:auto;"><table class="bt-table"><thead><tr><th>#</th><th>红球</th><th>蓝球</th></tr></thead><tbody>';
          for(var i=0;i<d.tickets.length;i++) h += '<tr><td>'+(i+1)+'</td><td style="color:#cc4444;">'+d.tickets[i].reds.join(' ')+'</td><td style="color:#3366cc;">'+String(d.tickets[i].blue).padStart(2,'0')+'</td></tr>';
          h += '</tbody></table></div>'; re.innerHTML = h;
        }
      }else{ if(st) st.textContent = d.msg||'失败'; }
    }).catch(function(){ if(st) st.textContent = '请求失败'; });
};

window._clearWeier = function(){
  var cbs = document.querySelectorAll('.weier-chk input');
  for(var i=0;i<cbs.length;i++) cbs[i].checked = false;
  var st = document.getElementById('weierStatus'); if(st) st.textContent = '';
  var re = document.getElementById('weierResult'); if(re) re.innerHTML = '';
};
