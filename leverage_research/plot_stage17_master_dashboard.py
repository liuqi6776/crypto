"""
Plot Publication-Grade Visual Master Dashboard for Stage 17:
- Panel 1: Parametric Leverage Frontier (Net Return, Sharpe & Drawdown across 10X to 100X).
- Panel 2: Binance Vision Empirical Order Book Depth Profile on ETHUSDT ($17M - $22M within 0.2%).
- Panel 3: Empirical Slippage Curve vs Position Size ($5k to $250k) under Normal vs Stressed Liquidity.
- Panel 4: Friction Drag Anatomy (% of Target Profit Eaten by Fees & Slippage across Leverages).
- Panel 5: Enhanced 38-Feature Matrix for Direction & Volatility Dual-Model.
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
    print("=" * 80)
    print("  PLOTTING STAGE 17 MASTER DASHBOARD: LEVERAGE SWEET SPOT & EMPIRICAL SLIPPAGE")
    print("=" * 80)

    # 1. Load data
    sweet_csv = os.path.join(OUTPUT_DIR, "leverage_sweet_spot_summary.csv")
    slip_csv = os.path.join(OUTPUT_DIR, "empirical_slippage_distribution.csv")

    df_sweet = pd.read_csv(sweet_csv)
    df_slip = pd.read_csv(slip_csv)

    # Filter for 30% Kelly and 20% Sci
    df_kelly = df_sweet[df_sweet['label'].str.contains('Kelly')].sort_values('leverage')
    df_sci = df_sweet[df_sweet['label'].str.contains('Sci')].sort_values('leverage')

    # Create master figure
    fig = plt.figure(figsize=(24, 16), dpi=150)
    gs = gridspec.GridSpec(3, 2, height_ratios=[1.1, 1.0, 1.1], hspace=0.32, wspace=0.22)

    c_cyan = '#00F0FF'
    c_green = '#00FF66'
    c_red = '#FF3366'
    c_gold = '#FFD700'
    c_purple = '#BD00FF'
    c_blue = '#3399FF'

    # -------------------------------------------------------------
    # Panel 1: Leverage vs Net Return & Sharpe Ratio (The Sweet Spot)
    # -------------------------------------------------------------
    ax1 = fig.add_subplot(gs[0, 0])
    levs = df_kelly['leverage'].values
    ret_k = df_kelly['net_return'].values
    sharpe_k = df_kelly['sharpe'].values
    max_dd_k = df_kelly['max_dd'].values

    ax1_twin = ax1.twinx()
    
    line1 = ax1.plot(levs, ret_k, color=c_green, marker='o', linewidth=2.5, markersize=8, label='Net Return (%) [Kelly]')
    line2 = ax1.plot(levs, -max_dd_k, color=c_red, marker='s', linewidth=2.0, linestyle='--', markersize=6, label='Max Drawdown (-%)')
    line3 = ax1_twin.plot(levs, sharpe_k, color=c_gold, marker='^', linewidth=2.2, markersize=8, label='Sharpe Ratio')

    # Highlight Sweet Spot at 30X
    ax1.axvspan(22, 35, color=c_gold, alpha=0.15, label='Sweet Spot Zone (25X-35X)')
    ax1.scatter([30.0], [ret_k[levs == 30.0][0]], color=c_gold, s=180, zorder=5, edgecolors='white', linewidth=2)
    ax1.annotate('OPTIMAL SWEET SPOT (30X)\n+6.93% Net (Zero Blowup)\nSharpe 0.69 | Friction 7.2%',
                 xy=(30.0, ret_k[levs == 30.0][0]), xytext=(42, 5),
                 arrowprops=dict(facecolor=c_gold, shrink=0.08, width=2, headwidth=8),
                 fontsize=11, fontweight='bold', color=c_gold,
                 bbox=dict(boxstyle='round,pad=0.5', facecolor='#1A1A2E', edgecolor=c_gold, alpha=0.9))

    ax1.set_title("Panel 1: Parametric Leverage Frontier vs Friction Drag (10X to 100X)\n杠杆倍数与真实摩擦净收益前沿曲线 (30X 黄金平衡点)", fontsize=13, fontweight='bold', color='white', pad=12)
    ax1.set_xlabel("Leverage (倍数)", fontsize=11, color='white')
    ax1.set_ylabel("Net Return / Max Drawdown (%)", fontsize=11, color=c_green)
    ax1_twin.set_ylabel("Sharpe Ratio", fontsize=11, color=c_gold)
    ax1.grid(True, linestyle=':', alpha=0.3)
    ax1.set_xticks(levs)
    ax1.axhline(0, color='gray', linestyle=':', alpha=0.5)

    lines = line1 + line2 + line3
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left', fontsize=9.5, facecolor='#14141E', edgecolor='gray')

    # -------------------------------------------------------------
    # Panel 2: Friction Drag Ratio vs Leverage
    # -------------------------------------------------------------
    ax2 = fig.add_subplot(gs[0, 1])
    fric_drag = df_kelly['friction_drag_pct'].values

    bars = ax2.bar([str(int(l)) + 'x' for l in levs], fric_drag, color=c_blue, width=0.55, edgecolor='white', alpha=0.85)
    
    # Color code bars by danger
    for i, b in enumerate(bars):
        if fric_drag[i] < 6.0:
            b.set_color(c_green)
        elif fric_drag[i] < 10.0:
            b.set_color(c_gold)
        else:
            b.set_color(c_red)

    ax2.axhline(8.0, color=c_gold, linestyle='--', linewidth=2.0, label='8.0% Safe Friction Ceiling (安全摩擦红线)')
    ax2.set_title("Panel 2: Friction Drag Share of Profit Target (%)\n来回摩擦成本 (手续费+滑点) 占总目标利润比例剖析", fontsize=13, fontweight='bold', color='white', pad=12)
    ax2.set_xlabel("Leverage (倍数)", fontsize=11, color='white')
    ax2.set_ylabel("Friction Drag on Profit (%)", fontsize=11, color='white')
    ax2.grid(True, linestyle=':', alpha=0.3)

    for i, v in enumerate(fric_drag):
        ax2.text(i, v + 0.6, f"{v:.1f}%", ha='center', va='bottom', fontsize=10, fontweight='bold', color='white')

    ax2.legend(loc='upper left', fontsize=10, facecolor='#14141E', edgecolor=c_gold)

    # -------------------------------------------------------------
    # Panel 3: Empirical Order Book Depth Profile on ETHUSDT
    # -------------------------------------------------------------
    ax3 = fig.add_subplot(gs[1, 0])
    depth_layers = ['±0.2% (~$5)', '±1.0% (~$26)', '±2.0% (~$52)', '±3.0% (~$78)', '±5.0% (~$130)']
    bid_depths_m = [17.8, 76.6, 184.4, 251.0, 326.8]
    ask_depths_m = [18.6, 73.5, 169.8, 227.3, 284.5]

    x_idx = np.arange(len(depth_layers))
    w = 0.35
    ax3.bar(x_idx - w/2, bid_depths_m, width=w, color=c_green, alpha=0.85, label='Bid Depth (买盘深度 $M)')
    ax3.bar(x_idx + w/2, ask_depths_m, width=w, color=c_red, alpha=0.85, label='Ask Depth (卖盘深度 $M)')

    ax3.set_title("Panel 3: Binance Official L2 Order Book Depth Profile (ETHUSDT)\n币安官方实际订单簿各档位深度分布 ($M 美元)", fontsize=13, fontweight='bold', color='white', pad=12)
    ax3.set_xticks(x_idx)
    ax3.set_xticklabels(depth_layers, fontsize=10)
    ax3.set_ylabel("Notional Liquidity Depth ($ Millions)", fontsize=11, color='white')
    ax3.grid(True, linestyle=':', alpha=0.3)

    for i in x_idx:
        ax3.text(i - w/2, bid_depths_m[i] + 5, f"${bid_depths_m[i]:.1f}M", ha='center', fontsize=9, color=c_green, fontweight='bold')
        ax3.text(i + w/2, ask_depths_m[i] + 5, f"${ask_depths_m[i]:.1f}M", ha='center', fontsize=9, color=c_red, fontweight='bold')

    ax3.legend(loc='upper left', fontsize=10, facecolor='#14141E', edgecolor='gray')

    # -------------------------------------------------------------
    # Panel 4: Empirical Slippage Curve vs Position Size ($5k to $250k)
    # -------------------------------------------------------------
    ax4 = fig.add_subplot(gs[1, 1])
    sizes = df_slip['order_size_usd'].values / 1000.0 # in $k
    slip_norm_bps = df_slip['normal_total_slippage_bps'].values
    slip_stress_bps = df_slip['stressed_total_slippage_bps'].values
    slip_norm_usd = df_slip['eth_price_slip_normal_usd'].values
    slip_stress_usd = df_slip['eth_price_slip_stressed_usd'].values

    ax4.plot(sizes, slip_norm_bps, marker='o', color=c_cyan, linewidth=2.5, markersize=8, label='Normal Liquidity Slippage (基准滑点 bps)')
    ax4.plot(sizes, slip_stress_bps, marker='^', color='#FF9900', linewidth=2.5, markersize=8, linestyle='--', label='Stressed Thin Liquidity (极端插针抽离滑点 bps)')

    ax4.set_title("Panel 4: Empirical Slippage Curve vs Position Size ($5k to $250k)\n不同开仓资金规模下的实测冲击滑点曲线 (ETHUSDT)", fontsize=13, fontweight='bold', color='white', pad=12)
    ax4.set_xlabel("Order Notional Size ($k USD)", fontsize=11, color='white')
    ax4.set_ylabel("Realized Total Slippage (Basis Points / bps)", fontsize=11, color=c_cyan)
    ax4.grid(True, linestyle=':', alpha=0.3)

    # Annotate typical sizes
    ax4.annotate(f"10k Size: {slip_norm_bps[1]:.2f} bps (~${slip_norm_usd[1]:.2f}/ETH)",
                 xy=(10, slip_norm_bps[1]), xytext=(25, 0.70),
                 arrowprops=dict(facecolor=c_cyan, shrink=0.08, width=1.5, headwidth=6),
                 fontsize=10, color=c_cyan, fontweight='bold')

    ax4.annotate(f"50k Size: {slip_norm_bps[3]:.2f} bps (~${slip_norm_usd[3]:.2f}/ETH)",
                 xy=(50, slip_norm_bps[3]), xytext=(70, 0.90),
                 arrowprops=dict(facecolor=c_cyan, shrink=0.08, width=1.5, headwidth=6),
                 fontsize=10, color=c_cyan, fontweight='bold')

    ax4.legend(loc='lower right', fontsize=10, facecolor='#14141E', edgecolor='gray')

    # -------------------------------------------------------------
    # Panel 5: Enhanced 38-Feature Architecture & Upgrades
    # -------------------------------------------------------------
    ax5 = fig.add_subplot(gs[2, :])
    ax5.axis('off')

    table_data = [
        ["Feature Category / 模块类别", "Feature Count", "Existing 30 Features Summary / 现有特征概览", "Newly Engineered 8 Features (Stage 17) / 新增核心特征与物理意义"],
        ["1. Multi-Horizon Returns / 收益", "6", "ret_1m, 3m, 5m, 15m, 30m, 60m (短中长趋势动量)", "已覆盖微观与波段多层级动量 (Micro & Swing Multi-Horizon)"],
        ["2. Moving Average Deviation / 均线", "3", "dist_ema_10, 30, 60 (均线偏离度与均值回归距离)", "已覆盖长短周期发散 (Trend Dispersion & Reversion)"],
        ["3. Volatility & Range / 波动与极值", "4", "atr_14_pct, parkinson_vol_15m, hl_spread, stoch_pos_60m", "★ garman_klass_ratio: GK波动比，精准区分跳空与连续波动"],
        ["4. Flow & Micro-Order Book / 资金流", "7", "taker_buy_ratio, ofi_1m..15m, trade_size, rel_trade_intensity", "★ depth_imbalance_ratio: L2十档挂单倾斜比，量化多空护城河厚度"],
        ["5. Value Anchoring / 价值锚定", "1", "dist_vwap_24h (日内大资金成交量加权持仓成本线)", "★ dist_poc_daily: 距离当日筹码峰(POC)引力偏离度"],
        ["6. Micro-Wick Needle / 微观影线", "3", "wick_ratio, lower_wick_ratio, upper_wick_ratio (上下影线探底比)", "★ spread_spike_ratio: 盘口价差骤扩倍数，做市商撤单与插针警报"],
        ["7. Clean Corridor / 纯净走廊", "1", "tau_vol (帕金森波动率膨胀与影线插针双重惩罚评分)", "★ whale_burst_intensity: Top 1%大额市价单爆发占比，主力扫损识别"],
        ["8. Cross-Asset & Alpha / 跨资产联动", "5", "ret_vs_btc 1m/5m/15m, ofi_vs_btc_5m, beta_residual_1m", "★ cross_lead_lag_sol_5m: 引入高Beta资产SOL对ETH的短线领先突破信号\n★ cvd_divergence_15m: 累积净主动买盘与价格背离，识别主力吸收吸筹\n★ funding_velocity_1h: 永续合约资金费率与多空挤压溢价变化率"]
    ]

    tbl = ax5.table(cellText=table_data, loc='center', cellLoc='left', colWidths=[0.16, 0.08, 0.36, 0.40])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10.0)
    tbl.scale(1.0, 1.45)

    # Style table cells
    for (row, col), cell in tbl.get_celld().items():
        cell.set_edgecolor('#333344')
        if row == 0:
            cell.set_facecolor('#1E2235')
            cell.set_text_props(weight='bold', color=c_cyan, size=10.5)
        else:
            if col == 3:
                cell.set_facecolor('#15222E')
                cell.set_text_props(color='#99EEFF')
            elif col == 0:
                cell.set_facecolor('#1A1A26')
                cell.set_text_props(weight='bold', color='white')
            else:
                cell.set_facecolor('#12121A')
                cell.set_text_props(color='#CCCCCC')

    ax5.set_title("Panel 5: Complete 38-Feature Architecture Breakdown (Audited 30 + 8 Newly Engineered Direction & Volatility Features)\nTransformer 38维特征全景矩阵：方向精准预测 (Value) 与微观防插针 (Volatility) 协同架构",
                  fontsize=13, fontweight='bold', color='white', pad=15)

    # Global Title
    fig.suptitle("STAGE 17 QUANTITATIVE MASTER DASHBOARD: LEVERAGE SWEET SPOT, EMPIRICAL SLIPPAGE & FEATURE ENGINEERING\n阶段17量化研报：抗摩擦杠杆平衡点探索、币安真实滑点分布与Transformer 38维特征工程体系",
                 fontsize=17, fontweight='bold', color='white', y=0.99)

    out_png = os.path.join(OUTPUT_DIR, "stage17_master_dashboard.png")
    art_png = os.path.join(ARTIFACT_DIR, "stage17_master_dashboard.png")

    plt.savefig(out_png, dpi=150, bbox_inches='tight')
    plt.savefig(art_png, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"\n[OK] Master dashboard generated successfully!")
    print(f"  Local file: {out_png}")
    print(f"  Artifact:   {art_png}")

if __name__ == '__main__':
    main()
