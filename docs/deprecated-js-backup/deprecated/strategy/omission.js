/** 遗漏策略 */
import { Strategy } from './base.js';
import { computeOmission } from '../analysis/omission.js';

export class OmissionStrategy extends Strategy {
  constructor() { super(); this.name = '遗漏'; }

  buildRedWeights() { return computeOmission('red'); }
  buildBlueWeights() { return computeOmission('blue'); }
}
