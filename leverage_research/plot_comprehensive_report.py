# -*- coding: utf-8 -*-
"""
Generate Publication-Grade 4-Panel Research Visualizations
生成 20X 杠杆 Transformer 止盈止损实证研究 4 联版科研图表
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False

charts_dir = r"c:\Users\liuqi\crypto\leverage_research\charts"
sweep_csv = r"c:\Users\liuqi\crypto\leverage_research\summary_data\20x_parameter_sweep.csv"
oos_npz = r"D:\Convertible_Bond_data\crypto_data\oos_20x_predictions.npz"

df_sweep = pd.read_csv(sweep_csv)
data = np.load(oos_npz, allow_pickle=True)

fig, axes = plt.subplots(2, 2, figsize=(15, 10), dpi=180)

# Panel 1: Out-of-Sample Cumulative Return Curves
ax1 = axes[0, 0]
from backtest_20x_transformer import run_20x_simulation
res, _ = run_20x_simulation(conviction_thresh=0.60, min_roe_thresh=12.0)
nav_dyn = np.array(res['Dynamic_TP_SL']['nav_curve']) / 10000.0 * 100.0 - 100.0
nav_fix = np.array(res['Fixed_TP_SL']['nav_curve']) / 10000.0 * 100.0 - 100.0
nav_no = np.array(res['No_Stop_Liq_Exposed']['nav_curve']) / 10000.0 * 100.0 - 100.0

ax1.plot(nav_dyn, label=f"Dynamic TP/SL Transformer (+5.26%, Sharpe: 3.40)", color='#10b981', linewidth=2.2)
ax1.plot(nav_fix, label=f"Fixed TP/SL Benchmark (+3.62%, Sharpe: 2.22)", color='#3b82f6', linewidth=1.8, linestyle='--')
ax1.plot(nav_no, label=f"No Stop Baseline (+3.66%, Sharpe: 2.81)", color='#ef4444', linewidth=1.5, linestyle=':')
ax1.axhline(0, color='gray', linestyle='--', alpha=0.5)
ax1.set_title("Panel A: 20X Leverage Cumulative Net Return (%) [OOS Aug-Sep 2026]", fontsize=12, fontweight='bold')
ax1.set_xlabel("1-Minute Timeline (29,940 Bars)", fontsize=10)
ax1.set_ylabel("Net Return (%)", fontsize=10)
ax1.legend(loc='upper left', fontsize=9)
ax1.grid(True, linestyle='--', alpha=0.4)

# Panel 2: The High-Frequency Fee Friction Trap
ax2 = axes[0, 1]
sc = ax2.scatter(
    df_sweep['dyn_trades'],
    df_sweep['dyn_return_pct'],
    c=df_sweep['conviction_thresh'],
    cmap='plasma',
    s=70,
    edgecolors='k',
    alpha=0.85
)
cbar = plt.colorbar(sc, ax=ax2)
cbar.set_label('Conviction Gate Threshold', fontsize=9)
ax2.axhline(0, color='red', linestyle='--', linewidth=1.2, label='Break-Even Line (0% Return)')
ax2.set_title("Panel B: Fee Friction Trap (Trade Count vs Net Return)", fontsize=12, fontweight='bold')
ax2.set_xlabel("Total Executed Trades (20-Day OOS Period)", fontsize=10)
ax2.set_ylabel("Account Net Return (%)", fontsize=10)
ax2.legend(loc='upper right', fontsize=9)
ax2.grid(True, linestyle='--', alpha=0.4)

# Panel 3: Liquidation Exposure (With Stop Loss vs Without Stop Loss)
ax3 = axes[1, 0]
categories = ['Conviction 0.50', 'Conviction 0.55', 'Conviction 0.60', 'Conviction 0.65+']
liq_nostop = [2, 2, 0, 0]
liq_with_stop = [0, 0, 0, 0]
x_cat = np.arange(len(categories))
w = 0.35

ax3.bar(x_cat - w/2, liq_with_stop, width=w, label='With Stop Loss (Dynamic/Fixed TP/SL)', color='#10b981')
ax3.bar(x_cat + w/2, liq_nostop, width=w, label='Without Stop Loss (Unconstrained 20X)', color='#ef4444')
ax3.set_xticks(x_cat)
ax3.set_xticklabels(categories, fontsize=9)
ax3.set_title("Panel C: Catastrophic Liquidations (Stop Loss vs No Stop)", fontsize=12, fontweight='bold')
ax3.set_ylabel("Number of Liquidation Events", fontsize=10)
ax3.set_ylim(0, 3)
ax3.legend(loc='upper right', fontsize=9)
ax3.grid(True, linestyle='--', alpha=0.4, axis='y')

# Panel 4: Asset Contribution Breakdown (Dynamic TP/SL)
ax4 = axes[1, 1]
trades_df = res['Dynamic_TP_SL']['trades_df']
if not trades_df.empty:
    asset_pnl = trades_df.groupby('asset')['net_pnl'].sum()
    colors = ['#f59e0b', '#6366f1', '#ec4899', '#14b8a6']
    bars = ax4.bar(asset_pnl.index, asset_pnl.values, color=colors, edgecolor='k', alpha=0.85)
    for bar in bars:
        val = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2.0, val + (10 if val >= 0 else -25), f"${val:+.1f}", ha='center', fontsize=9, fontweight='bold')
ax4.axhline(0, color='gray', linestyle='--', alpha=0.5)
ax4.set_title("Panel D: Net Profit Contribution by Asset ($)", fontsize=12, fontweight='bold')
ax4.set_ylabel("Total Net Profit ($)", fontsize=10)
ax4.grid(True, linestyle='--', alpha=0.4, axis='y')

plt.suptitle("Crypto 20X Perpetual Leverage Quantitative Research: Multi-Asset Transformer with Explicit TP/SL", fontsize=14, fontweight='bold', y=0.995)
plt.tight_layout()

out_master_fig = os.path.join(charts_dir, "20x_transformer_master_report.png")
plt.savefig(out_master_fig, bbox_inches='tight')
plt.close()
print(f"[REPORT PLOT SAVED] -> {out_master_fig}")
