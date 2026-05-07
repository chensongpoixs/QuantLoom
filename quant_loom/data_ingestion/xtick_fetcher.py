"""
XTick 数据抓取模块
通过 XTick HTTP REST API (api.xtick.top) 获取 A 股行情数据
官网: http://www.xtick.top
"""

import time
from datetime import datetime, date
from typing import Optional

import pandas as pd
import requests
from loguru import logger

from config.settings import settings
from quant_loom.ops.retry import network_retry


class XTickFetcher:
    """XTick 数据抓取器 — HTTP REST API"""

    def __init__(self, rate_limit: float = 0.5):
        self.token = settings.xtick_token
        self.api_url = settings.xtick_api_url
        self.rate_limit = rate_limit
        self._last_call = 0.0
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "QuantLoom/0.1",
            "Accept": "application/json",
        })

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def _throttle(self):
        """频率控制"""
        elapsed = time.time() - self._last_call
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_call = time.time()

    @network_retry
    def _do_api_call(self, params: dict) -> Optional[list]:
        """实际 HTTP GET 调用 (带重试)。
        仅重试 requests 网络层异常；业务层错误 (code != 0) 不重试。
        """
        self._throttle()
        resp = self._session.get(
            self.api_url,
            params=params,
            timeout=(10, 30),  # (connect, read)
        )
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, dict):
            if data.get("code") == 0:
                return data.get("data", [])
            else:
                logger.error(f"XTick API 返回错误: {data.get('msg', data)}")
                return None
        elif isinstance(data, list):
            return data
        else:
            logger.warning(f"XTick 未知响应格式: {type(data)}")
            return None

    def _request(self, params: dict) -> Optional[list]:
        """
        发送 HTTP GET 请求到 XTick API
        返回 JSON list，失败返回 None
        """
        if not self.enabled:
            logger.error("XTick token 未配置")
            return None

        params["token"] = self.token

        try:
            return self._do_api_call(params)
        except requests.Timeout:
            logger.error(f"XTick API 超时 (重试耗尽): {params.get('type')} {params.get('code')}")
            return None
        except requests.ConnectionError:
            logger.error(f"XTick API 连接失败 (重试耗尽): {self.api_url}")
            return None
        except Exception as e:
            logger.error(f"XTick API 请求异常: {e}")
            return None

    # ---- 股票列表 ----

    def fetch_all_stocks(self) -> pd.DataFrame:
        """
        获取全 A 股日线数据（取今日快照作为股票列表 + 行情）
        返回 DataFrame，包含 code, name, latest, pct_change, volume, turnover_amount
        """
        today = date.today().strftime("%Y-%m-%d")
        data = self._request({
            "type": 1,
            "code": "all",
            "period": "1d",
            "fq": "none",
            "startDate": today,
            "endDate": today,
        })

        if not data:
            logger.error("获取全 A 股列表失败")
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df = self._normalize_daily(df)
        df["ts"] = datetime.now()
        df["source"] = "xtick"
        logger.info(f"XTick 获取全 A 股: {len(df)} 只")
        return df

    # ---- 实时行情 ----

    def fetch_realtime_quotes(self) -> pd.DataFrame:
        """
        获取全市场日线快照（作为实时行情替代）
        XTick 日线数据包含 OHLCV，可替代盘中快照
        """
        return self.fetch_all_stocks()

    # ---- 资金流 ----
    # XTick 侧重 tick/K线数据，不提供东方财富式的资金流拆解
    # 资金流相关字段由特征层从成交额和涨跌中间接推算

    def fetch_fund_flow_rank(self) -> pd.DataFrame:
        """
        XTick 不直接提供 超大单/大单/中单/小单 净流入拆解
        返回空 DataFrame，资金流特征降级为成交额分析
        """
        logger.info("XTick 不支持资金流拆解，资金流分析降级为成交额 + 涨跌幅综合判断")
        return pd.DataFrame()

    def fetch_individual_fund_flow(self, code: str, market: str = "sh") -> Optional[pd.DataFrame]:
        """XTick 不提供个股历史资金流"""
        return None

    # ---- 板块/指数 ----

    def fetch_sector_quotes(self) -> pd.DataFrame:
        """获取指数行情（替代行业板块数据）"""
        today = date.today().strftime("%Y-%m-%d")
        data = self._request({
            "type": 10,          # 指数
            "code": "all",
            "period": "1d",
            "fq": "none",
            "startDate": today,
            "endDate": today,
        })

        if not data:
            logger.warning("获取指数行情失败")
            return pd.DataFrame()

        df = pd.DataFrame(data)
        # 统一字段名
        rename_map = {
            "code": "sector_name",
            "name": "sector_name",
            "index_code": "code",
            "index_name": "sector_name",
        }
        for old, new in rename_map.items():
            if old in df.columns:
                df = df.rename(columns={old: new})
        logger.info(f"XTick 获取指数行情: {len(df)} 条")
        return df

    # ---- 历史数据 ----

    def fetch_history(self, code: str, period: str = "1d", days: int = 250) -> Optional[pd.DataFrame]:
        """
        获取单只股票历史 K 线
        period: 1d/1w/1m
        """
        from datetime import timedelta

        end = date.today()
        start = end - timedelta(days=days * 2)  # 多取一些以覆盖非交易日

        data = self._request({
            "type": 1,
            "code": code,
            "period": period,
            "fq": "front",       # 前复权
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
        })

        if not data:
            return None

        df = pd.DataFrame(data)
        return self._normalize_daily(df)

    # ---- 标准化 ----

    @staticmethod
    def _normalize_daily(df: pd.DataFrame) -> pd.DataFrame:
        """将 XTick 日线返回字段标准化为系统内部字段

        XTick 真实 API 返回字段 (10个, 顶层 JSON 数组):
        ┌──────────┬─────────┬──────────────────────────────┐
        │ 字段      │ 类型    │ 说明                         │
        ├──────────┼─────────┼──────────────────────────────┤
        │ type     │ int     │ 1=A股, 10=指数               │
        │ code     │ str     │ 股票代码 (6位数字)            │
        │ time     │ int     │ Unix 毫秒时间戳               │
        │ open     │ float   │ 开盘价                        │
        │ close    │ float   │ 收盘价 → latest               │
        │ high     │ float   │ 最高价                        │
        │ low      │ float   │ 最低价                        │
        │ volume   │ float   │ 成交量(股)                    │
        │ amount   │ float   │ 成交额(元) → turnover_amount  │
        │ preClose │ float   │ 前收盘价 → 计算 pct_change    │
        └──────────┴─────────┴──────────────────────────────┘
        XTick 不提供: name, turnover_rate
        """
        if df.empty:
            return df

        # ---- 1. 字段重命名: XTick 真实字段 → 系统内部名 ----
        df = df.rename(columns={
            "close": "latest",
            "amount": "turnover_amount",
            "preClose": "pre_close",
        })

        # ---- 2. pct_change = (close - preClose) / preClose * 100 ----
        if "latest" in df.columns and "pre_close" in df.columns:
            pre = pd.to_numeric(df["pre_close"], errors="coerce")
            cur = pd.to_numeric(df["latest"], errors="coerce")
            df["pct_change"] = (
                (cur - pre) / pre.replace(0, float("nan")) * 100
            ).fillna(0).round(4)
        elif "latest" in df.columns and "open" in df.columns:
            opn = pd.to_numeric(df["open"], errors="coerce")
            cur = pd.to_numeric(df["latest"], errors="coerce")
            df["pct_change"] = (
                (cur - opn) / opn.replace(0, float("nan")) * 100
            ).fillna(0).round(4)
        else:
            df["pct_change"] = 0.0

        # ---- 3. 毫秒时间戳 → datetime ----
        if "time" in df.columns:
            df["ts"] = pd.to_datetime(
                pd.to_numeric(df["time"], errors="coerce"), unit="ms"
            )

        # ---- 4. 补全 XTick 不提供的字段 ----
        df["name"] = ""
        df["turnover_rate"] = 0.0
        df["source"] = "xtick"

        # ---- 5. 类型转换 ----
        for col in ["latest", "pct_change", "turnover_amount", "turnover_rate",
                     "open", "high", "low", "pre_close"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        if "volume" in df.columns:
            df["volume"] = pd.to_numeric(
                df["volume"], errors="coerce"
            ).fillna(0).astype("int64")

        if "code" in df.columns:
            df["code"] = df["code"].astype(str).str.zfill(6)

        return df

    def is_trading_time(self) -> bool:
        """简单判断是否在 A 股交易时段"""
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        morning_start = now.replace(hour=9, minute=30, second=0)
        morning_end = now.replace(hour=11, minute=30, second=0)
        afternoon_start = now.replace(hour=13, minute=0, second=0)
        afternoon_end = now.replace(hour=15, minute=0, second=0)
        return (morning_start <= now <= morning_end) or (afternoon_start <= now <= afternoon_end)


# 全局单例
fetcher = XTickFetcher()
