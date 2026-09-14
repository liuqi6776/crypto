# -*- coding: utf-8 -*-
"""
Unit tests for Latency Penalty Model (Phase 18 P0 Enhancement)
Verifies:
1. Latency penalty shifts fill price higher on buys and lower on sells.
2. Monotonicity: 5 bps latency creates greater adverse selection than 2 bps.
3. Zero latency penalty matches standard normal slippage exactly.
4. End-to-end continuous engine applies latency penalty to executed trades.
"""

import unittest
import pandas as pd
import numpy as np

from crypto_quant.execution_model import ExecutionModel
from crypto_quant.continuous_backtest import ContinuousBacktestEngine


class TestLatencyModel(unittest.TestCase):
    def test_latency_penalty_shifts_fill_price(self):
        em_base = ExecutionModel(normal_slippage=0.0004, latency_penalty=0.0)
        em_latent = ExecutionModel(normal_slippage=0.0004, latency_penalty=0.0002)

        p = 1000.0
        # Long fill price should be higher with latency penalty
        buy_base = em_base.get_fill_price(p, side=1)
        buy_latent = em_latent.get_fill_price(p, side=1)
        self.assertAlmostEqual(buy_base, 1000.4, places=4)
        self.assertAlmostEqual(buy_latent, 1000.6, places=4)
        self.assertGreater(buy_latent, buy_base)

        # Short fill price should be lower with latency penalty
        sell_base = em_base.get_fill_price(p, side=-1)
        sell_latent = em_latent.get_fill_price(p, side=-1)
        self.assertAlmostEqual(sell_base, 999.6, places=4)
        self.assertAlmostEqual(sell_latent, 999.4, places=4)
        self.assertLess(sell_latent, sell_base)

    def test_monotonicity_of_latency_stress(self):
        p = 2000.0
        em_0 = ExecutionModel(normal_slippage=0.0004, latency_penalty=0.0)
        em_2 = ExecutionModel(normal_slippage=0.0004, latency_penalty=0.0002)
        em_5 = ExecutionModel(normal_slippage=0.0004, latency_penalty=0.0005)

        fill_0 = em_0.get_fill_price(p, side=1)
        fill_2 = em_2.get_fill_price(p, side=1)
        fill_5 = em_5.get_fill_price(p, side=1)

        self.assertLess(fill_0, fill_2)
        self.assertLess(fill_2, fill_5)

    def test_continuous_engine_latency_impact(self):
        # Create bars that produce a clean trade
        dates = pd.date_range("2024-01-01", periods=60, freq="4h", tz="UTC")
        prices = [100.0 + i * 0.5 for i in range(60)]
        df_bars = pd.DataFrame(
            {
                "open": prices,
                "high": [p + 1.0 for p in prices],
                "low": [p - 1.0 for p in prices],
                "close": prices,
            },
            index=dates,
        )
        preds = pd.Series(0.5, index=dates)
        preds.iloc[15] = 0.95  # Enter long
        preds.iloc[35] = -0.95  # Exit

        engine_0 = ContinuousBacktestEngine(symbol="TEST", latency_penalty=0.0)
        res_0 = engine_0.run(df_bars, preds)

        engine_5 = ContinuousBacktestEngine(symbol="TEST", latency_penalty=0.0005)
        res_5 = engine_5.run(df_bars, preds)

        self.assertEqual(len(res_0.trades), len(res_5.trades))
        if len(res_0.trades) > 0:
            # Latency penalty must reduce net return of the trade
            self.assertGreater(res_0.trades[0].net_return, res_5.trades[0].net_return)


if __name__ == "__main__":
    unittest.main()
