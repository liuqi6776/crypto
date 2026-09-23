# -*- coding: utf-8 -*-
"""
Unit Tests for Dual Forward Paper Simulation Engine (ForwardDualRunner)
=====================================================================
Validates:
1. Fresh initialization: Candidate A and Candidate B starting from $10,000 cash each.
2. Causal execution: BUY fills at ask * (1+slip), SELL at bid * (1-slip), post-fill MTM.
3. Staleness Guard: arrival_latency > 900s triggers DATA_EXPIRED anomaly and skips execution.
4. Missing Quote Guard: Missing/empty order book quotes trigger QUOTE_MISSING and skip execution.
5. Restart Idempotency: Duplicate bar execution rejection.
6. Regime Isolation: is_demo=True writes strictly to demo files, leaving live files untouched.
7. Mathematical identity assertions hold on every bar.
"""

import pytest
import shutil
import json
from pathlib import Path
import pandas as pd
import numpy as np

from crypto_quant.paper.forward_dual_runner import ForwardDualRunner, CORE4_SYMBOLS


@pytest.fixture
def tmp_forward_dir(tmp_path):
    test_dir = tmp_path / "test_forward_tracking"
    test_dir.mkdir(parents=True, exist_ok=True)
    yield test_dir
    if test_dir.exists():
        shutil.rmtree(test_dir)


def test_forward_dual_runner_initialization(tmp_forward_dir):
    runner = ForwardDualRunner(
        output_dir=str(tmp_forward_dir),
        initial_cash=10000.0,
        fee_rate=0.0008,
        slippage=0.0005,
        is_demo=False,
    )
    assert runner.state["initial_cash"] == 10000.0
    assert runner.state["candidate_a"]["equity"] == 10000.0
    assert runner.state["candidate_a"]["cash"] == 10000.0
    assert runner.state["candidate_a"]["curr_pos"] == "USDT_CASH"
    assert runner.state["candidate_a"]["asset_units"] == 0.0

    assert runner.state["candidate_b"]["total_equity"] == 10000.0
    assert runner.state["candidate_b"]["total_cash"] == 10000.0
    assert len(runner.state["candidate_b"]["sub_portfolios"]) == 4

    for sym, sub in runner.state["candidate_b"]["sub_portfolios"].items():
        assert sub["cash"] == 2500.0
        assert sub["units"] == 0.0
        assert not sub["in_pos"]


def test_forward_dual_runner_causal_quote_execution(tmp_forward_dir):
    runner = ForwardDualRunner(
        output_dir=str(tmp_forward_dir),
        initial_cash=10000.0,
        fee_rate=0.0008,
        slippage=0.0005,
    )

    dates = pd.date_range("2026-01-01", periods=150, freq="4h")
    hist_closes = pd.DataFrame(index=dates)
    for sym in CORE4_SYMBOLS:
        hist_closes[sym] = np.linspace(100.0, 200.0, 150)

    bar_t = pd.Timestamp("2026-09-23 00:00:00")
    open_prices = {s: 201.0 for s in CORE4_SYMBOLS}
    close_prices = {s: 205.0 for s in CORE4_SYMBOLS}
    actual_quotes = {
        s: {"bid": 204.0, "ask": 204.2, "bid_qty": 5.0, "ask_qty": 3.0}
        for s in CORE4_SYMBOLS
    }

    # Step 1: Execute Bar T with fresh latency (< 900s)
    res = runner.process_bar(
        bar_time=bar_t,
        open_prices=open_prices,
        close_prices=close_prices,
        historical_closes=hist_closes,
        actual_quotes=actual_quotes,
        candle_close_time_utc="2026-09-23 04:00:00 UTC",
        data_arrival_time_utc="2026-09-23 04:00:15 UTC",
        quote_arrival_time_utc="2026-09-23 04:00:16 UTC",
    )

    assert res["status"] == "SUCCESS"
    assert res["trades_executed"] > 0
    assert res["arrival_latency_sec"] == 15.0

    # Verify journal events
    assert runner.journal_file.exists()
    with open(runner.journal_file, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f]
    assert len(lines) > 0
    for ev in lines:
        if ev.get("event_type") == "ORDER_FILL":
            assert ev["action"] == "BUY"
            # Verify execution price was based on actual_ask * (1 + slip), NOT old open_price
            expected_exec = round(ev["actual_ask"] * (1.0 + 0.0005), 4)
            assert ev["exec_price"] == expected_exec

    # Verify ledger file
    assert runner.ledger_file.exists()
    df_ledger = pd.read_csv(runner.ledger_file)
    assert len(df_ledger) == 1
    assert df_ledger["anomaly"].iloc[0] == "NONE"
    assert df_ledger["trades_executed"].iloc[0] > 0


