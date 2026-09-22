import os
import glob
import shutil
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import datetime

os.makedirs('reports', exist_ok=True)
artifact_dir = r"C:\Users\liuqi\.gemini\antigravity\brain\6179de5d-d34e-4593-916a-d372e623989f"

def get_episodes():
    files_1m = glob.glob('scratch/klines_1m/*.parquet')
    episodes = []
    for f1m in files_1m:
        basename = os.path.basename(f1m)
        f15m = os.path.join('scratch/klines_15m', basename)
        f1h = os.path.join('scratch/klines_1h', basename)
        if os.path.exists(f15m) and os.path.exists(f1h):
            b = basename.replace('.parquet', '')
            parts = b.split('_')
            ms_cands = [int(p) for p in parts if p.isdigit() and len(p) >= 12]
            start_ms = ms_cands[0] if ms_cands else 0
            sym = parts[0]
            episodes.append({
                'symbol': sym,
                'start_ms': start_ms,
                'f_1m': f1m,
                'f_15m': f15m,
                'f_1h': f1h
            })
    episodes.sort(key=lambda x: x['start_ms'])
    return episodes

def compute_vwap(df, window=20):
    pv = df['close'] * df['vol']
    vwap = pv.rolling(window, min_periods=3).sum() / df['vol'].rolling(window, min_periods=3).sum()
    return vwap.fillna(df['close'])

