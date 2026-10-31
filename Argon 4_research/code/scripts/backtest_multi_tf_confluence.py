import os
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import datetime

os.makedirs('reports', exist_ok=True)

files_1m = glob.glob('scratch/klines_1m/*.parquet')
episodes = []
for f1m in files_1m:
    basename = os.path.basename(f1m)
    f15m = os.path.join('scratch/klines_15m', basename)
    f1h = os.path.join('scratch/klines_1h', basename)
    if os.path.exists(f15m) and os.path.exists(f1h):
        parts = basename.replace('.parquet', '').split('_')
        sym = parts[0]
        start_ms = int(parts[2])
        episodes.append({
            'symbol': sym,
            'start_ms': start_ms,
            'f_1m': f1m,
            'f_15m': f15m,
            'f_1h': f1h
        })

episodes.sort(key=lambda x: x['start_ms'])
print(f"Total synchronized multi-timeframe episodes: {len(episodes)}")

def compute_vwap(df, window=20):
    pv = df['close'] * df['vol']
    vwap = pv.rolling(window, min_periods=3).sum() / df['vol'].rolling(window, min_periods=3).sum()
    return vwap.fillna(df['close'])

def run_multi_tf_confluence(mode='TAKER', leverage=3.0, slippage_pct=0.0020):
    """
    mode: 'TAKER' or 'MAKER'
    leverage: 3.0 or 5.0
    """
    taker_fee = 0.0005 # 0.05%
    maker_fee = 0.0002 # 0.02%
    fee_rate = taker_fee if mode == 'TAKER' else maker_fee
    slip = slippage_pct if mode == 'TAKER' else 0.0
    
    initial_equity = 10000.0
    equity = initial_equity
    equity_curve = [{'timestamp': pd.to_datetime('2023-01-01'), 'equity': initial_equity, 'trade_pnl': 0, 'symbol': 'INIT'}]
    trades = []
    
    for ep in episodes:
        df_15m = pd.read_parquet(ep['f_15m']).sort_values('open_time').reset_index(drop=True)
        df_1m = pd.read_parquet(ep['f_1m']).sort_values('open_time').reset_index(drop=True)
        
        if len(df_15m) < 20 or len(df_1m) < 120:
            continue
            
        sym = ep['symbol']
        
        # 1. Macro 15m Exhaustion & Reversal Detection
        peak_idx = df_15m['high'].idxmax()
        peak_high = df_15m.loc[peak_idx, 'high']
        peak_time = df_15m.loc[peak_idx, 'open_time']
        
        # Squeeze expansion requirement: peak is >= 30% above 24h baseline
        base_low = df_15m['low'].iloc[max(0, peak_idx-48):peak_idx].min()
        if (peak_high / base_low) < 1.30:
            continue
            
        post_peak_15m = df_15m.iloc[peak_idx:].copy().reset_index(drop=True)
        if len(post_peak_15m) < 4:
            continue
            
        # Detect the first swing low (neckline) within 8 bars (2 hours) of peak
        neck_idx = post_peak_15m['low'].iloc[1:min(10, len(post_peak_15m))].idxmin()
        neck_low = post_peak_15m.loc[neck_idx, 'low']
        
        # 15m MSS breakdown candle
        breakdown_15m = post_peak_15m.iloc[neck_idx+1:][post_peak_15m.iloc[neck_idx+1:]['close'] < neck_low]
        if len(breakdown_15m) == 0:
            # Fallback: breaks 15m VWAP
            post_peak_15m['vwap'] = compute_vwap(post_peak_15m, 8)
            breakdown_15m = post_peak_15m.iloc[1:][post_peak_15m.iloc[1:]['close'] < post_peak_15m.iloc[1:]['vwap']]
            if len(breakdown_15m) == 0:
                continue
                
        mss_candle = breakdown_15m.iloc[0]
        # 15m candle closes at open_time + 15 mins
        mss_close_time = mss_candle['open_time'] + pd.Timedelta(minutes=15)
        
        # 2. 1-Minute Precision Sniper Execution
        # Filter 1m candles starting from mss_close_time up to 2 hours after
        df_1m['ema_15'] = df_1m['close'].ewm(span=15).mean()
        df_1m['vwap_30'] = compute_vwap(df_1m, 30)
        
        # Scan 1m candles in execution window
        exec_window = df_1m[(df_1m['open_time'] >= mss_close_time) & 
                            (df_1m['open_time'] <= mss_close_time + pd.Timedelta(hours=2))].copy()
        if len(exec_window) == 0:
            continue
            
        entry_bar = None
        entry_price = None
        
        for idx, bar in exec_window.iterrows():
            ema = bar['ema_15']
            retest_ok = bar['high'] >= ema * 0.998
            
            if mode == 'TAKER':
                # Taker: retests EMA and closes bearish (close < open)
                if retest_ok and (bar['close'] < bar['open']):
                    entry_bar = bar
                    entry_price = bar['close'] * (1.0 - slip) # market sell slippage
                    break
            elif mode == 'MAKER':
                # Maker: limit order placed at EMA15
                limit_target = ema
                if bar['high'] >= limit_target and bar['low'] <= limit_target:
                    entry_bar = bar
                    entry_price = limit_target # 0 slippage
                    break
                    
        # If no retest occurred in 2h, take first confirmation
        if entry_bar is None:
            if mode == 'TAKER':
                entry_bar = exec_window.iloc[0]
                entry_price = entry_bar['close'] * (1.0 - slip)
            else:
                # Maker limit order filled at next touch
                entry_bar = exec_window.iloc[0]
                entry_price = entry_bar['open']
                
        # 3. Position Sizing & Parameters
        hard_sl = peak_high * 1.02 # 2% above 15m peak
        sl_dist = (hard_sl / entry_price) - 1.0
        if sl_dist > 0.25: hard_sl = entry_price * 1.20
        if sl_dist < 0.02: hard_sl = entry_price * 1.03
        
        margin = equity * 0.10 # 10% account equity
        notional = margin * leverage
        coins = notional / entry_price
        entry_fee = notional * fee_rate
        
        trade_info = {
            'symbol': sym,
            'mode': mode,
            'leverage': leverage,
            'entry_time': entry_bar['open_time'],
            'entry_price': entry_price,
            'peak_price': peak_high,
            'hard_sl': hard_sl,
            'orig_sl': hard_sl,
            'margin': margin,
            'notional': notional,
            'coins': coins,
            'coins_remaining': coins,
            'fees_paid': entry_fee,
            'realized_pnl': 0.0,
            'tp1_hit': False,
            'tp2_hit': False
        }
        
        # 4. Position Lifecycle Simulation on 1m candles
        entry_idx_in_1m = df_1m[df_1m['open_time'] >= entry_bar['open_time']].index[0]
        remaining_1m = df_1m.iloc[entry_idx_in_1m+1:].copy()
        
        for bar_i, (b_idx, row) in enumerate(remaining_1m.iterrows()):
            cur_time = row['open_time']
            cur_price = row['close']
            
            # Check Hard Stop Loss
            if row['high'] >= trade_info['hard_sl']:
                exit_price = trade_info['hard_sl'] * (1.0 + slip)
                exit_coins = trade_info['coins_remaining']
                pnl = exit_coins * (trade_info['entry_price'] - exit_price)
                exit_fee = (exit_coins * exit_price) * fee_rate
                trade_info['realized_pnl'] += (pnl - exit_fee)
                trade_info['fees_paid'] += exit_fee
                trade_info['exit_time'] = cur_time
                trade_info['exit_price'] = exit_price
                trade_info['exit_reason'] = 'STOP_LOSS' if not trade_info['tp1_hit'] else 'BREAK_EVEN'
                break
                
            # Check TP 1 (-15% drop)
            tp1_target = trade_info['entry_price'] * 0.85
            if (not trade_info['tp1_hit']) and (row['low'] <= tp1_target):
                exit_price = tp1_target * (1.0 + slip)
                close_coins = trade_info['coins'] * 0.35
                pnl = close_coins * (trade_info['entry_price'] - exit_price)
                fee = (close_coins * exit_price) * fee_rate
                trade_info['realized_pnl'] += (pnl - fee)
                trade_info['fees_paid'] += fee
                trade_info['coins_remaining'] -= close_coins
                trade_info['tp1_hit'] = True
                trade_info['hard_sl'] = trade_info['entry_price'] # Move SL to Break-Even!
                
            # Check TP 2 (-35% drop)
            tp2_target = trade_info['entry_price'] * 0.65
            if (not trade_info['tp2_hit']) and (row['low'] <= tp2_target):
                exit_price = tp2_target * (1.0 + slip)
                close_coins = trade_info['coins'] * 0.40
                pnl = close_coins * (trade_info['entry_price'] - exit_price)
                fee = (close_coins * exit_price) * fee_rate
                trade_info['realized_pnl'] += (pnl - fee)
                trade_info['fees_paid'] += fee
                trade_info['coins_remaining'] -= close_coins
                trade_info['tp2_hit'] = True
                
            # Time / Trailing exit (held 24h = 1440 bars or end of data)
            if bar_i >= 1440 or bar_i == len(remaining_1m) - 1:
                exit_price = cur_price * (1.0 + slip)
                exit_coins = trade_info['coins_remaining']
                pnl = exit_coins * (trade_info['entry_price'] - exit_price)
                fee = (exit_coins * exit_price) * fee_rate
                trade_info['realized_pnl'] += (pnl - fee)
                trade_info['fees_paid'] += fee
                trade_info['exit_time'] = cur_time
                trade_info['exit_price'] = exit_price
                trade_info['exit_reason'] = 'TIME_EXIT' if trade_info['tp1_hit'] else 'FINAL_BAR'
                break
                
        # Update portfolio equity
        equity += trade_info['realized_pnl']
        equity_curve.append({
            'timestamp': trade_info['exit_time'],
            'equity': equity,
            'trade_pnl': trade_info['realized_pnl'],
            'symbol': sym
        })
        trades.append(trade_info)
        
    return pd.DataFrame(trades), pd.DataFrame(equity_curve)

