"""Frozen v8 complete-bar aggregation and fresh-2026 causal 5m mapping."""
from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd

from signals_v8 import TYPE_ORDER, make_candidate_plans_since, pivots_causal

# This module is a local 4h adapter over the frozen v8 indexed generator.

TF_MINUTES = {"4h": 240}
HIDDEN_TYPES = ("hidden_bearish", "hidden_bullish")
ALL_TYPES = tuple(TYPE_ORDER)
START_NS = pd.Timestamp("2026-01-01T00:00:00Z").value
END_NS = pd.Timestamp("2026-10-26T00:00:00Z").value
EXEC_STEP_NS = 300_000_000_000


def aggregate_complete_5m(bars: pd.DataFrame, tf: str) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    """Aggregate complete UTC buckets from a gap-free 5m source; reject partials."""
    if tf not in TF_MINUTES:
        raise ValueError(f"unsupported timeframe {tf}")
    n5 = TF_MINUTES[tf] // 5
    if len(bars) % n5:
        raise ValueError(f"incomplete final {tf} bar")
    t = pd.to_datetime(bars.open_time, utc=True).array.asi8
    if len(t) == 0 or np.any(np.diff(t) != EXEC_STEP_NS):
        raise ValueError("5m input is empty or has gaps, duplicates, or irregular spacing")
    if t[0] % (TF_MINUTES[tf] * 60_000_000_000):
        raise ValueError(f"5m input is not UTC {tf}-aligned")
    arr = {k: bars[k].to_numpy(dtype=np.float64).reshape(-1, n5)
           for k in ("open", "high", "low", "close", "volume")}
    if any(not np.isfinite(x).all() for x in arr.values()):
        raise ValueError("5m input has nonfinite OHLCV")
    if ((arr["high"] < arr["low"]) | (arr["high"] < np.maximum(arr["open"], arr["close"]))
            | (arr["low"] > np.minimum(arr["open"], arr["close"])) | (arr["volume"] < 0)).any():
        raise ValueError("5m input has invalid OHLCV")
    hi, lo = arr["high"], arr["low"]
    highs, lows = hi.max(axis=1), lo.min(axis=1)
    n = len(highs); blocks = np.arange(len(bars), dtype=np.int64).reshape(n, n5)
    occ = {
        "high_constituent_index_5m_global": blocks[np.arange(n), np.argmax(hi == highs[:, None], axis=1)],
        "low_constituent_index_5m_global": blocks[np.arange(n), np.argmax(lo == lows[:, None], axis=1)],
        "constituent_first_index_5m_global": blocks[:, 0],
        "constituent_last_index_5m_global": blocks[:, -1],
    }
    frame = pd.DataFrame({
        "open_time": pd.to_datetime(t[::n5], utc=True),
        "open": arr["open"][:, 0], "high": highs, "low": lows,
        "close": arr["close"][:, -1], "volume": arr["volume"].sum(axis=1),
    })
    if not (frame.open_time.diff().dropna() == pd.Timedelta(minutes=TF_MINUTES[tf])).all():
        raise AssertionError("aggregate is not a complete uniform grid")
    return frame, occ


