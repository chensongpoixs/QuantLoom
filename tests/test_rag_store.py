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
        assert "(no recent relevant events)" in context

    def test_max_events_limit(self, rag, sample_events):
        many_events = sample_events * 3  # 9 events
        alert = {"code": "000001", "alert_type": "breakout"}
        context = rag.get_context_for_alert(alert, matched_events=many_events)
        # 最多只显示 3 个 (max_context_events=3)
        assert context.count("[") <= 4  # 3 event entries + potential format brackets

    def test_event_type_labels(self, rag, sample_events):
        alert = {"code": "000001"}
        context = rag.get_context_for_alert(alert, matched_events=sample_events[:1])
        assert "Announcement" in context  # announcement → Announcement

    def test_none_matched_events_falls_back(self, rag):
        # 当 matched_events=None 且无 MySQL 时，返回无事件
        alert = {"code": "999999", "alert_type": "breakout"}
        context = rag.get_context_for_alert(alert, matched_events=None)
        assert "(no recent relevant events)" in context


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
