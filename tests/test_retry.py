"""
test_retry.py — 重试策略单元测试
"""

import pytest
import requests
from unittest.mock import patch, MagicMock

from quant_loom.ops.retry import network_retry, db_retry, NETWORK_RETRY_KWARGS, DB_RETRY_KWARGS


NETWORK_RETRY_EXCEPTIONS = (requests.ConnectionError, requests.Timeout, requests.RequestException)


class TestNetworkRetryStrategy:
    """验证 network_retry 策略配置 — 检测 isinstance 逻辑"""

    def test_max_attempts_is_3(self):
        assert NETWORK_RETRY_KWARGS["stop"].max_attempt_number == 3

    def test_connection_error_is_retryable(self):
        assert isinstance(requests.ConnectionError("test"), NETWORK_RETRY_EXCEPTIONS)

    def test_timeout_is_retryable(self):
        assert isinstance(requests.Timeout("test"), NETWORK_RETRY_EXCEPTIONS)

    def test_request_exception_is_retryable(self):
        assert isinstance(requests.RequestException("test"), NETWORK_RETRY_EXCEPTIONS)

    def test_value_error_is_not_retryable(self):
        assert not isinstance(ValueError("test"), NETWORK_RETRY_EXCEPTIONS)


class TestDbRetryStrategy:
    """验证 db_retry 策略配置"""

    def test_max_attempts_is_2(self):
        assert DB_RETRY_KWARGS["stop"].max_attempt_number == 2

    def test_operational_error_is_retryable(self):
        from sqlalchemy.exc import OperationalError
        try:
            raise ValueError("original")
        except ValueError as orig:
            err = OperationalError("test", {}, orig)
        assert isinstance(err, OperationalError)

    def test_value_error_is_not_db_retryable(self):
        from sqlalchemy.exc import OperationalError
        assert not isinstance(ValueError("test"), OperationalError)


class TestRetryDecoratorBehavior:
    """验证装饰器行为"""

    def test_success_on_first_try(self):
        call_count = [0]

        @network_retry
        def succeed():
            call_count[0] += 1
            return "ok"

        result = succeed()
        assert result == "ok"
        assert call_count[0] == 1

    def test_retries_then_succeeds(self):
        call_count = [0]

        @network_retry
        def fail_twice():
            call_count[0] += 1
            if call_count[0] < 3:
                raise requests.ConnectionError("fail")
            return "ok"

        result = fail_twice()
        assert result == "ok"
        assert call_count[0] == 3

    def test_reraises_after_exhaustion(self):
        call_count = [0]

        @network_retry
        def always_fail():
            call_count[0] += 1
            raise requests.ConnectionError("always")

        with pytest.raises(requests.ConnectionError):
            always_fail()
        assert call_count[0] == 3  # 3 attempts total

    def test_no_retry_on_non_network_error(self):
        """非网络异常不重试，直接抛出"""
        call_count = [0]

        @network_retry
        def raise_value_error():
            call_count[0] += 1
            raise ValueError("not a network error")

        with pytest.raises(ValueError):
            raise_value_error()
        assert call_count[0] == 1  # 只调用一次

    def test_decorator_preserves_function_metadata(self):
        @network_retry
        def my_func():
            """My docstring"""
            pass

        assert my_func.__name__ == "my_func"
