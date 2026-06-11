/** 龙头凤尾分析 */
import { store } from '../store.js';

export function computeDragonPhoenix(reds) {
  const s = [...reds].sort((a, b) => a - b);
  return { dragon: s[0], phoenix: s[5] };
}

export function computeHistoricalDragonPhoenix() {
  const dragons = {}, phoenixes = {};
  for (let i = 1; i <= 33; i++) { dragons[i] = 0; phoenixes[i] = 0; }
  store.DATA.forEach(row => {
    const dp = computeDragonPhoenix(row.slice(1, 7));
    dragons[dp.dragon]++;
    phoenixes[dp.phoenix]++;
  });
  return { dragons, phoenixes };
}
