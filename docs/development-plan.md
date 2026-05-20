# QuantLoom·量梭 — 开发计划文档

> 基于业界对标分析，按优先级排序的详细开发计划。每个任务包含：目标、实现路径、涉及文件、验收标准。

---

## 第 5 阶段：信号增强

---

### 任务 5.1: 技术指标体系 ✅ **(已完成 2026-05-20)**

**目标**: 补齐当前完全空白的技术分析维度，新增 15+ 个标准技术指标。

**现状**: ~~`PriceFeatures` 仅有量比和年跌幅判断。`near_250d_low` 使用日内位置代理值。~~

**实现路径**:

#### 步骤 5.1.1 — 新增技术指标计算模块

**新建文件**: `quant_loom/feature_engineering/technical.py`

**指标清单**:

| 类别 | 指标 | 计算方法 |
|------|------|---------|
| 趋势 | MA(5/10/20/60/120) | 收盘价 N 日简单移动平均 |
| 趋势 | EMA(12/26) | 指数移动平均 |
| 趋势 | MACD (DIF/DEA/柱) | EMA12 - EMA26 = DIF; DIF 的 EMA9 = DEA; 柱 = 2*(DIF-DEA) |
| 动量 | RSI(6/14) | 100 - 100/(1 + 平均涨幅/平均跌幅) |
| 动量 | KDJ (K/D/J) | RSV → K → D → J |
| 波动 | BOLL (上轨/中轨/下轨) | 中轨=MA20; 上下轨=中轨±2*STD |
| 波动 | ATR(14) | True Range 的 14 日 MA |
| 量价 | VWAP | Σ(价格×成交量) / Σ成交量 |
| 量价 | OBV | 涨日+量, 跌日-量, 累积 |
| 均线关系 | 多头/空头排列 | MA5>MA10>MA20>MA60 判断 |
| 均线关系 | 金叉/死叉 | MA5 上穿/下穿 MA20 |
| 均线关系 | 均线粘合度 | MA5/10/20 标准差 / MA20 |

**函数签名示例**:
```python
class TechnicalIndicators:
    @staticmethod
    def compute_all(klines_df: pd.DataFrame) -> pd.DataFrame
    @staticmethod
    def ma(close: pd.Series, period: int) -> pd.Series
    @staticmethod
    def ema(close: pd.Series, period: int) -> pd.Series
    @staticmethod
    def macd(close: pd.Series) -> pd.DataFrame  # → DIF, DEA, MACD_hist
    @staticmethod
    def rsi(close: pd.Series, period: int = 14) -> pd.Series
    @staticmethod
    def kdj(df: pd.DataFrame, n: int = 9) -> pd.DataFrame  # → K, D, J
    @staticmethod
    def boll(close: pd.Series, period: int = 20) -> pd.DataFrame  # → upper, mid, lower
    @staticmethod
    def atr(df: pd.DataFrame, period: int = 14) -> pd.Series
    @staticmethod
    def vwap(df: pd.DataFrame) -> pd.Series
    @staticmethod
    def obv(df: pd.DataFrame) -> pd.Series
    @staticmethod
    def ma_alignment(df: pd.DataFrame) -> dict  # → bullish/bearish, golden_cross/death_cross, adhesion
```

#### 步骤 5.1.2 — 扫描管线集成 K 线数据

**修改文件**: `scripts/run_scanner.py`

在 `[3/7]` 和 `[4/7]` 之间增加步骤：
```
[3.5] 获取候选股历史 K 线 + 计算技术指标
```
- 对预扫描的 top 50 候选股调用 `fetcher.fetch_history()`
- 批量计算技术指标
- 结果作为新参数传入 `scanner.scan()`

#### 步骤 5.1.3 — 规则引擎增加技术共振维度

**修改文件**: `quant_loom/rule_engine/rules.py`, `config/rules.yaml`

新增 `technical` 规则配置:
```yaml
scan_rules:
  technical:
    enabled: true
    # 均线多头排列 + MACD 金叉 + RSI > 50
    require_bullish_alignment: true
    require_macd_golden_cross: true
    rsi_min: 50
```

新增 `check_technical_resonance()` 方法 — 在现有五类信号上增加技术面加权分。

#### 步骤 5.1.4 — 前端 K 线图组件

**新建文件**: `frontend/src/components/KLineChart.vue`

- ECharts 蜡烛图 (k线) + MA 均线叠加 + 成交量副图
- 在 `AlertDetail.vue` 中嵌入

#### 步骤 5.1.5 — 单元测试

