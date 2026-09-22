import os
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import datetime

os.makedirs('reports', exist_ok=True)

kline_files = glob.glob('scratch/klines_1m/*.parquet')
file_meta = []
for f in kline_files:
    basename = os.path.basename(f)
    parts = basename.replace('.parquet', '').split('_')
    sym = parts[0]
    t_start = int(parts[2])
    t_end = int(parts[3])
    file_meta.append({'file': f, 'symbol': sym, 'start_ms': t_start, 'end_ms': t_end})

file_meta.sort(key=lambda x: x['start_ms'])

def compute_vwap(df, window=60):
    pv = df['close'] * df['vol']
    vwap = pv.rolling(window, min_periods=5).sum() / df['vol'].rolling(window, min_periods=5).sum()
    return vwap.fillna(df['close'])

def run_backtest_engine(strict_exhaustion=True, leverage=3.0, slippage_pct=0.0020, taker_fee_pct=0.0005):
    """
    Backtest Strategy 2 on 1-minute data:
    strict_exhaustion: 
      - True: Enforces true Strategy 2 rules (massive expansion > 35%, blow-off top formed, breaks 60m neckline)
      - False: Naive 1m breakdown (early 8% expansion, breaks 20m low)
    """
    initial_equity = 10000.0
    equity = initial_equity
    equity_curve = [{'timestamp': pd.to_datetime('2023-01-01'), 'equity': initial_equity, 'trade_pnl': 0, 'symbol': 'INIT'}]
    
    trades = []
    
    for item in file_meta:
        df = pd.read_parquet(item['file'])
        if len(df) < 180:
            continue
            
        sym = item['symbol']
        df = df.sort_values('open_time').reset_index(drop=True)
        
        # Technical indicators on 1m
        df['vwap_60'] = compute_vwap(df, 60)
        
        # Funding settlement time check (avoid 30 mins before 4h marks)
        minute_of_day = df['open_time'].dt.hour * 60 + df['open_time'].dt.minute
        mins_to_4h = 240 - (minute_of_day % 240)
        df['mins_to_settle'] = mins_to_4h
        
        in_trade = False
        trade_info = {}
        
        # Scan for entry
        for i in range(120, len(df)):
            row = df.iloc[i]
            cur_time = row['open_time']
            cur_price = row['close']
            
            if not in_trade:
                if strict_exhaustion:
                    # Model B: Strict Exhaustion Squeeze Strategy
                    # 1. Parabolic expansion: 24h rolling high is at least 35% above the baseline
                    past_window = df.iloc[max(0, i-720):i] # last 12 hours
                    base_low = past_window['low'].min()
                    peak_high = past_window['high'].max()
                    expansion_pct = (peak_high / base_low) - 1.0
                    
                    # 2. Peak has already formed (peak is at least 30 mins ago, not making new high right now)
                    peak_bar_idx = past_window['high'].idxmax()
                    bars_since_peak = i - peak_bar_idx
                    
                    # 3. Right-side structural neckline break: breaks below rolling 45m low
                    swing_low_45 = df['low'].iloc[i-45:i].min()
                    is_breakdown = (cur_price < swing_low_45) and (cur_price < row['vwap_60'])
                    
                    # 4. Current price has pulled back between 5% and 25% from peak (entering the right-side collapse zone)
                    drawdown_from_peak = (peak_high - cur_price) / peak_high
                    
                    timing_ok = row['mins_to_settle'] > 30
                    
                    signal = (expansion_pct >= 0.35) and (bars_since_peak >= 20) and (0.05 <= drawdown_from_peak <= 0.28) and is_breakdown and timing_ok
                    swing_high_ref = peak_high
                else:
                    # Model A: Naive 1m breakdown
                    swing_high = df['high'].iloc[i-120:i].max()
                    swing_low = df['low'].iloc[i-20:i].min()
                    past_low = df['low'].iloc[max(0, i-120):i-20].min()
                    
                    is_parabolic = (swing_high / past_low) >= 1.08
                    is_breakdown = (cur_price < swing_low) and (cur_price < row['vwap_60'])
                    timing_ok = row['mins_to_settle'] > 30
                    signal = is_parabolic and is_breakdown and timing_ok
                    swing_high_ref = swing_high
                    
                if signal:
                    fill_price = cur_price * (1.0 - slippage_pct)
                    hard_sl = swing_high_ref * 1.02 # 2% above peak
                    
                    sl_dist = (hard_sl / fill_price) - 1.0
                    if sl_dist > 0.30:
                        hard_sl = fill_price * 1.25
                    if sl_dist < 0.02:
                        hard_sl = fill_price * 1.03
                        
                    margin = equity * 0.10 # 10% equity
                    notional = margin * leverage
                    coins = notional / fill_price
                    entry_fee = notional * taker_fee_pct
                    
                    in_trade = True
                    trade_info = {
                        'symbol': sym,
                        'entry_time': cur_time,
                        'entry_idx': i,
                        'entry_price': fill_price,
                        'hard_sl': hard_sl,
                        'orig_sl': hard_sl,
                        'swing_high': swing_high_ref,
                        'margin': margin,
                        'notional': notional,
                        'coins': coins,
                        'coins_remaining': coins,
                        'fees_paid': entry_fee,
                        'realized_pnl': 0.0,
                        'tp1_hit': False,
                        'tp2_hit': False,
                    }
            else:
                # Trade management
                # Check Stop Loss
                if row['high'] >= trade_info['hard_sl']:
                    exit_price = trade_info['hard_sl'] * (1.0 + slippage_pct)
                    exit_coins = trade_info['coins_remaining']
                    pnl = exit_coins * (trade_info['entry_price'] - exit_price)
                    exit_fee = (exit_coins * exit_price) * taker_fee_pct
                    trade_info['realized_pnl'] += (pnl - exit_fee)
                    trade_info['fees_paid'] += exit_fee
                    trade_info['exit_time'] = cur_time
                    trade_info['exit_price'] = exit_price
                    trade_info['exit_reason'] = 'STOP_LOSS' if not trade_info['tp1_hit'] else 'BREAK_EVEN'
                    in_trade = False
                    
                    equity += trade_info['realized_pnl']
                    equity_curve.append({
                        'timestamp': cur_time,
                        'equity': equity,
                        'trade_pnl': trade_info['realized_pnl'],
                        'symbol': sym
                    })
                    trades.append(trade_info)
                    break
                    
                # Check TP 1 (-15%)
                tp1_target = trade_info['entry_price'] * 0.85
                if (not trade_info['tp1_hit']) and (row['low'] <= tp1_target):
                    exit_price = tp1_target * (1.0 + slippage_pct)
                    close_coins = trade_info['coins'] * 0.35
                    pnl = close_coins * (trade_info['entry_price'] - exit_price)
                    fee = (close_coins * exit_price) * taker_fee_pct
                    trade_info['realized_pnl'] += (pnl - fee)
                    trade_info['fees_paid'] += fee
                    trade_info['coins_remaining'] -= close_coins
                    trade_info['tp1_hit'] = True
                    trade_info['hard_sl'] = trade_info['entry_price'] # Move to BE
                    
                # Check TP 2 (-35%)
                tp2_target = trade_info['entry_price'] * 0.65
                if (not trade_info['tp2_hit']) and (row['low'] <= tp2_target):
                    exit_price = tp2_target * (1.0 + slippage_pct)
                    close_coins = trade_info['coins'] * 0.40
                    pnl = close_coins * (trade_info['entry_price'] - exit_price)
                    fee = (close_coins * exit_price) * taker_fee_pct
                    trade_info['realized_pnl'] += (pnl - fee)
                    trade_info['fees_paid'] += fee
                    trade_info['coins_remaining'] -= close_coins
                    trade_info['tp2_hit'] = True
                    
                # Final exit (held 24 hours or end of data)
                held_bars = i - trade_info['entry_idx']
                if held_bars >= 1440 or i == len(df) - 1:
                    exit_price = cur_price * (1.0 + slippage_pct)
                    exit_coins = trade_info['coins_remaining']
                    pnl = exit_coins * (trade_info['entry_price'] - exit_price)
                    fee = (exit_coins * exit_price) * taker_fee_pct
                    trade_info['realized_pnl'] += (pnl - fee)
                    trade_info['fees_paid'] += fee
                    trade_info['exit_time'] = cur_time
                    trade_info['exit_price'] = exit_price
                    trade_info['exit_reason'] = 'TIME_EXIT' if trade_info['tp1_hit'] else 'FINAL_BAR'
                    in_trade = False
                    
                    equity += trade_info['realized_pnl']
                    equity_curve.append({
                        'timestamp': cur_time,
                        'equity': equity,
                        'trade_pnl': trade_info['realized_pnl'],
                        'symbol': sym
                    })
                    trades.append(trade_info)
                    break
                    
    return pd.DataFrame(trades), pd.DataFrame(equity_curve)

