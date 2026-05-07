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
Redis 缓存与去重客户端
Redis 为可选依赖：未安装或不可用时自动降级为空操作
"""

from typing import Optional

from loguru import logger

from config.settings import settings

try:
    import redis as _redis
    HAS_REDIS = True
except ImportError:
    _redis = None
    HAS_REDIS = False
    logger.warning("redis module not installed, Redis features unavailable")


class RedisClient:
    """Redis 客户端（可选依赖）"""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if not HAS_REDIS:
            return None
        if self._client is None:
            try:
                pool = _redis.ConnectionPool(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    password=settings.redis_password or None,
                    db=settings.redis_db,
                    max_connections=20,
                )
                self._client = _redis.Redis(connection_pool=pool)
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}")
                return None
        return self._client

    def ping(self) -> bool:
        """测试连接"""
        c = self.client
        if c is None:
            return False
        try:
            return c.ping()
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False

    # ---- 缓存 ----

    def cache_set(self, key: str, value: str, ttl: int = 300) -> None:
        """设置缓存，默认 TTL 5 分钟"""
        c = self.client
        if c:
            try:
                c.setex(key, ttl, value)
            except Exception as e:
                logger.warning(f"Redis cache_set failed: {e}")
                self._client = None

    def cache_get(self, key: str) -> Optional[str]:
        """获取缓存"""
        c = self.client
        if c:
            try:
                v = c.get(key)
                return v.decode() if v else None
            except Exception as e:
                logger.warning(f"Redis cache_get failed: {e}")
                self._client = None
        return None

    # ---- 告警去重 ----

    def alert_key(self, code: str, alert_type: str) -> str:
        """生成去重 key"""
        return f"alert_dedup:{code}:{alert_type}"

    def is_duplicate(self, code: str, alert_type: str, cooldown_minutes: int = 30) -> bool:
        """
        检查是否重复告警
        返回 True 表示在冷却期内，应跳过
        """
        c = self.client
        if c is None:
            return False
        key = self.alert_key(code, alert_type)
        try:
            return bool(c.exists(key))
        except Exception as e:
            logger.warning(f"Redis is_duplicate failed: {e}")
            self._client = None  # 标记不可用，下次走 None 分支
            return False

    def mark_alert_sent(self, code: str, alert_type: str, cooldown_minutes: int = 30) -> None:
        """标记告警已发送，设置冷却期"""
        c = self.client
        if c is None:
            return
        key = self.alert_key(code, alert_type)
        ttl = cooldown_minutes * 60
        try:
            c.setex(key, ttl, "1")
        except Exception as e:
            logger.warning(f"Redis mark_alert_sent failed: {e}")
            self._client = None


# 全局单例
redis_client = RedisClient()
