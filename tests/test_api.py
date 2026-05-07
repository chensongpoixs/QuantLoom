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
test_api.py — FastAPI 端点单元测试
"""

import pytest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from quant_loom.api.app import app

client = TestClient(app)


class TestHealthLive:
    """K8s liveness probe"""

    def test_live_returns_200(self):
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["alive"] is True


class TestHealthReady:
    """K8s readiness probe"""

    def test_ready_when_all_up(self):
        with patch("quant_loom.api.app._check_mysql", return_value=True), \
             patch("quant_loom.api.app._check_redis", return_value=True):
            response = client.get("/health/ready")
            assert response.status_code == 200
            assert response.json()["ready"] is True
            assert response.json()["checks"]["mysql"] == "ok"
            assert response.json()["checks"]["redis"] == "ok"

    def test_ready_when_mysql_down(self):
        with patch("quant_loom.api.app._check_mysql", return_value=False), \
             patch("quant_loom.api.app._check_redis", return_value=True):
            response = client.get("/health/ready")
            assert response.status_code == 503
            assert response.json()["ready"] is False
            assert response.json()["checks"]["mysql"] == "down"

    def test_ready_when_redis_down(self):
        with patch("quant_loom.api.app._check_mysql", return_value=True), \
             patch("quant_loom.api.app._check_redis", return_value=False):
            response = client.get("/health/ready")
            assert response.status_code == 503
            assert response.json()["ready"] is False


class TestHealth:
    """综合健康检查"""

    def test_health_all_up(self):
        with patch("quant_loom.api.app._check_mysql", return_value=True), \
             patch("quant_loom.api.app._check_redis", return_value=True):
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "ok"

    def test_health_degraded(self):
        with patch("quant_loom.api.app._check_mysql", return_value=False), \
             patch("quant_loom.api.app._check_redis", return_value=True):
            response = client.get("/health")
            assert response.status_code == 503
            assert response.json()["status"] == "degraded"


class TestMetrics:
    """/metrics 端点"""

    def test_metrics_returns_prometheus_format(self):
        response = client.get("/metrics")
        assert response.status_code == 200
        # Prometheus 格式: 包含 HELP/TYPE/实际指标行
        text = response.text
        assert "quantloom_" in text or "python_" in text
        assert "HELP" in text or "TYPE" in text

    def test_metrics_content_type(self):
        response = client.get("/metrics")
        assert "text/plain" in response.headers["content-type"]
