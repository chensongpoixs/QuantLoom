"""
止损/止盈计算器 — 基于 ATR/均线/摆动低点/移动止盈
"""

import numpy as np
import pandas as pd


class StopLossCalculator:
    """止损/止盈计算器 — 全部为静态方法"""

    @staticmethod
    def atr_stop(kline: pd.DataFrame, multiplier: float = 2.0, period: int = 14) -> dict:
        """
        ATR 动态止损 — 在最近最高点下方 N 倍 ATR 处设置止损

        Returns
        -------
        dict with: stop_price, atr, highest_price, stop_pct (距离当前价百分比)
        """
        if kline is None or kline.empty or "close" not in kline.columns:
            return {}

        df = kline.copy()
        required_cols = {"high", "low", "close"}
        if not required_cols.issubset(set(df.columns)):
            return {}

        for col in required_cols:
            df[col] = df[col].astype(float)

        # True Range
        df["tr"] = np.maximum(
            df["high"] - df["low"],
            np.maximum(
                abs(df["high"] - df["close"].shift(1)),
                abs(df["low"] - df["close"].shift(1)),
            ),
        )
        atr = df["tr"].iloc[-period:].mean() if len(df) >= period else df["tr"].mean()

        highest = df["high"].max()
        current = df["close"].iloc[-1]

        stop_price = highest - multiplier * atr
        stop_pct = (stop_price / current - 1) * 100  # 负值 = 止损位低于当前价

        return {
            "stop_price": round(stop_price, 2),
            "atr": round(atr, 2),
            "highest_price": round(highest, 2),
            "current_price": round(current, 2),
            "stop_pct": round(stop_pct, 2),
            "method": "atr_stop",
        }

    @staticmethod
    def ma_stop(kline: pd.DataFrame, period: int = 20) -> dict:
        """
        均线止损 — 跌破 N 日均线即止损

        Returns
        -------
        dict with: stop_price (MA值), current_price, stop_pct, period
        """
        if kline is None or kline.empty or "close" not in kline.columns:
            return {}

        close = kline["close"].astype(float)
        if len(close) < period:
            return {}

        ma = close.iloc[-period:].mean()
        current = close.iloc[-1]

        return {
            "stop_price": round(ma, 2),
            "current_price": round(current, 2),
            "stop_pct": round((ma / current - 1) * 100, 2),
            "period": period,
            "method": "ma_stop",
        }

    @staticmethod
    def swing_low_stop(kline: pd.DataFrame, lookback: int = 20) -> dict:
        """
        摆动低点止损 — 最近 N 日最低点下方作为止损

        Returns
        -------
        dict with: stop_price, current_price, stop_pct, lookback
        """
        if kline is None or kline.empty or "low" not in kline.columns:
            return {}

        low = kline["low"].astype(float)
        current = kline["close"].astype(float).iloc[-1] if "close" in kline.columns else low.iloc[-1]

        swing_low = low.iloc[-lookback:].min() if len(low) >= lookback else low.min()

        return {
            "stop_price": round(swing_low, 2),
            "current_price": round(current, 2),
            "stop_pct": round((swing_low / current - 1) * 100, 2),
            "lookback": lookback,
            "method": "swing_low_stop",
        }

    @staticmethod
    def trailing_stop(kline: pd.DataFrame, pct: float = 5.0) -> dict:
        """
        移动止盈 — 从最高点回撤 N% 即止盈

        Returns
        -------
        dict with: stop_price, highest, current_price, trail_pct, method
        """
        if kline is None or kline.empty or "high" not in kline.columns:
            return {}

        high = kline["high"].astype(float)
        current = kline["close"].astype(float).iloc[-1] if "close" in kline.columns else high.iloc[-1]

        highest = high.max()
        stop_price = highest * (1 - pct / 100)

        return {
            "stop_price": round(stop_price, 2),
            "highest_price": round(highest, 2),
            "current_price": round(current, 2),
            "trail_pct": pct,
            "stop_pct": round((stop_price / current - 1) * 100, 2),
            "method": "trailing_stop",
        }

    @staticmethod
    def compute_all_stops(kline: pd.DataFrame) -> dict:
        """计算所有止损/止盈位"""
        return {
            "atr": StopLossCalculator.atr_stop(kline),
            "ma": StopLossCalculator.ma_stop(kline),
            "swing_low": StopLossCalculator.swing_low_stop(kline),
            "trailing": StopLossCalculator.trailing_stop(kline),
        }

    @staticmethod
    def suggest_stop(kline: pd.DataFrame, risk_tolerance: str = "medium") -> dict:
        """
        根据风险偏好推荐止损策略

        risk_tolerance: "tight" / "medium" / "loose"

        Returns 推荐的止损位和策略信息
        """
        all_stops = StopLossCalculator.compute_all_stops(kline)

        # 根据风险偏好选择策略组合
        preferences = {
            "tight": ["atr", "ma"],        # 严格: ATR+均线双重确认
            "medium": ["atr", "swing_low"],  # 适中: ATR 为主, 摆动低点为辅
            "loose": ["swing_low", "ma"],    # 宽松: 给更多空间
        }

        methods = preferences.get(risk_tolerance, preferences["medium"])
        selected = {m: all_stops.get(m, {}) for m in methods}

        # 取最保守 (最接近当前价) 的止损位
        stops = []
        for s in selected.values():
            if s and s.get("stop_price"):
                stops.append(s["stop_price"])
        recommended = max(stops) if stops else 0  # 最高止损位 = 最严格

        return {
            "recommended_stop": round(recommended, 2),
            "current_price": all_stops.get("atr", {}).get("current_price", 0),
            "risk_tolerance": risk_tolerance,
            "strategies": selected,
            "risk_reward_ratio": StopLossCalculator._rr_ratio(recommended, all_stops),
        }

    @staticmethod
    def _rr_ratio(stop_price: float, all_stops: dict) -> float:
        """计算风险收益比 — stop 距离 / ATR"""
        atr_info = all_stops.get("atr", {})
        current = atr_info.get("current_price", 0)
        atr = atr_info.get("atr", 0)
        if not current or not atr or not stop_price:
            return 0.0
        risk = abs(current - stop_price)
        return round(risk / atr, 2) if atr > 0 else 0.0