def extract_all_signals(episodes, mode='MAKER', slippage_pct=0.0020, expansion_thr=1.15):
    taker_fee = 0.0005 # 0.05%
    maker_fee = 0.0002 # 0.02%
    fee_rate = taker_fee if mode == 'TAKER' else maker_fee
    slip = slippage_pct if mode == 'TAKER' else 0.0
    
    signals = []
    
    for ep in episodes:
        try:
            df_15m = pd.read_parquet(ep['f_15m']).sort_values('open_time').reset_index(drop=True)
            df_1m = pd.read_parquet(ep['f_1m']).sort_values('open_time').reset_index(drop=True)
        except Exception:
            continue
            
        if len(df_15m) < 20 or len(df_1m) < 60:
            continue
            
        sym = ep['symbol']
        
        # 1. Macro 15m Squeeze & Reversal Check
        peak_idx = df_15m['high'].idxmax()
        peak_high = df_15m.loc[peak_idx, 'high']
        
        # Expansion check (at least 15% pump before peak)
        base_low = df_15m['low'].iloc[max(0, peak_idx-48):peak_idx].min()
        if (peak_high / base_low) < expansion_thr:
            continue
            
        post_peak_15m = df_15m.iloc[peak_idx:].copy().reset_index(drop=True)
        if len(post_peak_15m) < 4:
            continue
            
        # Detect swing low (neckline) within 14 bars of peak
        neck_idx = post_peak_15m['low'].iloc[1:min(14, len(post_peak_15m))].idxmin()
        neck_low = post_peak_15m.loc[neck_idx, 'low']
        
        # 15m MSS breakdown candle
        breakdown_15m = post_peak_15m.iloc[neck_idx+1:][post_peak_15m.iloc[neck_idx+1:]['close'] < neck_low]
        if len(breakdown_15m) == 0:
            pv = post_peak_15m['close'] * post_peak_15m['vol']
            post_peak_15m['vwap'] = (pv.rolling(12, min_periods=3).sum() / post_peak_15m['vol'].rolling(12, min_periods=3).sum()).fillna(post_peak_15m['close'])
            breakdown_15m = post_peak_15m.iloc[1:][post_peak_15m.iloc[1:]['close'] < post_peak_15m.iloc[1:]['vwap']]
            if len(breakdown_15m) == 0:
                continue
                
        mss_candle = breakdown_15m.iloc[0]
        mss_close_time = mss_candle['open_time'] + pd.Timedelta(minutes=15)
        
        # 2. 1-Minute Precision Sniper Execution
        df_1m['ema_15'] = df_1m['close'].ewm(span=15).mean()
        
        # Execution window: within 4 hours after 15m breakdown
        exec_window = df_1m[(df_1m['open_time'] >= mss_close_time) & 
                            (df_1m['open_time'] <= mss_close_time + pd.Timedelta(hours=4))].copy()
        if len(exec_window) == 0:
            continue
            
        entry_bar = None
        entry_price = None
        
        for idx, bar in exec_window.iterrows():
            ema = bar['ema_15']
            retest_ok = bar['high'] >= ema * 0.998
            
            if mode == 'TAKER':
                if retest_ok and (bar['close'] < bar['open']):
                    entry_bar = bar
                    entry_price = bar['close'] * (1.0 - slip)
                    break
            elif mode == 'MAKER':
                limit_target = ema
                if bar['high'] >= limit_target and bar['low'] <= limit_target:
                    entry_bar = bar
                    entry_price = limit_target
                    break
                    
        if entry_bar is None:
            if mode == 'TAKER':
                entry_bar = exec_window.iloc[0]
                entry_price = entry_bar['close'] * (1.0 - slip)
            else:
                entry_bar = exec_window.iloc[0]
                entry_price = entry_bar['open']
                
        # 3. Position Sizing & Risk Controls
        hard_sl = peak_high * 1.02
        sl_dist = (hard_sl / entry_price) - 1.0
        if sl_dist > 0.20: hard_sl = entry_price * 1.15 # cap max stop distance at 15%
        if sl_dist < 0.02: hard_sl = entry_price * 1.03
        
        # 4. Simulation on 1m bars
        match_idx = df_1m[df_1m['open_time'] >= entry_bar['open_time']]
        if len(match_idx) == 0:
            continue
        entry_idx_in_1m = match_idx.index[0]
        remaining_1m = df_1m.iloc[entry_idx_in_1m+1:].copy()
        
        tp1_hit = False
        tp2_hit = False
        cur_sl = hard_sl
        exit_time = None
        exit_reason = None
        
        slices = []
        rem_fraction = 1.0
        
        for bar_i, (b_idx, row) in enumerate(remaining_1m.iterrows()):
            cur_time = row['open_time']
            cur_price = row['close']
            
            # Check Stop Loss
            if row['high'] >= cur_sl:
                exit_price = cur_sl * (1.0 + slip)
                slices.append({'frac': rem_fraction, 'exit_price': exit_price, 'fee_rate': fee_rate})
                exit_time = cur_time
                exit_reason = 'STOP_LOSS' if not tp1_hit else 'BREAK_EVEN'
                rem_fraction = 0.0
                break
                
            # Check TP 1 (-10% drop)
            tp1_target = entry_price * 0.90
            if (not tp1_hit) and (row['low'] <= tp1_target):
                exit_price = tp1_target * (1.0 + slip)
                close_frac = 0.35
                slices.append({'frac': close_frac, 'exit_price': exit_price, 'fee_rate': fee_rate})
                rem_fraction -= close_frac
                tp1_hit = True
                cur_sl = entry_price # Move to Break-Even
                
            # Check TP 2 (-25% drop)
            tp2_target = entry_price * 0.75
            if (not tp2_hit) and (row['low'] <= tp2_target):
                exit_price = tp2_target * (1.0 + slip)
                close_frac = 0.40
                slices.append({'frac': close_frac, 'exit_price': exit_price, 'fee_rate': fee_rate})
                rem_fraction -= close_frac
                tp2_hit = True
                
            # Time exit (held 24 hours or end of data)
            if bar_i >= 1440 or bar_i == len(remaining_1m) - 1:
                exit_price = cur_price * (1.0 + slip)
                slices.append({'frac': rem_fraction, 'exit_price': exit_price, 'fee_rate': fee_rate})
                exit_time = cur_time
                exit_reason = 'TIME_EXIT' if tp1_hit else 'FINAL_BAR'
                rem_fraction = 0.0
                break
                
        signals.append({
            'symbol': sym,
            'mode': mode,
            'entry_time': entry_bar['open_time'],
            'entry_price': entry_price,
            'peak_price': peak_high,
            'hard_sl': hard_sl,
            'exit_time': exit_time,
            'exit_reason': exit_reason,
            'slices': slices,
            'entry_fee_rate': fee_rate,
            'tp1_hit': tp1_hit,
            'tp2_hit': tp2_hit
        })
        
    df_sig = pd.DataFrame(signals)
    if len(df_sig) > 0:
        # Deduplicate identical events by symbol and entry_time
        df_sig = df_sig.drop_duplicates(subset=['symbol', 'entry_time']).sort_values('entry_time').reset_index(drop=True)
    return df_sig

