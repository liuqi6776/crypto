import requests
import pandas as pd
import numpy as np
import datetime
import os
import time
import concurrent.futures

os.makedirs('scratch/klines_1m', exist_ok=True)
os.makedirs('reports', exist_ok=True)

# 1. Define candidate squeeze episodes across 2023-2026
# Load extreme events from funding parquet
df_fund = pd.read_parquet('scratch/funding_dataset_with_returns.parquet')
neg_extreme = df_fund[df_fund['fundingRate'] <= -0.005].copy()
neg_extreme = neg_extreme.sort_values(['symbol', 'fundingTime'])

# Cluster into episodes within 48h
clusters = []
for sym, group in neg_extreme.groupby('symbol'):
    cur_cluster = []
    for idx, row in group.iterrows():
        if not cur_cluster:
            cur_cluster.append(row)
        else:
            diff_hours = (row['fundingTime'] - cur_cluster[-1]['fundingTime']).total_seconds() / 3600
            if diff_hours <= 48:
                cur_cluster.append(row)
            else:
                clusters.append(cur_cluster)
                cur_cluster = [row]
    if cur_cluster:
        clusters.append(cur_cluster)

episodes = []
for c in clusters:
    episodes.append({
        'symbol': c[0]['symbol'],
        't_start': c[0]['fundingTime'] - pd.Timedelta(hours=8),
        't_end': c[-1]['fundingTime'] + pd.Timedelta(hours=24),
        'min_fr': min(r['fundingRate'] for r in c),
        'count': len(c)
    })

# Add historical iconic 2023 events
extra_episodes = [
    {'symbol': 'GASUSDT', 't_start': pd.to_datetime('2023-11-09 00:00:00'), 't_end': pd.to_datetime('2023-11-13 00:00:00'), 'min_fr': -0.020, 'count': 6},
    {'symbol': 'BLZUSDT', 't_start': pd.to_datetime('2023-09-21 00:00:00'), 't_end': pd.to_datetime('2023-09-28 00:00:00'), 'min_fr': -0.018, 'count': 8},
    {'symbol': 'LOOMUSDT', 't_start': pd.to_datetime('2023-10-14 00:00:00'), 't_end': pd.to_datetime('2023-10-18 00:00:00'), 'min_fr': -0.030, 'count': 6},
    {'symbol': 'BIGTIMEUSDT', 't_start': pd.to_datetime('2023-12-04 00:00:00'), 't_end': pd.to_datetime('2023-12-08 00:00:00'), 'min_fr': -0.020, 'count': 6}
]
episodes.extend(extra_episodes)
print(f"Total candidate squeeze episodes to backtest: {len(episodes)}")

# 2. Fetch 1m klines for each episode
def fetch_1m_candles_for_episode(ep, ep_idx):
    sym = ep['symbol']
    t_start_ms = int(ep['t_start'].timestamp() * 1000)
    t_end_ms = int(ep['t_end'].timestamp() * 1000)
    cache_file = f"scratch/klines_1m/{sym}_{ep_idx}_{t_start_ms}_{t_end_ms}.parquet"
    
    if os.path.exists(cache_file):
        try:
            return pd.read_parquet(cache_file)
        except Exception:
            pass
            
    # Fetch in chunks of 1000 bars
    cur_start = t_start_ms
    all_bars = []
    while cur_start < t_end_ms:
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}&interval=1m&startTime={cur_start}&limit=1000"
        try:
            r = requests.get(url, timeout=10).json()
            if not isinstance(r, list) or len(r) == 0:
                break
            all_bars.extend(r)
            last_open = r[-1][0]
            cur_start = last_open + 60000
            if len(r) < 1000:
                break
        except Exception as e:
            time.sleep(1)
            break
            
    if len(all_bars) == 0:
        return None
        
    df = pd.DataFrame(all_bars, columns=['open_time', 'open', 'high', 'low', 'close', 'vol', 'close_time', 'q_vol', 'trades', 'tb_b', 'tb_q', 'ig'])
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df = df.drop_duplicates(subset=['open_time']).sort_values('open_time').reset_index(drop=True)
    for c in ['open', 'high', 'low', 'close', 'vol', 'q_vol']:
        df[c] = df[c].astype(float)
        
    df.to_parquet(cache_file)
    return df

print("Fetching and caching 1-minute klines for all candidate episodes...")
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(fetch_1m_candles_for_episode, ep, i) for i, ep in enumerate(episodes)]
    loaded_dfs = [f.result() for f in futures]

valid_episodes = [(ep, df) for ep, df in zip(episodes, loaded_dfs) if df is not None and len(df) >= 60]
print(f"Successfully loaded 1m klines for {len(valid_episodes)} / {len(episodes)} episodes.")
