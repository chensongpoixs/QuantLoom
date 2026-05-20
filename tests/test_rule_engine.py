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

"""规则引擎单元测试"""

import pandas as pd
import pytest

from quant_loom.rule_engine.rules import AlertResult, RuleEngine


@pytest.fixture
def engine():
    """加载默认规则配置"""
    from pathlib import Path
    import yaml

    config_path = Path(__file__).resolve().parent.parent / "config" / "rules.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return RuleEngine(config.get("scan_rules", {}))


class TestBreakout:
    """放量上攻型"""

    def test_breakout_matched(self, engine):
        row = pd.Series({
            "pct_change": 3.5,
            "turnover_amount": 200_000_000,
            "volume_ratio": 2.0,
            "main_force_ratio": 25.0,
        })
        result = engine.check_breakout(row)
        assert result.matched is True
        assert result.alert_type == "breakout"
        assert result.confidence_score > 0
        assert result.risk_level in ("P1", "P2")

    def test_breakout_pct_too_low(self, engine):
        row = pd.Series({
            "pct_change": 0.5,
            "turnover_amount": 200_000_000,
            "volume_ratio": 2.0,
            "main_force_ratio": 25.0,
        })
        result = engine.check_breakout(row)
        assert result.matched is False

    def test_breakout_pct_too_high(self, engine):
        row = pd.Series({
            "pct_change": 8.0,  # 超过 7% 上限
            "turnover_amount": 200_000_000,
            "volume_ratio": 2.0,
            "main_force_ratio": 25.0,
        })
        result = engine.check_breakout(row)
        assert result.matched is False

    def test_breakout_low_turnover(self, engine):
        row = pd.Series({
            "pct_change": 3.5,
            "turnover_amount": 10_000_000,  # 低于1亿
            "volume_ratio": 2.0,
            "main_force_ratio": 25.0,
        })
        result = engine.check_breakout(row)
        assert result.matched is False

    def test_breakout_low_main_force(self, engine):
        row = pd.Series({
            "pct_change": 3.5,
            "turnover_amount": 200_000_000,
            "volume_ratio": 2.0,
            "main_force_ratio": 5.0,  # 低于 20%
        })
        result = engine.check_breakout(row)
        assert result.matched is False


class TestAccumulation:
    """底部吸筹型"""

    def test_accumulation_matched(self, engine):
        row = pd.Series({
            "near_250d_low": True,
            "main_force_ratio": 15.0,
        })
        result = engine.check_accumulation(row, consecutive_inflow_days=5)
        assert result.matched is True
        assert result.alert_type == "accumulation"

    def test_accumulation_not_near_low(self, engine):
        row = pd.Series({
            "near_250d_low": False,
            "main_force_ratio": 15.0,
        })
        result = engine.check_accumulation(row, consecutive_inflow_days=5)
        assert result.matched is False

    def test_accumulation_insufficient_days(self, engine):
        row = pd.Series({
            "near_250d_low": True,
            "main_force_ratio": 15.0,
        })
        result = engine.check_accumulation(row, consecutive_inflow_days=0)
        assert result.matched is False


class TestTailChasing:
    """尾盘抢筹型"""

    def test_tail_chasing_matched(self, engine):
        row = pd.Series({
            "pct_change": 3.0,
            "turnover_amount": 200_000_000,
            "main_force_ratio": 15.0,
            "active_buy_ratio": 60.0,
        })
        result = engine.check_tail_chasing(row)
        # 注意：is_tail_window 取决于当前时间
        assert result.matched is True

    def test_tail_chasing_negative_pct(self, engine):
        row = pd.Series({
            "pct_change": -2.0,
            "turnover_amount": 200_000_000,
            "main_force_ratio": 15.0,
        })
        result = engine.check_tail_chasing(row)
        assert result.matched is False