def simulate_portfolio_50k(df_signals, leverage=3.0, sizing_pct=0.20, max_concurrent=3, is_fixed_margin=False):
    """
    Simulates portfolio starting at $50,000 USDT with concurrent position and risk limits.
    """
    initial_equity = 50000.0
    equity = initial_equity
    
    active_positions = []
    closed_trades = []
    skipped_count = 0
    
    signals = df_signals.sort_values('entry_time').to_dict('records')
    equity_curve = [{'timestamp': pd.to_datetime('2023-01-01'), 'equity': initial_equity, 'active_count': 0}]
    
    for sig in signals:
        t_entry = sig['entry_time']
        
        # 1. Close any active positions that have exited before or at t_entry
        still_active = []
        for pos in active_positions:
            if pos['exit_time'] <= t_entry:
                equity += pos['realized_pnl']
                pos['equity_after'] = equity
                closed_trades.append(pos)
                equity_curve.append({
                    'timestamp': pos['exit_time'],
                    'equity': equity,
                    'active_count': len(still_active)
                })
            else:
                still_active.append(pos)
        active_positions = still_active
        
        # 2. Check: Avoid duplicate position in the same symbol at the same time
        if any(p['symbol'] == sig['symbol'] for p in active_positions):
            skipped_count += 1
            continue
            
        # 3. Check portfolio concurrent capacity limit
        if len(active_positions) >= max_concurrent:
            skipped_count += 1
            continue
            
        # 4. Calculate position sizing
        if is_fixed_margin:
            margin = 10000.0 # $10,000 fixed
        else:
            margin = equity * sizing_pct
            
        notional = margin * leverage
        entry_price = sig['entry_price']
        coins = notional / entry_price
        entry_fee = notional * sig['entry_fee_rate']
        
        # Compute outcome from slices
        realized_pnl = -entry_fee
        total_fees = entry_fee
        weighted_exit_price = 0.0
        
        for sl in sig['slices']:
            close_coins = coins * sl['frac']
            pnl_gross = close_coins * (entry_price - sl['exit_price']) # Short position
            exit_fee = (close_coins * sl['exit_price']) * sl['fee_rate']
            realized_pnl += (pnl_gross - exit_fee)
            total_fees += exit_fee
            weighted_exit_price += sl['exit_price'] * sl['frac']
            
        pos_record = {
            'symbol': sig['symbol'],
            'mode': sig['mode'],
            'leverage': leverage,
            'entry_time': sig['entry_time'],
            'exit_time': sig['exit_time'],
            'entry_price': entry_price,
            'exit_price': weighted_exit_price,
            'margin': margin,
            'notional': notional,
            'coins': coins,
            'realized_pnl': realized_pnl,
            'pnl_on_margin': (realized_pnl / margin) * 100,
            'fees_paid': total_fees,
            'exit_reason': sig['exit_reason'],
            'tp1_hit': sig['tp1_hit'],
            'tp2_hit': sig['tp2_hit'],
            'equity_before': equity
        }
        
        active_positions.append(pos_record)
        equity_curve.append({
            'timestamp': t_entry,
            'equity': equity,
            'active_count': len(active_positions)
        })
        
    # 5. Close any remaining active positions at end of simulation
    for pos in sorted(active_positions, key=lambda x: x['exit_time']):
        equity += pos['realized_pnl']
        pos['equity_after'] = equity
        closed_trades.append(pos)
        equity_curve.append({
            'timestamp': pos['exit_time'],
            'equity': equity,
            'active_count': 0
        })
        
    df_trades = pd.DataFrame(closed_trades).sort_values('exit_time').reset_index(drop=True)
    df_curve = pd.DataFrame(equity_curve).sort_values('timestamp').reset_index(drop=True)
    
    return df_trades, df_curve, skipped_count

