import requests
import pandas as pd
import numpy as np
import datetime
import os

os.makedirs('scratch', exist_ok=True)

# -------------------------------------------------------------
# Part 1: Extreme Altcoin Squeezes (5m / 15m Analysis)
# -------------------------------------------------------------
print("="*70)
print("Part 1: Extreme Altcoins (Pure Contract Extremes) 5m/15m Squeeze Events")
print("="*70)

alt_events = [
    {'symbol': 'TRBUSDT', 'start_ms': 1704045600000, 'name': 'TRB Dec 2023 Squeeze', 'fr_peak': -0.020},
    {'symbol': 'GASUSDT', 'start_ms': 1699660800000, 'name': 'GAS Nov 2023 Squeeze', 'fr_peak': -0.020},
    {'symbol': 'BLZUSDT', 'start_ms': 1695427200000, 'name': 'BLZ Sep 2023 Squeeze', 'fr_peak': -0.018},
    {'symbol': 'ARKUSDT', 'start_ms': 1699574400000, 'name': 'ARK Nov 2023 Squeeze', 'fr_peak': -0.015},
    {'symbol': 'AUCTIONUSDT', 'start_ms': 1703635200000, 'name': 'AUCTION Dec 2023 Squeeze', 'fr_peak': -0.020},
    {'symbol': 'BIGTIMEUSDT', 'start_ms': 1701734400000, 'name': 'BIGTIME Dec 2023 Squeeze', 'fr_peak': -0.020},
    {'symbol': 'LOOMUSDT', 'start_ms': 1697328000000, 'name': 'LOOM Oct 2023 Squeeze', 'fr_peak': -0.015},
]

alt_results = []
for ev in alt_events:
    sym = ev['symbol']
    # Fetch 500 5m candles
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}&interval=5m&startTime={ev['start_ms']}&limit=500"
    try:
        r = requests.get(url, timeout=10).json()
        if isinstance(r, list) and len(r) > 50:
            df = pd.DataFrame(r, columns=['open_time', 'open', 'high', 'low', 'close', 'vol', 'close_time', 'q_vol', 'trades', 'tb_b', 'tb_q', 'ig'])
            df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
            for col in ['open', 'high', 'low', 'close', 'vol']: df[col] = df[col].astype(float)
            
            # Find peak price
            peak_idx = df['high'].idxmax()
            peak_price = df.loc[peak_idx, 'high']
            peak_time = df.loc[peak_idx, 'open_time']
            
            # Post-peak candles
            post_df = df.loc[peak_idx:].copy().reset_index(drop=True)
            
            # Simulate Entry at Strategy 2 Trigger:
            # 15m/5m breaks below local swing low (approx 5% from peak)
            entry_row = post_df[post_df['close'] <= peak_price * 0.93] # -7% breakdown confirmation
            if len(entry_row) > 0:
                entry_idx = entry_row.index[0]
                entry_price = entry_row.iloc[0]['close']
                entry_time = entry_row.iloc[0]['open_time']
                
                # Check performance 4h (48 bars), 12h (144 bars), 24h (288 bars)
                p_4h = post_df.iloc[min(entry_idx + 48, len(post_df)-1)]['close']
                p_12h = post_df.iloc[min(entry_idx + 144, len(post_df)-1)]['close']
                p_24h = post_df.iloc[min(entry_idx + 288, len(post_df)-1)]['close']
                
                min_price_after = post_df.iloc[entry_idx:]['low'].min()
                max_price_after = post_df.iloc[entry_idx:]['high'].max() # MAE (drawdown against short)
                
                ret_short_4h = (entry_price - p_4h) / entry_price * 100
                ret_short_12h = (entry_price - p_12h) / entry_price * 100
                ret_short_24h = (entry_price - p_24h) / entry_price * 100
                max_profit = (entry_price - min_price_after) / entry_price * 100
                max_drawdown = (max_price_after - entry_price) / entry_price * 100
                
                alt_results.append({
                    'Event': ev['name'],
                    'Peak Price': f"${peak_price:.2f}",
                    'Entry Price': f"${entry_price:.2f}",
                    'Min Price': f"${min_price_after:.2f}",
                    'Short Ret 4h': f"{ret_short_4h:+.1f}%",
                    'Short Ret 12h': f"{ret_short_12h:+.1f}%",
                    'Short Ret 24h': f"{ret_short_24h:+.1f}%",
                    'Max Gain': f"{max_profit:+.1f}%",
                    'Max DD': f"{max_drawdown:.1f}%",
                    'Win': 'WIN' if ret_short_24h > 0 else 'LOSS',
                    'num_24h': ret_short_24h
                })
    except Exception as e:
        print(f"Error {sym}: {e}")

df_alt_res = pd.DataFrame(alt_results)
print(df_alt_res[['Event', 'Peak Price', 'Entry Price', 'Min Price', 'Short Ret 4h', 'Short Ret 12h', 'Short Ret 24h', 'Max Gain', 'Max DD', 'Win']].to_string(index=False))
if len(df_alt_res) > 0:
    print(f"\nExtreme Altcoin Short Win Rate (24h): {(df_alt_res['num_24h'] > 0).mean()*100:.1f}%")
    print(f"Extreme Altcoin Mean 24h Short Return: {df_alt_res['num_24h'].mean():+.1f}%")

