"""Tests for LHB (Dragon-Tiger Board) fetcher, features, and rule matching."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from quant_loom.rule_engine.rules import AlertResult, RuleEngine
from quant_loom.data_ingestion.lhb_fetcher import LHBFetcher


# ================================================================
# LHBFetcher
# ================================================================

class TestLHBFetcher:
    def test_init(self):
        fetcher = LHBFetcher()
        assert fetcher is not None

    def test_fetch_features_returns_dict(self):
        fetcher = LHBFetcher()
        with patch.object(fetcher, "fetch_lhb_detail", return_value=None):
            with patch.object(fetcher, "fetch_lhb_top_list", return_value=None):
                features = fetcher.fetch_features()
        assert isinstance(features, dict)
        assert "lhb_stocks" in features
        assert "lhb_inst_stocks" in features
        assert "lhb_top_month" in features
        assert features["lhb_stocks"] == {}
        assert features["lhb_inst_stocks"] == []
        assert features["lhb_top_month"] == {}

    def test_fetch_features_with_detail_data(self):
        fetcher = LHBFetcher()
        mock_detail = pd.DataFrame([
            {"code": "000001", "lhb_net_amount": 8000, "reason": "涨幅偏离值达7%", "pct_change": 7.5},
            {"code": "000002", "lhb_net_amount": 3000, "reason": "机构专用席位买入", "pct_change": 3.2},
            {"code": "000003", "lhb_net_amount": 15000, "reason": "连续三个交易日涨幅偏离值累计达20% 机构专用", "pct_change": 9.8},
        ])
        with patch.object(fetcher, "fetch_lhb_detail", return_value=mock_detail):
            with patch.object(fetcher, "fetch_lhb_top_list", return_value=None):
                features = fetcher.fetch_features()

        assert len(features["lhb_stocks"]) == 3
        assert "000001" in features["lhb_stocks"]
        assert features["lhb_stocks"]["000001"]["net_amount"] == 8000
        # 000002 has "机构专用" in reason → should be inst
        # 000003 has "机构专用" in reason → should be inst
        assert "000002" in features["lhb_inst_stocks"]
        assert "000003" in features["lhb_inst_stocks"]
        # 000001 has no "机构" in reason → not inst
        assert "000001" not in features["lhb_inst_stocks"]

    def test_fetch_features_with_top_list(self):
        fetcher = LHBFetcher()
        mock_top = pd.DataFrame([
            {"code": "000001", "name": "平安银行", "on_board_count": 5, "total_lhb_net": 25000},
            {"code": "000002", "name": "万科A", "on_board_count": 2, "total_lhb_net": 8000},
        ])
        with patch.object(fetcher, "fetch_lhb_detail", return_value=None):
            with patch.object(fetcher, "fetch_lhb_top_list", return_value=mock_top):
                features = fetcher.fetch_features()

        assert len(features["lhb_top_month"]) == 2
        assert features["lhb_top_month"]["000001"]["count"] == 5
        assert features["lhb_top_month"]["000002"]["count"] == 2
        assert features["lhb_top_month"]["000001"]["total_net"] == 25000

    def test_fetch_features_empty_detail(self):
        fetcher = LHBFetcher()
        with patch.object(fetcher, "fetch_lhb_detail", return_value=pd.DataFrame()):
            with patch.object(fetcher, "fetch_lhb_top_list", return_value=None):
                features = fetcher.fetch_features()
        assert features["lhb_stocks"] == {}

    def test_code_padding_in_detail(self):
        """zfill is applied inside fetch_lhb_detail(), mock should reflect that."""
        fetcher = LHBFetcher()
        mock_detail = pd.DataFrame([
            {"code": "000001", "lhb_net_amount": 5000, "reason": "涨幅偏离值达7%", "pct_change": 5.0},
        ])
        with patch.object(fetcher, "fetch_lhb_detail", return_value=mock_detail):
            with patch.object(fetcher, "fetch_lhb_top_list", return_value=None):
                features = fetcher.fetch_features()
        assert "000001" in features["lhb_stocks"]
        assert len(features["lhb_stocks"]) == 1


# ================================================================
# LHB Rule: check_lhb_tracking
# ================================================================

class TestLHBRule:
    @pytest.fixture
    def engine(self):
        config = {
            "lhb_tracking": {
                "enabled": True,
                "lhb_net_amount_min": 5000,
                "retail_lhb_threshold": 20000,
                "frequent_board_bonus": True,
            }
        }
        return RuleEngine(config)

    @pytest.fixture
    def base_row(self):
        return pd.Series({
            "code": "000001",
            "pct_change": 6.0,
            "turnover_amount": 5e8,
            "main_force_ratio": 15.0,
        })

    def test_no_lhb_stocks_returns_no_match(self, engine, base_row):
        result = engine.check_lhb_tracking(base_row, lhb_stocks={})
        assert not result.matched

    def test_code_not_in_lhb_stocks(self, engine, base_row):
        result = engine.check_lhb_tracking(
            base_row,
            lhb_stocks={"000002": {"net_amount": 8000, "reason": "", "pct_change": 5.0}}
        )
        assert not result.matched

    def test_net_amount_below_threshold(self, engine, base_row):
        result = engine.check_lhb_tracking(
            base_row,
            lhb_stocks={"000001": {"net_amount": 3000, "reason": "", "pct_change": 5.0}}
        )
        assert not result.matched

    def test_basic_lhb_match(self, engine, base_row):
        result = engine.check_lhb_tracking(
            base_row,
            lhb_stocks={"000001": {"net_amount": 8000, "reason": "涨幅偏离值达7%", "pct_change": 7.0}}
        )
        assert result.matched
        assert result.alert_type == "lhb_tracking"
        assert result.confidence_score >= 0.50

    def test_institutional_seat_bonus(self, engine, base_row):
        result = engine.check_lhb_tracking(
            base_row,
            lhb_stocks={"000001": {"net_amount": 8000, "reason": "机构专用", "pct_change": 5.0}},
            lhb_inst_stocks=["000001"],
        )
        assert result.matched
        assert result.confidence_score >= 0.70  # 0.50 base + 0.20 inst

    def test_retail_large_driven(self, engine, base_row):
        """Large net buy without institutional seats → retail/游资 driven."""
        result = engine.check_lhb_tracking(
            base_row,
            lhb_stocks={"000001": {"net_amount": 25000, "reason": "涨幅偏离值达7%", "pct_change": 5.0}},
            lhb_inst_stocks=[],
        )
        assert result.matched
        assert result.confidence_score >= 0.60  # 0.50 + 0.10 retail large

    def test_frequent_board_3x_bonus(self, engine, base_row):
        result = engine.check_lhb_tracking(
            base_row,
            lhb_stocks={"000001": {"net_amount": 8000, "reason": "", "pct_change": 5.0}},
            lhb_top_month={"000001": {"count": 3, "total_net": 30000}},
        )
        assert result.matched
        assert result.confidence_score >= 0.65  # 0.50 + 0.15 frequent 3x

    def test_frequent_board_2x_bonus(self, engine, base_row):
        result = engine.check_lhb_tracking(
            base_row,
            lhb_stocks={"000001": {"net_amount": 8000, "reason": "", "pct_change": 5.0}},
            lhb_top_month={"000001": {"count": 2, "total_net": 15000}},
        )
        assert result.matched
        assert result.confidence_score >= 0.58  # 0.50 + 0.08 frequent 2x

    def test_strong_move_bonus(self, engine, base_row):
        row = base_row.copy()
        row["pct_change"] = 7.5  # >= 5%
        result = engine.check_lhb_tracking(
            row,
            lhb_stocks={"000001": {"net_amount": 8000, "reason": "", "pct_change": 7.5}},
        )
        assert result.matched
        assert result.confidence_score >= 0.55  # 0.50 + 0.05 strong move

    def test_combined_signals(self, engine, base_row):
        """All signals combined: inst + frequent + strong move."""
        row = base_row.copy()
        row["pct_change"] = 8.0
        result = engine.check_lhb_tracking(
            row,
            lhb_stocks={"000001": {"net_amount": 12000, "reason": "机构专用", "pct_change": 8.0}},
            lhb_inst_stocks=["000001"],
            lhb_top_month={"000001": {"count": 4, "total_net": 50000}},
        )
        assert result.matched
        # 0.50 + 0.20 inst + 0.15 frequent + 0.05 strong = 0.90, capped at 0.95
        assert result.confidence_score >= 0.85

    def test_confidence_score_capped(self, engine, base_row):
        """Confidence score should not exceed 0.95."""
        result = engine.check_lhb_tracking(
            base_row,
            lhb_stocks={"000001": {"net_amount": 50000, "reason": "机构专用", "pct_change": 10.0}},
            lhb_inst_stocks=["000001"],
            lhb_top_month={"000001": {"count": 10, "total_net": 200000}},
        )
        assert result.matched
        assert result.confidence_score <= 0.95

    def test_risk_level_p1_high_confidence(self, engine, base_row):
        result = engine.check_lhb_tracking(
            base_row,
            lhb_stocks={"000001": {"net_amount": 12000, "reason": "机构专用", "pct_change": 6.0}},
            lhb_inst_stocks=["000001"],
        )
        assert result.matched
        assert result.risk_level == "P1"  # score >= 0.75 with inst

    def test_risk_level_p2_low_confidence(self, engine, base_row):
        result = engine.check_lhb_tracking(
            base_row,
            lhb_stocks={"000001": {"net_amount": 6000, "reason": "", "pct_change": 2.0}},
        )
        assert result.matched
        assert result.risk_level == "P2"  # score < 0.75

    def test_disabled_rule_returns_no_match(self, engine, base_row):
        engine.config["lhb_tracking"]["enabled"] = False
        result = engine.check_lhb_tracking(
            base_row,
            lhb_stocks={"000001": {"net_amount": 8000, "reason": "", "pct_change": 5.0}},
        )
        assert not result.matched


# ================================================================
# Scanner integration
# ================================================================

class TestScannerLHBIntegration:
    """Tests that scanner.scan() correctly passes lhb_features to rule engine."""

    def test_scan_with_lhb_features(self):
        from quant_loom.rule_engine.scanner import MarketScanner

        scanner_inst = MarketScanner()
        quotes = pd.DataFrame([
            {"code": "000001", "pct_change": 6.0, "turnover_amount": 5e8,
             "volume_ratio": 2.0, "main_force_ratio": 25.0},
        ])
        fund_flow = pd.DataFrame([
            {"code": "000001", "main_force_ratio": 25.0, "net_inflow": 5000,
             "super_large_ratio": 30.0, "large_ratio": 10.0},
        ])
        lhb_features = {
            "lhb_stocks": {"000001": {"net_amount": 12000, "reason": "机构专用", "pct_change": 6.0}},
            "lhb_inst_stocks": ["000001"],
            "lhb_top_month": {"000001": {"count": 3, "total_net": 36000}},
        }

        results = scanner_inst.scan(quotes, fund_flow, lhb_features=lhb_features)
        alert_types = [r[0].alert_type for r in results]
        assert "lhb_tracking" in alert_types

    def test_scan_without_lhb_features(self):
        from quant_loom.rule_engine.scanner import MarketScanner

        scanner_inst = MarketScanner()
        quotes = pd.DataFrame([
            {"code": "000001", "pct_change": 6.0, "turnover_amount": 5e8,
             "volume_ratio": 2.0, "main_force_ratio": 25.0},
        ])
        fund_flow = pd.DataFrame([
            {"code": "000001", "main_force_ratio": 25.0, "net_inflow": 5000,
             "super_large_ratio": 30.0, "large_ratio": 10.0},
        ])

        results = scanner_inst.scan(quotes, fund_flow)  # no lhb_features
        alert_types = [r[0].alert_type for r in results]
        assert "lhb_tracking" not in alert_types


# ================================================================
# AlertResult dataclass
# ================================================================

class TestAlertResult:
    def test_default_values(self):
        result = AlertResult()
        assert result.matched is False
        assert result.alert_type == ""
        assert result.confidence_score == 0.0
        assert result.risk_level == "P3"

    def test_lhb_alert_fields(self):
        result = AlertResult(
            matched=True,
            alert_type="lhb_tracking",
            trigger_reason="LHB net buy=8000万; institutional seats present",
            confidence_score=0.75,
            risk_level="P1",
            details={"code": "000001", "net_amount": 8000, "has_inst": True},
        )
        assert result.matched
        assert result.alert_type == "lhb_tracking"
        assert result.confidence_score == 0.75
        assert result.details["has_inst"] is True
