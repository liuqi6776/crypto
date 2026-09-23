# -*- coding: utf-8 -*-
"""
CLI Runner for Dual Forward Paper Simulation (Candidate A vs Candidate B)
========================================================================
Usage Examples:
  # Initialize pristine forward tracking state:
  python scripts/run_forward_dual_paper.py --init

  # Seed forward ledger with the latest 20 4-hour bars:
  python scripts/run_forward_dual_paper.py --backfill-bars 20

  # Print current forward tracking comparison status:
  python scripts/run_forward_dual_paper.py --status
"""

import sys
import os
import argparse
from pathlib import Path
import pandas as pd
import numpy as np

# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from crypto_quant.paper.forward_dual_runner import ForwardDualRunner, CORE4_SYMBOLS


def load_market_data(symbols=CORE4_SYMBOLS):
    """Loads 4h parquet data for symbols and aligns on common timestamp index."""
    raw_dfs = {}
    for s in symbols:
        p = repo_root / "data" / f"{s}_4h_2020_2026.parquet"
        if not p.exists():
            raise FileNotFoundError(f"Missing required parquet data: {p}")
        df = pd.read_parquet(p)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        raw_dfs[s] = df

    common_idx = raw_dfs[symbols[0]].index
    for s in symbols[1:]:
        common_idx = common_idx.intersection(raw_dfs[s].index)
    common_idx = common_idx.sort_values()

    return raw_dfs, common_idx


def main():
    parser = argparse.ArgumentParser(description="Dual Forward Paper Tracking CLI")
    parser.add_argument("--init", action="store_true", help="Initialize or reset forward tracking ledgers")
    parser.add_argument("--backfill-bars", type=int, default=0, help="Number of recent 4h bars to backfill/seed")
    parser.add_argument("--status", action="store_true", help="Print current tracking status")
    parser.add_argument("--output-dir", type=str, default="data/forward_tracking", help="Tracking output directory")
    parser.add_argument("--initial-cash", type=float, default=10000.0, help="Initial cash for each model")

    args = parser.parse_args()

    runner = ForwardDualRunner(
        output_dir=args.output_dir,
        initial_cash=args.initial_cash,
    )

    if args.init:
        runner.reset()
        print("Initialized forward paper tracking state.")

    if args.backfill_bars > 0:
        raw_dfs, common_idx = load_market_data()
        n_bars = args.backfill_bars
        if n_bars > len(common_idx) - 200:
            n_bars = len(common_idx) - 200

        target_idx = common_idx[-n_bars:]
        print(f"Seeding forward paper ledger across {len(target_idx)} bars from {target_idx[0]} to {target_idx[-1]}...")

        # Precompute closes dataframe
        closes_df = pd.DataFrame({s: raw_dfs[s]["close"] for s in CORE4_SYMBOLS}, index=common_idx)

        # Precompute ATR 14 for each symbol
        df_atrs = pd.DataFrame(index=common_idx, columns=CORE4_SYMBOLS, dtype=float)
        for s in CORE4_SYMBOLS:
            df_s = raw_dfs[s].reindex(common_idx)
            tr1 = df_s["high"] - df_s["low"]
            tr2 = (df_s["high"] - df_s["close"].shift(1)).abs()
            tr3 = (df_s["low"] - df_s["close"].shift(1)).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            df_atrs[s] = tr.rolling(14).mean()

        for t in target_idx:
            i_loc = common_idx.get_loc(t)
            hist_closes = closes_df.iloc[:i_loc]
            hist_atrs = {s: float(df_atrs.loc[t, s]) for s in CORE4_SYMBOLS if not np.isnan(df_atrs.loc[t, s])}

            open_prices = {s: float(raw_dfs[s].loc[t, "open"]) for s in CORE4_SYMBOLS}
            close_prices = {s: float(raw_dfs[s].loc[t, "close"]) for s in CORE4_SYMBOLS}

            runner.process_bar(
                bar_time=t,
                open_prices=open_prices,
                close_prices=close_prices,
                historical_closes=hist_closes,
                historical_atrs=hist_atrs,
            )

        print(f"Successfully processed {len(target_idx)} forward bars.")

    if args.status or (not args.init and args.backfill_bars == 0):
        st = runner.state
        cA = st["candidate_a"]
        cB = st["candidate_b"]
        init_c = st["initial_cash"]
        ret_a = ((cA["equity"] / init_c) - 1.0) * 100.0
        ret_b = ((cB["total_equity"] / init_c) - 1.0) * 100.0

        print("=" * 80)
        print(" DUAL FORWARD PAPER TRACKING STATUS")
        print("=" * 80)
        print(f"Total Bars Tracked: {st['total_bars_processed']} | Last Bar: {st['last_processed_bar']}")
        print(f"Initial Cash: ${init_c:,.2f} each\n")
        print(f"[Candidate A: Top-1 Buffer 0.30]")
        print(f"  Current Equity: ${cA['equity']:,.2f} ({ret_a:+.2f}%)")
        print(f"  Position: {cA['curr_pos']} | Cash: ${cA['cash']:,.2f}")
        print(f"  Max Drawdown: {cA['max_drawdown_pct']:.2f}% | Trades: {cA['trade_count']}")
        print(f"  Fees: ${cA['total_fees']:,.2f} | Slippage: ${cA['total_slippage']:,.2f}\n")
        print(f"[Candidate B: Simple EMA Trend]")
        print(f"  Current Equity: ${cB['total_equity']:,.2f} ({ret_b:+.2f}%)")
        active_b = [s for s, sub in cB["sub_portfolios"].items() if sub["in_pos"]]
        print(f"  Active Tokens: {active_b or '100% Cash'} | Cash: ${cB['total_cash']:,.2f}")
        print(f"  Max Drawdown: {cB['max_drawdown_pct']:.2f}% | Trades: {cB['trade_count']}")
        print(f"  Fees: ${cB['total_fees']:,.2f} | Slippage: ${cB['total_slippage']:,.2f}\n")
        print(f"Alpha Spread (A - B): {ret_a - ret_b:+.2f}%")
        print("=" * 80)


if __name__ == "__main__":
    main()
