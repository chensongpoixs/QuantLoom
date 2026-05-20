"""Tests for portfolio risk analysis."""

import numpy as np
import pandas as pd
import pytest

from quant_loom.feature_engineering.risk import RiskAnalyzer


class TestRiskAnalyzer:
    @pytest.fixture
    def returns(self):
        np.random.seed(42)
        dates = pd.date_range("2026-01-01", periods=100, freq="B")
        return pd.Series(np.random.normal(0.001, 0.02, 100), index=dates)

    @pytest.fixture
    def multi_returns(self):
        np.random.seed(42)
        dates = pd.date_range("2026-01-01", periods=100, freq="B")
        df = pd.DataFrame({
            "000001": np.random.normal(0.001, 0.02, 100),
            "000002": np.random.normal(0.0005, 0.015, 100),
            "000003": np.random.normal(0.002, 0.03, 100),
        }, index=dates)
        return df

    def test_var(self, returns):
        v = RiskAnalyzer.var(returns)
        assert v < 0  # VaR should be negative

    def test_var_small_sample(self):
        v = RiskAnalyzer.var(pd.Series([0.01, 0.02]))
        assert v == 0.0

    def test_cvar(self, returns):
        cv = RiskAnalyzer.cvar(returns)
        assert cv < 0
        assert cv <= RiskAnalyzer.var(returns)  # CVaR <= VaR

    def test_max_drawdown(self, returns):
        nav = (1 + returns).cumprod()
        dd = RiskAnalyzer.max_drawdown(nav)
        assert dd <= 0

    def test_max_drawdown_from_returns(self, returns):
        dd = RiskAnalyzer.max_drawdown_from_returns(returns)
        assert dd <= 0

    def test_sharpe_ratio(self, returns):
        sr = RiskAnalyzer.sharpe_ratio(returns)
        assert isinstance(sr, float)

    def test_sharpe_small_sample(self):
        sr = RiskAnalyzer.sharpe_ratio(pd.Series([0.01, 0.02]))
        assert sr == 0.0

    def test_sortino_ratio(self, returns):
        sr = RiskAnalyzer.sortino_ratio(returns)
        assert isinstance(sr, float)

    def test_beta(self, returns):
        np.random.seed(99)
        bench = pd.Series(
            np.random.normal(0.0005, 0.015, 100),
            index=returns.index,
        )
        beta = RiskAnalyzer.beta(returns, bench)
        assert isinstance(beta, float)

    def test_beta_small_sample(self):
        s = pd.Series([0.01, 0.02], index=pd.date_range("2026-01-01", periods=2))
        b = pd.Series([0.005, 0.01], index=s.index)
        beta = RiskAnalyzer.beta(s, b)
        assert beta == 1.0

    def test_correlation_matrix(self, multi_returns):
        corr = RiskAnalyzer.correlation_matrix(multi_returns)
        assert corr.shape == (3, 3)
        assert (np.diag(corr) == 1.0).all()

    def test_correlation_single_stock(self):
        df = pd.DataFrame({"000001": [0.01, 0.02, 0.03]})
        corr = RiskAnalyzer.correlation_matrix(df)
        assert corr.empty

    def test_portfolio_risk_report(self, multi_returns):
        report = RiskAnalyzer.portfolio_risk_report(multi_returns)
        assert "sharpe" in report
        assert "max_dd" in report
        assert "var_95" in report
        assert report["n_stocks"] == 3

    def test_portfolio_risk_report_empty(self):
        report = RiskAnalyzer.portfolio_risk_report(pd.DataFrame())
        assert report == {}

    def test_returns_from_klines(self):
        dates = pd.date_range("2026-01-01", periods=30, freq="B")
        close = 10 * (1 + np.random.normal(0.001, 0.02, 30).cumsum() / 100)
        kline = pd.DataFrame({"close": close, "high": close * 1.01, "low": close * 0.99}, index=dates)
        df = RiskAnalyzer.returns_from_klines({"000001": kline})
        assert not df.empty
        assert "000001" in df.columns

    def test_returns_from_klines_empty(self):
        df = RiskAnalyzer.returns_from_klines({})
        assert df.empty
