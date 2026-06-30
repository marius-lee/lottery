/** Mandel 全买覆盖面板 — V选择器 + 成本分析 + 头奖触发
 *
 *  Stefan Mandel 14次中奖策略: 选V个号码 → 全买C(V,6)×16蓝球
 *  数学: 若6红全在V中 → 必中一等奖
 */

// ═══════════════════════════════════════════════════════════════
// API
// ═══════════════════════════════════════════════════════════════

async function loadMandelConfig() {
  const tbody = document.getElementById('mandelTbody');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="6" style="color:#FBBF24;">加载中...</td></tr>';

  try {
    const r = await fetch('/api/mandel/config');
    const d = await r.json();
    if (!d.ok) { tbody.innerHTML = '<tr><td colspan="6" style="color:#EF4444;">加载失败</td></tr>'; return; }

    let html = '';
    d.summary.forEach(function(row) {
      const cls = row.v <= 12 ? 'style="color:#22C55E;"' : 'style="color:#FBBF24;"';
      html += '<tr>' +
        '<td><b>' + row.v + '</b></td>' +
        '<td>' + row.total_combos.toLocaleString() + '</td>' +
        '<td>' + row.total_tickets.toLocaleString() + '</td>' +
        '<td ' + cls + '>¥' + row.cost_per_draw.toLocaleString() + '</td>' +
        '<td>' + row.p_all6_reds_pct + '%</td>' +
        '<td>' + row.expected_years + '年</td>' +
        '</tr>';
    });
    html += '<tr style="color:#FFFFFF;font-size:9px;"><td colspan="6">' +
      '保本头奖=¥3,544万 | 期望总成本=¥3,544万(与V无关) | 156期/年</td></tr>';
    tbody.innerHTML = html;
  } catch(e) {
    tbody.innerHTML = '<tr><td colspan="6" style="color:#EF4444;">请求失败</td></tr>';
  }
}

async function mandelPreview() {
  const v = parseInt(document.getElementById('mandelV').value || 12);
  const info = document.getElementById('mandelInfo');
  const sample = document.getElementById('mandelSample');
  if (!info) return;

  info.innerHTML = '<span style="color:#FBBF24;">计算中...</span>';

  try {
    const r = await fetch('/api/mandel/preview?v=' + v);
    const d = await r.json();
    if (!d.ok) { info.innerHTML = '<span style="color:#EF4444;">' + (d.msg || '失败') + '</span>'; return; }

    const c = d.config;
    const nums = d.v_numbers;
    info.innerHTML =
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 16px;font-size:11px;">' +
      '<span>C(' + v + ',6)=<b>' + c.total_combos.toLocaleString() + '</b>组合</span>' +
      '<span>×16蓝=<b>' + c.total_tickets.toLocaleString() + '</b>注</span>' +
      '<span>成本: <b style="color:#FBBF24;">¥' + c.cost_per_draw.toLocaleString() + '</b>/期</span>' +
      '<span>P(6红全在): <b>' + c.p_all6_reds_pct + '%</b></span>' +
      '<span>期望等待: <b>' + c.expected_years + '年</b></span>' +
      '<span>(' + c.expected_draws + '期)</span>' +
      '<span style="grid-column:1/3;margin-top:4px;">选号(' + v + '个): <span style="color:#22C55E;font-family:monospace;">' +
      nums.join(' ') + '</span></span>' +
      '</div>' +
      '<div style="margin-top:6px;padding:6px 8px;border-radius:4px;background:rgba(239,68,68,0.08);font-size:10px;color:#FCA5A5;line-height:1.4;">' +
      d.warning +
      '</div>';

    // Show sample tickets
    if (sample && d.sample_tickets) {
      let html = '';
      d.sample_tickets.slice(0, 3).forEach(function(t, i) {
        html += '<div style="display:flex;align-items:center;gap:4px;margin-bottom:3px;">' +
          '<span style="color:#FFFFFF;font-size:10px;">#' + (i+1) + '</span>';
        t.reds.forEach(function(rn) {
          html += '<span class="ball red" style="display:inline-flex;width:20px;height:20px;font-size:9px;">' +
            String(rn).padStart(2,'0') + '</span>';
        });
        html += '<span class="ball blue" style="display:inline-flex;width:20px;height:20px;font-size:9px;">' +
          String(t.blue).padStart(2,'0') + '</span>';
        html += '</div>';
      });
      html += '<div style="font-size:9px;color:#FFFFFF;margin-top:2px;">... 共 ' + c.total_tickets.toLocaleString() + ' 注 (全买)</div>';
      sample.innerHTML = html;
    }
  } catch(e) {
    info.innerHTML = '<span style="color:#EF4444;">请求失败</span>';
  }
}

async function checkJackpot() {
  const el = document.getElementById('jackpotStatus');
  if (!el) return;
  el.innerHTML = '<span style="color:#FBBF24;">拉取中...</span>';

  try {
    const r = await fetch('/api/mandel/jackpot');
    const d = await r.json();
    if (!d.ok) { el.innerHTML = '<span style="color:#EF4444;">' + (d.msg || '失败') + '</span>'; return; }

    const cls = d.jackpot >= d.breakeven_jackpot ? '#22C55E' : '#FBBF24';
    let html = '<div>头奖: <b style="color:' + cls + ';">' + d.jackpot_wan + '万</b> ' + d.verdict + '</div>';
    html += '<div style="margin-top:4px;font-size:10px;">';
    d.evaluations.forEach(function(e) {
      const ec = e.trigger ? '#22C55E' : '#EF4444';
      html += '<span style="margin-right:10px;">V=' + e.v + ': <span style="color:' + ec + ';">EV/成本=' + e.ev_ratio.toFixed(2) + '</span></span>';
    });
    html += '</div>';
    el.innerHTML = html;
  } catch(e) {
    el.innerHTML = '<span style="color:#EF4444;">网络请求失败</span>';
  }
}

// ═══════════════════════════════════════════════════════════════
// Init
// ═══════════════════════════════════════════════════════════════

function initMandelPanel() {
  loadMandelConfig();
  mandelPreview();

  // V slider change
  const slider = document.getElementById('mandelV');
  if (slider) {
    slider.addEventListener('input', function() {
      document.getElementById('mandelVLabel').textContent = 'V=' + this.value;
      mandelPreview();
    });
  }

  // Method selector
  const method = document.getElementById('mandelMethod');
  if (method) {
    method.addEventListener('change', function() { mandelPreview(); });
  }
}

// Panel shown
const mandelPanel = document.getElementById('mandelPanel');
if (mandelPanel) {
  mandelPanel.addEventListener('panel-shown', function() {
    initMandelPanel();
  });
}

// Expose
window.mandelPreview = mandelPreview;
window.checkJackpot = checkJackpot;
window.loadMandelConfig = loadMandelConfig;
