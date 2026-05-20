"""
北向资金数据抓取模块 NorthFlowFetcher
接入沪深港通北向资金净流入、持仓明细、十大成交股
"""

import time
from datetime import datetime, date
from typing import Optional

import pandas as pd
from loguru import logger

from quant_loom.ops.retry import network_retry


class NorthFlowFetcher:
    """沪深港通北向资金数据抓取器"""

    def __init__(self):
        self._last_call = 0.0

    def _throttle(self, min_interval: float = 1.5):
        elapsed = time.time() - self._last_call
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_call = time.time()

    @network_retry
    def _call_ak(self, fn, **kwargs):
        """带重试的 AkShare 调用"""
        self._throttle()
        import akshare as ak
        return fn(**kwargs)

    # ================================================================
    # 北向资金净流入
    # ================================================================

    def fetch_north_net_flow(self, days: int = 20) -> Optional[pd.DataFrame]:
        """
        获取北向资金历史净流入数据

        Returns
        -------
        DataFrame with columns: date, net_inflow_sh (沪股通), net_inflow_sz (深股通), total_net_inflow
        """
        try:
            df = self._call_ak(ak.stock_hsgt_north_net_flow_in_em)

            if df is None or df.empty:
                logger.warning("North net flow data is empty")
                return None

            df = df.tail(days).copy()
            df = df.rename(columns={
                "日期": "date",
                "当日净流入": "total_net_inflow",
                "沪股通净流入": "net_inflow_sh",
                "深股通净流入": "net_inflow_sz",
            })

            # Normalize: may have different column names in newer AkShare versions
            for col_map, target in [
                (["date", "日期"], "date"),
                (["total_net_inflow", "当日净流入", "北向资金净流入"], "total_net_inflow"),
                (["net_inflow_sh", "沪股通净流入", "沪股通"], "net_inflow_sh"),
                (["net_inflow_sz", "深股通净流入", "深股通"], "net_inflow_sz"),
            ]:
                for src in col_map:
                    if src in df.columns and target not in df.columns:
                        df = df.rename(columns={src: target})

            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"], errors="coerce")

            logger.info(f"North net flow fetched: {len(df)} records")
            return df
        except Exception as e:
            logger.warning(f"Failed to fetch north net flow: {e}")
            return None

    # ================================================================
    # 北向持仓明细
    # ================================================================

    def fetch_north_holdings(self, trade_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        获取沪深港通持股明细 (个股维度)

        Parameters
        ----------
        trade_date: 交易日期 "YYYY-MM-DD"，None 为最新

        Returns
        -------
        DataFrame with: code, name, hold_shares, hold_market_value, hold_ratio
        """
        try:
            df = self._call_ak(ak.stock_hsgt_hold_share_em, date=trade_date or "20260101")

            if df is None or df.empty:
                logger.warning("North holdings data is empty")
                return None

            df = df.copy()
            df = df.rename(columns={
                "代码": "code",
                "名称": "name",
                "持股数量": "hold_shares",
                "持股市值": "hold_market_value",
                "持股占比": "hold_ratio",
            })
            # Remap any remaining Chinese column names
            for cn, en in [
                ("持股数", "hold_shares"),
                ("持股市值", "hold_market_value"),
                ("占流通股比例", "hold_ratio"),
            ]:
                if cn in df.columns and en not in df.columns:
                    df = df.rename(columns={cn: en})

            if "code" in df.columns:
                df["code"] = df["code"].astype(str).str.zfill(6)

            logger.info(f"North holdings fetched: {len(df)} stocks")
            return df
        except Exception as e:
            logger.warning(f"Failed to fetch north holdings: {e}")
            return None

    # ================================================================
    # 十大成交活跃股
    # ================================================================

    def fetch_north_top10(self) -> Optional[pd.DataFrame]:
        """
        获取北向资金十大成交活跃股

        Returns
        -------
        DataFrame with: code, name, net_buy_amount, buy_amount, sell_amount
        """
        try:
            df = self._call_ak(ak.stock_hsgt_top10_em)

            if df is None or df.empty:
                logger.warning("North top10 data is empty")
                return None

            df = df.copy()
            df = df.rename(columns={
                "代码": "code",
                "名称": "name",
                "净买入": "net_buy_amount",
                "买入金额": "buy_amount",
                "卖出金额": "sell_amount",
            })

            if "code" in df.columns:
                df["code"] = df["code"].astype(str).str.zfill(6)

            logger.info(f"North top10 fetched: {len(df)} records")
            return df
        except Exception as e:
            logger.warning(f"Failed to fetch north top10: {e}")
            return None

    # ================================================================
    # 批量获取 + 格式化为特征字典
    # ================================================================

    def fetch_features(self) -> dict:
        """
        批量获取北向资金数据并返回特征字典 (供规则引擎)

        Returns
        -------
        dict with:
            north_net_inflow_today: float (当日净流入 亿元)
            north_net_inflow_5d_avg: float (5日均净流入)
            north_inflow_accel: float (流入加速率 %)
            north_top10_net_buy: {code: net_buy_amount} 十大成交净买映射
            north_holding_top: list[dict] 北向重仓 Top20
        """
        features: dict = {
            "north_net_inflow_today": 0.0,
            "north_net_inflow_5d_avg": 0.0,
            "north_inflow_accel": 0.0,
            "north_top10_net_buy": {},
            "north_holding_top": [],
        }

        # 净流入
        flow = self.fetch_north_net_flow(days=20)
        if flow is not None and not flow.empty:
            inflow_col = "total_net_inflow"
            if inflow_col in flow.columns:
                inflows = pd.to_numeric(flow[inflow_col], errors="coerce").fillna(0)
                if len(inflows) > 0:
                    features["north_net_inflow_today"] = round(float(inflows.iloc[-1]), 2)
                if len(inflows) >= 5:
                    features["north_net_inflow_5d_avg"] = round(float(inflows.tail(5).mean()), 2)
                if len(inflows) >= 6 and features["north_net_inflow_5d_avg"] != 0:
                    prev_5d_avg = float(inflows.tail(10).head(5).mean())
                    curr_5d_avg = float(inflows.tail(5).mean())
                    if abs(prev_5d_avg) > 1:
                        features["north_inflow_accel"] = round(
                            (curr_5d_avg - prev_5d_avg) / abs(prev_5d_avg) * 100, 1
                        )

        # 十大成交
        top10 = self.fetch_north_top10()
        if top10 is not None and not top10.empty and "code" in top10.columns:
            for _, row in top10.iterrows():
                code = str(row.get("code", ""))
                net = float(row.get("net_buy_amount", 0) or 0)
                features["north_top10_net_buy"][code] = net

        # 持仓 Top20
        holdings = self.fetch_north_holdings()
        if holdings is not None and not holdings.empty:
            if "hold_market_value" in holdings.columns:
                top_holdings = holdings.nlargest(20, "hold_market_value")
                features["north_holding_top"] = [
                    {
                        "code": str(row.get("code", "")),
                        "name": str(row.get("name", "")),
                        "hold_ratio": float(row.get("hold_ratio", 0) or 0),
                    }
                    for _, row in top_holdings.iterrows()
                ]

        return features
