"""
Comprehensive 4-Asset Backtest & Evaluation Engine for BB + MACD Dual-Timeframe 20X Strategy
四大主流资产（BTC、ETH、SOL、BNB）布林带与 MACD 双周期 20倍高杠杆策略全量评测引擎

Evaluates across 21,427,200 1-second bars (July & August 2026) covering:
- Mode A: Micro-Scalp Target (Net 2.0% Margin ROE after fees, +0.18% price move)
- Mode B: Dynamic BB Opposite Band Target (Upper for Long, Lower for Short)
- Mode C: Trend Swing Target (Net 2.0% Price Move, +40% Margin ROE)
- Mode D: Calibrated Wave Filter (Controlled frequency, ~15-25 quality trades/month)
"""

import os
import sys
import glob
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
import numba

from bb_macd_20x_strategy import compute_dual_timeframe_indicators, simulate_bb_macd_fast

@numba.njit
def simulate_calibrated_wave_bb(closes, opens, uppers, lowers, smas, ema50s, hists, macds, signals, widths,
                                min_width=0.0030, cooldown_bars=3600, lev=20.0, fee_roe=0.016):
    """
    Calibrated Wave Filter: Enforces MACD trend wave cycle separation
    and trailing breakeven guard to eliminate fee drag while achieving Net 2%+ per trade.
    """
    n = len(closes)
    max_trades = 20000
    
    trade_side = np.zeros(max_trades, dtype=np.int32)
    trade_entry_p = np.zeros(max_trades, dtype=np.float64)
    trade_exit_p = np.zeros(max_trades, dtype=np.float64)
    trade_entry_idx = np.zeros(max_trades, dtype=np.int64)
    trade_exit_idx = np.zeros(max_trades, dtype=np.int64)
    trade_gross_roe = np.zeros(max_trades, dtype=np.float64)
    trade_net_roe = np.zeros(max_trades, dtype=np.float64)
    trade_hold = np.zeros(max_trades, dtype=np.int32)
    trade_res = np.zeros(max_trades, dtype=np.int32)
    trade_count = 0
    
    in_pos = False
    side = 0
    entry_p = 0.0
    entry_idx = 0
    sl_p = 0.0
    last_exit_idx = -cooldown_bars
    be_active = False
    
    for i in range(120, n):
        p = closes[i]
        op = opens[i]
        
        if np.isnan(lowers[i]) or np.isnan(uppers[i]) or np.isnan(ema50s[i]):
            continue
            
        if not in_pos:
            if i - last_exit_idx < cooldown_bars:
                continue
            if widths[i] < min_width:
                continue
                
            # Uptrend: 1m MACD > Signal & Hist > 0 & Close > EMA50
            if hists[i] > 0.0 and macds[i] > signals[i] and p > ema50s[i] and smas[i] > ema50s[i]:
                # Pullback to Lower Band or Middle Band with 1s bounce confirmation
                if p <= smas[i] * 1.0005 and p >= lowers[i] and p >= op and closes[i] > closes[i-5]:
                    in_pos = True
                    side = 1
                    entry_p = p
                    entry_idx = i
                    be_active = False
                    raw_sl = lowers[i] * 0.999
                    hard_sl = entry_p * (1.0 - 0.006)
                    sl_p = max(raw_sl, hard_sl)
                    
            # Downtrend: 1m MACD < Signal & Hist < 0 & Close < EMA50
            elif hists[i] < 0.0 and macds[i] < signals[i] and p < ema50s[i] and smas[i] < ema50s[i]:
                # Rally to Upper Band or Middle Band with 1s rejection confirmation
                if p >= smas[i] * 0.9995 and p <= uppers[i] and p <= op and closes[i] < closes[i-5]:
                    in_pos = True
                    side = -1
                    entry_p = p
                    entry_idx = i
                    be_active = False
                    raw_sl = uppers[i] * 1.001
                    hard_sl = entry_p * (1.0 + 0.006)
                    sl_p = min(raw_sl, hard_sl)
                    
        else: # IN POSITION
            hold = i - entry_idx
            
            if side == 1:
                gross = (p - entry_p) / entry_p * lev
                net = gross - fee_roe
                
                # Breakeven lock once net ROE >= +2.0%
                if not be_active and net >= 0.02:
                    sl_p = max(sl_p, entry_p * (1.0 + fee_roe / lev + 0.0002))
                    be_active = True
                    
                # Take profit at Upper Band or when net ROE >= +2%
                if p >= uppers[i] and net >= 0.02:
                    trade_side[trade_count] = side
                    trade_entry_p[trade_count] = entry_p
                    trade_exit_p[trade_count] = p
                    trade_entry_idx[trade_count] = entry_idx
                    trade_exit_idx[trade_count] = i
                    trade_gross_roe[trade_count] = gross
                    trade_net_roe[trade_count] = net
                    trade_hold[trade_count] = hold
                    trade_res[trade_count] = 1 # TP
                    trade_count += 1
                    in_pos = False
                    last_exit_idx = i
                elif p <= sl_p:
                    trade_side[trade_count] = side
                    trade_entry_p[trade_count] = entry_p
                    trade_exit_p[trade_count] = p
                    trade_entry_idx[trade_count] = entry_idx
                    trade_exit_idx[trade_count] = i
                    trade_gross_roe[trade_count] = gross
                    trade_net_roe[trade_count] = net
                    trade_hold[trade_count] = hold
                    trade_res[trade_count] = 1 if net > 0 else -1
                    trade_count += 1
                    in_pos = False
                    last_exit_idx = i
                elif hold >= 7200: # 2 hours max hold
                    trade_side[trade_count] = side
                    trade_entry_p[trade_count] = entry_p
                    trade_exit_p[trade_count] = p
                    trade_entry_idx[trade_count] = entry_idx
                    trade_exit_idx[trade_count] = i
                    trade_gross_roe[trade_count] = gross
                    trade_net_roe[trade_count] = net
                    trade_hold[trade_count] = hold
                    trade_res[trade_count] = 1 if net > 0 else -1
                    trade_count += 1
                    in_pos = False
                    last_exit_idx = i
                    
            elif side == -1:
                gross = (entry_p - p) / entry_p * lev
                net = gross - fee_roe
                
                if not be_active and net >= 0.02:
                    sl_p = min(sl_p, entry_p * (1.0 - fee_roe / lev - 0.0002))
                    be_active = True
                    
                if p <= lowers[i] and net >= 0.02:
                    trade_side[trade_count] = side
                    trade_entry_p[trade_count] = entry_p
                    trade_exit_p[trade_count] = p
                    trade_entry_idx[trade_count] = entry_idx
                    trade_exit_idx[trade_count] = i
                    trade_gross_roe[trade_count] = gross
                    trade_net_roe[trade_count] = net
                    trade_hold[trade_count] = hold
                    trade_res[trade_count] = 1
                    trade_count += 1
                    in_pos = False
                    last_exit_idx = i
                elif p >= sl_p:
                    trade_side[trade_count] = side
                    trade_entry_p[trade_count] = entry_p
                    trade_exit_p[trade_count] = p
                    trade_entry_idx[trade_count] = entry_idx
                    trade_exit_idx[trade_count] = i
                    trade_gross_roe[trade_count] = gross
                    trade_net_roe[trade_count] = net
                    trade_hold[trade_count] = hold
                    trade_res[trade_count] = 1 if net > 0 else -1
                    trade_count += 1
                    in_pos = False
                    last_exit_idx = i
                elif hold >= 7200:
                    trade_side[trade_count] = side
                    trade_entry_p[trade_count] = entry_p
                    trade_exit_p[trade_count] = p
                    trade_entry_idx[trade_count] = entry_idx
                    trade_exit_idx[trade_count] = i
                    trade_gross_roe[trade_count] = gross
                    trade_net_roe[trade_count] = net
                    trade_hold[trade_count] = hold
                    trade_res[trade_count] = 1 if net > 0 else -1
                    trade_count += 1
                    in_pos = False
                    last_exit_idx = i

    return (trade_side[:trade_count], trade_entry_p[:trade_count], trade_exit_p[:trade_count],
            trade_entry_idx[:trade_count], trade_exit_idx[:trade_count],
            trade_gross_roe[:trade_count], trade_net_roe[:trade_count],
            trade_hold[:trade_count], trade_res[:trade_count])


