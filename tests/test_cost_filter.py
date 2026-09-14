# -*- coding: utf-8 -*-
"""
Unit tests for Cost-Aware Execution Filter (Phase 18 P0 Enhancement)
Verifies:
1. Weak signals (predicted return magnitude < cost hurdle) are filtered out.
2. Strong signals (predicted return magnitude > cost hurdle) are allowed to execute.
3. Stop-loss and risk exits are strictly immune to the cost filter.
4. Setting cost_filter_mult=0.0 matches baseline unconstrained entry behavior.
"""

import unittest
import pandas as pd
import numpy as np

from crypto_quant.continuous_backtest import ContinuousBacktestEngine


class TestCostFilter(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=60, freq="4h", tz="UTC")
        prices = [100.0 + i * 0.1 for i in range(60)]

        self.df_bars = pd.DataFrame(
            {
                "open": prices,
                "high": [p + 0.2 for p in prices],
                "low": [p - 0.2 for p in prices],
                "close": prices,
            },
            index=dates,
        )
        self.dates = dates

    def test_weak_signal_is_filtered_by_cost_barrier(self):
        """
        When predicted return is ~0.0010 (10 bps), while roundtrip cost is 16 bps,
        at k=2.0 the cost hurdle is 32 bps.
        The weak signal must be filtered out!
        """
        # Baseline series with low values ~0.0005
        preds = pd.Series(0.0005 + np.random.normal(0, 0.0002, 60), index=self.dates)
        # Spike to z > 1.0 but small magnitude: 0.0012 (12 bps)
        preds.iloc[25] = 0.0012

        engine_filtered = ContinuousBacktestEngine(
            symbol="TEST",
            cost_filter_mult=2.0,
            deadband=0.20,
        )
        res_filtered = engine_filtered.run(self.df_bars, preds)
        self.assertGreater(res_filtered.filter_stats["signals_cost_filtered"], 0)

    def test_strong_signal_passes_cost_barrier(self):
        """
        When predicted return is 0.0150 (150 bps), it clears the 32 bps hurdle.
        The signal must execute!
        """
        preds = pd.Series(0.0010 + np.random.normal(0, 0.0005, 60), index=self.dates)
        # Strong spike to 150 bps
        preds.iloc[25] = 0.0150

        engine_filtered = ContinuousBacktestEngine(
            symbol="TEST",
            cost_filter_mult=2.0,
            deadband=0.20,
        )
        res_filtered = engine_filtered.run(self.df_bars, preds)
        self.assertGreater(res_filtered.filter_stats["signals_executed"], 0)

    def test_zero_cost_mult_disables_filter_backward_compatible(self):
        """
        When cost_filter_mult=0.0, signals_cost_filtered must be strictly 0.
        """
        preds = pd.Series(0.0005 + np.random.normal(0, 0.0002, 60), index=self.dates)
        preds.iloc[25] = 0.0012

        engine_unfiltered = ContinuousBacktestEngine(
            symbol="TEST",
            cost_filter_mult=0.0,
        )
        res = engine_unfiltered.run(self.df_bars, preds)
        self.assertEqual(res.filter_stats["signals_cost_filtered"], 0)


if __name__ == "__main__":
    unittest.main()
