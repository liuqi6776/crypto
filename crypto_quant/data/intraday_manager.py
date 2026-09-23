# -*- coding: utf-8 -*-
"""
Intraday Market Data Manager & Local Parquet Cache
日内高频行情数据管理与 Parquet 本地极速缓存
=================================================
Manages 15m and 5m candlestick data for Spot and USDS-M Perpetual Futures:
- Concurrent paginated downloading from Binance public API.
- Local incremental parquet caching in data/intraday/.
- Data admission validation (monotonic index, no duplicates, interval regularity, OHLC sanity).
- Fast loading and cross-asset alignment for backtesting and live tracking.
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd

from crypto_quant.data_fetcher import fetch_klines

CORE4_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
DEFAULT_INTRADAY_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "intraday")


def validate_intraday_dataframe(df: pd.DataFrame, interval: str) -> Dict[str, Any]:
    """
    Validate data admission criteria for intraday candlestick series.
    日内高频 K 线数据准入合规检验。
    """
    report = {
        "is_valid": True,
        "rows": len(df),
        "start_time": str(df.index[0]) if not df.empty else None,
        "end_time": str(df.index[-1]) if not df.empty else None,
        "duplicate_indices": int(df.index.duplicated().sum()),
        "is_monotonic_increasing": bool(df.index.is_monotonic_increasing),
        "ohlc_violations": 0,
        "negative_volume": 0,
        "missing_bars": 0,
    }

    if df.empty:
        report["is_valid"] = False
        return report

    # 1. Duplicates and Monotonicity
    if report["duplicate_indices"] > 0 or not report["is_monotonic_increasing"]:
        report["is_valid"] = False

    # 2. OHLC Logic: High >= max(Open, Close) and Low <= min(Open, Close)
    max_oc = np.maximum(df["open"].values, df["close"].values)
    min_oc = np.minimum(df["open"].values, df["close"].values)
    high_viol = (df["high"].values < max_oc - 1e-6).sum()
    low_viol = (df["low"].values > min_oc + 1e-6).sum()
    report["ohlc_violations"] = int(high_viol + low_viol)
    if report["ohlc_violations"] > 0:
        report["is_valid"] = False

    # 3. Non-negative volume
    neg_vol = (df["volume"].values < 0).sum()
    report["negative_volume"] = int(neg_vol)
    if neg_vol > 0:
        report["is_valid"] = False

    # 4. Expected bar frequency gap check
    freq_map = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}
    step_minutes = freq_map.get(interval, 15)
    expected_delta = pd.Timedelta(minutes=step_minutes)

    diffs = df.index.to_series().diff().dropna()
    gaps = diffs[diffs > expected_delta]
    missing_count = sum((gap / expected_delta) - 1 for gap in gaps)
    report["missing_bars"] = int(missing_count)

    return report


def fetch_range_klines(
    symbol: str,
    interval: str,
    start_dt: pd.Timestamp,
    end_dt: pd.Timestamp,
    market_type: str = "spot",
    max_retries: int = 5,
) -> pd.DataFrame:
    """
    Fetch paginated historical K-lines in [start_dt, end_dt) forward chronologically.
    正向分页抓取指定时间范围的 K 线数据。
    """
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    curr_start_ms = start_ms
    all_dfs = []

    # Frequency duration in ms
    freq_map_ms = {
        "1m": 60_000,
        "5m": 300_000,
        "15m": 900_000,
        "1h": 3_600_000,
        "4h": 14_400_000,
        "1d": 86_400_000,
    }
    bar_ms = freq_map_ms.get(interval, 900_000)

    while curr_start_ms < end_ms:
        batch_df = None
        for attempt in range(max_retries):
            try:
                batch_df = fetch_klines(
                    symbol=symbol,
                    interval=interval,
                    limit=1000,
                    start_time=curr_start_ms,
                    end_time=end_ms,
                    market_type=market_type,
                )
                break
            except Exception as e:
                time.sleep(1.0 * (attempt + 1))

        if batch_df is None or batch_df.empty:
            break

        all_dfs.append(batch_df)
        last_open_time = batch_df.index[-1]
        last_ms = int(last_open_time.timestamp() * 1000)

        # Advance start time to next candle
        next_start_ms = last_ms + bar_ms
        if next_start_ms <= curr_start_ms:
            break
        curr_start_ms = next_start_ms

        if len(batch_df) < 1000:
            # Reached current available live boundary
            break

        # Polite throttling to respect Binance weight limits
        time.sleep(0.05)

    if not all_dfs:
        return pd.DataFrame()

    full_df = pd.concat(all_dfs)
    full_df = full_df[~full_df.index.duplicated(keep="first")]
    full_df.sort_index(inplace=True)
    return full_df


def sync_intraday_symbol(
    symbol: str,
    interval: str = "15m",
    market_type: str = "spot",
    start_date: str = "2023-01-01",
    end_date: Optional[str] = None,
    cache_dir: str = DEFAULT_INTRADAY_DIR,
) -> pd.DataFrame:
    """
    Synchronize intraday parquet cache for a single symbol.
    同步单个标的的日内 Parquet 缓存（支持断点续传）。
    """
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"{symbol.upper()}_{interval}_{market_type.lower()}.parquet")

    start_dt = pd.to_datetime(start_date, utc=True)
    end_dt = pd.to_datetime(end_date, utc=True) if end_date else pd.Timestamp.now(timezone.utc)

    existing_df = None
    if os.path.exists(cache_path):
        try:
            existing_df = pd.read_parquet(cache_path)
            if not existing_df.empty:
                if existing_df.index.tz is None:
                    existing_df.index = existing_df.index.tz_localize("UTC")
                else:
                    existing_df.index = existing_df.index.tz_convert("UTC")
                
                earliest_saved = existing_df.index[0]
                latest_saved = existing_df.index[-1]
                chunks = [existing_df]

                # Backward fetch if requested earlier data
                if start_dt < earliest_saved - pd.Timedelta(minutes=30):
                    fetch_end = earliest_saved - pd.Timedelta(seconds=1)
                    print(f"[DOWNLOAD BACKWARD] Fetching {symbol} {interval} ({market_type}) {start_dt.strftime('%Y-%m-%d')} -> {fetch_end.strftime('%Y-%m-%d')}...")
                    past_df = fetch_range_klines(symbol, interval, start_dt, fetch_end, market_type)
                    if not past_df.empty:
                        if past_df.index.tz is None:
                            past_df.index = past_df.index.tz_localize("UTC")
                        else:
                            past_df.index = past_df.index.tz_convert("UTC")
                        chunks.insert(0, past_df)

                # Forward fetch if newer data exists
                if latest_saved < end_dt - pd.Timedelta(minutes=30):
                    fetch_start = latest_saved + pd.Timedelta(seconds=1)
                    inc_df = fetch_range_klines(symbol, interval, fetch_start, end_dt, market_type)
                    if not inc_df.empty:
                        if inc_df.index.tz is None:
                            inc_df.index = inc_df.index.tz_localize("UTC")
                        else:
                            inc_df.index = inc_df.index.tz_convert("UTC")
                        chunks.append(inc_df)

                if len(chunks) > 1:
                    merged = pd.concat(chunks)
                    merged = merged[~merged.index.duplicated(keep="last")]
                    merged.sort_index(inplace=True)
                    merged.to_parquet(cache_path)
                    return merged
                return existing_df
        except Exception as e:
            print(f"[WARN] Error reading cache {cache_path}: {e}, re-fetching...")

    # Fetch full range
    print(f"[DOWNLOAD] Fetching {symbol} {interval} ({market_type}) from {start_dt.strftime('%Y-%m-%d')}...")
    full_df = fetch_range_klines(symbol, interval, start_dt, end_dt, market_type)
    if not full_df.empty:
        if full_df.index.tz is None:
            full_df.index = full_df.index.tz_localize("UTC")
        else:
            full_df.index = full_df.index.tz_convert("UTC")
        full_df.to_parquet(cache_path)
        print(f"[SAVED] {symbol} {interval} ({market_type}): {len(full_df)} bars saved to {cache_path}")
    return full_df


def load_intraday_symbol(
    symbol: str,
    interval: str = "15m",
    market_type: str = "spot",
    start_dt: Optional[pd.Timestamp] = None,
    end_dt: Optional[pd.Timestamp] = None,
    cache_dir: str = DEFAULT_INTRADAY_DIR,
) -> pd.DataFrame:
    """Load cached intraday data sliced to [start_dt, end_dt)."""
    cache_path = os.path.join(cache_dir, f"{symbol.upper()}_{interval}_{market_type.lower()}.parquet")
    if not os.path.exists(cache_path):
        raise FileNotFoundError(f"Intraday cache not found: {cache_path}. Run sync first.")

    df = pd.read_parquet(cache_path)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")

    if start_dt is not None:
        if start_dt.tzinfo is None:
            start_dt = start_dt.tz_localize("UTC")
        df = df[df.index >= start_dt]
    if end_dt is not None:
        if end_dt.tzinfo is None:
            end_dt = end_dt.tz_localize("UTC")
        df = df[df.index < end_dt]

    return df
