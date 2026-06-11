/** 共识系统 v5 — 红蓝分离权重 + 策略族上限 + 族内相关性惩罚
 *
 * ⚠️ 废弃声明: 当前工作流使用 ui/draw.js 直接调用 /api/micro/tickets (后端微投资组合),
 *   前端不运行策略，所有共识逻辑保留为参考代码，不接入任何调用路径。
 */
import { store } from './store.js';
import { runAllStrategies } from './strategy/registry.js';
import { CONSENSUS_CORRELATION_DISCOUNT } from './constants.js';

const CORRELATION_DISCOUNT = CONSENSUS_CORRELATION_DISCOUNT;

/** 对一组权重应用族上限（就地修改） */
function applyFamilyCap(weights, totalWeight) {
  const cap = totalWeight * store.familyCap;
  const families = store.strategyFamilies;
  for (const [fam, members] of Object.entries(families)) {
    let famTotal = 0;
    members.forEach(m => { famTotal += weights[m] || 0; });
    if (famTotal > cap) {
      const scale = cap / famTotal;
      members.forEach(m => { if (weights[m]) weights[m] *= scale; });
    }
  }
}

/** 族内相关性惩罚: 同族策略对同一号码的投票打了折扣 */
function applyCorrelationPenalty(countMap, strategies, weights) {
  const families = store.strategyFamilies;
  // 为每个族跟踪已投票的号码，第二票起打折扣
  for (const [fam, members] of Object.entries(families)) {
    const famSeenReds = {};  // ballNum → count of strategies that voted for it
    // 第一遍: 统计族内各号码的投票策略数
    strategies.forEach(s => {
      if (!members.includes(s.name)) return;
      const wr = weights[s.name] || 1.0;
      s.reds.forEach(n => {
        famSeenReds[n] = (famSeenReds[n] || 0) + 1;
      });
    });
    // 第二遍: 对同族重复投票应用折扣
    for (const [ball, voteCount] of Object.entries(famSeenReds)) {
      if (voteCount > 1) {
        // 总折扣 = 1 + (voteCount-1) * CORRELATION_DISCOUNT
        const effectiveMultiplier = 1 + (voteCount - 1) * CORRELATION_DISCOUNT;
        const discount = effectiveMultiplier / voteCount;
        const ballNum = parseInt(ball);
        // countMap 中的值来自加权投票，乘以折扣
        countMap[ballNum] = countMap[ballNum] * discount;
      }
    }
  }
}

export async function runAllStrategiesWithML() {
  const strats = (await runAllStrategies())
    .filter(s => s.name !== 'AI集成' || store.mlPredictionCache);

  if (store.useML && store.mlPredictionCache) {
    strats.push({
      name: 'AI集成',
      reds: [...store.mlPredictionCache.reds],
      blue: store.mlPredictionCache.blue,
    });
  }
  return strats;
}

export function computeConsensus(strategies) {
  const rCount = {};
  const bCount = {};
  for (let i = 1; i <= 33; i++) rCount[i] = 0;
  for (let i = 1; i <= 16; i++) bCount[i] = 0;

  // 计算总权重用于族上限
  let totalRedW = 0, totalBlueW = 0;
  strategies.forEach(s => {
    totalRedW += store.redWeights[s.name] || 1.0;
    totalBlueW += store.blueWeights[s.name] || 1.0;
  });

  // 复制权重并应用族上限
  const rw = {};
  const bw = {};
  strategies.forEach(s => {
    rw[s.name] = store.redWeights[s.name] || 1.0;
    bw[s.name] = store.blueWeights[s.name] || 1.0;
  });
  applyFamilyCap(rw, totalRedW);
  applyFamilyCap(bw, totalBlueW);

  // 红球投票: 使用红球权重
  strategies.forEach(s => {
    const wr = rw[s.name] || 1.0;
    s.reds.forEach(n => { rCount[n] += wr; });
  });

  // v5: 族内相关性惩罚 — 防止同族策略联合放大伪信号
  applyCorrelationPenalty(rCount, strategies, rw);

  // 蓝球投票: 使用蓝球权重
  strategies.forEach(s => {
    const wb = bw[s.name] || 1.0;
    bCount[s.blue] += wb;
  });

  const rEntries = Object.entries(rCount)
    .map(([k, v]) => [parseInt(k), v])
    .sort((a, b) => b[1] - a[1] || a[0] - b[0]);
  const consReds = rEntries.slice(0, 6).map(e => e[0]).sort((a, b) => a - b);

  const bEntries = Object.entries(bCount)
    .map(([k, v]) => [parseInt(k), v])
    .sort((a, b) => b[1] - a[1]);
  const consBlue = bEntries[0][0];

  return {
    reds: consReds,
    blue: consBlue,
    confidences: rCount,
    blueConfidences: bCount,  // 完整蓝球投票字典，供多注蓝球排序
    totalWeight: totalRedW,
  };
}