def test_forward_dual_runner_staleness_guard(tmp_forward_dir):
    runner = ForwardDualRunner(
        output_dir=str(tmp_forward_dir),
        initial_cash=10000.0,
        max_staleness_sec=900.0,
    )

    dates = pd.date_range("2026-01-01", periods=150, freq="4h")
    hist_closes = pd.DataFrame(index=dates)
    for sym in CORE4_SYMBOLS:
        hist_closes[sym] = np.linspace(100.0, 200.0, 150)

    bar_t = pd.Timestamp("2026-09-23 00:00:00")
    open_prices = {s: 201.0 for s in CORE4_SYMBOLS}
    close_prices = {s: 205.0 for s in CORE4_SYMBOLS}
    actual_quotes = {s: {"bid": 204.0, "ask": 204.2} for s in CORE4_SYMBOLS}

    # Data arrives 4200 seconds (> 900s) late!
    res = runner.process_bar(
        bar_time=bar_t,
        open_prices=open_prices,
        close_prices=close_prices,
        historical_closes=hist_closes,
        actual_quotes=actual_quotes,
        candle_close_time_utc="2026-09-23 04:00:00 UTC",
        data_arrival_time_utc="2026-09-23 05:10:00 UTC",
        quote_arrival_time_utc="2026-09-23 05:10:01 UTC",
    )

    assert res["status"] == "DATA_EXPIRED_SKIPPED"
    assert res["anomaly"] == "DATA_EXPIRED"
    assert res["trades_executed"] == 0

    # Ensure no trades occurred
    assert runner.state["candidate_a"]["curr_pos"] == "USDT_CASH"
    assert runner.state["candidate_a"]["cash"] == 10000.0
    assert runner.state["anomalies_count"] == 1

    # Verify journal recorded DATA_EXPIRED anomaly
    with open(runner.journal_file, "r", encoding="utf-8") as f:
        events = [json.loads(l) for l in f]
    assert len(events) == 1
    assert events[0]["event_type"] == "ANOMALY"
    assert events[0]["anomaly_type"] == "DATA_EXPIRED"
    assert events[0]["action_taken"] == "SKIP_EXECUTION"


def test_forward_dual_runner_missing_quote_guard(tmp_forward_dir):
    runner = ForwardDualRunner(
        output_dir=str(tmp_forward_dir),
        initial_cash=10000.0,
    )

    dates = pd.date_range("2026-01-01", periods=150, freq="4h")
    hist_closes = pd.DataFrame(index=dates)
    for sym in CORE4_SYMBOLS:
        hist_closes[sym] = np.linspace(100.0, 200.0, 150)

    bar_t = pd.Timestamp("2026-09-23 00:00:00")
    open_prices = {s: 201.0 for s in CORE4_SYMBOLS}
    close_prices = {s: 205.0 for s in CORE4_SYMBOLS}

    # Pass None for actual_quotes
    res = runner.process_bar(
        bar_time=bar_t,
        open_prices=open_prices,
        close_prices=close_prices,
        historical_closes=hist_closes,
        actual_quotes=None,
        candle_close_time_utc="2026-09-23 04:00:00 UTC",
        data_arrival_time_utc="2026-09-23 04:00:10 UTC",
    )

    assert res["status"] == "QUOTE_MISSING_SKIPPED"
    assert res["anomaly"] == "QUOTE_MISSING"
    assert res["trades_executed"] == 0
    assert runner.state["candidate_a"]["curr_pos"] == "USDT_CASH"
    assert runner.state["candidate_a"]["cash"] == 10000.0


