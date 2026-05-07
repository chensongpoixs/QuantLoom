#!/usr/bin/env python3
"""
QuantLoom 参数网格搜索调优 CLI
遍历参数组合，复用回测引擎评分，输出最优配置

用法:
  python scripts/run_tuning.py --alert breakout --start 2024-01-01 --end 2024-12-31
  python scripts/run_tuning.py --all --start 2024-01-01 --end 2024-12-31
  python scripts/run_tuning.py --export tuned     # 导出当前最优到 rules.tuned.yaml
  python scripts/run_tuning.py --list-spaces       # 列出各类型的搜索空间
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger

from quant_loom.tuning.grid_search import GridSearchTuner, SEARCH_SPACES


def parse_args():
    p = argparse.ArgumentParser(description="QuantLoom 参数调优")
    p.add_argument("--alert", type=str, help="调优目标异动类型 (breakout/accumulation/tail_chasing/event_driven/sector_linked)")
    p.add_argument("--all", action="store_true", help="调优所有异动类型")
    p.add_argument("--start", type=str, help="回测起始日期 YYYY-MM-DD")
    p.add_argument("--end", type=str, help="回测结束日期 YYYY-MM-DD")
    p.add_argument("--export", type=str, choices=["tuned"], help="导出最优配置")
    p.add_argument("--list-spaces", action="store_true", help="列出搜索空间")
    return p.parse_args()


def cmd_list_spaces():
    """列出搜索空间"""
    print("\n参数搜索空间:")
    print("=" * 60)
    for alert_type, space in SEARCH_SPACES.items():
        n_combos = 1
        for v in space.values():
            n_combos *= len(v)
        print(f"\n  [{alert_type}] — {n_combos} 种组合:")
        for param, values in space.items():
            print(f"    {param}: {values}")
    print()


def cmd_grid_search(alert_type: str, start_str: str = None, end_str: str = None):
    """执行单类型网格搜索"""
    tuner = GridSearchTuner()
    combinations = tuner.generate_combinations(alert_type)

    logger.info(f"开始 {alert_type} 网格搜索: {len(combinations)} 种组合")

    results = []
    for i, params in enumerate(combinations):
        ph = tuner.params_hash(params)

        # 尝试从 DB 加载缓存
        cached = tuner._load_results(ph, alert_type)
        if not cached.empty:
            score = tuner.score_params(alert_type, params, cached)
            results.append(score)
            logger.info(f"  [{i+1}/{len(combinations)}] 缓存命中: score={score['combined_score']:.4f}")
        else:
            # 需要运行回测 — 此处为预留接口，实际回测在 run_backtest.py 中完成
            logger.info(f"  [{i+1}/{len(combinations)}] 待回测: params={params} hash={ph[:8]}")

    if results:
        best = max(results, key=lambda r: r["combined_score"])
        print(f"\n最优参数 ({alert_type}):")
        print(f"  combined_score: {best['combined_score']:.4f}")
        print(f"  precision@3d:   {best['precision_3d']:.4f}")
        print(f"  avg_return@3d:  {best['avg_return_3d']:.4f}")
        print(f"  alert_count:    {best['alert_count']}")
        print(f"  params:         {best['params']}")

        # 导出最优
        tuner.export_best_config(alert_type, best["params"])
    else:
        print(f"  警告: 无缓存回测结果。请先运行 run_backtest.py 填充回测数据。")


def cmd_export():
    """导出当前最优配置 (从 DB 中读取最高评分组合)"""
    tuner = GridSearchTuner()

    for alert_type in SEARCH_SPACES:
        combinations = tuner.generate_combinations(alert_type)
        best_score = -1.0
        best_params = None

        for params in combinations:
            ph = tuner.params_hash(params)
            cached = tuner._load_results(ph, alert_type)
            if not cached.empty:
                score = tuner.score_params(alert_type, params, cached)
                if score["combined_score"] > best_score:
                    best_score = score["combined_score"]
                    best_params = params

        if best_params:
            tuner.export_best_config(alert_type, best_params)
            logger.info(f"{alert_type}: 最优 score={best_score:.4f}")
        else:
            logger.info(f"{alert_type}: 无缓存数据，跳过")

    print("\n最优配置已导出到 config/rules.tuned.yaml")


def main():
    args = parse_args()

    if args.list_spaces:
        cmd_list_spaces()
        return

    if args.export:
        cmd_export()
        return

    if args.all:
        for alert_type in SEARCH_SPACES:
            cmd_grid_search(alert_type, args.start, args.end)
        return

    if args.alert:
        cmd_grid_search(args.alert, args.start, args.end)
        return

    # 默认
    print("用法: python scripts/run_tuning.py --alert <type> [--start YYYY-MM-DD] [--end YYYY-MM-DD]")
    print("      python scripts/run_tuning.py --all")
    print("      python scripts/run_tuning.py --list-spaces")
    print(f"可用类型: {list(SEARCH_SPACES.keys())}")


if __name__ == "__main__":
    main()
