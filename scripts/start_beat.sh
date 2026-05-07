#!/usr/bin/env bash
# QuantLoom Celery Beat 定时调度启动脚本
# 用法: bash scripts/start_beat.sh

set -euo pipefail

cd "$(dirname "$0")/.."

exec celery -A quant_loom.tasks.celery_app beat \
    -l info \
    --scheduler celery.beat:PersistentScheduler
