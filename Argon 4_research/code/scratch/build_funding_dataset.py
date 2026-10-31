import requests
import concurrent.futures
import pandas as pd
import numpy as np
import datetime
import os
import time

os.makedirs('scratch', exist_ok=True)

# 1. Load recent funding data
print("Loading recent funding parquet...")
df_recent = pd.read_parquet('scratch/binance_funding_recent.parquet')
print(f"Loaded {len(df_recent)} recent records.")

# 2. Fetch historical deep records for famous extreme tokens (2023-2025)
extreme_tokens = [
    'TRBUSDT', 'BLZUSDT', 'GASUSDT', 'BIGTIMEUSDT', 'LOOMUSDT', 'CYBERUSDT', 
    'UNFIUSDT', 'ARKUSDT', 'LEVERUSDT', 'LPTUSDT', 'YGGUSDT', 'STMXUSDT', 
    'OGNUSDT', 'ORDIUSDT', 'AUCTIONUSDT', 'BAKEUSDT', 'POWRUSDT', 'STORJUSDT',
    'ARKMUSDT', 'WIFUSDT', 'PEPEUSDT', 'FLOKIUSDT', 'SOLUSDT', 'DOGEUSDT', 
    'BTCUSDT', 'ETHUSDT', 'NEARUSDT', 'SUIUSDT', 'APTUSDT', 'ENAUSDT'
]

def fetch_symbol_deep(sym):
    # Fetch 5 chunks going back from 2025/2026 into 2023
    chunks = []
    # start from 2024-06-01 back to 2023
    end_times = [
        1719792000000, # 2024-07-01
        1704067200000, # 2024-01-01
        1696118400000, # 2023-10-01
        1688169600000, # 2023-07-01
    ]
    for et in end_times:
        url = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={sym}&limit=100&endTime={et}"
        try:
            r = requests.get(url, timeout=5).json()
            if isinstance(r, list) and len(r) > 0:
                valid = [x for x in r if isinstance(x, dict) and 'fundingRate' in x]
                chunks.extend(valid)
        except Exception:
            pass
    return chunks

print("Fetching historical deep chunks for extreme tokens...")
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    historical_results = list(executor.map(fetch_symbol_deep, extreme_tokens))

hist_records = [item for sublist in historical_results for item in sublist]
print(f"Fetched {len(hist_records)} historical records.")

df_hist = pd.DataFrame(hist_records)
if len(df_hist) > 0:
    df_hist['fundingRate'] = pd.to_numeric(df_hist['fundingRate'], errors='coerce')
    df_hist['markPrice'] = pd.to_numeric(df_hist['markPrice'], errors='coerce')
    df_hist['fundingTime'] = pd.to_datetime(df_hist['fundingTime'], unit='ms')
    df_hist = df_hist.dropna(subset=['fundingRate', 'markPrice'])

# Combine and deduplicate
df_all = pd.concat([df_recent, df_hist], ignore_index=True)
df_all = df_all.drop_duplicates(subset=['symbol', 'fundingTime'])
df_all = df_all.sort_values(['symbol', 'fundingTime']).reset_index(drop=True)

print(f"Combined total records: {len(df_all)}")
print(f"Date range: {df_all['fundingTime'].min()} to {df_all['fundingTime'].max()}")

# 3. Calculate forward and backward price returns
# For each symbol, sort by fundingTime
df_all['ret_fwd_1'] = df_all.groupby('symbol')['markPrice'].shift(-1) / df_all['markPrice'] - 1.0
df_all['ret_fwd_3'] = df_all.groupby('symbol')['markPrice'].shift(-3) / df_all['markPrice'] - 1.0
df_all['ret_fwd_6'] = df_all.groupby('symbol')['markPrice'].shift(-6) / df_all['markPrice'] - 1.0
df_all['ret_fwd_21'] = df_all.groupby('symbol')['markPrice'].shift(-21) / df_all['markPrice'] - 1.0

df_all['ret_prev_1'] = df_all['markPrice'] / df_all.groupby('symbol')['markPrice'].shift(1) - 1.0
df_all['ret_prev_3'] = df_all['markPrice'] / df_all.groupby('symbol')['markPrice'].shift(3) - 1.0

# Filter rows where ret_fwd_1 is valid
df_valid = df_all.dropna(subset=['ret_fwd_1']).copy()
print(f"Valid records with forward returns: {len(df_valid)}")

df_valid.to_parquet('scratch/funding_dataset_with_returns.parquet')
print("Saved to scratch/funding_dataset_with_returns.parquet")
