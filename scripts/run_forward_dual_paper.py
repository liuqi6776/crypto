# -*- coding: utf-8 -*-
"""
CLI Runner for Dual Forward Paper Simulation (Candidate A vs Candidate B)
========================================================================
Operational Modes:
  # Initialize or reset live forward tracking state (pristine $10,000 cash each):
  python scripts/run_forward_dual_paper.py --reset

  # Seed historical demonstration replay (isolated completely as DEMO_REPLAY):
  python scripts/run_forward_dual_paper.py --seed-demo --bars 20

  # Check & process the latest completed 4h candle from Binance live:
  python scripts/run_forward_dual_paper.py --live-step

  # Run continuous live polling daemon:
  python scripts/run_forward_dual_paper.py --live-poll --interval 60

  # Print current tracking comparison status:
  python scripts/run_forward_dual_paper.py --status
"""

import sys
import os
import argparse
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests
import pandas as pd
import numpy as np

# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from crypto_quant.paper.forward_dual_runner import ForwardDualRunner, CORE4_SYMBOLS, DEFAULT_MAX_STALENESS_SEC
from crypto_quant.paper.market_data import MarketDataFetcher

BINANCE_PUBLIC_API_URLS = [
    "https://api.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
    "https://data-api.binance.vision",
]

OOS_CUTOFF_UTC = pd.Timestamp("2026-09-23 00:00:00")


def fetch_live_book_ticker(symbols: List[str] = CORE4_SYMBOLS) -> Dict[str, Dict[str, float]]:
    """
    Fetches real-time top-of-book quotes (bidPrice, bidQty, askPrice, askQty)
    from Binance public REST endpoint.
    """
    quotes = {}
    for base_url in BINANCE_PUBLIC_API_URLS:
        url = f"{base_url}/api/v3/ticker/bookTicker"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                for item in resp.json():
                    sym = item.get("symbol")
                    if sym in symbols:
                        quotes[sym] = {
                            "bid": float(item.get("bidPrice", 0.0)),
                            "bid_qty": float(item.get("bidQty", 0.0)),
                            "ask": float(item.get("askPrice", 0.0)),
                            "ask_qty": float(item.get("askQty", 0.0)),
                        }
                if len(quotes) >= len(symbols):
                    return quotes
        except Exception:
            continue
    return quotes


def load_local_market_data(symbols: List[str] = CORE4_SYMBOLS):
    """Loads local 4h parquet data for symbols and aligns on common timestamp index."""
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


def seed_demo_replay(output_dir: str = "data/forward_tracking", n_bars: int = 20):
    """
    Seeds historical demonstration replay completely isolated from live OOS.
    Uses is_demo=True writing strictly to demo_replay_ledger.csv and demo_status.json.
    """
    demo_runner = ForwardDualRunner(output_dir=output_dir, is_demo=True)
    demo_runner.reset()

    raw_dfs, common_idx = load_local_market_data()
    target_idx = common_idx[-n_bars:]
    print(f"[DEMO REPLAY] Processing {len(target_idx)} bars from {target_idx[0]} to {target_idx[-1]} in DEMO mode...")

    closes_df = pd.DataFrame({s: raw_dfs[s]["close"] for s in CORE4_SYMBOLS}, index=common_idx)

    # Precompute ATR 14
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
        # Includes newly closed candle t so signal incorporates bar t's close
        hist_closes = closes_df.iloc[:i_loc + 1]
        hist_atrs = {s: float(df_atrs.loc[t, s]) for s in CORE4_SYMBOLS if not np.isnan(df_atrs.loc[t, s])}

        open_prices = {s: float(raw_dfs[s].loc[t, "open"]) for s in CORE4_SYMBOLS}
        close_prices = {s: float(raw_dfs[s].loc[t, "close"]) for s in CORE4_SYMBOLS}

        # In offline demo, synthetic quotes based on open price with slight spread
        synthetic_quotes = {
            s: {"bid": open_prices[s] * 0.9999, "ask": open_prices[s] * 1.0001}
            for s in CORE4_SYMBOLS
        }

        demo_runner.process_bar(
            bar_time=t,
            open_prices=open_prices,
            close_prices=close_prices,
            historical_closes=hist_closes,
            historical_atrs=hist_atrs,
            actual_quotes=synthetic_quotes,
            candle_close_time_utc=str(t),
            data_arrival_time_utc=str(t),
            quote_arrival_time_utc=str(t),
            regime="DEMO_REPLAY",
            allow_stale=True,
        )

    print(f"[DEMO REPLAY] Successfully saved demonstration replay to {demo_runner.ledger_file}.")


