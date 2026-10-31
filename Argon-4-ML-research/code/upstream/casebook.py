"""Frozen, chart-only BTC regular divergence/Fibonacci casebook.

All output is written under this file's directory. The input is a bounded,
read-only registered source plus an exact 2024-2025 local-window cross-check.
This module does not convert data for Freqtrade or calculate trading returns.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import html
import json
import math
import os
import sys
import textwrap
from dataclasses import asdict, dataclass
from datetime import timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))

from perptools.ohlcv import read_source, resolve_index, sha256_file  # noqa: E402
from perptools.registry import load_registry  # noqa: E402
from perptools.source_data import lookup, verify_selected_copy  # noqa: E402

SOURCE = Path(r"C:\Users\liuqi\crypto\data\intraday\BTCUSDT_5m_futures.parquet")
LOCAL = ROOT / "source_data/intraday/BTCUSDT_5m_futures.parquet"
SOURCE_SHA256 = "68bcae204ba5edb6785045c5104c87666958aa1caf65edcdaaadd679cfa0fd66"
LOCAL_SHA256 = "6d2dce9c0053ee67f4fcb21d4d41dd64e7b9fb402f102190feae373d12cff602"
WINDOW_START = pd.Timestamp("2024-01-01T00:00:00Z")
WINDOW_END = pd.Timestamp("2026-01-01T00:00:00Z")
EXPECTED_WINDOW_ROWS = 210_528
TICK = Decimal("0.1")
MIN_SEPARATION = 6
MAX_SEPARATION = 144
BIG_ANCHOR_LOOKBACK = 288
ORDER_EXPIRY = 24
MAX_REVEAL = 96
PROVENANCE_STATUS = (
    "REGISTERED_SOURCE_CURRENT_WINDOW_CROSSCHECKED; "
    "historical frozen-copy identity NOT_ESTABLISHED"
)


@dataclass(frozen=True)
class Pivot:
    kind: str
    index: int
    price: float
    confirm_index: int


@dataclass
class Candidate:
    index: int
    price: float


def ema(values: np.ndarray, span: int) -> np.ndarray:
    return pd.Series(values, dtype="float64").ewm(span=span, adjust=False).mean().to_numpy()


def macd(close: Iterable[float]) -> tuple[np.ndarray, np.ndarray]:
    c = np.asarray(list(close), dtype="float64")
    dif = ema(c, 12) - ema(c, 26)
    return dif, ema(dif, 9)


def independent_ema(values: Iterable[float], span: int) -> np.ndarray:
    """Simple scalar recurrence used only by the independent chart-coordinate audit."""
    x = np.asarray(list(values), dtype="float64")
    out = np.empty_like(x)
    if not len(x):
        return out
    alpha = 2.0 / (span + 1.0)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = alpha * x[i] + (1.0 - alpha) * out[i - 1]
    return out


def independent_dif(close: Iterable[float]) -> np.ndarray:
    c = np.asarray(list(close), dtype="float64")
    return independent_ema(c, 12) - independent_ema(c, 26)


def rsi14(close: Iterable[float]) -> np.ndarray:
    """Wilder RSI-14 for chart context only; not used for signal selection."""
    c = np.asarray(list(close), dtype="float64")
    out = np.full(len(c), np.nan, dtype="float64")
    if len(c) <= 14:
        return out
    change = np.diff(c)
    gain, loss = np.maximum(change, 0), np.maximum(-change, 0)
    ag, al = gain[:14].mean(), loss[:14].mean()
    out[14] = 100.0 if al == 0 and ag > 0 else 50.0 if al == 0 else 100 - 100 / (1 + ag / al)
    for i in range(15, len(c)):
        ag = (ag * 13 + gain[i - 1]) / 14
        al = (al * 13 + loss[i - 1]) / 14
        out[i] = 100.0 if al == 0 and ag > 0 else 50.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


def confirm_high(close: float, candidate_high: float) -> bool:
    return close <= candidate_high * 0.998


def confirm_low(close: float, candidate_low: float) -> bool:
    return close >= candidate_low * 1.002


def leg_pivots(bars: pd.DataFrame, start_index: int = 300) -> list[Pivot]:
    """Causal alternating-leg pivots, confirmed only on a later candle close."""
    if start_index < 0 or start_index >= len(bars):
        return []
    direction = 1  # initialized upward at the first eligible closed bar
    candidate = Candidate(start_index, float(bars.high.iloc[start_index]))
    pivots: list[Pivot] = []
    for i in range(start_index + 1, len(bars)):
        close = float(bars.close.iloc[i])
        if direction == 1:
            high = float(bars.high.iloc[i])
            if high > candidate.price:  # strict: earliest bar keeps ties
                candidate = Candidate(i, high)
            if i - candidate.index >= 3 and confirm_high(close, candidate.price):
                pivots.append(Pivot("high", candidate.index, candidate.price, i))
                segment = bars.low.iloc[candidate.index + 1 : i + 1].to_numpy(dtype="float64")
                if len(segment) == 0:
                    continue
                min_value = float(np.min(segment))
                next_index = candidate.index + 1 + int(np.flatnonzero(segment == min_value)[0])
                candidate = Candidate(next_index, min_value)
                direction = -1
        else:
            low = float(bars.low.iloc[i])
            if low < candidate.price:
                candidate = Candidate(i, low)
            if i - candidate.index >= 3 and confirm_low(close, candidate.price):
                pivots.append(Pivot("low", candidate.index, candidate.price, i))
                segment = bars.high.iloc[candidate.index + 1 : i + 1].to_numpy(dtype="float64")
                if len(segment) == 0:
                    continue
                max_value = float(np.max(segment))
                next_index = candidate.index + 1 + int(np.flatnonzero(segment == max_value)[0])
                candidate = Candidate(next_index, max_value)
                direction = 1
    if any(a.index >= b.index for a, b in zip(pivots, pivots[1:])):
        raise ValueError("pivot extreme indices must strictly increase")
    return pivots


def divergence_kind(first: Pivot, second: Pivot, dif: np.ndarray) -> str | None:
    if first.kind != second.kind:
        return None
    d1, d2 = float(dif[first.index]), float(dif[second.index])
    if first.kind == "high":
        if second.price > first.price and d2 < d1:
            return "regular_bearish"
        if second.price < first.price and d2 > d1:
            return "hidden_bearish"
    else:
        if second.price < first.price and d2 > d1:
            return "regular_bullish"
        if second.price > first.price and d2 < d1:
            return "hidden_bullish"
    return None


def paired_signals(pivots: list[Pivot], dif: np.ndarray) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for j in range(2, len(pivots)):
        p1, middle, p2 = pivots[j - 2 : j + 1]
        if p1.kind != p2.kind or middle.kind == p1.kind:
            continue
        separation = p2.index - p1.index
        if not MIN_SEPARATION <= separation <= MAX_SEPARATION:
            continue
        # A first pivot expires by its extreme age, even when the later pivot
        # was formed before the boundary but confirmed only after it.
        if p2.confirm_index - p1.index > MAX_SEPARATION:
            continue
        kind = divergence_kind(p1, p2, dif)
        if kind and kind.startswith("regular_"):
            signals.append({"kind": kind, "p1": p1, "middle": middle, "p2": p2,
                            "signal_index": p2.confirm_index, "separation_bars": separation,
                            "dif1": float(dif[p1.index]), "dif2": float(dif[p2.index])})
    return sorted(signals, key=lambda s: (s["signal_index"], s["p2"].index))


def ceil_tick(value: float | Decimal) -> Decimal:
    d = value if isinstance(value, Decimal) else Decimal(str(float(value)))
    return (d / TICK).to_integral_value(rounding=ROUND_CEILING) * TICK


def floor_tick(value: float | Decimal) -> Decimal:
    d = value if isinstance(value, Decimal) else Decimal(str(float(value)))
    return (d / TICK).to_integral_value(rounding=ROUND_FLOOR) * TICK


def small_levels(signal: dict[str, Any], bars: pd.DataFrame) -> dict[str, Any]:
    p1, p2 = signal["p1"], signal["p2"]
    if signal["kind"] == "regular_bullish":
        segment = bars.high.iloc[p1.index + 1 : p2.index]
        if segment.empty:
            raise ValueError("bullish small anchor requires an intervening candle")
        anchor_value = float(segment.max())
        anchor_index = int(segment.index[np.flatnonzero(segment.to_numpy() == anchor_value)[0]])
        fib236 = Decimal(str(p2.price)) + Decimal("0.236") * (Decimal(str(anchor_value)) - Decimal(str(p2.price)))
        entry = ceil_tick(fib236) + TICK
        stop = floor_tick(p2.price) - TICK
        return {"small_anchor_kind": "Hsmall", "small_anchor_index": anchor_index,
                "small_anchor_price": anchor_value, "small_fib": fib236, "entry": entry, "stop": stop}
    segment = bars.low.iloc[p1.index + 1 : p2.index]
    if segment.empty:
        raise ValueError("bearish small anchor requires an intervening candle")
    anchor_value = float(segment.min())
    anchor_index = int(segment.index[np.flatnonzero(segment.to_numpy() == anchor_value)[0]])
    fib236 = Decimal(str(p2.price)) - Decimal("0.236") * (Decimal(str(p2.price)) - Decimal(str(anchor_value)))
    entry = floor_tick(fib236) - TICK
    stop = ceil_tick(p2.price) + TICK
    return {"small_anchor_kind": "Lsmall", "small_anchor_index": anchor_index,
            "small_anchor_price": anchor_value, "small_fib": fib236, "entry": entry, "stop": stop}


def big_anchor(signal: dict[str, Any], pivots: list[Pivot]) -> Pivot | None:
    p1 = signal["p1"]
    required_kind = "high" if signal["kind"] == "regular_bullish" else "low"
    candidates = [p for p in pivots if p.kind == required_kind and p.index < p1.index
                  and p1.index - p.index <= BIG_ANCHOR_LOOKBACK
                  and p.confirm_index <= signal["signal_index"]]
    if not candidates:
        return None
    extreme = max(p.price for p in candidates) if required_kind == "high" else min(p.price for p in candidates)
    return min((p for p in candidates if p.price == extreme), key=lambda p: p.index)


def fib_levels(signal: dict[str, Any], pivots: list[Pivot], bars: pd.DataFrame) -> dict[str, Any]:
    levels = small_levels(signal, bars)
    anchor = big_anchor(signal, pivots)
    levels["big_anchor_kind"] = "bigH" if signal["kind"] == "regular_bullish" else "bigL"
    levels["big_anchor_index"] = anchor.index if anchor else None
    levels["big_anchor_price"] = anchor.price if anchor else None
    levels["big_anchor_confirm_index"] = anchor.confirm_index if anchor else None
    if anchor is None:
        levels.update(target=None, level_status="MISSING_BIG_ANCHOR")
        return levels
    p2 = signal["p2"]
    if signal["kind"] == "regular_bullish":
        fib382 = Decimal(str(p2.price)) + Decimal("0.382") * (Decimal(str(anchor.price)) - Decimal(str(p2.price)))
        target = floor_tick(fib382) - TICK
        valid = target > levels["entry"]
    else:
        fib382 = Decimal(str(p2.price)) - Decimal("0.382") * (Decimal(str(p2.price)) - Decimal(str(anchor.price)))
        target = ceil_tick(fib382) + TICK
        valid = target < levels["entry"]
    levels["target"] = target
    levels["big_fib"] = fib382
    levels["level_status"] = "READY" if valid else "INVALID_TARGET"
    return levels


def pre_signal_touch(signal: dict[str, Any], bars: pd.DataFrame, levels: dict[str, Any]) -> bool:
    start = signal["p2"].index + 1
    stop = signal["signal_index"]
    if stop < start:
        return False
    after = bars.iloc[start : stop + 1]
    entry = float(levels["entry"])
    if signal["kind"] == "regular_bullish":
        return bool((after.high >= entry).any() or float(bars.close.iloc[stop]) >= entry)
    return bool((after.low <= entry).any() or float(bars.close.iloc[stop]) <= entry)


def trace_order(signal: dict[str, Any], bars: pd.DataFrame, levels: dict[str, Any]) -> dict[str, Any]:
    bull = signal["kind"] == "regular_bullish"
    entry, stop, target = float(levels["entry"]), float(levels["stop"]), levels["target"]
    trace: list[dict[str, Any]] = []
    if pre_signal_touch(signal, bars, levels):
        return {"event_status": "SKIPPED_TRIGGER_ALREADY_TOUCHED", "trace": [
            {"event": "signal_close_check", "index": signal["signal_index"], "result": "trigger_touched_before_or_at_signal"}]}
    if levels["level_status"] != "READY":
        return {"event_status": levels["level_status"], "trace": []}
    signal_ix = int(signal["signal_index"])
    fill_ix: int | None = None
    last_order_ix = min(signal_ix + ORDER_EXPIRY, len(bars) - 1)
    for i in range(signal_ix + 1, last_order_ix + 1):
        b = bars.iloc[i]
        ent = float(b.high) >= entry if bull else float(b.low) <= entry
        stp = float(b.low) <= stop if bull else float(b.high) >= stop
        refresh = float(b.low) < signal["p2"].price if bull else float(b.high) > signal["p2"].price
        trace.append({"index": i, "event": "waiting_order_bar", "entry_touched": bool(ent),
                      "stop_touched": bool(stp), "adverse_extreme_refresh": bool(refresh)})
        if ent and (stp or refresh):
            return {"event_status": "INTRABAR_ORDER_UNCERTAIN", "trace": trace}
        if stp:
            trace[-1]["event"] = "STOP_BEFORE_ENTRY_INVALIDATION"
            return {"event_status": "INVALIDATED_STOP_BEFORE_ENTRY", "trace": trace}
        if refresh:
            trace[-1]["event"] = "CANCELLED_EXTREME_REFRESH"
            return {"event_status": "CANCELLED_EXTREME_REFRESH", "trace": trace}
        if ent:
            fill_ix = i
            gap = (float(b.open) > entry) if bull else (float(b.open) < entry)
            trace[-1]["event"] = "ENTRY_GAP_PRICE_UNCERTAIN" if gap else "ENTRY_TOUCHED"
            break
    if fill_ix is None:
        status = "EXPIRED_24_BARS" if last_order_ix == signal_ix + ORDER_EXPIRY else "DATA_ENDED_UNFILLED"
        return {"event_status": status, "trace": trace}
    fillbar = bars.iloc[fill_ix]
    fill_stop = float(fillbar.low) <= stop if bull else float(fillbar.high) >= stop
    fill_target = float(fillbar.high) >= float(target) if bull else float(fillbar.low) <= float(target)
    if fill_stop and fill_target:
        trace.append({"index": fill_ix, "event": "ENTRY_BAR_BOTH_EXITS_UNCERTAIN"})
        return {"event_status": "INTRABAR_ORDER_UNCERTAIN", "trace": trace}
    if fill_stop:
        trace.append({"index": fill_ix, "event": "ENTRY_BAR_STOP_UNCERTAIN"})
        return {"event_status": "INTRABAR_ORDER_UNCERTAIN", "trace": trace}
    if fill_target:
        trace.append({"index": fill_ix, "event": "ENTRY_BAR_TARGET_UNCERTAIN"})
        return {"event_status": "INTRABAR_ORDER_UNCERTAIN", "trace": trace}
    end = min(signal_ix + MAX_REVEAL, len(bars) - 1)
    for i in range(fill_ix + 1, end + 1):
        b = bars.iloc[i]
        stp = float(b.low) <= stop if bull else float(b.high) >= stop
        tgt = float(b.high) >= float(target) if bull else float(b.low) <= float(target)
        if stp and tgt:
            trace.append({"index": i, "event": "EXIT_ORDER_UNCERTAIN", "stop_touched": True, "target_touched": True})
            return {"event_status": "EXIT_ORDER_UNCERTAIN", "trace": trace}
        if stp or tgt:
            trace.append({"index": i, "event": "STOP_EXIT" if stp else "TARGET_EXIT"})
            return {"event_status": "STOP_EXIT" if stp else "TARGET_EXIT", "trace": trace}
    status = "UNRESOLVED_96_BARS" if end == signal_ix + MAX_REVEAL else "DATA_ENDED_UNRESOLVED"
    trace.append({"index": end, "event": status})
    return {"event_status": status, "trace": trace}


def load_verified_window() -> tuple[pd.DataFrame, dict[str, Any]]:
    """Fail-closed current-source and exact local-window guard; no source writes."""
    registry = load_registry()
    ds = next((d for d in registry.datasets if d.id == "binance_futures_5m_intraday"), None)
    if not ds or ds.verification_status != "VERIFIED_PERPETUAL_LABEL" or ds.exchange != "binance" or ds.timeframe != "5m":
        raise RuntimeError("registered Binance BTC 5m perpetual label missing or inconsistent")
    if "intraday/{SYMBOL}_5m_futures.parquet" not in ds.source_path.replace("\\", "/"):
        raise RuntimeError("registered source path changed; refusing input")
    registered_source = Path(ds.source_path.replace("{SYMBOL}", "BTCUSDT"))
    if registered_source.resolve() != SOURCE.resolve():
        raise RuntimeError("registered source path does not match the frozen primary path")
    source_hash, local_hash = sha256_file(SOURCE), sha256_file(LOCAL)
    if source_hash != SOURCE_SHA256 or local_hash != LOCAL_SHA256:
        raise RuntimeError("one or both frozen current input hashes drifted")
    src_raw, loc_raw = read_source(SOURCE), read_source(LOCAL)
    src_ts, _, src_tz = resolve_index(src_raw)
    loc_ts, _, loc_tz = resolve_index(loc_raw)
    fields = ["open", "high", "low", "close", "volume"]
    if any(x not in src_raw.columns or x not in loc_raw.columns for x in fields):
        raise RuntimeError("OHLCV columns changed")
    sm = (src_ts >= WINDOW_START) & (src_ts < WINDOW_END)
    lm = (loc_ts >= WINDOW_START) & (loc_ts < WINDOW_END)
    st = pd.DatetimeIndex(src_ts.loc[sm].to_numpy())
    lt = pd.DatetimeIndex(loc_ts.loc[lm].to_numpy())
    sv = src_raw.loc[sm, fields].to_numpy(dtype="float64")
    lv = loc_raw.loc[lm, fields].to_numpy(dtype="float64")
    if len(st) != EXPECTED_WINDOW_ROWS or len(lt) != EXPECTED_WINDOW_ROWS:
        raise RuntimeError("bounded window row count drifted")
    if not np.array_equal(st.asi8, lt.asi8) or not np.array_equal(sv, lv, equal_nan=True):
        raise RuntimeError("source and local bounded timestamps/OHLCV no longer match exactly")
    if pd.Index(st).has_duplicates or pd.Index(lt).has_duplicates:
        raise RuntimeError("duplicate timestamps in bounded window")
    delta = np.diff(st.asi8)
    if len(delta) and not np.all(delta == 300_000_000_000):
        raise RuntimeError("gap or non-5m spacing in bounded window")
    if not np.isfinite(sv).all():
        raise RuntimeError("non-finite OHLCV in bounded window")
    for values in (sv, lv):
        o, h, l, c, v = values.T
        if np.any(h < np.maximum.reduce([o, c, l])) or np.any(l > np.minimum.reduce([o, c, h])) or np.any(v < 0):
            raise RuntimeError("invalid OHLCV value in bounded window")
    frame = pd.DataFrame(sv, columns=fields, index=st)
    frame.index.name = "open_time"
    frame = frame.reset_index()
    import pyarrow.parquet as pq
    meta = {
        "registry_dataset_id": ds.id, "registry_verification_status": ds.verification_status,
        "registry_market_type": ds.market_type, "registry_exchange": ds.exchange,
        "timeframe": ds.timeframe, "primary_path": str(SOURCE), "primary_sha256": source_hash,
        "primary_bytes": SOURCE.stat().st_size, "primary_total_rows": len(src_raw),
        "primary_schema": [{"name": f.name, "type": str(f.type)} for f in pq.ParquetFile(SOURCE).schema_arrow],
        "local_crosscheck_path": "source_data/intraday/BTCUSDT_5m_futures.parquet",
        "local_crosscheck_sha256": local_hash, "local_copy_status": getattr(lookup(LOCAL), "copy_status", "UNKNOWN"),
        "local_crosscheck_bytes": LOCAL.stat().st_size, "local_crosscheck_total_rows": len(loc_raw),
        "local_crosscheck_schema": [{"name": f.name, "type": str(f.type)} for f in pq.ParquetFile(LOCAL).schema_arrow],
        "local_verifier_refusal": None, "source_timestamp_semantics": src_tz, "local_timestamp_semantics": loc_tz,
        "window_start_utc": str(WINDOW_START), "window_end_exclusive_utc": str(WINDOW_END),
        "window_rows_each": EXPECTED_WINDOW_ROWS, "window_exact_timestamp_ohlcv_match": True,
        "duplicates_each": 0, "missing_5m_slots_each": 0,
        "provenance_status": PROVENANCE_STATUS,
        "limitations": ["Current-window source/local agreement does not establish historical frozen-copy identity.",
                        "Chart-only source normalization; no Freqtrade import or strategy validation."]
    }
    copy = lookup(LOCAL)
    if copy:
        try:
            meta["local_verification_result"] = verify_selected_copy(copy, purpose="divergence/Fibonacci chart casebook")
        except Exception as exc:
            meta["local_verifier_refusal"] = str(exc)
            meta["local_verification_result"] = "REFUSED; recorded for transparency"
    return frame, meta


def timestamp(index: int, bars: pd.DataFrame, close: bool = False) -> str:
    ts = pd.Timestamp(bars.open_time.iloc[index]) + (pd.Timedelta(minutes=5) if close else pd.Timedelta(0))
    return ts.tz_convert("UTC").isoformat()


def prepare_cases(bars: pd.DataFrame) -> tuple[list[dict[str, Any]], list[Pivot], np.ndarray, np.ndarray]:
    close = bars.close.to_numpy(dtype="float64")
    dif, sig = macd(close)
    pivots = leg_pivots(bars, 300)
    all_signals = paired_signals(pivots, dif)
    selected = [s for s in all_signals if s["kind"] == "regular_bullish"][:5]
    selected += [s for s in all_signals if s["kind"] == "regular_bearish"][:5]
    selected.sort(key=lambda s: (s["signal_index"], s["kind"]))
    cases = []
    for ordinal, signal in enumerate(selected, 1):
        levels = fib_levels(signal, pivots, bars)
        events = trace_order(signal, bars, levels)
        event_status = events["event_status"]
        if event_status in {"READY", "MISSING_BIG_ANCHOR", "INVALID_TARGET"}:
            pass
        case = {"case_id": f"CASE_{ordinal:02d}", "kind": signal["kind"], "signal": signal,
                "levels": levels, "events": events, "event_status": event_status,
                "dif": dif, "macd_signal": sig, "rsi14": rsi14(close)}
        cases.append(case)
    return cases, pivots, dif, sig


def iso_at(bars: pd.DataFrame, ix: int, close: bool = False) -> str:
    return timestamp(ix, bars, close=close)


def case_record(case: dict[str, Any], bars: pd.DataFrame) -> dict[str, Any]:
    s, lev = case["signal"], case["levels"]
    p1, p2, mid = s["p1"], s["p2"], s["middle"]
    def pivot_dict(p: Pivot) -> dict[str, Any]:
        return {"kind": p.kind, "index": p.index, "price": p.price,
                "extreme_open_time_utc": iso_at(bars, p.index), "confirm_index": p.confirm_index,
                "confirmation_close_time_utc": iso_at(bars, p.confirm_index, True)}
    return {"case_id": case["case_id"], "type": case["kind"], "event_status": case["event_status"],
            "p1": pivot_dict(p1), "intervening_pivot": pivot_dict(mid), "p2": pivot_dict(p2),
            "signal_confirmation_close_time_utc": iso_at(bars, s["signal_index"], True),
            "bars_between_extremes": s["separation_bars"], "dif_at_p1": s["dif1"], "dif_at_p2": s["dif2"],
            "small_anchor": {"kind": lev["small_anchor_kind"], "index": lev["small_anchor_index"],
                             "price": lev["small_anchor_price"], "open_time_utc": iso_at(bars, lev["small_anchor_index"])},
            "big_anchor": {"kind": lev["big_anchor_kind"], "index": lev["big_anchor_index"],
                           "price": lev["big_anchor_price"],
                           "open_time_utc": iso_at(bars, lev["big_anchor_index"]) if lev["big_anchor_index"] is not None else None,
                           "confirm_index": lev.get("big_anchor_confirm_index"),
                           "confirmation_close_time_utc": iso_at(bars, lev["big_anchor_confirm_index"], True) if lev.get("big_anchor_confirm_index") is not None else None},
            "small_fib_0236_usdt": float(lev["small_fib"]),
            "big_fib_0382_usdt": float(lev["big_fib"]) if lev.get("big_fib") is not None else None,
            "entry_reference_usdt": float(lev["entry"]), "stop_reference_usdt": float(lev["stop"]),
            "target_reference_usdt": float(lev["target"]) if lev["target"] is not None else None,
            "fib_status": lev["level_status"], "tick_usdt": float(TICK),
            "tick_status": "HISTORICAL TICK UNVERIFIED; 0.1 USDT ILLUSTRATION ASSUMPTION",
            "event_trace": case["events"]["trace"]}


def cases_from_manifest(records: list[dict[str, Any]], bars: pd.DataFrame) -> list[dict[str, Any]]:
    """Rebuild chart objects from the frozen selected manifest; never reselect signals."""
    close = bars.close.to_numpy(dtype="float64")
    dif, sig = macd(close)
    rsi = rsi14(close)
    out = []
    for rec in records:
        def read_pivot(key):
            item = rec[key]
            return Pivot(item["kind"], int(item["index"]), float(item["price"]), int(item["confirm_index"]))
        p1, middle, p2 = read_pivot("p1"), read_pivot("intervening_pivot"), read_pivot("p2")
        small, big = rec["small_anchor"], rec["big_anchor"]
        signal = {"kind":rec["type"],"p1":p1,"middle":middle,"p2":p2,
                  "signal_index":p2.confirm_index,"separation_bars":int(rec["bars_between_extremes"]),
                  "dif1":float(rec["dif_at_p1"]),"dif2":float(rec["dif_at_p2"])}
        levels = {"small_anchor_kind":small["kind"],"small_anchor_index":int(small["index"]),
                  "small_anchor_price":float(small["price"]),"small_fib":Decimal(str(rec["small_fib_0236_usdt"])),
                  "big_anchor_kind":big["kind"],"big_anchor_index":int(big["index"]) if big["index"] is not None else None,
                  "big_anchor_price":float(big["price"]) if big["price"] is not None else None,
                  "big_anchor_confirm_index":big.get("confirm_index"),
                  "big_fib":Decimal(str(rec["big_fib_0382_usdt"])) if rec["big_fib_0382_usdt"] is not None else None,
                  "entry":Decimal(str(rec["entry_reference_usdt"])),"stop":Decimal(str(rec["stop_reference_usdt"])),
                  "target":Decimal(str(rec["target_reference_usdt"])) if rec["target_reference_usdt"] is not None else None,
                  "level_status":rec["fib_status"]}
        events = {"event_status":rec["event_status"],"trace":rec["event_trace"]}
        out.append({"case_id":rec["case_id"],"kind":rec["type"],"signal":signal,"levels":levels,
                    "events":events,"event_status":rec["event_status"],"entry_compatibility":rec.get("entry_compatibility"),
                    "dif":dif,"macd_signal":sig,"rsi14":rsi})
    return out


def _font_setup() -> tuple[str, bool]:
    import matplotlib
    from matplotlib import font_manager
    candidates = ["Microsoft YaHei", "Microsoft YaHei UI", "SimHei", "Noto Sans CJK SC"]
    for name in candidates:
        try:
            font_manager.findfont(name, fallback_to_default=False)
            matplotlib.rcParams["font.sans-serif"] = [name, "DejaVu Sans"]
            matplotlib.rcParams["axes.unicode_minus"] = False
            return name, True
        except ValueError:
            continue
    matplotlib.rcParams["font.sans-serif"] = ["DejaVu Sans"]
    return "DejaVu Sans", False


def _level_label(key: str, value: Any) -> str:
    return "unavailable" if value is None else f"{float(value):,.1f} USDT"


def draw_case(case: dict[str, Any], bars: pd.DataFrame, out_path: Path, font_ok: bool) -> dict[str, Any]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    s, lev = case["signal"], case["levels"]
    p1, p2 = s["p1"], s["p2"]
    anchor_ix = lev["big_anchor_index"]
    left = max(0, min(p1.index, anchor_ix if anchor_ix is not None else p1.index) - 72)
    right = min(len(bars) - 1, s["signal_index"] + MAX_REVEAL)
    # Keep chart focus on the comparison and nearby structure; complete levels remain numeric in the side panel.
    x_lo, x_hi = left, right
    pad = max(8, int((x_hi - x_lo) * 0.06))
    xs = np.arange(x_lo, x_hi + 1)
    fig = plt.figure(figsize=(22, 14), dpi=100, facecolor="#f8fafc")
    grid = fig.add_gridspec(2, 2, width_ratios=[4.3, 1.5], height_ratios=[3.3, 1.0], hspace=0.055, wspace=0.15)
    ax = fig.add_subplot(grid[0, 0]); ad = fig.add_subplot(grid[1, 0], sharex=ax); note = fig.add_subplot(grid[:, 1]); note.axis("off")
    ax.set_facecolor("#ffffff"); ad.set_facecolor("#ffffff")
    candle_artists = []
    for i in xs:
        o, h, l, c = (float(bars[k].iloc[i]) for k in ("open", "high", "low", "close"))
        color = "#16a085" if c >= o else "#d35454"
        wick = ax.vlines(i, l, h, color=color, linewidth=0.75, zorder=2)
        body = abs(c - o)
        if body == 0:
            body_artist = ax.hlines(o, i - 0.32, i + 0.32, color=color, linewidth=1.1, zorder=3)
        else:
            body_artist = ax.vlines(i, min(o, c), max(o, c), color=color, linewidth=3.4, zorder=3)
        candle_artists.append({"index": int(i), "wick_segments": wick.get_segments(),
                               "body_segments": body_artist.get_segments()})
    future_start = s["signal_index"] + 1.0
    ax.axvspan(future_start, right + 0.5, color="#f3c969", alpha=0.17, zorder=0)
    ad.axvspan(future_start, right + 0.5, color="#f3c969", alpha=0.17, zorder=0)
    ax.axvline(future_start, color="#5144a5", linewidth=1.2, linestyle="--")
    annotation_artists = []
    confirmation_artists = []
    for pivot, tag, color in ((p1, "P1 / H1" if p1.kind == "high" else "P1 / L1", "#1769aa"),
                              (p2, "P2 / H2" if p2.kind == "high" else "P2 / L2", "#8e44ad")):
        marker = "v" if pivot.kind == "high" else "^"
        scatter = ax.scatter([pivot.index], [pivot.price], marker=marker, s=85, c=color, edgecolors="white", linewidths=0.8, zorder=6)
        annotation_artists.append({"label":tag.replace(" / ","_"),"field":"high" if pivot.kind=="high" else "low","artist":scatter,"index":pivot.index})
        xoff = -36 if tag.startswith("P1") else 38
        yoff = 28 if pivot.kind == "low" else -30
        ax.annotate(f"{tag}\n{pivot.price:,.1f}\n{iso_at(bars,pivot.index)[5:16]} open",
                    xy=(pivot.index, pivot.price), xytext=(xoff, yoff), textcoords="offset points",
                    xycoords="data", fontsize=8.3, color=color, ha="right" if xoff < 0 else "left", va="bottom" if pivot.kind == "low" else "top",
                    bbox={"boxstyle":"round,pad=.25","fc":"white","ec":color,"alpha":0.92}, zorder=8)
        confirm = ax.scatter([pivot.confirm_index + 1], [float(bars.close.iloc[pivot.confirm_index])], marker="x", s=50, c="#292929", zorder=7)
        confirmation_artists.append({"index":pivot.confirm_index,"artist":confirm})
    price_connector, = ax.plot([p1.index, p2.index], [p1.price, p2.price], color="#5144a5", linewidth=1.5, linestyle="-.", zorder=5)
    dif_connector, = ad.plot([p1.index, p2.index], [case["dif"][p1.index], case["dif"][p2.index]], color="#5144a5", linewidth=1.15, linestyle="-.", zorder=4)
    fib_connector_artists = []
    for name, ix, price, color in ((lev["small_anchor_kind"], lev["small_anchor_index"], lev["small_anchor_price"], "#d28e00"),
                                  (lev["big_anchor_kind"], lev["big_anchor_index"], lev["big_anchor_price"], "#007f86")):
        if ix is not None:
            anchor_artist = ax.scatter([ix], [price], marker="D", s=62, c=color, edgecolors="white", linewidths=0.7, zorder=7)
            annotation_artists.append({"label":name,"field":"high" if name in {"Hsmall","bigH"} else "low","artist":anchor_artist,"index":ix})
            offset_y = -16 if name in {"Lsmall", "bigH"} else 10
            ax.annotate(f"{name} {price:,.1f}", (ix, price), xytext=(5, offset_y), textcoords="offset points", fontsize=8.5,
                        va="top" if offset_y < 0 else "bottom", color=color,
                        bbox={"boxstyle":"round,pad=.2","fc":"white","ec":color,"alpha":0.9}, zorder=9)
            connector, = ax.plot([ix,p2.index],[price,p2.price],color=color,linewidth=1.0,linestyle=":",alpha=0.8,zorder=4)
            fib_connector_artists.append({"name":name,"artist":connector,"anchor_index":ix,"anchor_field":"high" if name in {"Hsmall","bigH"} else "low"})
    line_style = {"entry": ("#2468b4", "--"), "stop": ("#cf3f4b", "-"), "target": ("#18865d", "-")}
    fib_line_artists = {}
    for key, label in (("small_fib", "Small 0.236 retrace"), ("big_fib", "Big 0.382 target"),
                       ("entry", "Entry"), ("stop", "Stop"), ("target", "Target")):
        val = lev.get(key)
        if val is not None:
            color, ls = line_style[key] if key in line_style else (("#d28e00", "--") if key == "small_fib" else ("#007f86", ":"))
            fib_line_artists[key] = ax.axhline(float(val), color=color, linestyle=ls, linewidth=1.0, alpha=0.88, zorder=1)
    ax.set_xlim(x_lo - 1, x_hi + pad); ax.grid(True, color="#dce3eb", linewidth=0.5)
    ax.set_ylabel("Price (USDT)")
    typ = "Regular bullish divergence" if case["kind"] == "regular_bullish" else "Regular bearish divergence"
    ax.set_title(f"BTCUSDT perpetual • 5m • UTC • {typ} • {case['case_id']}", fontsize=15, loc="left", pad=12, weight="bold")
    ax.text(0.01, 0.985, "Known at signal close" + (" / 信号确认时已知" if font_ok else "") , transform=ax.transAxes,
            va="top", fontsize=9, color="#334155", bbox={"fc":"white","ec":"#64748b","alpha":0.9,"boxstyle":"round,pad=.3"})
    ax.text(0.99, 0.985, "Future reveal / 信号后 96 bars" if font_ok else "Future reveal: up to 96 bars (8h)", transform=ax.transAxes,
            va="top", ha="right", fontsize=9, color="#8a5b00", bbox={"fc":"#fff8e5","ec":"#d4a63d","alpha":0.95,"boxstyle":"round,pad=.3"})
    dif, sigline = case["dif"], case["macd_signal"]
    dif_artist, = ad.plot(xs, dif[xs], color="#2764ad", linewidth=1.15, label="DIF (EMA12 - EMA26)")
    signal_artist, = ad.plot(xs, sigline[xs], color="#df8a35", linewidth=0.95, label="Signal EMA9")
    ad.axhline(0, color="#555", linewidth=0.55); ad.axvline(future_start, color="#5144a5", linewidth=1.0, linestyle="--")
    for pivot, color in ((p1, "#1769aa"), (p2, "#8e44ad")):
        dif_point = ad.scatter([pivot.index], [dif[pivot.index]], c=color, s=54, edgecolors="white", zorder=5)
        annotation_artists.append({"label":f"{pivot.kind.upper()}_DIF_{pivot.index}","field":"dif","artist":dif_point,"index":pivot.index})
        xoff, yoff = (-18, 11) if pivot == p1 else (18, -11)
        ad.annotate(f"{dif[pivot.index]:.2f}", (pivot.index, dif[pivot.index]), xytext=(xoff, yoff), textcoords="offset points",
                    ha="right" if xoff < 0 else "left", fontsize=8, color=color,
                    arrowprops={"arrowstyle":"-","color":color,"lw":0.65})
    ad.set_ylabel("DIF"); ad.grid(True, color="#dce3eb", linewidth=0.5); ad.legend(loc="upper left", ncol=2, fontsize=8)
    ticks = np.linspace(x_lo, x_hi, min(9, max(3, int((x_hi-x_lo)/12)))).astype(int)
    ad.set_xticks(ticks); ad.set_xticklabels([pd.Timestamp(bars.open_time.iloc[i]).strftime("%m-%d %H:%M") for i in ticks], rotation=20, ha="right", fontsize=8)
    ad.set_xlabel("Candle open time (UTC), 5-minute spacing")
    def show_time(ix: int | None, close: bool = False) -> str:
        return "Unavailable" if ix is None else iso_at(bars, ix, close)
    note_lines = [f"CASE: {case['case_id']}", typ, "", f"Signal close (UTC):\n{show_time(s['signal_index'], True)}", "",
                  f"P1 extreme: {show_time(p1.index)}\nconfirmed: {show_time(p1.confirm_index, True)}",
                  f"P2 extreme: {show_time(p2.index)}\nconfirmed: {show_time(p2.confirm_index, True)}", "",
                  f"DIF P1 → P2: {s['dif1']:.3f} → {s['dif2']:.3f}",
                  f"Small anchor {lev['small_anchor_kind']}:\n{lev['small_anchor_price']:,.1f} USDT",
                  f"Big anchor {lev['big_anchor_kind']}:\n{_level_label('big_anchor_price',lev['big_anchor_price'])}",
                  f"Big anchor confirmed: {show_time(lev.get('big_anchor_confirm_index'), True)}", "",
                  f"Small Fib 0.236: {_level_label('small_fib',lev['small_fib'])}",
                  f"Big Fib 0.382: {_level_label('big_fib',lev.get('big_fib'))}",
                  f"Level status: {lev['level_status']}",
                  f"Event trace: {case['event_status']}", "", "Tick: 0.1 USDT illustration assumption; historical tick unverified.",
                  "No PnL, win-rate, or effectiveness claim."]
    compat=case.get("entry_compatibility")
    if compat:
        note_lines.insert(note_lines.index(f"Event trace: {case['event_status']}"),
                          f"First trigger touch: {compat['first_touch_open_utc']}\n({compat['bars_after_extreme_to_first_touch']} bar after P2)")
    note_text = "\n".join("\n".join(textwrap.wrap(line, width=31, break_long_words=False, break_on_hyphens=False)) if line else "" for line in note_lines)
    note.text(0.02, 0.98, note_text, transform=note.transAxes, va="top", fontsize=9.1, linespacing=1.2,
              color="#17212b", zorder=20, clip_on=False,
              bbox={"boxstyle":"round,pad=.55","fc":"white","ec":"#bcc8d6","lw":0.9})
    note.add_patch(Rectangle((0.025, 0.02), 0.95, 0.18, transform=note.transAxes,
                             facecolor="white", edgecolor="#bcc8d6", linewidth=0.9, zorder=0))
    for y, key, label, color, style in ((0.155,"entry","ENTRY / 入场","#2468b4","--"),
                                        (0.095,"stop","STOP / 止损","#cf3f4b","-"),
                                        (0.035,"target","TARGET / 目标","#18865d","-")):
        val=lev.get(key); value_text="unavailable" if val is None else f"{float(val):,.1f} USDT"
        note.plot([0.05,0.18],[y,y],transform=note.transAxes,color=color,linestyle=style,linewidth=2.0,clip_on=False)
        note.text(0.22,y,f"{label}: {value_text}",transform=note.transAxes,va="center",fontsize=8.8,color=color)
    fig.subplots_adjust(left=0.07, right=0.98, top=0.94, bottom=0.09)
    fig.savefig(out_path, dpi=100, facecolor=fig.get_facecolor())
    plt.close(fig)
    # Read artist coordinates back from Matplotlib; the audit below does not reuse
    # the desired points used to construct the chart.
    def line_xy(line):
        x, y = line.get_data()
        return {"x": np.asarray(x, dtype="float64").tolist(), "y": np.asarray(y, dtype="float64").tolist()}
    points = []
    for item in annotation_artists:
        xy = np.asarray(item["artist"].get_offsets(), dtype="float64")[0]
        ix = int(item["index"])
        points.append({"label":item["label"],"index":ix,"timestamp":iso_at(bars,ix),"field":item["field"],"x":float(xy[0]),"y":float(xy[1])})
    confirmations=[]
    for item in confirmation_artists:
        xy=np.asarray(item["artist"].get_offsets(),dtype="float64")[0]; ix=int(item["index"])
        confirmations.append({"index":ix,"timestamp":iso_at(bars,ix,close=True),"x":float(xy[0]),"y":float(xy[1])})
    candles=[]
    for item in candle_artists:
        candles.append({"index":item["index"],"wick":np.asarray(item["wick_segments"][0],dtype="float64").tolist(),
                        "body":np.asarray(item["body_segments"][0],dtype="float64").tolist()})
    lines={"price_p1_p2":line_xy(price_connector),"dif_p1_p2":line_xy(dif_connector),
           "dif_series":line_xy(dif_artist),"signal_series":line_xy(signal_artist),
           "fib_connectors":[{"name":item["name"],"xy":line_xy(item["artist"]),"anchor_index":item["anchor_index"],"anchor_field":item["anchor_field"]} for item in fib_connector_artists],
           "fib_levels":{key:float(np.asarray(line.get_ydata(),dtype="float64")[0]) for key,line in fib_line_artists.items()}}
    return {"case_id":case["case_id"],"png":out_path.name,"kind":case["kind"],
            "p1":{"index":p1.index,"kind":p1.kind},"p2":{"index":p2.index,"kind":p2.kind},
            "small_anchor":{"index":lev["small_anchor_index"],"kind":lev["small_anchor_kind"]},
            "big_anchor":{"index":lev["big_anchor_index"],"kind":lev["big_anchor_kind"]},
            "points":points,"confirmations":confirmations,"candles":candles,"lines":lines}


def coordinate_audit(rendered: list[dict[str, Any]], raw_bars: pd.DataFrame) -> dict[str, Any]:
    """Compare actual Matplotlib artist arrays with an independently read raw source frame."""
    raw_dif=independent_dif(raw_bars.close.to_numpy(dtype="float64"))
    raw_signal=independent_ema(raw_dif,9)
    checks=[]
    def add(case_id,label,actual,expected):
        a=np.asarray(actual,dtype="float64"); e=np.asarray(expected,dtype="float64")
        ok=a.shape==e.shape and np.array_equal(a,e)
        checks.append({"case_id":case_id,"item":label,"pass":bool(ok),"actual":a.tolist(),"expected_from_raw":e.tolist()})
    for case in rendered:
        cid=case["case_id"]
        for point in case["points"]:
            ix=int(point["index"]); field=point["field"]
            val=float(raw_dif[ix]) if field=="dif" else float(raw_bars[field].iloc[ix])
            add(cid,point["label"],[[point["x"],point["y"]]],[[ix,val]])
            if point["timestamp"]!=pd.Timestamp(raw_bars.open_time.iloc[ix]).isoformat():
                add(cid,point["label"]+"_timestamp",[[0.0]],[[1.0]])
        for point in case["confirmations"]:
            ix=int(point["index"]); add(cid,"confirmation_close",[[point["x"],point["y"]]],[[ix+1,float(raw_bars.close.iloc[ix])]])
            if point["timestamp"]!=(pd.Timestamp(raw_bars.open_time.iloc[ix])+pd.Timedelta(minutes=5)).isoformat(): add(cid,"confirmation_timestamp",[[0]],[[1]])
        for candle in case["candles"]:
            ix=int(candle["index"])
            add(cid,f"candle_{ix}_wick",candle["wick"],[[ix,float(raw_bars.low.iloc[ix])],[ix,float(raw_bars.high.iloc[ix])]])
            o,c=float(raw_bars.open.iloc[ix]),float(raw_bars.close.iloc[ix])
            if o==c: expected_body=[[ix-0.32,o],[ix+0.32,c]]
            else: expected_body=[[ix,min(o,c)],[ix,max(o,c)]]
            add(cid,f"candle_{ix}_body",candle["body"],expected_body)
        for name in ("price_p1_p2","dif_p1_p2"):
            coords=case["lines"][name]
            field="high" if case["p1"]["kind"]=="high" else "low"
            if name=="price_p1_p2":
                ys=[float(raw_bars[field].iloc[case[k]["index"]]) for k in ("p1","p2")]
            else: ys=[float(raw_dif[case[k]["index"]]) for k in ("p1","p2")]
            add(cid,name,list(zip(coords["x"],coords["y"])),[[case["p1"]["index"],ys[0]],[case["p2"]["index"],ys[1]]])
        for name in ("dif_series","signal_series"):
            coords=case["lines"][name]; x=np.asarray(coords["x"],dtype="int64")
            exp=raw_dif[x] if name=="dif_series" else raw_signal[x]
            add(cid,name,coords["y"],exp)
        # Recompute the Fibonacci levels from raw OHLC at the selected anchors.
        kind=case["kind"]; p2_ix=case["p2"]["index"]; p2_kind=case["p2"]["kind"]
        p2_price=float(raw_bars.high.iloc[p2_ix] if p2_kind=="high" else raw_bars.low.iloc[p2_ix])
        small=case["small_anchor"]; si=int(small["index"]); small_price=float(raw_bars.high.iloc[si] if small["kind"]=="Hsmall" else raw_bars.low.iloc[si])
        if kind=="regular_bullish":
            fib236=Decimal(str(p2_price))+Decimal("0.236")*(Decimal(str(small_price))-Decimal(str(p2_price)))
            entry=ceil_tick(fib236)+TICK; stop=floor_tick(p2_price)-TICK
        else:
            fib236=Decimal(str(p2_price))-Decimal("0.236")*(Decimal(str(p2_price))-Decimal(str(small_price)))
            entry=floor_tick(fib236)-TICK; stop=ceil_tick(p2_price)+TICK
        expected_levels={"small_fib":float(fib236),"entry":float(entry),"stop":float(stop)}
        big=case["big_anchor"]
        if big["index"] is not None:
            bi=int(big["index"]); big_price=float(raw_bars.high.iloc[bi] if big["kind"]=="bigH" else raw_bars.low.iloc[bi])
            if kind=="regular_bullish":
                fib382=Decimal(str(p2_price))+Decimal("0.382")*(Decimal(str(big_price))-Decimal(str(p2_price)))
                target=floor_tick(fib382)-TICK
            else:
                fib382=Decimal(str(p2_price))-Decimal("0.382")*(Decimal(str(p2_price))-Decimal(str(big_price)))
                target=ceil_tick(fib382)+TICK
            expected_levels.update({"big_fib":float(fib382),"target":float(target)})
        for key,expected in expected_levels.items():
            if key in case["lines"]["fib_levels"]:
                add(cid,f"fib_{key}",[case["lines"]["fib_levels"][key]],[expected])
        for connector in case["lines"]["fib_connectors"]:
            ix=int(connector["anchor_index"]); field=connector["anchor_field"]
            anchor=float(raw_bars[field].iloc[ix]);
            expected=[[ix,anchor],[p2_ix,p2_price]]
            add(cid,f"fib_connector_{connector['name']}",list(zip(connector["xy"]["x"],connector["xy"]["y"])),expected)
    return {"audit_method":"Read actual Matplotlib artist coordinates; reload the guarded source/local window independently; recompute EMA/DIF by scalar recurrence and recompute 0.236/0.382 Decimal levels from raw anchor OHLC.",
            "checked_items":len(checks),"passed":sum(x["pass"] for x in checks),"failed":sum(not x["pass"] for x in checks),"checks":checks}


def make_contact_sheet(image_paths: list[Path], destination: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from PIL import Image
    n = len(image_paths)
    if not n:
        return
    fig, axes = plt.subplots(math.ceil(n / 2), 2, figsize=(18, max(7, math.ceil(n / 2) * 5.8)), squeeze=False)
    for ax, p in zip(axes.flat, image_paths):
        ax.imshow(Image.open(p).convert("RGB")); ax.set_title(p.stem, fontsize=10); ax.axis("off")
    for ax in list(axes.flat)[n:]: ax.axis("off")
    fig.suptitle("BTC regular divergence + Fibonacci casebook • contact sheet", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.98)); fig.savefig(destination, dpi=120, facecolor="white"); plt.close(fig)


def render_html(records: list[dict[str, Any]], image_paths: list[Path], provenance: dict[str, Any], destination: Path, font_ok: bool) -> None:
    enc = []
    for rec, p in zip(records, image_paths):
        raw = base64.b64encode(p.read_bytes()).decode("ascii")
        title = html.escape(f"{rec['case_id']} • {rec['type']} • {rec['event_status']}")
        if rec["type"] == "regular_bullish":
            explain=f"普通底背离：价格低点由 {rec['p1']['price']:,.1f} 下移至 {rec['p2']['price']:,.1f} USDT，而 DIF 由 {rec['dif_at_p1']:.3f} 上升至 {rec['dif_at_p2']:.3f}。小级别 Hsmall={rec['small_anchor']['price']:,.1f}；0.236 参考线 {rec['small_fib_0236_usdt']:,.1f}；entry/stop/target 参考分别为 {rec['entry_reference_usdt']:,.1f}/{rec['stop_reference_usdt']:,.1f}/{rec['target_reference_usdt'] if rec['target_reference_usdt'] is not None else 'Unavailable'} USDT。"
        else:
            explain=f"普通顶背离：价格高点由 {rec['p1']['price']:,.1f} 上移至 {rec['p2']['price']:,.1f} USDT，而 DIF 由 {rec['dif_at_p1']:.3f} 下移至 {rec['dif_at_p2']:.3f}。小级别 Lsmall={rec['small_anchor']['price']:,.1f}；0.236 参考线 {rec['small_fib_0236_usdt']:,.1f}；entry/stop/target 参考分别为 {rec['entry_reference_usdt']:,.1f}/{rec['stop_reference_usdt']:,.1f}/{rec['target_reference_usdt'] if rec['target_reference_usdt'] is not None else 'Unavailable'} USDT。"
        compat=rec.get("entry_compatibility")
        if compat:
            explain += f" Entry 首次触及：{compat['first_touch_open_utc']}；触发回撤 {compat['trigger_retracement_percent']:.3f}%；0.2% 确认阈值单独保证触及：{compat['threshold_alone_guarantees_touch']}。"
        enc.append(f"<section><h2>{title}</h2><p>{html.escape(explain)}</p><img alt='{title}' src='data:image/png;base64,{raw}'><details><summary>锚点与事件追踪 / Anchors and event trace</summary><pre>{html.escape(json.dumps(rec,ensure_ascii=False,indent=2))}</pre></details></section>")
    prov = html.escape(json.dumps(provenance,ensure_ascii=False,indent=2))
    summary=f"检测到 {len(records)} 个样例：{sum(r['type']=='regular_bullish' for r in records)} 个普通底背离，{sum(r['type']=='regular_bearish' for r in records)} 个普通顶背离。"
    content = """<!doctype html><html lang='zh-CN'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>BTC 背离与 Fibonacci 案例图册</title><style>body{font:16px/1.55 system-ui,'Microsoft YaHei',sans-serif;max-width:1500px;margin:2rem auto;padding:0 1rem;color:#17212b;background:#f7f9fc}h1{font-size:2rem}section{margin:2rem 0;padding:1rem;background:white;border:1px solid #d9e1ea;border-radius:12px;box-shadow:0 3px 14px #18334a12}img{width:100%;height:auto}pre{overflow:auto;white-space:pre-wrap;word-break:break-word;background:#f4f6f8;padding:1rem;border-radius:8px}.notice{padding:1rem;background:#fff4d7;border-left:5px solid #d49c28}summary{cursor:pointer}</style><body><h1>BTC 普通背离 + Fibonacci 历史案例图册</h1><p>"""+html.escape(summary)+""" BTCUSDT USDT 永续，5 分钟，时间均为 UTC。</p><p>仅展示有限历史形态，说明高低点选择、DIF 对照、Fib 入场触发参考、止损、目标与后续事件。底背离定义为价格 L2&lt;L1 且 DIF2&gt;DIF1；顶背离定义为 H2&gt;H1 且 DIF2&lt;DIF1。</p><div class='notice'><b>研究限制：</b>图册不提供策略效果、收益、胜率或可交易性证据；不计算净收益。tick=0.1 USDT 是历史 tick 未验证时的示意假设。局部副本仍为 UNVERIFIED_NO_FROZEN_RECORD；使用注册的原始只读源，2024–2025 窗口与本地副本精确交叉核对。历史冻结副本身份仍未建立。</div><h2>冻结规则</h2><ul><li>前 300 根已闭合 K 线作为 warmup；摆动候选至少经过 3 根 bar，并在收盘相对极值反转 0.2% 后确认。</li><li>高点只由严格更高的 high 替换，低点只由严格更低的 low 替换；相等时取最早点，保留低高点/高低点结构。</li><li>DIF=EMA12−EMA26，signal=EMA9(DIF)，adjust=False；DIF 取实际价位极值 candle；RSI14 仅作辅助。</li><li>相邻同类 pivot 间距 6–144 根，首个对照信号每类最多取 5 个；大小级别 Fib 分别使用中间反向极值、以及前方 288 根内已确认大级别极值。</li><li>小 Fib 0.236 用于 entry 参考和固定 stop；大 Fib 0.382 用于固定 target。信号确认后不回填已触发 entry；订单 24 根过期，未来最多展示 96 根。</li><li>同一根 bar 顺序不明时标为 uncertain；不推断 bar 内先后、不移动止损。</li></ul><p>黄色阴影代表确认收盘之后最多 96 根 K 线。每张图包含价格蜡烛、DIF/signal、P1/P2 极值及确认时间、大小锚点、Fib 参考线和事件状态。完整来源状态与逐点坐标核查记录如下。</p><details><summary>来源与限制 / Provenance</summary><pre>"""+prov+"</pre></details>" + "".join(enc) + "</body></html>"
    dates = [r["signal_confirmation_close_time_utc"][:10] for r in records]
    if dates and not any(x.startswith("2025") for x in dates):
        date_note = ("Full scan window: 2024-01-01 through 2025-12-31 UTC. Under the frozen first-five-per-type rule, all ten selected signals occurred "
                     f"{min(dates)} through {max(dates)}; no 2025 sample was selected. This is chronological selection, not year-stratified sampling.")
    else:
        date_note = "Full scan window: 2024-01-01 through 2025-12-31 UTC. Cases follow the frozen chronological first-five-per-type rule."
    compatibility=provenance.get("entry_compatibility_summary")
    compat_note=""
    if compatibility:
        compat_note=(f"Compatibility finding: all 10 frozen samples first touched the entry trigger on the first bar after P2, before the confirmation close; all confirmation closes were already beyond entry. In 4/10 cases the 0.2% reversal threshold alone guarantees trigger crossing; in the other 6/10 it does not algebraically guarantee crossing, but the observed first post-P2 bar still touched it. This is a compatibility limit of the frozen confirmation and entry definitions, not proof that no alternative execution rule could work. Fib levels are references only; no executable order or outcome is claimed."
                     f" 中文：10 个冻结样例均在 P2 之后第一根 K 线触及 entry，早于信号确认收盘；确认收盘时 entry 已被越过。4/10 个样例仅凭 0.2% 反转阈值即可推出触发线必然被穿过；其余 6/10 不满足该代数保证，但观察到的 P2 后第一根 K 线仍触及。此结论仅说明本次冻结确认规则与 entry 定义存在兼容性限制，不代表其他执行规则已被检验。Fib 价位仅为参考，没有可执行订单或绩效结论。")
    content = content.replace("<body>", "<body><p class='notice'><b>Sample coverage:</b> " + html.escape(date_note) + "</p>" + ("<p class='notice'>"+html.escape(compat_note)+"</p>" if compat_note else ""), 1)
    destination.write_text(content, encoding="utf-8")


def write_samples_csv(records: list[dict[str, Any]]) -> None:
    csv_path = HERE / "samples.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        fields = ["case_id","type","event_status","p1_extreme_open_utc","p1_confirm_close_utc","p1_price","p1_dif",
                  "p2_extreme_open_utc","p2_confirm_close_utc","p2_price","p2_dif","small_anchor_kind","small_anchor_time_utc",
                  "small_anchor_price","small_fib_0236_usdt","big_anchor_kind","big_anchor_time_utc","big_anchor_confirm_close_utc",
                  "big_anchor_price","big_fib_0382_usdt","entry_usdt","stop_usdt","target_usdt","fib_status",
                  "first_trigger_touch_open_utc","trigger_retracement_percent","threshold_alone_guarantees_touch"]
        writer = csv.DictWriter(fh,fieldnames=fields); writer.writeheader()
        for rec in records:
            row={"case_id":rec["case_id"],"type":rec["type"],"event_status":rec["event_status"],
                 "p1_extreme_open_utc":rec["p1"]["extreme_open_time_utc"],"p1_confirm_close_utc":rec["p1"]["confirmation_close_time_utc"],"p1_price":rec["p1"]["price"],"p1_dif":rec["dif_at_p1"],
                 "p2_extreme_open_utc":rec["p2"]["extreme_open_time_utc"],"p2_confirm_close_utc":rec["p2"]["confirmation_close_time_utc"],"p2_price":rec["p2"]["price"],"p2_dif":rec["dif_at_p2"],
                 "small_anchor_kind":rec["small_anchor"]["kind"],"small_anchor_time_utc":rec["small_anchor"]["open_time_utc"],"small_anchor_price":rec["small_anchor"]["price"],"small_fib_0236_usdt":rec["small_fib_0236_usdt"],
                 "big_anchor_kind":rec["big_anchor"]["kind"],"big_anchor_time_utc":rec["big_anchor"]["open_time_utc"],
                 "big_anchor_confirm_close_utc":rec["big_anchor"].get("confirmation_close_time_utc"),
                 "big_anchor_price":rec["big_anchor"]["price"],"big_fib_0382_usdt":rec["big_fib_0382_usdt"],
                 "entry_usdt":rec["entry_reference_usdt"],"stop_usdt":rec["stop_reference_usdt"],"target_usdt":rec["target_reference_usdt"],"fib_status":rec["fib_status"],
                 "first_trigger_touch_open_utc":rec.get("entry_compatibility",{}).get("first_touch_open_utc"),
                 "trigger_retracement_percent":rec.get("entry_compatibility",{}).get("trigger_retracement_percent"),
                 "threshold_alone_guarantees_touch":rec.get("entry_compatibility",{}).get("threshold_alone_guarantees_touch")}
            writer.writerow(row)


