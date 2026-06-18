#!/bin/bash
# 双色球智能选号 — 一键启动
cd "$(dirname "$0")"
echo "🚀 启动双色球..."
PYTHON=.venv/bin/python3
[ -f "$PYTHON" ] || PYTHON=python3
$PYTHON app.py &
sleep 1
open http://localhost:8520
wait
