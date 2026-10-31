"""Phase 4 Learned Divergence Specialist (`phase4_learned_divergence_test.py`).

Fixes Audit Item #7 & Item #8:
- Preserves the exact Walk-Forward Learned Divergence Specialist (`Ridge(alpha=2000.0)` fit strictly
  on each fold's training set `tr_mask`, zero manual sign flips, zero test-period peeking) that
  produces `phase4_learned_divergence_m2_comparison.csv`.
- Decomposes Item #8 by evaluating each learned divergence specialist under BOTH:
  1. `RECAL_TH`: Validation thresholds recomputed on the combined score `va_base + w * va_div`.
  2. `FROZEN_TH`: Validation thresholds frozen on `va_base` (`threshold_va_sc=va_base`), isolating
     the pure score perturbation without shifting the validation quantile hurdle.
- Also compares `ROLL_PROXY` vs strict `CO_PIVOT` divergence features.
"""

from __future__ import annotations

import json
import time
from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from research.zero_fee_maker_ml_v1.code.features import build_dataset_bundle
from research.zero_fee_maker_ml_v1.code.models import FOLDS, _slice_mask, _zscore_from_val
from research.zero_fee_maker_ml_v1.code.phase2_focused_study import (
    _fit_fast_30m_60m_pair,
    _generate_bar_positions,
    evaluate_position_path,
)
from research.zero_fee_maker_ml_v1.code.phase3_master_ensemble import (
    _build_mature_quarterly_positions,
    _fit_multi_horizon_ridge,
)
from research.zero_fee_maker_ml_v1.code.phase4_divergence_study import (
    RUNS_DIR,
    build_5m_and_1h_divergence_frames,
)


def _fit_learned_divergence_score(
    bundle,
    X_div_df: pd.DataFrame,
    train_start: str,
    train_end: str,
    val_start: str,
    val_end: str,
    test_start: str,
    test_end: str,
) -> Dict[str, object]:
    """Fit causal multi-horizon Ridge model strictly on the training slice `tr_mask`."""
    X_raw = X_div_df.to_numpy(dtype=np.float32)
    y30 = bundle.y0_ret[30]
    y60 = bundle.y0_ret[60]
    valid = np.isfinite(y30) & np.isfinite(y60)

    tr_mask = _slice_mask(bundle.index, train_start, train_end, valid)
    va_mask = _slice_mask(bundle.index, val_start, val_end, valid)
    te_mask = _slice_mask(bundle.index, test_start, test_end, valid)

    scaler = StandardScaler()
    X_tr = scaler.fit_transform(np.nan_to_num(X_raw[tr_mask], nan=0.0))
    X_va = scaler.transform(np.nan_to_num(X_raw[va_mask], nan=0.0))
    X_te = scaler.transform(np.nan_to_num(X_raw[te_mask], nan=0.0))

    reg30 = Ridge(alpha=2000.0, random_state=42).fit(X_tr, np.clip(y30[tr_mask], -0.02, 0.02))
    reg60 = Ridge(alpha=2000.0, random_state=42).fit(X_tr, np.clip(y60[tr_mask], -0.03, 0.03))

    va_30 = _zscore_from_val(reg30.predict(X_va), reg30.predict(X_va))
    te_30 = _zscore_from_val(reg30.predict(X_va), reg30.predict(X_te))
    va_60 = _zscore_from_val(reg60.predict(X_va), reg60.predict(X_va))
    te_60 = _zscore_from_val(reg60.predict(X_va), reg60.predict(X_te))

    return {
        "va_z": 0.50 * va_30 + 0.50 * va_60,
        "te_z": 0.50 * te_30 + 0.50 * te_60,
        "coef_30": {k: round(float(v) * 1e4, 4) for k, v in zip(X_div_df.columns, reg30.coef_)},
        "coef_60": {k: round(float(v) * 1e4, 4) for k, v in zip(X_div_df.columns, reg60.coef_)},
    }


