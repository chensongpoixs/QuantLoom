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
事件数据抓取模块
通过 AkShare 获取 A 股新闻、公告、研报数据
"""

import time
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from loguru import logger

from quant_loom.ops.retry import network_retry


class EventFetcher:
    """AkShare 事件数据抓取器 — 新闻/公告/研报"""

    def __init__(self, rate_limit: float = 1.5):
        self.rate_limit = rate_limit
        self._last_call = 0.0

    @property
    def enabled(self) -> bool:
        return True

    def _throttle(self):
        elapsed = time.time() - self._last_call
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_call = time.time()

    # ---- 个股新闻 ----

    def fetch_stock_news(self, code: str) -> pd.DataFrame:
        """
        获取个股新闻 (东方财富)
        返回列: code, title, content, public_time, url
        """
        try:
            import akshare as ak

            @network_retry
            def _do_call():
                self._throttle()
                return ak.stock_news_em(symbol=code)

            df = _do_call()
            if df is None or df.empty:
                return pd.DataFrame()
            df = df.rename(columns={
                "public_time": "published_at",
            })
            df["code"] = code
            df["event_type"] = "news"
            df["source"] = "eastmoney"
            logger.debug(f"Fetched stock news: {code} ({len(df)} items)")
            return df
        except Exception as e:
            logger.warning(f"Failed to fetch stock news for {code}: {e}")
            return pd.DataFrame()

    # ---- 上市公司公告 ----

    def fetch_announcements(self, code: str) -> pd.DataFrame:
        """
        获取上市公司公告 (东方财富)
        返回列: 公告日期, 公告标题, 公告内容, 公告链接等
        """
        try:
            import akshare as ak

            @network_retry
            def _do_call():
                self._throttle()
                return ak.stock_notice_report(symbol=code)

            df = _do_call()
            if df is None or df.empty:
                return pd.DataFrame()
            # 标准化列名 — AkShare 返回的列名可能因版本而异
            col_map = {}
            for col in df.columns:
                if "日期" in col or "时间" in col:
                    col_map[col] = "published_at"
                elif "标题" in col:
                    col_map[col] = "title"
                elif "内容" in col:
                    col_map[col] = "content"
                elif "链接" in col or "url" in col:
                    col_map[col] = "url"
            if col_map:
                df = df.rename(columns=col_map)
            else:
                # fallback: 尝试按位置映射
                cols = list(df.columns)
                rename = {}
                if len(cols) >= 1:
                    rename[cols[0]] = "published_at"
                if len(cols) >= 2:
                    rename[cols[1]] = "title"
                df = df.rename(columns=rename)
            df["code"] = code
            df["event_type"] = "announcement"
            df["source"] = "eastmoney"
            if "content" not in df.columns:
                df["content"] = ""
            if "url" not in df.columns:
                df["url"] = ""
            logger.debug(f"Fetched announcements: {code} ({len(df)} items)")
            return df
        except Exception as e:
            logger.warning(f"Failed to fetch announcements for {code}: {e}")
            return pd.DataFrame()

    # ---- 个股研报 ----

    def fetch_research_reports(self, code: str) -> pd.DataFrame:
        """
        获取个股研报 (东方财富)
        返回列: 研报标题, 机构名称, 评级, 研究员, 日期, 盈利预测等
        """
        try:
            import akshare as ak

            @network_retry
            def _do_call():
                self._throttle()
                return ak.stock_research_report_em(symbol=code)

            df = _do_call()
            if df is None or df.empty:
                return pd.DataFrame()
            # 标准化列名
            col_map = {}
            for col in df.columns:
                if "日期" in col or "时间" in col:
                    col_map[col] = "published_at"
                elif "标题" in col:
                    col_map[col] = "title"
                elif "机构" in col:
                    col_map[col] = "org_name"
                elif "评级" in col:
                    col_map[col] = "rating"
                elif "研究员" in col:
                    col_map[col] = "researcher"
            if col_map:
                df = df.rename(columns=col_map)
            if "title" not in df.columns:
                cols = list(df.columns)
                if len(cols) >= 1:
                    df = df.rename(columns={cols[0]: "title"})
            df["code"] = code
            df["event_type"] = "report"
            df["source"] = "eastmoney"
            # 构建内容摘要
            if "org_name" in df.columns and "rating" in df.columns:
                df["content"] = df.apply(
                    lambda r: f"{r.get('org_name', '')} | 评级: {r.get('rating', '')} | 研究员: {r.get('researcher', '')}",
                    axis=1,
                )
            elif "content" not in df.columns:
                df["content"] = ""
            if "url" not in df.columns:
                df["url"] = ""
            logger.debug(f"Fetched research reports: {code} ({len(df)} items)")
            return df
        except Exception as e:
            logger.warning(f"Failed to fetch research reports for {code}: {e}")
            return pd.DataFrame()

    # ---- 全球财经快讯 ----

    def fetch_global_news(self) -> pd.DataFrame:
        """
        获取全球财经快讯 (财联社电报)
        返回最近 4 小时的资讯
        """
        try:
            import akshare as ak

            @network_retry
            def _do_call():
                self._throttle()
                return ak.stock_info_global_cls()

            df = _do_call()
            if df is None or df.empty:
                return pd.DataFrame()
            df["event_type"] = "news"
            df["source"] = "cls"
            df["code"] = ""  # 宏观新闻不关联个股
            if "title" not in df.columns and "content" in df.columns:
                df["title"] = df["content"].str[:80]
            if "content" not in df.columns:
                df["content"] = ""
            if "url" not in df.columns:
                df["url"] = ""
            if "published_at" not in df.columns:
                df["published_at"] = datetime.now()
            logger.info(f"Fetched global news: {len(df)} items")
            return df
        except Exception as e:
            logger.warning(f"Failed to fetch global news: {e}")
            return pd.DataFrame()

    # ---- 聚合接口 ----

    def _normalize_row(self, row: pd.Series, code: str, event_type: str) -> dict:
        """将 DataFrame 行标准化为统一 dict"""
        import datetime as dt
        pub = row.get("published_at")
        if pub is None:
            pub = dt.datetime.now()
        elif isinstance(pub, str):
            try:
                pub = pd.to_datetime(pub).to_pydatetime()
            except Exception:
                pub = dt.datetime.now()
        elif hasattr(pub, "to_pydatetime"):
            pub = pub.to_pydatetime()
        # 统一为 datetime.datetime (pd.to_datetime 对纯日期字符串可能返回 date)
        if isinstance(pub, dt.date) and not isinstance(pub, dt.datetime):
            pub = dt.datetime.combine(pub, dt.time.min)

        return {
            "code": code or str(row.get("code", "")),
            "event_type": event_type,
            "title": str(row.get("title", "") or "")[:500],
            "content": str(row.get("content", "") or "")[:2000],
            "source": str(row.get("source", "") or ""),
            "url": str(row.get("url", "") or ""),
            "published_at": pub,
        }

    def fetch_events_for_stock(self, code: str) -> list[dict]:
        """
        聚合单只股票的所有事件: 新闻 + 公告 + 研报
        返回标准化 dict 列表
        """
        events = []

        # 新闻
        news_df = self.fetch_stock_news(code)
        if not news_df.empty:
            for _, row in news_df.iterrows():
                events.append(self._normalize_row(row, code, "news"))

        # 公告
        ann_df = self.fetch_announcements(code)
        if not ann_df.empty:
            for _, row in ann_df.iterrows():
                events.append(self._normalize_row(row, code, "announcement"))

        # 研报
        report_df = self.fetch_research_reports(code)
        if not report_df.empty:
            for _, row in report_df.iterrows():
                events.append(self._normalize_row(row, code, "report"))

        # 按发布时间降序
        events.sort(key=lambda e: e["published_at"], reverse=True)
        logger.debug(f"Aggregated events for {code}: {len(events)} items (news/announcements/reports)")
        return events

    def fetch_events_batch(self, codes: list[str]) -> dict[str, list[dict]]:
        """
        批量获取多只股票事件
        返回 {code: [events]}
        """
        result = {}
        total = len(codes)
        for i, code in enumerate(codes):
            logger.info(f"  [{i+1}/{total}] Fetching events: {code}")
            events = self.fetch_events_for_stock(code)
            if events:
                result[code] = events
        logger.info(f"Batch event fetch complete: {len(result)}/{total} stocks have event data")
        return result

    def is_trading_time(self) -> bool:
        """判断是否在 A 股交易时段"""
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        mt = now.replace(hour=9, minute=30, second=0)
        me = now.replace(hour=11, minute=30, second=0)
        at = now.replace(hour=13, minute=0, second=0)
        ae = now.replace(hour=15, minute=0, second=0)
        return (mt <= now <= me) or (at <= now <= ae)
