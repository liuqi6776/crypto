import os
import glob
import requests
import pandas as pd
import concurrent.futures
import time

os.makedirs('scratch/klines_15m', exist_ok=True)
os.makedirs('scratch/klines_1h', exist_ok=True)

# Parse all 1m files to get exact symbol and time range for each episode
files_1m = glob.glob('scratch/klines_1m/*.parquet')
print(f"Found {len(files_1m)} 1m episode files.")

episode_targets = []
for f in files_1m:
    basename = os.path.basename(f).replace('.parquet', '')
    parts = basename.split('_')
    sym = parts[0]
    ep_idx = parts[1]
    t_start_ms = int(parts[2])
    t_end_ms = int(parts[3])
    episode_targets.append({
        'symbol': sym,
        'ep_idx': ep_idx,
        't_start_ms': t_start_ms,
        't_end_ms': t_end_ms
    })

def fetch_candles(sym, interval, start_ms, end_ms, out_dir, ep_idx):
    out_file = f"{out_dir}/{sym}_{ep_idx}_{start_ms}_{end_ms}.parquet"
    if os.path.exists(out_file):
        return
        
    all_bars = []
    cur_start = start_ms
    step_ms = 60000 * (15 if interval == '15m' else 60)
    
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
        for c in ['open', 'high', 'low', 'close', 'vol', 'q_vol']:
            df[c] = df[c].astype(float)
        df.to_parquet(out_file)

print("Fetching 15-minute candles...")
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    list(executor.map(lambda ep: fetch_candles(ep['symbol'], '15m', ep['t_start_ms'], ep['t_end_ms'], 'scratch/klines_15m', ep['ep_idx']), episode_targets))

print("Fetching 1-hour candles...")
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    list(executor.map(lambda ep: fetch_candles(ep['symbol'], '1h', ep['t_start_ms'], ep['t_end_ms'], 'scratch/klines_1h', ep['ep_idx']), episode_targets))

files_15m = glob.glob('scratch/klines_15m/*.parquet')
files_1h = glob.glob('scratch/klines_1h/*.parquet')
print(f"Done! Cached {len(files_15m)} 15m files and {len(files_1h)} 1h files.")
