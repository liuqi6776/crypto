# -*- coding: utf-8 -*-
"""
Unified 4-Hour Trend Re-Simulation & Controlled Benchmark Runner (Phase 37.3)
=============================================================================
Executes:
Step 1: Exact Reproduction of original registered results in original datasets and windows.
Step 2: Standardized Controlled Benchmark across 6 core models and stress variants on clean Spot data.
        - M1A: Structural Trend (ETH/SOL 50/50, Mode A Bar-Close Exit)
        - M1B: Structural Trend (ETH/SOL 50/50, Mode B Intrabar Stop Touch - Stress Scenario)
        - M2: Simple EMA Control ETH/SOL 50/50 (Direct apples-to-apples asset control)
        - M3: Simple EMA Control Core-4 (BTC/ETH/SOL/BNB 25% each)
        - M4: Core-4 Top-1 Rotation Candidate (0.30 buffer, structural exit)
        - M5: BTC Buy & Hold
        - M6: Core-4 Equal-Weight (EW 25%) Buy & Hold
        - Additional Mode B Slippage Stress Tests (15 bps, 30 bps, 50 bps)
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from crypto_quant.backtest.unified_4h_engine import Unified4hEngine, StopLossMode
from crypto_quant.structural_trend_engine import StructuralTrendEngine
from crypto_quant.backtest.clean_single_ledger_engine import SingleLedgerSimulator

OUT_DIR = repo_root / "reports" / "unified_4h_comparison"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def calculate_metrics(bar_ledger: pd.DataFrame, trades: pd.DataFrame, initial_cash: float = 10000.0) -> Dict[str, Any]:
    """Calculates standardized performance metrics from a continuous 4h bar ledger."""
    equity = bar_ledger["total_equity"]
    ret_series = equity.pct_change().dropna()

    # Daily sampled equity for standard Sharpe ratio
    daily_equity = equity.resample("1D").last().dropna()
    daily_ret = daily_equity.pct_change().dropna()

    total_ret_pct = float((equity.iloc[-1] / initial_cash - 1.0) * 100.0)

    # Max Drawdown
    cummax = equity.cummax()
    dd = (cummax - equity) / cummax
    max_dd_pct = float(dd.max() * 100.0)

    # Sharpe ratio
    sharpe = float(daily_ret.mean() / (daily_ret.std() + 1e-9) * np.sqrt(365)) if len(daily_ret) > 1 else 0.0

    # Calmar ratio
    cagr = float(((equity.iloc[-1] / initial_cash) ** (365.25 / max(1, (equity.index[-1] - equity.index[0]).days)) - 1.0) * 100.0)
    calmar = float(cagr / max_dd_pct) if max_dd_pct > 0 else 0.0

    # Average Cash %
    cash_pct_series = (bar_ledger["cash"] / bar_ledger["total_equity"]).clip(0.0, 1.0)
    avg_cash_pct = float(cash_pct_series.mean() * 100.0)

    # Trade stats
    n_trades = len(trades) if not trades.empty else 0
    if n_trades > 0 and "net_pnl_usd" in trades.columns:
        wins = trades[trades["net_pnl_usd"] > 0]
        win_rate = float(len(wins) / n_trades * 100.0)
        gross_profit = float(trades[trades["net_pnl_usd"] > 0]["net_pnl_usd"].sum())
        gross_loss = float(abs(trades[trades["net_pnl_usd"] < 0]["net_pnl_usd"].sum()))
        profit_factor = float(gross_profit / (gross_loss + 1e-9)) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)

        # Top 3 trades profit share
        sorted_trades = trades.sort_values(by="net_pnl_usd", ascending=False)
        top3_sum = float(sorted_trades["net_pnl_usd"].iloc[:3].sum())
        net_profit_sum = float(trades["net_pnl_usd"].sum())
        top3_share = float(top3_sum / net_profit_sum * 100.0) if net_profit_sum > 0 else 0.0
    else:
        win_rate = 0.0
        profit_factor = 0.0
        top3_share = 0.0

    # Max Drawdown Recovery Duration (in days)
    peak_dates = dd[dd == 0].index
    recovery_days = 0
    if len(peak_dates) > 1:
        diffs = (peak_dates[1:] - peak_dates[:-1]).total_seconds() / 86400.0
        recovery_days = int(np.max(diffs))

    return {
        "net_return_pct": round(total_ret_pct, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "annualized_sharpe": round(sharpe, 2),
        "calmar_ratio": round(calmar, 2),
        "avg_cash_pct": round(avg_cash_pct, 1),
        "total_trades": n_trades,
        "win_rate_pct": round(win_rate, 1),
        "profit_factor": round(profit_factor, 2),
        "top3_trades_profit_share_pct": round(top3_share, 1),
        "max_dd_recovery_days": recovery_days,
        "final_equity_usd": round(float(equity.iloc[-1]), 2),
        "total_friction_usd": round(float(bar_ledger["cum_fees"].iloc[-1] + bar_ledger["cum_slippage"].iloc[-1]), 2),
    }


def calculate_annual_metrics(bar_ledger: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    """Calculates year-by-year and regime breakdown for a strategy."""
    years = [2021, 2022, 2023, 2024, 2025, 2026]
    rows = []

    for yr in years:
        start_t = f"{yr}-01-01 00:00:00"
        end_t = f"{yr}-12-31 23:59:59"
        sub_ledger = bar_ledger.loc[start_t:end_t]
        if sub_ledger.empty:
            continue

        init_eq = sub_ledger["total_equity"].iloc[0]
        sub_trades = pd.DataFrame()
        if not trades.empty and "exit_time" in trades.columns:
            sub_trades = trades[(trades["exit_time"] >= start_t) & (trades["exit_time"] <= end_t)]

        m = calculate_metrics(sub_ledger, sub_trades, initial_cash=init_eq)
        m["year"] = str(yr)
        m["initial_equity"] = round(init_eq, 2)
        rows.append(m)

    # Full Cycle
    full_m = calculate_metrics(bar_ledger, trades, initial_cash=bar_ledger["total_equity"].iloc[0])
    full_m["year"] = "Full_Cycle"
    full_m["initial_equity"] = round(bar_ledger["total_equity"].iloc[0], 2)
    rows.append(full_m)

    return pd.DataFrame(rows)


def main():
    print("=" * 75)
    print("PHASE 37.3: TWO-STEP RE-SIMULATION & CORRECT SINGLE-LEDGER ACCOUNTING")
    print("=" * 75)

    # =========================================================================
    # STEP 1: ORIGINAL REPRODUCTION (原口径复现)
    # =========================================================================
    print("\n--- STEP 1: EXECUTING ORIGINAL REPRODUCTIONS ---")
    step1_rows = []

    # 1.1 Structural Trend Original Reproduction (2024-01-01 to 2026-09-01)
    print("[STEP 1.1] Reproducing Structural Trend (ETH/SOL 50/50, 2024-2026, Original Engine)...")
    from scripts.validate_structural_trend_deep import run_clean_evaluation, load_candles_and_funding
    candles, df_funding = load_candles_and_funding()
    clean_eval, _, _ = run_clean_evaluation(candles, df_funding, "2024-01-01 00:00:00", "2026-09-01 12:00:00", fee=0.0008)
    st_ret_pct = float(clean_eval["PORTFOLIO_50_50"]["total_return_pct"])

    print(f"-> Structural Trend Original Reproduction Return: {st_ret_pct:+.2f}% (Registry Registered: +107.36%)")
    step1_rows.append({
        "strategy": "Structural_Trend_ETH_SOL_50_50",
        "eval_period": "2024-01-01 to 2026-09-01",
        "original_data_source": "Local Historical Parquet (with funding)",
        "reproduced_return_pct": round(st_ret_pct, 2),
        "registry_target_return_pct": 107.36,
        "delta_error_pct": round(abs(st_ret_pct - 107.36), 2),
        "status": "VERIFIED_MATCH" if abs(st_ret_pct - 107.36) < 2.0 else "DIVERGENT",
    })

    # 1.2 Candidate Top-1 Rotation Reproduction (2020-10-15 to 2026-09-23)
    print("[STEP 1.2] Reproducing Top-1 Rotation Candidate (Buffer 0.30, Full Cycle, SingleLedgerSimulator)...")
    core4_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
    local_dfs = {s: pd.read_parquet(repo_root / "data" / f"{s}_4h_2020_2026.parquet") for s in core4_symbols}

    sim_cand = SingleLedgerSimulator(
        symbols=core4_symbols,
        raw_dfs=local_dfs,
        leverage=1.0,
        fee_rate=0.0008,
        execution_slippage=0.0005,
        stop_slippage=0.0015,
        delta_score_buffer=0.30,
        enable_atr_stop=False,
        initial_cash=10000.0,
    )
    res_cand = sim_cand.run("2020-10-15 00:00:00", "2026-09-23 00:00:00")
    cand_ret_pct = float(res_cand["total_ret_pct"])
    print(f"-> Candidate Top-1 Reproduction Return: {cand_ret_pct:+.2f}% (Target: +43,942.30%)")
    step1_rows.append({
        "strategy": "Candidate_Top1_Rotation_Buffer030",
        "eval_period": "2020-10-15 to 2026-09-23",
        "original_data_source": "Local Historical Parquet (1.0x Spot)",
        "reproduced_return_pct": round(cand_ret_pct, 2),
        "registry_target_return_pct": 43942.30,
        "delta_error_pct": round(abs(cand_ret_pct - 43942.30), 2),
        "status": "VERIFIED_MATCH" if abs(cand_ret_pct - 43942.30) < 1.0 else "DIVERGENT",
    })

    df_step1 = pd.DataFrame(step1_rows)
    df_step1.to_csv(OUT_DIR / "step1_reproduction.csv", index=False)
    print(f"[SAVED] Step 1 Reproduction Table saved to {OUT_DIR / 'step1_reproduction.csv'}")

    # =========================================================================
    # STEP 2: STANDARDIZED CONTROLLED BENCHMARK ON SPOT DATA (统一现货同场对照)
    # =========================================================================
    print("\n--- STEP 2: EXECUTING STANDARDIZED SPOT CONTROLLED BENCHMARKS ---")
    spot_dir = repo_root / "data" / "spot"
    spot_dfs = {s: pd.read_parquet(spot_dir / f"{s}_4h_2020_2026.parquet") for s in core4_symbols}

    eval_start_dt = "2020-10-15 00:00:00"
    eval_end_dt = "2026-09-23 00:00:00"

    # Sliced to [eval_start_dt, eval_end_dt)
    spot_eval_dfs = {}
    for s, df in spot_dfs.items():
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        spot_eval_dfs[s] = df.loc[eval_start_dt:eval_end_dt]

    all_models_summary = []
    all_annual_records = []

    # Model 1A: Structural Trend (Mode A: Bar-Close Exit)
    print("[RUNNING MODEL 1A] Structural Trend ETH/SOL 50/50 (Mode A: Bar-Close Exit)...")
    engine_m1a = Unified4hEngine(initial_cash=10000.0, stop_loss_mode=StopLossMode.BAR_CLOSE)
    res_m1a = engine_m1a.run_structural_trend(spot_eval_dfs, symbols=["ETHUSDT", "SOLUSDT"])
    res_m1a["bar_ledger"].to_csv(OUT_DIR / "bar_ledger_M1A_Structural_Trend_Close.csv")
    res_m1a["trades"].to_csv(OUT_DIR / "trades_M1A_Structural_Trend_Close.csv", index=False)

    m1a_metrics = calculate_metrics(res_m1a["bar_ledger"], res_m1a["trades"])
    m1a_metrics["model_key"] = "M1A_Structural_Trend_Close"
    m1a_metrics["strategy_name"] = "Structural Trend (ETH/SOL 50/50, Mode A Bar-Close)"
    m1a_metrics["role"] = "DEVELOPMENT_STRESS_TEST"
    all_models_summary.append(m1a_metrics)

    m1a_annual = calculate_annual_metrics(res_m1a["bar_ledger"], res_m1a["trades"])
    m1a_annual["model_key"] = "M1A_Structural_Trend_Close"
    all_annual_records.append(m1a_annual)

    # Model 1B: Structural Trend (Mode B: Intrabar Stop Touch - Stress Scenario)
    print("[RUNNING MODEL 1B] Structural Trend ETH/SOL 50/50 (Mode B: Intrabar Stop Touch - Stress Scenario)...")
    engine_m1b = Unified4hEngine(initial_cash=10000.0, stop_loss_mode=StopLossMode.INTRABAR_STOP_TOUCH, stop_slippage=0.0015)
    res_m1b = engine_m1b.run_structural_trend(spot_eval_dfs, symbols=["ETHUSDT", "SOLUSDT"])
    res_m1b["bar_ledger"].to_csv(OUT_DIR / "bar_ledger_M1B_Structural_Trend_Intrabar.csv")
    res_m1b["trades"].to_csv(OUT_DIR / "trades_M1B_Structural_Trend_Intrabar.csv", index=False)

    m1b_metrics = calculate_metrics(res_m1b["bar_ledger"], res_m1b["trades"])
    m1b_metrics["model_key"] = "M1B_Structural_Trend_Intrabar"
    m1b_metrics["strategy_name"] = "Structural Trend (ETH/SOL 50/50, Mode B Intrabar Stop Touch)"
    m1b_metrics["role"] = "STRESS_TEST_SCENARIO"
    all_models_summary.append(m1b_metrics)

    m1b_annual = calculate_annual_metrics(res_m1b["bar_ledger"], res_m1b["trades"])
    m1b_annual["model_key"] = "M1B_Structural_Trend_Intrabar"
    all_annual_records.append(m1b_annual)

    # Model 2: Simple EMA Control ETH/SOL 50/50 (Direct apples-to-apples asset control)
    print("[RUNNING MODEL 2] Simple EMA Control ETH/SOL 50/50 (Direct Asset Universe Control)...")
    engine_m2 = Unified4hEngine(initial_cash=10000.0)
    res_m2 = engine_m2.run_simple_ema_control(spot_eval_dfs, symbols=["ETHUSDT", "SOLUSDT"])
    res_m2["bar_ledger"].to_csv(OUT_DIR / "bar_ledger_M2_Simple_EMA_ETHSOL.csv")
    res_m2["trades"].to_csv(OUT_DIR / "trades_M2_Simple_EMA_ETHSOL.csv", index=False)

    m2_metrics = calculate_metrics(res_m2["bar_ledger"], res_m2["trades"])
    m2_metrics["model_key"] = "M2_Simple_EMA_ETHSOL"
    m2_metrics["strategy_name"] = "Simple EMA Control (ETH/SOL 50/50, No Rotation)"
    m2_metrics["role"] = "CONTROL_BENCHMARK"
    all_models_summary.append(m2_metrics)

    m2_annual = calculate_annual_metrics(res_m2["bar_ledger"], res_m2["trades"])
    m2_annual["model_key"] = "M2_Simple_EMA_ETHSOL"
    all_annual_records.append(m2_annual)

    # Model 3: Simple EMA Control Core-4 (BTC/ETH/SOL/BNB 25% each)
    print("[RUNNING MODEL 3] Simple EMA Control Core-4 (BTC/ETH/SOL/BNB 25% each)...")
    engine_m3 = Unified4hEngine(initial_cash=10000.0)
    res_m3 = engine_m3.run_simple_ema_control(spot_eval_dfs, symbols=core4_symbols)
    res_m3["bar_ledger"].to_csv(OUT_DIR / "bar_ledger_M3_Simple_EMA_Core4.csv")
    res_m3["trades"].to_csv(OUT_DIR / "trades_M3_Simple_EMA_Core4.csv", index=False)

    m3_metrics = calculate_metrics(res_m3["bar_ledger"], res_m3["trades"])
    m3_metrics["model_key"] = "M3_Simple_EMA_Core4"
    m3_metrics["strategy_name"] = "Simple EMA Control (Core-4 25% Each, No Rotation)"
    m3_metrics["role"] = "CONTROL_BENCHMARK"
    all_models_summary.append(m3_metrics)

    m3_annual = calculate_annual_metrics(res_m3["bar_ledger"], res_m3["trades"])
    m3_annual["model_key"] = "M3_Simple_EMA_Core4"
    all_annual_records.append(m3_annual)

    # Model 4: Core-4 Top-1 Rotation Candidate (0.30 buffer, structural exit) on SPOT data
    print("[RUNNING MODEL 4] Core-4 Top-1 Rotation Candidate (0.30 buffer on Spot Data)...")
    sim_m4 = SingleLedgerSimulator(
        symbols=core4_symbols,
        raw_dfs=spot_eval_dfs,
        leverage=1.0,
        fee_rate=0.0008,
        execution_slippage=0.0005,
        stop_slippage=0.0015,
        delta_score_buffer=0.30,
        enable_atr_stop=False,
        initial_cash=10000.0,
    )
    res_m4 = sim_m4.run(eval_start_dt, eval_end_dt)
    m4_bar_ledger = pd.DataFrame(res_m4["bar_records"]).set_index("bar_time")
    m4_bar_ledger["total_equity"] = m4_bar_ledger["equity"]
    m4_bar_ledger["cum_fees"] = res_m4["total_fees"]
    m4_bar_ledger["cum_slippage"] = res_m4["total_slippage"]
    m4_trades = pd.DataFrame([t.__dict__ for t in res_m4["trades_list"]]) if res_m4["trades_list"] else pd.DataFrame()
    if not m4_trades.empty:
        m4_trades["net_pnl_usd"] = m4_trades["net_pnl_usdt"]
    m4_bar_ledger.to_csv(OUT_DIR / "bar_ledger_M4_Top1_Rotation_Candidate.csv")
    m4_trades.to_csv(OUT_DIR / "trades_M4_Top1_Rotation_Candidate.csv", index=False)

    m4_metrics = calculate_metrics(m4_bar_ledger, m4_trades)
    m4_metrics["model_key"] = "M4_Top1_Rotation_Candidate"
    m4_metrics["strategy_name"] = "Top-1 Rotation Candidate (Buffer 0.30, Clean Spot)"
    m4_metrics["role"] = "HYPOTHESIS_EXPERIMENT"
    all_models_summary.append(m4_metrics)

    m4_annual = calculate_annual_metrics(m4_bar_ledger, m4_trades)
    m4_annual["model_key"] = "M4_Top1_Rotation_Candidate"
    all_annual_records.append(m4_annual)

    # Model 5: BTC Buy & Hold
    print("[RUNNING MODEL 5] BTC Buy & Hold...")
    engine_m5 = Unified4hEngine(initial_cash=10000.0)
    res_m5 = engine_m5.run_buy_and_hold(spot_eval_dfs, symbols=["BTCUSDT"])
    res_m5["bar_ledger"].to_csv(OUT_DIR / "bar_ledger_M5_BTC_Buy_Hold.csv")

    m5_metrics = calculate_metrics(res_m5["bar_ledger"], res_m5["trades"])
    m5_metrics["model_key"] = "M5_BTC_Buy_Hold"
    m5_metrics["strategy_name"] = "BTC Buy & Hold (Market Beta)"
    m5_metrics["role"] = "MARKET_BENCHMARK"
    all_models_summary.append(m5_metrics)

    m5_annual = calculate_annual_metrics(res_m5["bar_ledger"], res_m5["trades"])
    m5_annual["model_key"] = "M5_BTC_Buy_Hold"
    all_annual_records.append(m5_annual)

    # Model 6: Core-4 Equal-Weight (EW 25%) Buy & Hold
    print("[RUNNING MODEL 6] Core-4 Equal-Weight (EW 25%) Buy & Hold...")
    engine_m6 = Unified4hEngine(initial_cash=10000.0)
    res_m6 = engine_m6.run_buy_and_hold(spot_eval_dfs, symbols=core4_symbols)
    res_m6["bar_ledger"].to_csv(OUT_DIR / "bar_ledger_M6_Core4_EW_Buy_Hold.csv")

    m6_metrics = calculate_metrics(res_m6["bar_ledger"], res_m6["trades"])
    m6_metrics["model_key"] = "M6_Core4_EW_Buy_Hold"
    m6_metrics["strategy_name"] = "Core-4 Equal-Weight Buy & Hold (Market Beta)"
    m6_metrics["role"] = "MARKET_BENCHMARK"
    all_models_summary.append(m6_metrics)

    m6_annual = calculate_annual_metrics(res_m6["bar_ledger"], res_m6["trades"])
    m6_annual["model_key"] = "M6_Core4_EW_Buy_Hold"
    all_annual_records.append(m6_annual)

    # Additional Sensitivity Stress Tests on Mode B: 30 bps and 50 bps Slippage
    print("\n--- RUNNING MODE B SLIPPAGE STRESS SENSITIVITY ---")
    stress_rows = []
    for slip_val, tag in [(0.0015, "Mode_B_Baseline_15bps"), (0.0030, "Mode_B_Stress_30bps"), (0.0050, "Mode_B_Stress_50bps")]:
        eng_stress = Unified4hEngine(initial_cash=10000.0, stop_loss_mode=StopLossMode.INTRABAR_STOP_TOUCH, stop_slippage=slip_val)
        res_stress = eng_stress.run_structural_trend(spot_eval_dfs, symbols=["ETHUSDT", "SOLUSDT"])
        s_m = calculate_metrics(res_stress["bar_ledger"], res_stress["trades"])
        s_m["stop_slippage_bps"] = int(slip_val * 10000)
        s_m["scenario_tag"] = tag
        stress_rows.append(s_m)

    df_stress = pd.DataFrame(stress_rows)
    df_stress.to_csv(OUT_DIR / "mode_b_slippage_stress.csv", index=False)
    print(f"[SAVED] Mode B Slippage Stress Table saved to {OUT_DIR / 'mode_b_slippage_stress.csv'}")

    # Save Unified Summary CSV
    df_summary = pd.DataFrame(all_models_summary)
    df_summary = df_summary[[
        "model_key", "strategy_name", "role", "net_return_pct", "max_drawdown_pct",
        "annualized_sharpe", "calmar_ratio", "avg_cash_pct", "total_trades",
        "win_rate_pct", "profit_factor", "top3_trades_profit_share_pct",
        "max_dd_recovery_days", "final_equity_usd", "total_friction_usd"
    ]]
    df_summary.to_csv(OUT_DIR / "unified_summary.csv", index=False)
    print(f"[SAVED] Unified Summary CSV saved to {OUT_DIR / 'unified_summary.csv'}")

    # Save Annual Breakdown CSV
    df_annual = pd.concat(all_annual_records, ignore_index=True)
    df_annual.to_csv(OUT_DIR / "annual_breakdown.csv", index=False)
    print(f"[SAVED] Annual Breakdown CSV saved to {OUT_DIR / 'annual_breakdown.csv'}")

    print("\n" + "=" * 75)
    print("STEP 2 RE-SIMULATION COMPLETED SUCCESSFULLY!")
    print("=" * 75)


if __name__ == "__main__":
    main()
