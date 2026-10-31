"""Phase 4 Event & Overlay Integration Study (Audit-Clean, Zero Test-Period Peeking).

Fixes Audit Items #2, #7, and #8:
1. Item #2 (Zero Test-Period Sign Peeking):
   - Removes all post-hoc sign/weight selections derived from 2025-2026 evaluation statistics.
   - Evaluates two strictly pre-specified / training-only weighting rules:
     a) `TEXTBOOK_APRIORI`: Pure textbook directions (+1 for `reg_bull`/`hid_bull`, -1 for `reg_bear`/`hid_bear`).
     b) `TRAIN_FOLD_IC`: Feature signs and weights determined exclusively on each fold's `tr_mask`
        (2024-01..2024-09 for fold_2025; 2024-01..2025-09 for fold_2026), with zero access to val or test.
2. Item #8 (Strict Isolation of Event Impulse vs Threshold Shift):
   - Uses `threshold_va_sc=base_va_sc` (`FROZEN_TH`) so that on any bar where the event pulse is 0,
     the entry and hold thresholds are 100% identical to `M2_BASELINE_3X` (guaranteeing zero change
     on non-event bars unless a prior event changed the held state).
   - Also reports the `RECAL_TH` counterpart so the threshold-shift effect is explicitly quantified.
"""

from __future__ import annotations

import json
import time
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

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