def run_full_evaluation():
    base_dir = r'D:\Convertible_Bond_data\crypto_data\history\1s'
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT']
    months = ['2026-07', '2026-08']
    
    print('=' * 80)
    print('Starting 4-Asset BB + MACD 20X Full Evaluation (21,427,200 1s Bars)')
    print('=' * 80)
    
    all_results = []
    all_trade_logs = []
    
    for sym in symbols:
        for m in months:
            pattern = os.path.join(base_dir, sym, f'{sym}_1s_{m}.parquet')
            if not os.path.exists(pattern):
                print(f'File not found: {pattern}')
                continue
                
            print(f'\n>>> Processing {sym} [{m}] ...')
            t0 = time.time()
            df_1s = pd.read_parquet(pattern)
            load_time = time.time() - t0
            
            # Compute dual timeframe indicators
            t1 = time.time()
            df_merged = compute_dual_timeframe_indicators(df_1s)
            
            # Add 1m EMA50
            df_1m = df_1s.set_index('open_time')['close'].resample('1min').ohlc().dropna()
            df_1m['ema50'] = df_1m['close'].ewm(span=50, adjust=False).mean()
            df_1m_shifted = df_1m[['ema50']].shift(1)
            df_merged = pd.merge_asof(df_merged, df_1m_shifted, left_on='open_time', right_index=True)
            prep_time = time.time() - t1
            
            closes = df_merged['close'].values.astype(np.float64)
            opens = df_merged['open'].values.astype(np.float64)
            uppers = df_merged['upper'].values.astype(np.float64)
            lowers = df_merged['lower'].values.astype(np.float64)
            smas = df_merged['sma20'].values.astype(np.float64)
            ema50s = df_merged['ema50'].values.astype(np.float64)
            hists = df_merged['hist'].values.astype(np.float64)
            macds = df_merged['macd'].values.astype(np.float64)
            signals = df_merged['signal'].values.astype(np.float64)
            widths = df_merged['width'].values.astype(np.float64)
            times = df_merged['open_time'].values
            
            # 1. Test Mode A (Net 2% ROE Scalp)
            (side, ep, xp, ei, xi, gross, net, hold, res) = simulate_bb_macd_fast(
                closes, opens, uppers, lowers, smas, hists, macds, signals, widths, mode=1, min_width=0.0020
            )
            res_a = analyze_results(sym, m, 'Mode A: Net 2% ROE Scalp', side, ep, xp, ei, xi, gross, net, hold, res, times)
            all_results.append(res_a)
            
            # 2. Test Mode B (Dynamic BB Opposite Band)
            (side, ep, xp, ei, xi, gross, net, hold, res) = simulate_bb_macd_fast(
                closes, opens, uppers, lowers, smas, hists, macds, signals, widths, mode=2, min_width=0.0025
            )
            res_b = analyze_results(sym, m, 'Mode B: Dynamic BB Band', side, ep, xp, ei, xi, gross, net, hold, res, times)
            all_results.append(res_b)
            
            # 3. Test Mode C (2% Price Move, +40% ROE)
            (side, ep, xp, ei, xi, gross, net, hold, res) = simulate_bb_macd_fast(
                closes, opens, uppers, lowers, smas, hists, macds, signals, widths, mode=3, min_width=0.0025
            )
            res_c = analyze_results(sym, m, 'Mode C: 2% Price Move', side, ep, xp, ei, xi, gross, net, hold, res, times)
            all_results.append(res_c)
            
            # 4. Test Mode D (Calibrated Wave Filter)
            (side, ep, xp, ei, xi, gross, net, hold, res) = simulate_calibrated_wave_bb(
                closes, opens, uppers, lowers, smas, ema50s, hists, macds, signals, widths, min_width=0.0030, cooldown_bars=3600
            )
            res_d = analyze_results(sym, m, 'Mode D: Calibrated Wave Filter', side, ep, xp, ei, xi, gross, net, hold, res, times)
            all_results.append(res_d)
            
            print(f'Done {sym} [{m}] in {load_time+prep_time:.1f}s.')
            
    res_df = pd.DataFrame(all_results)
    out_csv = r'c:\Users\liuqi\crypto\leverage_research\bb_macd_4asset_results.csv'
    res_df.to_csv(out_csv, index=False)
    print(f'\nMaster results saved to: {out_csv}')
    
    # Print summary pivot
    print('\n' + '=' * 100)
    print('BB + MACD 20X STRATEGY: COMPREHENSIVE PERFORMANCE SUMMARY MATRIX')
    print('=' * 100)
    cols = ['symbol', 'month', 'mode', 'trades', 'win_rate', 'avg_win_roe', 'avg_loss_roe', 'total_net_roe', 'total_fee_roe', 'profit_factor', 'liquidations']
    print(res_df[cols].to_string(index=False))
    
    return res_df


