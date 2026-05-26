#!/usr/bin/env python3
"""双色球智能选号 — 本地服务 (SQLite 版)

启动后浏览器访问 http://localhost:8520
数据存储在 SQLite 数据库中。
"""

import http.cookiejar
import http.server
import json
import os
import re
import sqlite3
import ssl
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

HOST = "0.0.0.0"
PORT = 8520
ROOT = Path(__file__).parent
CACHE_DIR = ROOT / ".cache"
DB_PATH = CACHE_DIR / "ssq.db"
CACHE_MAX_AGE = 6 * 3600  # 6 hours

# ============ 数据库 ============


def get_db():
    """获取数据库连接（自动创建目录和表）"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """创建表结构（幂等）"""
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
    """)
    conn.commit()
    conn.close()


def db_upsert_draws(rows, source_name="中彩网"):
    """批量 upsert 开奖数据（存在则更新，不存在则插入）"""
    conn = get_db()
    conn.executemany("""
        INSERT OR REPLACE INTO draws (period, r1, r2, r3, r4, r5, r6, blue, source, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
    """, [(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], source_name) for r in rows])
    conn.commit()
    conn.close()


def db_load_draws(limit=None):
    """从数据库加载开奖数据，返回 [[period, r1..r6, blue], ...]"""
    conn = get_db()
    sql = "SELECT period, r1, r2, r3, r4, r5, r6, blue FROM draws ORDER BY period"
    if limit:
        sql += f" LIMIT {int(limit)}"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [[r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]] for r in rows]


def db_count_draws():
    conn = get_db()
    cnt = conn.execute("SELECT COUNT(*) FROM draws").fetchone()[0]
    conn.close()
    return cnt


def db_last_fetch_age():
    """返回距上次拉取的秒数；无记录时返回极大值"""
    conn = get_db()
    row = conn.execute("SELECT value FROM meta WHERE key='last_fetch_time'").fetchone()
    conn.close()
    if row and row[0]:
        return time.time() - float(row[0])
    return float("inf")


def db_set_fetch_time():
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('last_fetch_time', ?)",
                 (str(time.time()),))
    conn.commit()
    conn.close()


