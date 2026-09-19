"""
High-Speed Binance Vision Historical Archive Downloader (2017/2020 - 2026)
币安官方高频历史归档高速下载与合并引擎（2017/2020 - 2026）

Downloads complete monthly archives of 1m and 5m klines from data.binance.vision
for BTCUSDT, ETHUSDT, and SOLUSDT (both Futures and Spot), and merges them into
continuous multi-year Parquet datasets for quant backtesting and factor research.
"""

import os
import io
import time
import zipfile
import argparse
import datetime
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import numpy as np
from typing import List, Tuple, Optional

DEFAULT_PROXY = "http://127.0.0.1:7897"

STANDARD_COLUMNS = [
    'timestamp', 'open', 'high', 'low', 'close', 'volume',
    'close_time', 'quote_volume', 'trades_count',
    'taker_buy_volume', 'taker_buy_quote_volume', 'ignore'
]

def make_opener(proxy_url: Optional[str] = DEFAULT_PROXY) -> urllib.request.OpenerDirector:
    if proxy_url:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url})
        )
    return urllib.request.build_opener()

def download_and_parse_month(
    opener: urllib.request.OpenerDirector,
    url: str,
    out_parquet: str
) -> Optional[pd.DataFrame]:
    """
    Download a monthly zip archive, extract the CSV, clean & type columns, and save as Parquet.
    """
    if os.path.exists(out_parquet):
        try:
            df = pd.read_parquet(out_parquet)
            if not df.empty:
                return df
        except Exception:
            pass

    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    )
    try:
        with opener.open(req, timeout=15) as resp:
            content = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except Exception as e:
        # Retry once
        time.sleep(1.0)
        try:
            with opener.open(req, timeout=20) as resp:
                content = resp.read()
        except Exception:
            return None

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            csv_name = z.namelist()[0]
            with z.open(csv_name) as f:
                df = pd.read_csv(f, header=None, low_memory=False)

        # Header detection
        if str(df.iloc[0, 0]).startswith('open'):
            df = df.iloc[1:].reset_index(drop=True)

        cols = STANDARD_COLUMNS[:df.shape[1]]
        df.columns = cols

        # Clean types
        df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce')
        df = df.dropna(subset=['timestamp'])
        df['timestamp'] = df['timestamp'].astype(np.int64)

        # Microsecond normalization (if >= 1e14, convert us to ms)
        mask_us = df['timestamp'] > 100_000_000_000_000
        if mask_us.any():
            df.loc[mask_us, 'timestamp'] = df.loc[mask_us, 'timestamp'] // 1000

        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert('Asia/Shanghai').dt.strftime('%Y-%m-%d %H:%M:%S')

        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'quote_volume', 'taker_buy_volume', 'taker_buy_quote_volume']
        for c in numeric_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce')

        if 'trades_count' in df.columns:
            df['trades_count'] = pd.to_numeric(df['trades_count'], errors='coerce').fillna(0).astype(np.int64)

        keep_cols = ['timestamp', 'datetime', 'open', 'high', 'low', 'close', 'volume', 'quote_volume', 'trades_count', 'taker_buy_volume', 'taker_buy_quote_volume']
        keep_cols = [c for c in keep_cols if c in df.columns]
        df = df[keep_cols].sort_values('timestamp').reset_index(drop=True)

        os.makedirs(os.path.dirname(out_parquet), exist_ok=True)
        df.to_parquet(out_parquet, index=False)
        return df

    except Exception as e:
        print(f"Error parsing {url}: {e}")
        return None


