"""规则引擎单元测试"""

import pandas as pd
import pytest

from quant_loom.rule_engine.rules import AlertResult, RuleEngine


@pytest.fixture
def engine():
    """加载默认规则配置"""
    from pathlib import Path
    import yaml

    config_path = Path(__file__).resolve().parent.parent / "config" / "rules.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return RuleEngine(config.get("scan_rules", {}))


class TestBreakout:
    """放量上攻型"""

    def test_breakout_matched(self, engine):
        row = pd.Series({
            "pct_change": 3.5,
            "turnover_amount": 200_000_000,
            "volume_ratio": 2.0,
            "main_force_ratio": 25.0,
        })
        result = engine.check_breakout(row)
        assert result.matched is True
        assert result.alert_type == "breakout"
        assert result.confidence_score > 0
        assert result.risk_level in ("P1", "P2")

    def test_breakout_pct_too_low(self, engine):
        row = pd.Series({
            "pct_change": 0.5,
            "turnover_amount": 200_000_000,
            "volume_ratio": 2.0,
            "main_force_ratio": 25.0,
        })
        result = engine.check_breakout(row)
        assert result.matched is False

    def test_breakout_pct_too_high(self, engine):
        row = pd.Series({
            "pct_change": 8.0,  # 超过 7% 上限
            "turnover_amount": 200_000_000,
            "volume_ratio": 2.0,
            "main_force_ratio": 25.0,
        })
        result = engine.check_breakout(row)
        assert result.matched is False

    def test_breakout_low_turnover(self, engine):
        row = pd.Series({
            "pct_change": 3.5,
            "turnover_amount": 10_000_000,  # 低于1亿
            "volume_ratio": 2.0,
            "main_force_ratio": 25.0,
        })
        result = engine.check_breakout(row)
        assert result.matched is False

    def test_breakout_low_main_force(self, engine):
        row = pd.Series({
            "pct_change": 3.5,
            "turnover_amount": 200_000_000,
            "volume_ratio": 2.0,
            "main_force_ratio": 5.0,  # 低于 20%
        })
        result = engine.check_breakout(row)
        assert result.matched is False


class TestAccumulation:
    """底部吸筹型"""

    def test_accumulation_matched(self, engine):
        row = pd.Series({
            "near_250d_low": True,
            "main_force_ratio": 15.0,
        })
        result = engine.check_accumulation(row, consecutive_inflow_days=5)
        assert result.matched is True
        assert result.alert_type == "accumulation"

    def test_accumulation_not_near_low(self, engine):
        row = pd.Series({
            "near_250d_low": False,
            "main_force_ratio": 15.0,
        })
        result = engine.check_accumulation(row, consecutive_inflow_days=5)
        assert result.matched is False

    def test_accumulation_insufficient_days(self, engine):
        row = pd.Series({
            "near_250d_low": True,
            "main_force_ratio": 15.0,
        })
        result = engine.check_accumulation(row, consecutive_inflow_days=1)
        assert result.matched is False


class TestTailChasing:
    """尾盘抢筹型"""

    def test_tail_chasing_matched(self, engine):
        row = pd.Series({
            "pct_change": 3.0,
            "turnover_amount": 200_000_000,
            "main_force_ratio": 15.0,
            "active_buy_ratio": 60.0,
        })
        result = engine.check_tail_chasing(row)
        # 注意：is_tail_window 取决于当前时间
        assert result.matched is True

    def test_tail_chasing_negative_pct(self, engine):
        row = pd.Series({
            "pct_change": -2.0,
            "turnover_amount": 200_000_000,
            "main_force_ratio": 15.0,
        })
        result = engine.check_tail_chasing(row)
        assert result.matched is False


class TestEventDriven:
    """事件驱动型"""

    def test_event_driven_no_event(self, engine):
        row = pd.Series({
            "pct_change": 4.0,
            "turnover_amount": 150_000_000,
            "main_force_ratio": 20.0,
        })
        result = engine.check_event_driven(row, has_event=False)
        assert result.matched is True
        assert result.risk_level == "P2"

    def test_event_driven_with_event(self, engine):
        row = pd.Series({
            "pct_change": 5.0,
            "turnover_amount": 200_000_000,
            "main_force_ratio": 25.0,
        })
        result = engine.check_event_driven(row, has_event=True)
        assert result.matched is True
        assert result.risk_level == "P1"
        assert result.confidence_score >= 0.7

    def test_event_driven_low_main_force(self, engine):
        row = pd.Series({
            "pct_change": 5.0,
            "turnover_amount": 200_000_000,
            "main_force_ratio": 5.0,
        })
        result = engine.check_event_driven(row)
        assert result.matched is False


class TestSectorLinked:
    """板块联动型"""

    def test_sector_linked_matched(self, engine):
        row = pd.Series({"code": "000001"})
        sector_stats = {
            "sector_name": "银行",
            "avg_pct_change": 2.5,
            "rising_count": 8,
        }
        result = engine.check_sector_linked(row, sector_stats)
        assert result.matched is True
        assert result.alert_type == "sector_linked"

    def test_sector_linked_weak(self, engine):
        row = pd.Series({"code": "000001"})
        sector_stats = {
            "sector_name": "银行",
            "avg_pct_change": 0.5,  # 低于阈值
            "rising_count": 1,
        }
        result = engine.check_sector_linked(row, sector_stats)
        assert result.matched is False

    def test_sector_linked_no_stats(self, engine):
        row = pd.Series({"code": "000001"})
        result = engine.check_sector_linked(row, None)
        assert result.matched is False


class TestAlertResult:
    """AlertResult 数据类"""

    def test_default_not_matched(self):
        r = AlertResult()
        assert r.matched is False
        assert r.alert_type == ""
        assert r.confidence_score == 0.0

    def test_matched_result(self):
        r = AlertResult(
            matched=True,
            alert_type="breakout",
            trigger_reason="测试",
            confidence_score=0.85,
            risk_level="P1",
        )
        assert r.matched is True
        assert r.alert_type == "breakout"
