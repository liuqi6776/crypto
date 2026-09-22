# -*- coding: utf-8 -*-
"""
Build 4-Asset 1-Minute Feature Tensor and 20X Multi-Barrier Labels
构建 BTC、ETH、SOL、BNB 4 大资产 1 分钟时空微结构特征矩阵与 20倍杠杆动态止盈止损标签
"""

import os
import sys
import argparse
import time
import numpy as np
import pandas as pd
from typing import Dict, Tuple

# Add leverage_research to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from crypto_leverage_transformer import label_excursions_and_optimal_barriers_numba


ASSETS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT']
BASE_PATH = r"D:\Convertible_Bond_data\crypto_data\history\futures_1m"


def compute_asset_features(df: pd.DataFrame, btc_ret_dict: Dict[str, pd.Series] = None) -> Tuple[pd.DataFrame, list]:
    """
    Computes 28 microstructural, capital flow, and price dynamic features for a single asset.
    """
    c = df['close'].astype(np.float64)
    h = df['high'].astype(np.float64)
    l = df['low'].astype(np.float64)
    v = df['volume'].astype(np.float64)
    qv = df['quote_volume'].astype(np.float64)
    tb_v = df['taker_buy_volume'].astype(np.float64)
    trades = df['trades_count'].astype(np.float64).replace(0, 1.0)

    feat = pd.DataFrame(index=df.index)

    # 1. Multi-horizon Returns
    for w in [1, 3, 5, 15, 30, 60]:
        feat[f'ret_{w}m'] = c.pct_change(w).fillna(0.0).astype(np.float32)

    # 2. Moving Average Deviations
    for span in [10, 30, 60]:
        ema = c.ewm(span=span, adjust=False).mean()
        feat[f'dist_ema_{span}'] = ((c - ema) / ema).fillna(0.0).astype(np.float32)

    # 3. Volatility & Range Regimes
    prev_close = c.shift(1).bfill()
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_close), np.abs(l - prev_close)))
    atr_14 = tr.rolling(14).mean().bfill()
    feat['atr_14_pct'] = (atr_14 / c).fillna(0.0).astype(np.float32)

    # Parkinson Volatility (15m)
    hl_ratio = np.log((h / l.replace(0, np.nan)).fillna(1.0))
    feat['parkinson_vol_15m'] = np.sqrt((hl_ratio ** 2).rolling(15).mean().bfill() / (4.0 * np.log(2.0))).astype(np.float32)
    feat['hl_spread'] = ((h - l) / c).fillna(0.0).astype(np.float32)

    # Stochastic Position over 60 bars
    low_60 = l.rolling(60).min()
    high_60 = h.rolling(60).max()
    feat['stoch_pos_60m'] = ((c - low_60) / (high_60 - low_60 + 1e-6)).fillna(0.5).astype(np.float32)

    # 4. Capital Flow & OFI (主动买卖盘资金流与订单流不平衡)
    taker_sell = v - tb_v
    net_taker = tb_v - taker_sell
    feat['taker_buy_ratio'] = (tb_v / (v + 1e-6)).clip(0.0, 1.0).fillna(0.5).astype(np.float32)

    # Multi-scale OFI
    for w in [1, 3, 5, 15]:
        roll_net = net_taker.rolling(w).sum()
        roll_v = v.rolling(w).sum() + 1e-6
        feat[f'ofi_{w}m'] = (roll_net / roll_v).clip(-1.0, 1.0).fillna(0.0).astype(np.float32)

    # Relative Trade Intensity
    trade_size = qv / trades
    trade_size_ma20 = trade_size.rolling(20).mean().replace(0, np.nan)
    feat['rel_trade_intensity'] = (trade_size / trade_size_ma20).clip(0.1, 10.0).fillna(1.0).astype(np.float32)

    # Volume Z-score (30m)
    vol_mean = qv.rolling(30).mean()
    vol_std = qv.rolling(30).std().replace(0, np.nan)
    feat['vol_zscore_30m'] = ((qv - vol_mean) / vol_std).clip(-4.0, 4.0).fillna(0.0).astype(np.float32)

    # 5. Cross-Asset Lead-Lag (vs BTC)
    if btc_ret_dict is not None:
        for w in [1, 5, 15]:
            feat[f'ret_vs_btc_{w}m'] = (feat[f'ret_{w}m'] - btc_ret_dict[f'ret_{w}m']).fillna(0.0).astype(np.float32)
        feat['ofi_vs_btc_5m'] = (feat['ofi_5m'] - btc_ret_dict['ofi_5m']).fillna(0.0).astype(np.float32)
    else:
        for w in [1, 5, 15]:
            feat[f'ret_vs_btc_{w}m'] = np.zeros(len(df), dtype=np.float32)
        feat['ofi_vs_btc_5m'] = np.zeros(len(df), dtype=np.float32)

    # 6. Price Deviation from 24h VWAP
    cum_vol = v.rolling(1440, min_periods=60).sum() + 1e-6
    cum_pv = qv.rolling(1440, min_periods=60).sum()
    vwap_24h = (cum_pv / cum_vol).bfill()
    feat['dist_vwap_24h'] = ((c - vwap_24h) / vwap_24h).clip(-0.15, 0.15).fillna(0.0).astype(np.float32)

    # Clean infinities and NaNs
    feat = feat.replace([np.inf, -np.inf], 0.0).fillna(0.0)
    col_names = feat.columns.tolist()
    return feat, col_names


