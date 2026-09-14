# -*- coding: utf-8 -*-
"""
Generate publication-quality comparison chart (Phase 16):
Continuous Baseline vs. Institutional Trial Mode vs. Buy & Hold Benchmark.
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

from crypto_quant.portfolio import MultiAssetPortfolioEngine

data_dir = root_dir / 'data'
docs_dir = root_dir / 'docs'
pred_path = root_dir / 'predictions' / 'test_predictions.parquet'
df_pred = pd.read_parquet(pred_path)

onchain_path = data_dir / 'eth_onchain_sentiment_daily.parquet'
df_onchain = pd.read_parquet(onchain_path)
if df_onchain.index.tz is not None:
    df_onchain.index = df_onchain.index.tz_localize(None)

funding_path = data_dir / 'binance_funding_8h.parquet'
df_funding = pd.read_parquet(funding_path)
if df_funding.index.tz is not None:
    df_funding.index = df_funding.index.tz_localize(None)

tokens = ['ETHUSDT', 'SOLUSDT']
mkt_dict = {t: pd.read_parquet(data_dir / f'{t}_4h_2020_2026.parquet') for t in tokens}
pred_dict = {t: df_pred[f'{t}_pred_4h'] for t in tokens}
fund_dict = {t: df_funding[t] for t in tokens}
fng_series = df_onchain['fng_score']

# 1. Run Continuous Simulations
engine_trial = MultiAssetPortfolioEngine(trial_mode=True)
res_trial = engine_trial.run(mkt_dict, pred_dict, fund_dict, fng_series)

engine_base = MultiAssetPortfolioEngine(trial_mode=False)
res_base = engine_base.run(mkt_dict, pred_dict, fund_dict, fng_series)

common_idx = res_trial.common_index
sub_idx = common_idx[common_idx >= '2024-01-01']

cum_trial = res_trial.combined_equity.loc[sub_idx] / res_trial.combined_equity.loc[sub_idx].iloc[0]
cum_base = res_base.combined_equity.loc[sub_idx] / res_base.combined_equity.loc[sub_idx].iloc[0]

# Buy & Hold 50/50 Benchmark
bh_eth = mkt_dict['ETHUSDT'].loc[sub_idx, 'close'] / mkt_dict['ETHUSDT'].loc[sub_idx, 'close'].iloc[0]
bh_sol = mkt_dict['SOLUSDT'].loc[sub_idx, 'close'] / mkt_dict['SOLUSDT'].loc[sub_idx, 'close'].iloc[0]
cum_bh = 0.5 * bh_eth + 0.5 * bh_sol

dd_trial = (cum_trial - cum_trial.cummax()) / cum_trial.cummax()
dd_base = (cum_base - cum_base.cummax()) / cum_base.cummax()
dd_bh = (cum_bh - cum_bh.cummax()) / cum_bh.cummax()

pos_eth = res_trial.asset_results['ETHUSDT'].position_series.loc[sub_idx].abs()
pos_sol = res_trial.asset_results['SOLUSDT'].position_series.loc[sub_idx].abs()
comb_pos = 0.5 * pos_eth + 0.5 * pos_sol

# Plot 3-panel figure
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 11), sharex=True, gridspec_kw={'height_ratios': [2.2, 1.3, 1.0]})

# Panel 1: Cumulative Return
ax1.plot(cum_trial.index, cum_trial.values, color='#00a86b', linewidth=2.4, label=f'Trial Mode (Continuous Intrabar, 5D Downsizing): Ret={cum_trial.iloc[-1]-1:+.1%}, MDD={dd_trial.min():.1%}')
ax1.plot(cum_base.index, cum_base.values, color='#1f77b4', linewidth=1.8, linestyle='--', label=f'Baseline (Continuous Intrabar, Unconstrained): Ret={cum_base.iloc[-1]-1:+.1%}, MDD={dd_base.min():.1%}')
ax1.plot(cum_bh.index, cum_bh.values, color='#888888', linewidth=1.4, linestyle=':', label=f'50/50 Buy & Hold Benchmark: Ret={cum_bh.iloc[-1]-1:+.1%}, MDD={dd_bh.min():.1%}')

ax1.axvline(pd.Timestamp('2026-01-01'), color='#d9534f', linestyle='--', alpha=0.7, label='2026 Post-hoc Development / Stress-Test Period')
ax1.set_title('Continuous Intrabar Execution: Institutional Trial-Trading vs. Baseline (2024-2026 Full Horizon)', fontsize=14, fontweight='bold', pad=12)
ax1.set_ylabel('Cumulative NAV (Base 1.0)', fontsize=11, fontweight='bold')
ax1.legend(loc='upper left', frameon=True, framealpha=0.9, fontsize=9.5)
ax1.grid(True, linestyle=':', alpha=0.6)

# Panel 2: Underwater Drawdown Comparison
ax2.plot(dd_base.index, dd_base.values * 100, color='#1f77b4', linewidth=1.5, linestyle='--', alpha=0.8, label=f'Baseline MDD: {dd_base.min()*100:.1f}%')
ax2.plot(dd_bh.index, dd_bh.values * 100, color='#888888', linewidth=1.2, linestyle=':', alpha=0.6, label=f'Buy & Hold MDD: {dd_bh.min()*100:.1f}%')
ax2.fill_between(dd_trial.index, dd_trial.values * 100, 0, color='#00a86b', alpha=0.35, label=f'Trial Mode MDD: {dd_trial.min()*100:.1f}%')
ax2.set_ylabel('Drawdown (%)', fontsize=11, fontweight='bold')
ax2.set_ylim(-65, 5)
ax2.legend(loc='lower left', frameon=True, framealpha=0.9, fontsize=9.5)
ax2.grid(True, linestyle=':', alpha=0.6)

# Panel 3: Active Exposure Sizing
rolling_exp = comb_pos.rolling(18).mean()
ax3.plot(comb_pos.index, rolling_exp.values, color='#e67e22', linewidth=1.6, label=f'Dynamic Exposure (Mean: {comb_pos.mean():.2f}x)')
ax3.axhline(0.25, color='#888888', linestyle=':', label='25% Defensive Trial Sizing')
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
