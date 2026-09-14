# -*- coding: utf-8 -*-
"""
Institutional Trial-Trading Multi-Downsizing & Realistic Risk Engine (Phase 15):
Comparative Evaluation: Baseline (Phase 14) vs. Trial Mode (Phase 15).

Trial Mode features 5-dimensional dynamic position downsizing:
1. m_streak: Consecutive stop-loss throttle (1.0 -> 0.70 -> 0.50 -> 0.25)
2. m_dd: Portfolio peak-drawdown throttle (1.0 -> 0.75 -> 0.50 -> 0.25)
3. m_vol: Realized ATR target inverse volatility sizing [0.40, 1.10]
4. m_trend: Macro 144 EMA regime filter (counter-trend capped at 0.40-0.50)
5. m_conf: Prediction confidence gradient sizing (0.65 for 1.0 < |z| < 1.4, 1.0 for |z| >= 1.4)
"""
import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Dynamic root path resolution (zero hardcoded paths)
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from crypto_quant.dual_sleeve_portfolio import compute_sleeve_adaptive

data_dir = root_dir / 'data'
pred_path = root_dir / 'predictions' / 'test_predictions.parquet'
df_pred = pd.read_parquet(pred_path)

# Load aligned sentiment and funding data
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


def run_comparison(tokens=['ETHUSDT', 'SOLUSDT']):
    periods = [
        ('2024-2025 OUT-OF-SAMPLE VALIDATION', df_pred.loc['2024-01-01':'2025-12-31'].index),
        ('2026 LOCKED BLIND TEST SET', df_pred.loc['2026-01-01':'2026-09-13'].index)
    ]

    for period_name, sub_idx in periods:
        print('=' * 85)
        print(f'{period_name}')
        print('=' * 85)

        for trial_flag, mode_label in [(False, 'Baseline (Phase 14)'), (True, 'Trial Mode (Phase 15)')]:
            rets_dict = {}
            for token in tokens:
                raw_path = data_dir / f'{token}_4h_2020_2026.parquet'
                raw_df = pd.read_parquet(raw_path).loc[sub_idx]
                funding_s = df_funding[token].shift(1).reindex(sub_idx, method='ffill').fillna(0.0)
                fng_s = onchain_aligned.loc[sub_idx, 'fng_score'].values
                sl = 0.025 if token == 'ETHUSDT' else 0.050

                s_rets, trades, pos = compute_sleeve_adaptive(
                    preds=df_pred.loc[sub_idx, f'{token}_pred_4h'],
                    opens=raw_df['open'], closes=raw_df['close'],
                    lows=raw_df['low'], highs=raw_df['high'],
                    fng=fng_s, funding=funding_s,
                    stop_loss=sl, deadband=0.20,
                    fee_and_slippage=0.0008,
                    use_top_derisking=True, use_short=True,
                    trial_mode=trial_flag
                )
                rets_dict[token] = s_rets

                cum = (1.0 + s_rets).cumprod()
                tot_ret = cum.iloc[-1] - 1.0
                peak = cum.cummax()
                mdd = ((cum - peak) / peak).min()
                daily_cum = cum.resample('1D').last().ffill()
                daily_rets = daily_cum.pct_change().dropna()
                sharpe = daily_rets.mean() / (daily_rets.std() + 1e-8) * np.sqrt(365)
                cagr = (cum.iloc[-1]) ** (1 / (len(s_rets) / 2190)) - 1.0 if cum.iloc[-1] > 0 else -1.0
                calmar = cagr / abs(mdd) if abs(mdd) > 1e-6 else 0.0
                avg_size = trades['size'].mean() if len(trades) > 0 else 0.0
                win_rate = (trades['net_ret'] > 0).mean() if len(trades) > 0 else 0.0

                print(f"[{mode_label:22s}] {token:7s} | Ret: {tot_ret*100:+7.2f}% | MDD: {mdd*100:6.2f}% | Sharpe: {sharpe:5.2f} | Calmar: {calmar:5.2f} | AvgSize: {avg_size:.2f} | WinRate: {win_rate*100:4.1f}%")

            # 50/50 Combined Portfolio
            comb_rets = 0.5 * rets_dict['ETHUSDT'] + 0.5 * rets_dict['SOLUSDT']
            comb_cum = (1.0 + comb_rets).cumprod()
            comb_tot = comb_cum.iloc[-1] - 1.0
            comb_peak = comb_cum.cummax()
            comb_mdd = ((comb_cum - comb_peak) / comb_peak).min()
            comb_daily = comb_cum.resample('1D').last().ffill().pct_change().dropna()
            comb_sharpe = comb_daily.mean() / (comb_daily.std() + 1e-8) * np.sqrt(365)
            comb_cagr = (comb_cum.iloc[-1]) ** (1 / (len(comb_rets) / 2190)) - 1.0 if comb_cum.iloc[-1] > 0 else -1.0
            comb_calmar = comb_cagr / abs(comb_mdd) if abs(comb_mdd) > 1e-6 else 0.0
            print(f"[{mode_label:22s}] 50/50   | Ret: {comb_tot*100:+7.2f}% | MDD: {comb_mdd*100:6.2f}% | Sharpe: {comb_sharpe:5.2f} | Calmar: {comb_calmar:5.2f}")
            print('-' * 85)

    # October 2025 Flash-Crash Audit
    print('\n' + '=' * 85)
    print('OCTOBER 2025 HISTORIC FLASH-CRASH STRESS TEST AUDIT')
    print('=' * 85)
    oct_idx = df_pred.loc['2025-10-01':'2025-10-31'].index

    for token in tokens:
        raw_path = data_dir / f'{token}_4h_2020_2026.parquet'
        raw_df = pd.read_parquet(raw_path).loc[oct_idx]
        funding_s = df_funding[token].shift(1).reindex(oct_idx, method='ffill').fillna(0.0)
        fng_s = onchain_aligned.loc[oct_idx, 'fng_score'].values
        sl = 0.025 if token == 'ETHUSDT' else 0.050

        print(f"\n--- {token} (October 2025) ---")
        for trial_flag, mode_label in [(False, 'Baseline (Phase 14)'), (True, 'Trial Mode (Phase 15)')]:
            s_rets, trades, _ = compute_sleeve_adaptive(
                preds=df_pred.loc[oct_idx, f'{token}_pred_4h'],
                opens=raw_df['open'], closes=raw_df['close'],
                lows=raw_df['low'], highs=raw_df['high'],
                fng=fng_s, funding=funding_s,
                stop_loss=sl, deadband=0.20,
                fee_and_slippage=0.0008,
                use_top_derisking=True, use_short=True,
                trial_mode=trial_flag
            )
            cum = (1.0 + s_rets).cumprod()
            tot_ret = cum.iloc[-1] - 1.0
            peak = cum.cummax()
            mdd = ((cum - peak) / peak).min()
            pnl_sum = trades['weighted_pnl'].sum() if len(trades) > 0 else 0.0
            avg_size = trades['size'].mean() if len(trades) > 0 else 0.0
            print(f"[{mode_label:22s}] Month Ret: {tot_ret*100:+6.2f}% | Max DD: {mdd*100:6.2f}% | Trade PnL Sum: {pnl_sum*100:+6.2f}% | Avg Size: {avg_size:.2f} | Trades: {len(trades)}")


if __name__ == '__main__':
    run_comparison()
