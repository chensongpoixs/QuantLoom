#!/usr/bin/env python3
"""
一键运行全流程：抓取 → 清洗 → 扫描 → AI分析 → 告警 → 通知
用法:
  python scripts/run_scanner.py              # 执行一次扫描 (AI 分析 top 10)
  python scripts/run_scanner.py --top 20     # AI 分析 top 20
  python scripts/run_scanner.py --top 0      # 跳过 AI 分析
  python scripts/run_scanner.py --dry-run    # 仅扫描不写库
"""

import sys
from datetime import datetime
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
from quant_loom.storage.models import StockAlert


def parse_top_n() -> int:
    """从命令行解析 --top N 参数，默认 10"""
    for i, arg in enumerate(sys.argv):
        if arg == "--top" and i + 1 < len(sys.argv):
            return int(sys.argv[i + 1])
    return 10


def main(dry_run: bool = False, top_n: int = 10):
    trace_id = datetime.now().strftime("%Y%m%d%H%M%S")
    logger.info(f"=== AI-WhaleWatcher 扫描开始 === trace_id={trace_id}")

    # ---- 1. 数据抓取 ----
    logger.info(f"[1/5] 抓取数据 (source={settings.data_source})...")

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
    logger.info("[2/5] 清洗数据...")
    quotes_clean = DataCleaner.clean_quotes(quotes_raw)
    fund_flow_clean = DataCleaner.clean_fund_flow(fund_flow_raw)

    # ---- 3. 规则扫描 ----
    logger.info("[3/5] 规则扫描...")
    alerts = scanner.scan_and_format(quotes_clean, fund_flow_clean)

    # 按类型统计
    from collections import Counter
    type_counts = Counter(a["alert_type"] for a in alerts)
    type_str = "  ".join(f"{k}: {v}" for k, v in type_counts.most_common())
    logger.info(f"  扫描结果: {len(alerts)} 个异动信号  ({type_str})")

    if not alerts:
        logger.info("无异动信号，扫描结束")
        return

    # ---- 4. 去重 ----
    if redis_client.ping():
        dedup = AlertDeduplicator()
        before = len(alerts)
        alerts = dedup.filter_duplicates(alerts)
        if before != len(alerts):
            logger.info(f"  去重: {before} -> {len(alerts)}")
        if not alerts:
            logger.info("全部信号被去重，扫描结束")
            return

    # ---- 5. AI 分析 (仅 top N) ----
    top_alerts = alerts[:top_n] if top_n > 0 else []
    rest_alerts = alerts[top_n:] if top_n > 0 else alerts

    if top_alerts:
        logger.info(f"[4/5] AI 分析 (top {len(top_alerts)})...")
        top_alerts = llm_client.batch_analyze(top_alerts)
        logger.info(f"  AI 分析完成: {len(top_alerts)} 条")
    else:
        logger.info("[4/5] 跳过 AI 分析")

    all_alerts = top_alerts + rest_alerts

    # ---- 6. 入库 ----
    if not dry_run and mysql_client.ping():
        logger.info("[5/5] 写入数据库...")
        saved = 0
        for alert in all_alerts:
            if not alert.get("ai_summary"):
                continue  # 跳过未 AI 分析的
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

    # ---- 7. 通知推送 ----
    p1_alerts = [a for a in all_alerts if a.get("risk_level") == "P1"]
    if p1_alerts:
        logger.info(f"P1 告警 {len(p1_alerts)} 条，实时推送...")
        for alert in p1_alerts:
            webhook_notifier.send_alert(alert)

    # ---- 8. 打印汇总 ----
    print_summary(all_alerts)

    logger.info(f"=== AI-WhaleWatcher 扫描完成 === trace_id={trace_id}")


def print_summary(alerts: list):
    """打印扫描结果摘要（含 AI 分析详情）"""
    print()
    print("=" * 70)
    print(f"  AI-WhaleWatcher 扫描结果 ({len(alerts)} 条异动信号)")
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
    main(dry_run=dry, top_n=top_n)

