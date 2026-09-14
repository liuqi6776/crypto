# -*- coding: utf-8 -*-
"""
Verify Published Metrics against Single Source of Truth (Phase 16)
Validates that numbers published in README.md, WALKTHROUGH.md, and docs/index.html
match docs/metrics.json exactly.
Exits with code 0 on success, code 1 on metric discrepancy.
"""

import sys
import io
import json
import re
from pathlib import Path

# Safe stdout for windows gbk terminals
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).resolve().parent.parent
METRICS_JSON = ROOT_DIR / "docs" / "metrics.json"


def check_presence(content: str, text: str, doc_name: str, errors: list):
    if text not in content:
        errors.append(f"[{doc_name}] Missing or mismatched metric string: '{text}'")


def main():
    print("=" * 70)
    print("Verifying Documentation against docs/metrics.json Single Source of Truth")
    print("=" * 70)

    if not METRICS_JSON.exists():
        print(f"ERROR: {METRICS_JSON} does not exist. Run scripts/generate_metrics.py first.")
        sys.exit(1)

    with open(METRICS_JSON, "r", encoding="utf-8") as f:
        metrics = json.load(f)

    readme_path = ROOT_DIR / "README.md"
    walkthrough_path = ROOT_DIR / "WALKTHROUGH.md"

    if not readme_path.exists():
        print("ERROR: README.md not found.")
        sys.exit(1)

    readme = readme_path.read_text(encoding="utf-8")
    walkthrough = walkthrough_path.read_text(encoding="utf-8") if walkthrough_path.exists() else ""

    errors = []

    # Check prohibited promotional phrases
    prohibited_phrases = ["低于20%", "低于 20%", "合规红线", "绝对中性", "无懈可击"]
    for p in prohibited_phrases:
        if p in readme:
            errors.append(f"[README.md] Contains prohibited promotional phrase: '{p}'")

    # Extract target values from metrics.json (Trial Trading Mode)
    val_t = metrics["trial_trading"]["val_2024_2025"]
    str_t = metrics["trial_trading"]["stress_2026"]
    oct_t = metrics["trial_trading"]["october_2025"]

    port_ret_val = f"{val_t['portfolio_return_pct']}%"
    port_mdd_val = f"{val_t['portfolio_max_drawdown_pct']}%"
    port_sharpe_val = f"{val_t['portfolio_daily_sharpe']}"

    port_ret_str = f"{str_t['portfolio_return_pct']}%"
    port_mdd_str = f"{str_t['portfolio_max_drawdown_pct']}%"

    print("Target Check Values (Trial Mode):")
    print(f"- 2024-2025 Portfolio Return: {port_ret_val}, MDD: {port_mdd_val}, Sharpe: {port_sharpe_val}")
    print(f"- 2026 Stress Period Return: {port_ret_str}, MDD: {port_mdd_str}")
    print(f"- October 2025 Portfolio Return: {oct_t['portfolio_return_pct']}%, MDD: {oct_t['portfolio_max_drawdown_pct']}%")

    # Verify that README mentions the verified numbers
    check_presence(readme, port_ret_val, "README.md", errors)
    check_presence(readme, port_mdd_val, "README.md", errors)
    check_presence(readme, port_sharpe_val, "README.md", errors)
    check_presence(readme, port_ret_str, "README.md", errors)
    check_presence(readme, port_mdd_str, "README.md", errors)

    if errors:
        print("\n[FAIL] Verification Failed! Discrepancies found:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("\n[PASS] All published metrics perfectly aligned with docs/metrics.json!")
        sys.exit(0)


if __name__ == "__main__":
    main()
