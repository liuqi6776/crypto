# -*- coding: utf-8 -*-
"""
Stationary Block Bootstrap Statistical Inference (Phase 17)
Evaluates statistical significance of strategy returns via 2,000 block bootstrap iterations:
1. Block size: 6 days (36 4h bars) to preserve temporal autocorrelation.
2. Generates 95% confidence intervals (2.5th to 97.5th percentile) for Return, Sharpe, MDD.
3. Computes probability of beating cash P(Sharpe > 0) and probability of beating Buy & Hold.
"""

import sys
import json
from pathlib import Path
import pandas as pd
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from crypto_quant.portfolio import MultiAssetPortfolioEngine


def run_block_bootstrap(n_iterations: int = 2000, block_size_days: int = 6):
    print("=" * 75)
    print(f"Running Stationary Block Bootstrap Inference ({n_iterations:,} iterations, block={block_size_days}d)")
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

    # 2. Run simulation to get daily returns series
    engine = MultiAssetPortfolioEngine(trial_mode=True)
    res = engine.run(mkt_dict, pred_dict, fund_dict, fng_ser)

    eq_series = res.combined_equity.loc["2024-01-01":"2025-12-31"]
    daily_eq = eq_series.resample("1D").last().dropna()
    daily_rets = daily_eq.pct_change().dropna().values

    # Benchmark: 50/50 ETH + SOL Buy & Hold
    eth_c = df_eth["close"].loc["2024-01-01":"2025-12-31"].resample("1D").last().dropna()
    sol_c = df_sol["close"].loc["2024-01-01":"2025-12-31"].resample("1D").last().dropna()
    bh_eq = 0.5 * (eth_c / eth_c.iloc[0]) + 0.5 * (sol_c / sol_c.iloc[0])
    bh_rets = bh_eq.pct_change().dropna().values

    n_days = len(daily_rets)
    block_len = block_size_days
    num_blocks = int(np.ceil(n_days / block_len))

    # 3. Bootstrap Sampling
    np.random.seed(42)
    boot_returns = []
    boot_sharpes = []
    boot_mdds = []
    beats_bh_count = 0

    for _ in range(n_iterations):
        # Draw block start indices
        start_indices = np.random.randint(0, n_days - block_len + 1, size=num_blocks)
        sampled_rets = []
        sampled_bh_rets = []
        for idx in start_indices:
            sampled_rets.extend(daily_rets[idx : idx + block_len])
            sampled_bh_rets.extend(bh_rets[idx : idx + block_len])

        sampled_rets = np.array(sampled_rets[:n_days])
        sampled_bh = np.array(sampled_bh_rets[:n_days])

        # Equity curve
        eq_curve = np.cumprod(1.0 + sampled_rets)
        tot_ret = float(eq_curve[-1] - 1.0)
        boot_returns.append(tot_ret)

        bh_curve = np.cumprod(1.0 + sampled_bh)
        if tot_ret > (bh_curve[-1] - 1.0):
            beats_bh_count += 1

        # Sharpe
        std_r = float(np.std(sampled_rets))
        mean_r = float(np.mean(sampled_rets))
        sh = (mean_r / (std_r + 1e-8)) * np.sqrt(365)
        boot_sharpes.append(sh)

        # Max Drawdown
        peak = np.maximum.accumulate(eq_curve)
        dd = (eq_curve - peak) / peak
        boot_mdds.append(float(np.min(dd)))

    boot_returns = np.array(boot_returns)
    boot_sharpes = np.array(boot_sharpes)
    boot_mdds = np.array(boot_mdds)

    p_val_positive_sharpe = float(np.mean(boot_sharpes > 0))
    p_val_positive_return = float(np.mean(boot_returns > 0))
    p_val_beat_bh = float(beats_bh_count / n_iterations)

    ret_ci = (float(np.percentile(boot_returns, 2.5)), float(np.percentile(boot_returns, 97.5)))
    sharpe_ci = (float(np.percentile(boot_sharpes, 2.5)), float(np.percentile(boot_sharpes, 97.5)))
    mdd_ci = (float(np.percentile(boot_mdds, 2.5)), float(np.percentile(boot_mdds, 97.5)))

    print(f"\nBootstrap 95% Confidence Intervals (2024–2025):")
    print(f"- Total Return:      [{ret_ci[0]*100.0:+.2f}%, {ret_ci[1]*100.0:+.2f}%] (Median: {np.median(boot_returns)*100.0:+.2f}%)")
    print(f"- Annualized Sharpe: [{sharpe_ci[0]:+.2f}, {sharpe_ci[1]:+.2f}] (Median: {np.median(boot_sharpes):+.2f})")
    print(f"- Maximum Drawdown:  [{mdd_ci[0]*100.0:.2f}%, {mdd_ci[1]*100.0:.2f}%] (Median: {np.median(boot_mdds)*100.0:.2f}%)")
    print(f"\nStatistical Probabilities:")
    print(f"- P(Return > 0):      {p_val_positive_return:.2%}")
    print(f"- P(Sharpe > 0):      {p_val_positive_sharpe:.2%}")
    print(f"- P(Beat Buy & Hold): {p_val_beat_bh:.2%}")

    output_path = ROOT_DIR / "docs" / "block_bootstrap.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "iterations": n_iterations,
            "block_size_days": block_size_days,
            "sample_period": "2024-01-01 to 2025-12-31",
            "ci_95": {
                "return_lower_pct": round(ret_ci[0] * 100.0, 2),
                "return_upper_pct": round(ret_ci[1] * 100.0, 2),
                "return_median_pct": round(float(np.median(boot_returns)) * 100.0, 2),
                "sharpe_lower": round(sharpe_ci[0], 2),
                "sharpe_upper": round(sharpe_ci[1], 2),
                "sharpe_median": round(float(np.median(boot_sharpes)), 2),
                "mdd_lower_pct": round(mdd_ci[0] * 100.0, 2),
                "mdd_upper_pct": round(mdd_ci[1] * 100.0, 2),
                "mdd_median_pct": round(float(np.median(boot_mdds)) * 100.0, 2),
            },
            "probabilities": {
                "p_return_gt_zero": round(p_val_positive_return, 4),
                "p_sharpe_gt_zero": round(p_val_positive_sharpe, 4),
                "p_beat_buy_and_hold": round(p_val_beat_bh, 4),
            }
        }, f, indent=2, ensure_ascii=False)

    print(f"\n[Artifact Saved] Bootstrap results saved to: {output_path}")


if __name__ == "__main__":
    run_block_bootstrap()
