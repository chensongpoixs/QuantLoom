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
价格特征工程
从行情数据中提取技术面特征
"""

from typing import Optional

import pandas as pd


class PriceFeatures:
    """价格特征计算"""

    @staticmethod
    def volume_ratio(row: pd.Series, avg_volume: float = None) -> float:
        """
        量比 = 当前成交量 / 过去 5 日均量
        如未提供均量，使用 volume 字段本身作为占位
        """
        vol = row.get("volume", 0) or 0
        if avg_volume and avg_volume > 0:
            return float(vol) / avg_volume
        return 1.0

    @staticmethod
    def pct_change_normalized(pct_change: float) -> float:
        """标准化涨跌幅（保留两位小数）"""
        return round(float(pct_change or 0), 4)

    @staticmethod
    def near_52w_low(pct_change_ytd: Optional[float], current_pct_from_low: Optional[float] = None) -> bool:
        """
        判断是否接近 250 日低位
        简化实现：依赖外部传入的年迄今涨跌幅
        """
        if current_pct_from_low is not None:
            return current_pct_from_low <= 15.0
        if pct_change_ytd is not None:
            return pct_change_ytd <= -30.0  # 年跌幅超过 30% 视为低位区域
        return False

    @classmethod
    def compute_features(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        为行情 DataFrame 批量计算特征
        """
        if df.empty:
            return df

        df = df.copy()
        # 确保数值类型
        for col in ["pct_change", "volume", "turnover_amount", "turnover_rate"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        return df
