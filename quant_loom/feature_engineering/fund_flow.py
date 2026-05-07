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
资金流特征工程
从原始资金流数据中提取可用于规则判断的特征
"""

import pandas as pd


class FundFlowFeatures:
    """资金流特征计算"""

    @staticmethod
    def super_large_inflow_ratio(row: pd.Series) -> float:
        """
        超大单净流入占比 (%)
        = 超大单净流入 / 成交额 * 100
        """
        turnover = row.get("turnover_amount", 0) or 0
        inflow = row.get("super_large_net_inflow", 0) or 0
        if turnover > 0:
            return float(inflow) / float(turnover) * 100
        return 0.0

    @staticmethod
    def large_inflow_ratio(row: pd.Series) -> float:
        """大单净流入占比 (%)"""
        turnover = row.get("turnover_amount", 0) or 0
        inflow = row.get("large_net_inflow", 0) or 0
        if turnover > 0:
            return float(inflow) / float(turnover) * 100
        return 0.0

    @staticmethod
    def main_force_inflow_ratio(row: pd.Series) -> float:
        """
        主力净流入占比 (%)
        = (超大单 + 大单) 净流入 / 成交额 * 100
        """
        turnover = row.get("turnover_amount", 0) or 0
        super_large = row.get("super_large_net_inflow", 0) or 0
        large = row.get("large_net_inflow", 0) or 0
        if turnover > 0:
            return (float(super_large) + float(large)) / float(turnover) * 100
        return 0.0

    @staticmethod
    def net_inflow(row: pd.Series) -> float:
        """总净流入 = 超大单 + 大单 + 中单 + 小单"""
        cols = ["super_large_net_inflow", "large_net_inflow",
                "medium_net_inflow", "small_net_inflow"]
        return sum(float(row.get(c, 0) or 0) for c in cols)

    @classmethod
    def compute_features(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        为资金流 DataFrame 批量计算特征列
        新增列: super_large_ratio, large_ratio, main_force_ratio, net_inflow
        """
        if df.empty:
            return df

        df = df.copy()
        df["super_large_ratio"] = df.apply(cls.super_large_inflow_ratio, axis=1)
        df["large_ratio"] = df.apply(cls.large_inflow_ratio, axis=1)
        df["main_force_ratio"] = df.apply(cls.main_force_inflow_ratio, axis=1)
        df["net_inflow"] = df.apply(cls.net_inflow, axis=1)
        return df

    @staticmethod
    def compute_consecutive_days(net_inflows: list[float]) -> int:
        """
        从最近交易日起计算连续净流入天数
        net_inflows: 按日期降序排列的净流入列表 (最近的在前面)
        """
        days = 0
        for inflow in net_inflows:
            if inflow and inflow > 0:
                days += 1
            else:
                break
        return days
