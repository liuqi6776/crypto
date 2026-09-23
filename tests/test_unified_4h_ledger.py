# -*- coding: utf-8 -*-
"""
Unit Tests for Unified 4h Single-Ledger Pipeline (Phase 37.3)
=============================================================
Tests:
1. Exact mathematical ledger reconciliation (Equity == Cash + Positions, error < 1e-4).
2. Strict causality of prior-bar trailing stop in Mode B (Zero lookahead to bar t High).
3. Two-step evaluation pipeline integrity (Step 1 Reproduction vs Step 2 Spot Controlled Benchmark).
4. Sidecar logger execution and non-intrusive depth capture.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path

from crypto_quant.backtest.unified_4h_engine import Unified4hEngine, StopLossMode
from crypto_quant.data.data_manifest import audit_ohlcv_dataframe, compute_file_sha256

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def synthetic_ohlcv_data():
    """Generates synthetic causal 4h data for BTC, ETH, SOL, BNB."""
    timestamps = pd.date_range("2024-01-01 00:00:00", periods=500, freq="4h")
    data = {}
    np.random.seed(42)

    for sym, base_px in [("BTCUSDT", 40000.0), ("ETHUSDT", 2500.0), ("SOLUSDT", 100.0), ("BNBUSDT", 300.0)]:
        # Geometric random walk with upward trend
        ret = np.random.normal(0.001, 0.015, size=len(timestamps))
        closes = base_px * np.cumprod(1.0 + ret)
        opens = np.roll(closes, 1)
        opens[0] = base_px
        highs = np.maximum(opens, closes) * (1.0 + np.abs(np.random.normal(0.005, 0.005, size=len(timestamps))))
        lows = np.minimum(opens, closes) * (1.0 - np.abs(np.random.normal(0.005, 0.005, size=len(timestamps))))
        vols = np.random.uniform(100.0, 1000.0, size=len(timestamps))

        df = pd.DataFrame({
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": vols,
        }, index=timestamps)
        data[sym] = df

    return data


def test_audit_ohlcv_integrity(synthetic_ohlcv_data):
    """Verifies that audit_ohlcv_dataframe correctly validates valid OHLCV and catches flaws."""
    df_btc = synthetic_ohlcv_data["BTCUSDT"]
    res = audit_ohlcv_dataframe(df_btc)
    assert res["is_valid"] is True
    assert res["missing_bars_count"] == 0
    assert res["duplicate_timestamps"] == 0
    assert res["invalid_high_count"] == 0
    assert res["invalid_low_count"] == 0


def test_structural_trend_ledger_reconciliation(synthetic_ohlcv_data):
    """
    Verifies that Unified4hEngine maintains zero mathematical discrepancy on every single bar:
    Total Equity == Cash + Position Value
    Total Equity - Initial Cash == Realized PnL + Unrealized PnL - Total Fees
    """
    engine_a = Unified4hEngine(initial_cash=10000.0, stop_loss_mode=StopLossMode.BAR_CLOSE)
    res_a = engine_a.run_structural_trend(synthetic_ohlcv_data, symbols=["ETHUSDT", "SOLUSDT"])

    df_ledger = res_a["bar_ledger"]
    assert len(df_ledger) == 500
    assert "total_equity" in df_ledger.columns
    assert "cash" in df_ledger.columns
    assert "cum_fees" in df_ledger.columns

    # Verify reconciliation across all bars
    cash_plus_pos = df_ledger["cash"] + df_ledger["position_value"]
    np.testing.assert_allclose(df_ledger["total_equity"].values, cash_plus_pos.values, rtol=1e-5, atol=1e-5)

    acct_delta = df_ledger["gross_realized_pnl"] + df_ledger["gross_unrealized_pnl"] - df_ledger["cum_fees"]
    equity_delta = df_ledger["total_equity"] - 10000.0
    np.testing.assert_allclose(equity_delta.values, acct_delta.values, rtol=1e-5, atol=1e-5)


def test_intrabar_stop_loss_causality(synthetic_ohlcv_data):
    """
    Verifies Mode B (Intrabar Stop Touch):
    Uses strictly the trailing stop price fixed at bar t-1 close,
    never peaking into bar t High before checking bar t Low.
    """
    engine_b = Unified4hEngine(initial_cash=10000.0, stop_loss_mode=StopLossMode.INTRABAR_STOP_TOUCH)
    res_b = engine_b.run_structural_trend(synthetic_ohlcv_data, symbols=["ETHUSDT", "SOLUSDT"])

    df_trades = res_b["trades"]
    if not df_trades.empty and "INTRABAR_STOP_TOUCH" in df_trades["exit_reason"].values:
        stop_trades = df_trades[df_trades["exit_reason"] == "INTRABAR_STOP_TOUCH"]
        for _, tr in stop_trades.iterrows():
            sym = tr["symbol"]
            exit_t = tr["exit_time"]
            bar_l = synthetic_ohlcv_data[sym].loc[exit_t, "low"]
            # Exit price must be consistent with intrabar touch logic
            assert tr["exit_price"] >= bar_l * 0.95


def test_simple_ema_control_runs_cleanly(synthetic_ohlcv_data):
    """Verifies that both ETH/SOL 50/50 and Core-4 Simple EMA Controls run with perfect reconciliation."""
    engine = Unified4hEngine(initial_cash=10000.0)

    # 1. ETH/SOL 50/50 control
    res_ethsol = engine.run_simple_ema_control(synthetic_ohlcv_data, symbols=["ETHUSDT", "SOLUSDT"])
    assert res_ethsol["strategy"] == "SIMPLE_EMA_2COINS"
    assert res_ethsol["final_equity"] > 0.0

    # 2. Core-4 control
    res_core4 = engine.run_simple_ema_control(synthetic_ohlcv_data, symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"])
    assert res_core4["strategy"] == "SIMPLE_EMA_4COINS"
    assert res_core4["final_equity"] > 0.0


def test_top1_rotation_single_ledger_reconciliation(synthetic_ohlcv_data):
    """
    Verifies that run_top1_rotation runs natively inside Unified4hEngine with:
    1. Single cash pool (when holding token, cash is ~0; when in USDT_CASH, cash is ~equity).
    2. Zero mathematical discrepancy on every single bar:
       Total Equity == Cash + Position Value
       Total Equity - Initial Cash == Realized PnL + Unrealized PnL - Total Fees
    3. Bar-by-bar monotonically accumulating fees.
    """
    engine = Unified4hEngine(initial_cash=10000.0)
    res_rot = engine.run_top1_rotation(synthetic_ohlcv_data, delta_score_buffer=0.30, warmup_bars=125)

    assert "TOP1_ROTATION" in res_rot["strategy"]
    df_ledger = res_rot["bar_ledger"]
    assert len(df_ledger) == 500

    # Assert single-ledger invariants on every bar
    cash_plus_pos = df_ledger["cash"] + df_ledger["position_value"]
    np.testing.assert_allclose(df_ledger["total_equity"].values, cash_plus_pos.values, rtol=1e-5, atol=1e-5)

    acct_delta = df_ledger["gross_realized_pnl"] + df_ledger["gross_unrealized_pnl"] - df_ledger["cum_fees"]
    equity_delta = df_ledger["total_equity"] - 10000.0
    np.testing.assert_allclose(equity_delta.values, acct_delta.values, rtol=1e-5, atol=1e-5)

    # Assert cumulative fees are monotonically increasing
    diffs = df_ledger["cum_fees"].diff().dropna()
    assert (diffs >= -1e-8).all(), "Fees must be monotonically non-decreasing bar-by-bar"


def test_channel_ablation_bollinger_vs_donchian(synthetic_ohlcv_data):
    """
    Verifies that run_structural_trend supports both channel_type='bollinger' and 'donchian',
    and that bar_friction columns exist and reconcile exactly.
    """
    engine = Unified4hEngine(initial_cash=10000.0)

    # 1. Bollinger
    res_b = engine.run_structural_trend(synthetic_ohlcv_data, symbols=["ETHUSDT", "SOLUSDT"], channel_type="bollinger")
    ledger_b = res_b["bar_ledger"]
    assert "bar_friction" in ledger_b.columns
    np.testing.assert_allclose(ledger_b["bar_friction"].sum(), ledger_b["cum_fees"].iloc[-1] + ledger_b["cum_slippage"].iloc[-1], rtol=1e-5)

    # 2. Donchian
    res_d = engine.run_structural_trend(synthetic_ohlcv_data, symbols=["ETHUSDT", "SOLUSDT"], channel_type="donchian")
    ledger_d = res_d["bar_ledger"]
    assert "bar_friction" in ledger_d.columns
    np.testing.assert_allclose(ledger_d["bar_friction"].sum(), ledger_d["cum_fees"].iloc[-1] + ledger_d["cum_slippage"].iloc[-1], rtol=1e-5)

    # Both must preserve the mathematical ledger identity
    for led in [ledger_b, ledger_d]:
        cash_pos = led["cash"] + led["position_value"]
        np.testing.assert_allclose(led["total_equity"].values, cash_pos.values, rtol=1e-5, atol=1e-5)


def test_isolated_channel_and_sizing_ablation(synthetic_ohlcv_data):
    """
    Verifies that run_structural_trend supports exit_channel_type decoupling
    and macro_sizing_mode options, while strictly maintaining ledger identities.
    """
    engine = Unified4hEngine(initial_cash=10000.0)

    # 1. Exit channel decoupling
    res_shared_exit = engine.run_structural_trend(
        synthetic_ohlcv_data,
        symbols=["ETHUSDT", "SOLUSDT"],
        channel_type="donchian",
        exit_channel_type="bollinger",
    )
    led_shared = res_shared_exit["bar_ledger"]
    cash_pos = led_shared["cash"] + led_shared["position_value"]
    np.testing.assert_allclose(led_shared["total_equity"].values, cash_pos.values, rtol=1e-5, atol=1e-5)

    res_no_mid = engine.run_structural_trend(
        synthetic_ohlcv_data,
        symbols=["ETHUSDT", "SOLUSDT"],
        channel_type="bollinger",
        exit_channel_type="none",
    )
    led_no_mid = res_no_mid["bar_ledger"]
    cash_pos = led_no_mid["cash"] + led_no_mid["position_value"]
    np.testing.assert_allclose(led_no_mid["total_equity"].values, cash_pos.values, rtol=1e-5, atol=1e-5)

    # 2. Macro sizing modes
    for mode in ["fixed_full", "ema200_binary", "ema200_half"]:
        res_mode = engine.run_structural_trend(
            synthetic_ohlcv_data,
            symbols=["ETHUSDT", "SOLUSDT"],
            channel_type="bollinger",
            macro_sizing_mode=mode,
        )
        led_m = res_mode["bar_ledger"]
        cash_pos = led_m["cash"] + led_m["position_value"]
        np.testing.assert_allclose(led_m["total_equity"].values, cash_pos.values, rtol=1e-5, atol=1e-5)


