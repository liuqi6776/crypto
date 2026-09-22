# -*- coding: utf-8 -*-
"""
Multi-Asset 1-Second Streamer & Micro-Momentum Engine
四大资产 (BTC, ETH, SOL, BNB) 1秒高频微观动量与实时K线引擎
- Fetches / streams 1s bars across BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT
- Maintains rolling 300s / 1800s buffer for each asset
- Computes real-time micro-momentum, micro-VWAP, and micro-volatility
"""

import time
import json
import urllib.request
from typing import Dict, List, Optional
import numpy as np
import pandas as pd


SYMBOLS_4 = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]


class MultiAsset1sStreamer:
    """
    High-frequency 1-second data streamer & feature generator for BTC, ETH, SOL, BNB
    """
    def __init__(self, symbols: List[str] = None, buffer_size: int = 600):
        self.symbols = symbols or SYMBOLS_4
        self.buffer_size = buffer_size
        self.buffers: Dict[str, pd.DataFrame] = {}
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    def fetch_latest_1s_bars(self, symbol: str, limit: int = 120) -> pd.DataFrame:
        """
        Fetches the latest 1s bars from Binance Spot API
        """
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1s&limit={limit}"
        req = urllib.request.Request(url, headers=self.headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        
        # Schema: [Open time, Open, High, Low, Close, Volume, Close time, Quote asset volume, Number of trades, Taker buy base, Taker buy quote, Ignore]
        cols = ['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time',
                'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore']
        df = pd.DataFrame(data, columns=cols)
        
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'quote_volume', 'taker_buy_base', 'taker_buy_quote']
        for c in numeric_cols:
            df[c] = df[c].astype(float)
        
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
        df['symbol'] = symbol
        return df

    def sync_all_symbols(self, limit: int = 120) -> Dict[str, pd.DataFrame]:
        """
        Synchronously fetches 1s bars across all 4 target symbols
        """
        t0 = time.perf_counter()
        results = {}
        for sym in self.symbols:
            try:
                df = self.fetch_latest_1s_bars(sym, limit=limit)
                df = self.compute_micro_features(df)
                self.buffers[sym] = df
                results[sym] = df
            except Exception as e:
                print(f"Warning: Failed to fetch 1s bars for {sym}: {e}")
        
        elapsed_ms = (time.perf_counter() - t0) * 1000
        # print(f"Synced 4 assets 1s bars in {elapsed_ms:.1f}ms")
        return results

    @staticmethod
    def compute_micro_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        Computes 1-second micro-structure indicators:
        - 5s, 15s, 60s micro-momentum (% price change)
        - Micro-VWAP and price deviation
        - 1s Volatility (rolling std of log returns)
        - Taker Buy Imbalance (Order Flow Pressure)
        """
        df = df.copy()
        c = df['close']
        v = df['volume']
        qv = df['quote_volume']
        
        # 1s log returns
        log_ret = np.log(c / c.shift(1).replace(0, np.nan)).fillna(0)
        
        # Momentum slopes
        df['mom_5s'] = (c / c.shift(5) - 1.0) * 100.0
        df['mom_15s'] = (c / c.shift(15) - 1.0) * 100.0
        df['mom_60s'] = (c / c.shift(60) - 1.0) * 100.0
        
        # Micro-VWAP
        cum_qv = qv.rolling(window=60, min_periods=5).sum()
        cum_vol = v.rolling(window=60, min_periods=5).sum()
        df['micro_vwap'] = cum_qv / cum_vol.replace(0, np.nan)
        df['vwap_dev'] = (c - df['micro_vwap']) / df['micro_vwap'] * 100.0
        
        # Micro-volatility
        df['micro_vol_30s'] = log_ret.rolling(window=30, min_periods=5).std() * np.sqrt(3600) * 100.0
        
        # Order-flow taker buy ratio
        taker_vol = df['taker_buy_base']
        df['order_imbalance'] = (taker_vol * 2.0 - v) / v.replace(0, np.nan)
        
        return df


if __name__ == "__main__":
    streamer = MultiAsset1sStreamer()
    print("Testing 1-second streaming across BTC, ETH, SOL, BNB...")
    t0 = time.perf_counter()
    data = streamer.sync_all_symbols(limit=60)
    t_el = (time.perf_counter() - t0) * 1000
    
    print(f"\nSuccessfully fetched 4 assets in {t_el:.2f} ms:")
    for sym, df in data.items():
        latest = df.iloc[-1]
        print(f"[{sym}] Close: {latest['close']:.2f} | 5s Mom: {latest['mom_5s']:+.3f}% | 60s Mom: {latest['mom_60s']:+.3f}% | Imbal: {latest['order_imbalance']:+.2f}")
