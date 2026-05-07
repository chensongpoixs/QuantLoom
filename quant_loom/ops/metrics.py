"""
Prometheus 指标定义

所有指标集中在 quantloom_ 命名空间下。
"""

from prometheus_client import Counter, Gauge, Histogram, Info

# ---- 管线 ----

pipeline_runs = Counter(
    "quantloom_pipeline_runs_total",
    "管线执行总次数",
    ["status"],  # success / failed
)

pipeline_duration = Histogram(
    "quantloom_pipeline_duration_seconds",
    "管线执行耗时 (秒)",
    buckets=(10, 30, 60, 120, 300, 600, float("inf")),
)

# ---- 告警 ----

alerts_produced = Counter(
    "quantloom_alerts_total",
    "产生的告警总数",
    ["risk_level", "alert_type"],
)

# ---- 通知 ----

notifications_sent = Counter(
    "quantloom_notifications_total",
    "通知发送总数",
    ["channel", "status"],  # channel: wecom/feishu/dingtalk/email, status: success/failed
)

# ---- 数据抓取 ----

data_fetch_duration = Histogram(
    "quantloom_data_fetch_duration_seconds",
    "数据抓取耗时 (秒)",
    ["source"],  # xtick / akshare
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, float("inf")),
)

# ---- 外部 API 调用 ----

api_call_duration = Histogram(
    "quantloom_api_call_duration_seconds",
    "外部 API 调用耗时 (秒)",
    ["service"],  # xtick / akshare / openai / anthropic / llama
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, float("inf")),
)

api_errors = Counter(
    "quantloom_api_errors_total",
    "外部 API 调用错误总数",
    ["service", "error_type"],
)

# ---- 健康状态 ----

db_health = Gauge(
    "quantloom_db_health",
    "数据库健康状态 (1=正常, 0=不可用)",
    ["db"],  # mysql / redis
)

# ---- 重试 ----

retry_attempts = Counter(
    "quantloom_retry_attempts_total",
    "重试总次数",
    ["component"],  # network / db
)

# ---- 构建信息 ----

build_info = Info(
    "quantloom_build",
    "QuantLoom 构建信息",
)
build_info.info({"version": "0.4.0", "phase": "4-optimization"})

# ---- 告警质量 (Phase 4) ----

alert_precision = Gauge(
    "quantloom_alert_precision",
    "告警方向精度 (0-1)",
    ["alert_type", "window"],  # window: 1d/3d/5d
)

alert_relevance_score = Histogram(
    "quantloom_alert_relevance_score",
    "人工反馈相关度评分分布",
    ["alert_type"],
    buckets=(0.1, 0.3, 0.5, 0.7, 0.9, 1.0),
)

alert_outcome_correct = Counter(
    "quantloom_alert_outcomes_total",
    "结果方向正确/错误计数",
    ["alert_type", "outcome"],  # outcome: correct/incorrect
)
