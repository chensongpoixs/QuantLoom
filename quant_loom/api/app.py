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
FastAPI 应用 — 健康检查 + Prometheus /metrics + 反馈闭环

Usage:
  uvicorn quant_loom.api.app:app --host 0.0.0.0 --port 9090
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
from loguru import logger
from pydantic import BaseModel
from prometheus_client import generate_latest, CollectorRegistry, REGISTRY

from quant_loom.ops.metrics import db_health, alert_precision, alert_outcome_correct

_BANNER = r"""
     _    .-')              _  .-')    _   .-')      ('-.   .-')     ('-.
    ( '.( OO )_            ( \( -O )  ( '.( OO )_   _(  OO) ( OO ). ( OO )
   ,--.   ,--. .-'),-----. ,------.  ,--.   ,--.  (,------.(_/.  \_)(_/.  \_)
  |   `.'   |( OO'  .-.  '|  .---'  |   `.'   |   |  .---' \  `.'  / \  `.'  /
  |         |/   |  | |  ||  |      |         |   |  |      \     /   \     /
   |  |'.'|  |\_) |  |\|  ||  '--.   |  |'.'|  |  (|  '--.   \   /     \   /
  |  |   |  |  \ |  | |  ||  .--'   |  |   |  |   |  .--'  .-._)   \ .-._)   \
  |  |   |  |   `'  '-'  '|  `---.  |  |   |  |   |  `---. \       / \       /
  `--'   `--'     `-----' `------'  `--'   `--'   `------'  `-----'   `-----'

                                 ·  量  梭  ·
                    A-Share Institutional Flow AI Monitor

             QuantLoom·量梭 的野心，从不只是在手机上弹出几条信号

              这座织机真正要为你织出的终极产物，是 RTX Pro 6000
                         ——  黑曜神机 的自由召唤权。

             1. 它是躺在你机箱里的黑色方尖碑，数万核心如暗夜星海
 2. 它是本地训推大模型、实时织造全市场量能全景图、回溯十年资金指纹的物质根基
              3. 它过去只降落在超算中心、顶级量化基金和神秘矿场

    QuantLoom·量梭 每织出一匹盈利的锦缎，都是在为这座黑色圣坛添一根金线。
     当金线积聚成缆，黑曜神机便会从虚空货架撕开一道裂缝，降临在你的阵中。

                       从此，你拥有了一座个人算力神殿。
"""