print("Running Strict Exhaustion Strategy (Model B) with 3x leverage...")
tr_strict_3x, cu_strict_3x = run_backtest_engine(strict_exhaustion=True, leverage=3.0)

print("Running Strict Exhaustion Strategy (Model B) with 5x leverage...")
tr_strict_5x, cu_strict_5x = run_backtest_engine(strict_exhaustion=True, leverage=5.0)

def print_summary(df_tr, df_cu, name):
    n = len(df_tr)
    if n == 0:
        print(f"[{name}] 0 trades triggered.")
        return {}
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
    
    print(f"\n[{name}] Total Trades: {n} | Win Rate: {win_rate:.1f}% | Profit Factor: {pf:.2f} | Final Equity: ${final_eq:,.2f} ({ret_pct:+.1f}%) | Max DD: {max_dd:.2f}%")
    print(f"Total Volume: ${tot_vol:,.2f} | Avg Volume/Trade: ${avg_vol:,.2f} | Fees Paid: ${tot_fees:,.2f}")
    return {
        'Model': name,
        'Trades': n,
        'Win Rate': f"{win_rate:.1f}%",
        'Profit Factor': f"{pf:.2f}",
        'Final Equity': f"${final_eq:,.2f}",
        'Return (%)': f"{ret_pct:+.1f}%",
        'Max Drawdown': f"{max_dd:.2f}%",
        'Total Volume': f"${tot_vol:,.2f}",
        'Avg Volume': f"${avg_vol:,.2f}",
        'Total Fees': f"${tot_fees:,.2f}"
    }

