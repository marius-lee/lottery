/** 马尔可夫蓝球策略 — 转移矩阵预测蓝球 */
import { Strategy } from './base.js';
import { store } from '../store.js';
import { countFreq } from '../analysis/frequency.js';

export class MarkovBlueStrategy extends Strategy {
  constructor() { super(); this.name = '马尔可夫蓝'; }

  buildRedWeights() {
    return countFreq('red');
  }

  buildBlueWeights() {
    const trans = {};
    for (let d = 1; d < store.DATA.length; d++) {
      const prev = store.DATA[d - 1][7];
      const curr = store.DATA[d][7];
      if (!trans[prev]) trans[prev] = {};
      trans[prev][curr] = (trans[prev][curr] || 0) + 1;
    }
    const lastBlue = store.DATA[store.DATA.length - 1][7];
    const w = {};
    if (trans[lastBlue]) {
      for (let n = 1; n <= 16; n++) w[n] = (trans[lastBlue][n] || 0) + 1;
    } else {
      const f = countFreq('blue');
      for (let n = 1; n <= 16; n++) w[n] = f[n];
    }
    return w;
  }
}
