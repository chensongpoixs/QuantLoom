# QuantLoom·量梭 安装与部署指南

> 从零开始部署全市场 A 股机构动向 AI 监控与预警系统

---

## 环境要求

| 组件 | 最低版本 | 说明 |
|------|---------|------|
| Python | 3.10+ | 推荐 3.12，配套 Conda 环境 |
| Node.js | 18+ | 前端构建使用，推荐 20+ |
| MySQL | 8.0+ | 业务数据存储 |
| Redis | 6.0+ | 缓存与去重 (可选，支持优雅降级) |
| Conda / Miniconda | 任意版本 | Python 环境隔离 |

---

## 一、环境准备

### 1.1 安装 Conda

```bash
# 下载 Miniconda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
# 重启终端或 source ~/.bashrc
```

### 1.2 创建 Python 环境

```bash
conda create -n quant_loom python=3.12 -y
conda activate quant_loom
```

### 1.3 安装 Node.js (用于前端构建)

```bash
# 方式一: 使用 NodeSource (推荐)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# 方式二: 使用系统包管理器
sudo apt install nodejs npm

# 验证安装
node --version   # 应显示 v18+
npm --version    # 应显示 v9+
```

### 1.4 安装 MySQL

```bash
# Ubuntu / Debian
sudo apt install mysql-server
sudo systemctl start mysql
sudo systemctl enable mysql

# 创建数据库
mysql -u root -p <<'SQL'
CREATE DATABASE quant_loom CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'quantloom'@'localhost' IDENTIFIED BY 'your_password_here';
GRANT ALL PRIVILEGES ON quant_loom.* TO 'quantloom'@'localhost';
FLUSH PRIVILEGES;
SQL
```

### 1.5 安装 Redis (可选)

```bash
# Ubuntu / Debian
sudo apt install redis-server
sudo systemctl start redis

# 验证
redis-cli ping   # 应返回 PONG
```

---

## 二、项目安装

### 2.1 克隆项目

```bash
cd /path/to/workspace
git clone <your-repo-url> quant_loom
cd quant_loom
```

### 2.2 安装 Python 依赖

```bash
# 默认源
pip install -r requirements.txt

# 或使用镜像加速
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2.3 安装前端依赖

```bash
cd frontend
npm install
cd ..
```

---

## 三、配置

### 3.1 基础配置

```bash
# 从模板创建环境变量文件
cp .env.example .env

# 编辑 .env，填入实际配置
nano .env
```

**.env 核心配置项：**

```bash
# ---- 数据源 ----
DATA_SOURCE=akshare                      # "xtick" (需 token) 或 "akshare" (免费)
XTICK_TOKEN=                             # http://www.xtick.top 注册 (xtick 模式)

# ---- MySQL ----
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=quantloom
MYSQL_PASSWORD=your_password_here
MYSQL_DATABASE=quant_loom

# ---- Redis (可选) ----
REDIS_HOST=localhost
REDIS_PORT=6379

# ---- LLM (三选一) ----
# llama.cpp (优先)
LLAMA_BASE_URL=http://localhost:8080/v1
LLAMA_MODEL=qwen3-32b

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=
OPENAI_MODEL=gpt-4o-mini

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6
```

### 3.2 规则配置

规则阈值在 `config/rules.yaml` 中，可根据需要调整：

```bash
# 查看当前规则
cat config/rules.yaml
```

---

## 四、初始化数据库

```bash
# 方式一：Python 脚本 (推荐)
python scripts/init_db.py

# 方式二：直接导入 SQL
mysql -u quantloom -p quant_loom < scripts/init_db.sql
```

建表成功后，MySQL 中将包含以下 9 张表：

| 表名 | 说明 |
|------|------|
| `sq_stock_master` | 股票基础信息 |
| `sq_stock_quote_snapshot` | 行情快照 |
| `sq_stock_fund_flow` | 资金流记录 |
| `sq_stock_alerts` | 异动事件结果 |
| `sq_notification_log` | 通知发送日志 |
| `sq_stock_events` | 新闻/公告/研报 |
| `sq_fund_flow_daily` | 每日资金流累积 |
| `sq_backtest_results` | 回测结果 |
| `sq_alert_feedback` | 告警反馈 |

---

## 五、验证安装

### 5.1 运行测试

```bash
pytest tests/ -v
# 应显示 214 passed
```

### 5.2 执行一次扫描

```bash
# 跳过 AI 分析快速验证
python scripts/run_scanner.py --top 0

# 如果数据源正常，将看到扫描结果
```

---

## 六、启动服务

### 6.1 后端 API (必需)

```bash
uvicorn quant_loom.api.app:app --host 0.0.0.0 --port 9090
```

验证：

```bash
curl http://localhost:9090/health
# → {"status":"ok","checks":{"mysql":"ok","redis":"ok"}}