**新建文件**: `tests/test_technical.py`
- 测试所有 15 个指标的计算正确性 (用已知样本验证)

**验收标准**:
- [x] `TechnicalIndicators` 15 个指标全部可计算
- [x] `rules.yaml` 新增 `technical_resonance` 配置段
- [x] 扫描管线集成历史 K 线拉取
- [x] 规则引擎能根据技术指标加权置信度
- [x] 前端 K 线图可在告警详情页查看 (KLineChart.vue + AlertDetail 集成)
- [x] `GET /api/kline/{code}` API 端点可用
- [x] `tests/test_technical.py` 31 个测试全部通过

---

### 任务 5.2: 北向资金数据接入 ✅ **(已完成 2026-05-20)**

**目标**: 接入沪深港通北向资金数据，作为资金面新维度。

**实现路径**:

#### 步骤 5.2.1 — 数据抓取

**新建文件**: `quant_loom/data_ingestion/north_flow_fetcher.py`

```python
class NorthFlowFetcher:
    def fetch_north_net_flow(self) -> pd.DataFrame  # 北向资金净流入 (当日/历史)
    def fetch_north_holdings(self) -> pd.DataFrame  # 北向持仓明细 (个股持仓量/市值)
    def fetch_north_top10(self) -> pd.DataFrame     # 十大成交活跃股
```

使用的 AkShare 接口:
- `ak.stock_hsgt_north_net_flow_in_em()` — 北向资金净流量
- `ak.stock_hsgt_hold_share_em()` — 沪深港通持股明细
- `ak.stock_hsgt_top10_em()` — 十大成交股

#### 步骤 5.2.2 — 数据模型

**修改文件**: `quant_loom/storage/models.py`

新增表:
```python
class NorthFlowDaily(Base):
    __tablename__ = "sq_north_flow_daily"
    # date, net_inflow_sh, net_inflow_sz, total_net_inflow, balance_sh, balance_sz

class NorthHolding(Base):
    __tablename__ = "sq_north_holdings"
    # code, trade_date, hold_shares, hold_market_value, hold_ratio
```

#### 步骤 5.2.3 — 特征维度

**修改文件**: `quant_loom/feature_engineering/fund_flow.py`

新增:
```python
@staticmethod
def north_inflow_acceleration(df) -> float  # 北向资金流入加速率 (今日 vs 5日均值)
@staticmethod
def north_holding_change(df) -> float       # 北向持仓变化率
```

#### 步骤 5.2.4 — 规则集成

**修改文件**: `config/rules.yaml`, `quant_loom/rule_engine/rules.py`

在 5 类规则中增加北向资金加分项:
- 北向连续增持 → breakout/accumulation 置信度 +0.1
- 北向大幅减持 → 降低置信度
- 新增配置: `north_flow_increase_days_min: 3`

#### 步骤 5.2.5 — 前端展示

**修改文件**: `frontend/src/components/FundFlowBar.vue` (或新建 `NorthFlowCard.vue`)

在 Dashboard 和 AlertDetail 中展示北向资金流向。

#### 步骤 5.2.6 — 数据库变更 + 测试

**修改文件**: `scripts/init_db.py`
**新建文件**: `tests/test_north_flow.py`

**验收标准**:
- [x] 北向资金数据可正常抓取与存储
- [x] 北向持仓变化参与规则评分 (north_flow_score: ±0.08~+0.10)
- [x] 前端 Dashboard 展示北向资金流 (NorthFlowCard: 净流入+十大成交)
- [x] `GET /api/north-flow/latest` API 端点可用
- [x] `tests/test_north_flow.py` 15 个测试全部通过
- [x] 新表 `sq_north_flow_daily` + `sq_north_holdings` 可通过 init_db 自动创建

---

### 任务 5.3: 涨跌停/市场宽度统计 ✅ **(已完成 2026-05-20)**

**目标**: 新增市场情绪维度，包括涨停/跌停数、炸板率、连板高度、涨跌比。

**实现路径**:

#### 步骤 5.3.1 — 市场宽度计算模块 ✅

**新建文件**: `quant_loom/feature_engineering/market_breadth.py`

```python
class MarketBreadth:
    @staticmethod
    def compute(quotes_df: pd.DataFrame) -> dict:
        """
        返回:
        - limit_up_count: 涨停家数
        - limit_down_count: 跌停家数
        - up_down_ratio: 涨跌比 (上涨家数/下跌家数)
        - adl: 腾落指数 (上涨-下跌)
        - broken_board_count: 炸板数 (盘中触板但未封)
        - max_consecutive_boards: 最高连板数
        - avg_pct_change: 全市场平均涨跌幅
        - total_turnover: 全市场总成交额
        """
```

