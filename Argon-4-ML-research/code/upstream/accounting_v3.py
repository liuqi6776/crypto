"""Finite accounting replay for the frozen V2 ten-case BTC example set.

This module consumes already-frozen cases and bounded OHLCV. It never scans for
signals. Price paths and equal-third intrabar timestamps are scenario assumptions,
not observed ticks or executable fills.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import math
from typing import Any, Iterable

import numpy as np


TICK = Decimal("0.1")
QSTEP = Decimal("0.00000001")
NS = 1_000_000_000


def floor_tick(x: float) -> float:
    return float((Decimal(str(x)) / TICK).to_integral_value(rounding=ROUND_FLOOR) * TICK)


def ceil_tick(x: float) -> float:
    return float((Decimal(str(x)) / TICK).to_integral_value(rounding=ROUND_CEILING) * TICK)


def floor_qty(x: float) -> float:
    return float((Decimal(str(x)) / QSTEP).to_integral_value(rounding=ROUND_FLOOR) * QSTEP)


def adverse_fill(reference: float, action: str, slip: float) -> float:
    """Apply adverse proportional slippage, then illustrative tick rounding."""
    if action == "buy":
        return ceil_tick(reference * (1 + slip))
    if action == "sell":
        return floor_tick(reference * (1 - slip))
    raise ValueError("action must be buy or sell")


def size_position(*, equity: float, side: int, entry_fill: float,
                  stop_ref: float, target_ref: float, fee: float,
                  slip: float) -> dict[str, float]:
    """Frozen risk sizing, adverse stop estimate, fee reserve and 1x cap."""
    if side not in (-1, 1) or min(equity, entry_fill, stop_ref, target_ref) <= 0:
        raise ValueError("invalid size inputs")
    stop_est = adverse_fill(stop_ref, "sell" if side == 1 else "buy", slip)
    target_est = adverse_fill(target_ref, "sell" if side == 1 else "buy", slip)
    if side == 1:
        cap_notional = entry_fill
    else:
        cap_notional = max(entry_fill, 2 * stop_est - entry_fill)
    risk_unit = abs(entry_fill - stop_est) + fee * (entry_fill + stop_est)
    cap_unit = cap_notional + fee * entry_fill + fee * max(entry_fill, stop_est, target_est)
    risk_budget = 0.005 * equity
    q = floor_qty(min(risk_budget / risk_unit, equity / cap_unit))
    return {
        "quantity": q, "risk_unit": risk_unit, "risk_budget": risk_budget,
        "planned_cash_stop_loss": q * risk_unit, "stop_fill_est": stop_est,
        "target_fill_est": target_est, "cap_unit": cap_unit,
        "max_qty_1x": equity / cap_unit,
    }


def interp_ns(t0: int, t1: int, frac: float) -> int:
    return int(t0 + round((t1 - t0) * frac))


@dataclass
class Position:
    case_id: str
    version: int
    side: int
    qty: float
    entry_ref: float
    entry_fill: float
    entry_ns: int
    entry_bar_index: int
    candidate_extreme_open_utc: str
    candidate_decision_close_utc: str
    order_activation_open_utc: str
    stop: float
    target: float
    fee_rate: float
    slip_rate: float
    risk_budget: float
    planned_risk: float
    risk_unit: float
    entry_fee: float
    entry_slip_cost: float
    funding_cash: float = 0.0
    funding_events: list[dict[str, Any]] = field(default_factory=list)


def crossing_fraction(*, side: int, pending: bool, order: dict[str, Any] | None,
                       position: Position | None, p0: float, p1: float) -> tuple[float, str, float] | None:
    """First trigger crossed on one monotone price segment."""
    if p0 == p1:
        return None
    candidates: list[tuple[float, str, float]] = []
    if position is not None:
        s = position.side
        # A crossing at an endpoint is included. Only the correct traversal
        # direction is eligible, which prevents pre-entry stop touches exiting.
        if s == 1:
            if p1 > p0 and p0 <= position.target <= p1:
                candidates.append(((position.target - p0) / (p1 - p0), "TARGET", position.target))
            if p1 < p0 and p1 <= position.stop <= p0:
                candidates.append(((position.stop - p0) / (p1 - p0), "STOP", position.stop))
        else:
            if p1 < p0 and p1 <= position.target <= p0:
                candidates.append(((position.target - p0) / (p1 - p0), "TARGET", position.target))
            if p1 > p0 and p0 <= position.stop <= p1:
                candidates.append(((position.stop - p0) / (p1 - p0), "STOP", position.stop))
    # Pending orders remain visible while a different position is open so that
    # their first touch is rejected and logged as BUSY_POSITION_AT_TRIGGER.
    if pending and order is not None:
        trigger = float(order["entry"])
        pending_side = int(order["side"])
        if pending_side == 1 and p1 > p0 and p0 <= trigger <= p1:
            candidates.append(((trigger - p0) / (p1 - p0), "ENTRY", trigger))
        elif pending_side == -1 and p1 < p0 and p1 <= trigger <= p0:
            candidates.append(((trigger - p0) / (p1 - p0), "ENTRY", trigger))
    if not candidates:
        return None
    f, kind, level = min(candidates, key=lambda x: x[0])
    return max(0.0, min(1.0, f)), kind, level


class ScenarioEngine:
    def __init__(self, *, bars, cases: list[dict[str, Any]], funding_events: list[dict[str, Any]],
                 fund_mode: str, fee_rate: float, slip_rate: float, path_name: str,
                 cancel_case04: bool = False, scenario_id: str = ""):
        self.bars = bars
        self.cases = cases
        self.funding_events = funding_events
        self.fund_mode = fund_mode
        self.fee_rate = fee_rate
        self.slip_rate = slip_rate
        self.path_name = path_name
        self.cancel_case04 = cancel_case04
        self.scenario_id = scenario_id
        self.wallet = 10_000.0
        self.pos: Position | None = None
        self.pending: list[dict[str, Any]] = []
        self.versions: dict[tuple[str, int], dict[str, Any]] = {}
        self.case_by_id: dict[str, dict[str, Any]] = {c["case_id"]: c for c in cases}
        self.case_traded: set[str] = set()
        self.version_outcomes: dict[tuple[str, int], dict[str, Any]] = {}
        self.trade_rows: list[dict[str, Any]] = []
        self.event_rows: list[dict[str, Any]] = []
        self.mtm_rows: list[dict[str, Any]] = []
        self.busy_count = 0
        self.cap_breaches: list[dict[str, Any]] = []
        self.missing_funding: list[dict[str, Any]] = []
        self.realized = 0.0
        self.fees_paid = 0.0
        self.funding_paid = 0.0
        self.slippage_diagnostic = 0.0
        self.last_close_ns = int(bars.open_time.iloc[0].value)
        self.row_to_activations: dict[int, list[dict[str, Any]]] = {}
        self.row_to_cancels: dict[int, list[tuple[str, int]]] = {}
        self.row_to_eventidx: dict[int, list[dict[str, Any]]] = {}
        for c in cases:
            for v in c["versions"]:
                key = (c["case_id"], int(v["version"]))
                self.versions[key] = v
                self.version_outcomes[key] = {
                    "scenario_id": scenario_id, "case_id": c["case_id"],
                    "version": int(v["version"]), "frozen_v2_status": v["status"],
                    "armed_v2": bool(v.get("armed")), "disposition": v["status"],
                    "activation_index": v.get("active_from_index"),
                    "decision_close_utc": v.get("decision_close_utc"),
                    "activation_open_utc": v.get("activation_open_utc"),
                }
                if v.get("armed"):
                    self.row_to_activations.setdefault(int(v["active_from_index"]), []).append({"case": c, "version": v})
                # Native V2 closed-bar cancellation only.
                for e in c.get("events", []):
                    if e.get("event") == "CANCELLED_REFRESH_WITH_STOP_INVALIDATION" and int(e.get("version", -1)) == int(v["version"]):
                        self.row_to_cancels.setdefault(int(e["index"]), []).append(key)
        for e in funding_events:
            idx = int(e["bar_index"])
            self.row_to_eventidx.setdefault(idx, []).append(e)
        for rows in self.row_to_activations.values():
            rows.sort(key=lambda z: (int(z["version"]["active_from_index"]), z["case"]["case_id"], int(z["version"]["version"])))

    def _time(self, idx: int, offset_ns: int = 0) -> int:
        return int(self.bars.open_time.iloc[idx].value) + offset_ns

    def _result_event(self, case_id: str, version: int, kind: str, idx: int,
                      time_ns: int | None = None, **extra):
        self.event_rows.append({
            "scenario_id": self.scenario_id, "case_id": case_id, "version": version,
            "event": kind, "bar_index": idx, "time_ns": int(time_ns if time_ns is not None else self._time(idx)),
            **extra,
        })

    def _activate(self, idx: int):
        for pair in self.row_to_activations.get(idx, []):
            c, v = pair["case"], pair["version"]
            cid, vn = c["case_id"], int(v["version"])
            key = (cid, vn)
            outcome = self.version_outcomes[key]
            if cid == "CASE_04" and vn == 2 and self.cancel_case04:
                outcome["disposition"] = "ALTERNATIVE_CANCEL_BEFORE_TRIGGER_POLICY"
                outcome["actual_activation"] = False
                self._result_event(cid, vn, "ALTERNATIVE_CANCEL_BEFORE_TRIGGER_POLICY", idx)
                continue
            if cid in self.case_traded:
                outcome["disposition"] = "CASE_ALREADY_FILLED_NO_REOPEN"
                self._result_event(cid, vn, "CASE_ALREADY_FILLED_NO_REOPEN", idx)
                continue
            if self.pos is not None:
                outcome["disposition"] = "BUSY_POSITION_AT_ACTIVATION"
                self.busy_count += 1
                self._result_event(cid, vn, "BUSY_POSITION_AT_ACTIVATION", idx)
                continue
            order = {
                "case_id": cid, "version": vn, "side": 1 if c["type"] == "regular_bullish" else -1,
                "entry": float(v["levels"]["entry"]), "stop": float(v["levels"]["stop"]),
                "target": float(v["levels"]["target"]), "active_from": int(v["active_from_index"]),
                "active_through": int(v["active_through_index"]), "activation_ns": self._time(idx),
                "decision_ns": int(__import__("pandas").Timestamp(v["decision_close_utc"]).value),
                "candidate_extreme_open_utc": v["candidate_extreme_open_utc"],
                "candidate_decision_close_utc": v["decision_close_utc"],
                "order_activation_open_utc": v["activation_open_utc"],
                "entry_attempted": False,
            }
            outcome["disposition"] = "ACTIVE_PENDING"
            outcome["actual_activation"] = True
            self.pending.append(order)
            self.pending.sort(key=lambda o: (o["active_from"], o["case_id"], o["version"]))
            self._result_event(cid, vn, "ORDER_ACTIVE_NEXT_BAR", idx, order["activation_ns"],
                               entry=order["entry"], stop=order["stop"], target=order["target"])

    def _funding(self, ev: dict[str, Any], idx: int):
        # No synthetic zero: incomplete native rate/proxy data blocks the scenario.
        if self.pos is None:
            self.event_rows.append({"scenario_id": self.scenario_id, "event": "FUNDING_NO_POSITION",
                                    "bar_index": idx, "time_ns": ev["time_ns"],
                                    "funding_event_id": ev["event_id"]})
            return
        if ev.get("rate") is None or ev.get("proxy_mark") is None:
            self.missing_funding.append({"funding_event_id": ev["event_id"], "time_ns": ev["time_ns"]})
            self.event_rows.append({"scenario_id": self.scenario_id, "event": "BLOCKED_MISSING_FUNDING_OR_MARK",
                                    "bar_index": idx, "time_ns": ev["time_ns"],
                                    "funding_event_id": ev["event_id"]})
            return
        mark = float(ev["proxy_mark"] if self.fund_mode == "open_proxy" else ev["low" if self.fund_mode == "low_sensitivity" else "high"])
        cash = -self.pos.side * self.pos.qty * mark * float(ev["rate"])
        self.wallet += cash
        self.funding_paid += cash
        self.pos.funding_cash += cash
        rec = {
            "scenario_id": self.scenario_id, "case_id": self.pos.case_id,
            "version": self.pos.version, "funding_event_id": ev["event_id"],
            "funding_time_utc": ev["time_utc"], "funding_time_ms": ev["time_ms"],
            "rate": float(ev["rate"]), "mark_mode": self.fund_mode,
            "proxy_candle_open_utc": ev["mark_time_utc"], "mark_open": float(ev["proxy_mark"]),
            "mark_low_sensitivity": float(ev["low"]), "mark_high_sensitivity": float(ev["high"]),
            "mark_used": mark, "cash_delta_usdt": cash,
        }
        self.pos.funding_events.append(rec)
        self.event_rows.append({"scenario_id": self.scenario_id, "case_id": self.pos.case_id,
                                "version": self.pos.version, "event": "OBSERVED_FUNDING_APPLIED",
                                "bar_index": idx, "time_ns": ev["time_ns"], **rec})

    def _actual_fill(self, ref: float, action: str) -> tuple[float, float]:
        fill = adverse_fill(ref, action, self.slip_rate)
        slip_cost_per_unit = (fill - ref) if action == "buy" else (ref - fill)
        return fill, max(0.0, slip_cost_per_unit)

    def _reject_order(self, order: dict[str, Any], reason: str, idx: int, t_ns: int, **extra):
        key = (order["case_id"], order["version"])
        self.version_outcomes[key]["disposition"] = reason
        self.version_outcomes[key]["entry_attempted"] = True
        self._result_event(order["case_id"], order["version"], reason, idx, t_ns, **extra)
        if order in self.pending:
            self.pending.remove(order)

    def _enter(self, order: dict[str, Any], ref: float, idx: int, t_ns: int, *, gap: bool):
        if order["case_id"] in self.case_traded:
            self._reject_order(order, "CASE_ALREADY_FILLED_NO_REOPEN", idx, t_ns)
            return False
        if self.pos is not None:
            self._reject_order(order, "BUSY_POSITION_AT_TRIGGER", idx, t_ns)
            self.busy_count += 1
            return False
        action = "buy" if order["side"] == 1 else "sell"
        fill, slip_per_unit = self._actual_fill(ref, action)
        target_fill_est = adverse_fill(order["target"], "sell" if order["side"] == 1 else "buy", self.slip_rate)
        # Reject only when the actual entry is at/beyond the RAW fixed target.
        # A still-profitable target that becomes net-negative after costs is retained.
        raw_target_profitable = order["side"] * (order["target"] - fill) > 0
        if not raw_target_profitable:
            self._reject_order(order, "ENTRY_GAP_INVALIDATES_RAW_TARGET", idx, t_ns,
                               entry_fill=fill, raw_target=order["target"])
            return False
        sizing = size_position(equity=self.wallet, side=order["side"], entry_fill=fill,
                               stop_ref=order["stop"], target_ref=order["target"],
                               fee=self.fee_rate, slip=self.slip_rate)
        q = sizing["quantity"]
        if q <= 0:
            self._reject_order(order, "ZERO_SIZE_AFTER_CAP", idx, t_ns, entry_fill=fill)
            return False
        fee = q * fill * self.fee_rate
        slip_cost = q * slip_per_unit
        self.wallet -= fee
        self.fees_paid += fee
        self.slippage_diagnostic += slip_cost
        self.pos = Position(
            case_id=order["case_id"], version=order["version"], side=order["side"], qty=q,
            entry_ref=ref, entry_fill=fill, entry_ns=t_ns, entry_bar_index=idx,
            candidate_extreme_open_utc=order["candidate_extreme_open_utc"],
            candidate_decision_close_utc=order["candidate_decision_close_utc"],
            order_activation_open_utc=order["order_activation_open_utc"],
            stop=order["stop"], target=order["target"],
            fee_rate=self.fee_rate, slip_rate=self.slip_rate, risk_budget=sizing["risk_budget"],
            planned_risk=sizing["planned_cash_stop_loss"], risk_unit=sizing["risk_unit"],
            entry_fee=fee, entry_slip_cost=slip_cost,
        )
        self.case_traded.add(order["case_id"])
        self.version_outcomes[(order["case_id"], order["version"])]["disposition"] = "FILLED_OPEN"
        self.version_outcomes[(order["case_id"], order["version"])]["entry_attempted"] = True
        self.version_outcomes[(order["case_id"], order["version"])]["entry_fill_usdt"] = fill
        self.version_outcomes[(order["case_id"], order["version"])]["quantity_btc"] = q
        self.version_outcomes[(order["case_id"], order["version"])]["risk_budget_usdt"] = sizing["risk_budget"]
        self.version_outcomes[(order["case_id"], order["version"])]["planned_stop_loss_usdt"] = sizing["planned_cash_stop_loss"]
        self._result_event(order["case_id"], order["version"], "ENTRY_FILLED_GAP" if gap else "ENTRY_FILLED_TRIGGER",
                           idx, t_ns, reference=ref, fill=fill, quantity=q, fee=fee, slip_cost_embedded=slip_cost,
                           risk_budget=sizing["risk_budget"], planned_stop_loss=sizing["planned_cash_stop_loss"])
        self.pending.remove(order)
        # Any other already-live order that triggers later while the position is held
        # is explicitly rejected on trigger; it cannot overlap or reopen after exit.
        return True

    def _exit(self, reason: str, ref: float, idx: int, t_ns: int, *, gap: bool):
        pos = self.pos
        if pos is None:
            return
        action = "sell" if pos.side == 1 else "buy"
        fill, slip_per_unit = self._actual_fill(ref, action)
        fee = pos.qty * fill * self.fee_rate
        price_pnl = pos.side * pos.qty * (fill - pos.entry_fill)
        self.wallet += price_pnl - fee
        self.realized += price_pnl
        self.fees_paid += fee
        slip_cost = pos.qty * slip_per_unit
        self.slippage_diagnostic += slip_cost
        net = price_pnl - pos.entry_fee - fee + pos.funding_cash
        risk_r = net / pos.planned_risk if pos.planned_risk else None
        trade = {
            "scenario_id": self.scenario_id, "case_id": pos.case_id, "version": pos.version,
            "side": "LONG" if pos.side == 1 else "SHORT", "quantity_btc": pos.qty,
            "candidate_extreme_open_utc": pos.candidate_extreme_open_utc,
            "candidate_decision_close_utc": pos.candidate_decision_close_utc,
            "order_activation_open_utc": pos.order_activation_open_utc,
            "entry_time_assumed_utc": self._iso_ns(pos.entry_ns),
            "entry_time_observed_window_open_utc": str(self.bars.open_time.iloc[pos.entry_bar_index]),
            "entry_time_observed_window_close_utc": self._iso_ns(self._time(pos.entry_bar_index, 300 * NS)),
            "entry_ref": pos.entry_ref, "entry_fill": pos.entry_fill,
            "stop_ref": pos.stop, "target_ref": pos.target,
            "exit_time_assumed_utc": self._iso_ns(t_ns), "exit_bar_index": idx,
            "exit_time_observed_window_open_utc": str(self.bars.open_time.iloc[idx]),
            "exit_time_observed_window_close_utc": self._iso_ns(self._time(idx, 300 * NS)),
            "exit_reason": reason, "exit_ref": ref, "exit_fill": fill,
            "gap_exit": gap, "gross_price_pnl_usdt": price_pnl,
            "entry_fee_usdt": pos.entry_fee, "exit_fee_usdt": fee,
            "total_fee_usdt": pos.entry_fee + fee,
            "slippage_cost_diagnostic_embedded_usdt": pos.entry_slip_cost + slip_cost,
            "funding_cash_usdt": pos.funding_cash, "funding_event_count": len(pos.funding_events),
            "net_pnl_usdt": net, "risk_budget_usdt": pos.risk_budget,
            "planned_cash_stop_loss_usdt": pos.planned_risk, "net_R": risk_r,
            "wallet_after_exit": self.wallet,
            "funding_events": pos.funding_events,
        }
        self.trade_rows.append(trade)
        self.version_outcomes[(pos.case_id, pos.version)]["disposition"] = "FILLED_EXITED_" + reason
        self.version_outcomes[(pos.case_id, pos.version)]["exit_time_assumed_utc"] = self._iso_ns(t_ns)
        self.version_outcomes[(pos.case_id, pos.version)]["net_pnl_usdt"] = net
        self._result_event(pos.case_id, pos.version, "EXIT_" + reason, idx, t_ns,
                           exit_ref=ref, exit_fill=fill, gap=gap, net_pnl_usdt=net)
        self.pos = None

    @staticmethod
    def _iso_ns(ns: int) -> str:
        import pandas as pd
        return pd.Timestamp(ns, tz="UTC").isoformat().replace("+00:00", "Z")

    def _funding_between_segment(self, idx: int, t0: int, t1: int,
                                 fraction_to_event: float, p0: float, p1: float):
        # Funding event timestamps in (t0,t1]; compute its exact point along the
        # assumed linear segment. Times are scenario assumptions, not tick data.
        events = [e for e in self.row_to_eventidx.get(idx, []) if t0 < int(e["time_ns"]) <= t1]
        events.sort(key=lambda e: int(e["time_ns"]))
        cursor = 0.0
        for ev in events:
            f = (int(ev["time_ns"]) - t0) / (t1 - t0) if t1 > t0 else 0.0
            # Price-cross events strictly before settlement occur first. A tie is
            # settled before a fill/exit: entry<event excludes equal-time entry,
            # while event<=exit includes equal-time exit.
            while True:
                cur_p = p0 + (p1 - p0) * cursor
                next_hit = crossing_fraction(side=0, pending=bool(self.pending),
                                             order=self.pending[0] if self.pending else None,
                                             position=self.pos, p0=cur_p, p1=p1)
                hit_f = None if next_hit is None else cursor + (1 - cursor) * next_hit[0]
                if hit_f is None or hit_f >= f:
                    break
                hit_p = p0 + (p1 - p0) * hit_f
                hit_t = interp_ns(t0, t1, hit_f)
                self._handle_cross(next_hit[1], next_hit[2], idx, hit_t, hit_p)
                cursor = hit_f
                if cursor >= 1:
                    break
            self._funding(ev, idx)
            # Include a crossing exactly at settlement time after applying event.
            if f >= cursor:
                cur_p = p0 + (p1 - p0) * cursor
                hit = crossing_fraction(side=0, pending=bool(self.pending),
                                         order=self.pending[0] if self.pending else None,
                                         position=self.pos, p0=cur_p, p1=p1)
                if hit is not None:
                    hit_f = cursor + (1 - cursor) * hit[0]
                    if abs(hit_f - f) <= 1e-12:
                        hit_p = p0 + (p1 - p0) * f
                        self._handle_cross(hit[1], hit[2], idx, int(ev["time_ns"]), hit_p)
                        cursor = f
        # Process remaining price crossings after last event.
        while cursor < 1.0:
            cur_p = p0 + (p1 - p0) * cursor
            hit = crossing_fraction(side=0, pending=bool(self.pending),
                                     order=self.pending[0] if self.pending else None,
                                     position=self.pos, p0=cur_p, p1=p1)
            if hit is None:
                break
            hit_f = cursor + (1 - cursor) * hit[0]
            hit_p = p0 + (p1 - p0) * hit_f
            hit_t = interp_ns(t0, t1, hit_f)
            self._handle_cross(hit[1], hit[2], idx, hit_t, hit_p)
            cursor = hit_f
            if hit_f >= 1.0:
                break

    def _handle_cross(self, kind: str, level: float, idx: int, t_ns: int, price: float):
        if kind == "ENTRY":
            # The frozen path has a single pending-entry priority. If occupied,
            # reject touched orders in order, never defer their historical touch.
            order = self.pending[0]
            if self.pos is not None:
                self._reject_order(order, "BUSY_POSITION_AT_TRIGGER", idx, t_ns)
                self.busy_count += 1
                return
            # In a crossing segment, execute at the fixed trigger reference.
            self._enter(order, level, idx, t_ns, gap=False)
        elif kind == "STOP":
            self._exit("STOP", level, idx, t_ns, gap=False)
        elif kind == "TARGET":
            self._exit("TARGET", level, idx, t_ns, gap=False)

    def _at_open(self, idx: int, open_px: float, open_ns: int):
        # Funding exactly at the candle open occurs before open-gap fill/exit;
        # entry<event excludes an equal-time entry, exit-time equality includes it.
        for ev in self.row_to_eventidx.get(idx, []):
            if int(ev["time_ns"]) == open_ns:
                self._funding(ev, idx)
        if self.pos is not None:
            p = self.pos
            if (p.side == 1 and open_px <= p.stop) or (p.side == -1 and open_px >= p.stop):
                self._exit("STOP", open_px, idx, open_ns, gap=True)
            elif (p.side == 1 and open_px >= p.target) or (p.side == -1 and open_px <= p.target):
                self._exit("TARGET", open_px, idx, open_ns, gap=True)
        if self.pos is None:
            for order in list(self.pending):
                if not (order["active_from"] <= idx <= order["active_through"]):
                    continue
                crossed = (open_px >= order["entry"]) if order["side"] == 1 else (open_px <= order["entry"])
                if crossed:
                    self._enter(order, open_px, idx, open_ns, gap=True)
                    if self.pos is not None:
                        break
        # Remaining funding events after open are processed during the first
        # intrabar segment, retaining millisecond offsets.

    def _expire_and_cancel(self, idx: int):
        for key in self.row_to_cancels.get(idx, []):
            for order in list(self.pending):
                if (order["case_id"], order["version"]) == key:
                    self.pending.remove(order)
                    self.version_outcomes[key]["disposition"] = "CANCELLED_REFRESH_AT_BAR_CLOSE"
                    self._result_event(key[0], key[1], "CANCELLED_REFRESH_AT_BAR_CLOSE", idx,
                                       self._time(idx, 300 * NS))
        for order in list(self.pending):
            if idx >= order["active_through"]:
                self.pending.remove(order)
                key = (order["case_id"], order["version"])
                self.version_outcomes[key]["disposition"] = "EXPIRED_UNFILLED"
                self._result_event(key[0], key[1], "EXPIRED_UNFILLED", idx, self._time(idx, 300 * NS))

    def _mtm(self, idx: int, close_px: float):
        unreal = 0.0 if self.pos is None else self.pos.side * self.pos.qty * (close_px - self.pos.entry_fill)
        equity = self.wallet + unreal
        gross = 0.0 if self.pos is None else self.pos.qty * close_px
        margin = 0.0 if self.pos is None else self.pos.qty * self.pos.entry_fill
        if gross > equity + 1e-8:
            self.cap_breaches.append({"bar_index": idx, "gross": gross, "equity": equity})
        self.mtm_rows.append({
            "scenario_id": self.scenario_id, "bar_index": idx,
            "time_open_utc": str(self.bars.open_time.iloc[idx]),
            "time_close_utc": self._iso_ns(self._time(idx, 300 * NS)),
            "wallet": self.wallet, "realized_price_pnl_cum": self.realized,
            "fees_cum": self.fees_paid, "funding_cum": self.funding_paid,
            "unrealized_price_pnl": unreal, "equity": equity,
            "close_trade_price_proxy": close_px, "signed_qty": 0.0 if self.pos is None else self.pos.side * self.pos.qty,
            "gross_marked_notional": gross, "locked_margin_collateral": margin,
            "margin_not_cash_expenditure": True,
        })

    def run(self) -> dict[str, Any]:
        # Every fixed armed version that never reaches an activation is impossible
        # under this bounded prefix; retain its status explicitly.
        for i, row in self.bars.iterrows():
            idx = int(i)
            o, h, l, c = (float(row[k]) for k in ("open", "high", "low", "close"))
            op_ns = int(row.open_time.value)
            self._activate(idx)
            self._at_open(idx, o, op_ns)
            first, second, third = ((h, l, c) if self.path_name == "O-H-L-C" else (l, h, c))
            points = [o, first, second, third]
            times = [op_ns, op_ns + 100 * NS, op_ns + 200 * NS, op_ns + 300 * NS]
            for seg in range(3):
                self._funding_between_segment(idx, times[seg], times[seg + 1], 0, points[seg], points[seg + 1])
            # Closed-bar version cancellation and pending expiry occur only after
            # the entire assumed OHLC path has been traversed.
            self._expire_and_cancel(idx)
            if idx == len(self.bars) - 1 and self.pos is not None:
                self._exit("END_WINDOW", c, idx, times[-1], gap=False)
            self._mtm(idx, c)
        if self.pos is not None:
            raise AssertionError("end-window position failed to flatten")
        eq = np.asarray([r["equity"] for r in self.mtm_rows], float)
        eq0 = np.concatenate(([10_000.0], eq))
        peak = np.maximum.accumulate(eq0)
        dd = peak - eq0
        dd_pct = np.divide(dd, peak, out=np.zeros_like(dd), where=peak != 0)
        return {
            "scenario_id": self.scenario_id, "execution_path": self.path_name,
            "cancel_policy_case04": self.cancel_case04, "cost_fee_rate_per_side": self.fee_rate,
            "cost_slip_rate_per_side": self.slip_rate, "funding_valuation_mode": self.fund_mode,
            "initial_wallet": 10_000.0, "final_wallet": self.wallet,
            "final_equity": eq[-1], "net_change_usdt": eq[-1] - 10_000.0,
            "net_change_pct": (eq[-1] / 10_000 - 1) * 100,
            "max_drawdown_usdt_5m_close": float(dd.max()),
            "max_drawdown_pct_5m_close": float(dd_pct.max() * 100),
            "realized_price_pnl": self.realized, "total_fees": self.fees_paid,
            "funding_net_cash": self.funding_paid,
            "slippage_cost_diagnostic_embedded": self.slippage_diagnostic,
            "held_funding_event_count": sum(len(t["funding_events"]) for t in self.trade_rows),
            "trade_count": len(self.trade_rows), "busy_rejections": self.busy_count,
            "cap_breach_count": len(self.cap_breaches), "cap_breaches": self.cap_breaches,
            "funding_blocked": bool(self.missing_funding), "missing_funding": self.missing_funding,
            "trades": self.trade_rows,
            "versions": list(self.version_outcomes.values()),
            "events": self.event_rows, "mtm": self.mtm_rows,
        }


def validate_scenario_matrix(results: list[dict[str, Any]]) -> None:
    if len(results) != 18:
        raise AssertionError(f"expected 18 frozen scenarios, got {len(results)}")
    if len({r["scenario_id"] for r in results}) != 18:
        raise AssertionError("scenario ids are not unique")
    for r in results:
        if len(r["versions"]) != 12:
            raise AssertionError(f"{r['scenario_id']} lost V2 version dispositions")
        if r["cap_breach_count"]:
            raise AssertionError(f"{r['scenario_id']} breached the 1x marked notional limit")
        if r["funding_blocked"]:
            raise AssertionError(f"{r['scenario_id']} has missing funding/mark evidence")
        if len(r["mtm"]) != 1899:
            raise AssertionError(f"{r['scenario_id']} lacks full 5m close equity path")
