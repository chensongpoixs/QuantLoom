"""
Celery 应用 + Beat 定时调度

Usage:
  celery -A quant_loom.tasks.celery_app worker -l info --concurrency=2
  celery -A quant_loom.tasks.celery_app beat -l info
"""

from celery import Celery
from celery.schedules import crontab

from config.settings import settings

redis_broker = f"{settings.redis_url}/0"
redis_backend = f"{settings.redis_url}/1"

app = Celery(
    "quant_loom",
    broker=redis_broker,
    backend=redis_backend,
    include=["quant_loom.tasks.scanner_tasks"],
)

app.conf.update(
    timezone="Asia/Shanghai",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,            # 任务完成后才确认，防止 Worker 崩溃丢失任务
    task_soft_time_limit=600,       # 10 分钟软超时 (抛出 SoftTimeLimitExceeded)
    task_time_limit=900,            # 15 分钟硬超时 (强制 SIGKILL)
    worker_prefetch_multiplier=1,   # 单机场景，逐个消费
    beat_schedule={
        "market-hours-scan": {
            "task": "quant_loom.tasks.scanner_tasks.scan_task",
            "schedule": 300.0,          # 每 5 分钟
            "options": {"expires": 240},  # 过期不重试旧任务
        },
        # 收盘日报 — 每个交易日 16:05 (已收盘)
        "closing-daily-report": {
            "task": "quant_loom.tasks.scanner_tasks.closing_report_task",
            "schedule": crontab(hour=16, minute=5, day_of_week="1-5"),
            "options": {"expires": 600},
        },
    },
)
