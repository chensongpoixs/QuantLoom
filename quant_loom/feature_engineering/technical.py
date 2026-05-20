"""
技术指标计算模块
提供 15+ 标准技术指标: MA, EMA, MACD, RSI, KDJ, BOLL, ATR, VWAP, OBV, 均线关系判定
所有方法均为静态方法，接受 pandas Series/DataFrame，返回相同类型
"""

from typing import Optional

import numpy as np
import pandas as pd


class TechnicalIndicators:
    """技术指标计算器 — 全部静态方法，零外部依赖"""

    # ================================================================
    # 趋势类
    # ================================================================

    @staticmethod
    def ma(close: pd.Series, period: int = 5) -> pd.Series:
        """简单移动平均"""
        return close.rolling(window=period, min_periods=1).mean()

    @staticmethod
    def ema(close: pd.Series, period: int = 12) -> pd.Series:
        """指数移动平均"""
        return close.ewm(span=period, adjust=False).mean()

    @staticmethod
    def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        """
        MACD — 返回 DataFrame 含 DIF, DEA, MACD_hist
        DIF = EMA(fast) - EMA(slow)
        DEA = EMA(DIF, signal)
        MACD_hist = 2 * (DIF - DEA)
        """
        ema_fast = TechnicalIndicators.ema(close, fast)
        ema_slow = TechnicalIndicators.ema(close, slow)
        dif = ema_fast - ema_slow
        dea = TechnicalIndicators.ema(dif, signal)
        return pd.DataFrame({
            "dif": dif,
            "dea": dea,
            "macd_hist": 2 * (dif - dea),
        })

    # ================================================================
    # 动量类
    # ================================================================

    @staticmethod
    def rsi(close: pd.Series, period: int = 14) -> pd.Series:
        """RSI — 相对强弱指标"""
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()
        # 使用 Wilder's smoothing 处理后续值
        for i in range(period, len(avg_gain)):
            if pd.isna(avg_gain.iloc[i]):
                avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gain.iloc[i]) / period
                avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + loss.iloc[i]) / period
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def kdj(df: pd.DataFrame, n: int = 9, k_period: int = 3, d_period: int = 3) -> pd.DataFrame:
        """
        KDJ — 随机指标
        RSV = (close - low_n) / (high_n - low_n) * 100
        K = EMA(RSV, k_period)
        D = EMA(K, d_period)
        J = 3*K - 2*D
        """
        high_n = df["high"].rolling(window=n, min_periods=1).max()
        low_n = df["low"].rolling(window=n, min_periods=1).min()
        hl_range = (high_n - low_n).replace(0, np.nan)
        rsv = (df["close"] - low_n) / hl_range * 100
        rsv = rsv.fillna(50)

        k = rsv.ewm(alpha=1/k_period, adjust=False).mean()
        d = k.ewm(alpha=1/d_period, adjust=False).mean()
        j = 3 * k - 2 * d
        return pd.DataFrame({"k": k, "d": d, "j": j})

    @staticmethod
    def williams_r(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        威廉指标 WR
        WR = (high_n - close) / (high_n - low_n) * -100
        """
        high_n = df["high"].rolling(window=period, min_periods=1).max()
        low_n = df["low"].rolling(window=period, min_periods=1).min()
        hl_range = (high_n - low_n).replace(0, np.nan)
        return (high_n - df["close"]) / hl_range * -100

    # ================================================================
    # 波动类
    # ================================================================

    @staticmethod
    def boll(close: pd.Series, period: int = 20, std_multiplier: float = 2.0) -> pd.DataFrame:
        """
        布林带 BOLL
        middle = MA(period)
        upper = middle + std_multiplier * STD
        lower = middle - std_multiplier * STD
        """
        mid = TechnicalIndicators.ma(close, period)
        std = close.rolling(window=period, min_periods=1).std()
        return pd.DataFrame({
            "boll_upper": mid + std_multiplier * std,
            "boll_mid": mid,
            "boll_lower": mid - std_multiplier * std,
            "boll_width": (2 * std_multiplier * std) / mid.replace(0, np.nan),  # 带宽
        })

    @staticmethod
    def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        ATR — 平均真实波幅
        TR = max(high-low, |high-prev_close|, |low-prev_close|)
        ATR = MA(TR, period)
        """
        high, low, close = df["high"], df["low"], df["close"]
        prev_close = close.shift(1)
        tr = pd.concat([
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        return tr.rolling(window=period, min_periods=1).mean()

    # ================================================================
    # 量价类
    # ================================================================

    @staticmethod
    def obv(df: pd.DataFrame) -> pd.Series:
        """
        OBV — 能量潮
        涨日累加成交量，跌日累减成交量
        """
        close_diff = df["close"].diff()
        direction = np.where(close_diff > 0, 1, np.where(close_diff < 0, -1, 0))
        obv = (df["volume"] * direction).cumsum()
        return pd.Series(obv, index=df.index, name="obv")

    @staticmethod
    def vwap(df: pd.DataFrame) -> pd.Series:
        """
        VWAP — 成交量加权平均价格 (日内)
        VWAP = Σ(price * volume) / Σ(volume)

        日级别使用时，typical_price = (high+low+close)/3
        """
        typical = (df["high"] + df["low"] + df["close"]) / 3
        cum_vp = (typical * df["volume"]).cumsum()
        cum_vol = df["volume"].cumsum()
        return cum_vp / cum_vol.replace(0, np.nan)

    @staticmethod
    def volume_ratio(volume: pd.Series, period: int = 5) -> pd.Series:
        """量比 = 当日成交量 / 过去 N 日均量"""
        avg_vol = volume.shift(1).rolling(window=period, min_periods=1).mean()
        return volume / avg_vol.replace(0, np.nan)

    # ================================================================
    # 均线关系判定
    # ================================================================

    @staticmethod
    def ma_alignment(close: pd.Series) -> dict:
        """
        均线多空排列与交叉判定
        返回多维度字典:
        - is_bullish: MA5 > MA10 > MA20 > MA60 (多头排列)
        - is_bearish: MA5 < MA10 < MA20 < MA60 (空头排列)
        - golden_cross: MA5 上穿 MA20 (近3日内)
        - death_cross: MA5 下穿 MA20 (近3日内)
        - adhesion: 均线粘合度 (MA5/10/20 标准差 / MA20)
        - price_vs_ma: 最新价相对各均线的位置百分比
        """
        ma5 = TechnicalIndicators.ma(close, 5)
        ma10 = TechnicalIndicators.ma(close, 10)
        ma20 = TechnicalIndicators.ma(close, 20)
        ma60 = TechnicalIndicators.ma(close, 60)

        latest = slice(-1, None)

        # 多空排列
        is_bullish = bool(
            ma5.iloc[-1] > ma10.iloc[-1] > ma20.iloc[-1] > ma60.iloc[-1]
        )
        is_bearish = bool(
            ma5.iloc[-1] < ma10.iloc[-1] < ma20.iloc[-1] < ma60.iloc[-1]
        )

        # 金叉/死叉 — MA5 与 MA20 交叉
        golden_cross = False
        death_cross = False
        if len(ma5) >= 3 and len(ma20) >= 3:
            # 前日 MA5 <= MA20, 今日 MA5 > MA20 → 金叉
            prev_5 = ma5.iloc[-2]
            prev_20 = ma20.iloc[-2]
            cur_5 = ma5.iloc[-1]
            cur_20 = ma20.iloc[-1]
            if prev_5 <= prev_20 and cur_5 > cur_20:
                golden_cross = True
            if prev_5 >= prev_20 and cur_5 < cur_20:
                death_cross = True

        # 均线粘合度
        mas = pd.concat([ma5, ma10, ma20], axis=1)
        mas.columns = ["ma5", "ma10", "ma20"]
        adhesion = float(
            mas.iloc[-1].std() / ma20.iloc[-1] if ma20.iloc[-1] > 0 else 0
        )

        # 价格 vs 均线位置
        last_close = close.iloc[-1]
        price_vs_ma = {
            f"vs_ma{p}": round(float((last_close - ma.iloc[-1]) / ma.iloc[-1] * 100), 2)
            for p, ma in [(5, ma5), (10, ma10), (20, ma20), (60, ma60)]
            if ma.iloc[-1] > 0
        }

        return {
            "is_bullish": is_bullish,
            "is_bearish": is_bearish,
            "golden_cross": golden_cross,
            "death_cross": death_cross,
            "adhesion": round(adhesion, 4),
            "price_vs_ma": price_vs_ma,
        }

    # ================================================================
    # 批量计算
    # ================================================================

    @classmethod
    def compute_all(cls, klines_df: pd.DataFrame) -> pd.DataFrame:
        """
        批量计算所有技术指标，返回带全部指标列的 DataFrame
        klines_df 需包含: open, high, low, close, volume
        """
        if klines_df.empty:
            return klines_df

        df = klines_df.copy()
        close = df["close"]

        # 趋势
        for p in [5, 10, 20, 60, 120]:
            df[f"ma{p}"] = cls.ma(close, p)
        df["ema12"] = cls.ema(close, 12)
        df["ema26"] = cls.ema(close, 26)

        macd_df = cls.macd(close)
        df["macd_dif"] = macd_df["dif"]
        df["macd_dea"] = macd_df["dea"]
        df["macd_hist"] = macd_df["macd_hist"]

        # 动量
        df["rsi6"] = cls.rsi(close, 6)
        df["rsi14"] = cls.rsi(close, 14)

        kdj_df = cls.kdj(df)
        df["kdj_k"] = kdj_df["k"]
        df["kdj_d"] = kdj_df["d"]
        df["kdj_j"] = kdj_df["j"]

        df["wr14"] = cls.williams_r(df, 14)

        # 波动
        boll_df = cls.boll(close)
        df["boll_upper"] = boll_df["boll_upper"]
        df["boll_mid"] = boll_df["boll_mid"]
        df["boll_lower"] = boll_df["boll_lower"]
        df["boll_width"] = boll_df["boll_width"]

        df["atr14"] = cls.atr(df, 14)

        # 量价
        df["obv"] = cls.obv(df).astype(float)
        df["vwap"] = cls.vwap(df)
        df["vol_ratio5"] = cls.volume_ratio(df["volume"], 5)

        return df

    @classmethod
    def compute_latest_features(cls, klines_df: pd.DataFrame) -> dict:
        """
        计算最新一天的技术特征字典 (用于规则引擎)
        klines_df 需包含足够历史数据 (≥ 60 行)
        """
        df = cls.compute_all(klines_df)
        latest = df.iloc[-1]

        features = {
            "ma5": float(latest.get("ma5", 0) or 0),
            "ma10": float(latest.get("ma10", 0) or 0),
            "ma20": float(latest.get("ma20", 0) or 0),
            "ma60": float(latest.get("ma60", 0) or 0),
            "ma120": float(latest.get("ma120", 0) or 0),
            "macd_dif": float(latest.get("macd_dif", 0) or 0),
            "macd_dea": float(latest.get("macd_dea", 0) or 0),
            "macd_hist": float(latest.get("macd_hist", 0) or 0),
            "rsi6": float(latest.get("rsi6", 0) or 0),
            "rsi14": float(latest.get("rsi14", 0) or 0),
            "kdj_k": float(latest.get("kdj_k", 0) or 0),
            "kdj_d": float(latest.get("kdj_d", 0) or 0),
            "kdj_j": float(latest.get("kdj_j", 0) or 0),
            "wr14": float(latest.get("wr14", 0) or 0),
            "boll_upper": float(latest.get("boll_upper", 0) or 0),
            "boll_mid": float(latest.get("boll_mid", 0) or 0),
            "boll_lower": float(latest.get("boll_lower", 0) or 0),
            "boll_width": float(latest.get("boll_width", 0) or 0),
            "atr14": float(latest.get("atr14", 0) or 0),
            "vol_ratio5": float(latest.get("vol_ratio5", 0) or 0),
            "prev_close": float(df["close"].iloc[-2]) if len(df) >= 2 else 0.0,
            "today_open": float(df["open"].iloc[-1]) if "open" in df.columns and len(df) >= 1 else 0.0,
            "today_high": float(df["high"].iloc[-1]) if "high" in df.columns and len(df) >= 1 else 0.0,
            "today_low": float(df["low"].iloc[-1]) if "low" in df.columns and len(df) >= 1 else 0.0,
        }
        features.update(cls.ma_alignment(close=df["close"]))
        return features
