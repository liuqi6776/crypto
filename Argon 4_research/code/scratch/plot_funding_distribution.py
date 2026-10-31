import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import os

os.makedirs('reports', exist_ok=True)

df = pd.read_parquet('scratch/funding_dataset_with_returns.parquet')

# Bins definition
bins = [
    -np.inf, -0.01, -0.005, -0.002, -0.0005, 0.0, 
    0.0002, 0.0005, 0.001, 0.003, 0.005, np.inf
]
labels = [
    '<= -1.0%', '-1.0%~-0.5%', '-0.5%~-0.2%', '-0.2%~-0.05%', '-0.05%~0%',
    '0%~+0.02%', '+0.02%~+0.05%', '+0.05%~+0.1%', '+0.1%~+0.3%', '+0.3%~+0.5%', '>= +0.5%'
]
df['bin'] = pd.cut(df['fundingRate'], bins=bins, labels=labels, right=False)

stats = []
for b in labels:
    sub = df[df['bin'] == b]
    n = len(sub)
    if n == 0:
        continue
    f1 = sub['ret_fwd_1'].dropna() * 100
    f3 = sub['ret_fwd_3'].dropna() * 100
    stats.append({
        'bin': b,
        'N': n,
        'win_8h': (f1 > 0).mean() * 100,
        'mean_8h': f1.mean(),
        'median_8h': f1.median(),
        'win_24h': (f3 > 0).mean() * 100,
        'mean_24h': f3.mean(),
        'median_24h': f3.median(),
    })

res = pd.DataFrame(stats)

# Plotting
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
plt.subplots_adjust(hspace=0.25)

x = np.arange(len(res))
width = 0.35

# Chart 1: Win Rate (% Price Increase)
bars1 = ax1.bar(x - width/2, res['win_8h'], width, label='Next 8h Rise Prob (%)', color='#2b5c8f', alpha=0.85)
bars2 = ax1.bar(x + width/2, res['win_24h'], width, label='Next 24h Rise Prob (%)', color='#e06666', alpha=0.85)
ax1.axhline(50, color='gray', linestyle='--', linewidth=1, label='50% Baseline')
ax1.set_ylabel('Probability of Price Increase (%)', fontsize=12)
ax1.set_title('Subsequent Price Increase Probability by Funding Rate Bracket (Binance Futures)', fontsize=14, fontweight='bold')
ax1.legend(loc='upper left', frameon=True)
ax1.set_ylim(0, 100)
ax1.grid(axis='y', linestyle=':', alpha=0.6)

for bar in bars1:
    h = bar.get_height()
    ax1.annotate(f'{h:.1f}%', (bar.get_x() + bar.get_width()/2, h + 1.5), ha='center', va='bottom', fontsize=8)
for bar in bars2:
    h = bar.get_height()
    ax1.annotate(f'{h:.1f}%', (bar.get_x() + bar.get_width()/2, h + 1.5), ha='center', va='bottom', fontsize=8)

# Chart 2: Mean Return (%)
bars3 = ax1 = ax2.bar(x - width/2, res['mean_8h'], width, label='Next 8h Mean Return (%)', color='#1b7837', alpha=0.85)
bars4 = ax2.bar(x + width/2, res['mean_24h'], width, label='Next 24h Mean Return (%)', color='#762a83', alpha=0.85)
ax2.axhline(0, color='black', linestyle='-', linewidth=1)
ax2.set_ylabel('Mean Return (%)', fontsize=12)
ax2.set_title('Subsequent Mean Price Return by Funding Rate Bracket', fontsize=14, fontweight='bold')
ax2.set_xticks(x)
ax2.set_xticklabels(res['bin'], rotation=25, ha='right', fontsize=10)
ax2.legend(loc='upper left', frameon=True)
ax2.grid(axis='y', linestyle=':', alpha=0.6)

for bar in bars3:
    h = bar.get_height()
    va = 'bottom' if h >= 0 else 'top'
    offset = 0.3 if h >= 0 else -0.8
    ax2.annotate(f'{h:+.1f}%', (bar.get_x() + bar.get_width()/2, h + offset), ha='center', va=va, fontsize=8)
for bar in bars4:
    h = bar.get_height()
    va = 'bottom' if h >= 0 else 'top'
    offset = 0.3 if h >= 0 else -1.5
    ax2.annotate(f'{h:+.1f}%', (bar.get_x() + bar.get_width()/2, h + offset), ha='center', va=va, fontsize=8)

plt.tight_layout()
chart_path = 'reports/funding_rate_distribution_analysis.png'
plt.savefig(chart_path, dpi=200)
print(f"Chart saved to {chart_path}")
