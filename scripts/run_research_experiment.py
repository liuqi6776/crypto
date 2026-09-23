# -*- coding: utf-8 -*-
"""
Standardized Institutional Quant Research Experiment Runner
============================================================
Official reproducible execution pipeline enforcing:
1. One Official Baseline: Core-4 (BTC, ETH, SOL, BNB), 1.0x Spot, 8 bps fee, 5 bps execution slippage, 15 bps stop slippage.
2. Data Admission Quality Gate (strictly checked before execution).
3. Automatic Experiment Manifest Generation (captures Git commit hash, dirty status, data SHA256 hashes, exact CLI command).
4. Dual Evaluation Modes:
   - FRESH_START: Starts from cash at eval_start_dt.
   - CARRIED_STATE: Continuous historical state carried seamlessly into eval_start_dt.
5. Standardized Artifact Packaging in reports/experiments/<run_id>/:
   - manifest.json
   - data_admission_report.json & data_admission_report.md
   - trades.csv (Full trade-by-trade audit log)
   - bar_ledger.csv (Bar-by-bar cash, position, and equity ledger)
   - summary.json & summary.md (Institutional performance metrics)
"""

import sys
import os
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

# Add repo root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from crypto_quant.core.data_admission import validate_crypto_universe, DataAdmissionError
from crypto_quant.backtest.clean_single_ledger_engine import SingleLedgerSimulator
from crypto_quant.research.experiment_manifest import (
    generate_experiment_manifest,
    save_manifest,
    compute_output_hashes,
    finalize_manifest_with_outputs,
)

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

UNIVERSES = {
    "core4": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"],
    "top6": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "NEARUSDT", "SUIUSDT"],
    "top7": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "NEARUSDT", "SUIUSDT", "AVAXUSDT"],
    "top10": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "NEARUSDT", "SUIUSDT", "AVAXUSDT", "LINKUSDT", "ADAUSDT", "DOTUSDT"],
}

PERIODS = {
    "all": ("2020-10-15 00:00:00", "2026-09-23 00:00:00"),
    "2020-2024": ("2020-10-15 00:00:00", "2025-01-01 00:00:00"),
    "2025": ("2025-01-01 00:00:00", "2026-01-01 00:00:00"),
    "2026": ("2026-01-01 00:00:00", "2026-09-23 00:00:00"),
}


def parse_args():
    parser = argparse.ArgumentParser(description="Standardized Quant Research Experiment Runner")
    parser.add_argument("--universe", type=str, default="core4", help="Universe name (core4, top6, top7, top10) or comma-separated symbols")
    parser.add_argument("--leverage", type=float, default=1.0, help="Leverage multiplier (1.0 = Spot Baseline, 3.0 = Leveraged)")
    parser.add_argument("--period", type=str, default="all", help="Period key (all, 2020-2024, 2025, 2026) or custom 'START:END'")
    parser.add_argument("--mode", type=str, choices=["fresh", "carried"], default="fresh", help="Evaluation mode (fresh = fresh cash start, carried = continuous state carry-over)")
    parser.add_argument("--fee-rate", type=float, default=0.0008, help="One-way taker fee rate (default 0.0008 = 8 bps)")
    parser.add_argument("--execution-slippage", type=float, default=0.0005, help="Market execution slippage (default 0.0005 = 5 bps)")
    parser.add_argument("--stop-slippage", type=float, default=0.0015, help="Stop-out slippage (default 0.0015 = 15 bps)")
    parser.add_argument("--sl-atr-mult", type=float, default=1.5, help="ATR multiplier for stop loss (default 1.5)")
    parser.add_argument("--hysteresis", type=float, default=0.005, help="Hysteresis buffer around EMA200 (default 0.005 = 0.5%)")
    parser.add_argument("--delta-score-buffer", type=float, default=0.0, help="Momentum switching buffer (default 0.0, candidate uses 0.30)")
    parser.add_argument("--enable-atr-stop", dest="enable_atr_stop", action="store_true", default=True, help="Enable ATR stop loss (default True)")
    parser.add_argument("--no-atr-stop", dest="enable_atr_stop", action="store_false", help="Disable ATR stop loss (rely purely on structural trend exit)")
    parser.add_argument("--initial-cash", type=float, default=10000.0, help="Initial cash in USDT")
    parser.add_argument("--role", type=str, default=None, help="Experiment role (OFFICIAL_BASELINE, HYPOTHESIS_EXPERIMENT, DEVELOPMENT_STRESS_TEST)")
    parser.add_argument("--hypothesis", type=str, default=None, help="Pre-registered hypothesis for ablation or research experiments")
    parser.add_argument("--output-dir", type=str, default=None, help="Custom output directory for artifacts")
    return parser.parse_args()


