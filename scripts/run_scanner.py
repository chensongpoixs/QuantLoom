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

#!/usr/bin/env python3
"""
One-click full pipeline: fetch -> clean -> pre-scan -> event fetch -> historical fund flow -> rule scan -> AI analyze -> store -> notify
Usage:
  python scripts/run_scanner.py              # single scan (AI analyze top 10)
  python scripts/run_scanner.py --top 20     # AI analyze top 20
  python scripts/run_scanner.py --top 0      # skip AI analysis
  python scripts/run_scanner.py --dry-run    # scan only, no DB writes
  python scripts/run_scanner.py --skip-events # skip event fetching
"""

import sys
import time
from collections import Counter
from datetime import datetime, date
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger
import quant_loom.ops.logger  # noqa: F401 — 初始化文件日志输出

from config.settings import settings
from quant_loom.data_ingestion.cleaner import DataCleaner
from quant_loom.data_ingestion.north_flow_fetcher import NorthFlowFetcher
from quant_loom.data_ingestion.lhb_fetcher import LHBFetcher
from quant_loom.data_ingestion.finance_fetcher import FinanceFetcher
from quant_loom.data_ingestion.block_trade_fetcher import BlockTradeFetcher
from quant_loom.feature_engineering.factors import AlphaFactors
from quant_loom.feature_engineering.technical import TechnicalIndicators
from quant_loom.feature_engineering.market_breadth import MarketBreadth
from quant_loom.rule_engine.scanner import scanner
from quant_loom.rule_engine.dedup import AlertDeduplicator
from quant_loom.ai_analyzer.llm_client import llm_client
from quant_loom.notification.email_sender import email_sender
from quant_loom.notification.webhook import webhook_notifier
from quant_loom.storage.mysql_client import mysql_client
from quant_loom.storage.redis_client import redis_client
from quant_loom.storage.models import StockAlert, StockEvent, FundFlowDaily
from quant_loom.ops.metrics import (
    pipeline_runs,
    pipeline_duration,
    alerts_produced,
    data_fetch_duration,
)


def parse_top_n() -> int:
    """Parse --top N from command line args, default 10"""
    for i, arg in enumerate(sys.argv):
        if arg == "--top" and i + 1 < len(sys.argv):
            return int(sys.argv[i + 1])
    return 10


