"""
市场宽度单元测试
测试 MarketBreadth 的市场情绪快照计算正确性
"""

import numpy as np
import pandas as pd
import pytest

from quant_loom.feature_engineering.market_breadth import MarketBreadth


# ---- 测试数据 ----

@pytest.fixture
def quotes_df():
    """构造包含 200 只股票的全市场行情数据"""
    np.random.seed(42)
    n = 200
    codes = []
    for i in range(n):
        # 混合主板/创业板/科创板/北交所
        if i < 120:
            codes.append(f"00{i:04d}")  # 主板
        elif i < 160:
            codes.append(f"30{i:04d}")  # 创业板
        elif i < 180:
            codes.append(f"68{i:04d}")  # 科创板
        else:
            codes.append(f"83{i:04d}")  # 北交所

    pct_change = np.random.randn(n) * 3  # 大部分在 ±3% 内
    # 人工设置涨停/跌停
    pct_change[0] = 10.0   # 主板涨停
    pct_change[1] = -10.0  # 主板跌停
    pct_change[2] = 20.0   # 创业板涨停 (阈值 19.5)
    pct_change[3] = 5.0    # 普通上涨
    pct_change[4] = -3.0   # 普通下跌
    pct_change[5:10] = 0.0 # 平盘

    turnover = np.random.randint(1000000, 100000000, n)

    return pd.DataFrame({
        "code": codes,
        "pct_change": pct_change,
        "turnover_amount": turnover,
        "high": np.random.randn(n) * 0.5 + 10,
        "low": np.random.randn(n) * 0.5 + 9.5,
        "prev_close": [10.0] * n,
    })


@pytest.fixture
def empty_df():
    return pd.DataFrame()


@pytest.fixture
def all_up_df():
    """全部涨停 (主板代码，pct_change=10%)"""
    return pd.DataFrame({
        "code": [f"00{i:04d}" for i in range(10)],
        "pct_change": [10.0, 9.5, 10.0, 10.0, 10.0, 9.8, 10.0, 9.9, 10.0, 10.0],
        "turnover_amount": [1e8] * 10,
    })


# ================================================================
# 基本计算
# ================================================================

