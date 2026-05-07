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
test_metrics.py — Prometheus 指标单元测试
"""

import pytest
from prometheus_client import CollectorRegistry, generate_latest


class TestMetricsRegistered:
    """验证指标已注册并能正常收集"""

    def test_all_metrics_registered(self):
        from quant_loom.ops.metrics import (
            pipeline_runs,
            pipeline_duration,
            alerts_produced,
            notifications_sent,
            data_fetch_duration,
            api_call_duration,
            api_errors,
            db_health,
            retry_attempts,
            build_info,
        )
        # 所有指标都能访问，无 ImportError
        assert pipeline_runs is not None
        assert pipeline_duration is not None
        assert alerts_produced is not None
        assert notifications_sent is not None
        assert data_fetch_duration is not None
        assert api_call_duration is not None
        assert api_errors is not None
        assert db_health is not None
        assert retry_attempts is not None
        assert build_info is not None

    def test_counter_increment(self):
        from quant_loom.ops.metrics import alerts_produced

        before = alerts_produced.labels(risk_level="P1", alert_type="test")._value.get()
        alerts_produced.labels(risk_level="P1", alert_type="test").inc()
        after = alerts_produced.labels(risk_level="P1", alert_type="test")._value.get()
        assert after - before == 1

    def test_gauge_set(self):
        from quant_loom.ops.metrics import db_health

        db_health.labels(db="mysql").set(1)
        assert db_health.labels(db="mysql")._value.get() == 1
        db_health.labels(db="mysql").set(0)
        assert db_health.labels(db="mysql")._value.get() == 0

    def test_histogram_observe(self):
        from quant_loom.ops.metrics import pipeline_duration

        pipeline_duration.observe(2.5)
        # 验证不抛异常即可 — histogram 内部状态依赖 prometheus_client 实现
        assert True

    def test_build_info_has_version(self):
        from quant_loom.ops.metrics import build_info

        samples = list(build_info.collect())
        assert len(samples) > 0
        # Build info 包含 version 标签
        labels = {s.labels["version"] for s in samples[0].samples if s.labels.get("version")}
        assert len(labels) > 0
