# -*- coding: utf-8 -*-
"""
Evaluate Multi-Confidence 20X Return Curves on Validation Set (2025/06 - 2026/09)
2025年6月 至 2026年9月 验证集（65万根1分钟K线）在不同置信度下的收益变化曲线与风险实证引擎
"""

import os
import sys
import time
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import torch
from torch.utils.data import Dataset, DataLoader

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from crypto_leverage_transformer import CryptoLeverageTransformer


class FastValidationDataset(Dataset):
    def __init__(self, features: np.ndarray, val_indices: np.ndarray, lookback: int = 60):
        self.lookback = lookback
        self.indices = val_indices
        self.features = features

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, idx):
        t = self.indices[idx]
        x = self.features[t - self.lookback:t, :, :] # (L, K, D)
        x = np.transpose(x, (1, 0, 2))                # (K, L, D)
        return torch.from_numpy(x).float()


def run_validation_evaluation(
    data_path: str = r"D:\Convertible_Bond_data\crypto_data\multi_asset_full_2020_2026.npz",
    ckpt_path: str = r"c:\Users\liuqi\crypto\checkpoints\best_transformer_2020_2025.pt",
    initial_capital: float = 10000.0,
    margin_per_trade: float = 1000.0,
    leverage: float = 20.0,
    maker_fee: float = 0.0002,
    taker_fee: float = 0.0005,
    slippage: float = 0.0001,
    mmr: float = 0.005,
    horizon: int = 30,
    charts_dir: str = r"c:\Users\liuqi\crypto\leverage_research\charts"
):
    print("=" * 80)
    print("  Evaluating 20X Transformer on 2025/06 - 2026/09 Validation Set")
    print("=" * 80)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Inference Device: {device}")

    # 1. Load Data & Scaler
    print(f"\n[1/4] Loading multi-year archive & checkpoint...")
    data = np.load(data_path, allow_pickle=True)
    features = data['features']
    prices = data['prices']
    datetimes = data['datetimes']
    val_indices = data['val_indices']
    assets = data['assets']

    checkpoint = torch.load(ckpt_path, map_location=device, weights_only=False)
    scaler_mean = checkpoint['scaler_mean']
    scaler_std = checkpoint['scaler_std']
    lookback = checkpoint.get('lookback', 60)
    feat_dim = checkpoint.get('feature_dim', 25)

    print(f"  Validation bars: {len(val_indices):,} ({datetimes[val_indices[0]]} to {datetimes[val_indices[-1]]})")
    print(f"  Assets: {assets}")

    # Normalize validation features using train scaler
    features_norm = np.clip((features - scaler_mean) / scaler_std, -5.0, 5.0).astype(np.float32)

    cached_val_path = r"D:\Convertible_Bond_data\crypto_data\val_predictions_2025_2026.npz"
    if os.path.exists(cached_val_path):
        print(f"\n[2/4] Loading cached validation predictions from: {cached_val_path}...")
        c_data = np.load(cached_val_path, allow_pickle=True)
        all_prob_gate = c_data['prob_gate']
        all_pred_tp = c_data['pred_tp']
        all_pred_sl = c_data['pred_sl']
        all_pred_roe = c_data['pred_roe']
        val_prices = c_data['val_prices']
        val_dts = c_data['val_dts']
        M, K = all_pred_tp.shape
        print(f"  Loaded {M:,} predictions across {K} assets in 0.5s!")
    else:
        # 2. Batch Inference over all 650k validation bars
        print(f"\n[2/4] Running high-speed GPU batch inference over {len(val_indices):,} 1m bars...")
        model = CryptoLeverageTransformer(num_assets=len(assets), in_features=feat_dim, lookback=lookback).to(device)
        model.load_state_dict(checkpoint['model_state_dict'])
        model.eval()

        val_ds = FastValidationDataset(features_norm, val_indices, lookback=lookback)
        val_loader = DataLoader(val_ds, batch_size=2048, shuffle=False, num_workers=0, pin_memory=True)

        prob_gate_list = []
        pred_tp_list = []
        pred_sl_list = []
        pred_roe_list = []

        t0 = time.time()
        with torch.no_grad():
            for x in val_loader:
                x = x.to(device)
                out = model(x)
                prob_gate_list.append(out['prob_gate'].cpu().numpy())
                pred_tp_list.append(out['pred_tp_pct'].cpu().numpy())
                pred_sl_list.append(out['pred_sl_pct'].cpu().numpy())
                pred_roe_list.append(out['pred_expected_roe'].cpu().numpy())

        inference_time = time.time() - t0
        print(f"  GPU Inference Complete in {inference_time:.2f}s! ({len(val_indices)/inference_time:,.0f} bars/sec)")

        all_prob_gate = np.concatenate(prob_gate_list, axis=0) # (M, K, 3)
        all_pred_tp = np.concatenate(pred_tp_list, axis=0)     # (M, K)
        all_pred_sl = np.concatenate(pred_sl_list, axis=0)     # (M, K)
        all_pred_roe = np.concatenate(pred_roe_list, axis=0)   # (M, K)

        val_prices = prices[val_indices]                       # (M, K, 4)
        val_dts = datetimes[val_indices]                       # (M,)
        M, K = all_pred_tp.shape

        np.savez_compressed(
            cached_val_path,
            prob_gate=all_prob_gate,
            pred_tp=all_pred_tp,
            pred_sl=all_pred_sl,
            pred_roe=all_pred_roe,
            val_prices=val_prices,
            val_dts=val_dts,
            assets=assets
        )
        print(f"  Cached validation predictions -> {cached_val_path}")

    # 3. Simulate Execution across Confidence Thresholds
    thresholds = [0.48, 0.50, 0.52, 0.53, 0.54, 0.55]
    min_roe_thresh = 0.0 # Pure confidence gate evaluation
    liq_threshold_pct = (1.0 / leverage) - mmr

    print(f"\n[3/4] Simulating 20X high-frequency execution across {len(thresholds)} confidence levels...")

    results = {}
    summary_rows = []

    for tau in thresholds:
        capital = initial_capital
        nav_history = [capital]
        trades = []
        liquidations = 0

        asset_states = {
            k: {'in_pos': False, 'dir': 0, 'entry_bar': 0, 'entry_p': 0.0, 'tp_p': 0.0, 'sl_p': 0.0}
            for k in range(K)
        }

        for t in range(M):
            # Check open positions
            for k in range(K):
                st = asset_states[k]
                if not st['in_pos']:
                    continue

                bars_held = t - st['entry_bar']
                cur_high = val_prices[t, k, 1]
                cur_low = val_prices[t, k, 2]
                cur_close = val_prices[t, k, 3]
                p0 = st['entry_p']
                direction = st['dir']
                notional = margin_per_trade * leverage

                exit_triggered = False
                exit_type = ""
                raw_ret = 0.0
                fee = 0.0

                if direction == 1: # Long
                    adverse = (p0 - cur_low) / p0
                    if adverse >= liq_threshold_pct:
                        liquidations += 1
                        exit_triggered = True
                        net_pnl = -margin_per_trade
                    elif cur_low <= st['sl_p']:
                        exit_triggered = True
                        raw_ret = (st['sl_p'] - p0) / p0
                        fee = notional * (maker_fee + taker_fee + slippage)
                        net_pnl = notional * raw_ret - fee
                    elif cur_high >= st['tp_p']:
                        exit_triggered = True
                        raw_ret = (st['tp_p'] - p0) / p0
                        fee = notional * (maker_fee + maker_fee)
                        net_pnl = notional * raw_ret - fee
                    elif bars_held >= horizon:
                        exit_triggered = True
                        raw_ret = (cur_close - p0) / p0
                        fee = notional * (maker_fee + taker_fee + slippage)
                        net_pnl = notional * raw_ret - fee

                elif direction == -1: # Short
                    adverse = (cur_high - p0) / p0
                    if adverse >= liq_threshold_pct:
                        liquidations += 1
                        exit_triggered = True
                        net_pnl = -margin_per_trade
                    elif cur_high >= st['sl_p']:
                        exit_triggered = True
                        raw_ret = (p0 - st['sl_p']) / p0
                        fee = notional * (maker_fee + taker_fee + slippage)
                        net_pnl = notional * raw_ret - fee
                    elif cur_low <= st['tp_p']:
                        exit_triggered = True
                        raw_ret = (p0 - st['tp_p']) / p0
                        fee = notional * (maker_fee + maker_fee)
                        net_pnl = notional * raw_ret - fee
                    elif bars_held >= horizon:
                        exit_triggered = True
                        raw_ret = (p0 - cur_close) / p0
                        fee = notional * (maker_fee + taker_fee + slippage)
                        net_pnl = notional * raw_ret - fee

                if exit_triggered:
                    capital += net_pnl
                    trades.append(net_pnl)
                    st['in_pos'] = False

            # Check new entries
            if t < M - horizon and capital > margin_per_trade * 1.5:
                for k in range(K):
                    st = asset_states[k]
                    if st['in_pos']:
                        continue

                    p_long = all_prob_gate[t, k, 1]
                    p_short = all_prob_gate[t, k, 2]
                    exp_roe = all_pred_roe[t, k]
                    close_p = val_prices[t, k, 3]

                    if p_long >= tau and exp_roe >= min_roe_thresh:
                        st['in_pos'] = True
                        st['dir'] = 1
                        st['entry_bar'] = t
                        st['entry_p'] = close_p
                        st['tp_p'] = close_p * (1.0 + all_pred_tp[t, k])
                        st['sl_p'] = close_p * (1.0 - all_pred_sl[t, k])

                    elif p_short >= tau and exp_roe >= min_roe_thresh:
                        st['in_pos'] = True
                        st['dir'] = -1
                        st['entry_bar'] = t
                        st['entry_p'] = close_p
                        st['tp_p'] = close_p * (1.0 - all_pred_tp[t, k])
                        st['sl_p'] = close_p * (1.0 + all_pred_sl[t, k])

            # Sample nav curve every 60 bars (hourly) to conserve memory
            if t % 60 == 0 or t == M - 1:
                nav_history.append(capital)

        total_ret = (capital - initial_capital) / initial_capital * 100.0
        nav_s = pd.Series(nav_history)
        peak = nav_s.cummax()
        dd = (nav_s - peak) / peak
        max_dd = dd.min() * 100.0

        n_trades = len(trades)
        if n_trades > 0:
            trades_arr = np.array(trades)
            win_rate = (trades_arr > 0).mean() * 100.0
            gross_win = trades_arr[trades_arr > 0].sum()
            gross_loss = abs(trades_arr[trades_arr < 0].sum())
            pf = (gross_win / gross_loss) if gross_loss > 0 else float('inf')
            
            # Annualized Sharpe over 15-month validation period
            ret_hourly = nav_s.pct_change().dropna()
            sharpe = (ret_hourly.mean() / (ret_hourly.std() + 1e-8)) * np.sqrt(8760)
        else:
            win_rate = 0.0
            pf = 0.0
            sharpe = 0.0

        results[tau] = {
            'final_capital': capital,
            'total_return_pct': total_ret,
            'max_drawdown_pct': max_dd,
            'win_rate_pct': win_rate,
            'profit_factor': pf,
            'sharpe_ratio': sharpe,
            'total_trades': n_trades,
            'liquidations': liquidations,
            'nav_curve': nav_history
        }

        summary_rows.append({
            'Confidence Threshold (tau)': f"{tau:.2f}",
            'Total Return (%)': f"{total_ret:+.2f}%",
            'Max Drawdown (%)': f"{max_dd:.2f}%",
            'Sharpe Ratio': f"{sharpe:.2f}",
            'Win Rate (%)': f"{win_rate:.1f}%",
            'Profit Factor': f"{pf:.2f}",
            'Total Trades': n_trades,
            'Trades / Month': f"{n_trades / 15:.1f}",
            'Liquidations': liquidations
        })

        print(f"  tau={tau:.2f} -> Return: {total_ret:+.2f}% | MaxDD: {max_dd:.2f}% | Sharpe: {sharpe:.2f} | Trades: {n_trades} | Liq: {liquidations}")

    df_summary = pd.DataFrame(summary_rows)
    out_csv = os.path.join(charts_dir, "validation_confidence_summary_2025_2026.csv")
    os.makedirs(charts_dir, exist_ok=True)
    df_summary.to_csv(out_csv, index=False)

    print("\n" + "=" * 80)
    print("  Validation Set (2025/06 - 2026/09) Multi-Confidence Comparison Table:")
    print(df_summary.to_string(index=False))
    print("=" * 80)

    # 4. Plot Multi-Threshold Return Curves
    print(f"\n[4/4] Plotting multi-confidence return curves...")
    plt.figure(figsize=(14, 7), dpi=180)
    colors = ['#dc2626', '#ea580c', '#d97706', '#2563eb', '#10b981', '#059669']

    for idx, tau in enumerate(thresholds):
        curve = np.array(results[tau]['nav_curve']) / initial_capital * 100.0 - 100.0
        ret_val = results[tau]['total_return_pct']
        trades_val = results[tau]['total_trades']
        liq_val = results[tau]['liquidations']
        label_text = f"tau={tau:.2f} | Net Return: {ret_val:+.2f}% | Trades: {trades_val} | Liq: {liq_val}"
        lw = 2.4 if tau in [0.54, 0.55] else 1.5
        plt.plot(curve, label=label_text, color=colors[idx], linewidth=lw)

    plt.axhline(0, color='gray', linestyle='--', alpha=0.6)
    plt.title("20X Leverage Transformer Return Curves across Confidence Thresholds (Validation: 2025/06 - 2026/09)", fontsize=13, fontweight='bold', pad=12)
    plt.xlabel("Timeline (Hourly Snapshot over 15 Months, ~650,000 1m Bars)", fontsize=11)
    plt.ylabel("Cumulative Net Return (%)", fontsize=11)
    plt.grid(True, linestyle='--', alpha=0.4)
    plt.legend(loc='upper left', fontsize=10)
    plt.tight_layout()

    out_chart = os.path.join(charts_dir, "validation_confidence_curves_2025_2026.png")
    plt.savefig(out_chart)
    plt.close()
    print(f"Chart saved successfully -> {out_chart}")

    return results, df_summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-path', type=str, default=r"D:\Convertible_Bond_data\crypto_data\multi_asset_full_2020_2026.npz")
    parser.add_argument('--ckpt-path', type=str, default=r"c:\Users\liuqi\crypto\checkpoints\best_transformer_2020_2025.pt")
    args = parser.parse_args()
    run_validation_evaluation(data_path=args.data_path, ckpt_path=args.ckpt_path)