# ---- 应用工厂 ----

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期 — 启动/关闭日志"""
    print(_BANNER)
    logger.info("FastAPI service started — /health /metrics ready")
    yield
    logger.info("FastAPI service stopped")


app = FastAPI(
    title="QuantLoom·量梭 API",
    version="0.3.0",
    lifespan=lifespan,
)


# ---- 健康检查 ----

def _check_mysql() -> bool:
    """检查 MySQL 连通性"""
    try:
        from quant_loom.storage.mysql_client import mysql_client
        return mysql_client.ping()
    except Exception as e:
        logger.warning(f"MySQL health check failed: {e}")
        return False


def _check_redis() -> bool:
    """检查 Redis 连通性"""
    try:
        from quant_loom.storage.redis_client import redis_client
        return redis_client.ping()
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        return False


def _refresh_health_gauges() -> dict:
    """检查各组件并刷新 Prometheus 健康指标"""
    mysql_ok = _check_mysql()
    redis_ok = _check_redis()
    db_health.labels(db="mysql").set(1 if mysql_ok else 0)
    db_health.labels(db="redis").set(1 if redis_ok else 0)
    return {"mysql": "ok" if mysql_ok else "down",
            "redis": "ok" if redis_ok else "down"}


@app.get("/health")
async def health():
    """综合健康检查 — 含 MySQL + Redis"""
    checks = _refresh_health_gauges()
    all_ok = all(v == "ok" for v in checks.values())
    status = "ok" if all_ok else "degraded"
    return JSONResponse(
        content={"status": status, "checks": checks},
        status_code=200 if all_ok else 503,
    )


@app.get("/health/ready")
async def health_ready():
    """K8s readiness probe — MySQL + Redis 均可用才算就绪"""
    checks = _refresh_health_gauges()
    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        content={"ready": all_ok, "checks": checks},
        status_code=200 if all_ok else 503,
    )


@app.get("/health/live")
async def health_live():
    """K8s liveness probe — 进程存活即可"""
    return JSONResponse(content={"alive": True})


# ---- Prometheus 指标 ----

@app.get("/metrics")
async def metrics():
    """Prometheus 指标端点 — 返回 text/plain 格式"""
    return PlainTextResponse(
        content=generate_latest(REGISTRY),
        media_type="text/plain; charset=utf-8",
    )


# ---- 反馈闭环 (Phase 4) ----

class FeedbackRequest(BaseModel):
    alert_id: int
    verdict: str  # correct / incorrect / ambiguous
    notes: str = ""
    reviewer: str = ""


@app.post("/feedback")
async def submit_feedback(req: FeedbackRequest):
    """人工提交告警评审反馈"""
    if req.verdict not in ("correct", "incorrect", "ambiguous"):
        raise HTTPException(status_code=400, detail="verdict must be: correct/incorrect/ambiguous")

    try:
        from quant_loom.storage.mysql_client import mysql_client
        from quant_loom.storage.models import AlertFeedback, StockAlert

        if not mysql_client.ping():
            raise HTTPException(status_code=503, detail="MySQL unavailable")

        # 验证 alert_id 存在
        with mysql_client.get_session() as sess:
            alert = sess.query(StockAlert).filter(StockAlert.id == req.alert_id).first()
            if not alert:
                raise HTTPException(status_code=404, detail=f"Alert {req.alert_id} not found")

            feedback = AlertFeedback(
                alert_id=req.alert_id,
                feedback_type="manual",
                reviewer=req.reviewer or "anonymous",
                verdict=req.verdict,
                notes=req.notes,
            )
            mysql_client.insert_or_update(feedback)

            # 更新 Prometheus 指标
            alert_outcome_correct.labels(
                alert_type=alert.alert_type or "unknown",
                outcome=req.verdict,
            ).inc()

        logger.info(f"Feedback recorded: alert_id={req.alert_id} verdict={req.verdict}")
        return JSONResponse(content={"status": "ok", "alert_id": req.alert_id})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Feedback submission failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/alerts/pending-review")
async def pending_review(days: int = 7):
    """列出近 N 天尚未有人工反馈的告警"""
    try:
        from quant_loom.storage.mysql_client import mysql_client
        from quant_loom.storage.models import StockAlert, AlertFeedback

        if not mysql_client.ping():
            raise HTTPException(status_code=503, detail="MySQL unavailable")

        cutoff = datetime.now() - timedelta(days=days)
        with mysql_client.get_session() as sess:
            # 查近 N 天有 AI 分析的告警
            alerts = (
                sess.query(StockAlert)
                .filter(
                    StockAlert.created_at >= cutoff,
                    StockAlert.ai_summary.isnot(None),
                )
                .order_by(StockAlert.confidence_score.desc())
                .limit(50)
                .all()
            )

            pending = []
            for alert in alerts:
                # 检查是否已有手动反馈
                fb = (
                    sess.query(AlertFeedback)
                    .filter(
                        AlertFeedback.alert_id == alert.id,
                        AlertFeedback.feedback_type == "manual",
                    )
                    .first()
                )
                if not fb:
                    pending.append({
                        "alert_id": alert.id,
                        "ts": alert.ts.isoformat() if alert.ts else None,
                        "code": alert.code,
                        "name": alert.name,
                        "alert_type": alert.alert_type,
                        "confidence_score": alert.confidence_score,
                        "risk_level": alert.risk_level,
                        "ai_summary": alert.ai_summary,
                    })

        return JSONResponse(content={"count": len(pending), "alerts": pending})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query pending review alerts failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/alerts/quality")
async def alert_quality(days: int = 30):
    """查询告警质量统计"""
    try:
        from quant_loom.storage.mysql_client import mysql_client
        from quant_loom.storage.models import AlertFeedback
        from sqlalchemy import func

        if not mysql_client.ping():
            raise HTTPException(status_code=503, detail="MySQL unavailable")

        cutoff = datetime.now() - timedelta(days=days)
        with mysql_client.get_session() as sess:
            # 按 verdict 分组统计
            stats = (
                sess.query(
                    AlertFeedback.verdict,
                    func.count(AlertFeedback.id).label("cnt"),
                )
                .filter(AlertFeedback.created_at >= cutoff)
                .group_by(AlertFeedback.verdict)
                .all()
            )

            counts = {"correct": 0, "incorrect": 0, "ambiguous": 0}
            for s in stats:
                if s.verdict in counts:
                    counts[s.verdict] = s.cnt

            total = sum(counts.values())
            precision = counts["correct"] / total if total > 0 else None

            # 按类型统计平均置信度
            type_stats = _get_confidence_by_type(sess, cutoff)

        return JSONResponse(content={
            "period_days": days,
            "total_feedbacks": total,
            "verdict_counts": counts,
            "precision": round(precision, 4) if precision is not None else None,
            "confidence_by_type": type_stats,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query alert quality failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _get_confidence_by_type(sess, cutoff) -> dict:
    """按 alert_type 统计平均置信度和反馈精度"""
    from quant_loom.storage.models import StockAlert, AlertFeedback
    from sqlalchemy import func

    result = {}
    try:
        rows = (
            sess.query(
                StockAlert.alert_type,
                func.avg(StockAlert.confidence_score).label("avg_confidence"),
                func.count(StockAlert.id).label("total"),
            )
            .filter(StockAlert.created_at >= cutoff)
            .group_by(StockAlert.alert_type)
            .all()
        )
        for r in rows:
            a_type = r.alert_type or "unknown"
            # 该类型中正确的数量
            correct_count = (
                sess.query(func.count(AlertFeedback.id))
                .join(StockAlert, AlertFeedback.alert_id == StockAlert.id)
                .filter(
                    StockAlert.alert_type == r.alert_type,
                    AlertFeedback.verdict == "correct",
                    AlertFeedback.created_at >= cutoff,
                )
                .scalar()
            ) or 0
            result[a_type] = {
                "avg_confidence": round(float(r.avg_confidence or 0), 4),
                "total_alerts": r.total,
                "correct_feedbacks": correct_count,
            }
    except Exception as e:
        logger.warning(f"Confidence by type query failed: {e}")
    return result
