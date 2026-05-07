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

"""数据清洗单元测试"""

import pandas as pd
import pytest

from quant_loom.data_ingestion.cleaner import DataCleaner


class TestCleanQuotes:
    """行情数据清洗"""

    def test_filter_zero_price(self):
        df = pd.DataFrame([
            {"code": "000001", "name": "平安银行", "latest": 12.5, "pct_change": 2.0,
             "turnover_amount": 1e8, "volume": 1e7, "turnover_rate": 1.5},
            {"code": "000002", "name": "停牌股", "latest": 0, "pct_change": 0,
             "turnover_amount": 0, "volume": 0, "turnover_rate": 0},
        ])
        result = DataCleaner.clean_quotes(df)
        assert len(result) == 1
        assert result.iloc[0]["code"] == "000001"

    def test_filter_nan_price(self):
        df = pd.DataFrame([
            {"code": "000001", "name": "A", "latest": 10.0, "pct_change": 1.0,
             "turnover_amount": 1e8, "volume": 1e7, "turnover_rate": 1.0},
            {"code": "000002", "name": "B", "latest": None, "pct_change": 0,
             "turnover_amount": 0, "volume": 0, "turnover_rate": 0},
        ])
        result = DataCleaner.clean_quotes(df)
        assert len(result) == 1

    def test_fill_missing_values(self):
        df = pd.DataFrame([
            {"code": "000001", "name": "A", "latest": 10.0, "pct_change": None,
             "turnover_amount": None, "volume": None, "turnover_rate": None},
        ])
        result = DataCleaner.clean_quotes(df)
        assert len(result) == 1
        assert result.iloc[0]["pct_change"] == 0.0
        assert result.iloc[0]["turnover_amount"] == 0.0

    def test_filter_extreme_turnover(self):
        df = pd.DataFrame([
            {"code": "000001", "name": "A", "latest": 10.0, "pct_change": 1.0,
             "turnover_amount": 1e11, "volume": 1e7, "turnover_rate": 1.0},  # > 500亿
        ])
        result = DataCleaner.clean_quotes(df)
        assert len(result) == 0


class TestCleanFundFlow:
    """资金流数据清洗"""

    def test_fill_na_flow_fields(self):
        df = pd.DataFrame([
            {"code": "000001", "name": "A", "super_large_net_inflow": None,
             "large_net_inflow": None, "medium_net_inflow": None,
             "small_net_inflow": None, "turnover_amount": 1e8},
        ])
        result = DataCleaner.clean_fund_flow(df)
        assert result.iloc[0]["super_large_net_inflow"] == 0
        assert result.iloc[0]["large_net_inflow"] == 0

    def test_compute_inflow_ratio(self):
        df = pd.DataFrame([
            {"code": "000001", "name": "A",
             "super_large_net_inflow": 1000,
             "large_net_inflow": 2000,
             "medium_net_inflow": -500,
             "small_net_inflow": -1000,
             "turnover_amount": 100000},
        ])
        result = DataCleaner.clean_fund_flow(df)
        assert "inflow_ratio" in result.columns


class TestCodeValidation:
    """股票代码校验"""

    def test_valid_code(self):
        assert DataCleaner.is_valid_code("000001") is True
        assert DataCleaner.is_valid_code("600519") is True

    def test_invalid_code(self):
        assert DataCleaner.is_valid_code("") is False
        assert DataCleaner.is_valid_code("abc") is False
        assert DataCleaner.is_valid_code("12345") is False

    def test_extract_exchange(self):
        assert DataCleaner.extract_exchange("600519") == "sh"
        assert DataCleaner.extract_exchange("688001") == "sh"
        assert DataCleaner.extract_exchange("000001") == "sz"
        assert DataCleaner.extract_exchange("300750") == "sz"
        assert DataCleaner.extract_exchange("830799") == "bj"
