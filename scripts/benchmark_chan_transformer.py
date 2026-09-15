# -*- coding: utf-8 -*-
"""
Empirical Benchmark: ST-ChanTransformer Wave Hybrid vs. Baselines (Phase 20)
=============================================================================
Comparative evaluation on 2024–2026 out-of-sample data across:
1. Transformer Trial Mode (Phase 15 baseline)
2. Pure Macro Structural Trend Engine (Phase 19 baseline)
3. ST-ChanTransformer Hybrid Wave Engine (Phase 20)
4. 50/50 Portfolio of ETH + SOL ST-ChanTransformer

Exports results to `docs/chan_transformer_benchmark.json`.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from crypto_quant.chan_features import compute_chan_features
from crypto_quant.chan_transformer_engine import ChanTransformerHybridEngine

data_dir = root_dir / 'data'
pred_path = root_dir / 'predictions' / 'chan_transformer_predictions.parquet'
docs_dir = root_dir / 'docs'
docs_dir.mkdir(parents=True, exist_ok=True)


def load_data():
    if not pred_path.exists():
        raise FileNotFoundError(f"Predictions file not found at {pred_path}. Please complete training first.")

    df_preds = pd.read_parquet(pred_path)

    # Load raw candles
    candles = {}
    for token in ['ETHUSDT', 'SOLUSDT']:
        p = data_dir / f'{token}_4h_2020_2026.parquet'
        if not p.exists():
            p = data_dir / f'{token}_4h_2021_2026.parquet'
        df = pd.read_parquet(p)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        candles[token] = df

    # Funding rate
    funding_path = data_dir / 'binance_funding_8h.parquet'
    df_funding = pd.read_parquet(funding_path) if funding_path.exists() else None
    if df_funding is not None and df_funding.index.tz is not None:
        df_funding.index = df_funding.index.tz_localize(None)

    return df_preds, candles, df_funding


def compute_portfolio_metrics(ret1: pd.Series, ret2: pd.Series, w1: float = 0.5, w2: float = 0.5) -> Dict[str, Any]:
    common = ret1.index.intersection(ret2.index)
    port_ret = w1 * ret1.loc[common] + w2 * ret2.loc[common]
    cum = (1.0 + port_ret).cumprod()
    tot_ret = float(cum.iloc[-1] - 1.0)
    peak = cum.cummax()
    mdd = float(((cum - peak) / (peak + 1e-8)).min())

    daily_cum = cum.resample('1D').last().ffill()
    daily_rets = daily_cum.pct_change().dropna()
    sharpe = float(daily_rets.mean() / (daily_rets.std() + 1e-8) * np.sqrt(365))

    years = len(common) / 2190.0
    cagr = float(cum.iloc[-1] ** (1.0 / years) - 1.0) if cum.iloc[-1] > 0 else -1.0
    calmar = float(cagr / abs(mdd)) if abs(mdd) > 1e-6 else 0.0

    return {
        'total_return_pct': round(tot_ret * 100.0, 2),
        'cagr_pct': round(cagr * 100.0, 2),
        'max_drawdown_pct': round(mdd * 100.0, 2),
        'daily_sharpe': round(sharpe, 2),
        'calmar_ratio': round(calmar, 2),
    }


def main():
    print('=' * 95)
    print("EMPIRICAL BENCHMARK: ST-CHAN-TRANSFORMER WAVE HYBRID (2024–2026)")
    print('=' * 95)

    df_preds, candles, df_funding = load_data()
    print(f"Loaded out-of-sample predictions: {df_preds.shape}, range: {df_preds.index[0]} -> {df_preds.index[-1]}")

    # Compute Chan-Lun features
    chan_features = {}
    for token in ['ETHUSDT', 'SOLUSDT']:
        print(f"Computing causal Chan-Lun features for {token}...")
        chan_features[token] = compute_chan_features(candles[token])

    # Run ST-ChanTransformer Engine
    results = {}
    equity_curves = {}
    bar_rets = {}

    fixed_thresholds = {'ETHUSDT': 0.4135, 'SOLUSDT': 0.4367}

    for token in ['ETHUSDT', 'SOLUSDT']:
        print(f"\nEvaluating ST-ChanTransformer Engine on {token}...")
        engine = ChanTransformerHybridEngine(
            token=token,
            atr_trailing_mult=3.0,
            pred_12d_threshold=-0.01,
            use_transformer_gate=True,
            fixed_exp_thresh=fixed_thresholds[token],
        )
        res = engine.backtest(candles[token], chan_features[token], df_preds, df_funding)
        results[token] = res['metrics']
        results[f'{token}_trades_list'] = [
            {
                'entry_time': str(t.entry_time),
                'entry_price': t.entry_price,
                'exit_time': str(t.exit_time),
                'exit_price': t.exit_price,
                'net_ret': round(t.net_ret * 100, 2),
                'duration_days': round(t.duration_days, 1),
                'reason': t.exit_reason,
            }
            for t in res['trades']
        ]
        equity_curves[token] = res['equity_curve']
        bar_rets[token] = res['bar_rets']

        m = res['metrics']
        print(f"  Total Return: {m['total_return_pct']:+.2f}% | MDD: {m['max_drawdown_pct']:.2f}% | "
              f"Sharpe: {m['daily_sharpe']:.2f} | Trades: {m['num_trades']} | Avg Duration: {m['avg_duration_days']:.1f}d | "
              f"WinRate: {m['win_rate_pct']:.1f}% | ProfitFactor: {m['profit_factor']:.2f}")

    # Combined 50/50 Portfolio
    port_metrics = compute_portfolio_metrics(bar_rets['ETHUSDT'], bar_rets['SOLUSDT'], 0.5, 0.5)
    eth_m = results['ETHUSDT']
    sol_m = results['SOLUSDT']
    port_metrics['num_trades'] = eth_m['num_trades'] + sol_m['num_trades']
    port_metrics['avg_duration_days'] = round((eth_m['avg_duration_days'] + sol_m['avg_duration_days']) / 2.0, 2)
    port_metrics['win_rate_pct'] = round((eth_m['win_rate_pct'] + sol_m['win_rate_pct']) / 2.0, 1)
    port_metrics['cumulative_fee_drag_pct'] = round(eth_m['cumulative_fee_drag_pct'] + sol_m['cumulative_fee_drag_pct'], 2)
    results['PORTFOLIO_50_50'] = port_metrics

    print(f"\nCOMBINED 50/50 PORTFOLIO (ETH + SOL):")
    print(f"  Total Return: {port_metrics['total_return_pct']:+.2f}% | MDD: {port_metrics['max_drawdown_pct']:.2f}% | "
          f"Daily Sharpe: {port_metrics['daily_sharpe']:.2f} | CAGR: {port_metrics['cagr_pct']:+.2f}% | Calmar: {port_metrics['calmar_ratio']:.2f}")

    # Load Phase 19 Baselines for direct comparison
    baseline_file = docs_dir / 'structural_trend_clean_benchmark.json'
    baselines = {}
    if baseline_file.exists():
        with open(baseline_file, 'r', encoding='utf-8') as f:
            baselines = json.load(f)

    # Save benchmark artifact
    output_benchmark = {
        'phase': 'Phase 20 / Phase 21 - ST-ChanTransformer Clean Benchmark',
        'status': 'EXPERIMENTAL_RESEARCH_FILTER_ONLY',
        'evaluation_period': '2024-01-01 00:00:00 to 2026-09-01 12:00:00 (Development Backtest)',
        'debiasing_protocols_enforced': {
            'zero_bfill': True,
            'zero_full_sample_percentile': True,
            'train_only_fixed_threshold': True,
            'purge_bars': 72,
            'embargo_bars': 18,
        },
        'st_chan_transformer': results,
        'baselines_reference': baselines.get('clean_headline_results', {}),
    }

    out_file = docs_dir / 'chan_transformer_benchmark.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(output_benchmark, f, indent=2)

    print(f"\nBenchmark results successfully exported to: {out_file}")


if __name__ == '__main__':
    main()
