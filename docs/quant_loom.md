 

# 全市场 A 股机构动向 AI 监控与预警系统

## Project: QuantLoom（增强版）

> 目标：构建一套面向 A 股全市场的机构资金异动监测系统，对资金流、价格行为、新闻舆情、研报观点进行多源融合分析，并在满足规则与模型置信度要求时触发预警与日报推送。
> 说明：系统输出仅供研究与信息参考，不构成投资建议。

---

## 1. 项目定位与边界

### 1.1 业务目标

* 覆盖全市场 5000+ A 股标的，支持盘中与收盘后分析。
* 自动识别机构资金异动、板块联动、事件驱动和技术面共振。
* 输出标准化预警、日报与回溯分析结果。
* 支持人工复核闭环，逐步提升告警质量。

### 1.2 非目标

* 不承诺预测收益，不输出“必涨”“高胜率”之类结论。
* 不做高频撮合级交易系统，不直接对接实盘下单。
* 不依赖单一数据源，避免平台波动导致系统失效。

---

## 2. 功能需求（增强版）

### 2.1 监控层

#### 市场扫描

* 盘中按分钟级扫描全市场行情。
* 收盘后做全量复盘，生成候选池与排序结果。
* 对高流动性、低流动性标的分别采用不同阈值。

#### 异动识别

建议将“机构异动”拆成可解释的事件类型：

1. **放量上攻型**

   * 涨幅在阈值区间内，成交额显著放大。
   * 特大单/大单净流入占比高于基准线。

2. **底部吸筹型**

   * 近 250 日低位区域附近。
   * 连续多日资金净流入，价格波动收敛后放量。

3. **尾盘抢筹型**

   * 14:30 后资金流突然放大。
   * 尾盘主动买盘与收盘价偏强同步出现。

4. **事件驱动型**

   * 新闻、公告、政策、业绩预告、重组、订单等触发。
   * 资金面与消息面同向共振。

5. **板块联动型**

   * 个股并非独立异动，而是跟随行业/主题板块整体抬升。

### 2.2 分析层

#### 结构化分析

* 资金面：大单、特大单、净流入、净流出、换手率、量比。
* 价格面：涨跌幅、均线位置、波动率、支撑/压力位。
* 事件面：公告、新闻、研报、行业政策。
* 情绪面：社媒情绪、媒体正负向、舆情热度变化。
* 行业面：所属板块、产业链位置、同类标的联动。

#### AI 分析输出

每只触发标的输出统一结构：

* 核心逻辑一句话
* 触发原因分类
* 置信度评分
* 风险点
* 是否建议人工复核
* 是否进入重点跟踪池

### 2.3 预警层

* **实时预警**：触发后 5 分钟内推送。
* **收盘日报**：16:00 发送 HTML 邮件或企业微信/飞书消息。
* **重点池更新**：将高质量标的纳入次日观察列表。
* **告警去重**：同一标的同一原因在冷却期内不重复推送。

---

## 3. 业界更推荐的技术架构

### 3.1 推荐架构形态

建议采用**事件驱动 + 分层解耦**架构：

* **采集层**：行情、资金流、公告、新闻、研报、舆情
* **清洗层**：标准化、去重、字段对齐、异常修正
* **特征层**：资金特征、价格特征、事件特征、情绪特征
* **规则层**：可解释阈值与触发器
* **模型层**：LLM 归因、RAG 检索、分类评分
* **服务层**：告警、日报、查询 API、回溯 API
* **运维层**：监控、日志、审计、任务调度、灰度发布

### 3.2 技术选型建议

#### 数据采集

* AkShare：适合快速验证与非核心环境。
* Tushare：更适合稳定数据工程，但需关注积分与接口限制。
* 若进入生产阶段，建议增加**自有缓存层**，避免直接依赖单一外部源。

#### 存储

* MySQL：存业务事实表、任务表、策略配置、告警记录。
* Redis：缓存最新快照、热点候选池、去重标记、限流状态。
* 对于高频时序数据，可增加：

  * ClickHouse / TimescaleDB：用于高吞吐历史回放与分析。

#### 调度与任务

* APScheduler：适合轻量原型。
* Celery + Redis/RabbitMQ：适合任务解耦、重试、并发和失败恢复。
* 生产环境建议区分：

  * 采集任务
  * 分析任务
  * 通知任务
  * 回放任务

#### AI 与检索

* LLM 负责归因、摘要、分类、风险提示。
* RAG 负责研报、公告、新闻的可信检索。
* 向量库可选：

  * pgvector
  * Milvus
  * Elasticsearch 向量检索

#### 开发环境

* **Python 版本**：3.12
* **环境管理**：使用 Conda 创建独立环境

