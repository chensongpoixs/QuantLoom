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
    logger.info(f"=== Celery scan_task triggered === request_id={self.request.id}")
    try:
        from scripts.run_scanner import main
        main(dry_run=False, top_n=10, skip_events=False)
    except Exception as e:
        logger.error(f"scan_task execution error: {e}")
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
    logger.info(f"=== Celery closing_report_task triggered === request_id={self.request.id}")
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
        logger.error(f"closing_report_task execution error: {e}")
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


@app.task(
    bind=True,
    max_retries=1,
    default_retry_delay=300,
    autoretry_for=(Exception,),
)
def backfill_outcomes_task(self):
    """
    自动结果回填 — 每日 16:30 执行
    查 1/3/5 天前的告警，回填 outcome 到 sq_alert_feedback
    """
    from datetime import date, timedelta
    from quant_loom.storage.mysql_client import mysql_client
    from quant_loom.storage.models import StockAlert, AlertFeedback, BacktestResult

    logger.info(f"=== Celery backfill_outcomes_task triggered === request_id={self.request.id}")
    if not mysql_client.ping():
        logger.warning("MySQL unavailable, skipping outcome backfill")
        return

    today = date.today()
    windows = [("1d", 1), ("3d", 3), ("5d", 5)]

    try:
        with mysql_client.get_session() as sess:
            for label, n_days in windows:
                target_date = today - timedelta(days=n_days)
                alerts = (
                    sess.query(StockAlert)
                    .filter(
                        StockAlert.ts >= target_date,
                        StockAlert.ts < target_date + timedelta(days=1),
                    )
                    .all()
                )

                for alert in alerts:
                    # 查回测结果中的 outcome (如有)
                    btr = (
                        sess.query(BacktestResult)
                        .filter(
                            BacktestResult.code == alert.code,
                            BacktestResult.trade_date == target_date,
                            BacktestResult.alert_type == alert.alert_type,
                        )
                        .first()
                    )
                    if not btr:
                        continue

                    # 创建或更新自动反馈
                    existing = (
                        sess.query(AlertFeedback)
                        .filter(
                            AlertFeedback.alert_id == alert.id,
                            AlertFeedback.feedback_type == "auto",
                        )
                        .first()
                    )
                    if existing:
                        setattr(existing, f"outcome_{n_days}d", getattr(btr, f"outcome_{n_days}d", None))
                    else:
                        fb = AlertFeedback(
                            alert_id=alert.id,
                            feedback_type="auto",
                            **{f"outcome_{n_days}d": getattr(btr, f"outcome_{n_days}d", None)},
                        )
                        sess.add(fb)

            sess.commit()
            logger.info(f"Outcome backfill complete: {len(windows)} windows")
    except Exception as e:
        logger.error(f"backfill_outcomes_task error: {e}")
        raise


@app.task(
    bind=True,
    max_retries=1,
    default_retry_delay=120,
    autoretry_for=(Exception,),
)
def refresh_quality_metrics_task(self):
    """
    刷新告警质量 Prometheus 指标 — 每小时执行
    从 sq_alert_feedback 计算各类型精度
    """
    from quant_loom.storage.mysql_client import mysql_client
    from quant_loom.storage.models import AlertFeedback
    from sqlalchemy import func

    logger.info(f"=== Celery refresh_quality_metrics_task triggered === request_id={self.request.id}")
    if not mysql_client.ping():
        return

    try:
        from quant_loom.ops.metrics import alert_precision, alert_outcome_correct

        with mysql_client.get_session() as sess:
            # 按 alert_type 统计精度
            verdict_counts = (
                sess.query(
                    AlertFeedback.verdict,
                    func.count(AlertFeedback.id).label("cnt"),
                )
                .group_by(AlertFeedback.verdict)
                .all()
            )

            counts = {}
            for v in verdict_counts:
                if v.verdict in ("correct", "incorrect"):
                    counts[v.verdict] = v.cnt

            # 全部告警的总体精度
            total = sum(counts.values())
            if total > 0:
                precision = counts.get("correct", 0) / total
                alert_precision.labels(alert_type="all", window="3d").set(precision)

        logger.info(f"Quality metrics refreshed: precision={precision:.4f}" if total > 0 else "Quality metrics: no data")

    except Exception as e:
        logger.error(f"refresh_quality_metrics_task error: {e}")
        raise
