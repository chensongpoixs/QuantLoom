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


# LLM 分析 Prompt 模板 — Phase 6: Few-shot + 多步推理增强
ANALYSIS_SYSTEM_PROMPT = """你是一个A股机构资金分析专家，专注于识别主力资金异动信号的真实性与风险。

## 分析框架 (Chain-of-Thought)

请按以下步骤逐步推理，每一步都要有依据：

**第1步 — 资金面分析**: 主力净流入占比是否显著？成交额是否异常放大？是否有大单密集成交迹象？
**第2步 — 事件面分析**: 近期事件是否与该异动方向一致？事件对股价的驱动逻辑是否成立？
**第3步 — 技术面分析**: 当前股价处于相对高位还是低位？是否存在均线支撑/压力？RSI/MACD 是否配合？
**第4步 — 综合判断**: 资金面+事件面+技术面是否形成共振？信号可靠性如何？

## Few-shot 示例

### 示例 1 (高质量信号)
输入: 688981 中芯国际 breakout 涨幅+5.2% 成交额85亿 主力占比32% 事件:"先进制程突破获政策支持"
输出: {"summary":"先进制程政策利好驱动机构增配，资金面+事件面共振","reason_type":"政策驱动" ,"confidence_score":0.88,"risk_points":["短期涨幅较大存在技术回调风险","外部制裁不确定性"],"evidence":["主力净流入占比32%远超阈值20%","成交额85亿为近20日均值的2.3倍","政策事件:先进制程突破","MACD金叉+RSI65多头区间"],"action":"watch"}

### 示例 2 (中等质量信号)
输入: 600519 贵州茅台 accumulation 涨幅+1.8% 成交额32亿 主力占比12% 事件:"(no events)"
输出: {"summary":"底部连续3日资金净流入，但缺乏事件催化，属常规调仓行为","reason_type":"技术面","confidence_score":0.55,"risk_points":["无事件驱动","白酒行业整体处于调整期","主力参与度一般"],"evidence":["连续3日净流入","距250日低点仅8%","无近期催化事件"],"action":"review"}

### 示例 3 (低质量信号)
输入: 000001 平安银行 tail_chasing 涨幅+1.2% 成交额5亿 主力占比6% 事件:"(no events)"
输出: {"summary":"尾盘小幅资金流入，量能不足且无催化，可能为程序化交易尾盘再平衡","reason_type":"情绪","confidence_score":0.35,"risk_points":["量能不足","无事件支撑","银行板块无联动"],"evidence":["主力占比仅6%低于阈值10%","成交额5亿偏低","无对应事件"],"action":"ignore"}

## 输出要求

1. 判断异动原因（政策驱动/基本面变化/技术面反弹/行业联动/情绪驱动/机构调仓/游资炒作/未知）
2. 给出置信度评分（0.0-1.0）：资金+事件+技术共振 → 0.8+；单一维度 → 0.5-0.7；信号弱 → <0.5
3. 列出主要风险点（至少2条）
4. 给出操作建议（watch=加入观察/review=需要人工复核/ignore=低质量信号）
5. evidence 字段应列出支撑你判断的具体证据

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
{events_context}

历史分析参考:
{historical_context}

请按资金面→事件面→技术面→综合判断的顺序逐步分析。"""


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
            logger.debug("AI not configured, skipping analysis")
            return None

        try:
            if self.provider == "llama":
                return self._analyze_llama(alert, events_context)
            elif self.provider == "openai":
                return self._analyze_openai(alert, events_context)
            elif self.provider == "anthropic":
                return self._analyze_anthropic(alert, events_context)
        except Exception as e:
            logger.warning(f"AI analysis failed: {e}")
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
            events_context=events_context or "(no recent relevant events)",
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
                logger.warning(f"Cannot parse AI response: {content}")
                return LLMClient._fallback_result({})

    @staticmethod
    def _fallback_result(alert: dict = None) -> dict:
        """AI 不可用时的降级输出"""
        return {
            "summary": alert.get("trigger_reason", "Rule triggered") if alert else "Rule triggered",
            "reason_type": "unknown",
            "confidence_score": alert.get("confidence_score", 0.5) if alert else 0.5,
            "risk_points": ["AI analysis unavailable, relying on rule judgment only"],
            "evidence": ["Rule engine auto-triggered"],
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
            if ctx and ctx != "(no recent relevant events)":
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
