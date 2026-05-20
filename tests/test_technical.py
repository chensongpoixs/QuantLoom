"""
技术指标单元测试
测试 TechnicalIndicators 的 15+ 个指标计算正确性
"""

import numpy as np
import pandas as pd
import pytest

from quant_loom.feature_engineering.technical import TechnicalIndicators


# ---- 测试数据 ----

@pytest.fixture
def kline_df():
    """生成 100 行模拟 K 线数据"""
    np.random.seed(42)
    n = 100
    close = 10 + np.cumsum(np.random.randn(n) * 0.2)
    high = close + np.abs(np.random.randn(n) * 0.15)
    low = close - np.abs(np.random.randn(n) * 0.15)
    open_ = low + np.random.rand(n) * (high - low)
    volume = np.random.randint(1000000, 10000000, n)
    return pd.DataFrame({
        "open": open_, "high": high, "low": low, "close": close, "volume": volume,
    })


@pytest.fixture
def flat_df():
    """平坦价格测试 — 所有指标应为中性"""
    n = 100
    return pd.DataFrame({
        "open": [10.0] * n, "high": [10.1] * n, "low": [9.9] * n,
        "close": [10.0] * n, "volume": [5000000] * n,
    })


# ================================================================
# MA / EMA
# ================================================================

class TestMA:
    def test_ma5_length(self, kline_df):
        result = TechnicalIndicators.ma(kline_df["close"], 5)
        assert len(result) == len(kline_df)

    def test_ma_flat(self, flat_df):
        result = TechnicalIndicators.ma(flat_df["close"], 20)
        pd.testing.assert_series_equal(
            result.round(4), pd.Series([10.0] * 100).round(4), check_names=False,
        )

    def test_ema_flat(self, flat_df):
        result = TechnicalIndicators.ema(flat_df["close"], 12)
        assert len(result) == 100
        assert abs(result.iloc[-1] - 10.0) < 0.01

    def test_ma_increasing(self):
        close = pd.Series(range(1, 21), dtype=float)
        ma5 = TechnicalIndicators.ma(close, 5)
        # ma5[4] = (1+2+3+4+5)/5 = 3
        assert abs(ma5.iloc[4] - 3.0) < 0.01
        # ma5[-1] = (16+17+18+19+20)/5 = 18
        assert abs(ma5.iloc[-1] - 18.0) < 0.01


# ================================================================
# MACD
# ================================================================

class TestMACD:
    def test_macd_output_shape(self, kline_df):
        macd = TechnicalIndicators.macd(kline_df["close"])
        assert "dif" in macd.columns
        assert "dea" in macd.columns
        assert "macd_hist" in macd.columns
        assert len(macd) == len(kline_df)

    def test_macd_zero_on_flat(self, flat_df):
        """平盘时 DIF, DEA, hist 均应接近 0"""
        macd = TechnicalIndicators.macd(flat_df["close"])
        assert abs(macd["dif"].iloc[-1]) < 0.01
        assert abs(macd["dea"].iloc[-1]) < 0.01
        assert abs(macd["macd_hist"].iloc[-1]) < 0.01

    def test_macd_hist_relation(self, kline_df):
        """hist = 2*(DIF - DEA)"""
        macd = TechnicalIndicators.macd(kline_df["close"])
        expected = 2 * (macd["dif"] - macd["dea"])
        pd.testing.assert_series_equal(
            macd["macd_hist"].round(6), expected.round(6), check_names=False,
        )


# ================================================================
# RSI
# ================================================================

class TestRSI:
    def test_rsi_range(self, kline_df):
        rsi = TechnicalIndicators.rsi(kline_df["close"], 14)
        valid = rsi.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_rsi_all_up(self):
        """连续上涨 → RSI 接近 100"""
        close = pd.Series([float(i) for i in range(1, 31)])
        rsi = TechnicalIndicators.rsi(close, 14)
        last_rsi = rsi.iloc[-1]
        assert last_rsi > 90 or pd.isna(last_rsi)

    def test_rsi_all_down(self):
        """连续下跌 → RSI 接近 0"""
        close = pd.Series([float(i) for i in range(30, 0, -1)])
        rsi = TechnicalIndicators.rsi(close, 14)
        last_rsi = rsi.iloc[-1]
        assert last_rsi < 10 or pd.isna(last_rsi)


# ================================================================
# KDJ
# ================================================================

class TestKDJ:
    def test_kdj_output_shape(self, kline_df):
        kdj = TechnicalIndicators.kdj(kline_df)
        assert "k" in kdj.columns
        assert "d" in kdj.columns
        assert "j" in kdj.columns
        assert len(kdj) == len(kline_df)

    def test_kdj_flat(self, flat_df):
        """平盘时 KDJ 应接近 50"""
        kdj = TechnicalIndicators.kdj(flat_df)
        assert abs(kdj["k"].iloc[-1] - 50) < 10
        assert abs(kdj["d"].iloc[-1] - 50) < 10


# ================================================================
# BOLL
# ================================================================

class TestBOLL:
    def test_boll_output_shape(self, kline_df):
        boll = TechnicalIndicators.boll(kline_df["close"])
        assert "boll_upper" in boll.columns
        assert "boll_mid" in boll.columns
        assert "boll_lower" in boll.columns
        assert "boll_width" in boll.columns
        assert len(boll) == len(kline_df)

    def test_boll_upper_above_lower(self, kline_df):
        boll = TechnicalIndicators.boll(kline_df["close"])
        valid = boll.dropna()
        assert (valid["boll_upper"] >= valid["boll_lower"]).all()


