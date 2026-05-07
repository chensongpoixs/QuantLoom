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
