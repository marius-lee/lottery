/** 频率策略 */
import { Strategy } from './base.js';
import { countFreq } from '../analysis/frequency.js';

export class FreqStrategy extends Strategy {
  constructor() { super(); this.name = '频率'; }

  buildRedWeights() { return countFreq('red'); }
  buildBlueWeights() { return countFreq('blue'); }
}
