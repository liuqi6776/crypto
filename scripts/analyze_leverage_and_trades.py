# -*- coding: utf-8 -*-
"""
Analysis of Leverage Feasibility, Per-Trade Return Distribution, and Leveraged Equity Curves
for Ethereum (ETH) and Solana (SOL) Spatio-Temporal Transformer Strategies.
Now upgraded with Dynamic Adaptive Thresholds, Hard Stop-Loss & Cooldown (Phase 11).
"""
import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from scipy import stats

# Set plot style and font
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

root_dir = 'C:/Users/liuqi/crypto'
sys.path.insert(0, root_dir)

# Output paths
artifacts_dir = 'C:/Users/liuqi/.gemini/antigravity/brain/16cb006d-026f-4685-aa82-3db788cd48f6'
docs_dir = os.path.join(root_dir, 'docs')
os.makedirs(docs_dir, exist_ok=True)

# 1. Load Data
df_pred = pd.read_parquet(os.path.join(root_dir, 'predictions', 'test_predictions.parquet'))
val_df = df_pred.loc['2024-01-01':'2025-12-31']
val_idx = val_df.index

data_dir = os.path.join(root_dir, 'data')
raw_dfs = {t: pd.read_parquet(os.path.join(data_dir, f'{t}_4h_2020_2026.parquet')).loc[val_idx] for t in ['ETHUSDT', 'SOLUSDT']}

df_onchain = pd.read_parquet(os.path.join(data_dir, 'eth_onchain_sentiment_daily.parquet'))
if df_onchain.index.tz is not None:
    df_onchain.index = df_onchain.index.tz_localize(None)
onchain_aligned = df_onchain.shift(1).reindex(val_idx.normalize(), method='ffill')
onchain_aligned.index = val_idx

fng_arr = onchain_aligned['fng_score'].values
stb_flow_arr = onchain_aligned['stb_flow_7d'].values

df_basis = pd.read_parquet(os.path.join(data_dir, 'binance_basis_4h.parquet'))
df_funding = pd.read_parquet(os.path.join(data_dir, 'binance_funding_8h.parquet'))
if df_basis.index.tz is not None:
    df_basis.index = df_basis.index.tz_localize(None)
if df_funding.index.tz is not None:
    df_funding.index = df_funding.index.tz_localize(None)


from crypto_quant.dual_sleeve_portfolio import compute_sleeve_adaptive


