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
GridSearchTuner — 笛卡尔积网格搜索参数调优
复用回测引擎，遍历参数组合，找出最优配置
"""

import hashlib
import itertools
import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import yaml
from loguru import logger

from quant_loom.tuning.score import combined_score, precision_at_n, average_return, alert_count

# 仅同类型内穷举参数组合，不跨类型组合
SEARCH_SPACES: Dict[str, Dict[str, list]] = {
    "breakout": {
        "pct_change_min": [1.0, 2.0, 3.0],
        "pct_change_max": [5.0, 7.0, 9.0],
        "turnover_amount_min": [5e7, 1e8, 2e8],
        "volume_ratio_min": [1.2, 1.5, 2.0],
    },
    "accumulation": {
        "consecutive_inflow_days_min": [2, 3, 5],
        "avg_inflow_ratio_min": [5, 10, 15],
        "near_250d_low_pct": [10, 15, 20],
    },
    "tail_chasing": {
        "pct_change_min": [0.5, 1.0, 2.0],
        "pct_change_max": [5.0, 7.0, 9.0],
        "main_force_ratio_min": [5.0, 10.0, 15.0],
    },
    "event_driven": {
        "pct_change_min": [2.0, 3.0, 5.0],
        "turnover_amount_min": [5e7, 8e7, 1e8],
        "main_force_ratio_min": [10.0, 15.0, 20.0],
    },
    "sector_linked": {
        "min_sector_stocks": [2, 3, 5],
        "sector_pct_change_min": [1.0, 1.5, 2.0],
    },
}


class GridSearchTuner:
    """网格搜索参数调优器"""

    def __init__(self, rules_path: Optional[Path] = None):
        if rules_path is None:
            rules_path = Path(__file__).resolve().parent.parent.parent / "config" / "rules.yaml"
        self.rules_path = rules_path
        with open(rules_path, "r", encoding="utf-8") as f:
            self.base_config = yaml.safe_load(f)

    def get_space(self, alert_type: str) -> Dict[str, list]:
        """获取指定异动类型的搜索空间"""
        if alert_type not in SEARCH_SPACES:
            raise ValueError(f"Unknown alert_type: {alert_type}. Available: {list(SEARCH_SPACES.keys())}")
        return SEARCH_SPACES[alert_type]

    def generate_combinations(self, alert_type: str) -> List[Dict[str, Any]]:
        """笛卡尔积生成所有参数组合"""
        space = self.get_space(alert_type)
        keys = list(space.keys())
        values = list(space.values())
        combinations = []
        for combo in itertools.product(*values):
            combinations.append(dict(zip(keys, combo)))
        logger.info(f"{alert_type}: {len(combinations)} parameter combinations")
        return combinations

    @staticmethod
    def params_hash(params: Dict[str, Any]) -> str:
        """参数组合 → MD5 哈希 (确定性)"""
        raw = json.dumps(params, sort_keys=True, default=str)
        return hashlib.md5(raw.encode()).hexdigest()

    def apply_params(self, alert_type: str, params: Dict[str, Any]) -> dict:
        """将参数组合写入配置并返回完整配置 dict"""
        config = yaml.safe_load(
            yaml.dump(self.base_config)
        )  # 深拷贝
        scan_rules = config.get("scan_rules", {})

        if alert_type in scan_rules:
            for key, value in params.items():
                scan_rules[alert_type][key] = value

        return config

    def _load_results(self, params_hash_val: str, alert_type: str) -> pd.DataFrame:
        """从 DB 加载已有回测结果 (缓存命中)"""
        try:
            from quant_loom.storage.mysql_client import mysql_client
            from quant_loom.storage.models import BacktestResult

            if not mysql_client.ping():
                return pd.DataFrame()

            with mysql_client.get_session() as sess:
                rows = (
                    sess.query(BacktestResult)
                    .filter(
                        BacktestResult.params_hash == params_hash_val,
                        BacktestResult.alert_type == alert_type,
                    )
                    .all()
                )
                if not rows:
                    return pd.DataFrame()

                return pd.DataFrame([{
                    "pct_change_alert": float(r.pct_change_alert or 0),
                    "outcome_1d": float(r.outcome_1d) if r.outcome_1d else None,
                    "outcome_3d": float(r.outcome_3d) if r.outcome_3d else None,
                    "outcome_5d": float(r.outcome_5d) if r.outcome_5d else None,
                } for r in rows])
        except Exception as e:
            logger.warning(f"Failed to load cached results: {e}")
            return pd.DataFrame()

    def score_params(self, alert_type: str, params: Dict[str, Any],
                     results_df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        对参数组合评分
        若提供 results_df 则直接评分，否则尝试从 DB 缓存加载
        """
        if results_df is None:
            ph = self.params_hash(params)
            results_df = self._load_results(ph, alert_type)

        if results_df is None or results_df.empty:
            return {
                "params": params,
                "alert_count": 0,
                "precision_3d": 0.0,
                "avg_return_3d": 0.0,
                "combined_score": 0.0,
                "params_hash": self.params_hash(params),
            }

        return {
            "params": params,
            "alert_count": alert_count(results_df),
            "precision_3d": round(precision_at_n(results_df, 3), 4),
            "avg_return_3d": round(average_return(results_df, 3), 4),
            "combined_score": round(combined_score(results_df, 3), 4),
            "params_hash": self.params_hash(params),
        }

    def export_best_config(self, alert_type: str, best_params: Dict[str, Any],
                           output_path: Optional[Path] = None) -> Path:
        """导出最优参数组合到 YAML"""
        if output_path is None:
            output_path = self.rules_path.parent / "rules.tuned.yaml"

        config = self.apply_params(alert_type, best_params)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# QuantLoom·量梭 tuned rule config (auto-generated by GridSearchTuner)\n")
            f.write(f"# Best alert type: {alert_type}\n")
            f.write(f"# Best params: {json.dumps(best_params)}\n\n")
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

        logger.info(f"Best config exported: {output_path} (type={alert_type})")
        return output_path
