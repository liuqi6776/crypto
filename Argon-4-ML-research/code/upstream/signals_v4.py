"""Causal full-year candidate plans for the frozen BTC 5m v4 study.

Signal plans are generated from the full fixed window before any account replay;
the replay outcome cannot affect candidate discovery or plan levels.
"""
from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from typing import Any

import numpy as np
import pandas as pd

TICK = Decimal("0.1")
MIN_SEP = 6
MAX_SEP = 144
BIG_LOOKBACK = 288
ORDER_EXPIRY = 24
TYPE_ORDER = {"regular_bearish": 0, "regular_bullish": 1,
              "hidden_bearish": 2, "hidden_bullish": 3}


def ceil_tick(x: float | Decimal) -> float:
    d = x if isinstance(x, Decimal) else Decimal(str(float(x)))
    return float((d / TICK).to_integral_value(rounding=ROUND_CEILING) * TICK)


def floor_tick(x: float | Decimal) -> float:
    d = x if isinstance(x, Decimal) else Decimal(str(float(x)))
    return float((d / TICK).to_integral_value(rounding=ROUND_FLOOR) * TICK)

def _ct(x: Decimal) -> Decimal:
    return (x / TICK).to_integral_value(rounding=ROUND_CEILING) * TICK

def _ft(x: Decimal) -> Decimal:
    return (x / TICK).to_integral_value(rounding=ROUND_FLOOR) * TICK


def pivots_causal(bars: pd.DataFrame, start_index: int = 300):
    """V1 alternating strict-extreme/3-bar/0.2% close reversal state machine."""
    from casebook import Pivot, Candidate, confirm_high, confirm_low
    if start_index < 0 or start_index >= len(bars):
        return []
    hi, lo, close = (bars[k].to_numpy(dtype=np.float64) for k in ("high", "low", "close"))
    direction, cidx, cprice = 1, start_index, float(hi[start_index])
    out = []
    for i in range(start_index + 1, len(bars)):
        if direction == 1:
            if hi[i] > cprice:
                cidx, cprice = i, float(hi[i])
            if i - cidx >= 3 and confirm_high(float(close[i]), cprice):
                out.append(Pivot("high", cidx, cprice, i))
                seg = lo[cidx + 1:i + 1]
                if len(seg):
                    v = float(seg.min()); cidx = cidx + 1 + int(np.flatnonzero(seg == v)[0]); cprice = v
                    direction = -1
        else:
            if lo[i] < cprice:
                cidx, cprice = i, float(lo[i])
            if i - cidx >= 3 and confirm_low(float(close[i]), cprice):
                out.append(Pivot("low", cidx, cprice, i))
                seg = hi[cidx + 1:i + 1]
                if len(seg):
                    v = float(seg.max()); cidx = cidx + 1 + int(np.flatnonzero(seg == v)[0]); cprice = v
                    direction = 1
    if any(a.index >= b.index for a, b in zip(out, out[1:])):
        raise AssertionError("causal pivot extremes are not increasing")
    return out


