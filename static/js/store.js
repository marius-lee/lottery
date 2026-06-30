/** DataStore (Observer Pattern) — 全局状态单例 + 订阅通知
 *
 * 精简原因: 策略权重/ML融合等状态仅用于已归档的前端策略系统，
 * 当前工作流 (ui/draw.js → /api/micro/tickets) 不读取它们。
 * 归档备份: docs/deprecated-js-backup/
 */
export const store = {
  DATA: [],
  drawCount: 3,
  useAdvFilter: false,
  useDiversity: false,
  useGreedy: false,  useBacktest: false,
  useTwelveValue: false,
  useEightValue: false,
  useGridSelection: false,
  useFivePeriod: false,
  usePatternRules: false,
  lastDrawResults: null,
  useFreqBlue: false,
  blueMode: 'freq',
  redMode: 'pool',
  t: 4,          // 覆盖强度 t (4=四等奖, 5=三等奖)
  multiPeriod: false,  // 多期联合覆盖: 跨期跟踪已覆盖子集
  strategyMode: null,
  useAutoKelly: false,
  kellyRecommendedN: 0,
  currentAuthor: null,  // 当前选中的作者, null=无
  vOverride: null,       // 手动覆盖 v (null=自动), 来源: bias signal v selector
};

const _listeners = [];

export function subscribe(fn) {
  if (typeof fn === 'function') _listeners.push(fn);
}

export function notify(event, payload) {
  _listeners.forEach(fn => {
    if (typeof fn === 'function') fn(event, payload);
  });
}

export function updateData(newData) {
  store.DATA = newData;
  notify('data-changed', newData);
}
