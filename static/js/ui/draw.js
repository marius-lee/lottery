/** 主抽取 UI — 均匀随机采样 + 运气规则

 *  生成号码:  硬过滤 → [软过滤] → 池采样 → [运气偏置]
 *  幸运开奖:  位置加权独立抽号 → 硬过滤 → 去重
 */
import { store } from '../store.js';
import { playTick } from '../audio.js';

const delay = ms => new Promise(r => setTimeout(r, ms));

function createBall(num, type, cls) {
  const el = document.createElement('div');
  el.className = `ball ${type} ${cls || ''}`;
  el.textContent = String(num).padStart(2, '0');
  return el;
}

function createPlaceholder() {
  const el = document.createElement('div');
  el.className = 'ball placeholder';
  el.textContent = '?';
  return el;
}

function stageEl() { return document.getElementById('stage'); }
function progressEl() { return document.getElementById('drawProgress'); }
function progressBarEl() { return document.getElementById('progressBar'); }
function drawBtn() { return document.getElementById('drawBtn'); }
function saveBtn() { return document.getElementById('saveBtn'); }
function restoreButtons() {
  const db = drawBtn(), sb = saveBtn();
  if (db) db.disabled = false;
  if (sb) sb.disabled = false;
}

function disableButtons() {
  const db = drawBtn(), sb = saveBtn();
  if (db) db.disabled = true;
  if (sb) sb.disabled = true;
}

function updateProgress(text, pct) {
  const el = progressEl(), bar = progressBarEl();
  if (el) el.textContent = text;
  if (bar) bar.style.width = (pct || 0) + '%';
}

function clearProgress() {
  const el = progressEl(), bar = progressBarEl();
  if (el) el.textContent = '';
  if (bar) bar.style.width = '0%';
}

export function renderPlaceholders() {
  const stage = stageEl();
  stage.innerHTML = '';
  for (let d = 0; d < store.drawCount; d++) {
    const row = document.createElement('div');
    row.className = 'draw-row';
    row.id = 'row-' + d;
    const label = document.createElement('span');
    label.className = 'draw-label';
    label.textContent = '#' + (d + 1);
    row.appendChild(label);
    for (let i = 0; i < 6; i++) row.appendChild(createPlaceholder());
    row.appendChild(createPlaceholder());
    stage.appendChild(row);
  }
}

// ============ 选项 ============

export function updateAdvFilter() {
  store.useAdvFilter = document.getElementById('advFilterToggle').checked;
}

export function updateDiversity() {
  store.useDiversity = document.getElementById('diversityToggle').checked;
}

export function updateGreedy() {
  store.useGreedy = document.getElementById('greedyToggle').checked;
  if (store.useGreedy) {
    document.getElementById('diversityToggle').checked = true;
    store.useDiversity = true;
  }
}






export function updateBacktest() {
  store.useBacktest = document.getElementById('backtestToggle').checked;
}




export function updateTwelveValue() {
  store.useTwelveValue = document.getElementById('twelveValueToggle').checked;
}
export function updateEightValue() {
  store.useEightValue = document.getElementById('eightValueToggle').checked;
}

export function updateGridSelection() {
  store.useGridSelection = document.getElementById('gridSelectionToggle').checked;
}
export function updateFivePeriod() {
  store.useFivePeriod = document.getElementById('fivePeriodToggle').checked;
}
export function updatePatternRules() {
  store.usePatternRules = document.getElementById('patternRulesToggle').checked;
}

export function updateFreqBlue() {
  var checked = document.getElementById('freqBlueToggle').checked;
  store.useFreqBlue = checked;
  store.blueMode = document.querySelector("input[name=blueMode]:checked")?.value || "freq";
  // 联动蓝球选号方法radio: 勾选→可用, 未勾选→灰掉
  var lblFreq = document.getElementById('lblBlueFreq');
  var lblEntropy = document.getElementById('lblBlueEntropy');
  var radios = document.querySelectorAll('input[name="blueMode"]');
  for (var i = 0; i < radios.length; i++) {
    radios[i].disabled = !checked;
  }
  if (lblFreq) {
    lblFreq.style.opacity = checked ? '1' : '0.4';
    lblFreq.style.cursor = checked ? 'pointer' : 'not-allowed';
  }
  if (lblEntropy) {
    lblEntropy.style.opacity = checked ? '1' : '0.4';
    lblEntropy.style.cursor = checked ? 'pointer' : 'not-allowed';
  }
}