```bash
conda create -n quant_loom python=3.12
conda activate quant_loom
```

* **依赖安装**：

```bash
pip install akshare tushare mysqlclient redis celery apscheduler
pip install openai anthropic sentence-transformers
pip install pytest pytest-cov
```

---

## 4. 数据工程规范（建议补强）

### 4.1 数据质量控制

业界落地最容易出问题的不是模型，而是数据。建议增加以下机制：

* **数据完整性校验**：字段缺失、空值、异常值检测。
* **时间一致性校验**：盘中时间戳、收盘时间、公告发布时间统一标准化。
* **复权处理**：历史行情必须明确前复权/后复权口径。
* **停牌与涨跌停过滤**：避免将不可交易状态误判为有效信号。
* **异常值处理**：对极端成交额、极端涨跌幅设置保护阈值。
* **数据源优先级**：同一字段存在多源时明确主备顺序。

### 4.2 数据分层

建议按照 ODS / DWD / DWS / ADS 分层设计：

* **ODS**：原始抓取数据
* **DWD**：清洗后的明细数据
* **DWS**：按股票/行业/日期聚合后的主题宽表
* **ADS**：面向告警与报表的结果数据

---

## 5. 数据库设计增强版

原表太简单，建议扩展为以下核心表：

### 5.1 股票基础信息表

