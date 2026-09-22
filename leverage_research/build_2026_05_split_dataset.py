# -*- coding: utf-8 -*-
"""
Build Multi-Asset Dataset with Strict 2026/05 Temporal Split (2020/09 - 2026/09)
严格以 2026年5月1日 为时序切分边界的四币种全周期特征与标签张量构建引擎
- In-sample Train Period: 2020-09-14 to 2026-04-30 23:59:00 (~2.95M bars)
- Out-of-sample Test Period: 2026-05-01 00:00:00 to 2026-09-22 06:50:00 (~208k bars)
- Enhanced Features: Microstructure, OFI, BTC Lead-Lag, Beta Dislocation, Wick Needle Ratios, and Parkinson Volatility
"""

import os
import sys
import time
import argparse
import numpy as np
import pandas as pd
from typing import Dict, Tuple

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from crypto_leverage_transformer import label_excursions_and_optimal_barriers_numba
from volatility_needle_model import compute_parkinson_volatility_nb, compute_wick_ratios_nb

ASSETS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT']
BASE_PATH = r"D:\Convertible_Bond_data\crypto_data\history\futures_1m"


def compute_enhanced_asset_features(
    df: pd.DataFrame,
    btc_df: pd.DataFrame = None
) -> Tuple[pd.DataFrame, list]:
    """
    Computes 30 microstructural, capital flow, cross-asset alpha, and volatility features for a single asset.
    """
    c = df['close'].astype(np.float64)
    h = df['high'].astype(np.float64)
    l = df['low'].astype(np.float64)
    o = df['open'].astype(np.float64)
    v = df['volume'].astype(np.float64)
    qv = df['quote_volume'].astype(np.float64)
    tb_v = df['taker_buy_volume'].astype(np.float64)
    trades = df['trades_count'].astype(np.float64).replace(0, 1.0)

    feat = pd.DataFrame(index=df.index)

    # 1. Multi-horizon Returns (6 features)
    for w in [1, 3, 5, 15, 30, 60]:
        feat[f'ret_{w}m'] = c.pct_change(w).fillna(0.0).astype(np.float32)

    # 2. Moving Average Deviations (3 features)
    for span in [10, 30, 60]:
        ema = c.ewm(span=span, adjust=False).mean()
        feat[f'dist_ema_{span}'] = ((c - ema) / ema).fillna(0.0).astype(np.float32)

    # 3. Volatility & Range Regimes (4 features)
    prev_close = c.shift(1).bfill()
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_close), np.abs(l - prev_close)))
    atr_14 = tr.rolling(14).mean().bfill()
    feat['atr_14_pct'] = (atr_14 / c).fillna(0.0).astype(np.float32)

    hl_ratio = np.log((h / l.replace(0, np.nan)).fillna(1.0))
    feat['parkinson_vol_15m'] = np.sqrt((hl_ratio ** 2).rolling(15).mean().bfill() / (4.0 * np.log(2.0))).astype(np.float32)
    feat['hl_spread'] = ((h - l) / c).fillna(0.0).astype(np.float32)

    low_60 = l.rolling(60).min()
    high_60 = h.rolling(60).max()
    feat['stoch_pos_60m'] = ((c - low_60) / (high_60 - low_60 + 1e-6)).fillna(0.5).astype(np.float32)

    # 4. Capital Flow & OFI (7 features)
    taker_sell = v - tb_v
    net_taker = tb_v - taker_sell
    feat['taker_buy_ratio'] = (tb_v / (v + 1e-6)).clip(0.0, 1.0).fillna(0.5).astype(np.float32)

    for w in [1, 3, 5, 15]:
        roll_net = net_taker.rolling(w).sum()
        roll_v = v.rolling(w).sum() + 1e-6
        feat[f'ofi_{w}m'] = (roll_net / roll_v).clip(-1.0, 1.0).fillna(0.0).astype(np.float32)

    trade_size = qv / trades
    trade_size_ma20 = trade_size.rolling(20).mean().replace(0, np.nan)
    feat['rel_trade_intensity'] = (trade_size / trade_size_ma20).clip(0.1, 10.0).fillna(1.0).astype(np.float32)

    vol_mean = qv.rolling(30).mean()
    vol_std = qv.rolling(30).std().replace(0, np.nan)
    feat['vol_zscore_30m'] = ((qv - vol_mean) / vol_std).clip(-4.0, 4.0).fillna(0.0).astype(np.float32)

    # 5. Price Deviation from 24h VWAP (1 feature)
    cum_vol = v.rolling(1440, min_periods=60).sum() + 1e-6
    cum_pv = qv.rolling(1440, min_periods=60).sum()
    vwap_24h = (cum_pv / cum_vol).bfill()
    feat['dist_vwap_24h'] = ((c - vwap_24h) / vwap_24h).clip(-0.15, 0.15).fillna(0.0).astype(np.float32)

    # 6. Micro-Wick Needle Ratios (3 features)
    wick_ratio, lower_wick, upper_wick = compute_wick_ratios_nb(
        o.values, h.values, l.values, c.values
    )
    feat['wick_ratio'] = wick_ratio.astype(np.float32)
    feat['lower_wick_ratio'] = lower_wick.astype(np.float32)
    feat['upper_wick_ratio'] = upper_wick.astype(np.float32)

    # 7. Clean Corridor Score (1 feature)
    sigma_p = compute_parkinson_volatility_nb(h.values, l.values)
    s_p = pd.Series(sigma_p, index=df.index)
    sigma_fast = s_p.ewm(span=5).mean()
    sigma_slow = s_p.ewm(span=30).mean()
    vol_ratio = (sigma_fast / (sigma_slow + 1e-8)).clip(0.0, 5.0)
    wick_ma5 = feat['wick_ratio'].rolling(5, min_periods=1).mean()
    atr_ratio = (atr_14 / (atr_14.rolling(50, min_periods=10).mean() + 1e-8)).clip(0.0, 4.0)

    penalty_vol = 0.40 * np.tanh(np.maximum(vol_ratio - 1.05, 0.0) * 3.0)
    penalty_wick = 0.40 * np.tanh(np.maximum(wick_ma5 - 0.35, 0.0) * 3.5)
    penalty_atr = 0.20 * np.tanh(np.maximum(atr_ratio - 1.20, 0.0) * 2.5)
    feat['tau_vol'] = np.clip(1.0 - (penalty_vol + penalty_wick + penalty_atr), 0.0, 1.0).astype(np.float32)

    # 8. Cross-Asset Lead-Lag & Beta Dislocation vs BTC (5 features)
    if btc_df is not None:
        btc_c = btc_df['close'].astype(np.float64)
        btc_v = btc_df['volume'].astype(np.float64)
        btc_tb_v = btc_df['taker_buy_volume'].astype(np.float64)
        btc_net_taker = btc_tb_v - (btc_v - btc_tb_v)

        # Lead-lag return differentials
        for w in [1, 5, 15]:
            btc_ret = btc_c.pct_change(w).fillna(0.0)
            feat[f'ret_vs_btc_{w}m'] = (feat[f'ret_{w}m'] - btc_ret).fillna(0.0).astype(np.float32)

        btc_ofi_5m = (btc_net_taker.rolling(5).sum() / (btc_v.rolling(5).sum() + 1e-6)).clip(-1.0, 1.0).fillna(0.0)
        feat['ofi_vs_btc_5m'] = (feat['ofi_5m'] - btc_ofi_5m).fillna(0.0).astype(np.float32)

        # Dynamic 30m Beta Dislocation Residual
        ret_1m = feat['ret_1m']
        btc_ret_1m = btc_c.pct_change(1).fillna(0.0)
        cov_30 = ret_1m.rolling(30).cov(btc_ret_1m).fillna(0.0)
        var_30 = btc_ret_1m.rolling(30).var().replace(0, np.nan).bfill()
        beta_30 = (cov_30 / (var_30 + 1e-8)).clip(-2.0, 3.0).fillna(1.0)
        feat['beta_residual_1m'] = (ret_1m - beta_30 * btc_ret_1m).fillna(0.0).astype(np.float32)
    else:
        for w in [1, 5, 15]:
            feat[f'ret_vs_btc_{w}m'] = np.zeros(len(df), dtype=np.float32)
        feat['ofi_vs_btc_5m'] = np.zeros(len(df), dtype=np.float32)
        feat['beta_residual_1m'] = np.zeros(len(df), dtype=np.float32)

    # Clean infinities and NaNs
    feat = feat.replace([np.inf, -np.inf], 0.0).fillna(0.0)
    col_names = feat.columns.tolist()
    return feat, col_names


