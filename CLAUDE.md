# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a design/planning-phase repository containing architectural blueprints for two distinct systems. No code has been written yet.

### System 1: AI-WhaleWatcher (`docs/quant_loom.md`)

A-share (Chinese stock market) institutional capital flow anomaly detection and early warning system. Full-market coverage (5000+ stocks) with multi-source fusion of fund flow, price action, news sentiment, and research reports.

- **Language**: Python 3.11
- **Data sources**: AkShare / Tushare
- **Storage**: PostgreSQL (business data), Redis (caching/dedup), optional ClickHouse/TimescaleDB for high-throughput time-series
- **Task scheduling**: APScheduler (prototype) → Celery + Redis/RabbitMQ (production)
- **AI integration**: LLM APIs (GPT/DeepSeek/Claude) for structured JSON attribution; RAG via pgvector/Milvus/Elasticsearch for document retrieval

**Architecture**: Event-driven, 7-layer decoupled pipeline:
1. Collection → 2. Cleaning → 3. Feature Engineering → 4. Rule Engine → 5. Model (LLM/RAG) → 6. Service (alerts, reports, API) → 7. Operations (monitoring, logging)

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

- Zero commits on `master`; no source code exists
- Two untracked design documents in `docs/`: `doc.md`, `quant_loom.md`
- Implementation work should begin by referring to the detailed specs in these documents
- No build system, test framework, or CI/CD has been configured