def analyze_results(symbol, month, mode_name, side, ep, xp, ei, xi, gross, net, hold, res, times):
    n_trades = len(side)
    fee_roe = 0.016
    
    if n_trades == 0:
        return {
            'symbol': symbol,
            'month': month,
            'mode': mode_name,
            'trades': 0,
            'win_rate': '0.0%',
            'avg_win_roe': '0.0%',
            'avg_loss_roe': '0.0%',
            'total_gross_roe': '0.0%',
            'total_fee_roe': '0.0%',
            'total_net_roe': '0.0%',
            'profit_factor': 0.0,
            'avg_hold_min': 0.0,
            'max_drawdown': '0.0%',
            'liquidations': 0
        }
        
    wins = net > 0
    losses = net < 0
    win_rate = wins.mean()
    avg_win = net[wins].mean() if wins.any() else 0.0
    avg_loss = net[losses].mean() if losses.any() else 0.0
    tot_gross = gross.sum()
    tot_fee = n_trades * fee_roe
    tot_net = net.sum()
    
    gross_gains = net[wins].sum()
    gross_losses = abs(net[losses].sum())
    pf = (gross_gains / gross_losses) if gross_losses > 0 else 999.0
    
    # Liquidation check: did any trade suffer gross loss > 4.5% price move (90% margin loss)?
    # Max price loss distance = gross / 20
    liq_count = (gross < -0.90).sum()
    
    return {
        'symbol': symbol,
        'month': month,
        'mode': mode_name,
        'trades': n_trades,
        'win_rate': f'{win_rate*100:.1f}%',
        'avg_win_roe': f'{avg_win*100:.2f}%',
        'avg_loss_roe': f'{avg_loss*100:.2f}%',
        'total_gross_roe': f'{tot_gross*100:.1f}%',
        'total_fee_roe': f'{tot_fee*100:.1f}%',
        'total_net_roe': f'{tot_net*100:.1f}%',
        'profit_factor': round(pf, 2),
        'avg_hold_min': round(hold.mean() / 60.0, 1),
        'liquidations': int(liq_count)
    }

if __name__ == '__main__':
    run_full_evaluation()
