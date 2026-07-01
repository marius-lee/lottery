#!/usr/bin/env python3
"""双色球智能选号 — 近期偏差加权出号"""
import http.server
import socket
import threading
import time
from server import db
from server.handler import Handler

HOST, PORT = "0.0.0.0", 8520


def main():
    db.init_db()

    def _bg_fetch():
        time.sleep(3)
        try:
            from server import fetcher
            source, _, count = fetcher.fetch_data(force=True)
            print(f"[Data] {source}: {'+' + str(count) + ' new' if count else 'up to date'}", flush=True)
        except Exception as e:
            print(f"[Data] 后台拉取失败: {e}", flush=True)

    threading.Thread(target=_bg_fetch, daemon=True).start()

    draw_cnt = db.count_draws()
    print(f"\n  双色球 · 近期偏差加权出号", flush=True)
    print(f"  http://localhost:{PORT}", flush=True)
    if draw_cnt > 0:
        print(f"  开奖数据: {draw_cnt} 期", flush=True)
    else:
        print(f"  ⚠ 无本地数据 — 请点击「更新数据」", flush=True)
    print(flush=True)

    server = http.server.HTTPServer((HOST, PORT), Handler)
    server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        print(f"  ✅ 服务已启动 → http://localhost:{PORT}\n", flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止", flush=True)
        server.server_close()
    except OSError as e:
        if e.errno == 48:
            print(f"\n  ❌ 端口 {PORT} 被占用 — lsof -ti:{PORT} | xargs kill -9", flush=True)
        else:
            raise


if __name__ == "__main__":
    main()
