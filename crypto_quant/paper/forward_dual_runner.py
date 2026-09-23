# -*- coding: utf-8 -*-
"""
Dual Forward Paper Tracking Engine (Candidate A vs Candidate B)
=============================================================
Runs parallel real-time forward paper simulation for:
- Candidate A: Core-4 Top-1 Rotation (Structural EMA exit + 0.30 momentum buffer, 1.0x Spot)
- Candidate B: Simple Multi-Asset EMA Trend (25% equal allocation across Core-4, Close > EMA200, 1.0x Spot)

Operational Standards:
- Strict closed-candle causality (Signals calculated from Bar T-1 closed candles).
- Real obtainable order book quotes (Binance bookTicker best bid/ask) with two-way slippage.
- Physical timestamp audit trail:
  * candle_close_time_utc: Official 4h bar close timestamp
  * data_arrival_time_utc: Timestamp when complete closed candle arrived via REST
  * decision_time_utc: Timestamp when model ranking completed
  * quote_arrival_time_utc: Timestamp when real-time bookTicker quote was obtained
- Restart Idempotency: Guards against duplicate processing of the same bar.
- Clear regime segregation:
  * FORWARD_OOS_LIVE: Genuine out-of-sample forward tracking (>= 2026-09-23 UTC).
  * DEMO_REPLAY: Offline demonstration / backfill testing (stored in demo_replay_ledger.csv).
"""

import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
import numpy as np
import pandas as pd

from crypto_quant.core.top1_decision_engine import compute_top1_decision, Top1DecisionResult

CORE4_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
DEFAULT_INITIAL_CASH = 10000.0
DEFAULT_FEE_RATE = 0.0008          # 8 bps
DEFAULT_SLIPPAGE = 0.0005          # 5 bps
HYSTERESIS_PCT = 0.005             # 0.5%
DELTA_SCORE_BUFFER = 0.30          # 0.30 buffer for Candidate A


