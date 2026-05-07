"""事件匹配器测试"""
import pytest
from datetime import datetime, timedelta
from quant_loom.feature_engineering.event_matcher import EventMatcher


@pytest.fixture
def matcher():
    return EventMatcher(lookback_days=3)


@pytest.fixture
def sample_events():
    now = datetime.now()
    return [
        {
            "code": "000001",
            "event_type": "announcement",
            "title": "重大资产重组进展公告",
            "content": "公司拟通过发行股份方式购买标的资产",
            "published_at": now - timedelta(hours=2),
            "source": "eastmoney",
        },
        {
            "code": "000001",
            "event_type": "news",
            "title": "机构调研：Q1业绩超预期",
            "content": "多家机构调研公司，看好发展前景",
            "published_at": now - timedelta(hours=5),
            "source": "eastmoney",
        },
        {
            "code": "000001",
            "event_type": "news",
            "title": "公司获得高新技术企业认定",
            "content": "获得税收优惠资格",
            "published_at": now - timedelta(days=10),
            "source": "cls",
        },
    ]


class TestFilterByTime:
    def test_keeps_recent_events(self, matcher, sample_events):
        filtered = matcher._filter_by_time(sample_events)
        # 前2条在 3 天内，第3条是10天前
        assert len(filtered) == 2

    def test_empty_input(self, matcher):
        assert matcher._filter_by_time([]) == []


class TestFilterByKeyword:
    def test_event_driven_keywords(self, matcher):
        events = [
            {"title": "重大资产重组进展公告", "content": "购买资产", "published_at": datetime.now()},
            {"title": "日常经营信息", "content": "例行事务处理", "published_at": datetime.now()},
            {"title": "关于中标的公告", "content": "中标重大项目", "published_at": datetime.now()},
        ]
        filtered = matcher._filter_by_keyword("000001", "event_driven", events)
        assert len(filtered) == 2  # 重组 + 中标

    def test_empty_input(self, matcher):
        assert matcher._filter_by_keyword("000001", "event_driven", []) == []

    def test_code_in_keyword(self, matcher):
        events = [
            {"title": "000001 最新公告", "content": "", "published_at": datetime.now()},
        ]
        filtered = matcher._filter_by_keyword("000001", "unknown", events)
        assert len(filtered) == 1


class TestHasSignificantEvent:
    def test_no_events(self, matcher):
        assert matcher.has_significant_event("000001", []) is False

    def test_low_score_events(self, matcher):
        events = [{"relevance_score": 0.1}, {"relevance_score": 0.2}]
        assert matcher.has_significant_event("000001", events, min_relevance=0.3) is False

    def test_high_score_event(self, matcher):
        events = [{"relevance_score": 0.1}, {"relevance_score": 0.7}]
        assert matcher.has_significant_event("000001", events) is True

    def test_default_threshold(self, matcher):
        events = [{"relevance_score": 0.3}]
        assert matcher.has_significant_event("000001", events) is True


class TestParseRankingResponse:
    def test_valid_json(self, matcher):
        content = '[{"event_index": 1, "relevant": true, "score": 0.9}, {"event_index": 2, "relevant": false, "score": 0.1}]'
        scores = matcher._parse_ranking_response(content, 3)
        assert scores[0] == 0.9
        assert scores[1] == 0.1

    def test_invalid_json(self, matcher):
        content = "not json at all"
        scores = matcher._parse_ranking_response(content, 2)
        assert scores == {0: 0.5, 1: 0.5}

    def test_json_with_markdown(self, matcher):
        content = '```json\n[{"event_index": 1, "score": 0.8}]\n```'
        scores = matcher._parse_ranking_response(content, 2)
        assert scores[0] == 0.8
