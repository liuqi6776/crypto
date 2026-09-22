# -*- coding: utf-8 -*-
"""
Month-to-Date (Sept 1 - 22, 2026) ETH 100X Paper Trading Simulation Engine
2026年9月1日至22日以太坊 100倍杠杆实盘级模拟盘推演与逐笔盈亏流水引擎

Simulates:
1. Track A: 30% Golden Kelly Sizing (黄金凯利流: 30% 分仓 + 保本锁利)
2. Track B: 20% Scientific Sub-Allocation Sizing (科学稳健流: 20% 分仓 + 保本锁利)
3. Outputs full trade ledger: september_2026_paper_trades.csv
"""

import os
import sys
import numpy as np
import pandas as pd
import numba

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from transformer_channel_depth_engine import (
    compute_multi_timeframe_channels,
    compute_orderbook_confidence
)

DATA_PATH = r"D:\Convertible_Bond_data\crypto_data\history\futures_1m\ETHUSDT_2026_09_01_to_09_22.parquet"
OUTPUT_TRADES_CSV = r"c:\Users\liuqi\crypto\leverage_research\charts\september_2026_paper_trades.csv"
OUTPUT_SUMMARY_CSV = r"c:\Users\liuqi\crypto\leverage_research\charts\september_2026_summary.csv"
OUTPUT_CURVES_NPZ = r"c:\Users\liuqi\crypto\leverage_research\charts\september_2026_curves.npz"


