# -*- coding: utf-8 -*-
"""
Download 4h historical K-lines for top non-meme/non-stablecoin liquid tokens from Binance Futures
"""

import os
import sys
import time
import json
import urllib.request
import pandas as pd

def download_token_4h(symbol, start_ts=1597104000000): # 2020-08-11
    all_rows = []
    curr_ts = start_ts
    while True:
        url = f'https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=4h&limit=1500&startTime={curr_ts}'
        req = urllib.request.Request(url, headers={'User-Agent': 'CryptoQuant/1.0'})
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
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
        time.sleep(0.08)

    df = pd.DataFrame(all_rows, columns=['open_time','open','high','low','close','vol','close_time','qvol','trades','tb_base','tb_quote','ignore'])
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    for c in ['open','high','low','close','vol','qvol']:
        df[c] = df[c].astype(float)
    df = df.set_index('open_time').sort_index()
    df = df[~df.index.duplicated(keep='first')]
    return df

def main():
    target_tokens = ['XRPUSDT', 'ADAUSDT', 'AVAXUSDT', 'LINKUSDT', 'DOTUSDT', 'NEARUSDT', 'LTCUSDT']
    os.makedirs('data', exist_ok=True)

    for tok in target_tokens:
        out_path = f'data/{tok}_4h_2020_2026.parquet'
        if os.path.exists(out_path):
            print(f"Skipping {tok}, already exists at {out_path}")
            continue
        print(f"Downloading {tok} 4h data...")
        df = download_token_4h(tok)
        df.to_parquet(out_path)
        print(f"Saved {tok}: {len(df)} bars from {df.index.min()} to {df.index.max()}")

if __name__ == '__main__':
    main()
