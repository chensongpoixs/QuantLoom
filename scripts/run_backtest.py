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

#!/usr/bin/env python3
"""
QuantLoom·量梭 回测引擎
从历史 K 线重建日频快照，逐日运行规则扫描，计算后续表现指标

用法:
  python scripts/run_backtest.py --start 2024-01-01 --end 2024-06-30
  python scripts/run_backtest.py --date 2024-06-15
  python scripts/run_backtest.py --start 2024-01-01 --end 2024-06-30 --codes 000001,600519
  python scripts/run_backtest.py --start 2024-01-01 --end 2024-06-30 --dry-run
"""

import argparse
import hashlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple

import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings
from quant_loom.rule_engine.scanner import scanner
from quant_loom.storage.mysql_client import mysql_client
from quant_loom.storage.models import BacktestResult, FundFlowDaily


def parse_args():
    p = argparse.ArgumentParser(description="QuantLoom·量梭 回测引擎")
    p.add_argument("--start", type=str, help="起始日期 YYYY-MM-DD")
    p.add_argument("--end", type=str, help="结束日期 YYYY-MM-DD")
    p.add_argument("--date", type=str, help="单日回测 YYYY-MM-DD")
    p.add_argument("--codes", type=str, help="限定股票代码 (逗号分隔)")
    p.add_argument("--dry-run", action="store_true", help="仅扫描不写库")
    return p.parse_args()


def compute_params_hash() -> str:
    """对当前 rules.yaml 做 MD5 哈希，用于回测缓存键"""
    rules_path = Path(__file__).resolve().parent.parent / "config" / "rules.yaml"
    with open(rules_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def fetch_kline_data(codes: List[str]) -> pd.DataFrame:
    """
    获取全市场历史 K 线 (前复权)，每只股票获取最近 500 个交易日
    返回 DataFrame: 日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 涨跌幅, code
    """
    from quant_loom.data_ingestion.akshare_fetcher import AkshareFetcher

    logger.info(f"Fetching historical K-line data for {len(codes)} stocks...")

    fetcher = AkshareFetcher()
    all_frames = []

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(_fetch_single_kline, fetcher, code): code
            for code in codes
        }
        done = 0
        for future in as_completed(futures):
            code = futures[future]
            done += 1
            try:
                df = future.result(timeout=120)
                if df is not None and not df.empty:
                    all_frames.append(df)
            except Exception as e:
                logger.debug(f"K-line fetch failed for {code}: {e}")
            if done % 100 == 0:
                logger.info(f"  K-line progress: {done}/{len(codes)}")

    if not all_frames:
        return pd.DataFrame()

    result = pd.concat(all_frames, ignore_index=True)
    # 标准化列名: AkShare 中文列名 → 英文
    result = _normalize_kline_columns(result)
    result["date"] = pd.to_datetime(result["date"])
    logger.info(f"K-line fetch complete: {len(result)} rows, {result['code'].nunique()} stocks")
    return result


def _normalize_kline_columns(df: pd.DataFrame) -> pd.DataFrame:
    """将 AkShare stock_zh_a_hist 中文列名标准化为英文"""
    col_map = {
        "日期": "date", "开盘": "open", "收盘": "close", "最高": "high",
        "最低": "low", "成交量": "volume", "成交额": "turnover_amount",
        "涨跌幅": "pct_change", "换手率": "turnover_rate", "振幅": "amplitude",
        "涨跌额": "change_amount",
    }
    for old, new in col_map.items():
        if old in df.columns:
            df[new] = df[old]
    return df


def _fetch_single_kline(fetcher, code: str) -> Optional[pd.DataFrame]:
    """获取单只股票历史 K 线 (近 500 天)"""
    try:
        df = fetcher.fetch_history(code, period="1d", days=500)
        if df is not None and not df.empty:
            df["code"] = str(code).zfill(6)
            return df
    except Exception as e:
        logger.debug(f"K-line fetch failed for {code}: {e}")
    return None