@numba.njit
def simulate_paper_trading_100x(
    closes, opens, highs, lows, times_day, times_hour,
    channel_lows, channel_highs, is_oscillation,
    tau_long, tau_short,
    initial_equity=10000.0,
    tranche_frac=0.30,      # 30% Golden Kelly vs 20% Scientific
    leverage=100.0,
    sl_pct=0.0018,          # 0.18% Hard Stop-Loss (3.33x safety cushion before 0.60% liq)
    tp1_pct=0.0045,         # 0.45% Breakeven Lock Trigger (+45% ROE)
    tp2_pct=0.0090,         # 0.90% Final Take-Profit Target (+90% ROE)
    maker_fee=0.0004,       # 0.04% Round-trip Maker fee (4.0% ROE at 100x)
    tau_threshold=0.65,
    max_daily_trades=2
):
    """
    Numba-accelerated tick-by-tick simulation for continuous 1m bars.
    Records every trade execution with entry, exit, ROE, dollar PnL, equity, and exit reasons.
    """
    n = len(closes)
    fee_roe = maker_fee * leverage # 4.0% ROE
    liq_dist = 0.0060 # 0.60% at 100x
    
    max_trades = 1000
    t_side = np.zeros(max_trades, dtype=np.int32)        # 1: Long, -1: Short
    t_entry_p = np.zeros(max_trades, dtype=np.float64)
    t_exit_p = np.zeros(max_trades, dtype=np.float64)
    t_entry_idx = np.zeros(max_trades, dtype=np.int64)
    t_exit_idx = np.zeros(max_trades, dtype=np.int64)
    t_margin = np.zeros(max_trades, dtype=np.float64)
    t_margin_roe = np.zeros(max_trades, dtype=np.float64)
    t_dollar_pnl = np.zeros(max_trades, dtype=np.float64)
    t_equity_before = np.zeros(max_trades, dtype=np.float64)
    t_equity_after = np.zeros(max_trades, dtype=np.float64)
    t_res = np.zeros(max_trades, dtype=np.int32)         # 1: TP, -1: SL, 2: BE (Breakeven), -2: Liq, 0: Day Close
    t_day = np.zeros(max_trades, dtype=np.int32)
    
    # Track continuous equity curve (1 value per bar)
    bar_equity = np.zeros(n, dtype=np.float64)
    bar_equity[0] = initial_equity
    
    trade_count = 0
    portfolio_equity = initial_equity
    
    in_pos = False
    side = 0
    ep = 0.0
    e_idx = 0
    sl_p = 0.0
    tp1_p = 0.0
    tp2_p = 0.0
    be_active = False
    trade_margin = 0.0
    
    current_day = -1
    day_trades = 0
    day_had_tp = False
    
    for i in range(1, n):
        day = times_day[i]
        hr = times_hour[i]
        
        # Day Rollover Check
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
                t_res[trade_count] = 0 # Day close
                t_day[trade_count] = day
                trade_count += 1
                in_pos = False
                
        # Trading hour filter: 08:00 to 23:00 UTC (European & US active sessions)
        if hr < 8 or hr >= 23:
            bar_equity[i] = portfolio_equity
            continue

        p_close = closes[i]
        p_high = highs[i]
        p_low = lows[i]
        c_low = channel_lows[i]
        c_high = channel_highs[i]
        c_amp = (c_high - c_low) / c_low if c_low > 0 else 0.0
        
        if not in_pos:
            # Check Daily Quota & Profit Lock
            if day_trades >= max_daily_trades or day_had_tp:
                bar_equity[i] = portfolio_equity
                continue
                
            # Check Oscillation Regime
            if is_oscillation[i] == 0 or c_amp < 0.0035 or c_amp > 0.0150:
                bar_equity[i] = portfolio_equity
                continue
                
            # 1. Maker Long Entry at Channel_lower with High Conviction
            if (p_low <= c_low * 1.0002 and p_close >= c_low * 0.9995 and tau_long[i] >= tau_threshold):
                in_pos = True
                side = 1
                ep = c_low
                e_idx = i
                trade_margin = portfolio_equity * tranche_frac
                be_active = False
                sl_p = ep * (1.0 - sl_pct)
                target_move = min(tp1_pct, c_amp * 0.75)
                tp2_p = ep * (1.0 + target_move)
                day_trades += 1
                
            # 2. Maker Short Entry at Channel_upper with High Conviction
            elif (p_high >= c_high * 0.9998 and p_close <= c_high * 1.0005 and tau_short[i] >= tau_threshold):
                in_pos = True
                side = -1
                ep = c_high
                e_idx = i
                trade_margin = portfolio_equity * tranche_frac
                be_active = False
                sl_p = ep * (1.0 + sl_pct)
                target_move = min(tp1_pct, c_amp * 0.75)
                tp2_p = ep * (1.0 - target_move)
                day_trades += 1
                
        else: # IN POSITION
            if side == 1: # LONG
                # 1. Liquidation Check (0.60% cliff)
                if (ep - p_low) / ep >= liq_dist:
                    net_roe = -1.0
                    pnl = -trade_margin
                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = ep * (1.0 - liq_dist)
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_margin[trade_count] = trade_margin
                    t_margin_roe[trade_count] = net_roe
                    t_dollar_pnl[trade_count] = pnl
                    t_equity_before[trade_count] = portfolio_equity
                    portfolio_equity += pnl
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = -2
                    t_day[trade_count] = day
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
                    
                # 3. Take Profit Trigger (Target reached)
                if p_high >= tp2_p:
                    target_move = (tp2_p - ep) / ep
                    net_roe = target_move * leverage - fee_roe
                    pnl = trade_margin * net_roe
                    
                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = tp2_p
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_margin[trade_count] = trade_margin
                    t_margin_roe[trade_count] = net_roe
                    t_dollar_pnl[trade_count] = pnl
                    t_equity_before[trade_count] = portfolio_equity
                    portfolio_equity += pnl
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = 1 # Take-Profit
                    t_day[trade_count] = day
                    trade_count += 1
                    in_pos = False
                    day_had_tp = True
                    bar_equity[i] = portfolio_equity
                    continue
                    
                # 4. Stop-Loss Trigger (Hard Stop or Breakeven Stop)
                if p_low <= sl_p:
                    loss_pct = (sl_p - ep) / ep
                    net_roe = loss_pct * leverage - fee_roe
                    pnl = trade_margin * net_roe
                    
                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = sl_p
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_margin[trade_count] = trade_margin
                    t_margin_roe[trade_count] = net_roe
                    t_dollar_pnl[trade_count] = pnl
                    t_equity_before[trade_count] = portfolio_equity
                    portfolio_equity += pnl
                    portfolio_equity = max(portfolio_equity, 10.0)
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = 2 if be_active else -1 # 2: Breakeven lock, -1: Stop-loss
                    t_day[trade_count] = day
                    trade_count += 1
                    in_pos = False
                    bar_equity[i] = portfolio_equity
                    continue

                    
            else: # SHORT
                # 1. Liquidation Check
                if (p_high - ep) / ep >= liq_dist:
                    net_roe = -1.0
                    pnl = -trade_margin
                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = ep * (1.0 + liq_dist)
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_margin[trade_count] = trade_margin
                    t_margin_roe[trade_count] = net_roe
                    t_dollar_pnl[trade_count] = pnl
                    t_equity_before[trade_count] = portfolio_equity
                    portfolio_equity += pnl
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = -2
                    t_day[trade_count] = day
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
                    
                # 3. Take Profit Trigger (Target reached)
                if p_low <= tp2_p:
                    target_move = (ep - tp2_p) / ep
                    net_roe = target_move * leverage - fee_roe
                    pnl = trade_margin * net_roe
                    
                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = tp2_p
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_margin[trade_count] = trade_margin
                    t_margin_roe[trade_count] = net_roe
                    t_dollar_pnl[trade_count] = pnl
                    t_equity_before[trade_count] = portfolio_equity
                    portfolio_equity += pnl
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = 1 # Take-Profit
                    t_day[trade_count] = day
                    trade_count += 1
                    in_pos = False
                    day_had_tp = True
                    bar_equity[i] = portfolio_equity
                    continue
                    
                # 4. Stop-Loss Trigger (Hard Stop or Breakeven Stop)
                if p_high >= sl_p:
                    loss_pct = (ep - sl_p) / ep
                    net_roe = loss_pct * leverage - fee_roe
                    pnl = trade_margin * net_roe
                    
                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = sl_p
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_margin[trade_count] = trade_margin
                    t_margin_roe[trade_count] = net_roe
                    t_dollar_pnl[trade_count] = pnl
                    t_equity_before[trade_count] = portfolio_equity
                    portfolio_equity += pnl
                    portfolio_equity = max(portfolio_equity, 10.0)
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = 2 if be_active else -1 # 2: Breakeven lock, -1: Stop-loss
                    t_day[trade_count] = day
                    trade_count += 1
                    in_pos = False
                    bar_equity[i] = portfolio_equity
                    continue
                    
        # Update bar equity while in position (mark-to-market)
        if in_pos:
            unrealized_gain = (closes[i] - ep) / ep if side == 1 else (ep - closes[i]) / ep
            unrealized_pnl = trade_margin * (unrealized_gain * leverage - fee_roe)
            bar_equity[i] = max(10.0, portfolio_equity + unrealized_pnl)
        else:
            bar_equity[i] = portfolio_equity
            
    return (trade_count, portfolio_equity,
            t_side[:trade_count], t_entry_p[:trade_count], t_exit_p[:trade_count],
            t_entry_idx[:trade_count], t_exit_idx[:trade_count],
            t_margin[:trade_count], t_margin_roe[:trade_count],
            t_dollar_pnl[:trade_count], t_equity_before[:trade_count],
            t_equity_after[:trade_count], t_res[:trade_count], t_day[:trade_count],
            bar_equity)