def main():
    args = parse_args()

    # 1. Resolve Universe
    if args.universe.lower() in UNIVERSES:
        symbols = UNIVERSES[args.universe.lower()]
    else:
        symbols = [s.strip().upper() for s in args.universe.split(",") if s.strip()]

    # 2. Resolve Period
    if args.period.lower() in PERIODS:
        start_dt, end_dt = PERIODS[args.period.lower()]
    elif ":" in args.period:
        parts = args.period.split(":")
        start_dt, end_dt = parts[0].strip(), parts[1].strip()
    else:
        raise ValueError(f"Unknown period format '{args.period}'. Must be one of {list(PERIODS.keys())} or 'START:END'.")

    # 3. Resolve Role (Strict Date-Driven Classification)
    is_in_2026 = (start_dt >= "2026-01-01 00:00:00")
    if args.role:
        role = args.role
        if role == "OFFICIAL_BASELINE" and is_in_2026:
            raise ValueError(
                f"Research Discipline Violation: Interval starting in 2026 ({start_dt}) cannot be classified as OFFICIAL_BASELINE. "
                f"It must be classified as DEVELOPMENT_STRESS_TEST."
            )
    else:
        if is_in_2026:
            role = "DEVELOPMENT_STRESS_TEST"
        elif args.universe.lower() == "core4" and args.leverage == 1.0 and args.fee_rate == 0.0008 and args.execution_slippage == 0.0005 and args.stop_slippage == 0.0015 and args.sl_atr_mult == 1.5 and args.hysteresis == 0.005 and not is_in_2026:
            role = "OFFICIAL_BASELINE"
        else:
            role = "HYPOTHESIS_EXPERIMENT"

    if role == "HYPOTHESIS_EXPERIMENT" and not args.hypothesis:
        raise ValueError(
            "Research Discipline Violation: HYPOTHESIS_EXPERIMENT requires an explicit pre-registered hypothesis via --hypothesis."
        )

    # 4. Generate Run ID & Output Directory
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = f"exp_{args.universe.lower()}_L{int(args.leverage)}x_{args.period.replace('-', '_')}_{args.mode}_{timestamp_str}"
    out_dir = Path(args.output_dir) if args.output_dir else ROOT_DIR / "reports" / "experiments" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print(f" QUANT RESEARCH EXPERIMENT: {run_id}")
    print(f" Role: {role} | Mode: {args.mode.upper()} | Leverage: {args.leverage}x")
    print(f" Universe: {symbols}")
    print(f" Evaluation Interval: [{start_dt}, {end_dt}) UTC")
    if args.hypothesis:
        print(f" Pre-Registered Hypothesis: {args.hypothesis}")
    print("=" * 80)

    # 5. Load Data
    raw_dfs = {}
    data_files = {}
    for s in symbols:
        parquet_path = ROOT_DIR / "data" / f"{s}_4h_2020_2026.parquet"
        if not parquet_path.exists():
            raise FileNotFoundError(f"Missing required parquet data file: {parquet_path}")
        raw_dfs[s] = pd.read_parquet(parquet_path)
        data_files[s] = str(parquet_path)

    funding_path = ROOT_DIR / "data" / "binance_funding_8h.parquet"
    if funding_path.exists():
        df_funding = pd.read_parquet(funding_path)
        if df_funding.index.tz is not None:
            df_funding.index = df_funding.index.tz_localize(None)
        data_files["funding"] = str(funding_path)
    else:
        df_funding = None

    # 6. Data Admission Quality Check
    print("\n[Step 1/5] Running Data Admission Quality Gate...")
    admission_report = validate_crypto_universe(
        raw_dfs=raw_dfs,
        symbols=symbols,
        df_funding=df_funding if args.leverage > 1.0 else None,
        eval_start_dt=start_dt,
        eval_end_dt=end_dt,
        strict=True,
    )
    print(f"  Data Admission Passed: {admission_report.is_valid}")
    with open(out_dir / "data_admission_report.json", "w", encoding="utf-8") as f:
        json.dump(admission_report.to_dict(), f, indent=2, ensure_ascii=False)
    with open(out_dir / "data_admission_report.md", "w", encoding="utf-8") as f:
        f.write(admission_report.summary_markdown())

    # 7. Generate & Save Manifest
    print("\n[Step 2/5] Generating Experiment Reproducibility Manifest...")
    params = {
        "universe_name": args.universe,
        "symbols": symbols,
        "leverage": args.leverage,
        "period": args.period,
        "mode": args.mode,
        "fee_rate": args.fee_rate,
        "execution_slippage": args.execution_slippage,
        "stop_slippage": args.stop_slippage,
        "sl_atr_mult": args.sl_atr_mult,
        "hysteresis": args.hysteresis,
        "delta_score_buffer": args.delta_score_buffer,
        "enable_atr_stop": args.enable_atr_stop,
        "initial_cash": args.initial_cash,
    }
    manifest = generate_experiment_manifest(
        experiment_id=run_id,
        universe=symbols,
        data_files=data_files,
        parameters=params,
        eval_start_dt=start_dt,
        eval_end_dt=end_dt,
        role=role,
        description=f"Quantitative research evaluation of {args.universe} at {args.leverage}x leverage under {args.mode} mode.",
        hypothesis=args.hypothesis,
    )
    save_manifest(manifest, str(out_dir / "manifest.json"))
    print(f"  Manifest saved: Git commit {manifest['code_environment']['git_commit'][:8]} (Dirty: {manifest['code_environment']['git_dirty']})")

    # 8. Setup Simulator
    sim = SingleLedgerSimulator(
        symbols=symbols,
        raw_dfs=raw_dfs,
        df_funding=df_funding,
        leverage=args.leverage,
        fee_rate=args.fee_rate,
        execution_slippage=args.execution_slippage,
        stop_slippage=args.stop_slippage,
        sl_atr_mult=args.sl_atr_mult,
        hysteresis_pct=args.hysteresis,
        delta_score_buffer=args.delta_score_buffer,
        enable_atr_stop=args.enable_atr_stop,
        initial_cash=args.initial_cash,
    )

    # 9. Execute Backtest
    print("\n[Step 3/5] Executing Simulation...")
    carry_over_state = None
    if args.mode == "carried":
        # Run prior continuous history to extract exact carry-over state at start_dt
        print(f"  Extracting continuous state prior to {start_dt}...")
        res_prior = sim.run(start_dt="2020-10-15 00:00:00", end_dt=start_dt)
        if res_prior and res_prior.get("end_state"):
            carry_over_state = res_prior["end_state"]
            print(f"  Carried State successfully extracted: Pos={carry_over_state['curr_pos']}, Equity={carry_over_state['equity']:.2f}")

    sim_res = sim.run(
        start_dt=start_dt,
        end_dt=end_dt,
        carry_over_state=carry_over_state,
        data_admission_check=False,  # already verified in Step 1
    )

    if not sim_res:
        print("  Error: Simulation returned no data. Check time bounds and data alignment.")
        return

    # 10. Save Output Artifacts
    print("\n[Step 4/5] Packaging Verifiable Output Artifacts...")
    # A. Trades CSV
    trades_list = sim_res.get("trades_list", [])
    trades_dicts = [
        {
            "symbol": tr.symbol,
            "entry_time": str(tr.entry_time),
            "exit_time": str(tr.exit_time),
            "entry_price": tr.entry_price,
            "exit_price": tr.exit_price,
            "units": tr.units,
            "leverage": tr.leverage,
            "gross_pnl_usdt": tr.gross_pnl_usdt,
            "entry_fee_usdt": tr.entry_fee_usdt,
            "exit_fee_usdt": tr.exit_fee_usdt,
            "slippage_cost_usdt": tr.slippage_cost_usdt,
            "funding_cost_usdt": tr.funding_cost_usdt,
            "borrow_cost_usdt": tr.borrow_cost_usdt,
            "net_pnl_usdt": tr.net_pnl_usdt,
            "gross_ret_pct": tr.gross_ret_pct,
            "exit_reason": tr.exit_reason,
            "bars_held": tr.bars_held,
        }
        for tr in trades_list
    ]
    pd.DataFrame(trades_dicts).to_csv(out_dir / "trades.csv", index=False)

    # B. Bar Ledger CSV
    bar_records = sim_res.get("bar_records", [])
    pd.DataFrame(bar_records).to_csv(out_dir / "bar_ledger.csv", index=False)

    # C. Summary JSON & Markdown
    summary_metrics = {
        "run_id": run_id,
        "role": role,
        "universe": symbols,
        "leverage": args.leverage,
        "mode": args.mode,
        "eval_interval": f"[{start_dt}, {end_dt})",
        "initial_equity": sim_res["initial_equity"],
        "final_equity": sim_res["final_equity"],
        "final_cash": sim_res["final_cash"],
        "total_ret_pct": sim_res["total_ret_pct"],
        "cagr_pct": sim_res["cagr_pct"],
        "max_dd_pct": sim_res["max_dd_pct"],
        "sharpe": sim_res["sharpe"],
        "calmar": sim_res["calmar"],
        "win_rate": sim_res["win_rate"],
        "trade_count": sim_res["trade_count"],
        "stop_count": sim_res["stop_count"],
        "liquidated": sim_res["liquidated"],
        "liquidation_date": sim_res["liquidation_date"],
        "min_distance_to_liq_pct": sim_res["min_distance_to_liq_pct"],
        "total_fees": sim_res["total_fees"],
        "total_slippage": sim_res["total_slippage"],
        "total_funding": sim_res["total_funding"],
        "total_borrow": sim_res["total_borrow"],
        "is_perfectly_reconciled": sim_res["is_perfectly_reconciled"],
        "reconciliation_error": sim_res["reconciliation_error"],
        "expected_bars_count": sim_res["expected_bars_count"],
        "actual_bars_count": sim_res["actual_bars_count"],
        "missing_bars_count": sim_res["missing_bars_count"],
    }
    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary_metrics, f, indent=2, ensure_ascii=False)

    # D. Annual Breakdown CSV (if multi-year / full cycle)
    df_ledger = pd.DataFrame(bar_records)
    annual_breakdowns = []
    if not df_ledger.empty and "bar_time" in df_ledger.columns:
        df_ledger["bar_time"] = pd.to_datetime(df_ledger["bar_time"])
        df_ledger.set_index("bar_time", inplace=True)

        annual_regimes = [
            ("2021", "2021-01-01 00:00:00", "2022-01-01 00:00:00"),
            ("2022", "2022-01-01 00:00:00", "2023-01-01 00:00:00"),
            ("2023", "2023-01-01 00:00:00", "2024-01-01 00:00:00"),
            ("2024", "2024-01-01 00:00:00", "2025-01-01 00:00:00"),
            ("2025", "2025-01-01 00:00:00", "2026-01-01 00:00:00"),
            ("2026 (Stress)", "2026-01-01 00:00:00", "2026-09-23 00:00:00"),
            ("Full Cycle", start_dt, end_dt),
        ]

        for r_name, r_start, r_end in annual_regimes:
            sub = df_ledger.loc[r_start:r_end]
            if len(sub) >= 2:
                s_eq = float(sub["equity"].iloc[0])
                f_eq = float(sub["equity"].iloc[-1])
                ret_pct = ((f_eq / s_eq) - 1.0) * 100.0 if s_eq > 0 else 0.0

                cummax = sub["equity"].cummax()
                dd = (cummax - sub["equity"]) / cummax
                m_dd = float(dd.max() * 100.0)

                bar_rets = sub["equity"].pct_change().dropna()
                mean_r = bar_rets.mean()
                std_r = bar_rets.std()
                sh = float((mean_r / std_r) * np.sqrt(2190)) if std_r > 1e-12 else 0.0

                dur_years = (sub.index[-1] - sub.index[0]).total_seconds() / (365.25 * 86400)
                cagr = ((f_eq / s_eq) ** (1.0 / dur_years) - 1.0) * 100.0 if (dur_years > 0.1 and f_eq > 0 and s_eq > 0) else ret_pct
                calm = (cagr / m_dd) if m_dd > 0.001 else 0.0

                sub_tr = [
                    t for t in trades_list
                    if str(t.entry_time) >= r_start and str(t.entry_time) < r_end
                ]
                tr_cnt = len(sub_tr)
                st_cnt = len([t for t in sub_tr if t.exit_reason == "STOP_LOSS"])
                win_cnt = len([t for t in sub_tr if t.net_pnl_usdt > 0])
                wr = (win_cnt / tr_cnt * 100.0) if tr_cnt > 0 else 0.0

                p_fees = sum(t.entry_fee_usdt + t.exit_fee_usdt for t in sub_tr)
                p_slip = sum(t.slippage_cost_usdt for t in sub_tr)
                p_fric = p_fees + p_slip

                cash_pct = float((sub["curr_pos"] == "USDT_CASH").astype(float).mean() * 100.0)

                annual_breakdowns.append({
                    "regime": r_name,
                    "start_dt": r_start,
                    "end_dt": r_end,
                    "initial_equity": s_eq,
                    "final_equity": f_eq,
                    "net_ret_pct": ret_pct,
                    "cagr_pct": cagr,
                    "max_dd_pct": m_dd,
                    "sharpe": sh,
                    "calmar": calm,
                    "avg_cash_pct": cash_pct,
                    "trade_count": tr_cnt,
                    "stop_count": st_cnt,
                    "win_rate": wr,
                    "total_friction_usdt": p_fric,
                })

        if annual_breakdowns:
            pd.DataFrame(annual_breakdowns).to_csv(out_dir / "annual_breakdown.csv", index=False)
            with open(out_dir / "annual_breakdown.json", "w", encoding="utf-8") as f:
                json.dump(annual_breakdowns, f, indent=2, ensure_ascii=False)

    summary_md = f"""# Quantitative Research Experiment Summary / 实验总结报告
- **Experiment ID / 实验编号**: `{run_id}`
- **Role / 实验定位**: `{role}`
- **Mode / 运行模式**: `{args.mode.upper()}`
- **Universe / 资产池**: `{symbols}`
- **Leverage / 杠杆倍数**: `{args.leverage}x`
- **Time Interval / 时间区间**: `[{start_dt}, {end_dt}) UTC`
- **Bar Statistics / K线统计**: Expected {sim_res['expected_bars_count']} | Actual {sim_res['actual_bars_count']} | Missing {sim_res['missing_bars_count']}

---

## Audited Performance Metrics / 经审计核心绩效指标

| Metric / 指标项 | Audited Value / 审计数值 |
| :--- | :--- |
| **Initial Base Equity / 起始权益基准** | \${sim_res['initial_equity']:,.2f} USDT |
| **Final Equity / 期末总权益** | \${sim_res['final_equity']:,.2f} USDT |
| **Total Return / 周期累计收益率** | **{sim_res['total_ret_pct']:+.2f}%** |
| **CAGR / 年化复合收益率** | **{sim_res['cagr_pct']:+.2f}%** |
| **Max Drawdown / 最大回撤** | **{sim_res['max_dd_pct']:.2f}%** |
| **Sharpe Ratio / 夏普比率** | **{sim_res['sharpe']:.2f}** |
| **Calmar Ratio / 卡玛比率** | **{sim_res['calmar']:.2f}** |
| **Win Rate / 交易胜率** | **{sim_res['win_rate']:.1f}%** ({sim_res['trade_count']} trades) |
| **Stop-Loss Count / 触发止损次数** | **{sim_res['stop_count']}** |
| **Liquidated / 是否爆仓穿仓** | **{'YES (LIQUIDATED)' if sim_res['liquidated'] else 'NO (Safe)'}** |
| **Min Distance to Liq / 最低距强平线距离** | **{sim_res['min_distance_to_liq_pct']:.2f}%** |

---

## Mathematical Ledger Reconciliation / 账本数学恒等式核对

- **Total Trading Fees / 累计手续费**: \${sim_res['total_fees']:,.2f} USDT
- **Total Slippage Cost / 累计滑点成本**: \${sim_res['total_slippage']:,.2f} USDT
- **Total Funding Cost / 累计资金费支出**: \${sim_res['total_funding']:,.2f} USDT
- **Total Borrow Cost / 累计借贷利息**: \${sim_res['total_borrow']:,.2f} USDT
- **Ledger Reconciled / 账本数学闭环**: **{'PERFECT MATCH (误差 < 1e-4)' if sim_res['is_perfectly_reconciled'] else 'FAILED'}** (Error: {sim_res['reconciliation_error']:.6f})
"""

    if annual_breakdowns:
        summary_md += """
---

## Annual & Regime Performance Breakdown / 逐年与分周期表现

| Regime / 周期 | Initial Equity | Final Equity | Net Return / 净收益 | Max DD / 最大回撤 | Sharpe / 夏普 | Win Rate / 胜率 | Trades / 笔数 | Stops / 止损 | Friction / 摩擦 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
        for ab in annual_breakdowns:
            summary_md += (
                f"| **{ab['regime']}** | \${ab['initial_equity']:,.2f} | \${ab['final_equity']:,.2f} | "
                f"**{ab['net_ret_pct']:+.2f}%** | {ab['max_dd_pct']:.2f}% | {ab['sharpe']:.2f} | "
                f"{ab['win_rate']:.1f}% | {ab['trade_count']} | {ab['stop_count']} | \${ab['total_friction_usdt']:,.2f} |\n"
            )

    with open(out_dir / "summary.md", "w", encoding="utf-8") as f:
        f.write(summary_md)

    # Finalize Manifest with SHA256 hashes of generated artifacts
    output_hashes = compute_output_hashes(str(out_dir))
    finalize_manifest_with_outputs(str(out_dir / "manifest.json"), output_hashes)
    print(f"  Artifact SHA256 hashes computed and embedded into manifest.json ({len(output_hashes)} files)")

    # 11. Final Print
    print("\n[Step 5/5] Experiment Complete!")
    print(f"  Artifacts saved in: {out_dir}")
    print(f"  Total Return: {sim_res['total_ret_pct']:+.2f}% | Max DD: {sim_res['max_dd_pct']:.2f}% | Sharpe: {sim_res['sharpe']:.2f}")
    print(f"  Reconciliation: {sim_res['is_perfectly_reconciled']} (Error: {sim_res['reconciliation_error']:.6f})")
    print("=" * 80)


if __name__ == "__main__":
    main()
