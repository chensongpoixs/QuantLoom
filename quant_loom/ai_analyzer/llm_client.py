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
import time
from typing import Optional

from loguru import logger

from config.settings import settings
from quant_loom.ops.retry import network_retry


# LLM 分析 Prompt 模板
ANALYSIS_SYSTEM_PROMPT = """你是一个A股机构资金分析专家。你会收到一只股票的异动信号数据及相关事件信息，请分析：

1. 判断异动可能的原因（政策/重组/技术面/行业联动/情绪/未知）。如果有近期事件数据，优先基于事件进行归因
2. 给出置信度评分（0.0-1.0）。有真实事件支撑的应当给更高分
3. 列出主要风险点
4. 给出操作建议（watch=加入观察/review=需要人工复核/ignore=低质量信号）
5. evidence 字段应列出支撑你判断的具体事件或数据

要求：仅输出 JSON，不要任何额外文字。"""

ANALYSIS_USER_TEMPLATE = """请分析以下异动信号：

股票代码: {code}
股票名称: {name}
异动类型: {alert_type}
触发原因: {trigger_reason}
涨幅: {pct_change}%
成交额: {turnover_amount}
主力净流入占比: {main_force_ratio}%

近期相关事件:
{events_context}"""


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

    def analyze(self, alert: dict, events_context: str = "") -> Optional[dict]:
        """
        对单个异动告警进行 AI 分析
        events_context: RAG 检索的事件上下文文本
        返回结构化 JSON dict，失败则返回 None
        """
        if not settings.ai_enabled:
            logger.debug("AI 未配置，跳过分析")
            return None

        try:
            if self.provider == "llama":
                return self._analyze_llama(alert, events_context)
            elif self.provider == "openai":
                return self._analyze_openai(alert, events_context)
            elif self.provider == "anthropic":
                return self._analyze_anthropic(alert, events_context)
        except Exception as e:
            logger.warning(f"AI 分析失败: {e}")
            return self._fallback_result(alert)

    @staticmethod
    def _build_user_msg(alert: dict, events_context: str = "") -> str:
        """构建用户分析 prompt，含事件上下文"""
        return ANALYSIS_USER_TEMPLATE.format(
            code=alert.get("code", ""),
            name=alert.get("name", ""),
            alert_type=alert.get("alert_type", ""),
            trigger_reason=alert.get("trigger_reason", ""),
            pct_change=alert.get("pct_change", "N/A"),
            turnover_amount=alert.get("turnover_amount", "N/A"),
            main_force_ratio=alert.get("main_force_ratio", "N/A"),
            events_context=events_context or "（无近期相关事件）",
        )

    # ================================================================
    # 结构化日志 (与 Go 服务 ai/client.go 对齐)
    # ================================================================

    @staticmethod
    def _log_request(method: str, url: str, req_headers: dict, req_body: dict) -> None:
        """记录完整 HTTP 请求信息 (参考 Go: ai/client.go:237 http request full)"""
        # 序列化请求体为 JSON 字符串 (紧凑格式)
        body_str = json.dumps(req_body, ensure_ascii=False)
        logger.info(
            "http request full",
            method=method,
            url=url,
            request_headers=req_headers,
            request_body=body_str,
        )

    @staticmethod
    def _log_response(status: int, resp_headers: dict, resp_body: str) -> None:
        """记录完整 HTTP 响应信息 (参考 Go: ai/client.go:254 http response full)"""
        logger.info(
            "http response full",
            status=status,
            response_headers=resp_headers,
            response_body=resp_body,
        )

    @staticmethod
    def _log_completion(elapsed: float, model: str, usage: dict,
                        assistant_content: str) -> None:
        """记录请求完成摘要 (参考 Go: ai/client.go:172 request ok)"""
        logger.info(
            "request ok",
            elapsed=f"{elapsed:.3f}s",
            model=model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            assistant_message_content_full=assistant_content,
        )

    # ---- llama.cpp (OpenAI 兼容 HTTP API) ----

    @network_retry
    def _analyze_llama(self, alert: dict, events_context: str = "") -> dict:
        """
        llama.cpp 本地模型分析
        llama-server 提供 OpenAI 兼容的 /v1/chat/completions 端点
        """
        import openai

        base_url = settings.llama_base_url
        model = settings.llama_model or "local-model"
        user_msg = self._build_user_msg(alert, events_context)

        messages = [
            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]
        req_body = {
            "model": model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 500,
        }

        # 记录请求
        api_url = f"{base_url}/chat/completions"
        self._log_request(
            method="POST",
            url=api_url,
            req_headers={
                "Authorization": [f"Bearer {settings.llama_api_key}"],
                "Content-Type": ["application/json"],
            },
            req_body=req_body,
        )

        t0 = time.time()
        client = openai.OpenAI(
            api_key=settings.llama_api_key,
            base_url=base_url,
        )
        resp = client.chat.completions.create(**{k: v for k, v in req_body.items()
                                                  if k != "model"},
                                              model=model)
        elapsed = time.time() - t0

        content = resp.choices[0].message.content

        # 记录响应体 (完整 JSON)
        resp_body = resp.model_dump_json() if hasattr(resp, "model_dump_json") else json.dumps(
            {"choices": [{"message": {"content": content}}]}, ensure_ascii=False
        )
        self._log_response(
            status=200,
            resp_headers={"Content-Type": ["application/json"]},
            resp_body=resp_body,
        )

        # 记录完成摘要
        usage = {
            "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0) if resp.usage else 0,
            "completion_tokens": getattr(resp.usage, "completion_tokens", 0) if resp.usage else 0,
            "total_tokens": getattr(resp.usage, "total_tokens", 0) if resp.usage else 0,
        }
        self._log_completion(elapsed, model, usage, content)

        return self._parse_response(content)

    # ---- OpenAI ----

    @network_retry
    def _analyze_openai(self, alert: dict, events_context: str = "") -> dict:
        import openai

        base_url = settings.openai_base_url or None
        model = settings.openai_model or "gpt-4o-mini"
        user_msg = self._build_user_msg(alert, events_context)

        messages = [
            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]
        req_body = {
            "model": model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 500,
        }

        api_url = f"{base_url}/chat/completions" if base_url else "https://api.openai.com/v1/chat/completions"
        self._log_request(
            method="POST",
            url=api_url,
            req_headers={
                "Authorization": [f"Bearer {settings.openai_api_key}"],
                "Content-Type": ["application/json"],
            },
            req_body=req_body,
        )

        t0 = time.time()
        client = openai.OpenAI(
            api_key=settings.openai_api_key,
            base_url=base_url,
        )
        resp = client.chat.completions.create(**{k: v for k, v in req_body.items()
                                                  if k != "model"},
                                              model=model)
        elapsed = time.time() - t0

        content = resp.choices[0].message.content

        resp_body = resp.model_dump_json() if hasattr(resp, "model_dump_json") else json.dumps(
            {"choices": [{"message": {"content": content}}]}, ensure_ascii=False
        )
        self._log_response(
            status=200,
            resp_headers={"Content-Type": ["application/json"]},
            resp_body=resp_body,
        )

        usage = {
            "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0) if resp.usage else 0,
            "completion_tokens": getattr(resp.usage, "completion_tokens", 0) if resp.usage else 0,
            "total_tokens": getattr(resp.usage, "total_tokens", 0) if resp.usage else 0,
        }
        self._log_completion(elapsed, model, usage, content)

        return self._parse_response(content)

    # ---- Anthropic ----

    @network_retry
    def _analyze_anthropic(self, alert: dict, events_context: str = "") -> dict:
        import anthropic

        model = settings.anthropic_model or "claude-sonnet-4-6"
        user_msg = self._build_user_msg(alert, events_context)

        req_body = {
            "model": model,
            "max_tokens": 500,
            "system": ANALYSIS_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_msg}],
        }

        self._log_request(
            method="POST",
            url="https://api.anthropic.com/v1/messages",
            req_headers={
                "x-api-key": [f"{settings.anthropic_api_key}"],
                "Content-Type": ["application/json"],
            },
            req_body=req_body,
        )

        t0 = time.time()
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        resp = client.messages.create(**{k: v for k, v in req_body.items()
                                          if k != "system"},
                                      system=ANALYSIS_SYSTEM_PROMPT)
        elapsed = time.time() - t0

        content = resp.content[0].text

        resp_body = resp.model_dump_json() if hasattr(resp, "model_dump_json") else json.dumps(
            {"content": [{"text": content}]}, ensure_ascii=False
        )
        self._log_response(
            status=200,
            resp_headers={"Content-Type": ["application/json"]},
            resp_body=resp_body,
        )

        usage = {
            "prompt_tokens": getattr(resp.usage, "input_tokens", 0) if resp.usage else 0,
            "completion_tokens": getattr(resp.usage, "output_tokens", 0) if resp.usage else 0,
            "total_tokens": (getattr(resp.usage, "input_tokens", 0) + getattr(resp.usage, "output_tokens", 0)) if resp.usage else 0,
        }
        self._log_completion(elapsed, model, usage, content)

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
                logger.warning(f"无法解析 AI 响应: {content}")
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

    def batch_analyze(self, alerts: list[dict],
                      events_contexts: dict[str, str] = None) -> list[dict]:
        """
        批量 AI 分析，带进度和节流
        events_contexts: {code: context_text} 每个股票的事件上下文
        """
        results = []
        total = len(alerts)
        contexts = events_contexts or {}

        for i, alert in enumerate(alerts):
            code = alert.get("code", "?")
            a_type = alert.get("alert_type", "?")
            ctx = contexts.get(code, "")

            # 上下文预览 (完整打印第一行)
            ctx_preview = ""
            if ctx and ctx != "（无近期相关事件）":
                first_line = ctx.split("\n")[0]
                ctx_preview = f" | event: {first_line}"

            logger.info(f"[{i+1}/{total}] analyzing {code} {a_type}{ctx_preview}")

            # 节流: 至少间隔 0.5 秒
            if i > 0:
                time.sleep(0.5)

            analysis = self.analyze(alert, events_context=ctx)
            if analysis:
                alert["ai_summary"] = analysis.get("summary", "")
                alert["ai_evidence"] = analysis
                logger.info(
                    f"[{i+1}/{total}] {code} OK "
                    f"({analysis.get('reason_type', analysis.get('reason', ''))})"
                )
            else:
                logger.warning(f"[{i+1}/{total}] {code} SKIP (AI analysis failed)")

            results.append(alert)

        return results


# 全局单例
llm_client = LLMClient()
