"""
持仓风险分析 — VaR, CVaR, 最大回撤, 夏普比率, Beta, 相关性矩阵
"""

import numpy as np
import pandas as pd
from loguru import logger


class RiskAnalyzer:
    """风险分析工具集 — 全部为静态方法"""

    @staticmethod
    def returns_from_klines(klines_map: dict) -> pd.Series:
        """从 K 线图计算每只股票的日收益率 Series (统一索引=日期)"""
        all_returns = {}
        for code, kline in klines_map.items():
            if kline is None or kline.empty or "close" not in kline.columns:
                continue
            close = kline["close"].astype(float)
            rets = close.pct_change().dropna()
            if len(rets) >= 5:
                all_returns[code] = rets
        if not all_returns:
            return pd.DataFrame()
        # 对齐为 DataFrame
        df = pd.DataFrame(all_returns).dropna(how="all")
        return df

    @staticmethod
    def var(returns: pd.Series, confidence: float = 0.95) -> float:
        """
        Value at Risk — 历史模拟法
        returns: 日收益率序列
        """
        if returns.empty or len(returns) < 10:
            return 0.0
        return float(returns.quantile(1 - confidence))

    @staticmethod
    def cvar(returns: pd.Series, confidence: float = 0.95) -> float:
        """
        Conditional VaR — 尾部期望损失
        """
        if returns.empty or len(returns) < 10:
            return 0.0
        var_val = RiskAnalyzer.var(returns, confidence)
        tail = returns[returns <= var_val]
        if tail.empty:
            return var_val
        return float(tail.mean())

    @staticmethod
    def max_drawdown(nav: pd.Series) -> float:
        """最大回撤 — 净值曲线"""
        if nav.empty or len(nav) < 2:
            return 0.0
        peak = nav.expanding().max()
        dd = (nav - peak) / peak
        return float(dd.min())

    @staticmethod
    def max_drawdown_from_returns(returns: pd.Series) -> float:
        """从收益率序列计算最大回撤"""
        if returns.empty:
            return 0.0
        nav = (1 + returns).cumprod()
        return RiskAnalyzer.max_drawdown(nav)

    @staticmethod
    def sharpe_ratio(returns: pd.Series, rf: float = 0.02, periods_per_year: int = 252) -> float:
        """
        年化夏普比率
        rf: 无风险利率 (默认 2%)
        """
        if returns.empty or len(returns) < 5:
            return 0.0
        excess = returns - rf / periods_per_year
        if excess.std() == 0:
            return 0.0
        return float(excess.mean() / excess.std() * np.sqrt(periods_per_year))

    @staticmethod
    def sortino_ratio(returns: pd.Series, rf: float = 0.02, periods_per_year: int = 252) -> float:
        """
        年化索提诺比率 — 仅用下行波动率
        """
        if returns.empty or len(returns) < 5:
            return 0.0
        excess = returns - rf / periods_per_year
        downside = excess[excess < 0]
        if len(downside) < 3 or downside.std() == 0:
            return 0.0
        return float(excess.mean() / downside.std() * np.sqrt(periods_per_year))

    @staticmethod
    def beta(stock_returns: pd.Series, benchmark_returns: pd.Series) -> float:
        """
        Beta 系数 — 相对基准的系统性风险
        beta > 1: 比市场更波动; beta < 1: 更防御
        """
        common = stock_returns.index.intersection(benchmark_returns.index)
        if len(common) < 20:
            return 1.0
        s = stock_returns.loc[common]
        b = benchmark_returns.loc[common]
        cov = s.cov(b)
        var = b.var()
        if var == 0:
            return 1.0
        return float(cov / var)

    @staticmethod
    def correlation_matrix(returns_df: pd.DataFrame) -> pd.DataFrame:
        """持仓相关性矩阵"""
        if returns_df.empty or returns_df.shape[1] < 2:
            return pd.DataFrame()
        return returns_df.corr()

    @staticmethod
    def portfolio_risk_report(returns_df: pd.DataFrame, benchmark_returns: pd.Series = None) -> dict:
        """
        综合风险报告

        Returns
        -------
        dict with:
            avg_return: 平均年化收益
            volatility: 年化波动率
            sharpe: 夏普比率
            sortino: 索提诺比率
            max_dd: 最大回撤
            var_95: 95% VaR
            cvar_95: 95% CVaR
            avg_correlation: 持仓平均相关性
            concentration: 前 3 集中度
        """
        if returns_df.empty or returns_df.shape[1] == 0:
            return {}

        # 等权组合收益
        portfolio_returns = returns_df.mean(axis=1)
        n_stocks = returns_df.shape[1]

        report = {
            "n_stocks": n_stocks,
            "avg_return": round(float(portfolio_returns.mean() * 252 * 100), 2),
            "volatility": round(float(portfolio_returns.std() * np.sqrt(252) * 100), 2),
            "sharpe": round(RiskAnalyzer.sharpe_ratio(portfolio_returns), 2),
            "sortino": round(RiskAnalyzer.sortino_ratio(portfolio_returns), 2),
            "max_dd": round(RiskAnalyzer.max_drawdown_from_returns(portfolio_returns) * 100, 2),
            "var_95": round(RiskAnalyzer.var(portfolio_returns) * 100, 2),
            "cvar_95": round(RiskAnalyzer.cvar(portfolio_returns) * 100, 2),
        }

        # Beta
        if benchmark_returns is not None and not benchmark_returns.empty:
            report["beta"] = round(RiskAnalyzer.beta(portfolio_returns, benchmark_returns), 2)

        # 平均相关性
        if n_stocks >= 2:
            corr = RiskAnalyzer.correlation_matrix(returns_df)
            if not corr.empty:
                # 上三角均值 (不含对角线)
                upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
                report["avg_correlation"] = round(float(upper.stack().mean()), 3)

                # 前 3 集中度: 最高的 3 个权重所对应的平均相关
                if n_stocks >= 3:
                    top3 = upper.stack().nlargest(3).mean()
                    report["concentration"] = round(float(top3), 3)
                else:
                    report["concentration"] = report.get("avg_correlation", 1.0)

        return report
