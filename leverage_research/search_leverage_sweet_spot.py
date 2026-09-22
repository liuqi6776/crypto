"""
Search for Optimal Leverage vs Friction Sweet Spot (10X - 100X).
Evaluates across 206,545 1m bars of Out-of-Sample Test Period (May 1 - Sept 21, 2026).
Simulates realistic micro-execution:
- Maker limit entry (0.02% fee) with 2 bps orderbook penetration requirement to simulate queue fill.
- Maker limit TP (0.02% fee, 0 slippage).
- Stop Market Taker SL (0.05% fee + 2 bps market execution slippage).
- Stop Market Taker BE (0.05% fee + 1 bp market slippage).
"""

import os
import sys
import time
import numpy as np
import pandas as pd
import numba

from transformer_channel_depth_engine import (
    compute_multi_timeframe_channels,
    compute_orderbook_confidence
)

@numba.njit
def simulate_realistic_leverage_nb(
    closes, opens, highs, lows, times_day, times_hour, times_month,
    channel_lows, channel_highs, is_oscillation,
    tau_long, tau_short,
    initial_equity=10000.0,
    tranche_frac=0.30,
    leverage=30.0,
    sl_pct=0.0040,                  # calibrated stop-loss distance
    tp_pct=0.0125,                  # calibrated take-profit distance
    maker_pen_pct=0.0002,           # 2 bps penetration required for Maker fill
    entry_fee_rate=0.0002,          # 0.02% Maker
    tp_fee_rate=0.0002,             # 0.02% Maker
    sl_fee_rate=0.0005,             # 0.05% Stop Market Taker
    sl_slippage_pct=0.0002,         # 2 bps market slippage on stop-loss
    be_fee_rate=0.0005,             # 0.05% Stop Market Taker
    be_slippage_pct=0.0001,         # 1 bp market slippage on BE
    tau_threshold=0.70,
    max_daily_trades=2
):
    n = len(closes)
    # Liquidation threshold distance based on MMR
    # For leverage L, bankruptcy distance ~ 1 / L * (1 - MMR)
    # MMR approx 0.0040 for crypto perp
    mmr = 0.0050
    liq_dist = (1.0 / leverage) * (1.0 - mmr)

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

            if is_oscillation[i] == 0 or c_amp < (sl_pct * 1.5) or c_amp > 0.035:
                bar_equity[i] = portfolio_equity
                continue

            # Maker Long Entry: Price must penetrate c_low by maker_pen_pct to confirm queue fill!
            limit_buy = c_low
            fill_req_buy = limit_buy * (1.0 - maker_pen_pct)
            if tau_long[i] >= tau_threshold and p_low <= fill_req_buy and p_close >= limit_buy * 0.9985:
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

            # Maker Short Entry: Price must penetrate c_high by maker_pen_pct
            limit_sell = c_high
            fill_req_sell = limit_sell * (1.0 + maker_pen_pct)
            if tau_short[i] >= tau_threshold and p_high >= fill_req_sell and p_close <= limit_sell * 1.0015:
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
                # Catastrophic gap liquidation check on open
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
                # Breakeven lock when profit reaches 40% of target move
                if not be_active and curr_roe >= (tp_pct * leverage * 0.40):
                    be_active = True
                    # Lock price slightly above entry price to guarantee positive outcome after Taker exit fee + slippage
                    sl_p = max(sl_p, ep * (1.0 + (entry_fee_rate + be_fee_rate + be_slippage_pct) + 0.0003))

                # TP Fill (Maker Limit)
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

                # SL / BE Trigger (Stop Market Taker + Slippage)
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
                if not be_active and curr_roe >= (tp_pct * leverage * 0.40):
                    be_active = True
                    sl_p = min(sl_p, ep * (1.0 - (entry_fee_rate + be_fee_rate + be_slippage_pct) - 0.0003))

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
        t_res[:trade_count]
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
            'calmar': 0.0, 'win_rate': 0.0, 'win_be_rate': 0.0, 'profit_factor': 0.0,
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

    rets = np.diff(equity_curve[::1440]) / equity_curve[::1440][:-1] if len(equity_curve) > 1440 else np.array([0.0])
    sharpe = (np.mean(rets) / (np.std(rets) + 1e-8)) * np.sqrt(365) if len(rets) > 1 else 0.0
    calmar = (net_return / max_dd) if max_dd > 0 else 0.0

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
        'liquidations': liq_trades
    }