def run_live_step(runner: ForwardDualRunner, allow_stale: bool = False) -> Dict[str, Any]:
    """
    Checks Binance for the latest completed 4h candle, verifies freshness after all data arrives,
    computes model signals including the freshly closed bar, and then fetches live order book quotes.
    """
    fetcher = MarketDataFetcher()

    # Step 1: Fetch latest closed candles for all Core-4 symbols
    klines_dict = {}
    for s in CORE4_SYMBOLS:
        try:
            df_k = fetcher.fetch_closed_klines(symbol=s, interval="4h", limit=250, check_freshness=False)
            klines_dict[s] = df_k
        except Exception as e:
            print(f"[LIVE STEP ERROR] Failed to fetch {s}: {e}")
            return {"status": "ERROR", "message": str(e)}

    # Step 2: Verify common index across all symbols & validate data integrity
    common_idx = klines_dict[CORE4_SYMBOLS[0]].index
    for s in CORE4_SYMBOLS[1:]:
        common_idx = common_idx.intersection(klines_dict[s].index)
    common_idx = common_idx.sort_values()

    # Step 3: Record data_arrival_time AFTER all K-line data has been fetched and validated!
    now_utc = datetime.now(timezone.utc)
    arrival_time_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")

    latest_bar_t = common_idx[-1]
    candle_close_t = latest_bar_t + timedelta(hours=4)
    candle_close_str = candle_close_t.strftime("%Y-%m-%d %H:%M:%S UTC")

    bar_key = f"{runner.regime}:{latest_bar_t}"

    if bar_key in runner.processed_bars:
        print(f"[LIVE STEP] Bar {latest_bar_t} ({runner.regime}) already processed. No new closed bar. Current time: {arrival_time_str}")
        return {
            "status": "ALREADY_PROCESSED",
            "latest_bar": str(latest_bar_t),
            "regime": runner.regime,
            "current_time": arrival_time_str,
        }

    # Step 4: Include the newly closed candle in hist_closes so signal uses the freshly closed bar!
    closes_df = pd.DataFrame({s: klines_dict[s]["close"] for s in CORE4_SYMBOLS}, index=common_idx)
    i_loc = common_idx.get_loc(latest_bar_t)
    hist_closes = closes_df.iloc[:i_loc + 1]

    # Compute ATRs up to and including latest_bar_t
    df_atrs = pd.DataFrame(index=common_idx, columns=CORE4_SYMBOLS, dtype=float)
    for s in CORE4_SYMBOLS:
        df_s = klines_dict[s].reindex(common_idx)
        tr1 = df_s["high"] - df_s["low"]
        tr2 = (df_s["high"] - df_s["close"].shift(1)).abs()
        tr3 = (df_s["low"] - df_s["close"].shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df_atrs[s] = tr.rolling(14).mean()
    hist_atrs = {s: float(df_atrs.loc[latest_bar_t, s]) for s in CORE4_SYMBOLS if not np.isnan(df_atrs.loc[latest_bar_t, s])}

    open_prices = {s: float(klines_dict[s].loc[latest_bar_t, "open"]) for s in CORE4_SYMBOLS}
    close_prices = {s: float(klines_dict[s].loc[latest_bar_t, "close"]) for s in CORE4_SYMBOLS}

    print(f"[LIVE STEP] Processing newly closed bar {latest_bar_t} (closed at {candle_close_str}) under {runner.regime}...")
    # Step 5: Pass quote_fetcher callback so live quotes are fetched AFTER signal computation!
    res = runner.process_bar(
        bar_time=latest_bar_t,
        open_prices=open_prices,
        close_prices=close_prices,
        historical_closes=hist_closes,
        historical_atrs=hist_atrs,
        quote_fetcher=fetch_live_book_ticker,
        candle_close_time_utc=candle_close_str,
        data_arrival_time_utc=arrival_time_str,
        regime=runner.regime,
        allow_stale=allow_stale,
    )

    print(f"[LIVE STEP COMPLETE] Status={res['status']} | Latency={res.get('arrival_latency_sec')}s | Trades={res.get('trades_executed', 0)} | Anomaly={res.get('anomaly')}")
    return res


def run_live_poll_daemon(runner: ForwardDualRunner, interval_seconds: int = 60):
    """Continuous polling daemon that monitors Binance for new closed 4h candles."""
    print(f"[LIVE POLL DAEMON] Starting continuous listener (polling every {interval_seconds}s)...")
    print(f"[LIVE POLL DAEMON] Regime: {runner.regime} | Target cutoff: >= {OOS_CUTOFF_UTC} UTC")
    while True:
        try:
            run_live_step(runner)
        except Exception as e:
            print(f"[LIVE POLL EXCEPTION] Error during step: {e}")
        time.sleep(interval_seconds)


def print_status(runner: ForwardDualRunner):
    """Displays comprehensive forward paper tracking status."""
    st = runner.state
    cA = st["candidate_a"]
    cB = st["candidate_b"]
    init_c = st["initial_cash"]
    ret_a = ((cA["equity"] / init_c) - 1.0) * 100.0
    ret_b = ((cB["total_equity"] / init_c) - 1.0) * 100.0

    print("=" * 80)
    print(f" DUAL FORWARD PAPER TRACKING AUDIT STATUS ({runner.regime})")
    print("=" * 80)
    print(f"Genuine OOS Bars Processed:      {st.get('total_bars_processed', 0)}")
    print(f"Last Processed Bar:              {st.get('last_processed_bar') or 'Awaiting first live bar'}")
    print(f"Anomalies Recorded:              {st.get('anomalies_count', 0)}")
    print(f"Initial Capital:                 ${init_c:,.2f} USDT each (Pure Cash Start)\n")
    print(f"[Candidate A: Top-1 Buffer 0.30]")
    print(f"  Current Equity: ${cA['equity']:,.2f} ({ret_a:+.2f}%)")
    print(f"  Position: {cA['curr_pos']} | Cash: ${cA['cash']:,.2f}")
    print(f"  Max Drawdown: {cA['max_drawdown_pct']:.2f}% | Completed Trades: {cA['trade_count']}")
    print(f"  Fees: ${cA['total_fees']:,.2f} | Slippage: ${cA['total_slippage']:,.2f}\n")
    print(f"[Candidate B: Simple EMA Trend]")
    print(f"  Current Equity: ${cB['total_equity']:,.2f} ({ret_b:+.2f}%)")
    active_b = [s for s, sub in cB["sub_portfolios"].items() if sub["in_pos"]]
    print(f"  Active Tokens: {active_b or '100% Cash'} | Cash: ${cB['total_cash']:,.2f}")
    print(f"  Max Drawdown: {cB['max_drawdown_pct']:.2f}% | Completed Trades: {cB['trade_count']}")
    print(f"  Fees: ${cB['total_fees']:,.2f} | Slippage: ${cB['total_slippage']:,.2f}\n")
    print(f"Alpha Spread (A - B): {ret_a - ret_b:+.2f}%")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Dual Forward Paper Tracking CLI")
    parser.add_argument("--reset", action="store_true", help="Reset live forward tracking state (pristine $10k cash each)")
    parser.add_argument("--seed-demo", action="store_true", help="Seed historical demonstration replay (isolated in demo files)")
    parser.add_argument("--bars", type=int, default=20, help="Number of bars for demo replay")
    parser.add_argument("--live-step", action="store_true", help="Execute single live check for latest closed candle")
    parser.add_argument("--allow-stale", action="store_true", help="Allow execution even if data arrived after staleness threshold (testing only)")
    parser.add_argument("--live-poll", action="store_true", help="Run continuous live polling daemon")
    parser.add_argument("--interval", type=int, default=60, help="Polling interval in seconds")
    parser.add_argument("--status", action="store_true", help="Print current status")
    parser.add_argument("--output-dir", type=str, default="data/forward_tracking", help="Tracking output directory")
    parser.add_argument("--initial-cash", type=float, default=10000.0, help="Initial cash for each model")

    args = parser.parse_args()

    # Default runner is live OOS
    runner = ForwardDualRunner(
        output_dir=args.output_dir,
        initial_cash=args.initial_cash,
        is_demo=False,
    )

    if args.reset:
        runner.reset()
        print("Live forward tracking state has been cleanly reset to pristine cash.")

    if args.seed_demo:
        seed_demo_replay(output_dir=args.output_dir, n_bars=args.bars)

    if args.live_step:
        run_live_step(runner, allow_stale=args.allow_stale)

    if args.live_poll:
        run_live_poll_daemon(runner, interval_seconds=args.interval)

    if args.status or (not args.reset and not args.seed_demo and not args.live_step and not args.live_poll):
        print_status(runner)


if __name__ == "__main__":
    main()
