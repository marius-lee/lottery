/** AC值 + 跨度分析 */
import { store } from '../store.js';

export function computeACValue(reds) {
  const diffs = {};
  for (let i = 0; i < reds.length; i++) {
    for (let j = i + 1; j < reds.length; j++) {
      diffs[Math.abs(reds[i] - reds[j])] = true;
    }
  }
  return Object.keys(diffs).length - (reds.length - 1);
}

export function computeHistoricalACRange() {
  const acValues = [];
  store.DATA.forEach(row => acValues.push(computeACValue(row.slice(1, 7))));
  const sum = acValues.reduce((s, v) => s + v, 0);
  return {
    avg: sum / acValues.length,
    min: Math.min(...acValues),
    max: Math.max(...acValues),
    all: acValues,
  };
}

export function computeSpan(reds) {
  const s = [...reds].sort((a, b) => a - b);
  return s[5] - s[0];
}

export function computeHistoricalSpanRange() {
  const spans = [];
  store.DATA.forEach(row => spans.push(computeSpan(row.slice(1, 7))));
  const sum = spans.reduce((s, v) => s + v, 0);
  return {
    avg: sum / spans.length,
    min: Math.min(...spans),
    max: Math.max(...spans),
  };
}