def plans_for_timeframe(bars5_all: pd.DataFrame, bars5_exec: pd.DataFrame, tf: str):
    """Build all four frozen v4 signal types, warmup-only before 2026, map to 5m."""
    signal, occ = aggregate_complete_5m(bars5_all, tf)
    pivots = pivots_causal(signal, 300)
    close = signal.close.to_numpy(np.float64)
    dif = pd.Series(close).ewm(span=12, adjust=False).mean().to_numpy() - pd.Series(close).ewm(span=26, adjust=False).mean().to_numpy()
    exec_global_start = int(np.searchsorted(pd.to_datetime(bars5_all.open_time, utc=True).array.asi8,
                                            pd.to_datetime(bars5_exec.open_time.iloc[0], utc=True).value))
    exec_open = pd.to_datetime(bars5_exec.open_time, utc=True).array.asi8
    signal_open = signal.open_time.array.asi8
    tf_ns = TF_MINUTES[tf] * 60_000_000_000
    first_eligible = int(np.searchsorted(signal_open + tf_ns, START_NS, side="left"))
    raw_legs, raw_meta = make_candidate_plans_since(signal, pivots, dif, first_eligible)
    legs: list[dict[str, Any]] = []; versions: list[dict[str, Any]] = []; events: list[dict[str, Any]] = []
    counts = {"raw_divergence_candidate_versions_by_type": {k: 0 for k in ALL_TYPES},
              "qualified_plan_versions_by_type": {k: 0 for k in ALL_TYPES},
              "version_status_by_type": {k: {} for k in ALL_TYPES},
              "hidden_trend_rejected_by_type": {k: 0 for k in HIDDEN_TYPES},
              "invalid_or_missing_target_by_type": {k: 0 for k in ALL_TYPES},
              "leg_count": 0, "signal_bar_count": len(signal), "pivot_count": len(pivots),
              "first_eligible_signal_index": first_eligible,
              "first_eligible_decision_close_utc": pd.Timestamp(signal_open[first_eligible] + tf_ns, tz="UTC").isoformat() if first_eligible < len(signal) else None}
    for raw in raw_legs:
        kept = [v for v in raw["versions"] if int(v["decision_index"]) >= first_eligible]
        if not kept:
            continue
        leg = dict(raw); leg["case_id"] = f"{tf}_{raw['case_id']}"; leg["leg_id"] = leg["case_id"]
        leg["signal_tf"] = tf; leg["signal_tf_minutes"] = TF_MINUTES[tf]
        leg["p1_signal_tf"] = dict(raw["p1"]); leg["middle_signal_tf"] = dict(raw["middle"])
        mapped = []; versions_by_id = {int(v["version"]): v for v in kept}
        for v0 in kept:
            v = dict(v0); ci = int(v["candidate_extreme_index"]); di = int(v["decision_index"])
            if not (0 <= ci < len(signal) and first_eligible <= di < len(signal)):
                raise AssertionError("signal index outside frozen scan window")
            kind = str(v["type"])
            extreme_global = int(occ["high_constituent_index_5m_global"][ci] if kind.endswith("bearish") else occ["low_constituent_index_5m_global"][ci])
            bns = int(signal_open[di] + tf_ns)
            act = int(np.searchsorted(exec_open, bns, side="left"))
            deadline = bns + 24 * tf_ns
            exp = int(np.searchsorted(exec_open, deadline, side="left"))
            year_end = int(exec_open[-1] + EXEC_STEP_NS)
            if v.get("armed") and act >= len(exec_open):
                v["armed"] = False; v["status"] = "NO_ACTIVATION_BAR"; v["rationale"] = v["status"]
            active_through = exp - 1 if deadline <= year_end else len(exec_open)
            v.update({"case_id": leg["case_id"], "signal_tf": tf, "signal_tf_minutes": TF_MINUTES[tf],
                      "decision_index_signal_tf": di, "candidate_extreme_index_signal_tf": ci,
                      "candidate_extreme_bar_open_utc": pd.Timestamp(signal_open[ci], tz="UTC").isoformat(),
                      "candidate_extreme_constituent_5m_index_global": extreme_global,
                      "candidate_extreme_constituent_5m_index_exec": extreme_global-exec_global_start if extreme_global >= exec_global_start else None,
                      "candidate_extreme_constituent_5m_open_utc": pd.Timestamp(pd.to_datetime(bars5_all.open_time.iloc[extreme_global], utc=True).value, tz="UTC").isoformat(),
                      "activation_index_signal_tf": int(v0["activation_index"]), "decision_close_utc": pd.Timestamp(bns, tz="UTC").isoformat(),
                      "activation_index_5m": act, "activation_open_5m_utc": pd.Timestamp(exec_open[act], tz="UTC").isoformat() if act < len(exec_open) else None,
                      "active_through_index_5m": active_through, "expiry_deadline_utc": pd.Timestamp(deadline, tz="UTC").isoformat(),
                      "active_from_index": act, "active_through_index": active_through,
                      "activation_index": act, "activation_open_utc": pd.Timestamp(exec_open[act], tz="UTC").isoformat() if act < len(exec_open) else None})
            mapped.append(v); versions.append(v)
            status = str(v.get("status", "UNKNOWN")); b = counts["version_status_by_type"][kind]; b[status] = b.get(status, 0)+1
            counts["raw_divergence_candidate_versions_by_type"][kind] += 1
            if (v.get("levels") or {}).get("level_status") == "READY": counts["qualified_plan_versions_by_type"][kind] += 1
            if v.get("rationale") == "HIDDEN_TREND_NOT_CONFIRMED": counts["hidden_trend_rejected_by_type"][kind] += 1
            if str(v.get("rationale", "")).startswith(("MISSING_", "INVALID_")) or v.get("rationale") == "INVALID_LEVEL_ORDER":
                counts["invalid_or_missing_target_by_type"][kind] += 1
        leg["versions"] = mapped
        leg["events"] = []
        for e0 in raw["events"]:
            if int(e0["version"]) not in versions_by_id or int(e0["index"]) < first_eligible:
                continue
            e = dict(e0); si = int(e["index"]); boundary = int(signal_open[si] + tf_ns)
            exec_close_idx = int(np.searchsorted(exec_open, boundary, side="left") - 1)
            e.update({"case_id": leg["case_id"], "signal_tf": tf, "signal_index": si,
                      "execution_close_index": exec_close_idx,
                      "execution_close_utc": pd.Timestamp(boundary, tz="UTC").isoformat(), "index": exec_close_idx})
            leg["events"].append(e); events.append(e)
        counts["leg_count"] += 1; legs.append(leg)
    counts["version_count"] = len(versions)
    counts["raw_v4_counts_since_2024"] = {
        f: {k: raw_meta["counts"].get(f, {}).get(k, 0) for k in ALL_TYPES}
        for f in ("raw_divergence_candidate_versions_by_type", "qualified_plan_versions_by_type",
                  "hidden_trend_rejected_by_type", "invalid_or_missing_target_by_type")}
    return signal, occ, legs, versions, events, counts, dif, pivots






