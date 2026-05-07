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
test_webhook.py — 通知模块单元测试
"""

import pytest
from unittest.mock import patch, MagicMock

from quant_loom.notification.webhook import WebhookNotifier


class TestWebhookChannelSelection:
    """渠道自动检测"""

    def test_no_channels_when_none_configured(self):
        notifier = WebhookNotifier()
        notifier.wecom_url = ""
        notifier.feishu_url = ""
        notifier.dingtalk_url = ""
        results = notifier.send_alert({"risk_level": "P1"})
        assert results == {}

    def test_wecom_auto_detected(self):
        notifier = WebhookNotifier()
        notifier.wecom_url = "https://qyapi.weixin.qq.com/webhook"
        notifier.feishu_url = ""
        notifier.dingtalk_url = ""

        with patch.object(notifier, '_send_wecom', return_value=True):
            results = notifier.send_alert({"risk_level": "P1"})
            assert "wecom" in results

    def test_multiple_channels_auto_detected(self):
        notifier = WebhookNotifier()
        notifier.wecom_url = "https://qyapi.weixin.qq.com/webhook"
        notifier.feishu_url = "https://open.feishu.cn/webhook"
        notifier.dingtalk_url = ""

        with patch.object(notifier, '_send_wecom', return_value=True), \
             patch.object(notifier, '_send_feishu', return_value=True):
            results = notifier.send_alert({"risk_level": "P1"})
            assert "wecom" in results
            assert "feishu" in results

    def test_explicit_channels_override_auto(self):
        notifier = WebhookNotifier()
        notifier.wecom_url = "https://qyapi.weixin.qq.com/webhook"
        notifier.feishu_url = "https://open.feishu.cn/webhook"
        notifier.dingtalk_url = "https://oapi.dingtalk.com/webhook"

        with patch.object(notifier, '_send_dingtalk', return_value=True):
            results = notifier.send_alert({"risk_level": "P1"}, channels=["dingtalk"])
            assert "dingtalk" in results
            assert "wecom" not in results  # 未显式指定，不发送


class TestDingTalkFormat:
    """钉钉消息格式"""

    def test_markdown_format(self):
        notifier = WebhookNotifier()
        notifier.dingtalk_url = "https://oapi.dingtalk.com/webhook"

        alert = {
            "name": "测试股",
            "code": "000001",
            "alert_type": "放量上攻",
            "trigger_reason": "涨幅超阈值",
            "confidence_score": 0.85,
            "risk_level": "P1",
            "ai_summary": "机构资金大幅流入",
        }

        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"errcode":0}'
            mock_post.return_value = mock_resp

            result = notifier._send_dingtalk(alert)
            assert result is True

            call_args = mock_post.call_args
            payload = call_args[1]["json"]
            assert payload["msgtype"] == "markdown"
            assert "测试股" in payload["markdown"]["text"]
            assert "000001" in payload["markdown"]["text"]
            assert "机构资金大幅流入" in payload["markdown"]["text"]

    def test_p1_includes_at_all(self):
        notifier = WebhookNotifier()
        notifier.dingtalk_url = "https://oapi.dingtalk.com/webhook"

        alert = {"name": "t", "code": "1", "alert_type": "t",
                 "trigger_reason": "t", "confidence_score": 0.9, "risk_level": "P1"}

        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"errcode":0}'
            mock_post.return_value = mock_resp
            notifier._send_dingtalk(alert)
            payload = mock_post.call_args[1]["json"]
            assert "@所有人" in payload["markdown"]["text"]
            assert payload.get("at", {}).get("isAtAll") is True

    def test_p2_no_at_all(self):
        notifier = WebhookNotifier()
        notifier.dingtalk_url = "https://oapi.dingtalk.com/webhook"

        alert = {"name": "t", "code": "1", "alert_type": "t",
                 "trigger_reason": "t", "confidence_score": 0.6, "risk_level": "P2"}

        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"errcode":0}'
            mock_post.return_value = mock_resp
            notifier._send_dingtalk(alert)
            payload = mock_post.call_args[1]["json"]
            assert "@所有人" not in payload["markdown"]["text"]


class TestWecomFormat:
    """企业微信消息格式"""

    def test_markdown_content(self):
        notifier = WebhookNotifier()
        notifier.wecom_url = "https://qyapi.weixin.qq.com/webhook"

        alert = {
            "name": "测试股", "code": "000001", "alert_type": "放量上攻",
            "trigger_reason": "涨幅超阈值", "confidence_score": 0.85,
            "risk_level": "P1", "ai_summary": "机构资金流入",
        }

        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"errcode":0}'
            mock_post.return_value = mock_resp
            result = notifier._send_wecom(alert)
            assert result is True
            payload = mock_post.call_args[1]["json"]
            assert payload["msgtype"] == "markdown"
            assert "测试股" in payload["markdown"]["content"]


class TestWebhookRetry:
    """Webhook 重试行为"""

    def test_wecom_returns_false_on_network_error(self):
        notifier = WebhookNotifier()
        notifier.wecom_url = "https://qyapi.weixin.qq.com/webhook"

        import requests
        with patch("requests.post", side_effect=requests.ConnectionError("fail")):
            result = notifier._send_wecom({"risk_level": "P3"})
            assert result is False

    def test_feishu_returns_false_on_non_200(self):
        notifier = WebhookNotifier()
        notifier.feishu_url = "https://open.feishu.cn/webhook"

        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 400
            mock_resp.text = "Bad Request"
            mock_post.return_value = mock_resp
            result = notifier._send_feishu({"risk_level": "P3", "name": "t", "code": "1",
                                             "alert_type": "t", "trigger_reason": "t"})
            assert result is False


class TestNotificationLog:
    """NotificationLog 写入"""

    def test_log_notification_does_not_raise(self):
        """_log_notification 失败不抛异常 (graceful)"""
        # 无 MySQL 环境，验证不会抛异常
        try:
            WebhookNotifier._log_notification({"db_id": 1}, "wecom", True)
        except Exception as e:
            pytest.fail(f"_log_notification 不应抛异常: {e}")
