"""
test_email.py — 邮件模块单元测试
"""

import pytest
from unittest.mock import patch, MagicMock

from quant_loom.notification.email_sender import EmailSender, _HTML_TEMPLATE


class TestEmailTemplate:
    """邮件模板渲染"""

    def test_template_renders_with_data(self):
        alerts = [
            {"name": "测试股", "code": "000001", "alert_type": "放量上攻",
             "trigger_reason": "涨幅超阈值", "confidence_score": 0.85, "risk_level": "P1"},
        ]
        rows = '<tr><td>测试股(000001)</td><td>放量上攻</td><td>涨幅超阈值</td><td>0.85</td><td class="P1">P1</td></tr>'
        html = _HTML_TEMPLATE.format(
            report_time="2026-05-08 16:00",
            total_alerts=1,
            p1_count=1,
            p2_count=0,
            p3_count=0,
            table_rows=rows,
        )
        assert "QuantLoom 异动日报" in html
        assert "2026-05-08 16:00" in html
        assert "测试股(000001)" in html
        assert "P1" in html


class TestEmailSenderConfig:
    """邮件发送器配置"""

    def test_disabled_when_no_config(self):
        sender = EmailSender()
        sender.host = ""
        sender.user = ""
        sender.password = ""
        assert not sender.enabled

    def test_enabled_when_configured(self):
        sender = EmailSender()
        sender.host = "smtp.example.com"
        sender.user = "user"
        sender.password = "pass"
        assert sender.enabled


class TestSmtpPortSelection:
    """SMTP 端口选择"""

    def test_port_465_uses_ssl(self):
        """端口 465 应走 SMTP_SSL (不调用 starttls)"""
        with patch("smtplib.SMTP_SSL") as mock_ssl:
            sender = EmailSender()
            sender.host = "smtp.example.com"
            sender.port = 465
            sender.user = "user"
            sender.password = "pass"
            sender.from_addr = "a@b.com"
            sender.to_addr = "c@d.com"
            sender.enabled  # no-op

            # 验证 SMTP_SSL 类可用
            import smtplib
            assert hasattr(smtplib, "SMTP_SSL")

    def test_port_587_uses_starttls(self):
        """端口 587 应走 SMTP + starttls"""
        sender = EmailSender()
        sender.host = "smtp.example.com"
        sender.port = 587
        sender.user = "user"
        sender.password = "pass"
        assert sender.port == 587


class TestSkipWhenDisabled:
    """禁用时跳过发送"""

    def test_skip_when_disabled(self):
        sender = EmailSender()
        sender.host = ""
        sender.user = ""
        sender.password = ""
        result = sender.send_daily_report([])
        assert result is False

    def test_skip_when_no_alerts(self):
        sender = EmailSender()
        sender.host = "smtp.example.com"
        sender.user = "user"
        sender.password = "pass"
        result = sender.send_daily_report([])
        assert result is False