# -------------------------------------------------------------
# Part 2: Bitcoin & Ethereum (2023-2026 Analysis)
# -------------------------------------------------------------
print("\n" + "="*70)
print("Part 2: Bitcoin (BTC) & Ethereum (ETH) - Applying Negative Funding Strategy")
print("="*70)

btc_4h = pd.read_parquet('data/BTCUSDT_4h_2020_2026.parquet')
eth_4h = pd.read_parquet('data/ETHUSDT_4h_2020_2026.parquet')
funding_df = pd.read_parquet('data/binance_funding_8h.parquet')
funding_df.index = funding_df.index.tz_localize(None)

btc_df = btc_4h[['open', 'high', 'low', 'close', 'volume']].merge(
    funding_df[['BTCUSDT']].rename(columns={'BTCUSDT': 'fundingRate'}), 
    left_index=True, right_index=True, how='left'
).ffill()

eth_df = eth_4h[['open', 'high', 'low', 'close', 'volume']].merge(
    funding_df[['ETHUSDT']].rename(columns={'ETHUSDT': 'fundingRate'}), 
    left_index=True, right_index=True, how='left'
).ffill()

# Filter 2023-2026
btc_test = btc_df[btc_df.index >= '2023-01-01'].copy()
eth_test = eth_df[eth_df.index >= '2023-01-01'].copy()

# Forward returns: Short return = -(Price_fwd / Price - 1)
btc_test['short_ret_24h'] = -(btc_test['close'].shift(-6) / btc_test['close'] - 1.0) * 100
btc_test['short_ret_7d'] = -(btc_test['close'].shift(-42) / btc_test['close'] - 1.0) * 100
btc_test['long_ret_24h'] = (btc_test['close'].shift(-6) / btc_test['close'] - 1.0) * 100
btc_test['long_ret_7d'] = (btc_test['close'].shift(-42) / btc_test['close'] - 1.0) * 100
btc_test['prior_24h_ret'] = (btc_test['close'] / btc_test['close'].shift(6) - 1.0) * 100

eth_test['short_ret_24h'] = -(eth_test['close'].shift(-6) / eth_test['close'] - 1.0) * 100
eth_test['short_ret_7d'] = -(eth_test['close'].shift(-42) / eth_test['close'] - 1.0) * 100
eth_test['long_ret_24h'] = (eth_test['close'].shift(-6) / eth_test['close'] - 1.0) * 100
eth_test['long_ret_7d'] = (eth_test['close'].shift(-42) / eth_test['close'] - 1.0) * 100
eth_test['prior_24h_ret'] = (eth_test['close'] / eth_test['close'].shift(6) - 1.0) * 100

# When BTC/ETH funding is negative (< 0)
btc_neg = btc_test[btc_test['fundingRate'] < 0]
eth_neg = eth_test[eth_test['fundingRate'] < 0]

print(f"\n[BTC Negative Funding Events (N = {len(btc_neg)})]")
print(f"Prior 24h Price Move (前24h走势): {btc_neg['prior_24h_ret'].mean():+.2f}%  <-- Notice: It is already in a DUMP!")
print(f"SHORT Win Rate (24h 做空胜率): {(btc_neg['short_ret_24h'] > 0).mean()*100:.1f}%")
print(f"SHORT Mean Return (24h 做空均值): {btc_neg['short_ret_24h'].mean():+.2f}%")
print(f"SHORT Win Rate (7d 做空胜率): {(btc_neg['short_ret_7d'] > 0).mean()*100:.1f}%")
print(f"SHORT Mean Return (7d 做空均值): {btc_neg['short_ret_7d'].mean():+.2f}%")
print(f"--> If you LONG instead (反向做多 7d 均值收益): {btc_neg['long_ret_7d'].mean():+.2f}% (胜率: {(btc_neg['long_ret_7d'] > 0).mean()*100:.1f}%)")

print(f"\n[ETH Negative Funding Events (N = {len(eth_neg)})]")
print(f"Prior 24h Price Move (前24h走势): {eth_neg['prior_24h_ret'].mean():+.2f}%  <-- Already in a DUMP!")
print(f"SHORT Win Rate (24h 做空胜率): {(eth_neg['short_ret_24h'] > 0).mean()*100:.1f}%")
print(f"SHORT Mean Return (24h 做空均值): {eth_neg['short_ret_24h'].mean():+.2f}%")
print(f"SHORT Win Rate (7d 做空胜率): {(eth_neg['short_ret_7d'] > 0).mean()*100:.1f}%")
print(f"SHORT Mean Return (7d 做空均值): {eth_neg['short_ret_7d'].mean():+.2f}%")
print(f"--> If you LONG instead (反向做多 7d 均值收益): {eth_neg['long_ret_7d'].mean():+.2f}% (胜率: {(eth_neg['long_ret_7d'] > 0).mean()*100:.1f}%)")
