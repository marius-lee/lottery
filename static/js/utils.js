/** 通用工具函数 — 纯函数，无依赖 */

// 质数表 (1-33)
const _primes = new Set([2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31]);

export function isPrime(n) {
  return _primes.has(n);
}
