#!/bin/bash
# 安装 launchd 服务: 开机自启 + 崩溃自动恢复
set -e

PLIST="com.lottery.ssq.plist"
TARGET="$HOME/Library/LaunchAgents/$PLIST"

# 卸载旧服务 (如果存在)
launchctl unload "$TARGET" 2>/dev/null || true

# 创建 logs 目录
mkdir -p "$(dirname "$0")/logs"

# 复制 plist
cp "$(dirname "$0")/$PLIST" "$TARGET"
echo "  ✓ plist → $TARGET"

# 加载服务
launchctl load "$TARGET"
echo "  ✓ 服务已加载 (开机自启)"

# 验证
sleep 1
if launchctl list | grep -q com.lottery.ssq; then
    echo "  ✓ 服务运行中 → http://localhost:8520"
else
    echo "  ⚠ 服务未启动, 检查: cat logs/server.err"
fi
