-- ============================================================
-- QuantLoom 数据库初始化 DDL
-- 数据库: MySQL 8.0+
-- ============================================================

CREATE DATABASE IF NOT EXISTS quant_loom
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE quant_loom;

-- 1. 股票基础信息表
CREATE TABLE IF NOT EXISTS sq_stock_master (
    code VARCHAR(10) NOT NULL COMMENT '股票代码',
    name VARCHAR(50) NOT NULL COMMENT '股票名称',
    exchange VARCHAR(10) NOT NULL COMMENT '交易所: sh/sz/bj',
    industry VARCHAR(50) COMMENT '所属行业',
    list_date DATE COMMENT '上市日期',
    status VARCHAR(20) DEFAULT 'active' COMMENT '状态',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. 行情快照表
CREATE TABLE IF NOT EXISTS sq_stock_quote_snapshot (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    ts DATETIME NOT NULL COMMENT '快照时间',
    code VARCHAR(10) NOT NULL COMMENT '股票代码',
    last_price DECIMAL(18, 4) COMMENT '最新价',
    pct_change DECIMAL(10, 4) COMMENT '涨跌幅(%)',
    volume BIGINT COMMENT '成交量(股)',
    turnover_amount DECIMAL(20, 4) COMMENT '成交额',
    turnover_rate DECIMAL(10, 4) COMMENT '换手率(%)',
    limit_status VARCHAR(20) COMMENT '涨跌停状态',
    source VARCHAR(30) COMMENT '数据来源',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_quote_ts_code (ts, code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. 资金流记录表
CREATE TABLE IF NOT EXISTS sq_stock_fund_flow (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    ts DATETIME NOT NULL COMMENT '记录时间',
    code VARCHAR(10) NOT NULL COMMENT '股票代码',
    super_large_net_inflow DECIMAL(20, 4) COMMENT '超大单净流入',
    large_net_inflow DECIMAL(20, 4) COMMENT '大单净流入',
    medium_net_inflow DECIMAL(20, 4) COMMENT '中单净流入',
    small_net_inflow DECIMAL(20, 4) COMMENT '小单净流入',
    inflow_ratio DECIMAL(10, 4) COMMENT '净流入占比(%)',
    source VARCHAR(30) COMMENT '数据来源',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_flow_ts_code (ts, code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. 异动事件表
CREATE TABLE IF NOT EXISTS sq_stock_alerts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    ts DATETIME NOT NULL COMMENT '触发时间',
    code VARCHAR(10) NOT NULL COMMENT '股票代码',
    name VARCHAR(50) COMMENT '股票名称',
    alert_type VARCHAR(50) COMMENT '异动类型',
    trigger_reason TEXT COMMENT '触发原因描述',
    net_inflow_amount DECIMAL(20, 4) COMMENT '净流入金额',
    inflow_ratio DECIMAL(10, 4) COMMENT '净流入占比(%)',
    confidence_score DOUBLE COMMENT '置信度 0-1',
    risk_level VARCHAR(20) COMMENT '风险等级',
    ai_summary TEXT COMMENT 'AI 分析摘要',
    ai_evidence JSON COMMENT 'AI 分析证据',
    is_sent TINYINT(1) DEFAULT 0 COMMENT '是否已推送',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_alerts_ts_code (ts, code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. 通知发送日志表
CREATE TABLE IF NOT EXISTS sq_notification_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    alert_id BIGINT COMMENT '关联告警 ID',
    channel VARCHAR(20) COMMENT '通知渠道',
    recipient VARCHAR(100) COMMENT '接收方',
    status VARCHAR(20) COMMENT '发送状态',
    sent_at DATETIME COMMENT '发送时间',
    error_message TEXT COMMENT '失败原因',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. 股票事件表 (新闻/公告/研报)
CREATE TABLE IF NOT EXISTS sq_stock_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    code VARCHAR(10) NOT NULL COMMENT '股票代码',
    event_type VARCHAR(20) NOT NULL COMMENT '事件类型: news/announcement/report',
    title VARCHAR(500) NOT NULL COMMENT '标题',
    content TEXT COMMENT '内容摘要',
    source VARCHAR(100) COMMENT '来源: eastmoney/cls/jinshi/sina',
    url VARCHAR(500) COMMENT '原文链接',
    published_at DATETIME NOT NULL COMMENT '发布时间',
    sentiment_score DOUBLE COMMENT '情感评分 -1 到 1',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_evt_code_pub (code, published_at),
    INDEX idx_evt_type_pub (event_type, published_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. 每日资金流累积表 (历史特征计算)
CREATE TABLE IF NOT EXISTS sq_fund_flow_daily (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    code VARCHAR(10) NOT NULL COMMENT '股票代码',
    trade_date DATE NOT NULL COMMENT '交易日期',
    super_large_net_inflow DECIMAL(20, 4) DEFAULT 0 COMMENT '超大单净流入',
    large_net_inflow DECIMAL(20, 4) DEFAULT 0 COMMENT '大单净流入',
    medium_net_inflow DECIMAL(20, 4) DEFAULT 0 COMMENT '中单净流入',
    small_net_inflow DECIMAL(20, 4) DEFAULT 0 COMMENT '小单净流入',
    main_force_ratio DECIMAL(10, 4) DEFAULT 0 COMMENT '主力净流入占比(%)',
    net_inflow DECIMAL(20, 4) DEFAULT 0 COMMENT '总净流入',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    UNIQUE INDEX uk_ffd_code_date (code, trade_date),
    INDEX idx_ffd_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
