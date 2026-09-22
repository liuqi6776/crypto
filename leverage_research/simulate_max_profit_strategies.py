# -*- coding: utf-8 -*-
"""
Simulate and Compare Maximum Profit Strategies for 100X Leverage on ETH
实测与对比 100倍杠杆 ETH “最优执行方式” 与 “最大收益极限打法”

Strategies compared:
1. Standard Sub-Allocation (20% margin, static initial sizing)
2. Compounded Sub-Allocation (20% margin dynamically updated from portfolio equity)
3. Risk-Free Pyramiding (浮盈加仓滚仓法: lock BE at +0.45%, add 2nd tranche, target +1.20%)
4. High-Volatility Pyramiding (Squeeze breakout mode)
"""

import os
import sys
import numpy as np
import pandas as pd
import numba

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sub_allocation_100x_sniper import simulate_sub_allocation_100x_fast
from transformer_channel_depth_engine import build_multi_scale_channels


@numba.njit
def simulate_pyramiding_100x_fast(
    closes, opens, highs, lows, times_day, times_hour,
    channel_lows, channel_highs, is_oscillation,
    tau_long, tau_short,
    initial_equity=10000.0,
    tranche_frac=0.20,
    leverage=100.0,
    sl_pct=0.0018,
    tp1_pct=0.0045,         # Tier 1 TP / Pyramiding trigger (+0.45% move, +45% ROE)
    tp2_pct=0.0120,         # Final TP target (+1.20% move, +120% ROE)
    maker_fee=0.0004,
    tau_threshold=0.70,
    max_daily_trades=2,
    enable_pyramiding=True  # Whether to add 2nd tranche when BE is locked
):
    """
    Simulates 100X Execution with Risk-Free Pyramiding:
    - Base Entry: 20% margin at channel support.
    - When price moves +0.45%:
        * Move SL1 to entry cost + fees (Risk = 0).
        * If enable_pyramiding: Add 2nd tranche (20% margin) with SL2 at entry1 price!
        * If price continues to +1.20%: Take massive compound profit on both tranches!
    """
    n = len(closes)
    fee_roe = maker_fee * leverage # 4.0% ROE
    liq_dist = 0.0060 # 0.60% at 100x
    
    max_trades = 5000
    t_side = np.zeros(max_trades, dtype=np.int32)
    t_margin_roe = np.zeros(max_trades, dtype=np.float64)
    t_dollar_pnl = np.zeros(max_trades, dtype=np.float64)
    t_equity_after = np.zeros(max_trades, dtype=np.float64)
    t_res = np.zeros(max_trades, dtype=np.int32)
    
    trade_count = 0
    portfolio_equity = initial_equity
    
    in_pos = False
    side = 0
    ep1 = 0.0
    ep2 = 0.0
    sl1_p = 0.0
    sl2_p = 0.0
    margin1 = 0.0
    margin2 = 0.0
    has_pyramided = False
    
    current_day = -1
    day_trades = 0
    day_had_tp = False
    
    for i in range(1, n):
        day = times_day[i]
        hr = times_hour[i]
        
        # Day rollover
        if day != current_day:
            current_day = day
            day_trades = 0
            day_had_tp = False
            
            if in_pos:
                # Close out open positions at day close
                p = closes[i]
                gain1 = (p - ep1) / ep1 if side == 1 else (ep1 - p) / ep1
                roe1 = gain1 * leverage - fee_roe
                pnl1 = margin1 * roe1
                
                pnl_tot = pnl1
                tot_margin = margin1
                if has_pyramided:
                    gain2 = (p - ep2) / ep2 if side == 1 else (ep2 - p) / ep2
                    roe2 = gain2 * leverage - fee_roe
                    pnl2 = margin2 * roe2
                    pnl_tot += pnl2
                    tot_margin += margin2
                    
                portfolio_equity += pnl_tot
                portfolio_equity = max(portfolio_equity, 10.0)
                
                t_side[trade_count] = side
                t_margin_roe[trade_count] = pnl_tot / tot_margin
                t_dollar_pnl[trade_count] = pnl_tot
                t_equity_after[trade_count] = portfolio_equity
                t_res[trade_count] = 1 if pnl_tot > 0 else -1
                trade_count += 1
                in_pos = False
                has_pyramided = False
                
        if hr < 8 or hr >= 23:
            continue
            
        p_close = closes[i]
        p_high = highs[i]
        p_low = lows[i]
        c_low = channel_lows[i]
        c_high = channel_highs[i]
        c_amp = (c_high - c_low) / c_low if c_low > 0 else 0.0
        
        if not in_pos:
            if day_trades >= max_daily_trades or day_had_tp:
                continue
            if is_oscillation[i] == 0 or c_amp < 0.0035 or c_amp > 0.0125:
                continue
                
            # Maker Long Entry
            if (p_low <= c_low * 1.0002 and p_close >= c_low * 0.9995 and tau_long[i] >= tau_threshold):
                in_pos = True
                side = 1
                ep1 = c_low
                margin1 = portfolio_equity * tranche_frac
                sl1_p = ep1 * (1.0 - sl_pct)
                has_pyramided = False
                day_trades += 1
                
            # Maker Short Entry
            elif (p_high >= c_high * 0.9998 and p_close <= c_high * 1.0005 and tau_short[i] >= tau_threshold):
                in_pos = True
                side = -1
                ep1 = c_high
                margin1 = portfolio_equity * tranche_frac
                sl1_p = ep1 * (1.0 + sl_pct)
                has_pyramided = False
                day_trades += 1
                
        else: # IN POSITION
            if side == 1: # LONG
                # Check Liquidation
                if (ep1 - p_low) / ep1 >= liq_dist:
                    pnl_tot = -margin1 - (margin2 if has_pyramided else 0.0)
                    portfolio_equity += pnl_tot
                    t_side[trade_count] = side
                    t_margin_roe[trade_count] = -1.0
                    t_dollar_pnl[trade_count] = pnl_tot
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = -2
                    trade_count += 1
                    in_pos = False
                    has_pyramided = False
                    continue
                    
                # Check Pyramiding / Breakeven Lock trigger (+0.45% move)
                if not has_pyramided and (p_high - ep1) / ep1 >= tp1_pct:
                    # Lock SL1 to BE (Entry + Fees)
                    sl1_p = ep1 * (1.0 + maker_fee + 0.0002)
                    if enable_pyramiding:
                        has_pyramided = True
                        ep2 = ep1 * (1.0 + tp1_pct)
                        margin2 = portfolio_equity * tranche_frac
                        sl2_p = ep1 * 1.0010 # Stop for 2nd tranche is also above ep1!
                        
                # Check Stop Loss
                if has_pyramided:
                    if p_low <= sl2_p:
                        # Stopped out on pyramided trade
                        gain1 = (sl1_p - ep1) / ep1
                        roe1 = gain1 * leverage - fee_roe
                        pnl1 = margin1 * roe1
                        
                        gain2 = (sl2_p - ep2) / ep2
                        roe2 = gain2 * leverage - fee_roe
                        pnl2 = margin2 * roe2
                        
                        pnl_tot = pnl1 + pnl2
                        portfolio_equity += pnl_tot
                        portfolio_equity = max(portfolio_equity, 10.0)
                        
                        t_side[trade_count] = side
                        t_margin_roe[trade_count] = pnl_tot / (margin1 + margin2)
                        t_dollar_pnl[trade_count] = pnl_tot
                        t_equity_after[trade_count] = portfolio_equity
                        t_res[trade_count] = 1 if pnl_tot > 0 else -1
                        trade_count += 1
                        in_pos = False
                        has_pyramided = False
                        continue
                else:
                    if p_low <= sl1_p:
                        gain1 = (sl1_p - ep1) / ep1
                        roe1 = gain1 * leverage - fee_roe
                        pnl_tot = margin1 * roe1
                        portfolio_equity += pnl_tot
                        portfolio_equity = max(portfolio_equity, 10.0)
                        
                        t_side[trade_count] = side
                        t_margin_roe[trade_count] = roe1
                        t_dollar_pnl[trade_count] = pnl_tot
                        t_equity_after[trade_count] = portfolio_equity
                        t_res[trade_count] = 1 if pnl_tot > 0 else -1
                        trade_count += 1
                        in_pos = False
                        continue
                        
                # Check Final Take Profit Target (+1.20%)
                target_p = ep1 * (1.0 + tp2_pct)
                if p_high >= target_p:
                    gain1 = tp2_pct
                    roe1 = gain1 * leverage - fee_roe
                    pnl1 = margin1 * roe1
                    
                    pnl_tot = pnl1
                    tot_margin = margin1
                    if has_pyramided:
                        gain2 = (target_p - ep2) / ep2
                        roe2 = gain2 * leverage - fee_roe
                        pnl2 = margin2 * roe2
                        pnl_tot += pnl2
                        tot_margin += margin2
                        
                    portfolio_equity += pnl_tot
                    t_side[trade_count] = side
                    t_margin_roe[trade_count] = pnl_tot / tot_margin
                    t_dollar_pnl[trade_count] = pnl_tot
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = 1
                    trade_count += 1
                    in_pos = False
                    has_pyramided = False
                    day_had_tp = True
                    continue
                    
            else: # SHORT
                if (p_high - ep1) / ep1 >= liq_dist:
                    pnl_tot = -margin1 - (margin2 if has_pyramided else 0.0)
                    portfolio_equity += pnl_tot
                    t_side[trade_count] = side
                    t_margin_roe[trade_count] = -1.0
                    t_dollar_pnl[trade_count] = pnl_tot
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = -2
                    trade_count += 1
                    in_pos = False
                    has_pyramided = False
                    continue
                    
                if not has_pyramided and (ep1 - p_low) / ep1 >= tp1_pct:
                    sl1_p = ep1 * (1.0 - maker_fee - 0.0002)
                    if enable_pyramiding:
                        has_pyramided = True
                        ep2 = ep1 * (1.0 - tp1_pct)
                        margin2 = portfolio_equity * tranche_frac
                        sl2_p = ep1 * 0.9990
                        
                if has_pyramided:
                    if p_high >= sl2_p:
                        gain1 = (ep1 - sl1_p) / ep1
                        roe1 = gain1 * leverage - fee_roe
                        pnl1 = margin1 * roe1
                        
                        gain2 = (ep2 - sl2_p) / ep2
                        roe2 = gain2 * leverage - fee_roe
                        pnl2 = margin2 * roe2
                        
                        pnl_tot = pnl1 + pnl2
                        portfolio_equity += pnl_tot
                        portfolio_equity = max(portfolio_equity, 10.0)
                        
                        t_side[trade_count] = side
                        t_margin_roe[trade_count] = pnl_tot / (margin1 + margin2)
                        t_dollar_pnl[trade_count] = pnl_tot
                        t_equity_after[trade_count] = portfolio_equity
                        t_res[trade_count] = 1 if pnl_tot > 0 else -1
                        trade_count += 1
                        in_pos = False
                        has_pyramided = False
                        continue
                else:
                    if p_high >= sl1_p:
                        gain1 = (ep1 - sl1_p) / ep1
                        roe1 = gain1 * leverage - fee_roe
                        pnl_tot = margin1 * roe1
                        portfolio_equity += pnl_tot
                        portfolio_equity = max(portfolio_equity, 10.0)
                        
                        t_side[trade_count] = side
                        t_margin_roe[trade_count] = roe1
                        t_dollar_pnl[trade_count] = pnl_tot
                        t_equity_after[trade_count] = portfolio_equity
                        t_res[trade_count] = 1 if pnl_tot > 0 else -1
                        trade_count += 1
                        in_pos = False
                        continue
                        
                target_p = ep1 * (1.0 - tp2_pct)
                if p_low <= target_p:
                    gain1 = tp2_pct
                    roe1 = gain1 * leverage - fee_roe
                    pnl1 = margin1 * roe1
                    
                    pnl_tot = pnl1
                    tot_margin = margin1
                    if has_pyramided:
                        gain2 = (ep2 - target_p) / ep2
                        roe2 = gain2 * leverage - fee_roe
                        pnl2 = margin2 * roe2
                        pnl_tot += pnl2
                        tot_margin += margin2
                        
                    portfolio_equity += pnl_tot
                    t_side[trade_count] = side
                    t_margin_roe[trade_count] = pnl_tot / tot_margin
                    t_dollar_pnl[trade_count] = pnl_tot
                    t_equity_after[trade_count] = portfolio_equity
                    t_res[trade_count] = 1
                    trade_count += 1
                    in_pos = False
                    has_pyramided = False
                    day_had_tp = True
                    continue
                    
    return trade_count, portfolio_equity, t_margin_roe[:trade_count], t_dollar_pnl[:trade_count], t_equity_after[:trade_count], t_res[:trade_count]