export function updateBlueMode() {
  // 仅在蓝球缩小池勾选时更新, 否则保持默认
  if (store.useFreqBlue) {
    store.blueMode = document.querySelector("input[name=blueMode]:checked")?.value || "freq";
  }
}

export function updateRedMode() {
  store.redMode = document.querySelector("input[name=redMode]:checked")?.value || "pool";
}

export function updateTMode() {
  store.t = parseInt(document.querySelector("input[name=tMode]:checked")?.value || "4");
  var desc = document.getElementById('tModeDesc');
  if (desc) {
    if (store.t === 5) {
      desc.textContent = '保证至少5个红球命中（三等奖）| 成本约为 t=4 的 4-6 倍 | 仅支持贪心覆盖（La Jolla 无 C(v,6,5) 完整表）';
    } else {
      desc.textContent = '保证至少4个红球命中（四等奖）| 注数取决于热号池大小 v | La Jolla 精确表 + 贪心覆盖';
    }
  }
}

export function updateMultiPeriod() {
  store.multiPeriod = document.getElementById('multiPeriodToggle').checked;
}

export function toggleBanditMode() {
  store.strategyMode = store.strategyMode === 'bandit' ? null : 'bandit';
  var btn = document.getElementById('banditToggle');
  if (btn) {
    btn.classList.toggle('active', store.strategyMode === 'bandit');
    btn.querySelector('.btn-icon').textContent = store.strategyMode === 'bandit' ? '🎰' : '🎲';
  }
}


// ============ API 调用 ============

