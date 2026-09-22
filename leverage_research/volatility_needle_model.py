# -*- coding: utf-8 -*-
"""
Volatility & Micro-Needle Risk Prediction Model (波动率与微观防插针量化预测模型)
Author: Antigravity Quantitative Research Team

Mathematical Foundations:
1. Parkinson Realized Volatility:
   sigma_P = sqrt( ln(H/L)^2 / (4 * ln(2)) )
   Vol_Ratio = EMA_5(sigma_P) / (EMA_30(sigma_P) + eps)
   Identifies explosive volatility shocks (Vol_Ratio > 1.25) vs compressed corridors (Vol_Ratio <= 1.05).

2. Micro-Wick Needle Ratio (Pin Bar / Stop Sweep Index):
   Wick_Ratio = ((H - L) - |C - O|) / max(H - L, eps)
   Lower_Wick_Ratio = (min(O, C) - L) / max(H - L, eps)  # Sweeps Long stop loss
   Upper_Wick_Ratio = (H - max(O, C)) / max(H - L, eps)  # Sweeps Short stop loss
   Wick_MA_5 = SMA_5(Wick_Ratio)

3. ATR Squeeze Expansion Ratio:
   ATR_Ratio = ATR_14 / (SMA_50(ATR_14) + eps)

4. Clean Corridor Composite Score (tau_vol in [0, 1]):
   tau_vol measures how "clean, orderly, and needle-free" the current volatility regime is.
   High score (>= 0.65) indicates low needle hazard, ideal for 100X tight-stop sniper entries.
   Low score (< 0.65) triggers automatic gate veto (BLOCKED).
"""

import numpy as np
import pandas as pd
import numba


@numba.njit(fastmath=True)
def compute_parkinson_volatility_nb(highs, lows):
    """
    Computes bar-by-bar Parkinson realized volatility.
    """
    n = len(highs)
    sigma_p = np.zeros(n, dtype=np.float64)
    factor = 1.0 / (4.0 * np.log(2.0))
    for i in range(n):
        h = highs[i]
        l = lows[i]
        if l > 0 and h >= l:
            log_hl = np.log(h / l)
            sigma_p[i] = np.sqrt(factor * log_hl * log_hl)
        else:
            sigma_p[i] = 0.0
    return sigma_p


@numba.njit(fastmath=True)
def compute_wick_ratios_nb(opens, highs, lows, closes):
    """
    Computes total wick ratio, lower wick (down-needle) ratio, and upper wick (up-needle) ratio.
    """
    n = len(closes)
    wick_ratio = np.zeros(n, dtype=np.float64)
    lower_wick = np.zeros(n, dtype=np.float64)
    upper_wick = np.zeros(n, dtype=np.float64)
    
    for i in range(n):
        o = opens[i]
        h = highs[i]
        l = lows[i]
        c = closes[i]
        rng = h - l
        if rng > 1e-8:
            body = abs(c - o)
            wick_ratio[i] = (rng - body) / rng
            lower_wick[i] = (min(o, c) - l) / rng
            upper_wick[i] = (h - max(o, c)) / rng
        else:
            wick_ratio[i] = 0.0
            lower_wick[i] = 0.0
            upper_wick[i] = 0.0
            
    return wick_ratio, lower_wick, upper_wick


