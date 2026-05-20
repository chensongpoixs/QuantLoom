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

"""
全市场扫描器
加载 YAML 规则配置 → 遍历全市场股票数据 → 匹配五类异动信号 → 返回候选列表
"""

from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import yaml
from loguru import logger

from quant_loom.rule_engine.rules import AlertResult, RuleEngine
from quant_loom.feature_engineering.fund_flow import FundFlowFeatures
from quant_loom.feature_engineering.price import PriceFeatures


class MarketScanner:
    """全市场异动扫描器"""

    def __init__(self, rules_config_path: Optional[Path] = None):
        if rules_config_path is None:
            rules_config_path = Path(__file__).resolve().parent.parent.parent / "config" / "rules.yaml"

        self.config = self._load_config(rules_config_path)
        self.engine = RuleEngine(self.config.get("scan_rules", {}))

    @staticmethod
    def _load_config(path: Path) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def scan(self, quotes_df: pd.DataFrame, fund_flow_df: pd.DataFrame,
             sector_stats: Optional[Dict[str, Dict]] = None,
             stock_events: Optional[Dict[str, list]] = None,
             consecutive_inflow_map: Optional[Dict[str, int]] = None,
             current_time: Optional[datetime] = None,
             backtest_mode: bool = False,
             near_250d_low_map: Optional[Dict[str, bool]] = None,
             lhb_features: Optional[dict] = None,
             technical_features: Optional[Dict[str, dict]] = None,
             block_trade_features: Optional[Dict[str, dict]] = None) -> List[Tuple[AlertResult, pd.Series]]:
        """
        执行全市场扫描

        Parameters
        ----------
        stock_events: {code: [event_dicts]} 各股票的近期事件
        consecutive_inflow_map: {code: days} 各股票的连续净流入天数 (从历史数据计算)
        current_time: 用于判断尾盘窗口的时间 (回测时可传入历史时间)
        backtest_mode: 回测模式 — 跳过事件驱动规则 (无历史事件数据)
        near_250d_low_map: {code: bool} 回测模式下用真实 250 日最低价计算结果

        Returns
        -------
        List[Tuple[AlertResult, pd.Series]] : (告警结果, 原始数据行) 列表，按置信度降序
        """
        if quotes_df.empty:
            logger.warning("Market data is empty, skipping scan")
            return []

        # 合并行情与资金流
        merged = self._merge_data(quotes_df, fund_flow_df)
        if merged.empty:
            logger.warning("Merged data is empty")
            return []

        # 回测模式: 使用真实 250 日最低价计算结果覆盖启发式代理
        if near_250d_low_map:
            merged["near_250d_low"] = merged["code"].map(
                lambda c: near_250d_low_map.get(str(c).zfill(6), False)
            ).fillna(False)

        stock_events = stock_events or {}
        consecutive_inflow_map = consecutive_inflow_map or {}

        logger.info(f"Starting full market scan of {len(merged)} stocks...")
        alerts: List[Tuple[AlertResult, pd.Series]] = []

        for _, row in merged.iterrows():
            code = str(row.get("code", ""))

            # 1. 放量上攻
            result = self.engine.check_breakout(row)
            if result.matched:
                result.details["code"] = code
                alerts.append((result, row))

            # 2. 底部吸筹 — 使用历史资金流计算的连续流入天数
            inflow_days = consecutive_inflow_map.get(code, 0)
            if inflow_days == 0:
                net_inflow = float(row.get("net_inflow", 0) or 0)
                inflow_days = 1 if net_inflow > 0 else 0
            result = self.engine.check_accumulation(row, consecutive_inflow_days=inflow_days)
            if result.matched:
                result.details["code"] = code
                alerts.append((result, row))

            # 3. 尾盘抢筹
            result = self.engine.check_tail_chasing(row, current_time=current_time)
            if result.matched:
                result.details["code"] = code
                alerts.append((result, row))

            # 4. 事件驱动 — 检查是否有真实事件 (回测模式跳过: 无历史事件 API)
            if not backtest_mode:
                has_event = code in stock_events and len(stock_events[code]) > 0
                result = self.engine.check_event_driven(row, has_event=has_event)
                if result.matched:
                    result.details["code"] = code
                    result.details["has_event"] = has_event
                    alerts.append((result, row))

            # 5. 板块联动
            if sector_stats:
                industry = row.get("industry", "")
                if industry and industry in sector_stats:
                    result = self.engine.check_sector_linked(row, sector_stats[industry])
                    if result.matched:
                        result.details["code"] = code
                        alerts.append((result, row))

            # 6. 龙虎榜追踪
            if lhb_features:
                result = self.engine.check_lhb_tracking(
                    row,
                    lhb_stocks=lhb_features.get("lhb_stocks"),
                    lhb_inst_stocks=lhb_features.get("lhb_inst_stocks"),
                    lhb_top_month=lhb_features.get("lhb_top_month"),
                )
                if result.matched:
                    result.details["code"] = code
                    alerts.append((result, row))

            # 7. 缺口回补
            tech = (technical_features or {}).get(code)
            if tech:
                result = self.engine.check_gap_fill(row, tech=tech)
                if result.matched:
                    result.details["code"] = code
                    alerts.append((result, row))

            # 8. 大宗交易
            if block_trade_features:
                result = self.engine.check_block_trade(row, block_trades=block_trade_features)
                if result.matched:
                    result.details["code"] = code
                    alerts.append((result, row))

            # 9. 高换手低涨幅 (无需额外数据，仅用行情字段)
            result = self.engine.check_high_turnover_low_return(row)
            if result.matched:
                result.details["code"] = code
                alerts.append((result, row))

            # 10. 盘中急拉/急跌
            if tech:
                result = self.engine.check_intraday_spike(row, tech=tech)
                if result.matched:
                    result.details["code"] = code
                    alerts.append((result, row))

        sorted_alerts = sorted(alerts, key=lambda x: x[0].confidence_score, reverse=True)
        logger.info(f"Scan complete: found {len(sorted_alerts)} anomaly signals")
        return sorted_alerts

    def scan_and_format(self, quotes_df: pd.DataFrame, fund_flow_df: pd.DataFrame,
                        sector_stats: Optional[Dict] = None,
                        stock_events: Optional[Dict[str, list]] = None,
                        consecutive_inflow_map: Optional[Dict[str, int]] = None,
                        backtest_date: Optional[date] = None,
                        backtest_mode: bool = False,
                        near_250d_low_map: Optional[Dict[str, bool]] = None,
                        technical_features: Optional[Dict[str, dict]] = None,
                        lhb_features: Optional[dict] = None,
                        block_trade_features: Optional[Dict[str, dict]] = None) -> List[dict]:
        """
        扫描并返回格式化字典列表（便于入库和 AI 分析）
        每个 dict 包含完整的上游数据字段

        backtest_date: 回测日期 — ts 字段使用此日期，None 时使用当前时间
        backtest_mode: 回测模式 — 跳过事件驱动规则
        near_250d_low_map: 回测模式下的真实 250 日低位映射
        technical_features: {code: {ma5, ma10, rsi14, macd_dif, ...}} 技术面特征字典
        block_trade_features: {code: {premium, trade_amount, ...}} 大宗交易特征
        """
        results = self.scan(quotes_df, fund_flow_df, sector_stats,
                           stock_events=stock_events,
                           consecutive_inflow_map=consecutive_inflow_map,
                           backtest_mode=backtest_mode,
                           near_250d_low_map=near_250d_low_map,
                           lhb_features=lhb_features,
                           technical_features=technical_features,
                           block_trade_features=block_trade_features)

        formatted = []
        for alert, row in results:
            code = str(row.get("code", ""))
            # 回测时使用历史日期，实盘使用当前时间
            if backtest_date:
                ts = datetime.combine(backtest_date, datetime.min.time())
            else:
                ts = datetime.now()
            formatted.append({
                "ts": ts,
                "code": code,
                "name": str(row.get("name", "")),
                "alert_type": alert.alert_type,
                "trigger_reason": alert.trigger_reason,
                "pct_change": float(row.get("pct_change", 0) or 0),
                "turnover_amount": float(row.get("turnover_amount", 0) or 0),
                "main_force_ratio": float(row.get("main_force_ratio", 0) or 0),
                "net_inflow_amount": float(row.get("net_inflow", 0) or 0),
                "inflow_ratio": float(row.get("main_force_ratio", 0) or 0),
                "confidence_score": alert.confidence_score,
                "risk_level": alert.risk_level,
                "has_event": alert.details.get("has_event", False),
            })

        # 技术面共振评分: 基于技术指标修正置信度
        if technical_features:
            _apply_technical_resonance(formatted, technical_features)

        # 置信度校准: 基于历史反馈精度修正入库值 (不影响规则匹配)
        _calibrate_confidence_scores(formatted)

        return formatted

    @staticmethod
    def _merge_data(quotes_df: pd.DataFrame, fund_flow_df: pd.DataFrame) -> pd.DataFrame:
        """合并行情与资金流数据（按 code 左连接）"""
        if quotes_df.empty:
            return pd.DataFrame()

        # 确保 code 列为字符串
        quotes_df = quotes_df.copy()
        quotes_df["code"] = quotes_df["code"].astype(str).str.zfill(6)

        if not fund_flow_df.empty:
            fund_flow_df = fund_flow_df.copy()
            fund_flow_df["code"] = fund_flow_df["code"].astype(str).str.zfill(6)

            # 计算资金流特征
            fund_flow_df = FundFlowFeatures.compute_features(fund_flow_df)

            # 合并
            merged = quotes_df.merge(
                fund_flow_df[["code", "main_force_ratio", "net_inflow", "super_large_ratio", "large_ratio"]],
                on="code", how="left"
            )
        else:
            merged = quotes_df

        # 填充缺失的资金流列
        for col in ["main_force_ratio", "net_inflow", "super_large_ratio", "large_ratio"]:
            if col not in merged.columns:
                merged[col] = 0.0
        merged[["main_force_ratio", "net_inflow", "super_large_ratio", "large_ratio"]] = \
            merged[["main_force_ratio", "net_inflow", "super_large_ratio", "large_ratio"]].fillna(0)

        # 资金流数据不可用时 (全部为 0)，用成交额百分位作为主力参与度代理
        # 成交额越大 → 机构参与概率越高 → main_force_ratio 代理值越高
        if merged["main_force_ratio"].sum() == 0 and "turnover_amount" in merged.columns:
            to = pd.to_numeric(merged["turnover_amount"], errors="coerce").fillna(0)
            # 成交额排名百分位 * 20 → 映射到 0-20 区间
            merged["main_force_ratio"] = (to.rank(pct=True) * 20).round(2)

        # --- 计算 near_250d_low (原型阶段使用日内位置 + 跌幅代理) ---
        # 注：真正的 250 日低位需要历史 K 线数据，Phase 2 实现
        merged["near_250d_low"] = False
        if "high" in merged.columns and "low" in merged.columns and "latest" in merged.columns:
            high = pd.to_numeric(merged["high"], errors="coerce")
            low = pd.to_numeric(merged["low"], errors="coerce")
            latest = pd.to_numeric(merged["latest"], errors="coerce")
            day_range = (high - low).replace(0, float("nan"))
            position = ((latest - low) / day_range).fillna(0.5)
            pct = pd.to_numeric(merged["pct_change"], errors="coerce").fillna(0)
            # 日内价格处于下半区 + 跌幅 > 2% → 可能在低位区域吸筹
            merged["near_250d_low"] = (position < 0.3) & (pct < -2.0)

        return merged


