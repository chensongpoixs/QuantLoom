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
数据清洗模块
负责停牌/涨跌停过滤、异常值检测、字段标准化
"""

from typing import Optional

import pandas as pd
from loguru import logger


class DataCleaner:
    """数据清洗器"""

    # 异常值阈值
    MAX_SINGLE_TURNOVER = 5e10      # 单日成交额上限 500 亿
    MAX_PCT_CHANGE = 20.0           # 涨跌幅绝对值上限（非科创板/创业板常规情况）

    @classmethod
    def clean_quotes(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        清洗行情快照数据
        - 过滤停牌、退市、新股未上市
        - 过滤涨跌停状态
        - 过滤异常成交额
        - 填充/去除空值
        """
        if df.empty:
            return df

        initial = len(df)
        dropped_logs = []

        # 0. 确保操作独立副本，避免 SettingWithCopyWarning
        df = df.copy()

        # 1. 过滤无价格的记录（停牌/未上市）
        if "latest" in df.columns:
            mask = df["latest"].notna() & (df["latest"] > 0)
            n = (~mask).sum()
            if n:
                dropped_logs.append(f"no valid price: {n}")
            df = df.loc[mask]

        # 2. 填充关键字段空值（必须在数值过滤之前）
        fill_map = {
            "pct_change": 0.0,
            "volume": 0,
            "turnover_amount": 0.0,
            "turnover_rate": 0.0,
        }
        for col, default in fill_map.items():
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(default)

        # 3. 过滤涨跌停（NaN 已填充为 0）
        if "pct_change" in df.columns:
            mask = (df["pct_change"] >= -cls.MAX_PCT_CHANGE) & (df["pct_change"] <= cls.MAX_PCT_CHANGE)
            n = (~mask).sum()
            if n:
                dropped_logs.append(f"limit-up/down or abnormal pct_change: {n}")
            df = df.loc[mask]

        # 4. 过滤极端成交额
        if "turnover_amount" in df.columns:
            mask = df["turnover_amount"] <= cls.MAX_SINGLE_TURNOVER
            n = (~mask).sum()
            if n:
                dropped_logs.append(f"abnormal turnover amount: {n}")
            df = df.loc[mask]

        final = len(df)
        if initial - final > 0:
            logger.info(f"Quote cleaning: {initial} -> {final} records (filtered {initial - final}: {', '.join(dropped_logs)})")

        return df

    @classmethod
    def clean_fund_flow(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        清洗资金流数据
        - 填充空值
        - 计算净流入占比
        """
        if df.empty:
            return df

        df = df.copy()

        # 资金流字段填充 0
        flow_cols = ["super_large_net_inflow", "large_net_inflow",
                      "medium_net_inflow", "small_net_inflow"]
        for col in flow_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        # 计算净流入占比（如果源数据未提供）
        if "inflow_ratio" not in df.columns:
            total_inflow = df[[c for c in flow_cols if c in df.columns]].sum(axis=1)
            if "turnover_amount" in df.columns and df["turnover_amount"].notna().any():
                df["inflow_ratio"] = (total_inflow / df["turnover_amount"].replace(0, pd.NA)) * 100
            df["inflow_ratio"] = df.get("inflow_ratio", pd.Series(0)).fillna(0)

        return df

    @classmethod
    def is_valid_code(cls, code: str) -> bool:
        """校验股票代码格式"""
        if not isinstance(code, str):
            return False
        return len(code) == 6 and code.isdigit()

    @classmethod
    def extract_exchange(cls, code: str) -> Optional[str]:
        """根据代码推断交易所"""
        if not cls.is_valid_code(code):
            return None
        if code.startswith(("60", "68")):
            return "sh"
        elif code.startswith(("00", "30")):
            return "sz"
        elif code.startswith(("8", "4")):
            return "bj"
        return None
