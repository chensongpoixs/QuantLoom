# QuantLoom·量梭 — 系统架构与功能模块报告

> 全市场 A 股机构资金异动 AI 监控与预警系统
>
> 版本: 0.4.0 | 作者: chensong | 日期: 2026-05-20

---

## 一、项目概览

QuantLoom·量梭是一个面向 A 股全市场（5000+ 标的）的机构资金异动检测与 AI 归因分析系统。系统从多个数据源（XTick / 东方财富 AkShare）拉取行情、资金流、新闻、公告、研报数据，通过 YAML 配置驱动的规则引擎识别五类机构异动信号，再由 LLM（支持 llama.cpp / OpenAI / Anthropic 三级优先级）进行结构化 JSON 归因，最终通过企业微信/飞书/钉钉/邮件多通道推送告警。

**核心设计原则**: 规则引擎负责「是否值得看」，AI 负责「为什么值得看」。

### 技术栈

| 层级 | 技术选型 |
|------|---------|
| 语言 | Python 3.12 |
| 后端框架 | FastAPI (API 服务) |
| 前端框架 | Vue 3 + TypeScript + Vite |
| 前端图表 | ECharts 5 |
| 数据源 | XTick API / AkShare (东方财富) |
| 数据库 | MySQL 8 (SQLAlchemy 2.0 ORM) |
| 缓存 | Redis (可选，优雅降级) |
| 任务调度 | Celery + Redis (Beat + Worker) |
| AI/LLM | llama.cpp > OpenAI > Anthropic (三级优先级) |
| 监控 | Prometheus (10+ 指标) |
| 重试 | tenacity (指数退避 + 抖动) |
| 日志 | Loguru (结构化 JSON) |
| 配置 | Pydantic-settings + YAML |

---