# 全局单例
scanner = MarketScanner()


def _calibrate_confidence_scores(formatted: list) -> None:
    """
    校准告警 confidence_score — 基于历史反馈精度修正入库值

    仅影响入库值，不影响规则匹配 (规则匹配先发生)。
    历史精度 < 0.3 的 alert_type → confidence_score 乘 0.7 系数。
    """
    try:
        from quant_loom.storage.mysql_client import mysql_client
        from quant_loom.storage.models import AlertFeedback
        from sqlalchemy import func, inspect

        if not mysql_client.ping():
            return

        # 检查表是否存在，避免 session 内抛异常触发 rollback 日志
        insp = inspect(mysql_client.engine)
        if 'sq_alert_feedback' not in insp.get_table_names():
            return

        with mysql_client.get_session() as sess:
            rows = (
                sess.query(
                    AlertFeedback.verdict,
                    func.count(AlertFeedback.id).label("cnt"),
                )
                .group_by(AlertFeedback.verdict)
                .all()
            )
            total = sum(r.cnt for r in rows if r.verdict in ("correct", "incorrect"))
            correct = sum(r.cnt for r in rows if r.verdict == "correct")
            overall_precision = correct / total if total > 0 else 0.5

            if overall_precision < 0.3:
                for alert_dict in formatted:
                    alert_dict["confidence_score"] = round(
                        alert_dict.get("confidence_score", 0) * 0.7, 2
                    )
    except Exception as e:
        logger.warning(f"Confidence calibration failed: {e}")