def build_2026_05_split_dataset(
    split_date: str = "2026-05-01 00:00:00",
    horizon: int = 30,
    out_dir: str = r"D:\Convertible_Bond_data\crypto_data"
):
    print("=" * 85)
    print("  Building Multi-Asset Dataset with Strict 2026/05 Temporal Split")
    print(f"  Assets: {ASSETS}")
    print(f"  Strict Temporal Boundary: {split_date}")
    print(f"  In-Sample Training: < {split_date}")
    print(f"  Out-of-Sample Testing: >= {split_date}")
    print("=" * 85)

    # 1. Load Parquets and merge with September 2026 updates
    print("\n[1/5] Loading continuous and September 2026 Parquet files...")
    all_dfs = {}
    for sym in ASSETS:
        p_main = os.path.join(BASE_PATH, f"{sym}_futures_1m_continuous.parquet")
        df_main = pd.read_parquet(p_main)
        p_sept = os.path.join(BASE_PATH, f"{sym}_2026_09_01_to_09_22.parquet")
        if os.path.exists(p_sept):
            df_sept = pd.read_parquet(p_sept)
            df_all = pd.concat([df_main, df_sept], ignore_index=True).drop_duplicates(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)
            print(f"  {sym}: Merged main + Sept 2026 -> {len(df_all):,} bars")
        else:
            df_all = df_main.sort_values('timestamp').reset_index(drop=True)
            print(f"  {sym}: Main only -> {len(df_all):,} bars")
        all_dfs[sym] = df_all

    # 2. Align timestamps across all 4 assets
    print("\n[2/5] Aligning timestamps across all 4 assets...")
    common_ts = all_dfs[ASSETS[0]]['timestamp'].values
    for sym in ASSETS[1:]:
        common_ts = np.intersect1d(common_ts, all_dfs[sym]['timestamp'].values)

    print(f"  Common aligned 1m bars across all 4 assets: {len(common_ts):,}")

    aligned_dfs = {}
    for sym in ASSETS:
        df = all_dfs[sym]
        aligned_dfs[sym] = df[df['timestamp'].isin(common_ts)].sort_values('timestamp').reset_index(drop=True)

    dt_series = aligned_dfs['BTCUSDT']['datetime'].values
    print(f"  Aligned Time Range: {dt_series[0]} to {dt_series[-1]}")

    # 3. Compute Enhanced Features per asset
    print("\n[3/5] Computing multi-asset features with cross-asset lead-lag, beta dislocation & needle ratios...")
    btc_df = aligned_dfs['BTCUSDT']
    btc_feat, feat_names = compute_enhanced_asset_features(btc_df, btc_df=None)

    asset_features = {'BTCUSDT': btc_feat}
    for sym in ASSETS[1:]:
        t0 = time.time()
        feat, _ = compute_enhanced_asset_features(aligned_dfs[sym], btc_df=btc_df)
        asset_features[sym] = feat
        print(f"  {sym}: Extracted {feat.shape[1]} features in {time.time()-t0:.1f}s")

    print(f"  Feature dimensions per asset: {len(feat_names)}")
    print(f"  Feature names ({len(feat_names)}): {feat_names}")

    # 4. Vectorized Numba Labeling
    print("\n[4/5] Vectorized Numba labeling of 20X/100X optimal excursion barriers...")
    asset_labels = {}
    for sym in ASSETS:
        c = aligned_dfs[sym]['close'].values.astype(np.float64)
        h = aligned_dfs[sym]['high'].values.astype(np.float64)
        l = aligned_dfs[sym]['low'].values.astype(np.float64)

        t0 = time.time()
        gate, tp, sl, roe = label_excursions_and_optimal_barriers_numba(
            close=c,
            high=h,
            low=l,
            horizon=horizon,
            leverage=20.0,
            roundtrip_fee_pct=0.0004,
            min_profit_pct=0.006,
            max_safe_sl_pct=0.012,
            min_sl_pct=0.003
        )
        asset_labels[sym] = {'gate': gate, 'tp': tp, 'sl': sl, 'roe': roe}
        n_long = (gate == 1).sum()
        n_short = (gate == 2).sum()
        n_flat = (gate == 0).sum()
        print(f"  {sym} ({time.time()-t0:.1f}s) -> Long: {n_long:,} ({n_long/len(gate)*100:.1f}%), Short: {n_short:,} ({n_short/len(gate)*100:.1f}%), Flat: {n_flat:,} ({n_flat/len(gate)*100:.1f}%)")

    # 5. Split identification and packaging
    print("\n[5/5] Splitting by 2026-05-01 boundary...")
    # Convert dt_series to string for robust comparison
    dt_str = pd.Series(dt_series).astype(str)
    train_mask = dt_str < split_date
    test_mask = dt_str >= split_date

    train_indices = np.where(train_mask)[0]
    test_indices = np.where(test_mask)[0]

    print(f"  In-Sample Training Set: {len(train_indices):,} bars ({dt_series[train_indices[0]]} to {dt_series[train_indices[-1]]})")
    print(f"  Out-of-Sample Test Set: {len(test_indices):,} bars ({dt_series[test_indices[0]]} to {dt_series[test_indices[-1]]})")

    n_bars = len(common_ts)
    n_assets = len(ASSETS)
    n_feats = len(feat_names)

    feat_matrix = np.zeros((n_bars, n_assets, n_feats), dtype=np.float32)
    gate_matrix = np.zeros((n_bars, n_assets), dtype=np.int8)
    tp_matrix = np.zeros((n_bars, n_assets), dtype=np.float32)
    sl_matrix = np.zeros((n_bars, n_assets), dtype=np.float32)
    roe_matrix = np.zeros((n_bars, n_assets), dtype=np.float32)
    price_matrix = np.zeros((n_bars, n_assets, 4), dtype=np.float32)

    for k, sym in enumerate(ASSETS):
        feat_matrix[:, k, :] = asset_features[sym].values
        gate_matrix[:, k] = asset_labels[sym]['gate']
        tp_matrix[:, k] = asset_labels[sym]['tp']
        sl_matrix[:, k] = asset_labels[sym]['sl']
        roe_matrix[:, k] = asset_labels[sym]['roe']
        price_matrix[:, k, 0] = aligned_dfs[sym]['open'].values
        price_matrix[:, k, 1] = aligned_dfs[sym]['high'].values
        price_matrix[:, k, 2] = aligned_dfs[sym]['low'].values
        price_matrix[:, k, 3] = aligned_dfs[sym]['close'].values

    out_file = os.path.join(out_dir, "multi_asset_split_2026_05.npz")
    print(f"\nSaving split dataset -> {out_file}...")
    np.savez_compressed(
        out_file,
        features=feat_matrix,
        gates=gate_matrix,
        tp_targets=tp_matrix,
        sl_targets=sl_matrix,
        roe_targets=roe_matrix,
        prices=price_matrix,
        timestamps=common_ts,
        datetimes=dt_series,
        train_indices=train_indices,
        test_indices=test_indices,
        assets=np.array(ASSETS),
        feature_names=np.array(feat_names)
    )
    print(f"[SUCCESS] Dataset saved: {out_file} ({os.path.getsize(out_file)/1024/1024:.1f} MB)")
    return out_file


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--split-date', type=str, default="2026-05-01 00:00:00")
    parser.add_argument('--horizon', type=int, default=30)
    args = parser.parse_args()
    build_2026_05_split_dataset(split_date=args.split_date, horizon=args.horizon)
