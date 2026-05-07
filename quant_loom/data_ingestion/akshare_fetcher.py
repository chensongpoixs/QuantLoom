"""
AkShare 数据抓取模块
负责从公开数据源获取 A 股行情、资金流等数据
"""

import time
from datetime import datetime
from typing import Optional

import akshare as ak
import pandas as pd
from loguru import logger

from config.settings import settings


class AkshareFetcher:
    """AkShare 数据抓取器"""

    def __init__(self, rate_limit: float = 1.0):
        self.rate_limit = rate_limit  # API 调用间隔（秒）
        self._last_call = 0.0

    def _throttle(self):
        """频率控制"""
        elapsed = time.time() - self._last_call
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_call = time.time()

    # ---- 股票列表 ----

    def fetch_all_stocks(self) -> pd.DataFrame:
        """
        获取全 A 股股票列表
        返回 DataFrame，包含 code, name 等字段
        """
        self._throttle()
        try:
            df = ak.stock_info_a_code_name()
            df = df.rename(columns={"code": "code", "name": "name"})
            logger.info(f"获取全 A 股列表: {len(df)} 只")
            return df
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return pd.DataFrame()

    # ---- 实时行情 ----

    def fetch_realtime_quotes(self) -> pd.DataFrame:
        """
        获取全市场实时行情快照（东方财富）
        返回 DataFrame，包含 code, latest, pct_change, volume, turnover_amount, turnover_rate
        """
        self._throttle()
        ts = datetime.now()
        try:
            df = ak.stock_zh_a_spot_em()
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
            logger.info(f"获取实时行情: {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取实时行情失败: {e}")
            return pd.DataFrame()

    # ---- 资金流 ----

    def fetch_fund_flow_rank(self) -> pd.DataFrame:
        """
        获取全市场个股资金流排名（东方财富）
        包含 超大单/大单/中单/小单 净流入
        """
        self._throttle()
        ts = datetime.now()
        try:
            df = ak.stock_individual_fund_flow_rank(indicator="今日")
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
                "主力净流入占比排名": "inflow_ratio_rank",
            })
            df["ts"] = ts
            df["source"] = "akshare"
            logger.info(f"获取资金流排名: {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取资金流排名失败: {e}")
            return pd.DataFrame()

    def fetch_individual_fund_flow(self, code: str, market: str = "sh") -> Optional[pd.DataFrame]:
        """
        获取单只股票历史资金流
        """
        self._throttle()
        try:
            symbol = self._to_akshare_symbol(code, market)
            df = ak.stock_individual_fund_flow(symbol=symbol, market=market)
            logger.debug(f"获取个股资金流: {code}")
            return df
        except Exception as e:
            logger.warning(f"获取个股资金流失败 {code}: {e}")
            return None

    # ---- 板块 ----

    def fetch_sector_quotes(self) -> pd.DataFrame:
        """获取行业板块行情"""
        self._throttle()
        try:
            df = ak.stock_board_industry_name_em()
            df = df.rename(columns={
                "板块名称": "sector_name",
                "涨跌幅": "pct_change",
                "主力净流入": "main_net_inflow",
            })
            logger.info(f"获取板块行情: {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取板块行情失败: {e}")
            return pd.DataFrame()

    # ---- 工具 ----

    @staticmethod
    def _to_akshare_symbol(code: str, market: str = "sh") -> str:
        """将股票代码转为 akshare 格式，如 '000001' -> '000001'"""
        return code

    def is_trading_time(self) -> bool:
        """简单判断是否在 A 股交易时段"""
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        morning_start = now.replace(hour=9, minute=30, second=0)
        morning_end = now.replace(hour=11, minute=30, second=0)
        afternoon_start = now.replace(hour=13, minute=0, second=0)
        afternoon_end = now.replace(hour=15, minute=0, second=0)
        return (morning_start <= now <= morning_end) or (afternoon_start <= now <= afternoon_end)


# 全局单例
fetcher = AkshareFetcher()
