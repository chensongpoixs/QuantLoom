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
RAG 上下文存储模块
将新闻/公告/研报事件存储到 MySQL，并为 LLM 分析检索上下文
零外部依赖 — 使用 MySQL + LLM-as-ranker
"""

from datetime import datetime, timedelta
from typing import Optional

from loguru import logger

from quant_loom.storage.mysql_client import mysql_client
from quant_loom.storage.models import StockEvent


class RAGStore:
    """事件存储与上下文检索"""

    def __init__(self, max_context_events: int = 5, max_content_chars: int = 2000):
        self.max_context_events = max_context_events
        self.max_content_chars = max_content_chars

    # ---- 事件存储 ----

    def store_events(self, events: list[dict]) -> int:
        """
        批量存储事件到 MySQL
        返回: 成功写入的数量
        """
        if not events or not mysql_client.ping():
            return 0

        saved = 0
        for e in events:
            try:
                record = StockEvent(
                    code=e.get("code", ""),
                    event_type=e.get("event_type", ""),
                    title=e.get("title", ""),
                    content=e.get("content", ""),
                    source=e.get("source", ""),
                    url=e.get("url", ""),
                    published_at=e.get("published_at", datetime.now()),
                    sentiment_score=e.get("sentiment_score"),
                )
                mysql_client.insert_or_update(record)
                saved += 1
            except Exception as ex:
                logger.debug(f"Event write skipped (possible duplicate): {e.get('title', '')} - {ex}")

        if saved > 0:
            logger.info(f"RAGStore wrote events: {saved}")
        return saved

    def deduplicate_and_store(self, events: list[dict]) -> int:
        """
        去重后存储
        按 (code, title, published_at) 逻辑去重
        """
        if not events:
            return 0

        seen = set()
        unique = []
        for e in events:
            key = (
                e.get("code", ""),
                e.get("title", "")[:100],
                str(e.get("published_at", "")),
            )
            if key not in seen:
                seen.add(key)
                unique.append(e)

        skipped = len(events) - len(unique)
        if skipped > 0:
            logger.debug(f"Event dedup: {len(events)} -> {len(unique)} (skipped {skipped} duplicates)")

        return self.store_events(unique)

    # ---- 事件检索 ----

    def get_events_for_stock(self, code: str, days: int = 3) -> list[dict]:
        """
        从 MySQL 获取某只股票最近 N 天的事件
        返回: 事件 dict 列表，按发布时间降序
        """
        if not mysql_client.ping():
            return []

        cutoff = datetime.now() - timedelta(days=days)
        try:
            with mysql_client.get_session() as sess:
                from sqlalchemy import desc
                rows = (
                    sess.query(StockEvent)
                    .filter(
                        StockEvent.code == code,
                        StockEvent.published_at >= cutoff,
                    )
                    .order_by(desc(StockEvent.published_at))
                    .limit(20)
                    .all()
                )
                return [
                    {
                        "code": r.code,
                        "event_type": r.event_type,
                        "title": r.title,
                        "content": r.content or "",
                        "source": r.source,
                        "url": r.url,
                        "published_at": r.published_at,
                        "sentiment_score": r.sentiment_score,
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.warning(f"Event query failed {code}: {e}")
            return []

    # ---- 上下文构建 ----

    def get_context_for_alert(self, alert: dict,
                              matched_events: list[dict] = None) -> str:
        """
        为异动告警构建 LLM prompt 事件上下文文本
        优先级: matched_events (已排序) > 从 MySQL 按 code 检索
        """
        if matched_events:
            events = matched_events[: self.max_context_events]
        else:
            code = alert.get("code", "")
            events = self.get_events_for_stock(code)[: self.max_context_events]

        if not events:
            return "(no recent relevant events)"

        parts = []
        total_chars = 0
        for i, e in enumerate(events):
            event_type_label = {
                "news": "News", "announcement": "Announcement",
                "report": "Research Report",
            }.get(e.get("event_type", ""), "Event")

            pub_str = ""
            pub = e.get("published_at")
            if pub:
                if hasattr(pub, "strftime"):
                    pub_str = pub.strftime("%Y-%m-%d")
                else:
                    pub_str = str(pub)[:10]

            entry = (
                f"[{i+1}] {event_type_label} | {pub_str} | {e.get('title', '')}\n"
                f"    Summary: {(e.get('content', '') or '')[:200]}"
            )
            total_chars += len(entry)
            if total_chars > self.max_content_chars:
                break
            parts.append(entry)

        return "\n\n".join(parts)
