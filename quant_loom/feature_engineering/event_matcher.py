"""
事件匹配模块
将新闻/公告/研报与异动信号进行关联匹配
使用 LLM-as-ranker 判断事件相关性
"""

import json
from datetime import datetime, timedelta
from typing import Optional

from loguru import logger

from config.settings import settings

# LLM 事件相关性排序 prompt
EVENT_RANKING_SYSTEM_PROMPT = """你是一个A股事件分析专家。你会收到一只股票的异动信号和最近的相关事件列表。
请判断每个事件与该异动的相关性，仅输出 JSON 数组。"""

EVENT_RANKING_USER_TEMPLATE = """异动信号:
- 股票代码: {code}
- 异动类型: {alert_type}
- 触发原因: {trigger_reason}
- 涨跌幅: {pct_change}%

最近事件:
{events_text}

请判断每个事件是否与该异动相关，输出 JSON 数组:
[{{"event_index": 1, "relevant": true/false, "score": 0.0-1.0, "reason": "一句话说明"}}]"""


class EventMatcher:
    """事件匹配器 — LLM-as-ranker 判断事件与异动的相关性"""

    def __init__(self, lookback_days: int = 3):
        self.lookback_days = lookback_days

    # ---- 快速预筛选 ----

    def _filter_by_time(self, events: list[dict]) -> list[dict]:
        """时间窗口预筛选: 仅保留最近 N 天的事件"""
        cutoff = datetime.now() - timedelta(days=self.lookback_days)
        return [e for e in events if e.get("published_at") and e["published_at"] >= cutoff]

    def _filter_by_keyword(self, code: str, alert_type: str,
                           events: list[dict]) -> list[dict]:
        """关键词预筛选: 事件标题/内容包含股票代码或异动相关关键词"""
        # 根据异动类型确定相关关键词
        type_keywords = {
            "breakout": ["突破", "放量", "增持", "买入", "业绩", "预增", "超预期"],
            "accumulation": ["回购", "增持", "底部", "低估", "分红"],
            "tail_chasing": ["尾盘", "抢筹", "拉升", "流入"],
            "event_driven": ["公告", "重组", "停牌", "复牌", "政策", "中标",
                             "合同", "合作", "投资", "收购", "定增"],
            "sector_linked": ["行业", "板块", "政策", "规划", "利好"],
        }
        keywords = type_keywords.get(alert_type, [])
        keywords.append(code)

        filtered = []
        for e in events:
            title = e.get("title", "")
            content = e.get("content", "")
            text = title + " " + content
            if any(kw in text for kw in keywords):
                filtered.append(e)
        return filtered

    # ---- LLM 精排 ----

    def _rank_by_llm(self, code: str, alert: dict,
                     events: list[dict]) -> list[dict]:
        """
        使用 LLM 对候选事件进行相关性排序
        仅在配置了 LLM 时生效，否则返回规则预筛选结果
        """
        if not settings.ai_enabled or len(events) <= 1:
            # 单事件或 AI 不可用时，给预筛选结果一个基础分
            for e in events:
                e["relevance_score"] = 0.5
            return events

        # 构建事件文本
        events_text_parts = []
        for i, e in enumerate(events):
            events_text_parts.append(
                f"{i+1}. [{e.get('event_type', '')}] {e.get('title', '')} "
                f"({e.get('published_at', '')})"
                f"\n   内容: {(e.get('content', '') or '')[:150]}"
            )
        events_text = "\n\n".join(events_text_parts)

        user_msg = EVENT_RANKING_USER_TEMPLATE.format(
            code=code,
            alert_type=alert.get("alert_type", ""),
            trigger_reason=alert.get("trigger_reason", ""),
            pct_change=alert.get("pct_change", "N/A"),
            events_text=events_text,
        )

        try:
            import openai

            if settings.llama_base_url:
                client = openai.OpenAI(
                    api_key=settings.llama_api_key,
                    base_url=settings.llama_base_url,
                )
                model = settings.llama_model or "local-model"
            elif settings.openai_api_key:
                client = openai.OpenAI(
                    api_key=settings.openai_api_key,
                    base_url=settings.openai_base_url or None,
                )
                model = settings.openai_model or "gpt-4o-mini"
            else:
                for e in events:
                    e["relevance_score"] = 0.5
                return events

            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": EVENT_RANKING_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.1,
                max_tokens=500,
            )
            content = resp.choices[0].message.content

            # 解析 LLM 返回的 JSON 评分
            rankings = self._parse_ranking_response(content, len(events))
            for i, e in enumerate(events):
                e["relevance_score"] = rankings.get(i, 0.5)
            logger.debug(f"LLM 事件排序完成: {code}, {len(events)} 个事件")

        except Exception as e:
            logger.warning(f"LLM 事件排序失败 {code}: {e}")
            for e in events:
                e["relevance_score"] = 0.5

        # 按相关性降序
        events.sort(key=lambda e: e.get("relevance_score", 0), reverse=True)
        return events

    @staticmethod
    def _parse_ranking_response(content: str, n_events: int) -> dict[int, float]:
        """解析 LLM 返回的排序 JSON"""
        scores = {}
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            try:
                start = content.index("[")
                end = content.rindex("]") + 1
                data = json.loads(content[start:end])
            except (ValueError, json.JSONDecodeError):
                return {i: 0.5 for i in range(n_events)}

        if isinstance(data, list):
            for item in data:
                idx = item.get("event_index", 0) - 1
                score = item.get("score", 0.5)
                if 0 <= idx < n_events:
                    scores[idx] = float(score)
        return scores

    # ---- 主入口 ----

    def match_events(self, code: str, alert: dict,
                     events: list[dict]) -> list[dict]:
        """
        为异动信号匹配相关事件
        1. 时间窗口预筛选
        2. 关键词预筛选
        3. LLM 精排
        返回: 排序后的事件列表 (含 relevance_score 字段)
        """
        if not events:
            return []

        alert_type = alert.get("alert_type", "")

        # 1. 时间筛选
        events = self._filter_by_time(events)
        if not events:
            return []

        # 2. 关键词筛选
        events = self._filter_by_keyword(code, alert_type, events)
        if not events:
            return []

        # 3. LLM 精排
        events = self._rank_by_llm(code, alert, events)

        return events

    def has_significant_event(self, code: str, events: list[dict],
                              min_relevance: float = 0.3) -> bool:
        """
        判断是否有足够相关的事件
        用于决定 check_event_driven 的 has_event 参数
        """
        if not events:
            return False
        best_score = max(
            (e.get("relevance_score", 0) for e in events), default=0
        )
        return best_score >= min_relevance