def main(dry_run: bool = False, top_n: int = 10, skip_events: bool = False):
    trace_id = datetime.now().strftime("%Y%m%d%H%M%S")
    pipeline_start = time.time()
    logger.info(f"=== QuantLoom·量梭 scan start === trace_id={trace_id}")

    # ---- 1. Data fetch ----
    logger.info(f"[1/7] Fetching market data (source={settings.data_source})...")

    if settings.data_source == "akshare":
        from quant_loom.data_ingestion.akshare_fetcher import AkshareFetcher
        fetcher = AkshareFetcher()
    else:
        from quant_loom.data_ingestion.xtick_fetcher import fetcher as xtick_fetcher
        fetcher = xtick_fetcher

    t0 = time.time()
    quotes_raw = fetcher.fetch_realtime_quotes()
    fund_flow_raw = fetcher.fetch_fund_flow_rank()
    data_fetch_duration.labels(source=settings.data_source).observe(time.time() - t0)

    if quotes_raw.empty:
        logger.error("Market data is empty, cannot continue")
        return

    logger.info(f"  Quotes: {len(quotes_raw)} stocks  |  Fund flow: {len(fund_flow_raw)} records")

    # ---- 2. Data cleaning ----
    logger.info("[2/7] Cleaning data...")
    quotes_clean = DataCleaner.clean_quotes(quotes_raw)
    fund_flow_clean = DataCleaner.clean_fund_flow(fund_flow_raw)

    # ---- 2b. Market breadth ----
    market_breadth = MarketBreadth.compute(quotes_clean)
    logger.info(f"  Market breadth: {market_breadth['limit_up_count']}↑ / {market_breadth['limit_down_count']}↓ "
                f"| up/down ratio: {market_breadth['up_down_ratio']} "
                f"| sentiment: {market_breadth['sentiment']} "
                f"| total turnover: {market_breadth['total_turnover']/1e8:.1f}B")

    # Store market breadth snapshot
    if not dry_run and mysql_client.ping():
        try:
            from quant_loom.storage.models import MarketBreadthSnapshot
            snap = MarketBreadthSnapshot(
                limit_up_count=market_breadth["limit_up_count"],
                limit_down_count=market_breadth["limit_down_count"],
                up_count=market_breadth["up_count"],
                down_count=market_breadth["down_count"],
                flat_count=market_breadth["flat_count"],
                up_down_ratio=market_breadth["up_down_ratio"],
                adl=market_breadth["adl"],
                broken_board_count=market_breadth["broken_board_count"],
                avg_pct_change=market_breadth["avg_pct_change"],
                total_turnover=market_breadth["total_turnover"],
                limit_up_pct=market_breadth["limit_up_pct"],
                limit_down_pct=market_breadth["limit_down_pct"],
                sentiment=market_breadth["sentiment"],
            )
            mysql_client.insert_or_update(snap)
        except Exception as e:
            logger.debug(f"Market breadth storage skipped: {e}")

    # ---- 2c. North-bound capital flow ----
    north_features: dict = {}
    try:
        nf_fetcher = NorthFlowFetcher()
        north_features = nf_fetcher.fetch_features()
        logger.info(f"  North flow: today={north_features.get('north_net_inflow_today', 0):.1f}B "
                    f"| 5d avg={north_features.get('north_net_inflow_5d_avg', 0):.1f}B "
                    f"| accel={north_features.get('north_inflow_accel', 0):.1f}% "
                    f"| top10 buys={len(north_features.get('north_top10_net_buy', {}))}")

        # Store north flow daily snapshot
        if not dry_run and mysql_client.ping() and north_features.get("north_net_inflow_today", 0) != 0:
            try:
                from quant_loom.storage.models import NorthFlowDaily
                today = date.today()
                existing = False
                with mysql_client.get_session() as sess:
                    existing = sess.query(NorthFlowDaily).filter(
                        NorthFlowDaily.trade_date == today
                    ).first() is not None
                if not existing:
                    record = NorthFlowDaily(
                        trade_date=today,
                        total_net_inflow=north_features.get("north_net_inflow_today", 0),
                    )
                    mysql_client.insert_or_update(record, lookup_columns=["trade_date"])
            except Exception as e:
                logger.debug(f"North flow storage skipped: {e}")
    except Exception as e:
        logger.warning(f"North flow fetch failed (non-blocking): {e}")

    # ---- 2d. LHB (Dragon-Tiger Board) features ----
    lhb_features: dict = {}
    try:
        lhb_fetcher = LHBFetcher()
        lhb_features = lhb_fetcher.fetch_features()
        if lhb_features.get("lhb_stocks"):
            logger.info(f"  LHB: {len(lhb_features['lhb_stocks'])} on board today "
                        f"({len(lhb_features.get('lhb_inst_stocks', []))} with institutional seats) "
                        f"| top month: {len(lhb_features.get('lhb_top_month', {}))} frequent")
        else:
            logger.info("  LHB: no data today")
    except Exception as e:
        logger.warning(f"LHB fetch failed (non-blocking): {e}")

    # ---- 2e. Block trade features ----
    block_trade_features: dict[str, dict] = {}
    try:
        bt_fetcher = BlockTradeFetcher()
        block_trade_features = bt_fetcher.fetch_features()
        if block_trade_features:
            sig_count = sum(1 for v in block_trade_features.values()
                           if abs(v.get("premium", 0)) >= 3.0)
            logger.info(f"  Block trades: {len(block_trade_features)} stocks "
                        f"({sig_count} with significant premium/discount)")
        else:
            logger.info("  Block trades: no data today")
    except Exception as e:
        logger.warning(f"Block trade fetch failed (non-blocking): {e}")

    # ---- 3. Historical fund flow accumulation + consecutive inflow days ----
    consecutive_inflow_map: dict[str, int] = {}
    if not dry_run and mysql_client.ping():
        logger.info("[3/7] Computing historical fund flow features...")
        today = date.today()
        _upsert_daily_fund_flow(fund_flow_clean, today)
        consecutive_inflow_map = _compute_consecutive_inflow_map(
            list(quotes_clean["code"].unique()) if "code" in quotes_clean.columns else []
        )
        if consecutive_inflow_map:
            has_history = sum(1 for v in consecutive_inflow_map.values() if v >= 3)
            logger.info(f"  Consecutive inflow days computed (>=3d: {has_history} stocks)")
    else:
        logger.info("[3/7] Skipping historical fund flow (dry-run or MySQL unavailable)")

    # ---- 4. Pre-scan + K-line fetch + technical indicators ----
    technical_features: dict[str, dict] = {}
    candidate_codes: list[str] = []

    # Quick pre-scan to get candidate stock codes
    pre_alerts = scanner.scan_and_format(quotes_clean, fund_flow_clean,
                                         consecutive_inflow_map=consecutive_inflow_map)
    candidate_codes = list(set(a["code"] for a in pre_alerts[:50]))

    if candidate_codes:
        logger.info(f"[4/7] Fetching K-lines + computing technicals for {len(candidate_codes)} candidates...")
        tech_success = 0
        for i, code in enumerate(candidate_codes):
            try:
                kline = fetcher.fetch_history(code, period="daily", days=120)
                if kline is not None and not kline.empty and len(kline) >= 20:
                    kline = kline.sort_values("date" if "date" in kline.columns else kline.columns[0])
                    kline = kline.rename(columns={
                        "开盘": "open", "收盘": "close", "最高": "high",
                        "最低": "low", "成交量": "volume",
                    })
                    # Ensure required columns exist
                    for col in ["open", "high", "low", "close", "volume"]:
                        if col not in kline.columns:
                            raise KeyError(f"Missing column: {col}")
                    tech = TechnicalIndicators.compute_latest_features(kline)
                    technical_features[code] = tech
                    tech_success += 1
            except Exception as e:
                logger.debug(f"Technical indicators skipped {code}: {e}")
        logger.info(f"  Technical indicators computed: {tech_success}/{len(candidate_codes)} stocks")

        # ---- 4b. Event fetch ----
        stock_events: dict[str, list] = {}
        if not skip_events and not dry_run:
            logger.info(f"[4b/7] Event fetch for {len(candidate_codes)} candidates...")
            from quant_loom.data_ingestion.event_fetcher import EventFetcher
            event_fetcher = EventFetcher()
            stock_events = event_fetcher.fetch_events_batch(candidate_codes)

            from quant_loom.ai_analyzer.rag_store import RAGStore
            rag = RAGStore()
            all_events = []
            for events in stock_events.values():
                all_events.extend(events)
            rag.deduplicate_and_store(all_events)
            logger.info(f"  Event fetch complete: {len(stock_events)} stocks have event data")
    else:
        stock_events = {}
        logger.info("[4/7] No candidates, skipping K-line/event fetch")

    # ---- 4c. Financial metrics + alpha factor computation ----
    factor_scores: dict[str, float] = {}
    if candidate_codes:
        logger.info(f"[4c/7] Fetching financial metrics + computing alpha factors for {len(candidate_codes)} candidates...")
        try:
            fin_fetcher = FinanceFetcher()
            fin_features = fin_fetcher.fetch_features(candidate_codes=candidate_codes)
            metrics_map = fin_features.get("metrics_map", {})
            if metrics_map:
                factor_df = AlphaFactors.compute_all_factors(metrics_map)
                if not factor_df.empty:
                    composite = AlphaFactors.compute_composite_score(factor_df)
                    factor_scores = composite.to_dict()
                    top5 = sorted(factor_scores.items(), key=lambda x: x[1], reverse=True)[:5]
                    logger.info(f"  Alpha factors computed: {len(factor_scores)} stocks "
                                f"| top: {', '.join(f'{c}({s:.0f})' for c, s in top5)}")
                else:
                    logger.info("  Alpha factors: insufficient data")
            else:
                logger.info("  Financial metrics: no data available")
        except Exception as e:
            logger.warning(f"Financial factor computation failed (non-blocking): {e}")

    # ---- 5. Rule scan (with technical features + event matching) ----
    logger.info("[5/7] Rule scan...")
    alerts = scanner.scan_and_format(quotes_clean, fund_flow_clean,
                                     stock_events=stock_events,
                                     consecutive_inflow_map=consecutive_inflow_map,
                                     technical_features=technical_features,
                                     lhb_features=lhb_features,
                                     block_trade_features=block_trade_features)

    type_counts = Counter(a["alert_type"] for a in alerts)
    type_str = "  ".join(f"{k}: {v}" for k, v in type_counts.most_common())
    event_count = sum(1 for a in alerts if a.get("has_event"))
    logger.info(f"  Scan result: {len(alerts)} signals  (with events: {event_count})  ({type_str})")

    # Market breadth sentiment bias
    for a in alerts:
        old_conf = a.get("confidence_score", 0.5)
        new_conf = MarketBreadth.apply_sentiment_bias(old_conf, market_breadth)
        if new_conf != old_conf:
            a["confidence_score"] = new_conf
            a["_sentiment_bias"] = round(new_conf - old_conf, 2)

    # North flow scoring
    if north_features:
        for a in alerts:
            delta = _north_flow_score(a, north_features)
            if delta != 0:
                old = a.get("confidence_score", 0.5)
                a["confidence_score"] = round(max(0.0, min(1.0, old + delta)), 2)
                a["_north_flow_delta"] = delta

    # Alpha factor scoring (cross-sectional, relative to candidate universe)
    if factor_scores:
        for a in alerts:
            delta = _factor_score(str(a.get("code", "")), factor_scores)
            if delta != 0:
                old = a.get("confidence_score", 0.5)
                a["confidence_score"] = round(max(0.0, min(1.0, old + delta)), 2)
                a["_factor_delta"] = delta

    if not alerts:
        logger.info("No anomaly signals, scan complete")
        return

    # ---- 6. Dedup ----
    if redis_client.ping():
        dedup = AlertDeduplicator()
        before = len(alerts)
        alerts = dedup.filter_duplicates(alerts)
        if before != len(alerts):
            logger.info(f"  Dedup: {before} -> {len(alerts)}")
        if not alerts:
            logger.info("All signals deduplicated, scan complete")
            return

    # ---- 7. Build event context + AI analysis ----
    top_alerts = alerts[:top_n] if top_n > 0 else []
    rest_alerts = alerts[top_n:] if top_n > 0 else alerts

    events_contexts: dict[str, str] = {}
    if top_alerts and (stock_events or not dry_run):
        from quant_loom.ai_analyzer.rag_store import RAGStore
        from quant_loom.feature_engineering.event_matcher import EventMatcher
        rag = RAGStore()
        matcher = EventMatcher()

        for alert in top_alerts:
            code = alert.get("code", "")
            code_events = stock_events.get(code, [])
            if not code_events and mysql_client.ping():
                code_events = rag.get_events_for_stock(code, days=3)

            if code_events:
                matched = matcher.match_events(code, alert, code_events)
                events_contexts[code] = rag.get_context_for_alert(alert, matched)

    if top_alerts:
        logger.info(f"[6/7] AI analysis (top {len(top_alerts)}, "
                     f"with event context: {len(events_contexts)})...")
        top_alerts = llm_client.batch_analyze(top_alerts, events_contexts=events_contexts)
        logger.info(f"  AI analysis complete: {len(top_alerts)} alerts")
    else:
        logger.info("[6/7] Skipping AI analysis")

    all_alerts = top_alerts + rest_alerts

    # ---- 8. Store + notify ----
    if not dry_run and mysql_client.ping():
        logger.info("[7/7] Writing to database...")
        saved = 0
        for alert in all_alerts:
            record = StockAlert(
                ts=alert.get("ts", datetime.now()),
                code=alert.get("code", ""),
                name=alert.get("name", ""),
                alert_type=alert.get("alert_type", ""),
                trigger_reason=alert.get("trigger_reason", ""),
                net_inflow_amount=alert.get("net_inflow_amount", 0),
                inflow_ratio=alert.get("inflow_ratio", 0),
                confidence_score=alert.get("confidence_score", 0),
                risk_level=alert.get("risk_level", "P3"),
                ai_summary=alert.get("ai_summary", ""),
                ai_evidence=alert.get("ai_evidence"),
                is_sent=False,
            )
            try:
                merged = mysql_client.insert_or_update(record)
                alert["db_id"] = merged.id  # for NotificationLog FK reference
                saved += 1
                alerts_produced.labels(
                    risk_level=alert.get("risk_level", "P3"),
                    alert_type=alert.get("alert_type", ""),
                ).inc()
            except Exception as e:
                logger.error(f"DB insert failed {alert.get('code')}: {e}")
        logger.info(f"  Written {saved} records")

        if redis_client.ping():
            dedup.mark_sent(all_alerts)

    # ---- Notification push ----
    p1_alerts = [a for a in all_alerts if a.get("risk_level") == "P1"]
    if p1_alerts:
        logger.info(f"P1 alerts {len(p1_alerts)} records, pushing real-time...")
        for alert in p1_alerts:
            webhook_notifier.send_alert(alert)

    # ---- WebSocket broadcast ----
    if p1_alerts:
        _broadcast_alerts_ws(p1_alerts)

    # ---- Print summary ----
    print_summary(all_alerts)

    pipeline_duration.observe(time.time() - pipeline_start)
    pipeline_runs.labels(status="success").inc()
    logger.info(f"=== QuantLoom·量梭 scan complete === trace_id={trace_id}")


