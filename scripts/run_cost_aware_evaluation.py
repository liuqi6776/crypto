# -*- coding: utf-8 -*-
"""
Cost-Aware Execution Filter & Latency Penalty Stress Suite (Phase 18 P0 Enhancement)
Evaluates:
1. Trade count / turnover reduction when low-expectancy trades are filtered out.
2. Holding period duration expansion (capacity scaling).
3. Net Sharpe Ratio and Max Drawdown preservation on 2024-2025 and 2026 stress period.
4. Strategy resilience against 2 bps (100ms colocation) and 5 bps (retail latency) adverse selection.
"""

import sys
import json
from pathlib import Path
import pandas as pd
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from crypto_quant.execution_model import ExecutionModel
from crypto_quant.portfolio import MultiAssetPortfolioEngine


def run_evaluation():
    print("=" * 80)
    print("Running Phase 18: Cost-Aware Execution Filter & Latency Stress Suite")
    print("=" * 80)

    # 1. Load Data
    pred_path = ROOT_DIR / "predictions" / "test_predictions.parquet"
    eth_path = ROOT_DIR / "data" / "ETHUSDT_4h_2020_2026.parquet"
    sol_path = ROOT_DIR / "data" / "SOLUSDT_4h_2020_2026.parquet"
    funding_path = ROOT_DIR / "data" / "binance_funding_8h.parquet"
    fng_path = ROOT_DIR / "data" / "eth_onchain_sentiment_daily.parquet"

    df_p = pd.read_parquet(pred_path)
    df_eth = pd.read_parquet(eth_path)
    df_sol = pd.read_parquet(sol_path)
    df_fund = pd.read_parquet(funding_path)
    fng_ser = pd.read_parquet(fng_path)["fng_score"]

    if df_fund.index.tz is not None:
        df_fund.index = df_fund.index.tz_convert(None)

    mkt_dict = {"ETHUSDT": df_eth, "SOLUSDT": df_sol}
    pred_dict = {"ETHUSDT": df_p["ETHUSDT_pred_4h"], "SOLUSDT": df_p["SOLUSDT_pred_4h"]}
    fund_dict = {"ETHUSDT": df_fund["ETHUSDT"], "SOLUSDT": df_fund["SOLUSDT"]}

    configs = [
        {
            "name": "Baseline (No Filter, 0 Latency)",
            "cost_filter_mult": 0.0,
            "latency_penalty": 0.0,
        },
        {
            "name": "Cost Filter Moderate (k=1.5)",
            "cost_filter_mult": 1.5,
            "latency_penalty": 0.0,
        },
        {
            "name": "Cost Filter Standard (k=2.0)",
            "cost_filter_mult": 2.0,
            "latency_penalty": 0.0,
        },
        {
            "name": "Cost Filter Aggressive (k=2.5)",
            "cost_filter_mult": 2.5,
            "latency_penalty": 0.0,
        },
        {
            "name": "Baseline + 2 bps Latency",
            "cost_filter_mult": 0.0,
            "latency_penalty": 0.0002,
        },
        {
            "name": "Cost Filter (k=2.0) + 2 bps Latency",
            "cost_filter_mult": 2.0,
            "latency_penalty": 0.0002,
        },
        {
            "name": "Cost Filter (k=2.0) + 5 bps Stress",
            "cost_filter_mult": 2.0,
            "latency_penalty": 0.0005,
        },
    ]

    results = []

    print(f"\n{'Configuration':<34} | {'Val Ret':<9} | {'Sharpe':<7} | {'Max DD':<9} | {'Trades':<7} | {'Turnover Cut':<12} | {'Avg Hold':<9}")
    print("-" * 105)

    base_trades = None

    for cfg in configs:
        engine = MultiAssetPortfolioEngine(
            trial_mode=True,
            cost_filter_mult=cfg["cost_filter_mult"],
            latency_penalty=cfg["latency_penalty"],
        )
        res = engine.run(
            df_market_dict=mkt_dict,
            pred_dict=pred_dict,
            funding_dict=fund_dict,
            fng_series=fng_ser,
        )

        rep_val = res.slice_report("2024-01-01", "2025-12-31")
        rep_stress = res.slice_report("2026-01-01", "2026-09-13")
        rep_full = res.slice_report("2024-01-01", "2026-09-13")

        total_trades = sum(len(res.asset_results[sym].trades) for sym in res.asset_results)
        all_trades = [t for sym in res.asset_results for t in res.asset_results[sym].trades]
        avg_bars = np.mean([t.duration_bars for t in all_trades]) if all_trades else 0.0
        avg_hours = avg_bars * 4.0

        if base_trades is None:
            base_trades = total_trades

        turnover_reduction_pct = ((base_trades - total_trades) / base_trades * 100.0) if base_trades > 0 else 0.0

        cfg_summary = {
            "name": cfg["name"],
            "cost_filter_mult": cfg["cost_filter_mult"],
            "latency_penalty_bps": int(cfg["latency_penalty"] * 10000),
            "val_2024_2025": {
                "return_pct": round(rep_val.total_return * 100.0, 2),
                "sharpe": round(rep_val.daily_sharpe, 2),
                "max_dd_pct": round(rep_val.max_drawdown * 100.0, 2),
                "calmar": round(rep_val.calmar_ratio, 2),
            },
            "stress_2026": {
                "return_pct": round(rep_stress.total_return * 100.0, 2),
                "sharpe": round(rep_stress.daily_sharpe, 2),
                "max_dd_pct": round(rep_stress.max_drawdown * 100.0, 2),
            },
            "full_history": {
                "return_pct": round(rep_full.total_return * 100.0, 2),
                "sharpe": round(rep_full.daily_sharpe, 2),
                "max_dd_pct": round(rep_full.max_drawdown * 100.0, 2),
            },
            "execution_metrics": {
                "total_completed_trades": total_trades,
                "turnover_reduction_pct": round(turnover_reduction_pct, 2),
                "avg_holding_duration_hours": round(avg_hours, 1),
            },
        }
        results.append(cfg_summary)

        print(
            f"{cfg['name']:<34} | "
            f"{rep_val.total_return * 100.0:>+7.2f}% | "
            f"{rep_val.daily_sharpe:>6.2f}  | "
            f"{rep_val.max_drawdown * 100.0:>7.2f}% | "
            f"{total_trades:>6d}  | "
            f"{turnover_reduction_pct:>10.2f}% | "
            f"{avg_hours:>6.1f}h"
        )

    out_path = ROOT_DIR / "docs" / "cost_aware_evaluation.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"cost_aware_evaluation": results}, f, indent=2)

    print(f"\n[Artifact Saved] Successfully exported Phase 18 evaluation to: {out_path}")


if __name__ == "__main__":
    run_evaluation()
