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
    """)
    conn.commit()
    conn.close()
    init_performance_log()
    init_training_log()


# ============ Draws ============

def upsert_draws(rows, source_name="中彩网"):
    conn = get_db()
    conn.executemany(
        "INSERT OR REPLACE INTO draws (period, r1, r2, r3, r4, r5, r6, blue, source, fetched_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))",
        [(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], source_name) for r in rows],
    )
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

def init_training_log():
    """自训练日志表 (v5). 记录每轮训练指标."""
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS training_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            model           TEXT NOT NULL,
            round_number    INTEGER NOT NULL,
            phase           TEXT NOT NULL DEFAULT 'train',
            target_period   INTEGER,
            red_hits        INTEGER DEFAULT -1,
            blue_hit        INTEGER DEFAULT -1,
            loss            REAL,
            window_size     INTEGER,
            learning_rate   REAL,
            dropout         REAL,
            duration_sec    REAL,
            best_so_far     INTEGER DEFAULT 0,
            notes           TEXT,
            created_at      TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tlog_model ON training_log(model)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tlog_target ON training_log(target_period)")
    conn.commit()
    conn.close()


def insert_training_log(model, round_number, phase='train', target_period=None,
                        red_hits=-1, blue_hit=-1, loss=None, window_size=None,
                        learning_rate=None, dropout=None, duration_sec=None,
                        best_so_far=0, notes=None):
    conn = get_db()
    conn.execute(
        "INSERT INTO training_log (model, round_number, phase, target_period, "
        "red_hits, blue_hit, loss, window_size, learning_rate, dropout, "
        "duration_sec, best_so_far, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (model, round_number, phase, target_period, red_hits, blue_hit,
         loss, window_size, learning_rate, dropout, duration_sec,
         best_so_far, notes),
    )
    conn.commit()
    conn.close()


def load_training_log(model=None, limit=100, target_period=None):
    conn = get_db()
    sql = "SELECT * FROM training_log WHERE 1=1"
    params = []
    if model:
        sql += " AND model=?"
        params.append(model)
    if target_period:
        sql += " AND target_period=?"
        params.append(target_period)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_best_hits(target_period):
    """每个模型在指定期号上的最佳命中记录"""
    conn = get_db()
    rows = conn.execute(
        "SELECT model, MAX(red_hits) as best_red, MAX(blue_hit) as best_blue, "
        "COUNT(*) as total_rounds "
        "FROM training_log WHERE target_period=? AND phase='validate' "
        "GROUP BY model",
        (target_period,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


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
    conn.execute(
        "INSERT INTO user_picks (period, r1, r2, r3, r4, r5, r6, blue, strategy, score) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [period] + reds + [blue, strategy, score],
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


# ============ Strategy Picks ============

def insert_strategy_picks(period, picks):
    conn = get_db()
    conn.executemany(
        "INSERT INTO strategy_picks (period, r1, r2, r3, r4, r5, r6, blue, strategy) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(period, *p["reds"], p["blue"], p["strategy"]) for p in picks],
    )
    conn.commit()
    conn.close()


def load_strategy_picks(period=None):
    conn = get_db()
    if period:
        rows = conn.execute(
            "SELECT period, r1, r2, r3, r4, r5, r6, blue, strategy FROM strategy_picks "
            "WHERE period=? ORDER BY strategy", (period,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT period, r1, r2, r3, r4, r5, r6, blue, strategy FROM strategy_picks "
            "ORDER BY period DESC, strategy LIMIT 500"
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


# ============ Backtest Results ============

def save_backtest_results(results, window_size):
    conn = get_db()
    for r in results:
        conn.execute(
            "INSERT INTO backtest_results (window_size, strategy, avg_red_hit, blue_hit_rate, "
            "max_hit, test_count, weight) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (window_size, r["name"], r["avg_red_hit"], r["blue_hit_rate"],
             r["max_hit"], r["test_count"], r["weight"]),
        )
    conn.commit()
    conn.close()


def load_backtest_results(limit=50):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM backtest_results ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============ Prediction Log ============

def save_prediction_log(entries):
    conn = get_db()
    conn.executemany(
        "INSERT INTO prediction_log (period, source, reds_json, blue) VALUES (?, ?, ?, ?)",
        [(e["period"], e["source"], e["reds_json"], e["blue"]) for e in entries],
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
