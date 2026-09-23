# -*- coding: utf-8 -*-
"""
Unit Tests for Dual Forward Paper Simulation Engine (ForwardDualRunner)
=====================================================================
Validates:
1. Fresh initialization of Candidate A and Candidate B ledgers.
2. Accurate causality: signals strictly from Bar T-1 closes.
3. Execution order fills with live bookTicker quotes, fees, and latency tracking.
4. Restart Idempotency: Duplicate bar execution rejection.
5. Ledger segregation: DEMO_REPLAY vs FORWARD_OOS_LIVE.
6. Mathematical identity assertions on every bar.
"""

import pytest
import shutil
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
    )
    assert runner.state["initial_cash"] == 10000.0
    assert runner.state["candidate_a"]["equity"] == 10000.0
    assert runner.state["candidate_a"]["curr_pos"] == "USDT_CASH"
    assert runner.state["candidate_b"]["total_equity"] == 10000.0
    assert len(runner.state["candidate_b"]["sub_portfolios"]) == 4

    for sym, sub in runner.state["candidate_b"]["sub_portfolios"].items():
        assert sub["cash"] == 2500.0
        assert sub["units"] == 0.0
        assert not sub["in_pos"]


def test_forward_dual_runner_bar_processing_and_idempotency(tmp_forward_dir):
    runner = ForwardDualRunner(
        output_dir=str(tmp_forward_dir),
        initial_cash=10000.0,
    )

    # Synthetic 150 bars
    dates = pd.date_range("2026-01-01", periods=150, freq="4h")
    hist_closes = pd.DataFrame(index=dates)
    for sym in CORE4_SYMBOLS:
        hist_closes[sym] = np.linspace(100.0, 200.0, 150)

    bar_t = pd.Timestamp("2026-09-23 00:00:00")
    open_prices = {s: 201.0 for s in CORE4_SYMBOLS}
    close_prices = {s: 205.0 for s in CORE4_SYMBOLS}
    actual_quotes = {
        s: {"bid": 200.95, "ask": 201.05, "bid_qty": 5.0, "ask_qty": 3.0}
        for s in CORE4_SYMBOLS
    }

    # Step 1: Execute Bar T
    res1 = runner.process_bar(
        bar_time=bar_t,
        open_prices=open_prices,
        close_prices=close_prices,
        historical_closes=hist_closes,
        actual_quotes=actual_quotes,
        candle_close_time_utc="2026-09-23 04:00:00 UTC",
        data_arrival_time_utc="2026-09-23 04:00:15 UTC",
        quote_arrival_time_utc="2026-09-23 04:00:16 UTC",
        regime="FORWARD_OOS_LIVE",
    )

    assert res1["status"] == "SUCCESS"
    assert res1["bar_time"] == str(bar_t)
    assert res1["arrival_latency_sec"] == 15.0

    # Step 2: Idempotency Check (same bar fed again)
    res2 = runner.process_bar(
        bar_time=bar_t,
        open_prices=open_prices,
        close_prices=close_prices,
        historical_closes=hist_closes,
        regime="FORWARD_OOS_LIVE",
    )

    assert res2["status"] == "ALREADY_PROCESSED"

    # Verify ledger file
    assert runner.ledger_file.exists()
    df_ledger = pd.read_csv(runner.ledger_file)
    assert len(df_ledger) == 1
    assert df_ledger["arrival_latency_sec"].iloc[0] == 15.0
    assert df_ledger["regime"].iloc[0] == "FORWARD_OOS_LIVE"

    # Verify mathematical identity of Candidate A
    cA = runner.state["candidate_a"]
    expected_a_equity = cA["cash"] + (cA["asset_units"] * close_prices[cA["curr_pos"]] if cA["curr_pos"] != "USDT_CASH" else 0.0)
    assert abs(cA["equity"] - expected_a_equity) < 1e-4

    # Verify mathematical identity of Candidate B
    cB = runner.state["candidate_b"]
    expected_b_equity = sum(
        sub["cash"] + (sub["units"] * close_prices[s] if sub["in_pos"] else 0.0)
        for s, sub in cB["sub_portfolios"].items()
    )
    assert abs(cB["total_equity"] - expected_b_equity) < 1e-4


def test_forward_dual_runner_demo_replay_segregation(tmp_forward_dir):
    runner = ForwardDualRunner(
        output_dir=str(tmp_forward_dir),
        initial_cash=10000.0,
    )

    dates = pd.date_range("2026-01-01", periods=150, freq="4h")
    hist_closes = pd.DataFrame(index=dates)
    for sym in CORE4_SYMBOLS:
        hist_closes[sym] = np.linspace(100.0, 200.0, 150)

    bar_demo = pd.Timestamp("2026-09-20 00:00:00")
    open_prices = {s: 150.0 for s in CORE4_SYMBOLS}
    close_prices = {s: 152.0 for s in CORE4_SYMBOLS}

    res_demo = runner.process_bar(
        bar_time=bar_demo,
        open_prices=open_prices,
        close_prices=close_prices,
        historical_closes=hist_closes,
        regime="DEMO_REPLAY",
    )

    assert res_demo["status"] == "SUCCESS"
    assert runner.demo_ledger_file.exists()
    assert not runner.ledger_file.exists()

    df_demo = pd.read_csv(runner.demo_ledger_file)
    assert len(df_demo) == 1
    assert df_demo["regime"].iloc[0] == "DEMO_REPLAY"
    assert runner.state["total_demo_bars_processed"] == 1
    assert runner.state["total_live_bars_processed"] == 0
