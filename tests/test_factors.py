"""Tests for financial data fetcher and factor models."""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock

from quant_loom.data_ingestion.finance_fetcher import FinanceFetcher
from quant_loom.feature_engineering.factors import AlphaFactors
from quant_loom.feature_engineering.factor_eval import FactorEvaluator


class TestFinanceFetcher:
    def test_init(self):
        fetcher = FinanceFetcher()
        assert fetcher is not None

    def test_fetch_features_returns_dict(self):
        fetcher = FinanceFetcher()
        with patch.object(fetcher, "fetch_performance", return_value=None):
            with patch.object(fetcher, "fetch_express_report", return_value=None):
                features = fetcher.fetch_features()
        assert isinstance(features, dict)
        assert "performance" in features
        assert "metrics_map" in features

    def test_fetch_features_with_candidates(self):
        fetcher = FinanceFetcher()
        with patch.object(fetcher, "fetch_performance", return_value=None):
            with patch.object(fetcher, "fetch_express_report", return_value=None):
                with patch.object(fetcher, "fetch_key_metrics", return_value={"pe": 15.0, "roe": 12.5}):
                    features = fetcher.fetch_features(candidate_codes=["000001"])
        assert "000001" in features["metrics_map"]
        assert features["metrics_map"]["000001"]["pe"] == 15.0

    def test_fetch_key_metrics_handles_errors(self):
        fetcher = FinanceFetcher()
        with patch.object(fetcher, "_call_ak", side_effect=Exception("API error")):
            metrics = fetcher.fetch_key_metrics("000001")
        assert metrics == {}


class TestAlphaFactors:
    @pytest.fixture
    def metrics_map(self):
        return {
            "000001": {"pe": 12.0, "pb": 1.5, "ps": 2.0, "roe": 15.0, "roa": 3.5,
                       "gross_margin": 45.0, "net_margin": 20.0, "debt_ratio": 60.0,
                       "revenue_yoy": 10.0, "net_profit_yoy": 15.0, "eps": 2.5},
            "000002": {"pe": 25.0, "pb": 3.0, "ps": 4.0, "roe": 8.0, "roa": 2.0,
                       "gross_margin": 30.0, "net_margin": 10.0, "debt_ratio": 75.0,
                       "revenue_yoy": 5.0, "net_profit_yoy": -3.0, "eps": 0.8},
            "000003": {"pe": 8.0, "pb": 0.8, "roe": 22.0, "roa": 6.0,
                       "gross_margin": 55.0, "net_margin": 25.0, "debt_ratio": 35.0,
                       "revenue_yoy": 20.0, "net_profit_yoy": 30.0, "eps": 5.0},
        }

    def test_ep_factor(self, metrics_map):
        series = AlphaFactors.ep_factor(metrics_map)
        assert "000001" in series.index
        assert series["000001"] == pytest.approx(100 / 12.0)

    def test_bp_factor(self, metrics_map):
        series = AlphaFactors.bp_factor(metrics_map)
        assert "000001" in series.index
        assert series["000001"] == pytest.approx(1 / 1.5)

    def test_roe_quality(self, metrics_map):
        series = AlphaFactors.roe_quality(metrics_map)
        assert series["000003"] == 22.0

    def test_debt_burden_negative(self, metrics_map):
        """High debt ratio -> low (more negative) score"""
        series = AlphaFactors.debt_burden(metrics_map)
        assert series["000002"] == -75.0  # highest debt, lowest score
        assert series["000003"] > series["000002"]  # low debt gets higher score

    def test_compute_all_factors(self, metrics_map):
        df = AlphaFactors.compute_all_factors(metrics_map)
        assert not df.empty
        assert df.shape[0] == 3  # 3 stocks
        assert "roe" in df.columns
        assert "ep" in df.columns

    def test_composite_score(self, metrics_map):
        df = AlphaFactors.compute_all_factors(metrics_map)
        score = AlphaFactors.compute_composite_score(df)
        assert len(score) == 3
        assert score.max() <= 100
        assert score.min() >= 0

    def test_empty_metrics(self):
        df = AlphaFactors.compute_all_factors({})
        assert df.empty
        score = AlphaFactors.compute_composite_score(df)
        assert score.empty


class TestFactorEvaluator:
    @pytest.fixture
    def factor(self):
        return pd.Series(
            [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
            index=[f"00000{i}" for i in range(1, 11)],
            name="test_factor",
        )

    @pytest.fixture
    def forward_returns(self):
        return pd.Series(
            [0.01, 0.02, 0.03, -0.01, 0.00, 0.05, 0.02, 0.04, 0.06, 0.03],
            index=[f"00000{i}" for i in range(1, 11)],
        )

    def test_ic_positive(self, factor, forward_returns):
        ic = FactorEvaluator.information_coefficient(factor, forward_returns)
        assert isinstance(ic, float)
        assert -1.0 <= ic <= 1.0

    def test_ic_small_sample(self):
        f = pd.Series([1, 2, 3], index=["a", "b", "c"])
        r = pd.Series([0.01, 0.02], index=["a", "b"])
        ic = FactorEvaluator.information_coefficient(f, r)
        assert ic == 0.0

    def test_layered_backtest(self, factor, forward_returns):
        result = FactorEvaluator.layered_backtest(factor, forward_returns, n_groups=3)
        assert "groups" in result
        assert "top_bottom_spread" in result

    def test_evaluate_all(self, factor, forward_returns):
        factor_df = pd.DataFrame({"f1": factor, "f2": factor * 2})
        result = FactorEvaluator.evaluate_all(factor_df, forward_returns)
        assert len(result) == 2
        assert "ic" in result.columns

    def test_optimal_weights(self, factor, forward_returns):
        factor_df = pd.DataFrame({"f1": factor, "f2": factor * 2})
        weights = FactorEvaluator.optimal_weights(factor_df, forward_returns)
        assert len(weights) > 0
        assert abs(sum(weights.values()) - 1.0) < 0.01