def compute_near_250d_low_map(kline_df: pd.DataFrame, t_date: date) -> Dict[str, bool]:
    """
    计算每只股票在 t_date 是否接近 250 日最低价
    使用 t_date 之前的 250 个日历日数据 (从 kline_df 中过滤)
    """
    result = {}
    if kline_df.empty:
        return result

    kline = kline_df.copy()
    if "date" not in kline.columns:
        return result

    # 250 个日历日前
    lookback_start = t_date - timedelta(days=250)

    for code in kline["code"].unique():
        code_df = kline[(kline["code"] == code) & (kline["date"] < pd.Timestamp(t_date))].copy()
        if len(code_df) < 20:  # 最少需要 20 个交易日
            result[code] = False
            continue

        code_df = code_df[code_df["date"] >= pd.Timestamp(lookback_start)]
        if code_df.empty:
            result[code] = False
            continue

        low_250 = code_df["low"].min()
        current_close = code_df[code_df["date"] == code_df["date"].max()]["close"]
        if current_close.empty:
            result[code] = False
            continue

        current_price = float(current_close.iloc[0])
        near_low = (current_price - low_250) / low_250 < 0.15  # 15% within 250-day low
        result[code] = near_low

    return result


def build_snapshot(kline_df: pd.DataFrame, t_date: date) -> pd.DataFrame:
    """
    从历史 K 线重建当日行情快照 DataFrame
    每行: code, name, latest(=close), pct_change, high, low, open,
          turnover_amount, volume, volume_ratio, turnover_rate
    """
    if kline_df.empty:
        return pd.DataFrame()

    kline = kline_df.copy()
    if "date" not in kline.columns:
        return pd.DataFrame()

    kline["date"] = pd.to_datetime(kline["date"])
    day_data = kline[kline["date"] == pd.Timestamp(t_date)].copy()

    if day_data.empty:
        return pd.DataFrame()

    # 确保关键列存在
    day_data["latest"] = day_data["close"]
    if "pct_change" not in day_data.columns:
        day_data["pct_change"] = 0.0

    # 量比 = 当日成交量 / 近 5 日均量
    if "volume" in day_data.columns:
        day_data["volume_ratio"] = 1.0
        for code in day_data["code"].unique():
            code_df = kline[(kline["code"] == code) & (kline["date"] < pd.Timestamp(t_date))]
            if len(code_df) >= 5:
                avg_vol = float(code_df.sort_values("date").tail(5)["volume"].mean())
                cur_vol = float(day_data[day_data["code"] == code]["volume"].iloc[0])
                if avg_vol > 0:
                    day_data.loc[day_data["code"] == code, "volume_ratio"] = cur_vol / avg_vol

    # 填充缺失列
    if "turnover_amount" not in day_data.columns:
        day_data["turnover_amount"] = 0.0
    for col in ["name", "high", "low", "open", "turnover_rate", "industry"]:
        if col not in day_data.columns:
            day_data[col] = ""
        day_data[col] = day_data[col].fillna("")

    return day_data


def build_fund_flow_snapshot(t_date: date, codes: List[str]) -> pd.DataFrame:
    """从 sq_fund_flow_daily 重建当日资金流快照"""
    if not mysql_client.ping():
        logger.warning("MySQL unavailable, using empty fund flow")
        return pd.DataFrame()

    try:
        with mysql_client.get_session() as sess:
            rows = (
                sess.query(FundFlowDaily)
                .filter(FundFlowDaily.trade_date == t_date)
                .all()
            )
            if not rows:
                return pd.DataFrame()

            data = []
            for r in rows:
                data.append({
                    "code": r.code,
                    "main_force_ratio": float(r.main_force_ratio or 0),
                    "net_inflow": float(r.net_inflow or 0),
                    "super_large_net_inflow": float(r.super_large_net_inflow or 0),
                    "large_net_inflow": float(r.large_net_inflow or 0),
                    "medium_net_inflow": float(r.medium_net_inflow or 0),
                    "small_net_inflow": float(r.small_net_inflow or 0),
                })
            return pd.DataFrame(data)
    except Exception as e:
        logger.warning(f"Fund flow query failed {t_date}: {e}")
        return pd.DataFrame()


