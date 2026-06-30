/** 面板通用工具 — Factory + 共享渲染
*
*  用法: createPanel(config) — 一行创建完整面板
*  用法: showLoading(el), showError(el), renderTicketCards(tickets)
*/
window.PU = {
  BLUE: '#3B82F6',
  RED: '#EF4444',
  GRAY: '#FFFFFF',
  ERR: '#EF4444',
  WARN: '#FBBF24',
  OK: '#22C55E',
};

// ── 状态 ──
PU.showLoading = function(el, msg) {
  el.innerHTML = '<div style="color:' + PU.GRAY + ';padding:8px;">' + (msg || '加载中...') + '</div>';
};
PU.showError = function(el, msg) {
  el.innerHTML = '<div style="color:' + PU.ERR + ';padding:16px;">' + (msg || '加载失败') + '</div>';
};
PU.showWarn = function(el, msg) {
  el.innerHTML = '<div style="color:' + PU.WARN + ';padding:8px;">' + msg + '</div>';
};

// ── 格式化 ──
PU.fmtRed = function(n) { return String(n).padStart(2,'0'); };
PU.fmtBlue = function(b) { return String(b||'?').padStart(2,'0'); };
PU.fmtReds = function(reds) { return (reds||[]).map(PU.fmtRed).join(' '); };

// ── 共享票证渲染 ──
PU.renderTicketCards = function(tickets, opts) {
  opts = opts || {};
  var n = opts.max || tickets.length;
  var h = '';
  for (var i=0; i<Math.min(tickets.length, n); i++) {
    var t = tickets[i];
    h += '<div style="padding:10px 14px;border-radius:8px;background:rgba(' +
      (opts.bg || '59,130,246') + ',0.06);text-align:center;">';
    h += '<div style="font-size:16px;font-weight:700;color:' + PU.RED + ';letter-spacing:2px;">' +
      PU.fmtReds(t.reds) + '</div>';
    h += '<div style="font-size:16px;font-weight:700;color:' + PU.BLUE + ';margin-top:2px;">' +
      PU.fmtBlue(t.blue) + '</div>';
    h += '</div>';
  }
  return h;
};

// ── 简单异步draw: 一个API端点, 生成票证卡片 ──
PU.drawTickets = async function(endpoint, resultEl, opts) {
  opts = opts || {};
  var method = opts.method || 'GET';
  try {
    var r = await fetch(endpoint, { method: method });
    var data = await r.json();
  } catch(e) {
    PU.showError(resultEl, '出号失败');
    return null;
  }
  if (!data || !data.ok) {
    PU.showError(resultEl, data?.msg || '生成失败');
    return null;
  }
  return data;
};
