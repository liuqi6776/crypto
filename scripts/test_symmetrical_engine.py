# -*- coding: utf-8 -*-
"""
Canonical Production Symmetrical Long/Short Alpha Engine Verification:
Uses crypto_quant.dual_sleeve_portfolio as the single source of truth.
Features:
1. Platform-independent dynamic root path resolution (zero hardcoded paths)
2. Symmetrical Long & Short Trading (Long: z > 1.0, Short: z < -1.0, Deadband: |z| < 0.20)
3. Symmetrical Top & Bottom Multi-Factor Risk Sizing
4. Causal 8h perpetual funding rate carry (+ for shorts in bull peaks, - for longs)
5. Realistic execution cost & slippage (0.08% per turnover = 0.16% roundtrip)
6. State-driven instant recovery (zero clock freeze)
7. Full unvarnished evaluation across:
   - 2024-2025 Out-of-Sample Validation Set
   - 2026 Locked Blind Test Set
   - October 2025 Historic Flash-Crash Stress Test
"""
import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Dynamically resolve root directory
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


def run_evaluation(tokens=['ETHUSDT', 'SOLUSDT']):
    periods = [
        ('2024-2025 OUT-OF-SAMPLE VALIDATION', df_pred.loc['2024-01-01':'2025-12-31'].index),
        ('2026 LOCKED BLIND TEST SET', df_pred.loc['2026-01-01':'2026-09-13'].index)
    ]

    for period_name, sub_idx in periods:
        print('=' * 80)
        print(f'{period_name}')
        print('=' * 80)

        strat_rets_dict = {}
        bh_rets_dict = {}

        for token in tokens:
            raw_path = data_dir / f'{token}_4h_2020_2026.parquet'
            raw_df = pd.read_parquet(raw_path).loc[sub_idx]
            funding_s = df_funding[token].shift(1).reindex(sub_idx, method='ffill').fillna(0.0)
            fng_s = onchain_aligned.loc[sub_idx, 'fng_score'].values
            stb_s = onchain_aligned.loc[sub_idx, 'stb_flow_7d'].values

            sl = 0.025 if token == 'ETHUSDT' else 0.050

            s_rets, trades, pos = compute_sleeve_adaptive(
                preds=df_pred.loc[sub_idx, f'{token}_pred_4h'],
                opens=raw_df['open'], closes=raw_df['close'],
                lows=raw_df['low'], highs=raw_df['high'],
                fng=fng_s, stb=stb_s, funding=funding_s,
                stop_loss=sl, deadband=0.20,
                fee_and_slippage=0.0008,
                use_top_derisking=True, use_short=True
            )

            strat_rets_dict[token] = s_rets
            cum = (1 + s_rets).cumprod()
            total_ret = cum.iloc[-1] - 1.0
            cagr = (cum.iloc[-1]) ** (1 / (len(s_rets) / 2190)) - 1.0 if cum.iloc[-1] > 0 else -1.0
            mdd = ((cum - cum.cummax()) / cum.cummax()).min()

            daily_cum = cum.resample('1D').last().ffill()
            daily_rets = daily_cum.pct_change().dropna()
            daily_sharpe = daily_rets.mean() / (daily_rets.std() + 1e-8) * np.sqrt(365)
            calmar = cagr / abs(mdd) if abs(mdd) > 1e-6 else 0.0

            # Buy & Hold Benchmark
            bh_rets = (raw_df['open'].shift(-2) / raw_df['open'].shift(-1) - 1).iloc[:-2]
            bh_rets_dict[token] = bh_rets
            bh_cum = (1 + bh_rets).cumprod()
            bh_ret = bh_cum.iloc[-1] - 1.0
            bh_mdd = ((bh_cum - bh_cum.cummax()) / bh_cum.cummax()).min()
            bh_daily = bh_cum.resample('1D').last().ffill().pct_change().dropna()
            bh_sharpe = bh_daily.mean() / (bh_daily.std() + 1e-8) * np.sqrt(365)

            # Beta & Jensen Alpha to Buy & Hold
            cov = np.cov(daily_rets, bh_daily)[0, 1]
            var_m = np.var(bh_daily)
            beta = cov / (var_m + 1e-8)
            alpha = (daily_rets.mean() - beta * bh_daily.mean()) * 365

            n_trades = len(trades)
            n_longs = len(trades[trades['type'] == 'LONG']) if n_trades > 0 else 0
            n_shorts = len(trades[trades['type'] == 'SHORT']) if n_trades > 0 else 0
            long_win = (trades[trades['type'] == 'LONG']['net_ret'] > 0).mean() if n_longs > 0 else 0.0
            short_win = (trades[trades['type'] == 'SHORT']['net_ret'] > 0).mean() if n_shorts > 0 else 0.0

            print(f'\n--- {token} ---')
            print(f'Strategy Total Ret:   {total_ret:+.2%} (vs Buy & Hold: {bh_ret:+.2%})')
            print(f'Excess Return:        {total_ret - bh_ret:+.2%}')
            print(f'Max Drawdown:        {mdd:.2%} (vs Buy & Hold MDD: {bh_mdd:.2%})')
            print(f'Daily Sharpe Ratio:   {daily_sharpe:.2f} (vs Buy & Hold Sharpe: {bh_sharpe:.2f})')
            print(f'Market Beta (to B&H): {beta:.2f}')
            print(f'Annual Jensen Alpha:  {alpha:+.2%}')
            print(f'Calmar Ratio:         {calmar:.2f}')
            print(f'Trades Breakdown:     Total={n_trades}, Longs={n_longs} (Win: {long_win:.1%}), Shorts={n_shorts} (Win: {short_win:.1%})')

        # Combined 50/50 Portfolio
        comb_rets = 0.5 * strat_rets_dict['ETHUSDT'] + 0.5 * strat_rets_dict['SOLUSDT']
        comb_cum = (1 + comb_rets).cumprod()
        comb_ret = comb_cum.iloc[-1] - 1.0
        comb_mdd = ((comb_cum - comb_cum.cummax()) / comb_cum.cummax()).min()
        comb_daily = comb_cum.resample('1D').last().ffill().pct_change().dropna()
        comb_sharpe = comb_daily.mean() / (comb_daily.std() + 1e-8) * np.sqrt(365)

        bh_comb = 0.5 * bh_rets_dict['ETHUSDT'] + 0.5 * bh_rets_dict['SOLUSDT']
        bh_cum_comb = (1 + bh_comb).cumprod()
        bh_ret_comb = bh_cum_comb.iloc[-1] - 1.0
        bh_mdd_comb = ((bh_cum_comb - bh_cum_comb.cummax()) / bh_cum_comb.cummax()).min()
        bh_daily_comb = bh_cum_comb.resample('1D').last().ffill().pct_change().dropna()
        bh_sharpe_comb = bh_daily_comb.mean() / (bh_daily_comb.std() + 1e-8) * np.sqrt(365)

        cov_c = np.cov(comb_daily, bh_daily_comb)[0, 1]
        beta_c = cov_c / (np.var(bh_daily_comb) + 1e-8)
        alpha_c = (comb_daily.mean() - beta_c * bh_daily_comb.mean()) * 365

        print(f'\n--- 50/50 COMBINED PORTFOLIO ---')
        print(f'Strategy Total Ret:   {comb_ret:+.2%} (vs Buy & Hold: {bh_ret_comb:+.2%})')
        print(f'Excess Return:        {comb_ret - bh_ret_comb:+.2%}')
        print(f'Max Drawdown:        {comb_mdd:.2%} (vs Buy & Hold MDD: {bh_mdd_comb:.2%})')
        print(f'Daily Sharpe Ratio:   {comb_sharpe:.2f} (vs Buy & Hold Sharpe: {bh_sharpe_comb:.2f})')
        print(f'Market Beta (to B&H): {beta_c:.3f}')
        print(f'Annual Jensen Alpha:  {alpha_c:+.2%}')

    # October 2025 Historic Flash-Crash Stress Test (Full Transparent Audit)
    print('\n' + '=' * 80)
    print('OCTOBER 2025 HISTORIC FLASH-CRASH STRESS TEST (FULL UNVARNISHED AUDIT)')
    print('=' * 80)
    oct_idx = df_pred.loc['2025-10-01':'2025-10-31'].index

    for token in tokens:
        raw_path = data_dir / f'{token}_4h_2020_2026.parquet'
        raw_df = pd.read_parquet(raw_path).loc[oct_idx]
        funding_s = df_funding[token].shift(1).reindex(oct_idx, method='ffill').fillna(0.0)
        fng_s = onchain_aligned.loc[oct_idx, 'fng_score'].values
        stb_s = onchain_aligned.loc[oct_idx, 'stb_flow_7d'].values
        sl = 0.025 if token == 'ETHUSDT' else 0.050

        s_rets, trades, pos = compute_sleeve_adaptive(
            preds=df_pred.loc[oct_idx, f'{token}_pred_4h'],
            opens=raw_df['open'], closes=raw_df['close'],
            lows=raw_df['low'], highs=raw_df['high'],
            fng=fng_s, stb=stb_s, funding=funding_s,
            stop_loss=sl, deadband=0.20,
            fee_and_slippage=0.0008,
            use_top_derisking=True, use_short=True
        )

        cum = (1 + s_rets).cumprod()
        bh_cum = (1 + (raw_df['open'].shift(-2) / raw_df['open'].shift(-1) - 1).iloc[:-2]).cumprod()

        print(f'\n[{token}] October 2025 Full Month Strategy Return: {cum.iloc[-1]-1:+.2%} (vs Buy & Hold: {bh_cum.iloc[-1]-1:+.2%})')
        print(f'Executed Trades: {len(trades)}')
        for _, tr in trades.iterrows():
            t_type = tr['type']
            t_entry = str(tr['entry_time'])
            t_exit = str(tr['exit_time'])
            t_size = tr['size']
            t_net = tr['net_ret']
            t_pnl = tr['weighted_pnl']
            t_stop = tr['is_stop_loss']
            print(f'  {t_type:5s} {t_entry} -> {t_exit} | Size: {t_size:.2f} | Net: {t_net:+.2%} | PnL: {t_pnl:+.2%} | Stop: {t_stop}')
        pnl_sum = trades['weighted_pnl'].sum() if len(trades) > 0 else 0.0
        print(f'Sum of Discrete Trade PnL: {pnl_sum:+.2%}')


if __name__ == '__main__':
    run_evaluation()
