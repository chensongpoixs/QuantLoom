"""资金流特征工程测试"""
import pandas as pd
import pytest
from quant_loom.feature_engineering.fund_flow import FundFlowFeatures


class TestSuperLargeInflowRatio:
    def test_valid_inflow(self):
        row = pd.Series({"turnover_amount": 1e8, "super_large_net_inflow": 2e7})
        result = FundFlowFeatures.super_large_inflow_ratio(row)
        assert result == 20.0

    def test_zero_turnover(self):
        row = pd.Series({"turnover_amount": 0, "super_large_net_inflow": 1e6})
        result = FundFlowFeatures.super_large_inflow_ratio(row)
        assert result == 0.0

    def test_missing_columns(self):
        row = pd.Series({})
        result = FundFlowFeatures.super_large_inflow_ratio(row)
        assert result == 0.0


class TestLargeInflowRatio:
    def test_valid_inflow(self):
        row = pd.Series({"turnover_amount": 1e8, "large_net_inflow": 1e7})
        result = FundFlowFeatures.large_inflow_ratio(row)
        assert result == 10.0

    def test_zero_turnover(self):
        row = pd.Series({"turnover_amount": 0, "large_net_inflow": 5e6})
        result = FundFlowFeatures.large_inflow_ratio(row)
        assert result == 0.0


class TestMainForceInflowRatio:
    def test_valid(self):
        row = pd.Series({
            "turnover_amount": 1e8,
            "super_large_net_inflow": 1e7,
            "large_net_inflow": 5e6,
        })
        result = FundFlowFeatures.main_force_inflow_ratio(row)
        assert result == 15.0

    def test_zero_turnover(self):
        row = pd.Series({
            "turnover_amount": 0,
            "super_large_net_inflow": 1e7,
            "large_net_inflow": 5e6,
        })
        result = FundFlowFeatures.main_force_inflow_ratio(row)
        assert result == 0.0

    def test_missing_columns(self):
        row = pd.Series({})
        result = FundFlowFeatures.main_force_inflow_ratio(row)
        assert result == 0.0


class TestNetInflow:
    def test_sum_all_flow_types(self):
        row = pd.Series({
            "super_large_net_inflow": 1e7,
            "large_net_inflow": 5e6,
            "medium_net_inflow": -2e6,
            "small_net_inflow": -3e6,
        })
        result = FundFlowFeatures.net_inflow(row)
        assert result == 1e7  # 10M + 5M - 2M - 3M = 10M

    def test_missing_all(self):
        row = pd.Series({})
        result = FundFlowFeatures.net_inflow(row)
        assert result == 0.0


class TestComputeFeatures:
    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result = FundFlowFeatures.compute_features(df)
        assert result.empty

    def test_adds_feature_columns(self):
        df = pd.DataFrame({
            "code": ["000001"],
            "turnover_amount": [1e8],
            "super_large_net_inflow": [1e7],
            "large_net_inflow": [5e6],
            "medium_net_inflow": [-2e6],
            "small_net_inflow": [-3e6],
        })
        result = FundFlowFeatures.compute_features(df)
        assert "super_large_ratio" in result.columns
        assert "large_ratio" in result.columns
        assert "main_force_ratio" in result.columns
        assert "net_inflow" in result.columns
        assert result.loc[0, "main_force_ratio"] == 15.0
        assert result.loc[0, "net_inflow"] == 1e7
        assert result.loc[0, "super_large_ratio"] == 10.0
        assert result.loc[0, "large_ratio"] == 5.0

    def test_preserves_original_data(self):
        df = pd.DataFrame({
            "code": ["000001"],
            "turnover_amount": [5e7],
            "super_large_net_inflow": [5e6],
            "large_net_inflow": [0],
            "medium_net_inflow": [0],
            "small_net_inflow": [0],
        })
        result = FundFlowFeatures.compute_features(df)
        # 原始列不变
        assert result.loc[0, "code"] == "000001"
