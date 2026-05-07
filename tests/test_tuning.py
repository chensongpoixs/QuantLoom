"""
test_tuning.py — 参数网格搜索和评分子模块单元测试
"""

import hashlib
import json
from datetime import date

import pandas as pd
import pytest
import yaml


class TestScoreFunctions:
    """评分函数"""

    def test_precision_perfect(self):
        from quant_loom.tuning.score import precision_at_n

        df = pd.DataFrame({
            "pct_change_alert": [3.0, 5.0, -2.0],
            "outcome_3d": [4.0, 6.0, -3.0],  # 全部同向
        })
        assert precision_at_n(df, 3) == 1.0

    def test_precision_mixed(self):
        from quant_loom.tuning.score import precision_at_n

        df = pd.DataFrame({
            "pct_change_alert": [3.0, -5.0, 2.0],
            "outcome_3d": [4.0, 6.0, 1.0],  # only first correct (both +)
        })
        assert precision_at_n(df, 3) == pytest.approx(2 / 3, abs=0.01)

    def test_precision_empty(self):
        from quant_loom.tuning.score import precision_at_n
        assert precision_at_n(pd.DataFrame(), 3) == 0.0

    def test_precision_missing_col(self):
        from quant_loom.tuning.score import precision_at_n
        assert precision_at_n(pd.DataFrame({"a": [1]}), 3) == 0.0

    def test_average_return(self):
        from quant_loom.tuning.score import average_return

        df = pd.DataFrame({"outcome_3d": [1.0, 2.0, 3.0]})
        assert average_return(df, 3) == 2.0

    def test_average_return_empty(self):
        from quant_loom.tuning.score import average_return
        assert average_return(pd.DataFrame(), 3) == 0.0

    def test_hit_rate(self):
        from quant_loom.tuning.score import hit_rate

        df = pd.DataFrame({"outcome_3d": [1.0, 3.0, 5.0, -1.0]})
        # threshold=2.0: 3.0 and 5.0 hit → 2/4 = 0.5
        assert hit_rate(df, threshold_pct=2.0, n_days=3) == 0.5

    def test_combined_score(self):
        from quant_loom.tuning.score import combined_score

        df = pd.DataFrame({
            "pct_change_alert": [3.0, 5.0],
            "outcome_3d": [4.0, 6.0],
        })
        # precision = 1.0, avg_return = 5.0
        # 0.6 * 1.0 + 0.4 * 5.0/10.0 = 0.6 + 0.2 = 0.8
        assert combined_score(df, 3) == pytest.approx(0.8, abs=0.01)


class TestGridSearch:
    """GridSearchTuner 核心逻辑"""

    def test_generate_combinations_count(self):
        from quant_loom.tuning.grid_search import GridSearchTuner

        tuner = GridSearchTuner()
        combos = tuner.generate_combinations("breakout")
        # breakout: 3*3*3*3 = 81
        assert len(combos) == 81
        # 每个组合应有 4 个键
        for combo in combos:
            assert set(combo.keys()) == {"pct_change_min", "pct_change_max",
                                         "turnover_amount_min", "volume_ratio_min"}

    def test_generate_combinations_varied(self):
        from quant_loom.tuning.grid_search import GridSearchTuner

        tuner = GridSearchTuner()
        combos = tuner.generate_combinations("accumulation")
        # accumulation: 3*3*3 = 27
        assert len(combos) == 27
        # 所有组合应互不相同
        serialized = [json.dumps(c, sort_keys=True) for c in combos]
        assert len(set(serialized)) == 27

    def test_params_hash_deterministic(self):
        from quant_loom.tuning.grid_search import GridSearchTuner

        params = {"pct_change_min": 2.0, "volume_ratio_min": 1.5}
        h1 = GridSearchTuner.params_hash(params)
        h2 = GridSearchTuner.params_hash(params)
        assert h1 == h2
        assert len(h1) == 32

    def test_params_hash_order_independent(self):
        from quant_loom.tuning.grid_search import GridSearchTuner

        params_a = {"b": 2, "a": 1}
        params_b = {"a": 1, "b": 2}
        assert GridSearchTuner.params_hash(params_a) == GridSearchTuner.params_hash(params_b)

    def test_apply_params_modifies_config(self):
        from quant_loom.tuning.grid_search import GridSearchTuner

        tuner = GridSearchTuner()
        new_config = tuner.apply_params("breakout", {
            "pct_change_min": 1.5,
            "pct_change_max": 6.0,
            "turnover_amount_min": 150000000,
            "volume_ratio_min": 1.8,
        })
        cfg = new_config["scan_rules"]["breakout"]
        assert cfg["pct_change_min"] == 1.5
        assert cfg["volume_ratio_min"] == 1.8

    def test_score_params_empty_df(self):
        from quant_loom.tuning.grid_search import GridSearchTuner

        tuner = GridSearchTuner()
        result = tuner.score_params("breakout", {"pct_change_min": 2.0})
        assert result["alert_count"] == 0
        assert result["combined_score"] == 0.0
        assert "params_hash" in result

    def test_score_params_with_data(self):
        from quant_loom.tuning.grid_search import GridSearchTuner

        tuner = GridSearchTuner()
        df = pd.DataFrame({
            "pct_change_alert": [3.0, -2.0],
            "outcome_3d": [4.0, -1.0],
        })
        result = tuner.score_params("breakout", {"pct_change_min": 2.0}, results_df=df)
        assert result["alert_count"] == 2
        assert result["precision_3d"] == 1.0  # both same direction

    def test_export_best_config_writes_yaml(self, tmp_path):
        from quant_loom.tuning.grid_search import GridSearchTuner

        tuner = GridSearchTuner()
        output = tmp_path / "rules.tuned.yaml"
        path = tuner.export_best_config("breakout", {
            "pct_change_min": 1.5,
            "pct_change_max": 6.0,
            "turnover_amount_min": 1.5e8,
            "volume_ratio_min": 1.8,
        }, output_path=output)

        assert path.exists()
        with open(path, "r") as f:
            content = f.read()
        assert "pct_change_min: 1.5" in content

        # 应可被 yaml.safe_load 解析
        config = yaml.safe_load(content)
        assert config["scan_rules"]["breakout"]["pct_change_min"] == 1.5

    def test_export_best_config_content(self, tmp_path):
        from quant_loom.tuning.grid_search import GridSearchTuner

        tuner = GridSearchTuner()
        output = tmp_path / "rules.tuned.yaml"
        tuner.export_best_config("event_driven", {
            "pct_change_min": 5.0,
            "turnover_amount_min": 1e8,
            "main_force_ratio_min": 20.0,
        }, output_path=output)

        with open(output, "r") as f:
            content = f.read()
        # 注释头
        assert "auto-generated" in content
        # 参数值
        assert "main_force_ratio_min: 20.0" in content


class TestSearchSpaces:
    """搜索空间定义"""

    def test_all_types_have_spaces(self):
        from quant_loom.tuning.grid_search import SEARCH_SPACES
        expected = {"breakout", "accumulation", "tail_chasing", "event_driven", "sector_linked"}
        assert set(SEARCH_SPACES.keys()) == expected

    def test_no_empty_spaces(self):
        from quant_loom.tuning.grid_search import SEARCH_SPACES
        for name, space in SEARCH_SPACES.items():
            assert len(space) > 0, f"{name} has empty search space"
            for param, values in space.items():
                assert len(values) >= 2, f"{name}.{param} needs at least 2 values"