## 二、系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                      QuantLoom·量梭 系统架构                    │
├──────────┬──────────┬──────────┬──────────┬──────────────────┤
│ 数据采集层 │ 特征工程层 │ 规则引擎层 │ AI分析层  │  服务与通知层      │
│ (Ingest) │ (Feature)│ (Rules)  │ (AI)     │  (Service)       │
├──────────┼──────────┼──────────┼──────────┼──────────────────┤
│ XTick    │ 资金流特征│ 放量上攻  │ LLM客户端 │ FastAPI REST     │
│ AkShare  │ 价格特征  │ 底部吸筹  │ RAG存储   │ 健康检查          │
│ 数据清洗  │ 事件匹配  │ 尾盘抢筹  │ 事件上下文 │ Prometheus /metrics│
│ 事件抓取  │ LLM排序  │ 事件驱动  │ 批量分析  │ Webhook通知       │
│          │          │ 板块联动  │          │ 邮件日报          │
├──────────┴──────────┴──────────┴──────────┴──────────────────┤
│  存储层: MySQL (10张业务表) + Redis (缓存/去重/锁)              │
│  运维层: Celery Beat/Worker + tenacity重试 + Prometheus监控     │
│  优化层: 回测引擎 + 网格搜索调参 + 反馈闭环 + 置信度校准          │
├──────────────────────────────────────────────────────────────┤
│  前端: Vue 3 SPA — Dashboard / 信号中心 / 持仓管理 / 消息预警    │
│        ECharts 可视化 + Pinia 状态管理 + Hash 路由              │
└──────────────────────────────────────────────────────────────┘
```

### 数据分层 (ODS → DWD → DWS → ADS)

| 层级 | 说明 | 对应表/模块 |
|------|------|-----------|
| ODS | 原始抓取数据 | AkShare/XTick 原始返回 |
| DWD | 清洗后明细 | `sq_stock_quote_snapshot`, `sq_stock_fund_flow` |
| DWS | 聚合宽表 | `sq_fund_flow_daily` (每日资金流累积) |
| ADS | 结果数据 | `sq_stock_alerts`, `sq_backtest_results` |

---

## 三、后端功能模块详解

### 3.1 数据采集层 (`quant_loom/data_ingestion/`)

#### AkShare 抓取器 (`akshare_fetcher.py`)
- **全市场行情**: `stock_zh_a_spot_em()` → 5000+ 实时快照
- **资金流排名**: `stock_individual_fund_flow_rank()` → 超大单/大单/中单/小单净流入
- **行业板块**: `stock_board_industry_name_em()` → 板块涨跌幅与主力净流入
- **个股历史K线**: `stock_zh_a_hist()` → 前复权日线 (回测用)
- **韧性机制**:
  - 浏览器级请求头伪装 (Chrome 125 User-Agent, Referer)
  - urllib3 连接级自动重试 (8次, 1.5s 退避)
  - 东方财富 push2 多 host 轮询 (14个子域名)
  - 单请求级透明重试 (最多 10 次, 指数退避封顶 30s)
  - 全局限流 (默认 0.5s 间隔)
  - Stale 缓存降级 (成功数据持久化 pickle, 失败时用 24h 内快照)

#### XTick 抓取器 (`xtick_fetcher.py`)
- HTTP REST API 调用 (`api.xtick.top`)
- 日线数据标准化: 10 字段 → 系统内部字段 (close→latest, amount→turnover_amount)
- 自动计算 `pct_change = (close - preClose) / preClose * 100`
- 毫秒时间戳 → datetime 转换
- XTick 不提供资金流拆解 → 降级为成交额百分位代理主力参与度

#### 数据清洗器 (`cleaner.py`)
- 过滤: 停牌(无价格)、涨跌停(±20%)、异常成交额(>500亿)
- 填充: NaN → 0 (数值列)
- 交易所推断: 60x/68x→sh, 00x/30x→sz, 8xx/4xx→bj
- 资金流净流入占比自动计算

#### 事件抓取器 (`event_fetcher.py`)
- 三类事件: 个股新闻 (`stock_news_em`) + 上市公司公告 (`stock_notice_report`) + 个股研报 (`stock_research_report_em`)
- 全球财经快讯: 财联社电报 (`stock_info_global_cls`)
- 批量聚合: `fetch_events_batch()` — 并发抓取多只股票事件
- 标准化输出: 统一 dict 格式 (code, event_type, title, content, source, url, published_at)

### 3.2 特征工程层 (`quant_loom/feature_engineering/`)

#### 资金流特征 (`fund_flow.py`)
- `super_large_inflow_ratio`: 超大单净流入 / 成交额 × 100
- `large_inflow_ratio`: 大单净流入 / 成交额 × 100
- `main_force_ratio`: (超大单 + 大单) / 成交额 × 100 → 主力参与度
- `net_inflow`: 四单合计净流入
- `consecutive_inflow_days`: 从 `sq_fund_flow_daily` 表按交易日降序计算连续净流入天数

#### 价格特征 (`price.py`)
- `volume_ratio`: 当前量 / 过去5日均量
- `pct_change_normalized`: 标准化涨跌幅
- `near_52w_low`: 年跌幅 > 30% 视为低位区域

#### 事件匹配器 (`event_matcher.py`)
三级匹配流水线:
1. **时间窗口预筛选**: 仅保留最近 N 天事件
2. **关键词预筛选**: 根据异动类型匹配关键词 (如 "增持"→accumulation, "重组"→event_driven)
3. **LLM 精排**: 调用 LLM 对候选事件做相关性评分 (0-1), 按分降序排列

### 3.3 规则引擎层 (`quant_loom/rule_engine/`)

#### 五类异动信号 (`rules.py`)

| 编号 | 类型 | 核心逻辑 | 置信度计算 |
|------|------|---------|-----------|
| 1 | **放量上攻** (breakout) | 涨幅 2-7% + 成交额 > 1亿 + 量比 > 1.5 + 主力占比 > 20% | 通过项数 / 总检查项 |
| 2 | **底部吸筹** (accumulation) | 近250日低位 + 连续流入 ≥ 3日 + 主力占比 > 10% | 0.5 + 三个子项加权 |
| 3 | **尾盘抢筹** (tail_chasing) | 14:30后主力占比 > 10% + 主动买盘 > 55% | 尾盘窗口0.75(P1) / 非窗口0.55(P2) |
| 4 | **事件驱动** (event_driven) | 涨幅 ≥ 3% + 成交额 > 8千万 + 主力占比 > 15% | 有事件0.80 / 无事件0.55 |
| 5 | **板块联动** (sector_linked) | 板块内 ≥ 3只同步异动 + 板块均涨幅 > 1.5% | 0.45 + 板块涨幅/股票数加权 |

#### 配置驱动 (`rules.yaml`)
所有阈值均可通过 YAML 调整，无需修改代码。每种类型独立配置 `enabled`, 阈值参数等。

#### 全市场扫描器 (`scanner.py`)
- 合并行情+资金流 → 逐行匹配五类规则 → 按置信度降序排列
- 资金流不可用时: 成交额排名百分位 × 20 → 主力参与度代理值 (0-20 区间)
- `near_250d_low` 代理: 日内价格位置 < 30% + 跌幅 > 2%
- 置信度校准: 历史反馈精度 < 0.3 的类型 → confidence_score 乘 0.7

#### 告警去重 (`dedup.py`)
- Redis-based: `alert_dedup:{code}:{alert_type}` key, TTL = 冷却时间
- Redis 不可用时跳过去重 (不阻塞管线)

### 3.4 AI 分析层 (`quant_loom/ai_analyzer/`)

#### LLM 客户端 (`llm_client.py`)
- **三级优先级**: llama.cpp (本地) > OpenAI > Anthropic
- **结构化输出**: JSON (summary, reason_type, confidence_score, risk_points, evidence, action)
- **Prompt 模板**: 系统提示词 (A股机构分析专家) + 用户提示词 (含事件上下文)
- **可观测性**: 三级日志 — 请求前 (method/url/headers/body) → 响应后 (status/body) → 完成摘要 (elapsed/model/tokens)
- **降级策略**: AI 不可用时返回 fallback 结果
- **批量分析**: 逐个调用, 间隔 0.5s 节流

#### RAG 上下文存储 (`rag_store.py`)
- MySQL-backed: 零外部依赖, 无需向量数据库
- 去重存储: 按 (code, title[:100], published_at) 三元组去重
- 上下文构建: 检索最近 N 天事件 → 格式化为 LLM prompt 文本

### 3.5 通知层 (`quant_loom/notification/`)

#### Webhook 通知 (`webhook.py`)
| 渠道 | 格式 | 特性 |
|------|------|------|
| 企业微信 | Markdown | 按风险等级分色 emoji |
| 飞书 | 交互式卡片 | P1 红色/P2 黄色模板 |
| 钉钉 | Markdown | P1 @所有人 |

- 全部带 `@network_retry` 装饰器 (3次重试)
- 每条发送写入 `sq_notification_log` (审计日志)

#### 邮件通知 (`email_sender.py`)
- HTML 日报模板: 总览统计 + Top 20 告警表格 + 风险免责声明
- SMTP 端口自适应: 465 → SMTP_SSL, 587 → SMTP + STARTTLS
- 批量 NotificationLog 写入

### 3.6 存储层 (`quant_loom/storage/`)

#### 10 张 MySQL 核心表 (`models.py`)

| 表名 | 用途 | 关键字段 |
|------|------|---------|
| `sq_stock_master` | 股票基础信息 | code(PK), name, exchange, industry, status |
| `sq_stock_quote_snapshot` | 行情快照 | ts, code, last_price, pct_change, volume, turnover_amount |
| `sq_stock_fund_flow` | 资金流记录 | ts, code, super_large/large/medium/small 净流入 |
| `sq_stock_alerts` | 异动事件 | ts, code, alert_type, trigger_reason, confidence_score, risk_level(P1-P3), ai_summary(JSON), ai_evidence(JSON) |
| `sq_notification_log` | 通知发送日志 | alert_id, channel, status, sent_at, error_message |
| `sq_stock_events` | 股票事件 | code, event_type(news/announcement/report), title, content, published_at, sentiment_score |
| `sq_fund_flow_daily` | 每日资金流累积 | code, trade_date(UK), 四单净流入, main_force_ratio, net_inflow |
| `sq_backtest_results` | 回测结果 | trade_date, code, alert_type, outcome_1d/3d/5d, outcome_positive, params_hash |
| `sq_portfolio` | 持仓明细 | code(UK), name, shares, cost_price |
| `sq_alert_feedback` | 告警反馈 | alert_id, feedback_type(manual/auto), verdict(correct/incorrect/ambiguous), outcome_1d/3d/5d |

#### MySQL 客户端 (`mysql_client.py`)
- SQLAlchemy 2.0: 连接池 (pool_size=10, max_overflow=20), pool_pre_ping, 1h 回收
- `insert_or_update()`: 支持自然键 upsert (如 code+trade_date)
- 上下文管理器: 自动 commit/rollback/close

#### Redis 客户端 (`redis_client.py`)
- 可选依赖: 未安装或不可用时自动降级为空操作
- 连接池: max_connections=20
- 故障自愈: 任何异常标记 client=None, 下次调用跳过

### 3.7 运维层 (`quant_loom/ops/`)

#### 重试策略 (`retry.py`)
- `@network_retry`: 3次, 指数退避 2s→4s→30s, 目标 ConnectionError/Timeout
- `@db_retry`: 2次, 指数退避 1s→5s, 目标 OperationalError

#### Prometheus 指标 (`metrics.py`)

| 类型 | 指标名 | 说明 |
|------|--------|------|
| Counter | `quantloom_pipeline_runs_total` | 管线执行次数 (status: success/failed) |
| Histogram | `quantloom_pipeline_duration_seconds` | 管线执行耗时 |
| Counter | `quantloom_alerts_total` | 告警总数 (risk_level × alert_type) |
| Counter | `quantloom_notifications_total` | 通知发送数 (channel × status) |
| Histogram | `quantloom_data_fetch_duration_seconds` | 数据抓取耗时 (source) |
| Counter | `quantloom_data_fetch_errors_total` | 数据抓取失败数 |
| Histogram | `quantloom_api_call_duration_seconds` | API 调用耗时 (service) |
| Counter | `quantloom_api_errors_total` | API 错误数 |
| Gauge | `quantloom_db_health` | 数据库健康 (mysql/redis) |
| Counter | `quantloom_retry_attempts_total` | 重试次数 (component) |
| Gauge | `quantloom_alert_precision` | 告警精度 (alert_type × window) |
| Counter | `quantloom_alert_outcomes_total` | 方向正确/错误计数 |

### 3.8 任务调度层 (`quant_loom/tasks/`)

#### Celery Beat 定时任务

| 任务 | 频率 | 说明 |
|------|------|------|
| `scan_task` | 每 10 分钟 (交易时段) | 全市场扫描 + AI 分析 top 10 |
| `closing_report_task` | 交易日 16:05 | 收盘全量扫描 + AI top 20 + 邮件日报 |
| `backfill_outcomes_task` | 交易日 16:30 | 自动回填 1/3/5 日 outcome 到反馈表 |
| `refresh_quality_metrics_task` | 每小时第 37 分钟 | 刷新告警精度 Prometheus 指标 |

#### 防重复机制
- Redis 分布式锁: `qloom:full_market_scan_lock`, TTL 900s
- 降级方案: threading.Lock (Redis 不可用时)
- Worker 启动扫描锁: `qloom:celery_startup_scan`, TTL 180s

### 3.9 优化迭代层 (`quant_loom/tuning/`)

#### 网格搜索调参器 (`grid_search.py`)
- 笛卡尔积参数组合: 每种类型独立搜索空间 (3-4 参数, 各 3 个候选值)
- `params_hash`: MD5 缓存, 避免重复回测
- 评分: `0.6 × precision@3d + 0.4 × avg_return@3d`
- 导出: `rules.tuned.yaml` (最优参数组合)

#### 评分函数 (`score.py`)
- `precision_at_n()`: 方向准确率 (异动涨跌 → T+N 涨跌一致)
- `average_return()`: T+N 平均收益率
- `hit_rate()`: T+N 收益超过阈值 (默认 2%) 的比例
- `combined_score()`: 综合评分

### 3.10 API 服务层 (`quant_loom/api/app.py`)

FastAPI 应用, 15+ 端点:

| 分类 | 端点 | 方法 | 说明 |
|------|------|------|------|
| 健康检查 | `/health` | GET | 综合健康 (MySQL + Redis) |
| | `/health/ready` | GET | K8s readiness probe |
| | `/health/live` | GET | K8s liveness probe |
| 监控 | `/metrics` | GET | Prometheus text/plain |
| 告警 | `/api/alerts` | GET | 分页告警列表 (支持类型/风险/代码/日期筛选) |
| | `/api/alerts/{id}` | GET | 告警详情 (含关联事件 + 通知日志) |
| 统计 | `/api/stats/summary` | GET | 今日摘要 (P1/P2/P3 分布, 类型统计) |
| | `/api/stats/trend` | GET | 趋势数据 (按日期+类型聚合) |
| 搜索 | `/api/stocks/search` | GET | 股票搜索 (code/name 模糊匹配) |
| AI | `/api/analysis/daily` | GET | 今日 AI 分析 Top10 |
| 持仓 | `/api/portfolio` | GET/POST/DELETE | 持仓 CRUD |
| 行情 | `/api/quotes/batch` | GET | 批量最新行情 |
| 通知 | `/api/notifications` | GET | 通知日志分页 |
| | `/api/notifications/{id}/retry` | POST | 重推失败通知 |
| 资金流 | `/api/fund-flow/top` | GET | 净流入/流出 Top10 |
| 板块 | `/api/sectors/heatmap` | GET | 板块告警热力图 |
| 回测 | `/api/backtest/type-stats` | GET | 按类型回测统计 |
| 反馈 | `/feedback` | POST | 提交告警评审 |
| | `/alerts/pending-review` | GET | 待复核告警列表 |
| | `/alerts/quality` | GET | 告警质量统计 |

CORS 全开, SPA fallback (非 API 路径返回 `index.html`), 静态文件挂载 (`/assets`)

### 3.11 管线入口 (`scripts/run_scanner.py`)

7 步执行流程:
```
[1/7] 数据抓取 (行情 + 资金流)
[2/7] 数据清洗
[3/7] 历史资金流累积 + 连续流入天数计算
[4/7] 预扫描 + 事件获取 (仅候选股)
[5/7] 规则扫描 (五类信号)
[6/7] 去重 + AI 分析 top N
[7/7] 数据库写入 + 通知推送 (P1 实时, 其余日报)
```

命令行参数:
- `--top N`: AI 分析前 N 条 (0=跳过)
- `--dry-run`: 仅扫描, 不写库
- `--skip-events`: 跳过事件抓取

---

## 四、前端功能模块详解

### 4.1 技术栈

| 技术 | 用途 |
|------|------|
| Vue 3 (Composition API) | UI 框架 |
| TypeScript | 类型安全 |
| Vite | 构建工具 |
| Vue Router (Hash 模式) | 路由 |
| Pinia | 状态管理 |
| Axios | HTTP 客户端 |
| ECharts 5 | 可视化图表 |

### 4.2 页面结构

```
/                → Dashboard (行情看板)
/alerts          → AlertList (信号中心)
/alerts/:id      → AlertDetail (信号详情)
/portfolio       → Portfolio (持仓管理)
/notifications   → Notifications (消息预警)
```

### 4.3 各页面功能

#### Dashboard (行情看板)
- **StatsGrid**: 4 个统计卡片 — 今日告警数, P1 高风险数, AI 覆盖率, 近 7 天日均
- **TrendChart**: ECharts 折线图 — 近 N 天每日告警量 × 按类型分色
- **SignalGauge**: 最新 10 条告警快速列表, 点击进入详情
- **SectorHeatmap**: 行业板块 × 信号密度热力图 (Top 30 行业)
- **FundFlowStack**: 主力资金净流入/流出 Top10 双栏对比

#### AlertList (信号中心)
- **筛选栏**: alert_type (5类), risk_level (P1-P3), 日期范围, 股票代码搜索
- **AlertTable**: 分页表格 — code+name, 时间, 类型, 置信度圆环, 触发原因摘要
- **Pagination**: 翻页组件
- **人工反馈**: 正确/错误/模糊 评审按钮 (写入 `sq_alert_feedback`)

#### AlertDetail (信号详情)
- 完整 AI 分析: summary, evidence (JSON), risk_points, action
- **ConfidenceGauge**: 置信度圆环可视化
- **EventTimeline**: 关联事件时间线 (新闻/公告/研报, 含 relevance_score)
- **FundFlowBar**: 资金流快照 (超大单/大单/中单/小单)
- **NotificationLog**: 通知发送日志 (渠道, 状态, 时间)

#### Portfolio (持仓管理)
- 持仓列表: cost_price, shares, 浮动盈亏
- 添加/删除持仓
- 批量行情查询: 所有持仓实时价格/涨跌幅

#### Notifications (消息预警)
- 通知历史分页
- 失败通知一键重推

### 4.4 Pinia Store 设计

| Store | 管理状态 |
|-------|---------|
| `dashboard` | 摘要统计, 趋势数据, 板块热力图, 资金流 Top10 |
| `alerts` | 告警列表, 筛选条件, 分页, 告警详情 |
| `portfolio` | 持仓列表, 行情快照 |
| `notifications` | 通知日志, 重推状态 |

### 4.5 类型系统 (`types/index.ts`)

完整的 TypeScript 类型定义:
- `Alert`, `AlertDetail` (含 related_events, notification_logs)
- `EventItem`, `NotificationLog`
- `SummaryStats`, `TrendData`, `AlertsPage`
- `PortfolioHolding`, `FundFlowItem`, `SectorHeatmapItem`
- `FeedbackRequest`, `BacktestTypeStats`

### 4.6 PWA 支持
- `manifest.json`: 应用名称 "量梭", theme-color `#2563eb`
- `sw.js`: Service Worker (离线缓存)
- 移动端适配: viewport-fit=cover, apple-mobile-web-app

