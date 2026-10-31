"""V8 copy of the frozen v6 plan generator with exact indexed pivot lookup."""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import asdict

import numpy as np
import pandas as pd

from signals_v4 import (TICK, MIN_SEP, MAX_SEP, BIG_LOOKBACK, ORDER_EXPIRY, TYPE_ORDER,
                        _ct, _ft, _levels, _kind, pivots_causal)


class ConfirmedPivotIndex:
    """Indexed equivalent of `[p for p in pivots if p.confirm_index <= d]`.

    Pivot and confirmation indices are monotonic. The generator only consumes
    local 288-bar regular anchors and the last two known highs/lows before the
    candidate for hidden trend evidence, so this returns exactly those relevant
    confirmed pivots in their original order without copying the full prefix.
    """

    def __init__(self, pivots: list):
        self.pivots = pivots
        self.indices = [int(p.index) for p in pivots]
        self.confirms = [int(p.confirm_index) for p in pivots]
        if (any(a >= b for a, b in zip(self.indices, self.indices[1:]))
                or any(a >= b for a, b in zip(self.confirms, self.confirms[1:]))
                or any(i >= c for i, c in zip(self.indices, self.confirms))):
            raise ValueError("pivot index must preserve chronological confirmation order")
        self.by_kind = {}
        for kind in ("high", "low"):
            records = [(int(p.index), int(p.confirm_index), i)
                       for i, p in enumerate(pivots) if p.kind == kind]
            self.by_kind[kind] = {
                "indices": [x[0] for x in records],
                "confirms": [x[1] for x in records],
                "positions": [x[2] for x in records],
            }

    def relevant(self, decision: int, candidate: int, p1, signal_type: str) -> list:
        chosen: set[int] = set()
        for kind, records in self.by_kind.items():
            kind_indices = records["indices"]
            kind_confirms = records["confirms"]
            end_by_candidate = bisect_left(kind_indices, candidate)
            end_by_decision = bisect_right(kind_confirms, decision)
            known_before_candidate = min(end_by_candidate, end_by_decision)
            # Hidden trend checks read only the last two confirmed highs/lows.
            chosen.update(records["positions"][max(0, known_before_candidate - 2):known_before_candidate])

        if signal_type == "regular_bullish":
            anchor_kind = "high"
        elif signal_type == "regular_bearish":
            anchor_kind = "low"
        else:
            anchor_kind = None
        if anchor_kind is not None:
            records = self.by_kind[anchor_kind]
            ix = records["indices"]
            lo = bisect_left(ix, int(p1.index) - BIG_LOOKBACK)
            hi = bisect_left(ix, int(p1.index))
            known = [records["positions"][j] for j in range(lo, hi)
                     if records["confirms"][j] <= decision]
            chosen.update(known)
        return [self.pivots[i] for i in sorted(chosen)]


