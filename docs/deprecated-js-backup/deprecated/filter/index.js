/** 组合过滤器 (Chain of Responsibility #3 — 链末端) */
import { hardFilter } from './hard.js';
import { softFilterScore } from './soft.js';

export function enhancedFilter(reds, blue) {
  const hard = hardFilter(reds, blue);
  if (!hard.pass) return { pass: false, reason: hard.reason, score: 0 };
  const soft = softFilterScore(reds, blue);
  return { pass: true, score: soft };
}
