# QuantLoom

> 全市场 A 股机构动向 AI 监控与预警系统

对 A 股全市场 5000+ 标的进行实时扫描，通过**规则引擎 + AI 归因**识别机构资金异动，支持盘中预警与收盘日报推送。

**免责声明**：系统输出仅供研究参考，不构成投资建议。

---

## 系统架构

```text
                   ┌─────────────────────────┐
                   │      通知层              │
                   │  邮件 / 企业微信 / 飞书   │
                   └───────────┬─────────────┘
                               │
┌──────────┐    ┌──────────┐   ▼   ┌──────────┐    ┌──────────┐
│XTick/AK  │───▶│ 采集层   │──▶│ 清洗层   │──▶│ 特征层   │
│Share双源  │    │          │   │          │   │          │
└──────────┘    └──────────┘   └──────────┘   └─────┬────┘
                                                    │
              ┌─────────────────────────────────────┤
              ▼                                     ▼
    ┌─────────────────┐                   ┌─────────────────┐
    │   规则引擎       │                   │   AI 分析层     │
    │ 五类异动信号     │                   │  LLM 归因评分    │
    └────────┬────────┘                   └────────┬────────┘
             │                                     │
             └──────────────┬──────────────────────┘
                            ▼
                   ┌─────────────────┐
                   │   存储层         │
                   │ MySQL + Redis   │
                   └─────────────────┘
```

**核心原则**：规则负责"是否值得看"，AI 负责"为什么值得看"。

### 五类异动信号

| 类型 | 说明 | 关键指标 |
|------|------|---------|
| 放量上攻 | 涨幅适中 + 成交额放大 + 主力净流入 | 涨幅、成交额、量比、超大单占比 |
| 底部吸筹 | 250日低位 + 连续流入 + 波动收敛 | 距离低点、连续流入天数、主力占比 |
| 尾盘抢筹 | 14:30 后资金突增 + 主动买盘 | 尾盘成交占比、主动买盘比 |
| 事件驱动 | 公告/政策/新闻 + 资金共振 | 涨跌、成交额、主力占比 + 事件确认 |
| 板块联动 | 行业板块整体抬升 | 板块平均涨幅、同步上涨家数 |

### 数据分层

```
ODS (原始) → DWD (清洗明细) → DWS (聚合宽表) → ADS (告警结果)
```

---

## 项目结构

```
quant_loom/
├── config/
│   ├── settings.py              # 全局配置 (环境变量)
│   └── rules.yaml               # 规则阈值 (可调参)
├── quant_loom/
│   ├── data_ingestion/          # 采集层
│   │   ├── xtick_fetcher.py     #   XTick 行情/K线抓取
│   │   ├── akshare_fetcher.py   #   AkShare 东方财富数据抓取
│   │   └── cleaner.py           #   停牌过滤、异常值检测
│   ├── feature_engineering/     # 特征层
│   │   ├── fund_flow.py         #   资金流特征
│   │   └── price.py             #   价格特征
│   ├── rule_engine/             # 规则层
│   │   ├── rules.py             #   五类异动规则
│   │   ├── scanner.py           #   全市场扫描器
│   │   └── dedup.py             #   Redis 去重
│   ├── ai_analyzer/             # AI 分析层
│   │   └── llm_client.py        #   LLM 调用 (OpenAI/Anthropic/llama.cpp)
│   ├── notification/            # 通知层
│   │   ├── email_sender.py      #   HTML 邮件日报
│   │   └── webhook.py           #   企业微信/飞书推送
│   ├── storage/                 # 存储层
│   │   ├── models.py            #   ORM 模型 (7表)
│   │   ├── mysql_client.py      #   MySQL 连接管理
│   │   └── redis_client.py      #   Redis 缓存/去重
│   └── ops/                     # 运维层
│       └── logger.py            #   结构化日志
├── scripts/
│   ├── init_db.sql              # 建表 DDL (7张表)
│   ├── init_db.py               # 建表脚本
│   └── run_scanner.py           # 一键运行入口
├── tests/
│   ├── test_rule_engine.py       # 规则引擎 (18 tests)
│   ├── test_cleaner.py           # 数据清洗 (9 tests)
│   ├── test_dedup.py             # 告警去重 (6 tests)
│   ├── test_fund_flow.py         # 资金流特征 (19 tests)
│   ├── test_price.py             # 价格特征 (14 tests)
│   ├── test_scanner.py           # 全市场扫描器 (9 tests)
│   ├── test_event_fetcher.py     # 事件抓取 (11 tests)
│   ├── test_event_matcher.py     # 事件匹配 (11 tests)
│   └── test_rag_store.py         # RAG 存储 (7 tests)
├── requirements.txt
├── .env.example
└── README.md
```

