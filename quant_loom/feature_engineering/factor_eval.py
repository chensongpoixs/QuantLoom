"""
因子有效性评估 — IC/IR 计算 + 分层回测
评估因子预测方向性 (IC) 和分组收益区分度 (分层回测)
"""

import numpy as np
import pandas as pd
from loguru import logger


class FactorEvaluator:
    """因子评估工具 — IC 分析 + 分层回测"""

    @staticmethod
    def information_coefficient(factor: pd.Series, forward_returns: pd.Series) -> float:
        """
        IC (Information Coefficient) — Rank IC (Spearman)

        factor: (stocks,) 因子值
        forward_returns: (stocks,) 未来 N 日收益率
        """
        common = factor.index.intersection(forward_returns.index)
        if len(common) < 10:
            return 0.0

        f = factor.loc[common].dropna()
        r = forward_returns.loc[common].dropna()
        common2 = f.index.intersection(r.index)
        if len(common2) < 10:
            return 0.0

        return f.loc[common2].corr(r.loc[common2], method="spearman")

    @staticmethod
    def information_ratio(factor: pd.Series, forward_returns: dict) -> dict:
        """
        IR (Information Ratio) — IC 均值 / IC 标准差

        forward_returns: {period_label: forward_returns_series}
        返回: {period_label: {"ic_mean": ..., "ir": ..., "ic_std": ...}}
        """
        result = {}
        for period, fwd_ret in forward_returns.items():
            ic = FactorEvaluator.information_coefficient(factor, fwd_ret)
            result[period] = {
                "ic": round(ic, 4),
            }
        return result

    @staticmethod
    def layered_backtest(factor: pd.Series, forward_returns: pd.Series, n_groups: int = 5) -> dict:
        """
        分层回测 — 按因子值分 N 组，计算各组平均未来收益

        Returns
        -------
        dict with:
            groups: {group_label: avg_return}
            top_bottom_spread: 顶组 - 底组收益差
            monotonicity: 收益单调性 (正相关=1, 负相关=-1, 无=0)
        """
        common = factor.index.intersection(forward_returns.index)
        if len(common) < n_groups * 3:
            return {"groups": {}, "top_bottom_spread": 0.0, "monotonicity": 0}

        f = factor.loc[common].dropna()
        r = forward_returns.loc[common].dropna()
        common2 = f.index.intersection(r.index)
        if len(common2) < n_groups * 3:
            return {"groups": {}, "top_bottom_spread": 0.0, "monotonicity": 0}

        f = f.loc[common2]
        r = r.loc[common2]

        # 按因子值排秩分 5 组
        try:
            labels = [f"Q{i+1}" for i in range(n_groups)]
            group = pd.qcut(f, n_groups, labels=labels, duplicates="drop")
            group_returns = r.groupby(group).mean()
        except (ValueError, TypeError):
            return {"groups": {}, "top_bottom_spread": 0.0, "monotonicity": 0}

        groups = group_returns.to_dict()
        q_labels = group_returns.index.tolist()

        # Top-Bottom spread
        if len(q_labels) >= 2:
            top_lbl = q_labels[-1]  # Q5 = highest factor
            bot_lbl = q_labels[0]   # Q1 = lowest factor
            spread = float(group_returns.get(top_lbl, 0) - group_returns.get(bot_lbl, 0))
        else:
            spread = 0.0

        # Monotonicity: check if returns increase monotonically with factor quantile
        rets = group_returns.values
        diffs = np.diff(rets)
        if len(diffs) > 0 and all(d > 0 for d in diffs):
            monotonicity = 1
        elif len(diffs) > 0 and all(d < 0 for d in diffs):
            monotonicity = -1
        else:
            monotonicity = 0

        return {
            "groups": groups,
            "top_bottom_spread": round(spread, 4),
            "monotonicity": monotonicity,
        }

    @staticmethod
    def evaluate_all(factor_df: pd.DataFrame, forward_returns: pd.Series) -> pd.DataFrame:
        """
        批量评估所有因子

        Returns
        -------
        DataFrame with columns: factor, ic, abs_ic, top_bottom_spread, monotonicity
        """
        results = []
        for col in factor_df.columns:
            factor = factor_df[col].dropna()
            if factor.empty:
                continue

            ic = FactorEvaluator.information_coefficient(factor, forward_returns)
            layered = FactorEvaluator.layered_backtest(factor, forward_returns)

            results.append({
                "factor": col,
                "ic": round(ic, 4),
                "abs_ic": round(abs(ic), 4),
                "top_bottom_spread": layered["top_bottom_spread"],
                "monotonicity": layered["monotonicity"],
                "n_stocks": len(factor),
            })

        df = pd.DataFrame(results)
        if not df.empty:
            df = df.sort_values("abs_ic", ascending=False)
        return df

    @staticmethod
    def optimal_weights(factor_df: pd.DataFrame, forward_returns: pd.Series,
                        min_weight: float = 0.02) -> dict:
        """
        基于 IC 绝对值计算最优因子权重

        w_i = abs(IC_i) / sum(abs(IC_j)), 且 w_i >= min_weight
        """
        eval_df = FactorEvaluator.evaluate_all(factor_df, forward_returns)
        if eval_df.empty:
            return {}

        eval_df = eval_df[eval_df["abs_ic"] > 0.001]
        if eval_df.empty:
            return {}

        total_abs = eval_df["abs_ic"].sum()
        weights = {}
        for _, row in eval_df.iterrows():
            w = row["abs_ic"] / total_abs if total_abs > 0 else 0
            weights[row["factor"]] = max(round(w, 4), min_weight)

        # Re-normalize
        w_sum = sum(weights.values())
        if w_sum > 0:
            weights = {k: round(v / w_sum, 4) for k, v in weights.items()}

        return weights
