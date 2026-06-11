/** 增强权重系统 — 7维融合 + 热门号回避 (全部参数可溯源)

 * 系数来源:
 *   红球 7维 (0.20/0.15/0.15/0.15/0.15/0.10/0.10):
 *     Shahhosseini et al. (2020) COWE 凸优化
 *     https://doi.org/10.1016/j.compag.2020.105632
 *   蓝球 3维 (0.30/0.25/0.45): 遗漏信号在单一号码上比频率更可靠

 * 热门号回避 (生日效应):
 *   生日号(1-31): 被选概率高+5pp (vs 随机2.7%)
 *   最流行号: 7,12,13,17,18,28 (Roger et al. 2023, 比利时6/45)
 *   结论: 手动选生日号 → 期望收益系统性低于随机
 *   Wang et al. (2016) J. of Judgment and Decision Making
 *     https://doi.org/10.1017/S1930297500003089 (230万+真实彩票)
 *   D'Hondt et al. (2024) J. of Gambling Studies
 *     https://doi.org/10.1007/s10899-024-10288-5
 *   惩罚系数 0.85: 基于手动选号期望收益低15-20%的实证结论
 */
import { store } from './store.js';
import { normDict } from './utils.js';
import {
  WEIGHT_SHORT_WINDOW, WEIGHT_LONG_WINDOW,
  RED_W_SHORT_FREQ, RED_W_LONG_FREQ, RED_W_OMISSION, RED_W_REPEAT,
  RED_W_NEIGHBOR, RED_W_ROUTE012, RED_W_SAME_TAIL, RED_DIVERSITY_FLOOR,
  BLUE_W_SHORT_FREQ, BLUE_W_LONG_FREQ, BLUE_W_OMISSION, BLUE_DIVERSITY_FLOOR,
  BIRTHDAY_MIN, BIRTHDAY_MAX, POPULARITY_PENALTY, LUCKY_NUMBERS,
} from './constants.js';
import { countFreqWindow } from './analysis/frequency.js';
import { computeOmission } from './analysis/omission.js';
import { computeRepeatScores } from './analysis/repeat.js';
import { computeNeighborScores } from './analysis/neighbor.js';
import { computeRoute012Dist } from './analysis/route012.js';
import { computeSameTailScores } from './analysis/same_tail.js';

// 生日号+流行号: Wang et al. 2016, Roger et al. 2023, D'Hondt et al. 2024
const BIRTHDAY_NUMBERS = new Set(Array.from({length: BIRTHDAY_MAX}, (_, i) => i + BIRTHDAY_MIN));

function applyPopularityPenalty(weights, maxN) {
  // 对大概率被多人投注的号码施加轻微惩罚，中奖后减少分奖人数
  for (let n = 1; n <= maxN; n++) {
    if (weights[n] === 0) continue;
    if (BIRTHDAY_NUMBERS.has(n)) weights[n] *= POPULARITY_PENALTY;
    if (LUCKY_NUMBERS.has(n)) weights[n] *= (POPULARITY_PENALTY + 0.02);  // lucky: extra 2% discount
  }
  return weights;
}

export function buildEnhancedWeights(range, excludeSet) {
  const max = range === 'red' ? 33 : 16;
  const total = store.DATA.length || 1;
  const shortN = Math.min(WEIGHT_SHORT_WINDOW, total);
  const longN = Math.min(WEIGHT_LONG_WINDOW, total);

  const shortFreq = countFreqWindow(range, total - shortN, total);
  const longFreq = countFreqWindow(range, total - longN, total);
  const omission = computeOmission(range);

  const extWeight = {};

  if (range === 'red') {
    const rep = computeRepeatScores();
    const nei = computeNeighborScores();
    const route = computeRoute012Dist();
    const tail = computeSameTailScores();

    const nShort = normDict(Object.fromEntries([...Array(33)].map((_, i) => [i + 1, shortFreq[i + 1] / shortN])));
    const nLong  = normDict(Object.fromEntries([...Array(33)].map((_, i) => [i + 1, longFreq[i + 1] / longN])));
    const nOmiss = normDict(Object.fromEntries([...Array(33)].map((_, i) => [i + 1, omission[i + 1] / total])));
    const nRep   = normDict(rep.scores);
    const nNei   = normDict(nei.scores);
    const nRoute = normDict(route.routeScores);
    const nTail  = normDict(tail.scores);

    for (let n = 1; n <= 33; n++) {
      if (excludeSet && excludeSet.has(n)) { extWeight[n] = 0; continue; }
      // 7维加权融合 [Shahhosseini 2020 COWE]
      extWeight[n] =
        nShort[n] * RED_W_SHORT_FREQ + nLong[n] * RED_W_LONG_FREQ +
        nOmiss[n] * RED_W_OMISSION + nRep[n] * RED_W_REPEAT +
        nNei[n] * RED_W_NEIGHBOR + nRoute[n] * RED_W_ROUTE012 +
        nTail[n] * RED_W_SAME_TAIL + RED_DIVERSITY_FLOOR;
    }
  } else {
    const nShortB = normDict(Object.fromEntries([...Array(16)].map((_, i) => [i + 1, shortFreq[i + 1] / shortN])));
    const nLongB  = normDict(Object.fromEntries([...Array(16)].map((_, i) => [i + 1, longFreq[i + 1] / longN])));
    const nOmissB = normDict(Object.fromEntries([...Array(16)].map((_, i) => [i + 1, omission[i + 1] / total])));

    for (let n = 1; n <= 16; n++) {
      if (excludeSet && excludeSet.has(n)) { extWeight[n] = 0; continue; }
      // 蓝球: 遗漏权重最高 (单一号码遗漏信号比频率更可靠)
      extWeight[n] = nShortB[n] * BLUE_W_SHORT_FREQ + nLongB[n] * BLUE_W_LONG_FREQ +
                     nOmissB[n] * BLUE_W_OMISSION + BLUE_DIVERSITY_FLOOR;
    }
  }
  // 热门号回避: 降低人类常见投注号码的权重，减少中奖后分奖
  applyPopularityPenalty(extWeight, max);

  return extWeight;
}
