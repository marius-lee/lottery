#!/usr/bin/env python3
"""双色球智能选号 — 覆盖类算法（组合数学有效）

已归档 (ml/_deprecated/): GPT自训练/LSTM/XGBoost/Thompson/Sobol/Sirius/EVT/RMT/高级统计等
   — 全部经评估对中一等奖无提升。
保留活跃 (ml/): micro_portfolio (微投资组合) + covering_design (Mandel覆盖) + prize_evaluator (EV)
"""
import http.server
import socket
import threading
import time
from server import db
from server.handler import Handler

HOST = "0.0.0.0"
PORT = 8520


def main():
    db.init_db()

    # ── 后台数据刷新: 不阻塞 HTTP 服务启动 ──
    def _background_fetch():
        time.sleep(3)  # 让 HTTP 服务先起来
        try:
            from server import fetcher
            source, _, count = fetcher.fetch_data(force=True)
            label = f"+{count} new" if count else "up to date"
            print(f"[Data] {source}: {label}", flush=True)

            from server.auto_claim import auto_claim_all
            claim = auto_claim_all()
            if claim.get("claimed", 0) > 0:
                print(f"[Claim] 自动兑奖 {claim['claimed']} 注", flush=True)
        except Exception as e:
            print(f"[Data] 后台拉取失败(离线模式): {e}", flush=True)

    threading.Thread(target=_background_fetch, daemon=True).start()

    draw_cnt = db.count_draws()
    print(f"\n  双色球 — 覆盖优化引擎", flush=True)
    print(f"  浏览器: http://localhost:{PORT}", flush=True)
    print(f"  数据库: {db.DB_PATH}", flush=True)
    if draw_cnt > 0:
        print(f"  开奖数据: {draw_cnt} 期", flush=True)
    else:
        print(f"  ⚠ 无本地数据 — 请稍后点击「更新数据」拉取", flush=True)
    print(flush=True)

    # 启动定时调度器 (二/四/日 22:05 自动拉取+兑奖)
    try:
        from server.scheduler import start_scheduler
        threading.Thread(target=start_scheduler, daemon=True).start()
    except Exception as e:
        print(f"[Scheduler] 离线模式: {e}", flush=True)

    # SO_REUSEADDR: 允许端口快速复用, 避免 TIME_WAIT 阻塞
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
            print(f"\n  ❌ 端口 {PORT} 被占用", flush=True)
            print(f"  执行: lsof -ti:{PORT} | xargs kill -9", flush=True)
        else:
            raise


if __name__ == "__main__":
    main()
