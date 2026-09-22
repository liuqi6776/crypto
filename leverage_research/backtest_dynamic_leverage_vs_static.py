"""
Comparative Backtest: Transformer Self-Adaptive Dynamic Leverage vs Static Fixed Leverages
Evaluates across 206,545 1m bars of Out-of-Sample Test Period (May 1 - Sept 21, 2026).
Compares:
1. Track 1: Fixed 100X
2. Track 2: Fixed 30X (Static Sweet Spot)
3. Track 3: Fixed 20X (Conservative)
4. Track 4: Model Self-Adaptive Dynamic Leverage (0X - 75X)
"""

import os
import sys
import time
import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader
import numba

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from crypto_leverage_transformer_with_policy import CryptoLeverageTransformerWithPolicy
from transformer_channel_depth_engine import (
    compute_multi_timeframe_channels,
    compute_orderbook_confidence
)

OUTPUT_DIR = r"c:\Users\liuqi\crypto\leverage_research\charts"
os.makedirs(OUTPUT_DIR, exist_ok=True)

class FastInferenceDataset(Dataset):
    def __init__(self, features: np.ndarray, indices: np.ndarray, lookback: int = 60):
        self.lookback = lookback
        self.indices = indices
        self.features = features

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, idx):
        t = self.indices[idx]
        x = self.features[t - self.lookback:t, :, :]  # (L, K, D)
        x = np.transpose(x, (1, 0, 2))                 # (K, L, D)
        return torch.from_numpy(x).float()

