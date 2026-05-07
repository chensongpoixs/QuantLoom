"""告警去重单元测试"""

import pytest
from quant_loom.rule_engine.dedup import AlertDeduplicator


class TestDeduplicator:
    """去重逻辑"""

    def test_empty_list(self):
        dedup = AlertDeduplicator()
        result = dedup.filter_duplicates([])
        assert result == []

    def test_no_duplicates_first_pass(self):
        """首次通过的告警应该全部保留（假设 Redis 无记录）"""
        dedup = AlertDeduplicator()
        alerts = [
            {"code": "000001", "alert_type": "breakout", "trigger_reason": "测试1"},
            {"code": "000002", "alert_type": "accumulation", "trigger_reason": "测试2"},
        ]
        # 由于单元测试环境可能没有 Redis，dedup 检查默认跳过
        result = dedup.filter_duplicates(alerts)
        # 没有 Redis 时应该全保留
        assert len(result) == 2

    def test_missing_code_or_type_passes(self):
        """缺少 code 或 alert_type 的告警依然保留"""
        dedup = AlertDeduplicator()
        alerts = [
            {"code": "", "alert_type": "breakout"},
            {"code": "000001", "alert_type": ""},
            {"code": "000002", "alert_type": "breakout"},
        ]
        result = dedup.filter_duplicates(alerts)
        assert len(result) == 3

    def test_alert_key_format(self):
        from quant_loom.storage.redis_client import redis_client
        key = redis_client.alert_key("000001", "breakout")
        assert key == "alert_dedup:000001:breakout"

    def test_cooldown_default(self):
        dedup = AlertDeduplicator()
        assert dedup.cooldown_minutes == 30

    def test_cooldown_custom(self):
        dedup = AlertDeduplicator(cooldown_minutes=60)
        assert dedup.cooldown_minutes == 60
