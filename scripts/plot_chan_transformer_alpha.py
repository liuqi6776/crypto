# -*- coding: utf-8 -*-
"""
Generate Publication-Quality Alpha Return Curves for ST-ChanTransformer (Phase 20)
===================================================================================
Produces:
1. docs/chan_transformer_alpha_curve.png
2. <artifact_dir>/chan_transformer_alpha_curve.png
3. <artifact_dir>/widget_chan_transformer_alpha.html (Base64 embedded for 100% reliable chat rendering)
"""

import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

# Styling
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from crypto_quant.chan_features import compute_chan_features
from crypto_quant.chan_transformer_engine import ChanTransformerHybridEngine
from crypto_quant.structural_trend_engine import StructuralTrendEngine
from crypto_quant.dual_sleeve_portfolio import compute_sleeve_adaptive
from scripts.render_image_widget import encode_image

docs_dir = root_dir / 'docs'
docs_dir.mkdir(parents=True, exist_ok=True)
artifact_dir = Path(os.environ.get('ANTIGRAVITY_ARTIFACTS_DIR', 'C:/Users/liuqi/.gemini/antigravity/brain/16cb006d-026f-4685-aa82-3db788cd48f6'))
artifact_dir.mkdir(parents=True, exist_ok=True)

data_dir = root_dir / 'data'
pred_path_trans = root_dir / 'predictions' / 'test_predictions.parquet'
pred_path_chan = root_dir / 'predictions' / 'chan_transformer_predictions.parquet'

df_pred_trans = pd.read_parquet(pred_path_trans)
df_pred_chan = pd.read_parquet(pred_path_chan)
eval_idx = df_pred_trans.index.intersection(df_pred_chan.index)
df_pred_trans = df_pred_trans.loc[eval_idx]
df_pred_chan = df_pred_chan.loc[eval_idx]

df_funding = pd.read_parquet(data_dir / 'binance_funding_8h.parquet')
if df_funding.index.tz is not None:
    df_funding.index = df_funding.index.tz_localize(None)

df_onchain = pd.read_parquet(data_dir / 'eth_onchain_sentiment_daily.parquet')
if df_onchain.index.tz is not None:
    df_onchain.index = df_onchain.index.tz_localize(None)
onchain_aligned = df_onchain.shift(1).reindex(eval_idx.normalize(), method='ffill')
onchain_aligned.index = eval_idx
fng_s = onchain_aligned['fng_score'].values

# Collect returns across strategies
curves = {}

for token in ['ETHUSDT', 'SOLUSDT']:
    raw_df = pd.read_parquet(data_dir / f'{token}_4h_2020_2026.parquet').loc[eval_idx]
    fund = df_funding[token].shift(1).reindex(eval_idx, method='ffill').fillna(0.0)

    # 1. Buy and Hold
    bnh_cum = raw_df['close'] / raw_df['open'].iloc[0]

    # 2. Transformer Trial Mode (P15)
    sl = 0.025 if token == 'ETHUSDT' else 0.050
    s_rets_trial, _, _ = compute_sleeve_adaptive(
        preds=df_pred_trans[f'{token}_pred_4h'],
        opens=raw_df['open'], closes=raw_df['close'],
        lows=raw_df['low'], highs=raw_df['high'],
        fng=fng_s, funding=fund,
        stop_loss=sl, deadband=0.20,
        fee_and_slippage=0.0008,
        use_top_derisking=True, use_short=True,
        trial_mode=True
    )
    cum_trial = (1.0 + s_rets_trial).cumprod()

    # 3. Macro Structural Trend (P19)
    ema200 = raw_df['close'].shift(1).ewm(span=200).mean()
    macro_bull = raw_df['close'].shift(1) > ema200
    macro_mult = pd.Series(np.where(macro_bull, 1.0, 0.5), index=eval_idx)

    eng_trend = StructuralTrendEngine(
        mode='bollinger', lookback_bars=120, exit_lookback_bars=60, atr_trailing_mult=3.0, use_short=False
    )
    rets_trend, _, _ = eng_trend.run_backtest(raw_df, token=token, funding_rate=fund, macro_multipliers=macro_mult)
    cum_trend = (1.0 + rets_trend).cumprod()

    # 4. ST-ChanTransformer Hybrid (P20)
    chan_feats = compute_chan_features(raw_df)
    eng_chan = ChanTransformerHybridEngine(
        token=token, atr_trailing_mult=3.0, exp_pct=50.0, pred_12d_threshold=-0.01, use_transformer_gate=True
    )
    res_chan = eng_chan.backtest(raw_df, chan_feats, df_pred_chan, df_funding)
    cum_chan = res_chan['equity_curve']

    curves[token] = {
        'bnh': bnh_cum,
        'trial': cum_trial,
        'trend': cum_trend,
        'chan': cum_chan,
        'rets_trend': rets_trend,
        'rets_chan': res_chan['bar_rets'],
        'rets_trial': s_rets_trial,
    }