def _north_flow_score(alert: dict, north: dict) -> float:
    """北向资金背景加权 — 返回置信度修正值 delta ([-0.08, +0.10])"""
    delta = 0.0

    # 北向大幅净流入 → 整体信号可信度上升
    net_today = north.get("north_net_inflow_today", 0) or 0
    if net_today > 50:       # > 50亿: 显著看多
        delta += 0.05
    elif net_today > 20:     # > 20亿: 适量看多
        delta += 0.03
    elif net_today < -30:    # < -30亿: 北向避险
        delta -= 0.05

    # 流入加速 → 额外加分
    accel = north.get("north_inflow_accel", 0) or 0
    if accel > 30:
        delta += 0.03
    elif accel < -30:
        delta -= 0.03

    # 个股是否在十大成交净买入中
    code = str(alert.get("code", ""))
    top10_buys = north.get("north_top10_net_buy", {})
    if code in top10_buys:
        net_buy = float(top10_buys[code] or 0)
        if net_buy > 3:
            delta += 0.05  # 北向明确增持
        elif net_buy > 0:
            delta += 0.02

    # 个股是否在北向重仓 Top20
    holding_top = north.get("north_holding_top", [])
    for h in holding_top:
        if h.get("code") == code:
            hold_ratio = h.get("hold_ratio", 0) or 0
            if hold_ratio > 5:
                delta += 0.03  # 北向重仓 >5%
            elif hold_ratio > 2:
                delta += 0.01
            break

    return round(max(-0.08, min(0.10, delta)), 2)