def make_candidate_plans_since(bars: pd.DataFrame, pivots: list, dif: np.ndarray,
                               decision_start_index: int) -> tuple[list[dict], dict]:
    """Frozen v6 generator semantics with the complete-prefix rescan indexed."""
    hi = bars.high.to_numpy(float)
    lo = bars.low.to_numpy(float)
    close = bars.close.to_numpy(float)
    legs = []
    all_versions = []
    all_events = []
    raw_count = {k: 0 for k in TYPE_ORDER}
    qualified_count = {k: 0 for k in TYPE_ORDER}
    trend_reject = {k: 0 for k in TYPE_ORDER}
    invalid = {k: 0 for k in TYPE_ORDER}
    leg_specs = []
    for j in range(2, len(pivots)):
        p1, middle, p2 = pivots[j - 2:j + 1]
        if p1.kind != p2.kind or middle.kind == p1.kind:
            continue
        leg_specs.append((p1, middle, p2))
    if len(pivots) >= 2 and pivots[-2].kind != pivots[-1].kind:
        leg_specs.append((pivots[-2], pivots[-1], None))

    lookup = ConfirmedPivotIndex(pivots)
    for p1, middle, p2 in leg_specs:
        leg_id = f"LEG_{p1.kind}_{p1.index:06d}_{middle.index:06d}"
        seed = (hi if p1.kind == "high" else lo)[middle.index + 1:middle.confirm_index + 1]
        if not len(seed):
            continue
        direction_top = p1.kind == "high"
        cp = float(seed.max() if direction_top else seed.min())
        ci = middle.index + 1 + int(np.flatnonzero(seed == cp)[0])
        d_start = middle.confirm_index
        stop_confirm = p2.confirm_index if p2 is not None else len(bars)
        leg = {"case_id": leg_id, "leg_id": leg_id, "p1": asdict(p1), "middle": asdict(middle),
               "confirmed_end": asdict(p2) if p2 is not None else None,
               "type": "regular_bearish" if direction_top else "regular_bullish", "versions": [], "events": []}
        active_version = None
        seen_identity = set()
        vnum = 0
        d_end = min(stop_confirm - 1, len(bars) - 1)
        for d in range(d_start, d_end + 1):
            refreshed = False
            if d > middle.confirm_index:
                x = float(hi[d] if direction_top else lo[d])
                if (x > cp if direction_top else x < cp):
                    cp = x
                    ci = d
                    refreshed = True
            if refreshed and active_version is not None:
                leg["events"].append({"event": "CANCELLED_EXTREME_REFRESH", "index": d, "version": active_version})
                active_version = None
            if d < decision_start_index:
                continue
            sep = ci - p1.index
            age = d - p1.index
            if not (MIN_SEP <= sep <= MAX_SEP and 0 <= age <= MAX_SEP):
                continue
            kind = _kind(p1, cp, float(dif[p1.index]), float(dif[ci]))
            if kind is None:
                continue
            identity = (kind, ci)
            if identity in seen_identity:
                continue
            seen_identity.add(identity)
            vnum += 1
            raw_count[kind] += 1
            confirmed = lookup.relevant(d, ci, p1, kind)
            rationale = ""
            trend_evidence = None
            if kind.startswith("hidden"):
                highs = [p for p in confirmed if p.kind == "high" and p.index < ci]
                lows = [p for p in confirmed if p.kind == "low" and p.index < ci]
                h2 = highs[-2:] if len(highs) >= 2 else []
                l2 = lows[-2:] if len(lows) >= 2 else []
                trend_evidence = {"highs": [asdict(p) for p in h2], "lows": [asdict(p) for p in l2]}
                up = len(h2) == 2 and len(l2) == 2 and h2[1].price > h2[0].price and l2[1].price > l2[0].price
                down = len(h2) == 2 and len(l2) == 2 and h2[1].price < h2[0].price and l2[1].price < l2[0].price
                trend_ok = up if kind == "hidden_bullish" else down
                if not trend_ok:
                    rationale = "HIDDEN_TREND_NOT_CONFIRMED"
                    trend_reject[kind] += 1
            else:
                trend_ok = True
            levels = {"level_status": rationale or "NOT_COMPUTED"}
            if trend_ok:
                levels = _levels(kind, p1, middle, ci, cp, confirmed, bars, d)
                if levels["level_status"] != "READY":
                    rationale = levels["level_status"]
                    invalid[kind] += 1
                else:
                    qualified_count[kind] += 1
            version = {"version": vnum, "type": kind, "decision_index": d,
                       "decision_close_utc": (pd.Timestamp(bars.open_time.iloc[d]) + pd.Timedelta(minutes=5)).isoformat(),
                       "candidate_extreme_index": ci, "candidate_extreme_open_utc": pd.Timestamp(bars.open_time.iloc[ci]).isoformat(),
                       "candidate_price": cp, "candidate_dif": float(dif[ci]), "activation_index": d + 1,
                       "activation_open_utc": pd.Timestamp(bars.open_time.iloc[d]) + pd.Timedelta(minutes=5),
                       "active_from_index": d + 1, "active_through_index": d + 24, "p1_age_bars": age,
                       "separation_bars": sep, "trend_evidence": trend_evidence, "levels": levels,
                       "status": "NOT_ARMED", "armed": False, "rationale": rationale}
            if trend_ok and levels.get("level_status") == "READY":
                entry = float(levels["entry"])
                pre_side = close[d] < entry if kind in ("regular_bullish", "hidden_bullish") else close[d] > entry
                start = ci + 1
                touched = False
                if start <= d:
                    touched = bool(np.max(hi[start:d + 1]) >= entry) if kind in ("regular_bullish", "hidden_bullish") else bool(np.min(lo[start:d + 1]) <= entry)
                if not pre_side or touched:
                    version["status"] = "MISSED_BEFORE_ACTIVATION"
                    version["rationale"] = "CLOSE_BEYOND_TRIGGER" if not pre_side else "TRIGGER_TOUCHED_BEFORE_DECISION"
                elif d + 1 >= len(bars):
                    version["status"] = "NO_ACTIVATION_BAR"
                    version["rationale"] = version["status"]
                else:
                    version["status"] = "PENDING"
                    version["armed"] = True
                    leg["type"] = kind
                    active_version = vnum
            leg["versions"].append(version)
            all_versions.append({"case_id": leg_id, **version})
        legs.append(leg)
    for leg in legs:
        for event in leg["events"]:
            all_events.append({"case_id": leg["case_id"], **event})
    counts = {"raw_divergence_candidate_versions_by_type": raw_count,
              "qualified_plan_versions_by_type": qualified_count,
              "hidden_trend_rejected_by_type": trend_reject,
              "invalid_or_missing_target_by_type": invalid,
              "candidate_leg_count": len(legs), "candidate_version_count": len(all_versions),
              "armed_version_count": sum(v["armed"] for v in all_versions), "pivots_count": len(pivots)}
    return legs, {"versions": all_versions, "events": all_events, "counts": counts}
