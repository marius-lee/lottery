/** DataStore — 全局状态 */
export const store = {
  DATA: [],
  drawCount: 3,
  useAdvFilter: false,
  useDiversity: false,
  useGreedy: false,
  lastDrawResults: null,
  useFreqBlue: false,
  maxOverlap: 0,
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
