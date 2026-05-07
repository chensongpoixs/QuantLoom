#!/usr/bin/env bash
# QuantLoom·量梭 Celery Worker 启动脚本
# 用法: bash scripts/start_worker.sh

set -euo pipefail

cd "$(dirname "$0")/.."

exec celery -A quant_loom.tasks.celery_app worker \
    -l info \
    --concurrency=2 \
    --max-tasks-per-child=50 \
    -Q celery