@numba.njit
def simulate_trade_engine_nb(
    closes, opens, highs, lows, times_day, times_hour, times_month,
    channel_lows, channel_highs, is_oscillation,
    tau_long, tau_short, tau_vols,
    model_leverages, model_tps, model_sls,
    mode=0,                         # 0: Dynamic, 1: Fixed 100x, 2: Fixed 30x, 3: Fixed 20x
    initial_equity=10000.0,
    maker_pen_pct=0.0002,           # 2 bps penetration to fill Maker
    entry_fee_rate=0.0002,          # 0.02% Maker
    tp_fee_rate=0.0002,             # 0.02% Maker
    sl_fee_rate=0.0005,             # 0.05% Stop Market Taker
    sl_slippage_pct=0.000125,       # 1.25 bps market slippage
    be_fee_rate=0.0005,             # 0.05% Stop Market Taker
    be_slippage_pct=0.00006,        # 0.6 bp slippage on BE
    max_daily_trades=2
):
    n = len(closes)
    mmr = 0.0050

    max_trades = 5000
    t_side = np.zeros(max_trades, dtype=np.int32)
    t_entry_p = np.zeros(max_trades, dtype=np.float64)
    t_exit_p = np.zeros(max_trades, dtype=np.float64)
    t_entry_idx = np.zeros(max_trades, dtype=np.int64)
    t_exit_idx = np.zeros(max_trades, dtype=np.int64)
    t_margin = np.zeros(max_trades, dtype=np.float64)
    t_margin_roe = np.zeros(max_trades, dtype=np.float64)
    t_dollar_pnl = np.zeros(max_trades, dtype=np.float64)
    t_equity_before = np.zeros(max_trades, dtype=np.float64)
    t_equity_after = np.zeros(max_trades, dtype=np.float64)
    t_res = np.zeros(max_trades, dtype=np.int32)
    t_day = np.zeros(max_trades, dtype=np.int32)
    t_month = np.zeros(max_trades, dtype=np.int32)
    t_leverage = np.zeros(max_trades, dtype=np.float64)

    bar_equity = np.zeros(n, dtype=np.float64)
    bar_equity[0] = initial_equity

    trade_count = 0
    portfolio_equity = initial_equity

    in_pos = False
    side = 0
    ep = 0.0
    e_idx = 0
    sl_p = 0.0
    tp_p = 0.0
    be_active = False
    trade_margin = 0.0
    current_lev = 30.0

    current_day = -1
    day_trades = 0
    day_had_tp = False

    for i in range(1, n):
        day = times_day[i]
        hr = times_hour[i]
        month = times_month[i]

        if day != current_day:
            current_day = day
            day_trades = 0
            day_had_tp = False

            if in_pos:
                p = closes[i]
                raw_gain = (p - ep) / ep if side == 1 else (ep - p) / ep
                total_fee_roe = (entry_fee_rate + 0.0005) * current_lev
                net_roe = raw_gain * current_lev - total_fee_roe - 0.0002 * current_lev
                pnl = trade_margin * net_roe

                t_side[trade_count] = side
                t_entry_p[trade_count] = ep
                t_exit_p[trade_count] = p
                t_entry_idx[trade_count] = e_idx
                t_exit_idx[trade_count] = i
                t_margin[trade_count] = trade_margin
                t_margin_roe[trade_count] = net_roe
                t_dollar_pnl[trade_count] = pnl
                t_equity_before[trade_count] = portfolio_equity
                portfolio_equity += pnl
                portfolio_equity = max(portfolio_equity, 10.0)
                t_equity_after[trade_count] = portfolio_equity
                t_res[trade_count] = 0
                t_day[trade_count] = day
                t_month[trade_count] = month
                t_leverage[trade_count] = current_lev
                trade_count += 1
                in_pos = False

        if hr < 8 or hr >= 23:
            bar_equity[i] = portfolio_equity
            continue

        p_open = opens[i]
        p_close = closes[i]
        p_high = highs[i]
        p_low = lows[i]
        c_low = channel_lows[i]
        c_high = channel_highs[i]
        c_amp = (c_high - c_low) / c_low if c_low > 0 else 0.0

        if not in_pos:
            if day_trades >= max_daily_trades or day_had_tp:
                bar_equity[i] = portfolio_equity
                continue

            if is_oscillation[i] == 0 or c_amp < 0.0035 or c_amp > 0.025:
                bar_equity[i] = portfolio_equity
                continue

            t_long = tau_long[i]
            t_short = tau_short[i]
            t_v = tau_vols[i]

            if t_v >= 0.65 and (t_long >= 0.70 or t_short >= 0.70):
                is_long = (t_long >= t_short)
                tau_max = t_long if is_long else t_short

                # Configure Leverage & TP/SL according to Mode
                if mode == 0: # Transformer Dynamic Leverage
                    conf_norm = max(0.0, min(1.0, (tau_max - 0.70) / 0.20))
                    vol_norm = max(0.0, min(1.0, (t_v - 0.65) / 0.25))
                    # Model outputs optimal continuous leverage
                    dyn_lev = max(2.0, min(75.0, model_leverages[i]))
                    lev = dyn_lev
                    margin_frac = 0.20 + 0.12 * conf_norm
                    sl_dist = max(0.0018, min(0.0045, 0.12 / lev))
                    tp_dist = min(c_amp * 0.75, 0.40 / lev)
                elif mode == 1: # Fixed 100x
                    lev = 100.0
                    margin_frac = 0.30
                    sl_dist = 0.0018
                    tp_dist = min(0.0045, c_amp * 0.75)
                elif mode == 2: # Fixed 30x
                    lev = 30.0
                    margin_frac = 0.30
                    sl_dist = 0.0040
                    tp_dist = min(0.0125, c_amp * 0.75)
                else: # Fixed 20x
                    lev = 20.0
                    margin_frac = 0.30
                    sl_dist = 0.0060
                    tp_dist = min(0.0200, c_amp * 0.75)

                if is_long:
                    limit_buy = c_low
                    fill_req_buy = limit_buy * (1.0 - maker_pen_pct)
                    if p_low <= fill_req_buy and p_close >= limit_buy * 0.9985:
                        in_pos = True
                        side = 1
                        ep = limit_buy
                        e_idx = i
                        current_lev = lev
                        trade_margin = portfolio_equity * margin_frac
                        be_active = False
                        sl_p = ep * (1.0 - sl_dist)
                        tp_p = ep * (1.0 + tp_dist)
                        day_trades += 1
                else:
                    limit_sell = c_high
                    fill_req_sell = limit_sell * (1.0 + maker_pen_pct)
                    if p_high >= fill_req_sell and p_close <= limit_sell * 1.0015:
                        in_pos = True
                        side = -1
                        ep = limit_sell
                        e_idx = i
                        current_lev = lev
                        trade_margin = portfolio_equity * margin_frac
                        be_active = False
                        sl_p = ep * (1.0 + sl_dist)
                        tp_p = ep * (1.0 - tp_dist)
                        day_trades += 1

        else:  # IN POSITION
            liq_dist = (1.0 / current_lev) * (1.0 - mmr)

            if side == 1:
                # 1. Catastrophic Gap Liquidation Check
                if (ep - p_open) / ep >= liq_dist:
                    net_roe = -1.0
                    pnl = -trade_margin
                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = p_open
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_margin[trade_count] = trade_margin
                    t_margin_roe[trade_count] = net_roe
                    t_dollar_pnl[trade_count] = pnl
                    t_equity_before[trade_count] = portfolio_equity
                    portfolio_equity += pnl
                    portfolio_equity = max(portfolio_equity, 10.0)
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = -2
                    t_day[trade_count] = day
                    t_month[trade_count] = month
                    t_leverage[trade_count] = current_lev
                    trade_count += 1
                    in_pos = False
                    bar_equity[i] = portfolio_equity
                    continue

                gross = (p_close - ep) / ep * current_lev
                curr_roe = gross - (entry_fee_rate + tp_fee_rate) * current_lev
                if not be_active and curr_roe >= 0.15:
                    be_active = True
                    sl_p = max(sl_p, ep * (1.0 + (entry_fee_rate + be_fee_rate + be_slippage_pct) + 0.0002))

                if p_high >= tp_p:
                    target_move = (tp_p - ep) / ep
                    fee_roe = (entry_fee_rate + tp_fee_rate) * current_lev
                    net_roe = target_move * current_lev - fee_roe
                    pnl = trade_margin * net_roe

                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = tp_p
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_margin[trade_count] = trade_margin
                    t_margin_roe[trade_count] = net_roe
                    t_dollar_pnl[trade_count] = pnl
                    t_equity_before[trade_count] = portfolio_equity
                    portfolio_equity += pnl
                    portfolio_equity = max(portfolio_equity, 10.0)
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = 1
                    t_day[trade_count] = day
                    t_month[trade_count] = month
                    t_leverage[trade_count] = current_lev
                    trade_count += 1
                    in_pos = False
                    day_had_tp = True

                elif p_low <= sl_p:
                    is_be = be_active and (sl_p > ep)
                    if is_be:
                        realized_exit = sl_p * (1.0 - be_slippage_pct)
                        fee_roe = (entry_fee_rate + be_fee_rate) * current_lev
                        move = (realized_exit - ep) / ep
                        net_roe = move * current_lev - fee_roe
                        res_code = 2
                    else:
                        realized_exit = sl_p * (1.0 - sl_slippage_pct)
                        fee_roe = (entry_fee_rate + sl_fee_rate) * current_lev
                        move = (realized_exit - ep) / ep
                        net_roe = move * current_lev - fee_roe
                        res_code = -1

                    pnl = trade_margin * net_roe
                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = realized_exit
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_margin[trade_count] = trade_margin
                    t_margin_roe[trade_count] = net_roe
                    t_dollar_pnl[trade_count] = pnl
                    t_equity_before[trade_count] = portfolio_equity
                    portfolio_equity += pnl
                    portfolio_equity = max(portfolio_equity, 10.0)
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = res_code
                    t_day[trade_count] = day
                    t_month[trade_count] = month
                    t_leverage[trade_count] = current_lev
                    trade_count += 1
                    in_pos = False

            else:  # SHORT
                if (p_open - ep) / ep >= liq_dist:
                    net_roe = -1.0
                    pnl = -trade_margin
                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = p_open
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_margin[trade_count] = trade_margin
                    t_margin_roe[trade_count] = net_roe
                    t_dollar_pnl[trade_count] = pnl
                    t_equity_before[trade_count] = portfolio_equity
                    portfolio_equity += pnl
                    portfolio_equity = max(portfolio_equity, 10.0)
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = -2
                    t_day[trade_count] = day
                    t_month[trade_count] = month
                    t_leverage[trade_count] = current_lev
                    trade_count += 1
                    in_pos = False
                    bar_equity[i] = portfolio_equity
                    continue

                gross = (ep - p_close) / ep * current_lev
                curr_roe = gross - (entry_fee_rate + tp_fee_rate) * current_lev
                if not be_active and curr_roe >= 0.15:
                    be_active = True
                    sl_p = min(sl_p, ep * (1.0 - (entry_fee_rate + be_fee_rate + be_slippage_pct) - 0.0002))

                if p_low <= tp_p:
                    target_move = (ep - tp_p) / ep
                    fee_roe = (entry_fee_rate + tp_fee_rate) * current_lev
                    net_roe = target_move * current_lev - fee_roe
                    pnl = trade_margin * net_roe

                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = tp_p
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_margin[trade_count] = trade_margin
                    t_margin_roe[trade_count] = net_roe
                    t_dollar_pnl[trade_count] = pnl
                    t_equity_before[trade_count] = portfolio_equity
                    portfolio_equity += pnl
                    portfolio_equity = max(portfolio_equity, 10.0)
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = 1
                    t_day[trade_count] = day
                    t_month[trade_count] = month
                    t_leverage[trade_count] = current_lev
                    trade_count += 1
                    in_pos = False
                    day_had_tp = True

                elif p_high >= sl_p:
                    is_be = be_active and (sl_p < ep)
                    if is_be:
                        realized_exit = sl_p * (1.0 + be_slippage_pct)
                        fee_roe = (entry_fee_rate + be_fee_rate) * current_lev
                        move = (ep - realized_exit) / ep
                        net_roe = move * current_lev - fee_roe
                        res_code = 2
                    else:
                        realized_exit = sl_p * (1.0 + sl_slippage_pct)
                        fee_roe = (entry_fee_rate + sl_fee_rate) * current_lev
                        move = (ep - realized_exit) / ep
                        net_roe = move * current_lev - fee_roe
                        res_code = -1

                    pnl = trade_margin * net_roe
                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = realized_exit
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_margin[trade_count] = trade_margin
                    t_margin_roe[trade_count] = net_roe
                    t_dollar_pnl[trade_count] = pnl
                    t_equity_before[trade_count] = portfolio_equity
                    portfolio_equity += pnl
                    portfolio_equity = max(portfolio_equity, 10.0)
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = res_code
                    t_day[trade_count] = day
                    t_month[trade_count] = month
                    t_leverage[trade_count] = current_lev
                    trade_count += 1
                    in_pos = False

        bar_equity[i] = portfolio_equity

    return (
        bar_equity,
        t_side[:trade_count],
        t_entry_p[:trade_count],
        t_exit_p[:trade_count],
        t_margin_roe[:trade_count],
        t_dollar_pnl[:trade_count],
        t_res[:trade_count],
        t_leverage[:trade_count]
    )