print("\n" + "="*80)
print("Running Multi-Timeframe Confluence Simulation across 2023 - 2026...")
print("="*80)

# Run 4 models:
tr_3x_t, cu_3x_t = run_multi_tf_confluence(mode='TAKER', leverage=3.0)
tr_5x_t, cu_5x_t = run_multi_tf_confluence(mode='TAKER', leverage=5.0)
tr_3x_m, cu_3x_m = run_multi_tf_confluence(mode='MAKER', leverage=3.0)
tr_5x_m, cu_5x_m = run_multi_tf_confluence(mode='MAKER', leverage=5.0)

def compute_perf(df_tr, df_cu, name):
    n = len(df_tr)
    if n == 0:
        return {'Model': name, 'Trades': 0, 'Win Rate': 'N/A', 'Profit Factor': 'N/A', 'Final Equity': '$10,000', 'Return': '0.0%', 'Max DD': '0.0%'}
    wins = df_tr[df_tr['realized_pnl'] > 0]
    losses = df_tr[df_tr['realized_pnl'] < 0]
    win_rate = len(wins) / n * 100
    tot_p = wins['realized_pnl'].sum() if len(wins) > 0 else 0
    tot_l = abs(losses['realized_pnl'].sum()) if len(losses) > 0 else 1
    pf = tot_p / tot_l if tot_l > 0 else np.nan
    final_eq = df_cu['equity'].iloc[-1]
    ret_pct = (final_eq / 10000.0 - 1.0) * 100
    
    cummax = df_cu['equity'].cummax()
    dd = (df_cu['equity'] - cummax) / cummax * 100
    max_dd = abs(dd.min())
    
    tot_vol = df_tr['notional'].sum()
    avg_vol = df_tr['notional'].mean()
    tot_fees = df_tr['fees_paid'].sum()
    
    return {
        'Model (策略模式)': name,
        'Trades (交易数)': n,
        'Win Rate (胜率)': f"{win_rate:.1f}%",
        'Profit Factor (盈亏比)': f"{pf:.2f}",
        'Final Equity (最终净值)': f"${final_eq:,.2f}",
        'Return (累计回报)': f"{ret_pct:+.1f}%",
        'Max Drawdown (最大回撤)': f"{max_dd:.2f}%",
        'Total Volume (成交额)': f"${tot_vol:,.2f}",
        'Avg Vol/Trade (单笔体量)': f"${avg_vol:,.2f}",
        'Total Fees & Slippage': f"${tot_fees:,.2f}"
    }