class TestEventDriven:
    """事件驱动型"""

    def test_event_driven_no_event(self, engine):
        row = pd.Series({
            "pct_change": 4.0,
            "turnover_amount": 150_000_000,
            "main_force_ratio": 20.0,
        })
        result = engine.check_event_driven(row, has_event=False)
        assert result.matched is True
        assert result.risk_level == "P2"

    def test_event_driven_with_event(self, engine):
        row = pd.Series({
            "pct_change": 5.0,
            "turnover_amount": 200_000_000,
            "main_force_ratio": 25.0,
        })
        result = engine.check_event_driven(row, has_event=True)
        assert result.matched is True
        assert result.risk_level == "P1"
        assert result.confidence_score >= 0.7

    def test_event_driven_low_main_force(self, engine):
        row = pd.Series({
            "pct_change": 5.0,
            "turnover_amount": 200_000_000,
            "main_force_ratio": 5.0,
        })
        result = engine.check_event_driven(row)
        assert result.matched is False


class TestSectorLinked:
    """板块联动型"""

    def test_sector_linked_matched(self, engine):
        row = pd.Series({"code": "000001"})
        sector_stats = {
            "sector_name": "银行",
            "avg_pct_change": 2.5,
            "rising_count": 8,
        }
        result = engine.check_sector_linked(row, sector_stats)
        assert result.matched is True
        assert result.alert_type == "sector_linked"

    def test_sector_linked_weak(self, engine):
        row = pd.Series({"code": "000001"})
        sector_stats = {
            "sector_name": "银行",
            "avg_pct_change": 0.5,  # 低于阈值
            "rising_count": 1,
        }
        result = engine.check_sector_linked(row, sector_stats)
        assert result.matched is False

    def test_sector_linked_no_stats(self, engine):
        row = pd.Series({"code": "000001"})
        result = engine.check_sector_linked(row, None)
        assert result.matched is False


class TestTailChasingTime:
    """尾盘抢筹 current_time 参数 — 支持回测"""

    def test_tail_window_detectable_with_current_time(self, engine):
        """传入尾盘时间应命中 is_tail_window 逻辑"""
        from datetime import datetime
        tail_time = datetime(2024, 6, 15, 14, 35)  # 14:35 在尾盘窗口
        row = pd.Series({
            "pct_change": 3.0,
            "turnover_amount": 200_000_000,
            "main_force_ratio": 15.0,
            "active_buy_ratio": 60.0,
        })
        result = engine.check_tail_chasing(row, current_time=tail_time)
        assert result.matched is True
        # 尾盘窗口内置信度更高
        assert result.confidence_score >= 0.7

    def test_non_tail_window_with_current_time(self, engine):
        """传入非尾盘时间应使用基础阈值 (P2)"""
        from datetime import datetime
        morning_time = datetime(2024, 6, 15, 10, 30)  # 上午 10:30
        row = pd.Series({
            "pct_change": 3.0,
            "turnover_amount": 200_000_000,
            "main_force_ratio": 15.0,
            "active_buy_ratio": 60.0,
        })
        result = engine.check_tail_chasing(row, current_time=morning_time)
        assert result.matched is True
        # 非尾盘窗口置信度较低
        assert result.confidence_score < 0.7

    def test_tail_chasing_config_not_loaded_as_none(self, engine):
        """验证 .get() 在无 key 时回退到默认值而非 None"""
        # 使用 config 中未自定义阈值的场景 (引擎会 fallback)
        # 硬编码已被 .get(key, default) 替代
        row = pd.Series({
            "pct_change": 1.5,     # 在默认 [1.0, 7.0] 范围内
            "main_force_ratio": 12.0,  # >= 默认 10.0
        })
        result = engine.check_tail_chasing(row)
        # 如果 .get() 工作正常，不应该 crash
        assert isinstance(result.matched, bool)

    def test_event_driven_uses_config_main_force(self, engine):
        """event_driven 应使用 YAML 配置的 main_force_ratio_min 而非硬编码 15.0"""
        row_config_satisfied = pd.Series({
            "pct_change": 5.0,
            "turnover_amount": 100_000_000,
            "main_force_ratio": 15.0,
        })
        # 15.0 等于默认值，应通过
        result = engine.check_event_driven(row_config_satisfied)
        assert result.matched is True

        row_below_default = pd.Series({
            "pct_change": 5.0,
            "turnover_amount": 100_000_000,
            "main_force_ratio": 5.0,  # 低于默认 15.0
        })
        result = engine.check_event_driven(row_below_default)
        assert result.matched is False


