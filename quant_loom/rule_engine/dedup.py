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
                logger.debug(f"去重跳过: {code} {alert_type}")
                continue

            filtered.append(alert)

        if skipped:
            logger.info(f"去重: 跳过 {skipped} 条，保留 {len(filtered)} 条")

        return filtered

    def mark_sent(self, alerts: List[dict]) -> None:
        """标记告警已发送，开始冷却计时"""
        for alert in alerts:
            code = alert.get("code", "")
            alert_type = alert.get("alert_type", "")
            if code and alert_type and redis_client.client:
                redis_client.mark_alert_sent(code, alert_type, self.cooldown_minutes)
