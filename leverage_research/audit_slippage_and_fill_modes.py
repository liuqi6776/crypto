"""
Audit Slippage, Maker vs Taker, and Order Fillability for 100X Dual-Engine Strategy.
Tests across May - September 2026 Out-of-Sample Test Period (206,545 1m bars).
"""

import os
import sys
import time
import numpy as np
import pandas as pd
import numba

from transformer_channel_depth_engine import (
    compute_multi_timeframe_channels,
    compute_orderbook_confidence,
    compute_adx_fast
)

@numba.njit
def simulate_execution_with_slippage_nb(
    closes, opens, highs, lows, times_day, times_hour, times_month,
    channel_lows, channel_highs, is_oscillation,
    tau_long, tau_short,
    initial_equity=10000.0,
    tranche_frac=0.30,
    leverage=100.0,
    sl_pct=0.0018,                  # 0.18% Stop-Loss
    tp_pct=0.0045,                  # 0.45% Take-Profit
    entry_mode=0,                   # 0: Maker, 1: Taker
    maker_penetration_pct=0.0003,   # 3 bps price penetration required for Maker fill
    entry_fee_rate=0.0002,          # 0.02% Maker or 0.05% Taker
    entry_slippage_pct=0.0,         # 0.0 for Maker, 0.0002 for Taker
    tp_fee_rate=0.0002,             # 0.02% Maker limit exit
    sl_fee_rate=0.0005,             # 0.05% Stop Market Taker exit
    sl_slippage_pct=0.0002,         # 2 bps slippage on market stop fill
    be_fee_rate=0.0005,             # 0.05% Breakeven stop Taker exit
    be_slippage_pct=0.0001,         # 1 bp slippage on BE stop fill
    tau_threshold=0.70,
    max_daily_trades=2
):
    n = len(closes)
    liq_dist = 0.0060  # 0.60% bankruptcy distance at 100x

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

    missed_maker_signals = 0
    total_signals = 0

    for i in range(1, n):
        day = times_day[i]
        hr = times_hour[i]
        month = times_month[i]

        if day != current_day:
            current_day = day
            day_trades = 0
            day_had_tp = False

            if in_pos:
                # EOD Market Close (Taker)
                p = closes[i]
                if side == 1:
                    raw_gain = (p - ep) / ep
                else:
                    raw_gain = (ep - p) / ep
                
                # Deduct entry fee + exit taker fee + slippage
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

            if is_oscillation[i] == 0 or c_amp < 0.0035 or c_amp > 0.0135:
                bar_equity[i] = portfolio_equity
                continue

            # Check Long Signal
            if tau_long[i] >= tau_threshold:
                total_signals += 1
                if entry_mode == 0:  # Maker Entry
                    # Maker order sits at c_low. Must penetrate by maker_penetration_pct to guarantee queue fill!
                    limit_price = c_low
                    fill_level = limit_price * (1.0 - maker_penetration_pct)
                    if p_low <= fill_level and p_close >= limit_price * 0.9990:
                        in_pos = True
                        side = 1
                        ep = limit_price
                        e_idx = i
                        trade_margin = portfolio_equity * tranche_frac
                        be_active = False
                        sl_p = ep * (1.0 - sl_pct)
                        target_move = min(tp_pct, c_amp * 0.75)
                        tp_p = ep * (1.0 + target_move)
                        day_trades += 1
                    else:
                        missed_maker_signals += 1
                else:  # Taker Entry (Instant Market Order)
                    in_pos = True
                    side = 1
                    # Filled with adverse slippage at market
                    ep = p_close * (1.0 + entry_slippage_pct)
                    e_idx = i
                    trade_margin = portfolio_equity * tranche_frac
                    be_active = False
                    sl_p = ep * (1.0 - sl_pct)
                    target_move = min(tp_pct, c_amp * 0.75)
                    tp_p = ep * (1.0 + target_move)
                    day_trades += 1

            # Check Short Signal
            elif tau_short[i] >= tau_threshold:
                total_signals += 1
                if entry_mode == 0:  # Maker Entry
                    limit_price = c_high
                    fill_level = limit_price * (1.0 + maker_penetration_pct)
                    if p_high >= fill_level and p_close <= limit_price * 1.0010:
                        in_pos = True
                        side = -1
                        ep = limit_price
                        e_idx = i
                        trade_margin = portfolio_equity * tranche_frac
                        be_active = False
                        sl_p = ep * (1.0 + sl_pct)
                        target_move = min(tp_pct, c_amp * 0.75)
                        tp_p = ep * (1.0 - target_move)
                        day_trades += 1
                    else:
                        missed_maker_signals += 1
                else:  # Taker Entry
                    in_pos = True
                    side = -1
                    ep = p_close * (1.0 - entry_slippage_pct)
                    e_idx = i
                    trade_margin = portfolio_equity * tranche_frac
                    be_active = False
                    sl_p = ep * (1.0 + sl_pct)
                    target_move = min(tp_pct, c_amp * 0.75)
                    tp_p = ep * (1.0 - target_move)
                    day_trades += 1

        else:  # IN POSITION
            if side == 1:  # LONG
                # 1. Catastrophic Gap Liquidation Check on Open
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

                # Breakeven Check
                gross = (p_close - ep) / ep * leverage
                curr_roe = gross - (entry_fee_rate + tp_fee_rate) * leverage
                if not be_active and curr_roe >= 0.15:
                    # Set Stop Market BE level above entry price to guarantee lock after taker exit fee + slippage
                    be_active = True
                    sl_p = max(sl_p, ep * (1.0 + (entry_fee_rate + be_fee_rate + be_slippage_pct) + 0.0002))

                # Take Profit Trigger (Maker Limit Order at tp_p, 0 slippage)
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

                # Stop Loss Trigger (Stop Market Order - Taker Fee + Slippage)
                elif p_low <= sl_p:
                    is_be = be_active and (sl_p > ep)
                    # Realized exit price suffers downward market slippage
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
                if not be_active and curr_roe >= 0.15:
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
        t_entry_idx[:trade_count],
        t_exit_idx[:trade_count],
        t_margin[:trade_count],
        t_margin_roe[:trade_count],
        t_dollar_pnl[:trade_count],
        t_equity_before[:trade_count],
        t_equity_after[:trade_count],
        t_res[:trade_count],
        t_day[:trade_count],
        t_month[:trade_count],
        missed_maker_signals,
        total_signals
    )


