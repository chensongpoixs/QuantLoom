#!/usr/bin/env python3
"""
一键运行全流程：抓取 → 清洗 → 预扫描 → 事件抓取 → 历史资金流 → 规则扫描 → AI分析 → 告警 → 通知
用法:
  python scripts/run_scanner.py              # 执行一次扫描 (AI 分析 top 10)
  python scripts/run_scanner.py --top 20     # AI 分析 top 20
  python scripts/run_scanner.py --top 0      # 跳过 AI 分析
  python scripts/run_scanner.py --dry-run    # 仅扫描不写库
  python scripts/run_scanner.py --skip-events # 跳过事件抓取
"""

import sys
from collections import Counter
from datetime import datetime, date
from pathlib import Path

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


def parse_top_n() -> int:
    """从命令行解析 --top N 参数，默认 10"""
    for i, arg in enumerate(sys.argv):
        if arg == "--top" and i + 1 < len(sys.argv):
            return int(sys.argv[i + 1])
    return 10


def main(dry_run: bool = False, top_n: int = 10, skip_events: bool = False):
    trace_id = datetime.now().strftime("%Y%m%d%H%M%S")
    logger.info(f"=== QuantLoom 扫描开始 === trace_id={trace_id}")

    # ---- 1. 数据抓取 ----
    logger.info(f"[1/7] 抓取行情数据 (source={settings.data_source})...")

    if settings.data_source == "akshare":
        from quant_loom.data_ingestion.akshare_fetcher import AkshareFetcher
        fetcher = AkshareFetcher()
    else:
        from quant_loom.data_ingestion.xtick_fetcher import fetcher as xtick_fetcher
        fetcher = xtick_fetcher

    quotes_raw = fetcher.fetch_realtime_quotes()
    fund_flow_raw = fetcher.fetch_fund_flow_rank()

    if quotes_raw.empty:
        logger.error("行情数据为空，无法继续")
        return

    logger.info(f"  行情: {len(quotes_raw)} 只  |  资金流: {len(fund_flow_raw)} 条")

    # ---- 2. 数据清洗 ----
    logger.info("[2/7] 清洗数据...")
    quotes_clean = DataCleaner.clean_quotes(quotes_raw)
    fund_flow_clean = DataCleaner.clean_fund_flow(fund_flow_raw)

    # ---- 3. 历史资金流累积 + 连续流入天数计算 ----
    consecutive_inflow_map: dict[str, int] = {}
    if not dry_run and mysql_client.ping():
        logger.info("[3/7] 计算历史资金流特征...")
        today = date.today()
        _upsert_daily_fund_flow(fund_flow_clean, today)
        consecutive_inflow_map = _compute_consecutive_inflow_map(
            list(quotes_clean["code"].unique()) if "code" in quotes_clean.columns else []
        )
        if consecutive_inflow_map:
            has_history = sum(1 for v in consecutive_inflow_map.values() if v >= 3)
            logger.info(f"  连续流入天数计算完成 (>=3天: {has_history} 只)")
    else:
        logger.info("[3/7] 跳过历史资金流 (dry-run 或 MySQL 不可用)")

    # ---- 4. 事件抓取 (先快速预扫描获取候选标的) ----
    stock_events: dict[str, list] = {}
    if not skip_events and not dry_run:
        logger.info("[4/7] 预扫描 + 事件抓取...")
        # 快速预扫描获取候选标的代码列表
        pre_alerts = scanner.scan_and_format(quotes_clean, fund_flow_clean,
                                             consecutive_inflow_map=consecutive_inflow_map)
        candidate_codes = list(set(a["code"] for a in pre_alerts[:50]))  # top 50 候选

        if candidate_codes:
            from quant_loom.data_ingestion.event_fetcher import EventFetcher
            event_fetcher = EventFetcher()
            stock_events = event_fetcher.fetch_events_batch(candidate_codes)

            # 存储事件到 MySQL
            from quant_loom.ai_analyzer.rag_store import RAGStore
            rag = RAGStore()
            all_events = []
            for events in stock_events.values():
                all_events.extend(events)
            rag.deduplicate_and_store(all_events)
            logger.info(f"  事件抓取完成: {len(stock_events)} 只股票有事件数据")
    else:
        logger.info("[4/7] 跳过事件抓取")

    # ---- 5. 规则扫描 (含事件匹配) ----
    logger.info("[5/7] 规则扫描...")
    alerts = scanner.scan_and_format(quotes_clean, fund_flow_clean,
                                     stock_events=stock_events,
                                     consecutive_inflow_map=consecutive_inflow_map)

    type_counts = Counter(a["alert_type"] for a in alerts)
    type_str = "  ".join(f"{k}: {v}" for k, v in type_counts.most_common())
    event_count = sum(1 for a in alerts if a.get("has_event"))
    logger.info(f"  扫描结果: {len(alerts)} 个异动信号  (有事件: {event_count})  ({type_str})")

    if not alerts:
        logger.info("无异动信号，扫描结束")
        return

    # ---- 6. 去重 ----
    if redis_client.ping():
        dedup = AlertDeduplicator()
        before = len(alerts)
        alerts = dedup.filter_duplicates(alerts)
        if before != len(alerts):
            logger.info(f"  去重: {before} -> {len(alerts)}")
        if not alerts:
            logger.info("全部信号被去重，扫描结束")
            return

    # ---- 7. 构建事件上下文 + AI 分析 ----
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
        logger.info(f"[6/7] AI 分析 (top {len(top_alerts)}, "
                     f"有事件上下文: {len(events_contexts)})...")
        top_alerts = llm_client.batch_analyze(top_alerts, events_contexts=events_contexts)
        logger.info(f"  AI 分析完成: {len(top_alerts)} 条")
    else:
        logger.info("[6/7] 跳过 AI 分析")

    all_alerts = top_alerts + rest_alerts

    # ---- 8. 入库 + 通知 ----
    if not dry_run and mysql_client.ping():
        logger.info("[7/7] 写入数据库...")
        saved = 0
        for alert in all_alerts:
            if not alert.get("ai_summary"):
                continue
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
                mysql_client.insert_or_update(record)
                saved += 1
            except Exception as e:
                logger.error(f"入库失败 {alert.get('code')}: {e}")
        logger.info(f"  写入 {saved} 条")

        if redis_client.ping():
            dedup.mark_sent(all_alerts)

    # ---- 通知推送 ----
    p1_alerts = [a for a in all_alerts if a.get("risk_level") == "P1"]
    if p1_alerts:
        logger.info(f"P1 告警 {len(p1_alerts)} 条，实时推送...")
        for alert in p1_alerts:
            webhook_notifier.send_alert(alert)

    # ---- 打印汇总 ----
    print_summary(all_alerts)

    logger.info(f"=== QuantLoom 扫描完成 === trace_id={trace_id}")


