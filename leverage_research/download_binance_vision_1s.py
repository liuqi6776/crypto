# -*- coding: utf-8 -*-
"""
Binance Vision Official 1-Second (1s) K-Line Historical Downloader
币安官方 1秒 (1s) 高频 K 线历史数据批量下载与清洗引擎
- Downloads 1s monthly / daily archives from data.binance.vision
- Unpacks, cleans microsecond timestamps, parses OHLCV + Taker Flow
- Saves into highly compressed Parquet format for institutional backtesting
"""

import os
import sys
import io
import time
import zipfile
import urllib.request
import pandas as pd
import numpy as np

DATA_DIR = r"D:\Convertible_Bond_data\crypto_data\history\1s"
SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT']


def download_1s_day(symbol: str, date_str: str, save_dir: str = DATA_DIR) -> str:
    """
    Downloads and converts a single day of 1-second K-lines (86,400 bars)
    """
    os.makedirs(save_dir, exist_ok=True)
    sym_dir = os.path.join(save_dir, symbol)
    os.makedirs(sym_dir, exist_ok=True)
    
    out_parquet = os.path.join(sym_dir, f"{symbol}_1s_{date_str}.parquet")
    if os.path.exists(out_parquet):
        # print(f"Already exists: {out_parquet}")
        return out_parquet

    url = f"https://data.binance.vision/data/spot/daily/klines/{symbol}/1s/{symbol}-1s-{date_str}.zip"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    req = urllib.request.Request(url, headers=headers)
    
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            zip_bytes = resp.read()
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return ""

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        fname = z.namelist()[0]
        with z.open(fname) as f:
            cols = ['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time',
                    'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore']
            df = pd.read_csv(f, header=None, names=cols)

    # Convert timestamps: Binance 1s uses microseconds (16 digits)
    df['open_time'] = pd.to_datetime(df['open_time'], unit='us')
    df['close_time'] = pd.to_datetime(df['close_time'], unit='us')
    
    numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'quote_volume', 'taker_buy_base', 'taker_buy_quote']
    for c in numeric_cols:
        df[c] = df[c].astype(np.float32)
    df['trades'] = df['trades'].astype(np.int32)
    df.drop(columns=['ignore'], inplace=True)
    
    df.to_parquet(out_parquet, index=False, compression='zstd')
    el = time.time() - t0
    print(f"Saved {symbol} {date_str} 1s ({len(df):,} rows) -> {out_parquet} ({os.path.getsize(out_parquet)/1024:.1f} KB, took {el:.2f}s)")
    return out_parquet


if __name__ == "__main__":
    print("Testing 1-second historical data download across BTC, ETH, SOL, BNB for 2026-08-01:")
    for sym in SYMBOLS:
        download_1s_day(sym, "2026-08-01")
