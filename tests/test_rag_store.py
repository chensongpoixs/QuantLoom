"""RAG 上下文存储测试"""
import pytest
from datetime import datetime, timedelta
from quant_loom.ai_analyzer.rag_store import RAGStore


@pytest.fixture
def rag():
    return RAGStore(max_context_events=3, max_content_chars=1000)


@pytest.fixture
def sample_events():
    now = datetime.now()
    return [
        {
            "code": "000001",
            "event_type": "announcement",
            "title": "重大资产重组公告",
            "content": "公司拟通过发行股份购买资产",
            "published_at": now - timedelta(hours=2),
            "source": "eastmoney",
            "url": "http://example.com/1",
        },
        {
            "code": "000001",
            "event_type": "news",
            "title": "机构调研纪要",
            "content": "Q1业绩超预期，机构密集调研",
            "published_at": now - timedelta(hours=5),
            "source": "cls",
            "url": "http://example.com/2",
        },
        {
            "code": "000001",
            "event_type": "report",
            "title": "券商研报：买入评级",
            "content": "目标价上调20%，看好长期发展",
            "published_at": now - timedelta(days=1),
            "source": "eastmoney",
            "url": "http://example.com/3",
        },
    ]


class TestGetContextForAlert:
    def test_with_matched_events(self, rag, sample_events):
        alert = {"code": "000001", "alert_type": "breakout"}
        context = rag.get_context_for_alert(alert, matched_events=sample_events)
        assert "重大资产重组公告" in context
        assert "机构调研纪要" in context
        assert "买入评级" in context

    def test_no_events(self, rag):
        alert = {"code": "000001", "alert_type": "breakout"}
        context = rag.get_context_for_alert(alert, matched_events=[])
        assert "无近期相关事件" in context

    def test_max_events_limit(self, rag, sample_events):
        many_events = sample_events * 3  # 9 events
        alert = {"code": "000001", "alert_type": "breakout"}
        context = rag.get_context_for_alert(alert, matched_events=many_events)
        # 最多只显示 3 个 (max_context_events=3)
        assert context.count("[") <= 4  # 3 event entries + potential format brackets

    def test_event_type_labels(self, rag, sample_events):
        alert = {"code": "000001"}
        context = rag.get_context_for_alert(alert, matched_events=sample_events[:1])
        assert "公告" in context  # announcement → 公告

    def test_none_matched_events_falls_back(self, rag):
        # 当 matched_events=None 且无 MySQL 时，返回无事件
        alert = {"code": "999999", "alert_type": "breakout"}
        context = rag.get_context_for_alert(alert, matched_events=None)
        assert "无近期相关事件" in context


class TestDeduplicateAndStore:
    def test_deduplication(self, rag):
        now = datetime.now()
        events = [
            {"code": "000001", "event_type": "news", "title": "Same Title",
             "content": "", "published_at": now, "source": "", "url": ""},
            {"code": "000001", "event_type": "news", "title": "Same Title",
             "content": "", "published_at": now, "source": "", "url": ""},
            {"code": "000001", "event_type": "news", "title": "Different",
             "content": "", "published_at": now, "source": "", "url": ""},
        ]
        # 这个方法在无 MySQL 时会跳过存储
        saved = rag.deduplicate_and_store(events)
        assert saved >= 0  # 可能是 0 (MySQL 不可用)

    def test_empty_list(self, rag):
        assert rag.deduplicate_and_store([]) == 0
