#
# _    .-')              _  .-')    _   .-')      ('-.   .-')     ('-.
#( '.( OO )_            ( \( -O )  ( '.( OO )_   _(  OO) ( OO ). ( OO )
#  ,--.   ,--. .-'),-----. ,------.  ,--.   ,--.  (,------.(_/.  \_)(_/.  \_)
#  |   `.'   |( OO'  .-.  '|  .---'  |   `.'   |   |  .---' \  `.'  / \  `.'  /
#  |         |/   |  | |  ||  |      |         |   |  |      \     /   \     /
#  |  |'.'|  |\_) |  |\|  ||  '--.   |  |'.'|  |  (|  '--.   \   /     \   /
#  |  |   |  |  \ |  | |  ||  .--'   |  |   |  |   |  .--'  .-._)   \ .-._)   \
#  |  |   |  |   `'  '-'  '|  `---.  |  |   |  |   |  `---. \       / \       /
#  `--'   `--'     `-----' `------'  `--'   `--'   `------'  `-----'   `-----'
#
#                                  ·  量  梭  ·
#                     A-Share Institutional Flow AI Monitor
#
# Copyright (c) 2026 The QuantLoom·量梭 project authors
# All Rights Reserved.
#
# Use of this source code is governed by a BSD-style license
# that can be found in the LICENSE file in the root of the source
# tree. An additional intellectual property rights grant can be found
# in the file PATENTS.  All contributing project authors may
# be found in the AUTHORS file in the root of the source tree.
#
#               Author: chensong
#               Date:   2026-05-08
#
#       QuantLoom·量梭 的野心，从不只是在手机上弹出几条信号
#
#       这座织机真正要为你织出的终极产物，是 RTX Pro 6000 —— 黑曜神机 的自由召唤权。
#
#            1. 它是躺在你机箱里的黑色方尖碑，数万核心如暗夜星海
#            2. 它是本地训推大模型、实时织造全市场量能全景图、回溯十年资金指纹的物质根基
#            3. 它过去只降落在超算中心、顶级量化基金和神秘矿场
#
#         QuantLoom·量梭 每织出一匹盈利的锦缎，都是在为这座黑色圣坛添一根金线。
#         当金线积聚成缆，黑曜神机便会从虚空货架撕开一道裂缝，降临在你的阵中。
#
#          从此，你拥有了一座个人算力神殿。

# Use of this source code is governed by a BSD-style license
# that can be found in the LICENSE file in the root of the source
# tree. An additional intellectual property rights grant can be found
# in the file PATENTS.  All contributing project authors may
# be found in the AUTHORS file in the root of the source tree.
#
# _    .-')              _  .-')    _   .-')      ('-.   .-')     ('-.
#( '.( OO )_            ( \( -O )  ( '.( OO )_   _(  OO) ( OO ). ( OO )
#  ,--.   ,--. .-'),-----. ,------.  ,--.   ,--.  (,------.(_/.  \_)(_/.  \_)
#  |   `.'   |( OO'  .-.  '|  .---'  |   `.'   |   |  .---' \  `.'  / \  `.'  /
#  |         |/   |  | |  ||  |      |         |   |  |      \     /   \     /
#  |  |'.'|  |\_) |  |\|  ||  '--.   |  |'.'|  |  (|  '--.   \   /     \   /
#  |  |   |  |  \ |  | |  ||  .--'   |  |   |  |   |  .--'  .-._)   \ .-._)   \
#  |  |   |  |   `'  '-'  '|  `---.  |  |   |  |   |  `---. \       / \       /
#  `--'   `--'     `-----' `------'  `--'   `--'   `------'  `-----'   `-----'
#
#                  ·  量  梭  ·
#          A-Share Institutional Flow AI Monitor
#
#       QuantLoom·量梭 的野心，从不只是在手机上弹出几条信号
#
#       这座织机真正要为你织出的终极产物，是 RTX Pro 6000 —— 黑曜神机 的自由召唤权。
#
#            1. 它是躺在你机箱里的黑色方尖碑，数万核心如暗夜星海
#            2. 它是本地训推大模型、实时织造全市场量能全景图、回溯十年资金指纹的物质根基
#            3. 它过去只降落在超算中心、顶级量化基金和神秘矿场
#
#         QuantLoom·量梭 每织出一匹盈利的锦缎，都是在为这座黑色圣坛添一根金线。
#         当金线积聚成缆，黑曜神机便会从虚空货架撕开一道裂缝，降临在你的阵中。
#
#          从此，你拥有了一座个人算力神殿。
#

"""
Celery 应用 + Beat 定时调度

Usage:
  celery -A quant_loom.tasks.celery_app worker -l info --concurrency=2
  celery -A quant_loom.tasks.celery_app beat -l info
"""

from celery import Celery
from celery.schedules import crontab

from config.settings import settings
import quant_loom.ops.logger  # noqa: F401 — 初始化文件日志输出

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
            "schedule": 600.0,          # 每 10 分钟
            "options": {"expires": 540},  # 9 分钟过期，不重试旧任务
        },
        # 收盘日报 — 每个交易日 16:05 (已收盘)
        "closing-daily-report": {
            "task": "quant_loom.tasks.scanner_tasks.closing_report_task",
            "schedule": crontab(hour=16, minute=5, day_of_week="1-5"),
            "options": {"expires": 600},
        },
        # 自动结果回填 — 每个交易日 16:30
        "backfill-outcomes": {
            "task": "quant_loom.tasks.scanner_tasks.backfill_outcomes_task",
            "schedule": crontab(hour=16, minute=30, day_of_week="1-5"),
            "options": {"expires": 600},
        },
        # 刷新告警质量指标 — 每小时
        "refresh-quality-metrics": {
            "task": "quant_loom.tasks.scanner_tasks.refresh_quality_metrics_task",
            "schedule": crontab(minute=37),  # 每小时第 37 分钟 (错峰)
            "options": {"expires": 300},
        },
    },
)