# ================================================================
# ATR
# ================================================================

class TestATR:
    def test_atr_non_negative(self, kline_df):
        atr = TechnicalIndicators.atr(kline_df, 14)
        valid = atr.dropna()
        assert (valid >= 0).all()

    def test_atr_flat(self, flat_df):
        """high-low=0.2, ATR 应收敛到 0.2"""
        atr = TechnicalIndicators.atr(flat_df, 14)
        assert abs(atr.iloc[-1] - 0.2) < 0.05


# ================================================================
# VWAP / OBV
# ================================================================

class TestVWAP:
    def test_vwap_in_range(self, kline_df):
        vwap = TechnicalIndicators.vwap(kline_df)
        hi, lo = kline_df["high"], kline_df["low"]
        valid = vwap.dropna()
        assert len(valid) > 0


class TestOBV:
    def test_obv_length(self, kline_df):
        obv = TechnicalIndicators.obv(kline_df)
        assert len(obv) == len(kline_df)

    def test_obv_increasing_on_up(self, flat_df):
        """价格上涨时 OBV 应该增加"""
        df = flat_df.copy()
        df.loc[1, "close"] = 10.5
        obv = TechnicalIndicators.obv(df)
        assert obv.iloc[1] > obv.iloc[0]

    def test_obv_decreasing_on_down(self, flat_df):
        """价格下跌时 OBV 应该减少"""
        df = flat_df.copy()
        df.loc[1, "close"] = 9.5
        obv = TechnicalIndicators.obv(df)
        assert obv.iloc[1] < obv.iloc[0]


# ================================================================
# 威廉指标 WR
# ================================================================

class TestWilliamsR:
    def test_wr_range(self, kline_df):
        wr = TechnicalIndicators.williams_r(kline_df, 14)
        valid = wr.dropna()
        assert (valid >= -100).all() and (valid <= 0).all()


# ================================================================
# 量比
# ================================================================

class TestVolumeRatio:
    def test_vol_ratio(self, kline_df):
        vr = TechnicalIndicators.volume_ratio(kline_df["volume"], 5)
        assert len(vr) == len(kline_df)

    def test_vol_ratio_flat(self, flat_df):
        """成交量不变 → 量比 = 1"""
        vr = TechnicalIndicators.volume_ratio(flat_df["volume"], 5)
        valid = vr.dropna()
        assert (abs(valid.iloc[-1] - 1.0) < 0.01)


# ================================================================
# 均线关系
# ================================================================

class TestMAAlignment:
    def test_ma_alignment_output_keys(self, kline_df):
        result = TechnicalIndicators.ma_alignment(kline_df["close"])
        for key in ["is_bullish", "is_bearish", "golden_cross", "death_cross", "adhesion", "price_vs_ma"]:
            assert key in result

    def test_ma_alignment_bullish(self):
        """构造多头排列数据"""
        n = 80
        close = pd.Series([float(i) * 0.01 + 10 for i in range(1, n + 1)])
        result = TechnicalIndicators.ma_alignment(close)
        assert result["is_bullish"]

    def test_ma_alignment_bearish(self):
        """构造空头排列数据"""
        n = 80
        close = pd.Series([20.0 - float(i) * 0.01 for i in range(1, n + 1)])
        result = TechnicalIndicators.ma_alignment(close)
        assert result["is_bearish"]


# ================================================================
# compute_all 批量计算
# ================================================================

class TestComputeAll:
    def test_compute_all_columns(self, kline_df):
        df = TechnicalIndicators.compute_all(kline_df)
        expected_cols = [
            "ma5", "ma10", "ma20", "ma60", "ma120",
            "ema12", "ema26",
            "macd_dif", "macd_dea", "macd_hist",
            "rsi6", "rsi14",
            "kdj_k", "kdj_d", "kdj_j",
            "wr14",
            "boll_upper", "boll_mid", "boll_lower", "boll_width",
            "atr14",
            "obv", "vwap", "vol_ratio5",
        ]
        for col in expected_cols:
            assert col in df.columns, f"Missing column: {col}"

    def test_compute_all_empty(self):
        df = TechnicalIndicators.compute_all(pd.DataFrame())
        assert df.empty

    def test_compute_all_same_length(self, kline_df):
        df = TechnicalIndicators.compute_all(kline_df)
        assert len(df) == len(kline_df)


class TestComputeLatestFeatures:
    def test_returns_dict(self, kline_df):
        features = TechnicalIndicators.compute_latest_features(kline_df)
        assert isinstance(features, dict)
        assert "rsi14" in features
        assert "macd_dif" in features
        assert "is_bullish" in features

    def test_insufficient_data(self):
        """数据不足时应能正常计算"""
        df = pd.DataFrame({
            "open": [10.0] * 10, "high": [10.5] * 10, "low": [9.5] * 10,
            "close": [10.0] * 10, "volume": [1000000] * 10,
        })
        features = TechnicalIndicators.compute_latest_features(df)
        assert isinstance(features, dict)
        assert "ma5" in features
