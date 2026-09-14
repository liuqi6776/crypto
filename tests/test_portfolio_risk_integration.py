# -*- coding: utf-8 -*-
"""
Tests for Portfolio Risk Manager Integration (Phase 17)
Verifies that PortfolioRiskManager is actively wired into the MultiAssetPortfolioEngine:
1. Fault injection: ensures custom/mock risk manager is called on every bar.
2. Portfolio drawdown协同 throttles both ETH and SOL positions.
3. Max gross leverage (<= 1.50) is strictly enforced.
4. Max net leverage (<= 1.00) is strictly enforced.
"""

import unittest
from unittest.mock import MagicMock
from pathlib import Path
import numpy as np
import pandas as pd

from crypto_quant.portfolio import MultiAssetPortfolioEngine
from crypto_quant.risk_manager import PortfolioRiskManager, PortfolioState


def create_synthetic_market_data(n_bars=100):
    dates = pd.date_range("2024-01-01", periods=n_bars, freq="4h")
    df_eth = pd.DataFrame({
        "open": [3000.0 + i * 2 for i in range(n_bars)],
        "high": [3020.0 + i * 2 for i in range(n_bars)],
        "low": [2990.0 + i * 2 for i in range(n_bars)],
        "close": [3010.0 + i * 2 for i in range(n_bars)],
    }, index=dates)

    df_sol = pd.DataFrame({
        "open": [100.0 + i * 0.5 for i in range(n_bars)],
        "high": [102.0 + i * 0.5 for i in range(n_bars)],
        "low": [99.0 + i * 0.5 for i in range(n_bars)],
        "close": [101.0 + i * 0.5 for i in range(n_bars)],
    }, index=dates)

    pred_eth = pd.Series([0.0] * n_bars, index=dates)
    pred_sol = pd.Series([0.0] * n_bars, index=dates)
    # Trigger strong long signals at bar 20
    pred_eth.iloc[20:30] = 0.05
    pred_sol.iloc[20:30] = 0.05

    mkt_dict = {"ETHUSDT": df_eth, "SOLUSDT": df_sol}
    pred_dict = {"ETHUSDT": pred_eth, "SOLUSDT": pred_sol}
    return mkt_dict, pred_dict, dates


class TestPortfolioRiskIntegration(unittest.TestCase):

    def test_custom_risk_manager_is_called_every_bar(self):
        """Fault injection test: verify PortfolioRiskManager.update_portfolio_state is called every bar."""
        mkt_dict, pred_dict, dates = create_synthetic_market_data(60)

        class CountingRiskManager(PortfolioRiskManager):
            def __init__(self):
                super().__init__()
                self.call_count = 0

            def update_portfolio_state(self, current_state, timestamp, mark_prices):
                self.call_count += 1
                return super().update_portfolio_state(current_state, timestamp, mark_prices)

        custom_rm = CountingRiskManager()
        engine = MultiAssetPortfolioEngine(risk_manager=custom_rm, trial_mode=False)
        res = engine.run(mkt_dict, pred_dict)

        self.assertEqual(custom_rm.call_count, len(dates),
                         f"Expected {len(dates)} risk manager calls, got {custom_rm.call_count}")

    def test_portfolio_drawdown_reduces_all_asset_positions(self):
        """Verify that deep portfolio drawdown reduces position sizing across all assets."""
        mkt_dict, pred_dict, dates = create_synthetic_market_data(60)

        # Baseline engine with normal risk manager
        rm_normal = PortfolioRiskManager()
        engine_normal = MultiAssetPortfolioEngine(risk_manager=rm_normal, trial_mode=True)
        res_normal = engine_normal.run(mkt_dict, pred_dict)

        # Stressed risk manager that forces severe drawdown multiplier
        class StressedRiskManager(PortfolioRiskManager):
            def compute_portfolio_drawdown_multiplier(self, portfolio_dd: float) -> float:
                return 0.25  # Force emergency drawdown throttle

        rm_stressed = StressedRiskManager()
        engine_stressed = MultiAssetPortfolioEngine(risk_manager=rm_stressed, trial_mode=True)
        res_stressed = engine_stressed.run(mkt_dict, pred_dict)

        # Compare entered position sizes
        eth_pos_normal = res_normal.asset_results["ETHUSDT"].position_series.abs().max()
        eth_pos_stressed = res_stressed.asset_results["ETHUSDT"].position_series.abs().max()
        sol_pos_normal = res_normal.asset_results["SOLUSDT"].position_series.abs().max()
        sol_pos_stressed = res_stressed.asset_results["SOLUSDT"].position_series.abs().max()

        self.assertGreater(eth_pos_normal, eth_pos_stressed,
                           "ETH position size should be reduced under portfolio drawdown stress")
        self.assertGreater(sol_pos_normal, sol_pos_stressed,
                           "SOL position size should be reduced under portfolio drawdown stress")

    def test_max_gross_leverage_is_enforced(self):
        """Verify that total gross leverage across all assets never exceeds max_gross_leverage."""
        mkt_dict, pred_dict, dates = create_synthetic_market_data(80)

        custom_rm = PortfolioRiskManager(max_gross_leverage=0.80)
        engine = MultiAssetPortfolioEngine(risk_manager=custom_rm, trial_mode=False)
        res = engine.run(mkt_dict, pred_dict)

        eth_pos = res.asset_results["ETHUSDT"].position_series.abs()
        sol_pos = res.asset_results["SOLUSDT"].position_series.abs()
        total_gross = eth_pos + sol_pos

        max_gross = total_gross.max()
        self.assertLessEqual(max_gross, 0.80 + 1e-6,
                             f"Total gross leverage {max_gross} exceeded limit 0.80")

    def test_max_net_leverage_is_enforced(self):
        """Verify that total net leverage across all assets never exceeds max_net_leverage."""
        mkt_dict, pred_dict, dates = create_synthetic_market_data(80)

        custom_rm = PortfolioRiskManager(max_net_leverage=0.50)
        engine = MultiAssetPortfolioEngine(risk_manager=custom_rm, trial_mode=False)
        res = engine.run(mkt_dict, pred_dict)

        eth_pos = res.asset_results["ETHUSDT"].position_series
        sol_pos = res.asset_results["SOLUSDT"].position_series
        total_net = (eth_pos + sol_pos).abs()

        max_net = total_net.max()
        self.assertLessEqual(max_net, 0.50 + 1e-6,
                             f"Total net leverage {max_net} exceeded limit 0.50")


if __name__ == "__main__":
    unittest.main()
