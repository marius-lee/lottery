/** 软评分 — 5项评分 [数据] .cache/ssq.db 2000期 2026-06-06
 *  (龙头/凤尾/连号/三区覆盖 已升级为硬过滤, 此处不再评分) */
import { SOFT_SUM_MID_LO, SOFT_SUM_MID_HI, SOFT_SUM_TIGHT_LO, SOFT_SUM_TIGHT_HI } from '../constants.js';

export function softFilterScore(reds, blue) {
  const R = [...reds].sort((a, b) => a - b);

  // 1. 012路均衡 (实测 ~80% 开奖三路都有号)
  const routes = [0, 0, 0];
  R.forEach(n => { routes[n % 3]++; });
  const routeScore = (routes[0] >= 1 && routes[1] >= 1 && routes[2] >= 1) ? 1 : 0;

  // 2. 同尾号 (实测 76%)
  const tails = {};
  R.forEach(n => { const t = n % 10; tails[t] = (tails[t] || 0) + 1; });
  const hasTailPair = Object.values(tails).some(c => c >= 2) ? 1 : 0;

  // 3. 和值中心化 — 双级评分 (实测 52.9% 在90-120, 29.1% 在95-110)
  const sum = R.reduce((s, n) => s + n, 0);
  let sumScore = 0;
  if (sum >= SOFT_SUM_MID_LO && sum <= SOFT_SUM_MID_HI) sumScore = 1;
  if (sum >= SOFT_SUM_TIGHT_LO && sum <= SOFT_SUM_TIGHT_HI) sumScore = 2;

  // 4. 奇偶最优 — 3奇3偶 最优 (超几何分布: P=34.4%), 2/4 ratio次优
  const odds = R.filter(n => n % 2 === 1).length;
  const oddScore = odds === 3 ? 2 : (odds >= 2 && odds <= 4 ? 1 : 0);

  // 5. 大小最优 — 3大(≥17)3小 最优 (超几何分布: P=34.0%)
  const bigs = R.filter(n => n >= 17).length;
  const bigScore = bigs === 3 ? 2 : (bigs >= 2 && bigs <= 4 ? 1 : 0);

  return routeScore + hasTailPair + sumScore + oddScore + bigScore;
}
