/** 黄金分割策略 — φ=0.618 [Euclid ~300 BCE], 1-φ=0.382 */
import { Strategy } from './base.js';
import { store } from '../store.js';
import { computeOmission } from '../analysis/omission.js';
import { pickOne } from '../utils.js';
import { GOLDEN_RATIO } from '../constants.js';

export class GoldenRatioStrategy extends Strategy {
  constructor() { super(); this.name = '黄金分割'; }

  predict() {
    const phi = 1 - 1 / GOLDEN_RATIO;  // 1/φ ≈ 0.618
    const o = computeOmission('red');
    const total = store.DATA.length;
    const hotThreshold = total * 0.03;
    const coldThreshold = total * 0.20;

    const hotNums = [], midNums = [], coldNums = [];
    for (let n = 1; n <= 33; n++) {
      if (o[n] <= hotThreshold) hotNums.push(n);
      else if (o[n] >= coldThreshold) coldNums.push(n);
      else midNums.push(n);
    }

    const fromValueZone = Math.round(6 * phi);
    const fromHot = 6 - fromValueZone;
    const reds = new Set();

    // Hot picks
    const hotPool = [...hotNums];
    for (let i = 0; i < fromHot && hotPool.length > 0; i++) {
      const idx = Math.floor(Math.random() * hotPool.length);
      reds.add(hotPool[idx]);
      hotPool.splice(idx, 1);
    }

    // Value zone picks
    const valuePool = [...midNums, ...coldNums];
    while (reds.size < 6 && valuePool.length > 0) {
      const w = {};
      valuePool.forEach(n => { if (!reds.has(n)) w[n] = (o[n] / total) * 100; });
      if (Object.keys(w).length === 0) break;
      reds.add(pickOne(w));
    }

    // Fill random if needed
    while (reds.size < 6) {
      const n = Math.floor(Math.random() * 33) + 1;
      if (!reds.has(n)) reds.add(n);
    }

    const bo = computeOmission('blue');
    const bw = {};
    for (let n = 1; n <= 16; n++) {
      bw[n] = bo[n] >= coldThreshold ? bo[n] * 3 : bo[n];
    }
    return {
      name: this.name,
      reds: [...reds].sort((a, b) => a - b),
      blue: pickOne(bw),
    };
  }

  buildRedWeights() { return {}; }
  buildBlueWeights() { return {}; }
}