def run_simulation_pipeline():
    episodes = get_episodes()
    print(f"Total synchronized multi-timeframe episodes loaded: {len(episodes)}")
    
    print("\n" + "="*80)
    print("Extracting Squeeze Signals (Maker and Taker)...")
    print("="*80)
    sig_maker = extract_all_signals(episodes, mode='MAKER')
    sig_taker = extract_all_signals(episodes, mode='TAKER')
    print(f"Unique signals extracted: Maker={len(sig_maker)}, Taker={len(sig_taker)}")
    
    print("\n" + "="*80)
    print("Simulating $50,000 All-Satellite Dynamic Compounding Portfolios...")
    print("="*80)

    # 1. Primary Test: 20% Margin, Max 3 Concurrent
    tr_3x_m, cu_3x_m, sk_3x_m = simulate_portfolio_50k(sig_maker, leverage=3.0, sizing_pct=0.20, max_concurrent=3)
    tr_5x_m, cu_5x_m, sk_5x_m = simulate_portfolio_50k(sig_maker, leverage=5.0, sizing_pct=0.20, max_concurrent=3)
    tr_3x_t, cu_3x_t, sk_3x_t = simulate_portfolio_50k(sig_taker, leverage=3.0, sizing_pct=0.20, max_concurrent=3)
    tr_5x_t, cu_5x_t, sk_5x_t = simulate_portfolio_50k(sig_taker, leverage=5.0, sizing_pct=0.20, max_concurrent=3)

    # 2. Alternative Test: 15% Margin, Max 4 Concurrent
    tr_3x_m15, cu_3x_m15, sk_3x_m15 = simulate_portfolio_50k(sig_maker, leverage=3.0, sizing_pct=0.15, max_concurrent=4)
    tr_5x_m15, cu_5x_m15, sk_5x_m15 = simulate_portfolio_50k(sig_maker, leverage=5.0, sizing_pct=0.15, max_concurrent=4)

    # 3. Fixed $10,000 Margin Baseline (Non-compounding)
    tr_3x_fix, cu_3x_fix, _ = simulate_portfolio_50k(sig_maker, leverage=3.0, is_fixed_margin=True)
    tr_5x_fix, cu_5x_fix, _ = simulate_portfolio_50k(sig_maker, leverage=5.0, is_fixed_margin=True)

    def evaluate_metrics(df_tr, df_cu, name, initial_eq=50000.0):
        n = len(df_tr)
        if n == 0:
            return {'Model': name, 'Trades': 0, 'Win Rate': 'N/A', 'Profit Factor': 'N/A', 'Final Equity': f"${initial_eq:,.2f}", 'Return': '0.0%', 'Max DD': '0.0%'}
        wins = df_tr[df_tr['realized_pnl'] > 0]
        losses = df_tr[df_tr['realized_pnl'] < 0]
        win_rate = len(wins) / n * 100
        tot_p = wins['realized_pnl'].sum() if len(wins) > 0 else 0
        tot_l = abs(losses['realized_pnl'].sum()) if len(losses) > 0 else 1
        pf = tot_p / tot_l if tot_l > 0 else np.nan
        final_eq = df_cu['equity'].iloc[-1]
        net_profit = final_eq - initial_eq
        ret_pct = (final_eq / initial_eq - 1.0) * 100
        
        cummax = df_cu['equity'].cummax()
        dd = (df_cu['equity'] - cummax) / cummax * 100
        max_dd = abs(dd.min())
        
        tot_vol = df_tr['notional'].sum()
        avg_vol = df_tr['notional'].mean()
        tot_fees = df_tr['fees_paid'].sum()
        
        return {
            'Model (模式)': name,
            'Trades (交易数)': n,
            'Win Rate (胜率)': f"{win_rate:.1f}%",
            'Profit Factor (盈亏比)': f"{pf:.2f}",
            'Initial ($)': f"${initial_eq:,.0f}",
            'Final Equity ($)': f"${final_eq:,.2f}",
            'Net Profit ($)': f"${net_profit:+,.2f}",
            'Return (%)': f"{ret_pct:+.1f}%",
            'Max DD (%)': f"{max_dd:.2f}%",
            'Total Vol ($)': f"${tot_vol:,.0f}",
            'Total Fees ($)': f"${tot_fees:,.2f}"
        }

    metrics = [
        evaluate_metrics(tr_3x_m, cu_3x_m, "50k Satellite 3x Maker (20% pos)"),
        evaluate_metrics(tr_5x_m, cu_5x_m, "50k Satellite 5x Maker (20% pos)"),
        evaluate_metrics(tr_3x_t, cu_3x_t, "50k Satellite 3x Taker (20% pos)"),
        evaluate_metrics(tr_5x_t, cu_5x_t, "50k Satellite 5x Taker (20% pos)"),
        evaluate_metrics(tr_3x_m15, cu_3x_m15, "50k Satellite 3x Maker (15% pos)"),
        evaluate_metrics(tr_5x_m15, cu_5x_m15, "50k Satellite 5x Maker (15% pos)"),
        evaluate_metrics(tr_3x_fix, cu_3x_fix, "50k Baseline 3x Fixed $10k"),
        evaluate_metrics(tr_5x_fix, cu_5x_fix, "50k Baseline 5x Fixed $10k")
    ]

    df_perf = pd.DataFrame(metrics)
    print("\n" + "="*80)
    print("=== $50,000 USDT ALL-SATELLITE COMPREHENSIVE PERFORMANCE MATRIX ===")
    print("="*80)
    print(df_perf.to_string(index=False))

    # Export trade logs
    tr_3x_m.to_csv('reports/backtest_satellite_50k_trades_3x_maker.csv', index=False)
    tr_5x_m.to_csv('reports/backtest_satellite_50k_trades_5x_maker.csv', index=False)
    tr_3x_t.to_csv('reports/backtest_satellite_50k_trades_3x_taker.csv', index=False)
    tr_5x_t.to_csv('reports/backtest_satellite_50k_trades_5x_taker.csv', index=False)
    print("\nExported trade logs to reports/backtest_satellite_50k_trades_*.csv")

    # Plot High-Resolution Visual Equity Curves
    plt.figure(figsize=(14, 8))

    plt.plot(cu_3x_t['timestamp'], cu_3x_t['equity'], label=f"3x Taker (Ret: {metrics[2]['Return (%)']}, DD: {metrics[2]['Max DD (%)']}, Final: {metrics[2]['Final Equity ($)']})", color='#2b5c8f', linewidth=2.0, linestyle='--')
    plt.plot(cu_5x_t['timestamp'], cu_5x_t['equity'], label=f"5x Taker (Ret: {metrics[3]['Return (%)']}, DD: {metrics[3]['Max DD (%)']}, Final: {metrics[3]['Final Equity ($)']})", color='#d95f02', linewidth=2.0, linestyle='--')
    plt.plot(cu_3x_m['timestamp'], cu_3x_m['equity'], label=f"3x Maker (Ret: {metrics[0]['Return (%)']}, DD: {metrics[0]['Max DD (%)']}, Final: {metrics[0]['Final Equity ($)']})", color='#1b7837', linewidth=2.8)
    plt.plot(cu_5x_m['timestamp'], cu_5x_m['equity'], label=f"5x Maker (Ret: {metrics[1]['Return (%)']}, DD: {metrics[1]['Max DD (%)']}, Final: {metrics[1]['Final Equity ($)']})", color='#7570b3', linewidth=3.0)
    plt.plot(cu_5x_fix['timestamp'], cu_5x_fix['equity'], label=f"5x Fixed 10k USDT (No Compound, Final: {metrics[7]['Final Equity ($)']})", color='#999999', linewidth=1.5, linestyle=':')

    plt.axhline(50000, color='#666666', linestyle=':', label='Starting Capital: $50,000 USDT')
    plt.title('$50,000 USDT All-Satellite Tactical Squeeze Strategy Equity Curves (2023 - 2026)', fontsize=15, fontweight='bold')
    plt.xlabel('Execution Timeline (2023 - 2026)', fontsize=12)
    plt.ylabel('Portfolio Total Equity (USDT)', fontsize=12)
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(loc='upper left', fontsize=11, frameon=True)
    plt.tight_layout()

    chart_path = 'reports/backtest_satellite_50k_equity_curve.png'
    plt.savefig(chart_path, dpi=250)
    print(f"Saved equity curve to {chart_path}")

    # Also copy to artifact directory
    artifact_chart = os.path.join(artifact_dir, 'backtest_satellite_50k_equity_curve.png')
    shutil.copyfile(chart_path, artifact_chart)
    print(f"Copied chart to artifact directory: {artifact_chart}")

    print("\nSample Trades from 5x Maker ($50,000 Portfolio):")
    cols_show = ['symbol', 'entry_time', 'exit_time', 'entry_price', 'exit_price', 'margin', 'realized_pnl', 'pnl_on_margin', 'exit_reason']
    print(tr_5x_m[cols_show].head(12).to_string(index=False))

if __name__ == '__main__':
    run_simulation_pipeline()
