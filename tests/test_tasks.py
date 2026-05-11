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

"""
test_tasks.py — Celery 任务单元测试
"""

import pytest
from unittest.mock import patch, MagicMock


class TestCeleryApp:
    """Celery 应用配置"""

    def test_app_created(self):
        from quant_loom.tasks.celery_app import app
        assert app.main == "quant_loom"

    def test_beat_schedule_has_scan_task(self):
        from quant_loom.tasks.celery_app import app
        schedule = app.conf.beat_schedule
        assert "market-hours-scan" in schedule
        assert schedule["market-hours-scan"]["task"] == "quant_loom.tasks.scanner_tasks.scan_task"
        assert schedule["market-hours-scan"]["schedule"] == 600.0  # 10 min

    def test_beat_schedule_has_closing_report(self):
        from quant_loom.tasks.celery_app import app
        schedule = app.conf.beat_schedule
        assert "closing-daily-report" in schedule
        task = schedule["closing-daily-report"]["task"]
        assert task == "quant_loom.tasks.scanner_tasks.closing_report_task"

    def test_task_serializer_is_json(self):
        from quant_loom.tasks.celery_app import app
        assert app.conf.task_serializer == "json"

    def test_timeout_settings(self):
        from quant_loom.tasks.celery_app import app
        assert app.conf.task_soft_time_limit == 600
        assert app.conf.task_time_limit == 900


class TestScanTask:
    """扫描任务"""

    def test_scan_task_registered(self):
        from quant_loom.tasks.scanner_tasks import scan_task
        assert scan_task.name == "quant_loom.tasks.scanner_tasks.scan_task"

    def test_scan_task_has_max_retries(self):
        from quant_loom.tasks.scanner_tasks import scan_task
        assert scan_task.max_retries == 2

    def test_scan_task_calls_main(self):
        from quant_loom.tasks.scanner_tasks import scan_task
        with patch("quant_loom.tasks.scanner_tasks._load_main") as mock_load, \
             patch("quant_loom.tasks.scanner_tasks.is_trading_time", return_value=True):
            mock_main = mock_load.return_value
            # 调用底层函数 (绕过 Celery task 包装)
            scan_task.run()
            mock_main.assert_called_once_with(dry_run=False, top_n=10, skip_events=False)

    def test_scan_task_skips_outside_trading_hours(self):
        """非交易时段跳过扫描"""
        from quant_loom.tasks.scanner_tasks import scan_task
        with patch("quant_loom.tasks.scanner_tasks._load_main") as mock_load, \
             patch("quant_loom.tasks.scanner_tasks.is_trading_time", return_value=False):
            scan_task.run()
            mock_load.assert_not_called()

    def test_scan_task_skips_when_cluster_lock_held(self):
        """互斥锁已被占用时跳过，避免多任务并发打 AkShare"""
        from quant_loom.tasks.scanner_tasks import scan_task
        with patch("quant_loom.tasks.scanner_tasks._load_main") as mock_load, \
             patch("quant_loom.tasks.scanner_tasks.is_trading_time", return_value=True), \
             patch("quant_loom.tasks.scanner_tasks._begin_scan_lock", return_value=None):
            scan_task.run()
            mock_load.assert_not_called()


class TestClosingReportTask:
    """收盘日报任务"""

    def test_closing_report_task_registered(self):
        from quant_loom.tasks.scanner_tasks import closing_report_task
        assert closing_report_task.name == "quant_loom.tasks.scanner_tasks.closing_report_task"
