import csv
import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import verify_aggregate_evidence as verifier


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def make_archive(root: Path) -> None:
    performance = []
    for i in range(36):
        is_core = i < 24
        net = -2.5 if is_core else 3.0
        gross, fees, slip, funding = (0.0, 2.0, 1.0, 0.5) if is_core else (5.0, 1.0, 1.0, 0.0)
        initial = 100.0
        performance.append({
            "scenario_id": f"scenario-{i:02d}", "strategy_group": ("A_test" if i < 12 else "B_test") if is_core else "CONTROL",
            "total_return_fraction": -0.025 if is_core else 0.03,
            "gross_pnl_usdt": gross, "fees_usdt": fees, "slippage_usdt": slip, "funding_usdt": funding,
            "net_trade_pnl_usdt": net, "initial_equity_usdt": initial, "final_equity_usdt": initial + net,
        })
    performance_path = root / verifier.INPUTS["performance"]
    write_csv(performance_path, performance)
    performance_raw = performance_path.read_bytes()
    ledger_path = root / verifier.INPUTS["independent_ledger"]
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps({"status": "VERIFIED_LEDGER", "scenario_count": 36,
        "scenario_ids": [row["scenario_id"] for row in performance],
        "performance_sha256": hashlib.sha256(performance_raw).hexdigest()}), encoding="utf-8")

    event_rows = []
    for direction, values in (("positive", (5, 4, 3, 1, 2, 10, 16)), ("negative", (3, 2, 1, 1, 2, 20, 24))):
        true_events, predicted, tp, fp, fn, tn, eligible = values
        event_rows.append({"period": "eval_2024_2025", "model": "logistic", "direction": direction,
                           "true_events": true_events, "predicted_alerts": predicted, "TP": tp, "FP": fp,
                           "FN": fn, "TN": tn, "eligible_decisions": eligible})
    write_csv(root / verifier.INPUTS["event_metrics"], event_rows)

    small_rows = []
    for scenario in ("base", "pressure", "low", "high"):
        small_rows.append({"version": "v1", "scenario": scenario, "period_type": "annual", "period": "2024",
                           "gross_before_cost_usdt": 10, "fees_usdt": 3, "slippage_usdt": 2, "net_fee_only_usdt": 5})
    write_csv(root / verifier.INPUTS["small_cap_metrics"], small_rows)

    human_rows = []
    for variant in ("FIXED", "STRUCTURE", "TIME6H", "EXTREME"):
        human_rows.append({"cohort": "state_filtered", "variant": variant, "trade_count": 25, "full_net_expectancy": ""})
    for variant in ("FIXED", "STRUCTURE"):
        human_rows.append({"cohort": "all_candidates", "variant": variant, "trade_count": 100, "full_net_expectancy": ""})
    write_csv(root / verifier.INPUTS["human_protection_metrics"], human_rows)


class AggregateVerifierTests(unittest.TestCase):
    def test_cli_prints_json_when_output_path_is_omitted(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp)
            make_archive(archive)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                result = verifier.main([str(archive)])
            summary = json.loads(stdout.getvalue())
            self.assertEqual(result, 0)
            self.assertEqual(summary["status"], "PASS")
            self.assertFalse((archive / "verification_summary.json").exists())

    def test_arithmetic_tampering_fails_without_claiming_strategy_outcome(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp)
            make_archive(archive)
            performance_path = archive / verifier.INPUTS["performance"]
            with performance_path.open("r", newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
                fields = list(rows[0])
            rows[0]["net_trade_pnl_usdt"] = "-2.4"
            with performance_path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            summary = verifier.verify_archive(archive)
            self.assertEqual(summary["status"], "FAIL")
            performance = next(item for item in summary["datasets"] if item["dataset"] == "performance")
            net_check = next(item for item in performance["checks"] if item["name"] == "net_trade_pnl_identity")
            self.assertFalse(net_check["passed"])
            self.assertIn("no strategy assessment", summary["scope"])


if __name__ == "__main__":
    unittest.main()
