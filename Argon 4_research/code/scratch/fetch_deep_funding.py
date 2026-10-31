import requests
import concurrent.futures
import pandas as pd
import numpy as np
import datetime
import os
import time

# Top symbols + famous extreme symbols
tickers = requests.get('https://fapi.binance.com/fapi/v1/ticker/24hr').json()
df_t = [{'symbol': t['symbol'], 'vol': float(t['quoteVolume'])} for t in tickers if t['symbol'].endswith('USDT')]
df_t.sort(key=lambda x: x['vol'], reverse=True)
top_symbols = [x['symbol'] for x in df_t[:80]]
extreme_coins = [
    'TRBUSDT', 'BLZUSDT', 'GASUSDT', 'BIGTIMEUSDT', 'LOOMUSDT', 'CYBERUSDT', 
    'ARKUSDT', 'FRONTUSDT', 'UNFIUSDT', 'NMRUSDT', 'LEVERUSDT', 'LPTUSDT', 
    'YGGUSDT', 'BNTUSDT', 'STMXUSDT', 'OGNUSDT', 'ORDIUSDT', 'AUCTIONUSDT', 
    'BAKEUSDT', 'POWRUSDT', 'CREAMUSDT', 'BONDUSDT', 'STRAXUSDT', 'STORJUSDT',
    'ARKMUSDT', 'WIFUSDT', 'PEPEUSDT', 'FLOKIUSDT', 'MEMEUSDT', 'NOTUSDT',
    'TONUSDT', 'SOLUSDT', 'DOGEUSDT', 'BTCUSDT', 'ETHUSDT'
]
target_symbols = list(set(top_symbols + extreme_coins))
print(f"Total symbols: {len(target_symbols)}")

def fetch_deep_funding(sym):
    all_rows = []
    end_time = int(time.time() * 1000)
    # Paginate backwards up to 3 pages (3000 records = ~1000 days ~ 2.7 years)
    for _ in range(3):
        url = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={sym}&limit=1000&endTime={end_time}"
        try:
            r = requests.get(url, timeout=10).json()
            if isinstance(r, list) and len(r) > 0:
                valid_items = [x for x in r if isinstance(x, dict) and 'fundingRate' in x]
                all_rows.extend(valid_items)
                first_time = valid_items[0]['fundingTime']
                end_time = first_time - 1
                if len(r) < 1000:
                    break
            else:
                break
        except Exception:
            break
    return all_rows

print("Fetching deep history (2023-2026)...")
with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
    results = list(executor.map(fetch_deep_funding, target_symbols))

all_records = [item for sublist in results for item in sublist]
df = pd.DataFrame(all_records)
# Drop duplicates
df = df.drop_duplicates(subset=['symbol', 'fundingTime'])
df['fundingRate'] = df['fundingRate'].astype(float)
df['markPrice'] = df['markPrice'].astype(float)
df['fundingTime'] = pd.to_datetime(df['fundingTime'], unit='ms')
df = df.sort_values(['symbol', 'fundingTime']).reset_index(drop=True)

print(f"Total unique records fetched: {len(df)}")
print(f"Date range: {df['fundingTime'].min()} to {df['fundingTime'].max()}")

# Save to parquet
df.to_parquet('scratch/binance_funding_deep.parquet')
print("Saved to scratch/binance_funding_deep.parquet")
