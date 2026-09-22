# -*- coding: utf-8 -*-
"""
Sync September 1 to September 22, 2026 K-lines for BTCUSDT and ensure parity with ETHUSDT
"""

import os
import io
import time
import zipfile
import urllib.request
import json
import pandas as pd
import numpy as np

DATA_DIR = r"D:\Convertible_Bond_data\crypto_data\history\futures_1m"

def sync_symbol_september(symbol: str):
    print(f"=== Syncing {symbol} for September 1 to September 22, 2026 ===")
    daily_frames = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # 1. Binance Vision daily archives
    for day in range(1, 21):
        d_str = f"2026-09-{day:02d}"
        url = f"https://data.binance.vision/data/futures/um/daily/klines/{symbol}/1m/{symbol}-1m-{d_str}.zip"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                with zipfile.ZipFile(io.BytesIO(resp.read())) as z:
                    with z.open(z.namelist()[0]) as f:
                        cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_volume', 'trades_count', 'taker_buy_volume', 'taker_buy_quote_volume', 'ignore']
                        first = f.readline().decode('utf-8')
                        f.seek(0)
                        if 'open_time' in first or 'timestamp' in first:
                            df = pd.read_csv(f, header=0)
                            df.columns = cols[:len(df.columns)]
                        else:
                            df = pd.read_csv(f, header=None, names=cols)
                        daily_frames.append(df)
            print(f"  [Vision] {d_str} OK")
        except Exception as e:
            print(f"  [Vision] {d_str} skipped ({e})")

    # 2. Binance FAPI for live recent bars (Sept 21-22)
    start_ts = int(pd.Timestamp('2026-09-21 00:00:00', tz='UTC').timestamp() * 1000)
    end_ts = int(time.time() * 1000)
    fapi_frames = []
    curr = start_ts
    while curr < end_ts:
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=1m&startTime={curr}&endTime={end_ts}&limit=1500"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            if not data:
                break
            cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_volume', 'trades_count', 'taker_buy_volume', 'taker_buy_quote_volume', 'ignore']
            df_chunk = pd.DataFrame(data, columns=cols)
            fapi_frames.append(df_chunk)
            last_t = int(data[-1][0])
            if last_t <= curr:
                break
            curr = last_t + 60000
        except Exception as e:
            print(f"  [FAPI] Error fetching {curr}: {e}")
            break
            
    if fapi_frames:
        print(f"  [FAPI] Fetched {sum(len(f) for f in fapi_frames)} recent live bars.")
        daily_frames.extend(fapi_frames)
        
    df_all = pd.concat(daily_frames, ignore_index=True).drop_duplicates(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)
    df_all['datetime'] = pd.to_datetime(df_all['timestamp'], unit='ms', utc=True)
    for c in ['open', 'high', 'low', 'close', 'volume', 'quote_volume', 'taker_buy_volume', 'taker_buy_quote_volume']:
        df_all[c] = df_all[c].astype(np.float64)
    df_all['timestamp'] = df_all['timestamp'].astype(np.int64)
    df_all['trades_count'] = df_all['trades_count'].astype(np.int64)
    if 'ignore' in df_all.columns:
        df_all = df_all.drop(columns=['ignore'])
        
    out_p = os.path.join(DATA_DIR, f"{symbol}_2026_09_01_to_09_22.parquet")
    df_all.to_parquet(out_p, index=False, compression='zstd')
    print(f"  [SUCCESS] Saved {symbol} -> {len(df_all):,} bars ({df_all['datetime'].iloc[0]} to {df_all['datetime'].iloc[-1]})")
    return out_p

if __name__ == "__main__":
    sync_symbol_september("BTCUSDT")
