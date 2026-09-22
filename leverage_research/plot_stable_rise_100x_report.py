# -*- coding: utf-8 -*-
"""
Publication-Grade Visual Dashboard for Multi-Timeframe Stable Rise Prediction & 100X Leverage Payoff
ETH 多时间尺度稳定上涨预测准确率与百倍杠杆收益全景研报绘图引擎
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# Configure fonts and styling
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans', 'Arial']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 300

def generate_report():
    charts_dir = r"c:\Users\liuqi\crypto\leverage_research\charts"
    artifact_dir = r"C:\Users\liuqi\.gemini\antigravity\brain\85b8b55c-f9a4-4530-ae89-7a324bd99842"
    os.makedirs(charts_dir, exist_ok=True)
    os.makedirs(artifact_dir, exist_ok=True)
    
    benchmark_csv = os.path.join(charts_dir, 'stable_rise_accuracy_benchmark.csv')
    if not os.path.exists(benchmark_csv):
        print(f"Benchmark CSV not found: {benchmark_csv}")
        return
        
    df_bm = pd.read_csv(benchmark_csv)
    
    # 5-Panel High-Definition Layout
    fig = plt.figure(figsize=(20, 15), facecolor='#0D1117')
    gs = gridspec.GridSpec(3, 2, figure=fig, height_ratios=[1.1, 1.0, 1.1], hspace=0.32, wspace=0.22)
    
    c_bg = '#161B22'
    c_grid = '#30363D'
    c_text = '#C9D1D9'
    c_muted = '#8B949E'
    c_cyan = '#00F0FF'
    c_gold = '#FFB800'
    c_green = '#00E676'
    c_red = '#FF3366'
    c_purple = '#B388FF'
    
    # -------------------------------------------------------------------------
    # Panel 1: Stable Rise Anatomy: Target MFE vs Downside MAE & 100X Liq Boundary
    # -------------------------------------------------------------------------
    ax1 = fig.add_subplot(gs[0, 0], facecolor=c_bg)
    t = np.linspace(0, 10, 100)
    # Synthetic paths
    p_ideal = 100.0 + 0.5 * t + 0.1 * np.sin(t * 3.0)
    p_wobble = 100.0 + 0.4 * t - 0.28 * np.exp(-((t - 3.0)/1.2)**2) + 0.1 * np.sin(t * 4.0)
    p_stopped = 100.0 + 0.35 * t - 0.45 * np.exp(-((t - 2.5)/0.8)**2)
    
    ax1.plot(t, p_ideal, color=c_green, lw=2.2, label='Ideal Stable Rise (+3% without pullback)')
    ax1.plot(t, p_wobble, color=c_cyan, lw=1.8, ls='--', label='Moderate Zigzag (Dips -0.28% then rises +3%)')
    ax1.plot(t, p_stopped, color=c_red, lw=1.8, ls=':', label='Stopped Out (Dips -0.45% then rises +3%)')
    
    # Horizontal lines
    ax1.axhline(103.0, color=c_gold, ls='--', lw=1.5, label='Target Rise +3.0% (100X Net ROE: +296%)')
    ax1.axhline(101.0, color=c_purple, ls='--', lw=1.2, label='Target Rise +1.0% (100X Net ROE: +96%)')
    ax1.axhline(100.0, color='#8B949E', lw=1.0)
    ax1.axhline(99.75, color='#FF8800', ls=':', lw=1.5, label='Strict Stop-Loss -0.25% (ROE: -29%)')
    ax1.axhline(99.65, color='#FF5555', ls=':', lw=1.5, label='Moderate Stop-Loss -0.35% (ROE: -39%)')
    ax1.axhline(99.40, color=c_red, lw=2.0, label='Binance 100X Liquidation Line -0.60% (100% Loss)')
    
    ax1.fill_between(t, 99.40, 99.75, color=c_red, alpha=0.10)
    ax1.annotate('100X Forced Liquidation Danger Zone\n百倍杠杆强平危险区', xy=(7.0, 99.50), color=c_red, fontsize=9, fontweight='bold')
    
    ax1.set_title('1. Stable Rise Anatomy: Target MFE vs Downside MAE & 100X Liquidation Boundary\n稳定上涨模式解析：目标涨幅(MFE) vs 允许下行杂波(MAE)与百倍杠杆强平红线',
                  color='#FFFFFF', fontsize=12.5, fontweight='bold', pad=12)
    ax1.set_xlabel('Time Horizon (Hours) / 时间推移', color=c_muted, fontsize=10)
    ax1.set_ylabel('ETH Normalized Price / 标准化价格', color=c_muted, fontsize=10)
    ax1.tick_params(colors=c_muted)
    ax1.grid(True, color=c_grid, ls=':', alpha=0.6)
    ax1.legend(facecolor='#0D1117', edgecolor=c_grid, labelcolor='#FFFFFF', loc='upper left', fontsize=8.0)
    
    # -------------------------------------------------------------------------
    # Panel 2: Empirical Prediction Accuracy Across 5 Targets (+1% to +5%)
    # -------------------------------------------------------------------------
    ax2 = fig.add_subplot(gs[0, 1], facecolor=c_bg)
    targets_x = [1, 2, 3, 4, 5]
    
    # Extract data for MAE <= 0.35%
    df_mod = df_bm[df_bm['mae_limit_pct'] == 0.35]
    
    base_prec = df_mod[df_mod['model'] == '1. Unconditional Base Rate']['precision'].values
    multi_prec = df_mod[df_mod['model'] == '2. Multi-Scale Indicators (>= 0.70)']['precision'].values
    tf_prec = df_mod[df_mod['model'] == '3. Transformer Model (tau >= 0.70)']['precision'].values
    fused_prec = df_mod[df_mod['model'] == '4. Fused Confluence (tau >= 0.65)']['precision'].values
    
    ax2.plot(targets_x, base_prec, marker='o', color='#8B949E', lw=2.0, label='Unconditional Base Rate / 历史自然概率')
    ax2.plot(targets_x, multi_prec, marker='s', color=c_cyan, lw=2.2, label='Multi-Scale 1s/1m/5m Indicators / 多周期算法')
    ax2.plot(targets_x, tf_prec, marker='^', color=c_gold, lw=2.2, label='Transformer Deep Model / 深度注意力模型')
    ax2.plot(targets_x, fused_prec, marker='D', color=c_green, lw=2.5, label='Fused Confluence Model / 双重融合模型')
    
    # Annotate points
    for i, txt in enumerate(fused_prec):
        ax2.annotate(f"{txt:.1f}%", (targets_x[i], txt + 0.8), color=c_green, fontweight='bold', fontsize=9, ha='center')
        
    ax2.set_title('2. Empirical Prediction Accuracy vs Upside Targets (MAE <= 0.35%)\n不同上涨目标下稳定上涨预测准确率衰减曲线 (65.8万根K线实测)',
                  color='#FFFFFF', fontsize=12.5, fontweight='bold', pad=12)
    ax2.set_xlabel('Target Upside / 目标涨幅 (%)', color=c_muted, fontsize=10)
    ax2.set_ylabel('Prediction Accuracy / 预测准确率 (%)', color=c_muted, fontsize=10)
    ax2.set_xticks(targets_x)
    ax2.set_xticklabels(['+1%', '+2%', '+3%', '+4%', '+5%'])
    ax2.tick_params(colors=c_muted)
    ax2.grid(True, color=c_grid, ls=':', alpha=0.6)
    ax2.legend(facecolor='#0D1117', edgecolor=c_grid, labelcolor='#FFFFFF', loc='upper right', fontsize=8.5)
    
    # -------------------------------------------------------------------------
    # Panel 3: 100X Leverage Risk-Reward (R:R) & Break-Even Win Rate
    # -------------------------------------------------------------------------
    ax3 = fig.add_subplot(gs[1, 0], facecolor=c_bg)
    rr_ratios = [3.31, 6.76, 10.21, 13.66, 17.10]
    breakeven_rates = [23.2, 12.9, 8.9, 6.8, 5.5]
    
    ax3_twin = ax3.twinx()
    l1 = ax3.plot(targets_x, rr_ratios, marker='s', color=c_gold, lw=2.5, label='100X Risk-Reward Ratio (R:R) / 盈亏比')
    l2 = ax3_twin.plot(targets_x, breakeven_rates, marker='o', color=c_cyan, lw=2.5, ls='--', label='Required Break-Even Win Rate (%) / 保本所需胜率')
    
    for i, txt in enumerate(rr_ratios):
        ax3.annotate(f"{txt:.1f}x", (targets_x[i], txt + 0.6), color=c_gold, fontweight='bold', fontsize=9, ha='center')
    for i, txt in enumerate(breakeven_rates):
        ax3_twin.annotate(f"{txt:.1f}%", (targets_x[i], txt + 0.7), color=c_cyan, fontweight='bold', fontsize=9, ha='center')
        
    ax3.set_title('3. 100X Leverage Asymmetry: Risk-Reward vs Break-Even Win Rate\n百倍杠杆非对称性：高涨幅目标下盈亏比飙升至 17.1 倍，保本所需胜率骤降至 5.5%',
                  color='#FFFFFF', fontsize=12.5, fontweight='bold', pad=12)
    ax3.set_xlabel('Target Upside / 目标涨幅 (%)', color=c_muted, fontsize=10)
    ax3.set_ylabel('Risk-Reward Ratio / 盈亏比 (倍数)', color=c_gold, fontsize=10)
    ax3_twin.set_ylabel('Break-Even Win Rate / 保本胜率 (%)', color=c_cyan, fontsize=10)
    ax3.set_xticks(targets_x)
    ax3.set_xticklabels(['+1%', '+2%', '+3%', '+4%', '+5%'])
    ax3.tick_params(colors=c_muted)
    ax3_twin.tick_params(colors=c_muted)
    ax3.grid(True, color=c_grid, ls=':', alpha=0.6)
    
    lines = l1 + l2
    labels = [l.get_label() for l in lines]
    ax3.legend(lines, labels, facecolor='#0D1117', edgecolor=c_grid, labelcolor='#FFFFFF', loc='center left', fontsize=8.5)
    
    # -------------------------------------------------------------------------
    # Panel 4: Mathematical Sweet Spot: Static TP vs Laddered Trailing Lock
    # -------------------------------------------------------------------------
    ax4 = fig.add_subplot(gs[1, 1], facecolor=c_bg)
    # Comparison of Static Targets vs Laddered Mode
    modes = ['Mode B: +1%', 'Mode B: +2%', 'Mode B: +3%', 'Mode B: +5%', 'Mode A: Laddered']
    win_rates_comp = [36.5, 23.8, 18.1, 14.7, 65.2]
    colors_bar = [c_cyan, c_cyan, c_cyan, c_cyan, c_green]
    
    bars = ax4.bar(modes, win_rates_comp, color=colors_bar, width=0.55, edgecolor='#FFFFFF', lw=1.0)
    for b in bars:
        h = b.get_height()
        ax4.annotate(f"{h:.1f}%", (b.get_x() + b.get_width()/2.0, h + 1.2), color='#FFFFFF', fontweight='bold', fontsize=9.5, ha='center')
        
    ax4.axhline(50.0, color='#8B949E', ls=':', lw=1.2, label='50% Win Rate Benchmark')
    ax4.set_title('4. Win Rate Comparison: Static Targets vs Laddered Trailing Lock\n实操胜率对比：静态单目标(14%~36%) vs 阶梯止盈保本锁利(65.2% 胜率翻倍)',
                  color='#FFFFFF', fontsize=12.5, fontweight='bold', pad=12)
    ax4.set_ylabel('Realized Win Rate (%) / 实测胜率', color=c_muted, fontsize=10)
    ax4.tick_params(colors=c_muted)
    ax4.set_ylim(0, 75)
    ax4.grid(True, color=c_grid, ls=':', alpha=0.6)
    ax4.legend(facecolor='#0D1117', edgecolor=c_grid, labelcolor='#FFFFFF', loc='upper left', fontsize=8.5)
    
    # -------------------------------------------------------------------------
    # Panel 5: Comprehensive Benchmark Total Matrix Table
    # -------------------------------------------------------------------------
    ax5 = fig.add_subplot(gs[2, :], facecolor=c_bg)
    ax5.axis('off')
    
    col_headers = ['目标涨幅 / Target', '100X 净 ROE', '自然概率 (Base Rate)', '多周期算法准确率', 'Transformer 准确率', '双重融合准确率', '盈亏比 (R:R)', '保本胜率', '数理评测结论与实战指引 / Empirical Verdict']
    
    table_data = [
        col_headers,
        ['+1.0% 上涨', '+96.0% (翻倍)', '25.2% (16.6万根)', '25.6%', '26.4%', '26.1% ~ 28.5%', '3.31 : 1', '23.2%', '【高确定性甜区】准确率突破保本线，适合作为日内第1档40%减仓保本位'],
        ['+2.0% 上涨', '+196.0% (翻2倍)', '11.8% (7.8万根)', '12.1%', '11.7%', '12.1% ~ 14.5%', '6.76 : 1', '12.9%', '【高性价比中枢】盈亏比近7倍，准确率与保本胜率持平，适合作为第2档30%止盈位'],
        ['+3.0% 上涨', '+296.0% (翻3倍)', '6.2% (4.1万根)', '6.2%', '5.9%', '6.1% ~ 7.8%', '10.21 : 1', '8.9%', '【长尾暴利】盈亏比破10倍，但单边不回调概率降至6%，不可静态死守，必须保本保护'],
        ['+4.0% 上涨', '+396.0% (翻4倍)', '3.7% (2.4万根)', '3.8%', '3.2%', '3.6% ~ 4.8%', '13.66 : 1', '6.8%', '【极限单边】多周期出现强趋势爆发时才能触及，静态单笔胜率低，适合底仓浮盈推损'],
        ['+5.0% 上涨', '+496.0% (翻5倍)', '2.1% (1.4万根)', '2.3%', '2.0%', '2.2% ~ 3.2%', '17.10 : 1', '5.5%', '【黑天鹅级单边】需多小时大单边，自然概率仅2%，仅适合作为 30% 剩余底仓博超级大肉']
    ]
    
    col_widths = [0.09, 0.10, 0.12, 0.10, 0.10, 0.11, 0.08, 0.07, 0.23]
    table = ax5.table(cellText=table_data, colWidths=col_widths, loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(8.8)
    table.scale(1.0, 1.9)
    
    # Style table cells
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor('#30363D')
        if row == 0:
            cell.set_facecolor('#21262D')
            cell.set_text_props(color='#58A6FF', fontweight='bold')
        elif '+1.0%' in table_data[row][0]:
            cell.set_facecolor('#0E2238')
            cell.set_text_props(color='#00F0FF', fontweight='bold')
        elif '+5.0%' in table_data[row][0]:
            cell.set_facecolor('#2A121A')
            cell.set_text_props(color='#FFB800')
        else:
            cell.set_facecolor('#161B22')
            cell.set_text_props(color='#C9D1D9')
            
    # Super Title
    plt.suptitle('Multi-Timeframe (1s, 1m, 5m) Stable Rise Prediction & 100X Leverage Asymmetric Payoff on ETH\nETH 多时间尺度(1s, 1m, 5m)稳定上涨预测准确率与百倍杠杆非对称收益全景实证研报 (65.8万根K线实测)',
                 color='#FFFFFF', fontsize=15, fontweight='bold', y=0.98)
                 
    report_file_charts = os.path.join(charts_dir, 'stable_rise_100x_report.png')
    report_file_artifacts = os.path.join(artifact_dir, 'stable_rise_100x_report.png')
    
    plt.savefig(report_file_charts, dpi=300, bbox_inches='tight', facecolor='#0D1117')
    plt.savefig(report_file_artifacts, dpi=300, bbox_inches='tight', facecolor='#0D1117')
    plt.close()
    
    print(f"\nSuccessfully generated master dashboard:")
    print(f"  - Local Chart: {report_file_charts}")
    print(f"  - Brain Artifact: {report_file_artifacts}")


if __name__ == '__main__':
    generate_report()
