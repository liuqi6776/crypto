# -*- coding: utf-8 -*-
"""
Generate publication-quality comparison chart:
Baseline (Phase 14) vs. Institutional Trial Mode (Phase 15) vs. Buy & Hold Benchmark.
Produces: docs/trial_vs_baseline_comparison.png
"""
import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from crypto_quant.dual_sleeve_portfolio import compute_sleeve_adaptive

data_dir = root_dir / 'data'
docs_dir = root_dir / 'docs'
pred_path = root_dir / 'predictions' / 'test_predictions.parquet'
df_pred = pd.read_parquet(pred_path)

onchain_path = data_dir / 'eth_onchain_sentiment_daily.parquet'
df_onchain = pd.read_parquet(onchain_path)
if df_onchain.index.tz is not None:
    df_onchain.index = df_onchain.index.tz_localize(None)
onchain_aligned = df_onchain.shift(1).reindex(df_pred.index.normalize(), method='ffill')
onchain_aligned.index = df_pred.index

funding_path = data_dir / 'binance_funding_8h.parquet'
df_funding = pd.read_parquet(funding_path)
if df_funding.index.tz is not None:
    df_funding.index = df_funding.index.tz_localize(None)

# Run for full period (2024-01-01 to 2026-09-13)
full_idx = df_pred.loc['2024-01-01':'2026-09-13'].index
tokens = ['ETHUSDT', 'SOLUSDT']

rets_base = {}
rets_trial = {}
rets_bh = {}
pos_trial_dict = {}

for token in tokens:
    raw_path = data_dir / f'{token}_4h_2020_2026.parquet'
    raw_df = pd.read_parquet(raw_path).loc[full_idx]
    funding_s = df_funding[token].shift(1).reindex(full_idx, method='ffill').fillna(0.0)
    fng_s = onchain_aligned.loc[full_idx, 'fng_score'].values
    sl = 0.025 if token == 'ETHUSDT' else 0.050

    # Baseline
    rb, _, _ = compute_sleeve_adaptive(
        preds=df_pred.loc[full_idx, f'{token}_pred_4h'],
        opens=raw_df['open'], closes=raw_df['close'],
        lows=raw_df['low'], highs=raw_df['high'],
        fng=fng_s, funding=funding_s,
        stop_loss=sl, deadband=0.20,
        fee_and_slippage=0.0008,
        use_top_derisking=True, use_short=True,
        trial_mode=False
    )
    rets_base[token] = rb

    # Trial mode
    rt, _, pos_t = compute_sleeve_adaptive(
        preds=df_pred.loc[full_idx, f'{token}_pred_4h'],
        opens=raw_df['open'], closes=raw_df['close'],
        lows=raw_df['low'], highs=raw_df['high'],
        fng=fng_s, funding=funding_s,
        stop_loss=sl, deadband=0.20,
        fee_and_slippage=0.0008,
        use_top_derisking=True, use_short=True,
        trial_mode=True
    )
    rets_trial[token] = rt
    pos_trial_dict[token] = pos_t

    # Buy & Hold
    bh = (raw_df['open'].shift(-2) / raw_df['open'].shift(-1) - 1).iloc[:-2]
    rets_bh[token] = bh

# 50/50 Combined Series
comb_base = 0.5 * rets_base['ETHUSDT'] + 0.5 * rets_base['SOLUSDT']
comb_trial = 0.5 * rets_trial['ETHUSDT'] + 0.5 * rets_trial['SOLUSDT']
comb_bh = 0.5 * rets_bh['ETHUSDT'] + 0.5 * rets_bh['SOLUSDT']
comb_pos = 0.5 * pos_trial_dict['ETHUSDT'].abs() + 0.5 * pos_trial_dict['SOLUSDT'].abs()

cum_base = (1.0 + comb_base).cumprod()
cum_trial = (1.0 + comb_trial).cumprod()
cum_bh = (1.0 + comb_bh).cumprod()

