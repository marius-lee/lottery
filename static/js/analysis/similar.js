/** 相似期匹配 */
import { store } from '../store.js';

export function periodSimilarity(idx1, idx2) {
  const r1 = store.DATA[idx1].slice(1, 7);
  const r2 = store.DATA[idx2].slice(1, 7);
  const set = new Set(r1);
  return r2.filter(n => set.has(n)).length;
}

export function findSimilarPeriods(count) {
  if (store.DATA.length < 3) return [];
  const lastIdx = store.DATA.length - 1;
  const sims = [];
  for (let i = 0; i < lastIdx; i++) {
    sims.push({ idx: i, sim: periodSimilarity(i, lastIdx) });
  }
  sims.sort((a, b) => b.sim - a.sim);
  return sims.slice(0, count)
    .filter(s => s.idx + 1 < store.DATA.length)
    .map(s => ({
      similarPeriod: store.DATA[s.idx],
      nextPeriod: store.DATA[s.idx + 1],
      similarity: s.sim,
    }));
}