def compute_volatility_needle_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Appends volatility and micro-needle risk features to the input DataFrame.
    Expects columns: 'open', 'high', 'low', 'close'
    """
    opens = df['open'].values.astype(np.float64)
    highs = df['high'].values.astype(np.float64)
    lows = df['low'].values.astype(np.float64)
    closes = df['close'].values.astype(np.float64)
    
    # 1. Parkinson Realized Volatility
    sigma_p = compute_parkinson_volatility_nb(highs, lows)
    df['sigma_parkinson'] = sigma_p
    
    # Short-term (5-period) vs medium-term (30-period) Parkinson Volatility
    s_p = pd.Series(sigma_p, index=df.index)
    sigma_fast = s_p.ewm(span=5).mean()
    sigma_slow = s_p.ewm(span=30).mean()
    vol_ratio = (sigma_fast / (sigma_slow + 1e-8)).clip(0.0, 5.0)
    df['vol_expansion_ratio'] = vol_ratio
    
    # 2. Wick / Needle Pin Bar Ratios
    wick_ratio, lower_wick, upper_wick = compute_wick_ratios_nb(opens, highs, lows, closes)
    df['wick_ratio'] = wick_ratio
    df['lower_wick_ratio'] = lower_wick
    df['upper_wick_ratio'] = upper_wick
    
    # Rolling wick moving averages
    df['wick_ma5'] = pd.Series(wick_ratio, index=df.index).rolling(window=5, min_periods=1).mean()
    df['lower_wick_ma3'] = pd.Series(lower_wick, index=df.index).rolling(window=3, min_periods=1).mean()
    df['upper_wick_ma3'] = pd.Series(upper_wick, index=df.index).rolling(window=3, min_periods=1).mean()
    
    # 3. ATR Squeeze Expansion Ratio
    tr = np.maximum(
        highs - lows,
        np.maximum(
            np.abs(highs - np.roll(closes, 1)),
            np.abs(lows - np.roll(closes, 1))
        )
    )
    tr[0] = highs[0] - lows[0]
    atr14 = pd.Series(tr, index=df.index).ewm(span=14).mean() / closes
    atr_ma50 = atr14.rolling(window=50, min_periods=10).mean()
    atr_ratio = (atr14 / (atr_ma50 + 1e-8)).clip(0.0, 4.0)
    df['atr_ratio'] = atr_ratio
    
    # 4. Clean Corridor Composite Score (tau_vol)
    # Higher score = tranquil, orderly oscillation corridor with minimal needle sweep hazard
    # Decreases when volatility is exploding (vol_ratio > 1.05) or needles are frequent (wick_ma5 > 0.35)
    penalty_vol = 0.40 * np.tanh(np.maximum(vol_ratio - 1.05, 0.0) * 3.0)
    penalty_wick = 0.40 * np.tanh(np.maximum(df['wick_ma5'] - 0.35, 0.0) * 3.5)
    penalty_atr = 0.20 * np.tanh(np.maximum(atr_ratio - 1.20, 0.0) * 2.5)
    
    tau_vol_base = np.clip(1.0 - (penalty_vol + penalty_wick + penalty_atr), 0.0, 1.0)
    df['tau_vol'] = tau_vol_base
    
    # Directional Needle Hazards:
    # If lower wick spikes, danger of stop sweep for longs
    # If upper wick spikes, danger of stop sweep for shorts
    hazard_long = np.tanh(np.maximum(df['lower_wick_ma3'] - 0.40, 0.0) * 4.0)
    hazard_short = np.tanh(np.maximum(df['upper_wick_ma3'] - 0.40, 0.0) * 4.0)
    
    df['hazard_long'] = hazard_long
    df['hazard_short'] = hazard_short
    
    df['tau_vol_long'] = np.clip(tau_vol_base * (1.0 - hazard_long * 0.70), 0.0, 1.0)
    df['tau_vol_short'] = np.clip(tau_vol_base * (1.0 - hazard_short * 0.70), 0.0, 1.0)
    
    # Binary regime flags
    df['is_clean_corridor'] = (df['tau_vol'] >= 0.65).astype(np.int32)
    df['is_needle_hazard'] = ((df['hazard_long'] > 0.30) | (df['hazard_short'] > 0.30)).astype(np.int32)
    
    return df


if __name__ == "__main__":
    test_path = r"D:\Convertible_Bond_data\crypto_data\history\futures_1m\ETHUSDT_2026_09_01_to_09_22.parquet"
    print(f"Testing Volatility & Needle Model on {test_path}...")
    df_test = pd.read_parquet(test_path)
    df_test = df_test.set_index('datetime')
    df_res = compute_volatility_needle_features(df_test)
    
    print("\nVolatility & Needle Model Feature Summary:")
    print(df_res[['sigma_parkinson', 'vol_expansion_ratio', 'wick_ratio', 'wick_ma5', 'tau_vol', 'tau_vol_long', 'tau_vol_short']].describe())
    clean_pct = (df_res['tau_vol'] >= 0.65).mean() * 100.0
    print(f"\nProportion of Clean Corridor Bars (tau_vol >= 0.65): {clean_pct:.2f}%")
    print(f"Proportion of Needle Hazard Bars: {(df_res['is_needle_hazard'] == 1).mean() * 100.0:.2f}%")