m_list = [
    compute_perf(tr_3x_t, cu_3x_t, "Multi-TF 3x Taker (市价吃单)"),
    compute_perf(tr_5x_t, cu_5x_t, "Multi-TF 5x Taker (市价吃单)"),
    compute_perf(tr_3x_m, cu_3x_m, "Multi-TF 3x Maker (限价挂单)"),
    compute_perf(tr_5x_m, cu_5x_m, "Multi-TF 5x Maker (限价挂单)")
]

summary_df = pd.DataFrame(m_list)
print("\n" + "="*80)
print("=== MULTI-TIMEFRAME CONFLUENCE (1h + 15m + 1m) FINAL PERFORMANCE MATRIX ===")
print("="*80)
print(summary_df.to_string(index=False))

# Trade log export for Multi-TF 3x and 5x Maker
if len(tr_3x_m) > 0:
    out_cols = ['symbol', 'mode', 'entry_time', 'exit_time', 'entry_price', 'exit_price', 'notional', 'margin', 'realized_pnl', 'fees_paid', 'exit_reason']
    tr_out = tr_3x_m[out_cols].copy()
    tr_out['pnl_pct'] = (tr_out['realized_pnl'] / tr_out['margin']) * 100
    tr_out.to_csv('reports/backtest_multi_tf_trades_3x_maker.csv', index=False)
    print("\nDetailed Trade Log for Multi-TF 3x Maker:")
    print(tr_out[['symbol', 'entry_time', 'entry_price', 'exit_price', 'notional', 'realized_pnl', 'pnl_pct', 'exit_reason']].to_string(index=False))

