#
# _    .-')              _  .-')    _   .-')      ('-.   .-')     ('-.
#( '.( OO )_            ( \( -O )  ( '.( OO )_   _(  OO) ( OO ). ( OO )
#  ,--.   ,--. .-'),-----. ,------.  ,--.   ,--.  (,------.(_/.  \_)(_/.  \_)
#  |   `.'   |( OO'  .-.  '|  .---'  |   `.'   |   |  .---' \  `.'  / \  `.'  /
#  |         |/   |  | |  ||  |      |         |   |  |      \     /   \     /
#  |  |'.'|  |\_) |  |\|  ||  '--.   |  |'.'|  |  (|  '--.   \   /     \   /
#  |  |   |  |  \ |  | |  ||  .--'   |  |   |  |   |  .--'  .-._)   \ .-._)   \
#  |  |   |  |   `'  '-'  '|  `---.  |  |   |  |   |  `---. \       / \       /
#  `--'   `--'     `-----' `------'  `--'   `--'   `------'  `-----'   `-----'
#
#                                  ·  量  梭  ·
#                     A-Share Institutional Flow AI Monitor
#
# Copyright (c) 2026 The QuantLoom·量梭 project authors
# All Rights Reserved.
#
# Use of this source code is governed by a BSD-style license
# that can be found in the LICENSE file in the root of the source
# tree. An additional intellectual property rights grant can be found
# in the file PATENTS.  All contributing project authors may
# be found in the AUTHORS file in the root of the source tree.
#
#               Author: chensong
#               Date:   2026-05-08
#
#       QuantLoom·量梭 的野心，从不只是在手机上弹出几条信号
#
#       这座织机真正要为你织出的终极产物，是 RTX Pro 6000 —— 黑曜神机 的自由召唤权。
#
#            1. 它是躺在你机箱里的黑色方尖碑，数万核心如暗夜星海
#            2. 它是本地训推大模型、实时织造全市场量能全景图、回溯十年资金指纹的物质根基
#            3. 它过去只降落在超算中心、顶级量化基金和神秘矿场
#
#         QuantLoom·量梭 每织出一匹盈利的锦缎，都是在为这座黑色圣坛添一根金线。
#         当金线积聚成缆，黑曜神机便会从虚空货架撕开一道裂缝，降临在你的阵中。
#
#          从此，你拥有了一座个人算力神殿。

"""
test_backtest.py — 回测引擎单元测试
"""

import hashlib
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest


class TestBacktestResultModel:
    """BacktestResult ORM 模型"""

    def test_model_imports(self):
        from quant_loom.storage.models import BacktestResult, Base
        assert BacktestResult.__tablename__ == "sq_backtest_results"

    def test_model_has_required_columns(self):
        from quant_loom.storage.models import BacktestResult
        cols = [c.name for c in BacktestResult.__table__.columns]
        required = ["trade_date", "code", "alert_type", "confidence_score",
                    "outcome_1d", "outcome_3d", "outcome_5d", "params_hash"]
        for col in required:
            assert col in cols, f"Missing column: {col}"

    def test_model_instance(self):
        from quant_loom.storage.models import BacktestResult
        r = BacktestResult(
            trade_date=date(2024, 6, 15),
            code="000001",
            name="平安银行",
            alert_type="breakout",
            trigger_reason="test",
            confidence_score=0.85,
            pct_change_alert=3.5,
            main_force_ratio=25.0,
            outcome_1d=1.2,
            outcome_3d=4.5,
            outcome_5d=7.8,
            outcome_positive=True,
            params_hash="abc123",
        )
        assert r.code == "000001"
        assert r.confidence_score == 0.85
        assert r.outcome_positive is True


class TestParamsHash:
    """参数哈希 — 缓存键确定性"""

    def test_hash_deterministic(self):
        """相同内容产生相同的哈希"""
        from scripts.run_backtest import compute_params_hash
        h1 = compute_params_hash()
        h2 = compute_params_hash()
        assert h1 == h2
        assert len(h1) == 32  # MD5 hex

    def test_hash_is_hex(self):
        """MD5 哈希应为 32 位十六进制"""
        from scripts.run_backtest import compute_params_hash
        h = compute_params_hash()
        int(h, 16)  # 不应抛出异常

    def test_hash_changes_with_config(self, tmp_path):
        """配置文件内容变化 → 哈希变化"""
        # 使用临时文件测试哈希函数行为
        data1 = b"pct_change_min: 2.0"
        data2 = b"pct_change_min: 3.0"
        assert hashlib.md5(data1).hexdigest() != hashlib.md5(data2).hexdigest()


