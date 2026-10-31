"""Self-contained Causal Live Signal & State Engine for the 0-Fee Maker BTCUSDT Master Ensemble.

Compliance Note (AGENTS.md Constraint #1):
- Contains NO API keys, NO exchange network calls, NO order placement, and NO live trading daemon.
- Provides a deterministic, state-tracked inference & target-position generator (`ZeroFeeMakerMasterEngine`)
  and exports the trained latest model bundle (`runs/latest_live_model_manifest.json`) so an external
  execution wrapper or shadow-live observer (Gate 8) can query exact 5m target weights and Y1 risk caps.
"""
from __future__ import annotations

import hashlib
import json
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from research.zero_fee_maker_ml_v1.code.features import ROOT, DatasetBundle, build_dataset_bundle
from research.zero_fee_maker_ml_v1.code.models import _slice_mask, _zscore_from_val

RUNS_DIR = ROOT / "research" / "zero_fee_maker_ml_v1" / "runs"
LATEST_BUNDLE_PATH = RUNS_DIR / "latest_live_model_bundle.pkl"


@dataclass
class SubBookThresholds:
    th_long_entry: float
    th_short_entry: float
    th_long_hold: float
    th_short_hold: float
    y1_cap_long: float
    y1_cap_short: float
    step_bars: int


@dataclass
class LiveSignalPacket:
    strategy_mode: str                     # "M2_4ENGINE_SUBBOOK_NETTING" (default) or "M3_HYBRID_MASTER_LIVE"
    nominal_leverage: float                # Default 3.0x
    bar_open_time_utc: str
    decision_time_utc: str
    btc_close_price: float
    target_position_fraction: float        # Unlevered net weight in [-1.0, +1.0]
    target_leveraged_exposure: float       # Leveraged exposure in [-3.0, +3.0] (= target_position_fraction * nominal_leverage)
    raw_unbuffered_position: float
    delta_position_to_trade: float         # Unlevered delta in [-2.0, +2.0]
    delta_leveraged_exposure_to_trade: float  # Leveraged delta in [-6.0, +6.0]
    engine_4_allocations: Dict[str, float] # E1 (25%), E2 (25%), E3 (25%), E4 (25%)
    subbook_positions: Dict[str, float]
    component_zscores: Dict[str, float]
    predicted_y1_mae_long_30m_bp: float
    predicted_y1_mae_short_30m_bp: float
    predicted_y1_mae_long_60m_bp: float
    predicted_y1_mae_short_60m_bp: float
    y1_risk_gate_passed: bool
    recommended_max_leverage: float
    execution_instruction: str
    bar_open_time_bjt: str = ""
    decision_time_bjt: str = ""


@dataclass
class SubBookState:
    current_side: int = 0
    bars_held_in_step: int = 0
    total_bars_held: int = 0

    def step_update(
        self,
        score: float,
        y1_l: float,
        y1_s: float,
        cfg: SubBookThresholds,
    ) -> int:
        if self.current_side == 0:
            if score >= cfg.th_long_entry and y1_l <= cfg.y1_cap_long:
                self.current_side = 1
                self.bars_held_in_step = 1
                self.total_bars_held = 1
            elif score <= cfg.th_short_entry and y1_s <= cfg.y1_cap_short:
                self.current_side = -1
                self.bars_held_in_step = 1
                self.total_bars_held = 1
            return self.current_side

        # Currently holding a position: check if current step_bars block has completed
        if self.bars_held_in_step < cfg.step_bars:
            self.bars_held_in_step += 1
            self.total_bars_held += 1
            return self.current_side

        # At step boundary: check hysteresis hold condition and 96-bar (8h) max hold cap
        y1_now = y1_l if self.current_side == 1 else y1_s
        y1_cap = cfg.y1_cap_long if self.current_side == 1 else cfg.y1_cap_short
        keep = (
            (self.current_side == 1 and score >= cfg.th_long_hold)
            or (self.current_side == -1 and score <= cfg.th_short_hold)
        ) and (y1_now <= y1_cap * 1.15) and (self.total_bars_held < 96)

        if keep:
            self.bars_held_in_step = 1
            self.total_bars_held += 1
            return self.current_side

        # Otherwise exit and immediately check if a fresh entry is triggered
        self.current_side = 0
        self.bars_held_in_step = 0
        self.total_bars_held = 0
        if score >= cfg.th_long_entry and y1_l <= cfg.y1_cap_long:
            self.current_side = 1
            self.bars_held_in_step = 1
            self.total_bars_held = 1
        elif score <= cfg.th_short_entry and y1_s <= cfg.y1_cap_short:
            self.current_side = -1
            self.bars_held_in_step = 1
            self.total_bars_held = 1
        return self.current_side


