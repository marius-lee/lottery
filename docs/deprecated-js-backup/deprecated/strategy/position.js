/** 位置策略 — 每个位置独立建模 */
import { Strategy } from './base.js';
import { pickOne } from '../utils.js';
import { store } from '../store.js';

export class PositionStrategy extends Strategy {
  constructor() { super(); this.name = '位置'; }

  predict() {
    const posFreq = [{}, {}, {}, {}, {}, {}];
    store.DATA.forEach(row => {
      const s = row.slice(1, 7).sort((a, b) => a - b);
      for (let p = 0; p < 6; p++) {
        posFreq[p][s[p]] = (posFreq[p][s[p]] || 0) + 1;
      }
    });

    const reds = new Set();
    for (let p = 0; p < 6; p++) {
      const w = {};
      const minOk = Math.min(...Object.keys(posFreq[p]).map(Number));
      const maxOk = Math.max(...Object.keys(posFreq[p]).map(Number));
      for (let n = minOk; n <= maxOk; n++) {
        if (!reds.has(n)) w[n] = (posFreq[p][n] || 0) + 1;
      }
      reds.add(pickOne(w));
    }

    // Blue: Markov transition
    const lastBlue = store.DATA[store.DATA.length - 1][7];
    const bTrans = {};
    for (let d = 1; d < store.DATA.length; d++) {
      if (store.DATA[d - 1][7] === lastBlue) {
        bTrans[store.DATA[d][7]] = (bTrans[store.DATA[d][7]] || 0) + 1;
      }
    }
    const bw = {};
    for (let n = 1; n <= 16; n++) bw[n] = (bTrans[n] || 0) + 1;

    return {
      name: this.name,
      reds: [...reds].sort((a, b) => a - b),
      blue: pickOne(bw),
    };
  }

  buildRedWeights() { return {}; }
  buildBlueWeights() { return {}; }
}
