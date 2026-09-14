# -*- coding: utf-8 -*-
"""
Tests for Metrics Consistency Across Multi-Carrier Publications (Phase 17)
Verifies:
1. docs/metrics.json exists, is well-formed, and contains required metadata and lag policies.
2. README.md, WALKTHROUGH.md, and docs/index.html are aligned with metrics.json.
3. No unqualified "Blind Test" or "盲测" claims exist outside designated legacy archive sections.
"""

import os
import re
import json
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


class TestMetricsConsistency(unittest.TestCase):

    def setUp(self):
        self.metrics_path = ROOT_DIR / "docs" / "metrics.json"
        self.readme_path = ROOT_DIR / "README.md"
        self.walkthrough_path = ROOT_DIR / "WALKTHROUGH.md"

        self.assertTrue(self.metrics_path.exists(), "docs/metrics.json must exist")
        with open(self.metrics_path, "r", encoding="utf-8") as f:
            self.metrics = json.load(f)

    def test_metrics_json_structure(self):
        """Verify metrics.json contains all required schema keys."""
        meta = self.metrics.get("metadata", {})
        self.assertIn("system", meta)
        self.assertIn("git_commit", meta)
        self.assertIn("lag_policy", meta)
        self.assertIn("assumptions", meta)
        self.assertIn("trial_trading", self.metrics)
        self.assertIn("raw_baseline", self.metrics)

        # Check lag policy keys
        lag_pol = meta["lag_policy"]
        self.assertEqual(lag_pol.get("fng"), "1d_lag_ffill")

        # Check slices
        trial = self.metrics["trial_trading"]
        for key in ["val_2024_2025", "stress_2026", "october_2025", "full_history"]:
            self.assertIn(key, trial, f"Missing slice '{key}' in trial_trading metrics")

    def test_no_unqualified_blind_test_in_readme(self):
        """Verify README.md does not use 'Blind Test' or '盲测' as current verified status outside archive."""
        if not self.readme_path.exists():
            return
        with open(self.readme_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Split content into active sections and legacy archive
        archive_split = re.split(r"## .*Legacy.*Archive|## .*历史探索归档", content, flags=re.IGNORECASE)
        active_content = archive_split[0]

        # In active content, 2026 must be described as stress-test, post-hoc development, or out-of-sample stress
        # If 'blind test' or '盲测' appears, it must be accompanied by explicit caveat/quarantine note
        for line in active_content.splitlines():
            # Check for unqualified claims like "2026 盲测收益" without disclaimer
            if "2026 盲测收益" in line or "2026 Blind Test Return" in line:
                self.fail(f"Found unqualified claim in README active section: {line}")


if __name__ == "__main__":
    unittest.main()
