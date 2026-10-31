"""Phase 5 Study (Audit-Clean): Fibonacci Retracement (0.236 Entry / 0.382 Target),
Candidate-Extreme Stop Protection, and Wilder RSI-14 Resonance Layer Features (`5m`, `1h`, `15m`, `4h` + `ETH/SOL 1h`).

Extracts the exact causal state machine from `research/divergence_fib_examples_2024_2025_20261026`
(without modifying any file in that directory):
- `pivots_causal(signal, 300)`: 3-bar + 0.2% close-reversal alternating swing leg state machine
- `make_candidate_plans_since`: 4 divergence types (`regular_bullish`, `regular_bearish`, `hidden_bullish`,
  `hidden_bearish`) with 2-high/2-low structural trend confirmation for hidden divergences, 0.236 Fibonacci
  retracement entry (`entry`), candidate-extreme 1-tick protective stop (`stop`), 288-bar big-anchor 0.382
  Fibonacci target (`target`), 24-bar order expiry, and `CANCELLED_EXTREME_REFRESH` invalidation
- `strict_divergence` & `classify` (`layer_audit_v8.py`): Same-pivot Wilder RSI-14 resonance layers
  (`Layer 1` vs `Layer 3` for Regular; `Layer 5` vs `Layer 10` for Hidden)
- `accounting_v3.size_position`: Risk-unit inversely proportional to planned stop distance (`|entry - stop|`)

Strictly enforces all 12 independent audit rules:
1. Pre-test threshold freeze (thresholds frozen strictly on 2024 for 2025 OOS; 2024-2025 for 2026 OOS).
2. Zero test-period sign/direction peeking (all specialist weights learned strictly on `tr_mask` via Ridge,
   and guard parameters selected strictly on `va_mask`).
3. Genuine Pearson IC and Spearman Rank IC alongside event-conditional metrics.
4. 60m non-overlapping de-clustering + Newey-West HAC t-stats + Holm-Bonferroni adjusted p-values.
5. Execution bar timestamp attribution (`O_{i+1} -> O_{i+2}` attributed to `t_{i+1}`).
6. Exact `evaluate_position_path` column names.
7. Reproducible script + saved JSON/CSV artifacts.
8. Explicit decomposition of `FROZEN_TH` (`threshold_va_sc=va_base`) vs `RECAL_TH`.
9. Exact causal alternating swing leg pivots (`pivots_causal`) + same-pivot RSI resonance (`strict_divergence`).
10. Zero `.bfill()` anywhere.
11. Chronologically purged HGB early stopping (`_fit_hgb_clf_purged_chrono`).
12. Full multi-bar cumulative floating loss & forced liquidation settlement in `evaluate_position_path`.
"""

from __future__ import annotations

import copy
import json
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy.stats import norm, spearmanr
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from research.zero_fee_maker_ml_v1.code.features import ROOT, DatasetBundle, build_dataset_bundle
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
    _decluster_boolean_triggers,
    _newey_west_tstat,
)


def _holm_bonferroni(p_vals: np.ndarray) -> np.ndarray:
    """Compute Holm-Bonferroni step-down multiple-testing adjusted p-values."""
    m = len(p_vals)
    if m == 0:
        return p_vals
    order = np.argsort(p_vals)
    adj = np.empty(m, dtype=np.float64)
    running_max = 0.0
    for rank, idx in enumerate(order):
        val = min(1.0, float(p_vals[idx]) * (m - rank))
        running_max = max(running_max, val)
        adj[idx] = running_max
    return adj

# Add read-only reference paths from divergence_fib_examples_2024_2025_20261026
FIB_STUDY_DIR = ROOT / "research" / "divergence_fib_examples_2024_2025_20261026"
for _sub in (
    FIB_STUDY_DIR,
    FIB_STUDY_DIR / "v3_accounting",
    FIB_STUDY_DIR / "v4_2024_full",
    FIB_STUDY_DIR / "v8_2026_layer_type_tables",
    FIB_STUDY_DIR / "v8_4h_supplement_20261026",
):
    if str(_sub) not in sys.path:
        sys.path.insert(0, str(_sub))

import signals_v4  # noqa: E402
from adapter_v8 import aggregate_complete_5m  # noqa: E402
from adapter_4h_supplement import aggregate_complete_5m as aggregate_complete_5m_4h  # noqa: E402
from layer_audit_v8 import _rsi14, classify, strict_divergence  # noqa: E402
from signals_v8 import TYPE_ORDER, make_candidate_plans_since, pivots_causal  # noqa: E402

ALL_TYPES = ("regular_bullish", "regular_bearish", "hidden_bullish", "hidden_bearish")
SHORT_KEY = {
    "regular_bullish": "reg_bull",
    "regular_bearish": "reg_bear",
    "hidden_bullish": "hid_bull",
    "hidden_bearish": "hid_bear",
}


def _load_btc_5m_with_2023_warmup(
    end_exclusive_utc: str = "2026-09-25 00:00:00+00:00",
    bundle: DatasetBundle | None = None,
) -> pd.DataFrame:
    """Load verified BTC 5m futures from 2023-01-01 (for full 300-bar 4h/1h/15m/5m warmup before 2024)."""
    p_v6 = FIB_STUDY_DIR / "v6_2024_to_latest_12_accounts" / "inputs" / "signal_history_5m_v6.parquet"
    df_v6 = pd.read_parquet(p_v6)
    df_v6["open_time"] = pd.to_datetime(df_v6["open_time"], utc=True)
    if bundle is not None and len(bundle.index) > 0:
        df_2023 = df_v6[
            (df_v6["open_time"] >= pd.Timestamp("2023-01-01 00:00:00+00:00"))
            & (df_v6["open_time"] < pd.Timestamp("2024-01-01 00:00:00+00:00"))
        ][["open_time", "open", "high", "low", "close", "volume"]]
        df_bundle = pd.DataFrame(
            {
                "open_time": bundle.index,
                "open": bundle.open_raw,
                "high": bundle.high_raw,
                "low": bundle.low_raw,
                "close": bundle.close_raw,
                "volume": np.ones(len(bundle.index), dtype=np.float64),
            }
        )
        df = pd.concat([df_2023, df_bundle], ignore_index=True)
        return df[["open_time", "open", "high", "low", "close", "volume"]]

    df = df_v6[
        (df_v6["open_time"] >= pd.Timestamp("2023-01-01 00:00:00+00:00"))
        & (df_v6["open_time"] < pd.Timestamp(end_exclusive_utc))
    ].copy().reset_index(drop=True)
    return df[["open_time", "open", "high", "low", "close", "volume"]]


def _load_cross_asset_1h_with_warmup(symbol: str, end_exclusive_utc: str = "2026-09-25 00:00:00+00:00") -> pd.DataFrame:
    """Load verified ETHUSDT or SOLUSDT 1h futures from 2023-01-01 for v10 cross-asset 1h Fib plans."""
    base = symbol.replace("USDT", "")
    p_1h = ROOT / "user_data" / "data" / "binance" / "futures" / f"{base}_USDT_USDT-1h-futures.feather"
    df = pd.read_feather(p_1h).sort_values("date").reset_index(drop=True)
    df["open_time"] = pd.to_datetime(df["date"], utc=True)
    df = df[
        (df["open_time"] >= pd.Timestamp("2023-01-01 00:00:00+00:00"))
        & (df["open_time"] < pd.Timestamp(end_exclusive_utc))
    ].copy().reset_index(drop=True)
    return df[["open_time", "open", "high", "low", "close", "volume"]]


