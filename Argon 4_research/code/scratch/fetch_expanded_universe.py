import requests
import pandas as pd
import numpy as np
import datetime
import os
import time
import concurrent.futures

os.makedirs('scratch/klines_1m', exist_ok=True)
os.makedirs('scratch/klines_15m', exist_ok=True)
os.makedirs('scratch/klines_1h', exist_ok=True)

df_fund = pd.read_parquet('scratch/funding_dataset_with_returns.parquet')

# Identify all events with fundingRate <= -0.001 (-0.10%) and ret_prev_1 >= 0.03
cands_neg = df_fund[(df_fund['fundingRate'] <= -0.001) & (df_fund['ret_prev_1'] >= 0.03)].copy()
# Identify top positive with fundingRate >= 0.0008 (+0.08%) and ret_prev_1 >= 0.05
cands_pos = df_fund[(df_fund['fundingRate'] >= 0.0008) & (df_fund['ret_prev_1'] >= 0.05)].copy()

cands_all = pd.concat([cands_neg, cands_pos]).sort_values(['symbol', 'fundingTime']).reset_index(drop=True)

# Cluster into episodes
clusters = []
for sym, group in cands_all.groupby('symbol'):
    cur = []
    for idx, row in group.iterrows():
        if not cur:
            cur.append(row)
        else:
            diff_h = (row['fundingTime'] - cur[-1]['fundingTime']).total_seconds() / 3600
            if diff_h <= 36:
                cur.append(row)
            else:
                clusters.append(cur)
                cur = [row]
    if cur:
        clusters.append(cur)

print(f"Total candidate clusters found: {len(clusters)}")

targets = []
for i, c in enumerate(clusters):
    sym = c[0]['symbol']
    t_start = c[0]['fundingTime'] - pd.Timedelta(hours=12)
    t_end = c[-1]['fundingTime'] + pd.Timedelta(hours=24)
    start_ms = int(t_start.timestamp() * 1000)
    end_ms = int(t_end.timestamp() * 1000)
    targets.append({
        'symbol': sym,
        'ep_idx': f"exp_{i}",
        'start_ms': start_ms,
        'end_ms': end_ms
    })

print(f"Total targets to fetch: {len(targets)}")

def fetch_candles_for_target(t, interval, out_dir):
    sym = t['symbol']
    start_ms = t['start_ms']
    end_ms = t['end_ms']
    ep_idx = t['ep_idx']
    out_file = f"{out_dir}/{sym}_{ep_idx}_{start_ms}_{end_ms}.parquet"
    if os.path.exists(out_file):
        return
        
    step_ms = 60000 * (1 if interval == '1m' else (15 if interval == '15m' else 60))
    all_bars = []
    cur_start = start_ms
    while cur_start < end_ms:
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}&interval={interval}&startTime={cur_start}&limit=1000"
        try:
            r = requests.get(url, timeout=10).json()
            if not isinstance(r, list) or len(r) == 0:
                break
            all_bars.extend(r)
            last_open = r[-1][0]
            cur_start = last_open + step_ms
            if len(r) < 1000:
                break
        except Exception:
            time.sleep(0.5)
            break
            
    if len(all_bars) > 0:
        df = pd.DataFrame(all_bars, columns=['open_time', 'open', 'high', 'low', 'close', 'vol', 'close_time', 'q_vol', 'trades', 'tb_b', 'tb_q', 'ig'])
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df = df.drop_duplicates(subset=['open_time']).sort_values('open_time').reset_index(drop=True)
        for col in ['open', 'high', 'low', 'close', 'vol', 'q_vol']:
            df[col] = df[col].astype(float)
        df.to_parquet(out_file)

print("Fetching 15m candles in parallel...")
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
    list(executor.map(lambda t: fetch_candles_for_target(t, '15m', 'scratch/klines_15m'), targets))

print("Fetching 1m candles in parallel...")
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
    list(executor.map(lambda t: fetch_candles_for_target(t, '1m', 'scratch/klines_1m'), targets))

print("Fetching 1h candles in parallel...")
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
    list(executor.map(lambda t: fetch_candles_for_target(t, '1h', 'scratch/klines_1h'), targets))

print("Done fetching expanded universe!")
