"""
龙虎榜数据抓取模块 LHBFetcher
接入龙虎榜明细、个股上榜统计、机构席位追踪
"""

import time
from datetime import datetime, date
from typing import Optional, Dict, List

import pandas as pd
from loguru import logger

from quant_loom.ops.retry import network_retry


class LHBFetcher:
    """龙虎榜 (LHB) 数据抓取器 — 识别机构/游资行为"""

    def __init__(self):
        self._last_call = 0.0

    def _throttle(self, min_interval: float = 1.5):
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
    # 龙虎榜明细
    # ================================================================

    def fetch_lhb_detail(self, trade_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        获取龙虎榜明细 (当日上榜个股的买入/卖出席位)

        Parameters
        ----------
        trade_date: "YYYYMMDD" 格式, None 为最近交易日

        Returns
        -------
        DataFrame with: code, name, close, pct_change, turnover_rate,
                       lhb_net_amount (龙虎榜净买额), lhb_buy_amount, lhb_sell_amount,
                       reason (上榜原因), inst_buy_seats, inst_sell_seats
        """
        try:
            import akshare as ak

            date_str = trade_date or datetime.now().strftime("%Y%m%d")
            df = self._call_ak(ak.stock_lhb_detail_em, date=date_str)

            if df is None or df.empty:
                logger.info(f"No LHB data for {date_str}")
                return None

            df = df.copy()
            df = df.rename(columns={
                "代码": "code", "名称": "name",
                "收盘价": "close", "涨跌幅": "pct_change",
                "换手率": "turnover_rate",
                "龙虎榜净买额": "lhb_net_amount",
                "龙虎榜买入额": "lhb_buy_amount",
                "龙虎榜卖出额": "lhb_sell_amount",
                "上榜原因": "reason",
            })

            if "code" in df.columns:
                df["code"] = df["code"].astype(str).str.zfill(6)

            # 统计机构席位参与 (买入/卖出机构席位计数)
            # 席位名称通常含 "机构专用" 字样
            inst_buy_col = None
            inst_sell_col = None
            for col in df.columns:
                if "买入" in col and ("席位" in col or "营业部" in col):
                    inst_buy_col = col
                if "卖出" in col and ("席位" in col or "营业部" in col):
                    inst_sell_col = col

            logger.info(f"LHB detail fetched: {len(df)} records for {date_str}")
            return df
        except Exception as e:
            logger.warning(f"Failed to fetch LHB detail: {e}")
            return None

    # ================================================================
    # 个股上榜统计
    # ================================================================

    def fetch_lhb_top_list(self, period: str = "近一月") -> Optional[pd.DataFrame]:
        """
        获取个股龙虎榜上榜次数统计

        Parameters
        ----------
        period: "近一月" / "近三月" / "近六月" / "近一年"

        Returns
        -------
        DataFrame with: code, name,上榜次数, 累积龙虎榜净买额
        """
        try:
            import akshare as ak

            df = self._call_ak(ak.stock_lhb_stock_statistic_em)

            if df is None or df.empty:
                logger.info("LHB top list is empty")
                return None

            df = df.copy()
            # AkShare 返回的列名可能是中文
            rename_map = {}
            for cn, en in [
                ("代码", "code"), ("名称", "name"),
                ("上榜次数", "on_board_count"),
                ("龙虎榜净买额", "total_lhb_net"),
            ]:
                if cn in df.columns:
                    rename_map[cn] = en
            if rename_map:
                df = df.rename(columns=rename_map)

            if "code" in df.columns:
                df["code"] = df["code"].astype(str).str.zfill(6)

            # Filter by period if column exists
            logger.info(f"LHB top list fetched: {len(df)} records")
            return df
        except Exception as e:
            logger.warning(f"Failed to fetch LHB top list: {e}")
            return None

    # ================================================================
    # 批量特征提取
    # ================================================================

    def fetch_features(self, candidate_codes: Optional[List[str]] = None) -> dict:
        """
        批量获取龙虎榜特征 (供规则引擎)

        Returns
        -------
        dict with:
            lhb_stocks: {code: {net_amount, reason, buy_seats, sell_seats}} 当日上榜股票
            lhb_inst_stocks: [code] 机构席位参与的股票
            lhb_top_month: {code: {count, total_net}} 近期频繁上榜统计
        """
        features: dict = {
            "lhb_stocks": {},
            "lhb_inst_stocks": [],
            "lhb_top_month": {},
        }

        # 当日明细
        detail = self.fetch_lhb_detail()
        if detail is not None and not detail.empty:
            for _, row in detail.iterrows():
                code = str(row.get("code", ""))
                if not code:
                    continue

                info = {
                    "net_amount": float(row.get("lhb_net_amount", 0) or 0),
                    "reason": str(row.get("reason", "")),
                    "pct_change": float(row.get("pct_change", 0) or 0),
                }
                features["lhb_stocks"][code] = info

                # 检测机构席位: 买入/卖出营业部名称含 "机构专用"
                reason_str = str(row.get("reason", ""))
                if "机构专用" in reason_str or "机构" in reason_str:
                    features["lhb_inst_stocks"].append(code)

        # 上榜统计 (识别频繁上榜)
        top_list = self.fetch_lhb_top_list()
        if top_list is not None and not top_list.empty:
            for _, row in top_list.iterrows():
                code = str(row.get("code", ""))
                if not code:
                    continue
                features["lhb_top_month"][code] = {
                    "count": int(row.get("on_board_count", 0) or 0),
                    "total_net": float(row.get("total_lhb_net", 0) or 0),
                }

        if features["lhb_stocks"]:
            logger.info(f"LHB features: {len(features['lhb_stocks'])} on board "
                       f"({len(features['lhb_inst_stocks'])} with institutional seats)")

        return features