#### 步骤 5.3.2 — 数据存储 ✅

**修改文件**: `quant_loom/storage/models.py`

新增 `MarketBreadthSnapshot` 模型 → `sq_market_breadth` 表 (12 个字段)

#### 步骤 5.3.3 — 管线集成 ✅

**修改文件**: `scripts/run_scanner.py`

在 `[2/7]` 数据清洗后立即计算市场宽度，存入 DB，应用情绪偏差修正置信度。

#### 步骤 5.3.4 — 规则应用 ✅

**修改文件**: `quant_loom/feature_engineering/market_breadth.py`
通过 `apply_sentiment_bias()` 实现背景因子修正:
- 强势市场 (bullish): +0.03
- 恐慌市场 (bearish): +0.05
- 极端恐慌 (跌停 > 100): -0.05
- 涨跌比极端 (>5:1 或 <1:5): ±0.02

#### 步骤 5.3.5 — 前端展示 ✅

**新建文件**: `frontend/src/components/MarketBreadthCard.vue` — 6 项指标 + 涨跌比条形图
**修改文件**: `frontend/src/views/Dashboard.vue` — 嵌入市场情绪卡片

#### 步骤 5.3.6 — API + 测试 ✅

**修改文件**: `quant_loom/api/app.py` → 增加 `GET /api/market/breadth` 端点
**新建文件**: `tests/test_market_breadth.py` — 21 个测试全部通过

**验收标准**:
- [x] 市场宽度统计正确计算 (涨停阈值按板块适配: 主板10%, 创业板20%, 北交所30%)
- [x] 数据库存储每日快照 (sq_market_breadth)
- [x] 市场情绪参与规则背景修正
- [x] 前端展示市场情绪概览 (Dashboard 顶部)
- [x] API 端点可查询历史市场宽度 (GET /api/market/breadth?days=7)
- [x] 21 个单元测试通过

---

### 任务 5.4: 龙虎榜数据接入 ✅ **(已完成 2026-05-20)**

**目标**: 接入龙虎榜数据，识别机构/游资行为。

**实现路径**:

#### 步骤 5.4.1 — 数据抓取 ✅

**新建文件**: `quant_loom/data_ingestion/lhb_fetcher.py`

```python
class LHBFetcher:
    def fetch_lhb_detail(self, trade_date=None) -> pd.DataFrame
    # ak.stock_lhb_detail_em() — 龙虎榜明细
    def fetch_lhb_top_list(self, period="近一月") -> pd.DataFrame
    # ak.stock_lhb_stock_statistic_em() — 个股上榜统计
    def fetch_features(self, candidate_codes=None) -> dict
    # 批量提取: lhb_stocks, lhb_inst_stocks, lhb_top_month
```

- 机构席位检测: 上榜原因含 "机构专用" 字样自动标记
- 节流控制: `_throttle(1.5s)` + `@network_retry` 重试

#### 步骤 5.4.2 — 数据模型 ✅

**修改文件**: `quant_loom/storage/models.py`

```python
class LHBDetail(Base):
    __tablename__ = "sq_lhb_detail"
    # trade_date, code, name, close, pct_change, turnover_rate,
    # lhb_net_amount, lhb_buy_amount, lhb_sell_amount,
    # reason (上榜原因), has_inst_seat (是否有机构席位)
```

#### 步骤 5.4.3 — 管线集成与规则 ✅

**修改文件**: `config/rules.yaml` — 新增 `lhb_tracking` 配置段
**修改文件**: `quant_loom/rule_engine/rules.py` — 新增 `check_lhb_tracking()` 方法
**修改文件**: `quant_loom/rule_engine/scanner.py` — `scan()` / `scan_and_format()` 接收 `lhb_features` 参数
**修改文件**: `scripts/run_scanner.py` — [2d] 步骤拉取 LHB 特征 → 传入扫描管线

**规则逻辑**:
- 龙虎榜净买额 ≥ 5000 万 → 触发
- 机构席位参与 → 置信度 +0.20
- 无机构但净买额 ≥ 2 亿 (游资主导) → 置信度 +0.10
- 近一月上榜 ≥ 3 次 → +0.15; ≥ 2 次 → +0.08
- 当日涨幅 ≥ 5% → +0.05
- 置信度上限 0.95; ≥ 0.75 → P1, 否则 P2

