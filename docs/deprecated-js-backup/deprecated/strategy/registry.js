/** 策略注册表 (Factory Pattern) — 创建/管理所有策略实例
 *
 * ⚠️ 废弃声明: 当前工作流使用 ui/draw.js 直接调用 /api/micro/tickets (后端微投资组合),
 *   前端不运行策略。本文件和 static/js/strategy/ 下所有策略实现保留为参考代码，
 *   不接入任何调用路径。请勿在新工作流中引用。
 */
import { Strategy } from './base.js';
import { FreqStrategy } from './freq.js';
import { OmissionStrategy } from './omission.js';
import { TrendStrategy } from './trend.js';
import { UniformStrategy } from './uniform.js';
import { IntervalStrategy } from './interval.js';
import { GoldenRatioStrategy } from './golden_ratio.js';
import { SameTailStrategy } from './same_tail.js';
import { SimilarPeriodStrategy } from './similar_period.js';
import { PositionStrategy } from './position.js';
import { CooccurStrategy } from './cooccur.js';
import { MarkovBlueStrategy } from './markov_blue.js';
import { TemperatureStrategy } from './temperature.js';
import { ChaosStrategy } from './chaos.js';
import { ExponentialStrategy } from './exponential.js';
import { MLEnsembleStrategy } from './ml_ensemble.js';

/** 高级统计模型 — 通过后端API统一调用 (canonical: ml/advanced.py) */
class AdvancedStrategy extends Strategy {
  constructor(name, apiModel) {
    super();
    this.name = name;
    this._api = apiModel;
  }
  async predict() {
    try {
      const r = await fetch(`/api/ml/predict/${this._api}`);
      const d = await r.json();
      if (d.ok) return { name: this.name, reds: d.reds, blue: d.blue };
    } catch (e) { /* fallthrough */ }
    return null;
  }
  buildRedWeights() { return {}; }
  buildBlueWeights() { return {}; }
}

const _registry = new Map();

function register(StrategyClass) {
  const instance = new StrategyClass();
  _registry.set(instance.name, instance);
}

function registerAdvanced(name, apiModel) {
  const instance = new AdvancedStrategy(name, apiModel);
  _registry.set(name, instance);
}

// 14 基础策略
register(FreqStrategy);
register(OmissionStrategy);
register(TrendStrategy);
register(UniformStrategy);
register(IntervalStrategy);
register(GoldenRatioStrategy);
register(SameTailStrategy);
register(SimilarPeriodStrategy);
register(PositionStrategy);
register(CooccurStrategy);
register(MarkovBlueStrategy);
register(TemperatureStrategy);
register(ChaosStrategy);
register(ExponentialStrategy);

// ML集成
register(MLEnsembleStrategy);

// 6 高级统计模型 (后端 ml/advanced.py)
registerAdvanced('Copula', 'copula');
registerAdvanced('贝叶斯', 'bayesian');
registerAdvanced('熵值', 'entropy');
registerAdvanced('Pólya', 'polya');
registerAdvanced('EVT', 'evt');
registerAdvanced('RMT', 'rmt');

/** 运行单个策略 (同步或异步) */
export async function runStrategy(name) {
  const strategy = _registry.get(name);
  if (!strategy) return null;
  try {
    return await Promise.resolve(strategy.predict());
  } catch (e) {
    return null;
  }
}

/** 运行所有已注册策略 (过滤null/错误) */
export async function runAllStrategies() {
  const results = await Promise.all(
    [..._registry.values()].map(s => {
      try {
        return Promise.resolve(s.predict()).catch(() => null);
      } catch (e) {
        return null;
      }
    })
  );
  return results.filter(Boolean);
}

/** 同步运行内置策略 (跳过需要API的 — 用于前端口回测) */
export function runBuiltinStrategies() {
  const builtin = ['频率', '遗漏', '趋势', '均匀', '间隔', '黄金分割',
    '同尾', '相似期', '位置', '共现', '马尔可夫蓝', '温度', '混沌', '指数优化'];
  return builtin.map(name => {
    const s = _registry.get(name);
    return s ? s.predict() : null;
  }).filter(Boolean);
}

/** 获取策略名称列表 */
export function getStrategyNames() {
  return [..._registry.keys()];
}
