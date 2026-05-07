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
