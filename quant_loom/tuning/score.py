"""
回测结果评分函数
支持多窗口精度、收益率、命中率计算
"""

from typing import Optional

import pandas as pd


def precision_at_n(results_df: pd.DataFrame, n_days: int = 3) -> float:
    """
    方向准确率: 异动日涨幅方向与后续 N 日方向一致的比例

    例如: alert 日涨幅为正，后续 N 日收益也为正 → 正确
    """
    col = f"outcome_{n_days}d"
    if col not in results_df.columns:
        return 0.0

    df = results_df.dropna(subset=[col, "pct_change_alert"])
    if df.empty:
        return 0.0

    same_direction = (df["pct_change_alert"] > 0) == (df[col] > 0)
    return float(same_direction.sum() / len(df))


def average_return(results_df: pd.DataFrame, n_days: int = 3) -> float:
    """后续 N 日平均收益率 (%)"""
    col = f"outcome_{n_days}d"
    if col not in results_df.columns:
        return 0.0

    values = results_df[col].dropna()
    if values.empty:
        return 0.0

    return float(values.mean())


def hit_rate(results_df: pd.DataFrame, threshold_pct: float = 2.0,
             n_days: int = 3) -> float:
    """
    命中率: 后续 N 日收益超过 threshold_pct 的比例
    """
    col = f"outcome_{n_days}d"
    if col not in results_df.columns:
        return 0.0

    values = results_df[col].dropna()
    if values.empty:
        return 0.0

    return float((values >= threshold_pct).sum() / len(values))


def combined_score(results_df: pd.DataFrame, n_days: int = 3) -> float:
    """
    综合评分: 0.6 * precision@N + 0.4 * avg_return@N
    范围 [0, 1] (precision) + unbounded (return)
    """
    prec = precision_at_n(results_df, n_days)
    avg_ret = average_return(results_df, n_days)
    return 0.6 * prec + 0.4 * max(avg_ret / 10.0, 0.0)  # 归一化 return 到 ~0-1


def alert_count(results_df: pd.DataFrame) -> int:
    """回测结果中的告警数量"""
    return len(results_df)
