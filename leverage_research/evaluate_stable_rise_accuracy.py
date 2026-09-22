# -*- coding: utf-8 -*-
"""
Multi-Timeframe Stable Rise Accuracy Benchmark Engine
ETH 稳定上涨多目标预测准确率与数理上限全景测评引擎

Evaluates:
- Target Upsides: +1%, +2%, +3%, +4%, +5%
- Downside Volatility Constraints (MAE Limits): 0.25% (Strict) vs 0.35% (Moderate)
- Benchmarks:
  1. Unconditional Historical Base Rate
  2. Multi-Timeframe Technical Confluence (1s + 1m + 5m)
  3. Transformer Deep Spatio-Temporal Model
  4. Fused Confluence Model (Transformer + Multi-Scale Features)
"""

import os
import sys
import time
import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crypto_leverage_transformer import CryptoLeverageTransformer
from stable_rise_feature_engine import compute_multi_timeframe_features, label_stable_rise_fast


class SliceDataset(Dataset):
    def __init__(self, features, lookback=60):
        self.features = features
        self.lookback = lookback
        self.n = len(features)

    def __len__(self):
        return max(0, self.n - self.lookback)

    def __getitem__(self, idx):
        t = idx + self.lookback
        x = self.features[t - self.lookback:t, :, :]
        x = np.transpose(x, (1, 0, 2))
        return torch.from_numpy(x).float()


def run_transformer_inference(data_path, ckpt_path, start_idx, num_bars, batch_size=512):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Loading checkpoint: {ckpt_path} on {device}...")
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    model = CryptoLeverageTransformer(num_assets=4, in_features=25, lookback=60)
    model.load_state_dict(ckpt['model_state_dict'])
    model.to(device)
    model.eval()
    
    data = np.load(data_path, allow_pickle=True)
    raw_slice = data['features'][start_idx - 60:start_idx + num_bars]
    
    scaler_mean = ckpt['scaler_mean']
    scaler_std = ckpt['scaler_std']
    norm_slice = (raw_slice - scaler_mean) / np.maximum(scaler_std, 1e-6)
    
    dataset = SliceDataset(norm_slice, lookback=60)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    
    all_prob_long = []
    all_prob_short = []
    
    with torch.no_grad():
        for batch_x in loader:
            batch_x = batch_x.to(device)
            out = model(batch_x)
            prob_gate = out['prob_gate'].cpu().numpy()
            all_prob_long.append(prob_gate[:, 1, 1])  # ETH is index 1, long is index 1
            all_prob_short.append(prob_gate[:, 1, 2]) # ETH short is index 2
            
    prob_long = np.concatenate(all_prob_long)
    prob_short = np.concatenate(all_prob_short)
    
    denom = np.maximum(prob_long + prob_short, 1e-6)
    tau_transformer = prob_long / denom # Conditional probability
    return tau_transformer


