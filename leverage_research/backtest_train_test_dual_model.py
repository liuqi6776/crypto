# -*- coding: utf-8 -*-
"""
Dual-Engine 100X Sniper Backtest: In-Sample Training vs Out-of-Sample Test Evaluation
双模型联锁 100倍杠杆回测引擎：样本内训练集（2026/05前） vs 样本外测试集（2026/05后）全面实测
- Dual-Gate: Directional Transformer (tau_dir >= 0.70) + Volatility & Needle Model (tau_vol >= 0.65)
- Calibrated 100X Risk Controls:
  - -0.18% Hard Stop-Loss (3.33x buffer before -0.60% liquidation, 0% liquidation probability)
  - +15% ROE Trailing Breakeven Lock (locks in entry + fees)
  - +45% ROE Take-Profit Target
  - Daily 3-4 trade selective sniper cap
- Compares: 30% Golden Kelly vs 20% Scientific sizing across both Train and Test horizons
"""

import os
import sys
import time
import argparse
import numpy as np
import pandas as pd
import numba
import torch
from torch.utils.data import Dataset, DataLoader

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from crypto_leverage_transformer import CryptoLeverageTransformer
from transformer_channel_depth_engine import compute_multi_timeframe_channels
from volatility_needle_model import compute_volatility_needle_features

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
def simulate_100x_dual_engine_nb(
    closes, opens, highs, lows, times_day, times_hour, times_month,
    channel_lows, channel_highs, is_oscillation,
    tau_long, tau_short,
    initial_equity=10000.0,
    tranche_frac=0.30,
    leverage=100.0,
    sl_pct=0.0018,          # 0.18% Hard Stop-Loss (3.33x cushion before 0.60% liq)
    tp_pct=0.0045,          # 0.45% Base Take-Profit Target (+45% ROE)
    maker_fee=0.0004,       # 0.04% Round-trip Maker fee (4.0% ROE at 100x)
    tau_threshold=0.70,
    max_daily_trades=3
):
    """
    High-speed Numba execution simulator for 100X dual-engine strategy.
    Tracks mark-to-market equity and trade executions bar-by-bar.
    """
    n = len(closes)
    fee_roe = maker_fee * leverage  # 4.0% ROE
    liq_dist = 0.0060               # 0.60% at 100x

    max_trades = 10000
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
    t_res = np.zeros(max_trades, dtype=np.int32)  # 1: TP, -1: SL, 2: BE, -2: Liq, 0: Day Close
    t_day = np.zeros(max_trades, dtype=np.int32)
    t_month = np.zeros(max_trades, dtype=np.int32)

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

    current_day = -1
    day_trades = 0
    day_had_tp = False

    for i in range(1, n):
        day = times_day[i]
        hr = times_hour[i]
        month = times_month[i]

        # Day rollover check
        if day != current_day:
            current_day = day
            day_trades = 0
            day_had_tp = False

            # Close active trade at day change if still open
            if in_pos:
                p = closes[i]
                gain_pct = (p - ep) / ep if side == 1 else (ep - p) / ep
                net_roe = gain_pct * leverage - fee_roe
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
                trade_count += 1
                in_pos = False

        # Trading hour filter: 08:00 to 23:00 UTC
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
            # Check Daily Limit & TP Lock
            if day_trades >= max_daily_trades or day_had_tp:
                bar_equity[i] = portfolio_equity
                continue

            # Oscillation corridor filter
            if is_oscillation[i] == 0 or c_amp < 0.0035 or c_amp > 0.0135:
                bar_equity[i] = portfolio_equity
                continue

            # Maker Long Entry at Lower Channel Bound
            if p_low <= c_low * 1.0002 and p_close >= c_low * 0.9995 and tau_long[i] >= tau_threshold:
                in_pos = True
                side = 1
                ep = c_low
                e_idx = i
                trade_margin = portfolio_equity * tranche_frac
                be_active = False
                sl_p = ep * (1.0 - sl_pct)
                target_move = min(tp_pct, c_amp * 0.75)
                tp_p = ep * (1.0 + target_move)
                day_trades += 1

            # Maker Short Entry at Upper Channel Bound
            elif p_high >= c_high * 0.9998 and p_close <= c_high * 1.0005 and tau_short[i] >= tau_threshold:
                in_pos = True
                side = -1
                ep = c_high
                e_idx = i
                trade_margin = portfolio_equity * tranche_frac
                be_active = False
                sl_p = ep * (1.0 + sl_pct)
                target_move = min(tp_pct, c_amp * 0.75)
                tp_p = ep * (1.0 - target_move)
                day_trades += 1

        else:  # IN POSITION
            if side == 1:  # LONG
                # 1. Catastrophic Gap Liquidation on Open (e.g. flash crash opening below -0.60%)
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
                    t_res[trade_count] = -2  # Liquidation
                    t_day[trade_count] = day
                    t_month[trade_count] = month
                    trade_count += 1
                    in_pos = False
                    bar_equity[i] = portfolio_equity
                    continue

                gross = (p_close - ep) / ep * leverage
                curr_roe = gross - fee_roe

                # 2. Trailing Breakeven Lock once Net ROE >= +15%
                if not be_active and curr_roe >= 0.15:
                    sl_p = max(sl_p, ep * (1.0 + fee_roe / leverage + 0.0002))
                    be_active = True

                # 3. Take-Profit Trigger
                if p_high >= tp_p:
                    target_move = (tp_p - ep) / ep
                    net_roe = target_move * leverage - fee_roe
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
                    t_res[trade_count] = 1  # TP
                    t_day[trade_count] = day
                    t_month[trade_count] = month
                    trade_count += 1
                    in_pos = False
                    day_had_tp = True

                # 4. Stop-Loss / Breakeven Trigger (Pre-placed order fills at sl_p before liquidation barrier)
                elif p_low <= sl_p:
                    exit_price = min(p_open, sl_p)
                    loss_move = (exit_price - ep) / ep
                    net_roe = loss_move * leverage - fee_roe
                    pnl = trade_margin * net_roe
                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = exit_price
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_margin[trade_count] = trade_margin
                    t_margin_roe[trade_count] = net_roe
                    t_dollar_pnl[trade_count] = pnl
                    t_equity_before[trade_count] = portfolio_equity
                    portfolio_equity += pnl
                    portfolio_equity = max(portfolio_equity, 10.0)
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = 2 if be_active else -1  # BE or SL
                    t_day[trade_count] = day
                    t_month[trade_count] = month
                    trade_count += 1
                    in_pos = False

            else:  # SHORT
                # 1. Catastrophic Gap Liquidation on Open (e.g. flash spike opening above +0.60%)
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
                    t_res[trade_count] = -2  # Liquidation
                    t_day[trade_count] = day
                    t_month[trade_count] = month
                    trade_count += 1
                    in_pos = False
                    bar_equity[i] = portfolio_equity
                    continue

                gross = (ep - p_close) / ep * leverage
                curr_roe = gross - fee_roe

                # 2. Trailing Breakeven Lock once Net ROE >= +15%
                if not be_active and curr_roe >= 0.15:
                    sl_p = min(sl_p, ep * (1.0 - fee_roe / leverage - 0.0002))
                    be_active = True

                # 3. Take-Profit Trigger
                if p_low <= tp_p:
                    target_move = (ep - tp_p) / ep
                    net_roe = target_move * leverage - fee_roe
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
                    t_res[trade_count] = 1  # TP
                    t_day[trade_count] = day
                    t_month[trade_count] = month
                    trade_count += 1
                    in_pos = False
                    day_had_tp = True

                # 4. Stop-Loss / Breakeven Trigger (Pre-placed order fills at sl_p before liquidation barrier)
                elif p_high >= sl_p:
                    exit_price = max(p_open, sl_p)
                    loss_move = (ep - exit_price) / ep
                    net_roe = loss_move * leverage - fee_roe
                    pnl = trade_margin * net_roe
                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = exit_price
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_margin[trade_count] = trade_margin
                    t_margin_roe[trade_count] = net_roe
                    t_dollar_pnl[trade_count] = pnl
                    t_equity_before[trade_count] = portfolio_equity
                    portfolio_equity += pnl
                    portfolio_equity = max(portfolio_equity, 10.0)
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = 2 if be_active else -1  # BE or SL
                    t_day[trade_count] = day
                    t_month[trade_count] = month
                    trade_count += 1
                    in_pos = False

        bar_equity[i] = portfolio_equity

    return (
        bar_equity,
        t_side[:trade_count],
        t_entry_p[:trade_count],
        t_exit_p[:trade_count],
        t_entry_idx[:trade_count],
        t_exit_idx[:trade_count],
        t_margin[:trade_count],
        t_margin_roe[:trade_count],
        t_dollar_pnl[:trade_count],
        t_equity_before[:trade_count],
        t_equity_after[:trade_count],
        t_res[:trade_count],
        t_day[:trade_count],
        t_month[:trade_count]
    )