# 50/50 Portfolios
curves['PORT'] = {
    'chan': 0.5 * curves['ETHUSDT']['rets_chan'] + 0.5 * curves['SOLUSDT']['rets_chan'],
    'trend': 0.5 * curves['ETHUSDT']['rets_trend'] + 0.5 * curves['SOLUSDT']['rets_trend'],
    'trial': 0.5 * curves['ETHUSDT']['rets_trial'] + 0.5 * curves['SOLUSDT']['rets_trial'],
    'bnh': 0.5 * (curves['ETHUSDT']['bnh'] / curves['ETHUSDT']['bnh'].iloc[0]) + 0.5 * (curves['SOLUSDT']['bnh'] / curves['SOLUSDT']['bnh'].iloc[0]),
}
curves['PORT']['cum_chan'] = (1.0 + curves['PORT']['chan']).cumprod()
curves['PORT']['cum_trend'] = (1.0 + curves['PORT']['trend']).cumprod()
curves['PORT']['cum_trial'] = (1.0 + curves['PORT']['trial']).cumprod()

# Plotting
fig, axes = plt.subplots(2, 2, figsize=(18, 12), dpi=150)
fig.patch.set_facecolor('#0d1117')

palette = {
    'chan': '#00F0FF',     # Cyber Cyan
    'trend': '#2ECC71',    # Emerald Green
    'trial': '#FFA500',    # Amber Orange
    'bnh': '#888888',      # Muted Gray
}

def style_ax(ax, title):
    ax.set_facecolor('#161b22')
    ax.grid(True, color='#30363d', linestyle='--', alpha=0.6)
    ax.tick_params(colors='#c9d1d9', labelsize=10)
    for spine in ax.spines.values():
        spine.set_color('#30363d')
    ax.set_title(title, color='#f0f6fc', fontsize=13, fontweight='bold', pad=10)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))

# Plot ETH
ax_eth = axes[0, 0]
style_ax(ax_eth, "ETH: ST-ChanTransformer vs. Baselines (2024–2026)")
s_chan_eth = curves['ETHUSDT']['chan']
s_trend_eth = curves['ETHUSDT']['trend']
s_trial_eth = curves['ETHUSDT']['trial']
s_bnh_eth = curves['ETHUSDT']['bnh']
ax_eth.plot(s_chan_eth.index, s_chan_eth.values, label=f"ST-ChanTransformer (P20: +147.7%, MDD -25.0%, Sharpe 1.28)", color=palette['chan'], lw=2.4)
ax_eth.plot(s_trend_eth.index, s_trend_eth.values, label=f"Macro Structural Trend (P19: +122.4%, MDD -25.6%, Sharpe 1.29)", color=palette['trend'], lw=1.8, linestyle='--')
ax_eth.plot(s_trial_eth.index, s_trial_eth.values, label=f"Transformer Trial Mode (P15: +21.9%, MDD -27.6%, Sharpe 0.51)", color=palette['trial'], lw=1.5, alpha=0.8)
ax_eth.plot(s_bnh_eth.index, s_bnh_eth.values, label=f"ETH Buy & Hold (+10.2%, MDD -60.6%)", color=palette['bnh'], lw=1.2, alpha=0.6, linestyle=':')
ax_eth.legend(loc='upper left', facecolor='#161b22', edgecolor='#30363d', labelcolor='#f0f6fc', fontsize=9)

