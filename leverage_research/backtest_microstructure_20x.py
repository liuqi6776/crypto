"""
Backtest Microstructure 20X Perpetual Strategy
==============================================
Simulates high-leverage (20X) execution on 120,000 Out-of-Sample 1m bars:
1. Two-Stage Gate: Volatility Expansion + Microstructure OFI Directional Conviction
2. Realistic High-Frequency Execution:
   - Entry: Maker Post-Only Limit (0.02% fee)
   - TP Exit: Maker Limit (0.02% fee)
   - SL Exit: Taker Stop-Market (0.05% fee + 1 bps slippage)
   - Timeout Exit: Taker Market (0.05% fee + 1 bps slippage)
3. Strict 20X Isolated Margin & Liquidation Buffer (1.2% hard stop vs 4.25% liq line)
4. Academic Risk Metrics & Multi-Panel Visualization
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def run_microstructure_20x_simulation(
    pred_path: str,
    initial_capital: float = 10000.0,
    margin_per_trade: float = 1000.0, # 10% of portfolio as isolated margin
    leverage: float = 20.0,
    conviction_pct: float = 0.90,     # Top 10% high-conviction signals
    maker_fee: float = 0.0002,        # 0.02% maker fee
    taker_fee: float = 0.0005,        # 0.05% taker fee
    slippage: float = 0.0001,         # 1 bps slippage for taker exits
    mmr: float = 0.005                # 0.5% maintenance margin rate
):
    print("=" * 75)
    print("  Realistic 20X Microstructure & Triple Barrier Execution Backtest")
    print("=" * 75)

    print(f"\n[1/4] Loading out-of-sample prediction dataset...")
    df = pd.read_parquet(pred_path)
    n = len(df)
    print(f"  Loaded {n:,} out-of-sample bars ({df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]})")

    # Determine conviction thresholds
    long_thresh = df['pred_prob_long'].quantile(conviction_pct)
    short_thresh = df['pred_prob_short'].quantile(conviction_pct)
    print(f"  Signal Thresholds (Top {int((1-conviction_pct)*100)}% Conviction):")
    print(f"    Long Threshold:  P >= {long_thresh:.4f}")
    print(f"    Short Threshold: P >= {short_thresh:.4f}")

    # Vectors
    dt_arr = pd.to_datetime(df['datetime']).values
    close_arr = df['close'].values
    prob_long = df['pred_prob_long'].values
    prob_short = df['pred_prob_short'].values
    vol_gate = df['vol_gate'].values
    
    tb_long_label = df['tb_long_label'].values
    tb_long_bars = df['tb_long_touch_bars'].values
    tb_long_ret = df['tb_long_exit_ret'].values
    
    tb_short_label = df['tb_short_label'].values
    tb_short_bars = df['tb_short_touch_bars'].values
    tb_short_ret = df['tb_short_exit_ret'].values

    # Simulation State
    capital = initial_capital
    nav_history = []
    trades = []
    
    in_pos = False
    pos_dir = 0 # 1 for Long, -1 for Short
    pos_entry_bar = 0
    pos_exit_bar = 0
    pos_margin = margin_per_trade
    pos_notional = pos_margin * leverage

    liquidations = 0

    print("\n[2/4] Stepping through high-frequency execution...")
    
    i = 0
    while i < n:
        # If currently in position, fast-forward to exit bar
        if in_pos:
            if i < pos_exit_bar:
                nav_history.append((dt_arr[i], capital))
                i += 1
                continue
            else:
                # Position exits at bar pos_exit_bar
                in_pos = False

        # Evaluate entry signal if flat
        long_sig = (prob_long[i] >= long_thresh) and vol_gate[i]
        short_sig = (prob_short[i] >= short_thresh) and vol_gate[i]

        if long_sig and not short_sig:
            # Open Long
            in_pos = True
            pos_dir = 1
            pos_entry_bar = i
            hold_bars = tb_long_bars[i]
            pos_exit_bar = min(i + hold_bars, n - 1)
            raw_ret = tb_long_ret[i]
            outcome = tb_long_label[i]
            
            # Check liquidation (-4.25% adverse move)
            if raw_ret <= -(1.0 / leverage - mmr):
                liquidations += 1
                net_pnl = -pos_margin # Wiped
                exit_type = "LIQUIDATION"
            else:
                # Calculate fees: Maker entry (0.02%), Maker TP (0.02%) or Taker SL/Timeout (0.05% + slippage)
                entry_fee = pos_notional * maker_fee
                if outcome == 1:
                    exit_fee = pos_notional * maker_fee
                    exit_type = "TAKE_PROFIT"
                    trade_slippage = 0.0
                elif outcome == -1:
                    exit_fee = pos_notional * taker_fee
                    exit_type = "STOP_LOSS"
                    trade_slippage = pos_notional * slippage
                else:
                    exit_fee = pos_notional * taker_fee
                    exit_type = "TIMEOUT"
                    trade_slippage = pos_notional * slippage
                
                gross_pnl = pos_notional * raw_ret
                net_pnl = gross_pnl - entry_fee - exit_fee - trade_slippage

            capital += net_pnl
            trades.append({
                'entry_time': dt_arr[i],
                'exit_time': dt_arr[pos_exit_bar],
                'direction': 'LONG',
                'raw_ret_pct': raw_ret * 100.0,
                'net_roe_pct': (net_pnl / pos_margin) * 100.0,
                'net_pnl': net_pnl,
                'exit_type': exit_type,
                'holding_bars': hold_bars,
                'capital_after': capital
            })

        elif short_sig and not long_sig:
            # Open Short
            in_pos = True
            pos_dir = -1
            pos_entry_bar = i
            hold_bars = tb_short_bars[i]
            pos_exit_bar = min(i + hold_bars, n - 1)
            raw_ret = tb_short_ret[i]
            outcome = tb_short_label[i]

            if raw_ret <= -(1.0 / leverage - mmr):
                liquidations += 1
                net_pnl = -pos_margin
                exit_type = "LIQUIDATION"
            else:
                entry_fee = pos_notional * maker_fee
                if outcome == 1:
                    exit_fee = pos_notional * maker_fee
                    exit_type = "TAKE_PROFIT"
                    trade_slippage = 0.0
                elif outcome == -1:
                    exit_fee = pos_notional * taker_fee
                    exit_type = "STOP_LOSS"
                    trade_slippage = pos_notional * slippage
                else:
                    exit_fee = pos_notional * taker_fee
                    exit_type = "TIMEOUT"
                    trade_slippage = pos_notional * slippage

                gross_pnl = pos_notional * raw_ret
                net_pnl = gross_pnl - entry_fee - exit_fee - trade_slippage

            capital += net_pnl
            trades.append({
                'entry_time': dt_arr[i],
                'exit_time': dt_arr[pos_exit_bar],
                'direction': 'SHORT',
                'raw_ret_pct': raw_ret * 100.0,
                'net_roe_pct': (net_pnl / pos_margin) * 100.0,
                'net_pnl': net_pnl,
                'exit_type': exit_type,
                'holding_bars': hold_bars,
                'capital_after': capital
            })

        nav_history.append((dt_arr[i], capital))
        i += 1

    # Convert to DataFrame
    df_nav = pd.DataFrame(nav_history, columns=['datetime', 'nav']).set_index('datetime')
    df_trades = pd.DataFrame(trades)

    print(f"\n[3/4] Performance Analytics & Academic Risk Matrix...")
    total_trades = len(df_trades)
    print(f"  Total Trades: {total_trades:,}")
    
    if total_trades > 0:
        win_trades = df_trades[df_trades['net_pnl'] > 0]
        loss_trades = df_trades[df_trades['net_pnl'] <= 0]
        win_rate = len(win_trades) / total_trades
        gross_profit = win_trades['net_pnl'].sum()
        gross_loss = abs(loss_trades['net_pnl'].sum()) if len(loss_trades) > 0 else 1.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999.0
        mean_roe = df_trades['net_roe_pct'].mean()
        
        print(f"  Win Rate:       {win_rate*100:.2f}%")
        print(f"  Profit Factor:  {profit_factor:.2f}")
        print(f"  Mean Net ROE:   {mean_roe:+.2f}% per trade")
        print(f"  Liquidations:   {liquidations} (Strict Zero Survival Target)")
        print(f"\n  Exit Breakdown:")
        print(df_trades['exit_type'].value_counts().to_string())

    # Academic Performance Matrix
    days = (df_nav.index[-1] - df_nav.index[0]).total_seconds() / 86400.0
    total_ret = (capital - initial_capital) / initial_capital
    cagr = ((1.0 + total_ret) ** (365.25 / days)) - 1.0 if (1.0 + total_ret) > 0 else -1.0
    
    cummax = df_nav['nav'].cummax()
    drawdowns = (df_nav['nav'] - cummax) / cummax
    max_dd = abs(drawdowns.min())
    calmar = cagr / max_dd if max_dd > 0 else 0.0

    # Resample daily returns for Sharpe & Ulcer
    daily_nav = df_nav['nav'].resample('1D').last().dropna()
    daily_rets = daily_nav.pct_change().dropna()
    sharpe = (daily_rets.mean() / daily_rets.std()) * np.sqrt(365) if daily_rets.std() > 0 else 0.0
    
    # Ulcer Index
    daily_cummax = daily_nav.cummax()
    daily_dd = (daily_nav - daily_cummax) / daily_cummax
    ulcer_index = np.sqrt((daily_dd ** 2).mean()) * 100.0

    # ETH Buy & Hold Benchmark for identical period
    eth_bnh_ret = (close_arr[-1] - close_arr[0]) / close_arr[0]
    eth_bnh_cagr = ((1.0 + eth_bnh_ret) ** (365.25 / days)) - 1.0

    print("\n" + "=" * 80)
    print("              ACADEMIC PERFORMANCE SUMMARY (OUT-OF-SAMPLE)")
    print("=" * 80)
    print(f"  Initial Capital:        ${initial_capital:,.2f}")
    print(f"  Ending Capital:         ${capital:,.2f}")
    print(f"  Total Return:           {total_ret*100:+.2f}% (over {days:.1f} days)")
    print(f"  Annualized Return CAGR: {cagr*100:+.2f}%")
    print(f"  Max Drawdown (MaxDD):   {max_dd*100:.2f}%")
    print(f"  Calmar Ratio:           {calmar:.2f}")
    print(f"  Sharpe Ratio:           {sharpe:.2f}")
    print(f"  Ulcer Index:            {ulcer_index:.2f}")
    print(f"  ETH Buy & Hold Return:  {eth_bnh_ret*100:+.2f}% (CAGR: {eth_bnh_cagr*100:+.2f}%)")

    # Save summary table
    summary_df = pd.DataFrame([{
        'Model': 'Microstructure 20X GBDT (OFI + TB)',
        'Initial': initial_capital,
        'Ending': capital,
        'Total_Return': f"{total_ret*100:+.2f}%",
        'CAGR': f"{cagr*100:+.2f}%",
        'MaxDD': f"{max_dd*100:.2f}%",
        'Sharpe': f"{sharpe:.2f}",
        'Calmar': f"{calmar:.2f}",
        'Ulcer_Index': f"{ulcer_index:.2f}",
        'Win_Rate': f"{win_rate*100:.2f}%" if total_trades > 0 else "N/A",
        'Profit_Factor': f"{profit_factor:.2f}" if total_trades > 0 else "N/A",
        'Liquidations': liquidations
    }])
    summary_csv = r"d:\Convertible_Bond_data\crypto_data\microstructure_20x_summary.csv"
    summary_df.to_csv(summary_csv, index=False)
    print(f"\n[Saved] Matrix Summary -> {summary_csv}")

    # [4/4] Multi-Panel Visualization
    print("\n[4/4] Rendering performance visualization panels...")
    plt.style.use('dark_background')
    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=False, gridspec_kw={'height_ratios': [2.2, 1.2, 1.4]})

    # Panel 1: Strategy NAV vs ETH Price
    ax1 = axes[0]
    ax1.plot(df_nav.index, df_nav['nav'], label='Microstructure 20X GBDT (OFI + Triple Barrier)', color='#00e5ff', linewidth=1.8)
    ax1.set_ylabel('Portfolio NAV ($)', color='#00e5ff', fontsize=11, fontweight='bold')
    ax1.set_title('Out-of-Sample High-Leverage (20X) Microstructure Strategy Performance', fontsize=13, fontweight='bold', pad=10)
    ax1.grid(True, linestyle='--', alpha=0.3)
    ax1.legend(loc='upper left', frameon=True)

    ax1_twin = ax1.twinx()
    eth_series = pd.Series(close_arr, index=pd.to_datetime(df['datetime'])).reindex(df_nav.index).ffill()
    ax1_twin.plot(df_nav.index, eth_series, label='ETH Price ($)', color='#ff9100', linewidth=1.0, alpha=0.5, linestyle=':')
    ax1_twin.set_ylabel('ETH Price ($)', color='#ff9100', fontsize=11)
    ax1_twin.legend(loc='upper right', frameon=True)

    # Panel 2: Rolling Drawdown
    ax2 = axes[1]
    ax2.plot(df_nav.index, drawdowns * 100.0, color='#ff1744', linewidth=1.2, label='Drawdown (%)')
    ax2.fill_between(df_nav.index, drawdowns * 100.0, 0, color='#ff1744', alpha=0.25)
    ax2.set_ylabel('Drawdown (%)', color='#ff1744', fontsize=11, fontweight='bold')
    ax2.grid(True, linestyle='--', alpha=0.3)
    ax2.legend(loc='lower left', frameon=True)

    # Panel 3: Trade ROE Distribution
    ax3 = axes[2]
    if len(df_trades) > 0:
        colors = ['#00e676' if r > 0 else '#ff1744' for r in df_trades['net_roe_pct']]
        ax3.bar(range(len(df_trades)), df_trades['net_roe_pct'], color=colors, width=0.8, alpha=0.85)
        ax3.axhline(0, color='white', linestyle='--', alpha=0.4)
        ax3.set_ylabel('Net Trade ROE (%)', fontsize=11, fontweight='bold')
        ax3.set_xlabel('Trade Sequence (Out-of-Sample)', fontsize=11, fontweight='bold')
        ax3.set_title(f"Individual Trade ROE (Win Rate: {win_rate*100:.1f}%, Profit Factor: {profit_factor:.2f})", fontsize=11)
        ax3.grid(True, linestyle='--', alpha=0.3)

    plt.tight_layout()
    chart_path = r"d:\Convertible_Bond_data\microstructure_20x_performance.png"
    plt.savefig(chart_path, dpi=200)
    plt.close()
    print(f"[Saved] Visualization Chart -> {chart_path}")

    return df_nav, df_trades, summary_df

if __name__ == '__main__':
    pred_path = r"d:\Convertible_Bond_data\crypto_data\eth_microstructure_oos_predictions.parquet"
    run_microstructure_20x_simulation(
        pred_path=pred_path,
        initial_capital=10000.0,
        margin_per_trade=1000.0,
        leverage=20.0,
        conviction_pct=0.90, # Top 10%
        maker_fee=0.0002,
        taker_fee=0.0005,
        slippage=0.0001
    )
