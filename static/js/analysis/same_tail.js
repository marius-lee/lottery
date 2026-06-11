/** 同尾分析 */
import { store } from '../store.js';

export function computeSameTailScores() {
  const tailPairCounts = {};
  for (let t = 0; t <= 9; t++) tailPairCounts[t] = 0;
  store.DATA.forEach(row => {
    const tails = {};
    for (let j = 1; j <= 6; j++) {
      const tail = row[j] % 10;
      tails[tail] = (tails[tail] || 0) + 1;
    }
    for (const t in tails) {
      if (tails[t] >= 2) tailPairCounts[t]++;
    }
  });
  const total = store.DATA.length || 1;
  const scores = {};
  for (let i = 1; i <= 33; i++) {
    scores[i] = tailPairCounts[i % 10] / total;
  }
  return { scores, tailPairCounts };
}