def run_benchmark():
    data_path = r"D:\Convertible_Bond_data\crypto_data\multi_asset_full_2020_2026.npz"
    ckpt_path = r"c:\Users\liuqi\crypto\checkpoints\best_transformer_2020_2025.pt"
    charts_dir = r"c:\Users\liuqi\crypto\leverage_research\charts"
    os.makedirs(charts_dir, exist_ok=True)
    
    print("=" * 80)
    print("  ETH Multi-Timeframe Stable Rise Prediction Accuracy Benchmark")
    print("=" * 80)
    
    data = np.load(data_path, allow_pickle=True)
    # Evaluate across recent 15 months: 658,560 bars
    recent_len = 658560
    total_bars = len(data['datetimes'])
    start_idx = total_bars - recent_len
    
    datetimes_slice = data['datetimes'][start_idx:]
    eth_prices = data['prices'][start_idx:, 1, :]
    
    closes = eth_prices[:, 3].astype(np.float64)
    highs = eth_prices[:, 1].astype(np.float64)
    lows = eth_prices[:, 2].astype(np.float64)
    opens = eth_prices[:, 0].astype(np.float64)
    
    df_1m = pd.DataFrame({
        'open': opens, 'high': highs, 'low': lows, 'close': closes,
        'volume': np.random.uniform(500, 2500, size=len(closes))
    }, index=pd.to_datetime(datetimes_slice))
    
    # 1. Compute Multi-Timeframe Features
    print("\n[Step 1] Computing 1s/1m/5m Multi-Scale Indicators...")
    t0 = time.time()
    df_1m = compute_multi_timeframe_features(df_1m)
    print(f"  Features computed in {time.time() - t0:.2f}s.")
    
    # 2. Run Transformer Inference
    print("\n[Step 2] Running Spatio-Temporal Transformer Inference...")
    t0 = time.time()
    tau_transformer = run_transformer_inference(data_path, ckpt_path, start_idx, recent_len)
    df_1m['tau_transformer'] = tau_transformer
    print(f"  Inference completed in {time.time() - t0:.2f}s.")
    
    # 3. Fused Model Score
    df_1m['tau_fused'] = 0.50 * df_1m['tau_transformer'] + 0.50 * df_1m['multi_scale_score']
    
    # 4. Generate Ground Truth Labels for Targets [+1%, +2%, +3%, +4%, +5%]
    targets = np.array([0.01, 0.02, 0.03, 0.04, 0.05], dtype=np.float64)
    target_names = ['+1% Rise', '+2% Rise', '+3% Rise', '+4% Rise', '+5% Rise']
    mae_limits = [0.0025, 0.0035] # 0.25% Strict, 0.35% Moderate
    mae_names = ['Strict (MAE <= 0.25%)', 'Moderate (MAE <= 0.35%)']
    
    benchmark_results = []
    
    for m_idx, mae in enumerate(mae_limits):
        m_name = mae_names[m_idx]
        print(f"\n========================================================================")
        print(f"  Benchmarking Downside Constraint: {m_name}")
        print(f"========================================================================")
        
        # Ground truth labels shape: (N, 5)
        labels = label_stable_rise_fast(closes, highs, lows, targets, mae, max_horizon=720)
        valid_len = len(closes) - 720
        
        # Benchmarks to compare:
        # 1. Base Rate (All bars)
        # 2. Multi-Scale Indicators (score >= 0.70)
        # 3. Transformer Model (tau_tf >= 0.70)
        # 4. Fused Confluence Model (tau_fused >= 0.65)
        # 5. High-Conviction Fused Model (tau_fused >= 0.75)
        models = [
            {'name': '1. Unconditional Base Rate', 'mask': np.ones(valid_len, dtype=bool)},
            {'name': '2. Multi-Scale Indicators (>= 0.70)', 'mask': (df_1m['multi_scale_score'].values[:valid_len] >= 0.70)},
            {'name': '3. Transformer Model (tau >= 0.70)', 'mask': (df_1m['tau_transformer'].values[:valid_len] >= 0.70)},
            {'name': '4. Fused Confluence (tau >= 0.65)', 'mask': (df_1m['tau_fused'].values[:valid_len] >= 0.65)},
            {'name': '5. High-Conviction Fused (tau >= 0.75)', 'mask': (df_1m['tau_fused'].values[:valid_len] >= 0.75)}
        ]
        
        for mod in models:
            m_mask = mod['mask']
            n_samples = m_mask.sum()
            if n_samples == 0:
                continue
                
            print(f"\n>>> Model: {mod['name']} (Selected Signals: {n_samples:,} bars / {n_samples/valid_len*100:.1f}%)")
            
            for t_idx, tgt in enumerate(targets):
                target_label = labels[:valid_len, t_idx]
                hits = target_label[m_mask].sum()
                precision = hits / n_samples * 100.0
                
                # Financial Payoff at 100X leverage (% ROE on margin):
                leverage = 100.0
                fee_roe = 0.0004 * leverage * 100.0 # 4.0% ROE round-trip maker fee
                
                # Win Net ROE: target * 100 * 100 - fee (e.g. 1% price move * 100x = +100% gross - 4% = +96% ROE)
                net_win_roe = (tgt * leverage * 100.0) - fee_roe
                
                # SL Net ROE: -(mae * 100 * 100 + fee) (e.g. -0.25% price move * 100x = -25% gross - 4% = -29% ROE)
                net_loss_roe = -(mae * leverage * 100.0 + fee_roe)
                
                # Break-even win rate & Risk-Reward ratio
                rr = net_win_roe / abs(net_loss_roe)
                be_rate = 1.0 / (1.0 + rr) * 100.0
                
                # Expected Value (EV) per trade (% Net ROE on margin)
                ev = (precision / 100.0) * net_win_roe + (1.0 - precision / 100.0) * net_loss_roe
                
                print(f"  {target_names[t_idx]}: Precision: {precision:5.2f}% | Break-Even: {be_rate:4.1f}% | R:R: {rr:4.1f} | 100X Net EV: {ev:+6.2f}% ROE")
                
                benchmark_results.append({
                    'constraint': m_name,
                    'mae_limit_pct': mae * 100.0,
                    'model': mod['name'],
                    'samples': n_samples,
                    'target': target_names[t_idx],
                    'target_pct': tgt * 100.0,
                    'hits': hits,
                    'precision': precision,
                    'rr_ratio': rr,
                    'breakeven_rate': be_rate,
                    'net_win_roe': net_win_roe,
                    'net_loss_roe': net_loss_roe,
                    'ev_roe': ev
                })
                
    df_res = pd.DataFrame(benchmark_results)
    csv_path = os.path.join(charts_dir, 'stable_rise_accuracy_benchmark.csv')
    df_res.to_csv(csv_path, index=False)
    print(f"\nSaved benchmark results to: {csv_path}")
    return df_res


if __name__ == '__main__':
    run_benchmark()
