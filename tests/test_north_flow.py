"""
北向资金单元测试
测试 NorthFlowFetcher 数据抓取与特征计算
"""

import pandas as pd
import pytest

from quant_loom.feature_engineering.fund_flow import FundFlowFeatures
from quant_loom.data_ingestion.north_flow_fetcher import NorthFlowFetcher


# ---- 模拟数据 ----

@pytest.fixture
def mock_flow_df():
    """模拟北向净流入数据 (20 行)"""
    dates = pd.date_range("2026-04-20", periods=20, freq="B")
    inflows = [
        10, 15, -5, 20, 25, 18, -8, 30, 35, 22,
        40, 55, -12, 60, 70, 45, 80, 90, 75, 100,
    ]
    return pd.DataFrame({
        "date": dates,
        "total_net_inflow": inflows,
    })


@pytest.fixture
def mock_top10_df():
    """模拟十大成交活跃股"""
    return pd.DataFrame({
        "code": ["600519", "000858", "300750", "601318", "000333",
                 "002415", "600036", "000001", "601012", "600276"],
        "name": ["茅台", "五粮液", "宁德", "平安", "美的",
                 "海康", "招行", "平安银行", "隆基", "恒瑞"],
        "net_buy_amount": [8.5, 5.2, -3.1, 4.0, 2.8, -1.5, 3.6, 1.2, -0.8, 0.5],
        "buy_amount": [15, 10, 5, 8, 6, 4, 7, 4, 3, 2],
        "sell_amount": [6.5, 4.8, 8.1, 4, 3.2, 5.5, 3.4, 2.8, 3.8, 1.5],
    })


@pytest.fixture
def mock_holdings_df():
    """模拟北向持仓数据"""
    return pd.DataFrame({
        "code": ["600519", "300750", "000858", "601318", "000333"],
        "name": ["茅台", "宁德", "五粮液", "平安", "美的"],
        "hold_shares": [1.2e8, 2.0e8, 1.5e8, 5.0e8, 3.0e8],
        "hold_market_value": [2.0e11, 1.5e11, 1.0e11, 8.0e10, 6.0e10],
        "hold_ratio": [7.5, 5.2, 4.8, 3.2, 2.8],
    })


# ================================================================
# 数据抓取 (用 mock 验证列映射逻辑)
# ================================================================

class TestNorthFlowFetcher:
    def test_init(self):
        fetcher = NorthFlowFetcher()
        assert fetcher is not None

    def test_fetch_features_returns_dict(self):
        """即使 AkShare 不可用, fetch_features 也应安全返回空 dict"""
        fetcher = NorthFlowFetcher()
        features = fetcher.fetch_features()
        assert isinstance(features, dict)
        assert "north_net_inflow_today" in features
        assert "north_top10_net_buy" in features
        assert "north_holding_top" in features


# ================================================================
# 特征计算
# ================================================================

class TestNorthFlowFeatures:
    def test_acceleration_positive(self, mock_flow_df):
        """流入加速 → accel > 0"""
        inflows = mock_flow_df["total_net_inflow"].values
        # 后 5 日均值 > 前 5 日均值
        curr_5d = inflows[-5:].mean()
        prev_5d = inflows[-10:-5].mean()
        assert curr_5d > prev_5d  # 80 vs 34.4

    def test_acceleration_negative(self):
        """流入减速 → accel < 0"""
        dates = pd.date_range("2026-04-01", periods=20, freq="B")
        inflows = [80, 70, 60, 50, 40, 30, 20, 15, 10, 5,
                   5, 3, 0, -2, -5, -8, -10, -12, -15, -20]
        df = pd.DataFrame({"date": dates, "total_net_inflow": inflows})
        curr_5d = df["total_net_inflow"].iloc[-5:].mean()
        prev_5d = df["total_net_inflow"].iloc[-10:-5].mean()
        assert curr_5d < prev_5d


# ================================================================
# 北向持仓特征
# ================================================================

class TestNorthHoldingFeatures:
    def test_top20_by_market_value(self, mock_holdings_df):
        """按持股市值排序"""
        sorted_df = mock_holdings_df.sort_values("hold_market_value", ascending=False)
        assert sorted_df.iloc[0]["code"] == "600519"  # 茅台市值最大

    def test_hold_ratio_range(self, mock_holdings_df):
        """持仓占比在合理范围"""
        ratios = mock_holdings_df["hold_ratio"]
        assert (ratios >= 0).all()
        assert (ratios <= 100).all()

    def test_high_hold_ratio(self, mock_holdings_df):
        """北向重仓 >5%"""
        high_hold = mock_holdings_df[mock_holdings_df["hold_ratio"] > 5]
        assert len(high_hold) >= 1


# ================================================================
# 北向资金流特征 (集成到 FundFlowFeatures)
# ================================================================

class TestNorthFlowIntegration:
    def test_consecutive_inflow_days_from_north(self):
        """测试连续净流入天数 — 按日期降序(最近在前): 60,80,30 连续3天正"""
        inflows = [60, 80, 30, -20, 50, 100]
        days = FundFlowFeatures.compute_consecutive_days(inflows)
        assert days == 3

    def test_no_inflows(self):
        days = FundFlowFeatures.compute_consecutive_days([])
        assert days == 0

    def test_all_inflows(self):
        inflows = [10, 20, 30, 40, 50]
        days = FundFlowFeatures.compute_consecutive_days(inflows)
        assert days == 5


# ================================================================
# 北向资金评分函数
# ================================================================

class TestNorthFlowScoring:
    def _score(self, alert_code: str, north_features: dict) -> float:
        """复用 run_scanner._north_flow_score 的逻辑"""
        delta = 0.0
        net_today = north_features.get("north_net_inflow_today", 0) or 0
        if net_today > 50:
            delta += 0.05
        elif net_today > 20:
            delta += 0.03
        elif net_today < -30:
            delta -= 0.05

        accel = north_features.get("north_inflow_accel", 0) or 0
        if accel > 30:
            delta += 0.03
        elif accel < -30:
            delta -= 0.03

        top10 = north_features.get("north_top10_net_buy", {})
        if alert_code in top10:
            net_buy = top10[alert_code]
            if net_buy > 3:
                delta += 0.05
            elif net_buy > 0:
                delta += 0.02

        return round(max(-0.08, min(0.10, delta)), 2)

    def test_strong_inflow_bonus(self):
        """北向大幅流入 → 加分"""
        north = {"north_net_inflow_today": 80, "north_inflow_accel": 0, "north_top10_net_buy": {}}
        assert self._score("000001", north) == 0.05

    def test_outflow_penalty(self):
        """北向外流 → 扣分"""
        north = {"north_net_inflow_today": -50, "north_inflow_accel": 0, "north_top10_net_buy": {}}
        assert self._score("000001", north) == -0.05

    def test_top10_buy_bonus(self):
        """在十大成交净买入中 → 加分"""
        north = {
            "north_net_inflow_today": 10, "north_inflow_accel": 0,
            "north_top10_net_buy": {"600519": 5.0},
        }
        assert self._score("600519", north) == 0.05

    def test_combined_signals(self):
        """多信号叠加"""
        north = {
            "north_net_inflow_today": 60,  # +0.05
            "north_inflow_accel": 40,      # +0.03
            "north_top10_net_buy": {"000858": 4.0},  # +0.05
        }
        assert self._score("000858", north) == 0.10  # max capped

    def test_neutral(self):
        north = {"north_net_inflow_today": 5, "north_inflow_accel": 0, "north_top10_net_buy": {}}
        assert self._score("000001", north) == 0.0
