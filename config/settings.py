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
        """Redis 连接串"""
        pw = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{pw}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def ai_enabled(self) -> bool:
        """是否启用 AI 分析"""
        return bool(self.openai_api_key or self.anthropic_api_key or self.llama_base_url)

    model_config = dict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# 全局单例
settings = Settings()