def compute_outcomes(kline_df: pd.DataFrame, code: str, t_date: date,
                     pct_alert: float) -> Tuple[Optional[float], Optional[float],
                                                Optional[float], Optional[bool]]:
    """
    计算异动标的的后续表现
    Returns: (outcome_1d, outcome_3d, outcome_5d, outcome_positive)
    """
    if kline_df.empty:
        return None, None, None, None

    kline = kline_df.copy()
    if "date" not in kline.columns:
        return None, None, None, None
    kline["date"] = pd.to_datetime(kline["date"])

    code_df = kline[(kline["code"] == code) & (kline["date"] > pd.Timestamp(t_date))]
    if code_df.empty:
        return None, None, None, None

    code_df = code_df.sort_values("date")
    close_alert = code_df.iloc[0]["close"] if not code_df.empty else 0

    def _forward_return(n_days: int):
        future = code_df.head(n_days)
        if len(future) < n_days:
            return None
        close_future = float(future.iloc[-1]["close"])
        if close_alert and close_alert > 0:
            return (close_future - close_alert) / close_alert * 100
        return None

    o1d = _forward_return(1)
    o3d = _forward_return(3)
    o5d = _forward_return(5)
    # 方向正确: 异动日涨 + 后续涨 或 异动日跌 + 后续涨(反弹)
    o_pos = None
    if o3d is not None:
        o_pos = o3d > 0  # positive = 后续 N 日有正收益

    return o1d, o3d, o5d, o_pos


def run_backtest_day(kline_df: pd.DataFrame, t_date: date, params_hash: str,
                     dry_run: bool, codes_filter: Optional[List[str]] = None):
    """执行单日回测"""
    logger.info(f"--- Backtest {t_date} ---")
    t0 = time.time()

    # 1. 重建行情快照
    snapshot = build_snapshot(kline_df, t_date)
    if snapshot.empty:
        logger.info(f"  {t_date} no market data, skipping")
        return 0

    # 2. 重建资金流
    fund_flow = build_fund_flow_snapshot(t_date, list(snapshot["code"].unique()))

    # 3. 计算真实 near_250d_low
    near_low_map = compute_near_250d_low_map(kline_df, t_date)

    # 4. 过滤股票代码
    if codes_filter:
        snapshot = snapshot[snapshot["code"].isin(codes_filter)]

    # 5. 计算连续流入天数 (需要历史资金流数据)
    consecutive_map = _compute_hist_consecutive_inflow(t_date, list(snapshot["code"].unique()))

    # 6. 规则扫描 (回测模式: 跳过事件驱动)
    alerts = scanner.scan_and_format(
        snapshot, fund_flow,
        backtest_date=t_date,
        backtest_mode=True,
        near_250d_low_map=near_low_map,
        consecutive_inflow_map=consecutive_map,
    )

    logger.info(f"  {t_date}: {len(alerts)} anomaly signals (backtest mode)")

    # 7. 计算 outcome + 入库
    saved = 0
    for alert in alerts:
        code = alert["code"]
        o1d, o3d, o5d, o_pos = compute_outcomes(
            kline_df, code, t_date, alert.get("pct_change", 0)
        )

        if not dry_run and mysql_client.ping():
            try:
                record = BacktestResult(
                    trade_date=t_date,
                    code=code,
                    name=alert.get("name", ""),
                    alert_type=alert.get("alert_type", ""),
                    trigger_reason=alert.get("trigger_reason", ""),
                    confidence_score=alert.get("confidence_score", 0),
                    pct_change_alert=alert.get("pct_change", 0),
                    main_force_ratio=alert.get("main_force_ratio", 0),
                    outcome_1d=o1d,
                    outcome_3d=o3d,
                    outcome_5d=o5d,
                    outcome_positive=o_pos,
                    params_hash=params_hash,
                )
                mysql_client.insert_or_update(record)
                saved += 1
            except Exception as e:
                logger.warning(f"Failed to save backtest result for {code}: {e}")

    elapsed = time.time() - t0
    logger.info(f"  {t_date} done: {saved} saved, elapsed {elapsed:.1f}s")
    return saved


