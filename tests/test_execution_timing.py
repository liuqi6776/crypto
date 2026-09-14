# -*- coding: utf-8 -*-
"""
Tests for Causal Execution Timing (Phase 17)
Verifies strict causal signal-to-open execution timing:
1. Signal confirmed at bar t close -> order queued as pending.
2. Position remains 0.0 at bar t close.
3. Order filled at bar t+1 open with normal slippage.
4. Exit signal at bar t close fills at bar t+1 open.
5. Funding fee before order fill is strictly not charged.
"""

import unittest
import pandas as pd
import numpy as np

from crypto_quant.continuous_backtest import ContinuousBacktestEngine
from crypto_quant.execution_model import ExecutionModel


class TestExecutionTiming(unittest.TestCase):

    def setUp(self):
        # 10 bars starting at 2024-01-01 00:00:00 (settlement hour)
        dates = pd.date_range("2024-01-01 00:00:00", periods=10, freq="4h")
        self.dates = dates
        self.df_bars = pd.DataFrame({
            "open": [3000.0, 3010.0, 3020.0, 3030.0, 3040.0, 3050.0, 3060.0, 3070.0, 3080.0, 3090.0],
            "high": [3015.0, 3025.0, 3035.0, 3045.0, 3055.0, 3065.0, 3075.0, 3085.0, 3095.0, 3105.0],
            "low": [2995.0, 3005.0, 3015.0, 3025.0, 3035.0, 3045.0, 3055.0, 3065.0, 3075.0, 3085.0],
            "close": [3008.0, 3018.0, 3028.0, 3038.0, 3048.0, 3058.0, 3068.0, 3078.0, 3088.0, 3098.0],
        }, index=dates)

        # Baseline flat predictions
        self.preds = pd.Series([0.0] * 10, index=dates)
        self.funding = pd.Series([0.0001] * 10, index=dates)  # +0.01%
        self.fng = pd.Series([50.0] * 10, index=dates)

    def test_signal_at_t_fills_at_next_bar_open(self):
        """Verify signal at bar t close creates pending order and fills at bar t+1 open."""
        # Inject entry signal across bars 2 and 3
        preds = self.preds.copy()
        preds.iloc[2:5] = 0.05  # Keep prediction positive so it doesn't exit at bar 3

        exec_model = ExecutionModel(normal_slippage=0.0004)
        engine = ContinuousBacktestEngine(symbol="ETHUSDT", trial_mode=False, execution_model=exec_model)
        res = engine.run(self.df_bars, preds, self.funding, self.fng)

        # At bar 2 close: position must be 0.0, order must be pending
        st_bar2 = res.state_history[2]
        self.assertEqual(st_bar2.position, 0.0, "Position must be 0.0 at signal close bar")
        self.assertIsNotNone(st_bar2.pending_order, "Pending order must be queued at signal close bar")
        self.assertEqual(st_bar2.pending_order["side"], 1)

        # At bar 3 (next bar): filled at open[3]
        st_bar3 = res.state_history[3]
        self.assertGreater(st_bar3.position, 0.0, "Position must be active on bar 3")
        expected_fill = self.df_bars["open"].iloc[3] * (1.0 + 0.0004)
        self.assertAlmostEqual(st_bar3.entry_price, expected_fill, places=4)
        self.assertIsNone(st_bar3.pending_order, "Pending order must be cleared upon fill")

    def test_exit_signal_at_t_fills_at_next_bar_open(self):
        """Verify exit signal at bar t close fills at bar t+1 open."""
        preds = self.preds.copy()
        preds.iloc[2:4] = 0.05   # Enter long at bar 3 open, hold at bar 3
        preds.iloc[4] = -0.05    # Exit long (below deadband) at bar 4 close

        exec_model = ExecutionModel(normal_slippage=0.0004)
        engine = ContinuousBacktestEngine(symbol="ETHUSDT", trial_mode=False, execution_model=exec_model)
        res = engine.run(self.df_bars, preds, self.funding, self.fng)

        # At bar 4 close: still in position, but pending exit queued
        st_bar4 = res.state_history[4]
        self.assertGreater(st_bar4.position, 0.0, "Position must still be active at exit signal close")
        self.assertIsNotNone(st_bar4.pending_order, "Pending exit order must be queued")
        self.assertEqual(st_bar4.pending_order["type"], "exit")

        # At bar 5 open: exited
        st_bar5 = res.state_history[5]
        self.assertEqual(st_bar5.position, 0.0, "Position must be flat after exit fill")
        self.assertEqual(len(res.trades), 1, "One trade should be completed")
        trade = res.trades[0]
        expected_exit_fill = self.df_bars["open"].iloc[5] * (1.0 - 0.0004)
        self.assertAlmostEqual(trade.exit_price, expected_exit_fill, places=4)

    def test_funding_before_entry_is_not_charged(self):
        """Verify funding settlement occurring prior to entry is not charged to the trade."""
        preds = self.preds.copy()
        # Bar 0 is 00:00 (funding settlement). Inject entry at bar 0 close -> fills at bar 1 (04:00)
        preds.iloc[0] = 0.05

        engine = ContinuousBacktestEngine(symbol="ETHUSDT", trial_mode=False)
        res = engine.run(self.df_bars, preds, self.funding, self.fng)

        st_bar1 = res.state_history[1]
        self.assertEqual(st_bar1.cum_funding_recorded, 0.0,
                         "Funding at 00:00 must not be charged to position entered at 04:00")


if __name__ == "__main__":
    unittest.main()
