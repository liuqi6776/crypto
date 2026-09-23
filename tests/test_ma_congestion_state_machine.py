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


def test_state_machine_strict_support_long_lifecycle():
    """
    Tests complete successful STRICT_SUPPORT Long lifecycle:
    1. Trend valid (close > ma200, slope > 0)
    2. 3 consecutive bars with spread <= 0.5 * ATR and close > U -> directly AWAITING_PULLBACK
    3. Pullback bar: Low >= U (NO penetration) and Low <= U + 0.1 * ATR, Close > U -> CONFIRMED_SIGNAL
    4. Assert low_distance_to_u >= 0
    """
    sm = MACongestionStateMachine(symbol="BTCUSDT", direction="LONG", pullback_mode="STRICT_SUPPORT")
    now = pd.Timestamp("2026-01-01 00:00:00")

    # Bars 1-3: Congestion formed with price above U (U=100.1, L=99.9, ATR=1.0, close=100.5 > U)
    for i in range(3):
        t = now + pd.Timedelta(minutes=15 * i)
        row = pd.Series({
            "close": 100.5,
            "high": 101.0,
            "low": 100.2,
            "ma20": 100.1,
            "ma50": 100.0,
            "ma100": 99.9,
            "ma200": 95.0,
            "ma200_slope_4": 0.5,
            "atr14": 1.0,
        })
        sig = sm.feed_bar(t, row)
        assert sig is None

    # In STRICT_SUPPORT mode, directly transitions to AWAITING_PULLBACK
    assert sm.state == PatternState.AWAITING_PULLBACK
    assert sm.current_zone is not None
    assert sm.current_zone.U == 100.1
    assert sm.current_zone.L == 99.9
    assert sm.current_zone.frozen_atr == 1.0

    # Bar 4: Strict pullback bar!
    # Low = 100.15 >= U (100.1) -> NO penetration!
    # Low = 100.15 <= U + 0.1 * ATR (100.2) -> touches tolerance band
    # Close = 100.4 > U (100.1) -> reclaims/confirms support
    t4 = now + pd.Timedelta(minutes=45)
    row4 = pd.Series({
        "close": 100.4,
        "high": 100.8,
        "low": 100.15,
        "ma20": 100.1, "ma50": 100.0, "ma100": 99.9, "ma200": 95.1, "ma200_slope_4": 0.5, "atr14": 1.0,
    })
    sig4 = sm.feed_bar(t4, row4)
    assert sig4 is not None
    assert isinstance(sig4, TradeSignal)
    assert sig4.direction == "LONG"
    assert sig4.pullback_mode == "STRICT_SUPPORT"
    assert sig4.confirm_price == 100.4
    assert sig4.low_distance_to_u == round(100.15 - 100.1, 6)
    assert sig4.low_distance_to_u >= 0.0
    # Initial SL: L - 0.2 * frozen_atr = 99.9 - 0.2 = 99.7
    assert pytest.approx(sig4.initial_sl, 1e-5) == 99.7
    assert sm.state == PatternState.IDLE


def test_state_machine_strict_support_long_invalidation():
    """
    Tests STRICT_SUPPORT invalidation:
    If candle wick penetrates below U (Low < U), pattern is IMMEDIATELY VOIDED!
    """
    sm = MACongestionStateMachine(symbol="BTCUSDT", direction="LONG", pullback_mode="STRICT_SUPPORT")
    now = pd.Timestamp("2026-01-01 00:00:00")

    # Form congestion
    for i in range(3):
        t = now + pd.Timedelta(minutes=15 * i)
        row = pd.Series({
            "close": 100.5, "high": 101.0, "low": 100.2,
            "ma20": 100.1, "ma50": 100.0, "ma100": 99.9, "ma200": 95.0, "ma200_slope_4": 0.5, "atr14": 1.0,
        })
        sm.feed_bar(t, row)
    assert sm.state == PatternState.AWAITING_PULLBACK

    # Bar 4: Wick penetrates into MA group: Low = 100.05 < U (100.1)
    t4 = now + pd.Timedelta(minutes=45)
    row4 = pd.Series({
        "close": 100.3, "high": 100.8, "low": 100.05,  # 100.05 < 100.1!
        "ma20": 100.1, "ma50": 100.0, "ma100": 99.9, "ma200": 95.0, "ma200_slope_4": 0.5, "atr14": 1.0,
    })
    sig4 = sm.feed_bar(t4, row4)
    assert sig4 is None
    assert sm.state == PatternState.IDLE  # Pattern invalidated immediately!


