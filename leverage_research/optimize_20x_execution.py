# -*- coding: utf-8 -*-
"""
Sweep Conviction & Risk-Reward Regimes for 20X Leverage Transformer
系统性扫描置信度门控与盈亏比阈值，寻找 20X 杠杆费率摩擦与胜率的最优平衡点
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from backtest_20x_transformer import run_20x_simulation


def sweep_parameters():
    print("=" * 80)
    print("  Systematic Parameter Sweep for 20X Leverage Transformer Execution")
    print("=" * 80)

    conviction_list = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
    min_roe_list = [4.0, 8.0, 12.0, 16.0]

    sweep_records = []

    for c_th in conviction_list:
        for r_th in min_roe_list:
            res, _ = run_20x_simulation(
                conviction_thresh=c_th,
                min_roe_thresh=r_th,
                charts_dir=r"c:\Users\liuqi\crypto\leverage_research\charts"
            )
            dyn = res['Dynamic_TP_SL']
            fix = res['Fixed_TP_SL']
            nostop = res['No_Stop_Liq_Exposed']

            sweep_records.append({
                'conviction_thresh': c_th,
                'min_roe_thresh': r_th,
                'dyn_trades': dyn['total_trades'],
                'dyn_return_pct': dyn['total_return_pct'],
                'dyn_win_rate': dyn['win_rate_pct'],
                'dyn_max_dd': dyn['max_drawdown_pct'],
                'dyn_profit_factor': dyn['profit_factor'],
                'dyn_liquidations': dyn['liquidations'],
                'fix_return_pct': fix['total_return_pct'],
                'nostop_liquidations': nostop['liquidations']
            })

    df_sweep = pd.DataFrame(sweep_records)
    out_csv = r"c:\Users\liuqi\crypto\leverage_research\summary_data\20x_parameter_sweep.csv"
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    df_sweep.to_csv(out_csv, index=False)

    print("\n" + "=" * 80)
    print("  Parameter Sweep Summary (Top 10 by Return):")
    df_sorted = df_sweep.sort_values('dyn_return_pct', ascending=False)
    print(df_sorted[['conviction_thresh', 'min_roe_thresh', 'dyn_trades', 'dyn_win_rate', 'dyn_return_pct', 'dyn_max_dd', 'dyn_liquidations']].head(10).to_string(index=False))
    print("=" * 80)

    # Plot Trade Count vs Return curve
    plt.figure(figsize=(10, 5), dpi=150)
    plt.scatter(df_sweep['dyn_trades'], df_sweep['dyn_return_pct'], c=df_sweep['conviction_thresh'], cmap='viridis', s=60, edgecolors='k')
    plt.colorbar(label='Conviction Threshold')
    plt.title("20X Leverage: Trade Count (Fee Drag) vs Total Return", fontsize=12, fontweight='bold')
    plt.xlabel("Total Trades Taken in 20 Days", fontsize=10)
    plt.ylabel("Total Return (%)", fontsize=10)
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.tight_layout()
    plt.savefig(r"c:\Users\liuqi\crypto\leverage_research\charts\20x_trade_count_vs_return.png")
    plt.close()

    return df_sweep


if __name__ == '__main__':
    sweep_parameters()