#### 步骤 5.4.4 — 单元测试 ✅

**新建文件**: `tests/test_lhb.py` — 24 个测试全部通过

**验收标准**:
- [x] 龙虎榜数据正常抓取 (LHBFetcher 三大接口)
- [x] MySQL 存储上榜明细 (LHBDetail 模型)
- [x] 新增 lhb_tracking 异动类型 (6 类异动信号之第 6 类)
- [x] 管线集成完整 (run_scanner.py [2d] 步骤)
- [x] 24 个单元测试全部通过

---

### 任务 5.5: 前端增强 ✅ **(已完成 2026-05-20)**

**目标**: K线图、暗色主题、实时推送、信号回测可视化。

#### 步骤 5.5.1 — K 线图组件 ✅

**新建文件**: `frontend/src/components/KLineChart.vue`

功能: (全部实现)
- ECharts candlestick + MA(5/10/20/60/120) overlay
- 成交量副图 (红涨绿跌)
- MACD 副图 (DIF/DEA/柱)
- BOLL 上下轨叠加
- 支持拖拽缩放时间范围 (DataZoom inside + slider)

#### 步骤 5.5.2 — 暗色主题 ✅

**修改文件**: `frontend/src/styles/global.css`, `frontend/src/components/AppHeader.vue`, `frontend/src/utils/echarts-theme.ts`

- CSS 变量暗色主题 (`[data-theme="dark"]`) — 完整 30+ 变量覆盖
- 系统偏好自动检测 (`prefers-color-scheme: dark` 媒体查询)
- 主题切换按钮 ☀️/🌙 (localStorage 持久化)
- ECharts `quantloom-dark` 暗色配色方案注册
- 全部 7 个 ECharts 组件使用 `getEchartsTheme()` 动态加载主题

#### 步骤 5.5.3 — WebSocket 实时推送 ✅

**新建文件**: `frontend/src/composables/useWebSocket.ts`
**修改文件**: `quant_loom/api/app.py` — 新增 `/ws/alerts` WebSocket 端点
**修改文件**: `scripts/run_scanner.py` — P1 告警自动广播到 WebSocket 客户端
**修改文件**: `frontend/src/components/AppHeader.vue` — 实时 toast 弹窗

**功能**:
- FastAPI WebSocket 端点 `/ws/alerts` + `ConnectionManager` 管理连接
- 自动重连 (指数退避, max 30s) + 心跳 ping/pong
- 扫描管线 P1 告警入库后自动广播到前端
- 前端实时 toast 弹窗 (6 秒自动消失, 点击可跳转)

#### 步骤 5.5.4 — 信号回测展示 ✅

**修改文件**: `frontend/src/views/AlertDetail.vue` — 已完成

- 告警详情页显示 "该类型历史 T+1/3/5 胜率"、"平均收益"
- 调用 `/api/backtest/type-stats` 数据渲染 (BacktestComparison 组件已嵌入)

**验收标准**:
- [x] K 线图组件可用
- [x] 暗色主题可切换 (CSS变量 + localStorage + ECharts暗色)
- [x] WebSocket 告警实时弹窗 (/ws/alerts + useWebSocket + toast)
- [x] 告警详情页显示历史回测统计

---

## 第 6 阶段：深度分析与风控

---

### 任务 6.1: 财务数据接入 ✅ **(已完成 2026-05-20)**

**目标**: 接入基本面数据，为多因子模型提供数据基础。

**新建文件**: `quant_loom/data_ingestion/finance_fetcher.py`

```python
class FinanceFetcher:
    def _throttle(self, seconds: float)  # AkShare 请求节流
    def _call_ak(self, func, *args, **kwargs)  # 统一调用+异常处理
    def fetch_performance(self, date=None) -> pd.DataFrame  # 业绩报表 (stock_yjbb_em)
    def fetch_express_report(self, date=None) -> pd.DataFrame  # 业绩快报 (stock_yjkb_em)
    def fetch_income_statement(self, code, date=None) -> pd.DataFrame  # 利润表 (stock_profit_sheet_by_report_ths)
    def fetch_balance_sheet(self, code, date=None) -> pd.DataFrame  # 资产负债表
    def fetch_cash_flow(self, code, date=None) -> pd.DataFrame  # 现金流量表
    def fetch_key_metrics(self, code, date=None) -> dict  # ROE/ROA/PE/PB/毛利率/净利率/资产负债率/营收增速/利润增速/EPS
    def fetch_features(self, candidate_codes=None) -> dict  # 批量获取 (performance + metrics_map)
```

