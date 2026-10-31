import requests
import concurrent.futures
import pandas as pd
import numpy as np
import datetime
import os

os.makedirs('scratch', exist_ok=True)

# 1. Fetch symbols
tickers = requests.get('https://fapi.binance.com/fapi/v1/ticker/24hr').json()
df_t = [{'symbol': t['symbol'], 'vol': float(t['quoteVolume'])} for t in tickers if t['symbol'].endswith('USDT')]
df_t.sort(key=lambda x: x['vol'], reverse=True)
top_symbols = [x['symbol'] for x in df_t[:120]]
extra_symbols = ['TRBUSDT', 'BLZUSDT', 'GASUSDT', 'BIGTIMEUSDT', 'LOOMUSDT', 'CYBERUSDT', 
                 'ARKUSDT', 'FRONTUSDT', 'UNFIUSDT', 'NMRUSDT', 'LEVERUSDT', 'LPTUSDT', 
                 'YGGUSDT', 'BNTUSDT', 'STMXUSDT', 'OGNUSDT', 'ORDIUSDT', 'AUCTIONUSDT', 'BAKEUSDT']
target_symbols = list(set(top_symbols + extra_symbols))
print(f"Total symbols to query: {len(target_symbols)}")

# 2. Fetch up to 1000 records for each symbol
def fetch_symbol_funding(sym):
    # Fetch 1000 most recent records
    url = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={sym}&limit=1000"
    try:
        r = requests.get(url, timeout=10).json()
        if isinstance(r, list):
            return r
    except Exception as e:
        pass
    return []

with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
    results = list(executor.map(fetch_symbol_funding, target_symbols))

all_records = [item for sublist in results for item in sublist]
df = pd.DataFrame(all_records)
df['fundingRate'] = df['fundingRate'].astype(float)
df['markPrice'] = df['markPrice'].astype(float)
df['fundingTime'] = pd.to_datetime(df['fundingTime'], unit='ms')
df = df.sort_values(['symbol', 'fundingTime']).reset_index(drop=True)

print(f"Total records fetched: {len(df)}")
print(f"Date range: {df['fundingTime'].min()} to {df['fundingTime'].max()}")
print("\nFunding Rate Summary Statistics:")
print(df['fundingRate'].describe(percentiles=[0.001, 0.01, 0.05, 0.1, 0.5, 0.9, 0.95, 0.99, 0.999]))

# Counts of extremes
print(f"\nCount < -0.1% (-10 bps): {(df['fundingRate'] < -0.001).sum()}")
print(f"Count < -0.3% (-30 bps): {(df['fundingRate'] < -0.003).sum()}")
print(f"Count < -0.5% (-50 bps): {(df['fundingRate'] < -0.005).sum()}")
print(f"Count < -1.0% (-100 bps): {(df['fundingRate'] < -0.01).sum()}")
print(f"Count > +0.05% (+5 bps): {(df['fundingRate'] > 0.0005).sum()}")
print(f"Count > +0.1% (+10 bps): {(df['fundingRate'] > 0.001).sum()}")
print(f"Count > +0.3% (+30 bps): {(df['fundingRate'] > 0.003).sum()}")
print(f"Count > +0.5% (+50 bps): {(df['fundingRate'] > 0.005).sum()}")
print(f"Count > +1.0% (+100 bps): {(df['fundingRate'] > 0.01).sum()}")

# Save to parquet for further analysis
df.to_parquet('scratch/binance_funding_recent.parquet')
print("Saved to scratch/binance_funding_recent.parquet")