---

## 快速开始

### 1. 环境准备

```bash
# 创建 Conda 环境
conda create -n quant_loom python=3.12
conda activate quant_loom

# 安装依赖
#pip install -r requirements.txt 
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple  
```

### 2. 配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入数据源 / MySQL / Redis 连接信息
# 至少需要配置:
#   DATA_SOURCE=xtick      # 数据源: "xtick" (需 token) 或 "akshare" (免费)
#   XTICK_TOKEN            # http://www.xtick.top 注册获取 (仅 xtick 模式)
#   MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
#   REDIS_HOST, REDIS_PORT
```

### 3. 初始化数据库

```bash
# 方式一：Python 脚本（推荐）
python scripts/init_db.py

# 方式二：直接执行 SQL
mysql -u root -p < scripts/init_db.sql
```

### 4. 运行扫描

```bash
# 执行完整流程：抓取 → 清洗 → 扫描 → AI分析 → 入库 → 通知
python scripts/run_scanner.py

# 控制 AI 分析数量
python scripts/run_scanner.py --top 20     # AI 分析 top 20
python scripts/run_scanner.py --top 0      # 跳过 AI 分析

# 仅扫描不写库（测试用）
python scripts/run_scanner.py --dry-run
# 跳过事件抓取
python scripts/run_scanner.py --skip-events
```

### 5. 运行测试

```bash
pytest tests/ -v                          # 全部 107 个测试

# 带覆盖率
pytest tests/ -v --cov=quant_loom --cov-report=term-missing
```

---

## 配置说明

### 规则阈值 (`config/rules.yaml`)

所有异动判定阈值均为配置化，无需修改代码即可调整：

```yaml
scan_rules:
  min_turnover_amount: 100000000        # 最小成交额 1亿
  pct_change_min: 2                     # 最小涨幅 2%
  super_large_inflow_ratio_min: 20      # 超大单净流入占比最低 20%
  consecutive_inflow_days_min: 3        # 连续净流入天数
  alert_cooldown_minutes: 30            # 冷却时间

  breakout:              # 放量上攻
    enabled: true
    volume_ratio_min: 1.5
    ...
  accumulation:           # 底部吸筹
    enabled: true
    consecutive_inflow_days_min: 3      # 从历史数据计算连续流入天数
    ...
