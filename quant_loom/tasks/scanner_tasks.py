"""
扫描任务 — Celery task 定义

由 Beat 定时触发，执行全市场扫描管线。
"""

from datetime import datetime

from loguru import logger

from quant_loom.tasks.celery_app import app


@app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,  # 失败后 60s 重试
    autoretry_for=(Exception,),
)
def scan_task(self):
    """
    全市场扫描 — 交易时段每 5 分钟触发

    Celery 自动重试 (max 2次)，60s 间隔。
    扫描本身幂等 — 去重机制防止同一天内重复告警。
    """
    logger.info(f"=== Celery scan_task 触发 === request_id={self.request.id}")
    try:
        from scripts.run_scanner import main
        main(dry_run=False, top_n=10, skip_events=False)
    except Exception as e:
        logger.error(f"scan_task 执行异常: {e}")
        raise  # 重新抛出以触发 Celery retry


@app.task(
    bind=True,
    max_retries=1,
    default_retry_delay=120,
    autoretry_for=(Exception,),
)
def closing_report_task(self):
    """
    收盘日报 — 每个交易日 16:05 触发

    执行全量扫描 + AI 分析 top 20 + 发送邮件日报。
    如果当天没有交易数据 (如节假日)，空结果即为正常输出。
    """
    logger.info(f"=== Celery closing_report_task 触发 === request_id={self.request.id}")
    try:
        from scripts.run_scanner import main
        from quant_loom.storage.mysql_client import mysql_client
        from quant_loom.storage.models import StockAlert
        from quant_loom.notification.email_sender import email_sender

        # 全量扫描 (AI 分析 top 20)
        main(dry_run=False, top_n=20, skip_events=False)

        # 查询当天数据库中的告警并发送日报邮件
        if email_sender.enabled and mysql_client.ping():
            today_alerts_raw = mysql_client.query_alerts(limit=50)
            email_sender.send_daily_report([_alert_to_dict(a) for a in today_alerts_raw])
    except Exception as e:
        logger.error(f"closing_report_task 执行异常: {e}")
        raise


def _alert_to_dict(alert) -> dict:
    """ORM 对象 → dict (含 db_id)"""
    return {
        "db_id": alert.id,
        "code": alert.code,
        "name": alert.name,
        "alert_type": alert.alert_type,
        "trigger_reason": alert.trigger_reason,
        "confidence_score": alert.confidence_score or 0,
        "risk_level": alert.risk_level or "P3",
    }