# Plot SOL
ax_sol = axes[0, 1]
style_ax(ax_sol, "SOL: ST-ChanTransformer vs. Baselines (2024–2026)")
s_chan_sol = curves['SOLUSDT']['chan']
s_trend_sol = curves['SOLUSDT']['trend']
s_trial_sol = curves['SOLUSDT']['trial']
s_bnh_sol = curves['SOLUSDT']['bnh']
ax_sol.plot(s_chan_sol.index, s_chan_sol.values, label=f"ST-ChanTransformer (P20: +40.7%, MDD -30.6%, Sharpe 0.54)", color=palette['chan'], lw=2.4)
ax_sol.plot(s_trend_sol.index, s_trend_sol.values, label=f"Macro Structural Trend (P19: +75.4%, MDD -29.5%, Sharpe 0.81)", color=palette['trend'], lw=1.8, linestyle='--')
ax_sol.plot(s_trial_sol.index, s_trial_sol.values, label=f"Transformer Trial Mode (P15: +39.5%, MDD -24.9%, Sharpe 0.84)", color=palette['trial'], lw=1.5, alpha=0.8)
ax_sol.plot(s_bnh_sol.index, s_bnh_sol.values, label=f"SOL Buy & Hold (+0.1%, MDD -72.5%)", color=palette['bnh'], lw=1.2, alpha=0.6, linestyle=':')
ax_sol.legend(loc='upper left', facecolor='#161b22', edgecolor='#30363d', labelcolor='#f0f6fc', fontsize=9)

# Plot 50/50 Portfolio Equity
ax_port = axes[1, 0]
style_ax(ax_port, "Combined 50/50 Portfolio Cumulative Return")
s_chan_p = curves['PORT']['cum_chan']
s_trend_p = curves['PORT']['cum_trend']
s_trial_p = curves['PORT']['cum_trial']
s_bnh_p = curves['PORT']['bnh']
ax_port.plot(s_chan_p.index, s_chan_p.values, label=f"ST-ChanTransformer (P20: +94.6%, MDD -22.1%, Sharpe 1.08)", color=palette['chan'], lw=2.4)
ax_port.plot(s_trend_p.index, s_trend_p.values, label=f"Macro Structural Trend (P19: +105.1%, MDD -22.2%, Sharpe 1.27)", color=palette['trend'], lw=1.8, linestyle='--')
ax_port.plot(s_trial_p.index, s_trial_p.values, label=f"Transformer Trial Mode (P15: +38.6%, MDD -26.9%, Sharpe 0.77)", color=palette['trial'], lw=1.5, alpha=0.8)
ax_port.plot(s_bnh_p.index, s_bnh_p.values, label=f"50/50 Buy & Hold (+5.2%, MDD -66.5%)", color=palette['bnh'], lw=1.2, alpha=0.6, linestyle=':')
ax_port.legend(loc='upper left', facecolor='#161b22', edgecolor='#30363d', labelcolor='#f0f6fc', fontsize=9)

# Plot 50/50 Drawdown
ax_dd = axes[1, 1]
style_ax(ax_dd, "50/50 Portfolio Drawdown Profile (Watermark Underwater)")
c_chan = curves['PORT']['cum_chan']
dd_chan = (c_chan - c_chan.cummax()) / c_chan.cummax() * 100.0

c_trend = curves['PORT']['cum_trend']
dd_trend = (c_trend - c_trend.cummax()) / c_trend.cummax() * 100.0

c_trial = curves['PORT']['cum_trial']
dd_trial = (c_trial - c_trial.cummax()) / c_trial.cummax() * 100.0

ax_dd.plot(dd_chan.index, dd_chan.values, label=f"ST-ChanTransformer (Max DD: -22.10%)", color=palette['chan'], lw=1.8)
ax_dd.plot(dd_trend.index, dd_trend.values, label=f"Macro Structural Trend (Max DD: -22.19%)", color=palette['trend'], lw=1.5, linestyle='--')
ax_dd.plot(dd_trial.index, dd_trial.values, label=f"Transformer Trial Mode (Max DD: -26.90%)", color=palette['trial'], lw=1.2, alpha=0.7)
ax_dd.fill_between(dd_chan.index, dd_chan.values, 0, color=palette['chan'], alpha=0.15)
ax_dd.legend(loc='lower left', facecolor='#161b22', edgecolor='#30363d', labelcolor='#f0f6fc', fontsize=9)
ax_dd.set_ylabel("Drawdown (%)", color='#c9d1d9')

plt.tight_layout()