def _levels(kind: str, p1, middle, candidate_idx: int, candidate_price: float,
            confirmed: list, bars: pd.DataFrame, decision: int) -> dict[str, Any]:
    hi = bars.high.to_numpy(dtype=np.float64); lo = bars.low.to_numpy(dtype=np.float64)
    p2 = type(p1)(p1.kind, candidate_idx, candidate_price, candidate_idx)
    if kind == "regular_bullish":
        seg = hi[p1.index + 1:candidate_idx]
        if not len(seg): return {"level_status": "MISSING_SMALL_ANCHOR"}
        av = float(seg.max()); ai = p1.index + 1 + int(np.flatnonzero(seg == av)[0])
        fib = Decimal(str(candidate_price)) + Decimal("0.236") * (Decimal(str(av)) - Decimal(str(candidate_price)))
        entry = _ct(fib) + TICK; stop = _ft(Decimal(str(candidate_price))) - TICK
        anc = [p for p in confirmed if p.kind == "high" and p.index < p1.index and p1.index-p.index <= BIG_LOOKBACK]
        if not anc: return {"level_status": "MISSING_BIG_ANCHOR", "small_anchor_index": ai, "small_anchor_price": av, "entry": float(entry), "stop": float(stop)}
        extreme = max(p.price for p in anc); big = min((p for p in anc if p.price == extreme), key=lambda p:p.index)
        target = _ft(Decimal(str(candidate_price)) + Decimal("0.382") * (Decimal(str(big.price))-Decimal(str(candidate_price)))) - TICK
        valid = stop < entry < target
    elif kind == "regular_bearish":
        seg = lo[p1.index + 1:candidate_idx]
        if not len(seg): return {"level_status": "MISSING_SMALL_ANCHOR"}
        av = float(seg.min()); ai = p1.index + 1 + int(np.flatnonzero(seg == av)[0])
        fib = Decimal(str(candidate_price)) - Decimal("0.236") * (Decimal(str(candidate_price))-Decimal(str(av)))
        entry = _ft(fib) - TICK; stop = _ct(Decimal(str(candidate_price))) + TICK
        anc = [p for p in confirmed if p.kind == "low" and p.index < p1.index and p1.index-p.index <= BIG_LOOKBACK]
        if not anc: return {"level_status": "MISSING_BIG_ANCHOR", "small_anchor_index": ai, "small_anchor_price": av, "entry": float(entry), "stop": float(stop)}
        extreme = min(p.price for p in anc); big = min((p for p in anc if p.price == extreme), key=lambda p:p.index)
        target = _ct(Decimal(str(candidate_price)) - Decimal("0.382") * (Decimal(str(candidate_price))-Decimal(str(big.price)))) + TICK
        valid = target < entry < stop
    elif kind == "hidden_bullish":
        # Frozen experimental continuation rule: impulse is the confirmed middle
        # pivot, independent of the candidate's small-L2 stop.
        if not (p1.index < middle.index < candidate_idx and middle.confirm_index <= decision):
            return {"level_status":"MISSING_OR_UNCONFIRMED_MIDDLE_IMPULSE"}
        impulse = float(middle.price); l1 = float(p1.price)
        fib = Decimal(str(impulse)) - Decimal("0.236") * (Decimal(str(impulse))-Decimal(str(l1)))
        entry = _ct(fib) + TICK; stop = _ft(Decimal(str(candidate_price))) - TICK
        target = _ft(Decimal(str(impulse)) + Decimal("0.382") * (Decimal(str(impulse))-Decimal(str(l1)))) - TICK
        ai = middle.index; av = impulse; big = middle
        valid = stop < entry < target
    else:
        if not (p1.index < middle.index < candidate_idx and middle.confirm_index <= decision):
            return {"level_status":"MISSING_OR_UNCONFIRMED_MIDDLE_IMPULSE"}
        impulse = float(middle.price); h1 = float(p1.price)
        fib = Decimal(str(impulse)) + Decimal("0.236") * (Decimal(str(h1))-Decimal(str(impulse)))
        entry = _ft(fib) - TICK; stop = _ct(Decimal(str(candidate_price))) + TICK
        target = _ct(Decimal(str(impulse)) - Decimal("0.382") * (Decimal(str(h1))-Decimal(str(impulse)))) + TICK
        ai = middle.index; av = impulse; big = middle
        valid = target < entry < stop
    return {"level_status": "READY" if valid else "INVALID_LEVEL_ORDER", "small_anchor_kind": "middle_impulse" if kind.startswith("hidden") else ("Hsmall" if kind == "regular_bullish" else "Lsmall"),
            "small_anchor_index": int(ai), "small_anchor_price": float(av), "middle_index": int(middle.index), "middle_price": float(middle.price),
            "big_anchor_index": int(big.index), "big_anchor_confirm_index": int(big.confirm_index), "big_anchor_price": float(big.price), "entry": float(entry), "stop": float(stop), "target": float(target)}


def _kind(p1, price: float, d1: float, d2: float):
    if p1.kind == "high":
        if price > p1.price and d2 < d1: return "regular_bearish"
        if price < p1.price and d2 > d1: return "hidden_bearish"
    else:
        if price < p1.price and d2 > d1: return "regular_bullish"
        if price > p1.price and d2 < d1: return "hidden_bullish"
    return None