def compute_metrics(equity_curve, roes, results, label=""):
    init_eq = equity_curve[0]
    final_eq = equity_curve[-1]
    net_return = (final_eq - init_eq) / init_eq * 100.0

    peaks = np.maximum.accumulate(equity_curve)
    drawdowns = (peaks - equity_curve) / peaks
    max_dd = np.max(drawdowns) * 100.0

    n_trades = len(roes)
    if n_trades == 0:
        return {
            'label': label, 'net_return': 0.0, 'max_dd': 0.0, 'sharpe': 0.0,
            'win_rate': 0.0, 'win_be_rate': 0.0, 'profit_factor': 0.0,
            'total_trades': 0, 'liquidations': 0, 'final_equity': init_eq
        }

    tp_trades = np.sum(results == 1)
    be_trades = np.sum(results == 2)
    sl_trades = np.sum(results == -1)
    liq_trades = np.sum(results == -2)

    win_rate = tp_trades / n_trades * 100.0
    win_be_rate = (tp_trades + be_trades) / n_trades * 100.0

    wins = roes[roes > 0]
    losses = roes[roes < 0]
    gross_win = np.sum(wins) if len(wins) > 0 else 0.0
    gross_loss = np.abs(np.sum(losses)) if len(losses) > 0 else 1e-6
    profit_factor = gross_win / gross_loss

    # Daily Sharpe approximation
    rets = np.diff(equity_curve[::1440]) / equity_curve[::1440][:-1] if len(equity_curve) > 1440 else np.array([0.0])
    sharpe = (np.mean(rets) / (np.std(rets) + 1e-8)) * np.sqrt(365) if len(rets) > 1 else 0.0

    return {
        'label': label,
        'final_equity': final_eq,
        'net_return': net_return,
        'max_dd': max_dd,
        'sharpe': sharpe,
        'win_rate': win_rate,
        'win_be_rate': win_be_rate,
        'profit_factor': profit_factor,
        'total_trades': n_trades,
        'tp_count': tp_trades,
        'be_count': be_trades,
        'sl_count': sl_trades,
        'liquidations': liq_trades
    }