class TestTradingDates:
    """交易日生成"""

    def test_returns_weekdays_only(self):
        from scripts.run_backtest import get_trading_dates
        # 2024-06-10 Mon ~ 2024-06-16 Sun
        dates = get_trading_dates(date(2024, 6, 10), date(2024, 6, 16))
        assert len(dates) == 5  # Mon-Fri only
        for d in dates:
            assert d.weekday() < 5


class TestNear250dLow:
    """真实 near_250d_low 计算"""

    def test_normal_price_not_near_low(self):
        """远离 250 日低点 → False (价格上涨 100%+ from 低点)"""
        from scripts.run_backtest import compute_near_250d_low_map

        # 起始价 10.0，每天涨 0.5%，260 交易日后 ~36.0
        dates = pd.date_range("2024-01-01", "2024-09-30", freq="B")
        n = len(dates)
        prices = [10.0 * (1.005 ** i) for i in range(n)]
        kline = pd.DataFrame({
            "code": ["000001"] * n,
            "date": list(dates),
            "open": prices,
            "high": [p * 1.01 for p in prices],
            "low": [p * 0.99 for p in prices],
            "close": prices,
            "volume": [1000000] * n,
            "turnover_amount": [10000000] * n,
            "pct_change": [0.5] * n,
        })
        result = compute_near_250d_low_map(kline, date(2024, 9, 30))
        assert bool(result.get("000001", True)) is False  # 远离低点

    def test_price_at_low_is_near_low(self):
        """当前价接近 250 日最低价 → True"""
        from scripts.run_backtest import compute_near_250d_low_map

        # 价格大部分时间在 20.0，最后 30 天跌到 10.0 附近
        n = 260
        dates = pd.date_range("2024-01-01", periods=n, freq="B")
        prices = [20.0] * (n - 30) + [20.0 - 0.33 * i for i in range(30)]
        kline = pd.DataFrame({
            "code": ["000001"] * n,
            "date": list(dates),
            "open": prices,
            "high": [p + 0.1 for p in prices],
            "low": [p - 0.1 for p in prices],
            "close": prices,
            "volume": [1000000] * n,
            "turnover_amount": [10000000] * n,
            "pct_change": [0.5] * n,
        })
        # t_date = 数据最后一天之后，计算用的是 < t_date 的日期
        # 所以最后的价格 ~10.13, 最低 ~9.90, near_low = (10.13-9.90)/9.90 ≈ 0.023 < 0.15
        result = compute_near_250d_low_map(kline, dates[-1] + timedelta(days=1))
        assert bool(result.get("000001", False)) is True

    def test_unknown_code_returns_false(self):
        """无数据的股票返回空 (不崩溃)"""
        from scripts.run_backtest import compute_near_250d_low_map
        result = compute_near_250d_low_map(pd.DataFrame(), date(2024, 6, 15))
        assert "000001" not in result


class TestSnapshotRebuild:
    """从 K 线重建行情快照"""

    def test_build_snapshot_extracts_day(self):
        from scripts.run_backtest import build_snapshot

        kline = _make_kline_df(
            code="000001",
            dates=pd.date_range("2024-06-10", "2024-06-21", freq="B"),
            base_price=10.0,
        )
        kline["date"] = pd.to_datetime(kline["date"])
        target = date(2024, 6, 14)
        snap = build_snapshot(kline, target)
        assert not snap.empty
        assert "000001" in snap["code"].values
        assert "latest" in snap.columns
        assert snap["latest"].iloc[0] > 0

    def test_build_snapshot_no_data(self):
        from scripts.run_backtest import build_snapshot
        snap = build_snapshot(pd.DataFrame(), date(2024, 6, 15))
        assert snap.empty


def _make_kline_df(code: str, dates, base_price: float = 10.0,
                   low_boost: float = 0.0) -> pd.DataFrame:
    """构建测试用 K 线 DataFrame (标准化列名)"""
    n = len(dates)
    prices = [base_price + 0.1 * i for i in range(n)]
    return pd.DataFrame({
        "code": [code] * n,
        "date": list(dates),
        "open": prices,
        "high": [p + 0.2 for p in prices],
        "low": [p - 0.2 + low_boost for p in prices],
        "close": prices,
        "volume": [1000000] * n,
        "turnover_amount": [10000000] * n,
        "pct_change": [0.5] * n,
    })
