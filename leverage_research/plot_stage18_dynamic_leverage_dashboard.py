"""
Plot Publication-Grade Master Dashboard for Stage 18:
- Panel 1: Out-of-Sample Cumulative Equity Curves (May 1 - Sept 21, 2026) across 4 Leverage Policies.
- Panel 2: Underwater Drawdown Dynamics (%) showing Downside Risk Suppression.
- Panel 3: Empirical Distribution of Model Self-Adaptive Dynamic Leverage ($L_t^* \in [15\text{X}, 75\text{X}]$).
- Panel 4: Profit Factor & Trade-by-Trade Dollar PnL Anatomy (Avg Win vs Avg Loss).
- Panel 5: Master Key Performance Metrics & Sharpe/Calmar Comparative Audit Table.
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import Patch

plt.style.use('dark_background')
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

OUTPUT_DIR = r"c:\Users\liuqi\crypto\leverage_research\charts"
ARTIFACT_DIR = r"C:\Users\liuqi\.gemini\antigravity\brain\85b8b55c-f9a4-4530-ae89-7a324bd99842"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(ARTIFACT_DIR, exist_ok=True)

def main():
    print("=" * 85)
    print("  PLOTTING STAGE 18 MASTER DASHBOARD: DYNAMIC LEVERAGE TRANSFORMER VS STATIC")
    print("=" * 85)

    summary_csv = os.path.join(OUTPUT_DIR, "dynamic_vs_static_leverage_summary.csv")
    curves_npz = os.path.join(OUTPUT_DIR, "dynamic_vs_static_curves.npz")
    trades_csv = os.path.join(OUTPUT_DIR, "dynamic_vs_static_trades.csv")

    if not os.path.exists(summary_csv) or not os.path.exists(curves_npz):
        print("[ERROR] Required backtest results not found yet. Run backtest first!")
        return

    df_summary = pd.read_csv(summary_csv)
    curves_data = np.load(curves_npz)
    df_trades = pd.read_csv(trades_csv) if os.path.exists(trades_csv) else pd.DataFrame()

    fig = plt.figure(figsize=(24, 18), dpi=150)
    gs = gridspec.GridSpec(3, 2, height_ratios=[1.15, 1.05, 0.95], hspace=0.32, wspace=0.22)

    c_neon = '#00FF66'      # Dynamic leverage (hero color)
    c_gold = '#FFD700'      # 30X sweet spot
    c_cyan = '#00F0FF'      # 20X conservative
    c_red = '#FF3366'       # 100X high leverage
    c_purple = '#BD00FF'
    c_blue = '#3399FF'

    color_map = {
        'Track 1: Fixed 100X': c_red,
        'Track 2: Fixed 30X (Sweet Spot)': c_gold,
        'Track 3: Fixed 20X (Conservative)': c_cyan,
        'Track 4: Transformer Dynamic Leverage (0X-75X) ★★★': c_neon
    }

    # -------------------------------------------------------------
    # Panel 1: Out-of-Sample Cumulative Equity Curves
    # -------------------------------------------------------------
    ax1 = fig.add_subplot(gs[0, 0])
    track_names = list(curves_data.keys())

    # Generate approximate time axis (May 1 to Sept 21, 2026, 206,545 bars)
    n_bars = len(curves_data[track_names[0]])
    dates = pd.date_range(start='2026-05-01', periods=n_bars, freq='1min')

    # Downsample for snappy plotting
    step = 60 # 1-hour resolution
    d_sampled = dates[::step]

    for name in track_names:
        c = curves_data[name][::step]
        col = color_map.get(name, '#FFFFFF')
        lw = 3.0 if 'Dynamic' in name else 2.0
        alpha = 1.0 if 'Dynamic' in name else 0.8
        zorder = 5 if 'Dynamic' in name else 3
        lbl = name.replace(' (0X-75X) ★★★', ' [Model Dynamic]').replace(' (Sweet Spot)', '').replace(' (Conservative)', '')
        ax1.plot(d_sampled, c, label=lbl, color=col, linewidth=lw, alpha=alpha, zorder=zorder)

    ax1.axhline(10000.0, color='gray', linestyle=':', linewidth=1.2, alpha=0.7, label='Initial Capital ($10,000)')
    ax1.set_title("Panel 1: Out-of-Sample Cumulative Equity Curves (May 1 - Sept 21, 2026)\n2026年5月后样本外回测资金曲线 (端到端动态杠杆 vs 静态杠杆)", fontsize=13, fontweight='bold', color='white', pad=12)
    ax1.set_xlabel("Date (2026)", fontsize=11, color='white')
    ax1.set_ylabel("Portfolio Equity ($)", fontsize=11, color='white')
    ax1.legend(loc='upper left', fontsize=10, facecolor='#1A1A2E', edgecolor='gray')
    ax1.grid(True, linestyle='--', alpha=0.25)
    ax1.yaxis.set_major_formatter('${x:,.0f}')

    # -------------------------------------------------------------
    # Panel 2: Underwater Drawdown Dynamics (%)
    # -------------------------------------------------------------
    ax2 = fig.add_subplot(gs[0, 1])

    for name in track_names:
        curve = curves_data[name][::step]
        peaks = np.maximum.accumulate(curve)
        dd = (curve - peaks) / peaks * 100.0
        col = color_map.get(name, '#FFFFFF')
        lw = 2.5 if 'Dynamic' in name else 1.8
        alpha = 0.9 if 'Dynamic' in name else 0.6
        zorder = 5 if 'Dynamic' in name else 3
        lbl = name.replace(' (0X-75X) ★★★', ' [Model Dynamic]').replace(' (Sweet Spot)', '').replace(' (Conservative)', '')
        ax2.plot(d_sampled, dd, label=lbl, color=col, linewidth=lw, alpha=alpha, zorder=zorder)
        if 'Dynamic' in name:
            ax2.fill_between(d_sampled, dd, 0, color=col, alpha=0.15)

    ax2.set_title("Panel 2: Underwater Drawdown Dynamics (%)\n回撤深度与下行风险控制 (动态杠杆规避插针与爆仓风险)", fontsize=13, fontweight='bold', color='white', pad=12)
    ax2.set_xlabel("Date (2026)", fontsize=11, color='white')
    ax2.set_ylabel("Drawdown (%)", fontsize=11, color='white')
    ax2.legend(loc='lower left', fontsize=10, facecolor='#1A1A2E', edgecolor='gray')
    ax2.grid(True, linestyle='--', alpha=0.25)

    # -------------------------------------------------------------
    # Panel 3: Distribution of Model-Selected Dynamic Leverages ($L_t^*$)
    # -------------------------------------------------------------
    ax3 = fig.add_subplot(gs[1, 0])

    dyn_trades = df_trades[df_trades['track'].str.contains('Dynamic')] if not df_trades.empty else pd.DataFrame()
    if not dyn_trades.empty and 'leverage' in dyn_trades.columns:
        lev_values = dyn_trades['leverage'].values
        # Histogram
        n_bins = np.linspace(5, 35, 16)
        counts, bins, patches = ax3.hist(lev_values, bins=n_bins, color=c_neon, edgecolor='black', alpha=0.8, rwidth=0.85)
        
        # Color bins according to regime
        for bin_left, patch in zip(bins[:-1], patches):
            if bin_left < 15:
                patch.set_facecolor(c_cyan)
            elif bin_left < 25:
                patch.set_facecolor(c_gold)
            else:
                patch.set_facecolor(c_red)

        mean_l = np.mean(lev_values)
        med_l = np.median(lev_values)
        ax3.axvline(mean_l, color='white', linestyle='--', linewidth=2, label=f'Mean Leverage: {mean_l:.1f}X')
        ax3.axvline(med_l, color=c_gold, linestyle='-', linewidth=2, label=f'Median Leverage: {med_l:.1f}X')

        # Annotations of regimes
        ax3.axvspan(5, 15, color=c_cyan, alpha=0.10)
        ax3.axvspan(15, 25, color=c_gold, alpha=0.10)
        ax3.axvspan(25, 35, color=c_red, alpha=0.10)

        max_c = max(counts) if len(counts) > 0 and max(counts) > 0 else 10
        ax3.text(10, max_c * 0.9, "Learned Policy\n(5X-15X)\nSharpe-Optimized", ha='center', color=c_cyan, fontsize=9, fontweight='bold')
        ax3.text(20, max_c * 0.9, "Conservative\n(15X-25X)\nChoppy Market", ha='center', color=c_gold, fontsize=9, fontweight='bold')
        ax3.text(30, max_c * 0.9, "Aggressive\n(25X-35X)\nHigh Conviction", ha='center', color=c_red, fontsize=9, fontweight='bold')

        ax3.legend(loc='upper right', fontsize=10, facecolor='#1A1A2E', edgecolor='gray')
    else:
        ax3.text(0.5, 0.5, "Dynamic Leverage Distribution", ha='center', va='center', color='white', fontsize=12)

    ax3.set_title("Panel 3: Transformer Dynamic Leverage Policy Distribution ($L_t^* \\in [2X, 75X]$)\n模型端到端自适应杠杆输出分布 (按波动与通道置信度分层)", fontsize=13, fontweight='bold', color='white', pad=12)
    ax3.set_xlabel("Output Leverage ($L_t^*$ 倍数)", fontsize=11, color='white')
    ax3.set_ylabel("Number of Trades (交易次数)", fontsize=11, color='white')
    ax3.grid(True, linestyle='--', alpha=0.25)

    # -------------------------------------------------------------
    # Panel 4: Trade-by-Trade Dollar PnL & Profit Factor Comparison
    # -------------------------------------------------------------
    ax4 = fig.add_subplot(gs[1, 1])

    x = np.arange(len(df_summary))
    width = 0.22

    avg_win = df_summary['avg_win_pnl'].values
    avg_loss = np.abs(df_summary['avg_loss_pnl'].values)
    avg_trade = df_summary['avg_trade_pnl'].values
    pf = df_summary['profit_factor'].values

    ax4_twin = ax4.twinx()

    b1 = ax4.bar(x - width, avg_win, width, label='Avg Win PnL ($)', color=c_neon, alpha=0.85)
    b2 = ax4.bar(x, -avg_loss, width, label='Avg Loss PnL (-$)', color=c_red, alpha=0.85)
    b3 = ax4.bar(x + width, avg_trade, width, label='Avg Net Trade PnL ($)', color=c_cyan, alpha=0.85)

    p1 = ax4_twin.plot(x, pf, color=c_gold, marker='s', linewidth=2.5, markersize=8, label='Profit Factor (盈亏比)')

    short_labels = [row['label'].replace('Track ', 'T').split(':')[0] + "\n" + row['label'].split(':')[1].split('(')[0].strip() for _, row in df_summary.iterrows()]
    ax4.set_xticks(x)
    ax4.set_xticklabels(short_labels, fontsize=10, color='white')

    ax4.set_title("Panel 4: Trade PnL Anatomy & Profit Factor across Leverage Tracks\n单笔盈亏结构与盈亏比对比 (平均盈利 vs 平均亏损 vs 盈亏比)", fontsize=13, fontweight='bold', color='white', pad=12)
    ax4.set_ylabel("Average Dollar PnL ($)", fontsize=11, color='white')
    ax4_twin.set_ylabel("Profit Factor (Gross Win / Gross Loss)", fontsize=11, color=c_gold)
    ax4.grid(True, linestyle='--', alpha=0.25)

    # Combined legends
    lines_4, labels_4 = ax4.get_legend_handles_labels()
    lines_4t, labels_4t = ax4_twin.get_legend_handles_labels()
    ax4.legend(lines_4 + lines_4t, labels_4 + labels_4t, loc='upper left', fontsize=9, facecolor='#1A1A2E', edgecolor='gray')

    # -------------------------------------------------------------
    # Panel 5: Master Comparative Audit Table
    # -------------------------------------------------------------
    ax5 = fig.add_subplot(gs[2, :])
    ax5.axis('off')

    table_data = []
    headers = [
        "Track Strategy Name\n策略轨迹与杠杆模式",
        "Leverage Policy\n杠杆规则",
        "Final Equity\n最终资金",
        "Net Return\n净收益率",
        "Max DD\n最大回撤",
        "Sharpe\n夏普比率",
        "Calmar\n卡玛比率",
        "Profit Factor\n盈亏比",
        "Trades\n总笔数",
        "Win+BE %\n胜率+保本",
        "Avg Trade\n笔均盈亏",
        "Avg Win ROE\n均胜ROE",
        "Avg Loss ROE\n均损ROE"
    ]

    col_widths = [0.15, 0.09, 0.07, 0.07, 0.07, 0.06, 0.06, 0.07, 0.06, 0.07, 0.07, 0.08, 0.08]

    for _, row in df_summary.iterrows():
        clean_lbl = row['label'].replace(' ★★★', '').replace('Track 4: Transformer Dynamic Leverage (0X-75X)', 'Track 4: Dynamic Policy (0-75X)')
        lev_str = f"{row.get('mean_leverage', 0):.1f}X ({row.get('min_leverage', 0):.1f}-{row.get('max_leverage', 0):.1f}X)" if 'Dynamic' in row['label'] else f"{row.get('mean_leverage', 0):.0f}X Fixed"
        table_data.append([
            clean_lbl,
            lev_str,
            f"${row['final_equity']:,.2f}",
            f"{row['net_return']:+.2f}%",
            f"{row['max_dd']:.2f}%",
            f"{row['sharpe']:.2f}",
            f"{row['calmar']:.2f}",
            f"{row['profit_factor']:.2f}",
            f"{int(row['total_trades'])}",
            f"{row['win_be_rate']:.1f}%",
            f"${row['avg_trade_pnl']:+,.2f}",
            f"{row['avg_win_roe']:+.2f}%",
            f"{row['avg_loss_roe']:+.2f}%"
        ])

    table = ax5.table(
        cellText=table_data,
        colLabels=headers,
        colWidths=col_widths,
        loc='center',
        cellLoc='center'
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10.5)
    table.scale(1.0, 2.1)

    # Style header and rows
    for (i, j), cell in table.get_celld().items():
        cell.set_edgecolor('#333355')
        if i == 0:
            cell.set_facecolor('#1E1E38')
            cell.set_text_props(color='#FFD700', fontweight='bold')
        else:
            row_idx = i - 1
            if 'Dynamic' in df_summary.iloc[row_idx]['label']:
                cell.set_facecolor('#1A3828')
                cell.set_text_props(color='#00FF66', fontweight='bold')
            elif '30X' in df_summary.iloc[row_idx]['label']:
                cell.set_facecolor('#2A2A1A')
                cell.set_text_props(color='#FFD700')
            elif '100X' in df_summary.iloc[row_idx]['label']:
                cell.set_facecolor('#2E1820')
                cell.set_text_props(color='#FF8899')
            else:
                cell.set_facecolor('#18202A')
                cell.set_text_props(color='#00CCFF')

    ax5.set_title("Panel 5: Comprehensive Out-of-Sample Performance Audit (May 1 - Sept 21, 2026, 206,545 1m Bars)\n策略综合绩效审计总表 (自适应动态杠杆 vs 固定静态杠杆)", fontsize=13, fontweight='bold', color='white', pad=10)

    # Supertitle
    plt.suptitle("CRYPTO LEVERAGE RESEARCH - STAGE 18 MASTER DASHBOARD\nEnd-to-End Policy Network: Model Dynamic Leverage ($L_t^*$) vs Static Benchmarks",
                 fontsize=16, fontweight='bold', color='#00FFCC', y=0.995)

    out_png = os.path.join(OUTPUT_DIR, "stage18_master_dashboard.png")
    plt.savefig(out_png, dpi=150, bbox_inches='tight')
    plt.close()

    # Also copy to artifact directory
    artifact_png = os.path.join(ARTIFACT_DIR, "stage18_master_dashboard.png")
    import shutil
    shutil.copy2(out_png, artifact_png)

    print(f"\n[OK] Master Dashboard successfully saved:")
    print(f"  Local Path:    {out_png}")
    print(f"  Artifact Path: {artifact_png}")

if __name__ == '__main__':
    main()
