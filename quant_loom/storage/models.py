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
SQLAlchemy ORM 模型定义
对应 MySQL 数据库中的 7 张核心表
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Index,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class StockMaster(Base):
    """股票基础信息表"""

    __tablename__ = "sq_stock_master"

    code = Column(String(10), primary_key=True, comment="股票代码")
    name = Column(String(50), nullable=False, comment="股票名称")
    exchange = Column(String(10), nullable=False, comment="交易所: sh/sz/bj")
    industry = Column(String(50), comment="所属行业")
    list_date = Column(DateTime, comment="上市日期")
    status = Column(String(20), default="active", comment="状态: active/suspended/delisted")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class StockQuoteSnapshot(Base):
    """行情快照表"""

    __tablename__ = "sq_stock_quote_snapshot"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False, comment="快照时间")
    code = Column(String(10), nullable=False, comment="股票代码")
    last_price = Column(Numeric(18, 4), comment="最新价")
    pct_change = Column(Numeric(10, 4), comment="涨跌幅(%)")
    volume = Column(BigInteger, comment="成交量(股)")
    turnover_amount = Column(Numeric(20, 4), comment="成交额")
    turnover_rate = Column(Numeric(10, 4), comment="换手率(%)")
    limit_status = Column(String(20), comment="涨跌停状态")
    source = Column(String(30), comment="数据来源")
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("idx_quote_ts_code", "ts", "code"),
    )


class StockFundFlow(Base):
    """资金流记录表"""

    __tablename__ = "sq_stock_fund_flow"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False, comment="记录时间")
    code = Column(String(10), nullable=False, comment="股票代码")
    super_large_net_inflow = Column(Numeric(20, 4), comment="超大单净流入")
    large_net_inflow = Column(Numeric(20, 4), comment="大单净流入")
    medium_net_inflow = Column(Numeric(20, 4), comment="中单净流入")
    small_net_inflow = Column(Numeric(20, 4), comment="小单净流入")
    inflow_ratio = Column(Numeric(10, 4), comment="净流入占比(%)")
    source = Column(String(30), comment="数据来源")
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("idx_flow_ts_code", "ts", "code"),
    )


class StockAlert(Base):
    """异动事件表"""

    __tablename__ = "sq_stock_alerts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False, comment="触发时间")
    code = Column(String(10), nullable=False, comment="股票代码")
    name = Column(String(50), comment="股票名称")
    alert_type = Column(String(50), comment="异动类型")
    trigger_reason = Column(Text, comment="触发原因描述")
    net_inflow_amount = Column(Numeric(20, 4), comment="净流入金额")
    inflow_ratio = Column(Numeric(10, 4), comment="净流入占比(%)")
    confidence_score = Column(Float, comment="置信度 0-1")
    risk_level = Column(String(20), comment="风险等级: P1/P2/P3")
    ai_summary = Column(Text, comment="AI 分析摘要")
    ai_evidence = Column(JSON, comment="AI 分析证据 JSON")
    is_sent = Column(Boolean, default=False, comment="是否已推送")
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("idx_alerts_ts_code", "ts", "code"),
    )


class NotificationLog(Base):
    """通知发送日志表"""

    __tablename__ = "sq_notification_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    alert_id = Column(BigInteger, comment="关联告警 ID")
    channel = Column(String(20), comment="通知渠道")
    recipient = Column(String(100), comment="接收方")
    status = Column(String(20), comment="发送状态: success/failed")
    sent_at = Column(DateTime, comment="发送时间")
    error_message = Column(Text, comment="失败原因")
    created_at = Column(DateTime, default=datetime.now)


class StockEvent(Base):
    """股票事件表 — 新闻/公告/研报"""

    __tablename__ = "sq_stock_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False, comment="股票代码")
    event_type = Column(String(20), nullable=False, comment="事件类型: news/announcement/report")
    title = Column(String(500), nullable=False, comment="标题")
    content = Column(Text, comment="内容摘要")
    source = Column(String(100), comment="来源: eastmoney/cls/jinshi/sina")
    url = Column(String(500), comment="原文链接")
    published_at = Column(DateTime, nullable=False, comment="发布时间")
    sentiment_score = Column(Float, comment="情感评分 -1 到 1")
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("idx_evt_code_pub", "code", "published_at"),
        Index("idx_evt_type_pub", "event_type", "published_at"),
    )


class FundFlowDaily(Base):
    """每日资金流累积表 — 用于计算连续流入天数等历史特征"""

    __tablename__ = "sq_fund_flow_daily"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False, comment="股票代码")
    trade_date = Column(Date, nullable=False, comment="交易日期")
    super_large_net_inflow = Column(Numeric(20, 4), default=0)
    large_net_inflow = Column(Numeric(20, 4), default=0)
    medium_net_inflow = Column(Numeric(20, 4), default=0)
    small_net_inflow = Column(Numeric(20, 4), default=0)
    main_force_ratio = Column(Numeric(10, 4), default=0)
    net_inflow = Column(Numeric(20, 4), default=0)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("uk_ffd_code_date", "code", "trade_date", unique=True),
        Index("idx_ffd_date", "trade_date"),
    )


class BacktestResult(Base):
    """回测结果表 — 存储历史回测的告警与后续表现"""

    __tablename__ = "sq_backtest_results"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False, comment="交易日期")
    code = Column(String(10), nullable=False, comment="股票代码")
    name = Column(String(50), comment="股票名称")
    alert_type = Column(String(50), comment="异动类型")
    trigger_reason = Column(Text, comment="触发原因描述")
    confidence_score = Column(Float, comment="规则置信度")
    pct_change_alert = Column(Numeric(10, 4), comment="异动当日涨跌幅(%)")
    main_force_ratio = Column(Numeric(10, 4), comment="异动当日主力占比(%)")
    outcome_1d = Column(Numeric(10, 4), comment="T+1 涨跌幅(%)")
    outcome_3d = Column(Numeric(10, 4), comment="T+3 涨跌幅(%)")
    outcome_5d = Column(Numeric(10, 4), comment="T+5 涨跌幅(%)")
    outcome_positive = Column(Boolean, comment="T+3 方向正确 (涨价涨/跌价跌)")
    params_hash = Column(String(64), comment="参数组合 MD5 哈希 (用于缓存)")
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("idx_bktr_date_code", "trade_date", "code"),
        Index("idx_bktr_hash", "params_hash", "trade_date"),
    )


class AlertFeedback(Base):
    """告警反馈表 — 人工复核 + 自动结果回填"""

    __tablename__ = "sq_alert_feedback"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    alert_id = Column(BigInteger, nullable=False, comment="关联告警 ID (sq_stock_alerts.id)")
    feedback_type = Column(String(20), default="manual", comment="反馈类型: manual/auto")
    reviewer = Column(String(50), comment="评审人")
    verdict = Column(String(20), comment="评审结论: correct/incorrect/ambiguous")
    relevance_score = Column(Float, comment="相关度评分 0-1")
    outcome_1d = Column(Numeric(10, 4), comment="告警 1 日后涨跌幅(%)")
    outcome_3d = Column(Numeric(10, 4), comment="告警 3 日后涨跌幅(%)")
    outcome_5d = Column(Numeric(10, 4), comment="告警 5 日后涨跌幅(%)")
    notes = Column(Text, comment="备注")
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("idx_af_alert_id", "alert_id"),
        Index("idx_af_verdict", "verdict"),
    )
