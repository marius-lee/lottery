"""数据库层 (Repository Pattern) — 所有SQLite操作"""
import json
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
CACHE_DIR = ROOT / ".cache"
DB_PATH = CACHE_DIR / "ssq.db"


def get_db():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS draws (
            period   INTEGER PRIMARY KEY,
            r1       INTEGER NOT NULL,
            r2       INTEGER NOT NULL,
            r3       INTEGER NOT NULL,
            r4       INTEGER NOT NULL,
            r5       INTEGER NOT NULL,
            r6       INTEGER NOT NULL,
            blue     INTEGER NOT NULL,
            source   TEXT    NOT NULL DEFAULT '中彩网',
            fetched_at TEXT  NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS user_picks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            period     INTEGER NOT NULL,
            r1         INTEGER NOT NULL,
            r2         INTEGER NOT NULL,
            r3         INTEGER NOT NULL,
            r4         INTEGER NOT NULL,
            r5         INTEGER NOT NULL,
            r6         INTEGER NOT NULL,
            blue       INTEGER NOT NULL,
            strategy   TEXT,
            score      INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS strategy_picks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            period     INTEGER NOT NULL,
            r1         INTEGER NOT NULL,
            r2         INTEGER NOT NULL,
            r3         INTEGER NOT NULL,
            r4         INTEGER NOT NULL,
            r5         INTEGER NOT NULL,
            r6         INTEGER NOT NULL,
            blue       INTEGER NOT NULL,
            strategy   TEXT    NOT NULL,
            created_at TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS strategy_weights (
            name    TEXT PRIMARY KEY,
            weight  REAL NOT NULL,
            hits    INTEGER DEFAULT 0,
            tries   INTEGER DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS backtest_results (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            window_size INTEGER NOT NULL,
            strategy    TEXT NOT NULL,
            avg_red_hit REAL NOT NULL,
            blue_hit_rate REAL NOT NULL,
            max_hit     INTEGER NOT NULL,
            test_count  INTEGER NOT NULL,
            weight      REAL NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS prediction_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            period          INTEGER NOT NULL,
            source          TEXT    NOT NULL,
            reds_json       TEXT    NOT NULL,
            blue            INTEGER NOT NULL,
            actual_reds_json TEXT,
            actual_blue     INTEGER,
            red_hits        INTEGER DEFAULT -1,
            blue_hit        INTEGER DEFAULT -1,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_pred_log_period ON prediction_log(period);

        -- v2 schema improvements
        CREATE TABLE IF NOT EXISTS schema_version (
            version     INTEGER PRIMARY KEY,
            description TEXT    NOT NULL,
            applied_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_draws_period_desc ON draws(period DESC);
        CREATE INDEX IF NOT EXISTS idx_user_picks_period ON user_picks(period);
        CREATE INDEX IF NOT EXISTS idx_strategy_picks_period ON strategy_picks(period);

        CREATE TABLE IF NOT EXISTS red_freq (
            num              INTEGER PRIMARY KEY,
            count            INTEGER NOT NULL DEFAULT 0,
            last_seen_period INTEGER,
            updated_at       TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );


    """)
    conn.commit()

    # v2 migration: idempotent ALTER TABLE
    for col in ['source_type']:
        try: conn.execute(f"ALTER TABLE user_picks ADD COLUMN {col} TEXT DEFAULT 'user'")
        except Exception: pass
    for col in ['pred_r1','pred_r2','pred_r3','pred_r4','pred_r5','pred_r6']:
        try: conn.execute(f"ALTER TABLE prediction_log ADD COLUMN {col} INTEGER")
        except Exception: pass
    conn.commit()
    conn.close()
    init_performance_log()


# ============ Draws ============

def upsert_draws(rows, source_name="中彩网"):
    conn = get_db()
    conn.executemany(
        "INSERT OR REPLACE INTO draws (period, r1, r2, r3, r4, r5, r6, blue, source, fetched_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))",
        [(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], source_name) for r in rows],
    )
    conn.commit()

    # v2: refresh red_freq materialized table
    all_rows = conn.execute('SELECT r1,r2,r3,r4,r5,r6,period FROM draws ORDER BY period').fetchall()
    freq = {n: [0, 0] for n in range(1, 34)}
    for row in all_rows:
        for col in range(6):
            n = row[col]; freq[n][0] += 1; freq[n][1] = row[6]
    conn.execute('DELETE FROM red_freq')
    conn.executemany('INSERT INTO red_freq (num,count,last_seen_period) VALUES (?,?,?)',
        [(n, freq[n][0], freq[n][1]) for n in range(1, 34)])
    conn.commit()
    conn.close()


def load_draws(limit=None):
    conn = get_db()
    sql = "SELECT period, r1, r2, r3, r4, r5, r6, blue FROM draws ORDER BY period"
    if limit:
        sql += f" LIMIT {int(limit)}"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [[r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]] for r in rows]


def count_draws():
    conn = get_db()
    cnt = conn.execute("SELECT COUNT(*) FROM draws").fetchone()[0]
    conn.close()
    return cnt


# ============ Meta / Cache ============

def last_fetch_age():
    conn = get_db()
    row = conn.execute("SELECT value FROM meta WHERE key='last_fetch_time'").fetchone()
    conn.close()
    if row and row[0]:
        return time.time() - float(row[0])
    return float("inf")


def set_fetch_time():
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('last_fetch_time', ?)",
                 (str(time.time()),))
    conn.commit()
    conn.close()


# ============ Strategy Performance Log (权重优化 v4) ============

def init_performance_log():
    """创建策略表现日志表（幂等）"""
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS strategy_performance_log (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            period    INTEGER NOT NULL,
            strategy  TEXT    NOT NULL,
            red_hits  INTEGER NOT NULL,
            blue_hit  INTEGER NOT NULL,
            created_at TEXT   NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_spl_strategy ON strategy_performance_log(strategy)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_spl_period ON strategy_performance_log(period)")
    conn.commit()
    conn.close()


def insert_performance_log(period, strategy, red_hits, blue_hit):
    conn = get_db()
    conn.execute(
        "INSERT INTO strategy_performance_log (period, strategy, red_hits, blue_hit) VALUES (?, ?, ?, ?)",
        (period, strategy, red_hits, blue_hit),
    )
    conn.commit()
    conn.close()


def load_performance_log(strategy=None, limit=100):
    conn = get_db()
    if strategy:
        rows = conn.execute(
            "SELECT period, strategy, red_hits, blue_hit FROM strategy_performance_log "
            "WHERE strategy=? ORDER BY period DESC LIMIT ?",
            (strategy, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT period, strategy, red_hits, blue_hit FROM strategy_performance_log "
            "ORDER BY period DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_performance_log_since(since_period):
    """返回自某期号以来的新记录数"""
    conn = get_db()
    cnt = conn.execute(
        "SELECT COUNT(*) FROM strategy_performance_log WHERE period > ?",
        (since_period,),
    ).fetchone()[0]
    conn.close()
    return cnt


def flush_cache():
    conn = get_db()
    conn.execute("DELETE FROM meta WHERE key='last_fetch_time'")
    conn.commit()
    conn.close()


# ============ User Picks ============

def insert_user_pick(period, reds, blue, strategy="", score=0):
    conn = get_db()
    source_type = 'strategy' if strategy else 'user'
    conn.execute(
        "INSERT INTO user_picks (period, r1, r2, r3, r4, r5, r6, blue, strategy, score, source_type) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [period] + reds + [blue, strategy, score, source_type],
    )
    conn.commit()
    conn.close()


def load_user_picks(limit=200):
    conn = get_db()
    rows = conn.execute(
        "SELECT period, r1, r2, r3, r4, r5, r6, blue, strategy, score, created_at "
        "FROM user_picks ORDER BY period DESC LIMIT ?", (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============ Strategy Weights ============

def save_strategy_weights(weights, perf):
    conn = get_db()
    for name, w in weights.items():
        p = perf.get(name, {})
        conn.execute(
            "INSERT OR REPLACE INTO strategy_weights (name, weight, hits, tries) VALUES (?, ?, ?, ?)",
            (name, w, p.get("hits", 0), p.get("tries", 0)),
        )
    conn.commit()
    conn.close()


def load_strategy_weights():
    conn = get_db()
    rows = conn.execute("SELECT name, weight, hits, tries FROM strategy_weights").fetchall()
    conn.close()
    weights, perf = {}, {}
    for r in rows:
        weights[r["name"]] = r["weight"]
        perf[r["name"]] = {"hits": r["hits"], "tries": r["tries"]}
    return weights, perf



def load_backtest_results(limit=20):
    """获取最近回测结果."""
    conn = get_db()
    rows = conn.execute(
        "SELECT strategy, avg_red_hit, blue_hit_rate, max_hit, test_count, weight, window_size, created_at "
        "FROM backtest_results ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============ Prediction Log ============

def save_prediction_log(entries):
    conn = get_db()
    conn.executemany(
        "INSERT INTO prediction_log (period, source, reds_json, blue, pred_r1, pred_r2, pred_r3, pred_r4, pred_r5, pred_r6) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(e["period"], e["source"], e["reds_json"], e["blue"],
          e.get("pred_r1", 0), e.get("pred_r2", 0), e.get("pred_r3", 0),
          e.get("pred_r4", 0), e.get("pred_r5", 0), e.get("pred_r6", 0))
         for e in entries],
    )
    conn.commit()
    conn.close()


def update_prediction_log_actual(period, actual_reds, actual_blue):
    conn = get_db()
    actual_set = set(actual_reds)
    rows = conn.execute(
        "SELECT id, reds_json, blue FROM prediction_log WHERE period=? AND red_hits=-1", (period,)
    ).fetchall()
    for row in rows:
        pred_reds = json.loads(row["reds_json"])
        pred_blue = row["blue"]
        red_hits = len(set(pred_reds) & actual_set)
        blue_hit = 1 if pred_blue == actual_blue else 0
        conn.execute(
            "UPDATE prediction_log SET actual_reds_json=?, actual_blue=?, red_hits=?, blue_hit=? WHERE id=?",
            (json.dumps(sorted(actual_reds)), actual_blue, red_hits, blue_hit, row["id"]),
        )
    conn.commit()
    conn.close()


def load_prediction_log(limit=100, period=None):
    conn = get_db()
    if period:
        rows = conn.execute(
            "SELECT * FROM prediction_log WHERE period=? ORDER BY created_at DESC", (period,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM prediction_log ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def prediction_log_stats():
    conn = get_db()
    stats = {}
    rows = conn.execute(
        "SELECT source, red_hits, blue_hit FROM prediction_log WHERE red_hits >= 0"
    ).fetchall()
    for r in rows:
        src = r["source"]
        if src not in stats:
            stats[src] = {"total": 0, "red_sum": 0, "blue_sum": 0, "max_hit": 0}
        stats[src]["total"] += 1
        stats[src]["red_sum"] += r["red_hits"]
        stats[src]["blue_sum"] += r["blue_hit"]
        stats[src]["max_hit"] = max(stats[src]["max_hit"], r["red_hits"])
    for src in stats:
        s = stats[src]
        s["avg_red"] = round(s["red_sum"] / s["total"], 2) if s["total"] > 0 else 0
        s["blue_rate"] = round(s["blue_sum"] / s["total"] * 100, 1) if s["total"] > 0 else 0
    conn.close()
    return stats