def build_and_save_dataset(
    sample_bars: int = 150000,
    horizon: int = 30,
    out_dir: str = r"D:\Convertible_Bond_data\crypto_data"
):
    print("=" * 75)
    print("  Building 4-Asset 1m Microstructure & Capital Flow Dataset")
    print(f"  Assets: {ASSETS}")
    print(f"  Horizon: {horizon} bars (30 min) | Sample Bars: {sample_bars:,}")
    print("=" * 75)

    raw_dfs = {}
    print("\n[1/5] Loading continuous 1m Parquet files...")
    for sym in ASSETS:
        p = os.path.join(BASE_PATH, f"{sym}_futures_1m_continuous.parquet")
        df = pd.read_parquet(p)
        if sample_bars > 0 and len(df) > sample_bars:
            df = df.iloc[-sample_bars:].copy()
        raw_dfs[sym] = df.sort_values('timestamp').reset_index(drop=True)
        print(f"  {sym}: {len(df):,} bars ({df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]})")

    # [2/5] Align timestamps across all 4 assets
    print("\n[2/5] Aligning timestamps across all 4 assets...")
    common_ts = raw_dfs[ASSETS[0]]['timestamp']
    for sym in ASSETS[1:]:
        common_ts = np.intersect1d(common_ts, raw_dfs[sym]['timestamp'])

    print(f"  Common aligned bars: {len(common_ts):,}")
    aligned_dfs = {}
    for sym in ASSETS:
        df = raw_dfs[sym]
        aligned_dfs[sym] = df[df['timestamp'].isin(common_ts)].sort_values('timestamp').reset_index(drop=True)

    # [3/5] Extract Features
    print("\n[3/5] Computing microstructure, capital flow & lead-lag features...")
    # Compute BTC features first
    btc_feat, feat_names = compute_asset_features(aligned_dfs['BTCUSDT'], btc_ret_dict=None)
    btc_ret_dict = {
        'ret_1m': btc_feat['ret_1m'],
        'ret_5m': btc_feat['ret_5m'],
        'ret_15m': btc_feat['ret_15m'],
        'ofi_5m': btc_feat['ofi_5m']
    }

    asset_features = {'BTCUSDT': btc_feat}
    for sym in ASSETS[1:]:
        feat, _ = compute_asset_features(aligned_dfs[sym], btc_ret_dict=btc_ret_dict)
        asset_features[sym] = feat
        print(f"  Extracted {feat.shape[1]} features for {sym}")

    print(f"  Feature dimensions per asset per bar: {len(feat_names)}")

    # [4/5] Label Excursions & Dynamic Optimal Barriers (Numba JIT)
    print("\n[4/5] Vectorized Numba labeling of 20X MFE/MAE optimal TP/SL...")
    asset_labels = {}
    for sym in ASSETS:
        c = aligned_dfs[sym]['close'].values.astype(np.float64)
        h = aligned_dfs[sym]['high'].values.astype(np.float64)
        l = aligned_dfs[sym]['low'].values.astype(np.float64)

        gate, tp, sl, roe = label_excursions_and_optimal_barriers_numba(
            close=c,
            high=h,
            low=l,
            horizon=horizon,
            leverage=20.0,
            roundtrip_fee_pct=0.0004, # 0.04% maker-maker fee
            min_profit_pct=0.006,     # 0.6% price move (12% ROE at 20x)
            max_safe_sl_pct=0.012,    # 1.2% price move (24% ROE loss)
            min_sl_pct=0.003
        )
        asset_labels[sym] = {
            'gate': gate,
            'tp': tp,
            'sl': sl,
            'roe': roe
        }
        n_long = (gate == 1).sum()
        n_short = (gate == 2).sum()
        n_flat = (gate == 0).sum()
        print(f"  {sym} Labels -> Long: {n_long:,} ({n_long/len(gate)*100:.1f}%), Short: {n_short:,} ({n_short/len(gate)*100:.1f}%), Flat: {n_flat:,} ({n_flat/len(gate)*100:.1f}%)")

    # [5/5] Save structured tensors to disk
    print("\n[5/5] Packaging and saving multi-asset dataset...")
    n_bars = len(common_ts)
    n_assets = len(ASSETS)
    n_feats = len(feat_names)

    # Tensor shape: (N, K=4, D=28)
    feat_matrix = np.zeros((n_bars, n_assets, n_feats), dtype=np.float32)
    gate_matrix = np.zeros((n_bars, n_assets), dtype=np.int8)
    tp_matrix = np.zeros((n_bars, n_assets), dtype=np.float32)
    sl_matrix = np.zeros((n_bars, n_assets), dtype=np.float32)
    roe_matrix = np.zeros((n_bars, n_assets), dtype=np.float32)
    price_matrix = np.zeros((n_bars, n_assets, 4), dtype=np.float32) # open, high, low, close

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

    dt_series = aligned_dfs['BTCUSDT']['datetime'].values
    ts_series = common_ts

    out_file = os.path.join(out_dir, "multi_asset_20x_leverage_dataset.npz")
    np.savez_compressed(
        out_file,
        features=feat_matrix,
        gates=gate_matrix,
        tp_targets=tp_matrix,
        sl_targets=sl_matrix,
        roe_targets=roe_matrix,
        prices=price_matrix,
        timestamps=ts_series,
        datetimes=dt_series,
        assets=np.array(ASSETS),
        feature_names=np.array(feat_names)
    )
    print(f"\n[DONE] Dataset saved successfully -> {out_file}")
    print(f"  Feature Tensor Shape: {feat_matrix.shape}")
    print(f"  Date Range: {dt_series[0]} to {dt_series[-1]}")
    return out_file


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--sample-bars', type=int, default=150000, help="Number of recent bars (e.g. 150000 ~ 3.5 months)")
    parser.add_argument('--horizon', type=int, default=30)
    parser.add_argument('--out-dir', type=str, default=r"D:\Convertible_Bond_data\crypto_data")
    args = parser.parse_args()
    build_and_save_dataset(sample_bars=args.sample_bars, horizon=args.horizon, out_dir=args.out_dir)
