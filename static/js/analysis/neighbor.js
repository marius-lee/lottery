/** 邻号分析 */
import { store } from '../store.js';

export function computeNeighborScores() {
  const scores = {};
  for (let i = 1; i <= 33; i++) scores[i] = 0;
  if (store.DATA.length < 2) return { scores, avgNeighbor: 0 };

  let totalNeighbors = 0;
  const draws = store.DATA.length - 1;
  for (let d = 1; d < store.DATA.length; d++) {
    const prev = store.DATA[d - 1].slice(1, 7);
    const curr = store.DATA[d].slice(1, 7);
    prev.forEach(n => {
      if (n > 1 && curr.includes(n - 1)) totalNeighbors++;
      if (n < 33 && curr.includes(n + 1)) totalNeighbors++;
    });
  }
  const avgNeighbor = totalNeighbors / draws;
  const lastReds = store.DATA[store.DATA.length - 1].slice(1, 7);
  lastReds.forEach(n => {
    if (n > 1) scores[n - 1] = (scores[n - 1] || 0) + avgNeighbor / 12;
    if (n < 33) scores[n + 1] = (scores[n + 1] || 0) + avgNeighbor / 12;
  });
  return { scores, avgNeighbor };
}
