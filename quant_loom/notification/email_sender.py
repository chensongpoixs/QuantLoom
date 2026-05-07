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
<h2>QuantLoom 异动日报</h2>
<p>生成时间: {report_time}</p>
<p>今日异动总数: <strong>{total_alerts}</strong> (P1: {p1_count}, P2: {p2_count}, P3: {p3_count})</p>

<h3>Top 异动标的</h3>
<table>
<tr><th>股票</th><th>类型</th><th>触发原因</th><th>置信度</th><th>风险</th></tr>
{table_rows}
</table>

<h3>风险提示</h3>
<p>本报告仅供研究参考，不构成投资建议。所有信号基于公开数据与规则引擎自动生成，可能存在误报或滞后。</p>

<div class="footer">
<p>QuantLoom · 免责声明: 系统输出仅供研究信息参考</p>
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
            logger.warning("邮件未配置，跳过发送")
            return False
        if not alerts:
            logger.info("无告警，跳过日报发送")
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
            msg["Subject"] = f"[QuantLoom] 异动日报 {datetime.now().strftime('%Y-%m-%d')}"
            msg["From"] = self.from_addr
            msg["To"] = self.to_addr
            msg.attach(MIMEText(html, "html", "utf-8"))

            self._smtp_send(msg)

            logger.info(f"日报已发送: {len(alerts)} 条告警 -> {self.to_addr}")
            # 批量写入 NotificationLog
            self._log_email_notifications(alerts, success=True)
            return True
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
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
                except Exception:
                    pass  # 单条日志失败不影响其他
        except Exception:
            pass  # 通知日志写入失败不影响主流程


# 全局单例
email_sender = EmailSender()
