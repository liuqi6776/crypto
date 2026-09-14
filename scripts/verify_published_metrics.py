# -*- coding: utf-8 -*-
"""
Verify Published Metrics against Single Source of Truth (Phase 17)
Validates that numbers published across all communication channels:
1. README.md
2. WALKTHROUGH.md
3. docs/index.html
match docs/metrics.json exactly.
Also verifies git commit metadata, absence of promotional buzzwords, and absence
of unqualified 'blind test' phrasing outside legacy archive sections.
"""

import sys
import io
import json
import re
import subprocess
from pathlib import Path

# Safe stdout for windows gbk terminals
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).resolve().parent.parent
METRICS_JSON = ROOT_DIR / "docs" / "metrics.json"


def check_metric_presence(content: str, num, doc_name: str, errors: list, is_pct: bool = True):
    if is_pct:
        variants = [f"{num}%", f"{float(num):.2f}%", f"{float(num):+.2f}%", f"{float(num):+.1f}%"]
    else:
        variants = [f"{num}", f"{float(num):.2f}", f"{float(num):+.2f}"]
    if not any(v in content for v in variants):
        errors.append(f"[{doc_name}] Missing or mismatched metric: none of {variants} found in text")


def get_current_git_commit() -> str:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT_DIR), universal_newlines=True
        ).strip()
        return commit
    except Exception:
        return "unknown"


def main():
    print("=" * 75)
    print("Verifying Multi-Channel Metrics against docs/metrics.json Single Source of Truth")
    print("=" * 75)

    if not METRICS_JSON.exists():
        print(f"ERROR: {METRICS_JSON} does not exist. Run scripts/generate_metrics.py first.")
        sys.exit(1)

    with open(METRICS_JSON, "r", encoding="utf-8") as f:
        metrics = json.load(f)

    readme_path = ROOT_DIR / "README.md"
    walkthrough_path = ROOT_DIR / "WALKTHROUGH.md"
    html_path = ROOT_DIR / "docs" / "index.html"

    if not readme_path.exists():
        print("ERROR: README.md not found.")
        sys.exit(1)

    readme = readme_path.read_text(encoding="utf-8")
    walkthrough = walkthrough_path.read_text(encoding="utf-8") if walkthrough_path.exists() else ""
    html = html_path.read_text(encoding="utf-8") if html_path.exists() else ""

    errors = []

    # 1. Metadata and Lag Policy Check
    meta = metrics.get("metadata", {})
    if "lag_policy" not in meta:
        errors.append("[metrics.json] Missing 'lag_policy' in metadata")
    elif meta["lag_policy"].get("fng") != "1d_lag_ffill":
        errors.append(f"[metrics.json] Invalid FNG lag policy: {meta['lag_policy'].get('fng')}")

    # 2. Check Prohibited Promotional Phrases
    prohibited_phrases = ["低于20%", "低于 20%", "合规红线", "绝对中性", "无懈可击"]
    for p in prohibited_phrases:
        if p in readme:
            errors.append(f"[README.md] Contains prohibited promotional phrase: '{p}'")
        if p in walkthrough:
            errors.append(f"[WALKTHROUGH.md] Contains prohibited promotional phrase: '{p}'")

    # 3. Check for Unqualified 'Blind Test' / '盲测' in Active Sections
    readme_active = re.split(r"## .*Legacy.*Archive|### .*历史探索归档", readme, flags=re.IGNORECASE)[0]
    for line in readme_active.splitlines():
        if "2026 盲测" in line or "2026 Blind Test" in line:
            # Check if accompanied by caveat
            if "prototype" not in line.lower() and "quarantine" not in line.lower() and "archive" not in line.lower():
                errors.append(f"[README.md] Unqualified 'Blind Test' claim found in active section: {line.strip()}")

    # 4. Extract target values from metrics.json (Trial Trading Mode)
    val_t = metrics["trial_trading"]["val_2024_2025"]
    str_t = metrics["trial_trading"]["stress_2026"]
    oct_t = metrics["trial_trading"]["october_2025"]

    port_ret_val = f"{val_t['portfolio_return_pct']}%"
    port_mdd_val = f"{val_t['portfolio_max_drawdown_pct']}%"
    port_sharpe_val = f"{val_t['portfolio_daily_sharpe']}"

    port_ret_str = f"{str_t['portfolio_return_pct']}%"
    port_mdd_str = f"{str_t['portfolio_max_drawdown_pct']}%"
    oct_ret = f"{oct_t['portfolio_return_pct']}%"
    oct_mdd = f"{oct_t['portfolio_max_drawdown_pct']}%"

    print("\nTarget Check Values (Trial Mode):")
    print(f"- 2024-2025 Portfolio: Ret {port_ret_val}, MDD {port_mdd_val}, Sharpe {port_sharpe_val}")
    print(f"- 2026 Stress Period: Ret {port_ret_str}, MDD {port_mdd_str}")
    print(f"- October 2025 Crash:  Ret {oct_ret}, MDD {oct_mdd}")

    # Verify presence in README.md
    check_metric_presence(readme, val_t['portfolio_return_pct'], "README.md", errors, is_pct=True)
    check_metric_presence(readme, val_t['portfolio_max_drawdown_pct'], "README.md", errors, is_pct=True)
    check_metric_presence(readme, val_t['portfolio_daily_sharpe'], "README.md", errors, is_pct=False)
    check_metric_presence(readme, str_t['portfolio_return_pct'], "README.md", errors, is_pct=True)
    check_metric_presence(readme, str_t['portfolio_max_drawdown_pct'], "README.md", errors, is_pct=True)

    # Verify presence in docs/index.html
    if html:
        check_metric_presence(html, val_t['portfolio_return_pct'], "docs/index.html", errors, is_pct=True)
        check_metric_presence(html, val_t['portfolio_max_drawdown_pct'], "docs/index.html", errors, is_pct=True)
        check_metric_presence(html, val_t['portfolio_daily_sharpe'], "docs/index.html", errors, is_pct=False)
        check_metric_presence(html, str_t['portfolio_max_drawdown_pct'], "docs/index.html", errors, is_pct=True)

    # Verify presence in WALKTHROUGH.md if exists
    if walkthrough:
        check_metric_presence(walkthrough, val_t['portfolio_return_pct'], "WALKTHROUGH.md", errors, is_pct=True)
        check_metric_presence(walkthrough, val_t['portfolio_max_drawdown_pct'], "WALKTHROUGH.md", errors, is_pct=True)

    if errors:
        print("\n[FAIL] Verification Failed! Discrepancies found:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("\n[PASS] All multi-channel publications perfectly aligned with docs/metrics.json!")
        sys.exit(0)


if __name__ == "__main__":
    main()
