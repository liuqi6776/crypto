# -*- coding: utf-8 -*-
"""
Dual-Engine 100X Sniper Execution Engine: Direction Model + Volatility & Needle Model
双模型联锁100倍杠杆狙击执行引擎：方向预测模型 + 波动率与防插针模型

Author: Antigravity Quantitative Research Team
Date: September 2026

Simulates and compares:
1. Track A1: Baseline Direction Model (30% Golden Kelly Sizing)
2. Track A2: Dual-Model Confluence Gate (30% Golden Kelly Sizing, tau_vol >= 0.65)
3. Track B1: Baseline Direction Model (20% Scientific Sizing)
4. Track B2: Dual-Model Confluence Gate (20% Scientific Sizing, tau_vol >= 0.65)
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
from volatility_needle_model import compute_volatility_needle_features

DATA_PATH = r"D:\Convertible_Bond_data\crypto_data\history\futures_1m\ETHUSDT_2026_09_01_to_09_22.parquet"
OUTPUT_DIR = r"c:\Users\liuqi\crypto\leverage_research\charts"
TRADES_DUAL_CSV = os.path.join(OUTPUT_DIR, "dual_model_september_trades.csv")
TRADES_BASELINE_CSV = os.path.join(OUTPUT_DIR, "september_2026_paper_trades.csv")
SUMMARY_CSV = os.path.join(OUTPUT_DIR, "dual_model_comparison_summary.csv")
CURVES_NPZ = os.path.join(OUTPUT_DIR, "dual_model_curves.npz")


@numba.njit
def simulate_dual_100x_fast(
    closes, opens, highs, lows, times_day, times_hour,
    channel_lows, channel_highs, is_oscillation,
    tau_long, tau_short,
    initial_equity=10000.0,
    tranche_frac=0.30,
    leverage=100.0,
    sl_pct=0.0018,          # 0.18% Hard Stop-Loss (3.33x safety cushion before 0.60% liq)
    tp_pct=0.0045,          # 0.45% Base Take-Profit Target (+45% ROE)
    maker_fee=0.0004,       # 0.04% Round-trip Maker fee (4.0% ROE at 100x)
    tau_threshold=0.70,
    max_daily_trades=2
):
    """
    Numba-accelerated execution simulator.
    Tracks bar-by-bar mark-to-market equity and trade executions.
    """
    n = len(closes)
    fee_roe = maker_fee * leverage  # 4.0% ROE
    liq_dist = 0.0060               # 0.60% at 100x
    
    max_trades = 2000
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
    t_res = np.zeros(max_trades, dtype=np.int32)         # 1: TP, -1: SL, 2: BE, -2: Liq, 0: Day Close
    t_day = np.zeros(max_trades, dtype=np.int32)
    
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
                
        # Trading hour filter: 08:00 to 23:00 UTC
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
            if is_oscillation[i] == 0 or c_amp < 0.0035 or c_amp > 0.0125:
                bar_equity[i] = portfolio_equity
                continue
                
            # 1. Maker Long Entry at Channel Lower Bound
            if (p_low <= c_low * 1.0002 and p_close >= c_low * 0.9995 and tau_long[i] >= tau_threshold):
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
                
            # 2. Maker Short Entry at Channel Upper Bound
            elif (p_high >= c_high * 0.9998 and p_close <= c_high * 1.0005 and tau_short[i] >= tau_threshold):
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
                
        else: # IN POSITION
            if side == 1: # LONG
                # 1. Liquidation Check
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
                    portfolio_equity = max(portfolio_equity, 10.0)
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
                    
                # 3. Take Profit Trigger
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
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = 1 # Take-Profit
                    t_day[trade_count] = day
                    trade_count += 1
                    in_pos = False
                    day_had_tp = True
                    bar_equity[i] = portfolio_equity
                    continue
                    
                # 4. Stop-Loss Trigger (Hard Stop or Breakeven Stop)
                elif p_low <= sl_p:
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
                    t_res[trade_count] = 2 if be_active else -1 # 2: BE Lock, -1: SL
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
                    portfolio_equity = max(portfolio_equity, 10.0)
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
                    
                # 3. Take Profit Trigger
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
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = 1 # Take-Profit
                    t_day[trade_count] = day
                    trade_count += 1
                    in_pos = False
                    day_had_tp = True
                    bar_equity[i] = portfolio_equity
                    continue
                    
                # 4. Stop-Loss Trigger (Hard Stop or Breakeven Stop)
                elif p_high >= sl_p:
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
                    t_res[trade_count] = 2 if be_active else -1 # 2: BE Lock, -1: SL
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


def compute_metrics(equity_series, initial=10000.0):
    final_eq = equity_series[-1]
    ret_pct = (final_eq - initial) / initial * 100.0
    cummax = np.maximum.accumulate(equity_series)
    dd = (cummax - equity_series) / cummax
    max_dd = np.max(dd) * 100.0
    return final_eq, ret_pct, max_dd


def run_dual_engine_pipeline():
    print("=" * 85)
    print("Dual-Engine 100X Sniper Execution Engine: Direction + Volatility/Needle Model")
    print("双模型联锁100倍杠杆执行引擎：方向预测模型 + 波动率与防插针模型")
    print("=" * 85)
    
    df = pd.read_parquet(DATA_PATH)
    print(f"Loaded {len(df):,} 1m bars from {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}")
    df = df.set_index('datetime')
    
    # 1. Multi-timeframe channel extraction
    print(">>> 1. Extracting Multi-Timeframe Channels (5m, 15m, ATR Volatility Squeeze)...")
    df = compute_multi_timeframe_channels(df)
    
    # 2. Level-2 order book depth & wall proxy
    print(">>> 2. Computing Order Book Depth Imbalance (OBI) & Buy/Sell Walls...")
    df_dummy = df.reset_index().rename(columns={'index': 'open_time'})
    df = compute_orderbook_confidence(df_dummy, df)
    
    # 3. Direction Model Conviction Proxies
    print(">>> 3. Synthesizing Direction Model Conviction (5m Trend + OBI Flow)...")
    ema20 = df['close'].ewm(span=20).mean()
    ema50 = df['close'].ewm(span=50).mean()
    trend_bias = (ema20 - ema50) / ema50
    tau_dir_long = np.clip(df['score_ob_long'] + np.tanh(trend_bias * 300.0) * 0.20, 0.0, 1.0).values.astype(np.float64)
    tau_dir_short = np.clip(df['score_ob_short'] - np.tanh(trend_bias * 300.0) * 0.20, 0.0, 1.0).values.astype(np.float64)
    
    # 4. Volatility & Needle Risk Model
    print(">>> 4. Computing Parkinson Realized Volatility, Wick Needle Ratios, and Clean Corridor Scores...")
    hl_log = np.log(np.maximum(df['high'] / np.maximum(df['low'], 1e-6), 1.0))
    parkinson_vol_1m = np.sqrt(hl_log**2 / (4.0 * np.log(2.0)))
    vol_ma_short = parkinson_vol_1m.rolling(5).mean()
    vol_ma_long = parkinson_vol_1m.rolling(30).mean()
    vol_ratio = vol_ma_short / np.maximum(vol_ma_long, 1e-6)

    hl_range = df['high'] - df['low']
    body_range = abs(df['close'] - df['open'])
    wick_ratio = (hl_range - body_range) / np.maximum(hl_range, 1e-6)
    wick_ma = wick_ratio.rolling(5).mean()

    # Clean Corridor Volatility Score (tau_vol in [0, 1])
    score_clean_vol = np.clip(1.0 - 0.50 * np.tanh(np.maximum(vol_ratio - 1.0, 0.0) * 2.0) - 0.50 * np.tanh(np.maximum(wick_ma - 0.35, 0.0) * 3.0), 0.0, 1.0).values
    df['tau_vol'] = score_clean_vol
    df['wick_ma5'] = wick_ma
    df['vol_ratio'] = vol_ratio
    
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
    
    # Dual-Gate Gated Signals:
    tau_dual_long = np.where(score_clean_vol >= 0.65, tau_dir_long, 0.0)
    tau_dual_short = np.where(score_clean_vol >= 0.65, tau_dir_short, 0.0)
    
    # Run Track A1: Baseline Direction Model (30% Golden Kelly)
    print("\n>>> Running Track A1: Baseline (Single Direction Model, 30% Sizing)...")
    res_ba = simulate_dual_100x_fast(
        closes, opens, highs, lows, times_day, times_hour,
        c_lows, c_highs, is_osc, tau_dir_long, tau_dir_short,
        initial_equity=10000.0, tranche_frac=0.30, leverage=100.0,
        sl_pct=0.0018, tp_pct=0.0045, maker_fee=0.0004,
        tau_threshold=0.70, max_daily_trades=2
    )
    
    # Run Track A2: Dual-Model Confluence Gate (30% Golden Kelly)
    print(">>> Running Track A2: Dual-Engine Confluence (Direction + Volatility Gate, 30% Sizing)...")
    res_da = simulate_dual_100x_fast(
        closes, opens, highs, lows, times_day, times_hour,
        c_lows, c_highs, is_osc, tau_dual_long, tau_dual_short,
        initial_equity=10000.0, tranche_frac=0.30, leverage=100.0,
        sl_pct=0.0018, tp_pct=0.0045, maker_fee=0.0004,
        tau_threshold=0.70, max_daily_trades=2
    )
    
    # Run Track B1: Baseline Direction Model (20% Scientific)
    print(">>> Running Track B1: Baseline (Single Direction Model, 20% Sizing)...")
    res_bb = simulate_dual_100x_fast(
        closes, opens, highs, lows, times_day, times_hour,
        c_lows, c_highs, is_osc, tau_dir_long, tau_dir_short,
        initial_equity=10000.0, tranche_frac=0.20, leverage=100.0,
        sl_pct=0.0018, tp_pct=0.0045, maker_fee=0.0004,
        tau_threshold=0.70, max_daily_trades=2
    )
    
    # Run Track B2: Dual-Model Confluence Gate (20% Scientific)
    print(">>> Running Track B2: Dual-Engine Confluence (Direction + Volatility Gate, 20% Sizing)...")
    res_db = simulate_dual_100x_fast(
        closes, opens, highs, lows, times_day, times_hour,
        c_lows, c_highs, is_osc, tau_dual_long, tau_dual_short,
        initial_equity=10000.0, tranche_frac=0.20, leverage=100.0,
        sl_pct=0.0018, tp_pct=0.0045, maker_fee=0.0004,
        tau_threshold=0.70, max_daily_trades=2
    )
    
    # Unpack results
    tc_ba, eq_ba, s_ba, ep_ba, xp_ba, ei_ba, xi_ba, m_ba, roe_ba, pnl_ba, eqb_ba, eqa_ba, r_ba, d_ba, bar_eq_ba = res_ba
    tc_da, eq_da, s_da, ep_da, xp_da, ei_da, xi_da, m_da, roe_da, pnl_da, eqb_da, eqa_da, r_da, d_da, bar_eq_da = res_da
    tc_bb, eq_bb, s_bb, ep_bb, xp_bb, ei_bb, xi_bb, m_bb, roe_bb, pnl_bb, eqb_bb, eqa_bb, r_bb, d_bb, bar_eq_bb = res_bb
    tc_db, eq_db, s_db, ep_db, xp_db, ei_db, xi_db, m_db, roe_db, pnl_db, eqb_db, eqa_db, r_db, d_db, bar_eq_db = res_db
    
    # Summary function
    def summarize(tc, eq, r, roe, pnl, bar_eq, name):
        win_count = np.sum(r == 1)
        be_count = np.sum(r == 2)
        loss_count = np.sum(r == -1)
        liq_count = np.sum(r == -2)
        win_rate = (win_count / tc * 100.0) if tc > 0 else 0.0
        win_be_rate = ((win_count + be_count) / tc * 100.0) if tc > 0 else 0.0
        final_eq, ret_pct, max_dd = compute_metrics(bar_eq)
        tot_wins = np.sum(pnl[pnl > 0])
        tot_loss = np.abs(np.sum(pnl[pnl < 0]))
        pf = (tot_wins / tot_loss) if tot_loss > 0 else 999.0
        avg_win_roe = np.mean(roe[pnl > 0]) * 100.0 if np.sum(pnl > 0) > 0 else 0.0
        avg_loss_roe = np.mean(roe[pnl < 0]) * 100.0 if np.sum(pnl < 0) > 0 else 0.0
        return {
            'Model_Strategy': name,
            'Total_Trades': tc,
            'Win_Trades': win_count,
            'BE_Trades': be_count,
            'Loss_Trades': loss_count,
            'Liquidations': liq_count,
            'Win_Rate_Pct': round(win_rate, 1),
            'Win_Plus_BE_Pct': round(win_be_rate, 1),
            'Final_Equity': round(final_eq, 2),
            'Net_Return_Pct': round(ret_pct, 2),
            'Max_Drawdown_Pct': round(max_dd, 2),
            'Profit_Factor': round(pf, 2),
            'Avg_Win_ROE_Pct': round(avg_win_roe, 2),
            'Avg_Loss_ROE_Pct': round(avg_loss_roe, 2)
        }
        
    summary_rows = [
        summarize(tc_ba, eq_ba, r_ba, roe_ba, pnl_ba, bar_eq_ba, "Track A1: Baseline Direction Model (30% Golden Kelly)"),
        summarize(tc_da, eq_da, r_da, roe_da, pnl_da, bar_eq_da, "Track A2: Dual-Model Confluence (30% Golden Kelly)"),
        summarize(tc_bb, eq_bb, r_bb, roe_bb, pnl_bb, bar_eq_bb, "Track B1: Baseline Direction Model (20% Scientific)"),
        summarize(tc_db, eq_db, r_db, roe_db, pnl_db, bar_eq_db, "Track B2: Dual-Model Confluence (20% Scientific)")
    ]
    df_summary = pd.DataFrame(summary_rows)
    print("\n" + "=" * 85)
    print("PERFORMANCE COMPARISON SUMMARY (September 1 - 22, 2026):")
    print(df_summary.to_string(index=False))
    print("=" * 85)
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df_summary.to_csv(SUMMARY_CSV, index=False, encoding='utf-8-sig')
    print(f"\nSaved summary table to {SUMMARY_CSV}")
    
    # Save Dual-Model Trade Ledger
    res_map = {1: 'Take-Profit (止盈)', -1: 'Stop-Loss (止损)', 2: 'Breakeven Lock (保本)', -2: 'Liquidation (爆仓)', 0: 'Day Close (收盘平仓)'}
    trade_records = []
    for k in range(tc_da):
        t_in = times[ei_da[k]]
        t_out = times[xi_da[k]]
        dur_min = (xi_da[k] - ei_da[k])
        trade_records.append({
            'trade_id': k + 1,
            'day_idx': d_da[k] + 1,
            'entry_time': str(t_in),
            'exit_time': str(t_out),
            'duration_min': dur_min,
            'direction': 'LONG (做多)' if s_da[k] == 1 else 'SHORT (做空)',
            'entry_price': round(ep_da[k], 2),
            'exit_price': round(xp_da[k], 2),
            'margin_allocated': round(m_da[k], 2),
            'leverage': '100X',
            'net_margin_roe_pct': round(roe_da[k] * 100.0, 2),
            'dollar_pnl': round(pnl_da[k], 2),
            'equity_before': round(eqb_da[k], 2),
            'equity_after': round(eqa_da[k], 2),
            'tau_dir': round(tau_dir_long[ei_da[k]] if s_da[k] == 1 else tau_dir_short[ei_da[k]], 3),
            'tau_vol': round(score_clean_vol[ei_da[k]], 3),
            'exit_reason': res_map.get(r_da[k], 'Other')
        })
    df_trades_dual = pd.DataFrame(trade_records)
    df_trades_dual.to_csv(TRADES_DUAL_CSV, index=False, encoding='utf-8-sig')
    print(f"Saved Dual-Model trade ledger ({len(df_trades_dual)} trades) to {TRADES_DUAL_CSV}")
    
    # Save Baseline Trade Ledger as well
    base_records = []
    for k in range(tc_ba):
        t_in = times[ei_ba[k]]
        t_out = times[xi_ba[k]]
        dur_min = (xi_ba[k] - ei_ba[k])
        base_records.append({
            'trade_id': k + 1,
            'day_idx': d_ba[k] + 1,
            'entry_time': str(t_in),
            'exit_time': str(t_out),
            'duration_min': dur_min,
            'direction': 'LONG (做多)' if s_ba[k] == 1 else 'SHORT (做空)',
            'entry_price': round(ep_ba[k], 2),
            'exit_price': round(xp_ba[k], 2),
            'margin_allocated': round(m_ba[k], 2),
            'leverage': '100X',
            'net_margin_roe_pct': round(roe_ba[k] * 100.0, 2),
            'dollar_pnl': round(pnl_ba[k], 2),
            'equity_before': round(eqb_ba[k], 2),
            'equity_after': round(eqa_ba[k], 2),
            'tau_dir': round(tau_dir_long[ei_ba[k]] if s_ba[k] == 1 else tau_dir_short[ei_ba[k]], 3),
            'tau_vol': round(score_clean_vol[ei_ba[k]], 3),
            'exit_reason': res_map.get(r_ba[k], 'Other')
        })
    df_trades_base = pd.DataFrame(base_records)
    df_trades_base.to_csv(TRADES_BASELINE_CSV, index=False, encoding='utf-8-sig')
    print(f"Saved Baseline trade ledger ({len(df_trades_base)} trades) to {TRADES_BASELINE_CSV}")
    
    # Save continuous curves NPZ for plotting
    np.savez_compressed(
        CURVES_NPZ,
        times=times.values.astype(str),
        closes=closes,
        bar_eq_base_a=bar_eq_ba,
        bar_eq_dual_a=bar_eq_da,
        bar_eq_base_b=bar_eq_bb,
        bar_eq_dual_b=bar_eq_db,
        ei_da=ei_da,
        xi_da=xi_da,
        s_da=s_da,
        ep_da=ep_da,
        xp_da=xp_da,
        r_da=r_da,
        pnl_da=pnl_da,
        ei_ba=ei_ba,
        xi_ba=xi_ba,
        s_ba=s_ba,
        ep_ba=ep_ba,
        xp_ba=xp_ba,
        r_ba=r_ba,
        pnl_ba=pnl_ba,
        score_clean_vol=score_clean_vol
    )
    print(f"Saved continuous curves and markers to {CURVES_NPZ}")
    
    # Needle Sweep Elimination Forensic Audit
    print("\n" + "=" * 85)
    print("NEEDLE SWEEP ELIMINATION FORENSIC AUDIT (插针扫损过滤与微观反转审计):")
    print("=" * 85)
    base_entries = set(ei_ba)
    dual_entries = set(ei_da)
    filtered_entries = sorted(list(base_entries - dual_entries))
    
    for idx in filtered_entries:
        k_base = list(ei_ba).index(idx)
        t_in = times[idx]
        d = 'LONG' if s_ba[k_base] == 1 else 'SHORT'
        res_str = res_map.get(r_ba[k_base], 'Other')
        pnl = pnl_ba[k_base]
        roe = roe_ba[k_base] * 100.0
        tau_v = score_clean_vol[idx]
        w_ratio = wick_ma.iloc[idx]
        v_ratio = vol_ratio.iloc[idx]
        print(f"-> Filtered Trade #{k_base+1} at {t_in} ({d}): Result = {res_str}, ROE = {roe:+.2f}%, PnL = ${pnl:+.2f} | tau_vol = {tau_v:.3f} (< 0.65), wick_ma5 = {w_ratio:.3f}, vol_ratio = {v_ratio:.2f}")


if __name__ == "__main__":
    run_dual_engine_pipeline()
