"""Phase 2 Focused Study: Dual-Horizon (30m SIGN_HGB + 60m TAIL_HGB) + Y1 Anti-Liquidation Gate on 0-Fee Maker BTCUSDT.

Implements and backtests the exact recommended architecture across 2025 and 2026:
1. Architecture Variants:
   - V1_30M_SIGN_HGB: Single-horizon 30m Sign HGB + Y1 q90 gate
   - V2_60M_TAIL_HGB: Single-horizon 60m 65/35 Tail-Hurdle HGB + Y1 q90 gate
   - V3_DUAL_BOOK_50_50: 50/50 capital allocation between 30m SIGN_HGB and 60m TAIL_HGB sub-books (bar-level net position accounting so offsetting flips save spread/adverse selection)
   - V4_JOINT_30_60_HYSTERESIS: Unified z-scored 30m Sign + 60m Tail signal with dual Y1(30m, 60m) liquidation gate
   - V5_CONFIRMATION_FILTER: High-conviction entry requiring 30m and 60m alignment + Y1 gate
   - V6_QUARTERLY_EXPANDING_RETRAIN: Expanding-window quarterly retraining (Q1..Q4 2025, Q1..Q3 2026) vs static annual training
2. Post-Only Top-of-Book Fill & Adverse Selection Physics:
   - Exact empirical simulation of 1-tick (0.5 bp) & 2-tick (1.0 bp) Join-Best Post-Only fills vs flat 0.0 / 0.5 / 1.0 / 1.5 bp/side adverse-selection cost models.
3. Monthly PnL Attribution (all 21 OOS months: 2025-01 to 2026-09), Parameter Robustness Grid, and 1x-3x Leverage Sizing.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

from research.zero_fee_maker_ml_v1.code.backtest import _funding_sum_between, simulate_hysteresis_maker
from research.zero_fee_maker_ml_v1.code.features import HORIZON_BARS, ROOT, DatasetBundle, build_dataset_bundle
from research.zero_fee_maker_ml_v1.code.models import FOLDS, HorizonPredictions, _slice_mask, _zscore_from_val

RUNS_DIR = ROOT / "research" / "zero_fee_maker_ml_v1" / "runs"


def _fit_hgb_clf_purged_chrono(
    X_tr: np.ndarray,
    y_tr: np.ndarray,
    X_va: np.ndarray,
    X_te: np.ndarray,
    seed: int,
    max_iter: int = 160,
    learning_rate: float = 0.04,
) -> Tuple[np.ndarray, np.ndarray]:
    """Fit HistGradientBoostingClassifier using a strictly chronological, 24-bar (2h) purged
    internal early-stopping split from the tail of X_tr (eliminating random validation_fraction leakage)."""
    n_tr = len(X_tr)
    n_es = max(500, int(n_tr * 0.12))
    purge = 24  # 2-hour purge between internal train and internal chronological early-stop slice
    split_idx = max(1000, n_tr - n_es - purge)

    X_in, y_in = X_tr[:split_idx], y_tr[:split_idx]
    X_es, y_es = X_tr[split_idx + purge :], y_tr[split_idx + purge :]

    clf = HistGradientBoostingClassifier(
        max_iter=max_iter,
        learning_rate=learning_rate,
        max_leaf_nodes=15,
        min_samples_leaf=300,
        l2_regularization=10.0,
        early_stopping=False,
        random_state=seed,
    )
    clf.fit(X_in, y_in)

    # Select optimal boosting stage on chronological purged tail X_es via log-loss
    best_loss = float("inf")
    best_step = max_iter - 1
    no_improve = 0
    for step_idx, proba in enumerate(clf.staged_predict_proba(X_es)):
        p1 = np.clip(proba[:, 1], 1e-6, 1.0 - 1e-6)
        loss = -float(np.mean(y_es * np.log(p1) + (1.0 - y_es) * np.log(1.0 - p1)))
        if loss < best_loss - 1e-5:
            best_loss = loss
            best_step = step_idx
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= 20:
                break

    # Truncate predictor tree list to best_step + 1
    clf._predictors = clf._predictors[: best_step + 1]
    return clf.predict_proba(X_va)[:, 1], clf.predict_proba(X_te)[:, 1]


def _fit_fast_30m_60m_pair(
    bundle: DatasetBundle,
    train_start: str,
    train_end: str,
    val_start: str,
    val_end: str,
    test_start: str,
    test_end: str,
    purged_chrono_hgb: bool = True,
    allow_unlabeled_test: bool = False,
) -> Dict[str, np.ndarray]:
    """Fit the focused 30m SIGN_HGB + 60m TAIL_HGB + Y1(30m, 60m) q90 models on a given split."""
    X_all = bundle.features.to_numpy(dtype=np.float32)
    y0_30 = bundle.y0_ret[30]
    y0_60 = bundle.y0_ret[60]
    y1_ml_30 = bundle.y1_mae_long[30]
    y1_ms_30 = bundle.y1_mae_short[30]
    y1_ml_60 = bundle.y1_mae_long[60]
    y1_ms_60 = bundle.y1_mae_short[60]

    valid = (
        np.isfinite(y0_30)
        & np.isfinite(y0_60)
        & np.isfinite(y1_ml_30)
        & np.isfinite(y1_ms_30)
        & np.isfinite(y1_ml_60)
        & np.isfinite(y1_ms_60)
    )
    tr_mask = _slice_mask(bundle.index, train_start, train_end, valid)
    va_mask = _slice_mask(bundle.index, val_start, val_end, valid)
    te_valid = np.ones(len(bundle.index), dtype=bool) if allow_unlabeled_test else valid
    te_mask = _slice_mask(bundle.index, test_start, test_end, te_valid)

    X_tr, X_va, X_te = X_all[tr_mask], X_all[va_mask], X_all[te_mask]

    # 1. 30m SIGN_HGB model
    y_pos30_tr = (y0_30[tr_mask] > 0.0).astype(np.int32)
    y60_tr = y0_60[tr_mask]
    tau_l60 = float(np.quantile(y60_tr, 0.65))
    tau_s60 = float(np.quantile(y60_tr, 0.35))

    if purged_chrono_hgb:
        va_s30, te_s30 = _fit_hgb_clf_purged_chrono(X_tr, y_pos30_tr, X_va, X_te, seed=42)
        va_l60, te_l60 = _fit_hgb_clf_purged_chrono(X_tr, (y60_tr > tau_l60).astype(np.int32), X_va, X_te, seed=43)
        va_s60, te_s60 = _fit_hgb_clf_purged_chrono(X_tr, (y60_tr < tau_s60).astype(np.int32), X_va, X_te, seed=44)
        va_t60 = va_l60 - va_s60
        te_t60 = te_l60 - te_s60
    else:
        clf_sign30 = HistGradientBoostingClassifier(
            max_iter=160,
            learning_rate=0.04,
            max_leaf_nodes=15,
            min_samples_leaf=300,
            l2_regularization=10.0,
            early_stopping=True,
            validation_fraction=0.12,
            n_iter_no_change=20,
            random_state=42,
        )
        clf_sign30.fit(X_tr, y_pos30_tr)
        va_s30 = clf_sign30.predict_proba(X_va)[:, 1]
        te_s30 = clf_sign30.predict_proba(X_te)[:, 1]

        # 2. 60m TAIL_HGB (65/35 quantile hurdle) model
        clf_l60 = HistGradientBoostingClassifier(
            max_iter=160,
            learning_rate=0.04,
            max_leaf_nodes=15,
            min_samples_leaf=300,
            l2_regularization=10.0,
            early_stopping=True,
            validation_fraction=0.12,
            n_iter_no_change=20,
            random_state=43,
        )
        clf_s60 = HistGradientBoostingClassifier(
            max_iter=160,
            learning_rate=0.04,
            max_leaf_nodes=15,
            min_samples_leaf=300,
            l2_regularization=10.0,
            early_stopping=True,
            validation_fraction=0.12,
            n_iter_no_change=20,
            random_state=44,
        )
        clf_l60.fit(X_tr, (y60_tr > tau_l60).astype(np.int32))
        clf_s60.fit(X_tr, (y60_tr < tau_s60).astype(np.int32))
        va_t60 = clf_l60.predict_proba(X_va)[:, 1] - clf_s60.predict_proba(X_va)[:, 1]
        te_t60 = clf_l60.predict_proba(X_te)[:, 1] - clf_s60.predict_proba(X_te)[:, 1]

    # 3. Y1 90th-percentile MAE quantile regressors (30m & 60m)
    def _fit_q90(y_tr_arr: np.ndarray, seed: int) -> Tuple[np.ndarray, np.ndarray]:
        reg = HistGradientBoostingRegressor(
            loss="quantile",
            quantile=0.90,
            max_iter=120,
            learning_rate=0.05,
            max_leaf_nodes=15,
            min_samples_leaf=250,
            l2_regularization=10.0,
            early_stopping=not purged_chrono_hgb,
            validation_fraction=0.12,
            n_iter_no_change=15,
            random_state=seed,
        )
        # Stride by 12 bars (60m) when purged_chrono_hgb=True so adjacent training targets do not overlap
        stride = 12 if purged_chrono_hgb else 2
        reg.fit(X_tr[::stride], y_tr_arr[::stride])
        return np.clip(reg.predict(X_va), 1e-4, 0.30), np.clip(reg.predict(X_te), 1e-4, 0.30)

    va_ml30, te_ml30 = _fit_q90(y1_ml_30[tr_mask], 52)
    va_ms30, te_ms30 = _fit_q90(y1_ms_30[tr_mask], 53)
    va_ml60, te_ml60 = _fit_q90(y1_ml_60[tr_mask], 62)
    va_ms60, te_ms60 = _fit_q90(y1_ms_60[tr_mask], 63)

    # Joint standardized score
    va_joint = 0.50 * _zscore_from_val(va_s30, va_s30) + 0.50 * _zscore_from_val(va_t60, va_t60)
    te_joint = 0.50 * _zscore_from_val(va_s30, te_s30) + 0.50 * _zscore_from_val(va_t60, te_t60)

    return {
        "va_mask": va_mask,
        "te_mask": te_mask,
        "va_s30": va_s30,
        "te_s30": te_s30,
        "va_t60": va_t60,
        "te_t60": te_t60,
        "va_joint": va_joint,
        "te_joint": te_joint,
        "va_ml30": va_ml30,
        "te_ml30": te_ml30,
        "va_ms30": va_ms30,
        "te_ms30": te_ms30,
        "va_ml60": va_ml60,
        "te_ml60": te_ml60,
        "va_ms60": va_ms60,
        "te_ms60": te_ms60,
    }


def _generate_bar_positions(
    bundle: DatasetBundle,
    te_mask: np.ndarray,
    va_sc: np.ndarray,
    te_sc: np.ndarray,
    va_y1_l: np.ndarray,
    te_y1_l: np.ndarray,
    va_y1_s: np.ndarray,
    te_y1_s: np.ndarray,
    step_bars: int,
    entry_q: float = 0.92,
    hold_q: float = 0.58,
    y1_cap_q: float = 0.85,
    confirm_va_sc: np.ndarray | None = None,
    confirm_te_sc: np.ndarray | None = None,
    confirm_q: float = 0.60,
    threshold_va_sc: np.ndarray | None = None,
) -> np.ndarray:
    """Generate causal bar-by-bar target position array in {-1, 0, +1} on the test slice.

    If `threshold_va_sc` is supplied, quantiles `th_l_en, th_s_en, th_l_hd, th_s_hd` are
    frozen on `threshold_va_sc` so that zero-valued event adjustments on `te_sc` never alter
    baseline decisions via threshold shift.
    """
    ref_va = threshold_va_sc if threshold_va_sc is not None else va_sc
    th_l_en = float(np.quantile(ref_va, entry_q))
    th_s_en = float(np.quantile(ref_va, 1.0 - entry_q))
    th_l_hd = float(np.quantile(ref_va, hold_q))
    th_s_hd = float(np.quantile(ref_va, 1.0 - hold_q))
    y1_cap_l = float(np.quantile(va_y1_l, y1_cap_q))
    y1_cap_s = float(np.quantile(va_y1_s, y1_cap_q))

    if confirm_va_sc is not None:
        cf_l = float(np.quantile(confirm_va_sc, confirm_q))
        cf_s = float(np.quantile(confirm_va_sc, 1.0 - confirm_q))
    else:
        cf_l, cf_s = -1e9, 1e9

    n_te = int(te_mask.sum())
    pos = np.zeros(n_te, dtype=np.float64)

    p = 0
    while p < n_te:
        sc = te_sc[p]
        y1_l = te_y1_l[p]
        y1_s = te_y1_s[p]
        cf_val = confirm_te_sc[p] if confirm_te_sc is not None else 0.0

        side = 0
        if sc >= th_l_en and y1_l <= y1_cap_l and (confirm_te_sc is None or cf_val >= cf_l):
            side = 1
        elif sc <= th_s_en and y1_s <= y1_cap_s and (confirm_te_sc is None or cf_val <= cf_s):
            side = -1

        if side == 0:
            p += 1
            continue

        cur_p = p
        while True:
            end_p = min(cur_p + step_bars, n_te)
            pos[cur_p:end_p] = float(side)
            if end_p >= n_te:
                p = end_p
                break
            next_sc = te_sc[end_p]
            next_y1 = te_y1_l[end_p] if side == 1 else te_y1_s[end_p]
            y1_cap = y1_cap_l if side == 1 else y1_cap_s
            keep = (
                (side == 1 and next_sc >= th_l_hd)
                or (side == -1 and next_sc <= th_s_hd)
            ) and (next_y1 <= y1_cap * 1.15)
            if keep and (end_p - p) < 96:
                cur_p = end_p
            else:
                p = end_p
                break
    return pos


def evaluate_position_path(
    bundle: DatasetBundle,
    te_mask: np.ndarray,
    pos_path: np.ndarray,
    one_way_cost_bp: float = 0.5,
    leverage: float = 1.0,
    post_only_tick_offset_bp: float = 0.0,
    require_passive_tick_fill: bool = False,
) -> Tuple[Dict[str, float], pd.Series]:
    """Evaluate a bar-level position path (in [-1, +1]) with exact 8h funding, execution-aligned
    timestamps (t_{i+1}), and full multi-bar cumulative margin/liquidation settlement."""
    te_indices = np.flatnonzero(te_mask)
    n_te = len(te_indices)
    idx_ms = (bundle.index.astype("int64") // 10**6).to_numpy()
    o_raw = bundle.open_raw
    h_raw = bundle.high_raw
    l_raw = bundle.low_raw

    cost_rate = one_way_cost_bp * 1e-4
    tick_off = post_only_tick_offset_bp * 1e-4

    bar_net_rets = np.zeros(n_te, dtype=np.float64)
    bar_gross_rets = np.zeros(n_te, dtype=np.float64)
    bar_fund_rets = np.zeros(n_te, dtype=np.float64)
    bar_costs = np.zeros(n_te, dtype=np.float64)

    prev_pos = 0.0
    ep_entry_price = 0.0
    max_ep_floating_loss_pct = 0.0
    n_turn_events = 0
    n_filled_events = 0
    total_turnover = 0.0
    liq_count = 0
    liq_dist = max(0.0025, (1.0 / max(leverage, 1.0)) - 0.006)
    liq_clearance_fee = 0.0050  # 50 bp bankruptcy/insurance clearance fee on forced liquidation

    for k in range(n_te - 1):
        g_idx = te_indices[k]
        eb = g_idx + 1
        if eb + 1 >= len(o_raw):
            break

        target_pos = float(pos_path[k])
        delta_pos = target_pos - prev_pos

        o_cur = o_raw[eb]
        h_cur = h_raw[eb]
        l_cur = l_raw[eb]
        o_nxt = o_raw[eb + 1]
        t_start_ms = int(idx_ms[eb])
        t_end_ms = int(idx_ms[eb + 1])

        eff_pos = prev_pos
        entry_bonus = 0.0
        if abs(delta_pos) > 1e-6:
            n_turn_events += 1
            if require_passive_tick_fill and tick_off > 0.0:
                if delta_pos > 0:
                    lim_p = o_cur * (1.0 - tick_off)
                    filled = (l_cur <= lim_p) and (o_cur >= lim_p)
                else:
                    lim_p = o_cur * (1.0 + tick_off)
                    filled = (h_cur >= lim_p) and (o_cur <= lim_p)
                if filled:
                    eff_pos = target_pos
                    n_filled_events += 1
                    total_turnover += abs(delta_pos)
                    entry_bonus = abs(delta_pos) * (tick_off - cost_rate)
                else:
                    if abs(target_pos) < abs(prev_pos):
                        eff_pos = prev_pos
                        total_turnover += abs(delta_pos)
                        entry_bonus = -abs(delta_pos) * cost_rate
            else:
                eff_pos = target_pos
                n_filled_events += 1
                total_turnover += abs(delta_pos)
                entry_bonus = -abs(delta_pos) * cost_rate

        # Track episode reference price when opening or flipping direction
        if abs(eff_pos) < 1e-6:
            ep_entry_price = 0.0
        elif abs(prev_pos) < 1e-6 or (prev_pos * eff_pos < 0):
            ep_entry_price = o_cur

        # Full multi-bar & intrabar margin liquidation check + loss path settlement
        liquidated_this_bar = False
        if abs(eff_pos) > 1e-6:
            ref_p = ep_entry_price if ep_entry_price > 0 else o_cur
            if eff_pos > 0:
                bar_mae = max(0.0, (o_cur - l_cur) / o_cur)
                cum_mae = max(0.0, (ref_p - l_cur) / ref_p)
            else:
                bar_mae = max(0.0, (h_cur - o_cur) / o_cur)
                cum_mae = max(0.0, (h_cur - ref_p) / ref_p)

            worst_mae = max(bar_mae, cum_mae)
            floating_loss_lev = worst_mae * abs(eff_pos) * leverage
            if floating_loss_lev > max_ep_floating_loss_pct:
                max_ep_floating_loss_pct = floating_loss_lev

            if worst_mae * abs(eff_pos) >= liq_dist:
                liq_count += 1
                liquidated_this_bar = True

        f_sum = _funding_sum_between(bundle.funding_ms, bundle.funding_rate, t_start_ms, t_end_ms)
        fund_b = -eff_pos * f_sum

        if liquidated_this_bar:
            # Forced exit at liquidation boundary plus clearance fee; position forced to 0
            gross_b = -(liq_dist + abs(eff_pos) * liq_clearance_fee)
            net_b = (gross_b + fund_b + entry_bonus) * leverage
            eff_pos = 0.0
            ep_entry_price = 0.0
        else:
            gross_b = eff_pos * (o_nxt - o_cur) / o_cur
            net_b = (gross_b + fund_b + entry_bonus) * leverage

        bar_gross_rets[k] = gross_b * leverage
        bar_fund_rets[k] = fund_b * leverage
        bar_costs[k] = entry_bonus * leverage
        bar_net_rets[k] = np.clip(net_b, -0.99, 5.0)

        prev_pos = eff_pos

    eq = np.cumprod(1.0 + bar_net_rets)
    total_ret = float(eq[-1] - 1.0)
    peaks = np.maximum.accumulate(np.concatenate([[1.0], eq]))
    dd = (np.concatenate([[1.0], eq]) - peaks) / peaks
    max_dd = float(np.min(dd))

    years = max(n_te / (288.0 * 365.0), 0.1)
    cagr = float((eq[-1] ** (1.0 / years)) - 1.0) if eq[-1] > 0 else -1.0

    # Fix #5: Align realized bar return over [t_{i+1}, t_{i+2}] to execution timestamp t_{i+1} (eb = g_idx + 1)
    exec_indices = np.minimum(te_indices + 1, len(bundle.index) - 1)
    exec_ts_index = bundle.index[exec_indices]
    s_bar = pd.Series(bar_net_rets, index=exec_ts_index)
    daily_rets = s_bar.resample("1D").apply(lambda x: float(np.prod(1.0 + x) - 1.0))
    d_mu = float(daily_rets.mean())
    d_sd = float(daily_rets.std()) + 1e-12
    sharpe_daily = float((d_mu / d_sd) * np.sqrt(365.0))

    monthly_rets_all = s_bar.resample("1ME").apply(lambda x: float(np.prod(1.0 + x) - 1.0))
    monthly_counts = s_bar.resample("1ME").count()
    monthly_rets = monthly_rets_all[monthly_counts >= 12]
    if len(monthly_rets) == 0:
        monthly_rets = monthly_rets_all
    pos_months = float((monthly_rets > 0).mean()) if len(monthly_rets) > 0 else 0.0

    pos_daily = float(daily_rets[daily_rets > 0].sum())
    neg_daily = float(-daily_rets[daily_rets < 0].sum())
    pf_daily = float(pos_daily / neg_daily) if neg_daily > 1e-12 else 0.0

    round_trips_equiv = total_turnover / 2.0
    avg_gross_bp = (float(np.sum(bar_gross_rets)) / max(1.0, round_trips_equiv * leverage)) * 1e4
    avg_net_bp = (float(np.sum(bar_net_rets)) / max(1.0, round_trips_equiv * leverage)) * 1e4

    metrics = {
        "round_trips_equiv": round(float(round_trips_equiv), 1),
        "total_return_pct": round(total_ret * 100.0, 2),
        "cagr_pct": round(cagr * 100.0, 2),
        "max_drawdown_pct": round(max_dd * 100.0, 2),
        "sharpe_daily": round(sharpe_daily, 2),
        "profit_factor_daily": round(pf_daily, 3),
        "avg_gross_bp_per_rt": round(avg_gross_bp, 2),
        "avg_net_bp_per_rt": round(avg_net_bp, 2),
        "funding_net_pct": round(float(np.sum(bar_fund_rets)) * 100.0, 2),
        "exposure_pct": round(float(np.mean(np.abs(pos_path))) * 100.0, 2),
        "fill_rate_pct": round((n_filled_events / max(1, n_turn_events)) * 100.0, 1),
        "liquidations": int(liq_count),
        "max_ep_floating_loss_pct": round(float(max_ep_floating_loss_pct) * 100.0, 2),
        "positive_months_ratio": round(pos_months * 100.0, 1),
        "worst_month_pct": round(float(monthly_rets.min()) * 100.0, 2) if len(monthly_rets) else 0.0,
        "best_month_pct": round(float(monthly_rets.max()) * 100.0, 2) if len(monthly_rets) else 0.0,
    }
    return metrics, monthly_rets


def run_quarterly_expanding_retrain(bundle: DatasetBundle) -> Dict[int, Tuple[np.ndarray, np.ndarray]]:
    """Run expanding-window quarterly retraining across 2025 (4 quarters) and 2026 (3 quarters)."""
    quarters = [
        # (year, train_end, val_start, val_end, test_start, test_end)
        (2025, "2024-09-30 21:55:00+00:00", "2024-10-01 00:00:00+00:00", "2024-12-31 21:55:00+00:00", "2025-01-01 00:00:00+00:00", "2025-03-31 23:55:00+00:00"),
        (2025, "2024-12-31 21:55:00+00:00", "2025-01-01 00:00:00+00:00", "2025-03-31 21:55:00+00:00", "2025-04-01 00:00:00+00:00", "2025-06-30 23:55:00+00:00"),
        (2025, "2025-03-31 21:55:00+00:00", "2025-04-01 00:00:00+00:00", "2025-06-30 21:55:00+00:00", "2025-07-01 00:00:00+00:00", "2025-09-30 23:55:00+00:00"),
        (2025, "2025-06-30 21:55:00+00:00", "2025-07-01 00:00:00+00:00", "2025-09-30 21:55:00+00:00", "2025-10-01 00:00:00+00:00", "2025-12-31 23:55:00+00:00"),
        (2026, "2025-09-30 21:55:00+00:00", "2025-10-01 00:00:00+00:00", "2025-12-31 21:55:00+00:00", "2026-01-01 00:00:00+00:00", "2026-03-31 23:55:00+00:00"),
        (2026, "2025-12-31 21:55:00+00:00", "2026-01-01 00:00:00+00:00", "2026-03-31 21:55:00+00:00", "2026-04-01 00:00:00+00:00", "2026-06-30 23:55:00+00:00"),
        (2026, "2026-03-31 21:55:00+00:00", "2026-04-01 00:00:00+00:00", "2026-06-30 21:55:00+00:00", "2026-07-01 00:00:00+00:00", "2026-09-24 22:00:00+00:00"),
    ]
    n_total = len(bundle.index)
    full_pos_by_year: Dict[int, np.ndarray] = {
        2025: np.zeros(n_total, dtype=np.float64),
        2026: np.zeros(n_total, dtype=np.float64),
    }
    full_mask_by_year: Dict[int, np.ndarray] = {
        2025: np.zeros(n_total, dtype=bool),
        2026: np.zeros(n_total, dtype=bool),
    }

    for yr, tr_e, va_s, va_e, te_s, te_e in quarters:
        out = _fit_fast_30m_60m_pair(
            bundle,
            train_start="2024-01-05 00:00:00+00:00",
            train_end=tr_e,
            val_start=va_s,
            val_end=va_e,
            test_start=te_s,
            test_end=te_e,
        )
        p30 = _generate_bar_positions(
            bundle, out["te_mask"], out["va_s30"], out["te_s30"],
            out["va_ml30"], out["te_ml30"], out["va_ms30"], out["te_ms30"],
            step_bars=6, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
        )
        p60 = _generate_bar_positions(
            bundle, out["te_mask"], out["va_t60"], out["te_t60"],
            out["va_ml60"], out["te_ml60"], out["va_ms60"], out["te_ms60"],
            step_bars=12, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
        )
        p_dual = 0.5 * p30 + 0.5 * p60
        full_pos_by_year[yr][out["te_mask"]] = p_dual
        full_mask_by_year[yr] |= out["te_mask"]

    return {
        yr: (full_mask_by_year[yr], full_pos_by_year[yr][full_mask_by_year[yr]])
        for yr in (2025, 2026)
    }


def main() -> None:
    t0 = time.time()
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    print("=== Loading BTCUSDT DatasetBundle (with SOL/ETH/BNB & OrderFlow/Funding/Basis/DVOL) ===")
    bundle = build_dataset_bundle("BTCUSDT")

    arch_rows: List[Dict[str, object]] = []
    physics_rows: List[Dict[str, object]] = []
    param_rows: List[Dict[str, object]] = []
    monthly_records: List[Dict[str, object]] = []

    # 1. Fit static fold models (2025 & 2026)
    fold_outputs: Dict[int, Dict[str, np.ndarray]] = {}
    for fold in FOLDS:
        print(f"Fitting 30m SIGN_HGB + 60m TAIL_HGB + Y1 q90 models for {fold.year}...")
        fold_outputs[fold.year] = _fit_fast_30m_60m_pair(
            bundle,
            fold.train_start,
            fold.train_end,
            fold.val_start,
            fold.val_end,
            fold.test_start,
            fold.test_end,
        )

    # 2. Fit quarterly expanding-window models
    print("Running quarterly expanding-window retraining across 2025 Q1..Q4 and 2026 Q1..Q3...")
    q_retrain = run_quarterly_expanding_retrain(bundle)

    # 3. Evaluate all 6 Architecture Variants across 2025 & 2026 and cost tiers
    for yr in (2025, 2026):
        out = fold_outputs[yr]
        te_mask = out["te_mask"]

        p_v1_30m = _generate_bar_positions(
            bundle, te_mask, out["va_s30"], out["te_s30"],
            out["va_ml30"], out["te_ml30"], out["va_ms30"], out["te_ms30"],
            step_bars=6, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
        )
        p_v2_60m = _generate_bar_positions(
            bundle, te_mask, out["va_t60"], out["te_t60"],
            out["va_ml60"], out["te_ml60"], out["va_ms60"], out["te_ms60"],
            step_bars=12, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
        )
        p_v3_dual = 0.50 * p_v1_30m + 0.50 * p_v2_60m
        p_v4_joint = _generate_bar_positions(
            bundle, te_mask, out["va_joint"], out["te_joint"],
            out["va_ml60"], out["te_ml60"], out["va_ms60"], out["te_ms60"],
            step_bars=6, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
        )
        p_v5_confirm = _generate_bar_positions(
            bundle, te_mask, out["va_t60"], out["te_t60"],
            out["va_ml60"], out["te_ml60"], out["va_ms60"], out["te_ms60"],
            step_bars=12, entry_q=0.90, hold_q=0.56, y1_cap_q=0.85,
            confirm_va_sc=out["va_s30"], confirm_te_sc=out["te_s30"], confirm_q=0.62,
        )
        q_mask, p_v6_qtr = q_retrain[yr]

        variants = [
            ("V1_30M_SIGN_HGB", te_mask, p_v1_30m),
            ("V2_60M_TAIL_HGB", te_mask, p_v2_60m),
            ("V3_DUAL_BOOK_50_50", te_mask, p_v3_dual),
            ("V4_JOINT_30_60_HYSTERESIS", te_mask, p_v4_joint),
            ("V5_CONFIRMATION_30_60", te_mask, p_v5_confirm),
            ("V6_QUARTERLY_RETRAIN_DUAL", q_mask, p_v6_qtr),
        ]

        for v_name, m_arr, pos_arr in variants:
            for cost_bp in (0.0, 0.5, 1.0, 1.5, 6.0):
                res, m_series = evaluate_position_path(
                    bundle, m_arr, pos_arr, one_way_cost_bp=cost_bp, leverage=1.0
                )
                row: Dict[str, object] = {
                    "year": yr,
                    "variant": v_name,
                    "one_way_cost_bp": cost_bp,
                    "round_trip_cost_bp": cost_bp * 2.0,
                }
                row.update(res)
                arch_rows.append(row)

                if cost_bp == 0.5:
                    for dt_idx, m_ret in m_series.items():
                        monthly_records.append(
                            {
                                "variant": v_name,
                                "year_month": dt_idx.strftime("%Y-%m"),
                                "return_pct": round(float(m_ret) * 100.0, 2),
                            }
                        )

        # 4. Post-Only Top-of-Book Fill & Adverse Selection Physics on V3_DUAL_BOOK_50_50 & V5_CONFIRMATION_30_60
        for v_name, m_arr, pos_arr in (
            ("V3_DUAL_BOOK_50_50", te_mask, p_v3_dual),
            ("V5_CONFIRMATION_30_60", te_mask, p_v5_confirm),
            ("V6_QUARTERLY_RETRAIN_DUAL", q_mask, p_v6_qtr),
        ):
            for mode_label, c_bp, tick_bp, req_fill in (
                ("IDEAL_0BP_IMMEDIATE_MAKER", 0.0, 0.0, False),
                ("POST_ONLY_1TICK_0.5BP_OFFSET_NO_ADV", 0.0, 0.5, True),
                ("POST_ONLY_1TICK_0.5BP_OFFSET_WITH_0.5BP_ADV", 0.5, 0.5, True),
                ("POST_ONLY_2TICK_1.0BP_OFFSET_WITH_0.5BP_ADV", 0.5, 1.0, True),
                ("FLAT_0.5BP_ADV_SELECTION_100PCT_FILL", 0.5, 0.0, False),
                ("FLAT_1.0BP_ADV_SELECTION_100PCT_FILL", 1.0, 0.0, False),
            ):
                for lev in (1.0, 1.5, 2.0):
                    p_res, _ = evaluate_position_path(
                        bundle,
                        m_arr,
                        pos_arr,
                        one_way_cost_bp=c_bp,
                        leverage=lev,
                        post_only_tick_offset_bp=tick_bp,
                        require_passive_tick_fill=req_fill,
                    )
                    prow: Dict[str, object] = {
                        "year": yr,
                        "variant": v_name,
                        "execution_physics": mode_label,
                        "leverage": lev,
                    }
                    prow.update(p_res)
                    physics_rows.append(prow)

        # 5. Parameter Sensitivity Surface around (entry_q=0.92, hold_q=0.58, y1_cap_q=0.85) at 0.5 bp/side
        for eq_val in (0.88, 0.90, 0.92, 0.94):
            for hq_val in (0.54, 0.58, 0.62):
                for y1_val in (0.80, 0.85, 0.90):
                    p30_g = _generate_bar_positions(
                        bundle, te_mask, out["va_s30"], out["te_s30"],
                        out["va_ml30"], out["te_ml30"], out["va_ms30"], out["te_ms30"],
                        step_bars=6, entry_q=eq_val, hold_q=hq_val, y1_cap_q=y1_val,
                    )
                    p60_g = _generate_bar_positions(
                        bundle, te_mask, out["va_t60"], out["te_t60"],
                        out["va_ml60"], out["te_ml60"], out["va_ms60"], out["te_ms60"],
                        step_bars=12, entry_q=eq_val, hold_q=hq_val, y1_cap_q=y1_val,
                    )
                    p_dual_g = 0.5 * p30_g + 0.5 * p60_g
                    g_res, _ = evaluate_position_path(bundle, te_mask, p_dual_g, one_way_cost_bp=0.5, leverage=1.0)
                    param_rows.append(
                        {
                            "year": yr,
                            "entry_q": eq_val,
                            "hold_q": hq_val,
                            "y1_cap_q": y1_val,
                            "total_return_pct": g_res["total_return_pct"],
                            "max_drawdown_pct": g_res["max_drawdown_pct"],
                            "sharpe_daily": g_res["sharpe_daily"],
                            "round_trips_equiv": g_res["round_trips_equiv"],
                            "avg_net_bp_per_rt": g_res["avg_net_bp_per_rt"],
                        }
                    )

    df_arch = pd.DataFrame(arch_rows)
    df_phys = pd.DataFrame(physics_rows)
    df_param = pd.DataFrame(param_rows)
    df_month = pd.DataFrame(monthly_records)

    df_arch.to_csv(RUNS_DIR / "phase2_architecture_comparison.csv", index=False)
    df_phys.to_csv(RUNS_DIR / "phase2_execution_physics_and_leverage.csv", index=False)
    df_param.to_csv(RUNS_DIR / "phase2_parameter_robustness_surface.csv", index=False)
    df_month.to_csv(RUNS_DIR / "phase2_monthly_returns.csv", index=False)

    # Summarize Parameter Robustness (% of grid cells profitable in 2025, 2026, and both)
    piv = df_param.pivot(index=["entry_q", "hold_q", "y1_cap_q"], columns="year", values="total_return_pct")
    both_pos = float(((piv[2025] > 0) & (piv[2026] > 0)).mean() * 100.0)
    pos_2025 = float((piv[2025] > 0).mean() * 100.0)
    pos_2026 = float((piv[2026] > 0).mean() * 100.0)

    summary_p2 = {
        "elapsed_seconds": round(time.time() - t0, 2),
        "param_grid_cells": len(piv),
        "pct_profitable_2025": round(pos_2025, 1),
        "pct_profitable_2026": round(pos_2026, 1),
        "pct_profitable_both_years": round(both_pos, 1),
    }
    with open(RUNS_DIR / "phase2_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary_p2, f, indent=2)

    print(f"=== PHASE 2 COMPLETED in {summary_p2['elapsed_seconds']}s ===")
    print("Parameter surface profitability:", summary_p2)


if __name__ == "__main__":
    main()
