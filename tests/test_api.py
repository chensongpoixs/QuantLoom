"""
test_api.py — FastAPI 端点单元测试
"""

import pytest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from quant_loom.api.app import app

client = TestClient(app)


class TestHealthLive:
    """K8s liveness probe"""

    def test_live_returns_200(self):
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["alive"] is True


class TestHealthReady:
    """K8s readiness probe"""

    def test_ready_when_all_up(self):
        with patch("quant_loom.api.app._check_mysql", return_value=True), \
             patch("quant_loom.api.app._check_redis", return_value=True):
            response = client.get("/health/ready")
            assert response.status_code == 200
            assert response.json()["ready"] is True
            assert response.json()["checks"]["mysql"] == "ok"
            assert response.json()["checks"]["redis"] == "ok"

    def test_ready_when_mysql_down(self):
        with patch("quant_loom.api.app._check_mysql", return_value=False), \
             patch("quant_loom.api.app._check_redis", return_value=True):
            response = client.get("/health/ready")
            assert response.status_code == 503
            assert response.json()["ready"] is False
            assert response.json()["checks"]["mysql"] == "down"

    def test_ready_when_redis_down(self):
        with patch("quant_loom.api.app._check_mysql", return_value=True), \
             patch("quant_loom.api.app._check_redis", return_value=False):
            response = client.get("/health/ready")
            assert response.status_code == 503
            assert response.json()["ready"] is False


class TestHealth:
    """综合健康检查"""

    def test_health_all_up(self):
        with patch("quant_loom.api.app._check_mysql", return_value=True), \
             patch("quant_loom.api.app._check_redis", return_value=True):
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "ok"

    def test_health_degraded(self):
        with patch("quant_loom.api.app._check_mysql", return_value=False), \
             patch("quant_loom.api.app._check_redis", return_value=True):
            response = client.get("/health")
            assert response.status_code == 503
            assert response.json()["status"] == "degraded"


class TestMetrics:
    """/metrics 端点"""

    def test_metrics_returns_prometheus_format(self):
        response = client.get("/metrics")
        assert response.status_code == 200
        # Prometheus 格式: 包含 HELP/TYPE/实际指标行
        text = response.text
        assert "quantloom_" in text or "python_" in text
        assert "HELP" in text or "TYPE" in text

    def test_metrics_content_type(self):
        response = client.get("/metrics")
        assert "text/plain" in response.headers["content-type"]
