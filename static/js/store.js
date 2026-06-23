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
  useGreedy: false,
  useLiuBlue: false,
  useCaileleBlue: false,
  useGongyiBlue: false,
  useWumingBlue: false,
  useBacktest: false,
  useColorFilter: false,
  useBlock9Filter: false,
  useWumingClockwise: false,
  useWumingBSD: false,
  useXiaBlue: false,
  useSpreadFilter: false,
  useAcFilter: false,
  usePengChannelFilter: false,
  useGapFilter: false,
  useOmissionFilter: false,
  useTwelveValue: false,
  useEightValue: false,
  useGridSelection: false,
  lastDrawResults: null,
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
