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
        assert schedule["market-hours-scan"]["schedule"] == 300.0  # 5 min

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
        with patch("scripts.run_scanner.main") as mock_main:
            # 调用底层函数 (绕过 Celery task 包装)
            scan_task.run()
            mock_main.assert_called_once_with(dry_run=False, top_n=10, skip_events=False)


class TestClosingReportTask:
    """收盘日报任务"""

    def test_closing_report_task_registered(self):
        from quant_loom.tasks.scanner_tasks import closing_report_task
        assert closing_report_task.name == "quant_loom.tasks.scanner_tasks.closing_report_task"
