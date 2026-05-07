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

"""告警去重单元测试"""

import pytest
from quant_loom.rule_engine.dedup import AlertDeduplicator


class TestDeduplicator:
    """去重逻辑"""

    def test_empty_list(self):
        dedup = AlertDeduplicator()
        result = dedup.filter_duplicates([])
        assert result == []

    def test_no_duplicates_first_pass(self):
        """首次通过的告警应该全部保留（假设 Redis 无记录）"""
        dedup = AlertDeduplicator()
        alerts = [
            {"code": "000001", "alert_type": "breakout", "trigger_reason": "测试1"},
            {"code": "000002", "alert_type": "accumulation", "trigger_reason": "测试2"},
        ]
        # 由于单元测试环境可能没有 Redis，dedup 检查默认跳过
        result = dedup.filter_duplicates(alerts)
        # 没有 Redis 时应该全保留
        assert len(result) == 2

    def test_missing_code_or_type_passes(self):
        """缺少 code 或 alert_type 的告警依然保留"""
        dedup = AlertDeduplicator()
        alerts = [
            {"code": "", "alert_type": "breakout"},
            {"code": "000001", "alert_type": ""},
            {"code": "000002", "alert_type": "breakout"},
        ]
        result = dedup.filter_duplicates(alerts)
        assert len(result) == 3

    def test_alert_key_format(self):
        from quant_loom.storage.redis_client import redis_client
        key = redis_client.alert_key("000001", "breakout")
        assert key == "alert_dedup:000001:breakout"

    def test_cooldown_default(self):
        dedup = AlertDeduplicator()
        assert dedup.cooldown_minutes == 30

    def test_cooldown_custom(self):
        dedup = AlertDeduplicator(cooldown_minutes=60)
        assert dedup.cooldown_minutes == 60
