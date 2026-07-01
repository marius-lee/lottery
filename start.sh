#!/bin/bash
# 双色球智能选号 — 启动 (开发/生产)
#   ./start.sh         生产模式 (app.py 直启)
#   ./start.sh --dev   开发模式 (run.py 自动重启)
cd "$(dirname "$0")"

PYTHON=.venv/bin/python3
[ -f "$PYTHON" ] || PYTHON=python3

if [ "$1" = "--dev" ]; then
    echo "🔁 开发模式 (自动重启)"
    exec $PYTHON run.py
else
    echo "🚀 启动双色球..."
    mkdir -p logs
    $PYTHON app.py >> logs/server.log 2>> logs/server.err &
    sleep 1
    open http://localhost:8520 2>/dev/null || true
    echo "  http://localhost:8520"
    echo "  logs: logs/server.log"
    wait
fi