---

## 五、数据流全景

```
┌──────────┐   ┌──────────┐   ┌──────────────┐   ┌──────────┐
│ XTick /  │──▶│ Data     │──▶│ Rule Engine  │──▶│ AI (LLM) │
│ AkShare  │   │ Cleaner  │   │ (5 patterns) │   │ Analyzer │
└──────────┘   └──────────┘   └──────────────┘   └──────────┘
                                    │                    │
                    ┌───────────────┴────────────────────┤
                    ▼                                    ▼
             ┌──────────┐                        ┌──────────────┐
             │  MySQL   │◀───────────────────────│ RAG Context  │
             │ (10表)   │                        │ (事件匹配)    │
             └──────────┘                        └──────────────┘
                    │
        ┌───────────┼───────────┬──────────────┐
        ▼           ▼           ▼              ▼
   ┌────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐
   │ WeCom  │ │ Feishu │ │ DingTalk │ │  Email   │
   │ Webhook│ │ Webhook│ │ Webhook  │ │  (HTML)  │
   └────────┘ └────────┘ └──────────┘ └──────────┘
        │           │           │              │
        └───────────┴───────────┴──────────────┘
                          │
                          ▼
                  ┌───────────────┐
                  │NotificationLog│ (审计)
                  └───────────────┘

                          ┌──────────────┐
                          │  FastAPI     │
                          │  :9090       │
                          └──────┬───────┘
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
            ┌──────────────┐          ┌──────────────┐
            │ Prometheus   │          │ Vue 3 SPA    │
            │ /metrics     │          │ (前端看板)    │
            └──────────────┘          └──────────────┘
```

