# -*- coding: utf-8 -*-
"""
Multi-Asset 1-Second (1s) High-Speed Parallel Synchronizer
四大资产 (BTC, ETH, SOL, BNB) 1秒高频历史数据极速并行同步引擎
- Downloads 1s monthly archives from Binance Vision using thread pool
- Converts in-memory to compressed Parquet with microsecond timestamp parsing
- Merges into continuous 1s time-series for high-frequency quantitative research
"""

import os
import sys
import io
import time
import zipfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import numpy as np

DATA_DIR = r"D:\Convertible_Bond_data\crypto_data\history\1s"
SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT']
MONTHS_DEFAULT = ['2026-07', '2026-08']


def download_and_convert_month(symbol: str, month: str, save_dir: str = DATA_DIR) -> str:
    """
    Downloads and converts 1 month of 1-second K-lines (~2.6M rows, ~50MB compressed)
    """
    sym_dir = os.path.join(save_dir, symbol)
    os.makedirs(sym_dir, exist_ok=True)
    out_parquet = os.path.join(sym_dir, f"{symbol}_1s_{month}.parquet")

    if os.path.exists(out_parquet) and os.path.getsize(out_parquet) > 10 * 1024 * 1024:
        print(f"[{symbol} {month}] Already cached -> {out_parquet} ({os.path.getsize(out_parquet)/(1024*1024):.1f} MB)")
        return out_parquet

    url = f"https://data.binance.vision/data/spot/monthly/klines/{symbol}/1s/{symbol}-1s-{month}.zip"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    req = urllib.request.Request(url, headers=headers)

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            zip_bytes = resp.read()
    except Exception as e:
        print(f"[{symbol} {month}] Download failed ({url}): {e}")
        return ""

    dl_time = time.time() - t0
    dl_mb = len(zip_bytes) / (1024 * 1024)

    # In-memory unzip and parse
    t1 = time.time()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        fname = z.namelist()[0]
        with z.open(fname) as f:
            cols = ['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time',
                    'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore']
            df = pd.read_csv(f, header=None, names=cols)

    # Convert timestamps: Binance 1s uses microseconds
    df['open_time'] = pd.to_datetime(df['open_time'], unit='us')
    df['close_time'] = pd.to_datetime(df['close_time'], unit='us')

    numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'quote_volume', 'taker_buy_base', 'taker_buy_quote']
    for c in numeric_cols:
        df[c] = df[c].astype(np.float32)
    df['trades'] = df['trades'].astype(np.int32)
    df.drop(columns=['ignore'], inplace=True)

    df.to_parquet(out_parquet, compression='zstd', index=False)
    total_time = time.time() - t0
    pq_mb = os.path.getsize(out_parquet) / (1024 * 1024)

    print(f"[{symbol} {month}] SUCCESS: {len(df):,} 1s bars saved -> {out_parquet} "
          f"({pq_mb:.1f} MB, download: {dl_time:.1f}s @ {dl_mb/dl_time:.1f} MB/s, total: {total_time:.1f}s)")
    return out_parquet


def sync_all_1s_data(symbols: list = SYMBOLS, months: list = MONTHS_DEFAULT, max_workers: int = 4):
    """
    Parallel synchronization across multiple assets and months
    """
    print("=" * 80)
    print(f"STARTING 1-SECOND HISTORICAL DATA SYNC: {symbols} for {months}")
    print("=" * 80)

    tasks = []
    for s in symbols:
        for m in months:
            tasks.append((s, m))

    t_start = time.time()
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(download_and_convert_month, s, m): (s, m) for s, m in tasks}
        for fut in as_completed(futures):
            s, m = futures[fut]
            try:
                path = fut.result()
                if path:
                    results.append(path)
            except Exception as e:
                print(f"Task {s} {m} raised error: {e}")

    total_el = time.time() - t_start
    print("=" * 80)
    print(f"1-SECOND SYNC COMPLETE: {len(results)}/{len(tasks)} files synced in {total_el:.1f} seconds!")
    print(f"Storage location: {DATA_DIR}")
    print("=" * 80)
    return results


if __name__ == "__main__":
    # Sync 2026-07 and 2026-08 (2 months = ~5.3 million 1s bars per asset, ~21.2M total)
    sync_all_1s_data(SYMBOLS, ['2026-07', '2026-08'], max_workers=4)
