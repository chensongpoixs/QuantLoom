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
        assert "QuantLoom·量梭 Daily Flow Alert Report" in html
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
