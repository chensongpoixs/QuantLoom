# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains two systems: QuantLoom (working Python prototype) and an AI Software Engineering Runtime (Go design doc only).

### System 1: QuantLoom — Working Prototype

A-share (Chinese stock market) institutional capital flow anomaly detection and early warning system. Full-market coverage (5000+ stocks) with multi-source fusion of fund flow, price action, news sentiment, and research reports.

- **Language**: Python 3.12
- **Environment**: Conda environment `quant_loom` — create with `conda create -n quant_loom python=3.12` and activate with `conda activate quant_loom`
- **Data sources**: XTick (api.xtick.top) and AkShare (东方财富) — dual-source, configurable via `DATA_SOURCE` env var ("xtick" or "akshare"). XTick requires a token from http://www.xtick.top.
- **Storage**: MySQL (business data), Redis (caching/dedup — optional, graceful degradation)
- **Task scheduling**: Celery + Redis (Beat 定时调度, Worker 并发执行)
- **AI integration**: Three LLM providers (priority order: llama.cpp > OpenAI > Anthropic). Structured JSON output for anomaly attribution.
- **Monitoring**: Prometheus metrics (10 counters/gauges/histograms), FastAPI health endpoints
- **Notifications**: Email (SMTP), WeCom/Feishu/DingTalk webhooks, NotificationLog audit trail
- **Resilience**: tenacity-based retry (network: 3 attempts exponential backoff, DB: 2 attempts)

**Architecture**: 7-layer decoupled pipeline:
1. Collection (XTick/AkShare) → 2. Cleaning → 3. Feature Engineering → 4. Rule Engine → 5. LLM Analysis → 6. Service (alerts, reports, API) → 7. Operations (monitoring, logging, retry)

**Data layering**: ODS (raw) → DWD (cleaned) → DWS (aggregated) → ADS (results)

**Five anomaly patterns detected**: volume-driven breakout, bottom accumulation, end-of-day buying sprees, event-driven moves, sector-linked moves.

**Core design principle**: Rules filter first ("is it worth looking at?"), AI explains second ("why is it worth looking at?"). Rules are configuration-driven (YAML), not hardcoded. All AI outputs are structured JSON with fields: `summary`, `reason_type`, `confidence_score`, `risk_points`, `evidence`, `action`.

**Implementation phases**:
1. Prototype: data connection, DB modeling, rule scanner, basic alerts
2. Enhanced: news/research report ingestion, RAG, structured AI attribution
3. Production: task queues, monitoring/logging, multi-channel notifications, retry/degradation
4. Optimization: backtesting, parameter tuning, feedback loop

### System 2: AI Software Engineering Runtime (`docs/doc.md`)

A multi-agent AI coding system inspired by Claude Code and Devin. Blueprint for a Go-based CLI that decomposes tasks, modifies code in a local repo, compiles/tests, auto-fixes errors, and supports rollback/audit/observability.

- **Language**: Go
- **Execution**: Sandboxed via Docker/gVisor/Firecracker
- **LLMs**: GPT/DeepSeek/Claude

**Multi-agent architecture**:
- Planner Agent — task decomposition
- Code Agent — code generation/modification
- Debug Agent — automatic error fixing
- Review Agent — code review (security, performance, idioms, architecture)
- Tool Agent — shell/fs/git operations

**Proposed Go package structure**:
```
cmd/cli/                  # Entry point
core/
  orchestrator/           # Central agent scheduler
  planner/                # Task decomposition
  coder/                  # Code generation
  reviewer/               # Code review
  debugger/               # Auto-fix
  tools/                  # Unified tool interface
  sandbox/                # Docker execution layer
  rag/                    # Vector memory
  llm/                    # Model interface
  memory/                 # Session memory
```

**Key capabilities**: Self-healing loop (write → run → fail → read error → fix → retry), RAG-based code memory (vector retrieval of code snippets, error history, API patterns), repository-level understanding (call graphs, module structure, dependencies), full observability (every LLM output, tool call, diff, error/fix cycle).

## Current State