def sync_symbol_history(
    market: str, # 'futures' or 'spot'
    symbol: str,
    interval: str,
    start_year: int,
    end_year: int,
    output_base_dir: str,
    proxy: str,
    max_workers: int = 6
) -> str:
    """
    Sync all months for a symbol, then merge into a consolidated continuous Parquet file.
    """
    opener = make_opener(proxy)
    market_path = 'futures/um' if market == 'futures' else 'spot'
    folder_name = f"{market}_{interval}"
    save_dir = os.path.join(output_base_dir, folder_name, symbol)
    os.makedirs(save_dir, exist_ok=True)

    # Generate all candidate month tasks
    tasks = []
    current_time = datetime.datetime.now()
    for y in range(start_year, end_year + 1):
        for m in range(1, 13):
            # Do not query future months
            if y > current_time.year or (y == current_time.year and m > current_time.month):
                continue
            month_str = f"{y}-{m:02d}"
            url = f"https://data.binance.vision/data/{market_path}/monthly/klines/{symbol}/{interval}/{symbol}-{interval}-{month_str}.zip"
            out_file = os.path.join(save_dir, f"{symbol}_{interval}_{month_str}.parquet")
            tasks.append((month_str, url, out_file))

    print(f"\n>>> [{market.upper()} | {symbol} | {interval}] Starting download for {len(tasks)} months ({tasks[0][0]} to {tasks[-1][0]})...")

    downloaded_dfs = []
    success_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(download_and_parse_month, opener, url, out_file): (m_str, out_file)
            for m_str, url, out_file in tasks
        }
        for future in as_completed(future_map):
            m_str, out_file = future_map[future]
            try:
                df = future.result()
                if df is not None and not df.empty:
                    success_count += 1
            except Exception as e:
                print(f"  [Fail] {m_str}: {e}")

    # Now load and concatenate all available months in chronological order
    all_parquet_files = sorted([
        os.path.join(save_dir, f) for f in os.listdir(save_dir)
        if f.endswith('.parquet') and not f.endswith('_continuous.parquet')
    ])

    if not all_parquet_files:
        print(f"  No data found for {symbol} {interval}")
        return ""

    dfs = []
    for f in all_parquet_files:
        try:
            dfs.append(pd.read_parquet(f))
        except Exception:
            pass

    if dfs:
        continuous_df = pd.concat(dfs, ignore_index=True)
        continuous_df = continuous_df.drop_duplicates(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)

        consolidated_filename = f"{symbol}_{market}_{interval}_continuous.parquet"
        consolidated_path = os.path.join(output_base_dir, folder_name, consolidated_filename)
        continuous_df.to_parquet(consolidated_path, index=False)

        start_dt = continuous_df['datetime'].iloc[0]
        end_dt = continuous_df['datetime'].iloc[-1]
        print(f"  [CONSOLIDATED] {consolidated_filename}")
        print(f"    Total Bars: {len(continuous_df):,} | Range: {start_dt} -> {end_dt}")
        print(f"    Saved -> {consolidated_path}")
        return consolidated_path

    return ""


def run_full_historical_sync(output_dir: str, proxy: str, intervals: List[str] = ['5m', '1m']):
    print("=================================================================")
    print("  Binance Vision High-Speed Historical Ingestion Engine")
    print(f"  Destination: {output_dir}")
    print(f"  Proxy: {proxy}")
    print("=================================================================")

    # 1. Futures (USDT-M): BTC (2020+), ETH (2020+), SOL (2020+)
    futures_symbols = [
        ('BTCUSDT', 2020),
        ('ETHUSDT', 2020),
        ('SOLUSDT', 2020),
    ]

    for interval in intervals:
        for symbol, start_y in futures_symbols:
            sync_symbol_history(
                market='futures',
                symbol=symbol,
                interval=interval,
                start_year=start_y,
                end_year=2026,
                output_base_dir=output_dir,
                proxy=proxy,
                max_workers=8
            )

    # 2. Spot (extended history from 2017): BTC, ETH
    spot_symbols = [
        ('BTCUSDT', 2017),
        ('ETHUSDT', 2017),
    ]

    # For spot, sync 5m first to provide quick macro long-term baseline
    for interval in ['5m']:
        for symbol, start_y in spot_symbols:
            sync_symbol_history(
                market='spot',
                symbol=symbol,
                interval=interval,
                start_year=start_y,
                end_year=2026,
                output_base_dir=output_dir,
                proxy=proxy,
                max_workers=8
            )

    print("\n[ALL COMPLETE] Full multi-year historical ingestion and continuous dataset consolidation finished!")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Download Binance Vision Historical Datasets")
    parser.add_argument('--output-dir', type=str, default=r"d:\Convertible_Bond_data\crypto_data\history")
    parser.add_argument('--proxy', type=str, default=DEFAULT_PROXY)
    parser.add_argument('--intervals', nargs='+', default=['5m', '1m'])
    args = parser.parse_args()

    run_full_historical_sync(args.output_dir, args.proxy, args.intervals)
