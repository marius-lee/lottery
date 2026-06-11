/** 质数统计 */
import { isPrime } from '../utils.js';
import { store } from '../store.js';

export { isPrime };

export function countPrimesInReds(reds) {
  return reds.filter(n => isPrime(n)).length;
}

export function computeHistoricalPrimeRange() {
  const counts = [];
  store.DATA.forEach(row => counts.push(countPrimesInReds(row.slice(1, 7))));
  const freq = [0, 0, 0, 0, 0, 0, 0];
  counts.forEach(c => { freq[c]++; });
  const sum = counts.reduce((s, v) => s + v, 0);
  return { avg: sum / counts.length, freq };
}
