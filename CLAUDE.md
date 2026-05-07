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
- **Task scheduling**: APScheduler (prototype) → Celery + Redis/RabbitMQ (production)
- **AI integration**: Three LLM providers (priority order: llama.cpp > OpenAI > Anthropic). Structured JSON output for anomaly attribution.

**Architecture**: 7-layer decoupled pipeline:
1. Collection (XTick/AkShare) → 2. Cleaning → 3. Feature Engineering → 4. Rule Engine → 5. LLM Analysis → 6. Service (alerts, reports, API) → 7. Operations (monitoring, logging)

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
- **107 unit tests** across 10 test files — all passing (`pytest tests/ -v`)
- **Test files**: `test_rule_engine.py` (18), `test_cleaner.py` (9), `test_dedup.py` (6), `test_fund_flow.py` (19), `test_price.py` (14), `test_scanner.py` (9), `test_event_fetcher.py` (11), `test_event_matcher.py` (11), `test_rag_store.py` (7), plus misc
- Phase 2 (增强分析) completed:
  - Event/news data ingestion via AkShare (`event_fetcher.py`) — stock news, announcements, research reports
  - Event matching via LLM-as-ranker (`event_matcher.py`) — time filter → keyword pre-filter → LLM relevance scoring
  - RAG context store (`rag_store.py`) — MySQL-backed event storage + LLM prompt context building
  - Historical fund flow tracking (`sq_fund_flow_daily` table) — real `consecutive_inflow_days` from history
  - Enhanced AI analysis with real event context in prompts
  - `consecutive_inflow_days_min` restored to 3 in `rules.yaml`
  - Detailed LLM request/response logging (method, URL, headers, full body, tokens, elapsed)
- Remaining limitations:
  - XTick provides no fund flow data → `main_force_ratio` proxied by turnover percentile
  - `near_250d_low` proxied by intraday range position + pct_change (no 250-day history)
  - No Celery task scheduling yet (uses direct function calls)
- Redis gracefully degrades — all `redis_client` methods check `self.client is not None`
- AI analysis gracefully degrades — `_fallback_result()` returns rule-only output when LLM unavailable
- LLM observability: `_log_request()`, `_log_response()`, `_log_completion()` record full request/response body, headers, tokens, and elapsed time

### Quick Start (QuantLoom)

```bash
# Install deps
pip install -r requirements.txt
# Configure
cp .env.example .env
# Edit .env — set DATA_SOURCE (xtick/akshare), MySQL/Redis connections, LLM keys
# Init DB
python scripts/init_db.py
# Run scanner (top 10 AI-analyzed by default)
python scripts/run_scanner.py              # full run
python scripts/run_scanner.py --top 20     # AI analyze top 20
python scripts/run_scanner.py --top 0      # skip AI analysis
python scripts/run_scanner.py --dry-run    # scan only, no DB writes
# Run tests
pytest tests/ -v
```
