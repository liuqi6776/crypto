"""
Enhanced Feature Engineering Engine for CryptoLeverageTransformer.
Audits 30 existing features and adds 8 high-signal features for Direction & Volatility.
"""

import os
import sys
import numpy as np
import pandas as pd
import numba

@numba.njit
def compute_garman_klass_vol_nb(opens, highs, lows, closes, period=15):
    n = len(closes)
    gk_vol = np.zeros(n, dtype=np.float32)
    # Garman-Klass formulation:
    # 0.5 * ln(H/L)^2 - (2*ln(2) - 1) * ln(C/O)^2
    c1 = 0.5
    c2 = 2.0 * np.log(2.0) - 1.0

    raw_var = np.zeros(n, dtype=np.float64)
    for i in range(n):
        o = opens[i]
        h = highs[i]
        l = lows[i]
        c = closes[i]
        if o <= 0 or h <= 0 or l <= 0 or c <= 0:
            continue
        term1 = np.log(h / l) ** 2
        term2 = np.log(c / o) ** 2
        raw_var[i] = c1 * term1 - c2 * term2

    # Rolling mean
    window_sum = 0.0
    for i in range(n):
        window_sum += raw_var[i]
        if i >= period:
            window_sum -= raw_var[i - period]
            mean_var = max(0.0, window_sum / period)
            gk_vol[i] = np.sqrt(mean_var)
        else:
            mean_var = max(0.0, window_sum / (i + 1))
            gk_vol[i] = np.sqrt(mean_var)

    return gk_vol