def extract_timeframe_fib_features(
    signal_df: pd.DataFrame,
    tf_label: str,
    tf_minutes: int,
    bundle: DatasetBundle,
    tick_size: Decimal = Decimal("0.1"),
    start_eligible_utc: str = "2023-11-01T00:00:00Z",
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Run exact `pivots_causal` + `make_candidate_plans_since` + `strict_divergence` and map the
    causal Fibonacci + Stop/Target protection lifecycle onto `bundle.index` (5m decision grid).

    At each 5m bar `t` (closing at `exec_close_ns[t] = open_time[t] + 5m`), computes strictly causal
    features for each of the 4 divergence types (`reg_bull`, `reg_bear`, `hid_bull`, `hid_bear`):
      1. `{k}_arm_score_{tf}`: Armed plan waiting for `0.236` Fibonacci entry (not yet triggered or
         stop-invalidated), weighted by progress toward `0.236` entry, planned RR, and RSI layer.
      2. `{k}_trig_impulse_{tf}`: Fresh trigger/breakout across the `0.236` Fibonacci entry level
         (decayed causally over 6 bars), weighted by planned RR and RSI resonance layer (`1/3/5/10`).
      3. `{k}_active_rr_{tf}`: Currently holding inside the `[stop, target]` Fibonacci protective
         envelope (`0.236` entry triggered, `candidate_price` stop NOT breached, `0.382` target NOT
         yet exhausted), measuring live dynamic Reward-to-Risk `target_upside_bp / max(stop_cushion_bp, 2.0)`.
      4. `{k}_res_active_{tf}`: Same as `active_rr` but strictly gated to **MACD + Wilder RSI-14
         Same-Pivot Resonance** plans (`Layer 3` for Regular, `Layer 10` for Hidden).
      5. `{k}_stop_break_{tf}`: Causal protective stop-loss invalidation impulse when an armed or active
         plan breaches `stop = candidate_price ∓ 1 tick` or triggers `CANCELLED_EXTREME_REFRESH`.
      6. `{k}_targ_hit_{tf}`: Causal take-profit exhaustion impulse when an active plan reaches its
         `0.382` big-anchor Fibonacci `target`.
    """
    old_tick = signals_v4.TICK
    try:
        signals_v4.TICK = tick_size
        pivot_start = 300 if len(signal_df) > 350 else 0
        pivots = pivots_causal(signal_df, pivot_start)
        close = signal_df["close"].to_numpy(dtype=np.float64)
        dif = (
            pd.Series(close).ewm(span=12, adjust=False).mean().to_numpy()
            - pd.Series(close).ewm(span=26, adjust=False).mean().to_numpy()
        )
        rsi = _rsi14()(close)
        sig_open_ns = pd.to_datetime(signal_df["open_time"], utc=True).array.asi8
        tf_ns = int(tf_minutes) * 60_000_000_000
        start_ns = pd.Timestamp(start_eligible_utc).value
        first_eligible = int(np.searchsorted(sig_open_ns + tf_ns, start_ns, side="left"))
        raw_legs, raw_meta = make_candidate_plans_since(signal_df, pivots, dif, first_eligible)
    finally:
        signals_v4.TICK = old_tick

    n5 = len(bundle.index)
    exec_open_ns = bundle.index.asi8
    exec_close_ns = exec_open_ns + 300_000_000_000

    # If cross-asset (ETH/SOL), we track triggers/stops on the signal_df's own price series or BTC 5m;
    # for BTC timeframes, use exact 5m constituent OHLC (`bundle.high_raw`, `bundle.low_raw`, `bundle.close_raw`).
    is_btc = tf_label in ("5m", "15m", "1h", "4h")
    if is_btc:
        h5 = bundle.high_raw
        l5 = bundle.low_raw
        c5 = bundle.close_raw
    else:
        # Map signal_df close/high/low causally to 5m close_time
        sig_close_idx = pd.to_datetime(signal_df["open_time"], utc=True) + pd.Timedelta(minutes=tf_minutes)
        s_df = signal_df.copy()
        s_df.index = sig_close_idx
        c_5m_ts = bundle.index + pd.Timedelta(minutes=5)
        h5 = s_df["high"].reindex(c_5m_ts, method="ffill").ffill().fillna(0.0).to_numpy(dtype=np.float64)
        l5 = s_df["low"].reindex(c_5m_ts, method="ffill").ffill().fillna(0.0).to_numpy(dtype=np.float64)
        c5 = s_df["close"].reindex(c_5m_ts, method="ffill").ffill().fillna(0.0).to_numpy(dtype=np.float64)

    cols: Dict[str, np.ndarray] = {}
    for k in SHORT_KEY.values():
        cols[f"{k}_arm_score_{tf_label}"] = np.zeros(n5, dtype=np.float32)
        cols[f"{k}_trig_impulse_{tf_label}"] = np.zeros(n5, dtype=np.float32)
        cols[f"{k}_active_rr_{tf_label}"] = np.zeros(n5, dtype=np.float32)
        cols[f"{k}_res_active_{tf_label}"] = np.zeros(n5, dtype=np.float32)
        cols[f"{k}_stop_break_{tf_label}"] = np.zeros(n5, dtype=np.float32)
        cols[f"{k}_targ_hit_{tf_label}"] = np.zeros(n5, dtype=np.float32)

    stats = {
        "tf_label": tf_label,
        "armed_plans": 0,
        "resonance_plans": 0,
        "triggered_plans": 0,
        "stop_broken_plans": 0,
        "target_hit_plans": 0,
        "by_type_layer": {},
    }

    bars_per_sig = max(1, tf_minutes // 5)
    max_hold_5m = 24 * bars_per_sig

    for leg in raw_legs:
        p1i = int(leg["p1"]["index"])
        p1px = float(leg["p1"]["price"])
        cancel_map: Dict[int, int] = {}
        for ev in leg.get("events", []):
            if ev.get("event") in ("CANCELLED_EXTREME_REFRESH", "CANCELLED_REFRESH_WITH_STOP_INVALIDATION"):
                si = int(ev["index"])
                if si < len(sig_open_ns):
                    b_ns = int(sig_open_ns[si] + tf_ns)
                    c_idx = int(np.searchsorted(exec_close_ns, b_ns, side="left"))
                    vn = int(ev["version"])
                    cancel_map[vn] = min(cancel_map.get(vn, n5), c_idx)

        for v in leg["versions"]:
            if not (v.get("armed") or v.get("status") == "NO_ACTIVATION_BAR"):
                continue
            di = int(v["decision_index"])
            if di < first_eligible or di >= len(sig_open_ns):
                continue
            bns = int(sig_open_ns[di] + tf_ns)
            # i_dec is the exact 5m bar whose close_time == bns (decision is known at i_dec close!)
            i_dec = int(np.searchsorted(exec_close_ns, bns, side="left"))
            if i_dec >= n5:
                continue

            kind = str(v["type"])
            sk = SHORT_KEY[kind]
            side = 1 if kind.endswith("bullish") else -1
            ci = int(v["candidate_extreme_index"])
            px_col = "high" if kind.endswith("bearish") else "low"
            p2px = float(signal_df.iloc[ci][px_col])

            po, do, ro = strict_divergence(
                kind, p1px, p2px, float(dif[p1i]), float(dif[ci]), float(rsi[p1i]), float(rsi[ci])
            )
            _, is_res, _, layer = classify(kind, po, do, ro)

            lv = v["levels"]
            entry = float(lv["entry"])
            stop = float(lv["stop"])
            target = float(lv["target"])
            if entry <= 0.0 or abs(entry - stop) <= 0.0:
                continue

            plan_stop_bp = abs(entry - stop) / entry * 1e4
            plan_targ_bp = abs(target - entry) / entry * 1e4
            plan_rr = float(np.clip(plan_targ_bp / max(plan_stop_bp, 1.5), 0.2, 8.0))
            # accounting_v3 risk-parity weight (capped at 1.5, normalized)
            rp_w = float(np.clip(25.0 / max(plan_stop_bp + 5.0, 10.0), 0.25, 1.5))
            res_mult = 1.5 if is_res else 1.0
            plan_quality = float(np.clip(np.sqrt(plan_rr) * rp_w * res_mult, 0.2, 5.0))

            stats["armed_plans"] += 1
            if is_res:
                stats["resonance_plans"] += 1
            tl_key = f"{kind}_L{layer}"
            stats["by_type_layer"][tl_key] = stats["by_type_layer"].get(tl_key, 0) + 1

            deadline = bns + 24 * tf_ns
            i_exp_raw = int(np.searchsorted(exec_open_ns, deadline, side="left")) - 1
            i_exp = min(n5 - 1, i_exp_raw)
            has_real_cancel = int(v["version"]) in cancel_map
            i_can = cancel_map[int(v["version"])] if has_real_cancel else (n5 + 999999)
            end_arm = min(i_exp, i_can, n5 - 1)
            if end_arm < i_dec:
                end_arm = i_dec

            # Scan [i_dec + 1 .. end_arm] for 0.236 Fib entry trigger or pre-entry stop invalidation
            trig_idx = -1
            stop_pre_idx = -1
            if i_dec + 1 <= end_arm:
                sl_h = h5[i_dec + 1 : end_arm + 1]
                sl_l = l5[i_dec + 1 : end_arm + 1]
                if side == 1:
                    hit_e = np.flatnonzero(sl_h >= entry)
                    hit_s = np.flatnonzero(sl_l <= stop)
                else:
                    hit_e = np.flatnonzero(sl_l <= entry)
                    hit_s = np.flatnonzero(sl_h >= stop)
                fe = int(hit_e[0]) if len(hit_e) else 999999
                fs = int(hit_s[0]) if len(hit_s) else 999999
                if fs <= fe and fs < 999999:
                    stop_pre_idx = i_dec + 1 + fs
                elif fe < fs and fe < 999999:
                    trig_idx = i_dec + 1 + fe
            if stop_pre_idx < 0 and has_real_cancel and i_can <= i_exp_raw and (trig_idx < 0 or i_can < trig_idx):
                stop_pre_idx = i_can

            # 1) Populate ARMED waiting state on [i_dec .. arm_last]
            if trig_idx >= 0:
                arm_last = trig_idx - 1
            elif stop_pre_idx >= 0:
                arm_last = stop_pre_idx - 1
            else:
                arm_last = end_arm

            if arm_last >= i_dec >= 0:
                c_slice = c5[i_dec : arm_last + 1]
                prog = np.clip((side * (c_slice - stop)) / max( abs(entry - stop), 1e-6 ), 0.0, 1.0)
                arm_val = (prog * plan_quality).astype(np.float32)
                cols[f"{sk}_arm_score_{tf_label}"][i_dec : arm_last + 1] = np.maximum(
                    cols[f"{sk}_arm_score_{tf_label}"][i_dec : arm_last + 1], arm_val
                )

            # If pre-entry stop broke, record stop_break impulse at stop_pre_idx
            if stop_pre_idx >= 0 and stop_pre_idx < n5:
                stats["stop_broken_plans"] += 1
                cols[f"{sk}_stop_break_{tf_label}"][stop_pre_idx] = max(
                    cols[f"{sk}_stop_break_{tf_label}"][stop_pre_idx], float(plan_quality)
                )
                continue

            if trig_idx < 0 or trig_idx >= n5:
                continue

            # 2) Plan triggered 0.236 Fib entry at `trig_idx`!
            stats["triggered_plans"] += 1
            cols[f"{sk}_trig_impulse_{tf_label}"][trig_idx] = max(
                cols[f"{sk}_trig_impulse_{tf_label}"][trig_idx], float(plan_quality)
            )

            hold_end = min(n5 - 1, trig_idx + max_hold_5m)
            exit_idx = hold_end
            exit_kind = "EXPIRED"
            if trig_idx + 1 <= hold_end:
                hh = h5[trig_idx + 1 : hold_end + 1]
                ll = l5[trig_idx + 1 : hold_end + 1]
                if side == 1:
                    hs = np.flatnonzero(ll <= stop)
                    ht = np.flatnonzero(hh >= target)
                else:
                    hs = np.flatnonzero(hh >= stop)
                    ht = np.flatnonzero(ll <= target)
                f_s = int(hs[0]) if len(hs) else 999999
                f_t = int(ht[0]) if len(ht) else 999999
                if f_s <= f_t and f_s < 999999:
                    exit_idx = trig_idx + 1 + f_s
                    exit_kind = "STOP"
                elif f_t < f_s and f_t < 999999:
                    exit_idx = trig_idx + 1 + f_t
                    exit_kind = "TARGET"

            act_last = exit_idx - 1 if exit_kind in ("STOP", "TARGET") else exit_idx
            if act_last >= trig_idx:
                c_act = c5[trig_idx : act_last + 1]
                stop_cush_bp = np.maximum(side * (c_act - stop) / (c_act + 1e-12) * 1e4, 1.0)
                targ_up_bp = np.maximum(side * (target - c_act) / (c_act + 1e-12) * 1e4, 0.0)
                live_rr = np.clip(targ_up_bp / np.maximum(stop_cush_bp, 3.0), 0.0, 6.0)
                act_score = (np.sqrt(live_rr) * rp_w * res_mult).astype(np.float32)
                cols[f"{sk}_active_rr_{tf_label}"][trig_idx : act_last + 1] = np.maximum(
                    cols[f"{sk}_active_rr_{tf_label}"][trig_idx : act_last + 1], act_score
                )
                if is_res:
                    cols[f"{sk}_res_active_{tf_label}"][trig_idx : act_last + 1] = np.maximum(
                        cols[f"{sk}_res_active_{tf_label}"][trig_idx : act_last + 1], act_score
                    )

            if exit_kind == "STOP" and exit_idx < n5:
                stats["stop_broken_plans"] += 1
                cols[f"{sk}_stop_break_{tf_label}"][exit_idx] = max(
                    cols[f"{sk}_stop_break_{tf_label}"][exit_idx], float(plan_quality * 1.25)
                )
            elif exit_kind == "TARGET" and exit_idx < n5:
                stats["target_hit_plans"] += 1
                cols[f"{sk}_targ_hit_{tf_label}"][exit_idx] = max(
                    cols[f"{sk}_targ_hit_{tf_label}"][exit_idx], float(plan_quality)
                )

    # Smooth impulse columns causally with a short EMA (half-life ~3 bars) so 5m models can see recent triggers/stops
    out_cols: Dict[str, np.ndarray] = {}
    for col_name, arr in cols.items():
        out_cols[col_name] = arr
        if "_trig_impulse_" in col_name or "_stop_break_" in col_name or "_targ_hit_" in col_name:
            s_ema = pd.Series(arr, index=bundle.index).ewm(span=6, adjust=False).mean().to_numpy(dtype=np.float32)
            out_cols[f"{col_name}_ema6"] = s_ema

    # Construct composite directional Fibonacci & Stop-Protection features for this timeframe
    bull_arm = cols[f"reg_bull_arm_score_{tf_label}"] + cols[f"hid_bull_arm_score_{tf_label}"]
    bear_arm = cols[f"reg_bear_arm_score_{tf_label}"] + cols[f"hid_bear_arm_score_{tf_label}"]
    bull_act = cols[f"reg_bull_active_rr_{tf_label}"] + cols[f"hid_bull_active_rr_{tf_label}"]
    bear_act = cols[f"reg_bear_active_rr_{tf_label}"] + cols[f"hid_bear_active_rr_{tf_label}"]
    bull_res = cols[f"reg_bull_res_active_{tf_label}"] + cols[f"hid_bull_res_active_{tf_label}"]
    bear_res = cols[f"reg_bear_res_active_{tf_label}"] + cols[f"hid_bear_res_active_{tf_label}"]
    bull_stop_brk = out_cols[f"reg_bull_stop_break_{tf_label}_ema6"] + out_cols[f"hid_bull_stop_break_{tf_label}_ema6"]
    bear_stop_brk = out_cols[f"reg_bear_stop_break_{tf_label}_ema6"] + out_cols[f"hid_bear_stop_break_{tf_label}_ema6"]
    bull_trig = out_cols[f"reg_bull_trig_impulse_{tf_label}_ema6"] + out_cols[f"hid_bull_trig_impulse_{tf_label}_ema6"]
    bear_trig = out_cols[f"reg_bear_trig_impulse_{tf_label}_ema6"] + out_cols[f"hid_bear_trig_impulse_{tf_label}_ema6"]

    out_cols[f"net_fib_arm_{tf_label}"] = (bull_arm - bear_arm).astype(np.float32)
    out_cols[f"net_fib_trig_{tf_label}"] = (bull_trig - bear_trig).astype(np.float32)
    out_cols[f"net_fib_active_rr_{tf_label}"] = (bull_act - bear_act).astype(np.float32)
    out_cols[f"net_fib_res_active_{tf_label}"] = (bull_res - bear_res).astype(np.float32)
    # Note: when bull_stop_brk > 0, a bullish pivot stop was violated (bearish breakdown), and vice versa
    out_cols[f"net_fib_stop_break_{tf_label}"] = (bear_stop_brk - bull_stop_brk).astype(np.float32)

    df_out = pd.DataFrame(out_cols, index=bundle.index, dtype=np.float32)
    return df_out, stats


def build_all_fib_divergence_frames(
    bundle: DatasetBundle,
    only_5m_and_1h: bool = False,
) -> Tuple[Dict[str, pd.DataFrame], Dict[str, Any]]:
    """Build causal Fibonacci + Stop/Target protection feature frames for:
    - `5m` (BTC 5m)
    - `1h` (BTC 1h)
    - `15m` (BTC 15m)
    - `4h` (BTC 4h)
    - `eth_1h` & `sol_1h` (v10 cross-asset 1h Fibonacci + RSI Resonance layers)
    """
    btc_5m_full = _load_btc_5m_with_2023_warmup(bundle=bundle)

    frames: Dict[str, pd.DataFrame] = {}
    all_stats: Dict[str, Any] = {}

    tfs_to_run = [("5m", 5), ("1h", 60)] if only_5m_and_1h else [("5m", 5), ("15m", 15), ("1h", 60), ("4h", 240)]
    for tf, mins in tfs_to_run:
        n5 = mins // 5
        rem = len(btc_5m_full) % n5
        btc_slice = btc_5m_full.iloc[: len(btc_5m_full) - rem].reset_index(drop=True) if rem else btc_5m_full
        if tf == "4h":
            sig_df, _ = aggregate_complete_5m_4h(btc_slice, "4h")
        else:
            sig_df, _ = aggregate_complete_5m(btc_slice, tf)
        df_tf, st = extract_timeframe_fib_features(
            sig_df, tf_label=tf, tf_minutes=mins, bundle=bundle, tick_size=Decimal("0.1")
        )
        frames[tf] = df_tf
        all_stats[tf] = st

    if not only_5m_and_1h:
        end_str = str(bundle.index[-1] + pd.Timedelta(minutes=5))
        for sym, tick_dec, label in [
            ("ETHUSDT", Decimal("0.01"), "eth1h"),
            ("SOLUSDT", Decimal("0.001"), "sol1h"),
        ]:
            sig_cross = _load_cross_asset_1h_with_warmup(sym, end_str)
            df_c, st_c = extract_timeframe_fib_features(
                sig_cross, tf_label=label, tf_minutes=60, bundle=bundle, tick_size=tick_dec
            )
            frames[label] = df_c
            all_stats[label] = st_c

    return frames, all_stats


def evaluate_standalone_fib_factors(
    bundle: DatasetBundle,
    frames: Dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Audit-clean standalone evaluation of Fibonacci + Stop/Target protection features:
    - Computes genuine Pearson IC and Spearman Rank IC on full OOS bars.
    - Freezes the 70th active quantile threshold strictly on pre-test training history
      (2024 for 2025 OOS; 2024-2025 for 2026 OOS).
    - De-clusters triggers with a 12-bar (60m) cooldown so forward 60m return windows never overlap.
    - Reports independent non-overlapping t-stats, Newey-West HAC t-stats, and Holm-Bonferroni p-values.
    """
    idx = bundle.index
    y30_bp = bundle.y0_ret[30] * 1e4
    y60_bp = bundle.y0_ret[60] * 1e4
    valid_ret = np.isfinite(y30_bp) & np.isfinite(y60_bp)

    # Fix Item #6: Enforce 2-hour (24-bar) purge at year-end boundaries so no 60m training label crosses into OOS year
    tr_2025 = (idx >= pd.Timestamp("2024-01-01", tz="UTC")) & (idx <= pd.Timestamp("2024-12-31 21:55:00", tz="UTC")) & valid_ret
    te_2025 = (idx >= pd.Timestamp("2025-01-01", tz="UTC")) & (idx < pd.Timestamp("2026-01-01", tz="UTC")) & valid_ret
    tr_2026 = (idx >= pd.Timestamp("2024-01-01", tz="UTC")) & (idx <= pd.Timestamp("2025-12-31 21:55:00", tz="UTC")) & valid_ret
    te_2026 = (idx >= pd.Timestamp("2026-01-01", tz="UTC")) & (idx < pd.Timestamp("2027-01-01", tz="UTC")) & valid_ret

    rows: List[Dict[str, Any]] = []
    for tf, df_tf in frames.items():
        # Evaluate the key structural composite & subtype columns
        eval_cols = [
            f"reg_bull_active_rr_{tf}",
            f"reg_bear_active_rr_{tf}",
            f"hid_bull_active_rr_{tf}",
            f"hid_bear_active_rr_{tf}",
            f"reg_bull_res_active_{tf}",
            f"reg_bear_res_active_{tf}",
            f"hid_bull_res_active_{tf}",
            f"hid_bear_res_active_{tf}",
            f"reg_bull_stop_break_{tf}_ema6",
            f"reg_bear_stop_break_{tf}_ema6",
            f"hid_bull_stop_break_{tf}_ema6",
            f"hid_bear_stop_break_{tf}_ema6",
            f"net_fib_arm_{tf}",
            f"net_fib_trig_{tf}",
            f"net_fib_active_rr_{tf}",
            f"net_fib_res_active_{tf}",
            f"net_fib_stop_break_{tf}",
        ]
        for col in eval_cols:
            if col not in df_tf.columns:
                continue
            vals = df_tf[col].to_numpy(dtype=np.float64)
            # Determine theoretical sign on training set (2024) strictly without peeking at OOS!
            v_tr24 = vals[tr_2025]
            r60_tr24 = y60_bp[tr_2025]
            if np.std(v_tr24) > 1e-9:
                ic_2024 = float(np.corrcoef(v_tr24, r60_tr24)[0, 1])
            else:
                ic_2024 = 0.0
            train_sign = 1.0 if ic_2024 >= 0.0 else -1.0

            # Freeze 70th active quantile threshold strictly on training history
            if col.startswith("net_"):
                a25 = np.abs(vals[tr_2025])[np.abs(vals[tr_2025]) > 1e-6]
                a26 = np.abs(vals[tr_2026])[np.abs(vals[tr_2026]) > 1e-6]
                th25 = float(np.quantile(a25, 0.70)) if len(a25) >= 10 else 0.0
                th26 = float(np.quantile(a26, 0.70)) if len(a26) >= 10 else 0.0
                raw_trig = (te_2025 & (np.abs(vals) >= th25) & (np.abs(vals) > 1e-6)) | (
                    te_2026 & (np.abs(vals) >= th26) & (np.abs(vals) > 1e-6)
                )
                dir_vec = np.sign(vals) * train_sign
            else:
                a25 = vals[tr_2025][vals[tr_2025] > 1e-6]
                a26 = vals[tr_2026][vals[tr_2026] > 1e-6]
                th25 = float(np.quantile(a25, 0.70)) if len(a25) >= 10 else 0.0
                th26 = float(np.quantile(a26, 0.70)) if len(a26) >= 10 else 0.0
                raw_trig = (te_2025 & (vals >= th25) & (vals > 1e-6)) | (
                    te_2026 & (vals >= th26) & (vals > 1e-6)
                )
                dir_vec = np.full(len(vals), train_sign, dtype=np.float64)

            oos_mask = te_2025 | te_2026
            v_oos = vals[oos_mask] * train_sign
            r60_oos = y60_bp[oos_mask]
            if np.std(v_oos) > 1e-9:
                pearson_ic = float(np.corrcoef(v_oos, r60_oos)[0, 1])
                spearman_ic = float(spearmanr(v_oos, r60_oos).statistic)
            else:
                pearson_ic, spearman_ic = 0.0, 0.0

            declust_trig = _decluster_boolean_triggers(raw_trig, cooldown_bars=12)
            r30_raw = y30_bp[raw_trig] * dir_vec[raw_trig]
            r60_raw = y60_bp[raw_trig] * dir_vec[raw_trig]
            r30_dec = y30_bp[declust_trig] * dir_vec[declust_trig]
            r60_dec = y60_bp[declust_trig] * dir_vec[declust_trig]

            n_dec = int(len(r60_dec))
            if n_dec >= 5:
                m30_dec = float(np.mean(r30_dec))
                m60_dec = float(np.mean(r60_dec))
                wr60_dec = float(np.mean(r60_dec > 0) * 100.0)
                t60_indep = float(m60_dec / (np.std(r60_dec) / np.sqrt(n_dec) + 1e-12))
                p_indep = float(2.0 * (1.0 - norm.cdf(abs(t60_indep))))
            else:
                m30_dec, m60_dec, wr60_dec, t60_indep, p_indep = 0.0, 0.0, 0.0, 0.0, 1.0

            t60_hac = _newey_west_tstat(r60_raw, max_lag=12) if len(r60_raw) >= 10 else 0.0

            rows.append(
                {
                    "timeframe": tf,
                    "feature": col,
                    "train_2024_ic_60m": round(ic_2024, 5),
                    "train_learned_sign": int(train_sign),
                    "frozen_th_2025": round(th25, 5),
                    "frozen_th_2026": round(th26, 5),
                    "oos_pearson_ic_60m": round(pearson_ic, 5),
                    "oos_spearman_rank_ic_60m": round(spearman_ic, 5),
                    "raw_event_bars": int(len(r60_raw)),
                    "declustered_60m_events": n_dec,
                    "declust_dir_ret_30m_bp": round(m30_dec, 3),
                    "declust_dir_ret_60m_bp": round(m60_dec, 3),
                    "declust_win_rate_60m_pct": round(wr60_dec, 2),
                    "t_stat_60m_declustered": round(t60_indep, 2),
                    "t_stat_60m_hac": round(t60_hac, 2),
                    "p_val_raw": round(p_indep, 5),
                }
            )

    df_res = pd.DataFrame(rows)
    if len(df_res) > 0:
        df_res["p_val_holm_bonferroni"] = np.round(
            _holm_bonferroni(df_res["p_val_raw"].to_numpy(dtype=np.float64)), 5
        )
    return df_res


def _fit_learned_fib_specialist(
    bundle: DatasetBundle,
    X_fib_df: pd.DataFrame,
    train_start: str,
    train_end: str,
    val_start: str,
    val_end: str,
    test_start: str,
    test_end: str,
    alpha: float = 2000.0,
) -> Dict[str, Any]:
    """Fit causal multi-horizon Ridge specialist strictly on `tr_mask` (zero test peeking)."""
    X_raw = X_fib_df.to_numpy(dtype=np.float32)
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

    reg30 = Ridge(alpha=alpha, random_state=42).fit(X_tr, np.clip(y30[tr_mask], -0.02, 0.02))
    reg60 = Ridge(alpha=alpha, random_state=42).fit(X_tr, np.clip(y60[tr_mask], -0.03, 0.03))

    va_30 = _zscore_from_val(reg30.predict(X_va), reg30.predict(X_va))
    te_30 = _zscore_from_val(reg30.predict(X_va), reg30.predict(X_te))
    va_60 = _zscore_from_val(reg60.predict(X_va), reg60.predict(X_va))
    te_60 = _zscore_from_val(reg60.predict(X_va), reg60.predict(X_te))

    return {
        "va_z": 0.50 * va_30 + 0.50 * va_60,
        "te_z": 0.50 * te_30 + 0.50 * te_60,
        "top_coef_60": sorted(
            [(k, round(float(v) * 1e4, 4)) for k, v in zip(X_fib_df.columns, reg60.coef_)],
            key=lambda x: abs(x[1]),
            reverse=True,
        )[:8],
    }


def _build_m2_positions_with_overlay(
    bundle: DatasetBundle,
    g_out: Dict[str, np.ndarray],
    l_out: Dict[str, np.ndarray],
    pos_mature: np.ndarray,
    va_overlay: np.ndarray,
    te_overlay: np.ndarray,
    w_overlay: float,
    freeze_base_thresholds: bool,
    blend_mode: str = "CONVEX",
    eval_on_val: bool = False,
) -> np.ndarray:
    """Build exact M2 4-subbook netted positions (`0.25 * (p_e1 + p_e2 + p_e3 + p_e4)`) with specialist score overlay.

    blend_mode:
      - "CONVEX": `(1 - w) * base + w * overlay`
      - "ADDITIVE": `base + w * overlay` (guarantees overlay == 0 leaves base scores 100% unchanged under FROZEN_TH)
      - "ZERO_SPEC_SHRINK": `(1 - w) * base + 0.0` (control isolating score-shrinkage effect under FROZEN_TH)
    """
    target_mask = g_out["va_mask"] if eval_on_val else g_out["te_mask"]
    va_j_z = _zscore_from_val(g_out["va_joint"], g_out["va_joint"])
    te_j_z = va_j_z if eval_on_val else _zscore_from_val(g_out["va_joint"], g_out["te_joint"])

    te_s30 = g_out["va_s30"] if eval_on_val else g_out["te_s30"]
    te_joint = g_out["va_joint"] if eval_on_val else g_out["te_joint"]
    te_ml30 = g_out["va_ml30"] if eval_on_val else g_out["te_ml30"]
    te_ms30 = g_out["va_ms30"] if eval_on_val else g_out["te_ms30"]
    te_ml60 = g_out["va_ml60"] if eval_on_val else g_out["te_ml60"]
    te_ms60 = g_out["va_ms60"] if eval_on_val else g_out["te_ms60"]
    te_lin15 = l_out["va_lin_15"] if eval_on_val else l_out["te_lin_15"]
    te_lin_blend = l_out["va_lin_blend"] if eval_on_val else l_out["te_lin_blend"]
    ov_target = va_overlay if eval_on_val else te_overlay

    p_e1 = _generate_bar_positions(
        bundle,
        target_mask,
        g_out["va_s30"],
        te_s30,
        g_out["va_ml30"],
        te_ml30,
        g_out["va_ms30"],
        te_ms30,
        step_bars=6,
        entry_q=0.92,
        hold_q=0.58,
        y1_cap_q=0.85,
    )

    if abs(w_overlay) < 1e-12:
        p_e2 = _generate_bar_positions(
            bundle,
            target_mask,
            g_out["va_joint"],
            te_joint,
            g_out["va_ml60"],
            te_ml60,
            g_out["va_ms60"],
            te_ms60,
            step_bars=6,
            entry_q=0.92,
            hold_q=0.58,
            y1_cap_q=0.85,
        )
        p_lin15 = _generate_bar_positions(
            bundle,
            target_mask,
            l_out["va_lin_15"],
            te_lin15,
            g_out["va_ml30"],
            te_ml30,
            g_out["va_ms30"],
            te_ms30,
            step_bars=3,
            entry_q=0.92,
            hold_q=0.58,
            y1_cap_q=0.85,
        )
        p_lin30 = _generate_bar_positions(
            bundle,
            target_mask,
            l_out["va_lin_blend"],
            te_lin_blend,
            g_out["va_ml30"],
            te_ml30,
            g_out["va_ms30"],
            te_ms30,
            step_bars=6,
            entry_q=0.92,
            hold_q=0.58,
            y1_cap_q=0.85,
        )
    else:
        w_e2 = 0.80 * w_overlay
        if blend_mode == "ADDITIVE":
            va_e2_sc = va_j_z + w_e2 * va_overlay
            te_e2_sc = te_j_z + w_e2 * ov_target
            va_l15_sc = l_out["va_lin_15"] + w_overlay * va_overlay
            te_l15_sc = te_lin15 + w_overlay * ov_target
            va_l30_sc = l_out["va_lin_blend"] + w_overlay * va_overlay
            te_l30_sc = te_lin_blend + w_overlay * ov_target
        elif blend_mode == "ZERO_SPEC_SHRINK":
            va_e2_sc = (1.0 - w_e2) * va_j_z
            te_e2_sc = (1.0 - w_e2) * te_j_z
            va_l15_sc = (1.0 - w_overlay) * l_out["va_lin_15"]
            te_l15_sc = (1.0 - w_overlay) * te_lin15
            va_l30_sc = (1.0 - w_overlay) * l_out["va_lin_blend"]
            te_l30_sc = (1.0 - w_overlay) * te_lin_blend
        else:
            va_e2_sc = (1.0 - w_e2) * va_j_z + w_e2 * va_overlay
            te_e2_sc = (1.0 - w_e2) * te_j_z + w_e2 * ov_target
            va_l15_sc = (1.0 - w_overlay) * l_out["va_lin_15"] + w_overlay * va_overlay
            te_l15_sc = (1.0 - w_overlay) * te_lin15 + w_overlay * ov_target
            va_l30_sc = (1.0 - w_overlay) * l_out["va_lin_blend"] + w_overlay * va_overlay
            te_l30_sc = (1.0 - w_overlay) * te_lin_blend + w_overlay * ov_target

        p_e2 = _generate_bar_positions(
            bundle,
            target_mask,
            va_e2_sc,
            te_e2_sc,
            g_out["va_ml60"],
            te_ml60,
            g_out["va_ms60"],
            te_ms60,
            step_bars=6,
            entry_q=0.92,
            hold_q=0.58,
            y1_cap_q=0.85,
            threshold_va_sc=va_j_z if freeze_base_thresholds else None,
        )
        p_lin15 = _generate_bar_positions(
            bundle,
            target_mask,
            va_l15_sc,
            te_l15_sc,
            g_out["va_ml30"],
            te_ml30,
            g_out["va_ms30"],
            te_ms30,
            step_bars=3,
            entry_q=0.92,
            hold_q=0.58,
            y1_cap_q=0.85,
            threshold_va_sc=l_out["va_lin_15"] if freeze_base_thresholds else None,
        )
        p_lin30 = _generate_bar_positions(
            bundle,
            target_mask,
            va_l30_sc,
            te_l30_sc,
            g_out["va_ml30"],
            te_ml30,
            g_out["va_ms30"],
            te_ms30,
            step_bars=6,
            entry_q=0.92,
            hold_q=0.58,
            y1_cap_q=0.85,
            threshold_va_sc=l_out["va_lin_blend"] if freeze_base_thresholds else None,
        )

    p_e3 = 0.50 * p_lin15 + 0.50 * p_lin30
    if eval_on_val:
        # On validation split, E4 uses validation predictions of E1/E2
        p_e4_60 = _generate_bar_positions(
            bundle,
            target_mask,
            g_out["va_t60"],
            g_out["va_t60"],
            g_out["va_ml60"],
            te_ml60,
            g_out["va_ms60"],
            te_ms60,
            step_bars=12,
            entry_q=0.92,
            hold_q=0.58,
            y1_cap_q=0.85,
        )
        p_e4 = 0.50 * p_e1 + 0.50 * p_e4_60
        return 0.25 * p_e1 + 0.25 * p_e2 + 0.25 * p_e3 + 0.25 * p_e4
    return 0.25 * p_e1 + 0.25 * p_e2 + 0.25 * p_e3 + 0.25 * pos_mature


def _apply_causal_fib_stop_target_guard(
    pos_base: np.ndarray,
    te_mask: np.ndarray,
    fib_1h_df: pd.DataFrame,
    fib_5m_df: pd.DataFrame,
    guard_strength: float = 0.25,
) -> np.ndarray:
    """Apply causal Fibonacci Stop-Loss Invalidation & RSI-Resonance Active Channel guard to `pos_base`.

    Strictly structural rules from `divergence_fib_examples`:
    1. When an active `1h` or `5m` RSI-Resonance Fibonacci plan (`Layer 3 / 10`: `net_fib_res_active`)
       is inside its `[stop, target]` protective envelope:
       - If aligned with `pos_base`, reinforces confidence (`+guard_strength`, capped at nominal `1.0`).
       - If opposing `pos_base` (`pos_base * net_fib_res_active < 0`), trims exposure (`-guard_strength`)
         to respect the opposing Fibonacci retracement & stop protection!
    2. When a Fibonacci candidate-extreme protective stop (`stop = candidate_price ∓ 1 tick`) just
       suffered a stop-loss invalidation (`reg_bull_stop_break` / `hid_bull_stop_break` for longs;
       `reg_bear_stop_break` / `hid_bear_stop_break` for shorts):
       - Cuts/dampens same-side exposure by `guard_strength` to prevent holding into a broken pivot!
    """
    idx_te = np.flatnonzero(te_mask)
    p = pos_base.copy()

    res_1h = np.tanh(fib_1h_df["net_fib_res_active_1h"].to_numpy(dtype=np.float64)[idx_te])
    res_5m = np.tanh(fib_5m_df["net_fib_res_active_5m"].to_numpy(dtype=np.float64)[idx_te])
    act_1h = np.tanh(fib_1h_df["net_fib_active_rr_1h"].to_numpy(dtype=np.float64)[idx_te] * 0.5)

    # Same-side stop break invalidation (long stop broken vs short stop broken)
    long_stop_brk = np.tanh(
        (
            fib_1h_df["reg_bull_stop_break_1h_ema6"].to_numpy(dtype=np.float64)[idx_te]
            + fib_1h_df["hid_bull_stop_break_1h_ema6"].to_numpy(dtype=np.float64)[idx_te]
            + 0.5 * fib_5m_df["reg_bull_stop_break_5m_ema6"].to_numpy(dtype=np.float64)[idx_te]
        )
    )
    short_stop_brk = np.tanh(
        (
            fib_1h_df["reg_bear_stop_break_1h_ema6"].to_numpy(dtype=np.float64)[idx_te]
            + fib_1h_df["hid_bear_stop_break_1h_ema6"].to_numpy(dtype=np.float64)[idx_te]
            + 0.5 * fib_5m_df["reg_bear_stop_break_5m_ema6"].to_numpy(dtype=np.float64)[idx_te]
        )
    )

    fib_signal = 0.50 * res_1h + 0.25 * act_1h + 0.25 * res_5m

    for i in range(len(p)):
        if abs(p[i]) < 1e-6:
            continue
        side = 1.0 if p[i] > 0 else -1.0
        align = side * fib_signal[i]  # >0 if Fib channel aligns with position, <0 if opposing
        stop_hit = long_stop_brk[i] if side > 0 else short_stop_brk[i]
        mult = 1.0 + guard_strength * align - guard_strength * stop_hit
        mult = float(np.clip(mult, 0.35, 1.15))
        p[i] = float(np.clip(p[i] * mult, -1.0, 1.0))

    return p


def _summarize_variant(
    name: str,
    way: str,
    threshold_policy: str,
    bundle: DatasetBundle,
    pos_by_year: Dict[int, Tuple[np.ndarray, np.ndarray]],
    leverage: float = 3.0,
) -> Dict[str, Any]:
    r25, m25 = evaluate_position_path(
        bundle, pos_by_year[2025][0], pos_by_year[2025][1], one_way_cost_bp=0.5, leverage=leverage
    )
    r26, m26 = evaluate_position_path(
        bundle, pos_by_year[2026][0], pos_by_year[2026][1], one_way_cost_bp=0.5, leverage=leverage
    )
    r25_0, _ = evaluate_position_path(
        bundle, pos_by_year[2025][0], pos_by_year[2025][1], one_way_cost_bp=0.0, leverage=leverage
    )
    r26_0, _ = evaluate_position_path(
        bundle, pos_by_year[2026][0], pos_by_year[2026][1], one_way_cost_bp=0.0, leverage=leverage
    )
    # Fix #2: Evaluate connected 2025-2026 multi-year equity path for exact cross-year MaxDD and monthly stats
    full_mask = pos_by_year[2025][0] | pos_by_year[2026][0]
    full_pos = np.zeros(len(bundle.index), dtype=np.float64)
    full_pos[pos_by_year[2025][0]] = pos_by_year[2025][1]
    full_pos[pos_by_year[2026][0]] = pos_by_year[2026][1]
    r_full, m_full = evaluate_position_path(
        bundle, full_mask, full_pos[full_mask], one_way_cost_bp=0.5, leverage=leverage
    )
    r_full_0, _ = evaluate_position_path(
        bundle, full_mask, full_pos[full_mask], one_way_cost_bp=0.0, leverage=leverage
    )
    comp = r_full["total_return_pct"]
    comp_0bp = r_full_0["total_return_pct"]
    max_dd = min(r_full["max_drawdown_pct"], r25["max_drawdown_pct"], r26["max_drawdown_pct"])
    worst_m = r_full["worst_month_pct"]
    mean_sh = 0.5 * (r25["sharpe_daily"] + r26["sharpe_daily"])
    pos_m = int((m_full > 0).sum())
    tot_m = int(len(m_full))
    liq = r_full["liquidations"]
    trades = r_full["round_trips_equiv"]
    return {
        "variant": name,
        "way": way,
        "threshold_policy": threshold_policy,
        "leverage": leverage,
        "ret_2025_pct": round(r25["total_return_pct"], 2),
        "dd_2025_pct": round(r25["max_drawdown_pct"], 2),
        "sharpe_2025": round(r25["sharpe_daily"], 2),
        "ret_2026_pct": round(r26["total_return_pct"], 2),
        "dd_2026_pct": round(r26["max_drawdown_pct"], 2),
        "sharpe_2026": round(r26["sharpe_daily"], 2),
        "compounded_2025_2026_pct": round(comp, 2),
        "compounded_0bp_pct": round(comp_0bp, 2),
        "max_dd_2025_2026_pct": round(max_dd, 2),
        "worst_month_pct": round(worst_m, 2),
        "mean_daily_sharpe": round(mean_sh, 2),
        "positive_months": f"{pos_m}/{tot_m}",
        "total_round_trips": round(float(trades), 1),
        "liquidations": int(liq),
    }


def main() -> None:
    t0 = time.time()
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    bundle = build_dataset_bundle("BTCUSDT")

    print("[Phase 5] Extracting Causal Fibonacci (0.236/0.382) + Stop Protection + RSI Layer features...")
    frames, plan_stats = build_all_fib_divergence_frames(bundle)

    # Save plan generation & lifecycle audit summary
    for tf_k, st in plan_stats.items():
        print(
            f"  - {tf_k}: armed={st['armed_plans']}, resonance={st['resonance_plans']}, "
            f"triggered_0236={st['triggered_plans']}, stop_broken={st['stop_broken_plans']}, "
            f"target_0382_hit={st['target_hit_plans']}"
        )

    # Part A: Standalone Factor & State Evaluation
    df_standalone = evaluate_standalone_fib_factors(bundle, frames)
    standalone_csv = RUNS_DIR / "phase5_fib_standalone_metrics.csv"
    df_standalone.to_csv(standalone_csv, index=False)
    print(f"[Phase 5] Saved standalone metrics ({len(df_standalone)} rows) -> {standalone_csv}")

    # Combine feature sets for ML integration
    df_5m = frames["5m"]
    df_1h = frames["1h"]
    df_5m_1h = pd.concat([df_5m, df_1h], axis=1)
    df_all_mtf = pd.concat([frames["5m"], frames["15m"], frames["1h"], frames["4h"], frames["eth1h"], frames["sol1h"]], axis=1)

    # Also build combined Phase 4 Co-Pivot + Phase 5 Fibonacci feature matrix
    from research.zero_fee_maker_ml_v1.code.phase4_divergence_study import build_5m_and_1h_divergence_frames
    _, _, div_copiv_ml, _ = build_5m_and_1h_divergence_frames(bundle, co_pivot=True)
    df_copiv_plus_fib = pd.concat([div_copiv_ml, df_all_mtf], axis=1)

    # Fit Baseline M2 models per fold
    base_gbdt: Dict[int, Dict[str, np.ndarray]] = {}
    base_lin: Dict[int, Dict[str, np.ndarray]] = {}
    base_pos: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}

    fib_specs: Dict[str, Dict[int, Dict[str, Any]]] = {
        "FIB_5M": {},
        "FIB_1H": {},
        "FIB_5M_1H": {},
        "FIB_ALL_MTF": {},
        "COPIV_PLUS_FIB_ALL": {},
    }

    for fold in FOLDS:
        yr = fold.year
        base_gbdt[yr] = _fit_fast_30m_60m_pair(
            bundle,
            fold.train_start,
            fold.train_end,
            fold.val_start,
            fold.val_end,
            fold.test_start,
            fold.test_end,
            purged_chrono_hgb=True,
        )
        base_lin[yr] = _fit_multi_horizon_ridge(
            bundle, fold.train_start, fold.train_end, fold.val_start, fold.val_end, fold.test_start, fold.test_end
        )
        fib_specs["FIB_5M"][yr] = _fit_learned_fib_specialist(
            bundle, df_5m, fold.train_start, fold.train_end, fold.val_start, fold.val_end, fold.test_start, fold.test_end
        )
        fib_specs["FIB_1H"][yr] = _fit_learned_fib_specialist(
            bundle, df_1h, fold.train_start, fold.train_end, fold.val_start, fold.val_end, fold.test_start, fold.test_end
        )
        fib_specs["FIB_5M_1H"][yr] = _fit_learned_fib_specialist(
            bundle, df_5m_1h, fold.train_start, fold.train_end, fold.val_start, fold.val_end, fold.test_start, fold.test_end
        )
        fib_specs["FIB_ALL_MTF"][yr] = _fit_learned_fib_specialist(
            bundle, df_all_mtf, fold.train_start, fold.train_end, fold.val_start, fold.val_end, fold.test_start, fold.test_end
        )
        fib_specs["COPIV_PLUS_FIB_ALL"][yr] = _fit_learned_fib_specialist(
            bundle, df_copiv_plus_fib, fold.train_start, fold.train_end, fold.val_start, fold.val_end, fold.test_start, fold.test_end
        )

    base_mature = _build_mature_quarterly_positions(bundle, base_gbdt)
    for fold in FOLDS:
        yr = fold.year
        p_m2 = _build_m2_positions_with_overlay(
            bundle,
            base_gbdt[yr],
            base_lin[yr],
            base_mature[yr],
            np.zeros_like(base_gbdt[yr]["va_joint"]),
            np.zeros_like(base_gbdt[yr]["te_joint"]),
            w_overlay=0.0,
            freeze_base_thresholds=True,
        )
        base_pos[yr] = (base_gbdt[yr]["te_mask"], p_m2)

    summary_rows: List[Dict[str, Any]] = []
    summary_rows.append(_summarize_variant("M2_BASELINE_3X", "BASELINE", "BASELINE", bundle, base_pos))

    # Fix #5 Control: Zero-specialist shrinkage control `(1 - w) * base + 0` under FROZEN_TH
    for w in (0.08, 0.15):
        w_tag = f"w{int(w * 100):02d}"
        pos_ctrl: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}
        for fold in FOLDS:
            yr = fold.year
            p_c = _build_m2_positions_with_overlay(
                bundle,
                base_gbdt[yr],
                base_lin[yr],
                base_mature[yr],
                np.zeros_like(base_gbdt[yr]["va_joint"]),
                np.zeros_like(base_gbdt[yr]["te_joint"]),
                w_overlay=w,
                freeze_base_thresholds=True,
                blend_mode="ZERO_SPEC_SHRINK",
            )
            pos_ctrl[yr] = (base_gbdt[yr]["te_mask"], p_c)
        summary_rows.append(
            _summarize_variant(
                f"W2_ZERO_SPEC_SHRINK_CTRL_{w_tag}_FROZEN_TH",
                "WAY2_SHRINKAGE_CONTROL",
                "FROZEN_TH",
                bundle,
                pos_ctrl,
            )
        )

    # Way 1: Direct Feature Retraining (`5m` only, `1h` only, `5m+1h`, `all_mtf`)
    for w1_name, extra_df in [
        ("W1_RETRAIN_FIB_5M", df_5m),
        ("W1_RETRAIN_FIB_1H", df_1h),
        ("W1_RETRAIN_FIB_5M_1H", df_5m_1h),
        ("W1_RETRAIN_FIB_ALL_MTF", df_all_mtf),
    ]:
        aug_bundle = copy.copy(bundle)
        aug_bundle.features = pd.concat([bundle.features, extra_df], axis=1)
        pos_w1: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}
        for fold in FOLDS:
            yr = fold.year
            g_res = _fit_fast_30m_60m_pair(
                aug_bundle,
                fold.train_start,
                fold.train_end,
                fold.val_start,
                fold.val_end,
                fold.test_start,
                fold.test_end,
                purged_chrono_hgb=True,
            )
            l_res = _fit_multi_horizon_ridge(
                aug_bundle, fold.train_start, fold.train_end, fold.val_start, fold.val_end, fold.test_start, fold.test_end
            )
            p_w1 = _build_m2_positions_with_overlay(
                aug_bundle,
                g_res,
                l_res,
                base_mature[yr],
                np.zeros_like(g_res["va_joint"]),
                np.zeros_like(g_res["te_joint"]),
                w_overlay=0.0,
                freeze_base_thresholds=False,
            )
            pos_w1[yr] = (g_res["te_mask"], p_w1)
        summary_rows.append(_summarize_variant(w1_name, "WAY1_DIRECT_RETRAIN", "RECAL_TH", bundle, pos_w1))

    # Way 2A: Walk-Forward Learned Fibonacci Specialist (CONVEX blend under FROZEN_TH and RECAL_TH)
    # Plus Fix #5: True ADDITIVE overlay (`base + w * overlay` under FROZEN_TH: zero specialist = 0 change!)
    val_candidates_convex: Dict[int, List[Tuple[float, str, np.ndarray]]] = {2025: [], 2026: []}
    val_candidates_additive: Dict[int, List[Tuple[float, str, np.ndarray]]] = {2025: [], 2026: []}

    for spec_key, spec_folds in fib_specs.items():
        for w in (0.08, 0.15):
            w_tag = f"w{int(w * 100):02d}"
            for freeze_th, th_label in [(True, "FROZEN_TH"), (False, "RECAL_TH")]:
                pos_w2: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}
                for fold in FOLDS:
                    yr = fold.year
                    p_ov = _build_m2_positions_with_overlay(
                        bundle,
                        base_gbdt[yr],
                        base_lin[yr],
                        base_mature[yr],
                        spec_folds[yr]["va_z"],
                        spec_folds[yr]["te_z"],
                        w_overlay=w,
                        freeze_base_thresholds=freeze_th,
                        blend_mode="CONVEX",
                    )
                    pos_w2[yr] = (base_gbdt[yr]["te_mask"], p_ov)
                    if freeze_th:
                        p_va = _build_m2_positions_with_overlay(
                            bundle,
                            base_gbdt[yr],
                            base_lin[yr],
                            base_mature[yr],
                            spec_folds[yr]["va_z"],
                            spec_folds[yr]["te_z"],
                            w_overlay=w,
                            freeze_base_thresholds=True,
                            blend_mode="CONVEX",
                            eval_on_val=True,
                        )
                        r_va, _ = evaluate_position_path(
                            bundle, base_gbdt[yr]["va_mask"], p_va, one_way_cost_bp=0.5, leverage=3.0
                        )
                        val_candidates_convex[yr].append(
                            (float(r_va["sharpe_daily"]), f"{spec_key}_{w_tag}", p_ov)
                        )
                v_name = f"W2_LEARNED_{spec_key}_{w_tag}_{th_label}"
                summary_rows.append(_summarize_variant(v_name, "WAY2_LEARNED_SPECIALIST", th_label, bundle, pos_w2))

            # True ADDITIVE overlay (`base + w * overlay` under FROZEN_TH)
            pos_add: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}
            for fold in FOLDS:
                yr = fold.year
                p_add = _build_m2_positions_with_overlay(
                    bundle,
                    base_gbdt[yr],
                    base_lin[yr],
                    base_mature[yr],
                    spec_folds[yr]["va_z"],
                    spec_folds[yr]["te_z"],
                    w_overlay=w,
                    freeze_base_thresholds=True,
                    blend_mode="ADDITIVE",
                )
                pos_add[yr] = (base_gbdt[yr]["te_mask"], p_add)
                p_va_add = _build_m2_positions_with_overlay(
                    bundle,
                    base_gbdt[yr],
                    base_lin[yr],
                    base_mature[yr],
                    spec_folds[yr]["va_z"],
                    spec_folds[yr]["te_z"],
                    w_overlay=w,
                    freeze_base_thresholds=True,
                    blend_mode="ADDITIVE",
                    eval_on_val=True,
                )
                r_va_add, _ = evaluate_position_path(
                    bundle, base_gbdt[yr]["va_mask"], p_va_add, one_way_cost_bp=0.5, leverage=3.0
                )
                val_candidates_additive[yr].append(
                    (float(r_va_add["sharpe_daily"]), f"{spec_key}_{w_tag}", p_add)
                )
            summary_rows.append(
                _summarize_variant(
                    f"W2_ADDITIVE_{spec_key}_{w_tag}_FROZEN_TH",
                    "WAY2_ADDITIVE_INVARIANT",
                    "FROZEN_TH",
                    bundle,
                    pos_add,
                )
            )

    # Fix #4: Pre-test Validation-Locked Selection Protocol (selects best candidate per fold strictly on va_mask!)
    val_selected_meta: Dict[str, Dict[int, str]] = {"CONVEX_FROZEN_TH": {}, "ADDITIVE_FROZEN_TH": {}}
    pos_val_locked_convex: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}
    pos_val_locked_additive: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}
    for fold in FOLDS:
        yr = fold.year
        best_c = sorted(val_candidates_convex[yr], key=lambda x: x[0], reverse=True)[0]
        val_selected_meta["CONVEX_FROZEN_TH"][yr] = f"{best_c[1]} (val_sharpe={best_c[0]:.2f})"
        pos_val_locked_convex[yr] = (base_gbdt[yr]["te_mask"], best_c[2])

        best_a = sorted(val_candidates_additive[yr], key=lambda x: x[0], reverse=True)[0]
        val_selected_meta["ADDITIVE_FROZEN_TH"][yr] = f"{best_a[1]} (val_sharpe={best_a[0]:.2f})"
        pos_val_locked_additive[yr] = (base_gbdt[yr]["te_mask"], best_a[2])

    summary_rows.append(
        _summarize_variant(
            "W2_VAL_LOCKED_SELECTOR_CONVEX_FROZEN_TH",
            "WAY2_VAL_LOCKED_PROTOCOL",
            "FROZEN_TH",
            bundle,
            pos_val_locked_convex,
        )
    )
    summary_rows.append(
        _summarize_variant(
            "W2_VAL_LOCKED_SELECTOR_ADDITIVE_FROZEN_TH",
            "WAY2_VAL_LOCKED_PROTOCOL",
            "FROZEN_TH",
            bundle,
            pos_val_locked_additive,
        )
    )

    # Way 3: Causal Fibonacci Stop-Loss & RSI-Resonance Protective Guard on M2
    for g_str in (0.15, 0.25):
        g_tag = f"g{int(g_str * 100):02d}"
        pos_w3: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}
        for fold in FOLDS:
            yr = fold.year
            te_m, p_b = base_pos[yr]
            p_guarded = _apply_causal_fib_stop_target_guard(p_b, te_m, df_1h, df_5m, guard_strength=g_str)
            pos_w3[yr] = (te_m, p_guarded)
        summary_rows.append(
            _summarize_variant(f"W3_FIB_STOP_TARGET_GUARD_{g_tag}", "WAY3_PROTECTIVE_GUARD", "FROZEN_TH", bundle, pos_w3)
        )

    # Way 4: Combined Walk-Forward Learned Specialist + Causal Fibonacci Stop-Target Protective Guard
    for spec_key in ("FIB_5M_1H", "FIB_ALL_MTF", "COPIV_PLUS_FIB_ALL"):
        for freeze_th, th_label in [(True, "FROZEN_TH"), (False, "RECAL_TH")]:
            pos_w4: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}
            for fold in FOLDS:
                yr = fold.year
                p_ov = _build_m2_positions_with_overlay(
                    bundle,
                    base_gbdt[yr],
                    base_lin[yr],
                    base_mature[yr],
                    fib_specs[spec_key][yr]["va_z"],
                    fib_specs[spec_key][yr]["te_z"],
                    w_overlay=0.15,
                    freeze_base_thresholds=freeze_th,
                )
                p_comb = _apply_causal_fib_stop_target_guard(
                    p_ov, base_gbdt[yr]["te_mask"], df_1h, df_5m, guard_strength=0.15
                )
                pos_w4[yr] = (base_gbdt[yr]["te_mask"], p_comb)
            v_name = f"W4_COMBINED_{spec_key}_{th_label}"
            summary_rows.append(
                _summarize_variant(v_name, "WAY4_LEARNED_PLUS_GUARD", th_label, bundle, pos_w4)
            )

    df_summary = pd.DataFrame(summary_rows)
    summary_csv = RUNS_DIR / "phase5_fib_m2_integration_summary.csv"
    df_summary.to_csv(summary_csv, index=False)

    import hashlib
    def _file_sha256(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "MISSING"

    code_dir = ROOT / "research" / "zero_fee_maker_ml_v1" / "code"
    report = {
        "generated_at_utc": str(pd.Timestamp.now(tz="UTC")),
        "elapsed_sec": round(time.time() - t0, 2),
        "source_code_sha256": {
            "phase5_fib_divergence_study.py": _file_sha256(code_dir / "phase5_fib_divergence_study.py"),
            "phase2_focused_study.py": _file_sha256(code_dir / "phase2_focused_study.py"),
            "phase3_master_ensemble.py": _file_sha256(code_dir / "phase3_master_ensemble.py"),
            "features.py": _file_sha256(code_dir / "features.py"),
        },
        "validation_locked_selections": val_selected_meta,
        "plan_lifecycle_stats": plan_stats,
        "specialist_top_coefs_2026": {k: v[2026]["top_coef_60"] for k, v in fib_specs.items()},
        "m2_integration_summary": summary_rows,
    }
    report_json = RUNS_DIR / "phase5_fib_divergence_report.json"
    report_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n=== Phase 5 Fibonacci (0.236/0.382) + Stop/Target Protection M2 (3.0X) Summary ===")
    print(df_summary.to_string(index=False))


if __name__ == "__main__":
    main()
