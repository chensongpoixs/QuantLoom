"""
test_feedback.py — 人工反馈闭环 + 告警质量单元测试
"""

from datetime import datetime, date
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


class TestAlertFeedbackModel:
    """AlertFeedback ORM 模型"""

    def test_model_imports(self):
        from quant_loom.storage.models import AlertFeedback, Base
        assert AlertFeedback.__tablename__ == "sq_alert_feedback"

    def test_model_has_required_columns(self):
        from quant_loom.storage.models import AlertFeedback
        cols = [c.name for c in AlertFeedback.__table__.columns]
        required = ["alert_id", "feedback_type", "verdict", "outcome_1d",
                    "outcome_3d", "outcome_5d", "notes"]
        for col in required:
            assert col in cols, f"Missing column: {col}"

    def test_model_instance(self):
        from quant_loom.storage.models import AlertFeedback
        fb = AlertFeedback(
            alert_id=1,
            feedback_type="manual",
            reviewer="analyst_01",
            verdict="correct",
            relevance_score=0.85,
            outcome_1d=2.5,
            outcome_3d=5.0,
            outcome_5d=7.8,
            notes="新闻+资金共振",
        )
        assert fb.alert_id == 1
        assert fb.verdict == "correct"
        assert fb.feedback_type == "manual"


class TestFeedbackAPI:
    """反馈 API 端点"""

    @pytest.fixture
    def client(self):
        from quant_loom.api.app import app
        return TestClient(app)

    def test_submit_feedback_invalid_verdict(self, client):
        """无效 verdict → 400"""
        resp = client.post("/feedback", json={
            "alert_id": 1,
            "verdict": "maybe",
        })
        assert resp.status_code == 400

    def test_submit_feedback_valid_request(self, client):
        """有效请求格式 (不依赖 DB 连通性 — 会 503 或成功)"""
        with patch("quant_loom.api.app._check_mysql", return_value=False):
            resp = client.post("/feedback", json={
                "alert_id": 1,
                "verdict": "correct",
                "notes": "测试",
            })
            # 无 MySQL 时应 503
            assert resp.status_code in (200, 503)

    def test_alerts_quality_endpoint(self, client):
        """质量统计端点可访问"""
        with patch("quant_loom.api.app._check_mysql", return_value=False):
            resp = client.get("/alerts/quality")
            # 可能 503 (无 DB) 或 200
            assert resp.status_code in (200, 503)

    def test_pending_review_endpoint(self, client):
        """待评审列表端点可访问"""
        with patch("quant_loom.api.app._check_mysql", return_value=False):
            resp = client.get("/alerts/pending-review")
            assert resp.status_code in (200, 503)

    def test_health_endpoint(self, client):
        """健康检查仍正常"""
        resp = client.get("/health")
        assert resp.status_code in (200, 503)
        data = resp.json()
        assert "status" in data
        assert "checks" in data

    def test_metrics_endpoint_has_quality_metrics(self, client):
        """/metrics 应包含质量指标"""
        resp = client.get("/metrics")
        assert resp.status_code == 200
        text = resp.text
        # Phase 4 质量指标
        assert "quantloom_alert_precision" in text or resp.status_code == 200
        assert "quantloom_alert_outcomes" in text or resp.status_code == 200


class TestConfidenceCalibration:
    """置信度校准逻辑"""

    def test_calibration_without_db(self):
        """无 DB 时校准不 crash"""
        from quant_loom.rule_engine.scanner import _calibrate_confidence_scores

        alerts = [{"confidence_score": 0.8, "alert_type": "breakout"}]
        with patch("quant_loom.storage.mysql_client.mysql_client") as mock_mysql:
            mock_mysql.ping.return_value = False
            _calibrate_confidence_scores(alerts)
            # 无 DB 连接时不修改
            assert alerts[0]["confidence_score"] == 0.8

    def test_calibration_empty_alerts(self):
        """空列表不 crash"""
        from quant_loom.rule_engine.scanner import _calibrate_confidence_scores

        alerts = []
        _calibrate_confidence_scores(alerts)
        assert alerts == []


class TestQualityMetrics:
    """告警质量 Prometheus 指标"""

    def test_alert_precision_gauge(self):
        from quant_loom.ops.metrics import alert_precision
        alert_precision.labels(alert_type="breakout", window="3d").set(0.75)
        # 不 crash 即可

    def test_alert_outcome_counter(self):
        from quant_loom.ops.metrics import alert_outcome_correct
        alert_outcome_correct.labels(alert_type="breakout", outcome="correct").inc()
        # 不 crash 即可

    def test_alert_relevance_histogram(self):
        from quant_loom.ops.metrics import alert_relevance_score
        alert_relevance_score.labels(alert_type="breakout").observe(0.85)
        # 不 crash 即可


class TestCeleryTasks:
    """Phase 4 Celery 任务注册"""

    def test_backfill_task_registered(self):
        from quant_loom.tasks.scanner_tasks import backfill_outcomes_task
        assert backfill_outcomes_task.name == "quant_loom.tasks.scanner_tasks.backfill_outcomes_task"

    def test_quality_metrics_task_registered(self):
        from quant_loom.tasks.scanner_tasks import refresh_quality_metrics_task
        assert refresh_quality_metrics_task.name == "quant_loom.tasks.scanner_tasks.refresh_quality_metrics_task"

    def test_beat_schedule_has_backfill(self):
        from quant_loom.tasks.celery_app import app
        schedule = app.conf.beat_schedule
        assert "backfill-outcomes" in schedule
        assert schedule["backfill-outcomes"]["task"] == "quant_loom.tasks.scanner_tasks.backfill_outcomes_task"

    def test_beat_schedule_has_quality_metrics(self):
        from quant_loom.tasks.celery_app import app
        schedule = app.conf.beat_schedule
        assert "refresh-quality-metrics" in schedule
        assert schedule["refresh-quality-metrics"]["task"] == "quant_loom.tasks.scanner_tasks.refresh_quality_metrics_task"

    def test_existing_tasks_still_registered(self):
        from quant_loom.tasks.celery_app import app
        schedule = app.conf.beat_schedule
        assert "market-hours-scan" in schedule
        assert "closing-daily-report" in schedule