def _upsert_daily_fund_flow(fund_flow_df, trade_date: date):
    """将当日资金流数据写入 sq_fund_flow_daily (upsert)"""
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
            logger.debug(f"资金流写入跳过 {code}: {e}")
    if saved > 0:
        logger.info(f"  资金流历史写入: {saved} 条")


def _compute_consecutive_inflow_map(codes: list[str]) -> dict[str, int]:
    """从 sq_fund_flow_daily 计算每只股票的连续净流入天数"""
    from quant_loom.feature_engineering.fund_flow import FundFlowFeatures

    result = {}
    if not codes or not mysql_client.ping():
        return result

    try:
        with mysql_client.get_session() as sess:
            from sqlalchemy import desc
            for code in codes:
                rows = (
                    sess.query(FundFlowDaily.net_inflow)
                    .filter(FundFlowDaily.code == code)
                    .order_by(desc(FundFlowDaily.trade_date))
                    .limit(30)
                    .all()
                )
                inflows = [float(r.net_inflow or 0) for r in rows]
                days = FundFlowFeatures.compute_consecutive_days(inflows)
                if days > 0:
                    result[code] = days
    except Exception as e:
        logger.warning(f"查询历史资金流失败: {e}")

    return result


def print_summary(alerts: list):
    """打印扫描结果摘要（含 AI 分析详情）"""
    print()
    print("=" * 70)
    print(f"  QuantLoom 扫描结果 ({len(alerts)} 条异动信号)")
    print("=" * 70)

    # 统计
    p1, p2, p3 = 0, 0, 0
    ai_count = 0
    for a in alerts:
        r = a.get("risk_level", "P3")
        if r == "P1": p1 += 1
        elif r == "P2": p2 += 1
        else: p3 += 1
        if a.get("ai_summary"): ai_count += 1

    print(f"  P1 (高): {p1}  |  P2 (中): {p2}  |  P3 (低): {p3}  |  AI已分析: {ai_count}")
    print("-" * 70)

    # AI 分析过的在前
    analyzed = [a for a in alerts if a.get("ai_summary")]
    not_analyzed = [a for a in alerts if not a.get("ai_summary")]

    for a in analyzed:
        icon = {"P1": "!!", "P2": " !", "P3": " -"}.get(a.get("risk_level", "P3"), "")
        code = a.get("code", "")
        name = a.get("name", "") or "(无名称)"
        a_type = a.get("alert_type", "")
        conf = a.get("confidence_score", 0)
        pct = a.get("pct_change", 0)
        to = a.get("turnover_amount", 0)
        inflow = a.get("main_force_ratio", 0)
        ai = a.get("ai_summary", "")

        print(f" [{icon}] {code} {name}")
        print(f"      {a_type} | 涨跌: {pct:+.2f}% | 成交: {to/1e8:.2f}亿 | 主力占比: {inflow:.1f}%")
        print(f"      规则: {a.get('trigger_reason','')[:70]}")
        if ai:
            print(f"      AI  : {ai}")

        # 风险点
        evidence = a.get("ai_evidence", {})
        if isinstance(evidence, dict):
            risks = evidence.get("risk_points", evidence.get("risks", []))
            action = evidence.get("action", evidence.get("suggestion", evidence.get("operation_advice", "")))
            if risks:
                for r in risks:
                    print(f"      风险: {r}")
            if action:
                print(f"      建议: {action}")

        print()

    if not_analyzed:
        print(f"  ... 另有 {len(not_analyzed)} 条未 AI 分析")

    print("=" * 70)
    print()


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    top_n = parse_top_n()
    skip_events = "--skip-events" in sys.argv
    main(dry_run=dry, top_n=top_n, skip_events=skip_events)

