"""
大宗交易数据获取 — 检测折溢价率异常的大额交易
使用 AkShare `stock_dzjy_mrmx()` 每日大宗交易明细
"""

from typing import Optional

import pandas as pd
from loguru import logger

from quant_loom.ops.retry import network_retry


class BlockTradeFetcher:
    """大宗交易数据获取与特征提取"""

    @staticmethod
    @network_retry
    def fetch_daily_detail(trade_date: Optional[str] = None) -> pd.DataFrame:
        """获取每日大宗交易明细"""
        import akshare as ak
        df = ak.stock_dzjy_mrmx(symbol="沪深A股", start_date=trade_date, end_date=trade_date)
        return df

    @staticmethod
    def _pad_code(code: str) -> str:
        """补零到 6 位代码"""
        code = str(code).strip()
        return code.zfill(6)

    def fetch_features(self, candidate_codes: Optional[list] = None) -> dict[str, dict]:
        """
        获取大宗交易特征，返回 {code: {premium, trade_amount, ...}} 字典

        按个股聚合当日大宗交易:
        - 多笔交易取加权平均折溢价率
        - 汇总总成交额
        """
        try:
            detail = self.fetch_daily_detail()
        except Exception as e:
            logger.warning(f"Block trade fetch failed: {e}")
            return {}

        if detail is None or detail.empty:
            return {}

        features: dict[str, dict] = {}

        for _, row in detail.iterrows():
            try:
                code = self._pad_code(row.get("证券代码", row.get("code", "")))
                if not code or code == "000000":
                    continue

                price = float(row.get("成交价", row.get("price", 0)) or 0)
                amount = float(row.get("成交额", row.get("amount", 0)) or 0)  # 万元
                premium = float(row.get("折溢率", row.get("premium", 0)) or 0)

                if price <= 0 or amount <= 0:
                    continue

                if code not in features:
                    features[code] = {
                        "total_amount": 0.0,
                        "weighted_premium_sum": 0.0,
                        "trade_count": 0,
                        "max_premium": premium,
                        "min_premium": premium,
                    }

                f = features[code]
                f["total_amount"] += amount
                f["weighted_premium_sum"] += premium * amount
                f["trade_count"] += 1
                if premium > f["max_premium"]:
                    f["max_premium"] = premium
                if premium < f["min_premium"]:
                    f["min_premium"] = premium

            except (ValueError, KeyError, TypeError):
                continue

        # Compute weighted average premium and clean up
        result: dict[str, dict] = {}
        for code, f in features.items():
            if f["total_amount"] > 0:
                avg_premium = f["weighted_premium_sum"] / f["total_amount"]
                result[code] = {
                    "premium": round(avg_premium, 2),
                    "trade_amount": round(f["total_amount"], 2),
                    "trade_count": f["trade_count"],
                }

            # Filter by candidate codes if provided
        if candidate_codes:
            candidate_set = {str(c).zfill(6) for c in candidate_codes}
            result = {k: v for k, v in result.items() if k in candidate_set}

        return result