async function drawTickets(luckMode) {
  // luckMode: '' (无), '&luck=1' (blend), '&luck=2' (pure)
  updateProgress('生成中...', 20);
  const advFilter = store.useAdvFilter && luckMode !== '&luck=2' ? '&adv_filter=1' : '';
  const diversity = store.useGreedy && luckMode !== '&luck=2'
    ? '&max_overlap=2&div=1'
    : (store.useDiversity && luckMode !== '&luck=2' ? '&max_overlap=2' : '');
  const backtest = store.useBacktest && luckMode !== '&luck=2' ? '&backtest=1' : '';
  const fivePeriod = store.useFivePeriod ? '&five_period=1' : '';
  const patternRules = store.usePatternRules ? '&pattern_rules=1' : '';
  const author = store.currentAuthor ? '&author=' + store.currentAuthor : '';
  let data;
  try {
    const freqBlue = store.useFreqBlue ? '&freq_blue=1' : '';
    const blueModeParam = '&blue_mode=' + (store.blueMode || 'freq');
    const redModeParam = '&red_mode=' + (store.redMode || 'pool');
    const strategyParam = store.strategyMode ? '&strategy=' + store.strategyMode : '';
    const r = await fetch('/api/micro/tickets?n=' + store.drawCount + '&t=' + (store.t || 4) + (store.multiPeriod ? '&multi_period=1' : '') + advFilter + diversity + backtest + freqBlue + blueModeParam + redModeParam + strategyParam + fivePeriod + patternRules + author + luckMode);
    data = await r.json();
  } catch (e) {
    stageEl().innerHTML = '<div style="color:#cc3333;padding:20px;">生成失败，请重试</div>';
    clearProgress();
    restoreButtons();
    return;
  }
  if (!data || !data.ok || !data.tickets || data.tickets.length === 0) {
    stageEl().innerHTML = '<div style="color:#cc3333;padding:20px;">生成失败</div>';
    clearProgress();
    restoreButtons();
    return;
  }

  const apiTickets = data.tickets.slice(0, store.drawCount);
  const results = apiTickets.map(t => ({ reds: t.reds, blue: t.blue, score: 5, fails: {} }));

  store.lastDrawResults = results;
  const stage = stageEl();
  stage.innerHTML = '';

  // 信息栏
  const infoRow = document.createElement('div');
  infoRow.style.cssText = 'font-size:11px;margin-bottom:8px;text-align:center;padding:4px 8px;border-radius:6px;';

  infoRow.style.background = 'rgba(255,255,255,0.06)';
  infoRow.style.color = '#FFFFFF';
  const algo = data.algorithm || '';

  if (data.luck_mode === 'pure') {
    infoRow.style.background = '#2d1b0e';
    infoRow.style.color = '#fbbf24';
    infoRow.innerHTML = `🧿 运气开奖 · ${algo} · 近${data.luck_window || 10}期位置加权`;
  } else {
    const rs = data.rule_status || {};
    const h2 = rs.h2_arithmetic?.excluded || 0;
    const h3 = rs.h3_historical?.excluded || 0;
    const softTag = data.soft_filter
      ? ` + 高级过滤 排除${(data.soft_excluded||0).toLocaleString()}`
      : '';
    const poolStr = data.pool_valid_reds != null
      ? ` → 有效池 ${data.pool_valid_reds.toLocaleString()} 红球`
      : '';
    const bluePool = data.blue_pool_size != null ? ` | 蓝球池${data.blue_pool_size}个` : '';
    const blueMethod = data.blue_method ? ` · ${data.blue_method}` : '';
    infoRow.innerHTML = `硬过滤[排除${h2+h3}组合]${softTag}${poolStr}${bluePool}${blueMethod} · ${algo}`;
  }
  stage.appendChild(infoRow);

  // 票面
  for (let d = 0; d < results.length; d++) {
    const row = document.createElement('div');
    row.className = 'draw-row';
    const label = document.createElement('span');
    label.className = 'draw-label';
    label.textContent = '#' + (d + 1);
    row.appendChild(label);
    results[d].reds.forEach(n => row.appendChild(createBall(n, 'red', 'landed')));
    row.appendChild(createBall(results[d].blue, 'blue', 'landed'));
    stage.appendChild(row);
  }

  // 信号联动: 若后端SPRT自动切换了红球模式, 更新界面radio
  if (data.effective_red_mode) {
    var radio = document.querySelector('input[name="redMode"][value="' + data.effective_red_mode + '"]');
    if (radio && !radio.checked) {
      radio.checked = true;
      updateRedMode();
    }
  }
  // Kelly 自动闭环: 自动模式下, 后端推荐注数≠当前注数时更新
  var autoLabel = document.getElementById('autoKellyLabel');
  if (data.kelly_recommended_n != null && store.useAutoKelly) {
    store.drawCount = data.kelly_recommended_n;
    var drawCountEl = document.getElementById('drawCount');
    if (drawCountEl) {
      drawCountEl.value = String(data.kelly_recommended_n);
      updateDrawCount();
    }
  }
  // 更新监控条的Kelly建议 (同步monitor bar)
  if (autoLabel && data.kelly_recommended_n != null) {
    autoLabel.textContent = store.useAutoKelly ? '自动(' + data.kelly_recommended_n + '注)' : '手动';
  }

  updateProgress('完成', 100);
  await delay(300);
  clearProgress();
  restoreButtons();
}

// ============ 入口点 ============

export async function proceedWithDraw() {
  disableButtons();
  store.lastDrawResults = null;
  renderPlaceholders();

  // 闭环: Auto-Kelly 模式下先查询监控推荐注数
  var originalN = store.drawCount;
  if (store.useAutoKelly) {
    try {
      var resp = await fetch('/api/monitor?n=' + originalN + '&v=15&blue=6');
      var d = await resp.json();
      if (d && d.ok) {
        var rec = (d.status && d.status.recommended_tickets != null) ? d.status.recommended_tickets : originalN;
        if (rec !== originalN) {
          store.drawCount = Math.max(1, rec);
          renderPlaceholders();
          var msgEl = document.getElementById('dataMsg');
          if (msgEl) {
            msgEl.textContent = 'Kelly 注数调整: ' + originalN + '→' + store.drawCount;
            msgEl.style.color = '#22C55E';
            setTimeout(function() { msgEl.textContent = ''; }, 3000);
          }
        }
      }
    } catch (e) { /* 监控不可用时保持原注数 */ }
  }

  const safety = setTimeout(() => {
    restoreButtons();
    clearProgress();
  }, 30000);

  await drawTickets('').finally(() => clearTimeout(safety));

  // 出号完成后刷新监控 (SPRT/Kelly 会反映新 prediction_log 数据)
  if (store.useAutoKelly) {
    try {
      var md = await fetch('/api/monitor?n=' + store.drawCount + '&v=15&blue=6');
      if (md) {
        // refresh monitor.js cached data silently
        if (typeof window.fetchMonitor === 'function') {
          window._lastMonitorData = md;
        }
      }
    } catch(e) {}
  }
}