---

## 六、关键设计决策

### 6.1 双数据源架构
- XTick (推荐): 需 token, 日线数据, 无资金流拆解 → 成交额百分位代理
- AkShare (免费): 无需 token, 完整资金流, 但有网络/限流风险 → 多 host 轮询 + stale 缓存

### 6.2 规则先行, AI 后置
- 规则负责过滤 (全市场 5000+ → 数十条候选)
- AI 负责解释 (结构化 JSON 输出, 含证据链和操作建议)
- 降低 LLM 调用成本 (仅分析 top 10-20)

### 6.3 三级 LLM 优先级
1. llama.cpp (本地, 免费, 无网络延迟)
2. OpenAI (云端, 质量最高)
3. Anthropic (云端备选)

### 6.4 优雅降级
- Redis 不可用 → 跳过去重/缓存, 不阻塞管线
- LLM 不可用 → fallback 结果 (reason_type: unknown)
- 数据源不可用 → stale 缓存 (24h 内快照)
- 外部 API 失败 → 3 次指数退避重试 → 记录错误日志 → 继续

### 6.5 反馈闭环
1. 人工评审 (正确/错误/模糊) → `sq_alert_feedback`
2. 自动回填 (T+1/3/5 outcome) → 来自回测结果
3. 置信度校准: 历史精度 < 0.3 → 入库值 × 0.7
4. 精度 Prometheus 指标 → 告警质量监控

