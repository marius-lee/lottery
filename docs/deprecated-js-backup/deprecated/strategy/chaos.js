/** 混沌策略 — Logistic Map 分形预测 (倪大成模型)
 *
 * Feigenbaum 常数来源:
 *   Feigenbaum, M.J. (1978) "Quantitative Universality for a Class of Nonlinear
 *   Transformations", J. Stat. Phys. 19, 25-52. https://doi.org/10.1007/BF01020332
 *   μ序列: 3.0(周期2)→3.449(周期4)→3.544(周期8)→3.570(混沌起点)
 */
import { Strategy } from './base.js';
import { store } from '../store.js';
import { runStrategy } from './registry.js';
import { CHAOS_MU_CYCLE2, CHAOS_MU_CYCLE4, CHAOS_MU_CYCLE8, CHAOS_MU_CHAOS,
         GOLDEN_RATIO } from '../constants.js';

export class ChaosStrategy extends Strategy {
  constructor() { super(); this.name = '混沌'; }

  predict() {
    if (store.DATA.length < 10) return runStrategy('频率');

    const total = store.DATA.length;
    const height = {};
    for (let n = 1; n <= 33; n++) {
      height[n] = total;
      for (let d = total - 1; d >= 0; d--) {
        const reds = store.DATA[d].slice(1, 7);
        if (reds.includes(n)) { height[n] = total - 1 - d; break; }
      }
    }

    const Hmax = total;
    const C = {};
    for (let n = 1; n <= 33; n++) C[n] = height[n] / Hmax;

    let avgHeight = 0;
    for (let n = 1; n <= 33; n++) avgHeight += height[n];
    avgHeight /= 33;
    const avgC = avgHeight / Hmax;

    // Feigenbaum μ 序列 [Feigenbaum 1978]
    let mu;
    if (avgC < 0.1) mu = CHAOS_MU_CYCLE2;
    else if (avgC < 0.15) mu = CHAOS_MU_CYCLE4;
    else if (avgC < 0.25) mu = CHAOS_MU_CYCLE8;
    else mu = CHAOS_MU_CHAOS;

    const w = {};
    for (let n = 1; n <= 33; n++) {
      const Cnext = mu * C[n] * (1 - C[n]);
      const predictedHeight = Cnext * Hmax;
      w[n] = Math.max(0.5, (total - predictedHeight) + 1);
    }

    // Blue chaos
    const blueHeight = {};
    for (let n = 1; n <= 16; n++) {
      blueHeight[n] = total;
      for (let d = total - 1; d >= 0; d--) {
        if (store.DATA[d][7] === n) { blueHeight[n] = total - 1 - d; break; }
      }
    }
    let avgBH = 0;
    for (let n = 1; n <= 16; n++) avgBH += blueHeight[n];
    avgBH /= 16;
    const bmu = (avgBH / total) < 0.1 ? 1.2 : (avgBH / total) < 0.2 ? 2.7 : 3.236;
    const bw = {};
    for (let n = 1; n <= 16; n++) {
      const bCnext = bmu * (blueHeight[n] / total) * (1 - blueHeight[n] / total);
      bw[n] = Math.max(0.5, (total - bCnext * total) + 0.5);
    }

    return {
      name: this.name,
      reds: this._pickReds(w),
      blue: this._pickBlue(bw),
    };
  }

  buildRedWeights() { return {}; }
  buildBlueWeights() { return {}; }
}