# Save PNG
png_doc = docs_dir / 'chan_transformer_alpha_curve.png'
png_art = artifact_dir / 'chan_transformer_alpha_curve.png'
fig.savefig(png_doc, dpi=150, facecolor=fig.get_facecolor(), bbox_inches='tight')
fig.savefig(png_art, dpi=150, facecolor=fig.get_facecolor(), bbox_inches='tight')
plt.close(fig)

print(f"Chart saved to {png_doc} and {png_art}")

# Generate Base64 Generative UI Widget
b64_str = encode_image(str(png_art))
widget_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>ST-ChanTransformer Alpha Benchmark</title>
  <style>
    body {{
      background: #0d1117;
      color: #c9d1d9;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
      margin: 0;
      padding: 16px;
    }}
    .card {{
      background: #161b22;
      border: 1px solid #30363d;
      border-radius: 8px;
      padding: 20px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    }}
    h2 {{
      color: #58a6ff;
      margin-top: 0;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .stat-badge {{
      background: rgba(0, 240, 255, 0.15);
      border: 1px solid #00F0FF;
      color: #00F0FF;
      padding: 4px 10px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: 600;
    }}
    img {{
      width: 100%;
      height: auto;
      border-radius: 6px;
      border: 1px solid #30363d;
      margin-top: 12px;
    }}
    .metrics-table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 16px;
      font-size: 13px;
    }}
    .metrics-table th, .metrics-table td {{
      padding: 8px 12px;
      border: 1px solid #30363d;
      text-align: right;
    }}
    .metrics-table th {{
      background: #21262d;
      color: #f0f6fc;
      text-align: left;
    }}
    .metrics-table tr:hover {{
      background: rgba(255, 255, 255, 0.03);
    }}
    .highlight {{
      color: #00F0FF;
      font-weight: 600;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div style="display: flex; justify-content: space-between; align-items: center;">
      <h2>📈 ST-ChanTransformer Multi-Horizon Wave Alpha Curve</h2>
      <span class="stat-badge">Phase 20 Dual-Scale Wave Synthesis</span>
    </div>
    <p style="color: #8b949e; font-size: 13px; margin: 4px 0 16px 0;">
      Marrying Chan-Lun (缠论) 60-bar topological hubs and fractals with Spatio-Temporal Transformer 12-day wave predictions and expansion breakout confirmation.
    </p>
    <img src="data:image/png;base64,{b64_str}" alt="ST-ChanTransformer Alpha Curve" />
    <table class="metrics-table">
      <thead>
        <tr>
          <th>Strategy Architecture</th>
          <th>Total Return</th>
          <th>Max Drawdown</th>
          <th>Daily Sharpe</th>
          <th>Calmar Ratio</th>
          <th>Total Trades</th>
          <th>Avg Duration</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>Transformer Baseline (Phase 14)</strong></td>
          <td>+27.29%</td>
          <td>-66.58%</td>
          <td>0.43</td>
          <td>0.15</td>
          <td>784</td>
          <td>1.2 days</td>
        </tr>
        <tr>
          <td><strong>Transformer Trial Mode (Phase 15)</strong></td>
          <td>+38.64%</td>
          <td>-26.90%</td>
          <td>0.77</td>
          <td>0.48</td>
          <td>784</td>
          <td>1.2 days</td>
        </tr>
        <tr>
          <td><strong>Pure Structural Trend Engine (Phase 19)</strong></td>
          <td>+105.10%</td>
          <td>-22.19%</td>
          <td>1.27</td>
          <td>1.37</td>
          <td>62</td>
          <td>21.1 days</td>
        </tr>
        <tr style="background: rgba(0, 240, 255, 0.08);">
          <td><strong class="highlight">ST-ChanTransformer Hybrid (Phase 20)</strong></td>
          <td class="highlight">+94.57%</td>
          <td class="highlight">-22.10%</td>
          <td class="highlight">1.08</td>
          <td class="highlight">1.28</td>
          <td class="highlight">86</td>
          <td class="highlight">4.2 days</td>
        </tr>
      </tbody>
    </table>
  </div>
</body>
</html>
"""

widget_doc = docs_dir / 'widget_chan_transformer_alpha.html'
widget_art = artifact_dir / 'widget_chan_transformer_alpha.html'

with open(widget_doc, 'w', encoding='utf-8') as f:
    f.write(widget_html)
with open(widget_art, 'w', encoding='utf-8') as f:
    f.write(widget_html)

print(f"Interactive widget written to {widget_doc} and {widget_art}")