def _apply_technical_resonance(formatted: list, technical_features: dict) -> None:
    """
    技术面共振评分 — 基于技术指标修正置信度

    修正规则 (每项最多 ±0.10):
    - MACD 金叉 (DIF > DEA 且 hist > 0): +0.05
    - MACD 死叉 (DIF < DEA 且 hist < 0): -0.05
    - RSI14 在 30-70 之间 (非超买超卖): +0.03
    - RSI14 < 30 (超卖/底部): +0.08 (适合 accumulation)
    - RSI14 > 80 (超买): -0.05
    - 均线多头排列: +0.08
    - 均线空头排列: -0.05 (不适合 breakout 类)
    - MA5/20 金叉 3 日内: +0.05
    - 价格站上 MA20: +0.03
    - 布林带收窄 (boll_width < 0.1): +0.03 (变盘信号)
    - KDJ J < 0 (超卖): +0.05
    """
    if not technical_features:
        return

    for alert_dict in formatted:
        code = alert_dict.get("code", "")
        tech = technical_features.get(code)
        if not tech:
            continue

        score_delta = 0.0
        alert_type = alert_dict.get("alert_type", "")

        # MACD
        macd_dif = tech.get("macd_dif", 0) or 0
        macd_hist = tech.get("macd_hist", 0) or 0
        if macd_dif > 0 and macd_hist > 0:
            score_delta += 0.05
        elif macd_dif < 0 and macd_hist < 0:
            score_delta -= 0.05

        # RSI
        rsi14 = tech.get("rsi14", 50) or 50
        if rsi14 < 30:
            score_delta += 0.08 if alert_type == "accumulation" else 0.04
        elif rsi14 > 80:
            score_delta -= 0.05
        elif 30 <= rsi14 <= 70:
            score_delta += 0.03

        # 均线排列
        if tech.get("is_bullish"):
            score_delta += 0.08
        elif tech.get("is_bearish"):
            score_delta -= 0.05 if alert_type != "accumulation" else 0

        # 金叉
        if tech.get("golden_cross"):
            score_delta += 0.05

        # 价格位置
        price_vs = tech.get("price_vs_ma", {})
        vs_ma20 = price_vs.get("vs_ma20", 0) or 0
        if vs_ma20 > 0:
            score_delta += 0.03

        # 布林带
        boll_width = tech.get("boll_width", 0.2) or 0.2
        if boll_width < 0.1:
            score_delta += 0.03

        # KDJ 超卖
        kdj_j = tech.get("kdj_j", 50) or 50
        if kdj_j < 0:
            score_delta += 0.05

        # 应用修正，限制变化范围 ±0.20
        score_delta = max(-0.20, min(0.20, score_delta))
        old_score = alert_dict.get("confidence_score", 0.5)
        alert_dict["confidence_score"] = round(max(0.0, min(1.0, old_score + score_delta)), 2)
        alert_dict["_tech_resonance_delta"] = round(score_delta, 2)