def _factor_score(code: str, factor_scores: dict[str, float]) -> float:
    """Alpha 因子背景加权 — 基于截面排名映射置信度修正值 delta ([-0.08, +0.10])"""
    score = factor_scores.get(code)
    if score is None:
        return 0.0

    # 计算该股票在候选集中的百分位
    all_scores = sorted(factor_scores.values())
    n = len(all_scores)
    if n < 5:
        return 0.0

    rank = sum(1 for s in all_scores if s < score)
    pct = rank / n  # 0.0 = worst, 1.0 = best

    if pct >= 0.8:       # Top 20%: 优质基本面
        return 0.10
    elif pct >= 0.6:     # Top 40%: 良好
        return 0.05
    elif pct >= 0.4:     # Middle: 中性
        return 0.0
    elif pct >= 0.2:     # Bottom 40%: 偏弱
        return -0.05
    else:                 # Bottom 20%: 基本面不佳
        return -0.08


def _upsert_daily_fund_flow(fund_flow_df, trade_date: date):
    """Write daily fund flow data to sq_fund_flow_daily (upsert)"""
    if fund_flow_df.empty or "code" not in fund_flow_df.columns:
        return

    from quant_loom.feature_engineering.fund_flow import FundFlowFeatures

    df = FundFlowFeatures.compute_features(fund_flow_df.copy())
    saved = 0
    for _, row in df.iterrows():
        code = str(row.get("code", ""))
        if not code:
            continue
        try:
            record = FundFlowDaily(
                code=code,
                trade_date=trade_date,
                super_large_net_inflow=float(row.get("super_large_net_inflow", 0) or 0),
                large_net_inflow=float(row.get("large_net_inflow", 0) or 0),
                medium_net_inflow=float(row.get("medium_net_inflow", 0) or 0),
                small_net_inflow=float(row.get("small_net_inflow", 0) or 0),
                main_force_ratio=float(row.get("main_force_ratio", 0) or 0),
                net_inflow=float(row.get("net_inflow", 0) or 0),
            )
            mysql_client.insert_or_update(record, lookup_columns=["code", "trade_date"])
            saved += 1
        except Exception as e:
            logger.debug(f"Fund flow write skipped {code}: {e}")
    if saved > 0:
        logger.info(f"  Fund flow history written: {saved} records")


