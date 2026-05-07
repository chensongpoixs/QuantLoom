"""全市场扫描器测试"""
import pandas as pd
import pytest
from datetime import datetime
from quant_loom.rule_engine.scanner import MarketScanner


@pytest.fixture
def scanner():
    return MarketScanner()


@pytest.fixture
def sample_quotes():
    return pd.DataFrame({
        "code": ["000001", "000002", "600001"],
        "name": ["平安银行", "万科A", "上证测试"],
        "latest": [12.5, 15.0, 8.0],
        "pct_change": [3.5, -3.0, 5.2],
        "volume": [5e7, 3e7, 2e7],
        "turnover_amount": [6e8, 4.5e8, 1.6e8],
        "turnover_rate": [2.5, 1.8, 3.0],
        "high": [12.8, 15.5, 8.3],
        "low": [12.0, 14.8, 7.7],
        "open": [12.2, 15.2, 8.1],
    })


@pytest.fixture
def sample_fund_flow():
    return pd.DataFrame({
        "code": ["000001", "000002"],
        "name": ["平安银行", "万科A"],
        "turnover_amount": [6e8, 4.5e8],
        "super_large_net_inflow": [6e7, -2e7],
        "large_net_inflow": [3e7, -1e7],
        "medium_net_inflow": [-2e7, 1e7],
        "small_net_inflow": [-1e7, 5e6],
    })


class TestMergeData:
    def test_merge_with_fund_flow(self, scanner, sample_quotes, sample_fund_flow):
        merged = scanner._merge_data(sample_quotes, sample_fund_flow)
        assert len(merged) == 3
        # 有资金流的股票应有计算值
        row0 = merged[merged["code"] == "000001"].iloc[0]
        assert row0["main_force_ratio"] > 0
        assert row0["net_inflow"] != 0

    def test_merge_empty_quotes(self, scanner):
        merged = scanner._merge_data(pd.DataFrame(), pd.DataFrame())
        assert merged.empty

    def test_merge_empty_fund_flow(self, scanner, sample_quotes):
        merged = scanner._merge_data(sample_quotes, pd.DataFrame())
        assert len(merged) == 3
        # 无资金流时应使用成交额百分位代理
        assert merged["main_force_ratio"].sum() > 0
        # net_inflow 应填充为 0
        assert (merged["net_inflow"] == 0).all()

    def test_code_padding(self, scanner):
        quotes = pd.DataFrame({
            "code": ["1", "123", "123456"],
            "latest": [10.0, 20.0, 30.0],
            "pct_change": [1.0, 2.0, 3.0],
            "turnover_amount": [1e7, 2e7, 3e7],
        })
        merged = scanner._merge_data(quotes, pd.DataFrame())
        codes = merged["code"].tolist()
        assert codes == ["000001", "000123", "123456"]

    def test_missing_fund_flow_columns_filled(self, scanner, sample_quotes):
        merged = scanner._merge_data(sample_quotes, pd.DataFrame())
        for col in ["main_force_ratio", "net_inflow", "super_large_ratio", "large_ratio"]:
            assert col in merged.columns

    def test_near_250d_low_computation(self, scanner, sample_quotes):
        merged = scanner._merge_data(sample_quotes, pd.DataFrame())
        assert "near_250d_low" in merged.columns
        # 000002: latest=15.0, low=14.8, high=15.5, pct_change=-3.0
        # position = (15.0-14.8)/(15.5-14.8) = 0.2/0.7 ≈ 0.286
        # position < 0.3 AND pct < -2.0 → near_250d_low = True
        row2 = merged[merged["code"] == "000002"].iloc[0]
        assert row2["near_250d_low"] == True

        # 000001: latest=12.5, low=12.0, high=12.8, pct_change=3.5
        # pct is positive → near_250d_low = False
        row1 = merged[merged["code"] == "000001"].iloc[0]
        assert row1["near_250d_low"] == False


class TestScanAndFormat:
    def test_returns_list(self, scanner, sample_quotes):
        results = scanner.scan_and_format(sample_quotes, pd.DataFrame())
        assert isinstance(results, list)

    def test_format_fields(self, scanner, sample_quotes, sample_fund_flow):
        results = scanner.scan_and_format(sample_quotes, sample_fund_flow)
        for alert in results:
            assert "code" in alert
            assert "name" in alert
            assert "alert_type" in alert
            assert "trigger_reason" in alert
            assert "pct_change" in alert
            assert "turnover_amount" in alert
            assert "main_force_ratio" in alert
            assert "confidence_score" in alert
            assert "risk_level" in alert
            assert isinstance(alert["ts"], datetime)

    def test_empty_quotes(self, scanner):
        results = scanner.scan_and_format(pd.DataFrame(), pd.DataFrame())
        assert results == []
