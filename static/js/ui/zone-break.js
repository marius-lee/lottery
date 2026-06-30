/** 断区转换法面板 (刘大军 2014, 《双色球终极战法》第2章)
 *
 *  6×6行列分布表 + 断区3D号码历史 + 用户选择断区 → 过滤出号
 */
var ZB = {};

ZB.render = function(containerId) {
  var el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = '<div style="color:#FFFFFF;padding:8px;">加载中...</div>';

  fetch('/api/zone-break/data').then(function(r){return r.json()}).then(function(d){
    var h = '<div class="weier-container">';

    // 断区选择器
    h += '<div style="display:flex;gap:12px;margin-bottom:12px;flex-wrap:wrap;align-items:center;">';
    h += '<span style="font-size:12px;color:#FFFFFF;">断行3D码:</span>';
    h += '<select id="zbBreakRows" style="padding:5px 10px;border-radius:6px;border:1px solid rgba(255,255,255,0.1);background:#1E1E36;color:#E2E8F0;font-size:13px;">';
    ZB.ALL_CODES.forEach(function(c){ h += '<option value="'+c+'">'+c+'</option>'; });
    h += '</select>';
    h += '<span style="font-size:12px;color:#FFFFFF;">断列3D码:</span>';
    h += '<select id="zbBreakCols" style="padding:5px 10px;border-radius:6px;border:1px solid rgba(255,255,255,0.1);background:#1E1E36;color:#E2E8F0;font-size:13px;">';
    ZB.ALL_CODES.forEach(function(c){ h += '<option value="'+c+'">'+c+'</option>'; });
    h += '</select>';
    h += '<button class="btn btn-draw" onclick="ZB.filter()" style="font-size:12px;padding:6px 14px;">断区过滤</button>';
    h += '<span id="zbStatus" style="font-size:11px;color:#FFFFFF;"></span>';
    h += '</div>';

    // 6×6行列分布表
    h += '<div style="margin-bottom:12px;">';
    h += '<h5 style="color:#A78BFA;font-size:13px;margin:0 0 8px 0;">行列分布表 (近30期出现次数)</h5>';
    h += '<table style="border-collapse:collapse;font-size:11px;text-align:center;width:100%;max-width:420px;">';
    h += '<tr><th style="padding:4px;color:#FFFFFF;"></th>';
    for (var ci=1;ci<=6;ci++) h += '<th style="padding:4px;color:#FFFFFF;">第'+ci+'列</th>';
    h += '</tr>';
    for (var ri=0;ri<6;ri++) {
      h += '<tr><td style="padding:4px;color:#FFFFFF;font-weight:600;">第'+(ri+1)+'行</td>';
      for (var ci=0;ci<6;ci++) {
        var cnt = d.distribution[ri][ci];
        var bg = cnt > 8 ? 'rgba(16,185,129,0.2)' : cnt > 4 ? 'rgba(251,191,36,0.1)' : 'rgba(255,255,255,0.03)';
        var color = cnt > 8 ? '#10B981' : cnt > 4 ? '#FBBF24' : '#FFFFFF';
        var num = ri*6 + ci + 1;
        h += '<td style="padding:4px 6px;background:'+bg+';border:1px solid rgba(255,255,255,0.04);"><div style="font-weight:700;color:'+color+';">'+String(num).padStart(2,'0')+'</div><div style="font-size:9px;color:#FFFFFF;">'+cnt+'次</div></td>';
      }
      h += '</tr>';
    }
    h += '</table></div>';

    // 近30期断区历史
    h += '<div style="margin-bottom:12px;max-height:200px;overflow-y:auto;">';
    h += '<h5 style="color:#A78BFA;font-size:13px;margin:0 0 6px 0;">近30期断区3D历史</h5>';
    h += '<table class="bt-table"><thead><tr><th>期号</th><th>断行</th><th>断列</th></tr></thead><tbody>';
    for (var i = d.periods.length-1; i >= Math.max(0, d.periods.length-30); i--) {
      h += '<tr><td>'+d.periods[i]+'</td><td style="color:#cc4444;">'+d.break_rows[i]+'</td><td style="color:#3366cc;">'+d.break_cols[i]+'</td></tr>';
    }
    h += '</tbody></table></div>';

    h += '<div id="zbResult"></div></div>';
    el.innerHTML = h;
  }).catch(function(){ el.innerHTML = '<div style="color:#EF4444;padding:16px;">加载失败</div>'; });
};

ZB.ALL_CODES = ["000","001","002","003","004","005","006","012","013","014","015","016","023","024","025","026","034","035","036","045","046","056","123","124","125","126","134","135","136","145","146","156","234","235","236","245","246","256","345","346","356","456"];

ZB.filter = function() {
  var st = document.getElementById('zbStatus'); if(st) st.textContent = '过滤中...';
  var rows = document.getElementById('zbBreakRows').value;
  var cols = document.getElementById('zbBreakCols').value;
  fetch('/api/zone-break/filter', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({break_rows:rows, break_cols:cols})})
    .then(function(r){return r.json()}).then(function(d){
      if (d.ok) {
        if (st) st.textContent = d.tickets.length+'注, ¥'+d.cost_rmb;
        var re = document.getElementById('zbResult');
        if (re) {
          var info = d.filter_log ? '<div style="font-size:10px;color:#FFFFFF;margin-bottom:6px;">排除号码: '+d.filter_log.excluded_numbers.join(' ')+'</div>' : '';
          var h = info+'<div style="max-height:400px;overflow-y:auto;"><table class="bt-table"><thead><tr><th>#</th><th>红球</th><th>蓝球</th></tr></thead><tbody>';
          d.tickets.forEach(function(t,i){
            h += '<tr><td>'+(i+1)+'</td><td style="color:#cc4444;">'+t.reds.join(' ')+'</td><td style="color:#3366cc;">'+String(t.blue).padStart(2,'0')+'</td></tr>';
          });
          h += '</tbody></table></div>'; re.innerHTML = h;
        }
      } else { if(st) st.textContent = d.msg||'失败'; }
    }).catch(function(){ if(st) st.textContent = '请求失败'; });
};

// Panel listener
var _zbp = document.getElementById('zoneBreakPanel');
if (_zbp) { _zbp.addEventListener('panel-shown', function(){ ZB.render('zoneBreakContent'); }); }
