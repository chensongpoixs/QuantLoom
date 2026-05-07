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
