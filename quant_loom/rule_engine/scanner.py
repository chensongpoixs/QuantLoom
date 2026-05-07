"""
全市场扫描器
加载 YAML 规则配置 → 遍历全市场股票数据 → 匹配五类异动信号 → 返回候选列表
"""

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
             consecutive_inflow_map: Optional[Dict[str, int]] = None) -> List[Tuple[AlertResult, pd.Series]]:
        """
        执行全市场扫描

        Parameters
        ----------
        stock_events: {code: [event_dicts]} 各股票的近期事件
        consecutive_inflow_map: {code: days} 各股票的连续净流入天数 (从历史数据计算)

        Returns
        -------
        List[Tuple[AlertResult, pd.Series]] : (告警结果, 原始数据行) 列表，按置信度降序
        """
        if quotes_df.empty:
            logger.warning("行情数据为空，跳过扫描")
            return []

        # 合并行情与资金流
        merged = self._merge_data(quotes_df, fund_flow_df)
        if merged.empty:
            logger.warning("合并后数据为空")
            return []

        stock_events = stock_events or {}
        consecutive_inflow_map = consecutive_inflow_map or {}

        logger.info(f"开始扫描全市场 {len(merged)} 只股票...")
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
            result = self.engine.check_tail_chasing(row)
            if result.matched:
                result.details["code"] = code
                alerts.append((result, row))

            # 4. 事件驱动 — 检查是否有真实事件
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

        sorted_alerts = sorted(alerts, key=lambda x: x[0].confidence_score, reverse=True)
        logger.info(f"扫描完成: 发现 {len(sorted_alerts)} 个异动信号")
        return sorted_alerts

    def scan_and_format(self, quotes_df: pd.DataFrame, fund_flow_df: pd.DataFrame,
                        sector_stats: Optional[Dict] = None,
                        stock_events: Optional[Dict[str, list]] = None,
                        consecutive_inflow_map: Optional[Dict[str, int]] = None) -> List[dict]:
        """
        扫描并返回格式化字典列表（便于入库和 AI 分析）
        每个 dict 包含完整的上游数据字段
        """
        from datetime import datetime

        results = self.scan(quotes_df, fund_flow_df, sector_stats,
                           stock_events=stock_events,
                           consecutive_inflow_map=consecutive_inflow_map)

        formatted = []
        for alert, row in results:
            code = str(row.get("code", ""))
            formatted.append({
                "ts": datetime.now(),
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