def compute_metrics(equity_curve, roes, pnls, results, levs, label=""):
    init_eq = equity_curve[0]
    final_eq = equity_curve[-1]
    net_return = (final_eq - init_eq) / init_eq * 100.0

    peaks = np.maximum.accumulate(equity_curve)
    drawdowns = (peaks - equity_curve) / peaks
    max_dd = np.max(drawdowns) * 100.0

    n_trades = len(roes)
    if n_trades == 0:
        return {'label': label, 'net_return': 0.0, 'max_dd': 0.0, 'sharpe': 0.0, 'profit_factor': 0.0}

    tp_trades = np.sum(results == 1)
    be_trades = np.sum(results == 2)
    sl_trades = np.sum(results == -1)

    win_rate = tp_trades / n_trades * 100.0
    win_be_rate = (tp_trades + be_trades) / n_trades * 100.0

    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gross_win = np.sum(wins) if len(wins) > 0 else 0.0
    gross_loss = np.abs(np.sum(losses)) if len(losses) > 0 else 1e-6
    profit_factor = gross_win / gross_loss

    rets = np.diff(equity_curve[::1440]) / equity_curve[::1440][:-1] if len(equity_curve) > 1440 else np.array([0.0])
    sharpe = (np.mean(rets) / (np.std(rets) + 1e-8)) * np.sqrt(365) if len(rets) > 1 else 0.0
    calmar = net_return / max_dd if max_dd > 0 else 0.0

    return {
        'label': label,
        'final_equity': final_eq,
        'net_return': net_return,
        'max_dd': max_dd,
        'sharpe': sharpe,
        'calmar': calmar,
        'win_rate': win_rate,
        'win_be_rate': win_be_rate,
        'profit_factor': profit_factor,
        'total_trades': n_trades,
        'tp_count': tp_trades,
        'be_count': be_trades,
        'sl_count': sl_trades,
        'avg_trade_pnl': np.mean(pnls),
        'avg_win_pnl': np.mean(wins) if len(wins) > 0 else 0.0,
        'avg_loss_pnl': np.mean(losses) if len(losses) > 0 else 0.0,
        'avg_win_roe': np.mean(roes[pnls > 0]) * 100.0 if len(wins) > 0 else 0.0,
        'avg_loss_roe': np.mean(roes[pnls < 0]) * 100.0 if len(losses) > 0 else 0.0,
        'mean_leverage': np.mean(levs),
        'min_leverage': np.min(levs),
        'max_leverage': np.max(levs),
        'liquidations': np.sum(results == -2)
    }

