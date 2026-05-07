"""
结构化日志系统
基于 loguru，输出 JSON 格式日志，每个告警带唯一 trace_id
"""

import sys
import uuid
from pathlib import Path

from loguru import logger

from config.settings import settings


def setup_logging():
    """初始化日志系统"""
    logger.remove()  # 移除默认 handler

    # 控制台输出 — 人类可读格式
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>",
        colorize=True,
    )

    # 文件输出 — JSON 结构
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        log_path,
        level="DEBUG",
        format="{time} | {level} | {name}:{function}:{line} | {message}",
        rotation="10 MB",
        retention="7 days",
        encoding="utf-8",
    )

    logger.info(f"日志系统已初始化, level={settings.log_level}, file={log_path}")


def get_trace_id() -> str:
    """生成唯一 trace_id"""
    return uuid.uuid4().hex[:16]


# 自动初始化
setup_logging()
