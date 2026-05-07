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
邮件通知模块
发送 HTML 格式的异动告警日报
"""

import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional

from loguru import logger

from config.settings import settings
from quant_loom.ops.retry import network_retry


_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>
  body {{ font-family: Arial, sans-serif; }}
  h2 {{ color: #333; }}
  table {{ border-collapse: collapse; width: 100%%; }}
  th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
  th {{ background-color: #f5f5f5; }}
  .P1 {{ color: #d32f2f; font-weight: bold; }}
  .P2 {{ color: #f57c00; }}
  .P3 {{ color: #888; }}
  .footer {{ margin-top: 20px; color: #999; font-size: 12px; }}
</style></head>
<body>
<h2>QuantLoom·量梭 Daily Flow Alert Report</h2>
<p>Generated at: {report_time}</p>
<p>Total alerts today: <strong>{total_alerts}</strong> (P1: {p1_count}, P2: {p2_count}, P3: {p3_count})</p>

<h3>Top Alert Stocks</h3>
<table>
<tr><th>Stock</th><th>Type</th><th>Trigger Reason</th><th>Confidence</th><th>Risk</th></tr>
{table_rows}
</table>

<h3>Risk Disclaimer</h3>
<p>This report is for research reference only and does not constitute investment advice. All signals are generated automatically from public data and rule engine, and may contain false positives or delays.</p>

<div class="footer">
<p>QuantLoom·量梭 · Disclaimer: System output is for research reference only</p>
</div>
</body>
</html>"""


class EmailSender:
    """邮件发送器"""

    def __init__(self):
        self.host = settings.smtp_host
        self.port = settings.smtp_port
        self.user = settings.smtp_user
        self.password = settings.smtp_password
        self.from_addr = settings.smtp_from
        self.to_addr = settings.alert_email_to

    @property
    def enabled(self) -> bool:
        return bool(self.host and self.user and self.password)

    @network_retry
    def _smtp_send(self, msg: MIMEMultipart) -> None:
        """
        实际 SMTP 发送 (带重试)
        根据端口选择连接方式: 465 → SMTP_SSL, 587 → SMTP + STARTTLS
        """
        if self.port == 465:
            # SMTPS — 从连接开始即 SSL 加密
            with smtplib.SMTP_SSL(self.host, self.port, timeout=10) as s:
                s.login(self.user, self.password)
                s.send_message(msg)
        else:
            # SMTP + STARTTLS (port 587 或其他)
            with smtplib.SMTP(self.host, self.port, timeout=10) as s:
                s.starttls()
                s.login(self.user, self.password)
                s.send_message(msg)

    def send_daily_report(self, alerts: List[dict]) -> bool:
        """发送日报邮件"""
        if not self.enabled:
            logger.warning("Email not configured, skipping send")
            return False
        if not alerts:
            logger.info("No alerts, skipping daily report send")
            return False

        p1 = sum(1 for a in alerts if a.get("risk_level") == "P1")
        p2 = sum(1 for a in alerts if a.get("risk_level") == "P2")
        p3 = sum(1 for a in alerts if a.get("risk_level") == "P3")

        rows = ""
        for a in alerts[:20]:  # 最多 20 条
            rows += (
                f"<tr>"
                f"<td>{a.get('name', '')}({a.get('code', '')})</td>"
                f"<td>{a.get('alert_type', '')}</td>"
                f"<td>{a.get('trigger_reason', '')[:60]}</td>"
                f"<td>{a.get('confidence_score', 0):.2f}</td>"
                f"<td class='{a.get('risk_level', 'P3')}'>{a.get('risk_level', '')}</td>"
                f"</tr>"
            )

        html = _HTML_TEMPLATE.format(
            report_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
            total_alerts=len(alerts),
            p1_count=p1,
            p2_count=p2,
            p3_count=p3,
            table_rows=rows,
        )

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[QuantLoom·量梭] Daily Flow Alert Report {datetime.now().strftime('%Y-%m-%d')}"
            msg["From"] = self.from_addr
            msg["To"] = self.to_addr
            msg.attach(MIMEText(html, "html", "utf-8"))

            self._smtp_send(msg)

            logger.info(f"Daily report sent: {len(alerts)} alerts -> {self.to_addr}")
            # 批量写入 NotificationLog
            self._log_email_notifications(alerts, success=True)
            return True
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            self._log_email_notifications(alerts, success=False, error=str(e))
            return False

    @staticmethod
    def _log_email_notifications(alerts: list, success: bool, error: str = ""):
        """为日报邮件写入 sq_notification_log"""
        if not alerts:
            return
        try:
            from quant_loom.storage.mysql_client import mysql_client
            from quant_loom.storage.models import NotificationLog

            if not mysql_client.ping():
                return

            for a in alerts:
                log = NotificationLog(
                    alert_id=a.get("db_id"),
                    channel="email",
                    recipient=settings.alert_email_to,
                    status="success" if success else "failed",
                    sent_at=datetime.now(),
                    error_message=error[:200] if error else None,
                )
                try:
                    mysql_client.insert_or_update(log)
                except Exception as e:
                    logger.debug(f"NotificationLog single write failed: {e}")
        except Exception as e:
            logger.debug(f"NotificationLog batch write failed: {e}")


# 全局单例
email_sender = EmailSender()