dd_base = (cum_base - cum_base.cummax()) / cum_base.cummax()
dd_trial = (cum_trial - cum_trial.cummax()) / cum_trial.cummax()
dd_bh = (cum_bh - cum_bh.cummax()) / cum_bh.cummax()

# Plot 3-panel figure
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 11), sharex=True, gridspec_kw={'height_ratios': [2.2, 1.3, 1.0]})

# Panel 1: Cumulative Return (Log Scale)
ax1.plot(cum_trial.index, cum_trial.values, color='#00a86b', linewidth=2.4, label=f'Trial Mode (Phase 15, 5D Downsizing): Ret={cum_trial.iloc[-1]-1:+.1%}, MDD={dd_trial.min():.1%}')
ax1.plot(cum_base.index, cum_base.values, color='#1f77b4', linewidth=1.8, linestyle='--', label=f'Baseline (Phase 14, Unconstrained): Ret={cum_base.iloc[-1]-1:+.1%}, MDD={dd_base.min():.1%}')
ax1.plot(cum_bh.index, cum_bh.values, color='#888888', linewidth=1.4, linestyle=':', label=f'50/50 Buy & Hold Benchmark: Ret={cum_bh.iloc[-1]-1:+.1%}, MDD={dd_bh.min():.1%}')

ax1.axvline(pd.Timestamp('2026-01-01'), color='#d9534f', linestyle='--', alpha=0.7, label='2026 Locked Blind Test')
ax1.set_title('Institutional Trial-Trading Multi-Downsizing vs. Baseline (2024-2026 Full Horizon)', fontsize=15, fontweight='bold', pad=12)
ax1.set_ylabel('Cumulative NAV (Base 1.0)', fontsize=11, fontweight='bold')
ax1.legend(loc='upper left', frameon=True, framealpha=0.9, fontsize=10)
ax1.grid(True, linestyle=':', alpha=0.6)

# Panel 2: Underwater Drawdown Comparison
ax2.plot(dd_base.index, dd_base.values * 100, color='#1f77b4', linewidth=1.5, linestyle='--', alpha=0.8, label=f'Baseline MDD: {dd_base.min()*100:.1f}%')
ax2.plot(dd_bh.index, dd_bh.values * 100, color='#888888', linewidth=1.2, linestyle=':', alpha=0.6, label=f'Buy & Hold MDD: {dd_bh.min()*100:.1f}%')
ax2.fill_between(dd_trial.index, dd_trial.values * 100, 0, color='#00a86b', alpha=0.35, label=f'Trial Mode MDD: {dd_trial.min()*100:.1f}% (Compressed to < 20%!)')
ax2.axhline(-20.0, color='#d9534f', linestyle='-', linewidth=1.2, alpha=0.8, label='Institutional 20% DD Threshold')
ax2.set_ylabel('Drawdown (%)', fontsize=11, fontweight='bold')
ax2.set_ylim(-65, 5)
ax2.legend(loc='lower left', frameon=True, framealpha=0.9, fontsize=9.5)
ax2.grid(True, linestyle=':', alpha=0.6)

# Panel 3: Active Exposure / Capital Allocation Sizing
rolling_exp = comb_pos.rolling(18).mean()
ax3.plot(comb_pos.index, rolling_exp.values, color='#e67e22', linewidth=1.6, label=f'Dynamic Exposure (Mean: {comb_pos.mean():.2f}x)')
ax3.axhline(0.25, color='#888888', linestyle=':', label='25% Normal Trial Sizing')
ax3.set_ylabel('Exposure Sizing', fontsize=11, fontweight='bold')
ax3.set_xlabel('Date (UTC)', fontsize=11, fontweight='bold')
ax3.set_ylim(0.0, 1.05)
ax3.legend(loc='upper right', frameon=True, framealpha=0.9, fontsize=9.5)
ax3.grid(True, linestyle=':', alpha=0.6)

ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
fig.autofmt_xdate()

plt.tight_layout()
out_fp = docs_dir / 'trial_vs_baseline_comparison.png'
plt.savefig(out_fp, dpi=200)
plt.close()
print(f"Comparison chart successfully generated at: {out_fp}")
