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

"""资金流特征工程测试"""
import pandas as pd
import pytest
from quant_loom.feature_engineering.fund_flow import FundFlowFeatures


class TestComputeConsecutiveDays:
    def test_all_positive(self):
        result = FundFlowFeatures.compute_consecutive_days([100, 200, 50, 300])
        assert result == 4

    def test_mixed(self):
        result = FundFlowFeatures.compute_consecutive_days([100, 200, -50, 300])
        assert result == 2

    def test_first_negative(self):
        result = FundFlowFeatures.compute_consecutive_days([-100, 200, 50])
        assert result == 0

    def test_empty(self):
        result = FundFlowFeatures.compute_consecutive_days([])
        assert result == 0

    def test_with_none_values(self):
        result = FundFlowFeatures.compute_consecutive_days([100, None, 200])
        assert result == 1  # None 中断

    def test_all_zeros(self):
        result = FundFlowFeatures.compute_consecutive_days([0, 0, 0])
        assert result == 0


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
