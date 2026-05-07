"""
MySQL 连接管理
基于 SQLAlchemy 2.0，提供 session 工厂和常用 CRUD 操作
"""

from contextlib import contextmanager
from typing import Optional

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from config.settings import settings


class MySQLClient:
    """MySQL 数据库客户端"""

    def __init__(self):
        self._engine = None
        self._session_factory = None

    @property
    def engine(self):
        if self._engine is None:
            self._engine = create_engine(
                settings.mysql_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,      # 自动检测连接有效性
                pool_recycle=3600,       # 1小时回收连接
                echo=False,
            )
        return self._engine

    @property
    def session(self) -> sessionmaker:
        if self._session_factory is None:
            self._session_factory = sessionmaker(bind=self.engine)
        return self._session_factory

    @contextmanager
    def get_session(self) -> Session:
        """获取数据库 session，自动关闭"""
        s = self.session()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    def ping(self) -> bool:
        """测试数据库连接"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"MySQL ping 失败: {e}")
            return False

    def create_tables(self):
        """创建所有表（由 models 定义）"""
        from quant_loom.storage.models import Base

        Base.metadata.create_all(self.engine)
        logger.info("MySQL 表创建完成")

    def insert_or_update(self, instance) -> None:
        """插入或更新单条记录"""
        with self.get_session() as s:
            s.merge(instance)

    def bulk_insert(self, instances: list) -> None:
        """批量插入"""
        with self.get_session() as s:
            s.bulk_save_objects(instances)

    def query_alerts(self, code: Optional[str] = None, alert_type: Optional[str] = None, limit: int = 100):
        """查询告警记录"""
        from quant_loom.storage.models import StockAlert

        with self.get_session() as s:
            q = s.query(StockAlert)
            if code:
                q = q.filter(StockAlert.code == code)
            if alert_type:
                q = q.filter(StockAlert.alert_type == alert_type)
            return q.order_by(StockAlert.ts.desc()).limit(limit).all()


# 全局单例
mysql_client = MySQLClient()
