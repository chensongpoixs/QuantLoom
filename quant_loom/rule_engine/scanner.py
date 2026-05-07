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
             sector_stats: Optional[Dict[str, Dict]] = None) -> List[AlertResult]:
        """
        执行全市场扫描

        Parameters
        ----------
        quotes_df : 行情快照 DataFrame (已清洗)
        fund_flow_df : 资金流 DataFrame (已清洗、含特征)
        sector_stats : 板块统计数据 dict, key=sector_name

        Returns
        -------
        List[AlertResult] : 匹配的异动列表，按置信度降序
        """
        if quotes_df.empty:
            logger.warning("行情数据为空，跳过扫描")
            return []

        # 合并行情与资金流
        merged = self._merge_data(quotes_df, fund_flow_df)
        if merged.empty:
            logger.warning("合并后数据为空")
            return []

        logger.info(f"开始扫描全市场 {len(merged)} 只股票...")
        alerts: List[Tuple[AlertResult, pd.Series]] = []

        for _, row in merged.iterrows():
            # 1. 放量上攻
            result = self.engine.check_breakout(row)
            if result.matched:
                alerts.append((result, row))

            # 2. 底部吸筹（需要历史数据 — 此处简化，传 0 天）
            result = self.engine.check_accumulation(row, consecutive_inflow_days=0)
            if result.matched:
                alerts.append((result, row))

            # 3. 尾盘抢筹
            result = self.engine.check_tail_chasing(row)
            if result.matched:
                alerts.append((result, row))

            # 4. 事件驱动（先匹配资金面，事件确认留给 AI）
            result = self.engine.check_event_driven(row, has_event=False)
            if result.matched:
                alerts.append((result, row))

            # 5. 板块联动
            if sector_stats:
                industry = row.get("industry", "")
                if industry and industry in sector_stats:
                    result = self.engine.check_sector_linked(row, sector_stats[industry])
                    if result.matched:
                        alerts.append((result, row))

        # 按置信度降序排列
        sorted_alerts = sorted(alerts, key=lambda x: x[0].confidence_score, reverse=True)

        logger.info(f"扫描完成: 发现 {len(sorted_alerts)} 个异动信号")
        return [a[0] for a in sorted_alerts]

    def scan_and_format(self, quotes_df: pd.DataFrame, fund_flow_df: pd.DataFrame,
                        sector_stats: Optional[Dict] = None) -> List[dict]:
        """
        扫描并返回格式化字典列表（便于入库）
        """
        from datetime import datetime

        results = self.scan(quotes_df, fund_flow_df, sector_stats)

        # 重新合并数据以便获取 name 等字段
        merged = self._merge_data(quotes_df, fund_flow_df)
        code_to_row = {}
        for _, row in merged.iterrows():
            code_to_row[row.get("code", "")] = row

        formatted = []
        for alert in results:
            code = alert.details.get("code", "") if hasattr(alert, 'details') else ""
            row = code_to_row.get(code, pd.Series())
            formatted.append({
                "ts": datetime.now(),
                "code": code or row.get("code", ""),
                "name": row.get("name", "") if hasattr(row, 'get') else "",
                "alert_type": alert.alert_type,
                "trigger_reason": alert.trigger_reason,
                "net_inflow_amount": row.get("net_inflow", 0) if hasattr(row, 'get') else 0,
                "inflow_ratio": row.get("main_force_ratio", 0) if hasattr(row, 'get') else 0,
                "confidence_score": alert.confidence_score,
                "risk_level": alert.risk_level,
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

        return merged


# 全局单例
scanner = MarketScanner()
