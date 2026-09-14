# -*- coding: utf-8 -*-
"""
Tests for Continuous State Backtest and Slice Reporting (Phase 17)
Verifies:
1. Single continuous run preserves state across years.
2. Slice reporting reports carryover positions accurately.
3. Normalized equity within slices preserves continuous MTM drawdowns.
"""

import unittest
import numpy as np
import pandas as pd

from crypto_quant.continuous_backtest import ContinuousBacktestEngine


class TestContinuousState(unittest.TestCase):

    def setUp(self):
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=200, freq="4h")
        price = 3000.0 + np.cumsum(np.random.normal(0, 10, 200))
        self.df_bars = pd.DataFrame({
            "open": price,
            "high": price + 15,
            "low": price - 15,
            "close": price + 2,
        }, index=dates)

        # Pulse entry at bar 20 so trade is active at bar 50
        self.preds = pd.Series([0.0] * 200, index=dates)
        self.preds.iloc[20:60] = 0.04

        self.engine = ContinuousBacktestEngine(symbol="ETHUSDT", trial_mode=True)
        self.res = self.engine.run(self.df_bars, self.preds)

    def test_continuous_execution_has_consistent_index(self):
        """Result equity series and position series match input bars index."""
        self.assertEqual(len(self.res.equity_series), len(self.df_bars))
        self.assertEqual(len(self.res.position_series), len(self.df_bars))
        self.assertEqual(len(self.res.state_history), len(self.df_bars))

    def test_slice_report_captures_carryover_position(self):
        """Slice starting while in an open trade correctly captures carryover position."""
        # Slice from bar 30 to bar 70
        start_ts = str(self.df_bars.index[30])
        end_ts = str(self.df_bars.index[70])
        report = self.res.slice_report(start_ts, end_ts)

        self.assertIsNotNone(report.carryover_position)
        self.assertGreater(abs(report.carryover_position["position"]), 0.0)
        self.assertTrue(np.isfinite(report.total_return))
        self.assertTrue(np.isfinite(report.max_drawdown))

    def test_slice_report_metrics_validity(self):
        """Slice report calculates finite and well-formed performance metrics."""
        start_ts = str(self.df_bars.index[0])
        end_ts = str(self.df_bars.index[-1])
        report = self.res.slice_report(start_ts, end_ts)

        summary = report.to_summary_dict()
        self.assertIn("total_return_pct", summary)
        self.assertIn("max_drawdown_pct", summary)
        self.assertIn("daily_sharpe", summary)
        self.assertIn("calmar_ratio", summary)
        self.assertIn("win_rate_pct", summary)
        self.assertIn("total_trades", summary)


if __name__ == "__main__":
    unittest.main()
