#!/bin/bash
# 双色球智能选号 — 启动
#   ./start.sh         生产模式 (app.py, 前台)
#   ./start.sh --dev   开发模式 (run.py 自动重启)
cd "$(dirname "$0")"

PYTHON=.venv/bin/python3
[ -f "$PYTHON" ] || PYTHON=python3
PORT=8520
SERVICE="com.lottery.ssq"
PLIST="$HOME/Library/LaunchAgents/$SERVICE.plist"

if [ "$1" = "--dev" ]; then
    # 开发模式 — 先停launchd服务, 避免端口冲突
    if launchctl list | grep -q "$SERVICE" 2>/dev/null; then
        echo "  ⚠ 检测到 launchd 服务正在运行 → 正在暂停..."
        launchctl unload "$PLIST" 2>/dev/null || true
        sleep 1
        echo "  ✓ 已暂停 (重启后自动恢复)"
    fi

    # 清占用的端口
    if lsof -ti:$PORT &>/dev/null; then
        lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
        sleep 0.5
    fi

    echo "🔁 开发模式 (文件变更自动重启)"
    exec $PYTHON run.py
fi

# 生产模式 - 不碰 launchd (如果已用 launchd 则互斥)
if launchctl list | grep -q "$SERVICE" 2>/dev/null; then
    echo "⚠ 服务已由 launchd 管理 → http://localhost:$PORT"
    echo "  停止: launchctl unload $PLIST"
    echo "  开发: $0 --dev"
    exit 0
fi

echo "🚀 启动双色球..."
mkdir -p logs
$PYTHON app.py >> logs/server.log 2>> logs/server.err &
sleep 1
open http://localhost:8520 2>/dev/null || true
echo "  http://localhost:$PORT"
echo "  logs/logs/server.log"
wait
