/** 012路分析 */
import { store } from '../store.js';

export function computeRoute012Dist() {
  const dist = [];
  store.DATA.forEach(row => {
    let r0 = 0, r1 = 0, r2 = 0;
    for (let j = 1; j <= 6; j++) {
      const mod = row[j] % 3;
      if (mod === 0) r0++;
      else if (mod === 1) r1++;
      else r2++;
    }
    dist.push([r0, r1, r2]);
  });

  const patternCounts = {};
  dist.forEach(d => {
    const key = d.join(':');
    patternCounts[key] = (patternCounts[key] || 0) + 1;
  });

  const total = dist.length;
  const routeScores = {};
  for (let i = 1; i <= 33; i++) {
    routeScores[i] = dist.filter(d => d[i % 3] >= 2).length / total;
  }
  return { distribution: dist, routeScores, patternCounts };
}