def main() -> None:
    t0 = time.time()
    bundle = build_dataset_bundle("BTCUSDT")
    _, _, div_ml_roll, _ = build_5m_and_1h_divergence_frames(bundle, co_pivot=False)
    _, _, div_ml_copiv, _ = build_5m_and_1h_divergence_frames(bundle, co_pivot=True)

    cols_5m = [c for c in div_ml_roll.columns if ("5m" in c and "1h" not in c)]
    cols_1h = [c for c in div_ml_roll.columns if ("1h" in c and "5m" not in c)]
    cols_both = list(div_ml_roll.columns)

    fold_gbdt: Dict[int, Dict[str, np.ndarray]] = {}
    fold_lin: Dict[int, Dict[str, np.ndarray]] = {}
    div_models: Dict[str, Dict[int, Dict[str, object]]] = {
        "5m_roll": {},
        "1h_roll": {},
        "both_roll": {},
        "5m_copiv": {},
        "1h_copiv": {},
        "both_copiv": {},
    }

    for fold in FOLDS:
        fold_gbdt[fold.year] = _fit_fast_30m_60m_pair(
            bundle, fold.train_start, fold.train_end, fold.val_start, fold.val_end, fold.test_start, fold.test_end
        )
        fold_lin[fold.year] = _fit_multi_horizon_ridge(
            bundle, fold.train_start, fold.train_end, fold.val_start, fold.val_end, fold.test_start, fold.test_end
        )
        div_models["5m_roll"][fold.year] = _fit_learned_divergence_score(
            bundle, div_ml_roll[cols_5m], fold.train_start, fold.train_end, fold.val_start, fold.val_end, fold.test_start, fold.test_end
        )
        div_models["1h_roll"][fold.year] = _fit_learned_divergence_score(
            bundle, div_ml_roll[cols_1h], fold.train_start, fold.train_end, fold.val_start, fold.val_end, fold.test_start, fold.test_end
        )
        div_models["both_roll"][fold.year] = _fit_learned_divergence_score(
            bundle, div_ml_roll[cols_both], fold.train_start, fold.train_end, fold.val_start, fold.val_end, fold.test_start, fold.test_end
        )
        div_models["5m_copiv"][fold.year] = _fit_learned_divergence_score(
            bundle, div_ml_copiv[cols_5m], fold.train_start, fold.train_end, fold.val_start, fold.val_end, fold.test_start, fold.test_end
        )
        div_models["1h_copiv"][fold.year] = _fit_learned_divergence_score(
            bundle, div_ml_copiv[cols_1h], fold.train_start, fold.train_end, fold.val_start, fold.val_end, fold.test_start, fold.test_end
        )
        div_models["both_copiv"][fold.year] = _fit_learned_divergence_score(
            bundle, div_ml_copiv[cols_both], fold.train_start, fold.train_end, fold.val_start, fold.val_end, fold.test_start, fold.test_end
        )

    e4_pos_by_year = _build_mature_quarterly_positions(bundle, fold_gbdt)

    summary_rows: List[Dict[str, object]] = []
    pos_store: Dict[str, Dict[int, np.ndarray]] = {
        "M2_BASELINE_3X": {},
        "M2_PLUS_5M_DIV_3X": {},
        "M2_PLUS_1H_DIV_3X": {},
        "M2_PLUS_5M_AND_1H_DIV_3X": {},
        "M2_PLUS_5M_DIV_FROZEN_TH_3X": {},
        "M2_PLUS_5M_COPIVOT_DIV_3X": {},
        "M2_PLUS_1H_COPIVOT_DIV_3X": {},
        "M2_PLUS_BOTH_COPIVOT_DIV_3X": {},
    }

    for yr in (2025, 2026):
        g_out = fold_gbdt[yr]
        l_out = fold_lin[yr]
        te_mask = g_out["te_mask"]

        va_j_z = _zscore_from_val(g_out["va_joint"], g_out["va_joint"])
        te_j_z = _zscore_from_val(g_out["va_joint"], g_out["te_joint"])

        p_e1 = _generate_bar_positions(
            bundle, te_mask, g_out["va_s30"], g_out["te_s30"],
            g_out["va_ml30"], g_out["te_ml30"], g_out["va_ms30"], g_out["te_ms30"],
            step_bars=6, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
        )
        p_e2 = _generate_bar_positions(
            bundle, te_mask, g_out["va_joint"], g_out["te_joint"],
            g_out["va_ml60"], g_out["te_ml60"], g_out["va_ms60"], g_out["te_ms60"],
            step_bars=6, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
        )
        p_lin15 = _generate_bar_positions(
            bundle, te_mask, l_out["va_lin_15"], l_out["te_lin_15"],
            g_out["va_ml30"], g_out["te_ml30"], g_out["va_ms30"], g_out["te_ms30"],
            step_bars=3, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
        )
        p_lin30 = _generate_bar_positions(
            bundle, te_mask, l_out["va_lin_blend"], l_out["te_lin_blend"],
            g_out["va_ml30"], g_out["te_ml30"], g_out["va_ms30"], g_out["te_ms30"],
            step_bars=6, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
        )
        p_e3 = 0.50 * p_lin15 + 0.50 * p_lin30
        p_e4 = e4_pos_by_year[yr]
        pos_store["M2_BASELINE_3X"][yr] = 0.25 * p_e1 + 0.25 * p_e2 + 0.25 * p_e3 + 0.25 * p_e4

        def _build_div_m2(va_dz: np.ndarray, te_dz: np.ndarray, freeze_base_th: bool = False) -> np.ndarray:
            p_l15_d = _generate_bar_positions(
                bundle, te_mask,
                0.85 * l_out["va_lin_15"] + 0.15 * va_dz,
                0.85 * l_out["te_lin_15"] + 0.15 * te_dz,
                g_out["va_ml30"], g_out["te_ml30"], g_out["va_ms30"], g_out["te_ms30"],
                step_bars=3, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
                threshold_va_sc=l_out["va_lin_15"] if freeze_base_th else None,
            )
            p_l30_d = _generate_bar_positions(
                bundle, te_mask,
                0.85 * l_out["va_lin_blend"] + 0.15 * va_dz,
                0.85 * l_out["te_lin_blend"] + 0.15 * te_dz,
                g_out["va_ml30"], g_out["te_ml30"], g_out["va_ms30"], g_out["te_ms30"],
                step_bars=6, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
                threshold_va_sc=l_out["va_lin_blend"] if freeze_base_th else None,
            )
            p_e3_d = 0.50 * p_l15_d + 0.50 * p_l30_d

            p_e2_d = _generate_bar_positions(
                bundle, te_mask,
                0.88 * va_j_z + 0.12 * va_dz,
                0.88 * te_j_z + 0.12 * te_dz,
                g_out["va_ml60"], g_out["te_ml60"], g_out["va_ms60"], g_out["te_ms60"],
                step_bars=6, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
                threshold_va_sc=va_j_z if freeze_base_th else None,
            )
            return 0.25 * p_e1 + 0.25 * p_e2_d + 0.25 * p_e3_d + 0.25 * p_e4

        pos_store["M2_PLUS_5M_DIV_3X"][yr] = _build_div_m2(
            div_models["5m_roll"][yr]["va_z"], div_models["5m_roll"][yr]["te_z"], freeze_base_th=False
        )
        pos_store["M2_PLUS_1H_DIV_3X"][yr] = _build_div_m2(
            div_models["1h_roll"][yr]["va_z"], div_models["1h_roll"][yr]["te_z"], freeze_base_th=False
        )
        pos_store["M2_PLUS_5M_AND_1H_DIV_3X"][yr] = _build_div_m2(
            div_models["both_roll"][yr]["va_z"], div_models["both_roll"][yr]["te_z"], freeze_base_th=False
        )
        pos_store["M2_PLUS_5M_DIV_FROZEN_TH_3X"][yr] = _build_div_m2(
            div_models["5m_roll"][yr]["va_z"], div_models["5m_roll"][yr]["te_z"], freeze_base_th=True
        )
        pos_store["M2_PLUS_5M_COPIVOT_DIV_3X"][yr] = _build_div_m2(
            div_models["5m_copiv"][yr]["va_z"], div_models["5m_copiv"][yr]["te_z"], freeze_base_th=False
        )
        pos_store["M2_PLUS_1H_COPIVOT_DIV_3X"][yr] = _build_div_m2(
            div_models["1h_copiv"][yr]["va_z"], div_models["1h_copiv"][yr]["te_z"], freeze_base_th=False
        )
        pos_store["M2_PLUS_BOTH_COPIVOT_DIV_3X"][yr] = _build_div_m2(
            div_models["both_copiv"][yr]["va_z"], div_models["both_copiv"][yr]["te_z"], freeze_base_th=False
        )

        for v_name in pos_store:
            p_arr = pos_store[v_name][yr]
            res_3x, _ = evaluate_position_path(bundle, te_mask, p_arr, one_way_cost_bp=0.5, leverage=3.0)
            res_0bp, _ = evaluate_position_path(bundle, te_mask, p_arr, one_way_cost_bp=0.0, leverage=3.0)
            summary_rows.append(
                {
                    "variant": v_name,
                    "year": yr,
                    "ret_3x_05bp_pct": res_3x["total_return_pct"],
                    "ret_3x_00bp_pct": res_0bp["total_return_pct"],
                    "cagr_3x_05bp_pct": res_3x["cagr_pct"],
                    "max_dd_3x_pct": res_3x["max_drawdown_pct"],
                    "sharpe_daily": res_3x["sharpe_daily"],
                    "profit_factor": res_3x["profit_factor_daily"],
                    "round_trips": res_3x["round_trips_equiv"],
                    "avg_net_bp_per_rt": res_3x["avg_net_bp_per_rt"],
                    "worst_month_pct": res_3x["worst_month_pct"],
                    "best_month_pct": res_3x["best_month_pct"],
                    "liquidations": res_3x["liquidations"],
                    "max_ep_floating_loss_pct": res_3x["max_ep_floating_loss_pct"],
                }
            )

    df_out = pd.DataFrame(summary_rows)
    df_out.to_csv(RUNS_DIR / "phase4_learned_divergence_m2_comparison.csv", index=False)

    comp_summary = {}
    for v_name in pos_store:
        r25 = float(df_out[(df_out["variant"] == v_name) & (df_out["year"] == 2025)]["ret_3x_05bp_pct"].iloc[0])
        r26 = float(df_out[(df_out["variant"] == v_name) & (df_out["year"] == 2026)]["ret_3x_05bp_pct"].iloc[0])
        tot_21m = ((1.0 + r25 / 100.0) * (1.0 + r26 / 100.0) - 1.0) * 100.0
        comp_summary[v_name] = {
            "2025_ret_3x_pct": round(r25, 2),
            "2026_ret_3x_pct": round(r26, 2),
            "total_21m_compounded_3x_pct": round(tot_21m, 2),
        }

    with open(RUNS_DIR / "phase4_learned_divergence_summary.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "compounded_21m_comparison": comp_summary,
                "learned_coefficients_2026": {
                    "5m_roll_30m_coef_bp": div_models["5m_roll"][2026]["coef_30"],
                    "1h_roll_60m_coef_bp": div_models["1h_roll"][2026]["coef_60"],
                },
            },
            f,
            indent=2,
        )

    print(df_out.to_string(index=False))
    print("\n21-Month Compounded Totals (3.0X @ 0.5bp/side):")
    print(json.dumps(comp_summary, indent=2))
    print(f"Elapsed: {time.time() - t0:.2f}s")


if __name__ == "__main__":
    main()
