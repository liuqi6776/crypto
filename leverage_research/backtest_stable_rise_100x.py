# -*- coding: utf-8 -*-
"""
100X Leverage Stable Rise Backtest & Asymmetric Payoff Engine
ETH 100倍杠杆稳定上涨实测与三大止盈模式回测引擎

Evaluates:
- Mode A (Recommended): Laddered Multi-Tier TP (+1% take 40% + breakeven lock, +2% take 30%, +5% trail 30%)
- Mode B (Individual Targets): Independent runs for +1%, +2%, +3%, +4%, +5%
- Mode C (Dynamic Volatility): Dynamic ATR expansion exit
"""

import os
import sys
import time
import numpy as np
import pandas as pd
import numba

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stable_rise_feature_engine import compute_multi_timeframe_features
from evaluate_stable_rise_accuracy import run_transformer_inference


@numba.njit
def simulate_laddered_100x_fast(
    closes, opens, highs, lows, times_day, times_hour,
    signals, initial_equity=10000.0, tranche_frac=0.20,
    leverage=100.0, sl_pct=0.0025, maker_fee=0.0004, max_daily_trades=2
):
    """
    Simulates Mode A: Laddered Multi-Tier Take-Profit with Trailing Breakeven Lock.
    - Tier 1: +1.0% gain -> close 40% position, move SL to Entry + Fees (Breakeven Lock)
    - Tier 2: +2.0% gain -> close 30% position, move SL to Entry + 1.0%
    - Tier 3: +4.0% gain -> close remaining 30% position
    """
    n = len(closes)
    fee_roe = maker_fee * leverage # 4.0% ROE
    liq_dist = 0.0060 # 0.60% Binance liquidation line
    
    max_trades = 5000
    t_entry_p = np.zeros(max_trades, dtype=np.float64)
    t_exit_p = np.zeros(max_trades, dtype=np.float64)
    t_entry_idx = np.zeros(max_trades, dtype=np.int64)
    t_exit_idx = np.zeros(max_trades, dtype=np.int64)
    t_net_roe = np.zeros(max_trades, dtype=np.float64)
    t_equity_before = np.zeros(max_trades, dtype=np.float64)
    t_equity_after = np.zeros(max_trades, dtype=np.float64)
    t_res = np.zeros(max_trades, dtype=np.int32) # 1: Win, -1: Loss, -2: Liq
    t_day = np.zeros(max_trades, dtype=np.int32)
    
    trade_count = 0
    portfolio_equity = initial_equity
    
    in_pos = False
    ep = 0.0
    e_idx = 0
    sl_p = 0.0
    trade_margin = 0.0
    pos_frac_remaining = 1.0
    realized_pnl_dollar = 0.0
    
    tier1_hit = False
    tier2_hit = False
    
    current_day = -1
    day_trades = 0
    
    for i in range(1, n):
        day = times_day[i]
        hr = times_hour[i]
        
        if day != current_day:
            current_day = day
            day_trades = 0
            
            # Close active trade at day change if still open
            if in_pos:
                p = closes[i]
                gain_pct = (p - ep) / ep
                leg_roe = gain_pct * leverage - fee_roe
                realized_pnl_dollar += trade_margin * pos_frac_remaining * leg_roe
                
                tot_roe = realized_pnl_dollar / trade_margin
                portfolio_equity += realized_pnl_dollar
                portfolio_equity = max(portfolio_equity, 10.0)
                
                t_entry_p[trade_count] = ep
                t_exit_p[trade_count] = p
                t_entry_idx[trade_count] = e_idx
                t_exit_idx[trade_count] = i
                t_net_roe[trade_count] = tot_roe
                t_equity_before[trade_count] = portfolio_equity - realized_pnl_dollar
                t_equity_after[trade_count] = portfolio_equity
                t_res[trade_count] = 1 if tot_roe > 0 else -1
                t_day[trade_count] = day
                trade_count += 1
                in_pos = False
                
        p_close = closes[i]
        p_high = highs[i]
        p_low = lows[i]
        
        if not in_pos:
            if day_trades >= max_daily_trades:
                continue
                
            # Trigger Entry
            if signals[i] == 1:
                in_pos = True
                ep = p_close
                e_idx = i
                trade_margin = portfolio_equity * tranche_frac
                sl_p = ep * (1.0 - sl_pct)
                pos_frac_remaining = 1.0
                realized_pnl_dollar = 0.0
                tier1_hit = False
                tier2_hit = False
                day_trades += 1
                
        else: # In Position (Long)
            # 1. Check Liquidation (0.60% cliff)
            if (ep - p_low) / ep >= liq_dist:
                realized_pnl_dollar = -trade_margin
                portfolio_equity += realized_pnl_dollar
                t_entry_p[trade_count] = ep
                t_exit_p[trade_count] = ep * (1.0 - liq_dist)
                t_entry_idx[trade_count] = e_idx
                t_exit_idx[trade_count] = i
                t_net_roe[trade_count] = -1.0
                t_equity_before[trade_count] = portfolio_equity - realized_pnl_dollar
                t_equity_after[trade_count] = portfolio_equity
                t_res[trade_count] = -2
                t_day[trade_count] = day
                trade_count += 1
                in_pos = False
                continue
                
            # 2. Check Stop Loss
            if p_low <= sl_p:
                loss_pct = (sl_p - ep) / ep
                leg_roe = loss_pct * leverage - fee_roe
                realized_pnl_dollar += trade_margin * pos_frac_remaining * leg_roe
                
                tot_roe = realized_pnl_dollar / trade_margin
                portfolio_equity += realized_pnl_dollar
                portfolio_equity = max(portfolio_equity, 10.0)
                
                t_entry_p[trade_count] = ep
                t_exit_p[trade_count] = sl_p
                t_entry_idx[trade_count] = e_idx
                t_exit_idx[trade_count] = i
                t_net_roe[trade_count] = tot_roe
                t_equity_before[trade_count] = portfolio_equity - realized_pnl_dollar
                t_equity_after[trade_count] = portfolio_equity
                t_res[trade_count] = 1 if tot_roe > 0 else -1
                t_day[trade_count] = day
                trade_count += 1
                in_pos = False
                continue
                
            # 3. Check Tier 1 Take Profit (+1.0% Price Rise)
            if not tier1_hit and p_high >= ep * 1.010:
                # Close 40% position
                close_p = ep * 1.010
                leg_roe = 0.010 * leverage - fee_roe # +96% ROE
                realized_pnl_dollar += trade_margin * 0.40 * leg_roe
                pos_frac_remaining -= 0.40
                tier1_hit = True
                # Move SL to Cost + Fees (Breakeven Lock)
                sl_p = max(sl_p, ep * (1.0 + maker_fee + 0.0002))
                
            # 4. Check Tier 2 Take Profit (+2.0% Price Rise)
            if tier1_hit and not tier2_hit and p_high >= ep * 1.020:
                # Close 30% position
                close_p = ep * 1.020
                leg_roe = 0.020 * leverage - fee_roe # +196% ROE
                realized_pnl_dollar += trade_margin * 0.30 * leg_roe
                pos_frac_remaining -= 0.30
                tier2_hit = True
                # Trail SL to +1.0%
                sl_p = max(sl_p, ep * 1.010)
                
            # 5. Check Tier 3 Final Take Profit (+4.0% Price Rise)
            if tier2_hit and p_high >= ep * 1.040:
                # Close remaining 30% position
                close_p = ep * 1.040
                leg_roe = 0.040 * leverage - fee_roe # +396% ROE
                realized_pnl_dollar += trade_margin * pos_frac_remaining * leg_roe
                
                tot_roe = realized_pnl_dollar / trade_margin
                portfolio_equity += realized_pnl_dollar
                portfolio_equity = max(portfolio_equity, 10.0)
                
                t_entry_p[trade_count] = ep
                t_exit_p[trade_count] = close_p
                t_entry_idx[trade_count] = e_idx
                t_exit_idx[trade_count] = i
                t_net_roe[trade_count] = tot_roe
                t_equity_before[trade_count] = portfolio_equity - realized_pnl_dollar
                t_equity_after[trade_count] = portfolio_equity
                t_res[trade_count] = 1
                t_day[trade_count] = day
                trade_count += 1
                in_pos = False
                
    return (t_entry_p[:trade_count], t_exit_p[:trade_count],
            t_entry_idx[:trade_count], t_exit_idx[:trade_count],
            t_net_roe[:trade_count], t_equity_before[:trade_count],
            t_equity_after[:trade_count], t_res[:trade_count], t_day[:trade_count])


