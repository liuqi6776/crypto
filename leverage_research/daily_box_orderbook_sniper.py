"""
Daily Fixed Range Box & Order Book Wall Sniper Engine (200X vs 100X vs 50X)
每日固定箱体震荡与挂单量大单护城河狙击策略引擎

Core Principles:
1. Daily Fixed Format: Asian Session Box (00:00 - 08:00 UTC) with amplitude 0.35% - 1.20%.
2. Order Book Depth Wall Integration:
   - At Box Low: Buy Wall (Bid Depth >= 2.0x Ask Depth). Maker Post-Only Buy Limit Order.
   - At Box High: Sell Wall (Ask Depth >= 2.0x Bid Depth). Maker Post-Only Sell Limit Order.
3. Daily Discipline: Maximum 1 to 2 sniper trades per day.
4. Tri-Tier Leverage Evaluation:
   - 200X Leverage (0.10% liquidation cliff, SL = 0.07%, TP = 0.35%)
   - 100X Leverage (0.60% liquidation buffer, SL = 0.16%, TP = 0.45%)
   - 50X Leverage (1.60% liquidation buffer, SL = 0.25%, TP = 0.60%)
5. Trailing Breakeven Lock: Once floating Net ROE >= +15%, move SL to Entry + Fee.
"""

import os
import sys
import numpy as np
import pandas as pd
import numba

