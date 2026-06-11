/** 间隔策略 — 均值回归: 当前间隔 vs 历史平均间隔
 *  INTERVAL_WEIGHT_AMP=10: 间隔吻合度放大系数 [经验, 距均值越近权重越高]
 */
import { Strategy } from './base.js';
import { store } from '../store.js';
import { TOTAL_RED, TOTAL_BLUE, PICK_RED } from '../constants.js';

const INTERVAL_WEIGHT_AMP = 10;

export class IntervalStrategy extends Strategy {
  constructor() { super(); this.name = '间隔'; }

  buildRedWeights() {
    const intervals = {};
    for (let n = 1; n <= TOTAL_RED; n++) intervals[n] = [];
    store.DATA.forEach((row, d) => {
      for (let j = 1; j <= PICK_RED; j++) intervals[row[j]].push(d);
    });
    const avgIntervals = {};
    for (let n = 1; n <= TOTAL_RED; n++) {
      if (intervals[n].length < 2) { avgIntervals[n] = store.DATA.length; continue; }
      let sum = 0;
      for (let k = 1; k < intervals[n].length; k++) sum += intervals[n][k] - intervals[n][k - 1];
      avgIntervals[n] = sum / (intervals[n].length - 1);
    }
    const lastIdx = store.DATA.length - 1;
    const w = {};
    for (let n = 1; n <= TOTAL_RED; n++) {
      const lastAppear = intervals[n].length > 0 ? intervals[n][intervals[n].length - 1] : -1;
      const gap = lastIdx - lastAppear;
      const avg = avgIntervals[n] || (gap + 1);
      const deviation = Math.abs(gap - avg) / Math.max(avg, 1);
      w[n] = Math.max(1, (1 - Math.min(1, deviation)) * INTERVAL_WEIGHT_AMP + 1);
    }
    return w;
  }

  buildBlueWeights() {
    const intervals = {};
    for (let n = 1; n <= TOTAL_BLUE; n++) intervals[n] = [];
    store.DATA.forEach((row, d) => intervals[row[7]].push(d));
    const avgIntervals = {};
    for (let n = 1; n <= TOTAL_BLUE; n++) {
      if (intervals[n].length < 2) { avgIntervals[n] = store.DATA.length; continue; }
      let sum = 0;
      for (let k = 1; k < intervals[n].length; k++) sum += intervals[n][k] - intervals[n][k - 1];
      avgIntervals[n] = sum / (intervals[n].length - 1);
    }
    const lastIdx = store.DATA.length - 1;
    const w = {};
    for (let n = 1; n <= TOTAL_BLUE; n++) {
      const lastB = intervals[n].length > 0 ? intervals[n][intervals[n].length - 1] : -1;
      const bGap = lastIdx - lastB;
      const bAvg = avgIntervals[n] || (bGap + 1);
      const bDeviation = Math.abs(bGap - bAvg) / Math.max(bAvg, 1);
      w[n] = Math.max(1, (1 - Math.min(1, bDeviation)) * 10 + 1);
    }
    return w;
  }
}
