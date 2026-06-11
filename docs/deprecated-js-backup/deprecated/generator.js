/** 增强生成器 — 权重+过滤生成候选号码，含ML融合 + 多注覆盖优化
 *
 * ⚠️ 废弃声明: 当前工作流使用 ui/draw.js → /api/micro/tickets (后端微投资组合),
 *   不再经过前端生成器。本文件保留为参考代码，不接入任何调用路径。
 */
import { store } from './store.js';
import { pickOne } from './utils.js';
import { buildEnhancedWeights } from './weights.js';
import { enhancedFilter } from './filter/index.js';

// 6个红球分区: Z1=1-5, Z2=6-11, Z3=12-17, Z4=18-23, Z5=24-28, Z6=29-33
const ZONES = [
  { min: 1, max: 5 }, { min: 6, max: 11 }, { min: 12, max: 17 },
  { min: 18, max: 23 }, { min: 24, max: 28 }, { min: 29, max: 33 },
];
const COVERAGE_BOOST = 1.3;  // 未覆盖区域号码权重提升30%

function getZone(n) {
  for (let z = 0; z < ZONES.length; z++) {
    if (n >= ZONES[z].min && n <= ZONES[z].max) return z;
  }
  return -1;
}

/** mlProbs 可选,  coveredReds 可选 — 前n注已选的号码集合，用于覆盖优化 */
export function generateOneEnhanced(useFilter, mlProbs, coveredReds) {
  const fullRedW = buildEnhancedWeights('red', null);
  const fullBlueW = buildEnhancedWeights('blue', null);

  // ML 融合: 使用动态比例 (对比后自动调整)
  if (mlProbs && mlProbs.red) {
    const r = store.mlFusionRatio;
    for (const k in mlProbs.red) {
      fullRedW[k] = fullRedW[k] * (1 - r) + (mlProbs.red[k] || 0) * r;
    }
  }
  if (mlProbs && mlProbs.blue) {
    const r = store.mlFusionRatio;
    for (const k in mlProbs.blue) {
      fullBlueW[k] = fullBlueW[k] * (1 - r) + (mlProbs.blue[k] || 0) * r;
    }
  }

  // 多注覆盖优化: 统计已覆盖区域，提升未覆盖区域号码权重
  if (coveredReds && coveredReds.size > 0) {
    const coveredZones = new Set();
    coveredReds.forEach(n => { coveredZones.add(getZone(n)); });
    const uncoveredZones = [];
    for (let z = 0; z < ZONES.length; z++) {
      if (!coveredZones.has(z)) uncoveredZones.push(z);
    }
    // 至少2个未覆盖区域时才提升（保留一定随机性）
    if (uncoveredZones.length >= 2) {
      for (let n = 1; n <= 33; n++) {
        if (uncoveredZones.includes(getZone(n))) {
          fullRedW[n] = (fullRedW[n] || 0.01) * COVERAGE_BOOST;
        }
      }
    }
  }

  const failReasons = {};

  for (let attempt = 0; attempt < 300; attempt++) {
    const reds = new Set();
    const excluded = new Set();
    const redW = { ...fullRedW };
    while (reds.size < 6) {
      excluded.forEach(n => { redW[n] = 0; });
      const n = pickOne(redW);
      reds.add(n);
      excluded.add(n);
    }
    const blue = pickOne(fullBlueW);

    if (!useFilter) {
      return { reds: [...reds].sort((a, b) => a - b), blue, score: 5, fails: failReasons };
    }

    const result = enhancedFilter([...reds], blue);
    if (result.pass && result.score >= 3) {
      return { reds: [...reds].sort((a, b) => a - b), blue, score: result.score, fails: failReasons };
    }
    const reason = result.reason || 'unknown';
    failReasons[reason] = (failReasons[reason] || 0) + 1;
  }

  // Fallback
  const reds = new Set();
  const excluded = new Set();
  while (reds.size < 6) {
    reds.add(pickOne(buildEnhancedWeights('red', excluded)));
    excluded.add([...reds].pop());
  }
  return {
    reds: [...reds].sort((a, b) => a - b),
    blue: pickOne(buildEnhancedWeights('blue', new Set())),
    score: 0,
    fails: failReasons,
  };
}

export function summarizeFails(allResults) {
  const merged = {};
  for (const r of allResults) {
    if (r.fails) {
      for (const [reason, count] of Object.entries(r.fails)) {
        merged[reason] = (merged[reason] || 0) + count;
      }
    }
  }
  const sorted = Object.entries(merged).sort((a, b) => b[1] - a[1]);
  if (sorted.length === 0) return '';
  const total = sorted.reduce((s, [, c]) => s + c, 0);
  const items = sorted.map(([r, c]) => `${r}: ${c}次 (${Math.round(c / total * 100)}%)`);
  return `覆盖优化 | ${items.join(' | ')}`;
}
