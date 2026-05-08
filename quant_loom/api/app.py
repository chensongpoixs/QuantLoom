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

import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
import quant_loom.ops.logger  # noqa: F401 — 初始化文件日志输出
from pydantic import BaseModel
from prometheus_client import generate_latest, CollectorRegistry, REGISTRY
from sqlalchemy import func, Integer

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
    version="0.4.0",
    lifespan=lifespan,
)

# CORS — 允许前端开发调试 (Vite dev server :5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


# ---- 数据查询 API (Phase 5: 前端看板) ----

@app.get("/api/alerts")
async def api_alerts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    alert_type: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    code: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """分页告警列表 — 支持按类型/风险/代码/日期筛选"""
    try:
        from quant_loom.storage.mysql_client import mysql_client
        from quant_loom.storage.models import StockAlert

        if not mysql_client.ping():
            raise HTTPException(status_code=503, detail="MySQL unavailable")

        with mysql_client.get_session() as sess:
            q = sess.query(StockAlert)

            if alert_type:
                q = q.filter(StockAlert.alert_type == alert_type)
            if risk_level:
                q = q.filter(StockAlert.risk_level == risk_level)
            if code:
                q = q.filter(StockAlert.code.like(f"%{code}%"))
            if start_date:
                try:
                    sd = datetime.strptime(start_date, "%Y-%m-%d")
                    q = q.filter(StockAlert.ts >= sd)
                except ValueError:
                    raise HTTPException(status_code=400, detail="start_date format: YYYY-MM-DD")
            if end_date:
                try:
                    ed = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
                    q = q.filter(StockAlert.ts < ed)
                except ValueError:
                    raise HTTPException(status_code=400, detail="end_date format: YYYY-MM-DD")

            total = q.count()
            items = (
                q.order_by(StockAlert.ts.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )

            # 在 session 内将 ORM 对象转为普通 dict (避免 detached instance 错误)
            result_items = [
                {
                    "id": a.id,
                    "ts": a.ts.isoformat() if a.ts else None,
                    "code": a.code,
                    "name": a.name,
                    "alert_type": a.alert_type,
                    "trigger_reason": a.trigger_reason,
                    "net_inflow_amount": float(a.net_inflow_amount) if a.net_inflow_amount else 0,
                    "inflow_ratio": float(a.inflow_ratio) if a.inflow_ratio else 0,
                    "confidence_score": a.confidence_score,
                    "risk_level": a.risk_level,
                    "ai_summary": a.ai_summary,
                    "is_sent": a.is_sent,
                }
                for a in items
            ]

        return JSONResponse(content={
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": result_items,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query alerts failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/alerts/{alert_id}")
async def api_alert_detail(alert_id: int):
    """单条告警详情 — 含 AI 分析、相关事件、通知日志"""
    try:
        from quant_loom.storage.mysql_client import mysql_client
        from quant_loom.storage.models import StockAlert, NotificationLog, StockEvent

        if not mysql_client.ping():
            raise HTTPException(status_code=503, detail="MySQL unavailable")

        with mysql_client.get_session() as sess:
            alert = sess.query(StockAlert).filter(StockAlert.id == alert_id).first()
            if not alert:
                raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

            # 查询关联事件
            events = []
            if alert.code and alert.ts:
                events = (
                    sess.query(StockEvent)
                    .filter(
                        StockEvent.code == alert.code,
                        StockEvent.published_at >= alert.ts - timedelta(days=3),
                        StockEvent.published_at <= alert.ts,
                    )
                    .order_by(StockEvent.published_at.desc())
                    .limit(10)
                    .all()
                )

            # 查询通知日志
            notif_logs = (
                sess.query(NotificationLog)
                .filter(NotificationLog.alert_id == alert_id)
                .order_by(NotificationLog.sent_at.desc())
                .all()
            )

            # 在 session 内将 ORM 对象转为普通 dict (避免 detached instance 错误)
            result = {
                "id": alert.id,
                "ts": alert.ts.isoformat() if alert.ts else None,
                "code": alert.code,
                "name": alert.name,
                "alert_type": alert.alert_type,
                "trigger_reason": alert.trigger_reason,
                "net_inflow_amount": float(alert.net_inflow_amount) if alert.net_inflow_amount else 0,
                "inflow_ratio": float(alert.inflow_ratio) if alert.inflow_ratio else 0,
                "confidence_score": alert.confidence_score,
                "risk_level": alert.risk_level,
                "ai_summary": alert.ai_summary,
                "ai_evidence": alert.ai_evidence,
                "is_sent": alert.is_sent,
                "created_at": alert.created_at.isoformat() if alert.created_at else None,
                "related_events": [
                    {
                        "id": e.id,
                        "event_type": e.event_type,
                        "title": e.title,
                        "content": e.content,
                        "source": e.source,
                        "published_at": e.published_at.isoformat() if e.published_at else None,
                        "sentiment_score": e.sentiment_score,
                    }
                    for e in events
                ],
                "notification_logs": [
                    {
                        "id": n.id,
                        "channel": n.channel,
                        "status": n.status,
                        "sent_at": n.sent_at.isoformat() if n.sent_at else None,
                        "error_message": n.error_message,
                    }
                    for n in notif_logs
                ],
            }

        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query alert detail failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats/summary")
async def api_stats_summary():
    """仪表盘摘要 — 今日告警数、P1/P2/P3 分布、各类型数量"""
    try:
        from quant_loom.storage.mysql_client import mysql_client
        from quant_loom.storage.models import StockAlert

        if not mysql_client.ping():
            raise HTTPException(status_code=503, detail="MySQL unavailable")

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = today - timedelta(days=7)

        with mysql_client.get_session() as sess:
            # 今日统计
            today_alerts = sess.query(StockAlert).filter(StockAlert.ts >= today).all()
            today_count = len(today_alerts)
            p1_count = sum(1 for a in today_alerts if a.risk_level == "P1")
            p2_count = sum(1 for a in today_alerts if a.risk_level == "P2")
            p3_count = sum(1 for a in today_alerts if a.risk_level == "P3")
            ai_count = sum(1 for a in today_alerts if a.ai_summary)

            # 按类型统计 (今日)
            type_stats = (
                sess.query(
                    StockAlert.alert_type,
                    func.count(StockAlert.id).label("cnt"),
                )
                .filter(StockAlert.ts >= today)
                .group_by(StockAlert.alert_type)
                .all()
            )
            # 在 session 内材料化为普通 dict
            type_list = [
                {"type": t.alert_type or "unknown", "count": t.cnt}
                for t in type_stats
            ]

            # 近 7 天日均
            week_total = (
                sess.query(func.count(StockAlert.id))
                .filter(StockAlert.ts >= week_ago)
                .scalar()
            ) or 0
            avg_daily = round(week_total / 7, 1)

        return JSONResponse(content={
            "today": {
                "total": today_count,
                "p1": p1_count,
                "p2": p2_count,
                "p3": p3_count,
                "ai_analyzed": ai_count,
            },
            "by_type": type_list,
            "week_avg_daily": avg_daily,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query stats summary failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats/trend")
async def api_stats_trend(days: int = Query(7, ge=1, le=90)):
    """趋势数据 — 按日期 + alert_type 统计告警数量 (供 ECharts)"""
    try:
        from quant_loom.storage.mysql_client import mysql_client
        from quant_loom.storage.models import StockAlert

        if not mysql_client.ping():
            raise HTTPException(status_code=503, detail="MySQL unavailable")

        cutoff = datetime.now() - timedelta(days=days)
        with mysql_client.get_session() as sess:
            rows = (
                sess.query(
                    func.date(StockAlert.ts).label("d"),
                    StockAlert.alert_type,
                    func.count(StockAlert.id).label("cnt"),
                )
                .filter(StockAlert.ts >= cutoff)
                .group_by("d", StockAlert.alert_type)
                .order_by("d")
                .all()
            )

            # 在 session 内构建结果 (避免 detached instance)
            date_map: dict = {}
            for r in rows:
                d_str = str(r.d)
                if d_str not in date_map:
                    date_map[d_str] = {}
                date_map[d_str][r.alert_type or "unknown"] = r.cnt

            dates = sorted(date_map.keys())
            by_type: dict = {}
            for d in dates:
                for at, cnt in date_map[d].items():
                    if at not in by_type:
                        by_type[at] = []
                    by_type[at].append(cnt)
            for at in by_type:
                by_type[at] = by_type[at] + [0] * (len(dates) - len(by_type[at]))

            totals = [sum(date_map[d].values()) for d in dates]

        return JSONResponse(content={
            "dates": dates,
            "totals": totals,
            "by_type": by_type,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query stats trend failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stocks/search")
async def api_stocks_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
):
    """股票搜索 — code 或 name 模糊匹配"""
    try:
        from quant_loom.storage.mysql_client import mysql_client
        from quant_loom.storage.models import StockMaster

        if not mysql_client.ping():
            raise HTTPException(status_code=503, detail="MySQL unavailable")

        with mysql_client.get_session() as sess:
            stocks = (
                sess.query(StockMaster)
                .filter(
                    (StockMaster.code.like(f"%{q}%"))
                    | (StockMaster.name.like(f"%{q}%"))
                )
                .limit(limit)
                .all()
            )

            # 在 session 内将 ORM 对象转为普通 dict
            results = [
                {
                    "code": s.code,
                    "name": s.name,
                    "exchange": s.exchange,
                    "industry": s.industry,
                }
                for s in stocks
            ]

        return JSONResponse(content={"results": results})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stock search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---- AI 每日洞察 (Phase 5E) ----

@app.get("/api/analysis/daily")
async def api_analysis_daily(limit: int = Query(10, ge=1, le=20)):
    """今日 AI 分析 Top10 — 返回置信度最高的已分析告警"""
    try:
        from quant_loom.storage.mysql_client import mysql_client
        from quant_loom.storage.models import StockAlert
        from datetime import datetime

        if not mysql_client.ping():
            raise HTTPException(status_code=503, detail="MySQL unavailable")

        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        with mysql_client.get_session() as sess:
            # 今日总告警数
            total_today = (
                sess.query(func.count(StockAlert.id))
                .filter(StockAlert.ts >= today_start)
                .scalar()
            ) or 0

            # 今日有 AI 分析的告警数 + Top-N 列表
            base_q = sess.query(StockAlert).filter(
                StockAlert.ts >= today_start,
                StockAlert.ai_summary.isnot(None),
                StockAlert.ai_summary != "",
            )

            analyzed_count = base_q.count()

            # MySQL 不支持 NULLS LAST，用 coalesce(score, 0) 替代
            top_alerts = (
                base_q.order_by(func.coalesce(StockAlert.confidence_score, 0).desc())
                .limit(limit)
                .all()
            )

            items = []
            for a in top_alerts:
                item = {
                    "id": a.id,
                    "ts": a.ts.isoformat() if a.ts else None,
                    "code": a.code,
                    "name": a.name,
                    "alert_type": a.alert_type,
                    "risk_level": a.risk_level,
                    "confidence_score": a.confidence_score,
                    "pct_change": float(a.pct_change) if a.pct_change else None,
                    "turnover_amount": float(a.turnover_amount) if a.turnover_amount else None,
                    "trigger_reason": a.trigger_reason,
                    "ai_summary": a.ai_summary,
                }
                # ai_evidence is JSON type — SQLAlchemy may return dict or str
                ev = a.ai_evidence
                if isinstance(ev, str):
                    try:
                        item["ai_evidence"] = json.loads(ev)
                    except (json.JSONDecodeError, TypeError):
                        item["ai_evidence"] = None
                else:
                    item["ai_evidence"] = ev
                items.append(item)

        return JSONResponse(content={
            "total_today": total_today,
            "analyzed_count": analyzed_count,
            "items": items,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Daily analysis query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---- 静态文件 + SPA fallback (Phase 5) ----

_FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")

if os.path.isdir(_FRONTEND_DIR):
    # 挂载 assets 目录
    assets_dir = os.path.join(_FRONTEND_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # 显式路由: 根级静态文件 (必须在 SPA fallback 前注册)
    from fastapi.responses import FileResponse

    def _make_static_handler(file_path: str):
        def handler():
            return FileResponse(file_path)
        return handler

    for _filename in ("config.js", "vite.svg", "favicon.ico", "manifest.json", "sw.js"):
        _file_path = os.path.join(_FRONTEND_DIR, _filename)
        if os.path.isfile(_file_path):
            app.get(f"/{_filename}")(_make_static_handler(_file_path))

    @app.get("/{full_path:path}", response_class=HTMLResponse)
    async def spa_fallback(full_path: str):
        """SPA fallback — 非 /api /health /metrics /feedback 路径返回 index.html"""
        # 已由具体路由处理的路径不会到达这里
        index_path = os.path.join(_FRONTEND_DIR, "index.html")
        if os.path.isfile(index_path):
            return HTMLResponse(open(index_path, "r", encoding="utf-8").read())
        return HTMLResponse("<h1>Frontend not built. Run: cd frontend && npm run build</h1>", status_code=404)


# ---- 持仓管理 (Phase 5C) ----

@app.get("/api/portfolio")
async def api_portfolio_list():
    """持仓列表"""
    try:
        from quant_loom.storage.mysql_client import mysql_client
        from quant_loom.storage.models import PortfolioHolding

        if not mysql_client.ping():
            raise HTTPException(status_code=503, detail="MySQL unavailable")

        with mysql_client.get_session() as sess:
            holdings = sess.query(PortfolioHolding).order_by(PortfolioHolding.created_at.desc()).all()
            items = [
                {
                    "id": h.id,
                    "code": h.code,
                    "name": h.name,
                    "shares": h.shares,
                    "cost_price": float(h.cost_price) if h.cost_price else 0,
                    "created_at": h.created_at.isoformat() if h.created_at else None,
                    "updated_at": h.updated_at.isoformat() if h.updated_at else None,
                }
                for h in holdings
            ]

        return JSONResponse(content={"items": items})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query portfolio failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class PortfolioAddRequest(BaseModel):
    code: str
    name: Optional[str] = None
    shares: int = 0
    cost_price: Optional[float] = None


@app.post("/api/portfolio")
async def api_portfolio_add(req: PortfolioAddRequest):
    """添加持仓"""
    try:
        from quant_loom.storage.mysql_client import mysql_client
        from quant_loom.storage.models import PortfolioHolding

        if not mysql_client.ping():
            raise HTTPException(status_code=503, detail="MySQL unavailable")

        holding = PortfolioHolding(
            code=req.code,
            name=req.name or req.code,
            shares=req.shares,
            cost_price=req.cost_price,
        )
        mysql_client.insert_or_update(holding, lookup_columns=["code"])

        return JSONResponse(content={"status": "ok"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add portfolio failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/portfolio/{holding_id}")
async def api_portfolio_delete(holding_id: int):
    """删除持仓"""
    try:
        from quant_loom.storage.mysql_client import mysql_client
        from quant_loom.storage.models import PortfolioHolding

        if not mysql_client.ping():
            raise HTTPException(status_code=503, detail="MySQL unavailable")

        with mysql_client.get_session() as sess:
            holding = sess.query(PortfolioHolding).filter(PortfolioHolding.id == holding_id).first()
            if not holding:
                raise HTTPException(status_code=404, detail=f"Holding {holding_id} not found")
            sess.delete(holding)
            sess.commit()

        return JSONResponse(content={"status": "ok"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete portfolio failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---- 批量行情查询 (Phase 5C) ----

@app.get("/api/quotes/batch")
async def api_quotes_batch(codes: str = Query(..., description="逗号分隔的股票代码")):
    """批量查询股票最新行情"""
    try:
        from quant_loom.storage.mysql_client import mysql_client
        from quant_loom.storage.models import StockQuoteSnapshot

        if not mysql_client.ping():
            raise HTTPException(status_code=503, detail="MySQL unavailable")

        code_list = [c.strip() for c in codes.split(",") if c.strip()]
        if not code_list:
            return JSONResponse(content={"quotes": {}})

        with mysql_client.get_session() as sess:
            # 每个 code 的最新行情
            quotes = {}
            for code in code_list:
                snap = (
                    sess.query(StockQuoteSnapshot)
                    .filter(StockQuoteSnapshot.code == code)
                    .order_by(StockQuoteSnapshot.ts.desc())
                    .first()
                )
                if snap:
                    quotes[code] = {
                        "last_price": float(snap.last_price) if snap.last_price else None,
                        "pct_change": float(snap.pct_change) if snap.pct_change else None,
                    }

        return JSONResponse(content={"quotes": quotes})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch quotes query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---- 通知重推 (Phase 5D) ----

@app.post("/api/notifications/{log_id}/retry")
async def api_notification_retry(log_id: int):
    """重推失败的通知"""
    try:
        from quant_loom.storage.mysql_client import mysql_client
        from quant_loom.storage.models import NotificationLog

        if not mysql_client.ping():
            raise HTTPException(status_code=503, detail="MySQL unavailable")

        with mysql_client.get_session() as sess:
            log = sess.query(NotificationLog).filter(NotificationLog.id == log_id).first()
            if not log:
                raise HTTPException(status_code=404, detail=f"Notification log {log_id} not found")

            # 重发逻辑：根据 channel 调用对应的 webhook
            success = False
            try:
                from quant_loom.notify.webhook import send_alert_to_channel
                from quant_loom.storage.models import StockAlert

                alert = sess.query(StockAlert).filter(StockAlert.id == log.alert_id).first()
                if alert:
                    alert_dict = {
                        "id": alert.id,
                        "code": alert.code,
                        "name": alert.name,
                        "alert_type": alert.alert_type,
                        "risk_level": alert.risk_level,
                        "trigger_reason": alert.trigger_reason,
                        "confidence_score": alert.confidence_score,
                        "ai_summary": alert.ai_summary,
                    }
                    success = send_alert_to_channel(alert_dict, log.channel)
            except Exception as ex:
                logger.warning(f"Retry send failed: {ex}")

            if success:
                log.status = "success"
                log.error_message = None
                log.sent_at = datetime.now()
                sess.commit()
                return JSONResponse(content={"status": "ok", "message": "重推成功"})
            else:
                log.error_message = f"重推失败 ({datetime.now().strftime('%H:%M:%S')})"
                sess.commit()
                return JSONResponse(content={"status": "failed", "message": "重推失败"}, status_code=502)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Notification retry failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---- 资金流向 Top10 (Phase 5C) ----

@app.get("/api/fund-flow/top")
async def api_fund_flow_top():
    """最新交易日资金流 Top10 — 净流入和净流出 Top10"""
    try:
        from quant_loom.storage.mysql_client import mysql_client
        from quant_loom.storage.models import FundFlowDaily, StockMaster

        if not mysql_client.ping():
            raise HTTPException(status_code=503, detail="MySQL unavailable")

        with mysql_client.get_session() as sess:
            # 最新交易日
            latest_date = (
                sess.query(func.max(FundFlowDaily.trade_date)).scalar()
            )
            if not latest_date:
                return JSONResponse(content={"inflows": [], "outflows": []})

            # 净流入 Top10
            inflows_query = (
                sess.query(
                    FundFlowDaily.code,
                    StockMaster.name,
                    FundFlowDaily.net_inflow,
                    FundFlowDaily.main_force_ratio,
                )
                .outerjoin(StockMaster, FundFlowDaily.code == StockMaster.code)
                .filter(FundFlowDaily.trade_date == latest_date)
                .order_by(FundFlowDaily.net_inflow.desc())
                .limit(10)
                .all()
            )
            inflows = [
                {
                    "code": r.code,
                    "name": r.name or r.code,
                    "net_inflow": float(r.net_inflow) if r.net_inflow else 0,
                    "inflow_ratio": float(r.main_force_ratio) if r.main_force_ratio else 0,
                }
                for r in inflows_query
            ]

            # 净流出 Top10
            outflows_query = (
                sess.query(
                    FundFlowDaily.code,
                    StockMaster.name,
                    FundFlowDaily.net_inflow,
                    FundFlowDaily.main_force_ratio,
                )
                .outerjoin(StockMaster, FundFlowDaily.code == StockMaster.code)
                .filter(FundFlowDaily.trade_date == latest_date)
                .order_by(FundFlowDaily.net_inflow.asc())
                .limit(10)
                .all()
            )
            outflows = [
                {
                    "code": r.code,
                    "name": r.name or r.code,
                    "net_inflow": float(r.net_inflow) if r.net_inflow else 0,
                    "inflow_ratio": float(r.main_force_ratio) if r.main_force_ratio else 0,
                }
                for r in outflows_query
            ]

        return JSONResponse(content={"inflows": inflows, "outflows": outflows})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query fund flow top failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---- 通知日志 (Phase 5C) ----

@app.get("/api/notifications")
async def api_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """分页通知日志列表"""
    try:
        from quant_loom.storage.mysql_client import mysql_client
        from quant_loom.storage.models import NotificationLog

        if not mysql_client.ping():
            raise HTTPException(status_code=503, detail="MySQL unavailable")

        with mysql_client.get_session() as sess:
            total = sess.query(func.count(NotificationLog.id)).scalar() or 0
            logs = (
                sess.query(NotificationLog)
                .order_by(NotificationLog.sent_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            items = [
                {
                    "id": n.id,
                    "alert_id": n.alert_id,
                    "channel": n.channel,
                    "recipient": n.recipient,
                    "status": n.status,
                    "sent_at": n.sent_at.isoformat() if n.sent_at else None,
                    "error_message": n.error_message,
                }
                for n in logs
            ]

        return JSONResponse(content={
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query notifications failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---- 板块热力图 (Phase 5C) ----

@app.get("/api/sectors/heatmap")
async def api_sectors_heatmap():
    """板块告警热力图 — 按行业聚合告警数量与平均置信度"""
    try:
        from quant_loom.storage.mysql_client import mysql_client
        from quant_loom.storage.models import StockAlert, StockMaster

        if not mysql_client.ping():
            raise HTTPException(status_code=503, detail="MySQL unavailable")

        with mysql_client.get_session() as sess:
            rows = (
                sess.query(
                    StockMaster.industry,
                    func.count(StockAlert.id).label("alert_count"),
                    func.avg(StockAlert.confidence_score).label("avg_confidence"),
                )
                .join(StockAlert, StockAlert.code == StockMaster.code)
                .filter(StockMaster.industry.isnot(None), StockMaster.industry != "")
                .group_by(StockMaster.industry)
                .order_by(func.count(StockAlert.id).desc())
                .limit(30)
                .all()
            )
            # 在 session 内材料化
            items = [
                {
                    "sector": r.industry or "未知",
                    "alert_count": r.alert_count,
                    "avg_confidence": round(float(r.avg_confidence or 0), 4),
                }
                for r in rows
            ]

        return JSONResponse(content={"items": items})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query sectors heatmap failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---- 回测统计 (Phase 5B) ----

@app.get("/api/backtest/type-stats")
async def api_backtest_type_stats():
    """按告警类型聚合回测统计 — T+1/3/5 平均收益、命中率、样本数"""
    try:
        from quant_loom.storage.mysql_client import mysql_client
        from quant_loom.storage.models import BacktestResult

        if not mysql_client.ping():
            raise HTTPException(status_code=503, detail="MySQL unavailable")

        with mysql_client.get_session() as sess:
            rows = (
                sess.query(
                    BacktestResult.alert_type,
                    func.avg(BacktestResult.outcome_1d).label("avg_1d"),
                    func.avg(BacktestResult.outcome_3d).label("avg_3d"),
                    func.avg(BacktestResult.outcome_5d).label("avg_5d"),
                    func.count(BacktestResult.id).label("cnt"),
                    func.sum(BacktestResult.outcome_positive.cast(Integer)).label("hits"),
                )
                .filter(BacktestResult.alert_type.isnot(None))
                .group_by(BacktestResult.alert_type)
                .all()
            )
            items = {}
            for r in rows:
                at = r.alert_type or "unknown"
                total = r.cnt or 0
                hit_rate = round(r.hits / total, 4) if total > 0 else 0
                items[at] = {
                    "outcome_1d": round(float(r.avg_1d), 4) if r.avg_1d is not None else None,
                    "outcome_3d": round(float(r.avg_3d), 4) if r.avg_3d is not None else None,
                    "outcome_5d": round(float(r.avg_5d), 4) if r.avg_5d is not None else None,
                    "hit_rate": hit_rate,
                    "sample_count": total,
                    "precision": hit_rate,
                    "calibration": round(hit_rate * 0.7, 4) if hit_rate > 0 else None,
                    "benchmark_3d": None,
                }

        return JSONResponse(content={"by_type": items})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query backtest type stats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
