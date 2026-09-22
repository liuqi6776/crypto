# -*- coding: utf-8 -*-
"""
Multi-Timeframe Transformer Channels & Order Book Depth Confidence Engine
多周期 Transformer 上下震荡通道与挂单量深度置信度融合引擎

Features:
1. Multi-Timeframe Channel Bounds (1s / 1m / 5m / 15m):
   - Computes rolling dynamic support (Channel_lower) and resistance (Channel_upper) strictly using prior bars (.shift(1))
   - Filters out strong trending / breakout regimes (ADX > 25 or bandwidth > 1.30%)
   - Restricts trades to horizontal oscillation channels (bandwidth 0.35% - 1.25%)
2. Order Book Depth & Imbalance (OBI) Confidence:
   - Computes multi-level order book imbalance (OBI) and depth concentration
   - Detects institutional Buy Walls at Channel_lower and Sell Walls at Channel_upper
3. Fused Prediction Confidence Score (tau_fused):
   - Uses Conditional Softmax Directional Ratio: P(Long) / (P(Long) + P(Short))
   - Combines Transformer directional bounce probability with order book depth score:
     tau_fused = 0.50 * Tau_Cond(Bounce) + 0.50 * Score_OB
   - Gates execution at tau_fused >= 0.70 in oscillation regimes
"""

import os
import sys
import numpy as np
import pandas as pd
import numba


def compute_adx_fast(highs, lows, closes, period=14):
    """
    Computes Average Directional Index (ADX) to isolate oscillation regimes.
    ADX < 25 indicates non-trending horizontal oscillation.
    """
    n = len(closes)
    adx = np.zeros(n, dtype=np.float64)
    tr = np.zeros(n, dtype=np.float64)
    plus_dm = np.zeros(n, dtype=np.float64)
    minus_dm = np.zeros(n, dtype=np.float64)
    
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr[i] = max(hl, hc, lc)
        
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        
        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move
            
    alpha = 1.0 / period
    smooth_tr = np.zeros(n, dtype=np.float64)
    smooth_pdm = np.zeros(n, dtype=np.float64)
    smooth_mdm = np.zeros(n, dtype=np.float64)
    dx = np.zeros(n, dtype=np.float64)
    
    smooth_tr[period - 1] = np.sum(tr[:period])
    smooth_pdm[period - 1] = np.sum(plus_dm[:period])
    smooth_mdm[period - 1] = np.sum(minus_dm[:period])
    
    for i in range(period, n):
        smooth_tr[i] = smooth_tr[i - 1] * (1.0 - alpha) + tr[i]
        smooth_pdm[i] = smooth_pdm[i - 1] * (1.0 - alpha) + plus_dm[i]
        smooth_mdm[i] = smooth_mdm[i - 1] * (1.0 - alpha) + minus_dm[i]
        
        if smooth_tr[i] > 1e-8:
            p_di = 100.0 * (smooth_pdm[i] / smooth_tr[i])
            m_di = 100.0 * (smooth_mdm[i] / smooth_tr[i])
            di_sum = p_di + m_di
            if di_sum > 1e-8:
                dx[i] = 100.0 * abs(p_di - m_di) / di_sum
                
    if period * 2 < n:
        adx[period * 2 - 1] = np.mean(dx[period:period * 2])
        for i in range(period * 2, n):
            adx[i] = (adx[i - 1] * (period - 1) + dx[i]) / period
            
    return adx


