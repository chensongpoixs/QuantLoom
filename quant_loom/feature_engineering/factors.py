"""
Alpha 因子库 — 估值/成长/质量/动量/波动五大类因子
计算截面因子值，支持等权/IC加权合成
"""

import numpy as np
import pandas as pd
from loguru import logger


class AlphaFactors:
    """Alpha 因子计算器 — 静态方法，接收 DataFrame 返回因子 Series"""

    # ================================================================
    # 估值因子 (越低越好)
    # ================================================================

    @staticmethod
    def ep_factor(metrics_map: dict) -> pd.Series:
        """E/P 因子 — 1/PE，值越高越被低估"""
        data = {}
        for code, m in metrics_map.items():
            pe = m.get("pe")
            if pe and pe > 0:
                data[code] = 1.0 / pe * 100  # 百分比化
        return pd.Series(data, name="ep")

    @staticmethod
    def bp_factor(metrics_map: dict) -> pd.Series:
        """B/P 因子 — 1/PB，值越高越被低估"""
        data = {}
        for code, m in metrics_map.items():
            pb = m.get("pb")
            if pb and pb > 0:
                data[code] = 1.0 / pb
        return pd.Series(data, name="bp")

    @staticmethod
    def sp_factor(metrics_map: dict) -> pd.Series:
        """S/P 因子 — 1/PS，值越高越被低估"""
        data = {}
        for code, m in metrics_map.items():
            ps = m.get("ps")
            if ps and ps > 0:
                data[code] = 1.0 / ps
        return pd.Series(data, name="sp")

    # ================================================================
    # 成长因子
    # ================================================================

    @staticmethod
    def revenue_growth(metrics_map: dict) -> pd.Series:
        """营收增速因子"""
        data = {}
        for code, m in metrics_map.items():
            rev = m.get("revenue_yoy")
            if rev is not None and not np.isnan(rev):
                data[code] = rev
        return pd.Series(data, name="revenue_growth")

    @staticmethod
    def profit_growth(metrics_map: dict) -> pd.Series:
        """利润增速因子"""
        data = {}
        for code, m in metrics_map.items():
            np_yoy = m.get("net_profit_yoy")
            if np_yoy is not None and not np.isnan(np_yoy):
                data[code] = np_yoy
        return pd.Series(data, name="profit_growth")

    @staticmethod
    def eps_trend(metrics_map: dict) -> pd.Series:
        """EPS 绝对值因子 — 每股盈利能力"""
        data = {}
        for code, m in metrics_map.items():
            eps = m.get("eps")
            if eps is not None and not np.isnan(eps):
                data[code] = eps
        return pd.Series(data, name="eps")

    # ================================================================
    # 质量因子
    # ================================================================

    @staticmethod
    def roe_quality(metrics_map: dict) -> pd.Series:
        """ROE 因子 — 高 ROE 通常质量更好"""
        data = {}
        for code, m in metrics_map.items():
            roe = m.get("roe")
            if roe is not None and not np.isnan(roe):
                data[code] = roe
        return pd.Series(data, name="roe")

    @staticmethod
    def roa_quality(metrics_map: dict) -> pd.Series:
        """ROA 因子"""
        data = {}
        for code, m in metrics_map.items():
            roa = m.get("roa")
            if roa is not None and not np.isnan(roa):
                data[code] = roa
        return pd.Series(data, name="roa")

    @staticmethod
    def gross_margin_quality(metrics_map: dict) -> pd.Series:
        """毛利率因子 — 高毛利率=护城河"""
        data = {}
        for code, m in metrics_map.items():
            gm = m.get("gross_margin")
            if gm is not None and not np.isnan(gm):
                data[code] = gm
        return pd.Series(data, name="gross_margin")

    @staticmethod
    def net_margin_quality(metrics_map: dict) -> pd.Series:
        """净利率因子"""
        data = {}
        for code, m in metrics_map.items():
            nm = m.get("net_margin")
            if nm is not None and not np.isnan(nm):
                data[code] = nm
        return pd.Series(data, name="net_margin")

    @staticmethod
    def debt_burden(metrics_map: dict) -> pd.Series:
        """负债率因子 — 负向 (高负债=高风险)"""
        data = {}
        for code, m in metrics_map.items():
            dr = m.get("debt_ratio")
            if dr is not None and not np.isnan(dr):
                data[code] = -dr  # 取反: 高分=低负债
        return pd.Series(data, name="debt_burden")

    # ================================================================
    # 动量因子 (基于价格变化 — 可从行情或技术指标派生)
    # ================================================================

    @staticmethod
    def momentum_1m(klines_map: dict) -> pd.Series:
        """1 月动量因子 — 近 20 日累计收益率"""
        data = {}
        for code, kline in klines_map.items():
            if kline is None or kline.empty or "close" not in kline.columns:
                continue
            if len(kline) >= 20:
                close = kline["close"].astype(float)
                data[code] = (close.iloc[-1] / close.iloc[-20] - 1) * 100
        return pd.Series(data, name="momentum_1m")

    @staticmethod
    def momentum_3m(klines_map: dict) -> pd.Series:
        """3 月动量因子 — 近 60 日累计收益率"""
        data = {}
        for code, kline in klines_map.items():
            if kline is None or kline.empty or "close" not in kline.columns:
                continue
            if len(kline) >= 60:
                close = kline["close"].astype(float)
                data[code] = (close.iloc[-1] / close.iloc[-60] - 1) * 100
        return pd.Series(data, name="momentum_3m")

    # ================================================================
    # 波动因子
    # ================================================================

    @staticmethod
    def volatility_20d(klines_map: dict) -> pd.Series:
        """20 日波动率因子 — 负向 (高波动=高风险)"""
        data = {}
        for code, kline in klines_map.items():
            if kline is None or kline.empty or "close" not in kline.columns:
                continue
            if len(kline) >= 20:
                close = kline["close"].astype(float)
                returns = close.pct_change().dropna()
                if len(returns) >= 10:
                    vol = returns.iloc[-20:].std() * np.sqrt(252) * 100
                    data[code] = -vol  # 取反: 高分=低波动
        return pd.Series(data, name="volatility_20d")

    @staticmethod
    def max_drawdown_60d(klines_map: dict) -> pd.Series:
        """60 日最大回撤因子 — 负向 (小回撤=低风险)"""
        data = {}
        for code, kline in klines_map.items():
            if kline is None or kline.empty or "close" not in kline.columns:
                continue
            if len(kline) >= 60:
                close = kline["close"].astype(float).iloc[-60:]
                peak = close.expanding().max()
                dd = (close - peak) / peak * 100
                max_dd = dd.min()
                data[code] = max_dd  # 负值, 越接近 0 越好
        return pd.Series(data, name="max_drawdown_60d")

    # ================================================================
    # 因子合成
    # ================================================================

    @staticmethod
    def compute_all_factors(metrics_map: dict, klines_map: dict = None) -> pd.DataFrame:
        """计算所有因子值，返回 (stocks × factors) DataFrame"""
        klines_map = klines_map or {}
        factor_funcs = [
            AlphaFactors.ep_factor,
            AlphaFactors.bp_factor,
            AlphaFactors.revenue_growth,
            AlphaFactors.profit_growth,
            AlphaFactors.eps_trend,
            AlphaFactors.roe_quality,
            AlphaFactors.roa_quality,
            AlphaFactors.gross_margin_quality,
            AlphaFactors.net_margin_quality,
            AlphaFactors.debt_burden,
        ]

        factors = {}
        for func in factor_funcs:
            try:
                series = func(metrics_map)
                if not series.empty:
                    factors[series.name] = series
            except Exception as e:
                logger.debug(f"Factor {func.__name__} failed: {e}")

        # 动量/波动因子需要 K 线数据
        if klines_map:
            for func in [AlphaFactors.momentum_1m, AlphaFactors.momentum_3m,
                         AlphaFactors.volatility_20d, AlphaFactors.max_drawdown_60d]:
                try:
                    series = func(klines_map)
                    if not series.empty:
                        factors[series.name] = series
                except Exception as e:
                    logger.debug(f"Factor {func.__name__} failed: {e}")

        if not factors:
            return pd.DataFrame()

        df = pd.DataFrame(factors)
        df.index.name = "code"
        return df

    @staticmethod
    def compute_composite_score(factor_df: pd.DataFrame, weights: dict = None) -> pd.Series:
        """
        合成综合评分 — 等权或自定义权重

        factor_df: (stocks × factors) raw factor values
        weights: {factor_name: weight}, None 则等权

        返回: (stocks,) z-score 标准化后的综合评分 (0-100)
        """
        if factor_df.empty:
            return pd.Series(dtype=float, name="composite_score")

        # Z-score 标准化 (截面)
        normalized = factor_df.copy()
        for col in normalized.columns:
            mean = normalized[col].mean()
            std = normalized[col].std()
            if std and std > 0:
                normalized[col] = (normalized[col] - mean) / std

        # 等权合成
        if weights is None:
            weights = {col: 1.0 / len(normalized.columns) for col in normalized.columns}

        # 加权求和
        composite = pd.Series(0.0, index=normalized.index, name="composite_score")
        for col in normalized.columns:
            w = weights.get(col, 0)
            if w > 0 and col in normalized.columns:
                composite += normalized[col].fillna(0) * w

        # 映射到 0-100 区间
        if composite.std() > 0:
            composite = (composite - composite.min()) / (composite.max() - composite.min()) * 100

        return composite.round(2)