使用接口:
- `ak.stock_yjbb_em()` — 业绩报表 (东方财富)
- `ak.stock_yjkb_em()` — 业绩快报
- `ak.stock_profit_sheet_by_report_ths()` — 利润表 (同花顺)
- `ak.stock_balance_sheet_by_report_ths()` — 资产负债表
- `ak.stock_cash_flow_sheet_by_report_ths()` — 现金流量表
- `ak.stock_financial_analysis_indicator()` — 财务分析指标
- `ak.stock_a_lg_indicator()` — 行业领先指标

**修改文件**: `quant_loom/storage/models.py` — 新增 `FinancialMetrics` 模型 → `sq_financial_metrics` 表 (13 字段)

**验收标准**:
- [x] 财务数据三大报表可抓取
- [x] 关键财务指标 (ROE/ROA/PE/PB/毛利率/净利率/EPS等) 可批量获取
- [x] `sq_financial_metrics` 表可自动创建
- [x] `GET /api/finance/metrics/{code}` + `GET /api/finance/performance` API 端点可用
- [x] 测试覆盖 (4 tests)

---

### 任务 6.2: 多因子模型 ✅ **(已完成 2026-05-20)**

**目标**: 构建 Alpha 因子库，验证因子有效性。

**新建文件**: `quant_loom/feature_engineering/factors.py`

因子清单 (14 个因子，5 大类):
- 估值: EP (1/PE), BP (1/PB), SP (1/PS)
- 成长: revenue_growth, profit_growth
- 质量: ROE, ROA, gross_margin, net_margin, debt_burden (负向)
- 动量: momentum_1m, momentum_3m
- 波动: volatility, beta_proxy

```python
class AlphaFactors:
    @staticmethod
    def ep_factor(metrics_map: dict) -> pd.Series
    @staticmethod
    def bp_factor(metrics_map: dict) -> pd.Series
    # ... 14 个因子方法
    @staticmethod
    def compute_all_factors(metrics_map: dict) -> pd.DataFrame  # 批量计算
    @staticmethod
    def compute_composite_score(factor_df: pd.DataFrame) -> pd.Series  # 0-100 综合评分 (z-score 归一化 + 等权)
```

**新建文件**: `quant_loom/feature_engineering/factor_eval.py`

因子评估:
- IC (Information Coefficient) — Spearman Rank IC
- IR (Information Ratio) — IC 均值 / IC 标准差
- 分层回测 (5-quantile, 单调性检验)
- 批量评估 (evaluate_all → IC/abs_IC/top_bottom_spread/monotonicity)
- 最优权重 (IC 绝对值加权, 归一化)

```python
class FactorEvaluator:
    @staticmethod
    def information_coefficient(factor, forward_returns) -> float  # Spearman Rank IC
    @staticmethod
    def information_ratio(factor, forward_returns) -> dict
    @staticmethod
    def layered_backtest(factor, forward_returns, n_groups=5) -> dict  # → groups/spread/monotonicity
    @staticmethod
    def evaluate_all(factor_df, forward_returns) -> pd.DataFrame  # 批量评估
    @staticmethod
    def optimal_weights(factor_df, forward_returns, min_weight=0.02) -> dict  # IC 加权
```

**验收标准**:
- [x] 14 个 Alpha 因子可批量计算
- [x] IC/IR/分层回测/最优权重要素齐全
- [x] 综合评分 0-100 归一化输出
- [x] 测试覆盖 (10 tests)

---

### 任务 6.3: 板块轮动热力图 ✅ **(已完成 2026-05-20)**

**目标**: 行业涨跌幅 × 时间维度的轮动热力图。

**新建文件**: `frontend/src/components/SectorRotationHeatmap.vue`
**新建文件**: `quant_loom/data_ingestion/sector_rotation.py`

**后端**:
- `SectorRotationFetcher` 类 — 基于同花顺 (THS) 行业板块指数数据
- `fetch_sector_list()` — 获取行业板块列表 (含当日涨跌幅/成交额)
- `fetch_sector_history(symbol, start_date, end_date)` — 单个行业历史 K 线
- `compute_rotation_matrix(lookback_days=20)` — 构建 sectors×dates 收益矩阵
- 按成交额排序取前 30 个活跃板块，节流 1s/请求

**API**: `GET /api/sectors/rotation?weeks=4` — 返回:
- `sectors`: 行业名称列表
- `dates`: 日期列表
- `data`: 涨跌幅矩阵 (百分比)
- `latest_ranking`: 最新日排名
- `momentum_ranking`: 期间动量排名 (累计收益 + 日均收益)

