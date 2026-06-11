/** AI集成策略 — 使用ML双模型预测结果 */
import { Strategy } from './base.js';
import { store } from '../store.js';

export class MLEnsembleStrategy extends Strategy {
  constructor() { super(); this.name = 'AI集成'; }

  predict() {
    if (store.mlPredictionCache) {
      return {
        name: this.name,
        reds: [...store.mlPredictionCache.reds],
        blue: store.mlPredictionCache.blue,
      };
    }
    // Fallback: return null (will be filtered out by runAllStrategies)
    return null;
  }

  buildRedWeights() { return {}; }
  buildBlueWeights() { return {}; }
}