class TestAlertResult:
    """AlertResult 数据类"""

    def test_default_not_matched(self):
        r = AlertResult()
        assert r.matched is False
        assert r.alert_type == ""
        assert r.confidence_score == 0.0

    def test_matched_result(self):
        r = AlertResult(
            matched=True,
            alert_type="breakout",
            trigger_reason="测试",
            confidence_score=0.85,
            risk_level="P1",
        )
        assert r.matched is True
        assert r.alert_type == "breakout"


class TestGapFill:
    """缺口回补型"""

    def test_gap_up_fill_detected(self, engine):
        row = pd.Series({
            "volume_ratio": 1.5,
            "main_force_ratio": 10.0,
        })
        tech = {"prev_close": 50.0, "today_open": 52.0, "today_high": 53.0, "today_low": 50.0}
        result = engine.check_gap_fill(row, tech=tech)
        assert result.matched is True
        assert result.alert_type == "gap_fill"

    def test_gap_down_fill_detected(self, engine):
        row = pd.Series({
            "volume_ratio": 1.5,
            "main_force_ratio": -8.0,
        })
        tech = {"prev_close": 50.0, "today_open": 48.0, "today_high": 50.0, "today_low": 47.0}
        result = engine.check_gap_fill(row, tech=tech)
        assert result.matched is True
        assert result.alert_type == "gap_fill"

    def test_no_gap_no_alert(self, engine):
        row = pd.Series({"volume_ratio": 1.5, "main_force_ratio": 10.0})
        tech = {"prev_close": 50.0, "today_open": 50.2, "today_high": 51.0, "today_low": 49.8}
        result = engine.check_gap_fill(row, tech=tech)
        assert not result.matched

    def test_no_tech_data(self, engine):
        row = pd.Series({"volume_ratio": 1.5, "main_force_ratio": 10.0})
        result = engine.check_gap_fill(row, tech=None)
        assert not result.matched

    def test_low_volume_no_alert(self, engine):
        row = pd.Series({"volume_ratio": 1.0, "main_force_ratio": 10.0})
        tech = {"prev_close": 50.0, "today_open": 52.0, "today_high": 53.0, "today_low": 50.0}
        result = engine.check_gap_fill(row, tech=tech)
        assert not result.matched


class TestBlockTrade:
    """大宗交易异动型"""

    def test_premium_block_trade(self, engine):
        row = pd.Series({"code": "000001"})
        bt = {"000001": {"premium": 5.0, "trade_amount": 10000}}
        result = engine.check_block_trade(row, block_trades=bt)
        assert result.matched is True
        assert result.alert_type == "block_trade"

    def test_discount_block_trade(self, engine):
        row = pd.Series({"code": "000001"})
        bt = {"000001": {"premium": -8.0, "trade_amount": 10000}}
        result = engine.check_block_trade(row, block_trades=bt)
        assert result.matched is True
        assert result.alert_type == "block_trade"

    def test_small_trade_no_alert(self, engine):
        row = pd.Series({"code": "000001"})
        bt = {"000001": {"premium": 5.0, "trade_amount": 1000}}
        result = engine.check_block_trade(row, block_trades=bt)
        assert not result.matched

    def test_small_premium_no_alert(self, engine):
        row = pd.Series({"code": "000001"})
        bt = {"000001": {"premium": 1.0, "trade_amount": 10000}}
        result = engine.check_block_trade(row, block_trades=bt)
        assert not result.matched

    def test_code_not_in_bt(self, engine):
        row = pd.Series({"code": "000002"})
        bt = {"000001": {"premium": 5.0, "trade_amount": 10000}}
        result = engine.check_block_trade(row, block_trades=bt)
        assert not result.matched

    def test_no_block_trades(self, engine):
        row = pd.Series({"code": "000001"})
        result = engine.check_block_trade(row, block_trades=None)
        assert not result.matched