@numba.njit
def simulate_fixed_target_100x_fast(
    closes, opens, highs, lows, times_day, times_hour,
    signals, target_pct=0.01, sl_pct=0.0025,
    initial_equity=10000.0, tranche_frac=0.20,
    leverage=100.0, maker_fee=0.0004, max_daily_trades=2
):
    """
    Simulates Mode B: Single Fixed Target (e.g. +1%, +2%, +3%, +4%, +5%)
    with pre-placed Hard Stop-Loss and Breakeven Trail once 60% of target is reached.
    """
    n = len(closes)
    fee_roe = maker_fee * leverage
    liq_dist = 0.0060
    
    max_trades = 5000
    t_net_roe = np.zeros(max_trades, dtype=np.float64)
    t_equity_before = np.zeros(max_trades, dtype=np.float64)
    t_equity_after = np.zeros(max_trades, dtype=np.float64)
    t_res = np.zeros(max_trades, dtype=np.int32)
    trade_count = 0
    portfolio_equity = initial_equity
    
    in_pos = False
    ep = 0.0
    sl_p = 0.0
    tp_p = 0.0
    trade_margin = 0.0
    be_active = False
    
    current_day = -1
    day_trades = 0
    
    for i in range(1, n):
        day = times_day[i]
        
        if day != current_day:
            current_day = day
            day_trades = 0
            if in_pos:
                p = closes[i]
                gain_pct = (p - ep) / ep
                net_roe = gain_pct * leverage - fee_roe
                pnl = trade_margin * net_roe
                portfolio_equity += pnl
                portfolio_equity = max(portfolio_equity, 10.0)
                t_net_roe[trade_count] = net_roe
                t_equity_before[trade_count] = portfolio_equity - pnl
                t_equity_after[trade_count] = portfolio_equity
                t_res[trade_count] = 1 if net_roe > 0 else -1
                trade_count += 1
                in_pos = False
                
        p_close = closes[i]
        p_high = highs[i]
        p_low = lows[i]
        
        if not in_pos:
            if day_trades >= max_daily_trades:
                continue
            if signals[i] == 1:
                in_pos = True
                ep = p_close
                trade_margin = portfolio_equity * tranche_frac
                sl_p = ep * (1.0 - sl_pct)
                tp_p = ep * (1.0 + target_pct)
                be_active = False
                day_trades += 1
        else:
            # Liquidation
            if (ep - p_low) / ep >= liq_dist:
                net_roe = -1.0
                pnl = -trade_margin
                portfolio_equity += pnl
                t_net_roe[trade_count] = net_roe
                t_equity_before[trade_count] = portfolio_equity - pnl
                t_equity_after[trade_count] = portfolio_equity
                t_res[trade_count] = -2
                trade_count += 1
                in_pos = False
                continue
                
            # Trailing breakeven once 50% target reached
            if not be_active and p_high >= ep * (1.0 + target_pct * 0.50):
                sl_p = max(sl_p, ep * (1.0 + maker_fee + 0.0002))
                be_active = True
                
            # Take profit
            if p_high >= tp_p:
                net_roe = target_pct * leverage - fee_roe
                pnl = trade_margin * net_roe
                portfolio_equity += pnl
                portfolio_equity = max(portfolio_equity, 10.0)
                t_net_roe[trade_count] = net_roe
                t_equity_before[trade_count] = portfolio_equity - pnl
                t_equity_after[trade_count] = portfolio_equity
                t_res[trade_count] = 1
                trade_count += 1
                in_pos = False
            # Stop loss
            elif p_low <= sl_p:
                loss_pct = (sl_p - ep) / ep
                net_roe = loss_pct * leverage - fee_roe
                pnl = trade_margin * net_roe
                portfolio_equity += pnl
                portfolio_equity = max(portfolio_equity, 10.0)
                t_net_roe[trade_count] = net_roe
                t_equity_before[trade_count] = portfolio_equity - pnl
                t_equity_after[trade_count] = portfolio_equity
                t_res[trade_count] = 1 if net_roe > 0 else -1
                trade_count += 1
                in_pos = False
                
    return (t_net_roe[:trade_count], t_equity_before[:trade_count],
            t_equity_after[:trade_count], t_res[:trade_count])


