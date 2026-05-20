"""
板块轮动分析 — 行业涨跌幅 × 时间维度的热力图数据
使用同花顺 (THS) 行业板块指数数据
"""

import time
from typing import Optional

import pandas as pd
from loguru import logger

from quant_loom.ops.retry import network_retry


class SectorRotationFetcher:
    """行业板块轮动数据获取与计算"""

    def __init__(self, max_sectors: int = 30):
        self._max_sectors = max_sectors

    @staticmethod
    def _throttle(seconds: float = 1.0):
        """请求节流"""
        time.sleep(seconds)

    @staticmethod
    @network_retry
    def fetch_sector_list() -> pd.DataFrame:
        """获取行业板块列表 (含当日涨跌幅/成交额)"""
        import akshare as ak
        df = ak.stock_board_industry_summary_ths()
        return df

    @staticmethod
    @network_retry
    def fetch_sector_history(symbol: str, start_date: str,
                             end_date: str) -> pd.DataFrame:
        """获取单个行业板块的历史指数 K 线 (THS)"""
        import akshare as ak
        df = ak.stock_board_industry_index_ths(
            symbol=symbol, start_date=start_date, end_date=end_date
        )
        if df is None or df.empty:
            return pd.DataFrame()
        return df

    def compute_rotation_matrix(self, lookback_days: int = 20) -> Optional[dict]:
        """
        计算板块轮动矩阵

        Parameters
        ----------
        lookback_days: 回溯交易日数 (≈4周=20个交易日)

        Returns
        -------
        dict with:
            sectors: [sector_name, ...]
            dates: [date_str, ...]
            data: [[pct_change, ...], ...]  # sectors × dates 矩阵
            latest_ranking: [{sector, pct_change}, ...]  # 最新日排名
            momentum_ranking: [{sector, avg_return, cumulative}, ...]  # 期间动量排名
        """
        try:
            sectors_df = self.fetch_sector_list()
        except Exception as e:
            logger.warning(f"Failed to fetch sector list: {e}")
            return None

        if sectors_df is None or sectors_df.empty:
            return None

        # 按成交额排序，取前 N 个活跃板块
        if "总成交额" in sectors_df.columns:
            sectors_df = sectors_df.sort_values("总成交额", ascending=False)

        top_sectors = sectors_df.head(self._max_sectors)
        sector_names = top_sectors["板块"].tolist()

        # 计算日期范围
        from datetime import datetime, timedelta
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=lookback_days * 2)).strftime("%Y%m%d")

        # 拉取每个板块的历史数据
        all_returns = {}
        for i, name in enumerate(sector_names):
            try:
                hist = self.fetch_sector_history(name, start_date, end_date)
                if hist is not None and not hist.empty and "收盘价" in hist.columns:
                    hist["日期"] = pd.to_datetime(hist["日期"])
                    hist = hist.sort_values("日期")
                    hist["return"] = hist["收盘价"].pct_change()
                    hist = hist.dropna(subset=["return"])
                    # 取最近 N 个交易日
                    hist = hist.tail(lookback_days)
                    if not hist.empty:
                        all_returns[name] = hist.set_index("日期")["return"]
            except Exception as e:
                logger.debug(f"Failed to fetch history for sector {name}: {e}")

            if i > 0:
                self._throttle(1.0)

        if not all_returns:
            return None

        # 构建统一日期索引 (所有板块的交集)
        returns_df = pd.DataFrame(all_returns)
        returns_df = returns_df.dropna(how="all")  # 去掉全 NaN 行

        # 只保留至少有 50% 板块有数据的日期
        min_sectors = max(1, len(sector_names) // 2)
        returns_df = returns_df.dropna(thresh=min_sectors)

        if returns_df.empty or len(returns_df) < 3:
            return None

        # 构建输出: sectors × dates 矩阵
        dates = [d.strftime("%Y-%m-%d") for d in returns_df.index]
        sectors = [s for s in sector_names if s in returns_df.columns]

        data = []
        for sector in sectors:
            row = []
            for date_str in dates:
                val = returns_df.loc[date_str, sector]
                if pd.isna(val):
                    row.append(None)
                else:
                    row.append(round(val * 100, 2))  # 转为百分比
            data.append(row)

        # 最新日排名 (按涨跌幅降序)
        latest = returns_df.iloc[-1] if len(returns_df) > 0 else None
        if latest is not None:
            latest_sorted = latest.dropna().sort_values(ascending=False)
            latest_ranking = [
                {"sector": s, "pct_change": round(float(v) * 100, 2)}
                for s, v in latest_sorted.items()
            ]
        else:
            latest_ranking = []

        # 期间动量排名 (累计收益)
        cumulative = (1 + returns_df).prod() - 1
        cumulative_sorted = cumulative.sort_values(ascending=False)
        avg_ret = returns_df.mean()
        momentum_ranking = [
            {
                "sector": s,
                "cumulative_return": round(float(cumulative.get(s, 0)) * 100, 2),
                "avg_daily_return": round(float(avg_ret.get(s, 0)) * 100, 2),
            }
            for s in cumulative_sorted.index
        ]

        return {
            "sectors": sectors,
            "dates": dates,
            "data": data,
            "latest_ranking": latest_ranking,
            "momentum_ranking": momentum_ranking,
            "lookback_days": lookback_days,
        }
