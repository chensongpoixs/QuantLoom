"""
企业微信 / 飞书 Webhook 通知
"""

from typing import List, Optional

import requests
from loguru import logger

from config.settings import settings


class WebhookNotifier:
    """Webhook 通知器"""

    def __init__(self):
        self.wecom_url = settings.wecom_webhook_url
        self.feishu_url = settings.feishu_webhook_url

    def send_alert(self, alert: dict, channels: Optional[List[str]] = None) -> dict:
        """
        发送单条告警到指定渠道
        channels: ["wecom", "feishu"]
        """
        results = {}
        if channels is None:
            channels = []
            if self.wecom_url:
                channels.append("wecom")
            if self.feishu_url:
                channels.append("feishu")

        for ch in channels:
            if ch == "wecom" and self.wecom_url:
                results["wecom"] = self._send_wecom(alert)
            elif ch == "feishu" and self.feishu_url:
                results["feishu"] = self._send_feishu(alert)

        return results

    def _send_wecom(self, alert: dict) -> bool:
        """企业微信 Markdown 消息"""
        emoji_map = {"P1": "🔴", "P2": "🟡", "P3": "⚪"}
        emoji = emoji_map.get(alert.get("risk_level", "P3"), "⚪")

        content = (
            f"## {emoji} 机构异动告警\n"
            f"> **{alert.get('name', '')}** ({alert.get('code', '')})\n"
            f"> 类型: {alert.get('alert_type', '')}\n"
            f"> 原因: {alert.get('trigger_reason', '')}\n"
            f"> 置信度: {alert.get('confidence_score', 0):.2f}\n"
            f"> 风险: {alert.get('risk_level', 'P3')}\n"
        )
        if alert.get("ai_summary"):
            content += f"> AI: {alert['ai_summary']}\n"

        try:
            resp = requests.post(self.wecom_url, json={
                "msgtype": "markdown",
                "markdown": {"content": content},
            }, timeout=10)
            ok = resp.status_code == 200
            logger.debug(f"企业微信推送: {'成功' if ok else resp.text}")
            return ok
        except Exception as e:
            logger.error(f"企业微信推送失败: {e}")
            return False

    def _send_feishu(self, alert: dict) -> bool:
        """飞书富文本消息"""
        try:
            payload = {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {"tag": "plain_text", "content": f"机构异动: {alert.get('name', '')} {alert.get('code', '')}"},
                        "template": "red" if alert.get("risk_level") == "P1" else "yellow",
                    },
                    "elements": [
                        {"tag": "div", "text": {"tag": "lark_md", "content": f"**类型**: {alert.get('alert_type', '')}"}},
                        {"tag": "div", "text": {"tag": "lark_md", "content": f"**原因**: {alert.get('trigger_reason', '')}"}},
                        {"tag": "div", "text": {"tag": "lark_md", "content": f"**置信度**: {alert.get('confidence_score', 0):.2f}"}},
                        {"tag": "div", "text": {"tag": "lark_md", "content": f"**风险**: {alert.get('risk_level', 'P3')}"}},
                    ],
                },
            }
            resp = requests.post(self.feishu_url, json=payload, timeout=10)
            ok = resp.status_code == 200
            logger.debug(f"飞书推送: {'成功' if ok else resp.text}")
            return ok
        except Exception as e:
            logger.error(f"飞书推送失败: {e}")
            return False


# 全局单例
webhook_notifier = WebhookNotifier()
