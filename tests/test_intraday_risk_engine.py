# -*- coding: utf-8 -*-
"""
Unit Tests for Intraday Single-Ledger Risk & Execution Simulator
日内单账本风控与撮合执行引擎单元测试
"""

import pytest
import numpy as np
import pandas as pd

from crypto_quant.backtest.intraday_risk_engine import (
    IntradayRiskLedgerSimulator,
    IntradayTradeRecord,
)
from crypto_quant.ma_congestion.state_machine import TradeSignal


def create_dummy_signal(
    symbol: str = "BTCUSDT",
    direction: str = "LONG",
    confirm_price: float = 100.0,
    initial_sl: float = 98.0,
    frozen_atr: float = 1.0,
) -> TradeSignal:
    now = pd.Timestamp("2026-01-01 00:00:00")
    return TradeSignal(
        symbol=symbol,
        direction=direction,
        signal_time=now,
        confirm_price=confirm_price,
        initial_sl=initial_sl,
        frozen_atr=frozen_atr,
        formation_time=now - pd.Timedelta(minutes=60),
        breakout_time=now - pd.Timedelta(minutes=30),
        confirm_time=now,
        U=100.0,
        L=98.5,
        breakout_price=100.5,
        pattern_duration_bars=4,
    )


def test_risk_sizing_0_5_percent():
    """Verify that position size strictly risks 0.5% of total equity."""
    sim = IntradayRiskLedgerSimulator(
        symbols=["BTCUSDT"],
        initial_cash=10000.0,
        risk_per_trade_pct=0.005,
    )
    sig = create_dummy_signal(confirm_price=100.0, initial_sl=98.0)
    bar_t = pd.Timestamp("2026-01-01 00:15:00")
    bar_data = {
        "BTCUSDT": pd.Series({"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "atr14": 1.0})
    }

    sim.process_bar(bar_t, bar_data, [sig])
    assert "BTCUSDT" in sim.open_positions
    pos = sim.open_positions["BTCUSDT"]

    # Entry price with 5 bps slippage = 100.0 * 1.0005 = 100.05
    # Actual stop distance = 100.05 - 98.0 = 2.05
    # Expected units = (10000 * 0.005) / 2.05 = 50 / 2.05 = 24.39024
    expected_units = 50.0 / (pos.entry_price - pos.initial_sl)
    assert pytest.approx(pos.units, 1e-4) == expected_units
    assert pytest.approx(pos.risk_1r_usdt, 1e-4) == 50.0  # exactly 50 USDT (0.5% of $10,000)


def test_gap_cancellation():
    """Verify that if open price gaps up excessively widening stop distance, order is cancelled."""
    sim = IntradayRiskLedgerSimulator(
        symbols=["BTCUSDT"],
        initial_cash=10000.0,
        gap_sl_tolerance_ratio=1.25,
    )
    sig = create_dummy_signal(confirm_price=100.0, initial_sl=98.0, frozen_atr=1.0)
    bar_t = pd.Timestamp("2026-01-01 00:15:00")
    # Open gaps to 103.0! raw SL dist was 2.0, actual SL dist is 103.0 - 98 = 5.0 (> 1.25 * 2.0)
    bar_data = {
        "BTCUSDT": pd.Series({"open": 103.0, "high": 104.0, "low": 102.5, "close": 103.5, "atr14": 1.0})
    }

    sim.process_bar(bar_t, bar_data, [sig])
    assert len(sim.open_positions) == 0  # Cancelled!


def test_worst_case_intrabar_conflict():
    """Verify that if a single bar touches both SL and TP, Stop Loss is executed first."""
    sim = IntradayRiskLedgerSimulator(
        symbols=["BTCUSDT"],
        initial_cash=10000.0,
        exit_rule="FIXED_2R",
    )
    sig = create_dummy_signal(confirm_price=100.0, initial_sl=98.0)
    t1 = pd.Timestamp("2026-01-01 00:15:00")
    bar_data_1 = {
        "BTCUSDT": pd.Series({"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "atr14": 1.0})
    }
    sim.process_bar(t1, bar_data_1, [sig])
    assert "BTCUSDT" in sim.open_positions

    # Next bar: Extreme volatility wick touching both +2R (104.1) and Stop (98.0)
    # High = 106.0, Low = 97.0
    t2 = pd.Timestamp("2026-01-01 00:30:00")
    bar_data_2 = {
        "BTCUSDT": pd.Series({"open": 100.0, "high": 106.0, "low": 97.0, "close": 101.0, "atr14": 1.0})
    }
    exits = sim.process_bar(t2, bar_data_2, [])
    assert len(exits) == 1
    assert exits[0].exit_reason == "STOP_LOSS"
    assert exits[0].net_pnl_usdt < 0  # Stopped out, never banking false profit!


def test_trailing_stop_activation():
    """Verify trailing stop unlocks after +1R and ratchets up to max(SL, High - 2*ATR)."""
    sim = IntradayRiskLedgerSimulator(
        symbols=["BTCUSDT"],
        initial_cash=10000.0,
        exit_rule="DYNAMIC_TRAILING",
    )
    sig = create_dummy_signal(confirm_price=100.0, initial_sl=98.0, frozen_atr=1.0)
    t1 = pd.Timestamp("2026-01-01 00:15:00")
    bar_data_1 = {
        "BTCUSDT": pd.Series({"open": 100.0, "high": 100.2, "low": 99.8, "close": 100.0, "atr14": 1.0})
    }
    sim.process_bar(t1, bar_data_1, [sig])
    pos = sim.open_positions["BTCUSDT"]
    assert not pos.trailing_unlocked

    # Bar 2: High reaches +1R (entry + 2.05 = ~102.1)
    t2 = pd.Timestamp("2026-01-01 00:30:00")
    bar_data_2 = {
        "BTCUSDT": pd.Series({"open": 100.0, "high": 103.0, "low": 100.0, "close": 102.5, "atr14": 1.0})
    }
    sim.process_bar(t2, bar_data_2, [])
    assert pos.trailing_unlocked
    # Ratchet stop = max(98.0, 103.0 - 2 * 1.0 = 101.0)
    assert pos.current_sl == 101.0
    assert pos.sl_updates == 1


def test_cash_identity():
    """Verify exact cash ledger mathematical identity upon trade exit."""
    sim = IntradayRiskLedgerSimulator(
        symbols=["BTCUSDT"],
        initial_cash=10000.0,
    )
    sig = create_dummy_signal(confirm_price=100.0, initial_sl=98.0)
    t1 = pd.Timestamp("2026-01-01 00:15:00")
    bar_data_1 = {
        "BTCUSDT": pd.Series({"open": 100.0, "high": 100.2, "low": 99.8, "close": 100.0, "atr14": 1.0})
    }
    sim.process_bar(t1, bar_data_1, [sig])

    # Bar 2: Stop out
    t2 = pd.Timestamp("2026-01-01 00:30:00")
    bar_data_2 = {
        "BTCUSDT": pd.Series({"open": 97.5, "high": 98.0, "low": 97.0, "close": 97.2, "atr14": 1.0})
    }
    exits = sim.process_bar(t2, bar_data_2, [])
    assert len(exits) == 1
    tr = exits[0]

    # Math identity: Final Cash == Initial Cash + Gross PnL - Entry Fee - Exit Fee
    expected_cash = 10000.0 + tr.gross_pnl_usdt - tr.entry_fee_usdt - tr.exit_fee_usdt
    assert pytest.approx(sim.cash, 1e-5) == expected_cash
    assert pytest.approx(sim.get_portfolio_equity({"BTCUSDT": 97.2}), 1e-5) == sim.cash
