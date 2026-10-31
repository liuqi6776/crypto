"""Master runner for the 0-Fee Maker ML Study (SOLUSDT & BTCUSDT, 2025 & 2026 OOS).

Generates all model metrics, feature-group ablations, execution comparisons, cost sensitivity
grids, and Y1 anti-liquidation leverage stress tests under research/zero_fee_maker_ml_v1/runs/.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List

import pandas as pd

from research.zero_fee_maker_ml_v1.code.backtest import (
    simulate_hysteresis_maker,
    simulate_multi_horizon_consensus,
    simulate_passive_limit_maker,
)
from research.zero_fee_maker_ml_v1.code.features import (
    HORIZONS_MIN,
    ROOT,
    build_dataset_bundle,
)
from research.zero_fee_maker_ml_v1.code.models import (
    FOLDS,
    HorizonPredictions,
    run_feature_group_ablation,
    train_and_evaluate_horizon,
)

RUNS_DIR = ROOT / "research" / "zero_fee_maker_ml_v1" / "runs"


def main() -> None:
    t_start = time.time()
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    model_rows: List[Dict[str, object]] = []
    ablation_rows: List[Dict[str, object]] = []
    horizon_cost_rows: List[Dict[str, object]] = []
    exec_comp_rows: List[Dict[str, object]] = []
    leverage_y1_rows: List[Dict[str, object]] = []
    feature_importance_summary: Dict[str, object] = {}
    provenance_hashes: Dict[str, str] = {}

    for sym in ("SOLUSDT", "BTCUSDT"):
        print(f"\n=== Building DatasetBundle for {sym} ===")
        t0 = time.time()
        bundle = build_dataset_bundle(sym)
        provenance_hashes.update(bundle.provenance)
        print(f"Loaded {sym}: {bundle.features.shape} in {time.time() - t0:.2f}s")

        # 1. Feature Group Ablation (at 30m and 60m)
        for ab_h in (15, 30, 60):
            print(f"Running feature group ablation for {sym} H={ab_h}m...")
            ab_res = run_feature_group_ablation(bundle, horizon_min=ab_h)
            ablation_rows.extend(ab_res)

        # 2. Walk-Forward Training & Backtest Evaluation per Fold (2025 & 2026)
        for fold in FOLDS:
            preds_by_h: Dict[int, HorizonPredictions] = {}
            for h_min in HORIZONS_MIN:
                th0 = time.time()
                pred = train_and_evaluate_horizon(bundle, h_min, fold, run_catboost=True)
                preds_by_h[h_min] = pred
                print(
                    f"[{sym} | {fold.year} | H={h_min:2d}m] "
                    f"AUC_pos={pred.metrics['test_auc_pos_ens']:.4f} "
                    f"AUC_tailL={pred.metrics['test_auc_tail_long_hgb']:.4f} "
                    f"IC_comp={pred.metrics['test_ic_comp']:.4f} "
                    f"Top5Edge={pred.metrics['test_top05_combined_edge_bp']:.2f}bp "
                    f"Y1_IC={pred.metrics['test_y1_range_ic']:.4f} "
                    f"({time.time() - th0:.1f}s)"
                )

                m_row: Dict[str, object] = {
                    "target_symbol": sym,
                    "year": fold.year,
                    "horizon_min": h_min,
                }
                m_row.update(pred.metrics)
                model_rows.append(m_row)

                if fold.year == 2026 and h_min in (30, 60):
                    feature_importance_summary[f"{sym}_H{h_min}m_Y0"] = pred.top_features_y0[:10]
                    feature_importance_summary[f"{sym}_H{h_min}m_Y1"] = pred.top_features_y1[:10]

                # 3A. Horizon x Cost Tier Grid for S1_HYSTERESIS_MAKER
                for cost_bp in (0.0, 0.5, 1.0, 6.0):
                    bt = simulate_hysteresis_maker(
                        bundle=bundle,
                        pred=pred,
                        entry_quantile=0.92,
                        hold_quantile=0.58,
                        use_y1_gate=True,
                        y1_quantile_cap=0.85,
                        one_way_cost_bp=cost_bp,
                        leverage=1.0,
                        score_source="comp",
                    )
                    hc_row: Dict[str, object] = {
                        "target_symbol": sym,
                        "year": fold.year,
                        "horizon_min": h_min,
                        "one_way_cost_bp": cost_bp,
                        "round_trip_cost_bp": cost_bp * 2.0,
                        "strategy": "S1_HYSTERESIS_MAKER",
                    }
                    hc_row.update(bt)
                    horizon_cost_rows.append(hc_row)

                # 3B. Compare Score Sources (comp vs tail_hgb vs sign_hgb vs cat vs lin) at 0.5bp Maker cost
                if h_min in (15, 30, 60):
                    for sc_src in ("comp", "tail_hgb", "sign_hgb", "cat", "lin"):
                        bt_sc = simulate_hysteresis_maker(
                            bundle=bundle,
                            pred=pred,
                            entry_quantile=0.92,
                            hold_quantile=0.58,
                            use_y1_gate=True,
                            y1_quantile_cap=0.85,
                            one_way_cost_bp=0.5,
                            leverage=1.0,
                            score_source=sc_src,
                        )
                        ec_row: Dict[str, object] = {
                            "target_symbol": sym,
                            "year": fold.year,
                            "horizon_min": h_min,
                            "variant": f"S1_SCORE_{sc_src.upper()}",
                            "one_way_cost_bp": 0.5,
                        }
                        ec_row.update(bt_sc)
                        exec_comp_rows.append(ec_row)

                    # Compare S2_PASSIVE_LIMIT_MAKER (0bp maker fee, strict limit fill, 6bp SL taker)
                    bt_lim = simulate_passive_limit_maker(
                        bundle=bundle,
                        pred=pred,
                        entry_quantile=0.92,
                        alpha_entry_offset=0.15,
                        k_tp=0.85,
                        k_sl=1.15,
                        maker_fee_bp=0.0,
                        taker_stop_bp=6.0,
                        use_y1_gate=True,
                    )
                    lim_row: Dict[str, object] = {
                        "target_symbol": sym,
                        "year": fold.year,
                        "horizon_min": h_min,
                        "variant": "S2_PASSIVE_LIMIT_MAKER",
                        "one_way_cost_bp": 0.0,
                    }
                    lim_row.update(bt_lim)
                    exec_comp_rows.append(lim_row)

            # 3C. Multi-Horizon Consensus Strategy (5m+15m+30m+60m Y0 + 60m Y1 gate)
            for base_h in (30, 60):
                for cost_bp in (0.0, 0.5, 1.0, 6.0):
                    bt_mh = simulate_multi_horizon_consensus(
                        bundle=bundle,
                        preds_by_h=preds_by_h,
                        base_hold_min=base_h,
                        entry_quantile=0.93,
                        hold_quantile=0.58,
                        one_way_cost_bp=cost_bp,
                        leverage=1.0,
                        use_y1_gate=True,
                        dynamic_y1_sizing=True,
                    )
                    mh_row: Dict[str, object] = {
                        "target_symbol": sym,
                        "year": fold.year,
                        "horizon_min": base_h,
                        "variant": f"S3_MULTI_HORIZON_CONSENSUS_{base_h}M",
                        "one_way_cost_bp": cost_bp,
                    }
                    mh_row.update(bt_mh)
                    exec_comp_rows.append(mh_row)

            # 4. Leverage & Y1 Anti-Liquidation Gate Stress Test (at H=30m and H=60m, 0.5bp Maker cost)
            for h_test in (30, 60):
                pred_h = preds_by_h[h_test]
                for lev in (1.0, 3.0, 5.0, 10.0, 20.0):
                    for gate_mode, use_gate, dyn_sz in (
                        ("NO_Y1_GATE", False, False),
                        ("WITH_Y1_GATE", True, False),
                        ("WITH_Y1_GATE_AND_DYN_SIZING", True, True),
                    ):
                        bt_lev = simulate_hysteresis_maker(
                            bundle=bundle,
                            pred=pred_h,
                            entry_quantile=0.92,
                            hold_quantile=0.58,
                            use_y1_gate=use_gate,
                            y1_quantile_cap=0.82,
                            one_way_cost_bp=0.5,
                            leverage=lev,
                            safety_gamma=1.5,
                            dynamic_y1_sizing=dyn_sz,
                            score_source="comp",
                        )
                        l_row: Dict[str, object] = {
                            "target_symbol": sym,
                            "year": fold.year,
                            "horizon_min": h_test,
                            "leverage": lev,
                            "y1_mode": gate_mode,
                        }
                        l_row.update(bt_lev)
                        leverage_y1_rows.append(l_row)

    df_models = pd.DataFrame(model_rows)
    df_ablation = pd.DataFrame(ablation_rows)
    df_hcost = pd.DataFrame(horizon_cost_rows)
    df_exec = pd.DataFrame(exec_comp_rows)
    df_lev = pd.DataFrame(leverage_y1_rows)

    df_models.to_csv(RUNS_DIR / "model_metrics.csv", index=False)
    df_ablation.to_csv(RUNS_DIR / "feature_ablation.csv", index=False)
    df_hcost.to_csv(RUNS_DIR / "backtest_horizon_cost_grid.csv", index=False)
    df_exec.to_csv(RUNS_DIR / "backtest_execution_comparison.csv", index=False)
    df_lev.to_csv(RUNS_DIR / "backtest_leverage_y1_gate.csv", index=False)

    summary = {
        "elapsed_seconds": round(time.time() - t_start, 2),
        "provenance_sha256": provenance_hashes,
        "feature_importance_top10": feature_importance_summary,
        "n_model_cells": len(df_models),
        "n_ablation_rows": len(df_ablation),
        "n_horizon_cost_rows": len(df_hcost),
        "n_exec_comp_rows": len(df_exec),
        "n_leverage_rows": len(df_lev),
    }
    with open(RUNS_DIR / "summary_results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\n=== ALL RUNS COMPLETED in {summary['elapsed_seconds']}s ===")


if __name__ == "__main__":
    main()