def main():
    print("=" * 85)
    print("  COMPARATIVE AUDIT: MODEL DYNAMIC LEVERAGE VS STATIC FIXED LEVERAGES")
    print("=" * 85)

    data_path = r"D:\Convertible_Bond_data\crypto_data\multi_asset_split_2026_05.npz"
    ckpt_path = r"c:\Users\liuqi\crypto\checkpoints\best_transformer_dynamic_leverage.pt"

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}")

    data = np.load(data_path, allow_pickle=True)
    features = data['features']
    prices = data['prices']
    datetimes = data['datetimes']
    test_indices = data['test_indices']
    assets = data['assets']
    feat_names = data['feature_names'].tolist()

    # Check if checkpoint exists or wait for task
    if not os.path.exists(ckpt_path):
        print(f"[WAIT] Checkpoint not found: {ckpt_path}. Training might still be in progress.")
        return

    print(f"Loading checkpoint: {ckpt_path}...")
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    scaler_mean = ckpt['scaler_mean']
    scaler_std = ckpt['scaler_std']
    lookback = ckpt['lookback']
    feat_dim = ckpt['feature_dim']

    features_norm = np.clip((features - scaler_mean) / scaler_std, -5.0, 5.0).astype(np.float32)

    model = CryptoLeverageTransformerWithPolicy(
        num_assets=len(assets),
        in_features=feat_dim,
        lookback=lookback,
        d_model=64,
        n_heads=4,
        num_layers=3,
        dim_feedforward=256,
        min_leverage=0.0,
        max_leverage=75.0
    ).to(device)
    model.load_state_dict(ckpt['model_state_dict'])
    model.eval()

    print("Running GPU batch inference on Out-of-Sample Test Set (206,545 bars)...")
    ds = FastInferenceDataset(features_norm, test_indices, lookback=lookback)
    loader = DataLoader(ds, batch_size=4096, shuffle=False, num_workers=0, pin_memory=True)

    prob_list = []
    lev_list = []
    tp_list = []
    sl_list = []

    with torch.no_grad():
        for x_b in loader:
            x_b = x_b.to(device)
            out = model(x_b)
            prob_list.append(out['prob_gate'].cpu().numpy())
            lev_list.append(out['pred_leverage'].cpu().numpy())
            tp_list.append(out['pred_tp_pct'].cpu().numpy())
            sl_list.append(out['pred_sl_pct'].cpu().numpy())

    probs = np.concatenate(prob_list, axis=0) # (N, K, 3)
    levs = np.concatenate(lev_list, axis=0)   # (N, K)
    tps = np.concatenate(tp_list, axis=0)     # (N, K)
    sls = np.concatenate(sl_list, axis=0)     # (N, K)

    eth_idx = 1
    p_c = prices[test_indices, eth_idx, 3].astype(np.float64)
    p_o = prices[test_indices, eth_idx, 0].astype(np.float64)
    p_h = prices[test_indices, eth_idx, 1].astype(np.float64)
    p_l = prices[test_indices, eth_idx, 2].astype(np.float64)

    dt_test = pd.to_datetime(datetimes[test_indices], utc=True)
    df_test = pd.DataFrame({'open': p_o, 'high': p_h, 'low': p_l, 'close': p_c, 'volume': 1000.0}, index=dt_test)
    df_test = compute_multi_timeframe_channels(df_test)
    df_dummy = df_test.reset_index().rename(columns={'index': 'open_time'})
    df_test = compute_orderbook_confidence(df_dummy, df_test)

    ema20 = df_test['close'].ewm(span=20).mean()
    ema50 = df_test['close'].ewm(span=50).mean()
    trend_bias = (ema20 - ema50) / ema50

    p_long = probs[:, eth_idx, 1]
    p_short = probs[:, eth_idx, 2]
    denom = np.maximum(p_long + p_short, 1e-6)
    tau_cond_long = p_long / denom
    tau_cond_short = p_short / denom

    tau_ob_long = np.clip(df_test['score_ob_long'].values + np.tanh(trend_bias.values * 300.0) * 0.20, 0.0, 1.0)
    tau_ob_short = np.clip(df_test['score_ob_short'].values - np.tanh(trend_bias.values * 300.0) * 0.20, 0.0, 1.0)

    tau_fused_long = (0.50 * tau_cond_long + 0.50 * tau_ob_long).astype(np.float64)
    tau_fused_short = (0.50 * tau_cond_short + 0.50 * tau_ob_short).astype(np.float64)

    tau_vol_idx = feat_names.index('tau_vol')
    tau_vols = features[test_indices, eth_idx, tau_vol_idx].astype(np.float64)

    times_day = (dt_test - dt_test[0]).days.values.astype(np.int32)
    times_hr = dt_test.hour.values.astype(np.int32)
    times_mon = dt_test.month.values.astype(np.int32)

    c_l = df_test['channel_lower'].values.astype(np.float64)
    c_h = df_test['channel_upper'].values.astype(np.float64)
    osc = df_test['is_oscillation'].values.astype(np.int32)

    model_lev_eth = levs[:, eth_idx].astype(np.float64)
    model_tp_eth = tps[:, eth_idx].astype(np.float64)
    model_sl_eth = sls[:, eth_idx].astype(np.float64)

    tracks = [
        ('Track 1: Fixed 100X', 1),
        ('Track 2: Fixed 30X (Sweet Spot)', 2),
        ('Track 3: Fixed 20X (Conservative)', 3),
        ('Track 4: Transformer Dynamic Leverage (0X-75X) ★★★', 0)
    ]

    all_metrics = []
    curves_dict = {}
    all_trades_records = []

    for name, mode_code in tracks:
        out = simulate_trade_engine_nb(
            p_c, p_o, p_h, p_l, times_day, times_hr, times_mon,
            c_l, c_h, osc, tau_fused_long, tau_fused_short, tau_vols,
            model_lev_eth, model_tp_eth, model_sl_eth,
            mode=mode_code,
            initial_equity=10000.0
        )
        eq_arr = out[0]
        sides = out[1]
        e_ps = out[2]
        x_ps = out[3]
        roes = out[4]
        pnls = out[5]
        res = out[6]
        trade_levs = out[7]

        for k in range(len(roes)):
            all_trades_records.append({
                'track': name,
                'mode': mode_code,
                'side': 'LONG' if sides[k] == 1 else 'SHORT',
                'entry_price': e_ps[k],
                'exit_price': x_ps[k],
                'margin_roe': roes[k],
                'dollar_pnl': pnls[k],
                'result_code': res[k],
                'leverage': trade_levs[k]
            })

        m = compute_metrics(eq_arr, roes, pnls, res, trade_levs, label=name)
        all_metrics.append(m)
        curves_dict[name] = eq_arr

        print(f"\n{name}:")
        print(f"  Final Equity: ${m['final_equity']:,.2f} | Net Return: {m['net_return']:+.2f}% | MaxDD: {m['max_dd']:.2f}%")
        print(f"  Sharpe: {m['sharpe']:.2f} | Calmar: {m['calmar']:.2f} | Profit Factor: {m['profit_factor']:.2f}")
        print(f"  Trades: {m['total_trades']} | Win+BE Rate: {m['win_be_rate']:.1f}% | Avg Trade: ${m['avg_trade_pnl']:+,.2f}")
        print(f"  Avg Win: ${m['avg_win_pnl']:,.2f} ({m['avg_win_roe']:+.2f}%) | Avg Loss: ${m['avg_loss_pnl']:,.2f} ({m['avg_loss_roe']:+.2f}%)")
        if mode_code == 0:
            print(f"  Model Leverage Used: Range {m['min_leverage']:.1f}x - {m['max_leverage']:.1f}x (Avg: {m['mean_leverage']:.1f}x)")

    df_summary = pd.DataFrame(all_metrics)
    csv_path = os.path.join(OUTPUT_DIR, "dynamic_vs_static_leverage_summary.csv")
    df_summary.to_csv(csv_path, index=False)
    
    df_trades = pd.DataFrame(all_trades_records)
    trades_path = os.path.join(OUTPUT_DIR, "dynamic_vs_static_trades.csv")
    df_trades.to_csv(trades_path, index=False)

    np.savez_compressed(os.path.join(OUTPUT_DIR, "dynamic_vs_static_curves.npz"), **curves_dict)
    print(f"\n[OK] Summary table saved -> {csv_path}")
    print(f"[OK] Trade records saved -> {trades_path}")

if __name__ == '__main__':
    main()
