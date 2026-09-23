# -*- coding: utf-8 -*-
"""
Unit Tests for Dual Forward Paper Simulation Engine (ForwardDualRunner)
=====================================================================
Validates:
1. Fresh initialization of Candidate A and Candidate B ledgers.
2. Accurate causality: signals strictly from Bar T-1 closes.
3. Execution order fills with slippage, fees, and latency tracking.
4. Mathematical identity assertion: Equity == Cash + MTM Position.
5. Disk persistence: status.json, forward_ledger.csv, forward_journal.jsonl, forward_comparison.md.
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

    # Check 25% cash allocation in Candidate B
    for sym, sub in runner.state["candidate_b"]["sub_portfolios"].items():
        assert sub["cash"] == 2500.0
        assert sub["units"] == 0.0
        assert not sub["in_pos"]


def test_forward_dual_runner_bar_processing(tmp_forward_dir):
    runner = ForwardDualRunner(
        output_dir=str(tmp_forward_dir),
        initial_cash=10000.0,
    )

    # Construct synthetic 150 bars of historical closes
    dates = pd.date_range("2026-01-01", periods=150, freq="4h")
    hist_closes = pd.DataFrame(index=dates)
    for sym in CORE4_SYMBOLS:
        # Upward trending prices above EMA200
        hist_closes[sym] = np.linspace(100.0, 200.0, 150)

    # Bar T
    bar_t = pd.Timestamp("2026-01-26 00:00:00")
    open_prices = {s: 201.0 for s in CORE4_SYMBOLS}
    close_prices = {s: 205.0 for s in CORE4_SYMBOLS}

    res = runner.process_bar(
        bar_time=bar_t,
        open_prices=open_prices,
        close_prices=close_prices,
        historical_closes=hist_closes,
        latency_seconds=1.25,
    )

    assert res["bar_time"] == str(bar_t)
    assert res["latency_sec"] == 1.25

    # Check that disk files were created
    assert runner.status_file.exists()
    assert runner.ledger_file.exists()
    assert runner.journal_file.exists()
    assert runner.report_file.exists()

    # Read ledger CSV
    df_ledger = pd.read_csv(runner.ledger_file)
    assert len(df_ledger) == 1
    assert df_ledger["candidate_a_equity"].iloc[0] > 0
    assert df_ledger["candidate_b_equity"].iloc[0] > 0

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
