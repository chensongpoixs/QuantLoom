"""价格特征工程测试"""
import pandas as pd
import pytest
from quant_loom.feature_engineering.price import PriceFeatures


class TestVolumeRatio:
    def test_with_avg_volume(self):
        row = pd.Series({"volume": 1500000})
        result = PriceFeatures.volume_ratio(row, avg_volume=1000000)
        assert result == 1.5

    def test_without_avg_volume(self):
        row = pd.Series({"volume": 500000})
        result = PriceFeatures.volume_ratio(row)
        assert result == 1.0

    def test_missing_volume(self):
        row = pd.Series({})
        result = PriceFeatures.volume_ratio(row, avg_volume=1000000)
        assert result == 0.0

    def test_zero_avg_volume(self):
        row = pd.Series({"volume": 1000})
        result = PriceFeatures.volume_ratio(row, avg_volume=0)
        assert result == 1.0


class TestPctChangeNormalized:
    def test_rounds_to_4_decimals(self):
        result = PriceFeatures.pct_change_normalized(3.1415926)
        assert result == 3.1416

    def test_handles_none(self):
        result = PriceFeatures.pct_change_normalized(None)
        assert result == 0.0

    def test_negative_value(self):
        result = PriceFeatures.pct_change_normalized(-5.5)
        assert result == -5.5


class TestNear52wLow:
    def test_with_current_pct_from_low_within_threshold(self):
        result = PriceFeatures.near_52w_low(None, current_pct_from_low=10.0)
        assert result is True

    def test_with_current_pct_from_low_above_threshold(self):
        result = PriceFeatures.near_52w_low(None, current_pct_from_low=20.0)
        assert result is False

    def test_with_pct_change_ytd_below_negative_30(self):
        result = PriceFeatures.near_52w_low(pct_change_ytd=-35.0)
        assert result is True

    def test_with_pct_change_ytd_above_negative_30(self):
        result = PriceFeatures.near_52w_low(pct_change_ytd=-25.0)
        assert result is False

    def test_with_no_data(self):
        result = PriceFeatures.near_52w_low(None)
        assert result is False

    def test_current_pct_takes_priority(self):
        # current_pct_from_low 优先于 pct_change_ytd
        result = PriceFeatures.near_52w_low(
            pct_change_ytd=-35.0,  # 这个满足条件
            current_pct_from_low=20.0,  # 但这个不满足
        )
        assert result is False


class TestComputeFeatures:
    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result = PriceFeatures.compute_features(df)
        assert result.empty

    def test_fills_numeric_columns(self):
        df = pd.DataFrame({
            "code": ["000001"],
            "pct_change": [None],
            "volume": [None],
            "turnover_amount": [None],
            "turnover_rate": [None],
        })
        result = PriceFeatures.compute_features(df)
        assert result.loc[0, "pct_change"] == 0.0
        assert result.loc[0, "volume"] == 0.0
        assert result.loc[0, "turnover_amount"] == 0.0
        assert result.loc[0, "turnover_rate"] == 0.0

    def test_preserves_valid_values(self):
        df = pd.DataFrame({
            "code": ["000001"],
            "pct_change": [3.5],
            "volume": [1e6],
            "turnover_amount": [5e7],
        })
        result = PriceFeatures.compute_features(df)
        assert result.loc[0, "pct_change"] == 3.5
        assert result.loc[0, "volume"] == 1e6
        assert result.loc[0, "turnover_amount"] == 5e7
