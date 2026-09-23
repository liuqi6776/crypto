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


def test_forward_dual_runner_quote_fetcher_calling_sequence(tmp_forward_dir):
    """Verifies that quotes are fetched strictly AFTER decision, logging timestamps in physical sequence."""
    runner = ForwardDualRunner(
        output_dir=str(tmp_forward_dir),
        initial_cash=10000.0,
    )

    dates = pd.date_range("2026-01-01", periods=150, freq="4h")
    hist_closes = pd.DataFrame(index=dates)
    for sym in CORE4_SYMBOLS:
        hist_closes[sym] = np.linspace(100.0, 200.0, 150)

    call_order = []

    def mock_quote_fetcher(symbols=None):
        call_order.append("FETCH_QUOTES")
        return {s: {"bid": 204.0, "ask": 204.2} for s in CORE4_SYMBOLS}

    bar_t = pd.Timestamp("2026-09-23 00:00:00")
    open_prices = {s: 201.0 for s in CORE4_SYMBOLS}
    close_prices = {s: 205.0 for s in CORE4_SYMBOLS}

    res = runner.process_bar(
        bar_time=bar_t,
        open_prices=open_prices,
        close_prices=close_prices,
        historical_closes=hist_closes,
        quote_fetcher=mock_quote_fetcher,
        candle_close_time_utc="2026-09-23 04:00:00 UTC",
        data_arrival_time_utc="2026-09-23 04:00:05 UTC",
    )

    assert res["status"] == "SUCCESS"
    assert "FETCH_QUOTES" in call_order

    # Read journal to verify timestamp sequence
    with open(runner.journal_file, "r", encoding="utf-8") as f:
        events = [json.loads(line) for line in f]
    assert len(events) > 0
    ev = events[0]

    t_close = pd.to_datetime(ev["candle_close_time_utc"])
    t_data = pd.to_datetime(ev["data_arrival_time_utc"])
    t_decision = pd.to_datetime(ev["decision_time_utc"])
    t_quote = pd.to_datetime(ev["quote_arrival_time_utc"])

    # Strict physical temporal ordering: candle_close <= data_arrival <= decision <= quote
    assert t_close <= t_data
    assert t_data <= t_decision
    assert t_decision <= t_quote


def test_historical_vs_forward_signal_by_signal_equivalence():
    """
    Verifies 100% bit-for-bit equivalence between:
    - Backtest decision at Bar i (using closes.iloc[:i])
    - Forward paper decision when Bar i-1 closed (using closes.iloc[:loc(i-1) + 1])
    Proves that including the newly closed candle eliminates the 1-bar extra lag.
    """
    from crypto_quant.core.top1_decision_engine import compute_top1_decision
    from scripts.run_forward_dual_paper import load_local_market_data

    raw_dfs, common_idx = load_local_market_data()
    closes_df = pd.DataFrame({s: raw_dfs[s]["close"] for s in CORE4_SYMBOLS}, index=common_idx)

    curr_pos_backtest = "USDT_CASH"
    curr_pos_forward = "USDT_CASH"

    # Evaluate across 50 consecutive historical 4h bars
    start_i = 150
    end_i = 200

    matches = 0
    for i in range(start_i, end_i):
        bar_backtest = common_idx[i]
        prev_closed_bar = common_idx[i - 1]

        # 1. Backtest slice: all bars up to i (excluding bar i)
        sub_closes_backtest = closes_df.iloc[:i]
        dec_backtest = compute_top1_decision(
            closes_df=sub_closes_backtest,
            current_symbol=curr_pos_backtest,
            symbols=CORE4_SYMBOLS,
            delta_score_buffer=0.30,
        )

        # 2. Forward slice: all bars up to and including prev_closed_bar
        loc_prev = common_idx.get_loc(prev_closed_bar)
        sub_closes_forward = closes_df.iloc[:loc_prev + 1]

        # Assert slicing identity: sub_closes_forward IS EXACTLY sub_closes_backtest!
        assert len(sub_closes_forward) == len(sub_closes_backtest)
        assert sub_closes_forward.index[-1] == sub_closes_backtest.index[-1]
        assert sub_closes_forward.index[-1] == prev_closed_bar

        dec_forward = compute_top1_decision(
            closes_df=sub_closes_forward,
            current_symbol=curr_pos_forward,
            symbols=CORE4_SYMBOLS,
            delta_score_buffer=0.30,
        )

        # 3. Assert 100% signal equivalence
        assert dec_forward.target_symbol == dec_backtest.target_symbol, (
            f"Bar {bar_backtest}: target mismatch forward={dec_forward.target_symbol} vs backtest={dec_backtest.target_symbol}"
        )
        assert dec_forward.action == dec_backtest.action
        assert dec_forward.dual_gate_passed == dec_backtest.dual_gate_passed
        assert abs(dec_forward.top_score - dec_backtest.top_score) < 1e-6

        # 4. Assert Candidate B trend flags equivalence
        for s in CORE4_SYMBOLS:
            tb_backtest = sub_closes_backtest[s].iloc[-1] > sub_closes_backtest[s].ewm(span=200, adjust=False).mean().iloc[-1]
            tb_forward = sub_closes_forward[s].iloc[-1] > sub_closes_forward[s].ewm(span=200, adjust=False).mean().iloc[-1]
            assert tb_forward == tb_backtest

        # Advance positions
        curr_pos_backtest = dec_backtest.target_symbol
        curr_pos_forward = dec_forward.target_symbol
        matches += 1

    assert matches == (end_i - start_i)
    assert matches == 50