def main() -> None:
    import argparse
    parser=argparse.ArgumentParser(description="Frozen BTC divergence/Fibonacci casebook")
    parser.add_argument("--render-existing-manifest",action="store_true",help="render current frozen samples.json without reselecting signals")
    args=parser.parse_args()
    font, font_ok = _font_setup()
    bars, provenance = load_verified_window()
    provenance["font"] = font
    provenance["chinese_font_available"] = font_ok
    provenance["rows_used_for_scan"] = len(bars)
    provenance["warmup_bars"] = 300
    provenance["scan_window"] = "2024-01-01 through 2025-12-31 UTC open times inclusive"
    provenance["tick_assumption"] = "0.1 USDT; historical tick UNVERIFIED"
    manifest_path=HERE/"samples.json"
    if args.render_existing_manifest:
        frozen=json.loads(manifest_path.read_text(encoding="utf-8"))
        records=frozen["cases"]
        # Pivot-only reconciliation supplies the confirmation close for the already
        # selected big anchors. It does not call paired_signals or alter case IDs.
        pivots=leg_pivots(bars,300)
        pivot_by_key={(p.kind,p.index):p for p in pivots}
        for rec in records:
            anchor=rec["big_anchor"]
            if anchor["index"] is None:
                anchor["confirm_index"]=None; anchor["confirmation_close_time_utc"]=None
                continue
            pivot=pivot_by_key.get(("high" if anchor["kind"]=="bigH" else "low",int(anchor["index"])))
            if pivot is None or pivot.confirm_index>rec["p2"]["confirm_index"]:
                raise RuntimeError(f"frozen big anchor is not independently confirmed by signal: {rec['case_id']}")
            anchor["confirm_index"]=pivot.confirm_index
            anchor["confirmation_close_time_utc"]=iso_at(bars,pivot.confirm_index,True)
        compat_path=HERE/"review_detector_entry_compatibility.json"
        if compat_path.exists():
            compatibility=json.loads(compat_path.read_text(encoding="utf-8"))
            by_case={x["case_id"]:x for x in compatibility["cases"]}
            for rec in records:
                detail=by_case[rec["case_id"]]
                rec["entry_compatibility"]={k:detail[k] for k in ("trigger_retracement_percent","threshold_alone_guarantees_trigger_touch",
                    "first_touch_index","first_touch_open_utc","confirm_index","bars_after_extreme_to_first_touch",
                    "confirm_close","confirm_close_already_beyond_entry")}
                rec["entry_compatibility"]["threshold_alone_guarantees_touch"]=detail["threshold_alone_guarantees_trigger_touch"]
                rec["entry_compatibility"]["first_touch_close_utc"]=(pd.Timestamp(detail["first_touch_open_utc"])+pd.Timedelta(minutes=5)).isoformat()
                if not any(x.get("event")=="pre_signal_trigger_touch" for x in rec["event_trace"]):
                    rec["event_trace"].append({"event":"pre_signal_trigger_touch",**rec["entry_compatibility"]})
            provenance["entry_compatibility_summary"]={"threshold_guaranteed_count":compatibility["threshold_guaranteed_count"],
                "not_algebraically_guaranteed_but_observed_touch_count":compatibility["not_algebraically_guaranteed_but_observed_touch_count"],
                "all_first_touches_one_bar_after_p2":all(x["bars_after_extreme_to_first_touch"]==1 for x in compatibility["cases"]),
                "all_confirmation_closes_beyond_entry":all(x["confirm_close_already_beyond_entry"] for x in compatibility["cases"])}
        manifest_path.write_text(json.dumps({**frozen,"cases":records},ensure_ascii=False,indent=2),encoding="utf-8")
        write_samples_csv(records)
        cases=cases_from_manifest(records,bars)
        provenance["signal_scan_pass_count"]=2
        provenance["signal_scan_rerun_note"]="Two signal-selection passes were executed during implementation; the first was replaced after code corrections to honor the frozen pivot-expiry interpretation and fix chart/audit timing. No window, numeric threshold, market input, or case selection was changed based on event outcomes. Final chart-only render reused the frozen selected manifest and did not reselect signals."
        provenance["render_mode"]="FROZEN_MANIFEST_ONLY; no paired-signal rescan"
        provenance["pivot_confirmation_reconciliation"]="One pivot-only pass to add selected big-anchor confirmation close evidence; no hidden or regular divergence signal selection."
        pivot_count=frozen.get("all_confirmed_pivots")
    else:
        cases,pivots,dif,sig=prepare_cases(bars)
        records=[case_record(c,bars) for c in cases]
        manifest_path.write_text(json.dumps({"sample_count":len(records),"all_confirmed_pivots":len(pivots),"cases":records},ensure_ascii=False,indent=2),encoding="utf-8")
        write_samples_csv(records)
        pivot_count=len(pivots)
        provenance["signal_scan_pass_count"]=1
        provenance["render_mode"]="SIGNAL_SCAN_AND_RENDER"
    provenance["selected_case_confirmation_dates_utc"]=[rec["signal_confirmation_close_time_utc"][:10] for rec in records]
    provenance["selected_case_date_range_utc"]=[min(provenance["selected_case_confirmation_dates_utc"]),max(provenance["selected_case_confirmation_dates_utc"])] if records else []
    provenance["selected_cases_in_2025"]=sum(d.startswith("2025") for d in provenance["selected_case_confirmation_dates_utc"])
    provenance["performance_claims_made"]=False
    provenance["strategy_validation_gate"]="NOT_RUN; visual casebook only"
    (HERE/"provenance.json").write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding="utf-8")
    chart_dir=HERE/"charts"; chart_dir.mkdir(exist_ok=True)
    chart_paths=[]; audits=[]
    for case in cases:
        out=chart_dir/f"{case['case_id']}_{case['kind']}.png"
        audits.append(draw_case(case,bars,out,font_ok)); chart_paths.append(out)
    audit_bars, audit_provenance=load_verified_window()
    if audit_provenance["primary_sha256"]!=provenance["primary_sha256"] or audit_provenance["local_crosscheck_sha256"]!=provenance["local_crosscheck_sha256"]:
        raise RuntimeError("source identity changed between render and independent coordinate audit")
    audit=coordinate_audit(audits,audit_bars)
    if audit["failed"]:
        raise RuntimeError(f"independent chart-coordinate audit failed: {audit['failed']} point(s)")
    (HERE/"coordinate_audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
    make_contact_sheet(chart_paths,HERE/"contact_sheet.png")
    report_path=HERE/"BTC_2024_2025_divergence_fib_casebook.html"
    render_html(records,chart_paths,provenance,report_path,font_ok)
    import shutil
    shutil.copyfile(report_path,HERE/"index.html")
    (HERE/"render_summary.json").write_text(json.dumps({"case_count":len(records),"bullish_count":sum(c['kind']=='regular_bullish' for c in cases),
        "bearish_count":sum(c['kind']=='regular_bearish' for c in cases),"pivot_count":pivot_count,"coordinate_audit_passed":audit['passed'],
        "coordinate_audit_failed":audit['failed'],"font":font,"chinese_font_available":font_ok,
        "selected_case_date_range_utc":provenance["selected_case_date_range_utc"],
        "selected_cases_in_2025":provenance["selected_cases_in_2025"],
        "charts":[{"path":p.relative_to(HERE).as_posix(),"bytes":p.stat().st_size} for p in chart_paths]},ensure_ascii=False,indent=2),encoding="utf-8")


if __name__ == "__main__":
    main()
