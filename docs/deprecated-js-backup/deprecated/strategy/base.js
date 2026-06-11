/** 策略基类 (Strategy Pattern + Template Method)
 *
 *  子类只需实现 buildRedWeights() 和 buildBlueWeights()。
 *  框架自动执行: 构建权重 → 加权抽取红球 → 加权抽取蓝球 → 返回结果
 */
import { pickOne, pickBalls } from '../utils.js';

export class Strategy {
  constructor() {
    this.name = 'base';
  }

  /** Template Method — 定义算法骨架 */
  predict() {
    const redWeights = this.buildRedWeights();
    const reds = this._pickReds(redWeights);
    const blueWeights = this.buildBlueWeights();
    const blue = this._pickBlue(blueWeights);
    return { name: this.name, reds, blue };
  }

  /** 子类必须实现 */
  buildRedWeights() {
    throw new Error(`Strategy "${this.name}" must implement buildRedWeights()`);
  }

  buildBlueWeights() {
    throw new Error(`Strategy "${this.name}" must implement buildBlueWeights()`);
  }

  /** 基类提供: 从权重中抽取6个红球（已排序） */
  _pickReds(weights) {
    return pickBalls(weights, 6, 33);
  }

  /** 基类提供: 从权重中抽取1个蓝球 */
  _pickBlue(weights) {
    return pickOne(weights);
  }
}