def run_simulation():
    print("=" * 80)
    print("Running Month-to-Date (Sept 1 - 22, 2026) ETH 100X Paper Trading Simulation")
    print("=" * 80)
    
    if not os.path.exists(DATA_PATH):
        print(f"Error: Dataset not found at {DATA_PATH}")
        return
        
    df = pd.read_parquet(DATA_PATH)
    print(f"Loaded {len(df):,} 1m bars from {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}")
    
    # Set DatetimeIndex for resampling
    df = df.set_index('datetime')
    
    # 1. Compute multi-timeframe channels
    print(">>> 1. Extracting Multi-Timeframe Channels (5m, 15m, ATR Volatility Squeeze)...")
    df = compute_multi_timeframe_channels(df)
    
    # 2. Compute Level-2 order book depth & wall proxy
    print(">>> 2. Computing Order Book Depth Imbalance (OBI) & Buy/Sell Walls...")
    df_dummy = df.reset_index().rename(columns={'index': 'open_time'})
    df = compute_orderbook_confidence(df_dummy, df)
    
    # Generate mock Transformer confidence proxies (derived from 5m trend + 1m momentum alignment)
    ema20 = df['close'].ewm(span=20).mean()
    ema50 = df['close'].ewm(span=50).mean()
    # Trend bias from EMA20 and EMA50
    trend_bias = (ema20 - ema50) / ema50
    
    # Fused confidence score: Orderbook wall conviction + Macro trend bias
    tau_long = np.clip(df['score_ob_long'] + np.tanh(trend_bias * 300.0) * 0.20, 0.0, 1.0).values.astype(np.float64)
    tau_short = np.clip(df['score_ob_short'] - np.tanh(trend_bias * 300.0) * 0.20, 0.0, 1.0).values.astype(np.float64)
    
    times = df.index
    times_day = (times - times[0]).days.values.astype(np.int32)
    times_hour = times.hour.values.astype(np.int32)
    
    closes = df['close'].values.astype(np.float64)
    opens = df['open'].values.astype(np.float64)
    highs = df['high'].values.astype(np.float64)
    lows = df['low'].values.astype(np.float64)
    c_lows = df['channel_lower'].values.astype(np.float64)
    c_highs = df['channel_upper'].values.astype(np.float64)
    is_osc = df['is_oscillation'].values.astype(np.int32)
    
    # Run Track A: 30% Golden Kelly Sizing
    print("\n>>> 3. Running Track A: 30% Golden Kelly Sizing (黄金凯利流)...")
    (tc_a, eq_a, sides_a, eps_a, xps_a, eis_a, xis_a, margins_a, roes_a,
     pnls_a, eq_b_a, eq_a_a, res_a, days_a, bar_eq_a) = simulate_paper_trading_100x(
        closes, opens, highs, lows, times_day, times_hour,
        c_lows, c_highs, is_osc, tau_long, tau_short,
        initial_equity=10000.0, tranche_frac=0.30, leverage=100.0,
        sl_pct=0.0018, tp1_pct=0.0045, tp2_pct=0.0045, maker_fee=0.0004,
        tau_threshold=0.70, max_daily_trades=2
    )
    
    # Run Track B: 20% Scientific Baseline Sizing
    print(">>> 4. Running Track B: 20% Scientific Sub-Allocation Sizing (科学稳健流)...")
    (tc_b, eq_b, sides_b, eps_b, xps_b, eis_b, xis_b, margins_b, roes_b,
     pnls_b, eq_b_b, eq_a_b, res_b, days_b, bar_eq_b) = simulate_paper_trading_100x(
        closes, opens, highs, lows, times_day, times_hour,
        c_lows, c_highs, is_osc, tau_long, tau_short,
        initial_equity=10000.0, tranche_frac=0.20, leverage=100.0,
        sl_pct=0.0018, tp1_pct=0.0045, tp2_pct=0.0045, maker_fee=0.0004,
        tau_threshold=0.70, max_daily_trades=2
    )
    
    # Construct Detailed Trade Ledger for Track A (Primary User Focus)
    res_map = {1: 'Take-Profit (止盈)', -1: 'Stop-Loss (止损)', 2: 'Breakeven Lock (保本)', -2: 'Liquidation (爆仓)', 0: 'Day Close (收盘平仓)'}
    trade_records = []
    
    for k in range(tc_a):
        t_in = times[eis_a[k]]
        t_out = times[xis_a[k]]
        dur_min = (xis_a[k] - eis_a[k])
        trade_records.append({
            'trade_id': k + 1,
            'day_idx': days_a[k] + 1,
            'entry_time': str(t_in),
            'exit_time': str(t_out),
            'duration_min': dur_min,
            'direction': 'LONG (做多)' if sides_a[k] == 1 else 'SHORT (做空)',
            'entry_price': round(eps_a[k], 2),
            'exit_price': round(xps_a[k], 2),
            'margin_allocated': round(margins_a[k], 2),
            'leverage': '100X',
            'net_margin_roe_pct': round(roes_a[k] * 100.0, 2),
            'dollar_pnl': round(pnls_a[k], 2),
            'equity_before': round(eq_b_a[k], 2),
            'equity_after': round(eq_a_a[k], 2),
            'exit_reason': res_map.get(res_a[k], 'Other')
        })
        
    df_trades = pd.DataFrame(trade_records)
    os.makedirs(os.path.dirname(OUTPUT_TRADES_CSV), exist_ok=True)
    df_trades.to_csv(OUTPUT_TRADES_CSV, index=False, encoding='utf-8-sig')
    print(f"\nSaved detailed trade ledger ({len(df_trades)} trades) to: {OUTPUT_TRADES_CSV}")
    
    # Save Curves for Plotting
    np.savez(
        OUTPUT_CURVES_NPZ,
        bar_equity_a=bar_eq_a,
        bar_equity_b=bar_eq_b,
        closes=closes,
        timestamps=times.values,
        eis_a=eis_a,
        xis_a=xis_a,
        sides_a=sides_a,
        eps_a=eps_a,
        xps_a=xps_a,
        res_a=res_a,
        pnls_a=pnls_a,
        roes_a=roes_a
    )
    print(f"Saved equity curves to: {OUTPUT_CURVES_NPZ}")
    
    # Compute Master Summary Metrics
    def calc_metrics(name, tc, final_eq, res, roes, pnls, bar_eq):
        tot_ret = (final_eq / 10000.0 - 1.0) * 100.0
        wins = res == 1
        be = res == 2
        losses = res == -1
        liqs = (res == -2).sum()
        win_rate = (wins.sum() / tc * 100.0) if tc > 0 else 0.0
        effective_win_rate = ((wins.sum() + be.sum()) / tc * 100.0) if tc > 0 else 0.0
        
        cum_max = np.maximum.accumulate(bar_eq)
        dd = (cum_max - bar_eq) / cum_max * 100.0
        max_dd = dd.max()
        
        profit_sum = pnls[pnls > 0].sum()
        loss_sum = abs(pnls[pnls < 0].sum())
        pf = profit_sum / loss_sum if loss_sum > 0 else 999.0
        
        daily_rate = tc / 22.0
        
        return {
            'strategy': name,
            'total_trades': tc,
            'daily_trades': round(daily_rate, 2),
            'win_rate': round(win_rate, 1),
            'effective_win_rate (Win+BE)': round(effective_win_rate, 1),
            'tp_count': int(wins.sum()),
            'be_count': int(be.sum()),
            'sl_count': int(losses.sum()),
            'liquidations': int(liqs),
            'final_equity': round(final_eq, 2),
            'total_return_pct': round(tot_ret, 2),
            'max_drawdown_pct': round(max_dd, 2),
            'profit_factor': round(pf, 2)
        }
        
    m_a = calc_metrics('Track A: 30% Golden Kelly (黄金凯利流)', tc_a, eq_a, res_a, roes_a, pnls_a, bar_eq_a)
    m_b = calc_metrics('Track B: 20% Scientific Baseline (科学稳健流)', tc_b, eq_b, res_b, roes_b, pnls_b, bar_eq_b)
    
    df_sum = pd.DataFrame([m_a, m_b])
    df_sum.to_csv(OUTPUT_SUMMARY_CSV, index=False, encoding='utf-8-sig')
    print(f"Saved summary metrics to: {OUTPUT_SUMMARY_CSV}")
    
    print("\n" + "=" * 95)
    print("  MONTH-TO-DATE (SEPTEMBER 1 - 22, 2026) PAPER TRADING SUMMARY")
    print("=" * 95)
    for m in [m_a, m_b]:
        print(f"Strategy: {m['strategy']}")
        print(f"  Trades: {m['total_trades']} ({m['daily_trades']}/day) | Win Rate: {m['win_rate']}% | Win+BE Rate: {m['effective_win_rate (Win+BE)']}%")
        print(f"  TP: {m['tp_count']} | Breakeven: {m['be_count']} | SL: {m['sl_count']} | Liquidations: {m['liquidations']}")
        print(f"  Initial: $10,000.00 -> Final: ${m['final_equity']:,.2f} ({m['total_return_pct']:+.2f}%)")
        print(f"  Max Drawdown: {m['max_drawdown_pct']:.2f}% | Profit Factor: {m['profit_factor']:.2f}")
        print("-" * 95)


if __name__ == "__main__":
    run_simulation()
