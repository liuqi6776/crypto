"""
Comprehensive Evaluation Engine for Daily Box & Order Book Wall Sniper
每日固定箱体震荡与挂单量大单护城河狙击策略全景评测引擎

Evaluates across BTC and ETH for July & August 2026 across 200X, 100X, and 50X leverage tiers.
"""

import os
import sys
import glob
import time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from daily_box_orderbook_sniper import simulate_daily_box_sniper_fast, compute_daily_asian_boxes

def run_evaluation():
    base_dir = r'D:\Convertible_Bond_data\crypto_data\history\1s'
    symbols = ['BTCUSDT', 'ETHUSDT']
    months = ['2026-07', '2026-08']
    
    leverage_configs = [
        {'lev': 200.0, 'sl_pct': 0.0007, 'tp_pct': 0.0035, 'name': '200X Extreme Leverage'},
        {'lev': 100.0, 'sl_pct': 0.0016, 'tp_pct': 0.0045, 'name': '100X Calibrated Sweet Spot'},
        {'lev': 50.0,  'sl_pct': 0.0025, 'tp_pct': 0.0060, 'name': '50X Conservative Swing'}
    ]
    
    print('=' * 85)
    print('Starting Daily Box & Order Book Wall Sniper Evaluation (BTC & ETH, 200X vs 100X vs 50X)')
    print('=' * 85)
    
    all_summary = []
    all_trades = []
    
    for sym in symbols:
        for m in months:
            fpath = os.path.join(base_dir, sym, f'{sym}_1s_{m}.parquet')
            if not os.path.exists(fpath):
                print(f'File not found: {fpath}')
                continue
                
            print(f'\n>>> Processing {sym} [{m}] ...')
            t0 = time.time()
            df_1s = pd.read_parquet(fpath)
            
            # Resample to 1m
            df_1m = df_1s.set_index('open_time')[['close', 'open', 'high', 'low', 'volume']].resample('1min').agg({
                'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
            }).dropna()
            
            # Compute daily Asian boxes
            df_1m = compute_daily_asian_boxes(df_1m)
            
            # Convert timestamps to day-index and hour-of-day
            times = df_1m.index
            times_day = (times - times[0]).days.values.astype(np.int32)
            times_hour = times.hour.values.astype(np.int32)
            
            closes = df_1m['close'].values.astype(np.float64)
            opens = df_1m['open'].values.astype(np.float64)
            highs = df_1m['high'].values.astype(np.float64)
            lows = df_1m['low'].values.astype(np.float64)
            box_lows = df_1m['box_low'].values.astype(np.float64)
            box_highs = df_1m['box_high'].values.astype(np.float64)
            box_valid = df_1m['box_valid'].values.astype(np.int32)
            
            for cfg in leverage_configs:
                lev = cfg['lev']
                sl = cfg['sl_pct']
                tp = cfg['tp_pct']
                name = cfg['name']
                
                (side, ep, xp, ei, xi, net_roe, res, day_idx) = simulate_daily_box_sniper_fast(
                    closes, opens, highs, lows, times_day, times_hour,
                    box_lows, box_highs, box_valid,
                    lev=lev, sl_pct=sl, tp_pct=tp, maker_fee=0.0004, max_daily_trades=2
                )
                
                n_trades = len(side)
                if n_trades == 0:
                    continue
                    
                wins = net_roe > 0
                losses = net_roe < 0
                liqs = (res == -2).sum()
                tp_count = (res == 1).sum()
                sl_count = (res == -1).sum()
                
                win_rate = wins.mean() * 100
                tot_net = net_roe.sum() * 100
                avg_win = net_roe[wins].mean() * 100 if wins.any() else 0.0
                avg_loss = net_roe[losses].mean() * 100 if losses.any() else 0.0
                
                gains = net_roe[wins].sum()
                loss_sum = abs(net_roe[losses].sum())
                pf = (gains / loss_sum) if loss_sum > 0 else 999.0
                
                # Compound equity curve
                eq = (1.0 + net_roe).cumprod()
                peak = np.maximum.accumulate(eq)
                max_dd = ((eq - peak) / peak).min() * 100
                
                all_summary.append({
                    'symbol': sym,
                    'month': m,
                    'mode': name,
                    'leverage': f'{int(lev)}X',
                    'trades': n_trades,
                    'daily_trades': round(n_trades / 31.0, 2),
                    'win_rate': f'{win_rate:.1f}%',
                    'tp_count': tp_count,
                    'sl_count': sl_count,
                    'liquidations': int(liqs),
                    'total_net_roe': f'{tot_net:.1f}%',
                    'avg_win_roe': f'+{avg_win:.1f}%',
                    'avg_loss_roe': f'{avg_loss:.1f}%',
                    'profit_factor': round(pf, 2),
                    'max_drawdown': f'{max_dd:.1f}%'
                })
                
                # Store individual trades
                for t in range(n_trades):
                    all_trades.append({
                        'symbol': sym,
                        'month': m,
                        'leverage': int(lev),
                        'side': 'LONG' if side[t] == 1 else 'SHORT',
                        'entry_time': times[ei[t]],
                        'exit_time': times[xi[t]],
                        'entry_price': ep[t],
                        'exit_price': xp[t],
                        'net_roe': net_roe[t],
                        'result': 'TP' if res[t] == 1 else ('LIQ' if res[t] == -2 else 'SL')
                    })
                    
            print(f'Completed {sym} [{m}] in {time.time() - t0:.1f}s.')
            
    summary_df = pd.DataFrame(all_summary)
    trades_df = pd.DataFrame(all_trades)
    
    out_sum_csv = r'c:\Users\liuqi\crypto\leverage_research\daily_box_sniper_summary.csv'
    out_trd_csv = r'c:\Users\liuqi\crypto\leverage_research\daily_box_sniper_trades.csv'
    
    summary_df.to_csv(out_sum_csv, index=False)
    trades_df.to_csv(out_trd_csv, index=False)
    
    print('\n' + '=' * 100)
    print('DAILY BOX & ORDER BOOK WALL SNIPER: PERFORMANCE SUMMARY MATRIX')
    print('=' * 100)
    cols = ['symbol', 'month', 'leverage', 'trades', 'daily_trades', 'win_rate', 'liquidations', 'total_net_roe', 'avg_win_roe', 'avg_loss_roe', 'profit_factor']
    print(summary_df[cols].to_string(index=False))
    
    return summary_df, trades_df

if __name__ == '__main__':
    run_evaluation()