class TestMarketBreadth:
    def test_compute_returns_all_keys(self, quotes_df):
        result = MarketBreadth.compute(quotes_df)
        expected_keys = [
            "limit_up_count", "limit_down_count", "up_count", "down_count",
            "flat_count", "up_down_ratio", "adl", "broken_board_count",
            "avg_pct_change", "total_turnover", "limit_up_pct", "limit_down_pct",
            "sentiment",
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_empty_df(self, empty_df):
        result = MarketBreadth.compute(empty_df)
        assert result["limit_up_count"] == 0
        assert result["up_count"] == 0
        assert result["sentiment"] == "neutral"

    def test_limit_up_detection_main_board(self, quotes_df):
        """主板 10% 涨停阈值: pct_change >= 9.5"""
        result = MarketBreadth.compute(quotes_df)
        # quotes_df[0] = 10.0% → 主板涨停
        assert result["limit_up_count"] >= 1

    def test_limit_down_detection(self, quotes_df):
        """跌停检测"""
        result = MarketBreadth.compute(quotes_df)
        # quotes_df[1] = -10.0% → 跌停
        assert result["limit_down_count"] >= 1

    def test_chi_next_limit_up(self, quotes_df):
        """创业板 20% 涨停: pct_change >= 19.5"""
        result = MarketBreadth.compute(quotes_df)
        # quotes_df[2] = 20.0%, code 300000 → 涨停
        assert result["limit_up_count"] >= 1

    def test_up_down_counts(self, quotes_df):
        result = MarketBreadth.compute(quotes_df)
        assert result["up_count"] + result["down_count"] + result["flat_count"] == len(quotes_df)

    def test_up_down_ratio(self, quotes_df):
        result = MarketBreadth.compute(quotes_df)
        # up/down ratio should be positive
        assert result["up_down_ratio"] > 0

    def test_adl(self, quotes_df):
        """ADL = up_count - down_count"""
        result = MarketBreadth.compute(quotes_df)
        assert result["adl"] == result["up_count"] - result["down_count"]

    def test_total_turnover(self, quotes_df):
        result = MarketBreadth.compute(quotes_df)
        expected = float(pd.to_numeric(quotes_df["turnover_amount"]).sum())
        assert abs(result["total_turnover"] - expected) < 0.01


# ================================================================
# 情绪判断
# ================================================================

class TestSentiment:
    def test_bullish(self):
        """涨停 > 80 且跌停 < 10 → bullish"""
        codes = [f"00{i:04d}" for i in range(100)]
        pct = [10.0] * 85 + [1.0] * 15  # 85 涨停, 0 跌停
        df = pd.DataFrame({
            "code": codes, "pct_change": pct, "turnover_amount": [1e8] * 100,
        })
        result = MarketBreadth.compute(df)
        assert result["sentiment"] == "bullish"

    def test_bearish(self):
        """跌停 > 50 → bearish"""
        codes = [f"00{i:04d}" for i in range(100)]
        pct = [-10.0] * 55 + [-1.0] * 45  # 55 跌停
        df = pd.DataFrame({
            "code": codes, "pct_change": pct, "turnover_amount": [1e8] * 100,
        })
        result = MarketBreadth.compute(df)
        assert result["sentiment"] == "bearish"

    def test_neutral(self):
        """正常市场 → neutral"""
        codes = [f"00{i:04d}" for i in range(100)]
        pct = np.random.randn(100) * 2
        df = pd.DataFrame({
            "code": codes, "pct_change": pct, "turnover_amount": [1e8] * 100,
        })
        result = MarketBreadth.compute(df)
        assert result["sentiment"] == "neutral"


# ================================================================
# 阈值匹配
# ================================================================

class TestLimitThreshold:
    def test_main_board(self):
        assert MarketBreadth._limit_threshold("000001") == 9.5
        assert MarketBreadth._limit_threshold("600519") == 9.5

    def test_chi_next(self):
        assert MarketBreadth._limit_threshold("300750") == 19.5

    def test_star_board(self):
        assert MarketBreadth._limit_threshold("688981") == 19.5

    def test_beijing(self):
        assert MarketBreadth._limit_threshold("830001") == 29.5


# ================================================================
# 情绪偏差
# ================================================================

class TestSentimentBias:
    def test_bullish_bias(self):
        breadth = {"sentiment": "bullish", "up_down_ratio": 2.0, "limit_down_count": 5}
        result = MarketBreadth.apply_sentiment_bias(0.70, breadth)
        assert result > 0.70

    def test_bearish_bias(self):
        breadth = {"sentiment": "bearish", "up_down_ratio": 0.5, "limit_down_count": 60}
        result = MarketBreadth.apply_sentiment_bias(0.70, breadth)
        assert result > 0.70  # bearish = +0.05

    def test_extreme_panic_penalty(self):
        """跌停 > 100 时扣分"""
        breadth = {"sentiment": "bearish", "up_down_ratio": 0.5, "limit_down_count": 150}
        result = MarketBreadth.apply_sentiment_bias(0.70, breadth)
        # +0.05 (bearish) -0.05 (extreme panic) = 0.00 delta
        assert result == 0.70

    def test_neutral_no_change(self):
        breadth = {"sentiment": "neutral", "up_down_ratio": 1.5, "limit_down_count": 10}
        result = MarketBreadth.apply_sentiment_bias(0.70, breadth)
        assert result == 0.70

    def test_clamped_range(self):
        """不应超出 [0, 1]"""
        breadth = {"sentiment": "bullish", "up_down_ratio": 10.0, "limit_down_count": 0}
        result = MarketBreadth.apply_sentiment_bias(0.99, breadth)
        assert 0 <= result <= 1.0
        result2 = MarketBreadth.apply_sentiment_bias(0.01, breadth)
        assert 0 <= result2 <= 1.0