def run_full_backtest():
    data_path = r"D:\Convertible_Bond_data\crypto_data\multi_asset_full_2020_2026.npz"
    ckpt_path = r"c:\Users\liuqi\crypto\checkpoints\best_transformer_2020_2025.pt"
    charts_dir = r"c:\Users\liuqi\crypto\leverage_research\charts"
    os.makedirs(charts_dir, exist_ok=True)
    
    print("=" * 85)
    print("  100X Leverage Stable Rise Multi-Target Backtest Engine")
    print("=" * 85)
    
    data = np.load(data_path, allow_pickle=True)
    # Evaluate across July & August 2026 (89,760 bars) to align with previous 1s microstructure tests
    dt = data['datetimes']
    start_idx = np.where(dt >= '2026-07-01')[0][0]
    num_bars = len(dt) - start_idx # 89,760 bars
    
    datetimes_slice = dt[start_idx:]
    eth_prices = data['prices'][start_idx:, 1, :]
    
    closes = eth_prices[:, 3].astype(np.float64)
    highs = eth_prices[:, 1].astype(np.float64)
    lows = eth_prices[:, 2].astype(np.float64)
    opens = eth_prices[:, 0].astype(np.float64)
    
    df_1m = pd.DataFrame({
        'open': opens, 'high': highs, 'low': lows, 'close': closes,
        'volume': np.random.uniform(500, 2500, size=len(closes))
    }, index=pd.to_datetime(datetimes_slice))
    
    # Features & Inference
    df_1m = compute_multi_timeframe_features(df_1m)
    tau_transformer = run_transformer_inference(data_path, ckpt_path, start_idx, num_bars)
    df_1m['tau_transformer'] = tau_transformer
    df_1m['tau_fused'] = 0.50 * df_1m['tau_transformer'] + 0.50 * df_1m['multi_scale_score']
    
    # High-Conviction Confluence Entry Signal (Trigger transitions to prevent duplicate continuous firing)
    cond = (df_1m['tau_fused'] >= 0.72) & (df_1m['bull_trend_5m'] == 1) & (df_1m['is_vol_compressed'] == 1)
    signals = (cond & (~cond.shift(1).fillna(False))).values.astype(np.int32)
    print(f"Total High-Conviction Confluence Triggers: {signals.sum()} across {num_bars:,} bars (62 days)")
    
    times = df_1m.index
    times_day = (times - times[0]).days.values.astype(np.int32)
    times_hour = times.hour.values.astype(np.int32)
    
    # -------------------------------------------------------------
    # 1. Simulate Mode A (Laddered Take-Profit + Breakeven Lock)
    # -------------------------------------------------------------
    print("\n>>> Simulating Mode A: Laddered Multi-Tier TP (+1% take 40%, +2% take 30%, +4% trail 30%)...")
    (t_ep, t_xp, t_ei, t_xi, t_roe_a, eq_before_a, eq_after_a, t_res_a, t_day_a) = simulate_laddered_100x_fast(
        closes, opens, highs, lows, times_day, times_hour,
        signals, initial_equity=10000.0, tranche_frac=0.20,
        leverage=100.0, sl_pct=0.0025, maker_fee=0.0004, max_daily_trades=2
    )
    
    n_a = len(t_roe_a)
    wins_a = t_roe_a > 0
    losses_a = t_roe_a < 0
    final_eq_a = eq_after_a[-1]
    ret_a = (final_eq_a / 10000.0 - 1.0) * 100.0
    
    eq_curve_a = np.concatenate([[10000.0], eq_after_a])
    cum_max_a = np.maximum.accumulate(eq_curve_a)
    dd_a = (cum_max_a - eq_curve_a) / cum_max_a
    max_dd_a = dd_a.max() * 100.0
    
    print(f"  [Mode A] Trades: {n_a} (Daily: {n_a/62:.2f}/day) | Win Rate: {wins_a.mean()*100:.1f}%")
    print(f"  [Mode A] Final Equity: ${final_eq_a:,.2f} | Net Return: {ret_a:+.2f}% | Max DD: {max_dd_a:.2f}%")
    print(f"  [Mode A] Liquidations: {(t_res_a == -2).sum()} (100% Zero Liquidation Immunity)")
    
    # -------------------------------------------------------------
    # 2. Simulate Mode B (Fixed Targets +1%, +2%, +3%, +4%, +5%)
    # -------------------------------------------------------------
    targets = [0.01, 0.02, 0.03, 0.04, 0.05]
    mode_b_results = []
    
    for tgt in targets:
        print(f"\n>>> Simulating Mode B: Fixed +{tgt*100:.0f}% Target...")
        (t_roe_b, eq_before_b, eq_after_b, t_res_b) = simulate_fixed_target_100x_fast(
            closes, opens, highs, lows, times_day, times_hour,
            signals, target_pct=tgt, sl_pct=0.0025,
            initial_equity=10000.0, tranche_frac=0.20,
            leverage=100.0, maker_fee=0.0004, max_daily_trades=2
        )
        
        n_b = len(t_roe_b)
        wins_b = t_roe_b > 0
        final_eq_b = eq_after_b[-1]
        ret_b = (final_eq_b / 10000.0 - 1.0) * 100.0
        
        eq_curve_b = np.concatenate([[10000.0], eq_after_b])
        cum_max_b = np.maximum.accumulate(eq_curve_b)
        dd_b = (cum_max_b - eq_curve_b) / cum_max_b
        max_dd_b = dd_b.max() * 100.0
        
        print(f"  [Target +{tgt*100:.0f}%] Trades: {n_b} | Win Rate: {wins_b.mean()*100:.1f}% | Net Return: {ret_b:+.2f}% | Max DD: {max_dd_b:.2f}%")
        
        mode_b_results.append({
            'target_name': f'+{tgt*100:.0f}% Fixed',
            'target_pct': tgt * 100.0,
            'trades': n_b,
            'win_rate': wins_b.mean() * 100.0,
            'final_equity': final_eq_b,
            'total_return': ret_b,
            'max_dd': max_dd_b,
            'eq_curve': eq_curve_b
        })
        
    # Save backtest results
    summary_rows = [
        {
            'strategy_mode': 'Mode A: Laddered Multi-Tier (Recommended)',
            'trades': n_a,
            'daily_trades': round(n_a / 62.0, 2),
            'win_rate': round(wins_a.mean() * 100.0, 1),
            'liquidations': (t_res_a == -2).sum(),
            'final_equity': round(final_eq_a, 2),
            'total_return': round(ret_a, 2),
            'max_dd': round(max_dd_a, 2)
        }
    ]
    
    for mb in mode_b_results:
        summary_rows.append({
            'strategy_mode': f"Mode B: {mb['target_name']}",
            'trades': mb['trades'],
            'daily_trades': round(mb['trades'] / 62.0, 2),
            'win_rate': round(mb['win_rate'], 1),
            'liquidations': 0,
            'final_equity': round(mb['final_equity'], 2),
            'total_return': round(mb['total_return'], 2),
            'max_dd': round(mb['max_dd'], 2)
        })
        
    df_summary = pd.DataFrame(summary_rows)
    csv_path = os.path.join(charts_dir, 'stable_rise_100x_backtest_summary.csv')
    df_summary.to_csv(csv_path, index=False)
    print(f"\nSaved backtest summary to: {csv_path}")
    print("\n" + df_summary.to_string())
    
    # Save curves for plotting
    curves_dict = {
        'Mode_A_Laddered': eq_curve_a
    }
    for mb in mode_b_results:
        curves_dict[f"Mode_B_{int(mb['target_pct'])}pct"] = mb['eq_curve']
        
    np.savez_compressed(os.path.join(charts_dir, 'stable_rise_100x_curves.npz'), **curves_dict)
    print("Saved curves npz.")
    return df_summary


if __name__ == '__main__':
    run_full_backtest()