def _compute_consecutive_inflow_map(codes: list[str], backtest_date: Optional[date] = None) -> dict[str, int]:
    """Compute consecutive net inflow days for each stock from sq_fund_flow_daily

    backtest_date: When provided, only counts data before this date to avoid lookahead bias
    """
    from quant_loom.feature_engineering.fund_flow import FundFlowFeatures

    result = {}
    if not codes or not mysql_client.ping():
        return result

    try:
        with mysql_client.get_session() as sess:
            from sqlalchemy import desc
            for code in codes:
                query = sess.query(FundFlowDaily.net_inflow).filter(
                    FundFlowDaily.code == code
                )
                # Backtest mode: exclude data on or after backtest_date
                if backtest_date:
                    query = query.filter(FundFlowDaily.trade_date < backtest_date)
                rows = (
                    query.order_by(desc(FundFlowDaily.trade_date))
                    .limit(30)
                    .all()
                )
                inflows = [float(r.net_inflow or 0) for r in rows]
                days = FundFlowFeatures.compute_consecutive_days(inflows)
                if days > 0:
                    result[code] = days
    except Exception as e:
        logger.warning(f"Historical fund flow query failed: {e}")

    return result


def _broadcast_alerts_ws(p1_alerts: list):
    """WebSocket 实时推送 P1 告警到前端"""
    try:
        import asyncio
        from quant_loom.api.app import broadcast_alert

        async def _send():
            for a in p1_alerts:
                await broadcast_alert({
                    "code": a.get("code", ""),
                    "name": a.get("name", ""),
                    "alert_type": a.get("alert_type", ""),
                    "confidence_score": a.get("confidence_score", 0),
                    "risk_level": a.get("risk_level", "P3"),
                    "trigger_reason": (a.get("trigger_reason", "") or "")[:120],
                    "ai_summary": a.get("ai_summary", ""),
                })

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import threading
                threading.Thread(target=lambda: asyncio.run(_send()), daemon=True).start()
            else:
                loop.run_until_complete(_send())
        except RuntimeError:
            asyncio.run(_send())
    except Exception as e:
        logger.debug(f"WebSocket broadcast skipped: {e}")


