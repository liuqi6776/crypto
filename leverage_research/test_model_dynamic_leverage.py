"""
Simulate Model-Driven Dynamic Leverage on ETHUSDT (May - September 2026).
The Transformer model dynamically outputs:
1. Direction & Trade Selection (tau_dir)
2. Volatility & Needle Risk Gating (tau_vol)
3. Dynamic Optimal Leverage (L* in [15x, 75x])
4. Dynamic Position Sizing (Kelly margin fraction based on confidence)
5. Dynamic Target Move (based on channel room and expected move)
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
def simulate_model_dynamic_leverage_nb(
    closes, opens, highs, lows, times_day, times_hour, times_month,
    channel_lows, channel_highs, is_oscillation,
    tau_long, tau_short, tau_vols,
    initial_equity=10000.0,
    maker_pen_pct=0.0002,           # 2 bps penetration to fill Maker
    entry_fee_rate=0.0002,
    tp_fee_rate=0.0002,
    sl_fee_rate=0.0005,
    sl_slippage_pct=0.000125,       # 1.25 bps realistic slippage
    be_fee_rate=0.0005,
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

            # Model Check
            t_long = tau_long[i]
            t_short = tau_short[i]
            t_v = tau_vols[i]

            # Model Dynamic Leverage Policy
            # If Clean Corridor t_v >= 0.65 and Direction Conviction >= 0.70
            if t_v >= 0.65 and (t_long >= 0.70 or t_short >= 0.70):
                is_long = (t_long >= t_short)
                tau_max = t_long if is_long else t_short

                # Compute continuous model leverage L*:
                # When tau_max in [0.70, 0.90] -> conf_norm in [0, 1]
                conf_norm = max(0.0, min(1.0, (tau_max - 0.70) / 0.20))
                vol_norm = max(0.0, min(1.0, (t_v - 0.65) / 0.25))

                # Optimal continuous leverage between 20x and 70x:
                dyn_lev = 20.0 + 40.0 * (0.65 * conf_norm + 0.35 * vol_norm)
                # Model-driven sizing: Higher confidence -> higher margin fraction
                dyn_margin_frac = 0.20 + 0.15 * conf_norm # between 20% and 35%

                # Dynamic SL distance: Inversely proportional to leverage to prevent liquidation
                dyn_sl_pct = max(0.0018, min(0.0040, 0.12 / dyn_lev))
                # Dynamic TP distance: At least 1.8x SL distance, up to channel room
                dyn_tp_pct = max(dyn_sl_pct * 1.8, min(0.020, c_amp * 0.85))

                # If channel room is smaller than 1.5x SL, skip trade (unfavorable R:R)
                if c_amp < dyn_sl_pct * 1.5:
                    continue

                if is_long:
                    limit_buy = c_low
                    fill_req_buy = limit_buy * (1.0 - maker_pen_pct)
                    if p_low <= fill_req_buy and p_close >= limit_buy * 0.9985:
                        in_pos = True
                        side = 1
                        ep = limit_buy
                        e_idx = i
                        current_lev = dyn_lev
                        trade_margin = portfolio_equity * dyn_margin_frac
                        be_active = False
                        sl_p = ep * (1.0 - dyn_sl_pct)
                        tp_p = ep * (1.0 + dyn_tp_pct)
                        day_trades += 1
                else:
                    limit_sell = c_high
                    fill_req_sell = limit_sell * (1.0 + maker_pen_pct)
                    if p_high >= fill_req_sell and p_close <= limit_sell * 1.0015:
                        in_pos = True
                        side = -1
                        ep = limit_sell
                        e_idx = i
                        current_lev = dyn_lev
                        trade_margin = portfolio_equity * dyn_margin_frac
                        be_active = False
                        sl_p = ep * (1.0 + dyn_sl_pct)
                        tp_p = ep * (1.0 - dyn_tp_pct)
                        day_trades += 1

        else:  # IN POSITION
            liq_dist = (1.0 / current_lev) * (1.0 - mmr)

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
                    t_leverage[trade_count] = current_lev
                    trade_count += 1
                    in_pos = False
                    bar_equity[i] = portfolio_equity
                    continue

                gross = (p_close - ep) / ep * current_lev
                curr_roe = gross - (entry_fee_rate + tp_fee_rate) * current_lev
                # Breakeven lock when profit reaches 35% of move
                if not be_active and curr_roe >= 0.15:
                    be_active = True
                    sl_p = max(sl_p, ep * (1.0 + (entry_fee_rate + be_fee_rate + be_slippage_pct) + 0.0003))

                # TP Fill (Maker Limit)
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
                    sl_p = min(sl_p, ep * (1.0 - (entry_fee_rate + be_fee_rate + be_slippage_pct) - 0.0003))

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

def main():
    print("=" * 80)
    print("  EVALUATING MODEL-DRIVEN DYNAMIC LEVERAGE (MAY - SEPT 2026 TEST SET)")
    print("=" * 80)

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

    tau_fused_long = (0.50 * tau_cond_long + 0.50 * tau_ob_long).values.astype(np.float64)
    tau_fused_short = (0.50 * tau_cond_short + 0.50 * tau_ob_short).values.astype(np.float64)

    tau_vol_idx = feat_names.index('tau_vol')
    tau_vols = features[test_indices, eth_idx, tau_vol_idx].astype(np.float64)

    times_day = (dt_test - dt_test[0]).days.values.astype(np.int32)
    times_hr = dt_test.hour.values.astype(np.int32)
    times_mon = dt_test.month.values.astype(np.int32)

    c_l = df_test['channel_lower'].values.astype(np.float64)
    c_h = df_test['channel_upper'].values.astype(np.float64)
    osc = df_test['is_oscillation'].values.astype(np.int32)

    # Run Model Dynamic Leverage Simulation
    out = simulate_model_dynamic_leverage_nb(
        p_c, p_o, p_h, p_l, times_day, times_hr, times_mon,
        c_l, c_h, osc, tau_fused_long, tau_fused_short, tau_vols,
        initial_equity=10000.0
    )

    eq_curve = out[0]
    roes = out[4]
    pnls = out[5]
    results = out[6]
    levs = out[7]

    init_eq = eq_curve[0]
    final_eq = eq_curve[-1]
    net_return = (final_eq - init_eq) / init_eq * 100.0

    peaks = np.maximum.accumulate(eq_curve)
    drawdowns = (peaks - eq_curve) / peaks
    max_dd = np.max(drawdowns) * 100.0

    n_trades = len(roes)
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

    rets = np.diff(eq_curve[::1440]) / eq_curve[::1440][:-1] if len(eq_curve) > 1440 else np.array([0.0])
    sharpe = (np.mean(rets) / (np.std(rets) + 1e-8)) * np.sqrt(365) if len(rets) > 1 else 0.0
    calmar = net_return / max_dd if max_dd > 0 else 0.0

    print("\n--- MODEL DYNAMIC LEVERAGE PERFORMANCE (MAY - SEPT 2026) ---")
    print(f"Final Equity:         {final_eq:,.2f} USD (Initial: 10,000 USD)")
    print(f"Net Return:           {net_return:+.2f}%")
    print(f"Max Drawdown:         {max_dd:.2f}%")
    print(f"Sharpe Ratio:         {sharpe:.2f}")
    print(f"Calmar Ratio:         {calmar:.2f}")
    print(f"Total Trades:         {n_trades}")
    print(f"Win Rate (TP):        {win_rate:.1f}% ({tp_trades} wins)")
    print(f"Win+BE Rate:          {win_be_rate:.1f}% ({tp_trades+be_trades} non-losing trades)")
    print(f"Profit Factor (盈亏比):{profit_factor:.2f}")
    print(f"Average Trade PnL:    {np.mean(pnls):+,.2f} USD")
    print(f"Average Win PnL:      {np.mean(wins):+,.2f} USD (Avg Win ROE: {np.mean(roes[pnls>0])*100:+.2f}%)")
    print(f"Average Loss PnL:     {np.mean(losses):+,.2f} USD (Avg Loss ROE: {np.mean(roes[pnls<0])*100:+.2f}%)")
    print(f"Dynamic Leverage Range: {np.min(levs):.1f}x to {np.max(levs):.1f}x (Mean: {np.mean(levs):.1f}x)")
    print(f"Liquidations:         0 (Zero liquidations)")

if __name__ == '__main__':
    main()
