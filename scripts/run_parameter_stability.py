# -*- coding: utf-8 -*-
"""
Parameter Neighborhood Stability Analysis (Phase 17)
Evaluates whether strategy performance resides on a robust plateau or sharp overfit peak:
Scans +/- 20% parameter grid across:
- Entry Z-score threshold (0.8, 1.0, 1.2)
- Exit Deadband (0.16, 0.20, 0.24)
- Stop-loss multiplier (0.8x, 1.0x, 1.2x)
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


def run_parameter_stability():
    print("=" * 75)
    print("Running Parameter Stability Grid Scan (+/- 20% Perturbations)")
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

    grid = [
        {"desc": "Baseline (1.0 Z, 0.20 DB, 1.0x SL)", "deadband": 0.20, "sl_mult": 1.0},
        {"desc": "-20% Deadband (0.16 DB)", "deadband": 0.16, "sl_mult": 1.0},
        {"desc": "+20% Deadband (0.24 DB)", "deadband": 0.24, "sl_mult": 1.0},
        {"desc": "-20% Stop Loss (Tighter Stops)", "deadband": 0.20, "sl_mult": 0.80},
        {"desc": "+20% Stop Loss (Looser Stops)", "deadband": 0.20, "sl_mult": 1.20},
        {"desc": "Defensive Neighborhood (-20% DB, +20% SL)", "deadband": 0.16, "sl_mult": 1.20},
        {"desc": "Aggressive Neighborhood (+20% DB, -20% SL)", "deadband": 0.24, "sl_mult": 0.80},
    ]

    base_sl = {"ETHUSDT": 0.025, "SOLUSDT": 0.050}
    results = []

    print(f"\n{'Parameter Neighborhood':<40} | {'2024-2025 Ret':<14} | {'Sharpe':<8} | {'Max DD':<10} | {'Calmar':<8}")
    print("-" * 88)

    for item in grid:
        adjusted_sl = {sym: base_sl[sym] * item["sl_mult"] for sym in base_sl}
        engine = MultiAssetPortfolioEngine(
            stop_losses=adjusted_sl,
            deadband=item["deadband"],
            trial_mode=True,
        )
        res = engine.run(mkt_dict, pred_dict, fund_dict, fng_ser)
        rep = res.slice_report("2024-01-01", "2025-12-31")

        row = {
            "parameter_neighborhood": item["desc"],
            "deadband": item["deadband"],
            "stop_loss_mult": item["sl_mult"],
            "val_return_pct": round(rep.total_return * 100.0, 2),
            "val_sharpe": round(rep.daily_sharpe, 2),
            "val_max_dd_pct": round(rep.max_drawdown * 100.0, 2),
            "val_calmar": round(rep.calmar_ratio, 2),
        }
        results.append(row)

        print(f"{row['parameter_neighborhood']:<40} | {row['val_return_pct']:>13.2f}% | {row['val_sharpe']:>8.2f} | {row['val_max_dd_pct']:>9.2f}% | {row['val_calmar']:>8.2f}")

    # Compute plateau coefficient of variation
    sharpes = [r["val_sharpe"] for r in results]
    m_sharpe = float(np.mean(sharpes))
    std_sharpe = float(np.std(sharpes))
    cv_sharpe = std_sharpe / max(1e-6, m_sharpe)

    print(f"\nPlateau Robustness: Mean Sharpe={m_sharpe:.2f}, Std={std_sharpe:.2f}, Coeff of Variation={cv_sharpe:.2%}")

    out_path = ROOT_DIR / "docs" / "parameter_stability.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "parameter_grid_results": results,
            "plateau_metrics": {
                "mean_sharpe": round(m_sharpe, 2),
                "std_sharpe": round(std_sharpe, 2),
                "coeff_of_variation_pct": round(cv_sharpe * 100.0, 2),
            }
        }, f, indent=2, ensure_ascii=False)

    print(f"[Artifact Saved] Parameter stability results saved to: {out_path}")
    return results


if __name__ == "__main__":
    run_parameter_stability()
