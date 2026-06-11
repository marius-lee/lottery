#!/usr/bin/env python3
"""双色球智能选号 — 覆盖类算法（组合数学有效）

已归档 (ml/_deprecated/): GPT自训练/LSTM/XGBoost/Thompson/Sobol/Sirius/EVT/RMT/高级统计等
   — 全部经评估对中一等奖无提升。
保留活跃 (ml/): micro_portfolio (微投资组合) + covering_design (Mandel覆盖) + prize_evaluator (EV)
"""
import http.server
from server import db
from server.handler import Handler

HOST = "0.0.0.0"
PORT = 8520


def main():
    db.init_db()

    # 启动时拉取最新开奖数据
    from server import fetcher
    source, _, count = fetcher.fetch_data(force=True)
    print(f"[Data] {source}: {'+' + str(count) + ' new' if count > 0 else 'up to date'}")

    draw_cnt = db.count_draws()
    print(f"\n  双色球 — 覆盖优化引擎")
    print(f"  浏览器: http://localhost:{PORT}")
    print(f"  数据库: {db.DB_PATH}")
    print(f"  开奖数据: {draw_cnt} 期\n")

    server = http.server.HTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
        server.server_close()


if __name__ == "__main__":
    main()