m_s3 = print_summary(tr_strict_3x, cu_strict_3x, "Strict Strategy 2 (3x Leverage)")
m_s5 = print_summary(tr_strict_5x, cu_strict_5x, "Strict Strategy 2 (5x Leverage)")

# Print trades detail for Strict Strategy 2 (3x)
if len(tr_strict_3x) > 0:
    out_cols = ['symbol', 'entry_time', 'exit_time', 'entry_price', 'exit_price', 'notional', 'margin', 'realized_pnl', 'fees_paid', 'exit_reason']
    tr_display = tr_strict_3x[out_cols].copy()
    tr_display['pnl_pct'] = (tr_display['realized_pnl'] / tr_display['margin']) * 100
    tr_display.to_csv('reports/backtest_1m_strict_trades_3x.csv', index=False)
    print("\nStrict Strategy 2 (3x) Detailed Trade Log:")
    print(tr_display[['symbol', 'entry_time', 'entry_price', 'exit_price', 'notional', 'realized_pnl', 'pnl_pct', 'exit_reason']].to_string(index=False))

# Plot Comparative Equity Curve
plt.figure(figsize=(12, 6))
plt.plot(cu_strict_3x['timestamp'], cu_strict_3x['equity'], label=f"Strict 3x Leverage (Final: ${cu_strict_3x['equity'].iloc[-1]:,.0f}, Ret: {m_s3['Return (%)']})", color='#1b7837', linewidth=2.5)
plt.plot(cu_strict_5x['timestamp'], cu_strict_5x['equity'], label=f"Strict 5x Leverage (Final: ${cu_strict_5x['equity'].iloc[-1]:,.0f}, Ret: {m_s5['Return (%)']})", color='#762a83', linewidth=2.5)
plt.axhline(10000, color='gray', linestyle='--', alpha=0.7, label='Initial Capital ($10,000)')
plt.title('1-Minute Terminal Squeeze Strategy (Strict Model B) Equity Curve (2023 - 2026)', fontsize=14, fontweight='bold')
plt.xlabel('Date / Time', fontsize=12)
plt.ylabel('Portfolio Equity (USDT)', fontsize=12)
plt.grid(True, linestyle=':', alpha=0.6)
plt.legend(loc='upper left', fontsize=11, frameon=True)
plt.tight_layout()
chart_file = 'reports/backtest_1m_strict_equity_curve.png'
plt.savefig(chart_file, dpi=200)
print(f"\nEquity curve chart saved to {chart_file}")
