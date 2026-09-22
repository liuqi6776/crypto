# -*- coding: utf-8 -*-
"""
Build 6-Year Full-Horizon 4-Asset 1-Minute Dataset (2020/09 - 2026/09)
构建 2020年9月 至 2026年9月 连续 6 年超 310 万根 1 分钟四币种全量时空特征与 20X 动态标签张量
Split boundary: Train (2020-09-14 to 2025-05-31), Validation (2025-06-01 to 2026-09-01)
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
from build_4asset_1m_dataset import compute_asset_features

ASSETS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT']
BASE_PATH = r"D:\Convertible_Bond_data\crypto_data\history\futures_1m"


def build_full_dataset(
    split_date: str = "2025-06-01 00:00:00",
    horizon: int = 30,
    out_dir: str = r"D:\Convertible_Bond_data\crypto_data"
):
    print("=" * 80)
    print("  Building Full 6-Year 4-Asset 1m Dataset (2020/09 to 2026/09)")
    print(f"  Assets: {ASSETS}")
    print(f"  Train: 2020-09-14 -> {split_date} | Val/OOS: {split_date} -> 2026-09-01")
    print("=" * 80)

    # 1. Load Parquets
    print("\n[1/5] Loading continuous 1m Parquet files...")
    raw_dfs = {}
    for sym in ASSETS:
        p = os.path.join(BASE_PATH, f"{sym}_futures_1m_continuous.parquet")
        df = pd.read_parquet(p)
        raw_dfs[sym] = df.sort_values('timestamp').reset_index(drop=True)
        print(f"  {sym}: {len(df):,} bars ({df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]})")

    # 2. Align timestamps starting from SOL listing
    print("\n[2/5] Aligning timestamps across all 4 assets...")
    common_ts = raw_dfs[ASSETS[0]]['timestamp'].values
    for sym in ASSETS[1:]:
        common_ts = np.intersect1d(common_ts, raw_dfs[sym]['timestamp'].values)

    print(f"  Common aligned 1m bars: {len(common_ts):,}")

    aligned_dfs = {}
    for sym in ASSETS:
        df = raw_dfs[sym]
        aligned_dfs[sym] = df[df['timestamp'].isin(common_ts)].sort_values('timestamp').reset_index(drop=True)

    dt_series = aligned_dfs['BTCUSDT']['datetime'].values
    print(f"  Aligned Range: {dt_series[0]} to {dt_series[-1]}")

    # 3. Compute Features per asset
    print("\n[3/5] Computing multi-asset microstructure, OFI, and capital flow features...")
    btc_feat, feat_names = compute_asset_features(aligned_dfs['BTCUSDT'], btc_ret_dict=None)
    btc_ret_dict = {
        'ret_1m': btc_feat['ret_1m'],
        'ret_5m': btc_feat['ret_5m'],
        'ret_15m': btc_feat['ret_15m'],
        'ofi_5m': btc_feat['ofi_5m']
    }

    asset_features = {'BTCUSDT': btc_feat}
    for sym in ASSETS[1:]:
        t0 = time.time()
        feat, _ = compute_asset_features(aligned_dfs[sym], btc_ret_dict=btc_ret_dict)
        asset_features[sym] = feat
        print(f"  {sym}: Extracted {feat.shape[1]} features in {time.time()-t0:.1f}s")

    # 4. Vectorized Numba Labeling
    print("\n[4/5] Vectorized Numba labeling of 20X MFE/MAE optimal barriers...")
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
    print("\n[5/5] Determining train and validation index boundaries...")
    dt_str = pd.Series(dt_series)
    train_mask = dt_str < split_date
    val_mask = dt_str >= split_date

    train_indices = np.where(train_mask)[0]
    val_indices = np.where(val_mask)[0]

    print(f"  Train Set: {len(train_indices):,} bars ({dt_series[train_indices[0]]} to {dt_series[train_indices[-1]]})")
    print(f"  Validation Set: {len(val_indices):,} bars ({dt_series[val_indices[0]]} to {dt_series[val_indices[-1]]})")

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

    out_file = os.path.join(out_dir, "multi_asset_full_2020_2026.npz")
    print(f"Saving full compressed archive -> {out_file}...")
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
        val_indices=val_indices,
        assets=np.array(ASSETS),
        feature_names=np.array(feat_names)
    )
    print(f"[DONE] Multi-year dataset successfully assembled and saved -> {out_file}")
    return out_file


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--split-date', type=str, default="2025-06-01 00:00:00")
    parser.add_argument('--horizon', type=int, default=30)
    args = parser.parse_args()
    build_full_dataset(split_date=args.split_date, horizon=args.horizon)