def db_insert_user_pick(period, reds, blue, strategy="", score=0):
    """插入一条用户生成的号码"""
    conn = get_db()
    conn.execute("""
        INSERT INTO user_picks (period, r1, r2, r3, r4, r5, r6, blue, strategy, score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [period] + reds + [blue, strategy, score])
    conn.commit()
    conn.close()


def db_load_user_picks(limit=200):
    """加载用户保存的号码"""
    conn = get_db()
    rows = conn.execute(
        "SELECT period, r1, r2, r3, r4, r5, r6, blue, strategy, score, created_at "
        "FROM user_picks ORDER BY period DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============ HTTP 客户端（Cookie 支持）============

_cwl_opener = None


def _get_cwl_opener():
    global _cwl_opener
    if _cwl_opener is not None:
        return _cwl_opener
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    https_handler = urllib.request.HTTPSHandler(context=ctx)
    cj = http.cookiejar.CookieJar()
    cookie_handler = urllib.request.HTTPCookieProcessor(cj)
    _cwl_opener = urllib.request.build_opener(https_handler, cookie_handler)
    return _cwl_opener


def _parse_ssq_items(data):
    items = data.get("result", data.get("data", []))
    if isinstance(items, dict):
        items = items.get("list", items.get("records", []))
    if not isinstance(items, list):
        return []
    results = []
    for item in items:
        code = item.get("code", item.get("drawNum", ""))
        red = item.get("red", "")
        blue = item.get("blue", "")
        if not code or not red:
            continue
        reds = [int(x) for x in re.split(r'[|, ]+', red) if x.strip().isdigit()]
        blues = [int(x) for x in re.split(r'[|, ]+', blue) if x.strip().isdigit()]
        if len(reds) == 6 and len(blues) >= 1:
            try:
                results.append([int(code)] + reds + [blues[0]])
            except ValueError:
                continue
    results.sort(key=lambda r: r[0])
    return results


def fetch_from_cwl(count=100):
    url = (
        "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/"
        f"findDrawNotice?name=ssq&issueCount={count}"
    )
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.cwl.gov.cn/ygkj/ssq/kjgg/",
    }
    req = urllib.request.Request(url, headers=headers)
    opener = _get_cwl_opener()
    resp = opener.open(req, timeout=20)
    data = json.loads(resp.read().decode("utf-8"))
    return _parse_ssq_items(data)


def fetch_from_500():
    end_p = int(f"{date.today().year}{date.today().strftime('%m')}{date.today().strftime('%d')}")
    start_p = end_p - 400
    url = f"https://datachart.500.com/ssq/history/newinc/history.php?start={start_p}&end={end_p}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    })
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    resp = urllib.request.urlopen(req, timeout=15, context=ctx)
    html = resp.read().decode("utf-8", errors="ignore")
    results = []
    for row in re.findall(r'<tr[^>]*>.*?</tr>', html, re.DOTALL):
        code_match = re.search(r'(20\d{5})', row)
        balls = re.findall(r'class="ball_red"[^>]*>(\d+)</span>', row)
        blue_ball = re.findall(r'class="ball_blue"[^>]*>(\d+)</span>', row)
        if code_match and len(balls) >= 6 and blue_ball:
            try:
                results.append([int(code_match.group(1))] + [int(b) for b in balls[:6]] + [int(blue_ball[0])])
            except ValueError:
                continue
    results.sort(key=lambda r: r[0])
    return results


# ============ 数据获取 ============


def fetch_data():
    """获取开奖数据。优先读 SQLite，过期则拉取 API。

    返回 (source_name, short_data, long_data)
    """
    age = db_last_fetch_age()

    # 缓存未过期 → 直接从 SQLite 读取
    if age < CACHE_MAX_AGE and db_count_draws() > 0:
        all_data = db_load_draws()
        if all_data:
            short_data = all_data[-100:] if len(all_data) > 100 else all_data
            long_data = all_data[-300:] if len(all_data) > 100 else []
            return "本地数据库", short_data, long_data

    # 缓存过期或为空 → 拉取 API
    results = None
    source_name = None

    try:
        results = fetch_from_cwl(300)
        if results:
            source_name = "中彩网"
    except Exception as e:
        print(f"  [中彩网] 失败: {e}", file=sys.stderr)

    if not results:
        try:
            results = fetch_from_500()
            if results:
                source_name = "500.com"
        except Exception as e:
            print(f"  [500.com] 失败: {e}", file=sys.stderr)

    if results:
        db_upsert_draws(results, source_name)
        db_set_fetch_time()
        short_data = results[-100:] if len(results) > 100 else results
        long_data = results[-300:] if len(results) > 100 else []
        return source_name, short_data, long_data

    # API 失败但数据库有旧数据 → 降级使用
    fallback = db_load_draws()
    if fallback:
        short_data = fallback[-100:] if len(fallback) > 100 else fallback
        long_data = fallback[-300:] if len(fallback) > 100 else []
        return "数据库(离线)", short_data, long_data

    return None, None, None


# ============ HTTP 服务 ============

HTML = (ROOT / "index.html").read_text()


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(HTML.encode())

        elif self.path == "/api/fetch":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            source_name, short_data, long_data = fetch_data()

            if short_data:
                resp = {
                    "ok": True,
                    "source": source_name,
                    "count": len(short_data),
                    "data": short_data,
                }
                if long_data and len(long_data) > len(short_data):
                    resp["longData"] = long_data
                    resp["longCount"] = len(long_data)
                # 附带用户保存的号码
                user_picks = db_load_user_picks()
                if user_picks:
                    resp["userPicks"] = user_picks
            else:
                resp = {
                    "ok": False,
                    "msg": "所有数据源均失败，请检查网络连接",
                }

            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode())

        elif self.path == "/api/user-picks":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            picks = db_load_user_picks()
            self.wfile.write(json.dumps({"ok": True, "picks": picks}, ensure_ascii=False).encode())

        elif self.path == "/api/stats":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            conn = get_db()
            draw_count = conn.execute("SELECT COUNT(*) FROM draws").fetchone()[0]
            pick_count = conn.execute("SELECT COUNT(*) FROM user_picks").fetchone()[0]

            # 用户号码命中率统计
            hit_stats = []
            for row in conn.execute("""
                SELECT up.period, up.r1, up.r2, up.r3, up.r4, up.r5, up.r6, up.blue,
                       up.strategy, up.score, up.created_at
                FROM user_picks up ORDER BY up.period
            """):
                up = dict(row)
                # 查找对应开奖结果
                draw = conn.execute(
                    "SELECT r1,r2,r3,r4,r5,r6,blue FROM draws WHERE period=?",
                    (up["period"],)
                ).fetchone()
                if draw:
                    draw_reds = {draw[0], draw[1], draw[2], draw[3], draw[4], draw[5]}
                    user_reds = {up["r1"], up["r2"], up["r3"], up["r4"], up["r5"], up["r6"]}
                    red_hits = len(draw_reds & user_reds)
                    blue_hit = 1 if up["blue"] == draw[6] else 0
                    hit_stats.append({
                        "period": up["period"],
                        "red_hits": red_hits,
                        "blue_hit": blue_hit,
                        "strategy": up["strategy"],
                    })
            conn.close()

            self.wfile.write(json.dumps({
                "ok": True,
                "drawCount": draw_count,
                "pickCount": pick_count,
                "hitStats": hit_stats[-50:],  # 最近 50 条
            }, ensure_ascii=False).encode())

        elif self.path == "/api/flush-cache":
            conn = get_db()
            conn.execute("DELETE FROM meta WHERE key='last_fetch_time'")
            conn.commit()
            conn.close()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "msg": "缓存标记已清除"}).encode())

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/save":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                payload = json.loads(body.decode("utf-8"))
                picks = payload.get("picks", [])
                for p in picks:
                    db_insert_user_pick(
                        period=p["period"],
                        reds=p["reds"],
                        blue=p["blue"],
                        strategy=p.get("strategy", ""),
                        score=p.get("score", 0),
                    )
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "saved": len(picks)}).encode())
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "msg": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()


def main():
    init_db()

    draw_cnt = db_count_draws()
    pick_cnt = db_load_user_picks()
    print(f"\n  双色球智能选号（SQLite 版）已启动")
    print(f"  打开浏览器访问: http://localhost:{PORT}")
    print(f"  数据库: {DB_PATH}")
    print(f"  开奖数据: {draw_cnt} 期  |  用户保存: {len(pick_cnt)} 注")
    print(f"  点击页面「更新数据」按钮自动拉取最新数据\n")

    server = http.server.HTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
        server.server_close()


if __name__ == "__main__":
    main()
