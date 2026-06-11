/** 同尾策略 */
import { Strategy } from './base.js';
import { store } from '../store.js';
import { countFreq } from '../analysis/frequency.js';
import { computeOmission } from '../analysis/omission.js';
import { computeSameTailScores } from '../analysis/same_tail.js';

export class SameTailStrategy extends Strategy {
  constructor() { super(); this.name = '同尾'; }

  buildRedWeights() {
    const f = countFreq('red');
    const o = computeOmission('red');
    const tail = computeSameTailScores();
    const total = store.DATA.length;
    const w = {};
    for (let n = 1; n <= 33; n++) {
      w[n] = (f[n] / total) * 0.3 + (o[n] / total) * 0.3 + tail.scores[n] * 0.4 + 0.01;
    }
    return w;
  }

  buildBlueWeights() {
    const total = store.DATA.length || 1;
    const f = countFreq('red');
    const w = {};
    for (let n = 1; n <= 16; n++) w[n] = (f[n] || 0) / total + 0.01;
    return w;
  }
}
