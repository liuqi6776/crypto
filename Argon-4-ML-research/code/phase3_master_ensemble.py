"""Phase 3 Master Ensemble & Live-Ready Fusion Architecture for 0-Fee Maker BTCUSDT.

Fuses the orthogonal alpha engines discovered in Phases 1 & 2 into a unified, bar-netted
multi-model, multi-horizon strategy with Y1 90th-percentile anti-liquidation gating:

Component Engines:
- E1_30M_SIGN_HGB: 30m Non-linear HistGradientBoosting Sign Classifier + Y1(30m) q90 gate
- E2_30M_60M_JOINT_HGB: 30m Sign HGB + 60m 65/35 Tail-Hurdle HGB Joint Z-Score + Y1(60m) q90 gate
- E3_MULTI_HORIZON_RIDGE: L2-Regularized Linear Ridge Ensemble across 15m, 30m, 60m + Y1(30m) q90 gate
- E4_MATURE_QUARTERLY_HGB: Expanding-window Quarterly Retrained Dual HGB (activates quarterly refresh
  once training history >= 15 months, i.e., from 2025 Q3 onward; uses base fold before 2025 Q3)

Fusion Methods Tested:
- M1_SIGNAL_META_ENSEMBLE: Blends validation-standardized Z-scores of (30m Sign HGB + 60m Tail HGB +
  Multi-Horizon Ridge Linear) into a single composite score before hysteresis & Y1 gating.
- M2_SUBBOOK_BAR_NETTING: Runs E1, E2, E3, E4 as 4 sub-books (25% allocation each) and nets positions
  at every 5m bar before execution (discrete conviction tiers 0%, 25%, 50%, 75%, 100%; opposing flips cancel).
- M3_HYBRID_MASTER_ENSEMBLE: 50% M1 (Signal Meta-Ensemble) + 50% M2 (4-Sub-book Netting) with Y1
  inverse-volatility dynamic sizing and turnover buffer (ignores position adjustments < 15%).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from research.zero_fee_maker_ml_v1.code.features import ROOT, DatasetBundle, build_dataset_bundle
from research.zero_fee_maker_ml_v1.code.models import FOLDS, _slice_mask, _zscore_from_val
from research.zero_fee_maker_ml_v1.code.phase2_focused_study import (
    _fit_fast_30m_60m_pair,
    _generate_bar_positions,
    evaluate_position_path,
)

RUNS_DIR = ROOT / "research" / "zero_fee_maker_ml_v1" / "runs"


def _fit_multi_horizon_ridge(
    bundle: DatasetBundle,
    train_start: str,
    train_end: str,
    val_start: str,
    val_end: str,
    test_start: str,
    test_end: str,
) -> Dict[str, np.ndarray]:
    """Fit L2-regularized Ridge models across 15m, 30m, and 60m horizons and blend their Z-scores."""
    X_all = bundle.features.to_numpy(dtype=np.float32)
    y15 = bundle.y0_ret[15]
    y30 = bundle.y0_ret[30]
    y60 = bundle.y0_ret[60]

    valid = np.isfinite(y15) & np.isfinite(y30) & np.isfinite(y60)
    tr_mask = _slice_mask(bundle.index, train_start, train_end, valid)
    va_mask = _slice_mask(bundle.index, val_start, val_end, valid)
    te_mask = _slice_mask(bundle.index, test_start, test_end, valid)

    scaler = StandardScaler()
    X_tr = scaler.fit_transform(np.nan_to_num(X_all[tr_mask], nan=0.0, posinf=0.0, neginf=0.0))
    X_va = scaler.transform(np.nan_to_num(X_all[va_mask], nan=0.0, posinf=0.0, neginf=0.0))
    X_te = scaler.transform(np.nan_to_num(X_all[te_mask], nan=0.0, posinf=0.0, neginf=0.0))

    va_preds: Dict[int, np.ndarray] = {}
    te_preds: Dict[int, np.ndarray] = {}
    for h_min, y_arr in ((15, y15), (30, y30), (60, y60)):
        y_tr = y_arr[tr_mask]
        clip_v = float(np.quantile(np.abs(y_tr), 0.995))
        reg = Ridge(alpha=8000.0, random_state=42)
        reg.fit(X_tr, np.clip(y_tr, -clip_v, clip_v))
        va_p = reg.predict(X_va)
        te_p = reg.predict(X_te)
        va_preds[h_min] = _zscore_from_val(va_p, va_p)
        te_preds[h_min] = _zscore_from_val(va_p, te_p)

    va_lin_blend = 0.30 * va_preds[15] + 0.40 * va_preds[30] + 0.30 * va_preds[60]
    te_lin_blend = 0.30 * te_preds[15] + 0.40 * te_preds[30] + 0.30 * te_preds[60]
    return {
        "va_lin_15": va_preds[15],
        "te_lin_15": te_preds[15],
        "va_lin_30": va_preds[30],
        "te_lin_30": te_preds[30],
        "va_lin_60": va_preds[60],
        "te_lin_60": te_preds[60],
        "va_lin_blend": va_lin_blend,
        "te_lin_blend": te_lin_blend,
    }


def _build_mature_quarterly_positions(
    bundle: DatasetBundle,
    static_fold_outputs: Dict[int, Dict[str, np.ndarray]],
) -> Dict[int, np.ndarray]:
    """Build E4 positions: uses static fold when training history < 15 months (2025 H1),
    and quarterly expanding retraining once training history >= 15 months (2025 H2 & 2026 Q1..Q3)."""
    mature_quarters = [
        # (year, train_end, val_start, val_end, test_start, test_end)
        (2025, "2025-03-31 21:55:00+00:00", "2025-04-01 00:00:00+00:00", "2025-06-30 21:55:00+00:00", "2025-07-01 00:00:00+00:00", "2025-09-30 23:55:00+00:00"),
        (2025, "2025-06-30 21:55:00+00:00", "2025-07-01 00:00:00+00:00", "2025-09-30 21:55:00+00:00", "2025-10-01 00:00:00+00:00", "2025-12-31 23:55:00+00:00"),
        (2026, "2025-09-30 21:55:00+00:00", "2025-10-01 00:00:00+00:00", "2025-12-31 21:55:00+00:00", "2026-01-01 00:00:00+00:00", "2026-03-31 23:55:00+00:00"),
        (2026, "2025-12-31 21:55:00+00:00", "2026-01-01 00:00:00+00:00", "2026-03-31 21:55:00+00:00", "2026-04-01 00:00:00+00:00", "2026-06-30 23:55:00+00:00"),
        (2026, "2026-03-31 21:55:00+00:00", "2026-04-01 00:00:00+00:00", "2026-06-30 21:55:00+00:00", "2026-07-01 00:00:00+00:00", "2026-09-24 22:00:00+00:00"),
    ]
    n_total = len(bundle.index)
    global_pos = np.zeros(n_total, dtype=np.float64)

    # Default to static joint/dual positions for 2025 H1
    out25 = static_fold_outputs[2025]
    p30_25 = _generate_bar_positions(
        bundle, out25["te_mask"], out25["va_s30"], out25["te_s30"],
        out25["va_ml30"], out25["te_ml30"], out25["va_ms30"], out25["te_ms30"],
        step_bars=6, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
    )
    pjoint_25 = _generate_bar_positions(
        bundle, out25["te_mask"], out25["va_joint"], out25["te_joint"],
        out25["va_ml60"], out25["te_ml60"], out25["va_ms60"], out25["te_ms60"],
        step_bars=6, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
    )
    global_pos[out25["te_mask"]] = 0.5 * p30_25 + 0.5 * pjoint_25

    for yr, tr_e, va_s, va_e, te_s, te_e in mature_quarters:
        q_out = _fit_fast_30m_60m_pair(
            bundle,
            train_start="2024-01-05 00:00:00+00:00",
            train_end=tr_e,
            val_start=va_s,
            val_end=va_e,
            test_start=te_s,
            test_end=te_e,
        )
        p30 = _generate_bar_positions(
            bundle, q_out["te_mask"], q_out["va_s30"], q_out["te_s30"],
            q_out["va_ml30"], q_out["te_ml30"], q_out["va_ms30"], q_out["te_ms30"],
            step_bars=6, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
        )
        p60 = _generate_bar_positions(
            bundle, q_out["te_mask"], q_out["va_t60"], q_out["te_t60"],
            q_out["va_ml60"], q_out["te_ml60"], q_out["va_ms60"], q_out["te_ms60"],
            step_bars=12, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
        )
        global_pos[q_out["te_mask"]] = 0.5 * p30 + 0.5 * p60

    return {
        2025: global_pos[static_fold_outputs[2025]["te_mask"]],
        2026: global_pos[static_fold_outputs[2026]["te_mask"]],
    }


def _apply_rebalance_buffer(pos_path: np.ndarray, min_delta: float = 0.20) -> np.ndarray:
    """Suppress tiny fractional adjustments (< min_delta) unless unwinding to flat (0.0)."""
    out = np.zeros_like(pos_path)
    cur = 0.0
    for i, target in enumerate(pos_path):
        if abs(target) < 1e-6:
            cur = 0.0
        elif abs(target - cur) >= min_delta:
            cur = float(target)
        out[i] = cur
    return out


def main() -> None:
    t0 = time.time()
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    print("=== Phase 3: Building Master Ensemble on BTCUSDT ===")
    bundle = build_dataset_bundle("BTCUSDT")

    fold_gbdt: Dict[int, Dict[str, np.ndarray]] = {}
    fold_lin: Dict[int, Dict[str, np.ndarray]] = {}
    for fold in FOLDS:
        print(f"Fitting GBDT + Multi-Horizon Ridge models for {fold.year}...")
        fold_gbdt[fold.year] = _fit_fast_30m_60m_pair(
            bundle, fold.train_start, fold.train_end, fold.val_start, fold.val_end, fold.test_start, fold.test_end
        )
        fold_lin[fold.year] = _fit_multi_horizon_ridge(
            bundle, fold.train_start, fold.train_end, fold.val_start, fold.val_end, fold.test_start, fold.test_end
        )

    print("Fitting Mature Quarterly Expanding HGB Sub-Book...")
    e4_pos_by_year = _build_mature_quarterly_positions(bundle, fold_gbdt)

    comparison_rows: List[Dict[str, object]] = []
    monthly_rows: List[Dict[str, object]] = []
    corr_summary: Dict[str, object] = {}

    for yr in (2025, 2026):
        g_out = fold_gbdt[yr]
        l_out = fold_lin[yr]
        te_mask = g_out["te_mask"]

        # --- Component Engine 1: E1_30M_SIGN_HGB ---
        p_e1 = _generate_bar_positions(
            bundle, te_mask, g_out["va_s30"], g_out["te_s30"],
            g_out["va_ml30"], g_out["te_ml30"], g_out["va_ms30"], g_out["te_ms30"],
            step_bars=6, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
        )

        # --- Component Engine 2: E2_30M_60M_JOINT_HGB ---
        p_e2 = _generate_bar_positions(
            bundle, te_mask, g_out["va_joint"], g_out["te_joint"],
            g_out["va_ml60"], g_out["te_ml60"], g_out["va_ms60"], g_out["te_ms60"],
            step_bars=6, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
        )

        # --- Component Engine 3: E3_MULTI_HORIZON_RIDGE (15m + 30m + 60m Linear Sub-Books) ---
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

        # --- Component Engine 4: E4_MATURE_QUARTERLY_HGB ---
        p_e4 = e4_pos_by_year[yr]

        # Measure pairwise position correlation across the 4 engines
        mat_pos = pd.DataFrame({"E1_30m_HGB": p_e1, "E2_Joint_HGB": p_e2, "E3_Multi_Ridge": p_e3, "E4_Qtr_HGB": p_e4})
        corr_summary[str(yr)] = mat_pos.corr().round(3).to_dict()

        # --- Fusion Method M1: Signal-Level Meta-Ensemble (40% 30m HGB + 30% 60m Tail HGB + 30% Multi-Horizon Ridge) ---
        va_meta = (
            0.40 * _zscore_from_val(g_out["va_s30"], g_out["va_s30"])
            + 0.30 * _zscore_from_val(g_out["va_t60"], g_out["va_t60"])
            + 0.30 * _zscore_from_val(l_out["va_lin_blend"], l_out["va_lin_blend"])
        )
        te_meta = (
            0.40 * _zscore_from_val(g_out["va_s30"], g_out["te_s30"])
            + 0.30 * _zscore_from_val(g_out["va_t60"], g_out["te_t60"])
            + 0.30 * _zscore_from_val(l_out["va_lin_blend"], l_out["te_lin_blend"])
        )
        p_m1_30 = _generate_bar_positions(
            bundle, te_mask, va_meta, te_meta,
            g_out["va_ml30"], g_out["te_ml30"], g_out["va_ms30"], g_out["te_ms30"],
            step_bars=6, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
        )
        p_m1_60 = _generate_bar_positions(
            bundle, te_mask, va_meta, te_meta,
            g_out["va_ml60"], g_out["te_ml60"], g_out["va_ms60"], g_out["te_ms60"],
            step_bars=12, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
        )
        p_m1 = 0.50 * p_m1_30 + 0.50 * p_m1_60

        # --- Fusion Method M2: 4-Engine Sub-Book Bar Netting (25% each: E1 + E2 + E3 + E4) ---
        p_m2 = 0.25 * p_e1 + 0.25 * p_e2 + 0.25 * p_e3 + 0.25 * p_e4

        # --- Fusion Method M3: Hybrid Master Live Ensemble (Buffered 50% M1 + 50% M2) ---
        p_m3_raw = 0.50 * p_m1 + 0.50 * p_m2
        p_m3 = _apply_rebalance_buffer(p_m3_raw, min_delta=0.20)

        strategies = [
            ("E1_30M_SIGN_HGB", p_e1),
            ("E2_30M_60M_JOINT_HGB", p_e2),
            ("E3_MULTI_HORIZON_RIDGE", p_e3),
            ("E4_MATURE_QUARTERLY_HGB", p_e4),
            ("M1_SIGNAL_META_ENSEMBLE", p_m1),
            ("M2_4ENGINE_SUBBOOK_NETTING", p_m2),
            ("M3_HYBRID_MASTER_LIVE", p_m3),
        ]

        for s_name, pos_arr in strategies:
            for cost_bp in (0.0, 0.5, 1.0, 1.5):
                for lev in (1.0, 1.5, 2.0):
                    if cost_bp != 0.5 and lev != 1.0:
                        continue
                    res, m_series = evaluate_position_path(
                        bundle, te_mask, pos_arr, one_way_cost_bp=cost_bp, leverage=lev
                    )
                    row: Dict[str, object] = {
                        "year": yr,
                        "strategy": s_name,
                        "one_way_cost_bp": cost_bp,
                        "leverage": lev,
                    }
                    row.update(res)
                    comparison_rows.append(row)

                    if cost_bp == 0.5 and lev == 1.0:
                        for dt_idx, m_ret in m_series.items():
                            monthly_rows.append(
                                {
                                    "strategy": s_name,
                                    "year_month": dt_idx.strftime("%Y-%m"),
                                    "return_pct": round(float(m_ret) * 100.0, 2),
                                }
                            )

    df_comp = pd.DataFrame(comparison_rows)
    df_m = pd.DataFrame(monthly_rows)
    df_comp.to_csv(RUNS_DIR / "phase3_master_ensemble_comparison.csv", index=False)
    df_m.to_csv(RUNS_DIR / "phase3_master_monthly_returns.csv", index=False)

    with open(RUNS_DIR / "phase3_correlations_and_summary.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "elapsed_seconds": round(time.time() - t0, 2),
                "engine_position_correlations": corr_summary,
            },
            f,
            indent=2,
        )
    print(f"=== PHASE 3 COMPLETED in {time.time() - t0:.2f}s ===")


if __name__ == "__main__":
    main()