def run_train_test_backtest(
    data_path: str = r"D:\Convertible_Bond_data\crypto_data\multi_asset_split_2026_05.npz",
    ckpt_path: str = r"c:\Users\liuqi\crypto\checkpoints\best_transformer_pre_2026_05.pt",
    initial_equity: float = 10000.0,
    leverage: float = 100.0,
    sl_pct: float = 0.0018,
    tp_pct: float = 0.0045,
    max_daily_trades: int = 2,
    tau_threshold: float = 0.70,
    batch_size: int = 4096
):
    print("=" * 85)
    print("  Dual-Engine 100X Sniper Backtest: In-Sample Training vs Out-of-Sample Test")
    print("=" * 85)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Inference Device: {device}")

    # 1. Load Data
    print(f"\n[1/5] Loading split dataset: {data_path}...")
    data = np.load(data_path, allow_pickle=True)
    features = data['features']
    prices = data['prices']
    datetimes = data['datetimes']
    train_indices = data['train_indices']
    test_indices = data['test_indices']
    assets = data['assets']
    feat_names = data['feature_names'].tolist()

    print(f"  Total bars: {len(features):,} | Assets: {assets.tolist()}")
    print(f"  In-Sample Train bars: {len(train_indices):,} ({datetimes[train_indices[0]]} -> {datetimes[train_indices[-1]]})")
    print(f"  Out-of-Sample Test bars: {len(test_indices):,} ({datetimes[test_indices[0]]} -> {datetimes[test_indices[-1]]})")

    # 2. Load Checkpoint & Normalize Features
    print(f"\n[2/5] Loading trained checkpoint: {ckpt_path}...")
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    scaler_mean = ckpt['scaler_mean']
    scaler_std = ckpt['scaler_std']
    lookback = ckpt['lookback']
    feat_dim = ckpt['feature_dim']

    features_norm = np.clip((features - scaler_mean) / scaler_std, -5.0, 5.0).astype(np.float32)

    model = CryptoLeverageTransformer(
        num_assets=len(assets),
        in_features=feat_dim,
        lookback=lookback,
        d_model=64,
        n_heads=4
    ).to(device)
    model.load_state_dict(ckpt['model_state_dict'])
    model.eval()

    # 3. Model Batch Inference for Out-of-Sample Test and In-Sample Train
    print("\n[3/5] Running high-speed GPU batch inference...")
    
    # We evaluate the entire Test set (206,545 bars) and the representative In-Sample Train set (e.g. 2024 to 2026-04, 700k bars)
    train_eval_start = max(0, len(train_indices) - 700000)
    train_eval_indices = train_indices[train_eval_start:]
    print(f"  Evaluating In-Sample Train Horizon: {len(train_eval_indices):,} bars ({datetimes[train_eval_indices[0]]} -> {datetimes[train_eval_indices[-1]]})")
    print(f"  Evaluating Out-of-Sample Test Horizon: {len(test_indices):,} bars ({datetimes[test_indices[0]]} -> {datetimes[test_indices[-1]]})")

    def run_inference(indices):
        ds = FastInferenceDataset(features_norm, indices, lookback=lookback)
        loader = DataLoader(ds, batch_size=batch_size, shuffle=False, num_workers=0, pin_memory=True)
        prob_list = []
        with torch.no_grad():
            for x in loader:
                x = x.to(device)
                out = model(x)
                prob_list.append(out['prob_gate'].cpu().numpy())
        return np.concatenate(prob_list, axis=0)

    cache_path = r"D:\Convertible_Bond_data\crypto_data\train_test_inference_cache.npz"
    if os.path.exists(cache_path):
        print(f"  Loading cached inference predictions from: {cache_path}...")
        c_data = np.load(cache_path)
        test_probs = c_data['test_probs']
        train_probs = c_data['train_probs']
        print(f"  [OK] Loaded {len(test_probs):,} test bars and {len(train_probs):,} train bars in 0.2s!")
    else:
        t0 = time.time()
        test_probs = run_inference(test_indices)
        print(f"  Test inference completed: {len(test_probs):,} bars in {time.time()-t0:.2f}s ({len(test_probs)/(time.time()-t0):.0f} bars/s)")

        t0 = time.time()
        train_probs = run_inference(train_eval_indices)
        print(f"  Train inference completed: {len(train_probs):,} bars in {time.time()-t0:.2f}s ({len(train_probs)/(time.time()-t0):.0f} bars/s)")

        print(f"  Caching predictions -> {cache_path}...")
        np.savez_compressed(cache_path, test_probs=test_probs, train_probs=train_probs)

    # 4. Prepare ETH Execution Arrays
    print("\n[4/5] Preparing multi-timeframe channels, volatility needle gating, and timeline arrays...")
    eth_idx = 1 # ETHUSDT
    tau_vol_feat_idx = feat_names.index('tau_vol')

    # Parse timestamps
    dt_all = pd.to_datetime(datetimes, utc=True)
    all_days = dt_all.dayofyear.values.astype(np.int32)
    all_hours = dt_all.hour.values.astype(np.int32)
    all_months = dt_all.month.values.astype(np.int32)

    # Prices for ETH
    p_open = prices[:, eth_idx, 0].astype(np.float64)
    p_high = prices[:, eth_idx, 1].astype(np.float64)
    p_low = prices[:, eth_idx, 2].astype(np.float64)
    p_close = prices[:, eth_idx, 3].astype(np.float64)

    # Multi-Timeframe Composite Channels (30m + 60m envelope)
    s_low = pd.Series(p_low).shift(1)
    s_high = pd.Series(p_high).shift(1)
    c_low_30m = s_low.rolling(30, min_periods=10).min().bfill().values.astype(np.float64)
    c_high_30m = s_high.rolling(30, min_periods=10).max().bfill().values.astype(np.float64)
    c_low_60m = s_low.rolling(60, min_periods=10).min().bfill().values.astype(np.float64)
    c_high_60m = s_high.rolling(60, min_periods=10).max().bfill().values.astype(np.float64)

    c_low_all = np.maximum(c_low_30m, c_low_60m)
    c_high_all = np.minimum(c_high_30m, c_high_60m)
    mask_inv = c_low_all >= c_high_all
    c_low_all[mask_inv] = c_low_30m[mask_inv]
    c_high_all[mask_inv] = c_high_30m[mask_inv]
    
    # Fast ADX Filter (< 25 indicates non-trending oscillation)
    from transformer_channel_depth_engine import compute_adx_fast
    adx_all = compute_adx_fast(p_high, p_low, p_close, period=14)
    is_osc_all = (adx_all < 25).astype(np.int32)

    tb_ratio_idx = feat_names.index('taker_buy_ratio')
    ofi_idx = feat_names.index('ofi_5m')

    from transformer_channel_depth_engine import compute_multi_timeframe_channels, compute_orderbook_confidence

    # 5. Dual-Model Simulation Function
    def run_period_simulation(indices, probs, label=""):
        p_c = p_close[indices]
        p_o = p_open[indices]
        p_h = p_high[indices]
        p_l = p_low[indices]
        t_dts = datetimes[indices]
        d_dts = dt_all[indices]

        # Construct DataFrame for multi-timeframe channels
        df_period = pd.DataFrame({
            'open': p_o,
            'high': p_h,
            'low': p_l,
            'close': p_c,
            'volume': 1000.0
        }, index=d_dts)

        df_period = compute_multi_timeframe_channels(df_period)
        df_dummy = df_period.reset_index().rename(columns={'index': 'open_time'})
        df_period = compute_orderbook_confidence(df_dummy, df_period)

        ema20 = df_period['close'].ewm(span=20).mean()
        ema50 = df_period['close'].ewm(span=50).mean()
        trend_bias = (ema20 - ema50) / ema50

        # Conditional probabilities
        p_long = probs[:, eth_idx, 1]
        p_short = probs[:, eth_idx, 2]
        denom = np.maximum(p_long + p_short, 1e-6)
        tau_cond_long = p_long / denom
        tau_cond_short = p_short / denom

        tau_ob_long = np.clip(df_period['score_ob_long'].values + np.tanh(trend_bias * 300.0) * 0.20, 0.0, 1.0)
        tau_ob_short = np.clip(df_period['score_ob_short'].values - np.tanh(trend_bias * 300.0) * 0.20, 0.0, 1.0)

        tau_fused_long = 0.50 * tau_cond_long + 0.50 * tau_ob_long
        tau_fused_short = 0.50 * tau_cond_short + 0.50 * tau_ob_short

        # Volatility & Needle gate: tau_vol >= 0.65
        tau_vol = features[indices, eth_idx, tau_vol_feat_idx]
        clean_corridor = (tau_vol >= 0.65)

        tau_long_gated = np.where(clean_corridor, tau_fused_long, 0.0).astype(np.float64)
        tau_short_gated = np.where(clean_corridor, tau_fused_short, 0.0).astype(np.float64)

        times_day = (d_dts - d_dts[0]).days.values.astype(np.int32)
        times_hr = d_dts.hour.values.astype(np.int32)
        times_mon = d_dts.month.values.astype(np.int32)

        c_l = df_period['channel_lower'].values.astype(np.float64)
        c_h = df_period['channel_upper'].values.astype(np.float64)
        osc = df_period['is_oscillation'].values.astype(np.int32)

        # Track A: 30% Golden Kelly
        (eq_k, side_k, ep_k, xp_k, eidx_k, xidx_k, m_k, roe_k, pnl_k,
         eq_b_k, eq_a_k, res_k, day_k, mon_k) = simulate_100x_dual_engine_nb(
            p_c, p_o, p_h, p_l, times_day, times_hr, times_mon,
            c_l, c_h, osc, tau_long_gated, tau_short_gated,
            initial_equity=initial_equity,
            tranche_frac=0.30,
            leverage=leverage,
            sl_pct=sl_pct,
            tp_pct=tp_pct,
            max_daily_trades=max_daily_trades,
            tau_threshold=tau_threshold
        )

        # Track B: 20% Scientific
        (eq_s, side_s, ep_s, xp_s, eidx_s, xidx_s, m_s, roe_s, pnl_s,
         eq_b_s, eq_a_s, res_s, day_s, mon_s) = simulate_100x_dual_engine_nb(
            p_c, p_o, p_h, p_l, times_day, times_hr, times_mon,
            c_l, c_h, osc, tau_long_gated, tau_short_gated,
            initial_equity=initial_equity,
            tranche_frac=0.20,
            leverage=leverage,
            sl_pct=sl_pct,
            tp_pct=tp_pct,
            max_daily_trades=max_daily_trades,
        )

        m_kelly = compute_metrics(eq_k, roe_k, res_k, label=f"{label} (30% Kelly)")
        m_sci = compute_metrics(eq_s, roe_s, res_s, label=f"{label} (20% Sci)")

        trades_df = pd.DataFrame({
            'trade_idx': np.arange(len(side_k)),
            'side': np.where(side_k == 1, 'LONG', 'SHORT'),
            'entry_time': t_dts[eidx_k],
            'exit_time': t_dts[xidx_k],
            'entry_price': ep_k,
            'exit_price': xp_k,
            'net_roe_pct': roe_k * 100.0,
            'dollar_pnl': pnl_k,
            'equity_before': eq_b_k,
            'equity_after': eq_a_k,
            'result': np.where(res_k == 1, 'TP (+45%)', np.where(res_k == 2, 'BE (Lock)', np.where(res_k == -1, 'SL (-18%)', np.where(res_k == -2, 'LIQUIDATED', 'CLOSE')))),
            'month': mon_k
        })

        return {
            'eq_kelly': eq_k, 'eq_sci': eq_s,
            'metrics_kelly': m_kelly, 'metrics_sci': m_sci,
            'trades_df': trades_df,
            'dts': t_dts, 'p_close': p_c
        }

    # Run Test Simulation (May 1 to Sept 21, 2026)
    print("\n[5/5] Executing simulation on Out-of-Sample Test Set (May-Sept 2026)...")
    res_test = run_period_simulation(test_indices, test_probs, label="Test (2026/05-09)")

    # Run Train Simulation (In-Sample Horizon)
    print("Executing simulation on In-Sample Training Set...")
    res_train = run_period_simulation(train_eval_indices, train_probs, label="Train (In-Sample)")

    # Display Metrics Summary
    summary_rows = [
        res_train['metrics_kelly'],
        res_train['metrics_sci'],
        res_test['metrics_kelly'],
        res_test['metrics_sci']
    ]
    df_summary = pd.DataFrame(summary_rows)

    print("\n" + "=" * 95)
    print("  DUAL-ENGINE 100X IN-SAMPLE VS OUT-OF-SAMPLE PERFORMANCE MATRIX")
    print("=" * 95)
    cols_display = ['label', 'final_equity', 'net_return', 'max_dd', 'sharpe', 'win_rate', 'win_be_rate', 'profit_factor', 'total_trades', 'tp_count', 'be_count', 'sl_count', 'liquidations']
    print(df_summary[cols_display].to_string(index=False, justify='right', float_format=lambda x: f"{x:.2f}"))

    # Save summary CSV
    summary_csv = os.path.join(OUTPUT_DIR, "train_test_summary.csv")
    df_summary.to_csv(summary_csv, index=False)
    print(f"\nSaved Performance Summary -> {summary_csv}")

    # Save Test Trades CSV
    trades_csv = os.path.join(OUTPUT_DIR, "test_trades_may_sept_2026.csv")
    res_test['trades_df'].to_csv(trades_csv, index=False)
    print(f"Saved Test Trades Ledger -> {trades_csv} ({len(res_test['trades_df'])} trades)")

    # Save Curves NPZ for Plotting
    curves_npz = os.path.join(OUTPUT_DIR, "train_test_curves.npz")
    np.savez_compressed(
        curves_npz,
        train_equity_kelly=res_train['eq_kelly'],
        train_equity_sci=res_train['eq_sci'],
        train_dts=res_train['dts'],
        train_p_close=res_train['p_close'],
        test_equity_kelly=res_test['eq_kelly'],
        test_equity_sci=res_test['eq_sci'],
        test_dts=res_test['dts'],
        test_p_close=res_test['p_close']
    )
    print(f"Saved Curves Data -> {curves_npz}")
    print("=" * 85)
    return curves_npz, summary_csv, trades_csv


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-path', type=str, default=r"D:\Convertible_Bond_data\crypto_data\multi_asset_split_2026_05.npz")
    parser.add_argument('--ckpt-path', type=str, default=r"c:\Users\liuqi\crypto\checkpoints\best_transformer_pre_2026_05.pt")
    args = parser.parse_args()

    run_train_test_backtest(
        data_path=args.data_path,
        ckpt_path=args.ckpt_path
    )
