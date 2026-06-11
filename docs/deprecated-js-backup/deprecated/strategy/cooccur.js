/** 共现策略 — 基于共现矩阵的关联号选取
 *  COOCCUR_WINDOW=100: 共现统计窗口 [与 WEIGHT_LONG_WINDOW 一致]
 *  COOCCUR_MIN_COUNT=2: 近30期最少出现次数阈值 [保守, 排除单次噪声]
 */
import { Strategy } from './base.js';
import { pickOne } from '../utils.js';
import { store } from '../store.js';
import { TOTAL_RED, PICK_RED, WEIGHT_LONG_WINDOW } from '../constants.js';

const COOCCUR_MIN_COUNT = 2;
const COOCCUR_SHORT_WINDOW = 30;

export class CooccurStrategy extends Strategy {
  constructor() { super(); this.name = '共现'; }

  predict() {
    const cooc = {};
    const recent = store.DATA.slice(-WEIGHT_LONG_WINDOW);
    recent.forEach(r => {
      const reds = r.slice(1, 7).sort((a, b) => a - b);
      for (let i = 0; i < PICK_RED; i++) {
        if (!cooc[reds[i]]) cooc[reds[i]] = {};
        for (let j = 0; j < PICK_RED; j++) {
          if (i !== j) cooc[reds[i]][reds[j]] = (cooc[reds[i]][reds[j]] || 0) + 1;
        }
      }
    });

    const total = store.DATA.length;
    const shortN = Math.min(COOCCUR_SHORT_WINDOW, total);
    const hot = [];
    for (let n = 1; n <= TOTAL_RED; n++) {
      let cnt = 0;
      for (let d = total - shortN; d < total; d++) {
        if (store.DATA[d].slice(1, 7).includes(n)) cnt++;
      }
      if (cnt >= COOCCUR_MIN_COUNT) hot.push(n);
    }
    if (hot.length === 0) for (let n = 1; n <= TOTAL_RED; n++) hot.push(n);

    const seed = hot[Math.floor(Math.random() * hot.length)];
    const reds = new Set([seed]);

    while (reds.size < 6) {
      const w = {};
      for (let n = 1; n <= 33; n++) {
        if (reds.has(n)) { w[n] = 0; continue; }
        let totalCooc = 0;
        reds.forEach(r => {
          if (cooc[r] && cooc[r][n]) totalCooc += cooc[r][n];
          if (cooc[n] && cooc[n][r]) totalCooc += cooc[n][r];
        });
        w[n] = totalCooc + 1;
      }
      reds.add(pickOne(w));
    }

    const bw = {};
    for (let n = 1; n <= 16; n++) bw[n] = 1;

    return {
      name: this.name,
      reds: [...reds].sort((a, b) => a - b),
      blue: pickOne(bw),
    };
  }

  buildRedWeights() { return {}; }
  buildBlueWeights() { return {}; }
}
