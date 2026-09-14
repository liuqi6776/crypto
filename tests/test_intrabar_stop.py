# -*- coding: utf-8 -*-
"""
Tests for Intrabar Stop Execution and Gap Slippage (Phase 17)
Verifies:
1. Long and Short intrabar stop triggering on High/Low breach.
2. Gap down / Gap up open breach using conservative open fill.
3. Intrabar stop priority over candle close bounce.
"""

import unittest
import pandas as pd
import numpy as np

from crypto_quant.execution_model import ExecutionModel, StopCheckResult


class TestIntrabarStop(unittest.TestCase):

    def setUp(self):
        self.exec_model = ExecutionModel(
            stop_slippage=0.0010,
            gap_slippage=0.0015,
            taker_fee=0.0004,
        )

    def test_long_intrabar_stop_breach(self):
        """Long position stops out when Low breaches stop price."""
        # Entry 3000.0, stop 3% -> stop price 2910.0
        # Candle: open 2950, high 2960, low 2900 (breach), close 2930
        res = self.exec_model.check_intrabar_stop(
            pos_direction=1,
            entry_price=3000.0,
            stop_loss_pct=0.03,
            open_p=2950.0,
            high_p=2960.0,
            low_p=2900.0,
            close_p=2930.0,
        )
        self.assertTrue(res.is_stopped)
        self.assertFalse(res.is_gap)
        self.assertEqual(res.reason, "intrabar_stop")
        expected_fill = 2910.0 * (1.0 - 0.0010)
        self.assertAlmostEqual(res.fill_price, expected_fill, places=4)

    def test_short_intrabar_stop_breach(self):
        """Short position stops out when High breaches stop price."""
        # Entry 3000.0, stop 3% -> stop price 3090.0
        # Candle: open 3050, high 3100 (breach), low 3040, close 3060
        res = self.exec_model.check_intrabar_stop(
            pos_direction=-1,
            entry_price=3000.0,
            stop_loss_pct=0.03,
            open_p=3050.0,
            high_p=3100.0,
            low_p=3040.0,
            close_p=3060.0,
        )
        self.assertTrue(res.is_stopped)
        self.assertFalse(res.is_gap)
        self.assertEqual(res.reason, "intrabar_stop")
        expected_fill = 3090.0 * (1.0 + 0.0010)
        self.assertAlmostEqual(res.fill_price, expected_fill, places=4)

    def test_long_gap_down_stop(self):
        """Long position stopped by gap down at candle open."""
        # Entry 3000.0, stop 3% -> stop price 2910.0
        # Candle gaps open at 2880.0 (< 2910.0)
        res = self.exec_model.check_intrabar_stop(
            pos_direction=1,
            entry_price=3000.0,
            stop_loss_pct=0.03,
            open_p=2880.0,
            high_p=2890.0,
            low_p=2860.0,
            close_p=2870.0,
        )
        self.assertTrue(res.is_stopped)
        self.assertTrue(res.is_gap)
        self.assertEqual(res.reason, "gap_stop")
        expected_fill = 2880.0 * (1.0 - 0.0015)
        self.assertAlmostEqual(res.fill_price, expected_fill, places=4)

    def test_short_gap_up_stop(self):
        """Short position stopped by gap up at candle open."""
        # Entry 3000.0, stop 3% -> stop price 3090.0
        # Candle gaps open at 3120.0 (> 3090.0)
        res = self.exec_model.check_intrabar_stop(
            pos_direction=-1,
            entry_price=3000.0,
            stop_loss_pct=0.03,
            open_p=3120.0,
            high_p=3140.0,
            low_p=3110.0,
            close_p=3130.0,
        )
        self.assertTrue(res.is_stopped)
        self.assertTrue(res.is_gap)
        self.assertEqual(res.reason, "gap_stop")
        expected_fill = 3120.0 * (1.0 + 0.0015)
        self.assertAlmostEqual(res.fill_price, expected_fill, places=4)

    def test_intrabar_stop_overrides_close_bounce(self):
        """Even if candle bounces and closes green above entry, intrabar stop must execute."""
        # Entry 3000, stop 3% (2910). Low dips to 2890, but closes at 3050 (huge rebound)
        res = self.exec_model.check_intrabar_stop(
            pos_direction=1,
            entry_price=3000.0,
            stop_loss_pct=0.03,
            open_p=2980.0,
            high_p=3060.0,
            low_p=2890.0,
            close_p=3050.0,
        )
        self.assertTrue(res.is_stopped)
        self.assertEqual(res.reason, "intrabar_stop")


if __name__ == "__main__":
    unittest.main()
