"""
AI 分析模块
调用 LLM（OpenAI / Anthropic / llama.cpp）对异动标的做结构化 JSON 归因

输出格式:
{
  "summary": "一句话逻辑",
  "reason_type": "policy / restructuring / technical / industry / sentiment / unknown",
  "confidence_score": 0.0,
  "risk_points": ["..."],
  "evidence": ["..."],
  "action": "watch / review / ignore"
}
"""

import json
from typing import Optional

from loguru import logger

from config.settings import settings


# LLM 分析 Prompt 模板
ANALYSIS_SYSTEM_PROMPT = """你是一个A股机构资金分析专家。你会收到一只股票的异动信号数据，请分析：

1. 判断异动可能的原因（政策/重组/技术面/行业联动/情绪/未知）
2. 给出置信度评分（0.0-1.0）
3. 列出主要风险点
4. 给出操作建议（watch=加入观察/review=需要人工复核/ignore=低质量信号）

要求：仅输出 JSON，不要任何额外文字。"""

ANALYSIS_USER_TEMPLATE = """请分析以下异动信号：

股票代码: {code}
股票名称: {name}
异动类型: {alert_type}
触发原因: {trigger_reason}
涨幅: {pct_change}%
成交额: {turnover_amount}
主力净流入占比: {main_force_ratio}%
"""


class LLMClient:
    """LLM 客户端，支持 OpenAI / Anthropic / llama.cpp"""

    def __init__(self):
        self.provider = self._detect_provider()

    def _detect_provider(self) -> Optional[str]:
        """检测可用 LLM 提供商，优先级: llama > openai > anthropic"""
        if settings.llama_base_url:
            return "llama"
        if settings.openai_api_key:
            return "openai"
        if settings.anthropic_api_key:
            return "anthropic"
        return None

    def analyze(self, alert: dict) -> Optional[dict]:
        """
        对单个异动告警进行 AI 分析
        返回结构化 JSON dict，失败则返回 None
        """
        if not settings.ai_enabled:
            logger.debug("AI 未配置，跳过分析")
            return None

        try:
            if self.provider == "llama":
                return self._analyze_llama(alert)
            elif self.provider == "openai":
                return self._analyze_openai(alert)
            elif self.provider == "anthropic":
                return self._analyze_anthropic(alert)
        except Exception as e:
            logger.warning(f"AI 分析失败: {e}")
            return self._fallback_result(alert)

    # ---- llama.cpp (OpenAI 兼容 HTTP API) ----

    def _analyze_llama(self, alert: dict) -> dict:
        """
        llama.cpp 本地模型分析
        llama-server 提供 OpenAI 兼容的 /v1/chat/completions 端点
        """
        import openai

        client = openai.OpenAI(
            api_key=settings.llama_api_key,
            base_url=settings.llama_base_url,
        )
        user_msg = ANALYSIS_USER_TEMPLATE.format(
            code=alert.get("code", ""),
            name=alert.get("name", ""),
            alert_type=alert.get("alert_type", ""),
            trigger_reason=alert.get("trigger_reason", ""),
            pct_change=alert.get("pct_change", "N/A"),
            turnover_amount=alert.get("turnover_amount", "N/A"),
            main_force_ratio=alert.get("main_force_ratio", "N/A"),
        )
        resp = client.chat.completions.create(
            model=settings.llama_model or "local-model",
            messages=[
                {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
            max_tokens=500,
        )
        content = resp.choices[0].message.content
        logger.info(f"llama.cpp 分析完成, model={settings.llama_model}")
        return self._parse_response(content)

    # ---- OpenAI ----

    def _analyze_openai(self, alert: dict) -> dict:
        import openai

        client = openai.OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
        )
        user_msg = ANALYSIS_USER_TEMPLATE.format(
            code=alert.get("code", ""),
            name=alert.get("name", ""),
            alert_type=alert.get("alert_type", ""),
            trigger_reason=alert.get("trigger_reason", ""),
            pct_change=alert.get("pct_change", "N/A"),
            turnover_amount=alert.get("turnover_amount", "N/A"),
            main_force_ratio=alert.get("main_force_ratio", "N/A"),
        )
        resp = client.chat.completions.create(
            model=settings.openai_model or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
            max_tokens=500,
        )
        content = resp.choices[0].message.content
        return self._parse_response(content)

    # ---- Anthropic ----

    def _analyze_anthropic(self, alert: dict) -> dict:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        user_msg = ANALYSIS_USER_TEMPLATE.format(
            code=alert.get("code", ""),
            name=alert.get("name", ""),
            alert_type=alert.get("alert_type", ""),
            trigger_reason=alert.get("trigger_reason", ""),
            pct_change=alert.get("pct_change", "N/A"),
            turnover_amount=alert.get("turnover_amount", "N/A"),
            main_force_ratio=alert.get("main_force_ratio", "N/A"),
        )
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system=ANALYSIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        content = resp.content[0].text
        return self._parse_response(content)

    @staticmethod
    def _parse_response(content: str) -> dict:
        """解析 LLM 返回的 JSON"""
        try:
            # 尝试直接解析
            return json.loads(content)
        except json.JSONDecodeError:
            # 尝试提取 JSON 块
            try:
                start = content.index("{")
                end = content.rindex("}") + 1
                return json.loads(content[start:end])
            except (ValueError, json.JSONDecodeError):
                logger.warning(f"无法解析 AI 响应: {content[:200]}")
                return LLMClient._fallback_result({})

    @staticmethod
    def _fallback_result(alert: dict = None) -> dict:
        """AI 不可用时的降级输出"""
        return {
            "summary": alert.get("trigger_reason", "规则触发") if alert else "规则触发",
            "reason_type": "unknown",
            "confidence_score": alert.get("confidence_score", 0.5) if alert else 0.5,
            "risk_points": ["AI 分析不可用，仅依赖规则判断"],
            "evidence": ["规则引擎自动触发"],
            "action": "review",
        }

    def batch_analyze(self, alerts: list[dict]) -> list[dict]:
        """批量 AI 分析，带进度和节流"""
        import time

        results = []
        total = len(alerts)

        for i, alert in enumerate(alerts):
            code = alert.get("code", "?")
            a_type = alert.get("alert_type", "?")
            print(f"  [{i+1}/{total}] {code} {a_type} ...", end=" ", flush=True)

            # 节流: 至少间隔 0.5 秒
            if i > 0:
                time.sleep(0.5)

            analysis = self.analyze(alert)
            if analysis:
                alert["ai_summary"] = analysis.get("summary", "")
                alert["ai_evidence"] = analysis
                print(f"OK ({analysis.get('reason_type', analysis.get('reason', ''))})", flush=True)
            else:
                print("SKIP", flush=True)

            results.append(alert)

        return results


# 全局单例
llm_client = LLMClient()