export function proceedWithLuckDraw() {
  disableButtons();
  store.lastDrawResults = null;
  renderPlaceholders();

  const safety = setTimeout(() => {
    restoreButtons();
    clearProgress();
  }, 30000);

  drawTickets('&luck=2').finally(() => clearTimeout(safety));
}

// ============ 微尔算法 ============

export async function startWeierDraw() {
  disableButtons();
  store.lastDrawResults = null;
  renderPlaceholders();
  updateProgress('微尔算法分析中...', 10);

  const safety = setTimeout(() => {
    restoreButtons();
    clearProgress();
  }, 60000);

  let data;
  try {
    const r = await fetch('/api/weier/generate');
    data = await r.json();
  } catch (e) {
    stageEl().innerHTML = '<div style="color:#cc3333;padding:20px;">微尔算法失败，请重试</div>';
    clearProgress(); restoreButtons(); clearTimeout(safety); return;
  }
  if (!data || !data.ok) {
    stageEl().innerHTML = `<div style="color:#cc3333;padding:20px;">${data?.msg || '生成失败'}</div>`;
    clearProgress(); restoreButtons(); clearTimeout(safety); return;
  }

  const results = data.tickets.map(t => ({ reds: t.reds, blue: t.blue, score: 5, fails: {} }));
  store.lastDrawResults = results;
  const stage = stageEl();
  stage.innerHTML = '';

  // 条件检测信息栏
  const infoRow = document.createElement('div');
  infoRow.style.cssText = 'font-size:11px;margin-bottom:8px;text-align:left;padding:8px 12px;border-radius:6px;background:rgba(5,150,105,0.1);color:#4ade80;line-height:1.6;';
  let logHtml = `<b>微尔算法 · 8步条件过滤</b> `;
  if (data.filter_log) {
    const exact = data.filter_log.exact_pool_size || '';
    logHtml += `| ${exact} → ${data.filter_log.final_count || data.tickets.length}注`;
  }
  if (data.warning) {
    logHtml += `<br><span style="color:#FBBF24;">⚠ ${data.warning}</span>`;
  }
  if (data.filter_log && data.filter_log.original_filtered_count) {
    logHtml += `<br>原过滤池${data.filter_log.original_filtered_count}注, 降级采样${data.tickets.length}注`;
  }
  infoRow.innerHTML = logHtml;
  stage.appendChild(infoRow);

  // 票面
  for (let d = 0; d < results.length; d++) {
    const row = document.createElement('div');
    row.className = 'draw-row';
    const label = document.createElement('span');
    label.className = 'draw-label';
    label.textContent = '#' + (d + 1);
    row.appendChild(label);
    results[d].reds.forEach(n => row.appendChild(createBall(n, 'red', 'landed')));
    row.appendChild(createBall(results[d].blue, 'blue', 'landed'));
    stage.appendChild(row);
  }

  updateProgress('完成', 100);
  await delay(300);
  clearProgress(); restoreButtons(); clearTimeout(safety);
}

// ============ 覆盖设计 (Tier 3) ============