def extract_discrete_trades_and_leverage(token, leverage_list=[1.0, 1.5, 2.0, 3.0]):
    preds = val_df[f'{token}_pred_4h']
    opens = raw_dfs[token]['open']
    closes = raw_dfs[token]['close']
    lows = raw_dfs[token]['low']
    highs = raw_dfs[token]['high']

    funding_series = df_funding[token].shift(1).reindex(val_idx, method='ffill').fillna(0.0)
    sl = 0.025 if token == 'ETHUSDT' else 0.050

    # Execute Phase 13 Symmetrical Long/Short Adaptive Sleeve
    sleeve_rets_1x, trades_df, pos_series = compute_sleeve_adaptive(
        preds=preds, opens=opens, closes=closes,
        lows=lows, highs=highs,
        fng=fng_arr, stb=stb_flow_arr,
        funding=funding_series,
        stop_loss=sl, deadband=0.20,
        use_top_derisking=True, use_short=True
    )

    pos = pos_series.values
    o_series = pd.Series(opens.values, index=val_idx)
    rets_oto = (o_series.shift(-2) / o_series.shift(-1) - 1).values
    trade_signals = pos_series.diff().abs().fillna(0.0).values
    funding_s = funding_series.values

    # Benchmark Buy & Hold
    bh_rets = (o_series.shift(-2) / o_series.shift(-1) - 1).iloc[:-2]
    bh_cum = (1 + bh_rets).cumprod()

    lev_results = {
        'Buy & Hold': {
            'cum': bh_cum,
            'total_ret': bh_cum.iloc[-1] - 1.0,
            'cagr': (bh_cum.iloc[-1]) ** (1 / (len(bh_rets) / 2190)) - 1.0,
            'mdd': ((bh_cum - bh_cum.cummax()) / bh_cum.cummax()).min(),
            'daily_sharpe': bh_cum.resample('1D').last().ffill().pct_change().dropna().mean() / (bh_cum.resample('1D').last().ffill().pct_change().dropna().std() + 1e-8) * np.sqrt(365),
            'calmar': ((bh_cum.iloc[-1]) ** (1 / (len(bh_rets) / 2190)) - 1.0) / abs(((bh_cum - bh_cum.cummax()) / bh_cum.cummax()).min())
        }
    }

    dates_series = opens.index[:-2]

    rets_oto_aligned = rets_oto[:-2]
    funding_s_aligned = funding_s[:-2]

    for lev in leverage_list:
        cost_bar = trade_signals * 0.0005 * lev
        # Funding carry: Short earns positive funding from crowded retail longs!
        funding_carry = -pos * funding_s_aligned * lev
        # Margin interest on borrowed leverage capital:
        borrow_interest = np.abs(pos) * 0.00005 * max(0.0, lev - 1.0)
        strat_rets = pos * rets_oto_aligned * lev - cost_bar + funding_carry - borrow_interest

        cum = pd.Series((1 + strat_rets).cumprod(), index=dates_series)
        total_ret = cum.iloc[-1] - 1.0
        cagr = (1 + total_ret) ** (1 / (len(strat_rets) / 2190)) - 1.0 if total_ret > -1 else -1.0
        cum_max = cum.cummax()
        dd = (cum - cum_max) / cum_max
        mdd = dd.min()

        daily_equity = cum.resample('1D').last().ffill()
        daily_rets = daily_equity.pct_change().dropna()
        daily_sharpe = daily_rets.mean() / (daily_rets.std() + 1e-8) * np.sqrt(365)
        calmar = cagr / abs(mdd) if abs(mdd) > 1e-6 else 0.0

        lev_results[f'{lev:.1f}x Leverage' if lev > 1.0 else '1.0x (Original)'] = {
            'cum': cum,
            'drawdown': dd,
            'total_ret': total_ret,
            'cagr': cagr,
            'mdd': mdd,
            'daily_sharpe': daily_sharpe,
            'calmar': calmar
        }

    return trades_df, lev_results, dates_series


print("Computing ETH and SOL trade metrics and leverage simulation (Upgraded Phase 11)...")
eth_trades, eth_lev, eth_dates = extract_discrete_trades_and_leverage('ETHUSDT', [1.0, 1.5, 2.0, 3.0])
sol_trades, sol_lev, sol_dates = extract_discrete_trades_and_leverage('SOLUSDT', [1.0, 1.5, 2.0, 3.0])


# ==============================================================================
# PLOT 1: Trade Return Distributions (ETH & SOL)
# ==============================================================================
fig, axes = plt.subplots(2, 2, figsize=(16, 12))

colors = {'ETH': '#2980b9', 'SOL': '#8e44ad', 'win': '#27ae60', 'loss': '#e74c3c'}

