"""
FastAPI 应用 — 健康检查 + Prometheus /metrics

Usage:
  uvicorn quant_loom.api.app:app --host 0.0.0.0 --port 9090
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse, JSONResponse
from loguru import logger
from prometheus_client import generate_latest, CollectorRegistry, REGISTRY

from quant_loom.ops.metrics import db_health


# ---- 应用工厂 ----

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期 — 启动/关闭日志"""
    logger.info("FastAPI 服务启动 — /health /metrics 就绪")
    yield
    logger.info("FastAPI 服务关闭")


app = FastAPI(
    title="QuantLoom API",
    version="0.3.0",
    lifespan=lifespan,
)


# ---- 健康检查 ----

def _check_mysql() -> bool:
    """检查 MySQL 连通性"""
    try:
        from quant_loom.storage.mysql_client import mysql_client
        return mysql_client.ping()
    except Exception:
        return False


def _check_redis() -> bool:
    """检查 Redis 连通性"""
    try:
        from quant_loom.storage.redis_client import redis_client
        return redis_client.ping()
    except Exception:
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
