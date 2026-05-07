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
    logger.warning("redis 模块未安装，Redis 功能将不可用")


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
                logger.warning(f"Redis 连接失败: {e}")
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
            logger.error(f"Redis ping 失败: {e}")
            return False

    # ---- 缓存 ----

    def cache_set(self, key: str, value: str, ttl: int = 300) -> None:
        """设置缓存，默认 TTL 5 分钟"""
        c = self.client
        if c:
            c.setex(key, ttl, value)

    def cache_get(self, key: str) -> Optional[str]:
        """获取缓存"""
        c = self.client
        if c:
            v = c.get(key)
            return v.decode() if v else None
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
        return bool(c.exists(key))

    def mark_alert_sent(self, code: str, alert_type: str, cooldown_minutes: int = 30) -> None:
        """标记告警已发送，设置冷却期"""
        c = self.client
        if c is None:
            return
        key = self.alert_key(code, alert_type)
        ttl = cooldown_minutes * 60
        c.setex(key, ttl, "1")


# 全局单例
redis_client = RedisClient()
