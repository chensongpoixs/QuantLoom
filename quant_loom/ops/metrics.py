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
    "QuantLoom·量梭 构建信息",
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
