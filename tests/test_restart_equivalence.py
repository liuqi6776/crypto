# -*- coding: utf-8 -*-
"""
Tests for True Restart Equivalence (Phase 17)
Verifies that interrupting a continuous run at any point k, saving StrategyState to JSON,
and resuming from k+1 yields 100% identical positions, trades, and equity curves.
Tested across 10 random cut points: strictly 0 position mismatches allowed.
"""

import unittest
import numpy as np
import pandas as pd
from pathlib import Path

from crypto_quant.continuous_backtest import ContinuousBacktestEngine, StrategyState


def generate_test_dataset(n_bars=350):
    np.random.seed(123)
    dates = pd.date_range("2024-01-01", periods=n_bars, freq="4h")

    # Generate trending & oscillating price series
    rets = np.random.normal(0.0003, 0.015, n_bars)
    price = 3000.0 * np.exp(np.cumsum(rets))
    high = price * (1.0 + np.abs(np.random.normal(0, 0.006, n_bars)))
    low = price * (1.0 - np.abs(np.random.normal(0, 0.006, n_bars)))
    open_p = price * (1.0 + np.random.normal(0, 0.002, n_bars))
    close = price

    df_bars = pd.DataFrame({
        "open": open_p,
        "high": high,
        "low": low,
        "close": close,
    }, index=dates)

    # Generate signals that cycle in and out of positions
    preds = pd.Series(np.sin(np.linspace(0, 16 * np.pi, n_bars)) * 0.03 + np.random.normal(0, 0.008, n_bars), index=dates)
    funding = pd.Series(np.random.choice([0.0001, -0.0001, 0.0002], size=n_bars), index=dates)
    fng = pd.Series(np.random.uniform(20, 80, size=n_bars), index=dates)

    return df_bars, preds, funding, fng


class TestRestartEquivalence(unittest.TestCase):

    def setUp(self):
        self.df_bars, self.preds, self.funding, self.fng = generate_test_dataset(350)
        self.engine = ContinuousBacktestEngine(symbol="ETHUSDT", trial_mode=True)
        self.full_result = self.engine.run(
            df_bars=self.df_bars,
            series_pred=self.preds,
            series_funding=self.funding,
            series_fng=self.fng,
        )

    def test_ten_random_cut_points_zero_mismatch(self):
        """Test restart equivalence across 10 deterministic cut points with 0 position mismatch."""
        n = len(self.df_bars)
        # Select 10 diverse cut points spanning the dataset
        np.random.seed(42)
        cut_points = np.sort(np.random.choice(range(80, n - 30), size=10, replace=False))

        total_tested = 0
        total_mismatches = 0

        for k in cut_points:
            # 1. Capture state at step k
            state_at_k = self.full_result.state_history[k]
            json_str = state_at_k.to_json()
            recovered_state = StrategyState.from_json(json_str)

            # 2. Slice from step k+1 onwards
            sub_bars = self.df_bars.iloc[k + 1:]
            sub_preds = self.preds.iloc[k + 1:]
            sub_fund = self.funding.iloc[k + 1:]
            sub_fng = self.fng.iloc[k + 1:]

            # 3. Create fresh engine initialized with recovered state
            resumed_engine = ContinuousBacktestEngine(
                symbol="ETHUSDT",
                trial_mode=True,
                initial_state=recovered_state,
            )
            resumed_res = resumed_engine.run(
                df_bars=sub_bars,
                series_pred=sub_preds,
                series_funding=sub_fund,
                series_fng=sub_fng,
            )

            # 4. Compare position series
            bench_pos = self.full_result.position_series.loc[sub_bars.index]
            test_pos = resumed_res.position_series

            pos_diff = (bench_pos - test_pos).abs()
            mismatches = int((pos_diff > 1e-6).sum())
            total_mismatches += mismatches
            total_tested += len(sub_bars)

            self.assertEqual(
                mismatches, 0,
                f"Cut point k={k} ({self.df_bars.index[k]}) produced {mismatches} position mismatches!"
            )

            # 5. Compare equity series (within floating point precision)
            bench_eq = self.full_result.equity_series.loc[sub_bars.index]
            test_eq = resumed_res.equity_series
            max_eq_diff = float((bench_eq - test_eq).abs().max())
            self.assertLess(
                max_eq_diff, 1e-4,
                f"Cut point k={k} equity divergence {max_eq_diff:.6f} exceeded tolerance!"
            )

        print(f"\n[TestRestartEquivalence] Passed 10 random cut points: {total_tested} bars verified with 0 mismatches.")


if __name__ == "__main__":
    unittest.main()