class ZeroFeeMakerMasterEngine:
    """Deterministic causal inference & multi-sub-book state machine for 0-Fee Maker BTCUSDT.

    Default production configuration locked to:
    - strategy_mode = "M2" (M2_4ENGINE_SUBBOOK_NETTING: 25% E1 + 25% E2 + 25% E3 + 25% E4)
    - nominal_leverage = 3.0 (3.0X nominal leverage; 0.0 min_rebalance_delta for pure M2 bar netting)
    """

    def __init__(
        self,
        model_artifact: Dict[str, object],
        strategy_mode: str = "M2",
        nominal_leverage: float = 3.0,
        min_rebalance_delta: float = 0.0,
    ) -> None:
        self.art = model_artifact
        self.strategy_mode = strategy_mode.upper()
        self.nominal_leverage = float(nominal_leverage)
        self.feature_cols: List[str] = list(model_artifact["feature_cols"])
        self.min_rebalance_delta = min_rebalance_delta
        self.current_net_position: float = 0.0
        self.subbooks: Dict[str, SubBookState] = {
            "SB1_30M_SIGN_HGB": SubBookState(),
            "SB2_30M_60M_JOINT_HGB": SubBookState(),
            "SB3_15M_RIDGE_LIN": SubBookState(),
            "SB4_30M_RIDGE_BLEND": SubBookState(),
            "SB5_META_30M": SubBookState(),
            "SB6_META_60M": SubBookState(),
            "SB7_60M_TAIL_HGB": SubBookState(),
        }

    def _standardize(self, val: float, key: str) -> float:
        stats = self.art["val_norm_stats"][key]
        return (val - stats["mean"]) / (stats["std"] + 1e-12)

    def on_new_5m_bar(
        self,
        bar_open_time: pd.Timestamp,
        btc_close_price: float,
        feature_row: np.ndarray,
        fib_feature_row: Optional[np.ndarray] = None,
        e4_pos_override: Optional[float] = None,
    ) -> LiveSignalPacket:
        """Process one newly closed 5m feature vector and optional Phase 5 Fibonacci vector."""
        x_2d = np.asarray(feature_row, dtype=np.float32).reshape(1, -1)
        x_clean = np.nan_to_num(x_2d, nan=0.0, posinf=0.0, neginf=0.0)

        # 1. Raw model predictions
        p_s30 = float(self.art["clf_sign30"].predict_proba(x_2d)[0, 1])
        p_t60 = float(
            self.art["clf_l60"].predict_proba(x_2d)[0, 1]
            - self.art["clf_s60"].predict_proba(x_2d)[0, 1]
        )

        x_sc = self.art["scaler"].transform(x_clean)
        z_lin15 = self._standardize(float(self.art["ridge_15"].predict(x_sc)[0]), "lin15")
        z_lin30 = self._standardize(float(self.art["ridge_30"].predict(x_sc)[0]), "lin30")
        z_lin60 = self._standardize(float(self.art["ridge_60"].predict(x_sc)[0]), "lin60")
        z_lin_blend = 0.30 * z_lin15 + 0.40 * z_lin30 + 0.30 * z_lin60

        z_s30 = self._standardize(p_s30, "s30")
        z_t60 = self._standardize(p_t60, "t60")
        z_joint_raw = 0.50 * z_s30 + 0.50 * z_t60
        z_joint = (
            self._standardize(z_joint_raw, "joint")
            if "joint" in self.art.get("val_norm_stats", {})
            else z_joint_raw
        )
        z_meta = 0.40 * z_s30 + 0.30 * z_t60 + 0.30 * z_lin_blend

        # Phase 5 Causal Fibonacci (0.236/0.382) + Stop/Target Protection + RSI Layer Specialist
        z_fib = 0.0
        fib_telemetry: Dict[str, float] = {}
        if fib_feature_row is not None and "fib_ridge_30" in self.art and "fib_scaler" in self.art:
            f_2d = np.nan_to_num(
                np.asarray(fib_feature_row, dtype=np.float32).reshape(1, -1),
                nan=0.0,
                posinf=0.0,
                neginf=0.0,
            )
            f_sc = self.art["fib_scaler"].transform(f_2d)
            zf30 = self._standardize(float(self.art["fib_ridge_30"].predict(f_sc)[0]), "fib30")
            zf60 = self._standardize(float(self.art["fib_ridge_60"].predict(f_sc)[0]), "fib60")
            z_fib = 0.50 * zf30 + 0.50 * zf60
            w_fib = float(self.art.get("fib_overlay_weight", 0.15))
            w_e2 = 0.80 * w_fib
            blend_mode = str(self.art.get("fib_blend_mode", "ADDITIVE"))
            if blend_mode == "ADDITIVE":
                z_joint_eff = z_joint + w_e2 * z_fib
                z_lin15_eff = z_lin15 + w_fib * z_fib
                z_lin_blend_eff = z_lin_blend + w_fib * z_fib
            else:
                z_joint_eff = (1.0 - w_e2) * z_joint + w_e2 * z_fib
                z_lin15_eff = (1.0 - w_fib) * z_lin15 + w_fib * z_fib
                z_lin_blend_eff = (1.0 - w_fib) * z_lin_blend + w_fib * z_fib

            fib_col_map: Dict[str, int] = self.art.get("fib_col_index", {})
            f_1d = f_2d[0]
            fib_telemetry = {
                "z_fib_5m_1h_specialist": round(z_fib, 3),
                "fib_1h_active_rr_net": round(float(f_1d[fib_col_map["net_fib_active_rr_1h"]]), 3)
                if "net_fib_active_rr_1h" in fib_col_map
                else 0.0,
                "fib_1h_rsi_res_net": round(float(f_1d[fib_col_map["net_fib_res_active_1h"]]), 3)
                if "net_fib_res_active_1h" in fib_col_map
                else 0.0,
                "fib_5m_active_rr_net": round(float(f_1d[fib_col_map["net_fib_active_rr_5m"]]), 3)
                if "net_fib_active_rr_5m" in fib_col_map
                else 0.0,
                "fib_stop_protect_net": round(
                    float(
                        f_1d[fib_col_map.get("net_fib_stop_break_1h", 0)]
                        + 0.5 * f_1d[fib_col_map.get("net_fib_stop_break_5m", 0)]
                    ),
                    3,
                )
                if "net_fib_stop_break_1h" in fib_col_map
                else 0.0,
            }
        else:
            z_joint_eff = z_joint
            z_lin15_eff = z_lin15
            z_lin_blend_eff = z_lin_blend

        # 2. Y1 90th-percentile adverse excursion predictions
        y1_ml30 = float(np.clip(self.art["reg_ml30"].predict(x_2d)[0], 1e-4, 0.30))
        y1_ms30 = float(np.clip(self.art["reg_ms30"].predict(x_2d)[0], 1e-4, 0.30))
        y1_ml60 = float(np.clip(self.art["reg_ml60"].predict(x_2d)[0], 1e-4, 0.30))
        y1_ms60 = float(np.clip(self.art["reg_ms60"].predict(x_2d)[0], 1e-4, 0.30))

        # 3. Update each sub-book state machine
        cfgs: Dict[str, SubBookThresholds] = self.art["thresholds"]
        sb_out = {
            "SB1_30M_SIGN_HGB": float(self.subbooks["SB1_30M_SIGN_HGB"].step_update(p_s30, y1_ml30, y1_ms30, cfgs["SB1_30M_SIGN_HGB"])),
            "SB2_30M_60M_JOINT_HGB": float(self.subbooks["SB2_30M_60M_JOINT_HGB"].step_update(z_joint_eff, y1_ml60, y1_ms60, cfgs["SB2_30M_60M_JOINT_HGB"])),
            "SB3_15M_RIDGE_LIN": float(self.subbooks["SB3_15M_RIDGE_LIN"].step_update(z_lin15_eff, y1_ml30, y1_ms30, cfgs["SB3_15M_RIDGE_LIN"])),
            "SB4_30M_RIDGE_BLEND": float(self.subbooks["SB4_30M_RIDGE_BLEND"].step_update(z_lin_blend_eff, y1_ml30, y1_ms30, cfgs["SB4_30M_RIDGE_BLEND"])),
            "SB5_META_30M": float(self.subbooks["SB5_META_30M"].step_update(z_meta, y1_ml30, y1_ms30, cfgs["SB5_META_30M"])),
            "SB6_META_60M": float(self.subbooks["SB6_META_60M"].step_update(z_meta, y1_ml60, y1_ms60, cfgs["SB6_META_60M"])),
            "SB7_60M_TAIL_HGB": float(self.subbooks["SB7_60M_TAIL_HGB"].step_update(p_t60, y1_ml60, y1_ms60, cfgs["SB7_60M_TAIL_HGB"])),
        }

        # 4 Orthogonal Engines of M2_4ENGINE_SUBBOOK_NETTING (25% each):
        e1_pos = sb_out["SB1_30M_SIGN_HGB"]
        e2_pos = sb_out["SB2_30M_60M_JOINT_HGB"]
        e3_pos = 0.50 * sb_out["SB3_15M_RIDGE_LIN"] + 0.50 * sb_out["SB4_30M_RIDGE_BLEND"]
        e4_pos = (
            float(e4_pos_override)
            if e4_pos_override is not None
            else (0.50 * sb_out["SB1_30M_SIGN_HGB"] + 0.50 * sb_out["SB7_60M_TAIL_HGB"])
        )
        m2_pos = 0.25 * e1_pos + 0.25 * e2_pos + 0.25 * e3_pos + 0.25 * e4_pos
        m1_pos = 0.50 * sb_out["SB5_META_30M"] + 0.50 * sb_out["SB6_META_60M"]

        if self.strategy_mode == "M2":
            raw_pos = round(float(np.clip(m2_pos, -1.0, 1.0)), 4)
            mode_label = (
                "M2_FIB_5M_1H_PROTECTED_NETTING"
                if "fib_ridge_30" in self.art and fib_feature_row is not None
                else "M2_4ENGINE_SUBBOOK_NETTING"
            )
        else:
            raw_pos = round(float(np.clip(0.50 * m1_pos + 0.50 * m2_pos, -1.0, 1.0)), 4)
            mode_label = "M3_HYBRID_MASTER_LIVE"

        if abs(raw_pos) < 1e-6:
            target_pos = 0.0
        elif self.min_rebalance_delta <= 1e-6 or abs(raw_pos - self.current_net_position) >= self.min_rebalance_delta:
            target_pos = raw_pos
        else:
            target_pos = self.current_net_position

        delta_pos = round(target_pos - self.current_net_position, 4)
        self.current_net_position = target_pos

        target_lev_exp = round(target_pos * self.nominal_leverage, 4)
        delta_lev_exp = round(delta_pos * self.nominal_leverage, 4)

        worst_y1_60 = max(y1_ml60, y1_ms60)
        gate_ok = bool(
            y1_ml60 <= cfgs["SB7_60M_TAIL_HGB"].y1_cap_long
            and y1_ms60 <= cfgs["SB7_60M_TAIL_HGB"].y1_cap_short
        )
        rec_max_lev = round(float(np.clip(0.015 / max(worst_y1_60, 1e-4), 1.0, 3.0)), 2)

        if abs(delta_pos) < 1e-6:
            instr = f"HOLD_CURRENT_POSITION (Target: {target_lev_exp:+.3f}X equity; 0 order required)"
        elif delta_pos > 0:
            instr = (
                f"POST_ONLY_JOIN_BEST_BID (Buy {delta_lev_exp:+.3f}X equity -> Net {target_lev_exp:+.3f}X; "
                f"auto-repeg if unfilled in 10s)"
            )
        else:
            instr = (
                f"POST_ONLY_JOIN_BEST_ASK (Sell {delta_lev_exp:+.3f}X equity -> Net {target_lev_exp:+.3f}X; "
                f"auto-repeg if unfilled in 10s)"
            )

        decision_ts = bar_open_time + pd.Timedelta(minutes=5)
        bjt_open_ts = (
            bar_open_time.tz_convert("Asia/Shanghai")
            if bar_open_time.tzinfo is not None
            else bar_open_time.tz_localize("UTC").tz_convert("Asia/Shanghai")
        )
        bjt_dec_ts = bjt_open_ts + pd.Timedelta(minutes=5)
        comp_zs = {
            "z_s30_hgb": round(z_s30, 3),
            "z_t60_hgb": round(z_t60, 3),
            "z_lin_blend": round(z_lin_blend, 3),
            "z_meta_composite": round(z_meta, 3),
        }
        comp_zs.update(fib_telemetry)

        return LiveSignalPacket(
            strategy_mode=mode_label,
            nominal_leverage=self.nominal_leverage,
            bar_open_time_utc=str(bar_open_time),
            decision_time_utc=str(decision_ts),
            btc_close_price=round(float(btc_close_price), 2),
            target_position_fraction=target_pos,
            target_leveraged_exposure=target_lev_exp,
            raw_unbuffered_position=raw_pos,
            delta_position_to_trade=delta_pos,
            delta_leveraged_exposure_to_trade=delta_lev_exp,
            engine_4_allocations={
                "E1_30M_SIGN_HGB": round(e1_pos, 3),
                "E2_30M_60M_JOINT_HGB": round(e2_pos, 3),
                "E3_MULTI_HORIZON_RIDGE": round(e3_pos, 3),
                "E4_QUARTERLY_DUAL_HGB": round(e4_pos, 3),
            },
            subbook_positions=sb_out,
            component_zscores=comp_zs,
            predicted_y1_mae_long_30m_bp=round(y1_ml30 * 1e4, 2),
            predicted_y1_mae_short_30m_bp=round(y1_ms30 * 1e4, 2),
            predicted_y1_mae_long_60m_bp=round(y1_ml60 * 1e4, 2),
            predicted_y1_mae_short_60m_bp=round(y1_ms60 * 1e4, 2),
            y1_risk_gate_passed=gate_ok,
            recommended_max_leverage=rec_max_lev,
            execution_instruction=instr,
            bar_open_time_bjt=str(bjt_open_ts),
            decision_time_bjt=str(bjt_dec_ts),
        )