- **QuantLoom**: Working prototype with full pipeline (fetch → clean → pre-scan → event fetch → historical fund flow → rule scan → AI analyze → store → notify)
- **System 2** (AI Coding Runtime): Design-only, in `docs/doc.md`
- **160 unit tests** across 16 test files — all passing (`pytest tests/ -v`)
- **Test files**: `test_rule_engine.py` (18), `test_cleaner.py` (9), `test_dedup.py` (6), `test_fund_flow.py` (19), `test_price.py` (14), `test_scanner.py` (9), `test_event_fetcher.py` (11), `test_event_matcher.py` (11), `test_rag_store.py` (7), `test_retry.py` (13), `test_metrics.py` (5), `test_email.py` (6), `test_webhook.py` (11), `test_api.py` (8), `test_tasks.py` (8)
- Phase 2 (增强分析) completed:
  - Event/news data ingestion via AkShare (`event_fetcher.py`) — stock news, announcements, research reports
  - Event matching via LLM-as-ranker (`event_matcher.py`) — time filter → keyword pre-filter → LLM relevance scoring
  - RAG context store (`rag_store.py`) — MySQL-backed event storage + LLM prompt context building
  - Historical fund flow tracking (`sq_fund_flow_daily` table) — real `consecutive_inflow_days` from history
  - Enhanced AI analysis with real event context in prompts
  - `consecutive_inflow_days_min` restored to 3 in `rules.yaml`
  - Detailed LLM request/response logging (method, URL, headers, full body, tokens, elapsed)
- Phase 3 (生产化) completed:
  - **Retry** (`quant_loom/ops/retry.py`): tenacity-based — `@network_retry` (3x, exp backoff 2s→4s→30s) and `@db_retry` (2x, exp backoff 1s→5s). Applied to all fetchers, LLM calls, webhooks, SMTP.
  - **SMTP fix**: Port 465 → `SMTP_SSL`, Port 587 → `SMTP` + `STARTTLS`
  - **Celery** (`quant_loom/tasks/`): `celery_app.py` + `scanner_tasks.py` — Beat schedule runs `scan_task` every 5 min + `closing_report_task` at 16:05 weekdays
  - **DingTalk** (`webhook.py`): Markdown format, P1 @所有人. WeCom/Feishu/DingTalk all with `@network_retry`
  - **NotificationLog**: All channels (wecom/feishu/dingtalk/email) write to `sq_notification_log` with alert foreign key
  - **Prometheus** (`quant_loom/ops/metrics.py`): 10 metrics — pipeline runs, duration, alerts, notifications, data fetch, API calls, errors, DB health, retries, build info
  - **FastAPI** (`quant_loom/api/app.py`): `GET /health`, `/health/ready`, `/health/live`, `/metrics`
  - **Pipeline instrumentation** (`scripts/run_scanner.py`): data_fetch_duration, alerts_produced, pipeline_duration, pipeline_runs
- Remaining limitations:
  - XTick provides no fund flow data → `main_force_ratio` proxied by turnover percentile
  - `near_250d_low` proxied by intraday range position + pct_change (no 250-day history)

### Quick Start (QuantLoom)

```bash
# Install deps
pip install -r requirements.txt
# Configure
cp .env.example .env
# Edit .env — set DATA_SOURCE (xtick/akshare), MySQL/Redis connections, LLM keys
# Init DB
python scripts/init_db.py

# --- Manual run ---
python scripts/run_scanner.py              # full run (AI analyze top 10)
python scripts/run_scanner.py --top 20     # AI analyze top 20
python scripts/run_scanner.py --top 0      # skip AI analysis
python scripts/run_scanner.py --dry-run    # scan only, no DB writes
python scripts/run_scanner.py --skip-events # skip event fetching

# --- Scheduled run (Celery) ---
celery -A quant_loom.tasks.celery_app worker -l info --concurrency=2 &
celery -A quant_loom.tasks.celery_app beat -l info &
# Or via scripts:
bash scripts/start_worker.sh
bash scripts/start_beat.sh

# --- API server ---
uvicorn quant_loom.api.app:app --host 0.0.0.0 --port 9090

# Verify:
curl localhost:9090/health    # {"status":"ok","checks":{"mysql":"ok","redis":"ok"}}
curl localhost:9090/metrics   # Prometheus 指标

# --- Tests ---
pytest tests/ -v              # all tests
pytest tests/ -v -k "not test_no_duplicates and not test_redis"  # skip Redis
```
