"""数据清洗单元测试"""

import pandas as pd
import pytest

from quant_loom.data_ingestion.cleaner import DataCleaner


class TestCleanQuotes:
    """行情数据清洗"""

    def test_filter_zero_price(self):
        df = pd.DataFrame([
            {"code": "000001", "name": "平安银行", "latest": 12.5, "pct_change": 2.0,
             "turnover_amount": 1e8, "volume": 1e7, "turnover_rate": 1.5},
            {"code": "000002", "name": "停牌股", "latest": 0, "pct_change": 0,
             "turnover_amount": 0, "volume": 0, "turnover_rate": 0},
        ])
        result = DataCleaner.clean_quotes(df)
        assert len(result) == 1
        assert result.iloc[0]["code"] == "000001"

    def test_filter_nan_price(self):
        df = pd.DataFrame([
            {"code": "000001", "name": "A", "latest": 10.0, "pct_change": 1.0,
             "turnover_amount": 1e8, "volume": 1e7, "turnover_rate": 1.0},
            {"code": "000002", "name": "B", "latest": None, "pct_change": 0,
             "turnover_amount": 0, "volume": 0, "turnover_rate": 0},
        ])
        result = DataCleaner.clean_quotes(df)
        assert len(result) == 1

    def test_fill_missing_values(self):
        df = pd.DataFrame([
            {"code": "000001", "name": "A", "latest": 10.0, "pct_change": None,
             "turnover_amount": None, "volume": None, "turnover_rate": None},
        ])
        result = DataCleaner.clean_quotes(df)
        assert len(result) == 1
        assert result.iloc[0]["pct_change"] == 0.0
        assert result.iloc[0]["turnover_amount"] == 0.0

    def test_filter_extreme_turnover(self):
        df = pd.DataFrame([
            {"code": "000001", "name": "A", "latest": 10.0, "pct_change": 1.0,
             "turnover_amount": 1e11, "volume": 1e7, "turnover_rate": 1.0},  # > 500亿
        ])
        result = DataCleaner.clean_quotes(df)
        assert len(result) == 0


class TestCleanFundFlow:
    """资金流数据清洗"""

    def test_fill_na_flow_fields(self):
        df = pd.DataFrame([
            {"code": "000001", "name": "A", "super_large_net_inflow": None,
             "large_net_inflow": None, "medium_net_inflow": None,
             "small_net_inflow": None, "turnover_amount": 1e8},
        ])
        result = DataCleaner.clean_fund_flow(df)
        assert result.iloc[0]["super_large_net_inflow"] == 0
        assert result.iloc[0]["large_net_inflow"] == 0

    def test_compute_inflow_ratio(self):
        df = pd.DataFrame([
            {"code": "000001", "name": "A",
             "super_large_net_inflow": 1000,
             "large_net_inflow": 2000,
             "medium_net_inflow": -500,
             "small_net_inflow": -1000,
             "turnover_amount": 100000},
        ])
        result = DataCleaner.clean_fund_flow(df)
        assert "inflow_ratio" in result.columns


class TestCodeValidation:
    """股票代码校验"""

    def test_valid_code(self):
        assert DataCleaner.is_valid_code("000001") is True
        assert DataCleaner.is_valid_code("600519") is True

    def test_invalid_code(self):
        assert DataCleaner.is_valid_code("") is False
        assert DataCleaner.is_valid_code("abc") is False
        assert DataCleaner.is_valid_code("12345") is False

    def test_extract_exchange(self):
        assert DataCleaner.extract_exchange("600519") == "sh"
        assert DataCleaner.extract_exchange("688001") == "sh"
        assert DataCleaner.extract_exchange("000001") == "sz"
        assert DataCleaner.extract_exchange("300750") == "sz"
        assert DataCleaner.extract_exchange("830799") == "bj"
