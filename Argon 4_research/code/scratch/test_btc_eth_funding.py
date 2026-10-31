import requests
import pandas as pd
import numpy as np
import datetime
import os

os.makedirs('scratch', exist_ok=True)

# 1. Let's verify what happens on BTC and ETH when funding rate is negative
# Load BTC and ETH from local parquets
btc_4h = pd.read_parquet('data/BTCUSDT_4h_2020_2026.parquet')
eth_4h = pd.read_parquet('data/ETHUSDT_4h_2020_2026.parquet')
funding_df = pd.read_parquet('data/binance_funding_8h.parquet')
funding_df.index = funding_df.index.tz_localize(None)

print("BTC 4h data:", len(btc_4h), "from", btc_4h.index.min(), "to", btc_4h.index.max())
print("ETH 4h data:", len(eth_4h), "from", eth_4h.index.min(), "to", eth_4h.index.max())

# Merge funding rates
btc_df = btc_4h[['open', 'high', 'low', 'close', 'volume']].copy()
btc_df = btc_df.merge(funding_df[['BTCUSDT']].rename(columns={'BTCUSDT': 'fundingRate'}), 
                       left_index=True, right_index=True, how='left')
btc_df['fundingRate'] = btc_df['fundingRate'].ffill()

eth_df = eth_4h[['open', 'high', 'low', 'close', 'volume']].copy()
eth_df = eth_df.merge(funding_df[['ETHUSDT']].rename(columns={'ETHUSDT': 'fundingRate'}), 
                       left_index=True, right_index=True, how='left')
eth_df['fundingRate'] = eth_df['fundingRate'].ffill()

# Look at 2023 to 2026
btc_recent = btc_df[btc_df.index >= '2023-01-01'].copy()
eth_recent = eth_df[eth_df.index >= '2023-01-01'].copy()

print(f"\nBTC records (2023-2026): {len(btc_recent)}")
print(f"BTC negative funding instances (< 0): {(btc_recent['fundingRate'] < 0).sum()} ({(btc_recent['fundingRate'] < 0).mean()*100:.1f}%)")
print(f"BTC deep negative instances (< -0.01%): {(btc_recent['fundingRate'] < -0.0001).sum()}")
print(f"BTC extreme negative instances (< -0.03%): {(btc_recent['fundingRate'] < -0.0003).sum()}")
print(f"BTC instances (< -0.1%): {(btc_recent['fundingRate'] < -0.001).sum()}")

print(f"\nETH records (2023-2026): {len(eth_recent)}")
print(f"ETH negative funding instances (< 0): {(eth_recent['fundingRate'] < 0).sum()} ({(eth_recent['fundingRate'] < 0).mean()*100:.1f}%)")
print(f"ETH deep negative instances (< -0.01%): {(eth_recent['fundingRate'] < -0.0001).sum()}")
print(f"ETH extreme negative instances (< -0.03%): {(eth_recent['fundingRate'] < -0.0003).sum()}")
print(f"ETH instances (< -0.1%): {(eth_recent['fundingRate'] < -0.001).sum()}")

# Forward returns for BTC when funding rate is negative vs positive
btc_recent['ret_fwd_24h'] = btc_recent['close'].shift(-6) / btc_recent['close'] - 1.0
btc_recent['ret_fwd_7d'] = btc_recent['close'].shift(-42) / btc_recent['close'] - 1.0
btc_recent['ret_prev_24h'] = btc_recent['close'] / btc_recent['close'].shift(6) - 1.0

# Negative funding events in BTC
neg_btc = btc_recent[btc_recent['fundingRate'] < -0.0001]
print("\n=== BTC when Funding Rate < -0.01% (Relative Negative Extreme for BTC) ===")
print(f"Sample count: {len(neg_btc)}")
print(f"Prior 24h return (前24h走势): {neg_btc['ret_prev_24h'].mean()*100:+.2f}%")
print(f"Next 24h return (次24h走势均值): {neg_btc['ret_fwd_24h'].mean()*100:+.2f}%")
print(f"Next 24h Win Rate (% Price Rises - 上涨概率): {(neg_btc['ret_fwd_24h'] > 0).mean()*100:.1f}%")
print(f"Next 7d return (次7天走势均值): {neg_btc['ret_fwd_7d'].mean()*100:+.2f}%")
print(f"Next 7d Win Rate (% Price Rises - 上涨概率): {(neg_btc['ret_fwd_7d'] > 0).mean()*100:.1f}%")