def compute_enhanced_features(df: pd.DataFrame, btc_df: pd.DataFrame = None, sol_df: pd.DataFrame = None):
    """
    Computes 38 total features per asset:
    - 30 existing features
    - 8 newly engineered features (4 Direction + 4 Volatility/Needle)
    """
    from build_2026_05_split_dataset import compute_enhanced_asset_features
    # 1. Base 30 features
    base_feat, base_names = compute_enhanced_asset_features(df, btc_df=btc_df)

    feat = base_feat.copy()
    c = df['close'].astype(np.float64)
    o = df['open'].astype(np.float64)
    h = df['high'].astype(np.float64)
    l = df['low'].astype(np.float64)
    v = df['volume'].astype(np.float64)
    tb_v = df['taker_buy_volume'].astype(np.float64)
    qv = df['quote_volume'].astype(np.float64)
    trades = df['trades_count'].astype(np.float64).replace(0, 1.0)

    # 2. Add 4 Direction Features
    # Feature 31: CVD Divergence (15m)
    net_taker = tb_v - (v - tb_v)
    cvd_15m = net_taker.rolling(15).sum() / (v.rolling(15).sum() + 1e-6)
    ret_15m = c.pct_change(15).fillna(0.0)
    # Divergence: When price drops but CVD rises, absorption -> Bullish (+1)
    # When price rises but CVD drops, exhaustion -> Bearish (-1)
    feat['cvd_divergence_15m'] = (cvd_15m - np.tanh(ret_15m * 100.0)).clip(-2.0, 2.0).fillna(0.0).astype(np.float32)

    # Feature 32: Funding Velocity / Basis Proxy (1h)
    # Fast acceleration of VWAP deviation indicates aggressive premium expansion
    vwap_1h = (qv.rolling(60).sum() / (v.rolling(60).sum() + 1e-6)).bfill()
    dist_vwap_1h = (c - vwap_1h) / vwap_1h
    feat['funding_velocity_1h'] = (dist_vwap_1h - dist_vwap_1h.shift(15).fillna(0.0)).clip(-0.05, 0.05).fillna(0.0).astype(np.float32)

    # Feature 33: Distance to Daily Point of Control (POC) Proxy
    # Approximates daily POC via 24h volume-weighted price mode
    cum_pv = qv.rolling(1440, min_periods=60).sum()
    cum_v = v.rolling(1440, min_periods=60).sum() + 1e-6
    poc_proxy = (cum_pv / cum_v).bfill()
    feat['dist_poc_daily'] = ((c - poc_proxy) / poc_proxy).clip(-0.15, 0.15).fillna(0.0).astype(np.float32)

    # Feature 34: Cross-Asset Lead-Lag vs SOL
    if sol_df is not None:
        sol_c = sol_df['close'].astype(np.float64)
        sol_ret_5m = sol_c.pct_change(5).fillna(0.0)
        feat['cross_lead_lag_sol_5m'] = (sol_ret_5m - feat['ret_5m']).clip(-0.10, 0.10).fillna(0.0).astype(np.float32)
    else:
        feat['cross_lead_lag_sol_5m'] = np.zeros(len(df), dtype=np.float32)

    # 3. Add 4 Volatility / Needle Features
    # Feature 35: Spread Spike Ratio (Liquidity Evaporation Detector)
    hl_spread = feat['hl_spread']
    spread_ma30 = hl_spread.rolling(30, min_periods=5).mean().replace(0, np.nan).bfill()
    feat['spread_spike_ratio'] = (hl_spread / spread_ma30).clip(0.1, 10.0).fillna(1.0).astype(np.float32)

    # Feature 36: Depth Imbalance Ratio (15m smoothed)
    net_taker_15m = net_taker.rolling(15).sum()
    vol_15m = v.rolling(15).sum() + 1e-6
    feat['depth_imbalance_ratio'] = (net_taker_15m / vol_15m).clip(-1.0, 1.0).fillna(0.0).astype(np.float32)

    # Feature 37: Whale Trade Burst Intensity (Top trade size spikes)
    avg_trade_size = qv / trades
    trade_size_ma60 = avg_trade_size.rolling(60, min_periods=10).mean().replace(0, np.nan).bfill()
    feat['whale_burst_intensity'] = (avg_trade_size / trade_size_ma60).clip(0.1, 15.0).fillna(1.0).astype(np.float32)

    # Feature 38: Garman-Klass Volatility Jump Ratio
    gk_vol = compute_garman_klass_vol_nb(o.values, h.values, l.values, c.values, period=15)
    parkinson = feat['parkinson_vol_15m'].values
    ratio_gk = (gk_vol / (parkinson + 1e-6))
    feat['garman_klass_ratio'] = np.clip(ratio_gk, 0.1, 5.0).astype(np.float32)

    # Clean NaNs and Infs
    feat = feat.replace([np.inf, -np.inf], 0.0).fillna(0.0)
    col_names = feat.columns.tolist()
    return feat, col_names

def main():
    print("=" * 80)
    print("  TESTING ENHANCED FEATURE ENGINE (38 FEATURES)")
    print("=" * 80)

    # Load 1 asset Parquet
    parquet_path = r"D:\Convertible_Bond_data\crypto_data\history\futures_1m\ETHUSDT_futures_1m_continuous.parquet"
    if not os.path.exists(parquet_path):
        print(f"Parquet not found: {parquet_path}")
        return

    print(f"Loading sample data from {parquet_path}...")
    df = pd.read_parquet(parquet_path)
    df_sample = df.iloc[-10000:].copy() # last 10,000 bars
    print(f"Sample length: {len(df_sample):,} bars ({df_sample.index[0]} -> {df_sample.index[-1]})")

    feat, cols = compute_enhanced_features(df_sample)
    print(f"\n[OK] Computed {len(cols)} features successfully!")
    print("\nFeature Column Names:")
    for idx, col in enumerate(cols):
        flag = " [NEW!]" if idx >= 30 else ""
        print(f"  {idx+1:2d}. {col:28s} (min: {feat[col].min():8.4f}, max: {feat[col].max():8.4f}){flag}")

    out_csv = r"c:\Users\liuqi\crypto\leverage_research\charts\sample_enhanced_features.csv"
    feat.tail(50).to_csv(out_csv)
    print(f"\nSaved sample output to: {out_csv}")

if __name__ == '__main__':
    main()