def make_candidate_plans(bars: pd.DataFrame, pivots: list, dif: np.ndarray) -> tuple[list[dict], dict]:
    """Return one case per pivot leg and causal version/event ledgers."""
    hi=bars.high.to_numpy(float); lo=bars.low.to_numpy(float); close=bars.close.to_numpy(float)
    prefix_hi=np.maximum.accumulate(hi); prefix_lo=np.minimum.accumulate(lo)
    legs=[]; all_versions=[]; all_events=[]; raw_count={k:0 for k in TYPE_ORDER}; qualified_count={k:0 for k in TYPE_ORDER}; trend_reject={k:0 for k in TYPE_ORDER}; invalid={k:0 for k in TYPE_ORDER}
    leg_specs=[]
    for j in range(2,len(pivots)):
        p1,middle,p2=pivots[j-2:j+1]
        if p1.kind != p2.kind or middle.kind == p1.kind: continue
        leg_specs.append((p1,middle,p2))
    # The final in-progress swing has no future confirming pivot inside the year;
    # it is still part of the fixed-window causal scan through the last close.
    if len(pivots)>=2 and pivots[-2].kind!=pivots[-1].kind:
        leg_specs.append((pivots[-2],pivots[-1],None))
    for p1,middle,p2 in leg_specs:
        leg_id=f"LEG_{p1.kind}_{p1.index:06d}_{middle.index:06d}"
        seed=(hi if p1.kind=="high" else lo)[middle.index+1:middle.confirm_index+1]
        if not len(seed): continue
        direction_top=p1.kind=="high"
        cp=float(seed.max() if direction_top else seed.min())
        ci=middle.index+1+int(np.flatnonzero(seed==cp)[0])
        d_start=middle.confirm_index
        stop_confirm=p2.confirm_index if p2 is not None else len(bars)
        leg={"case_id":leg_id,"leg_id":leg_id,"p1":asdict(p1),"middle":asdict(middle),"confirmed_end":asdict(p2) if p2 is not None else None,"type":"regular_bearish" if direction_top else "regular_bullish","versions":[],"events":[]}
        active_version=None; seen_identity=set(); vnum=0
        # The bar that confirms this candidate ends plan creation. Any prior
        # pending version remains armed through its original expiry.
        d_end=min(stop_confirm-1,len(bars)-1)
        for d in range(d_start, d_end+1):
            refreshed=False
            if d>middle.confirm_index:
                x=float(hi[d] if direction_top else lo[d])
                if (x>cp if direction_top else x<cp):
                    cp=x; ci=d; refreshed=True
            if refreshed and active_version is not None:
                leg["events"].append({"event":"CANCELLED_EXTREME_REFRESH","index":d,"version":active_version})
                active_version=None
            sep=ci-p1.index; age=d-p1.index
            if not (MIN_SEP<=sep<=MAX_SEP and 0<=age<=MAX_SEP): continue
            kind=_kind(p1,cp,float(dif[p1.index]),float(dif[ci]))
            if kind is None: continue
            identity=(kind,ci)
            if identity in seen_identity: continue
            seen_identity.add(identity); vnum+=1; raw_count[kind]+=1
            confirmed=[p for p in pivots if p.confirm_index<=d]
            rationale=""
            trend_evidence=None
            if kind.startswith("hidden"):
                highs=[p for p in confirmed if p.kind=="high" and p.index<ci]
                lows=[p for p in confirmed if p.kind=="low" and p.index<ci]
                h2=highs[-2:] if len(highs)>=2 else []; l2=lows[-2:] if len(lows)>=2 else []
                trend_evidence={"highs":[asdict(p) for p in h2],"lows":[asdict(p) for p in l2]}
                up=len(h2)==2 and len(l2)==2 and h2[1].price>h2[0].price and l2[1].price>l2[0].price
                down=len(h2)==2 and len(l2)==2 and h2[1].price<h2[0].price and l2[1].price<l2[0].price
                trend_ok=up if kind=="hidden_bullish" else down
                if not trend_ok:
                    rationale="HIDDEN_TREND_NOT_CONFIRMED"; trend_reject[kind]+=1
            else: trend_ok=True
            lv={"level_status":rationale or "NOT_COMPUTED"}
            if trend_ok:
                lv=_levels(kind,p1,middle,ci,cp,confirmed,bars,d)
                if lv["level_status"]!="READY":
                    rationale=lv["level_status"]; invalid[kind]+=1
                else:
                    qualified_count[kind]+=1
            v={"version":vnum,"type":kind,"decision_index":d,"decision_close_utc":(pd.Timestamp(bars.open_time.iloc[d])+pd.Timedelta(minutes=5)).isoformat(),
               "candidate_extreme_index":ci,"candidate_extreme_open_utc":pd.Timestamp(bars.open_time.iloc[ci]).isoformat(),"candidate_price":cp,"candidate_dif":float(dif[ci]),
               "activation_index":d+1,"activation_open_utc":pd.Timestamp(bars.open_time.iloc[d])+pd.Timedelta(minutes=5),"active_from_index":d+1,"active_through_index":d+24,
               "p1_age_bars":age,"separation_bars":sep,"trend_evidence":trend_evidence,"levels":lv,"status":"NOT_ARMED","armed":False,"rationale":rationale}
            if trend_ok and lv.get("level_status")=="READY":
                entry=float(lv["entry"]); pre_side=(close[d]<entry if kind in ("regular_bullish","hidden_bullish") else close[d]>entry)
                start=ci+1
                touched=False
                if start<=d:
                    touched=bool(np.max(hi[start:d+1])>=entry) if kind in ("regular_bullish","hidden_bullish") else bool(np.min(lo[start:d+1])<=entry)
                if not pre_side or touched:
                    v["status"]="MISSED_BEFORE_ACTIVATION"; v["rationale"]="CLOSE_BEYOND_TRIGGER" if not pre_side else "TRIGGER_TOUCHED_BEFORE_DECISION"
                elif d+1>=len(bars): v["status"]="NO_ACTIVATION_BAR"; v["rationale"]=v["status"]
                else:
                    v["status"]="PENDING"; v["armed"]=True; leg["type"]=kind; active_version=vnum
            leg["versions"].append(v)
            all_versions.append({"case_id":leg_id,**v})
        legs.append(leg)
    for leg in legs:
        for e in leg["events"]: all_events.append({"case_id":leg["case_id"],**e})
    counts={"raw_divergence_candidate_versions_by_type":raw_count,"qualified_plan_versions_by_type":qualified_count,
            "hidden_trend_rejected_by_type":trend_reject,"invalid_or_missing_target_by_type":invalid,
            "candidate_leg_count":len(legs),"candidate_version_count":len(all_versions),"armed_version_count":sum(v["armed"] for v in all_versions),
            "pivots_count":len(pivots)}
    return legs,{"versions":all_versions,"events":all_events,"counts":counts}
