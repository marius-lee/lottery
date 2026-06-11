/** 遗漏分析 */
import { store } from '../store.js';

export function computeOmission(range) {
  const max = range === 'red' ? 33 : 16;
  const omission = {};
  const total = store.DATA.length;
  for (let i = 1; i <= max; i++) omission[i] = total;
  for (let d = total - 1; d >= 0; d--) {
    const row = store.DATA[d];
    const s = range === 'red' ? 1 : 7;
    const e = range === 'red' ? 6 : 7;
    for (let j = s; j <= e; j++) {
      const n = row[j];
      if (omission[n] === total) omission[n] = total - 1 - d;
    }
  }
  return omission;
}