def _compute_hist_consecutive_inflow(t_date: date, codes: List[str]) -> Dict[str, int]:
    """
    回测模式下的连续净流入天数计算 (排除 t_date 及以后数据 — 前瞻偏差)
    """
    from quant_loom.feature_engineering.fund_flow import FundFlowFeatures

    result = {}
    if not codes or not mysql_client.ping():
        return result

    try:
        with mysql_client.get_session() as sess:
            from sqlalchemy import desc
            for code in codes:
                rows = (
                    sess.query(FundFlowDaily.net_inflow)
                    .filter(
                        FundFlowDaily.code == code,
                        FundFlowDaily.trade_date < t_date,
                    )
                    .order_by(desc(FundFlowDaily.trade_date))
                    .limit(30)
                    .all()
                )
                inflows = [float(r.net_inflow or 0) for r in rows]
                days = FundFlowFeatures.compute_consecutive_days(inflows)
                if days > 0:
                    result[code] = days
    except Exception as e:
        logger.warning(f"Historical fund flow query failed {t_date}: {e}")

    return result


def get_trading_dates(start: date, end: date) -> List[date]:
    """生成日期范围内的交易日列表 (简单实现: 排除周六日，不精确但够用)"""
    import calendar

    dates = []
    current = start
    while current <= end:
        if current.weekday() < 5:  # Mon-Fri
            dates.append(current)
        current += timedelta(days=1)
    return dates


def get_all_codes(kline_df: pd.DataFrame, codes_filter: Optional[List[str]] = None) -> List[str]:
    """获取全部可用股票代码"""
    if codes_filter:
        return codes_filter
    if kline_df.empty:
        return []
    return sorted(kline_df["code"].unique().tolist())


def main():
    args = parse_args()
    params_hash = compute_params_hash()

    # 确定回测日期范围
    if args.date:
        start = end = date.fromisoformat(args.date)
    elif args.start and args.end:
        start = date.fromisoformat(args.start)
        end = date.fromisoformat(args.end)
    else:
        # 默认: 最近 30 个交易日
        end = date.today()
        start = end - timedelta(days=60)
        logger.info(f"Date range not specified, using last 60 days: {start} ~ {end}")

    trading_dates = get_trading_dates(start, end)
    logger.info(f"Backtest range: {start} ~ {end}, {len(trading_dates)} trading days total")

    codes_filter = None
    if args.codes:
        codes_filter = [c.strip() for c in args.codes.split(",")]

    # 预取 K 线数据 (每只股票近 500 天，含 lookback 用于 near_low 计算)
    all_codes = codes_filter or _get_default_codes()
    kline_df = fetch_kline_data(all_codes)

    if kline_df.empty:
        logger.error("Unable to fetch historical K-line data")
        return

    total_saved = 0
    for i, t_date in enumerate(trading_dates):
        try:
            saved = run_backtest_day(kline_df, t_date, params_hash, args.dry_run, codes_filter)
            total_saved += saved
        except Exception as e:
            logger.error(f"Backtest {t_date} exception: {e}")

        # 控制 API 速率
        if i < len(trading_dates) - 1:
            time.sleep(0.5)

    logger.info(f"Backtest complete: {total_saved} results total")
    print(f"\nBacktest complete: {len(trading_dates)} trading days, {total_saved} results")


def _get_default_codes() -> List[str]:
    """获取默认股票代码列表 (从 AkShare)"""
    try:
        from quant_loom.data_ingestion.akshare_fetcher import AkshareFetcher
        fetcher = AkshareFetcher()
        quotes = fetcher.fetch_realtime_quotes()
        if not quotes.empty and "code" in quotes.columns:
            return sorted(quotes["code"].astype(str).str.zfill(6).unique().tolist())
    except Exception:
        pass

    # 回退: 沪深 300 成分股 (少量代表性股票)
    logger.warning("Unable to fetch full market codes, using first 50 of CSI 300")
    return [
        "000001", "000002", "000063", "000100", "000333", "000338", "000425",
        "000568", "000625", "000651", "000725", "000768", "000776", "000858",
        "000876", "002007", "002142", "002230", "002352", "002415", "002475",
        "002594", "300015", "300059", "300124", "300274", "300433", "300498",
        "300750", "600000", "600009", "600016", "600028", "600030", "600031",
        "600036", "600048", "600050", "600085", "600104", "600111", "600196",
        "600276", "600309", "600436", "600519", "600585", "600690", "600809",
        "600887",
    ]


if __name__ == "__main__":
    main()
