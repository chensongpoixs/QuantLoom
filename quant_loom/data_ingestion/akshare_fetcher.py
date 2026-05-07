"""
AkShare 数据抓取模块
通过东方财富公开 API 获取 A 股行情、资金流等数据
"""

import time
from datetime import datetime, date
from typing import Optional

import pandas as pd
from loguru import logger

from quant_loom.ops.retry import network_retry


class AkshareFetcher:
    """AkShare / 东方财富 数据抓取器"""

    def __init__(self, rate_limit: float = 1.0):
        self.rate_limit = rate_limit
        self._last_call = 0.0

    @property
    def enabled(self) -> bool:
        return True  # AkShare 免费，无需 token

    def _throttle(self):
        elapsed = time.time() - self._last_call
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_call = time.time()

    # ---- 股票列表 + 实时行情 ----

    def fetch_all_stocks(self) -> pd.DataFrame:
        """获取全 A 股列表（含名称）"""
        try:
            import akshare as ak

            @network_retry
            def _do_call():
                self._throttle()
                return ak.stock_info_a_code_name()

            df = _do_call()
            df = df.rename(columns={"code": "code", "name": "name"})
            logger.info(f"AkShare 获取全 A 股列表: {len(df)} 只")
            return df
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return pd.DataFrame()

    def fetch_realtime_quotes(self) -> pd.DataFrame:
        """获取全市场实时行情快照（东方财富）"""
        try:
            import akshare as ak
            ts = datetime.now()

            @network_retry
            def _do_call():
                self._throttle()
                return ak.stock_zh_a_spot_em()

            df = _do_call()
            df = df.rename(columns={
                "代码": "code",
                "名称": "name",
                "最新价": "latest",
                "涨跌幅": "pct_change",
                "成交量": "volume",
                "成交额": "turnover_amount",
                "换手率": "turnover_rate",
            })
            df["ts"] = ts
            df["source"] = "akshare"
            logger.info(f"AkShare 获取实时行情: {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取实时行情失败: {e}")
            return pd.DataFrame()

    # ---- 资金流 ----

    def fetch_fund_flow_rank(self) -> pd.DataFrame:
        """获取全市场个股资金流排名（东方财富）"""
        try:
            import akshare as ak
            ts = datetime.now()

            @network_retry
            def _do_call():
                self._throttle()
                return ak.stock_individual_fund_flow_rank(indicator="今日")

            df = _do_call()
            df = df.rename(columns={
                "代码": "code",
                "名称": "name",
                "最新价": "latest",
                "涨跌幅": "pct_change",
                "超大单净流入": "super_large_net_inflow",
                "大单净流入": "large_net_inflow",
                "中单净流入": "medium_net_inflow",
                "小单净流入": "small_net_inflow",
                "主力净流入最大股": "main_force_stock",
            })
            df["ts"] = ts
            df["source"] = "akshare"
            logger.info(f"AkShare 获取资金流排名: {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取资金流排名失败: {e}")
            return pd.DataFrame()

    def fetch_individual_fund_flow(self, code: str, market: str = "sh") -> Optional[pd.DataFrame]:
        """获取单只股票历史资金流"""
        try:
            import akshare as ak

            @network_retry
            def _do_call():
                self._throttle()
                return ak.stock_individual_fund_flow(stock=code, market=market)

            df = _do_call()
            logger.debug(f"获取个股资金流: {code}")
            return df
        except Exception as e:
            logger.warning(f"获取个股资金流失败 {code}: {e}")
            return None

    # ---- 板块 ----

    def fetch_sector_quotes(self) -> pd.DataFrame:
        """获取行业板块行情"""
        try:
            import akshare as ak

            @network_retry
            def _do_call():
                self._throttle()
                return ak.stock_board_industry_name_em()

            df = _do_call()
            df = df.rename(columns={
                "板块名称": "sector_name",
                "涨跌幅": "pct_change",
                "主力净流入": "main_net_inflow",
            })
            logger.info(f"AkShare 获取板块行情: {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取板块行情失败: {e}")
            return pd.DataFrame()

    # ---- 历史数据 ----

    def fetch_history(self, code: str, period: str = "1d", days: int = 250) -> Optional[pd.DataFrame]:
        """获取单只股票历史 K 线"""
        try:
            import akshare as ak

            @network_retry
            def _do_call():
                self._throttle()
                return ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")

            df = _do_call()
            if df is not None and not df.empty:
                df = df.tail(days)
            return df
        except Exception as e:
            logger.warning(f"获取历史K线失败 {code}: {e}")
            return None

    def is_trading_time(self) -> bool:
        """简单判断是否在 A 股交易时段"""
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        mt = now.replace(hour=9, minute=30, second=0)
        me = now.replace(hour=11, minute=30, second=0)
        at = now.replace(hour=13, minute=0, second=0)
        ae = now.replace(hour=15, minute=0, second=0)
        return (mt <= now <= me) or (at <= now <= ae)