class TestHighTurnoverLowReturn:
    """高换手低涨幅型"""

    def test_high_turnover_low_return_matched(self, engine):
        row = pd.Series({
            "turnover_rate": 15.0,
            "pct_change": 1.0,
            "turnover_amount": 200_000_000,
            "main_force_ratio": 2.0,
        })
        result = engine.check_high_turnover_low_return(row)
        assert result.matched is True
        assert result.alert_type == "high_turnover_low_return"

    def test_normal_turnover_no_alert(self, engine):
        row = pd.Series({
            "turnover_rate": 3.0,
            "pct_change": 1.0,
            "turnover_amount": 200_000_000,
        })
        result = engine.check_high_turnover_low_return(row)
        assert not result.matched

    def test_large_move_no_alert(self, engine):
        row = pd.Series({
            "turnover_rate": 15.0,
            "pct_change": 5.0,
            "turnover_amount": 200_000_000,
        })
        result = engine.check_high_turnover_low_return(row)
        assert not result.matched

    def test_low_amount_no_alert(self, engine):
        row = pd.Series({
            "turnover_rate": 15.0,
            "pct_change": 0.5,
            "turnover_amount": 10_000_000,
        })
        result = engine.check_high_turnover_low_return(row)
        assert not result.matched

    def test_negative_return_still_matched(self, engine):
        row = pd.Series({
            "turnover_rate": 12.0,
            "pct_change": -1.5,
            "turnover_amount": 300_000_000,
            "main_force_ratio": -3.0,
        })
        result = engine.check_high_turnover_low_return(row)
        assert result.matched is True


class TestIntradaySpike:
    """盘中急拉/急跌型"""

    def test_spike_up_detected(self, engine):
        row = pd.Series({
            "pct_change": 3.0,
            "turnover_amount": 200_000_000,
        })
        tech = {"today_open": 50.0, "today_high": 53.0, "today_low": 49.5}
        result = engine.check_intraday_spike(row, tech=tech)
        assert result.matched is True
        assert result.alert_type == "intraday_spike"

    def test_spike_down_detected(self, engine):
        row = pd.Series({
            "pct_change": -3.0,
            "turnover_amount": 200_000_000,
        })
        tech = {"today_open": 50.0, "today_high": 50.5, "today_low": 47.0}
        result = engine.check_intraday_spike(row, tech=tech)
        assert result.matched is True
        assert result.alert_type == "intraday_spike"

    def test_wide_range_detected(self, engine):
        row = pd.Series({
            "pct_change": 0.0,
            "turnover_amount": 200_000_000,
        })
        tech = {"today_open": 50.0, "today_high": 54.0, "today_low": 46.5}
        result = engine.check_intraday_spike(row, tech=tech)
        assert result.matched is True

    def test_normal_range_no_alert(self, engine):
        row = pd.Series({
            "pct_change": 0.5,
            "turnover_amount": 200_000_000,
        })
        tech = {"today_open": 50.0, "today_high": 51.0, "today_low": 49.5}
        result = engine.check_intraday_spike(row, tech=tech)
        assert not result.matched

    def test_no_tech_data(self, engine):
        row = pd.Series({
            "pct_change": 3.0,
            "turnover_amount": 200_000_000,
        })
        result = engine.check_intraday_spike(row, tech=None)
        assert not result.matched

    def test_low_amount_no_alert(self, engine):
        row = pd.Series({
            "pct_change": 3.0,
            "turnover_amount": 10_000_000,
        })
        tech = {"today_open": 50.0, "today_high": 53.0, "today_low": 49.5}
        result = engine.check_intraday_spike(row, tech=tech)
        assert not result.matched
