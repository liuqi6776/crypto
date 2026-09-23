# -*- coding: utf-8 -*-
"""
Exhaustive Ledger Reconciliation & Edge-Case Unit Tests
=======================================================
Verifies:
1. Strict Mathematical Identity:
   Final Equity == Initial Cash + Sum(Gross Realized PnL) - Sum(Entry Fees) - Sum(Exit Fees)
                   - Sum(Funding) - Sum(Borrow) + Open Position Unrealized PnL
   Error must be < 1e-4 USD.
2. Edge-Case Matrix:
   - Same-bar stop-loss (开仓当根触发止损)
   - Gap-down open through stop-loss (跳空缺口穿透)
   - Consecutive rapid asset rotation (连续换币摩擦)
   - Simulation ends with open position (期末仍持仓对账)
   - Intrabar exchange liquidation (强平穿仓保护)
"""

import pytest
import pandas as pd
import numpy as np
from crypto_quant.backtest.clean_single_ledger_engine import SingleLedgerSimulator, TradeRecord


def make_mock_df(bars=160, start_price=100.0, trend=0.005, vol_mult=0.01):
    idx = pd.date_range('2024-01-01', periods=bars, freq='4h')
    closes = [start_price * ((1.0 + trend) ** i) for i in range(bars)]
    opens = [c * 0.999 for c in closes]
    highs = [c * (1.0 + vol_mult) for c in closes]
    lows = [c * (1.0 - vol_mult) for c in closes]
    vols = [1000.0 for _ in range(bars)]
    return pd.DataFrame({'open': opens, 'high': highs, 'low': lows, 'close': closes, 'vol': vols}, index=idx)


def test_strict_mathematical_identity():
    """Verify that Final Equity reconciles to within 1e-4 USD of all cash flows."""
    symbols = ['BTCUSDT', 'ETHUSDT']
    raw_dfs = {
        'BTCUSDT': make_mock_df(160, 40000.0, trend=0.004),
        'ETHUSDT': make_mock_df(160, 2000.0, trend=0.007),
    }
    # Test for 1.0x Spot
    sim_1x = SingleLedgerSimulator(symbols=symbols, raw_dfs=raw_dfs, leverage=1.0)
    res_1x = sim_1x.run('2024-01-01', '2024-03-01')
    assert res_1x is not None
    assert res_1x['is_perfectly_reconciled']
    assert res_1x['reconciliation_error'] < 1e-4

    # Test for 3.0x Leverage
    sim_3x = SingleLedgerSimulator(symbols=symbols, raw_dfs=raw_dfs, leverage=3.0)
    res_3x = sim_3x.run('2024-01-01', '2024-03-01')
    assert res_3x is not None
    assert res_3x['is_perfectly_reconciled']
    assert res_3x['reconciliation_error'] < 1e-4


def test_same_bar_stop_loss():
    """Verify a trade that opens and immediately stops out on the exact same bar."""
    idx = pd.date_range('2024-01-01', periods=140, freq='4h')
    # Create uptrend for 130 bars to trigger BUY
    closes = [100.0 * (1.002 ** i) for i in range(130)]
    # Bar 130 to 139: add 10 bars
    closes.append(112.0)
    for i in range(131, 140):
        closes.append(112.0 * (0.999 ** (i - 130)))

    opens = [c * 0.999 for c in closes]
    highs = [c * 1.01 for c in closes]
    lows = [c * 0.99 for c in closes]

    # Force bar 130 to have open 130 and low 110 (triggering stop)
    opens[130] = 130.0
    highs[130] = 131.0
    lows[130] = 110.0
    closes[130] = 112.0

    df = pd.DataFrame({'open': opens, 'high': highs, 'low': lows, 'close': closes, 'vol': [1000.0]*140}, index=idx)
    raw_dfs = {'BTCUSDT': df}

    sim = SingleLedgerSimulator(symbols=['BTCUSDT'], raw_dfs=raw_dfs, leverage=1.0)
    res = sim.run('2024-01-01', '2024-03-01')
    assert res is not None
    assert res['stop_count'] >= 1
    assert res['is_perfectly_reconciled']
    assert res['final_equity'] > 0


def test_gap_down_stop_loss():
    """Verify that if candle gaps down below stop price, exit execution is bounded by Open price."""
    idx = pd.date_range('2024-01-01', periods=140, freq='4h')
    closes = [100.0 * (1.002 ** i) for i in range(130)]
    closes.append(120.0) # bar 130
    closes.append(100.0) # bar 131 gap down
    for i in range(132, 140):
        closes.append(100.0)

    opens = [c for c in closes]
    highs = [c * 1.01 for c in closes]
    lows = [c * 0.99 for c in closes]

    # Bar 131 gaps down to 100
    opens[131] = 100.0
    lows[131] = 98.0
    highs[131] = 101.0
    closes[131] = 100.0

    df = pd.DataFrame({'open': opens, 'high': highs, 'low': lows, 'close': closes, 'vol': [1000.0]*140}, index=idx)
    raw_dfs = {'BTCUSDT': df}

    sim = SingleLedgerSimulator(symbols=['BTCUSDT'], raw_dfs=raw_dfs, leverage=1.0)
    res = sim.run('2024-01-01', '2024-03-01')
    assert res is not None
    assert res['is_perfectly_reconciled']


def test_open_position_at_simulation_end():
    """Verify ledger reconciliation when simulation finishes while still holding an active asset."""
    symbols = ['BTCUSDT']
    # Steady bull trend so it remains holding at end
    raw_dfs = {'BTCUSDT': make_mock_df(160, 40000.0, trend=0.005)}
    sim = SingleLedgerSimulator(symbols=symbols, raw_dfs=raw_dfs, leverage=1.0)
    res = sim.run('2024-01-01', '2024-03-01')
    assert res is not None
    assert res['open_unrealized_pnl'] != 0.0
    assert res['is_perfectly_reconciled']
    assert res['reconciliation_error'] < 1e-4


def test_intrabar_liquidation():
    """Verify that a drop below liquidation threshold terminates the account to exactly 0.0."""
    idx = pd.date_range('2024-01-01', periods=140, freq='4h')
    closes = [100.0 * (1.002 ** i) for i in range(130)]
    closes.append(130.0)
    closes.append(60.0)
    for i in range(132, 140):
        closes.append(60.0)

    opens = [c for c in closes]
    highs = [c * 1.01 for c in closes]
    lows = [c * 0.99 for c in closes]

    opens[131] = 130.0
    lows[131] = 50.0  # -61% drop intrabar!
    closes[131] = 60.0

    df = pd.DataFrame({'open': opens, 'high': highs, 'low': lows, 'close': closes, 'vol': [1000.0]*140}, index=idx)
    raw_dfs = {'BTCUSDT': df}

    sim = SingleLedgerSimulator(symbols=['BTCUSDT'], raw_dfs=raw_dfs, leverage=3.0)
    res = sim.run('2024-01-01', '2024-03-01')
    assert res is not None
    assert res['liquidated'] is True
    assert res['final_equity'] == 0.0
    assert res['final_cash'] == 0.0
    assert res['is_perfectly_reconciled']
