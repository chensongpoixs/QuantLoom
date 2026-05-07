"""
集中化重试策略
为外部 API / 数据库 / 网络调用提供无侵入式重试装饰器

使用 tenacity 实现指数退避 + 抖动，确保瞬态故障不丢数据。

Usage:
    from quant_loom.ops.retry import network_retry, db_retry

    @network_retry
    def call_external_api():
        ...
"""

from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

import requests
from sqlalchemy.exc import OperationalError


# ---- 重试策略定义 ----

NETWORK_RETRY_KWARGS = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((
        requests.ConnectionError,
        requests.Timeout,
        requests.RequestException,
    )),
    before_sleep=before_sleep_log(logger, "WARNING"),
    reraise=True,
)

DB_RETRY_KWARGS = dict(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type((OperationalError,)),
    before_sleep=before_sleep_log(logger, "WARNING"),
    reraise=True,
)


def network_retry(func):
    """网络请求重试: 3 次, 指数退避 2s→4s→8s, 目标 ConnectionError/Timeout"""
    return retry(**NETWORK_RETRY_KWARGS)(func)


def db_retry(func):
    """数据库操作重试: 2 次, 指数退避, 目标 OperationalError"""
    return retry(**DB_RETRY_KWARGS)(func)
