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
                logger.debug(f"事件写入跳过 (可能重复): {e.get('title', '')} - {ex}")

        if saved > 0:
            logger.info(f"RAGStore 写入事件: {saved} 条")
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
            logger.debug(f"事件去重: {len(events)} -> {len(unique)} (跳过 {skipped} 条重复)")

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
            logger.warning(f"事件查询失败 {code}: {e}")
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
            return "（无近期相关事件）"

        parts = []
        total_chars = 0
        for i, e in enumerate(events):
            event_type_label = {
                "news": "新闻", "announcement": "公告",
                "report": "研报",
            }.get(e.get("event_type", ""), "事件")

            pub_str = ""
            pub = e.get("published_at")
            if pub:
                if hasattr(pub, "strftime"):
                    pub_str = pub.strftime("%Y-%m-%d")
                else:
                    pub_str = str(pub)[:10]

            entry = (
                f"[{i+1}] {event_type_label} | {pub_str} | {e.get('title', '')}\n"
                f"    内容摘要: {(e.get('content', '') or '')[:200]}"
            )
            total_chars += len(entry)
            if total_chars > self.max_content_chars:
                break
            parts.append(entry)

        return "\n\n".join(parts)