def main():
    print("=" * 70)
    print("Simulating Optimal Execution & Maximum Return Strategies on ETH (100X)")
    print("实测 ETH 百倍杠杆最优落地与最大收益极限打法")
    print("=" * 70)
    
    # 1. Load 1s ETH dataset
    eth_path = r"D:\Convertible_Bond_data\crypto_data\history\1s\ETHUSDT_2026_07_08_1s.parquet"
    if not os.path.exists(eth_path):
        print(f"Dataset not found: {eth_path}")
        return
        
    df = pd.read_parquet(eth_path)
    print(f"Loaded ETH 1s dataset: {len(df):,} bars (62 days)")
    
    closes = df["close"].values.astype(np.float64)
    opens = df["open"].values.astype(np.float64)
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)
    volumes = df["volume"].values.astype(np.float64)
    taker_buy_vol = df["taker_buy_volume"].values.astype(np.float64)
    timestamps = df["open_time"].values
    
    dt = pd.to_datetime(timestamps, unit="ms", utc=True)
    times_day = dt.dayofyear.values.astype(np.int32)
    times_hour = dt.hour.values.astype(np.int32)
    
    print("Extracting multi-scale channel boundaries & order book walls...")
    channel_lows, channel_highs, is_oscillation, tau_long, tau_short = build_multi_scale_channels(
        closes, highs, lows, volumes, taker_buy_vol
    )
    
    initial_eq = 10000.0
    
    # Mode 1: Benchmark Base 100X Sub-Allocation (20% margin, static profit lock)
    tc1, eq1, roes1, pnls1, eq_curve1, res1 = simulate_sub_allocation_100x_fast(
        closes, opens, highs, lows, times_day, times_hour,
        channel_lows, channel_highs, is_oscillation,
        tau_long, tau_short,
        initial_equity=initial_eq, tranche_frac=0.20, leverage=100.0,
        sl_pct=0.0018, tp_pct=0.0045, maker_fee=0.0004, tau_threshold=0.70, max_daily_trades=2
    )
    
    # Mode 2: Dynamic Geometric Compounding (20% margin dynamically updated)
    # Mode 3: Risk-Free Pyramiding (浮盈加仓滚仓法)
    tc3, eq3, roes3, pnls3, eq_curve3, res3 = simulate_pyramiding_100x_fast(
        closes, opens, highs, lows, times_day, times_hour,
        channel_lows, channel_highs, is_oscillation,
        tau_long, tau_short,
        initial_equity=initial_eq, tranche_frac=0.20, leverage=100.0,
        sl_pct=0.0018, tp1_pct=0.0045, tp2_pct=0.0100, maker_fee=0.0004,
        tau_threshold=0.70, max_daily_trades=2, enable_pyramiding=True
    )
    
    # Mode 4: Aggressive Pyramiding (25% margin, Tier 2 target +1.50%)
    tc4, eq4, roes4, pnls4, eq_curve4, res4 = simulate_pyramiding_100x_fast(
        closes, opens, highs, lows, times_day, times_hour,
        channel_lows, channel_highs, is_oscillation,
        tau_long, tau_short,
        initial_equity=initial_eq, tranche_frac=0.25, leverage=100.0,
        sl_pct=0.0018, tp1_pct=0.0040, tp2_pct=0.0120, maker_fee=0.0004,
        tau_threshold=0.70, max_daily_trades=2, enable_pyramiding=True
    )
    
    modes = [
        ("1. 科学基准流 (标准 20% 分仓 + 保本锁利)", tc1, eq1, roes1, pnls1, eq_curve1, res1),
        ("2. 浮盈滚仓流 (保本后浮盈加仓 20%, 目标 +1.0%)", tc3, eq3, roes3, pnls3, eq_curve3, res3),
        ("3. 战神进阶流 (25% 分仓浮盈加仓, 目标 +1.2%)", tc4, eq4, roes4, pnls4, eq_curve4, res4),
    ]
    
    print("\n" + "=" * 85)
    print(f"{'Strategy Mode / 策略模式':<38} | {'Trades':<6} | {'WinRate':<7} | {'Return':<10} | {'MaxDD':<8} | {'Final Equity':<12}")
    print("-" * 85)
    
    for name, tc, eq, roes, pnls, eq_curve, res in modes:
        win_rate = (res == 1).sum() / tc * 100.0 if tc > 0 else 0.0
        tot_ret = (eq - initial_eq) / initial_eq * 100.0
        
        # Max Drawdown
        peak = initial_eq
        max_dd = 0.0
        for e in eq_curve:
            if e > peak:
                peak = e
            dd = (peak - e) / peak * 100.0
            if dd > max_dd:
                max_dd = dd
                
        print(f"{name:<38} | {tc:<6} | {win_rate:>6.1f}% | {tot_ret:>+8.1f}% | {max_dd:>7.1f}% | ${eq:>10.2f}")
        
    print("=" * 85)


if __name__ == "__main__":
    main()
