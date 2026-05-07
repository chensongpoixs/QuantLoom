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

"""事件抓取器测试"""
import pandas as pd
import pytest
from datetime import datetime
from quant_loom.data_ingestion.event_fetcher import EventFetcher


@pytest.fixture
def fetcher():
    return EventFetcher(rate_limit=0.0)


class TestNormalizeRow:
    def test_basic_normalization(self, fetcher):
        row = pd.Series({
            "title": "测试公告：重大资产重组",
            "content": "公司拟通过发行股份方式购买资产",
            "published_at": datetime(2026, 5, 7, 10, 0),
            "source": "eastmoney",
            "url": "http://example.com",
        })
        result = fetcher._normalize_row(row, "000001", "announcement")
        assert result["code"] == "000001"
        assert result["event_type"] == "announcement"
        assert result["title"] == "测试公告：重大资产重组"
        assert result["content"] == "公司拟通过发行股份方式购买资产"
        assert result["source"] == "eastmoney"
        assert result["url"] == "http://example.com"

    def test_title_truncation(self, fetcher):
        long_title = "A" * 600
        row = pd.Series({
            "title": long_title,
            "content": "",
            "published_at": datetime.now(),
            "source": "",
            "url": "",
        })
        result = fetcher._normalize_row(row, "000001", "news")
        assert len(result["title"]) == 500

    def test_content_truncation(self, fetcher):
        long_content = "B" * 2500
        row = pd.Series({
            "title": "test",
            "content": long_content,
            "published_at": datetime.now(),
            "source": "",
            "url": "",
        })
        result = fetcher._normalize_row(row, "000001", "news")
        assert len(result["content"]) == 2000

    def test_missing_published_at(self, fetcher):
        row = pd.Series({
            "title": "test",
            "content": "",
            "published_at": None,
            "source": "",
            "url": "",
        })
        result = fetcher._normalize_row(row, "000001", "news")
        assert result["published_at"] is not None

    def test_string_date_parsing(self, fetcher):
        row = pd.Series({
            "title": "test",
            "content": "",
            "published_at": "2026-05-07",
            "source": "",
            "url": "",
        })
        result = fetcher._normalize_row(row, "000001", "news")
        assert isinstance(result["published_at"], datetime)


class TestEmptyReturns:
    def test_fetch_stock_news_empty(self, fetcher):
        # 空/格式不对的代码应返回空 DataFrame
        df = fetcher.fetch_stock_news("invalid_code_xyz")
        assert isinstance(df, pd.DataFrame)

    def test_fetch_announcements_empty(self, fetcher):
        df = fetcher.fetch_announcements("invalid_code_xyz")
        assert isinstance(df, pd.DataFrame)

    def test_fetch_research_reports_empty(self, fetcher):
        df = fetcher.fetch_research_reports("invalid_code_xyz")
        assert isinstance(df, pd.DataFrame)


class TestIsTradingTime:
    def test_weekend(self, fetcher):
        # 这个方法简单测试不抛异常
        result = fetcher.is_trading_time()
        assert isinstance(result, bool)


class TestBatchFetch:
    def test_empty_codes(self, fetcher):
        result = fetcher.fetch_events_batch([])
        assert result == {}

    def test_invalid_codes(self, fetcher):
        result = fetcher.fetch_events_batch(["invalid"])
        assert isinstance(result, dict)
