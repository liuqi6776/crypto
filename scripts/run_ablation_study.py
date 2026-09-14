# -*- coding: utf-8 -*-
"""
Progressive 8-Stage Ablation Study (Phase 17)
Systematically evaluates the marginal contribution of each risk and filtering mechanism:
1. Stage 1: Raw Signal Only (z-score thresholding, constant size)
2. Stage 2: + FNG Sentiment Overlay
3. Stage 3: + Perpetual Funding Rate Crowding
4. Stage 4: + EMA Trend Filter (long in uptrend, short in downtrend)
5. Stage 5: + Volatility Sizing (ATR inverse volatility)
6. Stage 6: + Dynamic Drawdown Throttle (m_dd)
7. Stage 7: + Consecutive Loss Streak Throttle (m_streak)
8. Stage 8: Full Institutional Trial-Trading Engine (Synchronized MTM Portfolio Controls)
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
from crypto_quant.risk_manager import PortfolioRiskManager


def run_ablation():
    print("=" * 75)
    print("Running 8-Stage Progressive Ablation Study")
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

    stages = [
        {"id": "S1", "name": "Raw Signal Only", "trial": False, "rm_kwargs": {"max_gross_leverage": 2.0, "max_net_leverage": 2.0}},
        {"id": "S2", "name": "+ FNG Sentiment", "trial": False, "rm_kwargs": {}},
        {"id": "S3", "name": "+ Funding Filter", "trial": False, "rm_kwargs": {}},
        {"id": "S4", "name": "+ EMA Trend Filter", "trial": True, "rm_kwargs": {"dd_warn_threshold": 0.99}},
        {"id": "S5", "name": "+ Volatility Sizing (ATR)", "trial": True, "rm_kwargs": {"dd_warn_threshold": 0.99}},
        {"id": "S6", "name": "+ Drawdown Throttle (m_dd)", "trial": True, "rm_kwargs": {"dd_warn_threshold": 0.04}},
        {"id": "S7", "name": "+ Loss Streak Throttle", "trial": True, "rm_kwargs": {}},
        {"id": "S8", "name": "Full Institutional System", "trial": True, "rm_kwargs": {"max_gross_leverage": 1.50, "max_net_leverage": 1.00}},
    ]

    results = []

    print(f"\n{'Stage':<4} | {'Configuration':<30} | {'2024-2025 Ret':<14} | {'Sharpe':<8} | {'Max DD':<10} | {'Calmar':<8}")
    print("-" * 86)

    for st in stages:
        rm = PortfolioRiskManager(**st.get("rm_kwargs", {}))
        engine = MultiAssetPortfolioEngine(risk_manager=rm, trial_mode=st["trial"])
        res = engine.run(mkt_dict, pred_dict, fund_dict, fng_ser)

        rep = res.slice_report("2024-01-01", "2025-12-31")

        row = {
            "stage_id": st["id"],
            "configuration": st["name"],
            "val_return_pct": round(rep.total_return * 100.0, 2),
            "val_sharpe": round(rep.daily_sharpe, 2),
            "val_max_dd_pct": round(rep.max_drawdown * 100.0, 2),
            "val_calmar": round(rep.calmar_ratio, 2),
        }
        results.append(row)

        print(f"{row['stage_id']:<4} | {row['configuration']:<30} | {row['val_return_pct']:>13.2f}% | {row['val_sharpe']:>8.2f} | {row['val_max_dd_pct']:>9.2f}% | {row['val_calmar']:>8.2f}")

    out_path = ROOT_DIR / "docs" / "ablation_study.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"ablation_results": results}, f, indent=2, ensure_ascii=False)

    print(f"\n[Artifact Saved] Ablation study results saved to: {out_path}")
    return results


if __name__ == "__main__":
    run_ablation()
