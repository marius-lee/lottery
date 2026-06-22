/** 面板切换 — 纯 DOM 操作，各面板模块独立订阅 panel-shown 事件 */
import { store } from '../store.js';

export function togglePanel(name) {
  const panel = document.getElementById(name + 'Panel');
  const btn = document.getElementById(name + 'Toggle');
  if (!panel || !btn) return;

  if (panel.classList.contains('show')) {
    panel.classList.remove('show');
    btn.classList.remove('active');
  } else {
    panel.classList.add('show');
    btn.classList.add('active');
    panel.dispatchEvent(new CustomEvent('panel-shown'));
    if (name === 'help') panel.scrollTop = 0;
  }
}

export function resetHistoryPanels() {
  ['officialHistoryPanel', 'userHistoryPanel'].forEach(id => {
    const panel = document.getElementById(id);
    if (panel) panel.classList.remove('show2');
  });
  ['officialHistoryToggle', 'userHistoryToggle'].forEach(id => {
    const btn = document.getElementById(id);
    if (btn) { btn.classList.remove('active'); btn.textContent = btn.textContent.replace(' ▲', ''); }
  });
  const wrapper = document.getElementById('historyWrapper');
  if (wrapper) wrapper.classList.remove('show2');
}

export function toggleOfficialHistory() {
  const panel = document.getElementById('officialHistoryPanel');
  const btn = document.getElementById('officialHistoryToggle');
  const wrapper = document.getElementById('historyWrapper');
  const usrPanel = document.getElementById('userHistoryPanel');
  const usrBtn = document.getElementById('userHistoryToggle');

  if (panel.classList.contains('show2')) {
    panel.classList.remove('show2');
    btn.classList.remove('active');
    btn.textContent = '官方历史开奖号码';
    wrapper.classList.remove('show2');
  } else {
    if (usrPanel.classList.contains('show2')) {
      usrPanel.classList.remove('show2');
      usrBtn.classList.remove('active');
      usrBtn.textContent = '历史开奖号码';
    }
    let html = '';
    for (let i = store.DATA.length - 1; i >= 0; i--) {
      const row = store.DATA[i];
      const reds = row.slice(1, 7).map(n => String(n).padStart(2, '0')).join(' ');
      html += `<div class="row"><span class="pid">${row[0]}</span><span class="reds">${reds}</span><span class="blue">${String(row[7]).padStart(2, '0')}</span></div>`;
    }
    panel.innerHTML = html;
    panel.classList.add('show2');
    btn.classList.add('active');
    btn.textContent = '官方历史开奖号码 ▲';
    wrapper.classList.add('show2');
  }
}

export function toggleUserHistory() {
  const panel = document.getElementById('userHistoryPanel');
  const btn = document.getElementById('userHistoryToggle');
  const wrapper = document.getElementById('historyWrapper');
  const offPanel = document.getElementById('officialHistoryPanel');
  const offBtn = document.getElementById('officialHistoryToggle');

  if (panel.classList.contains('show2')) {
    panel.classList.remove('show2');
    btn.classList.remove('active');
    btn.textContent = '历史开奖号码';
    wrapper.classList.remove('show2');
  } else {
    if (offPanel.classList.contains('show2')) {
      offPanel.classList.remove('show2');
      offBtn.classList.remove('active');
      offBtn.textContent = '官方历史开奖号码';
    }
    fetch('/api/user-picks')
      .then(r => r.json())
      .then(json => {
        const picks = json.picks || [];
        let html = '';
        if (picks.length === 0) {
          html = '<div style="padding:10px;color:#999;">暂无保存的选号</div>';
        } else {
          picks.forEach(p => {
            const reds = [p.r1, p.r2, p.r3, p.r4, p.r5, p.r6].map(n => String(n).padStart(2, '0')).join(' ');
            html += `<div class="row"><span class="pid">${p.period}</span><span class="reds">${reds}</span><span class="blue">${String(p.blue).padStart(2, '0')}</span></div>`;
          });
        }
        panel.innerHTML = html;
      })
      .catch(() => { panel.innerHTML = '<div style="padding:10px;color:#c33;">加载失败</div>'; });
    panel.classList.add('show2');
    btn.classList.add('active');
    btn.textContent = '历史开奖号码 ▲';
    wrapper.classList.add('show2');
  }
}

export function saveCurrentDraw() {
  var merged = window._lastMergeResult;
  if (!merged || !merged.reds || !merged.blues) return;

  let maxPeriod = 0;
  store.DATA.forEach(r => { if (r[0] > maxPeriod) maxPeriod = r[0]; });
  if (maxPeriod === 0) {
    const now = new Date();
    maxPeriod = now.getFullYear() * 1000 + Math.floor((now.getMonth() + 1) * 12.75);
  }
  let period = maxPeriod + 1;
  const year = Math.floor(period / 1000);
  const seq = period % 1000;
  if (seq > 153) period = (year + 1) * 1000 + 1;

  var n = Math.min(merged.reds.length, merged.blues.length);
  var picks = [];
  for (var i=0; i<n; i++){
    picks.push({
      period, reds: merged.reds[i], blue: merged.blues[i] || merged.blues[0],
      strategy: 'manual-merge', score: 0,
    });
  }

  fetch('/api/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ picks }),
  }).catch(() => {});

  var logEntries = picks.map(function(p){ return {
    period, source: 'manual-merge',
    reds_json: JSON.stringify(p.reds), blue: p.blue,
  };});
  fetch('/api/prediction-log', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ entries: logEntries }),
  }).catch(() => {});

  const msg = document.getElementById('dataMsg');
  if (msg) {
    msg.textContent = `已保存 ${picks.length} 注 (期号 ${period})`;
    msg.style.color = '#33aa33';
  }
  if (document.getElementById('officialHistoryPanel').classList.contains('show2')) {
    document.getElementById('officialHistoryPanel').classList.remove('show2');
    toggleOfficialHistory();
  }
  setTimeout(() => { if (msg) msg.textContent = ''; }, 5000);
}
