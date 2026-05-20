"""
市场宽度统计模块 MarketBreadth
计算全市场情绪指标：涨停/跌停数、涨跌比、腾落指数、炸板率、平均涨跌幅、总成交额
"""

import numpy as np
import pandas as pd


class MarketBreadth:
    """全市场情绪快照 — 全部静态方法"""

    # A股涨跌停阈值 (主板 10%, 科创板/创业板 20%, 北交所 30%, ST 5%)
    @staticmethod
    def _limit_threshold(code: str) -> float:
        """根据股票代码返回涨停阈值"""
        code_str = str(code).zfill(6)
        if code_str.startswith("8"):
            return 29.5  # 北交所 30%
        if code_str.startswith("68") or code_str.startswith("30"):
            return 19.5  # 科创板/创业板 20%
        if code_str.startswith("4") or code_str.startswith("8"):
            return 29.5
        return 9.5  # 主板 10%

    @classmethod
    def compute(cls, quotes_df: pd.DataFrame) -> dict:
        """
        计算全市场宽度快照

        Parameters
        ----------
        quotes_df: 包含 pct_change, turnover_amount, code 列
                   可选: high (最高) / 最高, prev_close (昨收) / 昨收

        Returns
        -------
        dict with keys:
            limit_up_count, limit_down_count, up_count, down_count, flat_count,
            up_down_ratio, adl, broken_board_count, avg_pct_change, total_turnover,
            limit_up_pct, limit_down_pct, sentiment (bullish/neutral/bearish)
        """
        if quotes_df.empty:
            return {
                "limit_up_count": 0, "limit_down_count": 0,
                "up_count": 0, "down_count": 0, "flat_count": 0,
                "up_down_ratio": 1.0, "adl": 0, "broken_board_count": 0,
                "avg_pct_change": 0.0, "total_turnover": 0.0,
                "limit_up_pct": 0.0, "limit_down_pct": 0.0,
                "sentiment": "neutral",
            }

        df = quotes_df.copy()
        pct = pd.to_numeric(df.get("pct_change", 0), errors="coerce").fillna(0)

        # 上涨/下跌/平盘
        up_mask = pct > 0
        down_mask = pct < 0
        up_count = int(up_mask.sum())
        down_count = int(down_mask.sum())
        flat_count = int((pct == 0).sum())

        # 涨跌比
        up_down_ratio = round(up_count / down_count, 2) if down_count > 0 else (up_count if up_count > 0 else 1.0)

        # 腾落指数 ADL (今日上涨数 - 下跌数，可用于累积)
        adl = up_count - down_count

        # 涨停/跌停: 按代码前缀匹配阈值
        codes = df.get("code", pd.Series([""] * len(df)))
        limit_up_count = 0
        limit_down_count = 0
        broken_board_count = 0

        # 高/低/昨收列名兼容 (中英文)
        high_col = "high" if "high" in df.columns else ("最高" if "最高" in df.columns else None)
        low_col = "low" if "low" in df.columns else ("最低" if "最低" in df.columns else None)
        prev_close_col = "prev_close" if "prev_close" in df.columns else ("昨收" if "昨收" in df.columns else None)

        for i in range(len(df)):
            code = str(codes.iloc[i]) if i < len(codes) else ""
            threshold = cls._limit_threshold(code)
            change = pct.iloc[i]

            if change >= threshold:
                limit_up_count += 1
            elif change <= -threshold:
                limit_down_count += 1
            else:
                # 炸板检测: 最高价触及涨停位但收盘未封板
                if high_col and prev_close_col and change > 0:
                    high_val = pd.to_numeric(df[high_col].iloc[i], errors="coerce")
                    prev = pd.to_numeric(df[prev_close_col].iloc[i], errors="coerce")
                    if not pd.isna(high_val) and not pd.isna(prev) and prev > 0:
                        high_pct = (high_val - prev) / prev * 100
                        if high_pct >= threshold:
                            broken_board_count += 1

        total_stocks = len(df)
        limit_up_pct = round(limit_up_count / total_stocks * 100, 2)
        limit_down_pct = round(limit_down_count / total_stocks * 100, 2)

        # 平均涨跌幅
        avg_pct_change = round(float(pct.mean()), 2)

        # 总成交额
        to = pd.to_numeric(df.get("turnover_amount", 0), errors="coerce").fillna(0)
        total_turnover = float(to.sum())

        # 情绪定性
        if limit_up_count > 80 and limit_down_count < 10:
            sentiment = "bullish"
        elif limit_down_count > 50 or (limit_down_count > limit_up_count * 2):
            sentiment = "bearish"
        else:
            sentiment = "neutral"

        return {
            "limit_up_count": limit_up_count,
            "limit_down_count": limit_down_count,
            "up_count": up_count,
            "down_count": down_count,
            "flat_count": flat_count,
            "up_down_ratio": up_down_ratio,
            "adl": adl,
            "broken_board_count": broken_board_count,
            "avg_pct_change": avg_pct_change,
            "total_turnover": total_turnover,
            "limit_up_pct": limit_up_pct,
            "limit_down_pct": limit_down_pct,
            "sentiment": sentiment,
        }

    @classmethod
    def apply_sentiment_bias(cls, confidence_score: float, breadth: dict) -> float:
        """
        基于市场情绪背景修正置信度

        修正规则 (保守):
        - 市场强势 (bullish): +0.03 (全市场偏强，信号可信度略增)
        - 市场恐慌 (bearish): +0.05 (恐慌中底部吸筹信号更有价值)
        - 中性: 不变
        - 涨跌比极端 (>5:1): ±0.02

        Returns adjusted confidence_score (仍然 capped [0, 1])
        """
        delta = 0.0

        sentiment = breadth.get("sentiment", "neutral")
        if sentiment == "bullish":
            delta += 0.03
        elif sentiment == "bearish":
            delta += 0.05

        up_down_ratio = breadth.get("up_down_ratio", 1.0)
        if up_down_ratio >= 5:
            delta += 0.02
        elif up_down_ratio <= 0.2:
            delta -= 0.02

        if breadth.get("limit_down_count", 0) > 100:
            delta -= 0.05  # 极端恐慌，整体信号谨慎

        return round(max(0.0, min(1.0, confidence_score + delta)), 2)
