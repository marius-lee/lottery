#!/bin/bash
# 安装 launchd 服务: 开机自启 + 崩溃自动恢复
# 注意: 与 dev 模式互斥, 安装前自动停掉开发服务器
set -e

cd "$(dirname "$0")"

PLIST="com.lottery.ssq.plist"
TARGET="$HOME/Library/LaunchAgents/$PLIST"
PORT=8520

echo "═ 双色球 launchd 服务安装 ═"

# 1. 停掉已在运行的开发服务器 (run.py / app.py)
if lsof -ti:$PORT &>/dev/null; then
    echo "  ⚠ 端口 $PORT 已占用 → 正在停止..."
    lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
    sleep 1
    echo "  ✓ 已停止"
fi

# 2. 卸载旧服务
if launchctl list | grep -q com.lottery.ssq 2>/dev/null; then
    echo "  ⚠ 旧服务存在 → 正在卸载..."
    launchctl unload "$TARGET" 2>/dev/null || true
    echo "  ✓ 已卸载"
fi

# 3. 创建日志目录
mkdir -p logs

# 4. 复制 plist
cp "$PLIST" "$TARGET"
echo "  ✓ plist → $TARGET"

# 5. 加载服务
launchctl load "$TARGET"
echo "  ✓ 服务已加载"

# 6. 验证
sleep 2
if launchctl list | grep -q com.lottery.ssq; then
    echo "  ✓ 服务运行中 → http://localhost:$PORT"
    echo
    echo "  管理命令:"
    echo "    launchctl list | grep ssq         查看状态"
    echo "    launchctl unload $TARGET  停止服务"
    echo "    launchctl load $TARGET    启动服务"
    echo "    cat logs/server.log       查看日志"
else
    echo "  ✗ 服务未启动, 排查: cat logs/server.err"
fi
