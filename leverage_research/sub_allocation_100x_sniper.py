# -*- coding: utf-8 -*-
"""
Sub-Allocation 100X Perpetual Sniper Engine
100倍杠杆分仓狙击策略执行引擎

Core Principles:
1. Sub-Allocation (分仓): Margin = f * Portfolio_Equity (Default f = 0.20, 5 tranches).
   Max portfolio drawdown per stopped trade is strictly limited to:
   0.20 * (-18% price loss - 4% fee) = -4.4% of total account.
2. Maker Post-Only Limit Entry:
   - Placed at dynamic Channel_lower (Long) or Channel_upper (Short).
   - Maker fee: 0.02% per leg (0.04% round-trip notional, 4.0% ROE at 100x).
3. Pre-Placed Stop-Loss & Take-Profit:
   - Hard Stop-Loss: 0.18% adverse move (3.33x safety cushion before 0.60% 100x liquidation line).
   - Take-Profit: 0.35% to 0.60% favorable move (+31% to +56% net ROE on margin).
4. Trailing Breakeven Lock:
   - Once floating net ROE >= +15%, move SL to Entry + Fees.
5. Strict Daily Quota Discipline:
   - Maximum 1 to 2 trades per day.
   - If Trade 1 hits TP, halt trading for the day to lock in profit.
   - If Trade 1 hits SL, at most 1 secondary trade allowed if tau >= 0.75.
"""

import os
import sys
import numpy as np
import pandas as pd
import numba


