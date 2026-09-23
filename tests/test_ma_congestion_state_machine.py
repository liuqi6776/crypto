# -*- coding: utf-8 -*-
"""
Unit Tests for Moving Average Congestion Breakout & Pullback State Machine
均线密集突破后回踩状态机单元测试
"""

import pytest
import numpy as np
import pandas as pd

from crypto_quant.ma_congestion.state_machine import (
    MACongestionStateMachine,
    PatternState,
    TradeSignal,
    compute_indicators,
)


def make_synthetic_df(n_bars: int = 100, base_price: float = 100.0) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=n_bars, freq="15min")
    df = pd.DataFrame(index=dates)
    df["open"] = base_price
    df["high"] = base_price + 1.0
    df["low"] = base_price - 1.0
    df["close"] = base_price
    df["volume"] = 1000.0
    return df


def test_compute_indicators():
    df = make_synthetic_df(50, 100.0)
    res_ema = compute_indicators(df, ma_type="EMA")
    assert "ma20" in res_ema.columns
    assert "ma50" in res_ema.columns
    assert "ma100" in res_ema.columns
    assert "ma200" in res_ema.columns
    assert "atr14" in res_ema.columns
    assert "ma200_slope_4" in res_ema.columns
    assert "ma_spread" in res_ema.columns

    res_sma = compute_indicators(df, ma_type="SMA")
    assert "ma20" in res_sma.columns
    assert not res_sma["ma20"].isna().all()


def test_state_machine_long_full_lifecycle():
    """
    Tests complete successful Long lifecycle:
    1. Trend valid (close > ma200, slope > 0)
    2. 3 consecutive bars with spread <= 0.5 * ATR -> CONGESTION_FORMED
    3. Breakout within 6 bars -> AWAITING_PULLBACK
    4. Pullback touches tolerance, holds lower bound, closes > U -> CONFIRMED_SIGNAL
    """
    sm = MACongestionStateMachine(symbol="BTCUSDT", direction="LONG")
    now = pd.Timestamp("2026-01-01 00:00:00")

    # Bars 1-3: Congestion formed
    # ma20=100.1, ma50=100.0, ma100=99.9 -> spread=0.2 <= 0.5 * atr(1.0)
    for i in range(3):
        t = now + pd.Timedelta(minutes=15 * i)
        row = pd.Series({
            "close": 100.5,
            "high": 101.0,
            "low": 99.5,
            "ma20": 100.1,
            "ma50": 100.0,
            "ma100": 99.9,
            "ma200": 95.0,
            "ma200_slope_4": 0.5,
            "atr14": 1.0,
        })
        sig = sm.feed_bar(t, row)
        assert sig is None

    # After bar 3, state should be CONGESTION_FORMED
    assert sm.state == PatternState.CONGESTION_FORMED
    assert sm.current_zone is not None
    assert sm.current_zone.U == 100.1
    assert sm.current_zone.L == 99.9
    assert sm.current_zone.frozen_atr == 1.0

    # Bar 4: Non-breakout bar
    t4 = now + pd.Timedelta(minutes=45)
    row4 = pd.Series({
        "close": 100.4,
        "high": 100.8,
        "low": 100.0,
        "ma20": 100.1, "ma50": 100.0, "ma100": 99.9, "ma200": 95.1, "ma200_slope_4": 0.5, "atr14": 1.0,
    })
    sig4 = sm.feed_bar(t4, row4)
    assert sig4 is None
    assert sm.state == PatternState.CONGESTION_FORMED

    # Bar 5: Breakout bar! (Close > U + 0.5 * ATR = 100.1 + 0.5 = 100.6)
    t5 = now + pd.Timedelta(minutes=60)
    row5 = pd.Series({
        "close": 100.8,
        "high": 101.5,
        "low": 100.3,
        "ma20": 100.2, "ma50": 100.0, "ma100": 99.9, "ma200": 95.2, "ma200_slope_4": 0.5, "atr14": 1.0,
    })
    sig5 = sm.feed_bar(t5, row5)
    assert sig5 is None
    assert sm.state == PatternState.AWAITING_PULLBACK
    assert sm.breakout_bar == t5
    assert sm.breakout_price == 100.8

    # Bar 6: Pullback confirmation bar!
    # U = 100.1, L = 99.9, frozen_atr = 1.0
    # Tolerance zone: Low <= U + 0.1*ATR = 100.2
    # Lower bound hold: Low >= L - 0.1*ATR = 99.8
    # Close reclaims: Close > U = 100.1
    t6 = now + pd.Timedelta(minutes=75)
    row6 = pd.Series({
        "close": 100.4,
        "high": 100.7,
        "low": 100.05,  # 100.05 is <= 100.2 and >= 99.8
        "ma20": 100.2, "ma50": 100.0, "ma100": 99.9, "ma200": 95.3, "ma200_slope_4": 0.5, "atr14": 1.0,
    })
    sig6 = sm.feed_bar(t6, row6)
    assert sig6 is not None
    assert isinstance(sig6, TradeSignal)
    assert sig6.direction == "LONG"
    assert sig6.confirm_price == 100.4
    # Initial SL: L - 0.2 * frozen_atr = 99.9 - 0.2 = 99.7
    assert pytest.approx(sig6.initial_sl, 1e-5) == 99.7
    assert sm.state == PatternState.IDLE  # reset after firing