**前端**: `SectorRotationHeatmap.vue`
- ECharts heatmap: 行=行业, 列=日期, 颜色=红涨绿跌 (symmetric around 0)
- VisualMap 图例 (涨/跌)
- 回溯周数选择器 (2/4/6/8 周)
- 期间动量排名 Top 5 列表
- 响应式布局 (移动端 360px 高度)
- 暗色主题支持 (`getEchartsTheme()`)

**验收标准**:
- [x] 行业板块列表可正常获取 (THS 数据源)
- [x] 板块历史指数 K 线可拉取
- [x] 轮动矩阵正确计算 (sectors × dates × pct_change)
- [x] API 端点 `/api/sectors/rotation` 可用
- [x] 前端热力图组件渲染正常
- [x] 前端构建无错误

---

### 任务 6.4: 持仓风险分析 ✅ **(已完成 2026-05-20)**

**目标**: 为持仓组合提供 VaR、最大回撤、相关性等风险指标。

**新建文件**: `quant_loom/feature_engineering/risk.py`

```python
class RiskAnalyzer:
    @staticmethod
    def var(returns: pd.Series, confidence: float = 0.95) -> float  # 历史 VaR
    @staticmethod
    def cvar(returns: pd.Series, confidence: float = 0.95) -> float  # CVaR (尾部期望损失)
    @staticmethod
    def max_drawdown(nav: pd.Series) -> float  # 历史最大回撤
    @staticmethod
    def max_drawdown_from_returns(returns: pd.Series) -> float  # 从收益率计算最大回撤
    @staticmethod
    def sharpe_ratio(returns: pd.Series, rf: float = 0.02) -> float  # 夏普比率
    @staticmethod
    def sortino_ratio(returns: pd.Series, rf: float = 0.02) -> float  # 索提诺比率 (下行风险)
    @staticmethod
    def beta(stock_returns, benchmark_returns) -> float  # Beta 系数
    @staticmethod
    def correlation_matrix(returns_df: pd.DataFrame) -> pd.DataFrame  # 相关性矩阵
    @staticmethod
    def portfolio_risk_report(returns_df: pd.DataFrame) -> dict  # 综合风险报告
    @staticmethod
    def returns_from_klines(klines_map: dict) -> pd.DataFrame  # K线 → 收益率
```

**修改文件**: `quant_loom/api/app.py` — `GET /api/portfolio/risk` 端点

**验收标准**:
- [x] 全部风险指标可独立计算
- [x] 综合风险报告输出 (sharpe/max_dd/var_95/cvar_95/n_stocks/correlation)
- [x] API 端点 `/api/portfolio/risk` 可用
- [x] 测试覆盖 (17 tests)

---

### 任务 6.5: 止损/止盈建议 ✅ **(已完成 2026-05-20)**

**目标**: 基于技术指标提供动态止损位。

**新建文件**: `quant_loom/feature_engineering/stop_loss.py`

```python
class StopLossCalculator:
    @staticmethod
    def atr_stop(kline, multiplier=2.0, period=14) -> dict  # ATR 动态止损 (最高价 - N×ATR)
    @staticmethod
    def ma_stop(kline, period=20) -> dict  # 均线止损 (跌破MA即止损)
    @staticmethod
    def swing_low_stop(kline, lookback=20) -> dict  # 摆动低点止损 (N日最低点)
    @staticmethod
    def trailing_stop(kline, pct=5.0) -> dict  # 移动止盈 (最高点回撤N%)
    @staticmethod
    def compute_all_stops(kline) -> dict  # 计算全部止损位
    @staticmethod
    def suggest_stop(kline, risk_tolerance="medium") -> dict  # 风险偏好推荐 (tight/medium/loose)
```

**修改文件**: `quant_loom/api/app.py` — `GET /api/stops/{code}` 端点

**验收标准**:
- [x] 4 种止损策略全部可计算 (ATR/MA/SwingLow/Trailing)
- [x] 风险偏好推荐逻辑 (tight → ATR+MA, medium → ATR+SwingLow, loose → SwingLow+MA)
- [x] API 端点 `/api/stops/{code}` 可用
- [x] 测试覆盖 (12 tests)

---

### 任务 6.6: LLM 分析增强 ✅ **(已完成 2026-05-20)**

**目标**: 提升 AI 分析质量。

**修改文件**: `quant_loom/ai_analyzer/llm_client.py`

