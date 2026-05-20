"""
财务数据抓取模块 FinanceFetcher
接入利润表/资产负债表/现金流量表/关键财务指标
"""

import time
from datetime import datetime
from typing import Optional, Dict, List

import pandas as pd
from loguru import logger

from quant_loom.ops.retry import network_retry


class FinanceFetcher:
    """财务数据抓取器 — 为多因子模型提供基本面数据"""

    def __init__(self):
        self._last_call = 0.0

    def _throttle(self, min_interval: float = 1.0):
        elapsed = time.time() - self._last_call
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_call = time.time()

    @network_retry
    def _call_ak(self, fn, **kwargs):
        self._throttle()
        import akshare as ak
        return fn(**kwargs)

    # ================================================================
    # 业绩报表 (利润表核心指标)
    # ================================================================

    def fetch_performance(self, date_str: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        获取 A 股业绩报表 (东方财富)

        Parameters
        ----------
        date_str: "YYYYMMDD" 格式的报告期, None 为最新

        Returns
        -------
        DataFrame with: code, name, eps (每股收益), roe (净资产收益率),
                       net_profit_yoy (净利润同比), revenue_yoy (营收同比),
                       gross_margin (毛利率), net_margin (净利率)
        """
        try:
            import akshare as ak

            df = self._call_ak(ak.stock_yjbb_em, date=date_str or datetime.now().strftime("%Y%m%d"))

            if df is None or df.empty:
                logger.info("No performance data available")
                return None

            df = df.copy()
            rename_map = {}
            for cn, en in [
                ("股票代码", "code"), ("股票简称", "name"),
                ("每股收益", "eps"), ("营业收入-同比增长", "revenue_yoy"),
                ("净利润-同比增长", "net_profit_yoy"),
                ("净资产收益率", "roe"), ("销售毛利率", "gross_margin"),
                ("营业总收入", "total_revenue"), ("净利润", "net_profit"),
            ]:
                if cn in df.columns:
                    rename_map[cn] = en
            if rename_map:
                df = df.rename(columns=rename_map)

            if "code" in df.columns:
                df["code"] = df["code"].astype(str).str.zfill(6)

            # 转换数值列
            for col in ["eps", "revenue_yoy", "net_profit_yoy", "roe", "gross_margin"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            logger.info(f"Performance data fetched: {len(df)} stocks")
            return df
        except Exception as e:
            logger.warning(f"Failed to fetch performance data: {e}")
            return None

    # ================================================================
    # 业绩快报 (更及时的业绩数据)
    # ================================================================

    def fetch_express_report(self, date_str: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        获取业绩快报 (东方财富)
        比正式报表更早发布，用于提前感知业绩拐点
        """
        try:
            import akshare as ak

            df = self._call_ak(ak.stock_yjkb_em, date=date_str or datetime.now().strftime("%Y%m%d"))

            if df is None or df.empty:
                return None

            df = df.copy()
            rename_map = {}
            for cn, en in [
                ("股票代码", "code"), ("股票简称", "name"),
                ("每股收益", "eps"), ("营业收入-同比增长", "revenue_yoy"),
                ("净利润-同比增长", "net_profit_yoy"),
                ("净资产收益率", "roe"),
            ]:
                if cn in df.columns:
                    rename_map[cn] = en
            if rename_map:
                df = df.rename(columns=rename_map)

            if "code" in df.columns:
                df["code"] = df["code"].astype(str).str.zfill(6)

            logger.info(f"Express report fetched: {len(df)} stocks")
            return df
        except Exception as e:
            logger.warning(f"Failed to fetch express report: {e}")
            return None

    # ================================================================
    # 财务报表 (利润表/负债表/现金流)
    # ================================================================

    def fetch_income_statement(self, code: str, date_str: Optional[str] = None) -> Optional[pd.DataFrame]:
        """获取个股利润表"""
        try:
            import akshare as ak
            self._throttle()
            df = ak.stock_profit_sheet_by_report_ths(symbol=code, indicator="利润表")
            if df is not None and not df.empty:
                logger.debug(f"Income statement fetched: {code}")
            return df
        except Exception as e:
            logger.debug(f"Income statement fetch failed {code}: {e}")
            return None

    def fetch_balance_sheet(self, code: str, date_str: Optional[str] = None) -> Optional[pd.DataFrame]:
        """获取个股资产负债表"""
        try:
            import akshare as ak
            self._throttle()
            df = ak.stock_balance_sheet_by_report_ths(symbol=code, indicator="资产负债表")
            if df is not None and not df.empty:
                logger.debug(f"Balance sheet fetched: {code}")
            return df
        except Exception as e:
            logger.debug(f"Balance sheet fetch failed {code}: {e}")
            return None

    def fetch_cash_flow(self, code: str, date_str: Optional[str] = None) -> Optional[pd.DataFrame]:
        """获取个股现金流量表"""
        try:
            import akshare as ak
            self._throttle()
            df = ak.stock_cash_flow_sheet_by_report_ths(symbol=code, indicator="现金流量表")
            if df is not None and not df.empty:
                logger.debug(f"Cash flow fetched: {code}")
            return df
        except Exception as e:
            logger.debug(f"Cash flow fetch failed {code}: {e}")
            return None

    # ================================================================
    # 财务摘要 (PE/PB/PS/ROE/ROA 等关键指标)
    # ================================================================

    def fetch_key_metrics(self, code: str) -> dict:
        """
        获取个股关键财务指标摘要

        Returns
        -------
        dict with: pe, pb, ps, roe, roa, gross_margin, net_margin,
                  debt_ratio, current_ratio, dividend_yield
        """
        metrics: dict = {}
        try:
            import akshare as ak
            self._throttle()

            # 使用东方财富个股财务指标接口
            try:
                df = ak.stock_financial_analysis_indicator(symbol=code)
                if df is not None and not df.empty:
                    latest = df.iloc[-1] if len(df) > 0 else df.iloc[0]
                    for cn, en in [
                        ("净资产收益率(%)", "roe"), ("总资产报酬率(%)", "roa"),
                        ("销售毛利率(%)", "gross_margin"), ("销售净利率(%)", "net_margin"),
                        ("资产负债率(%)", "debt_ratio"), ("流动比率", "current_ratio"),
                        ("存货周转率", "inventory_turnover"),
                    ]:
                        val = latest.get(cn)
                        if val is not None and pd.notna(val):
                            metrics[en] = float(val)
            except Exception:
                logger.debug(f"stock_financial_analysis_indicator failed for {code}")

            # 补充 PE/PB/PS — 从行情或估值接口获取
            try:
                self._throttle()
                df_val = ak.stock_a_lg_indicator(symbol=code)
                if df_val is not None and not df_val.empty:
                    latest_val = df_val.iloc[-1] if len(df_val) > 0 else df_val.iloc[0]
                    for key, en in [("pe", "pe"), ("pb", "pb"), ("ps", "ps"), ("peg", "peg")]:
                        val = latest_val.get(key)
                        if val is not None and pd.notna(val):
                            metrics[en] = float(val)
            except Exception:
                logger.debug(f"stock_a_lg_indicator failed for {code}")

            if metrics:
                logger.debug(f"Key metrics for {code}: {', '.join(f'{k}={v}' for k, v in list(metrics.items())[:5])}")

        except Exception as e:
            logger.debug(f"Key metrics fetch failed {code}: {e}")

        return metrics

    # ================================================================
    # 批量特征提取
    # ================================================================

    def fetch_features(self, candidate_codes: Optional[List[str]] = None) -> dict:
        """
        批量获取财务特征

        Returns
        -------
        dict with:
            performance: DataFrame (全市场业绩报表)
            express: DataFrame (业绩快报)
            metrics_map: {code: {pe, pb, roe, roa, ...}} 关键指标映射
        """
        features: dict = {
            "performance": None,
            "express": None,
            "metrics_map": {},
        }

        # 业绩报表
        perf = self.fetch_performance()
        if perf is not None and not perf.empty:
            features["performance"] = perf

        # 业绩快报
        express = self.fetch_express_report()
        if express is not None and not express.empty:
            features["express"] = express

        # 关键指标 (仅获取候选股)
        codes_to_fetch = candidate_codes or []
        if codes_to_fetch:
            for code in codes_to_fetch:
                metrics = self.fetch_key_metrics(code)
                if metrics:
                    features["metrics_map"][code] = metrics

        return features
