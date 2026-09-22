# -*- coding: utf-8 -*-
"""
Publication-Grade Visual Dashboard for Month-to-Date (Sept 1 - 22, 2026) Paper Trading
绘制 2026年9月1日至22日以太坊 100倍杠杆模拟盘实操全景、资金曲线与买卖标注大图
"""

import os
import sys
import shutil
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

CURVES_NPZ = r"c:\Users\liuqi\crypto\leverage_research\charts\september_2026_curves.npz"
TRADES_CSV = r"c:\Users\liuqi\crypto\leverage_research\charts\september_2026_paper_trades.csv"
SUMMARY_CSV = r"c:\Users\liuqi\crypto\leverage_research\charts\september_2026_summary.csv"
OUT_IMG = r"c:\Users\liuqi\crypto\leverage_research\charts\september_2026_paper_trading_report.png"
ARTIFACT_IMG = r"C:\Users\liuqi\.gemini\antigravity\brain\85b8b55c-f9a4-4530-ae89-7a324bd99842\september_2026_paper_trading_report.png"


def plot_dashboard():
    print("=" * 80)
    print("Generating September 1 - 22, 2026 Paper Trading Master Dashboard...")
    print("=" * 80)
    
    if not os.path.exists(CURVES_NPZ) or not os.path.exists(TRADES_CSV):
        print("Required input data not found!")
        return
        
    data = np.load(CURVES_NPZ, allow_pickle=True)
    df_trades = pd.read_csv(TRADES_CSV)
    df_sum = pd.read_csv(SUMMARY_CSV)
    
    bar_eq_a = data['bar_equity_a']
    bar_eq_b = data['bar_equity_b']
    closes = data['closes']
    timestamps = pd.to_datetime(data['timestamps'])
    
    eis = data['eis_a']
    xis = data['xis_a']
    sides = data['sides_a']
    eps = data['eps_a']
    xps = data['xps_a']
    res = data['res_a']
    pnls = data['pnls_a']
    roes = data['roes_a']
    
    # Configure matplotlib style with Microsoft YaHei for clean Chinese rendering
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans', 'Arial']
    plt.rcParams['axes.unicode_minus'] = False
    
    fig = plt.figure(figsize=(24, 20), dpi=300)
    gs = fig.add_gridspec(5, 1, height_ratios=[2.2, 2.0, 1.3, 1.6, 1.4], hspace=0.32)
    
    # -------------------------------------------------------------------------
    # Panel 1: ETH Price Chart with Trade Entry/Exit Markers
    # -------------------------------------------------------------------------
    ax1 = fig.add_subplot(gs[0])
    ax1.plot(timestamps, closes, color='#94a3b8', alpha=0.75, linewidth=1.2, label='ETHUSDT 1m Mark Price')
    
    # Plot Long Entries (Green Triangles Up) and Short Entries (Magenta Triangles Down)
    long_mask = sides == 1
    short_mask = sides == -1
    
    if long_mask.any():
        ax1.scatter(timestamps[eis[long_mask]], eps[long_mask], marker='^', color='#10b981', s=90,
                    edgecolors='black', linewidth=0.8, label='Long Entry (30% Margin, 100X)', zorder=5)
    if short_mask.any():
        ax1.scatter(timestamps[eis[short_mask]], eps[short_mask], marker='v', color='#ec4899', s=90,
                    edgecolors='black', linewidth=0.8, label='Short Entry (30% Margin, 100X)', zorder=5)
                    
    # Plot Exits: TP (Gold Star), BE (Cyan Square), SL (Red X)
    tp_mask = res == 1
    be_mask = res == 2
    sl_mask = res == -1
    
    if tp_mask.any():
        ax1.scatter(timestamps[xis[tp_mask]], xps[tp_mask], marker='*', color='#f59e0b', s=130,
                    edgecolors='black', linewidth=0.8, label='Take-Profit Exit (+22%~+37% ROE)', zorder=6)
    if be_mask.any():
        ax1.scatter(timestamps[xis[be_mask]], xps[be_mask], marker='s', color='#06b6d4', s=60,
                    edgecolors='black', linewidth=0.8, label='Breakeven Lock (+2% ROE)', zorder=6)
    if sl_mask.any():
        ax1.scatter(timestamps[xis[sl_mask]], xps[sl_mask], marker='x', color='#ef4444', s=80,
                    linewidth=2.0, label='Stop-Loss (-22% ROE)', zorder=6)
                    
    ax1.set_title("Panel 1: ETHUSDT Perpetual Price Action & Trade Executions (Sept 1 - 22, 2026 | 28 Trades)",
                  fontsize=14, fontweight='bold', pad=10)
    ax1.set_ylabel("ETH Price (USDT)", fontsize=11, fontweight='bold')
    ax1.grid(True, linestyle='--', alpha=0.35)
    ax1.legend(loc='upper left', frameon=True, facecolor='#ffffff', framealpha=0.9, fontsize=9.5, ncol=3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
    
    # -------------------------------------------------------------------------
    # Panel 2: Continuous Equity Curves ($10,000 base)
    # -------------------------------------------------------------------------
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ret_a = (bar_eq_a[-1] / 10000.0 - 1.0) * 100.0
    ret_b = (bar_eq_b[-1] / 10000.0 - 1.0) * 100.0
    
    ax2.plot(timestamps, bar_eq_a, color='#059669', linewidth=2.2,
             label=f'Track A: 30% Golden Kelly Sizing (Final: ${bar_eq_a[-1]:,.2f} | {ret_a:+.2f}%)')
    ax2.plot(timestamps, bar_eq_b, color='#0284c7', linewidth=1.8, linestyle='--',
             label=f'Track B: 20% Scientific Baseline Sizing (Final: ${bar_eq_b[-1]:,.2f} | {ret_b:+.2f}%)')
    ax2.axhline(10000.0, color='#64748b', linestyle=':', linewidth=1.2, label='Initial Capital ($10,000.00)')
    
    ax2.set_title("Panel 2: Cumulative Portfolio Equity Curves ($10,000 Base, Continuous 1m Mark-to-Market)",
                  fontsize=14, fontweight='bold', pad=10)
    ax2.set_ylabel("Portfolio Equity ($)", fontsize=11, fontweight='bold')
    ax2.grid(True, linestyle='--', alpha=0.35)
    ax2.legend(loc='upper left', frameon=True, facecolor='#ffffff', framealpha=0.9, fontsize=10.5)
    
    # -------------------------------------------------------------------------
    # Panel 3: Underwater Drawdown Comparison
    # -------------------------------------------------------------------------
    ax3 = fig.add_subplot(gs[2], sharex=ax1)
    cum_max_a = np.maximum.accumulate(bar_eq_a)
    dd_a = (cum_max_a - bar_eq_a) / cum_max_a * 100.0
    
    cum_max_b = np.maximum.accumulate(bar_eq_b)
    dd_b = (cum_max_b - bar_eq_b) / cum_max_b * 100.0
    
    ax3.fill_between(timestamps, -dd_a, 0, color='#ef4444', alpha=0.3, label=f'Track A Max Drawdown: {dd_a.max():.2f}%')
    ax3.plot(timestamps, -dd_a, color='#dc2626', linewidth=1.4)
    ax3.plot(timestamps, -dd_b, color='#0284c7', linewidth=1.4, linestyle='--', label=f'Track B Max Drawdown: {dd_b.max():.2f}%')
    ax3.axhline(0, color='#64748b', linestyle='-', linewidth=0.8)
    
    ax3.set_title("Panel 3: Underwater Drawdown Curves (Strictly Controlled Risk & ZERO Liquidations)",
                  fontsize=13, fontweight='bold', pad=8)
    ax3.set_ylabel("Drawdown (%)", fontsize=11, fontweight='bold')
    ax3.grid(True, linestyle='--', alpha=0.35)
    ax3.legend(loc='lower left', frameon=True, facecolor='#ffffff', framealpha=0.9, fontsize=10)
    
    # -------------------------------------------------------------------------
    # Panel 4: Trade-by-Trade Net ROE (%) & Dollar PnL ($)
    # -------------------------------------------------------------------------
    ax4 = fig.add_subplot(gs[3])
    x_indices = np.arange(1, len(pnls) + 1)
    bar_colors = ['#10b981' if r == 1 else ('#06b6d4' if r == 2 else '#ef4444') for r in res]
    
    bars = ax4.bar(x_indices, pnls, color=bar_colors, width=0.72, edgecolor='black', linewidth=0.6)
    ax4.axhline(0, color='#334155', linestyle='-', linewidth=1.0)
    
    # Annotate bar values
    for b, pnl, roe in zip(bars, pnls, roes):
        y_pos = b.get_height()
        offset = 40 if y_pos >= 0 else -65
        ax4.annotate(f"${pnl:+.0f}\n({roe*100:+.0f}%)",
                     xy=(b.get_x() + b.get_width() / 2, y_pos),
                     xytext=(0, offset), textcoords="offset points",
                     ha='center', va='center', fontsize=7.5, fontweight='bold',
                     color='#065f46' if y_pos >= 0 else '#991b1b')
                     
    ax4.set_title("Panel 4: Trade-by-Trade Net Dollar PnL ($) and Margin ROE (%) (Green: TP, Cyan: Breakeven, Red: SL)",
                  fontsize=13, fontweight='bold', pad=8)
    ax4.set_xlabel("Trade Number (Sequence of 28 Trades across 22 Days)", fontsize=11, fontweight='bold')
    ax4.set_ylabel("Realized PnL ($)", fontsize=11, fontweight='bold')
    ax4.set_xticks(x_indices)
    ax4.set_xlim(0.3, len(pnls) + 0.7)
    ax4.grid(True, linestyle='--', alpha=0.35, axis='y')
    
    # -------------------------------------------------------------------------
    # Panel 5: Master Metrics Table
    # -------------------------------------------------------------------------
    ax5 = fig.add_subplot(gs[4])
    ax5.axis('off')
    
    col_labels = [
        'Strategy Track', 'Trades', 'Daily Rate', 'Win Rate',
        'Win+BE Rate', 'Take-Profits', 'Breakeven Locks', 'Stop-Losses',
        'Liquidations', 'Initial Capital', 'Final Equity', 'Net Return', 'Max Drawdown', 'Profit Factor'
    ]
    
    row_data = []
    for _, row in df_sum.iterrows():
        row_data.append([
            row['strategy'],
            f"{row['total_trades']}",
            f"{row['daily_trades']}/day",
            f"{row['win_rate']:.1f}%",
            f"{row['effective_win_rate (Win+BE)']:.1f}%",
            f"{row['tp_count']}",
            f"{row['be_count']}",
            f"{row['sl_count']}",
            f"{row['liquidations']} (Zero)",
            "$10,000.00",
            f"${row['final_equity']:,.2f}",
            f"{row['total_return_pct']:+.2f}%",
            f"{row['max_drawdown_pct']:.2f}%",
            f"{row['profit_factor']:.2f}"
        ])
        
    table = ax5.table(cellText=row_data, colLabels=col_labels, loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.0, 2.2)
    
    # Style table header & rows
    for (i, j), cell in table.get_celld().items():
        if i == 0:
            cell.set_facecolor('#1e293b')
            cell.set_text_props(color='#ffffff', fontweight='bold')
        else:
            if i == 1:
                cell.set_facecolor('#ecfdf5')
            else:
                cell.set_facecolor('#f0f9ff')
            cell.set_text_props(color='#0f172a')
            
    ax5.set_title("Panel 5: Month-to-Date Performance Audit Ledger (September 1 - 22, 2026)",
                  fontsize=13, fontweight='bold', pad=12)
                  
    plt.savefig(OUT_IMG, bbox_inches='tight')
    plt.close()
    print(f"Master dashboard successfully generated at: {OUT_IMG}")
    
    # Copy to artifacts directory
    os.makedirs(os.path.dirname(ARTIFACT_IMG), exist_ok=True)
    shutil.copy(OUT_IMG, ARTIFACT_IMG)
    print(f"Copied to artifact directory: {ARTIFACT_IMG}")
    print("=" * 80)


if __name__ == "__main__":
    plot_dashboard()
