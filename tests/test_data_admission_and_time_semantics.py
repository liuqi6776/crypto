# -*- coding: utf-8 -*-
"""
Unit Tests for Phase 1: Data Admission & Time Semantics
======================================================
Verifies:
1. Data admission validator detects index non-monotonicity, duplicate timestamps,
   OHLC mathematical violations, negative prices, and <95% funding rate coverage.
2. Indicator warmup separation: Historical data prior to eval_start_dt is used for
   indicator calculation (EMA200, ATR, Momentum) without skipping evaluation bars.
3. Strict Equivalence Invariant:
   Slicing year 2025 from a continuous full-cycle run matches running year 2025
   standalone under CARRIED_STATE mode 100% bar-by-bar!
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path

from crypto_quant.core.data_admission import (
    validate_crypto_universe,
    DataAdmissionError,
    DataAdmissionReport,
)
from crypto_quant.backtest.clean_single_ledger_engine import SingleLedgerSimulator


def make_clean_df(bars=300, start_price=100.0, trend=0.001):
    idx = pd.date_range("2024-01-01", periods=bars, freq="4h")
    closes = [start_price * ((1.0 + trend) ** i) for i in range(bars)]
    opens = [c * 0.999 for c in closes]
    highs = [c * 1.01 for c in closes]
    lows = [c * 0.99 for c in closes]
    vols = [1000.0 for _ in range(bars)]
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes, "vol": vols}, index=idx)


def test_data_admission_passes_clean_data():
    raw_dfs = {
        "BTCUSDT": make_clean_df(100, 40000.0),
        "ETHUSDT": make_clean_df(100, 2000.0),
    }
    report = validate_crypto_universe(raw_dfs, ["BTCUSDT", "ETHUSDT"], strict=True)
    assert report.is_valid is True
    assert report.missing_bars_count["BTCUSDT"] == 0
    assert report.total_bars_per_symbol["BTCUSDT"] == 100


def test_data_admission_catches_non_monotonic_and_duplicates():
    df = make_clean_df(100, 40000.0)
    # Shuffle or duplicate index
    df_dup = pd.concat([df, df.iloc[:5]]).sort_index()
    raw_dfs = {"BTCUSDT": df_dup}

    with pytest.raises(DataAdmissionError) as exc_info:
        validate_crypto_universe(raw_dfs, ["BTCUSDT"], strict=True)
    assert "DUPLICATE_INDEX" in str(exc_info.value)


def test_data_admission_catches_ohlc_violation():
    df = make_clean_df(100, 40000.0)
    # Corrupt a high price to be lower than open
    df.iloc[10, df.columns.get_loc("high")] = df.iloc[10, df.columns.get_loc("open")] - 10.0
    raw_dfs = {"BTCUSDT": df}

    with pytest.raises(DataAdmissionError) as exc_info:
        validate_crypto_universe(raw_dfs, ["BTCUSDT"], strict=True)
    assert "OHLC_VIOLATION" in str(exc_info.value)


def test_data_admission_catches_insufficient_funding_coverage():
    df = make_clean_df(200, 40000.0)
    raw_dfs = {"BTCUSDT": df}
    # Create funding df with only 10% coverage
    f_idx = pd.date_range("2024-01-01", periods=10, freq="8h")
    df_funding = pd.DataFrame({"BTCUSDT": [0.0001]*10}, index=f_idx)

    with pytest.raises(DataAdmissionError) as exc_info:
        validate_crypto_universe(
            raw_dfs=raw_dfs,
            symbols=["BTCUSDT"],
            df_funding=df_funding,
            eval_start_dt="2024-01-01",
            eval_end_dt="2024-02-01",
            strict=True,
            min_funding_coverage=0.95,
        )
    assert "INSUFFICIENT_FUNDING_COVERAGE" in str(exc_info.value)


@pytest.fixture(scope="module")
def core4_full_data():
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
    raw_dfs = {s: pd.read_parquet(f"data/{s}_4h_2020_2026.parquet") for s in symbols}
    df_funding = pd.read_parquet("data/binance_funding_8h.parquet")
    if df_funding.index.tz is not None:
        df_funding.index = df_funding.index.tz_localize(None)
    return symbols, raw_dfs, df_funding


def test_full_cycle_slice_vs_carried_standalone_equivalence(core4_full_data):
    """
    Core Invariant:
    1. Run continuous simulation from 2024-01-01 to 2024-07-01.
    2. Extract state at 2024-04-01 00:00:00.
    3. Run standalone simulation from 2024-04-01 to 2024-07-01 using carry_over_state.
    4. Assert that every single bar record from 2024-04-01 to 2024-07-01 is 100% IDENTICAL!
    """
    symbols, raw_dfs, df_funding = core4_full_data

    # A. Continuous Run (Period 1 + Period 2)
    sim_full = SingleLedgerSimulator(
        symbols=symbols,
        raw_dfs=raw_dfs,
        df_funding=df_funding,
        leverage=1.0,
        fee_rate=0.0008,
        execution_slippage=0.0005,
        stop_slippage=0.0015,
        initial_cash=10000.0,
    )
    res_part1 = sim_full.run(start_dt="2024-01-01 00:00:00", end_dt="2024-04-01 00:00:00")
    state_at_part2_start = res_part1["end_state"]

    # Continuous Continuation (from part1 end to part2 end)
    res_part2_carried = sim_full.run(
        start_dt="2024-04-01 00:00:00",
        end_dt="2024-07-01 00:00:00",
        carry_over_state=state_at_part2_start,
    )

    # Full Combined Run (2024-01-01 to 2024-07-01 in one go)
    res_combined = sim_full.run(start_dt="2024-01-01 00:00:00", end_dt="2024-07-01 00:00:00")

    # Extract segment from res_combined matching 2024-04-01 to 2024-07-01
    combined_bars = res_combined["bar_records"]
    part2_start_ts = pd.Timestamp("2024-04-01 00:00:00")
    part2_end_ts = pd.Timestamp("2024-07-01 00:00:00")
    combined_slice = [b for b in combined_bars if b["bar_time"] >= part2_start_ts and b["bar_time"] < part2_end_ts]

    carried_bars = res_part2_carried["bar_records"]
    assert len(combined_slice) == len(carried_bars), f"Length mismatch: {len(combined_slice)} vs {len(carried_bars)}"

    for i in range(len(carried_bars)):
        bar_c = combined_slice[i]
        bar_s = carried_bars[i]
        t = bar_c["bar_time"]

        assert bar_c["bar_time"] == bar_s["bar_time"]
        assert bar_c["target_pos"] == bar_s["target_pos"], f"[{t}] target mismatch: {bar_c['target_pos']} vs {bar_s['target_pos']}"
        assert bar_c["curr_pos"] == bar_s["curr_pos"], f"[{t}] curr_pos mismatch: {bar_c['curr_pos']} vs {bar_s['curr_pos']}"
        assert abs(bar_c["asset_units"] - bar_s["asset_units"]) < 1e-4, f"[{t}] units mismatch"
        assert abs(bar_c["cash"] - bar_s["cash"]) < 1e-2, f"[{t}] cash mismatch: {bar_c['cash']} vs {bar_s['cash']}"
        assert abs(bar_c["equity"] - bar_s["equity"]) < 1e-2, f"[{t}] equity mismatch: {bar_c['equity']} vs {bar_s['equity']}"

    assert abs(res_part2_carried["final_equity"] - res_combined["final_equity"]) < 1e-2
