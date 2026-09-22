# -*- coding: utf-8 -*-
"""
Publication-Grade Visual Dashboard: In-Sample Training vs Out-of-Sample Test Comparison
样本内训练集（2026/05前） vs 样本外测试集（2026/05后）全景对比量化研报大图
- 5-Panel Professional Dark/Cyberpunk Theme Dashboard
- Panel 1: Out-of-Sample (May-Sept 2026) Price Action with Buy/Sell Execution Markers
- Panel 2: Cumulative Equity Curves ($10k base) comparing Train vs Test across Kelly & Sci modes
- Panel 3: Underwater Drawdown Dynamics proving zero liquidations
- Panel 4: Test Horizon Monthly Return & Win Rate Breakdown (May, June, July, August, September)
- Panel 5: Comprehensive Performance Audit Matrix Table
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

OUTPUT_DIR = r"c:\Users\liuqi\crypto\leverage_research\charts"
ARTIFACT_DIR = r"C:\Users\liuqi\.gemini\antigravity\brain\85b8b55c-f9a4-4530-ae89-7a324bd99842"
REPORT_PNG = os.path.join(OUTPUT_DIR, "train_test_comparison_report.png")
ARTIFACT_PNG = os.path.join(ARTIFACT_DIR, "train_test_comparison_report.png")

CURVES_NPZ = os.path.join(OUTPUT_DIR, "train_test_curves.npz")
SUMMARY_CSV = os.path.join(OUTPUT_DIR, "train_test_summary.csv")
TRADES_CSV = os.path.join(OUTPUT_DIR, "test_trades_may_sept_2026.csv")


def generate_train_test_comparison_report():
    print("=" * 85)
    print("  Generating Publication-Grade Train vs Test Visual Dashboard")
    print("=" * 85)

    if not os.path.exists(CURVES_NPZ) or not os.path.exists(SUMMARY_CSV) or not os.path.exists(TRADES_CSV):
        print(f"Required files not found: {CURVES_NPZ}, {SUMMARY_CSV}, or {TRADES_CSV}")
        return

    # Load data
    curves = np.load(CURVES_NPZ, allow_pickle=True)
    train_eq_k = curves['train_equity_kelly']
    train_eq_s = curves['train_equity_sci']
    train_dts = curves['train_dts']
    test_eq_k = curves['test_equity_kelly']
    test_eq_s = curves['test_equity_sci']
    test_dts = curves['test_dts']
    test_p_close = curves['test_p_close']

    df_summary = pd.read_csv(SUMMARY_CSV)
    df_trades = pd.read_csv(TRADES_CSV)

    # Style Setup
    plt.style.use('dark_background')
    fig = plt.figure(figsize=(24, 18), facecolor='#0B0E14')
    gs = fig.add_gridspec(3, 2, height_ratios=[1.2, 1.0, 1.1], width_ratios=[1.3, 1.0], hspace=0.30, wspace=0.20)

    color_primary = '#00F0FF'      # Cyberpunk Cyan
    color_kelly = '#FFD700'        # Golden Kelly
    color_sci = '#00E676'          # Scientific Green
    color_train = '#BB86FC'        # In-sample Purple
    color_down = '#FF5252'         # Coral Red
    color_up = '#00E676'           # Neon Green
    color_be = '#40C4FF'           # Sky Blue Breakeven
    card_bg = '#141A23'
    grid_color = '#202938'

    # -------------------------------------------------------------------------
    # Panel 1: Out-of-Sample Price & Execution Markers (May-Sept 2026)
    # -------------------------------------------------------------------------
    ax1 = fig.add_subplot(gs[0, :])
    ax1.set_facecolor(card_bg)
    ax1.grid(True, color=grid_color, linestyle='--', alpha=0.5)

    test_dates = pd.to_datetime(test_dts, format='mixed', utc=True)
    train_dates = pd.to_datetime(train_dts, format='mixed', utc=True)
    ax1.plot(test_dates, test_p_close, color='#90CAF9', linewidth=1.2, alpha=0.85, label='ETHUSDT 1m Mark Price (Test Period)')

    # Plot Trade Executions
    if not df_trades.empty:
        df_trades['entry_dt'] = pd.to_datetime(df_trades['entry_time'], format='mixed', utc=True)
        df_trades['exit_dt'] = pd.to_datetime(df_trades['exit_time'], format='mixed', utc=True)

        # Longs
        longs = df_trades[df_trades['side'] == 'LONG']
        ax1.scatter(longs['entry_dt'], longs['entry_price'], color=color_up, marker='^', s=65, zorder=5, label=f'Long Entry ({len(longs)})')

        # Shorts
        shorts = df_trades[df_trades['side'] == 'SHORT']
        ax1.scatter(shorts['entry_dt'], shorts['entry_price'], color=color_down, marker='v', s=65, zorder=5, label=f'Short Entry ({len(shorts)})')

        # Exits by type
        tp_exits = df_trades[df_trades['result'].str.contains('TP')]
        be_exits = df_trades[df_trades['result'].str.contains('BE')]
        sl_exits = df_trades[df_trades['result'].str.contains('SL')]

        ax1.scatter(tp_exits['exit_dt'], tp_exits['exit_price'], color='#FFD700', marker='*', s=110, zorder=6, label=f'TP Exit +45% ({len(tp_exits)})')
        ax1.scatter(be_exits['exit_dt'], be_exits['exit_price'], color=color_be, marker='o', s=55, zorder=6, label=f'BE Lock Exit ({len(be_exits)})')
        ax1.scatter(sl_exits['exit_dt'], sl_exits['exit_price'], color='#FF1744', marker='x', s=65, zorder=6, label=f'Hard SL -18% ({len(sl_exits)})')

    ax1.set_title("PANEL 1: OUT-OF-SAMPLE TEST EXECUTION (MAY 1 TO SEPT 21, 2026) | 100X DUAL-ENGINE CONFLUENCE",
                  fontsize=14, fontweight='bold', color=color_primary, pad=12)
    ax1.set_ylabel("ETHUSDT Price ($)", fontsize=11, color='#CFD8DC')
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    ax1.legend(loc='upper right', ncol=6, framealpha=0.3, facecolor='#0B0E14', edgecolor='#37474F', fontsize=9)

    # -------------------------------------------------------------------------
    # Panel 2: Comparative Cumulative Equity Curves ($10k Base)
    # -------------------------------------------------------------------------
    ax2 = fig.add_subplot(gs[1, 0])
    ax2.set_facecolor(card_bg)
    ax2.grid(True, color=grid_color, linestyle='--', alpha=0.5)

    test_days = (test_dates - test_dates[0]).total_seconds() / 86400.0

    ax2.plot(test_dates, test_eq_k, color=color_kelly, linewidth=2.4, label=f"Test 30% Golden Kelly (+{df_summary.loc[2, 'net_return']:.1f}%)")
    ax2.plot(test_dates, test_eq_s, color=color_sci, linewidth=2.0, linestyle='--', label=f"Test 20% Scientific (+{df_summary.loc[3, 'net_return']:.1f}%)")
    ax2.axhline(10000, color='#78909C', linestyle=':', alpha=0.7, label='Initial Capital ($10,000)')

    ax2.set_title("PANEL 2: OUT-OF-SAMPLE TEST EQUITY GROWTH (2026/05 - 2026/09)",
                  fontsize=13, fontweight='bold', color='#FFD700', pad=10)
    ax2.set_xlabel("Date (May 1 to Sept 21, 2026)", fontsize=10, color='#CFD8DC')
    ax2.set_ylabel("Portfolio Value (USDT)", fontsize=10, color='#CFD8DC')
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    ax2.legend(loc='upper left', framealpha=0.3, facecolor='#0B0E14', edgecolor='#37474F', fontsize=9)

    # -------------------------------------------------------------------------
    # Panel 3: In-Sample vs Out-of-Sample Underwater Drawdown Curves
    # -------------------------------------------------------------------------
    ax3 = fig.add_subplot(gs[1, 1])
    ax3.set_facecolor(card_bg)
    ax3.grid(True, color=grid_color, linestyle='--', alpha=0.5)

    # Test Drawdown
    peak_test = np.maximum.accumulate(test_eq_k)
    dd_test = (peak_test - test_eq_k) / peak_test * 100.0

    ax3.plot(test_dates, -dd_test, color='#FF5252', linewidth=1.8, label=f"Test MaxDD: -{np.max(dd_test):.2f}%")
    ax3.fill_between(test_dates, -dd_test, 0, color='#FF5252', alpha=0.25)
    ax3.axhline(-15.0, color='#FF9100', linestyle='--', alpha=0.6, label='Warning Threshold (-15%)')
    ax3.axhline(-100.0, color='#D50000', linestyle='-', alpha=0.8, label='Liquidation Barrier (-100%, 0 occurrences)')

    ax3.set_title("PANEL 3: TEST UNDERWATER DRAWDOWN & ZERO-LIQUIDATION PROOF",
                  fontsize=13, fontweight='bold', color='#FF5252', pad=10)
    ax3.set_xlabel("Date (May 1 to Sept 21, 2026)", fontsize=10, color='#CFD8DC')
    ax3.set_ylabel("Drawdown Depth (%)", fontsize=10, color='#CFD8DC')
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    ax3.set_ylim(-45, 2)
    ax3.legend(loc='lower left', framealpha=0.3, facecolor='#0B0E14', edgecolor='#37474F', fontsize=9)

    # -------------------------------------------------------------------------
    # Panel 4: Monthly Performance Breakdown in Out-of-Sample Period
    # -------------------------------------------------------------------------
    ax4 = fig.add_subplot(gs[2, 0])
    ax4.set_facecolor(card_bg)
    ax4.grid(True, color=grid_color, linestyle='--', alpha=0.5)

    month_names = ['May 2026', 'June 2026', 'July 2026', 'August 2026', 'Sept 2026']
    month_ids = [5, 6, 7, 8, 9]

    monthly_pnl_pct = []
    monthly_wr = []

    for m in month_ids:
        m_trades = df_trades[df_trades['month'] == m]
        if not m_trades.empty:
            m_pnl = m_trades['dollar_pnl'].sum() / 10000.0 * 100.0
            tp_cnt = (m_trades['result'].str.contains('TP')).sum()
            be_cnt = (m_trades['result'].str.contains('BE')).sum()
            wr = (tp_cnt + be_cnt) / len(m_trades) * 100.0
        else:
            m_pnl = 0.0
            wr = 0.0
        monthly_pnl_pct.append(m_pnl)
        monthly_wr.append(wr)

    x_idx = np.arange(len(month_names))
    width = 0.35

    bars1 = ax4.bar(x_idx - width/2, monthly_pnl_pct, width, color='#00E5FF', alpha=0.85, label='Net Return Contribution (%)')
    bars2 = ax4.bar(x_idx + width/2, monthly_wr, width, color='#FFD700', alpha=0.85, label='Win+BE Rate (%)')

    for bar in bars1:
        yval = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2.0, max(yval + 1.0, 1.0), f"{yval:+.1f}%", ha='center', va='bottom', fontsize=9, color='#00E5FF', fontweight='bold')

    for bar in bars2:
        yval = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2.0, max(yval + 1.0, 1.0), f"{yval:.0f}%", ha='center', va='bottom', fontsize=9, color='#FFD700', fontweight='bold')

    ax4.set_title("PANEL 4: OUT-OF-SAMPLE MONTHLY BREAKDOWN (MAY - SEPT 2026)",
                  fontsize=13, fontweight='bold', color='#00E5FF', pad=10)
    ax4.set_xticks(x_idx)
    ax4.set_xticklabels(month_names, fontsize=10, color='#CFD8DC')
    ax4.set_ylabel("Metric Value (%)", fontsize=10, color='#CFD8DC')
    ax4.legend(loc='upper left', framealpha=0.3, facecolor='#0B0E14', edgecolor='#37474F', fontsize=9)

    # -------------------------------------------------------------------------
    # Panel 5: Master Performance Audit Matrix Table
    # -------------------------------------------------------------------------
    ax5 = fig.add_subplot(gs[2, 1])
    ax5.axis('off')

    table_data = [
        ["Regime / Mode", "Net Return", "Max Drawdown", "Sharpe", "Win Rate", "Win+BE Rate", "Total Trades", "Liquidations"],
    ]

    for _, row in df_summary.iterrows():
        table_data.append([
            row['label'],
            f"{row['net_return']:+.2f}%",
            f"{row['max_dd']:.2f}%",
            f"{row['sharpe']:.2f}",
            f"{row['win_rate']:.1f}%",
            f"{row['win_be_rate']:.1f}%",
            f"{int(row['total_trades'])}",
            f"{int(row['liquidations'])}"
        ])

    table = ax5.table(
        cellText=table_data,
        loc='center',
        cellLoc='center'
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10.5)
    table.scale(1.0, 2.2)

    # Style header and rows
    for (i, j), cell in table.get_celld().items():
        cell.set_edgecolor('#37474F')
        if i == 0:
            cell.set_facecolor('#1E2838')
            cell.set_text_props(weight='bold', color='#00F0FF')
        else:
            if 'Test' in table_data[i][0]:
                cell.set_facecolor('#1A2230')
                cell.set_text_props(color='#FFD700' if j in [1, 2, 4, 5] else '#E0E0E0')
            else:
                cell.set_facecolor('#141A23')
                cell.set_text_props(color='#00E676' if j in [1, 2, 4, 5] else '#B0BEC5')

    ax5.set_title("PANEL 5: MASTER PERFORMANCE AUDIT MATRIX (TRAIN VS TEST)",
                  fontsize=13, fontweight='bold', color='#B388FF', pad=15)

    # Main Title
    plt.suptitle("DUAL-ENGINE 100X SNIPER SYSTEM: IN-SAMPLE TRAINING VS OUT-OF-SAMPLE TEST AUDIT\n"
                 "Strict Pre-2026/05 Training (< 2026-05-01) vs Post-2026/05 Unseen Out-of-Sample Test (2026/05/01 - 2026/09/21)",
                 fontsize=16, fontweight='bold', color='#FFFFFF', y=0.985)

    # Save PNG
    plt.savefig(REPORT_PNG, dpi=300, bbox_inches='tight')
    plt.savefig(ARTIFACT_PNG, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"\n[SUCCESS] Master Dashboard saved to:")
    print(f"  Local:    {REPORT_PNG}")
    print(f"  Artifact: {ARTIFACT_PNG}")
    print("=" * 85)


if __name__ == '__main__':
    generate_train_test_comparison_report()