def print_summary(alerts: list):
    """Print scan result summary (with AI analysis details)"""
    print()
    print("=" * 70)
    print(f"  QuantLoom·量梭 Scan Results ({len(alerts)} signals)")
    print("=" * 70)

    # Summary stats
    p1, p2, p3 = 0, 0, 0
    ai_count = 0
    for a in alerts:
        r = a.get("risk_level", "P3")
        if r == "P1": p1 += 1
        elif r == "P2": p2 += 1
        else: p3 += 1
        if a.get("ai_summary"): ai_count += 1

    print(f"  P1 (High): {p1}  |  P2 (Med): {p2}  |  P3 (Low): {p3}  |  AI analyzed: {ai_count}")
    print("-" * 70)

    # AI-analyzed first
    analyzed = [a for a in alerts if a.get("ai_summary")]
    not_analyzed = [a for a in alerts if not a.get("ai_summary")]

    for a in analyzed:
        icon = {"P1": "!!", "P2": " !", "P3": " -"}.get(a.get("risk_level", "P3"), "")
        code = a.get("code", "")
        name = a.get("name", "") or "(N/A)"
        a_type = a.get("alert_type", "")
        conf = a.get("confidence_score", 0)
        pct = a.get("pct_change", 0)
        to = a.get("turnover_amount", 0)
        inflow = a.get("main_force_ratio", 0)
        ai = a.get("ai_summary", "")

        print(f" [{icon}] {code} {name}")
        print(f"      {a_type} | chg: {pct:+.2f}% | turnover: {to/1e8:.2f}B | main_force: {inflow:.1f}%")
        print(f"      rule: {a.get('trigger_reason','')[:70]}")
        if ai:
            print(f"      AI  : {ai}")

        # Risk points
        evidence = a.get("ai_evidence", {})
        if isinstance(evidence, dict):
            risks = evidence.get("risk_points", evidence.get("risks", []))
            action = evidence.get("action", evidence.get("suggestion", evidence.get("operation_advice", "")))
            if risks:
                for r in risks:
                    print(f"      risk: {r}")
            if action:
                print(f"      action: {action}")

        print()

    if not_analyzed:
        print(f"  ... {len(not_analyzed)} more not AI-analyzed")

    print("=" * 70)
    print()


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    top_n = parse_top_n()
    skip_events = "--skip-events" in sys.argv
    main(dry_run=dry, top_n=top_n, skip_events=skip_events)
