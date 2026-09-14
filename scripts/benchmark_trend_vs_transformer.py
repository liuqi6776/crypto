# -*- coding: utf-8 -*-
"""
Empirical Benchmark: Structural Trend Architecture vs. Micro 4h Transformer (Phase 19)
======================================================================================
Direct side-by-side comparative evaluation on 2024–2026 out-of-sample data.

Evaluates:
1. Transformer Baseline (Phase 14)
2. Transformer Trial Mode (Phase 15)
3. Donchian Turtle Breakout (120/60)
4. Bollinger Dynamic Trailing Breakout (120-bar)
5. Macro Structural Trend Engine (Bollinger + 200 EMA Macro Regime Sizing)
6. Combined 50/50 ETH + SOL Structural Trend Portfolio

Exports results to `docs/trend_vs_transformer_benchmark.json`.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

# Dynamic root resolution
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from crypto_quant.dual_sleeve_portfolio import compute_sleeve_adaptive
from crypto_quant.structural_trend_engine import StructuralTrendEngine

data_dir = root_dir / 'data'
pred_path = root_dir / 'predictions' / 'test_predictions.parquet'
df_pred = pd.read_parquet(pred_path)
eval_idx = df_pred.index

# Align sentiment and funding
df_onchain = pd.read_parquet(data_dir / 'eth_onchain_sentiment_daily.parquet')
if df_onchain.index.tz is not None:
    df_onchain.index = df_onchain.index.tz_localize(None)
onchain_aligned = df_onchain.shift(1).reindex(eval_idx.normalize(), method='ffill')
onchain_aligned.index = eval_idx

df_funding = pd.read_parquet(data_dir / 'binance_funding_8h.parquet')
if df_funding.index.tz is not None:
    df_funding.index = df_funding.index.tz_localize(None)


def compute_metrics(bar_rets: pd.Series, trades: Any, fee_rate: float = 0.0008) -> Dict[str, Any]:
    cum = (1.0 + bar_rets).cumprod()
    tot_ret = float(cum.iloc[-1] - 1.0)
    peak = cum.cummax()
    mdd = float(((cum - peak) / (peak + 1e-8)).min())

    daily_cum = cum.resample('1D').last().ffill()
    daily_rets = daily_cum.pct_change().dropna()
    sharpe = float(daily_rets.mean() / (daily_rets.std() + 1e-8) * np.sqrt(365))

    years = len(bar_rets) / 2190.0  # 6 bars/day * 365 days
    cagr = float(cum.iloc[-1] ** (1.0 / years) - 1.0) if cum.iloc[-1] > 0 else -1.0
    calmar = float(cagr / abs(mdd)) if abs(mdd) > 1e-6 else 0.0

    if isinstance(trades, pd.DataFrame):
        num_trades = len(trades)
        if num_trades > 0:
            rets = trades['net_ret'].tolist()
            durations = (trades['duration_hours'] / 24.0).tolist()
        else:
            rets = []
            durations = []
    elif isinstance(trades, list):
        num_trades = len(trades)
        if num_trades > 0:
            if isinstance(trades[0], dict):
                rets = [t['net_ret'] for t in trades]
                durations = [t['duration_hours'] / 24.0 for t in trades]
            else:
                rets = [t.net_ret for t in trades]
                durations = [t.duration_days for t in trades]
        else:
            rets = []
            durations = []
    else:
        num_trades = 0
        rets = []
        durations = []

    if num_trades > 0:
        win_rate = float(np.mean([r > 0 for r in rets]))
        pos_sum = sum(r for r in rets if r > 0)
        neg_sum = abs(sum(r for r in rets if r < 0))
        profit_factor = float(pos_sum / (neg_sum + 1e-8)) if neg_sum > 0 else float('inf')
        avg_dur = float(np.mean(durations))
    else:
        win_rate = 0.0
        profit_factor = 0.0
        avg_dur = 0.0

    cum_fee_drag = num_trades * 2.0 * fee_rate

    return {
        'total_return_pct': round(tot_ret * 100.0, 2),
        'cagr_pct': round(cagr * 100.0, 2),
        'max_drawdown_pct': round(mdd * 100.0, 2),
        'daily_sharpe': round(sharpe, 2),
        'calmar_ratio': round(calmar, 2),
        'num_trades': num_trades,
        'avg_duration_days': round(avg_dur, 2),
        'win_rate_pct': round(win_rate * 100.0, 1),
        'profit_factor': round(profit_factor, 2),
        'cumulative_fee_drag_pct': round(cum_fee_drag * 100.0, 2),
    }


def main():
    print('=' * 105)
    print('EMPIRICAL BENCHMARK: STRUCTURAL TREND ARCHITECTURE VS TRANSFORMER (2024 - 2026)')
    print('=' * 105)

    benchmark_results = {}
    tokens = ['ETHUSDT', 'SOLUSDT']

    trend_rets_dict = {}

    for token in tokens:
        raw_df = pd.read_parquet(data_dir / f'{token}_4h_2020_2026.parquet').loc[eval_idx]
        funding_s = df_funding[token].shift(1).reindex(eval_idx, method='ffill').fillna(0.0)
        fng_s = onchain_aligned['fng_score'].values
        sl = 0.025 if token == 'ETHUSDT' else 0.050

        # Buy and Hold Benchmark
        bnh_ret = (raw_df['close'].iloc[-1] / raw_df['open'].iloc[0] - 1.0) * 100.0

        token_results = {
            'buy_and_hold_return_pct': round(bnh_ret, 2)
        }

        # 1. Transformer Baseline
        s_rets_base, trades_base, _ = compute_sleeve_adaptive(
            preds=df_pred[f'{token}_pred_4h'],
            opens=raw_df['open'], closes=raw_df['close'],
            lows=raw_df['low'], highs=raw_df['high'],
            fng=fng_s, funding=funding_s,
            stop_loss=sl, deadband=0.20,
            fee_and_slippage=0.0008,
            use_top_derisking=True, use_short=True,
            trial_mode=False
        )
        token_results['transformer_baseline'] = compute_metrics(s_rets_base, trades_base)

        # 2. Transformer Trial Mode
        s_rets_trial, trades_trial, _ = compute_sleeve_adaptive(
            preds=df_pred[f'{token}_pred_4h'],
            opens=raw_df['open'], closes=raw_df['close'],
            lows=raw_df['low'], highs=raw_df['high'],
            fng=fng_s, funding=funding_s,
            stop_loss=sl, deadband=0.20,
            fee_and_slippage=0.0008,
            use_top_derisking=True, use_short=True,
            trial_mode=True
        )
        token_results['transformer_trial_mode'] = compute_metrics(s_rets_trial, trades_trial)

        # 3. Donchian Turtle Breakout
        eng_don = StructuralTrendEngine(mode='donchian', lookback_bars=120, exit_lookback_bars=60, atr_trailing_mult=3.0, use_short=False)
        rets_don, trades_don, _ = eng_don.run_backtest(raw_df, token=token, funding_rate=funding_s)
        token_results['donchian_turtle'] = compute_metrics(rets_don, trades_don)

        # 4. Bollinger Dynamic Trailing Breakout
        eng_bb = StructuralTrendEngine(mode='bollinger', lookback_bars=120, exit_lookback_bars=60, atr_trailing_mult=3.0, use_short=False)
        rets_bb, trades_bb, _ = eng_bb.run_backtest(raw_df, token=token, funding_rate=funding_s)
        token_results['bollinger_breakout'] = compute_metrics(rets_bb, trades_bb)

        # 5. Macro Structural Trend Engine (with 200 EMA macro sizing)
        ema200 = raw_df['close'].shift(1).ewm(span=200).mean()
        macro_bull = raw_df['close'].shift(1) > ema200
        macro_mult = pd.Series(np.where(macro_bull, 1.0, 0.5), index=eval_idx)

        eng_macro = StructuralTrendEngine(mode='bollinger', lookback_bars=120, exit_lookback_bars=60, atr_trailing_mult=3.0, use_short=False)
        rets_macro, trades_macro, _ = eng_macro.run_backtest(raw_df, token=token, funding_rate=funding_s, macro_multipliers=macro_mult)
        token_results['structural_trend_macro'] = compute_metrics(rets_macro, trades_macro)
        trend_rets_dict[token] = rets_macro

        benchmark_results[token] = token_results

        # Print Table for Token
        print(f"\n[{token}] (Buy & Hold: {bnh_ret:+.2f}%):")
        print(f"{'Strategy Name':30s} | {'Total Ret':10s} | {'MDD':8s} | {'Sharpe':6s} | {'Calmar':6s} | {'Trades':6s} | {'AvgDur':7s} | {'WinRate':7s} | {'FeeDrag':7s}")
        print('-' * 105)
        for s_key, s_name in [
            ('transformer_baseline', 'Transformer Baseline (P14)'),
            ('transformer_trial_mode', 'Transformer Trial Mode (P15)'),
            ('donchian_turtle', 'Donchian Turtle (120/60)'),
            ('bollinger_breakout', 'Bollinger Breakout (120-bar)'),
            ('structural_trend_macro', 'Macro Structural Trend (P19)'),
        ]:
            m = token_results[s_key]
            print(f"{s_name:30s} | {m['total_return_pct']:+9.2f}% | {m['max_drawdown_pct']:7.2f}% | {m['daily_sharpe']:6.2f} | {m['calmar_ratio']:6.2f} | {m['num_trades']:6d} | {m['avg_duration_days']:5.1f}d | {m['win_rate_pct']:6.1f}% | {m['cumulative_fee_drag_pct']:6.1f}%")

    # 50/50 Combined Portfolio
    comb_trend_rets = 0.5 * trend_rets_dict['ETHUSDT'] + 0.5 * trend_rets_dict['SOLUSDT']
    comb_trades = benchmark_results['ETHUSDT']['structural_trend_macro']['num_trades'] + benchmark_results['SOLUSDT']['structural_trend_macro']['num_trades']

    cum_comb = (1.0 + comb_trend_rets).cumprod()
    tot_comb = float(cum_comb.iloc[-1] - 1.0)
    peak_comb = cum_comb.cummax()
    mdd_comb = float(((cum_comb - peak_comb) / (peak_comb + 1e-8)).min())
    daily_cum_comb = cum_comb.resample('1D').last().ffill()
    daily_rets_comb = daily_cum_comb.pct_change().dropna()
    sharpe_comb = float(daily_rets_comb.mean() / (daily_rets_comb.std() + 1e-8) * np.sqrt(365))
    years_comb = len(comb_trend_rets) / 2190.0
    cagr_comb = float(cum_comb.iloc[-1] ** (1.0 / years_comb) - 1.0)
    calmar_comb = float(cagr_comb / abs(mdd_comb))

    combined_summary = {
        'total_return_pct': round(tot_comb * 100.0, 2),
        'cagr_pct': round(cagr_comb * 100.0, 2),
        'max_drawdown_pct': round(mdd_comb * 100.0, 2),
        'daily_sharpe': round(sharpe_comb, 2),
        'calmar_ratio': round(calmar_comb, 2),
        'total_trades': comb_trades,
    }
    benchmark_results['portfolio_50_50_structural_trend'] = combined_summary

    print('\n' + '=' * 105)
    print(f"COMBINED 50/50 PORTFOLIO (ETH + SOL MACRO STRUCTURAL TREND):")
    print(f"Total Return: {tot_comb*100:+.2f}% | CAGR: {cagr_comb*100:+.2f}% | MDD: {mdd_comb*100:.2f}% | Sharpe: {sharpe_comb:.2f} | Calmar: {calmar_comb:.2f} | Total Trades: {comb_trades}")
    print('=' * 105)

    # Export JSON
    out_path = root_dir / 'docs' / 'trend_vs_transformer_benchmark.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(benchmark_results, f, indent=2, ensure_ascii=False)
    print(f"\nArtifact successfully exported to: {out_path}")


if __name__ == '__main__':
    main()
