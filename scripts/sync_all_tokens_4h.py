# -*- coding: utf-8 -*-
"""
Update all 4h parquet files to the latest bar from Binance Futures.
Also downloads SUIUSDT 4h data.
"""
import os
import sys
import time
import json
import urllib.request
import pandas as pd

def fetch_klines(symbol, start_ts=1597104000000):
    all_rows = []
    curr_ts = start_ts
    while True:
        url = f'https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=4h&limit=1500&startTime={curr_ts}'
        req = urllib.request.Request(url, headers={'User-Agent': 'CryptoQuant/1.0'})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            print(f"Retry {symbol} at {curr_ts}: {e}")
            time.sleep(1)
            continue

        if not data:
            break
        all_rows.extend(data)
        last_time = data[-1][0]
        if last_time == curr_ts or len(data) < 1500:
            break
        curr_ts = last_time + 4 * 3600 * 1000
        time.sleep(0.05)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows, columns=['open_time','open','high','low','close','vol','close_time','qvol','trades','tb_base','tb_quote','ignore'])
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    for c in ['open','high','low','close','vol','qvol']:
        df[c] = df[c].astype(float)
    df = df.set_index('open_time').sort_index()
    df = df[~df.index.duplicated(keep='first')]
    return df

def update_symbol(symbol):
    path = f'data/{symbol}_4h_2020_2026.parquet'
    start_ts = 1597104000000 # 2020-08-11
    if os.path.exists(path):
        existing_df = pd.read_parquet(path)
        last_ts = int(existing_df.index.max().timestamp() * 1000)
        # fetch from last timestamp
        print(f"Updating {symbol} from {existing_df.index.max()}...")
        new_df = fetch_klines(symbol, start_ts=last_ts)
        if not new_df.empty:
            combined = pd.concat([existing_df, new_df])
            combined = combined[~combined.index.duplicated(keep='last')].sort_index()
            combined.to_parquet(path)
            print(f"Updated {symbol}: now {len(combined)} bars, ending {combined.index.max()}")
        else:
            print(f"{symbol} is already up to date.")
    else:
        print(f"Downloading new symbol {symbol}...")
        df = fetch_klines(symbol, start_ts=start_ts)
        df.to_parquet(path)
        print(f"Saved {symbol}: {len(df)} bars from {df.index.min()} to {df.index.max()}")

def main():
    symbols = [
        'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT',
        'AVAXUSDT', 'NEARUSDT', 'LINKUSDT', 'ADAUSDT',
        'DOTUSDT', 'LTCUSDT', 'XRPUSDT', 'SUIUSDT'
    ]
    for s in symbols:
        try:
            update_symbol(s)
        except Exception as e:
            print(f"Error updating {s}: {e}")

if __name__ == '__main__':
    main()