for idx, (token, trades_df, color) in enumerate([('ETHUSDT', eth_trades, colors['ETH']), ('SOLUSDT', sol_trades, colors['SOL'])]):
    net_rets = trades_df['net_ret'] * 100.0  # percentage
    wins = net_rets[net_rets > 0]
    losses = net_rets[net_rets <= 0]
    win_rate = len(wins) / len(net_rets) * 100.0
    profit_factor = wins.sum() / abs(losses.sum()) if abs(losses.sum()) > 0 else np.nan
    payoff_ratio = wins.mean() / abs(losses.mean()) if abs(losses.mean()) > 0 else np.nan
    skewness = stats.skew(net_rets)
    kurt = stats.kurtosis(net_rets)

    # Top: Histogram & KDE
    ax = axes[0, idx]
    bins = np.linspace(min(net_rets.min(), -8.0), max(net_rets.max(), 12.0), 36)
    n_counts, _, patches = ax.hist(net_rets, bins=bins, density=True, alpha=0.65, edgecolor='black', linewidth=0.5)

    for patch, left_edge in zip(patches, bins[:-1]):
        if left_edge >= 0:
            patch.set_facecolor(colors['win'])
        else:
            patch.set_facecolor(colors['loss'])

    # KDE line
    kde = stats.gaussian_kde(net_rets)
    x_grid = np.linspace(bins[0], bins[-1], 200)
    ax.plot(x_grid, kde(x_grid), color='black', linewidth=2.2, label='KDE Density Fit')

    ax.axvline(0, color='red', linestyle='--', linewidth=1.5, alpha=0.8)
    ax.axvline(net_rets.mean(), color='blue', linestyle='-', linewidth=2.0, label=f'Mean Net: {net_rets.mean():+.2f}%')
    ax.axvline(net_rets.median(), color='orange', linestyle=':', linewidth=2.0, label=f'Median: {net_rets.median():+.2f}%')

    longs = trades_df[trades_df['type'] == 'LONG']
    shorts = trades_df[trades_df['type'] == 'SHORT']
    win_rate_long = (longs['net_ret'] > 0).mean() * 100.0 if len(longs) > 0 else 0.0
    win_rate_short = (shorts['net_ret'] > 0).mean() * 100.0 if len(shorts) > 0 else 0.0

    stats_text = (
        f"Total Trades: {len(trades_df)} (Long: {len(longs)}, Short: {len(shorts)})\n"
        f"Win Rate: {win_rate:.1f}% (L: {win_rate_long:.1f}%, S: {win_rate_short:.1f}%)\n"
        f"Profit Factor: {profit_factor:.2f}\n"
        f"Payoff Ratio: {payoff_ratio:.2f}\n"
        f"Mean Ret: {net_rets.mean():+.2f}%\n"
        f"Std Dev: {net_rets.std():.2f}%\n"
        f"Skewness: {skewness:+.2f}\n"
        f"Max Win: {net_rets.max():+.2f}%\n"
        f"Max Loss: {net_rets.min():+.2f}% (Stop-Loss Capped)"
    )
    ax.text(0.04, 0.95, stats_text, transform=ax.transAxes, verticalalignment='top',
            fontsize=9.2, fontfamily='monospace', bbox=dict(boxstyle='round,pad=0.5', facecolor='#ffffff', edgecolor='#7f8c8d', alpha=0.9))

    ax.set_title(f"{token[:3]} Per-Trade Net Return Distribution (2024-2025)\nSymmetrical Long/Short True Alpha (Phase 13)", fontsize=12, fontweight='bold')
    ax.set_xlabel('Per-Trade Net Return [%] (After 0.10% Taker Fee & Funding Cost)', fontsize=10)
    ax.set_ylabel('Probability Density', fontsize=10)
    ax.legend(loc='upper right', fontsize=9)
    ax.grid(True, linestyle='--', alpha=0.4)

    # Bottom: Boxplot
    ax_box = axes[1, idx]
    bp = ax_box.boxplot(net_rets, vert=False, patch_artist=True,
                        boxprops=dict(facecolor=color, alpha=0.7, color='black'),
                        whiskerprops=dict(color='black', linewidth=1.2),
                        capprops=dict(color='black', linewidth=1.2),
                        medianprops=dict(color='yellow', linewidth=2.2),
                        flierprops=dict(marker='o', color=color, alpha=0.6, markersize=5))

    ax_box.axvline(0, color='red', linestyle='--', linewidth=1.5, alpha=0.8)
    ax_box.set_xlabel('Per-Trade Net Return [%]', fontsize=10)
    ax_box.set_yticks([1])
    ax_box.set_yticklabels([token[:3]])
    ax_box.grid(True, linestyle='--', alpha=0.4)
    ax_box.set_title(f"{token[:3]} Return Dispersion & Outliers (Boxplot)", fontsize=11, fontweight='bold')

plt.tight_layout()
plot1_path = os.path.join(artifacts_dir, 'eth_sol_trade_distribution.png')
plot1_docs = os.path.join(docs_dir, 'eth_sol_trade_distribution.png')
fig.savefig(plot1_path, dpi=300, bbox_inches='tight')
fig.savefig(plot1_docs, dpi=300, bbox_inches='tight')
plt.close(fig)
print(f"Saved Trade Distribution Plot to {plot1_path}")


# ==============================================================================
# PLOT 2: Leveraged Equity Curves & Drawdown Comparison
# ==============================================================================
fig, axes = plt.subplots(2, 2, figsize=(17, 12), sharex='col')

lev_colors = {
    'Buy & Hold': '#7f8c8d',
    '1.0x (Original)': '#2ecc71',
    '1.5x Leverage': '#3498db',
    '2.0x Leverage': '#9b59b6',
    '3.0x Leverage': '#e74c3c'
}

