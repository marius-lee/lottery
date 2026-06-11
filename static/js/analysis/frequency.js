/** 频率统计 */
import { store } from '../store.js';

export function countFreq(range) {
  const max = range === 'red' ? 33 : 16;
  const freq = {};
  for (let i = 1; i <= max; i++) freq[i] = 0;
  store.DATA.forEach(row => {
    const s = range === 'red' ? 1 : 7;
    const e = range === 'red' ? 6 : 7;
    for (let j = s; j <= e; j++) freq[row[j]]++;
  });
  return freq;
}

export function countFreqWindow(range, startIdx, endIdx) {
  const max = range === 'red' ? 33 : 16;
  const freq = {};
  for (let i = 1; i <= max; i++) freq[i] = 0;
  for (let d = startIdx; d < endIdx; d++) {
    const row = store.DATA[d];
    const s = range === 'red' ? 1 : 7;
    const e = range === 'red' ? 6 : 7;
    for (let j = s; j <= e; j++) freq[row[j]]++;
  }
  return freq;
}
