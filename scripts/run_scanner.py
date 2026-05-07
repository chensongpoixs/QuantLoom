#!/usr/bin/env python3
"""
一键运行全流程：抓取 → 清洗 → 扫描 → AI分析 → 告警 → 通知
用法:
  python scripts/run_scanner.py           # 执行一次扫描
  python scripts/run_scanner.py --dry-run # 仅扫描不写库
"""

import sys
from datetime import datetime
from pathlib import Path

# 将项目根目录加入 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger

from quant_loom.data_ingestion.akshare_fetcher import fetcher
from quant_loom.data_ingestion.cleaner import DataCleaner
from quant_loom.rule_engine.scanner import scanner
from quant_loom.rule_engine.dedup import AlertDeduplicator
from quant_loom.ai_analyzer.llm_client import llm_client
from quant_loom.notification.email_sender import email_sender
from quant_loom.notification.webhook import webhook_notifier
from quant_loom.storage.mysql_client import mysql_client
from quant_loom.storage.redis_client import redis_client
from quant_loom.storage.models import StockAlert


def main(dry_run: bool = False):
    trace_id = datetime.now().strftime("%Y%m%d%H%M%S")
    logger.info(f"=== AI-WhaleWatcher 扫描开始 === trace_id={trace_id}")

    # ---- 1. 数据抓取 ----
    logger.info("[1/5] 抓取数据...")
    quotes_raw = fetcher.fetch_realtime_quotes()
    fund_flow_raw = fetcher.fetch_fund_flow_rank()

    if quotes_raw.empty:
        logger.error("行情数据为空，无法继续")
        return

    # ---- 2. 数据清洗 ----
    logger.info("[2/5] 清洗数据...")
    quotes_clean = DataCleaner.clean_quotes(quotes_raw)
    fund_flow_clean = DataCleaner.clean_fund_flow(fund_flow_raw)

    # ---- 3. 规则扫描 ----
    logger.info("[3/5] 规则扫描...")
    alerts = scanner.scan_and_format(quotes_clean, fund_flow_clean)
    logger.info(f"扫描结果: {len(alerts)} 个异动信号")

    if not alerts:
        logger.info("无异动信号，扫描结束")
        return

    # ---- 4. 去重 ----
    if redis_client.ping():
        dedup = AlertDeduplicator()
        alerts = dedup.filter_duplicates(alerts)
        if not alerts:
            logger.info("全部信号被去重，扫描结束")
            return

    # ---- 5. AI 分析 ----
    logger.info("[4/5] AI 分析...")
    alerts = llm_client.batch_analyze(alerts)

    # ---- 6. 入库 ----
    if not dry_run and mysql_client.ping():
        logger.info("[5/5] 写入数据库...")
        for alert in alerts:
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
            except Exception as e:
                logger.error(f"入库失败 {alert.get('code')}: {e}")

        # 标记已发送，启用冷却
        if redis_client.ping():
            dedup.mark_sent(alerts)

    # ---- 7. 通知推送 ----
    p1_alerts = [a for a in alerts if a.get("risk_level") == "P1"]
    if p1_alerts:
        logger.info(f"P1 告警 {len(p1_alerts)} 条，实时推送...")
        for alert in p1_alerts:
            webhook_notifier.send_alert(alert)

    # ---- 8. 打印汇总 ----
    print_summary(alerts)

    logger.info(f"=== AI-WhaleWatcher 扫描完成 === trace_id={trace_id}")


def print_summary(alerts: list):
    """打印扫描结果摘要"""
    print("\n" + "=" * 60)
    print(f"  AI-WhaleWatcher 扫描结果 ({len(alerts)} 条)")
    print("=" * 60)
    p1, p2, p3 = 0, 0, 0
    for a in alerts:
        r = a.get("risk_level", "P3")
        if r == "P1":
            p1 += 1
        elif r == "P2":
            p2 += 1
        else:
            p3 += 1

    print(f"  P1 (高): {p1}  |  P2 (中): {p2}  |  P3 (低): {p3}")
    print("-" * 60)
    for a in alerts[:10]:
        icon = {"P1": "🔴", "P2": "🟡", "P3": "⚪"}.get(a.get("risk_level", "P3"), "")
        print(f"  {icon} {a.get('name','')}({a.get('code','')}) "
              f"| {a.get('alert_type',''):20s} "
              f"| 置信度:{a.get('confidence_score',0):.2f} "
              f"| {a.get('trigger_reason','')[:50]}")
    if len(alerts) > 10:
        print(f"  ... 共 {len(alerts)} 条")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    main(dry_run=dry)