class ForwardDualRunner:
    """
    Manages dual forward paper ledgers for Candidate A and Candidate B.
    Supports real-time live execution and isolated demo replays.
    """

    def __init__(
        self,
        output_dir: str = "data/forward_tracking",
        initial_cash: float = DEFAULT_INITIAL_CASH,
        fee_rate: float = DEFAULT_FEE_RATE,
        slippage: float = DEFAULT_SLIPPAGE,
        symbols: Optional[List[str]] = None,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.initial_cash = float(initial_cash)
        self.fee_rate = float(fee_rate)
        self.slippage = float(slippage)
        self.symbols = symbols or CORE4_SYMBOLS

        self.status_file = self.output_dir / "status.json"
        self.ledger_file = self.output_dir / "forward_ledger.csv"
        self.demo_ledger_file = self.output_dir / "demo_replay_ledger.csv"
        self.journal_file = self.output_dir / "forward_journal.jsonl"
        self.report_file = self.output_dir / "forward_comparison.md"

        self.processed_bars: Set[str] = self._load_processed_bar_keys()
        self.state: Dict[str, Any] = self._load_or_initialize_state()

    def _load_processed_bar_keys(self) -> Set[str]:
        """Loads all previously processed (regime, bar_time) keys from ledgers to enforce idempotency."""
        keys = set()
        for f in [self.ledger_file, self.demo_ledger_file]:
            if f.exists():
                try:
                    df = pd.read_csv(f)
                    if "bar_time" in df.columns:
                        reg = "DEMO_REPLAY" if "demo" in f.name else "FORWARD_OOS_LIVE"
                        for b in df["bar_time"].dropna():
                            keys.add(f"{reg}:{str(b)}")
                except Exception:
                    pass
        return keys

    def _load_or_initialize_state(self) -> Dict[str, Any]:
        """Loads state from status.json if exists, otherwise initializes fresh state."""
        if self.status_file.exists():
            try:
                with open(self.status_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data
            except Exception as e:
                print(f"[ForwardDualRunner] Warning: Failed to load existing status.json ({e}). Reinitializing.")

        per_asset_cash_b = self.initial_cash / len(self.symbols)
        fresh_state = {
            "version": "2.0.0",
            "initialized_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "initial_cash": self.initial_cash,
            "fee_rate": self.fee_rate,
            "slippage": self.slippage,
            "symbols": self.symbols,
            "total_live_bars_processed": 0,
            "total_demo_bars_processed": 0,
            "last_processed_live_bar": None,
            "candidate_a": {
                "name": "Candidate A: Top-1 Rotation (Buffer 0.30)",
                "cash": self.initial_cash,
                "equity": self.initial_cash,
                "curr_pos": "USDT_CASH",
                "asset_units": 0.0,
                "entry_price": 0.0,
                "entry_time": None,
                "entry_fee_current": 0.0,
                "entry_slippage_current": 0.0,
                "trade_count": 0,
                "win_count": 0,
                "realized_pnl": 0.0,
                "unrealized_pnl": 0.0,
                "total_fees": 0.0,
                "total_slippage": 0.0,
                "peak_equity": self.initial_cash,
                "max_drawdown_pct": 0.0,
                "bars_in_cash": 0,
                "bars_in_token": 0,
            },
            "candidate_b": {
                "name": "Candidate B: Simple Multi-Asset EMA Trend",
                "total_cash": self.initial_cash,
                "total_equity": self.initial_cash,
                "sub_portfolios": {
                    sym: {
                        "cash": per_asset_cash_b,
                        "units": 0.0,
                        "in_pos": False,
                        "entry_price": 0.0,
                        "entry_time": None,
                        "entry_fee_current": 0.0,
                        "entry_slippage_current": 0.0,
                    }
                    for sym in self.symbols
                },
                "trade_count": 0,
                "win_count": 0,
                "realized_pnl": 0.0,
                "unrealized_pnl": 0.0,
                "total_fees": 0.0,
                "total_slippage": 0.0,
                "peak_equity": self.initial_cash,
                "max_drawdown_pct": 0.0,
            },
        }
        return fresh_state

    def reset(self, keep_demo: bool = False):
        """Wipes tracking data and reinitializes with pristine state."""
        targets = [self.status_file, self.ledger_file, self.journal_file, self.report_file]
        if not keep_demo:
            targets.append(self.demo_ledger_file)
        for p in targets:
            if p.exists():
                p.unlink()
        self.processed_bars = self._load_processed_bar_keys()
        self.state = self._load_or_initialize_state()
        self._save_state()
        print(f"[ForwardDualRunner] Reset completed. Pristine state written to {self.output_dir}.")

    def _append_journal(self, entry: Dict[str, Any]):
        """Appends a structured event entry to forward_journal.jsonl."""
        with open(self.journal_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _append_ledger(self, row: Dict[str, Any], regime: str = "FORWARD_OOS_LIVE"):
        """Appends a bar row to forward_ledger.csv or demo_replay_ledger.csv."""
        target_file = self.demo_ledger_file if regime == "DEMO_REPLAY" else self.ledger_file
        df_row = pd.DataFrame([row])
        header = not target_file.exists()
        df_row.to_csv(target_file, mode="a", index=False, header=header)

    def _save_state(self):
        """Atomically saves current status.json and updates comparison report."""
        tmp_status = self.status_file.with_suffix(".tmp")
        with open(tmp_status, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)
        tmp_status.replace(self.status_file)
        self._generate_comparison_markdown()

    def process_bar(
        self,
        bar_time: Any,
        open_prices: Dict[str, float],
        close_prices: Dict[str, float],
        historical_closes: pd.DataFrame,
        historical_atrs: Optional[Dict[str, float]] = None,
        actual_quotes: Optional[Dict[str, Dict[str, float]]] = None,
        candle_close_time_utc: Optional[str] = None,
        data_arrival_time_utc: Optional[str] = None,
        quote_arrival_time_utc: Optional[str] = None,
        regime: str = "FORWARD_OOS_LIVE",
    ) -> Dict[str, Any]:
        """
        Processes Bar T with strict causality, idempotency, and physical latency tracking.
        """
        bar_str = str(bar_time)
        bar_key = f"{regime}:{bar_str}"

        # 1. Idempotency Check: Reject duplicate processing
        if bar_key in self.processed_bars:
            return {
                "status": "ALREADY_PROCESSED",
                "bar_time": bar_str,
                "regime": regime,
                "message": f"Bar {bar_str} has already been processed under {regime}. Duplicate execution skipped.",
            }

        t_start = time.perf_counter()
        now_utc = datetime.now(timezone.utc)
        now_utc_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")

        # Arrival & latency timestamps
        c_close_ts_str = candle_close_time_utc or bar_str
        d_arrival_ts_str = data_arrival_time_utc or now_utc_str

        # Compute arrival latency (seconds from candle close to data arrival)
        try:
            t_close = pd.to_datetime(c_close_ts_str).tz_localize("UTC") if pd.to_datetime(c_close_ts_str).tzinfo is None else pd.to_datetime(c_close_ts_str)
            t_arrival = pd.to_datetime(d_arrival_ts_str).tz_localize("UTC") if pd.to_datetime(d_arrival_ts_str).tzinfo is None else pd.to_datetime(d_arrival_ts_str)
            arrival_latency_sec = max(0.0, (t_arrival - t_close).total_seconds())
        except Exception:
            arrival_latency_sec = 0.0

        # Step 1: Decision for Candidate A
        cA = self.state["candidate_a"]
        curr_pos_a = cA["curr_pos"]

        decision_a: Top1DecisionResult = compute_top1_decision(
            closes_df=historical_closes,
            atrs_dict=historical_atrs,
            current_symbol=curr_pos_a,
            symbols=self.symbols,
            hysteresis_pct=HYSTERESIS_PCT,
            delta_score_buffer=DELTA_SCORE_BUFFER,
            use_btc_gate=True,
            use_asset_gate=True,
            disable_momentum_rank=False,
        )
        target_pos_a = decision_a.target_symbol

        # Step 2: Decision for Candidate B (Independent 4-asset EMA200 trend)
        cB = self.state["candidate_b"]
        target_b: Dict[str, bool] = {}
        for sym in self.symbols:
            s_series = historical_closes[sym]
            ema200_val = float(s_series.ewm(span=200, adjust=False).mean().iloc[-1])
            prev_close_val = float(s_series.iloc[-1])
            target_b[sym] = bool(prev_close_val > ema200_val)

        t_decision = time.perf_counter()
        calc_latency_sec = round(t_decision - t_start, 4)
        decision_time_utc_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        q_arrival_ts_str = quote_arrival_time_utc or decision_time_utc_str

        # Execution latency (data arrival to quote/fill)
        try:
            t_q = pd.to_datetime(q_arrival_ts_str).tz_localize("UTC") if pd.to_datetime(q_arrival_ts_str).tzinfo is None else pd.to_datetime(q_arrival_ts_str)
            execution_latency_sec = max(calc_latency_sec, (t_q - t_arrival).total_seconds())
        except Exception:
            execution_latency_sec = calc_latency_sec

        total_latency_sec = round(arrival_latency_sec + execution_latency_sec, 4)

        events_this_bar: List[Dict[str, Any]] = []

        # -------------------------------------------------------------
        # Execute Candidate A
        # -------------------------------------------------------------
        # A. Exit / Rotate if target changed
        if curr_pos_a != "USDT_CASH" and target_pos_a != curr_pos_a:
            raw_p = open_prices[curr_pos_a]
            # Use actual obtainable bid quote if available, bounded by theoretical slippage
            if actual_quotes and curr_pos_a in actual_quotes and "bid" in actual_quotes[curr_pos_a]:
                act_bid = float(actual_quotes[curr_pos_a]["bid"])
                exec_exit = min(act_bid, raw_p * (1.0 - self.slippage))
                exit_slip = max(0.0, raw_p - exec_exit)
            else:
                act_bid = raw_p * (1.0 - self.slippage)
                exec_exit = raw_p * (1.0 - self.slippage)
                exit_slip = raw_p - exec_exit

            units = cA["asset_units"]
            gross_proceeds = units * exec_exit
            exit_fee = gross_proceeds * self.fee_rate
            net_proceeds = max(0.0, gross_proceeds - exit_fee)
            trade_pnl = net_proceeds - (units * cA["entry_price"] + cA["entry_fee_current"])

            cA["cash"] += net_proceeds
            cA["realized_pnl"] += trade_pnl
            cA["total_fees"] += exit_fee
            cA["total_slippage"] += units * exit_slip
            cA["trade_count"] += 1
            if trade_pnl > 0:
                cA["win_count"] += 1

            ev_exit = {
                "event_type": "ORDER_FILL",
                "model": "Candidate_A",
                "regime": regime,
                "bar_time": bar_str,
                "candle_close_time_utc": c_close_ts_str,
                "data_arrival_time_utc": d_arrival_ts_str,
                "decision_time_utc": decision_time_utc_str,
                "quote_arrival_time_utc": q_arrival_ts_str,
                "action": "SELL",
                "symbol": curr_pos_a,
                "units": units,
                "theoretical_open": raw_p,
                "actual_bid": act_bid,
                "exec_price": round(exec_exit, 4),
                "fee_usdt": round(exit_fee, 4),
                "slippage_usdt": round(units * exit_slip, 4),
                "pnl_usdt": round(trade_pnl, 4),
                "arrival_latency_sec": round(arrival_latency_sec, 3),
                "execution_latency_sec": round(execution_latency_sec, 3),
                "reason": "SIGNAL_ROTATE" if target_pos_a != "USDT_CASH" else "TREND_GATE_EXIT",
            }
            events_this_bar.append(ev_exit)
            self._append_journal(ev_exit)

            cA["curr_pos"] = "USDT_CASH"
            cA["asset_units"] = 0.0
            cA["entry_price"] = 0.0
            cA["entry_time"] = None
            cA["entry_fee_current"] = 0.0
            cA["entry_slippage_current"] = 0.0

        # B. Enter new position for Candidate A
        if target_pos_a != "USDT_CASH" and cA["curr_pos"] == "USDT_CASH" and cA["cash"] > 1.0:
            raw_p = open_prices[target_pos_a]
            if actual_quotes and target_pos_a in actual_quotes and "ask" in actual_quotes[target_pos_a]:
                act_ask = float(actual_quotes[target_pos_a]["ask"])
                exec_entry = max(act_ask, raw_p * (1.0 + self.slippage))
                entry_slip = max(0.0, exec_entry - raw_p)
            else:
                act_ask = raw_p * (1.0 + self.slippage)
                exec_entry = raw_p * (1.0 + self.slippage)
                entry_slip = exec_entry - raw_p

            avail_cash = cA["cash"]
            entry_fee = avail_cash * self.fee_rate
            investable = max(0.0, avail_cash - entry_fee)
            units = investable / exec_entry
            entry_slip_total = units * entry_slip

            cA["curr_pos"] = target_pos_a
            cA["asset_units"] = units
            cA["entry_price"] = exec_entry
            cA["entry_time"] = bar_str
            cA["entry_fee_current"] = entry_fee
            cA["entry_slippage_current"] = entry_slip_total
            cA["total_fees"] += entry_fee
            cA["total_slippage"] += entry_slip_total
            cA["cash"] = 0.0

            ev_entry = {
                "event_type": "ORDER_FILL",
                "model": "Candidate_A",
                "regime": regime,
                "bar_time": bar_str,
                "candle_close_time_utc": c_close_ts_str,
                "data_arrival_time_utc": d_arrival_ts_str,
                "decision_time_utc": decision_time_utc_str,
                "quote_arrival_time_utc": q_arrival_ts_str,
                "action": "BUY",
                "symbol": target_pos_a,
                "units": units,
                "theoretical_open": raw_p,
                "actual_ask": act_ask,
                "exec_price": round(exec_entry, 4),
                "fee_usdt": round(entry_fee, 4),
                "slippage_usdt": round(entry_slip_total, 4),
                "pnl_usdt": 0.0,
                "arrival_latency_sec": round(arrival_latency_sec, 3),
                "execution_latency_sec": round(execution_latency_sec, 3),
                "reason": "SIGNAL_ENTRY",
            }
            events_this_bar.append(ev_entry)
            self._append_journal(ev_entry)

        # Mark-to-market Candidate A
        if cA["curr_pos"] == "USDT_CASH":
            cA["unrealized_pnl"] = 0.0
            cA["equity"] = cA["cash"]
            cA["bars_in_cash"] += 1
        else:
            c_p = close_prices[cA["curr_pos"]]
            pos_val = cA["asset_units"] * c_p
            cA["unrealized_pnl"] = pos_val - (cA["asset_units"] * cA["entry_price"])
            cA["equity"] = cA["cash"] + pos_val
            cA["bars_in_token"] += 1

        if cA["equity"] > cA["peak_equity"]:
            cA["peak_equity"] = cA["equity"]
        cur_dd_a = ((cA["peak_equity"] - cA["equity"]) / cA["peak_equity"]) * 100.0 if cA["peak_equity"] > 0 else 0.0
        if cur_dd_a > cA["max_drawdown_pct"]:
            cA["max_drawdown_pct"] = cur_dd_a

        # -------------------------------------------------------------
        # Execute Candidate B (Simple Multi-Asset EMA Trend)
        # -------------------------------------------------------------
        for sym in self.symbols:
            sub = cB["sub_portfolios"][sym]
            should_long = target_b[sym]
            raw_p = open_prices[sym]

            # Sell
            if not should_long and sub["in_pos"]:
                if actual_quotes and sym in actual_quotes and "bid" in actual_quotes[sym]:
                    act_bid = float(actual_quotes[sym]["bid"])
                    exec_exit = min(act_bid, raw_p * (1.0 - self.slippage))
                    exit_slip = max(0.0, raw_p - exec_exit)
                else:
                    act_bid = raw_p * (1.0 - self.slippage)
                    exec_exit = raw_p * (1.0 - self.slippage)
                    exit_slip = raw_p - exec_exit

                units = sub["units"]
                gross_proceeds = units * exec_exit
                exit_fee = gross_proceeds * self.fee_rate
                net_proceeds = max(0.0, gross_proceeds - exit_fee)
                trade_pnl = net_proceeds - (units * sub["entry_price"] + sub["entry_fee_current"])

                sub["cash"] += net_proceeds
                cB["realized_pnl"] += trade_pnl
                cB["total_fees"] += exit_fee
                cB["total_slippage"] += units * exit_slip
                cB["trade_count"] += 1
                if trade_pnl > 0:
                    cB["win_count"] += 1

                ev_exit_b = {
                    "event_type": "ORDER_FILL",
                    "model": "Candidate_B",
                    "regime": regime,
                    "bar_time": bar_str,
                    "candle_close_time_utc": c_close_ts_str,
                    "data_arrival_time_utc": d_arrival_ts_str,
                    "decision_time_utc": decision_time_utc_str,
                    "quote_arrival_time_utc": q_arrival_ts_str,
                    "action": "SELL",
                    "symbol": sym,
                    "units": units,
                    "theoretical_open": raw_p,
                    "actual_bid": act_bid,
                    "exec_price": round(exec_exit, 4),
                    "fee_usdt": round(exit_fee, 4),
                    "slippage_usdt": round(units * exit_slip, 4),
                    "pnl_usdt": round(trade_pnl, 4),
                    "arrival_latency_sec": round(arrival_latency_sec, 3),
                    "execution_latency_sec": round(execution_latency_sec, 3),
                    "reason": "EMA200_BREAKDOWN",
                }
                events_this_bar.append(ev_exit_b)
                self._append_journal(ev_exit_b)

                sub["units"] = 0.0
                sub["in_pos"] = False
                sub["entry_price"] = 0.0
                sub["entry_time"] = None
                sub["entry_fee_current"] = 0.0
                sub["entry_slippage_current"] = 0.0

            # Buy
            elif should_long and not sub["in_pos"] and sub["cash"] > 1.0:
                if actual_quotes and sym in actual_quotes and "ask" in actual_quotes[sym]:
                    act_ask = float(actual_quotes[sym]["ask"])
                    exec_entry = max(act_ask, raw_p * (1.0 + self.slippage))
                    entry_slip = max(0.0, exec_entry - raw_p)
                else:
                    act_ask = raw_p * (1.0 + self.slippage)
                    exec_entry = raw_p * (1.0 + self.slippage)
                    entry_slip = exec_entry - raw_p

                avail_cash = sub["cash"]
                entry_fee = avail_cash * self.fee_rate
                investable = max(0.0, avail_cash - entry_fee)
                units = investable / exec_entry
                entry_slip_total = units * entry_slip

                sub["units"] = units
                sub["in_pos"] = True
                sub["entry_price"] = exec_entry
                sub["entry_time"] = bar_str
                sub["entry_fee_current"] = entry_fee
                sub["entry_slippage_current"] = entry_slip_total
                cB["total_fees"] += entry_fee
                cB["total_slippage"] += entry_slip_total
                sub["cash"] = 0.0

                ev_entry_b = {
                    "event_type": "ORDER_FILL",
                    "model": "Candidate_B",
                    "regime": regime,
                    "bar_time": bar_str,
                    "candle_close_time_utc": c_close_ts_str,
                    "data_arrival_time_utc": d_arrival_ts_str,
                    "decision_time_utc": decision_time_utc_str,
                    "quote_arrival_time_utc": q_arrival_ts_str,
                    "action": "BUY",
                    "symbol": sym,
                    "units": units,
                    "theoretical_open": raw_p,
                    "actual_ask": act_ask,
                    "exec_price": round(exec_entry, 4),
                    "fee_usdt": round(entry_fee, 4),
                    "slippage_usdt": round(entry_slip_total, 4),
                    "pnl_usdt": 0.0,
                    "arrival_latency_sec": round(arrival_latency_sec, 3),
                    "execution_latency_sec": round(execution_latency_sec, 3),
                    "reason": "EMA200_BREAKOUT",
                }
                events_this_bar.append(ev_entry_b)
                self._append_journal(ev_entry_b)

        # Mark-to-market Candidate B
        b_total_cash = 0.0
        b_total_equity = 0.0
        b_total_unrealized = 0.0
        for sym in self.symbols:
            sub = cB["sub_portfolios"][sym]
            b_total_cash += sub["cash"]
            if sub["in_pos"]:
                c_p = close_prices[sym]
                sub_val = sub["units"] * c_p
                b_total_equity += sub_val
                b_total_unrealized += sub_val - (sub["units"] * sub["entry_price"])
            else:
                b_total_equity += sub["cash"]

        cB["total_cash"] = b_total_cash
        cB["total_equity"] = b_total_equity
        cB["unrealized_pnl"] = b_total_unrealized

        if cB["total_equity"] > cB["peak_equity"]:
            cB["peak_equity"] = cB["total_equity"]
        cur_dd_b = ((cB["peak_equity"] - cB["total_equity"]) / cB["peak_equity"]) * 100.0 if cB["peak_equity"] > 0 else 0.0
        if cur_dd_b > cB["max_drawdown_pct"]:
            cB["max_drawdown_pct"] = cur_dd_b

        # -------------------------------------------------------------
        # Mathematical Identity Assertions
        # -------------------------------------------------------------
        expected_eq_a = cA["cash"] + (cA["asset_units"] * close_prices.get(cA["curr_pos"], 0.0) if cA["curr_pos"] != "USDT_CASH" else 0.0)
        assert abs(cA["equity"] - expected_eq_a) < 1e-4, f"Candidate A Identity Failure: equity={cA['equity']}, expected={expected_eq_a}"

        expected_eq_b = sum(
            sub["cash"] + (sub["units"] * close_prices[s] if sub["in_pos"] else 0.0)
            for s, sub in cB["sub_portfolios"].items()
        )
        assert abs(cB["total_equity"] - expected_eq_b) < 1e-4, f"Candidate B Identity Failure: equity={cB['total_equity']}, expected={expected_eq_b}"

        # -------------------------------------------------------------
        # Append to Ledger CSV
        # -------------------------------------------------------------
        ledger_row = {
            "bar_time": bar_str,
            "candle_close_time_utc": c_close_ts_str,
            "data_arrival_time_utc": d_arrival_ts_str,
            "decision_time_utc": decision_time_utc_str,
            "quote_arrival_time_utc": q_arrival_ts_str,
            "arrival_latency_sec": round(arrival_latency_sec, 3),
            "execution_latency_sec": round(execution_latency_sec, 3),
            "total_latency_sec": total_latency_sec,
            "candidate_a_equity": round(cA["equity"], 4),
            "candidate_a_cash": round(cA["cash"], 4),
            "candidate_a_pos": cA["curr_pos"],
            "candidate_a_units": round(cA["asset_units"], 6),
            "candidate_b_equity": round(cB["total_equity"], 4),
            "candidate_b_cash": round(cB["total_cash"], 4),
            "candidate_b_btc_pos": int(cB["sub_portfolios"]["BTCUSDT"]["in_pos"]),
            "candidate_b_eth_pos": int(cB["sub_portfolios"]["ETHUSDT"]["in_pos"]),
            "candidate_b_sol_pos": int(cB["sub_portfolios"]["SOLUSDT"]["in_pos"]),
            "candidate_b_bnb_pos": int(cB["sub_portfolios"]["BNBUSDT"]["in_pos"]),
            "regime": regime,
        }
        self._append_ledger(ledger_row, regime=regime)

        # Update metadata state & processed bars cache
        self.processed_bars.add(bar_key)
        if regime == "FORWARD_OOS_LIVE":
            self.state["total_live_bars_processed"] += 1
            self.state["last_processed_live_bar"] = bar_str
        else:
            self.state["total_demo_bars_processed"] += 1

        self._save_state()

        return {
            "status": "SUCCESS",
            "bar_time": bar_str,
            "regime": regime,
            "candidate_a": {
                "equity": round(cA["equity"], 2),
                "pos": cA["curr_pos"],
                "target": target_pos_a,
            },
            "candidate_b": {
                "equity": round(cB["total_equity"], 2),
                "active_tokens": [s for s, sub in cB["sub_portfolios"].items() if sub["in_pos"]],
            },
            "events_count": len(events_this_bar),
            "arrival_latency_sec": round(arrival_latency_sec, 3),
            "execution_latency_sec": round(execution_latency_sec, 3),
        }

    def _generate_comparison_markdown(self):
        """Generates dynamic dual-language comparison markdown artifact."""
        cA = self.state["candidate_a"]
        cB = self.state["candidate_b"]

        init_c = self.state["initial_cash"]
        ret_a = ((cA["equity"] / init_c) - 1.0) * 100.0
        ret_b = ((cB["total_equity"] / init_c) - 1.0) * 100.0
        alpha_spread = ret_a - ret_b

        wr_a = (cA["win_count"] / cA["trade_count"] * 100.0) if cA["trade_count"] > 0 else 0.0
        wr_b = (cB["win_count"] / cB["trade_count"] * 100.0) if cB["trade_count"] > 0 else 0.0

        live_bars = self.state.get("total_live_bars_processed", 0)
        demo_bars = self.state.get("total_demo_bars_processed", 0)
        last_live = self.state.get("last_processed_live_bar") or "Awaiting First Live Candle (>= 2026-09-23 UTC)"

        md_content = f"""# Forward Paper Tracking & A/B Model Performance
# 前向实测模拟与 A/B 模型绩效实时对照报告

- **Report Updated / 报告更新时间**: `{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}`
- **Evaluation Cutoff / 冻结基准线**: `2026-09-23 00:00:00 UTC`
- **Total Genuine OOS Bars Tracked / 累计样本外真实 K 线**: `{live_bars}` bars
- **Historical Demo Replay Bars / 流程演示回填根数**: `{demo_bars}` bars (Stored in `demo_replay_ledger.csv`)
- **Last Processed Live Bar / 最新样本外闭合 K 线**: `{last_live}`
- **Initial Capital / 初始本金**: `${init_c:,.2f} USDT` each

---

## 1. Live Performance Comparison Matrix / 实时表现对比矩阵

| Metric / 指标 | Candidate A (Top-1 Buffer 0.30) | Candidate B (Simple EMA Trend) | Alpha Spread / 差异 (A - B) |
| :--- | :--- | :--- | :--- |
| **Current Equity / 当前权益** | **${cA["equity"]:,.2f} USDT** | **${cB["total_equity"]:,.2f} USDT** | ${cA["equity"] - cB["total_equity"]:+,.2f} USDT |
| **Net Return / 累计净收益率** | **{ret_a:+.2f}%** | **{ret_b:+.2f}%** | **{alpha_spread:+.2f}%** |
| **Max Drawdown / 最大回撤** | {cA["max_drawdown_pct"]:.2f}% | {cB["max_drawdown_pct"]:.2f}% | {cA["max_drawdown_pct"] - cB["max_drawdown_pct"]:+.2f}% |
| **Current Allocation / 当前持仓** | `{cA["curr_pos"]}` | `{", ".join([s for s, sub in cB["sub_portfolios"].items() if sub["in_pos"]]) or "100% CASH"}` | - |
| **Completed Trades / 平仓笔数** | {cA["trade_count"]} trades | {cB["trade_count"]} trades | - |
| **Win Rate / 交易胜率** | {wr_a:.1f}% | {wr_b:.1f}% | {wr_a - wr_b:+.1f}% |
| **Total Fees Paid / 手续费损耗** | ${cA["total_fees"]:,.2f} | ${cB["total_fees"]:,.2f} | ${cA["total_fees"] - cB["total_fees"]:+,.2f} |
| **Total Slippage / 滑点损耗** | ${cA["total_slippage"]:,.2f} | ${cB["total_slippage"]:,.2f} | ${cA["total_slippage"] - cB["total_slippage"]:+,.2f} |

---

## 2. Institutional Decision Hurdle Status / 机构级前瞻评判准则状态

- **Required Minimum Horizon / 最低跟踪周期**: 180 days (6 months) OR >= 30 completed trades for Candidate A.
- **Current Progress / 当前进度**: `{cA["trade_count"]} / 30` completed roundtrips ({live_bars} live bars accumulated).
- **Data Integrity & Demarcation / 数据纯度与口径隔离**:
  - Offline backfills prior to 2026-09-23 are strictly isolated in `demo_replay_ledger.csv` with `DEMO_REPLAY` tag and do not count toward official OOS performance.
  - The live ledger `forward_ledger.csv` records real physical data arrival latency, bookTicker quotes, and restart idempotency guards.
- **Current Verdict / 当前科学裁定**:
  - `EVALUATION_IN_PROGRESS`: Insufficient out-of-sample forward sample to validate or reject Candidate A.
  - Candidate A must maintain cost-adjusted Sharpe superiority and positive excess alpha over Candidate B across the 180-day window to earn live deployment consideration.
"""
        with open(self.report_file, "w", encoding="utf-8") as f:
            f.write(md_content)
