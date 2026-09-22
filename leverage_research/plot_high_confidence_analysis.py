# -*- coding: utf-8 -*-
"""
High Confidence (0.60 - 0.90) Analysis & Visualization
0.60 至 0.90 极高置信度数理上限剖析与收益变化曲线
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False

charts_dir = r"c:\Users\liuqi\crypto\leverage_research\charts"
oos_npz = r"D:\Convertible_Bond_data\crypto_data\val_predictions_2025_2026.npz"
data = np.load(oos_npz, allow_pickle=True)

prob = data['prob_gate'] # (M, K, 3)
p_long = prob[:, :, 1].flatten()
p_short = prob[:, :, 2].flatten()
p_dir_max = np.maximum(p_long, p_short)

cond_long = prob[:, :, 1] / (prob[:, :, 1] + prob[:, :, 2] + 1e-8)
cond_short = prob[:, :, 2] / (prob[:, :, 1] + prob[:, :, 2] + 1e-8)
cond_max = np.maximum(cond_long, cond_short).flatten()

fig, axes = plt.subplots(1, 2, figsize=(15, 6), dpi=180)

# Panel 1: Probability Density & The 0.58 Softmax Ceiling
ax1 = axes[0]
ax1.hist(p_dir_max, bins=80, density=True, alpha=0.6, color='#3b82f6', label='Raw Directional Probability $P(Dir)$')
ax1.hist(cond_max, bins=80, density=True, alpha=0.5, color='#10b981', label='Conditional Conviction $P(Long|Active)$')
ax1.axvline(0.577, color='red', linestyle='--', linewidth=1.8, label='Raw 3-Class Ceiling (~0.58)')
ax1.axvline(0.60, color='purple', linestyle=':', linewidth=1.5, label='User Threshold 0.60')
ax1.axvline(0.90, color='orange', linestyle=':', linewidth=1.5, label='User Threshold 0.90')
ax1.set_title("Panel A: Probability Distribution & Softmax Ceiling in 3-Class System", fontsize=12, fontweight='bold')
ax1.set_xlabel("Probability / Confidence Score", fontsize=10)
ax1.set_ylabel("Empirical Density", fontsize=10)
ax1.legend(loc='upper right', fontsize=9)
ax1.grid(True, linestyle='--', alpha=0.4)

# Panel 2: Performance Evolution across 0.60 - 0.90
ax2 = axes[1]
taus = [0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]
trades = [612, 738, 768, 249, 5, 0, 0]
returns = [-85.69, -85.18, -85.72, -37.97, -0.63, 0.0, 0.0]

ax2_twin = ax2.twinx()
line1 = ax2.plot(taus, returns, color='#dc2626', marker='o', linewidth=2.2, label='Net Return (%)')
line2 = ax2_twin.bar(np.array(taus), trades, width=0.02, alpha=0.3, color='#6366f1', label='Trade Count (15 Months)')

ax2.axhline(0, color='gray', linestyle='--', alpha=0.5)
ax2.set_title("Panel B: Conditional Confidence (0.60 - 0.90) vs Return & Trade Frequency", fontsize=12, fontweight='bold')
ax2.set_xlabel("Conditional Confidence Threshold", fontsize=10)
ax2.set_ylabel("Net Cumulative Return (%)", color='#dc2626', fontsize=10)
ax2_twin.set_ylabel("Executed Trade Count", color='#6366f1', fontsize=10)

lines = line1 + [line2]
labels = [l.get_label() for l in lines]
ax2.legend(lines, labels, loc='center left', fontsize=9)
ax2.grid(True, linestyle='--', alpha=0.4)

plt.suptitle("Crypto 20X Leverage: Deep Dive into High Confidence Regimes (0.60 - 0.90)", fontsize=13, fontweight='bold')
plt.tight_layout()

out_plot = os.path.join(charts_dir, "high_confidence_analysis_060_090.png")
plt.savefig(out_plot, bbox_inches='tight')
plt.close()
print(f"High confidence analysis chart saved -> {out_plot}")
