# -*- coding: utf-8 -*-
"""
Unit Tests for ETH 3x Leverage Model & Funding Arbitrage Engine
==============================================================
"""

import unittest
from crypto_quant.paper.leverage_model import LeverageModel
from crypto_quant.paper.funding_arb import get_funding_arbitrage_guide, fetch_binance_funding_info


class TestLeverageAndFunding(unittest.TestCase):
    def setUp(self):
        self.leverage_model = LeverageModel(default_leverage=3.0, mmr=0.005)

    def test_3x_liquidation_price_formula(self):
        """Test isolated 3x long liquidation price calculation."""
        entry_price = 2500.0
        # Liq = 2500 * (1 - (1/3) + 0.005) = 2500 * (0.6666667 + 0.005) = 2500 * 0.6716667 = 1679.167
        liq_price = self.leverage_model.calculate_liquidation_price(entry_price, leverage=3.0)
        self.assertAlmostEqual(liq_price, 1679.166666666667, delta=1.0)
        # Distance to liquidation is approx 32.8%
        drop_pct = (entry_price - liq_price) / entry_price
        self.assertAlmostEqual(drop_pct, 0.3283, delta=0.01)

    def test_leverage_metrics_in_position(self):
        """Test full metrics computation when in 3x long position."""
        metrics = self.leverage_model.compute_metrics(
            base_equity_usdt=10000.0,
            entry_price=2500.0,
            current_price=2600.0,
            highest_price=2650.0,
            trailing_stop_price=2530.0,
            atr=40.0,
            is_in_position=True,
            leverage=3.0,
        )
        self.assertEqual(metrics["leverage"], 3.0)
        self.assertEqual(metrics["base_equity_usdt"], 10000.0)
        self.assertEqual(metrics["nominal_position_usdt"], 30000.0)
        self.assertTrue(metrics["is_safe"])
        # Trailing stop at 2530 must be well above liquidation price (~1679)
        self.assertGreater(metrics["trailing_stop_price"], metrics["liquidation_price"])
        self.assertGreater(metrics["safety_buffer_pct"], 25.0)

    def test_funding_info_and_guide(self):
        """Test funding rate info extraction and 4-step guide generation."""
        guide = get_funding_arbitrage_guide(10000.0)
        self.assertEqual(guide["base_capital_usdt"], 10000.0)
        self.assertEqual(guide["half_capital_usdt"], 5000.0)
        self.assertEqual(len(guide["steps"]), 4)
        self.assertIn("funding_info", guide)
        self.assertGreaterEqual(guide["funding_info"]["annualized_apy_pct"], 0.0)


if __name__ == "__main__":
    unittest.main()
