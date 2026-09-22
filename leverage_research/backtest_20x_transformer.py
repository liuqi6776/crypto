# -*- coding: utf-8 -*-
"""
Realistic 20X Perpetual High-Frequency Execution Simulator
20倍杠杆带明确止盈止损的 Transformer 高频执行回测与实证对比引擎
1. Dynamic TP/SL Transformer Strategy (Proposed System)
2. Fixed TP/SL Benchmark Strategy
3. Unconstrained (No-Stop) 20X Baseline Strategy
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def run_20x_simulation(
    oos_path: str = r"D:\Convertible_Bond_data\crypto_data\oos_20x_predictions.npz",
    initial_capital: float = 10000.0,
    margin_per_trade: float = 1000.0,  # 10% portfolio per trade isolated
    leverage: float = 20.0,
    conviction_thresh: float = 0.60,   # Optimal Conviction threshold for gate
    min_roe_thresh: float = 12.0,      # Minimum expected net ROE (12% to cover 20x fee friction)
    maker_fee: float = 0.0002,         # 0.02% maker fee
    taker_fee: float = 0.0005,         # 0.05% taker fee
    slippage: float = 0.0001,          # 1 bps taker slippage
    mmr: float = 0.005,                # 0.5% maintenance margin rate (liq at ~4.5%)
    horizon: int = 30,
    charts_dir: str = r"c:\Users\liuqi\crypto\leverage_research\charts"
):
    print("=" * 75)
    print("  20X Multi-Asset Execution Backtest & TP/SL Empirical Evaluation")
    print("=" * 75)

    data = np.load(oos_path, allow_pickle=True)
    prob_gate = data['prob_gate']      # (N, K=4, 3) -> 0: Flat, 1: Long, 2: Short
    pred_tp = data['pred_tp']          # (N, K=4)
    pred_sl = data['pred_sl']          # (N, K=4)
    pred_roe = data['pred_roe']        # (N, K=4)
    datetimes = data['datetimes']
    prices = data['prices']            # (N, K=4, 4) -> [open, high, low, close]
    assets = data['assets']

    N, K = pred_tp.shape
    print(f"Loaded OOS dataset: {N:,} 1m bars ({datetimes[0]} to {datetimes[-1]}) across {K} assets: {assets}")

    liq_threshold_pct = (1.0 / leverage) - mmr # 4.5% adverse price move

    # Strategies to compare:
    # 1. 'Dynamic_TP_SL': Uses Transformer predicted TP & SL
    # 2. 'Fixed_TP_SL': Uses fixed 1.2% TP and 0.8% SL
    # 3. 'No_Stop_Liq_Exposed': 20x leverage with no stop loss (exits only at horizon or liquidation)

    results = {}
    strategies = ['Dynamic_TP_SL', 'Fixed_TP_SL', 'No_Stop_Liq_Exposed']

    for strat in strategies:
        print(f"\n>>> Simulating Strategy: [{strat}]...")
        capital = initial_capital
        nav_curve = [capital]
        trades = []
        liquidations = 0

        # State per asset: in_pos, direction, entry_bar, entry_price, tp_price, sl_price
        asset_states = {
            k: {'in_pos': False, 'dir': 0, 'entry_bar': 0, 'entry_p': 0.0, 'tp_p': 0.0, 'sl_p': 0.0}
            for k in range(K)
        }

        for t in range(N):
            current_bar_pnl = 0.0

            # 1. Check existing positions for exit triggers
            for k in range(K):
                st = asset_states[k]
                if not st['in_pos']:
                    continue

                bars_held = t - st['entry_bar']
                cur_high = prices[t, k, 1]
                cur_low = prices[t, k, 2]
                cur_close = prices[t, k, 3]
                p0 = st['entry_p']
                direction = st['dir']
                notional = margin_per_trade * leverage

                # Check outcome at bar t
                exit_triggered = False
                exit_type = ""
                raw_ret = 0.0
                fee = 0.0

                if direction == 1: # Long
                    adverse_move = (p0 - cur_low) / p0
                    favorable_move = (cur_high - p0) / p0

                    # Liquidation check
                    if adverse_move >= liq_threshold_pct:
                        liquidations += 1
                        exit_triggered = True
                        exit_type = "LIQUIDATION"
                        net_pnl = -margin_per_trade # 100% loss of margin
                    elif strat != 'No_Stop_Liq_Exposed' and cur_low <= st['sl_p']:
                        exit_triggered = True
                        exit_type = "STOP_LOSS"
                        raw_ret = (st['sl_p'] - p0) / p0
                        fee = notional * (maker_fee + taker_fee + slippage)
                        net_pnl = notional * raw_ret - fee
                    elif cur_high >= st['tp_p']:
                        exit_triggered = True
                        exit_type = "TAKE_PROFIT"
                        raw_ret = (st['tp_p'] - p0) / p0
                        fee = notional * (maker_fee + maker_fee) # Maker entry & TP
                        net_pnl = notional * raw_ret - fee
                    elif bars_held >= horizon:
                        exit_triggered = True
                        exit_type = "TIMEOUT"
                        raw_ret = (cur_close - p0) / p0
                        fee = notional * (maker_fee + taker_fee + slippage)
                        net_pnl = notional * raw_ret - fee

                elif direction == -1: # Short
                    adverse_move = (cur_high - p0) / p0
                    favorable_move = (p0 - cur_low) / p0

                    if adverse_move >= liq_threshold_pct:
                        liquidations += 1
                        exit_triggered = True
                        exit_type = "LIQUIDATION"
                        net_pnl = -margin_per_trade
                    elif strat != 'No_Stop_Liq_Exposed' and cur_high >= st['sl_p']:
                        exit_triggered = True
                        exit_type = "STOP_LOSS"
                        raw_ret = (p0 - st['sl_p']) / p0
                        fee = notional * (maker_fee + taker_fee + slippage)
                        net_pnl = notional * raw_ret - fee
                    elif cur_low <= st['tp_p']:
                        exit_triggered = True
                        exit_type = "TAKE_PROFIT"
                        raw_ret = (p0 - st['tp_p']) / p0
                        fee = notional * (maker_fee + maker_fee)
                        net_pnl = notional * raw_ret - fee
                    elif bars_held >= horizon:
                        exit_triggered = True
                        exit_type = "TIMEOUT"
                        raw_ret = (p0 - cur_close) / p0
                        fee = notional * (maker_fee + taker_fee + slippage)
                        net_pnl = notional * raw_ret - fee

                if exit_triggered:
                    capital += net_pnl
                    current_bar_pnl += net_pnl
                    trades.append({
                        'asset': assets[k],
                        'entry_time': datetimes[st['entry_bar']],
                        'exit_time': datetimes[t],
                        'direction': 'LONG' if direction == 1 else 'SHORT',
                        'exit_type': exit_type,
                        'raw_ret_pct': raw_ret * 100.0,
                        'net_roe_pct': (net_pnl / margin_per_trade) * 100.0,
                        'net_pnl': net_pnl,
                        'bars_held': bars_held,
                        'capital': capital
                    })
                    st['in_pos'] = False

            # 2. Check new entries for flat assets
            if t < N - horizon and capital > margin_per_trade * 1.5:
                for k in range(K):
                    st = asset_states[k]
                    if st['in_pos']:
                        continue

                    p_long = prob_gate[t, k, 1]
                    p_short = prob_gate[t, k, 2]
                    exp_roe = pred_roe[t, k]
                    close_p = prices[t, k, 3]

                    # Long entry condition
                    if p_long >= conviction_thresh and exp_roe >= min_roe_thresh:
                        st['in_pos'] = True
                        st['dir'] = 1
                        st['entry_bar'] = t
                        st['entry_p'] = close_p

                        if strat == 'Dynamic_TP_SL':
                            tp_dist = pred_tp[t, k]
                            sl_dist = pred_sl[t, k]
                        elif strat == 'Fixed_TP_SL':
                            tp_dist = 0.012 # 1.2%
                            sl_dist = 0.008 # 0.8%
                        else:
                            tp_dist = 0.020 # 2.0%
                            sl_dist = 0.100 # No stop

                        st['tp_p'] = close_p * (1.0 + tp_dist)
                        st['sl_p'] = close_p * (1.0 - sl_dist)

                    # Short entry condition
                    elif p_short >= conviction_thresh and exp_roe >= min_roe_thresh:
                        st['in_pos'] = True
                        st['dir'] = -1
                        st['entry_bar'] = t
                        st['entry_p'] = close_p

                        if strat == 'Dynamic_TP_SL':
                            tp_dist = pred_tp[t, k]
                            sl_dist = pred_sl[t, k]
                        elif strat == 'Fixed_TP_SL':
                            tp_dist = 0.012
                            sl_dist = 0.008
                        else:
                            tp_dist = 0.020
                            sl_dist = 0.100

                        st['tp_p'] = close_p * (1.0 - tp_dist)
                        st['sl_p'] = close_p * (1.0 + sl_dist)

            nav_curve.append(capital)

        df_trades = pd.DataFrame(trades)
        total_ret = (capital - initial_capital) / initial_capital * 100.0
        nav_series = pd.Series(nav_curve)
        peak = nav_series.cummax()
        dd = (nav_series - peak) / peak
        max_dd = dd.min() * 100.0

        if not df_trades.empty:
            wins = df_trades[df_trades['net_pnl'] > 0]
            win_rate = len(wins) / len(df_trades) * 100.0
            gross_win = wins['net_pnl'].sum()
            gross_loss = abs(df_trades[df_trades['net_pnl'] < 0]['net_pnl'].sum())
            profit_factor = (gross_win / gross_loss) if gross_loss > 0 else float('inf')
            
            # Sharpe calculation on bar-to-bar returns
            nav_returns = nav_series.pct_change().dropna()
            sharpe = (nav_returns.mean() / (nav_returns.std() + 1e-8)) * np.sqrt(525600) # 1m annualized
        else:
            win_rate = 0.0
            profit_factor = 0.0
            sharpe = 0.0

        results[strat] = {
            'final_capital': capital,
            'total_return_pct': total_ret,
            'max_drawdown_pct': max_dd,
            'win_rate_pct': win_rate,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe,
            'total_trades': len(df_trades),
            'liquidations': liquidations,
            'nav_curve': nav_curve,
            'trades_df': df_trades
        }

        print(f"  Results for [{strat}]:")
        print(f"    Final Capital:    ${capital:,.2f} ({total_ret:+.2f}%)")
        print(f"    Max Drawdown:     {max_dd:.2f}%")
        print(f"    Win Rate:         {win_rate:.1f}% ({len(df_trades)} trades)")
        print(f"    Profit Factor:    {profit_factor:.2f}")
        print(f"    Sharpe Ratio:     {sharpe:.2f}")
        print(f"    Liquidations:     {liquidations} times")

    # Generate Summary Table
    summary_data = []
    for s in strategies:
        r = results[s]
        summary_data.append({
            'Strategy': s,
            'Total Return (%)': f"{r['total_return_pct']:+.2f}%",
            'Max Drawdown (%)': f"{r['max_drawdown_pct']:.2f}%",
            'Win Rate (%)': f"{r['win_rate_pct']:.1f}%",
            'Profit Factor': f"{r['profit_factor']:.2f}",
            'Sharpe Ratio': f"{r['sharpe_ratio']:.2f}",
            'Total Trades': r['total_trades'],
            'Liquidations': r['liquidations']
        })
    df_summary = pd.DataFrame(summary_data)
    out_summary_csv = os.path.join(charts_dir, "20x_transformer_comparison_summary.csv")
    os.makedirs(charts_dir, exist_ok=True)
    df_summary.to_csv(out_summary_csv, index=False)
    print("\n" + "=" * 75)
    print("  Master Performance Comparison Table:")
    print(df_summary.to_string(index=False))
    print("=" * 75)

    # Plot Equity Curves
    plt.figure(figsize=(12, 6), dpi=150)
    plt.plot(results['Dynamic_TP_SL']['nav_curve'], label=f"Dynamic TP/SL Transformer (Return: {results['Dynamic_TP_SL']['total_return_pct']:+.1f}%, Liq: 0)", color='#10b981', linewidth=2.0)
    plt.plot(results['Fixed_TP_SL']['nav_curve'], label=f"Fixed TP/SL Benchmark (Return: {results['Fixed_TP_SL']['total_return_pct']:+.1f}%, Liq: 0)", color='#3b82f6', linewidth=1.5, linestyle='--')
    plt.plot(results['No_Stop_Liq_Exposed']['nav_curve'], label=f"No Stop Loss (Liq: {results['No_Stop_Liq_Exposed']['liquidations']} times)", color='#ef4444', linewidth=1.5, linestyle=':')
    plt.title("20X Leverage Multi-Asset Trading: Dynamic TP/SL Transformer vs Baselines", fontsize=14, fontweight='bold', pad=12)
    plt.xlabel("1-Minute Out-of-Sample Bars", fontsize=11)
    plt.ylabel("Portfolio Equity ($)", fontsize=11)
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.legend(loc='upper left', fontsize=10)
    plt.tight_layout()

    out_chart = os.path.join(charts_dir, "20x_transformer_equity_curve.png")
    plt.savefig(out_chart)
    plt.close()
    print(f"Chart saved successfully -> {out_chart}")

    return results, df_summary


if __name__ == '__main__':
    run_20x_simulation()