def test_forward_dual_runner_idempotency(tmp_forward_dir):
    runner = ForwardDualRunner(
        output_dir=str(tmp_forward_dir),
        initial_cash=10000.0,
    )

    dates = pd.date_range("2026-01-01", periods=150, freq="4h")
    hist_closes = pd.DataFrame(index=dates)
    for sym in CORE4_SYMBOLS:
        hist_closes[sym] = np.linspace(100.0, 200.0, 150)

    bar_t = pd.Timestamp("2026-09-23 00:00:00")
    open_prices = {s: 201.0 for s in CORE4_SYMBOLS}
    close_prices = {s: 205.0 for s in CORE4_SYMBOLS}
    actual_quotes = {s: {"bid": 204.0, "ask": 204.2} for s in CORE4_SYMBOLS}

    res1 = runner.process_bar(
        bar_time=bar_t,
        open_prices=open_prices,
        close_prices=close_prices,
        historical_closes=hist_closes,
        actual_quotes=actual_quotes,
        candle_close_time_utc="2026-09-23 04:00:00 UTC",
        data_arrival_time_utc="2026-09-23 04:00:10 UTC",
    )
    assert res1["status"] == "SUCCESS"

    # Second execution of same bar
    res2 = runner.process_bar(
        bar_time=bar_t,
        open_prices=open_prices,
        close_prices=close_prices,
        historical_closes=hist_closes,
        actual_quotes=actual_quotes,
        candle_close_time_utc="2026-09-23 04:00:00 UTC",
        data_arrival_time_utc="2026-09-23 04:00:10 UTC",
    )
    assert res2["status"] == "ALREADY_PROCESSED"


def test_forward_dual_runner_demo_isolation(tmp_forward_dir):
    demo_runner = ForwardDualRunner(
        output_dir=str(tmp_forward_dir),
        initial_cash=10000.0,
        is_demo=True,
    )
    assert demo_runner.regime == "DEMO_REPLAY"
    assert demo_runner.status_file.name == "demo_status.json"
    assert demo_runner.ledger_file.name == "demo_replay_ledger.csv"
    assert demo_runner.journal_file.name == "demo_journal.jsonl"
    assert demo_runner.report_file.name == "demo_comparison.md"

    dates = pd.date_range("2026-01-01", periods=150, freq="4h")
    hist_closes = pd.DataFrame(index=dates)
    for sym in CORE4_SYMBOLS:
        hist_closes[sym] = np.linspace(100.0, 200.0, 150)

    bar_demo = pd.Timestamp("2026-09-20 00:00:00")
    open_prices = {s: 150.0 for s in CORE4_SYMBOLS}
    close_prices = {s: 152.0 for s in CORE4_SYMBOLS}
    quotes = {s: {"bid": 151.9, "ask": 152.1} for s in CORE4_SYMBOLS}

    res_demo = demo_runner.process_bar(
        bar_time=bar_demo,
        open_prices=open_prices,
        close_prices=close_prices,
        historical_closes=hist_closes,
        actual_quotes=quotes,
        allow_stale=True,
    )

    assert res_demo["status"] == "SUCCESS"
    assert demo_runner.ledger_file.exists()

    # Verify live files were NEVER created
    live_ledger = tmp_forward_dir / "forward_ledger.csv"
    live_status = tmp_forward_dir / "status.json"
    assert not live_ledger.exists()
    assert not live_status.exists()