def test_state_machine_strict_support_short_lifecycle():
    """
    Tests complete successful STRICT_SUPPORT Short lifecycle:
    1. Trend valid (close < ma200, slope < 0)
    2. 3 consecutive bars with spread <= 0.5 * ATR and close < L -> directly AWAITING_PULLBACK
    3. Pullback bar: High <= L (NO penetration) and High >= L - 0.1 * ATR, Close < L -> CONFIRMED_SIGNAL
    4. Assert high_distance_to_l >= 0
    """
    sm = MACongestionStateMachine(symbol="BTCUSDT", direction="SHORT", pullback_mode="STRICT_SUPPORT")
    now = pd.Timestamp("2026-01-01 00:00:00")

    # Form congestion (U=100.1, L=99.9, ATR=1.0, close=99.5 < L)
    for i in range(3):
        t = now + pd.Timedelta(minutes=15 * i)
        row = pd.Series({
            "close": 99.5, "high": 99.8, "low": 99.0,
            "ma20": 100.1, "ma50": 100.0, "ma100": 99.9, "ma200": 105.0, "ma200_slope_4": -0.5, "atr14": 1.0,
        })
        sm.feed_bar(t, row)
    assert sm.state == PatternState.AWAITING_PULLBACK

    # Bar 4: Strict short bounce:
    # High = 99.85 <= L (99.9) -> NO penetration into MA band!
    # High = 99.85 >= L - 0.1 * ATR (99.8) -> touches tolerance band
    # Close = 99.6 < L (99.9) -> confirms resistance
    t4 = now + pd.Timedelta(minutes=45)
    row4 = pd.Series({
        "close": 99.6, "high": 99.85, "low": 99.2,
        "ma20": 100.1, "ma50": 100.0, "ma100": 99.9, "ma200": 105.0, "ma200_slope_4": -0.5, "atr14": 1.0,
    })
    sig4 = sm.feed_bar(t4, row4)
    assert sig4 is not None
    assert sig4.direction == "SHORT"
    assert sig4.pullback_mode == "STRICT_SUPPORT"
    assert sig4.high_distance_to_l == round(99.9 - 99.85, 6)
    assert sig4.high_distance_to_l >= 0.0
    # Initial SL: U + 0.2 * ATR = 100.1 + 0.2 = 100.3
    assert pytest.approx(sig4.initial_sl, 1e-5) == 100.3
    assert sm.state == PatternState.IDLE


def test_state_machine_strict_support_short_invalidation():
    """
    Tests STRICT_SUPPORT Short invalidation:
    If candle wick penetrates above L (High > L), pattern is IMMEDIATELY VOIDED!
    """
    sm = MACongestionStateMachine(symbol="BTCUSDT", direction="SHORT", pullback_mode="STRICT_SUPPORT")
    now = pd.Timestamp("2026-01-01 00:00:00")

    for i in range(3):
        t = now + pd.Timedelta(minutes=15 * i)
        row = pd.Series({
            "close": 99.5, "high": 99.8, "low": 99.0,
            "ma20": 100.1, "ma50": 100.0, "ma100": 99.9, "ma200": 105.0, "ma200_slope_4": -0.5, "atr14": 1.0,
        })
        sm.feed_bar(t, row)
    assert sm.state == PatternState.AWAITING_PULLBACK

    # Bar 4: Wick penetrates into MA band: High = 99.95 > L (99.9)
    t4 = now + pd.Timedelta(minutes=45)
    row4 = pd.Series({
        "close": 99.6, "high": 99.95, "low": 99.2,  # 99.95 > 99.9!
        "ma20": 100.1, "ma50": 100.0, "ma100": 99.9, "ma200": 105.0, "ma200_slope_4": -0.5, "atr14": 1.0,
    })
    sig4 = sm.feed_bar(t4, row4)
    assert sig4 is None
    assert sm.state == PatternState.IDLE


