/** 温度策略 — 升温号码优先
 *  TEMP_WINDOW=30: 对比窗口 [倪大成, 约2.5个月]
 *  TEMP_SCALE=0.5: 趋势信号缩放 [趋势 ∈ [-1,1] → 权重 ∈ [0.5, 1.5]]
 */
import { Strategy } from './base.js';
import { store } from '../store.js';
import { TOTAL_RED, TOTAL_BLUE, PICK_RED } from '../constants.js';

const TEMP_WINDOW = 30;
const TEMP_SCALE = 0.5;

export class TemperatureStrategy extends Strategy {
  constructor() { super(); this.name = '温度'; }

  buildRedWeights() {
    const n = Math.min(TEMP_WINDOW, store.DATA.length);
    const recent = store.DATA.slice(-n);
    const older = store.DATA.slice(-2 * n, -n);
    if (older.length === 0) {
      const f = {};
      recent.forEach(r => { for (let j = 1; j <= PICK_RED; j++) f[r[j]] = (f[r[j]] || 0) + 1; });
      return f;
    }
    const rf = {}, of = {}, w = {};
    for (let i = 1; i <= TOTAL_RED; i++) { rf[i] = 0; of[i] = 0; }
    recent.forEach(r => { for (let j = 1; j <= PICK_RED; j++) rf[r[j]]++; });
    older.forEach(r => { for (let j = 1; j <= PICK_RED; j++) of[r[j]]++; });
    for (let i = 1; i <= TOTAL_RED; i++) {
      const temp = rf[i] - of[i];
      w[i] = Math.max(TEMP_SCALE, 1 + temp * TEMP_SCALE);
    }
    return w;
  }

  buildBlueWeights() {
    const n = Math.min(TEMP_WINDOW, store.DATA.length);
    const recent = store.DATA.slice(-n);
    const older = store.DATA.slice(-2 * n, -n);
    const rb = {}, ob = {}, w = {};
    for (let i = 1; i <= TOTAL_BLUE; i++) { rb[i] = 0; ob[i] = 0; }
    recent.forEach(r => { rb[r[7]]++; });
    older.forEach(r => { ob[r[7]]++; });
    for (let i = 1; i <= TOTAL_BLUE; i++) {
      const temp = rb[i] - ob[i];
      w[i] = Math.max(TEMP_SCALE, 1 + temp * TEMP_SCALE);
    }
    return w;
  }
}