def train_and_export_latest_live_bundle(
    bundle: Optional[DatasetBundle] = None,
    train_start: str = "2024-01-05 00:00:00+00:00",
    train_end: str = "2026-06-30 21:55:00+00:00",
    val_start: str = "2026-07-01 00:00:00+00:00",
    val_end: str = "2026-09-23 21:55:00+00:00",
    entry_q: float = 0.92,
    hold_q: float = 0.58,
    y1_cap_q: float = 0.85,
    fib_features_df: Optional[pd.DataFrame] = None,
    fib_overlay_weight: float = 0.15,
    export_path: Optional[Path] = None,
) -> Tuple[ZeroFeeMakerMasterEngine, Path]:
    """Fit the complete Master Ensemble (+ optional Phase 5 Fibonacci 5m/1h Specialist) and export a bundle."""
    if bundle is None:
        bundle = build_dataset_bundle("BTCUSDT")

    X_all = bundle.features.to_numpy(dtype=np.float32)
    y15 = bundle.y0_ret[15]
    y30 = bundle.y0_ret[30]
    y60 = bundle.y0_ret[60]
    y1_ml30 = bundle.y1_mae_long[30]
    y1_ms30 = bundle.y1_mae_short[30]
    y1_ml60 = bundle.y1_mae_long[60]
    y1_ms60 = bundle.y1_mae_short[60]

    valid_gbdt = (
        np.isfinite(y30)
        & np.isfinite(y60)
        & np.isfinite(y1_ml30)
        & np.isfinite(y1_ms30)
        & np.isfinite(y1_ml60)
        & np.isfinite(y1_ms60)
    )
    tr_mask = _slice_mask(bundle.index, train_start, train_end, valid_gbdt)
    va_mask = _slice_mask(bundle.index, val_start, val_end, valid_gbdt)

    X_tr, X_va = X_all[tr_mask], X_all[va_mask]

    def _fit_hgb_clf_model_purged_chrono(X_train: np.ndarray, y_train: np.ndarray, seed: int) -> HistGradientBoostingClassifier:
        n_tr = len(X_train)
        n_es = max(500, int(n_tr * 0.12))
        purge_bars = 24
        split_idx = max(1000, n_tr - n_es - purge_bars)
        X_sub, y_sub = X_train[:split_idx], y_train[:split_idx]
        X_es, y_es = X_train[split_idx + purge_bars :], y_train[split_idx + purge_bars :]

        clf = HistGradientBoostingClassifier(
            max_iter=160,
            learning_rate=0.04,
            max_leaf_nodes=15,
            min_samples_leaf=300,
            l2_regularization=10.0,
            early_stopping=False,
            random_state=seed,
        )
        clf.fit(X_sub, y_sub)
        best_loss = float("inf")
        best_step = len(clf._predictors) - 1
        no_improve = 0
        for step_i, stage_proba in enumerate(clf.staged_predict_proba(X_es)):
            p = np.clip(stage_proba[:, 1], 1e-6, 1.0 - 1e-6)
            loss = -float(np.mean(y_es * np.log(p) + (1.0 - y_es) * np.log(1.0 - p)))
            if loss < best_loss - 1e-5:
                best_loss = loss
                best_step = step_i
                no_improve = 0
            else:
                no_improve += 1
                if no_improve >= 20:
                    break
        clf._predictors = clf._predictors[: best_step + 1]
        return clf

    clf_sign30 = _fit_hgb_clf_model_purged_chrono(X_tr, (y30[tr_mask] > 0.0).astype(np.int32), seed=42)

    tau_l60 = float(np.quantile(y60[tr_mask], 0.65))
    tau_s60 = float(np.quantile(y60[tr_mask], 0.35))
    clf_l60 = _fit_hgb_clf_model_purged_chrono(X_tr, (y60[tr_mask] > tau_l60).astype(np.int32), seed=43)
    clf_s60 = _fit_hgb_clf_model_purged_chrono(X_tr, (y60[tr_mask] < tau_s60).astype(np.int32), seed=44)

    valid_lin = np.isfinite(y15) & np.isfinite(y30) & np.isfinite(y60)
    tr_mask_lin = _slice_mask(bundle.index, train_start, train_end, valid_lin)
    va_mask_lin = _slice_mask(bundle.index, val_start, val_end, valid_lin)

    scaler = StandardScaler()
    X_tr_sc = scaler.fit_transform(np.nan_to_num(X_all[tr_mask_lin], nan=0.0, posinf=0.0, neginf=0.0))
    X_va_sc = scaler.transform(np.nan_to_num(X_all[va_mask_lin], nan=0.0, posinf=0.0, neginf=0.0))

    ridges: Dict[str, Ridge] = {}
    for h_key, y_arr in (("ridge_15", y15), ("ridge_30", y30), ("ridge_60", y60)):
        clip_v = float(np.quantile(np.abs(y_arr[tr_mask_lin]), 0.995))
        ridges[h_key] = Ridge(alpha=8000.0, random_state=42).fit(X_tr_sc, np.clip(y_arr[tr_mask_lin], -clip_v, clip_v))

    def _fit_q90_model(y_tr_arr: np.ndarray, seed: int) -> HistGradientBoostingRegressor:
        return HistGradientBoostingRegressor(
            loss="quantile", quantile=0.90, max_iter=120, learning_rate=0.05, max_leaf_nodes=15,
            min_samples_leaf=250, l2_regularization=10.0, early_stopping=False, validation_fraction=0.12,
            n_iter_no_change=15, random_state=seed,
        ).fit(X_tr[::12], y_tr_arr[::12])

    reg_ml30 = _fit_q90_model(y1_ml30[tr_mask], 52)
    reg_ms30 = _fit_q90_model(y1_ms30[tr_mask], 53)
    reg_ml60 = _fit_q90_model(y1_ml60[tr_mask], 62)
    reg_ms60 = _fit_q90_model(y1_ms60[tr_mask], 63)

    # Validation calibration statistics
    va_s30 = clf_sign30.predict_proba(X_va)[:, 1]
    va_t60 = clf_l60.predict_proba(X_va)[:, 1] - clf_s60.predict_proba(X_va)[:, 1]
    va_l15 = ridges["ridge_15"].predict(X_va_sc)
    va_l30 = ridges["ridge_30"].predict(X_va_sc)
    va_l60 = ridges["ridge_60"].predict(X_va_sc)

    norm_stats = {
        "s30": {"mean": float(np.mean(va_s30)), "std": float(np.std(va_s30))},
        "t60": {"mean": float(np.mean(va_t60)), "std": float(np.std(va_t60))},
        "lin15": {"mean": float(np.mean(va_l15)), "std": float(np.std(va_l15))},
        "lin30": {"mean": float(np.mean(va_l30)), "std": float(np.std(va_l30))},
        "lin60": {"mean": float(np.mean(va_l60)), "std": float(np.std(va_l60))},
    }

    z_va_s30 = _zscore_from_val(va_s30, va_s30)
    z_va_t60 = _zscore_from_val(va_t60, va_t60)
    z_va_l15 = _zscore_from_val(va_l15, va_l15)
    z_va_l30 = _zscore_from_val(va_l30, va_l30)
    z_va_l60 = _zscore_from_val(va_l60, va_l60)
    z_va_lin_blend = 0.30 * z_va_l15 + 0.40 * z_va_l30 + 0.30 * z_va_l60
    z_va_joint_raw = 0.50 * z_va_s30 + 0.50 * z_va_t60
    norm_stats["joint"] = {"mean": float(np.mean(z_va_joint_raw)), "std": float(np.std(z_va_joint_raw))}
    z_va_joint = _zscore_from_val(z_va_joint_raw, z_va_joint_raw)
    z_va_meta = 0.40 * z_va_s30 + 0.30 * z_va_t60 + 0.30 * z_va_lin_blend

    fib_extras: Dict[str, object] = {}
    if fib_features_df is not None:
        valid_fib = np.isfinite(y30) & np.isfinite(y60)
        tr_mask_fib = _slice_mask(bundle.index, train_start, train_end, valid_fib)
        va_mask_fib = _slice_mask(bundle.index, val_start, val_end, valid_fib)
        F_all = fib_features_df.to_numpy(dtype=np.float32)
        F_tr = np.nan_to_num(F_all[tr_mask_fib], nan=0.0, posinf=0.0, neginf=0.0)
        F_va = np.nan_to_num(F_all[va_mask_fib], nan=0.0, posinf=0.0, neginf=0.0)
        fib_scaler = StandardScaler()
        F_tr_sc = fib_scaler.fit_transform(F_tr)
        F_va_sc = fib_scaler.transform(F_va)

        fib_r30 = Ridge(alpha=2000.0, random_state=42).fit(F_tr_sc, np.clip(y30[tr_mask_fib], -0.02, 0.02))
        fib_r60 = Ridge(alpha=2000.0, random_state=42).fit(F_tr_sc, np.clip(y60[tr_mask_fib], -0.03, 0.03))
        va_f30 = fib_r30.predict(F_va_sc)
        va_f60 = fib_r60.predict(F_va_sc)
        norm_stats["fib30"] = {"mean": float(np.mean(va_f30)), "std": float(np.std(va_f30))}
        norm_stats["fib60"] = {"mean": float(np.mean(va_f60)), "std": float(np.std(va_f60))}

        z_va_fib = 0.50 * _zscore_from_val(va_f30, va_f30) + 0.50 * _zscore_from_val(va_f60, va_f60)
        # Fix #5: Use ADDITIVE overlay + FROZEN_TH (thresholds frozen on base validation scores z_va_joint, z_va_l15, z_va_lin_blend)
        # so zero specialist signal leaves original M2 decisions 100% unchanged!
        z_va_joint_eff = z_va_joint
        z_va_l15_eff = z_va_l15
        z_va_lin_blend_eff = z_va_lin_blend

        fib_cols = list(fib_features_df.columns)
        fib_extras = {
            "fib_cols": fib_cols,
            "fib_col_index": {c: idx_c for idx_c, c in enumerate(fib_cols)},
            "fib_scaler": fib_scaler,
            "fib_ridge_30": fib_r30,
            "fib_ridge_60": fib_r60,
            "fib_overlay_weight": float(fib_overlay_weight),
            "fib_blend_mode": "ADDITIVE",
            "fib_threshold_policy": "FROZEN_TH",
        }
    else:
        z_va_joint_eff = z_va_joint
        z_va_l15_eff = z_va_l15
        z_va_lin_blend_eff = z_va_lin_blend

    va_ml30 = np.clip(reg_ml30.predict(X_va), 1e-4, 0.30)
    va_ms30 = np.clip(reg_ms30.predict(X_va), 1e-4, 0.30)
    va_ml60 = np.clip(reg_ml60.predict(X_va), 1e-4, 0.30)
    va_ms60 = np.clip(reg_ms60.predict(X_va), 1e-4, 0.30)

    def _mk_th(sc_arr: np.ndarray, ml_arr: np.ndarray, ms_arr: np.ndarray, step_b: int) -> SubBookThresholds:
        return SubBookThresholds(
            th_long_entry=float(np.quantile(sc_arr, entry_q)),
            th_short_entry=float(np.quantile(sc_arr, 1.0 - entry_q)),
            th_long_hold=float(np.quantile(sc_arr, hold_q)),
            th_short_hold=float(np.quantile(sc_arr, 1.0 - hold_q)),
            y1_cap_long=float(np.quantile(ml_arr, y1_cap_q)),
            y1_cap_short=float(np.quantile(ms_arr, y1_cap_q)),
            step_bars=step_b,
        )

    thresholds = {
        "SB1_30M_SIGN_HGB": _mk_th(va_s30, va_ml30, va_ms30, 6),
        "SB2_30M_60M_JOINT_HGB": _mk_th(z_va_joint_eff, va_ml60, va_ms60, 6),
        "SB3_15M_RIDGE_LIN": _mk_th(z_va_l15_eff, va_ml30, va_ms30, 3),
        "SB4_30M_RIDGE_BLEND": _mk_th(z_va_lin_blend_eff, va_ml30, va_ms30, 6),
        "SB5_META_30M": _mk_th(z_va_meta, va_ml30, va_ms30, 6),
        "SB6_META_60M": _mk_th(z_va_meta, va_ml60, va_ms60, 12),
        "SB7_60M_TAIL_HGB": _mk_th(va_t60, va_ml60, va_ms60, 12),
    }

    artifact = {
        "default_strategy_mode": (
            "M2_FIB_5M_1H_PROTECTED_NETTING" if fib_features_df is not None else "M2_4ENGINE_SUBBOOK_NETTING"
        ),
        "default_nominal_leverage": 3.0,
        "feature_cols": list(bundle.features.columns),
        "train_window": [train_start, train_end],
        "val_window": [val_start, val_end],
        "clf_sign30": clf_sign30,
        "clf_l60": clf_l60,
        "clf_s60": clf_s60,
        "scaler": scaler,
        "ridge_15": ridges["ridge_15"],
        "ridge_30": ridges["ridge_30"],
        "ridge_60": ridges["ridge_60"],
        "reg_ml30": reg_ml30,
        "reg_ms30": reg_ms30,
        "reg_ml60": reg_ml60,
        "reg_ms60": reg_ms60,
        "val_norm_stats": norm_stats,
        "thresholds": thresholds,
    }
    artifact.update(fib_extras)

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    pkl_path = export_path or (RUNS_DIR / "latest_live_model_bundle.pkl")
    with open(pkl_path, "wb") as f:
        pickle.dump(artifact, f)

    sha = hashlib.sha256(pkl_path.read_bytes()).hexdigest()
    manifest = {
        "default_strategy_mode": artifact["default_strategy_mode"],
        "default_nominal_leverage": 3.0,
        "model_bundle_path": str(pkl_path.relative_to(ROOT)),
        "model_bundle_sha256": sha,
        "target_symbol": "BTCUSDT",
        "cross_asset_inputs": ["SOLUSDT", "ETHUSDT", "BNBUSDT"],
        "n_features": len(artifact["feature_cols"]),
        "n_fib_features": len(artifact.get("fib_cols", [])),
        "train_window": artifact["train_window"],
        "val_window": artifact["val_window"],
        "entry_quantile": entry_q,
        "hold_quantile": hold_q,
        "y1_cap_quantile": y1_cap_q,
        "subbooks": {k: vars(v) for k, v in thresholds.items()},
    }
    with open(RUNS_DIR / "latest_live_model_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return ZeroFeeMakerMasterEngine(artifact, strategy_mode="M2", nominal_leverage=3.0), pkl_path