def test_state_machine_intraband_penetration():
    """
    Tests INTRABAND_PENETRATION mode:
    Wick can penetrate inside zone (L <= Low < U), but Close > U triggers confirmation.
    Breach below L - 0.1 * ATR invalidates.
    """
    sm = MACongestionStateMachine(symbol="BTCUSDT", direction="LONG", pullback_mode="INTRABAND_PENETRATION")
    now = pd.Timestamp("2026-01-01 00:00:00")

    for i in range(3):
        t = now + pd.Timedelta(minutes=15 * i)
        row = pd.Series({
            "close": 100.2, "high": 100.5, "low": 99.5,
            "ma20": 100.1, "ma50": 100.0, "ma100": 99.9, "ma200": 95.0, "ma200_slope_4": 0.5, "atr14": 1.0,
        })
        sm.feed_bar(t, row)
    assert sm.state == PatternState.CONGESTION_FORMED

    # Breakout
    t_bo = now + pd.Timedelta(minutes=45)
    row_bo = pd.Series({
        "close": 100.8, "high": 101.0, "low": 100.0,
        "ma20": 100.1, "ma50": 100.0, "ma100": 99.9, "ma200": 95.0, "ma200_slope_4": 0.5, "atr14": 1.0,
    })
    sm.feed_bar(t_bo, row_bo)
    assert sm.state == PatternState.AWAITING_PULLBACK

    # Pullback penetrates into band: Low = 100.0 (between L=99.9 and U=100.1), Close = 100.4 > U
    t_pb = now + pd.Timedelta(minutes=60)
    row_pb = pd.Series({
        "close": 100.4, "high": 100.7, "low": 100.0,
        "ma20": 100.1, "ma50": 100.0, "ma100": 99.9, "ma200": 95.0, "ma200_slope_4": 0.5, "atr14": 1.0,
    })
    sig = sm.feed_bar(t_pb, row_pb)
    assert sig is not None
    assert sig.pullback_mode == "INTRABAND_PENETRATION"
    assert sig.low_distance_to_u == round(100.0 - 100.1, 6)  # negative because penetrated below U!
    assert sig.low_distance_to_u < 0.0


def test_state_machine_loose_penetration_reclaim_lifecycle():
    """
    Tests previous LOOSE_PENETRATION_RECLAIM lifecycle:
    Requires antecedent breakout > U + 0.5*ATR, and allows Low down to L - 0.1*ATR.
    """
    sm = MACongestionStateMachine(symbol="BTCUSDT", direction="LONG", pullback_mode="LOOSE_PENETRATION_RECLAIM")
    now = pd.Timestamp("2026-01-01 00:00:00")

    # 3 bars congestion
    for i in range(3):
        t = now + pd.Timedelta(minutes=15 * i)
        row = pd.Series({
            "close": 100.5, "high": 101.0, "low": 99.5,
            "ma20": 100.1, "ma50": 100.0, "ma100": 99.9, "ma200": 95.0, "ma200_slope_4": 0.5, "atr14": 1.0,
        })
        sm.feed_bar(t, row)
    assert sm.state == PatternState.CONGESTION_FORMED
    assert sm.current_zone.U == 100.1
    assert sm.current_zone.L == 99.9

    # Breakout bar (Close > 100.1 + 0.5 = 100.6)
    t_bo = now + pd.Timedelta(minutes=45)
    row_bo = pd.Series({
        "close": 100.8, "high": 101.5, "low": 100.3,
        "ma20": 100.2, "ma50": 100.0, "ma100": 99.9, "ma200": 95.2, "ma200_slope_4": 0.5, "atr14": 1.0,
    })
    sm.feed_bar(t_bo, row_bo)
    assert sm.state == PatternState.AWAITING_PULLBACK

    # Reclaim bar
    t_rec = now + pd.Timedelta(minutes=60)
    row_rec = pd.Series({
        "close": 100.4, "high": 100.7, "low": 100.05,
        "ma20": 100.2, "ma50": 100.0, "ma100": 99.9, "ma200": 95.3, "ma200_slope_4": 0.5, "atr14": 1.0,
    })
    sig = sm.feed_bar(t_rec, row_rec)
    assert sig is not None
    assert sig.pullback_mode == "LOOSE_PENETRATION_RECLAIM"
    assert sm.state == PatternState.IDLE
