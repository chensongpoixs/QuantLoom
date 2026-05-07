#!/usr/bin/env python3
"""
初始化数据库 — 创建所有表
用法: python scripts/init_db.py
"""

import sys
from pathlib import Path

# 将项目根目录加入 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger

from quant_loom.storage.mysql_client import mysql_client


def main():
    logger.info("正在初始化数据库...")

    if not mysql_client.ping():
        logger.error("MySQL 连接失败，请检查配置")
        sys.exit(1)

    mysql_client.create_tables()
    logger.info("数据库初始化完成")


if __name__ == "__main__":
    main()