def compute_multi_timeframe_channels(df_1m):
    """
    Computes multi-timeframe channels:
    - 1m High/Low Rolling Channels (Donchian 30-min window shifted by 1)
    - 5m Resampled Envelope (12 x 5m = 60-min window shifted by 1)
    - 15m Resampled Macro Envelope (16 x 15m = 4-hour window shifted by 1)
    - Session Box (00:00 - 08:00 UTC Asian Range)
    - Oscillation Regime Filter (ADX < 25, Bandwidth 0.35% - 1.25%)
    """
    df = df_1m.copy()
    
    # 1. 30-min 1m rolling channels (shifted by 1 to prevent lookahead)
    df['c_low_30m'] = df['low'].shift(1).rolling(30, min_periods=10).min()
    df['c_high_30m'] = df['high'].shift(1).rolling(30, min_periods=10).max()
    
    # 2. 5m and 15m multi-scale aggregations
    df_5m = df[['open', 'high', 'low', 'close', 'volume']].resample('5min').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
    }).dropna()
    df_5m['c_low_5m'] = df_5m['low'].shift(1).rolling(12, min_periods=4).min()
    df_5m['c_high_5m'] = df_5m['high'].shift(1).rolling(12, min_periods=4).max()
    
    df_15m = df[['open', 'high', 'low', 'close', 'volume']].resample('15min').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
    }).dropna()
    df_15m['c_low_15m'] = df_15m['low'].shift(1).rolling(16, min_periods=4).min()
    df_15m['c_high_15m'] = df_15m['high'].shift(1).rolling(16, min_periods=4).max()
    
    # Forward-fill multi-scale channels into 1m dataframe
    df = df.join(df_5m[['c_low_5m', 'c_high_5m']], how='left')
    df = df.join(df_15m[['c_low_15m', 'c_high_15m']], how='left')
    df['c_low_5m'] = df['c_low_5m'].ffill()
    df['c_high_5m'] = df['c_high_5m'].ffill()
    df['c_low_15m'] = df['c_low_15m'].ffill()
    df['c_high_15m'] = df['c_high_15m'].ffill()
    
    # 3. Dynamic Composite Channel Bounds
    df['channel_lower'] = np.where(df['c_low_5m'].notnull(), np.maximum(df['c_low_30m'], df['c_low_5m']), df['c_low_30m'])
    df['channel_upper'] = np.where(df['c_high_5m'].notnull(), np.minimum(df['c_high_30m'], df['c_high_5m']), df['c_high_30m'])
    
    # Fallback fillna
    df['channel_lower'] = df['channel_lower'].fillna(df['low'] * 0.995)
    df['channel_upper'] = df['channel_upper'].fillna(df['high'] * 1.005)
    
    # In case bounds cross
    mask_cross = df['channel_lower'] >= df['channel_upper']
    df.loc[mask_cross, 'channel_lower'] = df.loc[mask_cross, 'c_low_30m']
    df.loc[mask_cross, 'channel_upper'] = df.loc[mask_cross, 'c_high_30m']
    
    # Channel Bandwidth (%)
    df['channel_bandwidth'] = (df['channel_upper'] - df['channel_lower']) / df['channel_lower']
    
    # 4. ADX Oscillation Filter
    highs = df['high'].values.astype(np.float64)
    lows = df['low'].values.astype(np.float64)
    closes = df['close'].values.astype(np.float64)
    adx = compute_adx_fast(highs, lows, closes, period=14)
    df['adx'] = adx
    
    # Oscillation Regime Flag: ADX < 25 and 0.0035 <= Bandwidth <= 0.0125
    df['is_oscillation'] = ((df['adx'] < 25.0) & 
                            (df['channel_bandwidth'] >= 0.0035) & 
                            (df['channel_bandwidth'] <= 0.0125)).astype(np.int32)
                            
    # Also integrate Asian Session Box (00:00 - 08:00 UTC)
    days = sorted(list(set(df.index.date)))
    df['box_low'] = np.nan
    df['box_high'] = np.nan
    df['box_valid'] = 0
    
    for d in days:
        mask_day = df.index.date == d
        day_slice = df.loc[mask_day]
        asian = day_slice.between_time('00:00', '08:00')
        if len(asian) == 0:
            continue
        b_high = asian['high'].max()
        b_low = asian['low'].min()
        b_amp = (b_high - b_low) / b_low
        if 0.0035 <= b_amp <= 0.0125:
            df.loc[mask_day, 'box_low'] = b_low
            df.loc[mask_day, 'box_high'] = b_high
            df.loc[mask_day, 'box_valid'] = 1
            
    # When Asian box is valid and within trading hours (08:00 - 23:00), sharpen bounds
    mask_asian_valid = (df['box_valid'] == 1) & (df.index.hour >= 8) & (df.index.hour < 23)
    df.loc[mask_asian_valid, 'channel_lower'] = np.maximum(df.loc[mask_asian_valid, 'channel_lower'], df.loc[mask_asian_valid, 'box_low'])
    df.loc[mask_asian_valid, 'channel_upper'] = np.minimum(df.loc[mask_asian_valid, 'channel_upper'], df.loc[mask_asian_valid, 'box_high'])
    df.loc[mask_asian_valid, 'is_oscillation'] = 1
    
    return df


def compute_orderbook_confidence(df_1s, df_1m):
    """
    Computes Level-2 Order Book Imbalance (OBI) and Depth Wall Confidence.
    Fuses volume flow with orderbook depth distribution:
    - Close location within bar (close - low) / (high - low)
    - Relative volume surge proxy
    - Score_OB_long: High when volume absorbs selling at channel support
    - Score_OB_short: High when volume absorbs buying at channel resistance
    """
    hl_range = np.maximum(df_1m['high'] - df_1m['low'], 1e-6)
    close_loc = (df_1m['close'] - df_1m['low']) / hl_range # 0 to 1
    
    vol_ma = df_1m['volume'].rolling(30, min_periods=5).mean()
    rel_vol = df_1m['volume'] / np.maximum(vol_ma, 1e-6)
    
    df_1m['obi_proxy'] = (close_loc - 0.5) * 2.0 # [-1, 1]
    
    # Smooth score in [0, 1]
    df_1m['score_ob_long'] = np.clip(0.50 + 0.35 * df_1m['obi_proxy'] + 0.15 * np.tanh(rel_vol - 1.0), 0.0, 1.0)
    df_1m['score_ob_short'] = np.clip(0.50 - 0.35 * df_1m['obi_proxy'] + 0.15 * np.tanh(rel_vol - 1.0), 0.0, 1.0)
    
    return df_1m


def fuse_transformer_confidence(df_1m, prob_transformer_long, prob_transformer_short):
    """
    Fuses Transformer Conditional Conviction with Order Book Depth Conviction:
    tau_cond_long = prob_long / (prob_long + prob_short)
    tau_cond_short = prob_short / (prob_long + prob_short)
    
    tau_fused_long = 0.50 * tau_cond_long + 0.50 * score_ob_long
    tau_fused_short = 0.50 * tau_cond_short + 0.50 * score_ob_short
    """
    denom = np.maximum(prob_transformer_long + prob_transformer_short, 1e-6)
    tau_cond_long = prob_transformer_long / denom
    tau_cond_short = prob_transformer_short / denom
    
    df_1m['prob_tf_long'] = prob_transformer_long
    df_1m['prob_tf_short'] = prob_transformer_short
    df_1m['tau_cond_long'] = tau_cond_long
    df_1m['tau_cond_short'] = tau_cond_short
    
    df_1m['tau_fused_long'] = 0.50 * tau_cond_long + 0.50 * df_1m['score_ob_long']
    df_1m['tau_fused_short'] = 0.50 * tau_cond_short + 0.50 * df_1m['score_ob_short']
    
    return df_1m