---

## 七、项目文件结构

```
QuantLoom/
├── config/
│   ├── settings.py           # Pydantic 全局配置
│   └── rules.yaml            # 规则阈值配置
├── quant_loom/
│   ├── data_ingestion/       # 数据采集层
│   │   ├── akshare_fetcher.py
│   │   ├── xtick_fetcher.py
│   │   ├── cleaner.py
│   │   └── event_fetcher.py
│   ├── feature_engineering/  # 特征工程层
│   │   ├── fund_flow.py
│   │   ├── price.py
│   │   └── event_matcher.py
│   ├── rule_engine/          # 规则引擎层
│   │   ├── rules.py
│   │   ├── scanner.py
│   │   └── dedup.py
│   ├── ai_analyzer/          # AI 分析层
│   │   ├── llm_client.py
│   │   └── rag_store.py
│   ├── notification/         # 通知层
│   │   ├── webhook.py
│   │   └── email_sender.py
│   ├── storage/              # 存储层
│   │   ├── models.py         # 10 张 ORM 模型
│   │   ├── mysql_client.py
│   │   └── redis_client.py
│   ├── ops/                  # 运维层
│   │   ├── retry.py
│   │   ├── metrics.py
│   │   └── logger.py
│   ├── tasks/                # 任务调度
│   │   ├── celery_app.py
│   │   └── scanner_tasks.py
│   ├── tuning/               # 调优层
│   │   ├── grid_search.py
│   │   └── score.py
│   └── api/
│       └── app.py            # FastAPI 应用 (15+ 端点)
├── scripts/
│   ├── run_scanner.py        # 管线入口
│   ├── run_backtest.py       # 回测引擎
│   ├── run_tuning.py         # 网格搜索
│   ├── init_db.py            # 数据库初始化
│   ├── run_api.py            # API 启动器
│   ├── run_celery_worker.py  # Worker 启动器
│   └── run_celery_beat.py    # Beat 启动器
├── frontend/
│   ├── src/
│   │   ├── views/            # 5 个页面
│   │   ├── components/       # 15+ 组件
│   │   ├── stores/           # 4 个 Pinia store
│   │   ├── api/              # Axios 配置
│   │   ├── router/           # Hash 路由
│   │   ├── types/            # TS 类型定义
│   │   └── utils/            # 工具函数
│   └── dist/                 # 构建产物 (由 FastAPI 托管)
├── tests/                    # 20 个测试文件, 208 个用例
└── docs/                     # 设计文档
```

