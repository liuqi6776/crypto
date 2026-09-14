# -*- coding: utf-8 -*-
"""
Tests for Feature Availability and Point-in-Time Integrity (Phase 17)
Verifies:
1. Daily features aligned to 4h bars strictly lag by 1 day.
2. At 00:00:00 on day D, features from day D are not accessible (only day D-1).
3. Canonical lag policy dictionary is returned as defined.
"""

import unittest
import pandas as pd
import numpy as np

from crypto_quant.data_aligner import align_daily_features_to_4h, get_lag_policy


class TestFeatureAvailability(unittest.TestCase):

    def test_daily_lag_policy_constants(self):
        """Verify the immutable lag policy dictionary."""
        policy = get_lag_policy()
        self.assertEqual(policy.get("fng"), "1d_lag_ffill")
        self.assertEqual(policy.get("macro"), "1d_lag_ffill")
        self.assertEqual(policy.get("onchain"), "1d_lag_ffill")

    def test_daily_feature_strictly_unavailable_on_same_day(self):
        """Data labeled day D is not knowable on day D 00:00:00 UTC, only starting day D+1."""
        daily_dates = pd.date_range("2024-01-01", periods=5, freq="1D")
        daily_fng = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0], index=daily_dates, name="fng")

        target_4h = pd.date_range("2024-01-01 00:00:00", "2024-01-04 20:00:00", freq="4h")
        aligned = align_daily_features_to_4h(daily_fng, target_4h, lag_days=1)

        # On 2024-01-01 all bars should be NaN (no prior day available)
        day1_bars = aligned.loc["2024-01-01"]
        self.assertTrue(day1_bars.isna().all(), "Day 1 must not know Day 1's values")

        # On 2024-01-02 (all 6 4h bars: 00:00 to 20:00), value must strictly equal 10.0 (Day 1's value)
        day2_bars = aligned.loc["2024-01-02"]
        self.assertTrue((day2_bars == 10.0).all(), "Day 2 must read Day 1's value (10.0)")

        # On 2024-01-03, value must strictly equal 20.0 (Day 2's value)
        day3_bars = aligned.loc["2024-01-03"]
        self.assertTrue((day3_bars == 20.0).all(), "Day 3 must read Day 2's value (20.0)")


if __name__ == "__main__":
    unittest.main()
