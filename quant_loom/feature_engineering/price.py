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
