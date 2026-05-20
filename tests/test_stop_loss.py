"""Tests for stop loss / take profit calculator."""

import numpy as np
import pandas as pd
import pytest

from quant_loom.feature_engineering.stop_loss import StopLossCalculator


class TestStopLoss:
    @pytest.fixture
    def kline(self):
        np.random.seed(42)
        dates = pd.date_range("2026-01-01", periods=60, freq="B")
        close = 50 + np.cumsum(np.random.normal(0.1, 1.0, 60))
        high = close + np.abs(np.random.normal(0.5, 0.3, 60))
        low = close - np.abs(np.random.normal(0.5, 0.3, 60))
        return pd.DataFrame({"close": close, "high": high, "low": low, "open": close}, index=dates)

    def test_atr_stop(self, kline):
        result = StopLossCalculator.atr_stop(kline)
        assert "stop_price" in result
        assert "atr" in result
        assert result["stop_price"] < result["highest_price"]
        assert result["method"] == "atr_stop"

    def test_atr_stop_empty(self):
        result = StopLossCalculator.atr_stop(pd.DataFrame())
        assert result == {}

    def test_atr_stop_missing_columns(self):
        result = StopLossCalculator.atr_stop(pd.DataFrame({"close": [10, 11, 12]}))
        assert result == {}

    def test_ma_stop(self, kline):
        result = StopLossCalculator.ma_stop(kline)
        assert "stop_price" in result
        assert "current_price" in result
        assert result["period"] == 20
        assert result["method"] == "ma_stop"

    def test_ma_stop_short_data(self):
        kline = pd.DataFrame({"close": [10, 11, 12]})
        result = StopLossCalculator.ma_stop(kline, period=20)
        assert result == {}

    def test_swing_low_stop(self, kline):
        result = StopLossCalculator.swing_low_stop(kline, lookback=20)
        assert "stop_price" in result
        assert result["method"] == "swing_low_stop"
        assert result["stop_price"] <= result["current_price"]

    def test_trailing_stop(self, kline):
        result = StopLossCalculator.trailing_stop(kline, pct=5.0)
        assert "stop_price" in result
        assert result["method"] == "trailing_stop"
        # trailing stop at 5% below highest
        assert result["stop_price"] == pytest.approx(result["highest_price"] * 0.95, rel=1e-3)

    def test_compute_all_stops(self, kline):
        all_stops = StopLossCalculator.compute_all_stops(kline)
        assert "atr" in all_stops
        assert "ma" in all_stops
        assert "swing_low" in all_stops
        assert "trailing" in all_stops

    def test_suggest_stop_tight(self, kline):
        suggestion = StopLossCalculator.suggest_stop(kline, risk_tolerance="tight")
        assert "recommended_stop" in suggestion
        assert "strategies" in suggestion
        assert suggestion["risk_tolerance"] == "tight"
        assert "atr" in suggestion["strategies"]

    def test_suggest_stop_medium(self, kline):
        suggestion = StopLossCalculator.suggest_stop(kline, risk_tolerance="medium")
        assert suggestion["risk_tolerance"] == "medium"
        assert suggestion["recommended_stop"] > 0

    def test_suggest_stop_loose(self, kline):
        suggestion = StopLossCalculator.suggest_stop(kline, risk_tolerance="loose")
        assert suggestion["risk_tolerance"] == "loose"

    def test_empty_kline_all_methods(self):
        empty = pd.DataFrame()
        assert StopLossCalculator.atr_stop(empty) == {}
        assert StopLossCalculator.ma_stop(empty) == {}
        assert StopLossCalculator.swing_low_stop(empty) == {}
        assert StopLossCalculator.trailing_stop(empty) == {}
        all_stops = StopLossCalculator.compute_all_stops(empty)
        assert all_stops["atr"] == {}
        suggestion = StopLossCalculator.suggest_stop(empty)
        assert suggestion["recommended_stop"] == 0
