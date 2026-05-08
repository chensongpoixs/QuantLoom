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

from config.settings import settings
from quant_loom.data_ingestion.cleaner import DataCleaner
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

    # ---- 4. Event fetch (quick pre-scan for candidate codes first) ----
    stock_events: dict[str, list] = {}
    if not skip_events and not dry_run:
        logger.info("[4/7] Pre-scan + event fetch...")
        # Quick pre-scan to get candidate stock codes
        pre_alerts = scanner.scan_and_format(quotes_clean, fund_flow_clean,
                                             consecutive_inflow_map=consecutive_inflow_map)
        candidate_codes = list(set(a["code"] for a in pre_alerts[:50]))  # top 50 candidates

        if candidate_codes:
            from quant_loom.data_ingestion.event_fetcher import EventFetcher
            event_fetcher = EventFetcher()
            stock_events = event_fetcher.fetch_events_batch(candidate_codes)

            # Store events to MySQL
            from quant_loom.ai_analyzer.rag_store import RAGStore
            rag = RAGStore()
            all_events = []
            for events in stock_events.values():
                all_events.extend(events)
            rag.deduplicate_and_store(all_events)
            logger.info(f"  Event fetch complete: {len(stock_events)} stocks have event data")
    else:
        logger.info("[4/7] Skipping event fetch")

    # ---- 5. Rule scan (with event matching) ----
    logger.info("[5/7] Rule scan...")
    alerts = scanner.scan_and_format(quotes_clean, fund_flow_clean,
                                     stock_events=stock_events,
                                     consecutive_inflow_map=consecutive_inflow_map)

    type_counts = Counter(a["alert_type"] for a in alerts)
    type_str = "  ".join(f"{k}: {v}" for k, v in type_counts.most_common())
    event_count = sum(1 for a in alerts if a.get("has_event"))
    logger.info(f"  Scan result: {len(alerts)} signals  (with events: {event_count})  ({type_str})")

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

    # ---- Print summary ----
    print_summary(all_alerts)

    pipeline_duration.observe(time.time() - pipeline_start)
    pipeline_runs.labels(status="success").inc()
    logger.info(f"=== QuantLoom·量梭 scan complete === trace_id={trace_id}")


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
            mysql_client.insert_or_update(record)
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
