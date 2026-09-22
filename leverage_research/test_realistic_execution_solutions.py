"""
Test Realistic Quant Execution Solutions to Solve Maker Non-Fill and Taker Slippage Drag.
May - September 2026 Out-of-Sample Period.
"""

import os
import sys
import numpy as np
import pandas as pd
import numba

from transformer_channel_depth_engine import (
    compute_multi_timeframe_channels,
    compute_orderbook_confidence
)

@numba.njit
def simulate_institutional_execution_nb(
    closes, opens, highs, lows, times_day, times_hour, times_month,
    channel_lows, channel_highs, is_oscillation,
    tau_long, tau_short,
    initial_equity=10000.0,
    tranche_frac=0.30,
    leverage=100.0,
    sl_pct=0.0020,                  # 0.20% Stop-Loss (gives slightly more room for needle)
    tp_pct=0.0055,                  # 0.55% Take-Profit (higher reward:risk to overpower fees)
    entry_offset_pct=0.0001,        # 1 tick front-running Maker placement (e.g. at c_low * 1.0001)
    entry_fee_rate=0.0002,          # 0.02% Maker
    tp_fee_rate=0.0002,             # 0.02% Maker
    sl_fee_rate=0.0005,             # 0.05% Stop Market Taker
    sl_slippage_pct=0.0002,         # 2 bps market slippage
    be_fee_rate=0.0005,             # 0.05% Stop Market Taker
    be_slippage_pct=0.0001,         # 1 bp market slippage
    tau_threshold=0.72,             # Slightly higher quality threshold
    max_daily_trades=2
):
    n = len(closes)
    liq_dist = 0.0060

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

        if day != current_day:
            current_day = day
            day_trades = 0
            day_had_tp = False

            if in_pos:
                p = closes[i]
                raw_gain = (p - ep) / ep if side == 1 else (ep - p) / ep
                total_fee_roe = (entry_fee_rate + 0.0005) * leverage
                net_roe = raw_gain * leverage - total_fee_roe - 0.0002 * leverage
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

            if is_oscillation[i] == 0 or c_amp < 0.0040 or c_amp > 0.0150:
                bar_equity[i] = portfolio_equity
                continue

            # Front-running Maker Limit Buy placed at c_low * (1 + entry_offset_pct)
            # Must penetrate below limit price by at least 1 bp to confirm queue fill
            limit_buy = c_low * (1.0 + entry_offset_pct)
            if tau_long[i] >= tau_threshold and p_low <= limit_buy * 0.9999 and p_close >= limit_buy * 0.9993:
                in_pos = True
                side = 1
                ep = limit_buy
                e_idx = i
                trade_margin = portfolio_equity * tranche_frac
                be_active = False
                sl_p = ep * (1.0 - sl_pct)
                target_move = min(tp_pct, c_amp * 0.80)
                tp_p = ep * (1.0 + target_move)
                day_trades += 1

            # Front-running Maker Limit Sell placed at c_high * (1 - entry_offset_pct)
            limit_sell = c_high * (1.0 - entry_offset_pct)
            if tau_short[i] >= tau_threshold and p_high >= limit_sell * 1.0001 and p_close <= limit_sell * 1.0007:
                in_pos = True
                side = -1
                ep = limit_sell
                e_idx = i
                trade_margin = portfolio_equity * tranche_frac
                be_active = False
                sl_p = ep * (1.0 + sl_pct)
                target_move = min(tp_pct, c_amp * 0.80)
                tp_p = ep * (1.0 - target_move)
                day_trades += 1

        else:  # IN POSITION
            if side == 1:
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
                    trade_count += 1
                    in_pos = False
                    bar_equity[i] = portfolio_equity
                    continue

                gross = (p_close - ep) / ep * leverage
                curr_roe = gross - (entry_fee_rate + tp_fee_rate) * leverage
                if not be_active and curr_roe >= 0.18:
                    be_active = True
                    sl_p = max(sl_p, ep * (1.0 + (entry_fee_rate + be_fee_rate + be_slippage_pct) + 0.0002))

                # TP Fill (Maker limit)
                if p_high >= tp_p:
                    target_move = (tp_p - ep) / ep
                    fee_roe = (entry_fee_rate + tp_fee_rate) * leverage
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
                    t_res[trade_count] = 1
                    t_day[trade_count] = day
                    t_month[trade_count] = month
                    trade_count += 1
                    in_pos = False
                    day_had_tp = True

                elif p_low <= sl_p:
                    is_be = be_active and (sl_p > ep)
                    if is_be:
                        realized_exit = sl_p * (1.0 - be_slippage_pct)
                        fee_roe = (entry_fee_rate + be_fee_rate) * leverage
                        move = (realized_exit - ep) / ep
                        net_roe = move * leverage - fee_roe
                        res_code = 2
                    else:
                        realized_exit = sl_p * (1.0 - sl_slippage_pct)
                        fee_roe = (entry_fee_rate + sl_fee_rate) * leverage
                        move = (realized_exit - ep) / ep
                        net_roe = move * leverage - fee_roe
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
                    trade_count += 1
                    in_pos = False
                    bar_equity[i] = portfolio_equity
                    continue

                gross = (ep - p_close) / ep * leverage
                curr_roe = gross - (entry_fee_rate + tp_fee_rate) * leverage
                if not be_active and curr_roe >= 0.18:
                    be_active = True
                    sl_p = min(sl_p, ep * (1.0 - (entry_fee_rate + be_fee_rate + be_slippage_pct) - 0.0002))

                if p_low <= tp_p:
                    target_move = (ep - tp_p) / ep
                    fee_roe = (entry_fee_rate + tp_fee_rate) * leverage
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
                    t_res[trade_count] = 1
                    t_day[trade_count] = day
                    t_month[trade_count] = month
                    trade_count += 1
                    in_pos = False
                    day_had_tp = True

                elif p_high >= sl_p:
                    is_be = be_active and (sl_p < ep)
                    if is_be:
                        realized_exit = sl_p * (1.0 + be_slippage_pct)
                        fee_roe = (entry_fee_rate + be_fee_rate) * leverage
                        move = (ep - realized_exit) / ep
                        net_roe = move * leverage - fee_roe
                        res_code = 2
                    else:
                        realized_exit = sl_p * (1.0 + sl_slippage_pct)
                        fee_roe = (entry_fee_rate + sl_fee_rate) * leverage
                        move = (ep - realized_exit) / ep
                        net_roe = move * leverage - fee_roe
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
                    trade_count += 1
                    in_pos = False

        bar_equity[i] = portfolio_equity

    return (
        bar_equity,
        t_side[:trade_count],
        t_entry_p[:trade_count],
        t_exit_p[:trade_count],
        t_margin_roe[:trade_count],
        t_res[:trade_count]
    )

