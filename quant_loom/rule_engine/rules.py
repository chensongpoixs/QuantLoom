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
        checks.append(("pct_change%", pct, f"{cfg['pct_change_min']}-{cfg['pct_change_max']}", pct_ok))

        # 成交额
        turnover_ok = turnover >= cfg["turnover_amount_min"]
        checks.append(("turnover", turnover, f">={cfg['turnover_amount_min']}", turnover_ok))

        # 量比
        vol_ok = vol_ratio >= cfg["volume_ratio_min"]
        checks.append(("volume_ratio", vol_ratio, f">={cfg['volume_ratio_min']}", vol_ok))

        # 主力净流入占比
        mf_ok = main_force >= cfg["super_large_inflow_ratio_min"]
        checks.append(("main_force_ratio%", main_force, f">={cfg['super_large_inflow_ratio_min']}", mf_ok))

        all_ok = all(c[3] for c in checks)
        if not all_ok:
            return AlertResult()

        # 计算置信度
        score = self._score_confidence(checks)
        reason = "、".join(f"{c[0]}={c[1]:.2f}" for c in checks)
        return AlertResult(
            matched=True,
            alert_type="breakout",
            trigger_reason=f"Volume-driven breakout: {reason}",
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
        reason = f"Bottom accumulation: near 250d low={near_low}, consecutive inflow {consecutive_inflow_days} days, main force ratio={main_force:.2f}%"
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
    def check_tail_chasing(self, row: pd.Series, current_time: Optional[datetime] = None) -> AlertResult:
        """
        14:30 后资金流突然放大，尾盘主动买盘与收盘价偏强同步出现
        注：此规则依赖盘中分钟级数据，简化实现基于日级别成交额集中度判断

        current_time: 用于判断尾盘窗口的时间 (回测时可传入历史时间)
        """
        cfg = self.config.get("tail_chasing", {})
        if not cfg.get("enabled", True):
            return AlertResult()

        # 检查当前是否在尾盘时段
        if current_time is None:
            current_time = datetime.now()
        hour = current_time.hour
        minute = current_time.minute
        is_tail_window = (hour == 14 and minute >= 30) or (hour == 15 and minute == 0)

        pct = float(row.get("pct_change", 0) or 0)
        turnover = float(row.get("turnover_amount", 0) or 0)
        main_force = float(row.get("main_force_ratio", 0) or 0)
        active_buy = float(row.get("active_buy_ratio", main_force))  # 优先取主动买盘比

        # 尾盘信号：主力净流入占比高 + 涨幅适中（未封板）
        pct_ok = cfg.get("pct_change_min", 1.0) <= pct <= cfg.get("pct_change_max", 7.0)
        mf_ok = main_force >= cfg.get("main_force_ratio_min", 10.0)

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

        reason = f"End-of-day buying: pct_change={pct:.2f}%, main force ratio={main_force:.2f}%, active buy ratio={active_buy:.2f}%"
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
        mf_ok = main_force >= cfg.get("main_force_ratio_min", 15.0)

        if not (pct_ok and turnover_ok and mf_ok):
            return AlertResult()

        score = 0.55  # 基础分，待 AI 确认事件后上调
        if has_event:
            score = 0.80

        reason = f"Event-driven: pct_change={pct:.2f}%, turnover={turnover:.0f}, main force ratio={main_force:.2f}%"
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
        reason = f"Sector-linked: {sector_stats.get('sector_name', '')} sector up {sector_pct:.2f}%, {sector_stock_count} stocks rising together"
        return AlertResult(
            matched=True,
            alert_type="sector_linked",
            trigger_reason=reason,
            confidence_score=min(score, 1.0),
            risk_level="P2",
            details=sector_stats,
        )

    # ================================================================
    # 6. 龙虎榜追踪型
    # ================================================================
    def check_lhb_tracking(self, row: pd.Series,
                           lhb_stocks: Optional[Dict[str, dict]] = None,
                           lhb_inst_stocks: Optional[list] = None,
                           lhb_top_month: Optional[Dict[str, dict]] = None) -> AlertResult:
        """
        龙虎榜机构/游资行为追踪
        - 机构席位净买入额大 → 触发
        - 知名游资席位出现 + 成交额放大 → 触发
        - 连续/频繁上榜 → 提高置信度
        """
        cfg = self.config.get("lhb_tracking", {})
        if not cfg.get("enabled", True):
            return AlertResult()

        code = str(row.get("code", ""))
        if not code or not lhb_stocks:
            return AlertResult()

        lhb_info = lhb_stocks.get(code)
        if not lhb_info:
            return AlertResult()

        net_amount = abs(lhb_info.get("net_amount", 0))
        lhb_inst_stocks = lhb_inst_stocks or []
        has_inst = code in lhb_inst_stocks
        lhb_top_month = lhb_top_month or {}
        top_info = lhb_top_month.get(code, {})
        on_board_count = top_info.get("count", 1) if top_info else 1

        # 最低净买额
        net_min = cfg.get("lhb_net_amount_min", 5000)  # 万元
        if net_amount < net_min:
            return AlertResult()

        # 置信度计算
        score = 0.50
        reason_parts = [f"LHB net buy={net_amount:.0f}万"]

        # 机构席位加分
        if has_inst:
            score += 0.20
            reason_parts.append("institutional seats present")
        else:
            # 无机构但净买额大 → 游资主导
            if net_amount >= cfg.get("retail_lhb_threshold", 20000):
                score += 0.10
                reason_parts.append("large retail/游资 driven")

        # 频繁上榜
        if on_board_count >= 3:
            score += 0.15
            reason_parts.append(f"frequent on board ({on_board_count}x)")
        elif on_board_count >= 2:
            score += 0.08
            reason_parts.append(f"recently on board ({on_board_count}x)")

        # 涨幅 + 成交额验证
        pct = abs(float(row.get("pct_change", 0) or 0))
        if pct >= 5:
            score += 0.05
            reason_parts.append(f"strong move {pct:+.1f}%")

        score = min(score, 0.95)
        risk = "P1" if score >= 0.75 else "P2"

        return AlertResult(
            matched=True,
            alert_type="lhb_tracking",
            trigger_reason="; ".join(reason_parts),
            confidence_score=score,
            risk_level=risk,
            details={
                "code": code,
                "net_amount": lhb_info.get("net_amount", 0),
                "has_inst": has_inst,
                "on_board_count": on_board_count,
            },
        )

    # ================================================================
    # 7. 缺口回补型
    # ================================================================
    def check_gap_fill(self, row: pd.Series, tech: Optional[dict] = None) -> AlertResult:
        """
        跳空高开/低开后回补缺口 — 价格回到前收盘价附近
        需要 K 线技术特征 (prev_close + today open/high/low)
        """
        cfg = self.config.get("gap_fill", {})
        if not cfg.get("enabled", True):
            return AlertResult()

        if not tech:
            return AlertResult()

        prev_close = float(tech.get("prev_close", 0) or 0)
        today_open = float(tech.get("today_open", 0) or 0)
        today_high = float(tech.get("today_high", 0) or 0)
        today_low = float(tech.get("today_low", 0) or 0)

        if prev_close <= 0 or today_open <= 0:
            return AlertResult()

        gap_pct = (today_open - prev_close) / prev_close * 100
        gap_min = cfg.get("gap_pct_min", 1.5)

        # Detect gap direction and fill
        fill_detected = False
        gap_type = ""
        if gap_pct >= gap_min:
            gap_type = "gap_up"
            # Gap up: low crosses below prev_close → filling the gap downward
            if today_low <= prev_close:
                fill_pct = (today_open - today_low) / (today_open - prev_close) * 100 if (today_open - prev_close) > 0 else 0
                if fill_pct >= cfg.get("fill_pct_min", 30):
                    fill_detected = True
        elif gap_pct <= -gap_min:
            gap_type = "gap_down"
            # Gap down: high crosses above prev_close → filling the gap upward
            if today_high >= prev_close:
                fill_pct = (today_high - today_open) / (prev_close - today_open) * 100 if (prev_close - today_open) > 0 else 0
                if fill_pct >= cfg.get("fill_pct_min", 30):
                    fill_detected = True

        if not fill_detected:
            return AlertResult()

        # Volume confirmation
        vol_ratio = float(row.get("volume_ratio", 0) or 0)
        if vol_ratio < cfg.get("volume_ratio_min", 1.2):
            return AlertResult()

        main_force = float(row.get("main_force_ratio", 0) or 0)
        if abs(main_force) < cfg.get("main_force_ratio_min", 5.0):
            return AlertResult()

        # Score: gap size + fill completeness + volume
        score = 0.45
        score += 0.15 * min(abs(gap_pct) / 5, 1)      # larger gap = more significant
        score += 0.20 * min(vol_ratio / 2, 1)           # volume confirmation
        score += 0.20 * (1 if main_force > 0 else 0.5)  # direction alignment

        reason = (f"Gap fill ({gap_type}): gap={gap_pct:+.1f}%, "
                  f"fill, vol_ratio={vol_ratio:.1f}x, main_force={main_force:.1f}%")
        return AlertResult(
            matched=True,
            alert_type="gap_fill",
            trigger_reason=reason,
            confidence_score=min(score, 0.90),
            risk_level="P1" if score >= 0.70 else "P2",
            details={"gap_type": gap_type, "gap_pct": round(gap_pct, 2), "vol_ratio": vol_ratio},
        )

    # ================================================================
    # 8. 大宗交易异动型
    # ================================================================
    def check_block_trade(self, row: pd.Series,
                          block_trades: Optional[Dict[str, dict]] = None) -> AlertResult:
        """
        大宗交易折溢价率异常 — 大额折价/溢价交易可能预示筹码转移
        """
        cfg = self.config.get("block_trade", {})
        if not cfg.get("enabled", True):
            return AlertResult()

        code = str(row.get("code", ""))
        if not code or not block_trades or code not in block_trades:
            return AlertResult()

        bt = block_trades[code]
        trade_amount = float(bt.get("trade_amount", 0) or 0)  # 万元
        premium = float(bt.get("premium", 0) or 0)  # 折溢价率 %

        # Filter: minimum trade size
        if trade_amount < cfg.get("trade_amount_min", 5000):
            return AlertResult()

        # Significant premium or discount
        premium_threshold = cfg.get("premium_threshold", 3.0)
        discount_threshold = cfg.get("discount_threshold", 5.0)

        if abs(premium) < min(premium_threshold, abs(discount_threshold)):
            return AlertResult()

        is_premium = premium > premium_threshold
        is_discount = premium < -discount_threshold

        if not (is_premium or is_discount):
            return AlertResult()

        direction = "premium" if is_premium else "discount"
        score = 0.45
        score += 0.20 * min(abs(premium) / 10, 1)     # magnitude of premium/discount
        score += 0.15 * min(trade_amount / 20000, 1)   # trade size
        if is_premium:
            score += 0.15                               # premium = bullish signal

        reason = (f"Block trade ({direction}): {premium:+.1f}%, "
                  f"amount={trade_amount:.0f}万")
        return AlertResult(
            matched=True,
            alert_type="block_trade",
            trigger_reason=reason,
            confidence_score=min(score, 0.90),
            risk_level="P1" if score >= 0.70 else "P2",
            details={"premium": premium, "trade_amount": trade_amount},
        )

    # ================================================================
    # 9. 高换手低涨幅型
    # ================================================================
    def check_high_turnover_low_return(self, row: pd.Series) -> AlertResult:
        """
        成交极度活跃但价格变化极小 — 可能换庄/洗盘/对倒
        """
        cfg = self.config.get("high_turnover_low_return", {})
        if not cfg.get("enabled", True):
            return AlertResult()

        turnover_rate = float(row.get("turnover_rate", 0) or 0)
        pct_change = float(row.get("pct_change", 0) or 0)
        turnover_amount = float(row.get("turnover_amount", 0) or 0)

        # High turnover, low price change
        if turnover_rate < cfg.get("turnover_rate_min", 10.0):
            return AlertResult()
        if abs(pct_change) > cfg.get("pct_change_max", 2.0):
            return AlertResult()
        if turnover_amount < cfg.get("turnover_amount_min", 100000000):  # 1亿
            return AlertResult()

        main_force = float(row.get("main_force_ratio", 0) or 0)

        score = 0.40
        score += 0.20 * min(turnover_rate / 20, 1)           # higher turnover = more suspicious
        score += 0.15 * (1 - abs(pct_change) / 2)             # lower price change = more suspicious
        score += 0.15 * min(turnover_amount / 5e8, 1)         # larger amount
        # Main force near zero (balanced) or slightly negative = distribution
        if -5 < main_force < 5:
            score += 0.10  # balanced = position transfer signal

        reason = (f"High turnover low return: turnover={turnover_rate:.1f}%, "
                  f"pct={pct_change:+.2f}%, amount={turnover_amount/1e8:.1f}亿")
        return AlertResult(
            matched=True,
            alert_type="high_turnover_low_return",
            trigger_reason=reason,
            confidence_score=min(score, 0.85),
            risk_level="P2",
            details={"turnover_rate": turnover_rate, "pct_change": pct_change},
        )

    # ================================================================
    # 10. 盘中急拉/急跌型
    # ================================================================
    def check_intraday_spike(self, row: pd.Series, tech: Optional[dict] = None) -> AlertResult:
        """
        盘中快速拉升或下跌 — 日内振幅异常，可能为突发消息或操纵
        使用日线 high/low/open 作为盘中波动代理
        """
        cfg = self.config.get("intraday_spike", {})
        if not cfg.get("enabled", True):
            return AlertResult()

        if not tech:
            return AlertResult()

        today_open = float(tech.get("today_open", 0) or 0)
        today_high = float(tech.get("today_high", 0) or 0)
        today_low = float(tech.get("today_low", 0) or 0)

        if today_open <= 0:
            return AlertResult()

        pct_change = float(row.get("pct_change", 0) or 0)
        turnover_amount = float(row.get("turnover_amount", 0) or 0)

        # Intraday range
        high_rise = (today_high - today_open) / today_open * 100   # intraday rally %
        low_drop = (today_open - today_low) / today_open * 100     # intraday drop %
        total_range = (today_high - today_low) / today_open * 100  # total amplitude %

        # Detect spike: large intraday move
        spike_up = high_rise >= cfg.get("spike_up_pct_min", 4.0)
        spike_down = low_drop >= cfg.get("spike_down_pct_min", 4.0)
        wide_range = total_range >= cfg.get("wide_range_pct_min", 7.0)

        if not (spike_up or spike_down or wide_range):
            return AlertResult()

        # Need some volume confirmation
        if turnover_amount < cfg.get("turnover_amount_min", 50000000):
            return AlertResult()

        direction = ""
        if spike_up and not spike_down:
            direction = "spike_up"
        elif spike_down and not spike_up:
            direction = "spike_down"
        else:
            direction = "wide_range"

        score = 0.40
        score += 0.20 * min(total_range / 10, 1)            # wider range = stronger signal
        score += 0.15 * min(turnover_amount / 5e8, 1)       # volume confirmation
        if direction == "spike_up" and pct_change > 0:
            score += 0.10
        elif direction == "spike_down" and pct_change < 0:
            score += 0.10

        reason = (f"Intraday {direction}: open={today_open:.2f}, "
                  f"high={today_high:.2f}, low={today_low:.2f}, range={total_range:.1f}%")
        return AlertResult(
            matched=True,
            alert_type="intraday_spike",
            trigger_reason=reason,
            confidence_score=min(score, 0.85),
            risk_level="P1" if score >= 0.70 else "P2",
            details={"direction": direction, "total_range": round(total_range, 2),
                     "high_rise": round(high_rise, 2), "low_drop": round(low_drop, 2)},
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
