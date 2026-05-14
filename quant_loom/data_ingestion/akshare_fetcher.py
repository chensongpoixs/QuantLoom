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
AkShare 数据抓取模块
通过东方财富公开 API 获取 A 股行情、资金流等数据
"""

import os
import pickle
import random
import time
from datetime import datetime, date
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit, parse_qsl, urlencode, urlunsplit

import pandas as pd
from loguru import logger
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from tenacity import (
    retry as _tenacity_retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from quant_loom.ops.metrics import data_fetch_errors

# ---- urllib3 连接级重试 ----
# AkShare 单次接口（如 stock_zh_a_spot_em）内部会连续请求多页；东方财富常返回
# RemoteDisconnected。在 Session 上挂载 Retry，由 urllib3 对单次 HTTP 自动重试。
_ORIG_SESSION_INIT = requests.Session.__init__


def _session_init_with_urllib3_retry(self, *args, **kwargs):
    _ORIG_SESSION_INIT(self, *args, **kwargs)
    retry = Retry(
        total=8,
        connect=8,
        read=8,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "HEAD", "POST"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_maxsize=8, pool_connections=4)
    self.mount("https://", adapter)
    self.mount("http://", adapter)


if not getattr(requests.Session, "_quant_loom_urllib3_retry", False):
    requests.Session.__init__ = _session_init_with_urllib3_retry  # type: ignore[method-assign]
    requests.Session._quant_loom_urllib3_retry = True  # type: ignore[attr-defined]

# ---- 浏览器级请求头伪装 (避免被东方财富识别为爬虫) ----
# 注意：Connection 改为 close，避免复用已被服务端关闭的 keep-alive 连接 (RemoteDisconnected 主因)
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "close",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Referer": "https://data.eastmoney.com/",
}

# ---- HTTP 详细日志 + 单请求级透明重试 + 多 host 轮询 ----
# 关键: akshare 内部对单页失败只重试 ~3 次就放弃，导致整个分页接口崩。
# 我们在 Session.send 这层拦截每个 HTTP 请求，自动重试到成功（或上限），
# 同时对东方财富 push2 系列做客户端多 host 轮询（重试时换 host，避开单点限流）。
#
# 环境变量:
#   QL_HTTP_LOG=0              完全关闭 HTTP 日志（仅业务日志）
#   QL_HTTP_LOG_BODY=N         响应体打印长度（默认 0 不打印；设 800 可看到 JSON 摘要）
#   QL_HTTP_MAX_ATTEMPTS=N     单请求最大重试次数（默认 10）
#   QL_HTTP_BACKOFF_MAX=N      单次最长退避秒数（默认 30）
#   QL_EASTMONEY_UT=xxx        覆盖默认 ut 参数（被滥用 / 被 ban 时自己抓包替换）
#   QL_EASTMONEY_HOST_ROTATE=0 关闭 host 轮询
#   QL_HTTP_THROTTLE=0.5       东财接口访问的全局限流（秒），降低被封风险
_HTTP_LOG_ENABLED = os.getenv("QL_HTTP_LOG", "1") != "0"
_HTTP_LOG_BODY_LEN = int(os.getenv("QL_HTTP_LOG_BODY", "0"))
_HTTP_MAX_ATTEMPTS = max(1, int(os.getenv("QL_HTTP_MAX_ATTEMPTS", "10")))
_HTTP_BACKOFF_MAX = max(1.0, float(os.getenv("QL_HTTP_BACKOFF_MAX", "30")))
_QL_UT_OVERRIDE = os.getenv("QL_EASTMONEY_UT", "").strip()
_QL_HOST_ROTATE = os.getenv("QL_EASTMONEY_HOST_ROTATE", "1") != "0"
_QL_HTTP_THROTTLE = float(os.getenv("QL_HTTP_THROTTLE", "0.5"))

import threading
_THROTTLE_LOCK = threading.Lock()
_last_request_time = 0.0

# 东方财富 push2 多 host 池 (来自社区抓包 + DNS 探测)
# 业界共识: 客户端轮询多个子域名可分散单 host 限流，是替代付费代理的免费方案
_PUSH2_HOSTS = [
    "1.push2.eastmoney.com",
    "17.push2.eastmoney.com",
    "18.push2.eastmoney.com",
    "44.push2.eastmoney.com",
    "48.push2.eastmoney.com",
    "50.push2.eastmoney.com",
    "62.push2.eastmoney.com",
    "81.push2.eastmoney.com",
    "82.push2.eastmoney.com",
    "84.push2.eastmoney.com",
    "88.push2.eastmoney.com",
    "92.push2.eastmoney.com",
    "push2.eastmoney.com",
]
_PUSH2_DELAY_HOSTS = [
    "1.push2delay.eastmoney.com",
    "17.push2delay.eastmoney.com",
    "82.push2delay.eastmoney.com",
    "88.push2delay.eastmoney.com",
    "push2delay.eastmoney.com",
]

_RETRYABLE_EXC = (
    requests.ConnectionError,
    requests.Timeout,
    ConnectionResetError,
    ConnectionAbortedError,
)


def _rewrite_eastmoney_url(url: str, force_rotate: bool = False) -> str:
    """对东方财富 push2 系列做 host 轮询 + ut 覆盖

    force_rotate=True 时（重试场景）必定换 host；否则按 _QL_HOST_ROTATE 决定
    """
    try:
        sp = urlsplit(url)
    except Exception:
        return url
    host = sp.hostname or ""
    if "eastmoney.com" not in host:
        return url

    new_host = host
    if _QL_HOST_ROTATE or force_rotate:
        if "push2delay.eastmoney.com" in host:
            candidates = [h for h in _PUSH2_DELAY_HOSTS if h != host] or _PUSH2_DELAY_HOSTS
            new_host = random.choice(candidates)
        elif "push2.eastmoney.com" in host:
            candidates = [h for h in _PUSH2_HOSTS if h != host] or _PUSH2_HOSTS
            new_host = random.choice(candidates)

    new_query = sp.query
    if _QL_UT_OVERRIDE and "ut=" in sp.query:
        qs = dict(parse_qsl(sp.query, keep_blank_values=True))
        if qs.get("ut"):
            qs["ut"] = _QL_UT_OVERRIDE
            new_query = urlencode(qs)

    if new_host == host and new_query == sp.query:
        return url

    new_netloc = new_host
    if sp.port:
        new_netloc = f"{new_host}:{sp.port}"
    return urlunsplit((sp.scheme, new_netloc, sp.path, new_query, sp.fragment))

# 全局 monkey-patch: 所有 requests Session 的 send() 注入浏览器 headers + 单请求级重试 + 详细日志
_send_original = requests.Session.send


def _format_url_brief(url: str, max_len: int = 200) -> tuple[str, dict]:
    """拆出 host+path 和 query 字典，便于阅读"""
    try:
        sp = urlsplit(url)
        brief = f"{sp.scheme}://{sp.netloc}{sp.path}"
        params = dict(parse_qsl(sp.query, keep_blank_values=True))
        return brief[:max_len], params
    except Exception:
        return url[:max_len], {}


def _truncate(text: str, n: int) -> str:
    if not text or n <= 0:
        return ""
    if len(text) <= n:
        return text
    return text[:n] + f"...[truncated {len(text) - n} chars]"


def _send_with_headers(self, request, **kwargs):
    """注入浏览器伪装头 + 单请求级透明重试 + 多 host 轮询 + 详细日志 + 全局限流"""
    global _last_request_time
    
    # 针对东方财富接口做全局限流，避免并发/连续翻页太快触发服务端封禁
    if _QL_HTTP_THROTTLE > 0 and "eastmoney.com" in (request.url or ""):
        with _THROTTLE_LOCK:
            now = time.time()
            elapsed = now - _last_request_time
            if elapsed < _QL_HTTP_THROTTLE:
                time.sleep(_QL_HTTP_THROTTLE - elapsed)
            _last_request_time = time.time()

    for key, value in _BROWSER_HEADERS.items():
        request.headers.setdefault(key, value)

    # 入口先做一次 ut 覆盖（host 不轮换，保留 akshare 原始选择）
    original_url = request.url or ""
    rewritten = _rewrite_eastmoney_url(original_url, force_rotate=False)
    if rewritten != original_url:
        request.url = rewritten

    if _HTTP_LOG_ENABLED:
        brief_url, params = _format_url_brief(request.url or "")
        req_body = request.body
        if isinstance(req_body, bytes):
            try:
                req_body = req_body.decode("utf-8", errors="replace")
            except Exception:
                req_body = f"<bytes len={len(req_body)}>"
        logger.info(
            "HTTP REQ {} {} | params={} | body={}",
            request.method,
            brief_url,
            params,
            _truncate(str(req_body) if req_body else "", _HTTP_LOG_BODY_LEN) if _HTTP_LOG_BODY_LEN else "",
        )

    last_exc: Optional[BaseException] = None
    for attempt in range(1, _HTTP_MAX_ATTEMPTS + 1):
        # 每次重试都对东财 host 做强制轮换（绕开单 host 限流）
        if attempt > 1:
            new_url = _rewrite_eastmoney_url(request.url or "", force_rotate=True)
            if new_url != request.url:
                request.url = new_url
                if _HTTP_LOG_ENABLED:
                    sp = urlsplit(new_url)
                    logger.info("HTTP rotate -> {}", sp.hostname)

        t0 = time.time()
        brief_url, _ = _format_url_brief(request.url or "")
        try:
            resp = _send_original(self, request, **kwargs)
        except _RETRYABLE_EXC as e:
            elapsed = time.time() - t0
            last_exc = e
            if _HTTP_LOG_ENABLED:
                logger.warning(
                    "HTTP ERR {} {} | attempt={}/{} | elapsed={:.2f}s | exc={}: {}",
                    request.method,
                    brief_url,
                    attempt,
                    _HTTP_MAX_ATTEMPTS,
                    elapsed,
                    type(e).__name__,
                    e,
                )
            if attempt >= _HTTP_MAX_ATTEMPTS:
                raise
            # 指数退避 + jitter: 1s, 2s, 4s, 8s, 16s, 30s 封顶
            backoff = min(2 ** (attempt - 1) + random.uniform(0, 1.5), _HTTP_BACKOFF_MAX)
            time.sleep(backoff)
            continue

        if _HTTP_LOG_ENABLED:
            elapsed = time.time() - t0
            body_preview = ""
            if _HTTP_LOG_BODY_LEN > 0:
                try:
                    ct = resp.headers.get("Content-Type", "")
                    if any(k in ct for k in ("json", "text", "javascript", "xml")):
                        body_preview = _truncate(resp.text, _HTTP_LOG_BODY_LEN)
                    else:
                        body_preview = f"<binary {ct} len={len(resp.content or b'')}>"
                except Exception as e:
                    body_preview = f"<read-error: {e}>"
            attempt_tag = f"attempt={attempt} | " if attempt > 1 else ""
            logger.info(
                "HTTP RSP {} {} | {}status={} | elapsed={:.2f}s | len={} | body={}",
                request.method,
                brief_url,
                attempt_tag,
                resp.status_code,
                elapsed,
                len(resp.content or b""),
                body_preview,
            )
        return resp

    # 不可达，最后一次失败已 raise
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("HTTP retry loop exited unexpectedly")


requests.Session.send = _send_with_headers  # type: ignore[method-assign]


# ---- AkShare 业务层重试 ----
# send 级已经兜住每个 HTTP 请求；业务层只兜一次"整接口被打断"的极端情况
def _akshare_retry(func):
    return _tenacity_retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1.5, min=3, max=30),
        retry=retry_if_exception_type((
            requests.ConnectionError,
            requests.Timeout,
            requests.RequestException,
            ConnectionResetError,
            ConnectionAbortedError,
        )),
        before_sleep=before_sleep_log(logger, "WARNING"),
        reraise=True,
    )(func)


# ---- Stale 缓存目录 ----
# 业界共识: 东财限流不可避免；成功一次就持久化，失败时降级用上次的快照，让上层流程不崩
_CACHE_DIR = Path(os.getenv("QL_AKSHARE_CACHE_DIR", "logs/_akshare_cache"))
_STALE_MAX_AGE_SEC = int(os.getenv("QL_AKSHARE_STALE_MAX_AGE", "86400"))  # 默认 24h


def _save_cache(name: str, df: pd.DataFrame) -> None:
    """成功拉到数据后持久化到本地 pickle，作为下次失败时的 fallback"""
    if df is None or df.empty:
        return
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _CACHE_DIR / f"{name}.pkl"
        df.to_pickle(path)
        logger.debug(f"Cached {name} -> {path} ({len(df)} rows)")
    except Exception as e:
        logger.warning(f"Failed to save cache for {name}: {e}")


def _load_stale_cache(name: str) -> Optional[pd.DataFrame]:
    """主接口失败时，从本地 pickle 加载上次成功的快照（带陈旧度检查）"""
    path = _CACHE_DIR / f"{name}.pkl"
    if not path.exists():
        return None
    try:
        age = time.time() - path.stat().st_mtime
        if age > _STALE_MAX_AGE_SEC:
            logger.warning(
                f"Stale cache for {name} too old ({age / 3600:.1f}h > "
                f"{_STALE_MAX_AGE_SEC / 3600:.1f}h), refusing to use"
            )
            return None
        df = pd.read_pickle(path)
        logger.warning(
            f"!! Using STALE cache for {name} (age={age:.0f}s, {len(df)} rows) "
            f"-- akshare upstream failing, alerts may use slightly old data"
        )
        return df
    except Exception as e:
        logger.warning(f"Failed to load stale cache for {name}: {e}")
        return None


class AkshareFetcher:
    """AkShare / 东方财富 数据抓取器"""

    def __init__(self, rate_limit: float = 1.5):
        """rate_limit: 每次发起 AkShare 入口调用前的最小间隔（秒），略增可降低被服务端掐断概率。"""
        self.rate_limit = rate_limit
        self._last_call = 0.0

    @property
    def enabled(self) -> bool:
        return True  # AkShare 免费，无需 token

    def _throttle(self):
        elapsed = time.time() - self._last_call
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_call = time.time()

    # ---- 股票列表 + 实时行情 ----

    def fetch_all_stocks(self) -> pd.DataFrame:
        """获取全 A 股列表（含名称）"""
        try:
            import akshare as ak

            @_akshare_retry
            def _do_call():
                self._throttle()
                return ak.stock_info_a_code_name()

            df = _do_call()
            df = df.rename(columns={"code": "code", "name": "name"})
            logger.info(f"AkShare fetched full A-share list: {len(df)} stocks")
            _save_cache("stock_list", df)
            return df
        except Exception as e:
            logger.error(f"Failed to fetch stock list: {e}")
            data_fetch_errors.labels(source="akshare", endpoint="stock_list").inc()
            stale = _load_stale_cache("stock_list")
            if stale is not None:
                return stale
            return pd.DataFrame()

    def fetch_realtime_quotes(self) -> pd.DataFrame:
        """获取全市场实时行情快照（东方财富，失败时降级用本地 stale 快照）"""
        try:
            import akshare as ak
            ts = datetime.now()

            @_akshare_retry
            def _do_call():
                self._throttle()
                return ak.stock_zh_a_spot_em()

            df = _do_call()
            df = df.rename(columns={
                "代码": "code",
                "名称": "name",
                "最新价": "latest",
                "涨跌幅": "pct_change",
                "成交量": "volume",
                "成交额": "turnover_amount",
                "换手率": "turnover_rate",
            })
            df["ts"] = ts
            df["source"] = "akshare"
            logger.info(f"AkShare fetched real-time quotes: {len(df)} records")
            _save_cache("realtime_quotes", df)
            return df
        except Exception as e:
            logger.error(f"Failed to fetch real-time quotes: {e}")
            data_fetch_errors.labels(source="akshare", endpoint="quotes").inc()
            stale = _load_stale_cache("realtime_quotes")
            if stale is not None:
                stale = stale.copy()
                stale["source"] = "akshare_stale"
                return stale
            return pd.DataFrame()

    # ---- 资金流 ----

    def fetch_fund_flow_rank(self) -> pd.DataFrame:
        """获取全市场个股资金流排名（东方财富，失败时降级用本地 stale 快照）"""
        try:
            import akshare as ak
            ts = datetime.now()

            @_akshare_retry
            def _do_call():
                self._throttle()
                return ak.stock_individual_fund_flow_rank(indicator="今日")

            df = _do_call()
            df = df.rename(columns={
                "代码": "code",
                "名称": "name",
                "最新价": "latest",
                "涨跌幅": "pct_change",
                "超大单净流入": "super_large_net_inflow",
                "大单净流入": "large_net_inflow",
                "中单净流入": "medium_net_inflow",
                "小单净流入": "small_net_inflow",
                "主力净流入最大股": "main_force_stock",
            })
            df["ts"] = ts
            df["source"] = "akshare"
            logger.info(f"AkShare fetched fund flow ranking: {len(df)} records")
            _save_cache("fund_flow_rank", df)
            return df
        except Exception as e:
            logger.error(f"Failed to fetch fund flow ranking: {e}")
            data_fetch_errors.labels(source="akshare", endpoint="fund_flow").inc()
            stale = _load_stale_cache("fund_flow_rank")
            if stale is not None:
                stale = stale.copy()
                stale["source"] = "akshare_stale"
                return stale
            return pd.DataFrame()

    def fetch_individual_fund_flow(self, code: str, market: str = "sh") -> Optional[pd.DataFrame]:
        """获取单只股票历史资金流"""
        try:
            import akshare as ak

            @_akshare_retry
            def _do_call():
                self._throttle()
                return ak.stock_individual_fund_flow(stock=code, market=market)

            df = _do_call()
            logger.debug(f"Fetched individual stock fund flow: {code}")
            return df
        except Exception as e:
            logger.warning(f"Failed to fetch individual fund flow for {code}: {e}")
            return None

    # ---- 板块 ----

    def fetch_sector_quotes(self) -> pd.DataFrame:
        """获取行业板块行情（失败时降级用本地 stale 快照）"""
        try:
            import akshare as ak

            @_akshare_retry
            def _do_call():
                self._throttle()
                return ak.stock_board_industry_name_em()

            df = _do_call()
            df = df.rename(columns={
                "板块名称": "sector_name",
                "涨跌幅": "pct_change",
                "主力净流入": "main_net_inflow",
            })
            logger.info(f"AkShare fetched sector quotes: {len(df)} records")
            _save_cache("sector_quotes", df)
            return df
        except Exception as e:
            logger.error(f"Failed to fetch sector quotes: {e}")
            data_fetch_errors.labels(source="akshare", endpoint="sectors").inc()
            stale = _load_stale_cache("sector_quotes")
            if stale is not None:
                return stale
            return pd.DataFrame()

    # ---- 历史数据 ----

    def fetch_history(self, code: str, period: str = "1d", days: int = 250) -> Optional[pd.DataFrame]:
        """获取单只股票历史 K 线"""
        try:
            import akshare as ak

            @_akshare_retry
            def _do_call():
                self._throttle()
                return ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")

            df = _do_call()
            if df is not None and not df.empty:
                df = df.tail(days)
            return df
        except Exception as e:
            logger.warning(f"Failed to fetch historical K-line for {code}: {e}")
            return None

    def is_trading_time(self) -> bool:
        """简单判断是否在 A 股交易时段"""
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        mt = now.replace(hour=9, minute=30, second=0)
        me = now.replace(hour=11, minute=30, second=0)
        at = now.replace(hour=13, minute=0, second=0)
        ae = now.replace(hour=15, minute=0, second=0)
        return (mt <= now <= me) or (at <= now <= ae)