def compute_metrics(equity_curve, roes, results, label="", missed=0, signals=0):
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
            'total_trades': 0, 'liquidations': 0, 'final_equity': init_eq,
            'fill_rate': 0.0
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

    rets = np.diff(equity_curve[::1440]) / equity_curve[::1440][:-1] if len(equity_curve) > 1440 else np.array([0.0])
    sharpe = (np.mean(rets) / (np.std(rets) + 1e-8)) * np.sqrt(365) if len(rets) > 1 else 0.0

    fill_rate = (n_trades / signals * 100.0) if signals > 0 else 100.0

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
        'liquidations': liq_trades,
        'missed_signals': missed,
        'fill_rate': fill_rate
    }


def main():
    print("=" * 80)
    print("  AUDITING MAKER VS TAKER, SLIPPAGE, AND FILLABILITY (2026/05 - 2026/09)")
    print("=" * 80)

    data_path = r"D:\Convertible_Bond_data\crypto_data\multi_asset_split_2026_05.npz"
    cache_path = r"D:\Convertible_Bond_data\crypto_data\train_test_inference_cache.npz"

    data = np.load(data_path, allow_pickle=True)
    features = data['features']
    prices = data['prices']
    datetimes = data['datetimes']
    test_indices = data['test_indices']
    feat_names = data['feature_names'].tolist()

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

    # Regimes to test:
    regimes = [
        {
            'name': 'Regime 0: Theoretical Baseline',
            'desc': 'Maker Entry (Touch), 0 Slippage, Maker SL (Idealized)',
            'entry_mode': 0, 'maker_pen': 0.0,
            'entry_fee': 0.0002, 'entry_slip': 0.0,
            'tp_fee': 0.0002,
            'sl_fee': 0.0002, 'sl_slip': 0.0,
            'be_fee': 0.0002, 'be_slip': 0.0
        },
        {
            'name': 'Regime 1: Realistic Conservative Maker',
            'desc': 'Maker Entry (3 bps penetration to fill queue), 0 slip; Stop Market Taker SL (5 bps fee + 2 bps slip)',
            'entry_mode': 0, 'maker_pen': 0.0003,
            'entry_fee': 0.0002, 'entry_slip': 0.0,
            'tp_fee': 0.0002,
            'sl_fee': 0.0005, 'sl_slip': 0.0002,
            'be_fee': 0.0005, 'be_slip': 0.0001
        },
        {
            'name': 'Regime 2: Harsh Liquidity Maker',
            'desc': 'Maker Entry (5 bps penetration), Stop Market Taker SL (5 bps fee + 4 bps needle slip)',
            'entry_mode': 0, 'maker_pen': 0.0005,
            'entry_fee': 0.0002, 'entry_slip': 0.0,
            'tp_fee': 0.0002,
            'sl_fee': 0.0005, 'sl_slip': 0.0004,
            'be_fee': 0.0005, 'be_slip': 0.0002
        },
        {
            'name': 'Regime 3: Aggressive Market Taker',
            'desc': 'Taker Entry (5 bps fee + 2 bps slip, 100% fill), Maker TP, Stop Market Taker SL (5 bps + 2 bps slip)',
            'entry_mode': 1, 'maker_pen': 0.0,
            'entry_fee': 0.0005, 'entry_slip': 0.0002,
            'tp_fee': 0.0002,
            'sl_fee': 0.0005, 'sl_slip': 0.0002,
            'be_fee': 0.0005, 'be_slip': 0.0001
        },
        {
            'name': 'Regime 4: Severe Taker Friction',
            'desc': 'Taker Entry (5 bps fee + 4 bps slip), Maker TP, Stop Market Taker SL (5 bps + 4 bps slip)',
            'entry_mode': 1, 'maker_pen': 0.0,
            'entry_fee': 0.0005, 'entry_slip': 0.0004,
            'tp_fee': 0.0002,
            'sl_fee': 0.0005, 'sl_slip': 0.0004,
            'be_fee': 0.0005, 'be_slip': 0.0002
        }
    ]

    results_summary = []

    print("\nRunning Multi-Regime Execution Simulations...\n")
    for r in regimes:
        # Run 30% Kelly
        out_k = simulate_execution_with_slippage_nb(
            p_c, p_o, p_h, p_l, times_day, times_hr, times_mon,
            c_l, c_h, osc, tau_long_gated, tau_short_gated,
            initial_equity=10000.0, tranche_frac=0.30, leverage=100.0,
            sl_pct=0.0018, tp_pct=0.0045,
            entry_mode=r['entry_mode'],
            maker_penetration_pct=r['maker_pen'],
            entry_fee_rate=r['entry_fee'],
            entry_slippage_pct=r['entry_slip'],
            tp_fee_rate=r['tp_fee'],
            sl_fee_rate=r['sl_fee'],
            sl_slippage_pct=r['sl_slip'],
            be_fee_rate=r['be_fee'],
            be_slippage_pct=r['be_slip'],
            tau_threshold=0.70, max_daily_trades=2
        )
        eq_k = out_k[0]
        roe_k = out_k[7]
        res_k = out_k[11]
        missed = out_k[14]
        signals = out_k[15]
        m_k = compute_metrics(eq_k, roe_k, res_k, label=f"{r['name']} (30% Kelly)", missed=missed, signals=signals)
        m_k['desc'] = r['desc']

        # Run 20% Sci
        out_s = simulate_execution_with_slippage_nb(
            p_c, p_o, p_h, p_l, times_day, times_hr, times_mon,
            c_l, c_h, osc, tau_long_gated, tau_short_gated,
            initial_equity=10000.0, tranche_frac=0.20, leverage=100.0,
            sl_pct=0.0018, tp_pct=0.0045,
            entry_mode=r['entry_mode'],
            maker_penetration_pct=r['maker_pen'],
            entry_fee_rate=r['entry_fee'],
            entry_slippage_pct=r['entry_slip'],
            tp_fee_rate=r['tp_fee'],
            sl_fee_rate=r['sl_fee'],
            sl_slippage_pct=r['sl_slip'],
            be_fee_rate=r['be_fee'],
            be_slippage_pct=r['be_slip'],
            tau_threshold=0.70, max_daily_trades=2
        )
        eq_s = out_s[0]
        roe_s = out_s[7]
        res_s = out_s[11]
        m_s = compute_metrics(eq_s, roe_s, res_s, label=f"{r['name']} (20% Sci)", missed=missed, signals=signals)
        m_s['desc'] = r['desc']

        results_summary.append(m_k)
        results_summary.append(m_s)

        print(f"--- {r['name']} ---")
        print(f"  [Kelly 30%] Net Return: {m_k['net_return']:+.2f}% | Final: ${m_k['final_equity']:,.2f} | MaxDD: {m_k['max_dd']:.2f}% | Sharpe: {m_k['sharpe']:.2f} | Trades: {m_k['total_trades']} | Win+BE: {m_k['win_be_rate']:.1f}% | Liq: {m_k['liquidations']}")
        print(f"  [Sci 20%]   Net Return: {m_s['net_return']:+.2f}% | Final: ${m_s['final_equity']:,.2f} | MaxDD: {m_s['max_dd']:.2f}% | Sharpe: {m_s['sharpe']:.2f} | Trades: {m_s['total_trades']} | Win+BE: {m_s['win_be_rate']:.1f}% | Liq: {m_s['liquidations']}")
        if r['entry_mode'] == 0:
            print(f"  [Maker Execution] Total Channel Signals: {signals} | Missed/Unfilled: {missed} | Effective Filled Trades: {m_k['total_trades']}")
        print()

    df_res = pd.DataFrame(results_summary)
    csv_out = r"c:\Users\liuqi\crypto\leverage_research\charts\slippage_and_fill_audit.csv"
    df_res.to_csv(csv_out, index=False)
    print(f"\n[OK] Summary table saved to: {csv_out}")

if __name__ == '__main__':
    main()
