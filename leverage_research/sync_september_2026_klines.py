# -*- coding: utf-8 -*-
"""
Sync September 1 to September 22, 2026 ETH 1-Minute Futures K-Lines
2026年9月1日至9月22日以太坊 1分钟连续合约数据同步与清洗引擎
- Downloads daily archives from data.binance.vision (Sept 1 to Sept 20)
- Fetches recent live bars from fapi.binance.com (Sept 21 to Sept 22)
- Merges into a clean, continuous, gap-free Parquet dataset
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
OUT_PARQUET = os.path.join(DATA_DIR, "ETHUSDT_2026_09_01_to_09_22.parquet")
SYMBOL = "ETHUSDT"

STANDARD_COLUMNS = [
    'timestamp', 'open', 'high', 'low', 'close', 'volume',
    'close_time', 'quote_volume', 'trades_count',
    'taker_buy_volume', 'taker_buy_quote_volume', 'ignore'
]


def download_vision_daily_1m(symbol: str, date_str: str) -> pd.DataFrame:
    """
    Downloads and extracts a single daily 1m zip archive from Binance Vision.
    """
    url = f"https://data.binance.vision/data/futures/um/daily/klines/{symbol}/1m/{symbol}-1m-{date_str}.zip"
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            zip_bytes = resp.read()
    except Exception as e:
        print(f"  [Vision] Failed to download {url}: {e}")
        return pd.DataFrame()
        
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        fname = z.namelist()[0]
        with z.open(fname) as f:
            # Check first line to see if it has a header
            first_line = f.readline().decode('utf-8')
            f.seek(0)
            if 'open_time' in first_line or 'timestamp' in first_line:
                df = pd.read_csv(f, header=0)
                df.columns = STANDARD_COLUMNS[:len(df.columns)]
            else:
                df = pd.read_csv(f, header=None, names=STANDARD_COLUMNS)
            
    return df


def fetch_recent_klines_fapi(symbol: str, start_time_ms: int, end_time_ms: int) -> pd.DataFrame:
    """
    Paginates and fetches recent 1m klines from Binance Futures REST API (fapi.binance.com).
    """
    all_rows = []
    current_start = start_time_ms
    limit = 1500
    
    while current_start < end_time_ms:
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=1m&startTime={current_start}&limit={limit}"
        headers = {"User-Agent": "Mozilla/5.0"}
        req = urllib.request.Request(url, headers=headers)
        
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            print(f"  [FAPI] Error fetching at {current_start}: {e}")
            time.sleep(2)
            continue
            
        if not data:
            break
            
        for row in data:
            all_rows.append(row)
            
        last_time = data[-1][0]
        if last_time <= current_start or len(data) < limit:
            break
        current_start = last_time + 60000
        time.sleep(0.1)
        
    if not all_rows:
        return pd.DataFrame()
        
    df = pd.DataFrame(all_rows, columns=STANDARD_COLUMNS)
    return df


def main():
    print("=" * 70)
    print("Syncing ETHUSDT 1m Futures Data (2026-09-01 00:00 to 2026-09-22 14:48)")
    print("=" * 70)
    
    os.makedirs(DATA_DIR, exist_ok=True)
    daily_frames = []
    
    # 1. Download daily archives (Sept 1 to Sept 20, 2026)
    print(">>> 1. Fetching Binance Vision archives (Sept 1 to Sept 20)...")
    for day in range(1, 21):
        date_str = f"2026-09-{day:02d}"
        df_day = download_vision_daily_1m(SYMBOL, date_str)
        if not df_day.empty:
            daily_frames.append(df_day)
            print(f"  [OK] {date_str}: {len(df_day)} bars (start: {pd.to_datetime(df_day['timestamp'].iloc[0], unit='ms', utc=True)})")
        else:
            print(f"  [WARN] Missing Vision archive for {date_str}, will backfill from FAPI")
            
    # Determine the latest timestamp collected from Vision
    if daily_frames:
        combined_vision = pd.concat(daily_frames, ignore_index=True)
        latest_ts = int(combined_vision['timestamp'].max())
        print(f"Latest Vision timestamp: {pd.to_datetime(latest_ts, unit='ms', utc=True)}")
        fapi_start = latest_ts + 60000
    else:
        fapi_start = int(pd.Timestamp("2026-09-01 00:00:00", tz='UTC').timestamp() * 1000)
        
    # 2. Fetch remaining recent bars up to now from fapi.binance.com
    now_ms = int(time.time() * 1000)
    print(f"\n>>> 2. Fetching recent bars from fapi.binance.com ({pd.to_datetime(fapi_start, unit='ms', utc=True)} to now)...")
    df_recent = fetch_recent_klines_fapi(SYMBOL, fapi_start, now_ms)
    
    if not df_recent.empty:
        print(f"  [OK] Fetched {len(df_recent)} bars from FAPI (up to {pd.to_datetime(df_recent['timestamp'].iloc[-1], unit='ms', utc=True)})")
        daily_frames.append(df_recent)
    else:
        print("  [INFO] No newer bars needed from FAPI.")
        
    # 3. Concatenate and clean
    print("\n>>> 3. Merging and deduplicating...")
    df_all = pd.concat(daily_frames, ignore_index=True)
    
    # Cast types
    numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'quote_volume',
                    'taker_buy_volume', 'taker_buy_quote_volume']
    for c in numeric_cols:
        df_all[c] = df_all[c].astype(np.float64)
        
    df_all['timestamp'] = df_all['timestamp'].astype(np.int64)
    df_all['trades_count'] = df_all['trades_count'].astype(np.int64)
    
    # Sort and deduplicate
    df_all = df_all.drop_duplicates(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)
    
    # Add datetime
    df_all['datetime'] = pd.to_datetime(df_all['timestamp'], unit='ms', utc=True)
    
    # Filter strictly to September 2026
    start_cut = pd.Timestamp("2026-09-01 00:00:00", tz='UTC')
    df_all = df_all[df_all['datetime'] >= start_cut].reset_index(drop=True)
    
    # Check continuity
    time_diffs = df_all['timestamp'].diff()
    gaps = (time_diffs > 60000).sum()
    print(f"\n--- Data Integrity Verification ---")
    print(f"  Total 1m bars: {len(df_all):,}")
    print(f"  Start: {df_all['datetime'].iloc[0]}")
    print(f"  End:   {df_all['datetime'].iloc[-1]}")
    print(f"  Gaps (> 1m): {gaps} (0 expected)")
    print(f"  Min Price: ${df_all['low'].min():.2f} | Max Price: ${df_all['high'].max():.2f}")
    
    # Drop ignore column if present
    if 'ignore' in df_all.columns:
        df_all = df_all.drop(columns=['ignore'])

    # Save to parquet
    df_all.to_parquet(OUT_PARQUET, index=False, compression='zstd')
    print(f"\nSaved successfully to: {OUT_PARQUET} ({os.path.getsize(OUT_PARQUET)/1024/1024:.2f} MB)")
    print("=" * 70)


if __name__ == "__main__":
    main()
