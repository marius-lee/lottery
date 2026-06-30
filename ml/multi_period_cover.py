"""多期联合覆盖设计 — 跨期跟踪已覆盖组合, 下期优先补充未覆盖空间

核心思路 (Stommer 2024: "Lottery Problem — Tracing Mandel's Combinatorial Condensation"):
  - 每期投注覆盖一部分 t-子集空间
  - 下期优先覆盖上期未命中的 t-子集
  - 多期累积覆盖 > 单期独立覆盖

数据规模: t=4 时 C(33,4)=40,920 个 4-子集, 每期 3 注约覆盖 45 个.
SQLite 存储覆盖历史, 按 hash 索引快速查询.
"""
import itertools
import sqlite3
import os
from typing import List, Set, Tuple, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '.cache', 'ssq.db')


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_coverage_db():
    """初始化多期覆盖状态表."""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS multi_period_coverage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period_id TEXT NOT NULL,
            ticket_idx INTEGER NOT NULL,
            t_value INTEGER NOT NULL DEFAULT 4,
            subset_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_mpc_hash_t 
        ON multi_period_coverage(subset_hash, t_value)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_mpc_period 
        ON multi_period_coverage(period_id)
    """)
    conn.commit()
    conn.close()


def _subset_hash(subset: Tuple[int, ...]) -> str:
    """4-子集 -> 字符串 hash, e.g. (1,5,12,23) -> '1-5-12-23'."""
    return '-'.join(str(x) for x in sorted(subset))


def save_coverage(period_id: str, tickets: List[List[int]], t: int = 4):
    """保存本期覆盖的 t-子集到数据库."""
    conn = _get_conn()
    rows = []
    for tix, reds in enumerate(tickets):
        for tup in itertools.combinations(sorted(reds), t):
            rows.append((period_id, tix, t, _subset_hash(tup)))
    conn.executemany(
        "INSERT INTO multi_period_coverage (period_id, ticket_idx, t_value, subset_hash) VALUES (?, ?, ?, ?)",
        rows
    )
    conn.commit()
    conn.close()


def get_covered_subsets(t: int = 4, max_periods: int = 50) -> Set[str]:
    """获取最近 max_periods 期内已覆盖的 t-子集 hash 集合."""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT DISTINCT subset_hash FROM multi_period_coverage 
        WHERE t_value = ?
        ORDER BY id DESC LIMIT ?
    """, (t, max_periods * 10)).fetchall()
    conn.close()
    return {r[0] for r in rows}


def get_covered_draw_indices(
    hot_numbers: List[int], 
    t: int = 4, 
    max_periods: int = 50
) -> dict:
    """返回已被覆盖的开奖组合索引 -> 覆盖t-子集数映射.
    
    对 C(v,6) 的所有可能开奖组合, 统计其 t-子集中已被历史覆盖的数量.
    贪心算法可利用此信息: 已覆盖多的组合降低权重, 优先选覆盖新组合的票.
    """
    covered_hashes = get_covered_subsets(t, max_periods)
    if not covered_hashes:
        return {}
    
    v = len(hot_numbers)
    result = {}
    for di, draw in enumerate(itertools.combinations(range(v), 6)):
        actual_draw = tuple(hot_numbers[x] for x in draw)
        covered_count = 0
        for tup in itertools.combinations(sorted(actual_draw), t):
            if _subset_hash(tup) in covered_hashes:
                covered_count += 1
        if covered_count > 0:
            result[di] = covered_count
    return result


def clear_coverage(t: int = 4):
    """清空覆盖历史."""
    conn = _get_conn()
    conn.execute("DELETE FROM multi_period_coverage WHERE t_value = ?", (t,))
    conn.commit()
    conn.close()


def coverage_stats(t: int = 4) -> dict:
    """多期覆盖统计."""
    conn = _get_conn()
    total = conn.execute(
        "SELECT COUNT(DISTINCT subset_hash) FROM multi_period_coverage WHERE t_value = ?", (t,)
    ).fetchone()[0]
    periods = conn.execute(
        "SELECT COUNT(DISTINCT period_id) FROM multi_period_coverage WHERE t_value = ?", (t,)
    ).fetchone()[0]
    conn.close()
    
    total_possible = 40920 if t == 4 else 237336  # C(33,4)=40920, C(33,5)=237336
    
    return {
        "t": t,
        "covered_subsets": total,
        "total_possible": total_possible,
        "coverage_pct": round(total / total_possible * 100, 2) if total_possible else 0,
        "periods_tracked": periods,
        "note": f"已跨{periods}期覆盖 {total}/{total_possible} 个{t}-子集",
    }


# 自动初始化
try:
    init_coverage_db()
except Exception:
    pass