export async function startCoveringDraw() {
  disableButtons();
  store.lastDrawResults = null;
  renderPlaceholders();
  updateProgress('覆盖设计优化中...', 10);

  const safety = setTimeout(() => {
    restoreButtons();
    clearProgress();
  }, 60000);

  let data;
  try {
    const n = store.drawCount >= 3 ? store.drawCount : 3;
    const r = await fetch('/api/covering-diverse?v=15&t=4&n=' + n);
    data = await r.json();
  } catch (e) {
    stageEl().innerHTML = '<div style="color:#cc3333;padding:20px;">覆盖设计生成失败，请重试</div>';
    clearProgress();
    restoreButtons();
    clearTimeout(safety);
    return;
  }

  if (!data || !data.ok || !data.tickets) {
    stageEl().innerHTML = '<div style="color:#cc3333;padding:20px;">' +
      (data?.msg || '覆盖设计生成失败') + '</div>';
    clearProgress();
    restoreButtons();
    clearTimeout(safety);
    return;
  }

  const results = data.tickets.map(t => ({ reds: t.reds, blue: t.blue, score: 5, fails: {} }));
  store.lastDrawResults = results;
  const stage = stageEl();
  stage.innerHTML = '';

  // 覆盖元数据栏
  const infoRow = document.createElement('div');
  infoRow.style.cssText = 'font-size:11px;margin-bottom:8px;text-align:center;padding:4px 8px;border-radius:6px;background:rgba(34,197,94,0.1);color:#4ade80;';
  if (data.covering) {
    const cov = data.covering;
    infoRow.innerHTML = `覆盖设计(v=${cov.v},t=${cov.t}) · 覆盖率≥${(cov.estimated_coverage_pct||0).toFixed(0)}% · ${cov.guarantee || ''}`;
  } else {
    infoRow.textContent = '覆盖设计';
  }
  stage.appendChild(infoRow);

  // 票面
  for (let d = 0; d < results.length; d++) {
    const row = document.createElement('div');
    row.className = 'draw-row';
    const label = document.createElement('span');
    label.className = 'draw-label';
    label.textContent = '#' + (d + 1);
    row.appendChild(label);
    results[d].reds.forEach(n => row.appendChild(createBall(n, 'red', 'landed')));
    row.appendChild(createBall(results[d].blue, 'blue', 'landed'));
    stage.appendChild(row);
  }

  updateProgress('完成', 100);
  await delay(300);
  clearProgress();
  restoreButtons();
  clearTimeout(safety);
}

// ============ 张委铭算法 ============

