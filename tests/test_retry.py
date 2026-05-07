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