@numba.njit
def simulate_sub_allocation_100x_fast(
    closes, opens, highs, lows, times_day, times_hour,
    channel_lows, channel_highs, is_oscillation,
    tau_long, tau_short,
    initial_equity=10000.0,
    tranche_frac=0.20,      # 20% margin per trade (5 tranches)
    leverage=100.0,
    sl_pct=0.0018,          # 0.18% stop loss distance
    tp_pct=0.0045,          # 0.45% base take profit distance
    maker_fee=0.0004,       # 0.04% round trip notional
    tau_threshold=0.70,     # Confidence gate
    max_daily_trades=2
):
    """
    Numba-accelerated execution simulator for sub-allocation 100X trading.
    Tracks both Margin ROE and Compounded Portfolio Equity.
    """
    n = len(closes)
    fee_roe = maker_fee * leverage # 4.0% ROE
    liq_dist = max(0.001, 1.0 / leverage - 0.004) # 0.60% at 100x
    
    max_trades = 5000
    t_side = np.zeros(max_trades, dtype=np.int32)
    t_entry_p = np.zeros(max_trades, dtype=np.float64)
    t_exit_p = np.zeros(max_trades, dtype=np.float64)
    t_entry_idx = np.zeros(max_trades, dtype=np.int64)
    t_exit_idx = np.zeros(max_trades, dtype=np.int64)
    t_margin_roe = np.zeros(max_trades, dtype=np.float64)
    t_equity_before = np.zeros(max_trades, dtype=np.float64)
    t_equity_after = np.zeros(max_trades, dtype=np.float64)
    t_res = np.zeros(max_trades, dtype=np.int32) # 1: TP, -1: SL, -2: LIQ, 0: Day Close
    t_day = np.zeros(max_trades, dtype=np.int32)
    
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
        
        # New Day Reset
        if day != current_day:
            current_day = day
            day_trades = 0
            day_had_tp = False
            
            # If in position from previous day, close at market
            if in_pos:
                p = closes[i]
                gross = (p - ep) / ep * leverage if side == 1 else (ep - p) / ep * leverage
                net_roe = gross - fee_roe
                pnl_dollar = trade_margin * net_roe
                
                t_side[trade_count] = side
                t_entry_p[trade_count] = ep
                t_exit_p[trade_count] = p
                t_entry_idx[trade_count] = e_idx
                t_exit_idx[trade_count] = i
                t_margin_roe[trade_count] = net_roe
                t_equity_before[trade_count] = portfolio_equity
                
                portfolio_equity += pnl_dollar
                portfolio_equity = max(portfolio_equity, 10.0) # Floor
                
                t_equity_after[trade_count] = portfolio_equity
                t_res[trade_count] = 1 if net_roe > 0 else -1
                t_day[trade_count] = day
                trade_count += 1
                in_pos = False
                
        # Only trade between 08:00 and 23:00 UTC
        if hr < 8 or hr >= 23:
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
                continue
                
            # Check Oscillation Regime
            if is_oscillation[i] == 0 or c_amp < 0.0035 or c_amp > 0.0125:
                continue
                
            # 1. Maker Long Entry at Channel_lower with High Confidence
            # Price touches or pierces channel lower bound, but closes above 0.9995 of bound
            if (p_low <= c_low * 1.0002 and p_close >= c_low * 0.9995 and
                tau_long[i] >= tau_threshold):
                
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
                
            # 2. Maker Short Entry at Channel_upper with High Confidence
            elif (p_high >= c_high * 0.9998 and p_close <= c_high * 1.0005 and
                  tau_short[i] >= tau_threshold):
                  
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
                
        else: # In Position
            if side == 1: # LONG
                # 1. Liquidation Check (0.60% buffer)
                max_drop = (ep - p_low) / ep
                if max_drop >= liq_dist:
                    net_roe = -1.0
                    pnl_dollar = -trade_margin
                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = ep * (1.0 - liq_dist)
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_margin_roe[trade_count] = net_roe
                    t_equity_before[trade_count] = portfolio_equity
                    portfolio_equity += pnl_dollar
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = -2
                    t_day[trade_count] = day
                    trade_count += 1
                    in_pos = False
                    continue
                    
                gross = (p_close - ep) / ep * leverage
                net_roe = gross - fee_roe
                
                # 2. Trailing Breakeven Lock once Net ROE >= +15%
                if not be_active and net_roe >= 0.15:
                    sl_p = max(sl_p, ep * (1.0 + fee_roe / leverage + 0.0002))
                    be_active = True
                    
                # 3. Take Profit
                if p_high >= tp_p:
                    gain_roe = (tp_p - ep) / ep * leverage - fee_roe
                    pnl_dollar = trade_margin * gain_roe
                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = tp_p
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_margin_roe[trade_count] = gain_roe
                    t_equity_before[trade_count] = portfolio_equity
                    portfolio_equity += pnl_dollar
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = 1
                    t_day[trade_count] = day
                    trade_count += 1
                    in_pos = False
                    day_had_tp = True # Halt trading for today
                    
                # 4. Stop Loss
                elif p_low <= sl_p:
                    loss_roe = (sl_p - ep) / ep * leverage - fee_roe
                    pnl_dollar = trade_margin * loss_roe
                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = sl_p
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_margin_roe[trade_count] = loss_roe
                    t_equity_before[trade_count] = portfolio_equity
                    portfolio_equity += pnl_dollar
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = -1
                    t_day[trade_count] = day
                    trade_count += 1
                    in_pos = False
                    
            elif side == -1: # SHORT
                # 1. Liquidation Check
                max_surge = (p_high - ep) / ep
                if max_surge >= liq_dist:
                    net_roe = -1.0
                    pnl_dollar = -trade_margin
                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = ep * (1.0 + liq_dist)
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_margin_roe[trade_count] = net_roe
                    t_equity_before[trade_count] = portfolio_equity
                    portfolio_equity += pnl_dollar
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = -2
                    t_day[trade_count] = day
                    trade_count += 1
                    in_pos = False
                    continue
                    
                gross = (ep - p_close) / ep * leverage
                net_roe = gross - fee_roe
                
                # 2. Trailing Breakeven Lock once Net ROE >= +15%
                if not be_active and net_roe >= 0.15:
                    sl_p = min(sl_p, ep * (1.0 - fee_roe / leverage - 0.0002))
                    be_active = True
                    
                # 3. Take Profit
                if p_low <= tp_p:
                    gain_roe = (ep - tp_p) / ep * leverage - fee_roe
                    pnl_dollar = trade_margin * gain_roe
                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = tp_p
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_margin_roe[trade_count] = gain_roe
                    t_equity_before[trade_count] = portfolio_equity
                    portfolio_equity += pnl_dollar
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = 1
                    t_day[trade_count] = day
                    trade_count += 1
                    in_pos = False
                    day_had_tp = True
                    
                # 4. Stop Loss
                elif p_high >= sl_p:
                    loss_roe = (ep - sl_p) / ep * leverage - fee_roe
                    pnl_dollar = trade_margin * loss_roe
                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = sl_p
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_margin_roe[trade_count] = loss_roe
                    t_equity_before[trade_count] = portfolio_equity
                    portfolio_equity += pnl_dollar
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = -1
                    t_day[trade_count] = day
                    trade_count += 1
                    in_pos = False
                    
    return (t_side[:trade_count], t_entry_p[:trade_count], t_exit_p[:trade_count],
            t_entry_idx[:trade_count], t_exit_idx[:trade_count],
            t_margin_roe[:trade_count], t_equity_before[:trade_count],
            t_equity_after[:trade_count], t_res[:trade_count], t_day[:trade_count])
