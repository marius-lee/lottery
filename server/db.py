"""数据库层 — SQLite 操作 (精简版)

表:
  draws       — 中彩网开奖号码
  user_picks  — 用户保存的选号
  meta        — 元数据 (抓取时间等)
"""
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
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS draws (
            period   INTEGER PRIMARY KEY,
            r1       INTEGER NOT NULL, r2 INTEGER NOT NULL, r3 INTEGER NOT NULL,
            r4       INTEGER NOT NULL, r5 INTEGER NOT NULL, r6 INTEGER NOT NULL,
            blue     INTEGER NOT NULL,
            source   TEXT    NOT NULL DEFAULT '中彩网',
            fetched_at TEXT  NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS user_picks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            period     INTEGER NOT NULL,
            r1 INTEGER NOT NULL, r2 INTEGER NOT NULL, r3 INTEGER NOT NULL,
            r4 INTEGER NOT NULL, r5 INTEGER NOT NULL, r6 INTEGER NOT NULL,
            blue       INTEGER NOT NULL,
            strategy   TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(period, r1, r2, r3, r4, r5, r6, blue)
        );
        CREATE TABLE IF NOT EXISTS meta (
            key   TEXT PRIMARY KEY, value TEXT
        );
    """)
    conn.commit()
    conn.close()


# ═══ Draws ═══

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


# ═══ User Picks ═══

def insert_user_pick(period, reds, blue, strategy=""):
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO user_picks (period, r1, r2, r3, r4, r5, r6, blue, strategy) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [period] + reds + [blue, strategy],
    )
    conn.commit()
    conn.close()


def load_user_picks(limit=200):
    conn = get_db()
    rows = conn.execute(
        "SELECT period, r1, r2, r3, r4, r5, r6, blue, strategy, created_at "
        "FROM user_picks ORDER BY period DESC LIMIT ?", (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ═══ Meta / Cache ═══

def last_fetch_age():
    conn = get_db()
    row = conn.execute("SELECT value FROM meta WHERE key='last_fetch_time'").fetchone()
    conn.close()
    return time.time() - float(row[0]) if (row and row[0]) else float("inf")


def set_fetch_time():
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('last_fetch_time', ?)",
                 (str(time.time()),))
    conn.commit()
    conn.close()


def flush_cache():
    conn = get_db()
    conn.execute("DELETE FROM meta WHERE key='last_fetch_time'")
    conn.commit()
    conn.close()
