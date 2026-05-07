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
