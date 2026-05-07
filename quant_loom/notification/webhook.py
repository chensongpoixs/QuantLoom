"""
企业微信 / 飞书 / 钉钉 Webhook 通知
含 NotificationLog 写入
"""

from datetime import datetime
from typing import List, Optional

import requests
from loguru import logger

from config.settings import settings
from quant_loom.ops.retry import network_retry


class WebhookNotifier:
    """Webhook 通知器 — WeCom / Feishu / DingTalk"""

    def __init__(self):
        self.wecom_url = settings.wecom_webhook_url
        self.feishu_url = settings.feishu_webhook_url
        self.dingtalk_url = settings.dingtalk_webhook_url

    def send_alert(self, alert: dict, channels: Optional[List[str]] = None) -> dict:
        """
        发送单条告警到指定渠道，并写入 NotificationLog
        channels: ["wecom", "feishu", "dingtalk"]
        """
        results = {}
        if channels is None:
            channels = []
            if self.wecom_url:
                channels.append("wecom")
            if self.feishu_url:
                channels.append("feishu")
            if self.dingtalk_url:
                channels.append("dingtalk")

        for ch in channels:
            if ch == "wecom" and self.wecom_url:
                ok = self._send_wecom(alert)
                results["wecom"] = ok
                self._log_notification(alert, "wecom", ok)
            elif ch == "feishu" and self.feishu_url:
                ok = self._send_feishu(alert)
                results["feishu"] = ok
                self._log_notification(alert, "feishu", ok)
            elif ch == "dingtalk" and self.dingtalk_url:
                ok = self._send_dingtalk(alert)
                results["dingtalk"] = ok
                self._log_notification(alert, "dingtalk", ok)

        return results

    # ---- 企业微信 ----

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

        @network_retry
        def _do_post():
            resp = requests.post(self.wecom_url, json={
                "msgtype": "markdown",
                "markdown": {"content": content},
            }, timeout=10)
            return resp.status_code == 200, resp.text

        try:
            ok, txt = _do_post()
            if not ok:
                logger.warning(f"企业微信推送非 200: {txt}")
            else:
                logger.debug("企业微信推送: 成功")
            return ok
        except Exception as e:
            logger.error(f"企业微信推送失败 (重试耗尽): {e}")
            return False

    # ---- 飞书 ----

    def _send_feishu(self, alert: dict) -> bool:
        """飞书富文本消息"""
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

        @network_retry
        def _do_post():
            resp = requests.post(self.feishu_url, json=payload, timeout=10)
            return resp.status_code == 200, resp.text

        try:
            ok, txt = _do_post()
            if not ok:
                logger.warning(f"飞书推送非 200: {txt}")
            else:
                logger.debug("飞书推送: 成功")
            return ok
        except Exception as e:
            logger.error(f"飞书推送失败 (重试耗尽): {e}")
            return False

    # ---- 钉钉 ----

    def _send_dingtalk(self, alert: dict) -> bool:
        """钉钉 Markdown 消息 (支持 @所有人 仅 P1)"""
        emoji_map = {"P1": "🔴", "P2": "🟡", "P3": "⚪"}
        emoji = emoji_map.get(alert.get("risk_level", "P3"), "⚪")

        title = f"{emoji} 机构异动告警"
        text = (
            f"# {title}\n\n"
            f"- **股票**: {alert.get('name', '')} ({alert.get('code', '')})\n"
            f"- **类型**: {alert.get('alert_type', '')}\n"
            f"- **原因**: {alert.get('trigger_reason', '')}\n"
            f"- **置信度**: {alert.get('confidence_score', 0):.2f}\n"
            f"- **风险等级**: {alert.get('risk_level', 'P3')}\n"
        )
        if alert.get("ai_summary"):
            text += f"- **AI 分析**: {alert['ai_summary']}\n"

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": text,
            },
        }
        # P1 告警 @所有人
        if alert.get("risk_level") == "P1":
            payload["markdown"]["text"] += "\n@所有人"
            payload["at"] = {"isAtAll": True}

        @network_retry
        def _do_post():
            resp = requests.post(self.dingtalk_url, json=payload, timeout=10)
            return resp.status_code == 200, resp.text

        try:
            ok, txt = _do_post()
            if not ok:
                logger.warning(f"钉钉推送非 200: {txt}")
            else:
                logger.debug("钉钉推送: 成功")
            return ok
        except Exception as e:
            logger.error(f"钉钉推送失败 (重试耗尽): {e}")
            return False

    # ---- NotificationLog ----

    @staticmethod
    def _log_notification(alert: dict, channel: str, success: bool):
        """写入 sq_notification_log，失败不阻塞管线"""
        try:
            from quant_loom.storage.mysql_client import mysql_client
            from quant_loom.storage.models import NotificationLog

            if not mysql_client.ping():
                return

            alert_id = alert.get("db_id")
            recipient = ""
            if channel == "wecom":
                recipient = settings.wecom_webhook_url
            elif channel == "feishu":
                recipient = settings.feishu_webhook_url
            elif channel == "dingtalk":
                recipient = settings.dingtalk_webhook_url

            log = NotificationLog(
                alert_id=alert_id,
                channel=channel,
                recipient=recipient[:100],
                status="success" if success else "failed",
                sent_at=datetime.now(),
            )
            mysql_client.insert_or_update(log)
        except Exception:
            pass  # 通知日志写入失败不影响主流程


# 全局单例
webhook_notifier = WebhookNotifier()