---

## 八、测试覆盖

- **208 个单元测试** (20 个测试文件), 全部通过
- 覆盖: rule_engine (22), cleaner (9), dedup (6), fund_flow (19), price (14), scanner (9), event_fetcher (11), event_matcher (11), rag_store (7), retry (13), metrics (5), email (6), webhook (11), api (8), tasks (8), backtest (12), tuning (19), feedback (19)

---

## 九、实施阶段回顾

| 阶段 | 状态 | 关键交付 |
|------|------|---------|
| 1. 原型验证 | ✅ | 数据连接, DB 建模, 规则扫描, 基础告警 |
| 2. 增强分析 | ✅ | 事件数据接入, RAG, AI 结构化归因, 历史资金流, LLM 日志 |
| 3. 生产化 | ✅ | Celery 任务队列, tenacity 重试, SMTP 修复, Prometheus, FastAPI, 钉钉通知, NotificationLog |
| 4. 优化迭代 | ✅ | 回测引擎, 网格搜索调参, 反馈闭环, 置信度校准, 前端看板 |

---

## 十、已知限制

1. XTick 不提供资金流拆解 → `main_force_ratio` 由成交额百分位代理 (0-20 区间)
2. `near_250d_low` 由日内位置 + 跌幅代理 (需历史 K 线数据方可精确计算)
3. 回测模式跳过事件驱动规则 (无历史事件 API)
4. 事件相关性判断依赖 LLM 可用性 (不可用时降级为关键词匹配)

---

> 免责声明: 系统输出仅供研究与信息参考，不构成投资建议。
