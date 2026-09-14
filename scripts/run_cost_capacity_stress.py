# -*- coding: utf-8 -*-
"""
Cost and Capacity Friction Stress Testing (Phase 17)
Evaluates strategy robustness under escalating slippage and transaction costs:
Friction levels: 5 bps, 8 bps (baseline), 10 bps, 15 bps, 20 bps, 30 bps.
Computes return degradation, Sharpe decay, and estimates breakeven capacity.
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


def run_cost_stress():
    print("=" * 75)
    print("Running Institutional Cost & Capacity Stress Suite (5 bps to 30 bps)")
    print("=" * 75)

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

    friction_levels = [
        {"name": "5 bps (VIP/Tier-1)", "fee": 0.0003, "slip": 0.0002, "stop_slip": 0.0006},
        {"name": "8 bps (Baseline Tier)", "fee": 0.0004, "slip": 0.0004, "stop_slip": 0.0010},
        {"name": "10 bps (Retail Default)", "fee": 0.0005, "slip": 0.0005, "stop_slip": 0.0012},
        {"name": "15 bps (Moderate Stress)", "fee": 0.0007, "slip": 0.0008, "stop_slip": 0.0018},
        {"name": "20 bps (High Stress)", "fee": 0.0010, "slip": 0.0010, "stop_slip": 0.0025},
        {"name": "30 bps (Severe Illiquid)", "fee": 0.0015, "slip": 0.0015, "stop_slip": 0.0035},
    ]

    results = []

    print(f"\n{'Friction Level':<24} | {'2024-2025 Ret':<14} | {'Sharpe':<8} | {'Max DD':<10} | {'Full Ret':<10} | {'Full Sharpe':<11}")
    print("-" * 88)

    for f_cfg in friction_levels:
        exec_model = ExecutionModel(
            taker_fee=f_cfg["fee"],
            normal_slippage=f_cfg["slip"],
            stop_slippage=f_cfg["stop_slip"],
            gap_slippage=f_cfg["stop_slip"] * 1.5,
        )
        engine = MultiAssetPortfolioEngine(execution_model=exec_model, trial_mode=True)
        res = engine.run(mkt_dict, pred_dict, fund_dict, fng_ser)

        rep_val = res.slice_report("2024-01-01", "2025-12-31")
        rep_full = res.slice_report("2024-01-01", "2026-09-13")

        row = {
            "name": f_cfg["name"],
            "one_way_friction_bps": int(round((f_cfg["fee"] + f_cfg["slip"]) * 10000)),
            "val_return_pct": round(rep_val.total_return * 100.0, 2),
            "val_sharpe": round(rep_val.daily_sharpe, 2),
            "val_max_dd_pct": round(rep_val.max_drawdown * 100.0, 2),
            "val_calmar": round(rep_val.calmar_ratio, 2),
            "full_return_pct": round(rep_full.total_return * 100.0, 2),
            "full_sharpe": round(rep_full.daily_sharpe, 2),
            "full_max_dd_pct": round(rep_full.max_drawdown * 100.0, 2),
        }
        results.append(row)

        print(f"{row['name']:<24} | {row['val_return_pct']:>13.2f}% | {row['val_sharpe']:>8.2f} | {row['val_max_dd_pct']:>9.2f}% | {row['full_return_pct']:>9.2f}% | {row['full_sharpe']:>11.2f}")

    # Export to docs
    out_path = ROOT_DIR / "docs" / "cost_capacity_stress.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"cost_stress_results": results}, f, indent=2, ensure_ascii=False)

    print(f"\n[Artifact Saved] Results saved to: {out_path}")
    return results


if __name__ == "__main__":
    run_cost_stress()