curl http://localhost:9090/api/alerts
# → {"total":...,"page":1,...}
```

### 6.2 前端看板

**开发模式** (前后端分离)：

```bash
cd frontend
npm run dev
# → 访问 http://localhost:5173
```

**生产模式** (单进程部署)：

```bash
cd frontend
npm run build
cd ..
uvicorn quant_loom.api.app:app --host 0.0.0.0 --port 9090
# → 访问 http://localhost:9090
```

### 6.3 前端配置 (`frontend/dist/config.js`)

生产部署后，如需修改后端地址，直接编辑 `frontend/dist/config.js`：

```js
window.__QUANTLOOM_CONFIG__ = {
  apiBaseUrl: 'http://192.168.1.100:9090',  // 修改为实际后端地址
  appTitle: 'QuantLoom·量梭',
  timeout: 15000,
  pageSize: 20,
  trendDays: 7,
};
```

修改后刷新浏览器即可，无需重新构建。

### 6.4 定时调度 (Celery)

```bash
# 启动 Worker
celery -A quant_loom.tasks.celery_app worker -l info --concurrency=2 &

# 启动 Beat 定时器
celery -A quant_loom.tasks.celery_app beat -l info &
```

定时任务：
- 盘中每 5 分钟扫描全市场
- 每个工作日 16:05 发送收盘日报

---

## 七、通知配置 (可选)

### 7.1 邮件

在 `.env` 中配置 SMTP：

```bash
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=alert@example.com
SMTP_PASSWORD=your_password
SMTP_FROM=alert@example.com
ALERT_EMAIL_TO=you@example.com
```

### 7.2 企业微信机器人

在群里添加机器人，将 Webhook URL 填入 `.env`：

```bash
WECOM_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
```

### 7.3 飞书机器人

```bash
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
```

### 7.4 钉钉机器人

```bash
DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=xxx
```

---

## 八、常用命令速查

```bash
# ---- 运行 ----
python scripts/run_scanner.py                  # 完整扫描 (AI 分析 top 10)
python scripts/run_scanner.py --top 20         # AI 分析 top 20
python scripts/run_scanner.py --top 0          # 跳过 AI
python scripts/run_scanner.py --dry-run        # 仅扫描，不写库
python scripts/run_scanner.py --skip-events    # 跳过事件抓取

# ---- 回测 ----
python scripts/run_backtest.py --start 2024-01-01 --end 2024-06-30
python scripts/run_backtest.py --date 2024-06-15 --codes 000001

# ---- 调优 ----
python scripts/run_tuning.py --alert breakout --start 2024-01-01 --end 2024-12-31
python scripts/run_tuning.py --all

# ---- API ----
uvicorn quant_loom.api.app:app --host 0.0.0.0 --port 9090
#   GET  /health                   健康检查
#   GET  /health/ready             K8s readiness
#   GET  /health/live              K8s liveness
#   GET  /metrics                  Prometheus 指标
#   GET  /api/alerts               分页告警列表
#   GET  /api/alerts/{id}          告警详情
#   GET  /api/stats/summary        仪表盘摘要
#   GET  /api/stats/trend          趋势数据
#   GET  /api/stocks/search?q=    股票搜索
#   POST /feedback                 人工反馈

# ---- 前端 ----
cd frontend && npm run dev          # 开发模式
cd frontend && npm run build        # 构建生产环境
cd frontend && npm run preview      # 预览构建结果

# ---- Celery ----
celery -A quant_loom.tasks.celery_app worker -l info --concurrency=2 &
celery -A quant_loom.tasks.celery_app beat -l info &

# ---- 测试 ----
pytest tests/ -v                              # 全部测试
pytest tests/ -v -k "rule_engine"             # 按关键字筛选
```

---

## 九、故障排查

### MySQL 连接失败

```bash
# 检查服务状态
sudo systemctl status mysql

# 检查端口监听
sudo netstat -tlnp | grep 3306

# 测试连接
mysql -u quantloom -p -h localhost quant_loom -e "SELECT 1"
```

### Redis 连接失败

> Redis 不可用不影响核心流程，系统会自动跳过去重功能。

```bash
# 检查服务状态
sudo systemctl status redis

# 测试连接
redis-cli ping
```

### 前端构建失败

```bash
cd frontend
rm -rf node_modules dist
npm install
npm run build
```

### 数据源无数据

```bash
# akshare 模式 — 检查网络连接 (需要访问东方财富)
curl -s "https://push2.eastmoney.com/" > /dev/null && echo "OK" || echo "FAIL"

# xtick 模式 — 检查 token
curl -s "http://api.xtick.top/doc/market?token=YOUR_TOKEN" | head -c 200
```

---

## 十、生产部署建议

1. **使用 systemd 托管 API 服务**：
   ```ini
   # /etc/systemd/system/quantloom-api.service
   [Unit]
   Description=QuantLoom API Server
   After=network.target mysql.service

   [Service]
   Type=simple
   User=quantloom
   WorkingDirectory=/opt/quant_loom
   ExecStart=/home/quantloom/miniconda3/envs/quant_loom/bin/uvicorn quant_loom.api.app:app --host 0.0.0.0 --port 9090
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

2. **前端构建**：每次部署前 `cd frontend && npm run build`

3. **反向代理** (可选)：使用 Nginx 在 80/443 端口提供统一入口，HTTPS 保护

4. **日志**：loguru JSON 日志写入 `logs/`，建议配置 logrotate

5. **监控**：Prometheus 抓取 `:9090/metrics`，Grafana 面板可视化
