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
告警去重模块
基于 Redis 实现同标的同原因在冷却期内不重复推送
"""

from typing import List

from loguru import logger

from quant_loom.storage.redis_client import redis_client


class AlertDeduplicator:
    """告警去重器"""

    def __init__(self, cooldown_minutes: int = 30):
        self.cooldown_minutes = cooldown_minutes

    def filter_duplicates(self, alerts: List[dict]) -> List[dict]:
        """
        过滤重复告警
        - 同股票 + 同类型在冷却期内只保留首条
        - 返回去重后的告警列表
        """
        if not alerts:
            return []

        filtered = []
        skipped = 0

        for alert in alerts:
            code = alert.get("code", "")
            alert_type = alert.get("alert_type", "")

            if not code or not alert_type:
                filtered.append(alert)
                continue

            if redis_client.client and redis_client.is_duplicate(code, alert_type, self.cooldown_minutes):
                skipped += 1
                logger.debug(f"Dedup skipped: {code} {alert_type}")
                continue

            filtered.append(alert)

        if skipped:
            logger.info(f"Dedup: skipped {skipped}, kept {len(filtered)}")

        return filtered

    def mark_sent(self, alerts: List[dict]) -> None:
        """标记告警已发送，开始冷却计时"""
        for alert in alerts:
            code = alert.get("code", "")
            alert_type = alert.get("alert_type", "")
            if code and alert_type and redis_client.client:
                redis_client.mark_alert_sent(code, alert_type, self.cooldown_minutes)
