/** 遗漏面板 UI */
import { store, subscribe } from '../store.js';
import { computeOmission } from '../analysis/omission.js';

function omissionClass(gap, total) {
  const r = gap / (total || 1);
  if (r < 0.03) return 'hot';
  if (r < 0.10) return 'warm';
  if (r < 0.20) return 'cool';
  return 'cold';
}

export function renderOmission() {
  const ro = computeOmission('red'), bo = computeOmission('blue'), t = store.DATA.length;
  const rr = document.getElementById('redOmission');
  const br = document.getElementById('blueOmission');
  if (!rr || !br) return;

  rr.innerHTML = '<span class="label">红球 1-33（遗漏期数）</span>';
  for (let n = 1; n <= 33; n++) {
    rr.innerHTML += `<div class="omission-cell ${omissionClass(ro[n], t)}"><span class="num">${String(n).padStart(2, '0')}</span><span class="gap">${ro[n]}</span></div>`;
  }
  br.innerHTML = '<span class="label">蓝球 1-16（遗漏期数）</span>';
  for (let n = 1; n <= 16; n++) {
    br.innerHTML += `<div class="omission-cell ${omissionClass(bo[n], t)}"><span class="num">${String(n).padStart(2, '0')}</span><span class="gap">${bo[n]}</span></div>`;
  }
}

// Auto-refresh on data change
subscribe('data-changed', () => {
  const panel = document.getElementById('omissionPanel');
  if (panel && panel.classList.contains('show')) renderOmission();
});

// Render on panel open
const omissionPanel = document.getElementById('omissionPanel');
if (omissionPanel) {
  omissionPanel.addEventListener('panel-shown', () => renderOmission());
}