def test_state_machine_long_invalidation():
    """Tests that breaching L - 0.1 * ATR during pullback voids pattern immediately."""
    sm = MACongestionStateMachine(symbol="BTCUSDT", direction="LONG")
    now = pd.Timestamp("2026-01-01 00:00:00")

    # Form congestion
    for i in range(3):
        t = now + pd.Timedelta(minutes=15 * i)
        row = pd.Series({
            "close": 100.0, "high": 100.5, "low": 99.5,
            "ma20": 100.1, "ma50": 100.0, "ma100": 99.9, "ma200": 95.0, "ma200_slope_4": 0.5, "atr14": 1.0,
        })
        sm.feed_bar(t, row)
    assert sm.state == PatternState.CONGESTION_FORMED

    # Breakout
    t_bo = now + pd.Timedelta(minutes=45)
    row_bo = pd.Series({
        "close": 101.0, "high": 101.5, "low": 100.0,
        "ma20": 100.1, "ma50": 100.0, "ma100": 99.9, "ma200": 95.0, "ma200_slope_4": 0.5, "atr14": 1.0,
    })
    sm.feed_bar(t_bo, row_bo)
    assert sm.state == PatternState.AWAITING_PULLBACK

    # Flash crash breaching lower tolerance: Low < L - 0.1 * ATR = 99.9 - 0.1 = 99.8
    t_inv = now + pd.Timedelta(minutes=60)
    row_inv = pd.Series({
        "close": 100.2, "high": 100.5, "low": 99.6,  # 99.6 < 99.8!
        "ma20": 100.1, "ma50": 100.0, "ma100": 99.9, "ma200": 95.0, "ma200_slope_4": 0.5, "atr14": 1.0,
    })
    sig = sm.feed_bar(t_inv, row_inv)
    assert sig is None
    assert sm.state == PatternState.IDLE  # Invalidated to IDLE!


def test_state_machine_short_mirror():
    """Tests strict short mirror logic."""
    sm = MACongestionStateMachine(symbol="BTCUSDT", direction="SHORT")
    now = pd.Timestamp("2026-01-01 00:00:00")

    # 3 bars congestion in downtrend (Close < MA200 and slope < 0)
    for i in range(3):
        t = now + pd.Timedelta(minutes=15 * i)
        row = pd.Series({
            "close": 99.5, "high": 100.5, "low": 99.0,
            "ma20": 100.1, "ma50": 100.0, "ma100": 99.9, "ma200": 105.0, "ma200_slope_4": -0.5, "atr14": 1.0,
        })
        sm.feed_bar(t, row)
    assert sm.state == PatternState.CONGESTION_FORMED
    assert sm.current_zone.U == 100.1
    assert sm.current_zone.L == 99.9

    # Breakdown: Close < L - 0.5 * ATR = 99.9 - 0.5 = 99.4
    t_bd = now + pd.Timedelta(minutes=45)
    row_bd = pd.Series({
        "close": 99.2, "high": 99.6, "low": 98.5,
        "ma20": 100.0, "ma50": 100.0, "ma100": 99.9, "ma200": 105.0, "ma200_slope_4": -0.5, "atr14": 1.0,
    })
    sm.feed_bar(t_bd, row_bd)
    assert sm.state == PatternState.AWAITING_PULLBACK

    # Pullback upward confirmation:
    # High touches L - 0.1 * ATR = 99.8, High <= U + 0.1 * ATR = 100.2, and Close < L (99.9)
    t_pb = now + pd.Timedelta(minutes=60)
    row_pb = pd.Series({
        "close": 99.7, "high": 100.0, "low": 99.3,  # High=100.0 is >= 99.8 and <= 100.2; Close=99.7 < 99.9
        "ma20": 100.0, "ma50": 100.0, "ma100": 99.9, "ma200": 105.0, "ma200_slope_4": -0.5, "atr14": 1.0,
    })
    sig = sm.feed_bar(t_pb, row_pb)
    assert sig is not None
    assert sig.direction == "SHORT"
    # Initial SL: U + 0.2 * ATR = 100.1 + 0.2 = 100.3
    assert pytest.approx(sig.initial_sl, 1e-5) == 100.3
    assert sm.state == PatternState.IDLE
