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
        except Exception as e:
            logger.warning(f"DB session error, rolling back: {e}")
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
            logger.error(f"MySQL ping failed: {e}")
            return False

    def create_tables(self):
        """创建所有表（由 models 定义）"""
        from quant_loom.storage.models import Base

        Base.metadata.create_all(self.engine)
        logger.info("MySQL tables created")

    def insert_or_update(self, instance):
        """插入或更新单条记录，返回 merged instance (含 auto-increment ID)"""
        with self.get_session() as s:
            merged = s.merge(instance)
            s.flush()
            return merged

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
