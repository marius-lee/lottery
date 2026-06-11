/** 相似期策略 */
import { Strategy } from './base.js';
import { findSimilarPeriods } from '../analysis/similar.js';
import { runStrategy } from './registry.js';

export class SimilarPeriodStrategy extends Strategy {
  constructor() { super(); this.name = '相似期'; }

  predict() {
    const similar = findSimilarPeriods(10);
    if (similar.length === 0) return runStrategy('频率');

    const w = {}, bw = {};
    for (let n = 1; n <= 33; n++) w[n] = 1;
    for (let n = 1; n <= 16; n++) bw[n] = 1;

    similar.forEach(s => {
      const nextReds = s.nextPeriod.slice(1, 7);
      nextReds.forEach(n => { w[n] += s.similarity * 2; });
      bw[s.nextPeriod[7]] += s.similarity * 2;
    });

    const reds = this._pickReds(w);
    const blue = this._pickBlue(bw);
    return { name: this.name, reds, blue };
  }

  buildRedWeights() { return {}; }
  buildBlueWeights() { return {}; }
}
