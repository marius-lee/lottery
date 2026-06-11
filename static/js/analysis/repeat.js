/** 重号分析 */
import { store } from '../store.js';

export function computeRepeatScores() {
  const scores = {};
  for (let i = 1; i <= 33; i++) scores[i] = 0;
  if (store.DATA.length < 2) return { scores, avgRepeat: 0 };

  let totalRepeats = 0;
  const draws = store.DATA.length - 1;
  for (let d = 1; d < store.DATA.length; d++) {
    const prev = store.DATA[d - 1].slice(1, 7);
    const curr = store.DATA[d].slice(1, 7);
    curr.forEach(n => { if (prev.includes(n)) totalRepeats++; });
  }
  const avgRepeat = totalRepeats / draws;
  const lastReds = store.DATA[store.DATA.length - 1].slice(1, 7);
  lastReds.forEach(n => { scores[n] = avgRepeat / 6; });
  return { scores, avgRepeat };
}