def _build_textbook_event_pulses(
    div_5m: pd.DataFrame,
    div_1h: pd.DataFrame,
    tr_mask: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Build strictly textbook (+bull - bear) event pulses with thresholds frozen on `tr_mask`."""
    s5_bull = (
        div_5m["macd_reg_bull_5m"].to_numpy()
        + div_5m["rsi_reg_bull_5m"].to_numpy()
        + 0.5 * div_5m["macd_hid_bull_5m"].to_numpy()
        + 0.5 * div_5m["rsi_hid_bull_5m"].to_numpy()
    )
    s5_bear = (
        div_5m["macd_reg_bear_5m"].to_numpy()
        + div_5m["rsi_reg_bear_5m"].to_numpy()
        + 0.5 * div_5m["macd_hid_bear_5m"].to_numpy()
        + 0.5 * div_5m["rsi_hid_bear_5m"].to_numpy()
    )

    pos5_b = s5_bull[tr_mask][s5_bull[tr_mask] > 0]
    pos5_s = s5_bear[tr_mask][s5_bear[tr_mask] > 0]
    th5_b = float(np.quantile(pos5_b, 0.70)) if len(pos5_b) > 10 else 1.0
    th5_s = float(np.quantile(pos5_s, 0.70)) if len(pos5_s) > 10 else 1.0

    pulse_5m = np.zeros(len(div_5m), dtype=np.float64)
    pulse_5m[s5_bull >= th5_b] += np.clip(s5_bull[s5_bull >= th5_b] / (th5_b + 1e-9), 0.0, 2.5)
    pulse_5m[s5_bear >= th5_s] -= np.clip(s5_bear[s5_bear >= th5_s] / (th5_s + 1e-9), 0.0, 2.5)

    s1h_bull = (
        div_1h["macd_reg_bull_1h"].to_numpy()
        + div_1h["rsi_reg_bull_1h"].to_numpy()
        + 0.5 * div_1h["macd_hid_bull_1h"].to_numpy()
        + 0.5 * div_1h["rsi_hid_bull_1h"].to_numpy()
    )
    s1h_bear = (
        div_1h["macd_reg_bear_1h"].to_numpy()
        + div_1h["rsi_reg_bear_1h"].to_numpy()
        + 0.5 * div_1h["macd_hid_bear_1h"].to_numpy()
        + 0.5 * div_1h["rsi_hid_bear_1h"].to_numpy()
    )

    pos1h_b = s1h_bull[tr_mask][s1h_bull[tr_mask] > 0]
    pos1h_s = s1h_bear[tr_mask][s1h_bear[tr_mask] > 0]
    th1h_b = float(np.quantile(pos1h_b, 0.70)) if len(pos1h_b) > 10 else 1.0
    th1h_s = float(np.quantile(pos1h_s, 0.70)) if len(pos1h_s) > 10 else 1.0

    pulse_1h = np.zeros(len(div_1h), dtype=np.float64)
    pulse_1h[s1h_bull >= th1h_b] += np.clip(s1h_bull[s1h_bull >= th1h_b] / (th1h_b + 1e-9), 0.0, 2.5)
    pulse_1h[s1h_bear >= th1h_s] -= np.clip(s1h_bear[s1h_bear >= th1h_s] / (th1h_s + 1e-9), 0.0, 2.5)

    return pulse_5m, pulse_1h


def _build_train_ic_event_pulses(
    div_5m: pd.DataFrame,
    div_1h: pd.DataFrame,
    y30: np.ndarray,
    y60: np.ndarray,
    tr_mask: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, float]]:
    """Learn each divergence feature's sign & t-weight strictly on `tr_mask` (zero val/test peeking)."""
    weights_learned: Dict[str, float] = {}

    def _score_df(df: pd.DataFrame, target_y: np.ndarray) -> np.ndarray:
        total_sig = np.zeros(len(df), dtype=np.float64)
        y_tr = target_y[tr_mask] * 1e4
        for col in df.columns:
            arr = df[col].to_numpy(dtype=np.float64)
            arr_tr = arr[tr_mask]
            pos = arr_tr[arr_tr > 0]
            if len(pos) < 20:
                weights_learned[col] = 0.0
                continue
            th = float(np.quantile(pos, 0.70))
            trig_tr = arr_tr >= th
            # De-cluster by 12 bars on training set
            indep_idx = []
            nxt = 0
            for idx_i in np.flatnonzero(trig_tr):
                if idx_i >= nxt:
                    indep_idx.append(idx_i)
                    nxt = idx_i + 12
            if len(indep_idx) < 10:
                weights_learned[col] = 0.0
                continue
            r_tr = y_tr[indep_idx]
            t_tr = float(np.mean(r_tr) / (np.std(r_tr, ddof=1) / np.sqrt(len(indep_idx)) + 1e-9))
            # Soft threshold at |t_tr| > 0.75 on training fold only
            w = float(np.clip(t_tr / 2.0, -1.5, 1.5)) if abs(t_tr) >= 0.75 else 0.0
            weights_learned[col] = round(w, 3)
            if w != 0.0:
                event_indicator = np.where(arr >= th, np.clip(arr / (th + 1e-9), 0.0, 2.5), 0.0)
                total_sig += w * event_indicator
        return np.clip(total_sig, -2.5, 2.5)

    p5 = _score_df(div_5m, y30)
    p1h = _score_df(div_1h, y60)
    return p5, p1h, weights_learned


def main() -> None:
    t0 = time.time()
    bundle = build_dataset_bundle("BTCUSDT")
    div_5m, div_1h, _, _ = build_5m_and_1h_divergence_frames(bundle, co_pivot=False)

    fold_gbdt: Dict[int, Dict[str, np.ndarray]] = {}
    fold_lin: Dict[int, Dict[str, np.ndarray]] = {}
    for fold in FOLDS:
        fold_gbdt[fold.year] = _fit_fast_30m_60m_pair(
            bundle, fold.train_start, fold.train_end, fold.val_start, fold.val_end, fold.test_start, fold.test_end
        )
        fold_lin[fold.year] = _fit_multi_horizon_ridge(
            bundle, fold.train_start, fold.train_end, fold.val_start, fold.val_end, fold.test_start, fold.test_end
        )
    e4_pos_by_year = _build_mature_quarterly_positions(bundle, fold_gbdt)

    results_rows: List[Dict[str, object]] = []
    train_weights_log: Dict[str, Dict[str, float]] = {}
    pos_store: Dict[str, Dict[int, np.ndarray]] = {
        "1_M2_BASELINE_3X": {},
        "2_M2_TEXTBOOK_5M_FROZEN_TH_3X": {},
        "3_M2_TEXTBOOK_1H_FROZEN_TH_3X": {},
        "4_M2_TEXTBOOK_BOTH_FROZEN_TH_3X": {},
        "5_M2_TRAIN_IC_5M_FROZEN_TH_3X": {},
        "6_M2_TRAIN_IC_1H_FROZEN_TH_3X": {},
        "7_M2_TRAIN_IC_BOTH_FROZEN_TH_3X": {},
        "8_M2_TRAIN_IC_BOTH_RECAL_TH_3X": {},
    }

    valid = np.isfinite(bundle.y0_ret[30]) & np.isfinite(bundle.y0_ret[60])

    for fold in FOLDS:
        yr = fold.year
        g_out = fold_gbdt[yr]
        l_out = fold_lin[yr]
        tr_mask = _slice_mask(bundle.index, fold.train_start, fold.train_end, valid)
        va_mask = g_out["va_mask"]
        te_mask = g_out["te_mask"]

        va_s30_z = _zscore_from_val(g_out["va_s30"], g_out["va_s30"])
        te_s30_z = _zscore_from_val(g_out["va_s30"], g_out["te_s30"])
        va_j_z = _zscore_from_val(g_out["va_joint"], g_out["va_joint"])
        te_j_z = _zscore_from_val(g_out["va_joint"], g_out["te_joint"])

        # Base E1..E4
        p_e1 = _generate_bar_positions(
            bundle, te_mask, va_s30_z, te_s30_z,
            g_out["va_ml30"], g_out["te_ml30"], g_out["va_ms30"], g_out["te_ms30"],
            step_bars=6, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
        )
        p_e2 = _generate_bar_positions(
            bundle, te_mask, va_j_z, te_j_z,
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
        pos_store["1_M2_BASELINE_3X"][yr] = 0.25 * p_e1 + 0.25 * p_e2 + 0.25 * p_e3 + 0.25 * p_e4

        # 1. Textbook a-priori event pulses (thresholds frozen on tr_mask)
        tb_p5, tb_p1h = _build_textbook_event_pulses(div_5m, div_1h, tr_mask)
        # 2. Train-fold-only learned IC event pulses (signs & thresholds learned strictly on tr_mask)
        tr_p5, tr_p1h, w_learned = _build_train_ic_event_pulses(
            div_5m, div_1h, bundle.y0_ret[30], bundle.y0_ret[60], tr_mask
        )
        train_weights_log[str(yr)] = w_learned

        def _apply_pulses(
            p5_arr: np.ndarray,
            p1h_arr: np.ndarray,
            use_5m: bool,
            use_1h: bool,
            freeze_th: bool = True,
        ) -> np.ndarray:
            if use_5m:
                va_5, te_5 = p5_arr[va_mask], p5_arr[te_mask]
                p_l15 = _generate_bar_positions(
                    bundle, te_mask,
                    l_out["va_lin_15"] + 0.18 * va_5,
                    l_out["te_lin_15"] + 0.18 * te_5,
                    g_out["va_ml30"], g_out["te_ml30"], g_out["va_ms30"], g_out["te_ms30"],
                    step_bars=3, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
                    threshold_va_sc=l_out["va_lin_15"] if freeze_th else None,
                )
                p_l30 = _generate_bar_positions(
                    bundle, te_mask,
                    l_out["va_lin_blend"] + 0.18 * va_5,
                    l_out["te_lin_blend"] + 0.18 * te_5,
                    g_out["va_ml30"], g_out["te_ml30"], g_out["va_ms30"], g_out["te_ms30"],
                    step_bars=6, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
                    threshold_va_sc=l_out["va_lin_blend"] if freeze_th else None,
                )
                e3_mod = 0.50 * p_l15 + 0.50 * p_l30
            else:
                e3_mod = p_e3

            if use_1h:
                va_1, te_1 = p1h_arr[va_mask], p1h_arr[te_mask]
                e1_mod = _generate_bar_positions(
                    bundle, te_mask,
                    va_s30_z + 0.18 * va_1,
                    te_s30_z + 0.18 * te_1,
                    g_out["va_ml30"], g_out["te_ml30"], g_out["va_ms30"], g_out["te_ms30"],
                    step_bars=6, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
                    threshold_va_sc=va_s30_z if freeze_th else None,
                )
                e2_mod = _generate_bar_positions(
                    bundle, te_mask,
                    va_j_z + 0.20 * va_1,
                    te_j_z + 0.20 * te_1,
                    g_out["va_ml60"], g_out["te_ml60"], g_out["va_ms60"], g_out["te_ms60"],
                    step_bars=6, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
                    threshold_va_sc=va_j_z if freeze_th else None,
                )
            else:
                e1_mod, e2_mod = p_e1, p_e2

            return 0.25 * e1_mod + 0.25 * e2_mod + 0.25 * e3_mod + 0.25 * p_e4

        pos_store["2_M2_TEXTBOOK_5M_FROZEN_TH_3X"][yr] = _apply_pulses(tb_p5, tb_p1h, True, False, freeze_th=True)
        pos_store["3_M2_TEXTBOOK_1H_FROZEN_TH_3X"][yr] = _apply_pulses(tb_p5, tb_p1h, False, True, freeze_th=True)
        pos_store["4_M2_TEXTBOOK_BOTH_FROZEN_TH_3X"][yr] = _apply_pulses(tb_p5, tb_p1h, True, True, freeze_th=True)

        pos_store["5_M2_TRAIN_IC_5M_FROZEN_TH_3X"][yr] = _apply_pulses(tr_p5, tr_p1h, True, False, freeze_th=True)
        pos_store["6_M2_TRAIN_IC_1H_FROZEN_TH_3X"][yr] = _apply_pulses(tr_p5, tr_p1h, False, True, freeze_th=True)
        pos_store["7_M2_TRAIN_IC_BOTH_FROZEN_TH_3X"][yr] = _apply_pulses(tr_p5, tr_p1h, True, True, freeze_th=True)
        pos_store["8_M2_TRAIN_IC_BOTH_RECAL_TH_3X"][yr] = _apply_pulses(tr_p5, tr_p1h, True, True, freeze_th=False)

        for v_name in pos_store:
            p_arr = pos_store[v_name][yr]
            res_3x, _ = evaluate_position_path(bundle, te_mask, p_arr, one_way_cost_bp=0.5, leverage=3.0)
            res_0bp, _ = evaluate_position_path(bundle, te_mask, p_arr, one_way_cost_bp=0.0, leverage=3.0)
            results_rows.append(
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
                }
            )

    df_res = pd.DataFrame(results_rows)
    df_res.to_csv(RUNS_DIR / "phase4_non_destructive_overlay_comparison.csv", index=False)
    df_res.to_csv(RUNS_DIR / "phase4_event_divergence_m2_comparison.csv", index=False)

    comp_summary = {}
    for v_name in pos_store:
        r25 = float(df_res[(df_res["variant"] == v_name) & (df_res["year"] == 2025)]["ret_3x_05bp_pct"].iloc[0])
        r26 = float(df_res[(df_res["variant"] == v_name) & (df_res["year"] == 2026)]["ret_3x_05bp_pct"].iloc[0])
        tot_21m = ((1.0 + r25 / 100.0) * (1.0 + r26 / 100.0) - 1.0) * 100.0
        comp_summary[v_name] = {
            "2025_ret_3x_pct": round(r25, 2),
            "2026_ret_3x_pct": round(r26, 2),
            "total_21m_compounded_3x_pct": round(tot_21m, 2),
        }

    with open(RUNS_DIR / "phase4_divergence_summary.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "compounded_21m_comparison": comp_summary,
                "train_fold_learned_event_weights": train_weights_log,
            },
            f,
            indent=2,
        )

    print(df_res.to_string(index=False))
    print("\n21-Month Compounded Totals (3.0X @ 0.5bp/side):")
    print(json.dumps(comp_summary, indent=2))
    print(f"Elapsed: {time.time() - t0:.2f}s")


if __name__ == "__main__":
    main()
