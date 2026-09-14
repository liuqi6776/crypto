# -*- coding: utf-8 -*-
"""
Purged Walk-Forward Semi-Annual Slice Analysis (Phase 17)
Breaks continuous out-of-sample history into 5 non-resetting semi-annual evaluation windows:
1. 2024 H1 (2024-01-01 to 2024-06-30)
2. 2024 H2 (2024-07-01 to 2024-12-31)
3. 2025 H1 (2025-01-01 to 2025-06-30)
4. 2025 H2 (2025-07-01 to 2025-12-31)
5. 2026 Stress Period (2026-01-01 to 2026-09-13)

Reports continuous carryover positions, intra-window Sharpe, and max drawdown.
"""

import sys
import json
from pathlib import Path
import pandas as pd
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from crypto_quant.portfolio import MultiAssetPortfolioEngine


def run_walk_forward():
    print("=" * 75)
    print("Running Semi-Annual Purged Walk-Forward Evaluation Windows")
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

    # 2. Run continuous portfolio simulation
    engine = MultiAssetPortfolioEngine(trial_mode=True)
    res = engine.run(mkt_dict, pred_dict, fund_dict, fng_ser)

    windows = [
        {"id": "2024 H1", "start": "2024-01-01", "end": "2024-06-30"},
        {"id": "2024 H2", "start": "2024-07-01", "end": "2024-12-31"},
        {"id": "2025 H1", "start": "2025-01-01", "end": "2025-06-30"},
        {"id": "2025 H2", "start": "2025-07-01", "end": "2025-12-31"},
        {"id": "2026 Stress", "start": "2026-01-01", "end": "2026-09-13"},
    ]

    results = []

    print(f"\n{'Window':<14} | {'Date Range':<23} | {'Portfolio Ret':<14} | {'Sharpe':<8} | {'Max DD':<10} | {'Calmar':<8}")
    print("-" * 87)

    for w in windows:
        rep = res.slice_report(w["start"], w["end"])
        row = {
            "window": w["id"],
            "start_date": w["start"],
            "end_date": w["end"],
            "portfolio_return_pct": round(rep.total_return * 100.0, 2),
            "portfolio_daily_sharpe": round(rep.daily_sharpe, 2),
            "portfolio_max_drawdown_pct": round(rep.max_drawdown * 100.0, 2),
            "portfolio_calmar": round(rep.calmar_ratio, 2),
            "asset_breakdown": {
                sym: {
                    "return_pct": round(a_rep.total_return * 100.0, 2),
                    "sharpe": round(a_rep.daily_sharpe, 2),
                    "max_dd_pct": round(a_rep.max_drawdown * 100.0, 2),
                    "win_rate_pct": round(a_rep.win_rate * 100.0, 2),
                    "trades": a_rep.total_trades,
                }
                for sym, a_rep in rep.asset_reports.items()
            }
        }
        results.append(row)

        date_str = f"{w['start']} to {w['end']}"
        print(f"{row['window']:<14} | {date_str:<23} | {row['portfolio_return_pct']:>13.2f}% | {row['portfolio_daily_sharpe']:>8.2f} | {row['portfolio_max_drawdown_pct']:>9.2f}% | {row['portfolio_calmar']:>8.2f}")

    output_path = ROOT_DIR / "docs" / "purged_walk_forward.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"walk_forward_windows": results}, f, indent=2, ensure_ascii=False)

    print(f"\n[Artifact Saved] Walk-forward results saved to: {output_path}")
    return results


if __name__ == "__main__":
    run_walk_forward()
