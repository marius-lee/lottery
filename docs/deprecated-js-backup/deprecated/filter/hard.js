/** 硬过滤 — 2000期实测 + 行业标准 [数据] .cache/ssq.db 2026-06-06 */
import { store } from '../store.js';
import { isPrime } from '../utils.js';
import { computeACValue } from '../analysis/ac_span.js';
import {
  FILTER_SUM_LO, FILTER_SUM_HI, FILTER_SPAN_LO, FILTER_SPAN_HI,
  FILTER_AC_LO, FILTER_AC_HI, FILTER_ODD_MIN, FILTER_ODD_MAX,
  FILTER_BIG_MIN, FILTER_BIG_MAX, FILTER_PRIME_MIN, FILTER_PRIME_MAX,
  FILTER_REPEAT_MIN, FILTER_REPEAT_MAX,
  FILTER_TAIL_GROUPS_MIN, FILTER_TAIL_GROUPS_MAX,
  FILTER_ROUTE012_MIN_TYPES,
  FILTER_MAX_GAP_LO, FILTER_MAX_GAP_HI,
  FILTER_CONSEC_MIN,
  FILTER_DRAGON_MAX, FILTER_PHOENIX_MIN,
  BLUE_BALANCE_WINDOW, BLUE_BALANCE_ODD_MAX, BLUE_BALANCE_ODD_MIN,
} from '../constants.js';

export function hardFilter(reds, blue) {
  const R = [...reds].sort((a, b) => a - b);

  // 1. 和值 [数据] 2000期 P2.5/P97.5: 70-142
  const sum = R.reduce((s, n) => s + n, 0);
  if (sum < FILTER_SUM_LO || sum > FILTER_SUM_HI) return { pass: false, reason: '和值' };

  // 2. 奇偶比 [行业] 2-4奇数
  const odds = R.filter(n => n % 2 === 1).length;
  if (odds < FILTER_ODD_MIN || odds > FILTER_ODD_MAX) return { pass: false, reason: '奇偶比' };

  // 3. 大小比 [行业] 2-4大号(≥17)
  const bigs = R.filter(n => n >= 17).length;
  if (bigs < FILTER_BIG_MIN || bigs > FILTER_BIG_MAX) return { pass: false, reason: '大小比' };

  // 4. 跨度 [行业] 20-31
  const span = R[5] - R[0];
  if (span < FILTER_SPAN_LO || span > FILTER_SPAN_HI) return { pass: false, reason: '跨度' };

  // 5. AC值 [行业] 6-9
  const ac = computeACValue(R);
  if (ac < FILTER_AC_LO || ac > FILTER_AC_HI) return { pass: false, reason: 'AC值' };

  // 6. 质数 [行业] 1-3
  const primeCount = R.filter(n => isPrime(n)).length;
  if (primeCount < FILTER_PRIME_MIN || primeCount > FILTER_PRIME_MAX) return { pass: false, reason: '质数比' };

  // 7. 重号 [行业] 1-2个红球与上期相同 (概率67.5%, 超几何分布)
  if (store.DATA.length > 0) {
    const lastReds = new Set(store.DATA[store.DATA.length - 1].slice(1, 7));
    const repeatCount = R.filter(n => lastReds.has(n)).length;
    if (repeatCount < FILTER_REPEAT_MIN || repeatCount > FILTER_REPEAT_MAX) return { pass: false, reason: '重号' };
  }

  // 8. 尾数组数 [行业] 5-6组 (概率95%+)
  const tails = new Set(R.map(n => n % 10));
  if (tails.size < FILTER_TAIL_GROUPS_MIN || tails.size > FILTER_TAIL_GROUPS_MAX) return { pass: false, reason: '尾数组数' };

  // 9. 012路 [行业] 至少2种余数 (概率97%+)
  const routeTypes = new Set(R.map(n => n % 3));
  if (routeTypes.size < FILTER_ROUTE012_MIN_TYPES) return { pass: false, reason: '012路' };

  // 10. 最大邻号间距 [行业] 10-13
  let maxGap = 0;
  for (let i = 0; i < R.length - 1; i++) {
    maxGap = Math.max(maxGap, R[i + 1] - R[i]);
  }
  if (maxGap < FILTER_MAX_GAP_LO || maxGap > FILTER_MAX_GAP_HI) return { pass: false, reason: '最大邻号间距' };

  // 11. 三区覆盖 [数据] 1-11 / 12-22 / 23-33 每区至少1个 (概率~80%)
  const z1 = R.filter(n => n <= 11).length;
  const z2 = R.filter(n => n >= 12 && n <= 22).length;
  const z3 = R.filter(n => n >= 23).length;
  if (z1 === 0 || z2 === 0 || z3 === 0) return { pass: false, reason: '三区覆盖' };

  // 12. 连号 [行业] ≥1对 (概率~65%)
  let hasConsec = false;
  for (let i = 0; i < R.length - 1; i++) {
    if (R[i + 1] - R[i] === 1) { hasConsec = true; break; }
  }
  if (FILTER_CONSEC_MIN > 0 && !hasConsec) return { pass: false, reason: '连号' };

  // 13. 龙头 [数据] ≤9 (88.7%)
  if (R[0] > FILTER_DRAGON_MAX) return { pass: false, reason: '龙头' };

  // 14. 凤尾 [数据] ≥28 (70.3%)
  if (R[5] < FILTER_PHOENIX_MIN) return { pass: false, reason: '凤尾' };

  // 15. 蓝球重号 [行业] 禁止与上期同蓝
  if (store.DATA.length > 0 && blue === store.DATA[store.DATA.length - 1][7]) {
    return { pass: false, reason: '蓝球重号' };
  }

  // 16. 蓝球奇偶平衡 [数据] 近10期奇≤8, 偶≥2
  const lookback = Math.min(BLUE_BALANCE_WINDOW, store.DATA.length);
  let blueOdds = 0;
  for (let d = store.DATA.length - lookback; d < store.DATA.length; d++) {
    if (store.DATA[d][7] % 2 === 1) blueOdds++;
  }
  if (blue % 2 === 1 && blueOdds >= BLUE_BALANCE_ODD_MAX) return { pass: false, reason: '蓝球奇偏' };
  if (blue % 2 === 0 && blueOdds <= BLUE_BALANCE_ODD_MIN) return { pass: false, reason: '蓝球偶偏' };

  return { pass: true };
}
