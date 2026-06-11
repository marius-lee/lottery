/** 趋势策略 — 近期 vs 远期频率差 */
import { Strategy } from './base.js';
import { store } from '../store.js';

export class TrendStrategy extends Strategy {
  constructor() { super(); this.name = '趋势'; }

  buildRedWeights() {
    const n = Math.min(30, store.DATA.length);
    const recent = store.DATA.slice(-n);
    const older = store.DATA.slice(-2 * n, -n);
    const rf = {}, of = {}, w = {};
    for (let i = 1; i <= 33; i++) { rf[i] = 0; of[i] = 0; }
    recent.forEach(r => { for (let j = 1; j <= 6; j++) rf[r[j]]++; });
    older.forEach(r => { for (let j = 1; j <= 6; j++) of[r[j]]++; });
    for (let i = 1; i <= 33; i++) w[i] = Math.max(1, (rf[i] - of[i]) * 2 + Math.floor(Math.random() * 4) + 1);
    return w;
  }

  buildBlueWeights() {
    const n = Math.min(30, store.DATA.length);
    const recent = store.DATA.slice(-n);
    const older = store.DATA.slice(-2 * n, -n);
    const rb = {}, ob = {}, w = {};
    for (let i = 1; i <= 16; i++) { rb[i] = 0; ob[i] = 0; }
    recent.forEach(r => { rb[r[7]]++; });
    older.forEach(r => { ob[r[7]]++; });
    for (let i = 1; i <= 16; i++) w[i] = Math.max(1, (rb[i] - ob[i]) * 2 + Math.floor(Math.random() * 3) + 1);
    return w;
  }
}
