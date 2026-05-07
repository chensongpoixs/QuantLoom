"""
五类机构异动信号规则
每条规则接收一行行情+资金流合并数据，返回是否匹配及详情
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd


@dataclass
class AlertResult:
    """规则匹配结果"""
    matched: bool = False
    alert_type: str = ""
    trigger_reason: str = ""
    confidence_score: float = 0.0
    risk_level: str = "P3"          # P1/P2/P3
    details: Dict[str, Any] = field(default_factory=dict)


class RuleEngine:
    """规则引擎 — 五类异动信号"""

    def __init__(self, config: dict):
        """
        config: 来自 rules.yaml 的 scan_rules 字典
        """
        self.config = config

    # ================================================================
    # 1. 放量上攻型
    # ================================================================
    def check_breakout(self, row: pd.Series) -> AlertResult:
        """
        涨幅在阈值区间内，成交额显著放大，特大单/大单净流入占比高
        """
        cfg = self.config.get("breakout", {})
        if not cfg.get("enabled", True):
            return AlertResult()

        pct = float(row.get("pct_change", 0) or 0)
        turnover = float(row.get("turnover_amount", 0) or 0)
        vol_ratio = float(row.get("volume_ratio", 0) or 0)
        main_force = float(row.get("main_force_ratio", 0) or 0)

        checks = []
        # 涨幅
        pct_ok = cfg["pct_change_min"] <= pct <= cfg["pct_change_max"]
        checks.append(("涨幅%", pct, f"{cfg['pct_change_min']}-{cfg['pct_change_max']}", pct_ok))

        # 成交额
        turnover_ok = turnover >= cfg["turnover_amount_min"]
        checks.append(("成交额", turnover, f">={cfg['turnover_amount_min']}", turnover_ok))

        # 量比
        vol_ok = vol_ratio >= cfg["volume_ratio_min"]
        checks.append(("量比", vol_ratio, f">={cfg['volume_ratio_min']}", vol_ok))

        # 主力净流入占比
        mf_ok = main_force >= cfg["super_large_inflow_ratio_min"]
        checks.append(("主力净流入占比%", main_force, f">={cfg['super_large_inflow_ratio_min']}", mf_ok))

        all_ok = all(c[3] for c in checks)
        if not all_ok:
            return AlertResult()

        # 计算置信度
        score = self._score_confidence(checks)
        reason = "、".join(f"{c[0]}={c[1]:.2f}" for c in checks)
        return AlertResult(
            matched=True,
            alert_type="breakout",
            trigger_reason=f"放量上攻: {reason}",
            confidence_score=score,
            risk_level="P1" if score >= 0.8 else "P2",
            details={"checks": [(c[0], c[1], c[2], c[3]) for c in checks]},
        )

    # ================================================================
    # 2. 底部吸筹型
    # ================================================================
    def check_accumulation(self, row: pd.Series, consecutive_inflow_days: int = 0) -> AlertResult:
        """
        近 250 日低位区域，连续多日资金净流入，价格波动收敛后放量
        """
        cfg = self.config.get("accumulation", {})
        if not cfg.get("enabled", True):
            return AlertResult()

        near_low = bool(row.get("near_250d_low", False))
        consecutive_ok = consecutive_inflow_days >= cfg["consecutive_inflow_days_min"]
        main_force = float(row.get("main_force_ratio", 0) or 0)
        inflow_ok = main_force >= cfg["avg_inflow_ratio_min"]

        if not (near_low and consecutive_ok and inflow_ok):
            return AlertResult()

        score = 0.5 + 0.15 * near_low + 0.15 * min(consecutive_inflow_days / 10, 1) + 0.2 * inflow_ok
        reason = f"底部吸筹: 近250日低位={near_low}, 连续流入{consecutive_inflow_days}天, 主力占比={main_force:.2f}%"
        return AlertResult(
            matched=True,
            alert_type="accumulation",
            trigger_reason=reason,
            confidence_score=min(score, 1.0),
            risk_level="P1" if score >= 0.7 else "P2",
            details={"near_low": near_low, "consecutive_days": consecutive_inflow_days},
        )

    # ================================================================
    # 3. 尾盘抢筹型
    # ================================================================
    def check_tail_chasing(self, row: pd.Series) -> AlertResult:
        """
        14:30 后资金流突然放大，尾盘主动买盘与收盘价偏强同步出现
        注：此规则依赖盘中分钟级数据，简化实现基于日级别成交额集中度判断
        """
        cfg = self.config.get("tail_chasing", {})
        if not cfg.get("enabled", True):
            return AlertResult()

        # 检查当前是否在尾盘时段
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        is_tail_window = (hour == 14 and minute >= 30) or (hour == 15 and minute == 0)

        pct = float(row.get("pct_change", 0) or 0)
        turnover = float(row.get("turnover_amount", 0) or 0)
        main_force = float(row.get("main_force_ratio", 0) or 0)
        active_buy = float(row.get("active_buy_ratio", main_force))  # 优先取主动买盘比

        # 尾盘信号：主力净流入占比高 + 涨幅适中（未封板）
        pct_ok = 1.0 <= pct <= 7.0
        mf_ok = main_force >= 10.0

        if not (pct_ok and mf_ok):
            return AlertResult()

        # 盘中尾盘窗口执行更严格的判定
        if is_tail_window:
            active_ok = active_buy >= cfg.get("active_buy_ratio_min", 55)
            if not active_ok:
                return AlertResult()
            score = 0.75
            risk = "P1"
        else:
            score = 0.55
            risk = "P2"

        reason = f"尾盘抢筹: 涨幅={pct:.2f}%, 主力占比={main_force:.2f}%, 主动买盘={active_buy:.2f}%"
        return AlertResult(
            matched=True,
            alert_type="tail_chasing",
            trigger_reason=reason,
            confidence_score=score,
            risk_level=risk,
            details={"pct_change": pct, "main_force_ratio": main_force, "tail_window": is_tail_window},
        )

    # ================================================================
    # 4. 事件驱动型
    # ================================================================
    def check_event_driven(self, row: pd.Series, has_event: bool = False) -> AlertResult:
        """
        新闻、公告、政策等事件触发，资金面与消息面同向共振
        规则负责识别资金异动，事件真实性由 AI 模块归因
        """
        cfg = self.config.get("event_driven", {})
        if not cfg.get("enabled", True):
            return AlertResult()

        pct = float(row.get("pct_change", 0) or 0)
        turnover = float(row.get("turnover_amount", 0) or 0)
        main_force = float(row.get("main_force_ratio", 0) or 0)

        pct_ok = abs(pct) >= cfg["pct_change_min"]
        turnover_ok = turnover >= cfg["turnover_amount_min"]
        mf_ok = main_force >= 15.0  # 主力资金明显介入

        if not (pct_ok and turnover_ok and mf_ok):
            return AlertResult()

        score = 0.55  # 基础分，待 AI 确认事件后上调
        if has_event:
            score = 0.80

        reason = f"事件驱动: 涨跌={pct:.2f}%, 成交额={turnover:.0f}, 主力占比={main_force:.2f}%"
        return AlertResult(
            matched=True,
            alert_type="event_driven",
            trigger_reason=reason,
            confidence_score=score,
            risk_level="P1" if has_event else "P2",
            details={"has_event": has_event, "pct_change": pct},
        )

    # ================================================================
    # 5. 板块联动型
    # ================================================================
    def check_sector_linked(self, row: pd.Series, sector_stats: Optional[dict] = None) -> AlertResult:
        """
        个股并非独立异动，而是跟随行业/主题板块整体抬升
        需要外部传入板块统计数据
        """
        cfg = self.config.get("sector_linked", {})
        if not cfg.get("enabled", True):
            return AlertResult()

        if sector_stats is None:
            return AlertResult()

        sector_pct = sector_stats.get("avg_pct_change", 0) or 0
        sector_stock_count = sector_stats.get("rising_count", 0) or 0
        min_stocks = cfg.get("min_sector_stocks", 3)

        if sector_pct < cfg.get("sector_pct_change_min", 1.5):
            return AlertResult()
        if sector_stock_count < min_stocks:
            return AlertResult()

        score = 0.45 + 0.3 * min(sector_pct / 5, 1) + 0.25 * min(sector_stock_count / 10, 1)
        reason = f"板块联动: {sector_stats.get('sector_name', '')} 板块涨幅{sector_pct:.2f}%, {sector_stock_count}只同步上涨"
        return AlertResult(
            matched=True,
            alert_type="sector_linked",
            trigger_reason=reason,
            confidence_score=min(score, 1.0),
            risk_level="P2",
            details=sector_stats,
        )

    # ================================================================
    # 工具
    # ================================================================
    @staticmethod
    def _score_confidence(checks: List[tuple]) -> float:
        """根据通过的检查项数量计算置信度"""
        n_ok = sum(1 for c in checks if c[3])
        n_total = len(checks)
        if n_total == 0:
            return 0.0
        return n_ok / n_total