- 在 `ANALYSIS_SYSTEM_PROMPT` 中注入 3 个 few-shot 示例 (高质量/中等/低质量信号)
- 增加历史上下文: `{historical_context}` 占位符 — 同一 code 之前的 AI 分析结论
- 多步推理 prompt (Chain-of-Thought): 资金面→事件面→技术面→综合判断
- `ANALYSIS_USER_TEMPLATE` 新增 `{historical_context}` 字段

**验收标准**:
- [x] Few-shot 示例融入 system prompt (3 个分层示例: 0.88/0.55/0.35)
- [x] 同一标的连续告警时带上历史 AI 摘要
- [x] 多步推理模板生效 (4 步推理框架)
- [x] 所有 3 个 LLM provider (llama/openai/anthropic) 共用增强 prompt

---

## 实施顺序

```
第 5 阶段:
  5.1 技术指标体系 ✅ 已完成 (2026-05-20)
  5.3 市场宽度统计 ✅ 已完成 (2026-05-20)
  5.2 北向资金 ✅ 已完成 (2026-05-20)
  5.4 龙虎榜 ✅ 已完成 (2026-05-20)
  5.5 前端增强 ✅ 已完成 (2026-05-20)

第 6 阶段 (全部已完成):
  6.1 财务数据 ✅ → 6.2 多因子模型 ✅ → 6.3 板块轮动 ✅ → 6.4 风险分析 ✅ → 6.5 止损建议 ✅ → 6.6 LLM增强 ✅
```

## 进度总览

| 阶段 | 任务 | 状态 | 完成率 |
|------|------|------|--------|
| 5 | 5.1-5.5 信号增强 | ✅ 全部完成 | 100% (5/5) |
| 6 | 6.1-6.6 深度分析 | ✅ 全部完成 | 100% (6/6) |
| 7 | 7.1-7.2 管线集成+新模式 | ✅ 全部完成 | 100% (2/2) |

## 文件变更总览

### 新建文件
| 文件 | 所属任务 | 状态 |
|------|---------|-------|
| `quant_loom/feature_engineering/technical.py` | 5.1 | ✅ 已创建 |
| `quant_loom/feature_engineering/market_breadth.py` | 5.3 | ✅ 已创建 |
| `quant_loom/data_ingestion/north_flow_fetcher.py` | 5.2 | ✅ 已创建 |
| `frontend/src/components/KLineChart.vue` | 5.5 | ✅ 已创建 |
| `frontend/src/components/MarketBreadthCard.vue` | 5.3 | ✅ 已创建 |
| `frontend/src/components/NorthFlowCard.vue` | 5.2 | ✅ 已创建 |
| `tests/test_technical.py` | 5.1 | ✅ (31 tests) |
| `tests/test_market_breadth.py` | 5.3 | ✅ (21 tests) |
| `tests/test_north_flow.py` | 5.2 | ✅ (15 tests) |
| `quant_loom/data_ingestion/lhb_fetcher.py` | 5.4 | ✅ 已创建 |
| `quant_loom/data_ingestion/finance_fetcher.py` | 6.1 | ✅ 已创建 |
| `quant_loom/feature_engineering/factors.py` | 6.2 | ✅ 已创建 |
| `quant_loom/feature_engineering/factor_eval.py` | 6.2 | ✅ 已创建 |
| `quant_loom/feature_engineering/risk.py` | 6.4 | ✅ 已创建 |
| `quant_loom/feature_engineering/stop_loss.py` | 6.5 | ✅ 已创建 |
| `quant_loom/data_ingestion/sector_rotation.py` | 6.3 | ✅ 已创建 |
| `quant_loom/data_ingestion/block_trade_fetcher.py` | 7.2 | ✅ 已创建 |
| `frontend/src/components/SectorRotationHeatmap.vue` | 6.3 | ✅ 已创建 |
| `frontend/src/composables/useWebSocket.ts` | 5.5 | ✅ 已创建 |
| `tests/test_lhb.py` | 5.4 | ✅ (24 tests) |
| `tests/test_factors.py` | 6.1/6.2 | ✅ (16 tests) |
| `tests/test_risk.py` | 6.4 | ✅ (17 tests) |
| `tests/test_stop_loss.py` | 6.5 | ✅ (12 tests) |