export async function startZhangDraw() {
  disableButtons();
  store.lastDrawResults = null;
  renderPlaceholders();
  updateProgress('张委铭算法分析中...', 10);

  const safety = setTimeout(() => {
    restoreButtons();
    clearProgress();
  }, 60000);

  // 决定调用哪个端点
  let endpoint;
  if (store.useGridSelection) {
    endpoint = '/api/zhang/grid?n=' + store.drawCount;
  } else if (store.useTwelveValue && store.useEightValue) {
    endpoint = '/api/zhang/combined?n=' + store.drawCount;
  } else if (store.useTwelveValue) {
    endpoint = '/api/zhang/twelve-value?n=' + store.drawCount;
  } else if (store.useEightValue) {
    endpoint = '/api/zhang/eight-value?n=' + store.drawCount;
  } else {
    stageEl().innerHTML = '<div style="color:#FBBF24;padding:20px;">请先在策略面板勾选张委铭选项（十二值红球/八值蓝球/行列网格）</div>';
    clearProgress(); restoreButtons(); clearTimeout(safety); return;
  }

  let data;
  try {
    const r = await fetch(endpoint);
    data = await r.json();
  } catch (e) {
    stageEl().innerHTML = '<div style="color:#cc3333;padding:20px;">张委铭算法失败，请重试</div>';
    clearProgress(); restoreButtons(); clearTimeout(safety); return;
  }
  if (!data || !data.ok) {
    stageEl().innerHTML = `<div style="color:#cc3333;padding:20px;">${data?.msg || '生成失败'}</div>`;
    clearProgress(); restoreButtons(); clearTimeout(safety); return;
  }

  const results = data.tickets.map(t => ({ reds: t.reds, blue: t.blue, score: 5, fails: {} }));
  store.lastDrawResults = results;
  const stage = stageEl();
  stage.innerHTML = '';

  // 信息栏
  const infoRow = document.createElement('div');
  infoRow.style.cssText = 'font-size:11px;margin-bottom:8px;text-align:left;padding:8px 12px;border-radius:6px;background:rgba(168,85,247,0.1);color:#A78BFA;line-height:1.6;';

  let infoHtml = '<b>张委铭 · ' + (data.algorithm || '') + '</b><br>';

  if (data.twelve_value) {
    const tv = data.twelve_value;
    infoHtml += `十二值红球: ${tv.candidate_count}个候选 [${(tv.candidates||[]).slice(0,12).join(' ')}${tv.candidate_count>12?'...':''}]<br>`;
    infoHtml += `策略: P1-2→前8, P3-4→池+邻, P5→避池选邻, P6→30-33<br>`;
    infoHtml += `<span style="color:#FFFFFF;">原书1767期: avg${tv.stats.avg_hits_per_period}个/期, ≥4占${tv.stats.pct_ge_4}%</span><br>`;
  }
  if (data.grid) {
    const g = data.grid;
    infoHtml += `行列网格: ${g.mode_desc}<br>`;
    infoHtml += `断行: [${(g.break_rows||[]).join(',')||'无'}] 断列: [${(g.break_cols||[]).join(',')}]<br>`;
    infoHtml += `<span style="color:#FFFFFF;">剩余${g.remaining_count}个号码: ${(g.remaining_numbers||[]).slice(0,15).join(' ')}${g.remaining_count>15?'...':''}</span><br>`;
  }
  if (data.eight_value) {
    const ev = data.eight_value;
    infoHtml += `八值蓝球: ${ev.candidate_count}个候选 [${(ev.candidates||[]).join(' ')}]<br>`;
    infoHtml += `<span style="color:#FBBF24;">${ev.use_recommendation} (连续错${ev.consecutive_errors}次)</span> `;
    infoHtml += `<span style="color:#FFFFFF;">| 原书: ${ev.stats.success_rate_pct}%成功率 vs 理论${ev.stats.theoretical_rate_pct}%</span><br>`;
  }

  infoRow.innerHTML = infoHtml;
  stage.appendChild(infoRow);

  // 票面
  for (let d = 0; d < results.length; d++) {
    const row = document.createElement('div');
    row.className = 'draw-row';
    const label = document.createElement('span');
    label.className = 'draw-label';
    label.textContent = '#' + (d + 1);
    row.appendChild(label);
    results[d].reds.forEach(n => row.appendChild(createBall(n, 'red', 'landed')));
    row.appendChild(createBall(results[d].blue, 'blue', 'landed'));
    stage.appendChild(row);
  }

  updateProgress('完成', 100);
  await delay(300);
  clearProgress(); restoreButtons(); clearTimeout(safety);
}

// ═══ 偏差信号面板 ═══
export function fetchBiasStatus() {
  fetch('/api/bias/status')
    .then(r => r.json())
    .then(d => {
      if (!d.ok) return;
      var dot = document.getElementById('biasSignalDot');
      var label = document.getElementById('biasSignalLabel');
      var reason = document.getElementById('biasSignalReason');
      var sel = document.getElementById('vOverride');
      
      // Update dot class
      dot.className = 'bias-dot ' + (d.signal_level || 'none');
      
      // Update label
      var labels = { strong: '强信号', moderate: '中等信号', weak: '弱信号', none: '无信号' };
      label.textContent = '偏差: ' + (labels[d.signal_level] || '检测中...');
      
      // Update reasoning
      reason.textContent = d.reasoning || '';
      
      // Update v selector
      if (d.v_options && sel) {
        sel.style.display = 'inline-block';
        sel.querySelectorAll('option').forEach(function(opt){
          opt.removeAttribute('selected');
        });
        d.v_options.forEach(function(o){
          var el = sel.querySelector('option[value="' + o.v + '"]');
          if (!el) {
            el = document.createElement('option');
            el.value = o.v;
            el.textContent = o.label;
            sel.appendChild(el);
          }
          if (o.active) el.selected = true;
        });
      }
    })
    .catch(function(){});
}

export function updateVOverride() {
  var sel = document.getElementById('vOverride');
  if (!sel) return;
  var v = parseInt(sel.value);
  if (v === 0) {
    window.store.vOverride = null;
  } else {
    window.store.vOverride = v;
  }
}
