/** 均匀策略 — 6个区间各取1个（覆盖整个号码空间） */
import { Strategy } from './base.js';

export class UniformStrategy extends Strategy {
  constructor() { super(); this.name = '均匀'; }

  // 覆盖整个 predict() — 不用权重抽取，而是分段随机
  predict() {
    const segments = [[1, 5], [6, 11], [12, 16], [17, 22], [23, 27], [28, 33]];
    const reds = segments.map(([a, b]) => a + Math.floor(Math.random() * (b - a + 1)));
    reds.sort((a, b) => a - b);
    const blue = Math.floor(Math.random() * 16) + 1;
    return { name: this.name, reds, blue };
  }

  buildRedWeights() { return {}; }  // Not used
  buildBlueWeights() { return {}; }  // Not used
}
