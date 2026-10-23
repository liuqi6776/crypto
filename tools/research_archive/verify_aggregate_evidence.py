#!/usr/bin/env python3
"""Check arithmetic and documented row coverage in the curated aggregate archive.

This verifies aggregate-file consistency only. It does not evaluate strategies or
make trading claims. All paths are relative to the supplied archive directory.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

TOLERANCE = 1e-7
INPUTS = {
    "performance": "evidence/recent/langlang_fixed/outputs/v3/performance.csv",
    "independent_ledger": "evidence/recent/langlang_fixed/INDEPENDENT_LEDGER_V3.json",
    "event_metrics": "evidence/recent/funding_switch/btc_funding_switch_study/event_metrics.csv",
    "small_cap_metrics": "evidence/recent/small_cap_game/root_review_run_v1/strategy_metrics.csv",
    "human_protection_metrics": "evidence/recent/human_protection/algorithm_metrics.csv",
}


def _read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError("CSV header missing")
        rows = list(reader)
        return rows, list(reader.fieldnames)


def _number(row: dict[str, str], field: str) -> float:
    raw = row.get(field, "")
    if raw is None or not raw.strip():
        raise ValueError(f"missing numeric field {field}")
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError(f"non-finite numeric field {field}")
    return value


def _integer(row: dict[str, str], field: str) -> int:
    value = _number(row, field)
    if not value.is_integer():
        raise ValueError(f"non-integer count field {field}")
    return int(value)


def _check(name: str, passed: bool, *, observed: Any = None, expected: Any = None,
           tolerance: float | None = None, errors: list[str] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"name": name, "passed": bool(passed)}
    if observed is not None:
        result["observed"] = observed
    if expected is not None:
        result["expected"] = expected
    if tolerance is not None:
        result["tolerance"] = tolerance
    if errors:
        result["errors"] = errors
    return result


def _dataset(name: str, path: str) -> dict[str, Any]:
    return {"dataset": name, "path": path, "status": "PASS", "checks": [], "errors": []}


def _finish(record: dict[str, Any]) -> dict[str, Any]:
    if record["errors"] or any(not check["passed"] for check in record["checks"]):
        record["status"] = "FAIL"
    return record


def verify_performance(archive: Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    rel = INPUTS["performance"]
    record = _dataset("performance", rel)
    path = archive / Path(rel)
    try:
        raw = path.read_bytes()
        rows, fields = _read_csv(path)
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        record["errors"].append(f"input unavailable or invalid: {type(exc).__name__}")
        return _finish(record), None
    record["rows"] = len(rows)
    identities = [row.get("scenario_id", "") for row in rows]
    nonempty_unique = all(identities) and len(set(identities)) == len(identities)
    record["checks"].append(_check("unique_scenario_id", nonempty_unique,
                                    observed={"nonempty": sum(bool(v) for v in identities), "unique": len(set(identities))},
                                    expected="one nonempty unique scenario_id per row"))
    record["checks"].append(_check("documented_row_count", len(rows) == 36,
                                    observed=len(rows), expected=36))
    missing = sorted({field for field in ("strategy_group", "total_return_fraction", "gross_pnl_usdt", "fees_usdt",
                                           "slippage_usdt", "funding_usdt", "net_trade_pnl_usdt",
                                           "initial_equity_usdt", "final_equity_usdt", "total_return_fraction") if field not in fields})
    if missing:
        record["errors"].append("required columns missing: " + ", ".join(missing))
        return _finish(record), None
    core = [row for row in rows if row.get("strategy_group", "").startswith(("A_", "B_"))]
    negative = 0
    net_identity_errors: list[str] = []
    equity_identity_errors: list[str] = []
    max_net_residual = 0.0
    max_equity_residual = 0.0
    for row in rows:
        row_id = row.get("scenario_id") or "<empty>"
        try:
            gross = _number(row, "gross_pnl_usdt")
            fees = _number(row, "fees_usdt")
            slip = _number(row, "slippage_usdt")
            funding = _number(row, "funding_usdt")
            net = _number(row, "net_trade_pnl_usdt")
            initial = _number(row, "initial_equity_usdt")
            final = _number(row, "final_equity_usdt")
            net_residual = abs((gross - fees - slip + funding) - net)
            equity_residual = abs((final - initial) - net)
            max_net_residual = max(max_net_residual, net_residual)
            max_equity_residual = max(max_equity_residual, equity_residual)
            if net_residual > TOLERANCE:
                net_identity_errors.append(row_id)
            if equity_residual > TOLERANCE:
                equity_identity_errors.append(row_id)
            if row in core:
                if _number(row, "total_return_fraction") < 0:
                    negative += 1
        except ValueError as exc:
            record["errors"].append(f"{row_id}: {exc}")
    record["core_rows"] = len(core)
    record["checks"].append(_check("documented_core_scope", len(core) == 24,
                                    observed=len(core), expected=24))
    record["checks"].append(_check("core_negative_total_return", len(core) == 24 and negative == len(core),
                                    observed={"core_rows": len(core), "negative_rows": negative}, expected="all core rows < 0"))
    record["checks"].append(_check("net_trade_pnl_identity", not net_identity_errors,
                                    observed={"mismatches": len(net_identity_errors), "max_abs_residual": max_net_residual}, expected=0,
                                    tolerance=TOLERANCE, errors=net_identity_errors[:25]))
    record["checks"].append(_check("equity_change_identity", not equity_identity_errors,
                                    observed={"mismatches": len(equity_identity_errors), "max_abs_residual": max_equity_residual}, expected=0,
                                    tolerance=TOLERANCE, errors=equity_identity_errors[:25]))
    ledger_record = verify_ledger(archive, raw, identities)
    return _finish(record), ledger_record


def verify_ledger(archive: Path, performance_raw: bytes | None, scenario_ids: list[str]) -> dict[str, Any]:
    rel = INPUTS["independent_ledger"]
    record = _dataset("independent_ledger", rel)
    try:
        obj = json.loads((archive / Path(rel)).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        record["errors"].append(f"input unavailable or invalid: {type(exc).__name__}")
        return _finish(record)
    if not isinstance(obj, dict):
        record["errors"].append("JSON root must be an object")
        return _finish(record)
    status = obj.get("status")
    count = obj.get("scenario_count")
    record["checks"].append(_check("ledger_status", status == "VERIFIED_LEDGER", observed=status, expected="VERIFIED_LEDGER"))
    record["checks"].append(_check("ledger_scenario_count", count == 36, observed=count, expected=36))
    ledger_ids = obj.get("scenario_ids")
    ids_match = isinstance(ledger_ids, list) and len(ledger_ids) == len(scenario_ids) and set(ledger_ids) == set(scenario_ids)
    record["checks"].append(_check("ledger_scenario_ids_match_performance", ids_match,
                                    observed=len(ledger_ids) if isinstance(ledger_ids, list) else None,
                                    expected="same scenario_id set as performance.csv"))
    digest = hashlib.sha256(performance_raw).hexdigest() if performance_raw is not None else None
    hash_match = digest is not None and obj.get("performance_sha256") == digest
    record["checks"].append(_check("ledger_performance_hash", hash_match,
                                    observed="match" if hash_match else ("unavailable" if digest is None else "mismatch"), expected="match"))
    return _finish(record)


def verify_event_metrics(archive: Path) -> dict[str, Any]:
    rel = INPUTS["event_metrics"]
    record = _dataset("event_metrics", rel)
    try:
        rows, fields = _read_csv(archive / Path(rel))
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        record["errors"].append(f"input unavailable or invalid: {type(exc).__name__}")
        return _finish(record)
    record["rows"] = len(rows)
    required = ("period", "model", "direction", "true_events", "predicted_alerts", "TP", "FP", "FN", "TN", "eligible_decisions")
    missing = [field for field in required if field not in fields]
    if missing:
        record["errors"].append("required columns missing: " + ", ".join(missing))
        return _finish(record)
    selected = [row for row in rows if row.get("period") == "eval_2024_2025" and row.get("model") == "logistic"]
    directions = [row.get("direction", "") for row in selected]
    row_ids = [f"{r.get('period')}|{r.get('model')}|{r.get('direction')}" for r in selected]
    record["checks"].append(_check("logistic_eval_direction_rows", len(selected) == 2 and set(directions) == {"positive", "negative"} and len(set(directions)) == len(directions),
                                    observed={"rows": len(selected), "directions": sorted(directions)}, expected=["negative", "positive"]))
    identity_errors: list[str] = []
    observations = []
    for row, row_id in zip(selected, row_ids):
        try:
            true_events = _integer(row, "true_events")
            predicted = _integer(row, "predicted_alerts")
            tp, fp, fn, tn = (_integer(row, key) for key in ("TP", "FP", "FN", "TN"))
            eligible = _integer(row, "eligible_decisions")
            if tp + fp != predicted or tp + fn != true_events or tp + fp + fn + tn != eligible:
                identity_errors.append(row_id)
            observations.append({"direction": row.get("direction"), "TP": tp, "FP": fp, "FN": fn})
        except ValueError as exc:
            identity_errors.append(f"{row_id}: {exc}")
    record["observed_counts"] = observations
    record["checks"].append(_check("directional_confusion_count_identities", not identity_errors,
                                    observed={"mismatches": len(identity_errors)}, expected=0, errors=identity_errors[:25]))
    return _finish(record)


def verify_small_cap(archive: Path) -> dict[str, Any]:
    rel = INPUTS["small_cap_metrics"]
    record = _dataset("small_cap_metrics", rel)
    try:
        rows, fields = _read_csv(archive / Path(rel))
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        record["errors"].append(f"input unavailable or invalid: {type(exc).__name__}")
        return _finish(record)
    record["rows"] = len(rows)
    identity_fields = ("version", "scenario", "period_type", "period")
    required = identity_fields + ("gross_before_cost_usdt", "fees_usdt", "slippage_usdt", "net_fee_only_usdt")
    missing = [field for field in required if field not in fields]
    if missing:
        record["errors"].append("required columns missing: " + ", ".join(missing))
        return _finish(record)
    keys = [tuple(row.get(field, "") for field in identity_fields) for row in rows]
    unique = all(all(key) for key in keys) and len(set(keys)) == len(keys)
    record["checks"].append(_check("unique_metric_identity", unique, observed={"unique": len(set(keys))}, expected="one unique row key per row"))
    record["checks"].append(_check("documented_row_count", len(rows) == 4, observed=len(rows), expected=4))
    mismatches = []
    max_residual = 0.0
    for row, key in zip(rows, keys):
        try:
            expected_net = (_number(row, "gross_before_cost_usdt") - _number(row, "fees_usdt") - _number(row, "slippage_usdt"))
            residual = abs(expected_net - _number(row, "net_fee_only_usdt"))
            max_residual = max(max_residual, residual)
            if residual > TOLERANCE:
                mismatches.append("|".join(key))
        except ValueError as exc:
            mismatches.append(f"{'|'.join(key)}: {exc}")
    record["checks"].append(_check("fee_only_cost_identity", not mismatches,
                                    observed={"mismatches": len(mismatches), "max_abs_residual": max_residual}, expected=0,
                                    tolerance=TOLERANCE, errors=mismatches[:25]))
    return _finish(record)


def verify_human_protection(archive: Path) -> dict[str, Any]:
    rel = INPUTS["human_protection_metrics"]
    record = _dataset("human_protection_metrics", rel)
    try:
        rows, fields = _read_csv(archive / Path(rel))
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        record["errors"].append(f"input unavailable or invalid: {type(exc).__name__}")
        return _finish(record)
    record["rows"] = len(rows)
    required = ("cohort", "variant", "trade_count", "full_net_expectancy")
    missing = [field for field in required if field not in fields]
    if missing:
        record["errors"].append("required columns missing: " + ", ".join(missing))
        return _finish(record)
    keys = [(r.get("cohort", ""), r.get("variant", "")) for r in rows]
    unique = all(all(key) for key in keys) and len(set(keys)) == len(keys)
    record["checks"].append(_check("unique_metric_identity", unique, observed={"unique": len(set(keys))}, expected="one cohort/variant row"))
    record["checks"].append(_check("documented_row_count", len(rows) == 6, observed=len(rows), expected=6))
    state_rows = [row for row in rows if row.get("cohort") == "state_filtered"]
    state_counts = []
    count_errors = []
    for row in state_rows:
        try:
            state_counts.append(_integer(row, "trade_count"))
        except ValueError as exc:
            count_errors.append(str(exc))
    record["checks"].append(_check("state_filtered_variant_scope", len(state_rows) == 4 and len(state_counts) == 4 and all(v == 25 for v in state_counts),
                                    observed={"rows": len(state_rows), "trade_counts": state_counts}, expected={"rows": 4, "trade_count_each": 25}, errors=count_errors))
    blank_expectancy = all(not (row.get("full_net_expectancy") or "").strip() for row in rows)
    record["checks"].append(_check("funding_full_net_expectancy_unavailable", blank_expectancy,
                                    observed={"blank_rows": sum(not (r.get("full_net_expectancy") or "").strip() for r in rows), "rows": len(rows)},
                                    expected="field blank for all aggregate rows"))
    return _finish(record)


def verify_archive(archive_dir: str | os.PathLike[str]) -> dict[str, Any]:
    archive = Path(archive_dir)
    performance, ledger = verify_performance(archive)
    checks = [performance]
    checks.append(ledger if ledger is not None else verify_ledger(archive, None, []))
    checks.extend((verify_event_metrics(archive), verify_small_cap(archive), verify_human_protection(archive)))
    failed = [record["dataset"] for record in checks if record["status"] != "PASS"]
    return {
        "schema_version": 1,
        "scope": "Aggregate-file arithmetic, identifiers, and documented row coverage only; no strategy assessment or trading claim.",
        "tolerance": TOLERANCE,
        "status": "FAIL" if failed else "PASS",
        "datasets": checks,
        "failed_datasets": failed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive_dir", help="research_archive directory containing evidence/")
    parser.add_argument("--output", help="write the JSON verification summary to this path")
    args = parser.parse_args(argv)
    summary = verify_archive(args.archive_dir)
    summary_json = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(summary_json, encoding="utf-8")
        except OSError:
            print("aggregate verification summary could not be written", file=sys.stderr)
            return 2
        print(f"aggregate evidence verification: {summary['status']} ({len(summary['datasets'])} datasets)")
    else:
        print(summary_json, end="")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