```

### 告警分级

| 级别 | 含义 | 推送方式 |
|------|------|---------|
| P1 | 高置信度，资金与事件共振 | 即时推送 (webhook) |
| P2 | 中等置信度 | 进入观察池 |
| P3 | 弱信号 | 仅入库 |

### AI 分析输出格式

每个触发标的的 AI 分析输出统一 JSON 结构：

```json
{
  "summary": "一句话逻辑",
  "reason_type": "policy / restructuring / technical / industry / sentiment / unknown",
  "confidence_score": 0.0,
  "risk_points": ["..."],
  "evidence": ["..."],
  "action": "watch / review / ignore"
}
```

---

## 数据库

### MySQL 表结构 (7 张核心表)

| 表名 | 说明 | 数据层 |
|------|------|-------|
| `sq_stock_master` | 股票基础信息 | ODS |
| `sq_stock_quote_snapshot` | 行情快照 | DWD |
| `sq_stock_fund_flow` | 资金流记录 | DWD |
| `sq_stock_alerts` | 异动事件 | ADS |
| `sq_notification_log` | 通知发送日志 | ADS |
| `sq_stock_events` | 事件数据 (新闻/公告/研报) | ODS |
| `sq_fund_flow_daily` | 每日资金流累积 (历史特征) | DWS |

### Redis 用途

- 实时行情缓存 (TTL 5分钟)
- 告警去重标记 (同股票同原因冷却期内不重复)
- 限流状态

---

## 实施路线图

### 第 1 阶段：原型验证 ✅

- [x] XTick + AkShare 双数据源可配置切换
- [x] 行情与资金流数据抓取与清洗
- [x] MySQL 数据库建模 (7 张核心表)
- [x] 五类异动规则引擎 (YAML 配置化)
- [x] 全市场扫描器 (含资金流代理、近低位计算)
- [x] LLM 结构化归因 (llama.cpp / OpenAI / Anthropic 三选一)
- [x] Redis 告警去重 (可选, 优雅降级)
- [x] Webhook 实时推送 + 邮件通知
- [x] 结构化 JSON 日志 (trace_id 贯穿全链路)
- [x] 107 个单元测试全部通过

### 第 2 阶段：增强分析 ✅

- [x] 接入公告、新闻、研报数据 (`event_fetcher.py`)
- [x] 实现 RAG 检索 (`rag_store.py`)
- [x] 事件匹配 + LLM 相关性排序 (`event_matcher.py`)
- [x] 历史资金流累积 + 真实连续流入天数 (`sq_fund_flow_daily`)
- [x] LLM 分析 prompt 含真实事件上下文
- [x] LLM 请求/响应完整日志 (`_log_request` / `_log_response` / `_log_completion`)

### 第 3 阶段：生产化

- [ ] 引入 Celery 任务队列
- [ ] 增加 Prometheus 指标监控
- [ ] 完成邮件/飞书/钉钉通知
- [ ] 增加失败重试与降级策略

### 第 4 阶段：优化迭代

- [ ] 历史回测
- [ ] 参数调优
- [ ] 事件分类器优化
- [ ] 告警质量评估与人工反馈闭环

---

## 技术栈

| 组件 | 选型 |
|------|------|
| 语言 | Python 3.12 |
| 环境管理 | Conda |
| 数据源 | XTick (api.xtick.top) / AkShare (东方财富) 双源可配置 |
| 数据格式 | HTTP REST API (JSON) / AkShare Python SDK |
| 关系数据库 | MySQL 8.0+ |
| 缓存/去重 | Redis |
| 任务队列 | Celery (生产) / APScheduler (原型) |
| AI | OpenAI / Anthropic / llama.cpp (三选一，优先级: llama > openai > anthropic) |
| 配置 | YAML + pydantic-settings |
| 日志 | loguru (JSON 结构化) |
| 测试 | pytest |

---

## 运维与可观测性

- **结构化日志**：JSON 格式，每次扫描带 trace_id
- **Redis 优雅降级**：Redis 不可用时自动跳过去重/缓存，不影响核心流程
- **AI 可选**：未配置 LLM 密钥时跳过 AI 分析，仅输出规则结果
- **关键指标**：数据抓取成功率、API 延迟、告警触发数、推送成功率

## 原型阶段已知限制

| 限制 | 说明 | 计划 |
|------|------|------|
| XTick 无资金流数据 | 主力净流入用成交额百分位代理 (0-20 区间) | 更多数据源 |
| 近 250 日低位为代理值 | 使用日内价格位置 + 跌幅近似判断 | Phase 3 接入历史 K 线 |
| 无 Celery 调度 | 直接函数调用，非定时任务 | Phase 3 引入任务队列 |

---

## 安全与合规

- API Key 使用 `.env` 管理，不入库
- MySQL 账号遵循最小权限原则
- 生产环境启用 TLS
- 日志禁止打印密钥/Token
- 对外输出包含风险提示与免责声明