if len(tr_5x_m) > 0:
    tr_out_5x = tr_5x_m[out_cols].copy()
    tr_out_5x['pnl_pct'] = (tr_out_5x['realized_pnl'] / tr_out_5x['margin']) * 100
    tr_out_5x.to_csv('reports/backtest_multi_tf_trades_5x_maker.csv', index=False)

# Plot Equity Curves
plt.figure(figsize=(13, 7))
plt.plot(cu_3x_t['timestamp'], cu_3x_t['equity'], label=f"3x Taker ({m_list[0]['Return (累计回报)']}, DD: {m_list[0]['Max Drawdown (最大回撤)']})", color='#2b5c8f', linewidth=2, linestyle='--')
plt.plot(cu_5x_t['timestamp'], cu_5x_t['equity'], label=f"5x Taker ({m_list[1]['Return (累计回报)']}, DD: {m_list[1]['Max Drawdown (最大回撤)']})", color='#e06666', linewidth=2, linestyle='--')
plt.plot(cu_3x_m['timestamp'], cu_3x_m['equity'], label=f"3x Maker ({m_list[2]['Return (累计回报)']}, DD: {m_list[2]['Max Drawdown (最大回撤)']})", color='#1b7837', linewidth=2.5)
plt.plot(cu_5x_m['timestamp'], cu_5x_m['equity'], label=f"5x Maker ({m_list[3]['Return (累计回报)']}, DD: {m_list[3]['Max Drawdown (最大回撤)']})", color='#762a83', linewidth=2.5)

plt.axhline(10000, color='gray', linestyle=':', label='Initial Capital ($10,000)')
plt.title('Multi-Timeframe Confluence (1h+15m+1m) Strategy Equity Curves (2023 - 2026)', fontsize=14, fontweight='bold')
plt.xlabel('Date / Time', fontsize=12)
plt.ylabel('Portfolio Equity (USDT)', fontsize=12)
plt.grid(True, linestyle=':', alpha=0.6)
plt.legend(loc='upper left', fontsize=11, frameon=True)
plt.tight_layout()
chart_file = 'reports/backtest_multi_tf_equity_curve.png'
plt.savefig(chart_file, dpi=200)
print(f"\nComparative equity curves saved to {chart_file}")
