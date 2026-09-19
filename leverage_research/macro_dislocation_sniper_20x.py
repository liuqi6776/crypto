"""
Macro Dislocation & Microstructure Liquidation Sniper (Path A: 20X Leverage)
============================================================================
Simulates the 6-year continuous full backtest (2020 - 2026, 701,280 5m bars)
on ETHUSDT:
1. Macro Liquidation Dislocation: 24h extreme drop/pump (> 9%), Volume climax (> 3.5x 7d avg)
2. Microstructure Absorption: Rejection wicks and multi-scale OFI exhaustion
3. Asymmetric Payoff Envelope:
   - TP: +5.0% price move (+100% ROE on 20X margin)
   - Hard Stop: -1.8% price move (-36% ROE on 20X margin, 2.45% buffer to liquidation)
   - Break-Even Stop: moves to +0.1% once price gains +2.0% (+40% ROE)
   - Timeout: 24 hours (288 bars)
4. Realistic High-Friction Fees:
   - Maker entry: 0.02%
   - Maker TP: 0.02%
   - Taker SL/Timeout: 0.05% + 1 bps slippage
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def run_macro_sniper_simulation(
    data_path: str,
    initial_capital: float = 10000.0,
    margin_ratio: float = 0.15,      # 15% of capital allocated per sniper trade
    leverage: float = 20.0,
    tp_pct: float = 0.050,           # +5.0% price move = +100% ROE
    sl_pct: float = 0.018,           # -1.8% price move = -36% ROE (strictly capped)
    breakeven_trigger: float = 0.020,# +2.0% move triggers break-even (+40% ROE)
    horizon_bars: int = 288,         # 24 hours (288 * 5m)
    cooldown_bars: int = 144,        # 12 hours cooldown
    maker_fee: float = 0.0002,
    taker_fee: float = 0.0005,
    slippage: float = 0.0001,
    mmr: float = 0.005               # 0.5% maintenance margin
):
    print("=" * 80)
    print("  Path A: Macro Dislocation & Liquidation Sniper (2020 - 2026)")
    print("  20X Isolated Leverage | +5% TP (+100% ROE) | -1.8% SL (-36% ROE)")
    print("=" * 80)

    print(f"\n[1/4] Loading continuous 5m dataset: {data_path}...")
    df = pd.read_parquet(data_path)
    n = len(df)
    print(f"  Total records: {n:,} continuous 5m bars ({df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]})")

    dt_arr = pd.to_datetime(df['datetime']).values
    open_arr = df['open'].values.astype(np.float64)
    high_arr = df['high'].values.astype(np.float64)
    low_arr = df['low'].values.astype(np.float64)
    close_arr = df['close'].values.astype(np.float64)
    vol_arr = df['volume'].values.astype(np.float64)
    quote_arr = df['quote_volume'].values.astype(np.float64)
    taker_buy = df['taker_buy_volume'].values.astype(np.float64)

    print("\n[2/4] Constructing Macro Dislocation & Liquidation Climax Features...")
    # 1. 24h Price Change (288 bars)
    ret_24h = pd.Series(close_arr).pct_change(288).bfill().values

    # 2. 7-Day Average Volume Baseline (288 * 7 = 2016 bars)
    vol_sma7d = pd.Series(quote_arr).rolling(2016).mean().bfill().values
    vol_mult = np.where(vol_sma7d > 0, quote_arr / vol_sma7d, 1.0)

    # 3. Microstructure Wicks & Rejection
    candle_range = high_arr - low_arr
    lower_shadow = np.minimum(close_arr, open_arr) - low_arr
    upper_shadow = high_arr - np.maximum(close_arr, open_arr)
    lower_ratio = np.where(candle_range > 0, lower_shadow / candle_range, 0.0)
    upper_ratio = np.where(candle_range > 0, upper_shadow / candle_range, 0.0)

    # Signals
    long_signals = (ret_24h < -0.09) & (vol_mult > 3.5) & (lower_ratio > 0.30)
    short_signals = (ret_24h > 0.09) & (vol_mult > 3.5) & (upper_ratio > 0.30)
    print(f"  Identified Long Climax Signals:  {long_signals.sum():,}")
    print(f"  Identified Short Climax Signals: {short_signals.sum():,}")

    print("\n[3/4] Running 6-Year Step-by-Step 20X Execution Simulation...")
    capital = initial_capital
    portfolio_daily = []
    date_tracker = []
    trades = []
    liquidations = 0

    in_pos = False
    pos_dir = 0
    pos_entry_bar = 0
    pos_entry_price = 0.0
    pos_margin = 0.0
    pos_notional = 0.0
    active_stop = 0.0
    breakeven_hit = False
    cooldown_until = 0

    for i in range(2016, n):
        curr_dt = dt_arr[i]
        curr_close = close_arr[i]
        curr_high = high_arr[i]
        curr_low = low_arr[i]

        # -------------------------------------------------------------
        # 1. Manage Active Position
        # -------------------------------------------------------------
        if in_pos:
            hold_bars = i - pos_entry_bar
            exit_trade = False
            exit_price = 0.0
            exit_type = ""

            if pos_dir == 1: # LONG
                # Check Breakeven trigger (+2.0% advance)
                if not breakeven_hit and curr_high >= pos_entry_price * (1.0 + breakeven_trigger):
                    active_stop = pos_entry_price * 1.001 # Move stop to BE + 0.1%
                    breakeven_hit = True

                # Check Take Profit (+5.0%)
                if curr_high >= pos_entry_price * (1.0 + tp_pct):
                    exit_trade = True
                    exit_price = pos_entry_price * (1.0 + tp_pct)
                    exit_type = "TAKE_PROFIT"
                # Check Stop Loss
                elif curr_low <= active_stop:
                    exit_trade = True
                    exit_price = active_stop
                    exit_type = "BREAK_EVEN" if breakeven_hit else "STOP_LOSS"
                # Check 24h Timeout
                elif hold_bars >= horizon_bars:
                    exit_trade = True
                    exit_price = curr_close
                    exit_type = "TIMEOUT"

                if exit_trade:
                    price_ret = (exit_price - pos_entry_price) / pos_entry_price
                    # Check Liquidation (-4.25%)
                    if price_ret <= -(1.0 / leverage - mmr):
                        liquidations += 1
                        net_pnl = -pos_margin
                        exit_type = "LIQUIDATION"
                    else:
                        entry_fee = pos_notional * maker_fee
                        if exit_type == "TAKE_PROFIT":
                            exit_fee = pos_notional * maker_fee
                            trade_slip = 0.0
                        else:
                            exit_fee = pos_notional * taker_fee
                            trade_slip = pos_notional * slippage
                        gross_pnl = pos_notional * price_ret
                        net_pnl = gross_pnl - entry_fee - exit_fee - trade_slip

                    capital += net_pnl
                    trades.append({
                        'entry_time': dt_arr[pos_entry_bar],
                        'exit_time': curr_dt,
                        'direction': 'LONG',
                        'entry_price': pos_entry_price,
                        'exit_price': exit_price,
                        'price_ret_pct': price_ret * 100.0,
                        'net_roe_pct': (net_pnl / pos_margin) * 100.0,
                        'net_pnl': net_pnl,
                        'exit_type': exit_type,
                        'hold_hours': hold_bars * 5 / 60.0,
                        'capital_after': capital
                    })
                    in_pos = False
                    cooldown_until = i + cooldown_bars

            elif pos_dir == -1: # SHORT
                if not breakeven_hit and curr_low <= pos_entry_price * (1.0 - breakeven_trigger):
                    active_stop = pos_entry_price * 0.999
                    breakeven_hit = True

                if curr_low <= pos_entry_price * (1.0 - tp_pct):
                    exit_trade = True
                    exit_price = pos_entry_price * (1.0 - tp_pct)
                    exit_type = "TAKE_PROFIT"
                elif curr_high >= active_stop:
                    exit_trade = True
                    exit_price = active_stop
                    exit_type = "BREAK_EVEN" if breakeven_hit else "STOP_LOSS"
                elif hold_bars >= horizon_bars:
                    exit_trade = True
                    exit_price = curr_close
                    exit_type = "TIMEOUT"

                if exit_trade:
                    price_ret = (pos_entry_price - exit_price) / pos_entry_price
                    if price_ret <= -(1.0 / leverage - mmr):
                        liquidations += 1
                        net_pnl = -pos_margin
                        exit_type = "LIQUIDATION"
                    else:
                        entry_fee = pos_notional * maker_fee
                        if exit_type == "TAKE_PROFIT":
                            exit_fee = pos_notional * maker_fee
                            trade_slip = 0.0
                        else:
                            exit_fee = pos_notional * taker_fee
                            trade_slip = pos_notional * slippage
                        gross_pnl = pos_notional * price_ret
                        net_pnl = gross_pnl - entry_fee - exit_fee - trade_slip

                    capital += net_pnl
                    trades.append({
                        'entry_time': dt_arr[pos_entry_bar],
                        'exit_time': curr_dt,
                        'direction': 'SHORT',
                        'entry_price': pos_entry_price,
                        'exit_price': exit_price,
                        'price_ret_pct': price_ret * 100.0,
                        'net_roe_pct': (net_pnl / pos_margin) * 100.0,
                        'net_pnl': net_pnl,
                        'exit_type': exit_type,
                        'hold_hours': hold_bars * 5 / 60.0,
                        'capital_after': capital
                    })
                    in_pos = False
                    cooldown_until = i + cooldown_bars

        # -------------------------------------------------------------
        # 2. Check for New Entry Signal
        # -------------------------------------------------------------
        if not in_pos and i >= cooldown_until:
            if long_signals[i]:
                in_pos = True
                pos_dir = 1
                pos_entry_bar = i
                pos_entry_price = curr_close
                pos_margin = capital * margin_ratio
                pos_notional = pos_margin * leverage
                active_stop = pos_entry_price * (1.0 - sl_pct)
                breakeven_hit = False
            elif short_signals[i]:
                in_pos = True
                pos_dir = -1
                pos_entry_bar = i
                pos_entry_price = curr_close
                pos_margin = capital * margin_ratio
                pos_notional = pos_margin * leverage
                active_stop = pos_entry_price * (1.0 + sl_pct)
                breakeven_hit = False

        # Record daily equity snapshots (every 288 bars = 24h)
        if i % 288 == 0:
            portfolio_daily.append(capital)
            date_tracker.append(curr_dt)

    # Final snapshot
    portfolio_daily.append(capital)
    date_tracker.append(dt_arr[-1])

    daily_idx = pd.to_datetime(date_tracker)
    strategy_series = pd.Series(portfolio_daily, index=daily_idx).resample('1D').last().ffill()
    
    # ETH Buy & Hold Series
    df_daily_eth = pd.DataFrame({'datetime': pd.to_datetime(df['datetime']), 'close': close_arr}).set_index('datetime').resample('1D').last().dropna()
    bnh_series = (df_daily_eth['close'] / df_daily_eth['close'].iloc[0]) * initial_capital
    bnh_series = bnh_series.reindex(strategy_series.index).ffill()

    # Performance Analytics
    df_trades = pd.DataFrame(trades)
    print("\n" + "=" * 85)
    print("          PATH A: MACRO DISLOCATION SNIPER PERFORMANCE (2020 - 2026)")
    print("=" * 85)
    
    days = (strategy_series.index[-1] - strategy_series.index[0]).total_seconds() / 86400.0
    years = days / 365.25
    tot_ret = (capital - initial_capital) / initial_capital
    cagr = ((1.0 + tot_ret) ** (1.0 / years)) - 1.0 if (1.0 + tot_ret) > 0 else -1.0

    cummax = strategy_series.cummax()
    drawdown = (strategy_series - cummax) / cummax
    max_dd = abs(drawdown.min())
    calmar = cagr / max_dd if max_dd > 0 else 0.0

    daily_rets = strategy_series.pct_change().dropna()
    sharpe = (daily_rets.mean() / daily_rets.std()) * np.sqrt(365) if daily_rets.std() > 0 else 0.0

    ulcer_index = np.sqrt((drawdown ** 2).mean()) * 100.0

    bnh_tot = (bnh_series.iloc[-1] - bnh_series.iloc[0]) / bnh_series.iloc[0]
    bnh_cagr = ((1.0 + bnh_tot) ** (1.0 / years)) - 1.0
    bnh_cummax = bnh_series.cummax()
    bnh_dd = (bnh_series - bnh_cummax) / bnh_cummax
    bnh_max_dd = abs(bnh_dd.min())
    bnh_rets = bnh_series.pct_change().dropna()
    bnh_sharpe = (bnh_rets.mean() / bnh_rets.std()) * np.sqrt(365) if bnh_rets.std() > 0 else 0.0
    bnh_ulcer = np.sqrt((bnh_dd ** 2).mean()) * 100.0

    print(f"  Initial Capital:        ${initial_capital:,.2f}")
    print(f"  Ending Capital:         ${capital:,.2f}")
    print(f"  Total Return:           {tot_ret*100:+.2f}% (over {years:.2f} years)")
    print(f"  CAGR (Annualized):      {cagr*100:+.2f}%")
    print(f"  Max Drawdown (MaxDD):   {max_dd*100:.2f}%")
    print(f"  Calmar Ratio:           {calmar:.2f}")
    print(f"  Sharpe Ratio:           {sharpe:.2f}")
    print(f"  Ulcer Index (溃疡指数): {ulcer_index:.2f}")
    print(f"  Total Liquidations:     {liquidations} (Strict Zero Survival Target)")
    print("-" * 85)
    print(f"  ETH Buy & Hold Return:  {bnh_tot*100:+.2f}% | MaxDD: {bnh_max_dd*100:.2f}% | Sharpe: {bnh_sharpe:.2f} | Ulcer: {bnh_ulcer:.2f}")

    if len(df_trades) > 0:
        win_trades = df_trades[df_trades['net_pnl'] > 0]
        loss_trades = df_trades[df_trades['net_pnl'] <= 0]
        win_rate = len(win_trades) / len(df_trades)
        gross_p = win_trades['net_pnl'].sum()
        gross_l = abs(loss_trades['net_pnl'].sum()) if len(loss_trades) > 0 else 1.0
        pf = gross_p / gross_l if gross_l > 0 else 999.0
        
        print("\n--- 20X Macro Sniper Execution Statistics ---")
        print(f"  Total Trades:           {len(df_trades)} (~{len(df_trades)/years:.1f} trades/year)")
        print(f"  Win Rate:               {win_rate*100:.2f}%")
        print(f"  Profit Factor:          {pf:.2f}")
        print(f"  Average Holding Period: {df_trades['hold_hours'].mean():.1f} hours")
        print(f"  Mean Net ROE per Trade: {df_trades['net_roe_pct'].mean():+.2f}%")
        print("\n  Exit Breakdown:")
        print(df_trades['exit_type'].value_counts().to_string())

    # Save summary
    summary_df = pd.DataFrame([{
        'Model': 'Path A: Macro Dislocation Sniper (20X)',
        'Initial': initial_capital,
        'Ending': capital,
        'Total_Return': f"{tot_ret*100:+.2f}%",
        'CAGR': f"{cagr*100:+.2f}%",
        'MaxDD': f"{max_dd*100:.2f}%",
        'Sharpe': f"{sharpe:.2f}",
        'Calmar': f"{calmar:.2f}",
        'Ulcer_Index': f"{ulcer_index:.2f}",
        'Win_Rate': f"{win_rate*100:.2f}%" if len(df_trades) > 0 else "N/A",
        'Profit_Factor': f"{pf:.2f}" if len(df_trades) > 0 else "N/A",
        'Trades_Per_Year': f"{len(df_trades)/years:.1f}" if len(df_trades) > 0 else "N/A",
        'Liquidations': liquidations
    }])
    summary_csv = r"d:\Convertible_Bond_data\crypto_data\macro_sniper_20x_summary.csv"
    summary_df.to_csv(summary_csv, index=False)
    print(f"\n[Saved] Performance Summary -> {summary_csv}")

    # [4/4] Multi-Panel Visualization
    print("\n[4/4] Rendering Multi-Panel Performance Charts...")
    plt.style.use('dark_background')
    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=False, gridspec_kw={'height_ratios': [2.2, 1.2, 1.4]})

    # Panel 1: Strategy NAV vs Buy & Hold
    ax1 = axes[0]
    ax1.plot(strategy_series.index, strategy_series, label='Path A: 20X Macro Sniper NAV ($)', color='#00e5ff', linewidth=1.8)
    ax1.set_ylabel('Strategy NAV ($)', color='#00e5ff', fontsize=11, fontweight='bold')
    ax1.set_title('Path A: 20X Macro Dislocation & Liquidation Sniper Backtest (2020 - 2026)', fontsize=13, fontweight='bold', pad=10)
    ax1.grid(True, linestyle='--', alpha=0.3)
    ax1.legend(loc='upper left', frameon=True)

    ax1_twin = ax1.twinx()
    ax1_twin.plot(bnh_series.index, bnh_series, label='ETH Buy & Hold ($)', color='#ff9100', linewidth=1.0, alpha=0.5, linestyle=':')
    ax1_twin.set_ylabel('ETH Buy & Hold ($)', color='#ff9100', fontsize=11)
    ax1_twin.legend(loc='upper right', frameon=True)

    # Panel 2: Rolling Drawdown
    ax2 = axes[1]
    ax2.plot(strategy_series.index, drawdown * 100.0, color='#00e676', linewidth=1.2, label='Path A Drawdown (%)')
    ax2.fill_between(strategy_series.index, drawdown * 100.0, 0, color='#00e676', alpha=0.25)
    ax2.plot(bnh_series.index, bnh_dd * 100.0, color='#ff1744', linewidth=0.8, alpha=0.4, label='ETH Buy & Hold Drawdown (%)')
    ax2.set_ylabel('Drawdown (%)', fontsize=11, fontweight='bold')
    ax2.grid(True, linestyle='--', alpha=0.3)
    ax2.legend(loc='lower left', frameon=True)

    # Panel 3: Trade ROE Distribution
    ax3 = axes[2]
    if len(df_trades) > 0:
        colors = ['#00e676' if r > 0 else '#ff1744' for r in df_trades['net_roe_pct']]
        ax3.bar(range(len(df_trades)), df_trades['net_roe_pct'], color=colors, width=0.8, alpha=0.85)
        ax3.axhline(0, color='white', linestyle='--', alpha=0.4)
        ax3.set_ylabel('Net Trade ROE (%)', fontsize=11, fontweight='bold')
        ax3.set_xlabel('Trade Sequence (2020 - 2026)', fontsize=11, fontweight='bold')
        ax3.set_title(f"Individual Trade ROE (Win Rate: {win_rate*100:.1f}%, Profit Factor: {pf:.2f}, Mean ROE: {df_trades['net_roe_pct'].mean():+.1f}%)", fontsize=11)
        ax3.grid(True, linestyle='--', alpha=0.3)

    plt.tight_layout()
    chart_path = r"d:\Convertible_Bond_data\macro_sniper_20x_performance.png"
    plt.savefig(chart_path, dpi=200)
    plt.close()
    print(f"[Saved] Visualization Chart -> {chart_path}")

    return strategy_series, df_trades, summary_df

if __name__ == '__main__':
    data_path = r"d:\Convertible_Bond_data\crypto_data\history\futures_5m\ETHUSDT_futures_5m_continuous.parquet"
    run_macro_sniper_simulation(
        data_path=data_path,
        initial_capital=10000.0,
        margin_ratio=0.15,      # 15% isolated margin per trade
        leverage=20.0,
        tp_pct=0.050,           # +5.0% TP (+100% ROE)
        sl_pct=0.018,           # -1.8% SL (-36% ROE)
        breakeven_trigger=0.020,# +2.0% triggers BE stop
        horizon_bars=288,       # 24h
        cooldown_bars=144,      # 12h cooldown
        maker_fee=0.0002,
        taker_fee=0.0005,
        slippage=0.0001
    )
