/** 指数优化策略 — EWMA λ=0.85 [RiskMetrics 1996] */
import { Strategy } from './base.js';
import { store } from '../store.js';
import { EWMA_LAMBDA, TOTAL_RED, TOTAL_BLUE, PICK_RED } from '../constants.js';

export class ExponentialStrategy extends Strategy {
  constructor() { super(); this.name = '指数优化'; }

  buildRedWeights() {
    const total = store.DATA.length;
    const lambda = EWMA_LAMBDA;
    const ewma = {};
    for (let n = 1; n <= TOTAL_RED; n++) ewma[n] = 0;
    let weightSum = 0;
    for (let d = total - 1; d >= 0; d--) {
      const w = Math.pow(lambda, total - 1 - d);
      weightSum += w;
      const reds = store.DATA[d].slice(1, 7);
      for (let j = 0; j < PICK_RED; j++) ewma[reds[j]] += w;
    }
    const result = {};
    for (let n = 1; n <= TOTAL_RED; n++) result[n] = ewma[n] / weightSum * 10 + 0.5;
    return result;
  }

  buildBlueWeights() {
    const total = store.DATA.length;
    const lambda = EWMA_LAMBDA;
    const bewma = {};
    for (let n = 1; n <= TOTAL_BLUE; n++) bewma[n] = 0;
    let weightSum = 0;
    for (let d = total - 1; d >= 0; d--) {
      const w = Math.pow(lambda, total - 1 - d);
      weightSum += w;
      bewma[store.DATA[d][7]] += w;
    }
    const result = {};
    for (let n = 1; n <= TOTAL_BLUE; n++) result[n] = bewma[n] / weightSum * 5 + 0.5;
    return result;
  }
}