@numba.njit
def simulate_daily_box_sniper_fast(closes, opens, highs, lows, times_day, times_hour,
                                   box_lows, box_highs, box_valid,
                                   lev=100.0, sl_pct=0.0016, tp_pct=0.0045, maker_fee=0.0004,
                                   max_daily_trades=2):
    """
    Numba accelerated simulation for daily box sniper.
    fee_roe = maker_fee * lev (e.g. 0.04% notional * 100x = 4.0% ROE)
    liq_dist = 1.0/lev - 0.004 (e.g. at 200x = 0.10%, at 100x = 0.60%)
    """
    n = len(closes)
    fee_roe = maker_fee * lev
    liq_dist = max(0.0005, 1.0 / lev - 0.004)
    
    max_trades = 5000
    t_side = np.zeros(max_trades, dtype=np.int32) # 1 long, -1 short
    t_entry_p = np.zeros(max_trades, dtype=np.float64)
    t_exit_p = np.zeros(max_trades, dtype=np.float64)
    t_entry_idx = np.zeros(max_trades, dtype=np.int64)
    t_exit_idx = np.zeros(max_trades, dtype=np.int64)
    t_net_roe = np.zeros(max_trades, dtype=np.float64)
    t_res = np.zeros(max_trades, dtype=np.int32) # 1 TP, -1 SL, -2 LIQ
    t_day = np.zeros(max_trades, dtype=np.int32)
    trade_count = 0
    
    in_pos = False
    side = 0
    ep = 0.0
    e_idx = 0
    sl_p = 0.0
    tp_p = 0.0
    be_active = False
    
    current_day = -1
    day_trades = 0
    
    for i in range(1, n):
        day = times_day[i]
        hr = times_hour[i]
        
        # Reset daily quota on new day
        if day != current_day:
            current_day = day
            day_trades = 0
            # If in position from previous day, close at market
            if in_pos:
                p = closes[i]
                gross = (p - ep) / ep * lev if side == 1 else (ep - p) / ep * lev
                net = gross - fee_roe
                t_side[trade_count] = side
                t_entry_p[trade_count] = ep
                t_exit_p[trade_count] = p
                t_entry_idx[trade_count] = e_idx
                t_exit_idx[trade_count] = i
                t_net_roe[trade_count] = net
                t_res[trade_count] = 1 if net > 0 else -1
                t_day[trade_count] = day
                trade_count += 1
                in_pos = False
                
        # Only trade between 08:00 and 23:00 (after Asian Box forms)
        if hr < 8 or hr >= 23:
            continue
            
        # Check if today had a valid Asian box
        if box_valid[i] == 0:
            continue
            
        b_low = box_lows[i]
        b_high = box_highs[i]
        b_amp = (b_high - b_low) / b_low
        
        p_close = closes[i]
        p_high = highs[i]
        p_low = lows[i]
        
        if not in_pos:
            if day_trades >= max_daily_trades:
                continue
                
            # Maker Buy Limit Order triggered at Box Low
            # Price pierces or touches Box Low but closes at/above Box Low
            if p_low <= b_low * 1.0002 and p_close >= b_low * 0.9995:
                in_pos = True
                side = 1
                ep = b_low
                e_idx = i
                be_active = False
                sl_p = ep * (1.0 - sl_pct)
                target_move = min(tp_pct, b_amp * 0.75)
                tp_p = ep * (1.0 + target_move)
                day_trades += 1
                
            # Maker Sell Limit Order triggered at Box High
            # Price spikes into Box High but closes at/below Box High
            elif p_high >= b_high * 0.9998 and p_close <= b_high * 1.0005:
                in_pos = True
                side = -1
                ep = b_high
                e_idx = i
                be_active = False
                sl_p = ep * (1.0 + sl_pct)
                target_move = min(tp_pct, b_amp * 0.75)
                tp_p = ep * (1.0 - target_move)
                day_trades += 1
                
        else: # IN POSITION
            if side == 1: # LONG
                # 1. Check Forced Liquidation first
                max_drop = (ep - p_low) / ep
                if max_drop >= liq_dist:
                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = ep * (1.0 - liq_dist)
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_net_roe[trade_count] = -1.0 # 100% loss
                    t_res[trade_count] = -2 # Liquidation
                    t_day[trade_count] = day
                    trade_count += 1
                    in_pos = False
                    continue
                    
                gross = (p_close - ep) / ep * lev
                net = gross - fee_roe
                
                # 2. Breakeven Lock once net ROE >= +15%
                if not be_active and net >= 0.15:
                    sl_p = max(sl_p, ep * (1.0 + fee_roe / lev + 0.0002))
                    be_active = True
                    
                # 3. Check Take Profit
                if p_high >= tp_p:
                    gain = (tp_p - ep) / ep * lev - fee_roe
                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = tp_p
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_net_roe[trade_count] = gain
                    t_res[trade_count] = 1
                    t_day[trade_count] = day
                    trade_count += 1
                    in_pos = False
                # 4. Check Stop Loss
                elif p_low <= sl_p:
                    loss = (sl_p - ep) / ep * lev - fee_roe
                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = sl_p
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_net_roe[trade_count] = loss
                    t_res[trade_count] = -1
                    t_day[trade_count] = day
                    trade_count += 1
                    in_pos = False
                    
            elif side == -1: # SHORT
                # 1. Check Forced Liquidation first
                max_surge = (p_high - ep) / ep
                if max_surge >= liq_dist:
                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = ep * (1.0 + liq_dist)
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_net_roe[trade_count] = -1.0
                    t_res[trade_count] = -2
                    t_day[trade_count] = day
                    trade_count += 1
                    in_pos = False
                    continue
                    
                gross = (ep - p_close) / ep * lev
                net = gross - fee_roe
                
                if not be_active and net >= 0.15:
                    sl_p = min(sl_p, ep * (1.0 - fee_roe / lev - 0.0002))
                    be_active = True
                    
                if p_low <= tp_p:
                    gain = (ep - tp_p) / ep * lev - fee_roe
                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = tp_p
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_net_roe[trade_count] = gain
                    t_res[trade_count] = 1
                    t_day[trade_count] = day
                    trade_count += 1
                    in_pos = False
                elif p_high >= sl_p:
                    loss = (ep - sl_p) / ep * lev - fee_roe
                    t_side[trade_count] = side
                    t_entry_p[trade_count] = ep
                    t_exit_p[trade_count] = sl_p
                    t_entry_idx[trade_count] = e_idx
                    t_exit_idx[trade_count] = i
                    t_net_roe[trade_count] = loss
                    t_res[trade_count] = -1
                    t_day[trade_count] = day
                    trade_count += 1
                    in_pos = False

    return (t_side[:trade_count], t_entry_p[:trade_count], t_exit_p[:trade_count],
            t_entry_idx[:trade_count], t_exit_idx[:trade_count],
            t_net_roe[:trade_count], t_res[:trade_count], t_day[:trade_count])


def compute_daily_asian_boxes(df_1m):
    """
    Computes Asian Session Box (00:00 - 08:00 UTC) for each calendar day,
    validating if amplitude is between 0.35% and 1.20%.
    """
    days = sorted(list(set(df_1m.index.date)))
    df_1m['box_low'] = np.nan
    df_1m['box_high'] = np.nan
    df_1m['box_valid'] = 0
    
    for d in days:
        mask_day = df_1m.index.date == d
        day_slice = df_1m.loc[mask_day]
        asian = day_slice.between_time('00:00', '08:00')
        if len(asian) == 0:
            continue
            
        b_high = asian['high'].max()
        b_low = asian['low'].min()
        b_amp = (b_high - b_low) / b_low
        
        # Valid box: 0.35% <= amp <= 1.20%
        if 0.0035 <= b_amp <= 0.0120:
            df_1m.loc[mask_day, 'box_low'] = b_low
            df_1m.loc[mask_day, 'box_high'] = b_high
            df_1m.loc[mask_day, 'box_valid'] = 1
            
    return df_1m
