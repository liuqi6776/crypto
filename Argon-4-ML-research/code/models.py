"""Multi-horizon Y0 (directional probability) and Y1 (volatility range & liquidation MAE) models.

Implements walk-forward training, validation calibration, out-of-sample evaluation for 2025 and 2026,
model-family comparison (HGB/XGB-hist, CatBoost, Ridge/Linear, GBDT Ensemble), target-definition
comparison (Sign > 0 vs Data-Balanced 65/35 Quantile Hurdle vs Regression), and feature-group ablation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier, CatBoostRegressor
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss, mean_absolute_error, roc_auc_score
from sklearn.preprocessing import StandardScaler

from research.zero_fee_maker_ml_v1.code.features import HORIZON_BARS, HORIZONS_MIN, DatasetBundle

PURGE_BARS = 24  # 2 hours (24 x 5m bars) strict purge between train/val and val/test


@dataclass
class WalkForwardFold:
    name: str
    year: int
    train_start: str
    train_end: str
    val_start: str
    val_end: str
    test_start: str
    test_end: str


FOLDS: Tuple[WalkForwardFold, ...] = (
    WalkForwardFold(
        name="fold_2025",
        year=2025,
        train_start="2024-01-05 00:00:00+00:00",
        train_end="2024-09-30 21:55:00+00:00",
        val_start="2024-10-01 00:00:00+00:00",
        val_end="2024-12-31 21:55:00+00:00",
        test_start="2025-01-01 00:00:00+00:00",
        test_end="2025-12-31 23:55:00+00:00",
    ),
    WalkForwardFold(
        name="fold_2026",
        year=2026,
        train_start="2024-01-05 00:00:00+00:00",
        train_end="2025-09-30 21:55:00+00:00",
        val_start="2025-10-01 00:00:00+00:00",
        val_end="2025-12-31 21:55:00+00:00",
        test_start="2026-01-01 00:00:00+00:00",
        test_end="2026-09-24 22:00:00+00:00",
    ),
)


@dataclass
class HorizonPredictions:
    horizon_min: int
    fold_name: str
    year: int
    tau_long: float
    tau_short: float
    # Validation arrays & indices
    val_mask: np.ndarray
    test_mask: np.ndarray
    # Predictions on validation set
    val_p_pos_hgb: np.ndarray
    val_p_pos_cat: np.ndarray
    val_p_pos_lin: np.ndarray
    val_p_pos_ens: np.ndarray
    val_score_tail_hgb: np.ndarray
    val_ret_pred_hgb: np.ndarray
    val_score_comp: np.ndarray
    val_y1_range_mean: np.ndarray
    val_y1_mae_long_q90: np.ndarray
    val_y1_mae_short_q90: np.ndarray
    # Predictions on test set
    test_p_pos_hgb: np.ndarray
    test_p_pos_cat: np.ndarray
    test_p_pos_lin: np.ndarray
    test_p_pos_ens: np.ndarray
    test_score_tail_hgb: np.ndarray
    test_ret_pred_hgb: np.ndarray
    test_score_comp: np.ndarray
    test_y1_range_mean: np.ndarray
    test_y1_mae_long_q90: np.ndarray
    test_y1_mae_short_q90: np.ndarray
    # Metrics dictionary
    metrics: Dict[str, float]
    top_features_y0: List[Tuple[str, float]]
    top_features_y1: List[Tuple[str, float]]


def _slice_mask(index: pd.DatetimeIndex, start: str, end: str, valid_y: np.ndarray) -> np.ndarray:
    t0 = pd.Timestamp(start)
    t1 = pd.Timestamp(end)
    return np.asarray((index >= t0) & (index <= t1) & valid_y, dtype=bool)


def _safe_spearman(x: np.ndarray, y: np.ndarray) -> float:
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 30:
        return 0.0
    r, _ = spearmanr(x[m], y[m])
    return float(0.0 if np.isnan(r) else r)


def _zscore_from_val(val_arr: np.ndarray, target_arr: np.ndarray) -> np.ndarray:
    mu = float(np.nanmean(val_arr))
    sd = float(np.nanstd(val_arr)) + 1e-12
    return (target_arr - mu) / sd


def train_and_evaluate_horizon(
    bundle: DatasetBundle,
    horizon_min: int,
    fold: WalkForwardFold,
    run_catboost: bool = True,
) -> HorizonPredictions:
    """Train Y0 and Y1 models for a given (symbol, horizon_min, fold) and evaluate on Val & Test."""
    X_all = bundle.features.to_numpy(dtype=np.float32)
    feat_names = list(bundle.features.columns)
    y0_all = bundle.y0_ret[horizon_min]
    y1_rng_all = bundle.y1_range[horizon_min]
    y1_ml_all = bundle.y1_mae_long[horizon_min]
    y1_ms_all = bundle.y1_mae_short[horizon_min]

    valid = np.isfinite(y0_all) & np.isfinite(y1_rng_all) & np.isfinite(y1_ml_all) & np.isfinite(y1_ms_all)
    tr_mask = _slice_mask(bundle.index, fold.train_start, fold.train_end, valid)
    va_mask = _slice_mask(bundle.index, fold.val_start, fold.val_end, valid)
    te_mask = _slice_mask(bundle.index, fold.test_start, fold.test_end, valid)

    X_tr, X_va, X_te = X_all[tr_mask], X_all[va_mask], X_all[te_mask]
    y0_tr, y0_va, y0_te = y0_all[tr_mask], y0_all[va_mask], y0_all[te_mask]
    y1_rng_tr, y1_rng_va, y1_rng_te = y1_rng_all[tr_mask], y1_rng_all[va_mask], y1_rng_all[te_mask]
    y1_ml_tr, y1_ml_va, y1_ml_te = y1_ml_all[tr_mask], y1_ml_all[va_mask], y1_ml_all[te_mask]
    y1_ms_tr, y1_ms_va, y1_ms_te = y1_ms_all[tr_mask], y1_ms_all[va_mask], y1_ms_all[te_mask]

    # Data-balanced thresholds on training set only:
    # 1. Sign > 0 (~50% positive)
    y_pos_tr = (y0_tr > 0.0).astype(np.int32)
    y_pos_va = (y0_va > 0.0).astype(np.int32)
    y_pos_te = (y0_te > 0.0).astype(np.int32)

    # 2. Balanced 35% tail hurdles (Q65 for long, Q35 for short)
    tau_long = float(np.quantile(y0_tr, 0.65))
    tau_short = float(np.quantile(y0_tr, 0.35))
    y_long_tr = (y0_tr > tau_long).astype(np.int32)
    y_short_tr = (y0_tr < tau_short).astype(np.int32)
    y_long_te = (y0_te > tau_long).astype(np.int32)
    y_short_te = (y0_te < tau_short).astype(np.int32)

    # --- Model 1A: HGB (XGBoost-hist equivalent) Sign Classifier ---
    clf_pos_hgb = HistGradientBoostingClassifier(
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
    clf_pos_hgb.fit(X_tr, y_pos_tr)
    va_p_pos_hgb = clf_pos_hgb.predict_proba(X_va)[:, 1]
    te_p_pos_hgb = clf_pos_hgb.predict_proba(X_te)[:, 1]

    # --- Model 1B: HGB Tail Hurdle Classifiers (Q65 Long & Q35 Short) ---
    clf_long_hgb = HistGradientBoostingClassifier(
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
    clf_short_hgb = HistGradientBoostingClassifier(
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
    clf_long_hgb.fit(X_tr, y_long_tr)
    clf_short_hgb.fit(X_tr, y_short_tr)
    va_p_long = clf_long_hgb.predict_proba(X_va)[:, 1]
    va_p_short = clf_short_hgb.predict_proba(X_va)[:, 1]
    te_p_long = clf_long_hgb.predict_proba(X_te)[:, 1]
    te_p_short = clf_short_hgb.predict_proba(X_te)[:, 1]
    va_score_tail_hgb = va_p_long - va_p_short
    te_score_tail_hgb = te_p_long - te_p_short

    # --- Model 1C: HGB Expected Return Regressor (clipped at 3x Q99 to prevent outlier distortion) ---
    clip_lim = float(np.quantile(np.abs(y0_tr), 0.995))
    y0_tr_clip = np.clip(y0_tr, -clip_lim, clip_lim)
    reg_y0_hgb = HistGradientBoostingRegressor(
        loss="squared_error",
        max_iter=160,
        learning_rate=0.04,
        max_leaf_nodes=15,
        min_samples_leaf=300,
        l2_regularization=15.0,
        early_stopping=True,
        validation_fraction=0.12,
        n_iter_no_change=20,
        random_state=45,
    )
    reg_y0_hgb.fit(X_tr, y0_tr_clip)
    va_ret_pred_hgb = reg_y0_hgb.predict(X_va)
    te_ret_pred_hgb = reg_y0_hgb.predict(X_te)

    # --- Model 2: CatBoost Classifier (Symmetric Tree GBDT) ---
    if run_catboost:
        clf_pos_cat = CatBoostClassifier(
            iterations=160,
            learning_rate=0.05,
            depth=5,
            l2_leaf_reg=15.0,
            random_seed=42,
            thread_count=8,
            verbose=False,
        )
        clf_pos_cat.fit(X_tr[::2], y_pos_tr[::2], eval_set=(X_va[::2], y_pos_va[::2]), early_stopping_rounds=20, verbose=False)
        va_p_pos_cat = clf_pos_cat.predict_proba(X_va)[:, 1]
        te_p_pos_cat = clf_pos_cat.predict_proba(X_te)[:, 1]
        fi_y0 = clf_pos_cat.get_feature_importance()
    else:
        va_p_pos_cat = va_p_pos_hgb.copy()
        te_p_pos_cat = te_p_pos_hgb.copy()
        fi_y0 = np.zeros(len(feat_names))

    # --- Model 3: L2 Linear / Ridge Baseline ---
    scaler = StandardScaler()
    # Subsample every 2nd bar on train for fast linear fit if large
    X_tr_sc = scaler.fit_transform(np.nan_to_num(X_tr, nan=0.0, posinf=0.0, neginf=0.0))
    X_va_sc = scaler.transform(np.nan_to_num(X_va, nan=0.0, posinf=0.0, neginf=0.0))
    X_te_sc = scaler.transform(np.nan_to_num(X_te, nan=0.0, posinf=0.0, neginf=0.0))
    lin_reg = Ridge(alpha=5000.0, random_state=42)
    lin_reg.fit(X_tr_sc, y0_tr_clip)
    va_lin_raw = lin_reg.predict(X_va_sc)
    te_lin_raw = lin_reg.predict(X_te_sc)
    # Convert linear return prediction into calibrated probability around 0.5
    lin_scale = float(np.std(va_lin_raw)) + 1e-12
    va_p_pos_lin = 1.0 / (1.0 + np.exp(-0.25 * (va_lin_raw / lin_scale)))
    te_p_pos_lin = 1.0 / (1.0 + np.exp(-0.25 * (te_lin_raw / lin_scale)))

    # --- Ensemble GBDT & Composite Directional Score ---
    va_p_pos_ens = 0.5 * va_p_pos_hgb + 0.5 * va_p_pos_cat
    te_p_pos_ens = 0.5 * te_p_pos_hgb + 0.5 * te_p_pos_cat

    va_score_comp = (
        0.40 * _zscore_from_val(va_p_pos_ens, va_p_pos_ens)
        + 0.35 * _zscore_from_val(va_score_tail_hgb, va_score_tail_hgb)
        + 0.25 * _zscore_from_val(va_ret_pred_hgb, va_ret_pred_hgb)
    )
    te_score_comp = (
        0.40 * _zscore_from_val(va_p_pos_ens, te_p_pos_ens)
        + 0.35 * _zscore_from_val(va_score_tail_hgb, te_score_tail_hgb)
        + 0.25 * _zscore_from_val(va_ret_pred_hgb, te_ret_pred_hgb)
    )

    # --- Y1 Volatility Range & Liquidation Risk Models ---
    # 1. Expected Range Regressor (Mean)
    reg_y1_rng = HistGradientBoostingRegressor(
        loss="squared_error",
        max_iter=160,
        learning_rate=0.05,
        max_leaf_nodes=15,
        min_samples_leaf=250,
        l2_regularization=10.0,
        early_stopping=True,
        validation_fraction=0.12,
        n_iter_no_change=20,
        random_state=51,
    )
    reg_y1_rng.fit(X_tr, np.clip(y1_rng_tr, 0.0, np.quantile(y1_rng_tr, 0.998)))
    va_y1_rng_mean = np.clip(reg_y1_rng.predict(X_va), 1e-4, 0.25)
    te_y1_rng_mean = np.clip(reg_y1_rng.predict(X_te), 1e-4, 0.25)

    # 2. 90th-Percentile Adverse Excursion (Quantile 0.90) for Long & Short Liquidation Gate
    # Fit on stride-2 subsample for fast exact quantile tree splitting
    reg_y1_ml_q90 = HistGradientBoostingRegressor(
        loss="quantile",
        quantile=0.90,
        max_iter=120,
        learning_rate=0.05,
        max_leaf_nodes=15,
        min_samples_leaf=250,
        l2_regularization=10.0,
        early_stopping=True,
        validation_fraction=0.12,
        n_iter_no_change=15,
        random_state=52,
    )
    reg_y1_ms_q90 = HistGradientBoostingRegressor(
        loss="quantile",
        quantile=0.90,
        max_iter=120,
        learning_rate=0.05,
        max_leaf_nodes=15,
        min_samples_leaf=250,
        l2_regularization=10.0,
        early_stopping=True,
        validation_fraction=0.12,
        n_iter_no_change=15,
        random_state=53,
    )
    reg_y1_ml_q90.fit(X_tr[::2], y1_ml_tr[::2])
    reg_y1_ms_q90.fit(X_tr[::2], y1_ms_tr[::2])
    va_y1_ml_q90 = np.clip(reg_y1_ml_q90.predict(X_va), 1e-4, 0.30)
    te_y1_ml_q90 = np.clip(reg_y1_ml_q90.predict(X_te), 1e-4, 0.30)
    va_y1_ms_q90 = np.clip(reg_y1_ms_q90.predict(X_va), 1e-4, 0.30)
    te_y1_ms_q90 = np.clip(reg_y1_ms_q90.predict(X_te), 1e-4, 0.30)

    # Feature importance for Y1 (via fast CatBoostRegressor or correlation proxy if skipped)
    if run_catboost:
        cb_y1 = CatBoostRegressor(
            iterations=120,
            learning_rate=0.06,
            depth=5,
            l2_leaf_reg=12.0,
            random_seed=54,
            thread_count=8,
            verbose=False,
        )
        cb_y1.fit(X_tr[::3], y1_rng_tr[::3], verbose=False)
        fi_y1 = cb_y1.get_feature_importance()
    else:
        fi_y1 = np.zeros(len(feat_names))

    top_y0_idx = np.argsort(fi_y0)[::-1][:15]
    top_y1_idx = np.argsort(fi_y1)[::-1][:15]
    top_features_y0 = [(feat_names[i], float(fi_y0[i])) for i in top_y0_idx]
    top_features_y1 = [(feat_names[i], float(fi_y1[i])) for i in top_y1_idx]

    # Top-decile vs Bottom-decile spread on Test (in basis points per horizon bar)
    q90_sc = float(np.quantile(va_score_comp, 0.90))
    q10_sc = float(np.quantile(va_score_comp, 0.10))
    q95_sc = float(np.quantile(va_score_comp, 0.95))
    q05_sc = float(np.quantile(va_score_comp, 0.05))

    long_d10 = y0_te[te_score_comp >= q90_sc]
    short_d10 = -y0_te[te_score_comp <= q10_sc]
    long_d05 = y0_te[te_score_comp >= q95_sc]
    short_d05 = -y0_te[te_score_comp <= q05_sc]

    metrics = {
        "n_train": int(tr_mask.sum()),
        "n_val": int(va_mask.sum()),
        "n_test": int(te_mask.sum()),
        "tau_long_bp": float(tau_long * 1e4),
        "tau_short_bp": float(tau_short * 1e4),
        # Validation Y0 metrics
        "val_auc_pos_hgb": float(roc_auc_score(y_pos_va, va_p_pos_hgb)),
        "val_auc_pos_cat": float(roc_auc_score(y_pos_va, va_p_pos_cat)),
        "val_auc_pos_lin": float(roc_auc_score(y_pos_va, va_p_pos_lin)),
        "val_auc_pos_ens": float(roc_auc_score(y_pos_va, va_p_pos_ens)),
        "val_ic_comp": _safe_spearman(va_score_comp, y0_va),
        # Test Y0 metrics
        "test_auc_pos_hgb": float(roc_auc_score(y_pos_te, te_p_pos_hgb)),
        "test_auc_pos_cat": float(roc_auc_score(y_pos_te, te_p_pos_cat)),
        "test_auc_pos_lin": float(roc_auc_score(y_pos_te, te_p_pos_lin)),
        "test_auc_pos_ens": float(roc_auc_score(y_pos_te, te_p_pos_ens)),
        "test_auc_tail_long_hgb": float(roc_auc_score(y_long_te, te_p_long)),
        "test_auc_tail_short_hgb": float(roc_auc_score(y_short_te, te_p_short)),
        "test_brier_pos_ens": float(brier_score_loss(y_pos_te, te_p_pos_ens)),
        "test_ic_pos_hgb": _safe_spearman(te_p_pos_hgb, y0_te),
        "test_ic_pos_cat": _safe_spearman(te_p_pos_cat, y0_te),
        "test_ic_pos_lin": _safe_spearman(te_p_pos_lin, y0_te),
        "test_ic_tail_hgb": _safe_spearman(te_score_tail_hgb, y0_te),
        "test_ic_ret_hgb": _safe_spearman(te_ret_pred_hgb, y0_te),
        "test_ic_comp": _safe_spearman(te_score_comp, y0_te),
        # Top-decile / Top-5% gross return edge (in basis points)
        "test_top10_long_mean_bp": float(np.mean(long_d10) * 1e4) if len(long_d10) else 0.0,
        "test_bot10_short_mean_bp": float(np.mean(short_d10) * 1e4) if len(short_d10) else 0.0,
        "test_top10_combined_edge_bp": float(
            (np.sum(long_d10) + np.sum(short_d10)) / max(1, len(long_d10) + len(short_d10)) * 1e4
        ),
        "test_top05_combined_edge_bp": float(
            (np.sum(long_d05) + np.sum(short_d05)) / max(1, len(long_d05) + len(short_d05)) * 1e4
        ),
        "test_top05_win_rate": float(
            (np.sum(long_d05 > 0) + np.sum(short_d05 > 0)) / max(1, len(long_d05) + len(short_d05))
        ),
        # Y1 Volatility & Liquidation MAE metrics on Test
        "test_y1_range_ic": _safe_spearman(te_y1_rng_mean, y1_rng_te),
        "test_y1_range_mae_bp": float(mean_absolute_error(y1_rng_te, te_y1_rng_mean) * 1e4),
        "test_y1_mae_long_q90_ic": _safe_spearman(te_y1_ml_q90, y1_ml_te),
        "test_y1_mae_short_q90_ic": _safe_spearman(te_y1_ms_q90, y1_ms_te),
        "test_y1_mae_long_q90_exceed_rate": float(np.mean(y1_ml_te > te_y1_ml_q90)),
        "test_y1_mae_short_q90_exceed_rate": float(np.mean(y1_ms_te > te_y1_ms_q90)),
    }

    return HorizonPredictions(
        horizon_min=horizon_min,
        fold_name=fold.name,
        year=fold.year,
        tau_long=tau_long,
        tau_short=tau_short,
        val_mask=va_mask,
        test_mask=te_mask,
        val_p_pos_hgb=va_p_pos_hgb,
        val_p_pos_cat=va_p_pos_cat,
        val_p_pos_lin=va_p_pos_lin,
        val_p_pos_ens=va_p_pos_ens,
        val_score_tail_hgb=va_score_tail_hgb,
        val_ret_pred_hgb=va_ret_pred_hgb,
        val_score_comp=va_score_comp,
        val_y1_range_mean=va_y1_rng_mean,
        val_y1_mae_long_q90=va_y1_ml_q90,
        val_y1_mae_short_q90=va_y1_ms_q90,
        test_p_pos_hgb=te_p_pos_hgb,
        test_p_pos_cat=te_p_pos_cat,
        test_p_pos_lin=te_p_pos_lin,
        test_p_pos_ens=te_p_pos_ens,
        test_score_tail_hgb=te_score_tail_hgb,
        test_ret_pred_hgb=te_ret_pred_hgb,
        test_score_comp=te_score_comp,
        test_y1_range_mean=te_y1_rng_mean,
        test_y1_mae_long_q90=te_y1_ml_q90,
        test_y1_mae_short_q90=te_y1_ms_q90,
        metrics=metrics,
        top_features_y0=top_features_y0,
        top_features_y1=top_features_y1,
    )


def run_feature_group_ablation(
    bundle: DatasetBundle,
    horizon_min: int = 30,
) -> List[Dict[str, object]]:
    """Progressive feature-group ablation on both 2025 and 2026 OOS folds."""
    ordered_groups = [
        ("G1_OWN_PRICE", ["OWN_PRICE"]),
        ("G1+G2_CROSS_ASSET", ["OWN_PRICE", "CROSS_ASSET"]),
        ("G1..G3_+ORDER_FLOW", ["OWN_PRICE", "CROSS_ASSET", "ORDER_FLOW_SENTIMENT"]),
        ("G1..G4_+FUNDING_BASIS", ["OWN_PRICE", "CROSS_ASSET", "ORDER_FLOW_SENTIMENT", "FUNDING_BASIS"]),
        ("G1..G5_ALL_+OPTIONS_DVOL", ["OWN_PRICE", "CROSS_ASSET", "ORDER_FLOW_SENTIMENT", "FUNDING_BASIS", "OPTIONS_DVOL"]),
        ("ONLY_ORDER_FLOW_SENTIMENT", ["ORDER_FLOW_SENTIMENT"]),
        ("ONLY_CROSS_ASSET", ["CROSS_ASSET"]),
        ("ONLY_FUNDING_BASIS_DVOL", ["FUNDING_BASIS", "OPTIONS_DVOL"]),
    ]

    results: List[Dict[str, object]] = []
    y0_all = bundle.y0_ret[horizon_min]
    y1_rng_all = bundle.y1_range[horizon_min]
    valid = np.isfinite(y0_all) & np.isfinite(y1_rng_all)

    for stage_name, g_list in ordered_groups:
        cols: List[str] = []
        for g in g_list:
            cols.extend(bundle.feature_groups[g])
        X_sub = bundle.features[cols].to_numpy(dtype=np.float32)

        row: Dict[str, object] = {
            "target_symbol": bundle.target_symbol,
            "horizon_min": horizon_min,
            "stage": stage_name,
            "n_features": len(cols),
        }
        for fold in FOLDS:
            tr_mask = _slice_mask(bundle.index, fold.train_start, fold.train_end, valid)
            te_mask = _slice_mask(bundle.index, fold.test_start, fold.test_end, valid)
            X_tr, X_te = X_sub[tr_mask], X_sub[te_mask]
            y_pos_tr = (y0_all[tr_mask] > 0.0).astype(np.int32)
            y_pos_te = (y0_all[te_mask] > 0.0).astype(np.int32)
            y0_te = y0_all[te_mask]

            clf = HistGradientBoostingClassifier(
                max_iter=140,
                learning_rate=0.04,
                max_leaf_nodes=15,
                min_samples_leaf=300,
                l2_regularization=10.0,
                early_stopping=True,
                validation_fraction=0.12,
                n_iter_no_change=20,
                random_state=42,
            )
            clf.fit(X_tr, y_pos_tr)
            p_te = clf.predict_proba(X_te)[:, 1]
            row[f"auc_{fold.year}"] = float(roc_auc_score(y_pos_te, p_te))
            row[f"ic_{fold.year}"] = _safe_spearman(p_te, y0_te)
            q95 = float(np.quantile(p_te, 0.95))
            q05 = float(np.quantile(p_te, 0.05))
            edge_bp = (np.mean(y0_te[p_te >= q95]) - np.mean(y0_te[p_te <= q05])) * 0.5 * 1e4
            row[f"top5_edge_bp_{fold.year}"] = float(edge_bp)
        results.append(row)
    return results
