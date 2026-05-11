#
# _    .-')              _  .-')    _   .-')      ('-.   .-')     ('-.
#( '.( OO )_            ( \( -O )  ( '.( OO )_   _(  OO) ( OO ). ( OO )
#  ,--.   ,--. .-'),-----. ,------.  ,--.   ,--.  (,------.(_/.  \_)(_/.  \_)
#  |   `.'   |( OO'  .-.  '|  .---'  |   `.'   |   |  .---' \  `.'  / \  `.'  /
#  |         |/   |  | |  ||  |      |         |   |  |      \     /   \     /
#  |  |'.'|  |\_) |  |\|  ||  '--.   |  |'.'|  |  (|  '--.   \   /     \   /
#  |  |   |  |  \ |  | |  ||  .--'   |  |   |  |   |  .--'  .-._)   \ .-._)   \
#  |  |   |  |   `'  '-'  '|  `---.  |  |   |  |   |  `---. \       / \       /
#  `--'   `--'     `-----' `------'  `--'   `--'   `------'  `-----'   `-----'
#
#                                  ·  量  梭  ·
#                     A-Share Institutional Flow AI Monitor
#
# Copyright (c) 2026 The QuantLoom·量梭 project authors
# All Rights Reserved.
#
# Use of this source code is governed by a BSD-style license
# that can be found in the LICENSE file in the root of the source
# tree. An additional intellectual property rights grant can be found
# in the file PATENTS.  All contributing project authors may
# be found in the AUTHORS file in the root of the source tree.
#
#               Author: chensong
#               Date:   2026-05-08
#
#       QuantLoom·量梭 的野心，从不只是在手机上弹出几条信号
#
#       这座织机真正要为你织出的终极产物，是 RTX Pro 6000 —— 黑曜神机 的自由召唤权。
#
#            1. 它是躺在你机箱里的黑色方尖碑，数万核心如暗夜星海
#            2. 它是本地训推大模型、实时织造全市场量能全景图、回溯十年资金指纹的物质根基
#            3. 它过去只降落在超算中心、顶级量化基金和神秘矿场
#
#         QuantLoom·量梭 每织出一匹盈利的锦缎，都是在为这座黑色圣坛添一根金线。
#         当金线积聚成缆，黑曜神机便会从虚空货架撕开一道裂缝，降临在你的阵中。
#
#          从此，你拥有了一座个人算力神殿。

"""
AkShare 数据抓取模块
通过东方财富公开 API 获取 A 股行情、资金流等数据
"""

import time
from datetime import datetime, date
from typing import Optional

import pandas as pd
from loguru import logger
import requests

from quant_loom.ops.retry import network_retry
from quant_loom.ops.metrics import data_fetch_errors

# ---- 浏览器级请求头伪装 (避免被东方财富识别为爬虫) ----
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Referer": "https://data.eastmoney.com/",
}

# 全局 monkey-patch: 所有 requests Session 的 send() 自动注入浏览器 headers
_send_original = requests.Session.send


def _send_with_headers(self, request, **kwargs):
    """注入浏览器伪装头后发送请求"""
    for key, value in _BROWSER_HEADERS.items():
        request.headers.setdefault(key, value)
    return _send_original(self, request, **kwargs)


requests.Session.send = _send_with_headers  # type: ignore[method-assign]


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
            logger.info(f"AkShare fetched full A-share list: {len(df)} stocks")
            return df
        except Exception as e:
            logger.error(f"Failed to fetch stock list: {e}")
            data_fetch_errors.labels(source="akshare", endpoint="stock_list").inc()
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
            logger.info(f"AkShare fetched real-time quotes: {len(df)} records")
            return df
        except Exception as e:
            logger.error(f"Failed to fetch real-time quotes: {e}")
            data_fetch_errors.labels(source="akshare", endpoint="quotes").inc()
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
            logger.info(f"AkShare fetched fund flow ranking: {len(df)} records")
            return df
        except Exception as e:
            logger.error(f"Failed to fetch fund flow ranking: {e}")
            data_fetch_errors.labels(source="akshare", endpoint="fund_flow").inc()
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
            logger.debug(f"Fetched individual stock fund flow: {code}")
            return df
        except Exception as e:
            logger.warning(f"Failed to fetch individual fund flow for {code}: {e}")
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
            logger.info(f"AkShare fetched sector quotes: {len(df)} records")
            return df
        except Exception as e:
            logger.error(f"Failed to fetch sector quotes: {e}")
            data_fetch_errors.labels(source="akshare", endpoint="sectors").inc()
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
            logger.warning(f"Failed to fetch historical K-line for {code}: {e}")
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