for col_idx, (token, lev_res) in enumerate([('ETHUSDT', eth_lev), ('SOLUSDT', sol_lev)]):
    ax_top = axes[0, col_idx]
    ax_bot = axes[1, col_idx]

    # Benchmark
    bh = lev_res['Buy & Hold']
    ax_top.plot(bh['cum'].index, bh['cum'].values, label=f"Buy & Hold (Tot: {bh['total_ret']*100:+.1f}%, MDD: {bh['mdd']*100:.1f}%)",
                color=lev_colors['Buy & Hold'], linewidth=1.5, linestyle=':')

    bh_dd = (bh['cum'] - bh['cum'].cummax()) / bh['cum'].cummax()
    ax_bot.plot(bh['cum'].index, bh_dd.values * 100.0, color=lev_colors['Buy & Hold'], linewidth=1.2, linestyle=':')

    for name in ['1.0x (Original)', '1.5x Leverage', '2.0x Leverage', '3.0x Leverage']:
        r = lev_res[name]
        c = lev_colors[name]
        ax_top.plot(r['cum'].index, r['cum'].values,
                    label=f"{name} (Tot: {r['total_ret']*100:+.1f}%, Sh: {r['daily_sharpe']:.2f}, MDD: {r['mdd']*100:.1f}%)",
                    color=c, linewidth=2.0 if '1.5x' in name or '1.0x' in name else 1.4)
        ax_bot.plot(r['drawdown'].index, r['drawdown'].values * 100.0,
                    label=f"{name} (Max DD: {r['mdd']*100:.1f}%)", color=c, linewidth=1.4)

    ax_top.set_title(f"{token} Leverage Equity Curves (2024-2025)\nSymmetrical Long/Short Alpha Strategy (Log Scale)", fontsize=12, fontweight='bold')
    ax_top.set_ylabel('Cumulative Portfolio Equity [Log Scale]', fontsize=10)
    ax_top.set_yscale('log')
    ax_top.yaxis.set_major_formatter(ticker.ScalarFormatter())
    ax_top.grid(True, linestyle='--', alpha=0.4)
    ax_top.legend(loc='upper left', fontsize=9.2)

    ax_bot.set_title(f"{token} Underwater Drawdown Comparison [%]", fontsize=11, fontweight='bold')
    ax_bot.set_ylabel('Drawdown [%]', fontsize=10)
    ax_bot.set_xlabel('Date (2024 - 2025)', fontsize=10)
    ax_bot.axhline(-20, color='gray', linestyle='--', alpha=0.5)
    ax_bot.axhline(-35, color='orange', linestyle='--', alpha=0.5)
    ax_bot.axhline(-50, color='red', linestyle='--', alpha=0.5)
    ax_bot.grid(True, linestyle='--', alpha=0.4)
    ax_bot.legend(loc='lower left', fontsize=8.8)

plt.tight_layout()
plot2_path = os.path.join(artifacts_dir, 'eth_sol_leverage_comparison.png')
plot2_docs = os.path.join(docs_dir, 'eth_sol_leverage_comparison.png')
fig.savefig(plot2_path, dpi=300, bbox_inches='tight')
fig.savefig(plot2_docs, dpi=300, bbox_inches='tight')
plt.close(fig)
print(f"Saved Leverage Comparison Plot to {plot2_path}")


# ==============================================================================
# PRINT PERFORMANCE SUMMARY TABLE
# ==============================================================================
print("\n" + "="*80)
print("LEVERAGE BACKTEST COMPARISON SUMMARY (2024-2025) - UPGRADED WITH STOP-LOSS")
print("="*80)
for token, lev_res in [('ETHUSDT', eth_lev), ('SOLUSDT', sol_lev)]:
    print(f"\n--- {token} ---")
    for name in ['Buy & Hold', '1.0x (Original)', '1.5x Leverage', '2.0x Leverage', '3.0x Leverage']:
        r = lev_res[name]
        print(f"  {name:<18} | Total Ret: {r['total_ret']*100:+7.2f}% | CAGR: {r['cagr']*100:+6.2f}% | MDD: {r['mdd']*100:6.2f}% | Daily Sharpe: {r['daily_sharpe']:5.2f} | Calmar: {r['calmar']:5.2f}")
