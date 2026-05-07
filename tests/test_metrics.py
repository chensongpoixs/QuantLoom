"""
test_metrics.py — Prometheus 指标单元测试
"""

import pytest
from prometheus_client import CollectorRegistry, generate_latest


class TestMetricsRegistered:
    """验证指标已注册并能正常收集"""

    def test_all_metrics_registered(self):
        from quant_loom.ops.metrics import (
            pipeline_runs,
            pipeline_duration,
            alerts_produced,
            notifications_sent,
            data_fetch_duration,
            api_call_duration,
            api_errors,
            db_health,
            retry_attempts,
            build_info,
        )
        # 所有指标都能访问，无 ImportError
        assert pipeline_runs is not None
        assert pipeline_duration is not None
        assert alerts_produced is not None
        assert notifications_sent is not None
        assert data_fetch_duration is not None
        assert api_call_duration is not None
        assert api_errors is not None
        assert db_health is not None
        assert retry_attempts is not None
        assert build_info is not None

    def test_counter_increment(self):
        from quant_loom.ops.metrics import alerts_produced

        before = alerts_produced.labels(risk_level="P1", alert_type="test")._value.get()
        alerts_produced.labels(risk_level="P1", alert_type="test").inc()
        after = alerts_produced.labels(risk_level="P1", alert_type="test")._value.get()
        assert after - before == 1

    def test_gauge_set(self):
        from quant_loom.ops.metrics import db_health

        db_health.labels(db="mysql").set(1)
        assert db_health.labels(db="mysql")._value.get() == 1
        db_health.labels(db="mysql").set(0)
        assert db_health.labels(db="mysql")._value.get() == 0

    def test_histogram_observe(self):
        from quant_loom.ops.metrics import pipeline_duration

        pipeline_duration.observe(2.5)
        # 验证不抛异常即可 — histogram 内部状态依赖 prometheus_client 实现
        assert True

    def test_build_info_has_version(self):
        from quant_loom.ops.metrics import build_info

        samples = list(build_info.collect())
        assert len(samples) > 0
        # Build info 包含 version 标签
        labels = {s.labels["version"] for s in samples[0].samples if s.labels.get("version")}
        assert len(labels) > 0