```sql
CREATE TABLE stock_master (
    code VARCHAR(10) PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    exchange VARCHAR(10) NOT NULL,
    industry VARCHAR(50),
    list_date DATE,
    status VARCHAR(20) DEFAULT 'active',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 5.2 行情快照表

```sql
CREATE TABLE stock_quote_snapshot (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMP NOT NULL,
    code VARCHAR(10) NOT NULL,
    last_price NUMERIC(18,4),
    pct_change NUMERIC(10,4),
    volume NUMERIC(20,4),
    turnover_amount NUMERIC(20,4),
    turnover_rate NUMERIC(10,4),
    limit_status VARCHAR(20),
    source VARCHAR(30),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_quote_ts_code ON stock_quote_snapshot(ts, code);
```

### 5.3 资金流记录表

```sql
CREATE TABLE stock_fund_flow (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMP NOT NULL,
    code VARCHAR(10) NOT NULL,
    super_large_net_inflow NUMERIC(20,4),
    large_net_inflow NUMERIC(20,4),
    medium_net_inflow NUMERIC(20,4),
    small_net_inflow NUMERIC(20,4),
    inflow_ratio NUMERIC(10,4),
    source VARCHAR(30),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_flow_ts_code ON stock_fund_flow(ts, code);
```

### 5.4 异动事件表

```sql
CREATE TABLE stock_alerts (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMP NOT NULL,
    code VARCHAR(10) NOT NULL,
    name VARCHAR(50),
    alert_type VARCHAR(50),
    trigger_reason TEXT,
    net_inflow_amount NUMERIC(20,4),
    inflow_ratio NUMERIC(10,4),
    confidence_score NUMERIC(5,2),
    risk_level VARCHAR(20),
    ai_summary TEXT,
    ai_evidence JSONB,
    is_sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_alerts_ts_code ON stock_alerts(ts, code);
```

### 5.5 通知发送日志表

```sql
CREATE TABLE notification_log (
    id BIGSERIAL PRIMARY KEY,
    alert_id BIGINT,
    channel VARCHAR(20),
    recipient VARCHAR(100),
    status VARCHAR(20),
    sent_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 6. 规则引擎设计建议

建议把“交易逻辑阈值”从代码里抽离成配置，便于调参与回测。

### 6.1 规则配置示例

```yaml
scan_rules:
  min_turnover_amount: 100000000
  pct_change_min: 2
  pct_change_max: 7
  super_large_inflow_ratio_min: 20
  consecutive_inflow_days_min: 3
  tail_chasing_start_time: "14:30"
  alert_cooldown_minutes: 30
```

### 6.2 规则执行原则

* 先规则过滤，再 AI 分析。
* 规则负责“是否值得看”，AI 负责“为什么值得看”。
* 所有触发结果必须保存原始证据，便于回放和审计。

---

## 7. AI 模块增强建议

### 7.1 Prompt 设计原则

业界更推荐把 Prompt 设计成**结构化输出**，而不是自由发挥。建议输出 JSON：

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

### 7.2 RAG 检索策略

* 时间窗分层：近 7 天、30 天、90 天。
* 文档类型分层：公告 > 研报 > 权威新闻 > 社媒。
* 检索优先级按可信度排序。
* 引用来源必须留存，避免“幻觉归因”。

### 7.3 模型治理

建议增加：

* 输出一致性检查
* 低置信度降级策略
* 事实核验步骤
* 结果人工复核入口
* Prompt 版本管理

### 7.4 LLM 可观测性 (Phase 2 已实现)

每次 LLM 调用记录三级日志（与 Go 服务 `ai/client.go` 对齐）：

* **请求前** (`http request full`): method, url, request_headers, request_body (完整 JSON)
* **响应后** (`http response full`): status, response_headers, response_body (完整 JSON)
* **完成摘要** (`request ok`): elapsed, model, prompt_tokens, completion_tokens, total_tokens, assistant_message_content_full

所有内容完整打印，不做截断。

---

## 8. 通知系统增强建议

### 8.1 告警分级

建议分三档：

* **P1**：高置信度、资金与事件共振、即时推送
* **P2**：中等置信度、进入观察池
* **P3**：弱信号，仅入库不打扰

### 8.2 去重策略

* 同标的同原因 30 分钟内不重复发送
* 相似事件合并
* 盘中与收盘告警分渠道处理

### 8.3 邮件模板建议

邮件不只展示表格，还应包含：

* 今日总览
* Top 5 异动标的
* 板块热度排行
* 风险提示
* 数据更新时间
* 免责声明

---

## 9. 运维与可观测性

这是很多“能跑的脚本”变成“能用的系统”的分水岭。

### 9.1 日志

* 结构化日志 JSON 化
* 记录请求耗时、任务状态、异常堆栈、数据源状态
* 每个告警带唯一 trace_id

### 9.2 指标

建议监控：

* 数据抓取成功率
* API 响应延迟
* 告警触发数量
* 邮件/消息发送成功率
* AI 分析耗时
* 队列积压量
* 数据延迟分钟数

### 9.3 告警

系统自身也要告警：

* 数据源不可用
* Redis/数据库连接失败
* 告警发送失败
* 任务堆积超过阈值
* AI 接口异常

---

## 10. 安全与合规增强

### 10.1 安全

* API Key 使用 `.env` 或密钥管理系统，不入库。
* MySQL 账号最小权限原则。
* 生产环境启用 TLS。
* 日志中禁止打印密钥、Cookie、token。

### 10.2 合规

* 明确系统仅为研究和信息参考。
* 对外输出增加风险提示。
* 如接入社媒数据，注意平台条款与抓取频率。
* 若用于机构内部，建议增加权限分级和审计日志。

---

## 11. 测试策略

建议把测试补进去，这是工程化的核心。

### 11.1 单元测试

* 规则阈值计算
* 数据清洗函数
* 告警去重逻辑
* 邮件模板渲染

### 11.2 集成测试

* 行情抓取 → 数据库存储 → 告警生成 → 通知发送
* AI 接口失败时的降级逻辑
* 断网/接口超时恢复

### 11.3 回测与验证

* 历史样本验证触发率
* 告警后 1 日、3 日、5 日表现统计
* 不同阈值组合下的 Precision / Recall
* 误报与漏报分析

---

## 12. 推荐的实施路线图（更可执行）

### 第 1 阶段：原型验证

* 接通行情与资金流数据
* 完成数据库建模
* 实现规则扫描器
* 形成基础告警

### 第 2 阶段：增强分析 ✅

* 接入公告、新闻、研报数据
* 实现 RAG 检索
* 建立 AI 结构化归因输出
* 历史资金流累积 + 真实连续流入天数
* LLM 请求/响应完整日志

### 第 3 阶段：生产化

* 引入任务队列
* 增加监控、日志、审计
* 完成邮件/飞书/钉钉通知
* 增加失败重试与降级策略

### 第 4 阶段：优化迭代

* 历史回测
* 参数调优
* 事件分类器优化
* 告警质量评估与人工反馈闭环

---

## 13. 更适合直接给 AI 编程工具的“增强版提示词”

> 请基于以下工程要求，设计并实现一个 Python 3.12 的 A 股机构资金异动监控系统核心模块。
> 要求：
>
> 1. 使用 AkShare 或 Tushare 获取全市场实时行情和资金流数据；
> 2. 将行情快照、资金流、告警事件存入 MySQL；
> 3. 使用 Redis 作为实时缓存和告警去重；
> 4. 规则引擎支持配置化阈值，并区分放量上攻、底部吸筹、尾盘抢筹、事件驱动四类信号；
> 5. 告警触发后调用 AI 模块输出 JSON 结构化结果，包括 summary、reason_type、confidence_score、risk_points、evidence、action；
> 6. 提供完整的异常处理、重试、日志、指标和单元测试；
> 7. 代码按模块拆分：data_ingestion、feature_engineering、rule_engine、ai_analyzer、notification、storage、config；
> 8. 输出可运行的项目骨架和关键代码。

---

 