### 修改文件
| 文件 | 涉及任务 | 状态 |
|------|---------|-------|
| `config/rules.yaml` | 5.1, 5.4 | ✅ 技术共振+lhb_tracking |
| `quant_loom/rule_engine/scanner.py` | 5.1, 5.4 | ✅ 技术共振+LHB集成 |
| `quant_loom/api/app.py` | 5.1, 5.2, 5.3, 5.5 | ✅ K线+北向+市场宽度+回测完成 |
| `scripts/run_scanner.py` | 5.1, 5.2, 5.3, 5.4 | ✅ 全部集成 |
| `quant_loom/storage/models.py` | 5.2, 5.3, 5.4 | ✅ 北向+市场宽度+LHB完成 |
| `frontend/src/views/Dashboard.vue` | 5.2, 5.3, 5.5, 6.3 | ✅ 市场情绪+北向+轮动热力图已集成 |
| `frontend/src/views/AlertDetail.vue` | 5.1, 5.5 | ✅ KLineChart+Backtest 已集成 |
| `frontend/src/stores/dashboard.ts` | 5.2, 5.3 | ✅ fetchBreadth+fetchNorthFlow |
| `frontend/src/styles/global.css` | 5.5 | ✅ 纯白背景+暗色主题CSS变量 |
| `frontend/src/utils/echarts-theme.ts` | 5.5 | ✅ quantloom-dark 主题+getEchartsTheme() |
| `quant_loom/rule_engine/rules.py` | 5.4 | ✅ check_lhb_tracking() 已添加 |
| `quant_loom/ai_analyzer/llm_client.py` | 6.6 | ✅ Few-shot+CoT+历史上下文 |
| `quant_loom/storage/models.py` | 6.1 | ✅ FinancialMetrics 模型 |
| `requirements.txt` | 6.2 | ✅ 新增 scipy |
| `frontend/src/components/AppHeader.vue` | 5.5 | ✅ 主题切换+WebSocket toast |
| `scripts/run_scanner.py` | 6.x, 7.x | ✅ 财务+因子+大宗交易管线接入 |
| `quant_loom/rule_engine/rules.py` | 7.x | ✅ 缺口回补+大宗+高换手+盘中急拉 (4 rules) |
| `quant_loom/rule_engine/scanner.py` | 6.x, 7.x | ✅ technical_features+block_trade 参数传递 |
| `quant_loom/feature_engineering/technical.py` | 7.x | ✅ prev_close/today_open/today_high/today_low 字段 |
| `quant_loom/data_ingestion/block_trade_fetcher.py` | 7.x | ✅ 已创建 |
| `tests/test_rule_engine.py` | 7.x | ✅ 22 → 44 tests |

---

## 第 7 阶段：信号增强补充 (2026-05-20)

### 任务 7.1: Phase 6 管线集成 ✅

**目标**: 将 Phase 6 独立模块接入 `run_scanner.py` 日常扫描管线。

- [x] `FinanceFetcher` + `AlphaFactors` 接入: 预扫描候选股基本面因子计算 → 截面排名 → 置信度修正 (±0.08~+0.10)
- [x] `_factor_score()` 函数: 基于因子截面百分位的置信度映射
- [x] 因子得分 Top 5 日志输出

### 任务 7.2: 4 种新异动模式 ✅

**目标**: 从 6 类扩展至 10 类异动信号。

| # | 类型 | 说明 | 所需数据 |
|---|------|------|---------|
| 7 | gap_fill | 缺口回补 — 跳空后价格回补缺口 | K线 prev_close + today O/H/L |
| 8 | block_trade | 大宗交易 — 折溢价异常的大额交易 | 大宗交易明细 (AkShare `stock_dzjy_mrmx`) |
| 9 | high_turnover_low_return | 高换手低涨幅 — 换庄/洗盘信号 | 行情 turnover_rate + pct_change |
| 10 | intraday_spike | 盘中急拉/急跌 — 日内振幅异常 | K线 today O/H/L |

- [x] `check_gap_fill()` (5 tests): 缺口检测 + 回补比例 + 量能确认
- [x] `check_block_trade()` (6 tests): 溢价/折价 + 成交额过滤
- [x] `check_high_turnover_low_return()` (5 tests): 换手率+涨跌幅+成交额
- [x] `check_intraday_spike()` (6 tests): 盘中拉升/下跌/宽幅震荡
- [x] `BlockTradeFetcher`: 大宗交易聚合特征提取 (加权平均折溢价率)
- [x] `rules.yaml` 新增 4 段配置
- [x] `scanner.py` `scan()` 新增 4 个规则调用
- [x] `technical.py` 新增 prev_close/today_open/today_high/today_low 字段
- [x] `run_scanner.py` [2e] 大宗交易拉取 + 参数传递