def main():
    print("=" * 90)
    print("  PARAMETRIC LEVERAGE SWEET SPOT SEARCH (10X to 100X) UNDER REALISTIC FRICTION")
    print("=" * 90)

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

    # Leverage grid with calibrated targets
    # (Leverage, Target Move %, Stop Loss %)
    grid = [
        (10.0, 0.0350, 0.0100),
        (15.0, 0.0250, 0.0075),
        (20.0, 0.0200, 0.0060),
        (25.0, 0.0150, 0.0050),
        (30.0, 0.0125, 0.0040),
        (40.0, 0.0100, 0.0032),
        (50.0, 0.0080, 0.0025),
        (75.0, 0.0060, 0.0020),
        (100.0, 0.0045, 0.0018)
    ]

    results = []

    print(f"{'Lev':>5} | {'TP Move':>8} | {'SL Move':>8} | {'FrictionDrag':>12} | {'NetRet(Kelly)':>13} | {'MaxDD(K)':>9} | {'Sharpe':>7} | {'Calmar':>7} | {'Win+BE':>7} | {'Trades':>6} | {'Liq':>3}")
    print("-" * 105)

    for lev, tp_pct, sl_pct in grid:
        # Calculate theoretical round-trip friction drag ratio
        # Maker entry (0.02%) + Taker exit (0.05%) + 2 bps slip = 0.09% price friction
        price_friction = 0.0002 + 0.0005 + 0.0002 # 9 bps
        friction_roe = price_friction * lev * 100.0
        gross_tp_roe = tp_pct * lev * 100.0
        friction_drag_pct = (friction_roe / gross_tp_roe) * 100.0

        out_k = simulate_realistic_leverage_nb(
            p_c, p_o, p_h, p_l, times_day, times_hr, times_mon,
            c_l, c_h, osc, tau_long_gated, tau_short_gated,
            initial_equity=10000.0, tranche_frac=0.30, leverage=lev,
            sl_pct=sl_pct, tp_pct=tp_pct,
            maker_pen_pct=0.0002,           # 2 bps penetration to fill
            entry_fee_rate=0.0002,
            tp_fee_rate=0.0002,
            sl_fee_rate=0.0005,
            sl_slippage_pct=0.0002,
            be_fee_rate=0.0005,
            be_slippage_pct=0.0001,
            tau_threshold=0.70, max_daily_trades=2
        )
        eq_k = out_k[0]
        roe_k = out_k[7]
        res_k = out_k[11]

        m_k = compute_metrics(eq_k, roe_k, res_k, label=f"Lev {lev:.0f}x (30% Kelly)")
        m_k['leverage'] = lev
        m_k['tp_pct'] = tp_pct
        m_k['sl_pct'] = sl_pct
        m_k['friction_drag_pct'] = friction_drag_pct

        out_s = simulate_realistic_leverage_nb(
            p_c, p_o, p_h, p_l, times_day, times_hr, times_mon,
            c_l, c_h, osc, tau_long_gated, tau_short_gated,
            initial_equity=10000.0, tranche_frac=0.20, leverage=lev,
            sl_pct=sl_pct, tp_pct=tp_pct,
            maker_pen_pct=0.0002,
            entry_fee_rate=0.0002,
            tp_fee_rate=0.0002,
            sl_fee_rate=0.0005,
            sl_slippage_pct=0.0002,
            be_fee_rate=0.0005,
            be_slippage_pct=0.0001,
            tau_threshold=0.70, max_daily_trades=2
        )
        eq_s = out_s[0]
        roe_s = out_s[7]
        res_s = out_s[11]
        m_s = compute_metrics(eq_s, roe_s, res_s, label=f"Lev {lev:.0f}x (20% Sci)")
        m_s['leverage'] = lev
        m_s['tp_pct'] = tp_pct
        m_s['sl_pct'] = sl_pct
        m_s['friction_drag_pct'] = friction_drag_pct

        results.append(m_k)
        results.append(m_s)

        print(f"{lev:4.0f}x | {tp_pct*100:7.2f}% | {sl_pct*100:7.2f}% | {friction_drag_pct:10.1f}% | {m_k['net_return']:+12.2f}% | {m_k['max_dd']:8.2f}% | {m_k['sharpe']:7.2f} | {m_k['calmar']:7.2f} | {m_k['win_be_rate']:6.1f}% | {m_k['total_trades']:6d} | {m_k['liquidations']:3d}")

    df_res = pd.DataFrame(results)
    out_csv = r"c:\Users\liuqi\crypto\leverage_research\charts\leverage_sweet_spot_summary.csv"
    df_res.to_csv(out_csv, index=False)
    print(f"\n[OK] Sweet spot grid search completed! Saved to {out_csv}")

if __name__ == '__main__':
    main()
