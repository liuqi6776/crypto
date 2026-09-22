"""
Bollinger Bands & MACD Dual-Timeframe (1s & 1m) 20X Quantitative Strategy Engine
布林带与 MACD 双周期（1秒 + 1分钟）20倍高杠杆量化策略引擎

Core Strategy Logic:
1. Macro Trend Determination (1m MACD):
   - Uptrend: MACD > Signal & Hist > 0 -> ONLY LONG trades permitted.
   - Downtrend: MACD < Signal & Hist < 0 -> ONLY SHORT trades permitted.
   - Neutral / Chop: 100% Cash / No trades.
2. Bollinger Bands Setup (1m BB 20, 2.0 & 1s Execution):
   - Longs: Enter when 1s price pulls back to/near 1m Lower Band and confirms 1s micro-bounce.
   - Shorts: Enter when 1s price rallies to/near 1m Upper Band and confirms 1s micro-rejection.
3. Strict 20X Risk Guard:
   - Stop Loss placed outside Bollinger Band, hard-capped at <= 0.60% price move (-12% ROE).
   - Zero liquidation guarantee (7.5x distance to Binance -4.5% liquidation line).
4. Three Exit Modes:
   - Mode 1 (Mode A): Micro-Scalp Net 2% ROE (+0.18% price move).
   - Mode 2 (Mode B): Dynamic BB Opposite Band (Upper for Long, Lower for Short) with Min 2% Net ROE.
   - Mode 3 (Mode C): Net 2% Price Move (+40% ROE on 20x).
"""

import os
import time
import glob
import numpy as np
import pandas as pd
import numba

