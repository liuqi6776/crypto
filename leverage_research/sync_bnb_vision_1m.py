"""
Sync BNBUSDT 1m Futures Data from Binance Vision (2023 - 2026)
高速同步币安 Vision 官方归档的 BNBUSDT 1m 永续合约历史数据
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

DEFAULT_PROXY = "http://127.0.0.1:7897"

STANDARD_COLUMNS = [
    'timestamp', 'open', 'high', 'low', 'close', 'volume',
    'close_time', 'quote_volume', 'trades_count',
    'taker_buy_volume', 'taker_buy_quote_volume', 'ignore'
]

def make_opener(proxy_url: str = DEFAULT_PROXY):
    if proxy_url:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url})
        )
    return urllib.request.build_opener()

def download_and_parse_month(opener, url: str, out_parquet: str):
    if os.path.exists(out_parquet):
        try:
            df = pd.read_parquet(out_parquet)
            if not df.empty:
                return df
        except Exception:
            pass

    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    content = None
    for attempt in range(3):
        try:
            with opener.open(req, timeout=20) as resp:
                content = resp.read()
                break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(1.0)
        except Exception:
            time.sleep(1.0)

    if content is None:
        return None

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            csv_name = z.namelist()[0]
            with z.open(csv_name) as f:
                df = pd.read_csv(f, header=None, low_memory=False)

        if str(df.iloc[0, 0]).startswith('open'):
            df = df.iloc[1:].reset_index(drop=True)

        cols = STANDARD_COLUMNS[:df.shape[1]]
        df.columns = cols

        df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce')
        df = df.dropna(subset=['timestamp'])
        df['timestamp'] = df['timestamp'].astype(np.int64)

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

def sync_bnb(start_year: int = 2023, end_year: int = 2026, base_dir: str = r"D:\Convertible_Bond_data\crypto_data\history\futures_1m", proxy: str = DEFAULT_PROXY):
    opener = make_opener(proxy)
    symbol = "BNBUSDT"
    interval = "1m"
    save_dir = os.path.join(base_dir, symbol)
    os.makedirs(save_dir, exist_ok=True)

    tasks = []
    curr = datetime.datetime.now()
    for y in range(start_year, end_year + 1):
        for m in range(1, 13):
            if y > curr.year or (y == curr.year and m > curr.month):
                continue
            month_str = f"{y}-{m:02d}"
            url = f"https://data.binance.vision/data/futures/um/monthly/klines/{symbol}/{interval}/{symbol}-{interval}-{month_str}.zip"
            out_file = os.path.join(save_dir, f"{symbol}_{interval}_{month_str}.parquet")
            tasks.append((month_str, url, out_file))

    print(f"\n>>> [BNBUSDT | 1m] Downloading {len(tasks)} months ({tasks[0][0]} to {tasks[-1][0]})...")
    with ThreadPoolExecutor(max_workers=8) as executor:
        fmap = {executor.submit(download_and_parse_month, opener, url, out_file): m_str for m_str, url, out_file in tasks}
        success = 0
        for f in as_completed(fmap):
            m_str = fmap[f]
            try:
                res = f.result()
                if res is not None and not res.empty:
                    success += 1
                    print(f"  [OK] {m_str}: {len(res):,} bars")
            except Exception as e:
                print(f"  [FAIL] {m_str}: {e}")

    print(f"\nDownloaded {success}/{len(tasks)} months. Consolidating into continuous Parquet...")
    all_files = sorted([
        os.path.join(save_dir, f) for f in os.listdir(save_dir)
        if f.endswith('.parquet') and not f.endswith('_continuous.parquet')
    ])
    dfs = [pd.read_parquet(f) for f in all_files]
    if dfs:
        df_all = pd.concat(dfs, ignore_index=True).drop_duplicates(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)
        consolidated = os.path.join(base_dir, f"{symbol}_futures_1m_continuous.parquet")
        df_all.to_parquet(consolidated, index=False)
        print(f"[CONSOLIDATED] {consolidated}")
        print(f"  Total Bars: {len(df_all):,} | Range: {df_all['datetime'].iloc[0]} -> {df_all['datetime'].iloc[-1]}")
        return consolidated
    return ""

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--start-year', type=int, default=2023)
    parser.add_argument('--end-year', type=int, default=2026)
    parser.add_argument('--base-dir', type=str, default=r"D:\Convertible_Bond_data\crypto_data\history\futures_1m")
    parser.add_argument('--proxy', type=str, default=DEFAULT_PROXY)
    args = parser.parse_args()
    sync_bnb(args.start_year, args.end_year, args.base_dir, args.proxy)