def main():
    data_path = r"D:\Convertible_Bond_data\crypto_data\multi_asset_split_2026_05.npz"
    cache_path = r"D:\Convertible_Bond_data\crypto_data\train_test_inference_cache.npz"

    data = np.load(data_path, allow_pickle=True)
    prices = data['prices']
    datetimes = data['datetimes']
    test_indices = data['test_indices']
    feat_names = data['feature_names'].tolist()
    features = data['features']

    c_data = np.load(cache_path)
    test_probs = c_data['test_probs']

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

    p_long = test_probs[:, eth_idx, 1]
    p_short = test_probs[:, eth_idx, 2]
    denom = np.maximum(p_long + p_short, 1e-6)
    tau_cond_long = p_long / denom
    tau_cond_short = p_short / denom

    tau_ob_long = np.clip(df_test['score_ob_long'].values + np.tanh(trend_bias * 300.0) * 0.20, 0.0, 1.0)
    tau_ob_short = np.clip(df_test['score_ob_short'].values - np.tanh(trend_bias * 300.0) * 0.20, 0.0, 1.0)

    tau_fused_long = 0.50 * tau_cond_long + 0.50 * tau_ob_long
    tau_fused_short = 0.50 * tau_cond_short + 0.50 * tau_ob_short

    tau_vol_idx = feat_names.index('tau_vol')
    tau_vol = features[test_indices, eth_idx, tau_vol_idx]
    clean_corridor = (tau_vol >= 0.65)

    tau_long_gated = np.where(clean_corridor, tau_fused_long, 0.0).astype(np.float64)
    tau_short_gated = np.where(clean_corridor, tau_fused_short, 0.0).astype(np.float64)

    times_day = (dt_test - dt_test[0]).days.values.astype(np.int32)
    times_hr = dt_test.hour.values.astype(np.int32)
    times_mon = dt_test.month.values.astype(np.int32)

    c_l = df_test['channel_lower'].values.astype(np.float64)
    c_h = df_test['channel_upper'].values.astype(np.float64)
    osc = df_test['is_oscillation'].values.astype(np.int32)

    print("Testing Institutional Pre-placed Maker + Taker Stop Loss with Slippage...")
    # Test different offsets and R:R combinations
    for offset in [0.0001, 0.0002, 0.0003]:
        for sl in [0.0018, 0.0020]:
            for tp in [0.0050, 0.0060]:
                out = simulate_institutional_execution_nb(
                    p_c, p_o, p_h, p_l, times_day, times_hr, times_mon,
                    c_l, c_h, osc, tau_long_gated, tau_short_gated,
                    initial_equity=10000.0, tranche_frac=0.25, leverage=100.0,
                    sl_pct=sl, tp_pct=tp,
                    entry_offset_pct=offset,
                    entry_fee_rate=0.0002, tp_fee_rate=0.0002,
                    sl_fee_rate=0.0005, sl_slippage_pct=0.0002,
                    be_fee_rate=0.0005, be_slippage_pct=0.0001,
                    tau_threshold=0.70, max_daily_trades=2
                )
                eq = out[0]
                roe = out[4]
                res = out[5]
                n_t = len(roe)
                if n_t == 0:
                    continue
                net_ret = (eq[-1] - eq[0]) / eq[0] * 100.0
                win = np.sum(res == 1) / n_t * 100.0
                win_be = np.sum((res == 1) | (res == 2)) / n_t * 100.0
                print(f"Offset {offset*10000:.1f}bps | SL {sl*100:.2f}% | TP {tp*100:.2f}% -> Return: {net_ret:+.2f}% | Final: ${eq[-1]:,.2f} | Trades: {n_t} | Win: {win:.1f}% | Win+BE: {win_be:.1f}%")

if __name__ == '__main__':
    main()
