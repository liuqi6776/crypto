# -*- coding: utf-8 -*-
"""
Multi-Timeframe (1s, 1m, 5m) Stable Rise Feature & Labeling Engine
ETH 多时间尺度 (1s, 1m, 5m) 稳定上涨特征工程与标签构建引擎

Features:
1. 5m Macro Layer:
   - Structural Bull Trend (EMA12 > EMA26 > EMA50)
   - Volatility Squeeze (Bollinger Bandwidth contraction)
2. 1m Momentum & Volatility Layer:
   - Expanding MACD Histogram (Hist > 0 and Hist > Hist[t-1])
   - Low-volatility compression (20-bar ATR / Close <= 0.18%)
   - Volume Momentum (Up-volume > Down-volume)
3. 1s Microstructure Layer:
   - Micro-velocity (5s / 15s) and Order Book Imbalance (OBI) proxy
4. Multi-Target Stable Rise Labels:
   - For targets U in [1%, 2%, 3%, 4%, 5%]:
     Label = 1 if (Max High - P0)/P0 >= U BEFORE (P0 - Min Low)/P0 >= MAE_limit
"""

import os
import sys
import numpy as np
import pandas as pd
import numba


@numba.njit(parallel=True)
def label_stable_rise_fast(closes, highs, lows, targets, mae_limit, max_horizon=720):
    """
    Computes ground-truth stable rise labels for multiple targets.
    Returns: labels of shape (N, len(targets)) with values 0 or 1.
    """
    n = len(closes)
    n_targets = len(targets)
    labels = np.zeros((n, n_targets), dtype=np.int32)
    
    valid_len = n - max_horizon
    for i in numba.prange(valid_len):
        p0 = closes[i]
        
        for t in range(n_targets):
            target = targets[t]
            hit = 0
            for k in range(1, max_horizon + 1):
                cur_low = lows[i + k]
                cur_high = highs[i + k]
                
                # Check adverse limit breach
                if (p0 - cur_low) / p0 >= mae_limit:
                    hit = 0
                    break
                # Check favorable target reach
                if (cur_high - p0) / p0 >= target:
                    hit = 1
                    break
            labels[i, t] = hit
            
    return labels


def compute_multi_timeframe_features(df_1m):
    """
    Computes multi-timeframe signals on 1m OHLCV dataframe.
    """
    df = df_1m.copy()
    
    # ---------------------------------------------------------
    # 1. 1m Momentum & Realized Volatility
    # ---------------------------------------------------------
    ema12_1m = df['close'].ewm(span=12).mean()
    ema26_1m = df['close'].ewm(span=26).mean()
    macd_1m = ema12_1m - ema26_1m
    macd_sig_1m = macd_1m.ewm(span=9).mean()
    macd_hist_1m = macd_1m - macd_sig_1m
    
    df['macd_hist_1m'] = macd_hist_1m
    df['macd_expanding'] = ((macd_hist_1m > 0) & (macd_hist_1m > macd_hist_1m.shift(1))).astype(np.int32)
    
    # Low-volatility compression filter: ATR / Close
    hl_range = df['high'] - df['low']
    df['atr20_pct'] = hl_range.rolling(20, min_periods=5).mean() / df['close']
    df['is_vol_compressed'] = (df['atr20_pct'] <= 0.0020).astype(np.int32) # <= 0.20%
    
    # 1m Relative Volume
    vol_ma = df['volume'].rolling(30, min_periods=5).mean()
    df['rel_vol'] = df['volume'] / np.maximum(vol_ma, 1e-6)
    
    # ---------------------------------------------------------
    # 2. 5m Macro Structural Trend
    # ---------------------------------------------------------
    df_5m = df[['open', 'high', 'low', 'close', 'volume']].resample('5min').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
    }).dropna()
    
    ema12_5m = df_5m['close'].ewm(span=12).mean()
    ema26_5m = df_5m['close'].ewm(span=26).mean()
    ema50_5m = df_5m['close'].ewm(span=50).mean()
    
    df_5m['bull_trend_5m'] = ((ema12_5m > ema26_5m) & (ema26_5m > ema50_5m)).astype(np.int32)
    
    # 5m Bollinger Band Squeeze
    roll_mean_5m = df_5m['close'].rolling(20, min_periods=5).mean()
    roll_std_5m = df_5m['close'].rolling(20, min_periods=5).std()
    bb_width_5m = (roll_std_5m * 4.0) / roll_mean_5m
    df_5m['is_bb_squeeze_5m'] = (bb_width_5m < bb_width_5m.rolling(50, min_periods=10).quantile(0.35)).astype(np.int32)
    
    # Join 5m features back to 1m
    df = df.join(df_5m[['bull_trend_5m', 'is_bb_squeeze_5m']], how='left')
    df['bull_trend_5m'] = df['bull_trend_5m'].ffill().fillna(0).astype(np.int32)
    df['is_bb_squeeze_5m'] = df['is_bb_squeeze_5m'].ffill().fillna(0).astype(np.int32)
    
    # ---------------------------------------------------------
    # 3. Microstructure Order Flow Proxy (1s alignment)
    # ---------------------------------------------------------
    # Intraday Close position in bar (proxy for taker buy defense)
    close_loc = (df['close'] - df['low']) / np.maximum(hl_range, 1e-6)
    df['micro_buy_wall_defense'] = (close_loc >= 0.65).astype(np.int32)
    
    # Composite Multi-Timeframe Score [0 to 1]
    df['multi_scale_score'] = (
        0.35 * df['bull_trend_5m'] +
        0.25 * df['macd_expanding'] +
        0.20 * df['is_vol_compressed'] +
        0.20 * df['micro_buy_wall_defense']
    )
    
    return df