@numba.njit
def simulate_bb_macd_fast(closes, opens, uppers, lowers, smas, hists, macds, signals, widths,
                          mode=2, min_width=0.0025, fee_roe=0.016, lev=20.0, max_hold_bars=7200):
    """
    Ultra-fast Numba execution loop across 1-second price bars.
    fee_roe: 20X round-trip fee on margin (0.08% notional = 1.60% ROE)
    lev: 20.0x
    mode: 1 = Net 2% ROE, 2 = Dynamic BB Band, 3 = Net 2% Price Move
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
    trade_res = np.zeros(max_trades, dtype=np.int32) # 1=TP, -1=SL, 0=Timeout
    trade_count = 0
    
    in_pos = False
    side = 0
    entry_p = 0.0
    entry_idx = 0
    sl_p = 0.0
    tp_p = 0.0
    be_active = False
    
    for i in range(120, n):
        p = closes[i]
        op = opens[i]
        
        if np.isnan(lowers[i]) or np.isnan(uppers[i]) or np.isnan(hists[i]):
            continue
            
        if not in_pos:
            # Bandwidth filter: must have sufficient volatility to cover fee + 2% profit
            if widths[i] < min_width:
                continue
                
            # 1. UPTREND: 1m MACD > Signal & Hist > 0
            if hists[i] > 0.0 and macds[i] > signals[i]:
                # Price touches or dips near Lower Band and 1s bar shows micro-reversal
                if p <= lowers[i] * 1.0005 and p >= op:
                    in_pos = True
                    side = 1
                    entry_p = p
                    entry_idx = i
                    be_active = False
                    
                    # Stop Loss: placed below Lower Band, capped at 0.6% price move
                    raw_sl = lowers[i] * 0.9985
                    hard_sl = entry_p * (1.0 - 0.006)
                    sl_p = max(raw_sl, hard_sl)
                    
                    if mode == 1: # Net 2% ROE (Gross ROE = 3.6% -> Price Move = +0.18%)
                        tp_p = entry_p * (1.0 + (0.02 + fee_roe) / lev)
                    elif mode == 2: # Dynamic BB: Upper Band
                        tp_p = uppers[i]
                    elif mode == 3: # 2% Price Move (+40% ROE)
                        tp_p = entry_p * (1.0 + 0.02 + fee_roe / lev)
                        
            # 2. DOWNTREND: 1m MACD < Signal & Hist < 0
            elif hists[i] < 0.0 and macds[i] < signals[i]:
                # Price touches or spikes near Upper Band and 1s bar shows micro-rejection
                if p >= uppers[i] * 0.9995 and p <= op:
                    in_pos = True
                    side = -1
                    entry_p = p
                    entry_idx = i
                    be_active = False
                    
                    raw_sl = uppers[i] * 1.0015
                    hard_sl = entry_p * (1.0 + 0.006)
                    sl_p = min(raw_sl, hard_sl)
                    
                    if mode == 1:
                        tp_p = entry_p * (1.0 - (0.02 + fee_roe) / lev)
                    elif mode == 2:
                        tp_p = lowers[i]
                    elif mode == 3:
                        tp_p = entry_p * (1.0 - 0.02 - fee_roe / lev)
                        
        else: # IN POSITION
            hold = i - entry_idx
            
            if side == 1: # LONG POSITION
                gross = (p - entry_p) / entry_p * lev
                net = gross - fee_roe
                
                # Trailing Breakeven Lock: once net ROE >= +2.0%, lock SL to breakeven + fee
                if mode >= 2 and not be_active and net >= 0.02:
                    sl_p = max(sl_p, entry_p * (1.0 + fee_roe / lev + 0.0002))
                    be_active = True
                    
                if mode == 2:
                    # Dynamic TP: Upper Band, but ensure at least +2% net ROE if hit
                    target_tp = max(uppers[i], entry_p * (1.0 + (0.02 + fee_roe) / lev))
                else:
                    target_tp = tp_p
                    
                # Check TP
                if p >= target_tp:
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
                # Check SL
                elif p <= sl_p:
                    trade_side[trade_count] = side
                    trade_entry_p[trade_count] = entry_p
                    trade_exit_p[trade_count] = p
                    trade_entry_idx[trade_count] = entry_idx
                    trade_exit_idx[trade_count] = i
                    trade_gross_roe[trade_count] = gross
                    trade_net_roe[trade_count] = net
                    trade_hold[trade_count] = hold
                    trade_res[trade_count] = -1 # SL
                    trade_count += 1
                    in_pos = False
                # Check Timeout (max hold = 2 hours)
                elif hold >= max_hold_bars:
                    trade_side[trade_count] = side
                    trade_entry_p[trade_count] = entry_p
                    trade_exit_p[trade_count] = p
                    trade_entry_idx[trade_count] = entry_idx
                    trade_exit_idx[trade_count] = i
                    trade_gross_roe[trade_count] = gross
                    trade_net_roe[trade_count] = net
                    trade_hold[trade_count] = hold
                    trade_res[trade_count] = 0 # Timeout
                    trade_count += 1
                    in_pos = False
                    
            elif side == -1: # SHORT POSITION
                gross = (entry_p - p) / entry_p * lev
                net = gross - fee_roe
                
                if mode >= 2 and not be_active and net >= 0.02:
                    sl_p = min(sl_p, entry_p * (1.0 - fee_roe / lev - 0.0002))
                    be_active = True
                    
                if mode == 2:
                    target_tp = min(lowers[i], entry_p * (1.0 - (0.02 + fee_roe) / lev))
                else:
                    target_tp = tp_p
                    
                # Check TP
                if p <= target_tp:
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
                # Check SL
                elif p >= sl_p:
                    trade_side[trade_count] = side
                    trade_entry_p[trade_count] = entry_p
                    trade_exit_p[trade_count] = p
                    trade_entry_idx[trade_count] = entry_idx
                    trade_exit_idx[trade_count] = i
                    trade_gross_roe[trade_count] = gross
                    trade_net_roe[trade_count] = net
                    trade_hold[trade_count] = hold
                    trade_res[trade_count] = -1
                    trade_count += 1
                    in_pos = False
                elif hold >= max_hold_bars:
                    trade_side[trade_count] = side
                    trade_entry_p[trade_count] = entry_p
                    trade_exit_p[trade_count] = p
                    trade_entry_idx[trade_count] = entry_idx
                    trade_exit_idx[trade_count] = i
                    trade_gross_roe[trade_count] = gross
                    trade_net_roe[trade_count] = net
                    trade_hold[trade_count] = hold
                    trade_res[trade_count] = 0
                    trade_count += 1
                    in_pos = False

    return (trade_side[:trade_count], trade_entry_p[:trade_count], trade_exit_p[:trade_count],
            trade_entry_idx[:trade_count], trade_exit_idx[:trade_count],
            trade_gross_roe[:trade_count], trade_net_roe[:trade_count],
            trade_hold[:trade_count], trade_res[:trade_count])


def compute_dual_timeframe_indicators(df_1s):
    """
    Resamples 1s dataframe to 1m, computes MACD and Bollinger Bands,
    and maps them back to 1s bars without look-ahead bias.
    """
    df_1m = df_1s.set_index('open_time')['close'].resample('1min').ohlc().dropna()
    
    # 1. Bollinger Bands (20, 2.0)
    sma20 = df_1m['close'].rolling(20).mean()
    std20 = df_1m['close'].rolling(20).std()
    upper = sma20 + 2.0 * std20
    lower = sma20 - 2.0 * std20
    width = (upper - lower) / sma20
    
    # 2. MACD (12, 26, 9)
    ema12 = df_1m['close'].ewm(span=12, adjust=False).mean()
    ema26 = df_1m['close'].ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    
    df_1m['sma20'] = sma20
    df_1m['upper'] = upper
    df_1m['lower'] = lower
    df_1m['width'] = width
    df_1m['macd'] = macd
    df_1m['signal'] = signal
    df_1m['hist'] = hist
    
    # Shift 1m indicators by 1 bar to prevent lookahead bias
    df_1m_shifted = df_1m[['sma20', 'upper', 'lower', 'width', 'macd', 'signal', 'hist']].shift(1)
    
    # Merge asof to 1s
    df_merged = pd.merge_asof(
        df_1s.sort_values('open_time'),
        df_1m_shifted,
        left_on='open_time',
        right_index=True
    )
    
    return df_merged


def run_single_asset_simulation(parquet_path, mode=2, min_width=0.0025, fee_roe=0.016, lev=20.0):
    """
    Loads a 1s parquet file, computes indicators, runs Numba simulation,
    and returns a structured trades DataFrame and summary metrics.
    """
    t0 = time.time()
    df_1s = pd.read_parquet(parquet_path)
    load_time = time.time() - t0
    
    t1 = time.time()
    df_merged = compute_dual_timeframe_indicators(df_1s)
    prep_time = time.time() - t1
    
    closes = df_merged['close'].values.astype(np.float64)
    opens = df_merged['open'].values.astype(np.float64)
    uppers = df_merged['upper'].values.astype(np.float64)
    lowers = df_merged['lower'].values.astype(np.float64)
    smas = df_merged['sma20'].values.astype(np.float64)
    hists = df_merged['hist'].values.astype(np.float64)
    macds = df_merged['macd'].values.astype(np.float64)
    signals = df_merged['signal'].values.astype(np.float64)
    widths = df_merged['width'].values.astype(np.float64)
    times = df_merged['open_time'].values
    
    t2 = time.time()
    (side, entry_p, exit_p, entry_idx, exit_idx, gross_roe, net_roe, hold, res) = simulate_bb_macd_fast(
        closes, opens, uppers, lowers, smas, hists, macds, signals, widths,
        mode=mode, min_width=min_width, fee_roe=fee_roe, lev=lev
    )
    sim_time = time.time() - t2
    
    if len(side) == 0:
        return pd.DataFrame(), {'total_trades': 0}
        
    trades_df = pd.DataFrame({
        'side': np.where(side == 1, 'LONG', 'SHORT'),
        'entry_time': times[entry_idx],
        'exit_time': times[exit_idx],
        'entry_price': entry_p,
        'exit_price': exit_p,
        'gross_roe': gross_roe,
        'net_roe': net_roe,
        'hold_seconds': hold,
        'result': np.where(res == 1, 'TP', np.where(res == -1, 'SL', 'TIMEOUT'))
    })
    
    # Calculate performance metrics
    win_rate = (trades_df['result'] == 'TP').mean()
    total_net_roe = trades_df['net_roe'].sum()
    gross_gains = trades_df.loc[trades_df['net_roe'] > 0, 'net_roe'].sum()
    gross_losses = abs(trades_df.loc[trades_df['net_roe'] < 0, 'net_roe'].sum())
    profit_factor = (gross_gains / gross_losses) if gross_losses > 0 else 999.0
    avg_hold_s = trades_df['hold_seconds'].mean()
    
    # Cumulative equity curve
    equity_curve = (1.0 + trades_df['net_roe']).cumprod()
    peak = equity_curve.cummax()
    max_dd = ((equity_curve - peak) / peak).min()
    
    summary = {
        'total_trades': len(trades_df),
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'total_net_roe': total_net_roe,
        'compounded_return': equity_curve.iloc[-1] - 1.0,
        'max_drawdown': max_dd,
        'avg_hold_seconds': avg_hold_s,
        'tp_count': (trades_df['result'] == 'TP').sum(),
        'sl_count': (trades_df['result'] == 'SL').sum(),
        'timeout_count': (trades_df['result'] == 'TIMEOUT').sum(),
        'load_time': load_time,
        'prep_time': prep_time,
        'sim_time': sim_time
    }
    
    return trades_df, summary

if __name__ == '__main__':
    sample_file = r'D:\Convertible_Bond_data\crypto_data\history\1s\ETHUSDT\ETHUSDT_1s_2026-08-01.parquet'
    if os.path.exists(sample_file):
        print(f'Testing on {sample_file}...')
        for m, name in [(1, 'Mode A: Net 2% ROE'), (2, 'Mode B: Dynamic BB'), (3, 'Mode C: 2% Price Move')]:
            tdf, s = run_single_asset_simulation(sample_file, mode=m, min_width=0.0025)
            print(f'[{name}] Trades: {s["total_trades"]}, Win Rate: {s.get("win_rate",0)*100:.1f}%, Net ROE: {s.get("total_net_roe",0)*100:.2f}%, Sim Time: {s.get("sim_time",0)*1000:.1f}ms')
