#!/bin/bash
cd "$(dirname "$0")"
PYTHON=.venv/bin/python3
[ -f "$PYTHON" ] || PYTHON=python3
echo "🚀 自训练引擎 v5"
$PYTHON -c "from ml.self_trainer import start; start()" 2>&1 | tee .cache/training_output.log
