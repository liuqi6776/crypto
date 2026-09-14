# -*- coding: utf-8 -*-
"""
Generate Metrics Single Source of Truth (Phase 16)
Runs continuous history backtesting on ETH and SOL across full dataset (2024-01-01 to 2026-09-13).
Extracts:
1. 2024-2025 Out-of-Sample Validation metrics
2. 2026 Post-hoc Development / Stress-Test metrics
3. October 2025 Continuous Accounting metrics
4. Full 2024-2026 History metrics
5. Trial-trading vs Raw Baseline comparison

Outputs docs/metrics.json with git commit SHA and data provenance.
"""

import os
import sys
import json
import hashlib
import subprocess
from pathlib import Path
import pandas as pd
import numpy as np

# Ensure crypto_quant can be imported
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from crypto_quant.execution_model import ExecutionModel
from crypto_quant.continuous_backtest import ContinuousBacktestEngine
from crypto_quant.portfolio import MultiAssetPortfolioEngine


def compute_file_hash(filepath: Path) -> str:
    """Calculates SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()[:16]


def get_git_commit() -> str:
    """Retrieves current git commit hash."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT_DIR), universal_newlines=True
        ).strip()
        return commit
    except Exception:
        return "unknown"


def main():
    print("=" * 70)
    print("Generating Institutional Metrics Single Source of Truth (metrics.json)")
    print("=" * 70)

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

    # Provenance tracking
    data_hashes = {
        "test_predictions": compute_file_hash(pred_path),
        "eth_market": compute_file_hash(eth_path),
        "sol_market": compute_file_hash(sol_path),
        "funding_rates": compute_file_hash(funding_path),
        "fng_sentiment": compute_file_hash(fng_path),
    }

    # 2. Run Simulations: Mode A (Trial Trading) and Mode B (Baseline)
    print("\n[1/3] Running Mode A: Institutional Trial Trading (Dynamic Multi-Downsizing)...")
    engine_trial = MultiAssetPortfolioEngine(trial_mode=True)
    res_trial = engine_trial.run(mkt_dict, pred_dict, fund_dict, fng_ser)

    print("[2/3] Running Mode B: Raw Symmetrical Baseline...")
    engine_base = MultiAssetPortfolioEngine(trial_mode=False)
    res_base = engine_base.run(mkt_dict, pred_dict, fund_dict, fng_ser)

    # 3. Extract Slices
    slices_to_extract = [
        ("val_2024_2025", "2024-01-01", "2025-12-31"),
        ("stress_2026", "2026-01-01", "2026-09-13"),
        ("october_2025", "2025-10-01", "2025-10-31"),
        ("full_history", "2024-01-01", "2026-09-13"),
    ]

    metrics = {
        "metadata": {
            "system": "Crypto Transformer Multi-Asset Quantitative Engine (Phase 16)",
            "git_commit": get_git_commit(),
            "generated_at": pd.Timestamp.utcnow().isoformat(),
            "data_hashes": data_hashes,
            "assumptions": {
                "execution": "Continuous intrabar High/Low stops with conservative gap fill",
                "funding": "Event-based 8h settlement (00:00, 08:00, 16:00 UTC)",
                "fees": "0.04% taker fee + 0.04% regular slippage + 0.10% stop slippage + 0.15% gap slippage",
                "stop_losses": {"ETHUSDT": 0.025, "SOLUSDT": 0.050},
                "deadband": 0.20,
            },
            "disclaimer": "Research backtest result under stated continuous simulation assumptions. Not an independently verified live-trading result.",
        },
        "trial_trading": {},
        "raw_baseline": {},
    }

    for name, start_d, end_d in slices_to_extract:
        rep_t = res_trial.slice_report(start_d, end_d)
        rep_b = res_base.slice_report(start_d, end_d)

        metrics["trial_trading"][name] = rep_t.to_summary_dict()
        metrics["raw_baseline"][name] = rep_b.to_summary_dict()

    # 4. Save to docs/metrics.json
    output_path = ROOT_DIR / "docs" / "metrics.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    print(f"\n[3/3] Successfully generated and exported metrics to: {output_path}")

    # Summary Display
    val_t = metrics["trial_trading"]["val_2024_2025"]
    str_t = metrics["trial_trading"]["stress_2026"]
    oct_t = metrics["trial_trading"]["october_2025"]
    print("\nKey Institutional Summary (Trial Mode):")
    print(f"- 2024-2025 Portfolio Return: +{val_t['portfolio_return_pct']}% | Max DD: {val_t['portfolio_max_drawdown_pct']}% | Sharpe: {val_t['portfolio_daily_sharpe']}")
    print(f"- 2026 Stress Period Return: {str_t['portfolio_return_pct']}% | Max DD: {str_t['portfolio_max_drawdown_pct']}% | Sharpe: {str_t['portfolio_daily_sharpe']}")
    print(f"- October 2025 Portfolio Return: {oct_t['portfolio_return_pct']}% | Max DD: {oct_t['portfolio_max_drawdown_pct']}%")


if __name__ == "__main__":
    main()
