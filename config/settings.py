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
全局配置管理
从环境变量 /.env 文件加载，使用 pydantic-settings 做校验
"""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """应用全局配置"""

    # --- MySQL ---
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "quant_loom"

    # --- Redis ---
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    # --- AI / LLM ---
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # --- llama.cpp (OpenAI 兼容 HTTP API) ---
    llama_base_url: str = ""      # e.g. http://localhost:8080/v1
    llama_model: str = ""         # e.g. qwen3-32b
    llama_api_key: str = "not-needed"  # llama.cpp 默认不需要 key

    # --- Celery ---
    # Worker 就绪后是否立即投递一次全市场扫描（不等 Beat 下一个周期）
    celery_scan_on_worker_startup: bool = True

    # --- 数据源 ---
    # "xtick" = XTick HTTP API (推荐, 需 token)
    # "akshare" = AkShare / 东方财富 (免费, 但可能网络受限)
    data_source: str = "xtick"

    # --- XTick ---
    xtick_token: str = ""           # xtick.top 注册获取 token
    xtick_api_url: str = "http://api.xtick.top/doc/market"

    # --- 事件抓取 ---
    event_fetch_enabled: bool = True     # 是否启用事件抓取 (新闻/公告/研报)
    event_lookback_days: int = 3         # 事件回溯天数

    # --- 通知 ---
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    alert_email_to: str = ""
    wecom_webhook_url: str = ""
    feishu_webhook_url: str = ""
    dingtalk_webhook_url: str = ""

    # --- 日志 ---
    log_level: str = "INFO"
    log_file: str = "logs/whale_watcher.log"

    @property
    def mysql_url(self) -> str:
        """SQLAlchemy MySQL 连接串"""
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            "?charset=utf8mb4"
        )

    @property
    def redis_url(self) -> str:
        """Redis 连接串 (不含 DB 编号，由调用方追加)"""
        pw = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{pw}{self.redis_host}:{self.redis_port}"

    @property
    def ai_enabled(self) -> bool:
        """是否启用 AI 分析"""
        return bool(self.openai_api_key or self.anthropic_api_key or self.llama_base_url)

    model_config = dict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# 全局单例
settings = Settings()
