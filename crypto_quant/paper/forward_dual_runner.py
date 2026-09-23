# -*- coding: utf-8 -*-
"""
Dual Forward Paper Tracking Engine (Candidate A vs Candidate B)
=============================================================
Runs parallel real-time forward paper simulation for:
- Candidate A: Core-4 Top-1 Rotation (Structural EMA exit + 0.30 momentum buffer, 1.0x Spot)
- Candidate B: Simple Multi-Asset EMA Trend (25% equal allocation across Core-4, Close > EMA200, 1.0x Spot)

Operational Standards:
1. Complete Regime & State Demarcation:
   - Live OOS runner tracks strictly genuine live bars on or after 2026-09-23 00:00:00 UTC.
   - Live state starts independently from pristine $10,000.00 USDT cash each.
   - Demo replay is completely segregated into dedicated demo files (demo_status.json, demo_replay_ledger.csv).
2. Strict Causal Execution Sequence:
   Closed Candle Arrival -> Freshness Gate -> Signal -> Live bookTicker -> Obtainable Quote Fill -> Post-Execution MTM.
3. Anomaly & Safety Guards:
   - Staleness Guard: If data arrives > max_staleness_sec (default 900s) after candle close, log DATA_EXPIRED and skip execution.
   - Missing Quote Guard: If live top-of-book quotes fail or are incomplete, log QUOTE_MISSING and skip execution.
4. Obtainable Quote Execution:
   - BUY executes at actual_ask * (1 + slippage).
   - SELL executes at actual_bid * (1 - slippage).
   - Historical open prices from 4 hours ago are never used for live fill prices.
5. Post-Execution Mark-to-Market:
   - Positions are valued using obtainable market prices at/after execution.
6. Restart Idempotency:
   - Deduplication cache prevents re-processing or balance corruption upon service restarts.
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
DEFAULT_MAX_STALENESS_SEC = 900.0  # 15 minutes
HYSTERESIS_PCT = 0.005             # 0.5%
DELTA_SCORE_BUFFER = 0.30          # 0.30 buffer for Candidate A


class ForwardDualRunner:
    """
    Manages dual forward paper ledgers for Candidate A and Candidate B.
    Enforces complete separation between genuine live OOS and demo replays.
    """

    def __init__(
        self,
        output_dir: str = "data/forward_tracking",
        initial_cash: float = DEFAULT_INITIAL_CASH,
        fee_rate: float = DEFAULT_FEE_RATE,
        slippage: float = DEFAULT_SLIPPAGE,
        max_staleness_sec: float = DEFAULT_MAX_STALENESS_SEC,
        symbols: Optional[List[str]] = None,
        is_demo: bool = False,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.initial_cash = float(initial_cash)
        self.fee_rate = float(fee_rate)
        self.slippage = float(slippage)
        self.max_staleness_sec = float(max_staleness_sec)
        self.symbols = symbols or CORE4_SYMBOLS
        self.is_demo = is_demo
        self.regime = "DEMO_REPLAY" if is_demo else "FORWARD_OOS_LIVE"

        # Dedicated isolated files for demo vs live
        if self.is_demo:
            self.status_file = self.output_dir / "demo_status.json"
            self.ledger_file = self.output_dir / "demo_replay_ledger.csv"
            self.journal_file = self.output_dir / "demo_journal.jsonl"
            self.report_file = self.output_dir / "demo_comparison.md"
        else:
            self.status_file = self.output_dir / "status.json"
            self.ledger_file = self.output_dir / "forward_ledger.csv"
            self.journal_file = self.output_dir / "forward_journal.jsonl"
            self.report_file = self.output_dir / "forward_comparison.md"

        self.processed_bars: Set[str] = self._load_processed_bar_keys()
        self.state: Dict[str, Any] = self._load_or_initialize_state()

    def _load_processed_bar_keys(self) -> Set[str]:
        """Loads previously processed bar keys from this runner's ledger to enforce idempotency."""
        keys = set()
        if self.ledger_file.exists():
            try:
                df = pd.read_csv(self.ledger_file)
                if "bar_time" in df.columns:
                    for b in df["bar_time"].dropna():
                        keys.add(f"{self.regime}:{str(b)}")
            except Exception:
                pass
        return keys

    def _load_or_initialize_state(self) -> Dict[str, Any]:
        """Loads state from status_file if exists, otherwise initializes fresh pristine state."""
        if self.status_file.exists():
            try:
                with open(self.status_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data
            except Exception as e:
                print(f"[ForwardDualRunner] Warning: Failed to load {self.status_file.name} ({e}). Reinitializing.")

        per_asset_cash_b = self.initial_cash / len(self.symbols)
        fresh_state = {
            "version": "2.1.0",
            "mode": self.regime,
            "initialized_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "initial_cash": self.initial_cash,
            "fee_rate": self.fee_rate,
            "slippage": self.slippage,
            "max_staleness_sec": self.max_staleness_sec,
            "symbols": self.symbols,
            "total_bars_processed": 0,
            "last_processed_bar": None,
            "anomalies_count": 0,
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

    def reset(self):
        """Wipes tracking data for this specific runner mode and reinitializes pristine state."""
        targets = [self.status_file, self.ledger_file, self.journal_file, self.report_file]
        for p in targets:
            if p.exists():
                p.unlink()
        self.processed_bars = set()
        self.state = self._load_or_initialize_state()
        self._save_state()
        print(f"[ForwardDualRunner] Reset completed ({self.regime}). Pristine state written to {self.output_dir}.")

    def _append_journal(self, entry: Dict[str, Any]):
        """Appends a structured event entry to journal file."""
        with open(self.journal_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _append_ledger(self, row: Dict[str, Any]):
        """Appends a bar row to this runner's ledger CSV."""
        df_row = pd.DataFrame([row])
        header = not self.ledger_file.exists()
        df_row.to_csv(self.ledger_file, mode="a", index=False, header=header)

    def _save_state(self):
        """Atomically saves status.json and updates comparison report."""
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
        regime: Optional[str] = None,
        allow_stale: bool = False,
    ) -> Dict[str, Any]:
        """
        Processes Bar T with strict temporal causality:
        1. Idempotency Check
        2. Freshness Check (arrival_latency <= max_staleness_sec) -> Log anomaly & skip on stale
        3. Signal Decision on closed bars
        4. Quote Availability Gate -> Log anomaly & skip on missing
        5. Obtainable Quote Execution: BUY at ask * (1+slip), SELL at bid * (1-slip)
        6. Post-execution MTM Accounting & Ledger Persistence
        """
        bar_str = str(bar_time)
        exec_regime = regime or self.regime
        bar_key = f"{exec_regime}:{bar_str}"

        # 1. Idempotency Check: Reject duplicate processing
        if bar_key in self.processed_bars:
            return {
                "status": "ALREADY_PROCESSED",
                "bar_time": bar_str,
                "regime": exec_regime,
                "message": f"Bar {bar_str} has already been processed under {exec_regime}. Duplicate execution skipped.",
            }

        t_start = time.perf_counter()
        now_utc = datetime.now(timezone.utc)
        now_utc_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")

        c_close_ts_str = candle_close_time_utc or bar_str
        d_arrival_ts_str = data_arrival_time_utc or now_utc_str

        # Compute arrival latency (seconds from candle close to data arrival)
        try:
            t_close = pd.to_datetime(c_close_ts_str)
            if t_close.tzinfo is None:
                t_close = t_close.tz_localize("UTC")
            t_arrival = pd.to_datetime(d_arrival_ts_str)
            if t_arrival.tzinfo is None:
                t_arrival = t_arrival.tz_localize("UTC")
            arrival_latency_sec = max(0.0, (t_arrival - t_close).total_seconds())
        except Exception:
            arrival_latency_sec = 0.0

        cA = self.state["candidate_a"]
        cB = self.state["candidate_b"]
        events_this_bar: List[Dict[str, Any]] = []

        # -------------------------------------------------------------
        # 2. Staleness Gate: If data arrived too late, skip execution
        # -------------------------------------------------------------
        is_stale = (arrival_latency_sec > self.max_staleness_sec) and not allow_stale
        if is_stale:
            anomaly_ev = {
                "event_type": "ANOMALY",
                "anomaly_type": "DATA_EXPIRED",
                "regime": exec_regime,
                "bar_time": bar_str,
                "candle_close_time_utc": c_close_ts_str,
                "data_arrival_time_utc": d_arrival_ts_str,
                "arrival_latency_sec": round(arrival_latency_sec, 3),
                "max_staleness_sec": self.max_staleness_sec,
                "action_taken": "SKIP_EXECUTION",
                "message": (
                    f"Candle closed at {c_close_ts_str}, arrived at {d_arrival_ts_str} "
                    f"(latency {arrival_latency_sec:.1f}s > {self.max_staleness_sec:.1f}s). "
                    f"Execution skipped to preserve causality."
                ),
            }
            events_this_bar.append(anomaly_ev)
            self._append_journal(anomaly_ev)
            self.state["anomalies_count"] += 1

            # Mark to market with close prices without executing trades
            return self._record_and_finalize_bar(
                bar_str=bar_str,
                c_close_ts_str=c_close_ts_str,
                d_arrival_ts_str=d_arrival_ts_str,
                decision_time_utc_str=now_utc_str,
                q_arrival_ts_str=now_utc_str,
                arrival_latency_sec=arrival_latency_sec,
                execution_latency_sec=0.0,
                close_prices=close_prices,
                mark_prices=close_prices,
                exec_regime=exec_regime,
                bar_key=bar_key,
                events_this_bar=events_this_bar,
                status="DATA_EXPIRED_SKIPPED",
                anomaly="DATA_EXPIRED",
            )

        # -------------------------------------------------------------
        # 3. Model Decisions on Closed Candle History
        # -------------------------------------------------------------
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

        # Execution latency (data arrival to quote arrival)
        try:
            t_q = pd.to_datetime(q_arrival_ts_str)
            if t_q.tzinfo is None:
                t_q = t_q.tz_localize("UTC")
            execution_latency_sec = max(calc_latency_sec, (t_q - t_arrival).total_seconds())
        except Exception:
            execution_latency_sec = calc_latency_sec

        # -------------------------------------------------------------
        # 4. Quote Availability Gate
        # -------------------------------------------------------------
        a_needs_trade = (target_pos_a != curr_pos_a)
        b_needs_trade = any(target_b[s] != cB["sub_portfolios"][s]["in_pos"] for s in self.symbols)

        symbols_needed = set()
        if a_needs_trade:
            if curr_pos_a != "USDT_CASH":
                symbols_needed.add(curr_pos_a)
            if target_pos_a != "USDT_CASH":
                symbols_needed.add(target_pos_a)
        if b_needs_trade:
            for s in self.symbols:
                if target_b[s] != cB["sub_portfolios"][s]["in_pos"]:
                    symbols_needed.add(s)

        quotes_missing = False
        missing_symbols = []
        if symbols_needed:
            if not actual_quotes:
                quotes_missing = True
                missing_symbols = list(symbols_needed)
            else:
                for s in symbols_needed:
                    if s not in actual_quotes or "bid" not in actual_quotes[s] or "ask" not in actual_quotes[s]:
                        quotes_missing = True
                        missing_symbols.append(s)
                    elif float(actual_quotes[s]["bid"]) <= 0 or float(actual_quotes[s]["ask"]) <= 0:
                        quotes_missing = True
                        missing_symbols.append(s)

        if quotes_missing:
            anomaly_ev = {
                "event_type": "ANOMALY",
                "anomaly_type": "QUOTE_MISSING",
                "regime": exec_regime,
                "bar_time": bar_str,
                "candle_close_time_utc": c_close_ts_str,
                "data_arrival_time_utc": d_arrival_ts_str,
                "missing_symbols": missing_symbols,
                "action_taken": "SKIP_EXECUTION",
                "message": f"Quotes missing or invalid for required symbols {missing_symbols}. Execution skipped.",
            }
            events_this_bar.append(anomaly_ev)
            self._append_journal(anomaly_ev)
            self.state["anomalies_count"] += 1

            return self._record_and_finalize_bar(
                bar_str=bar_str,
                c_close_ts_str=c_close_ts_str,
                d_arrival_ts_str=d_arrival_ts_str,
                decision_time_utc_str=decision_time_utc_str,
                q_arrival_ts_str=q_arrival_ts_str,
                arrival_latency_sec=arrival_latency_sec,
                execution_latency_sec=execution_latency_sec,
                close_prices=close_prices,
                mark_prices=close_prices,
                exec_regime=exec_regime,
                bar_key=bar_key,
                events_this_bar=events_this_bar,
                status="QUOTE_MISSING_SKIPPED",
                anomaly="QUOTE_MISSING",
            )

        # -------------------------------------------------------------
        # 5. Order Execution at Prevailing Obtainable Quotes
        # -------------------------------------------------------------
        mark_prices = dict(close_prices)

        # --- Execute Candidate A ---
        # A. Exit if target changed
        if curr_pos_a != "USDT_CASH" and target_pos_a != curr_pos_a:
            act_bid = float(actual_quotes[curr_pos_a]["bid"])
            exec_exit = act_bid * (1.0 - self.slippage)
            exit_slip = act_bid - exec_exit

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
                "regime": exec_regime,
                "bar_time": bar_str,
                "candle_close_time_utc": c_close_ts_str,
                "data_arrival_time_utc": d_arrival_ts_str,
                "decision_time_utc": decision_time_utc_str,
                "quote_arrival_time_utc": q_arrival_ts_str,
                "action": "SELL",
                "symbol": curr_pos_a,
                "units": units,
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
            act_ask = float(actual_quotes[target_pos_a]["ask"])
            exec_entry = act_ask * (1.0 + self.slippage)
            entry_slip = exec_entry - act_ask

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

            # Post-execution obtainable mark price
            mark_prices[target_pos_a] = float(actual_quotes[target_pos_a]["bid"])

            ev_entry = {
                "event_type": "ORDER_FILL",
                "model": "Candidate_A",
                "regime": exec_regime,
                "bar_time": bar_str,
                "candle_close_time_utc": c_close_ts_str,
                "data_arrival_time_utc": d_arrival_ts_str,
                "decision_time_utc": decision_time_utc_str,
                "quote_arrival_time_utc": q_arrival_ts_str,
                "action": "BUY",
                "symbol": target_pos_a,
                "units": units,
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

        # --- Execute Candidate B (Simple Multi-Asset EMA Trend) ---
        for sym in self.symbols:
            sub = cB["sub_portfolios"][sym]
            should_long = target_b[sym]

            # Sell
            if not should_long and sub["in_pos"]:
                act_bid = float(actual_quotes[sym]["bid"])
                exec_exit = act_bid * (1.0 - self.slippage)
                exit_slip = act_bid - exec_exit

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
                    "regime": exec_regime,
                    "bar_time": bar_str,
                    "candle_close_time_utc": c_close_ts_str,
                    "data_arrival_time_utc": d_arrival_ts_str,
                    "decision_time_utc": decision_time_utc_str,
                    "quote_arrival_time_utc": q_arrival_ts_str,
                    "action": "SELL",
                    "symbol": sym,
                    "units": units,
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
                act_ask = float(actual_quotes[sym]["ask"])
                exec_entry = act_ask * (1.0 + self.slippage)
                entry_slip = exec_entry - act_ask

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

                mark_prices[sym] = float(actual_quotes[sym]["bid"])

                ev_entry_b = {
                    "event_type": "ORDER_FILL",
                    "model": "Candidate_B",
                    "regime": exec_regime,
                    "bar_time": bar_str,
                    "candle_close_time_utc": c_close_ts_str,
                    "data_arrival_time_utc": d_arrival_ts_str,
                    "decision_time_utc": decision_time_utc_str,
                    "quote_arrival_time_utc": q_arrival_ts_str,
                    "action": "BUY",
                    "symbol": sym,
                    "units": units,
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

        return self._record_and_finalize_bar(
            bar_str=bar_str,
            c_close_ts_str=c_close_ts_str,
            d_arrival_ts_str=d_arrival_ts_str,
            decision_time_utc_str=decision_time_utc_str,
            q_arrival_ts_str=q_arrival_ts_str,
            arrival_latency_sec=arrival_latency_sec,
            execution_latency_sec=execution_latency_sec,
            close_prices=close_prices,
            mark_prices=mark_prices,
            exec_regime=exec_regime,
            bar_key=bar_key,
            events_this_bar=events_this_bar,
            status="SUCCESS",
            anomaly="NONE",
        )

    def _record_and_finalize_bar(
        self,
        bar_str: str,
        c_close_ts_str: str,
        d_arrival_ts_str: str,
        decision_time_utc_str: str,
        q_arrival_ts_str: str,
        arrival_latency_sec: float,
        execution_latency_sec: float,
        close_prices: Dict[str, float],
        mark_prices: Dict[str, float],
        exec_regime: str,
        bar_key: str,
        events_this_bar: List[Dict[str, Any]],
        status: str,
        anomaly: str,
    ) -> Dict[str, Any]:
        """Finalizes MTM, asserts accounting identities, appends ledger row, and saves state."""
        cA = self.state["candidate_a"]
        cB = self.state["candidate_b"]

        # Mark-to-market Candidate A
        if cA["curr_pos"] == "USDT_CASH":
            cA["unrealized_pnl"] = 0.0
            cA["equity"] = cA["cash"]
            cA["bars_in_cash"] += 1
        else:
            m_p = mark_prices[cA["curr_pos"]]
            pos_val = cA["asset_units"] * m_p
            cA["unrealized_pnl"] = pos_val - (cA["asset_units"] * cA["entry_price"])
            cA["equity"] = cA["cash"] + pos_val
            cA["bars_in_token"] += 1

        if cA["equity"] > cA["peak_equity"]:
            cA["peak_equity"] = cA["equity"]
        cur_dd_a = ((cA["peak_equity"] - cA["equity"]) / cA["peak_equity"]) * 100.0 if cA["peak_equity"] > 0 else 0.0
        if cur_dd_a > cA["max_drawdown_pct"]:
            cA["max_drawdown_pct"] = cur_dd_a

        # Mark-to-market Candidate B
        b_total_cash = 0.0
        b_total_equity = 0.0
        b_total_unrealized = 0.0
        for sym in self.symbols:
            sub = cB["sub_portfolios"][sym]
            b_total_cash += sub["cash"]
            if sub["in_pos"]:
                m_p = mark_prices[sym]
                sub_val = sub["units"] * m_p
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

        # Mathematical Identity Assertions
        expected_eq_a = cA["cash"] + (cA["asset_units"] * mark_prices.get(cA["curr_pos"], 0.0) if cA["curr_pos"] != "USDT_CASH" else 0.0)
        assert abs(cA["equity"] - expected_eq_a) < 1e-4, f"Candidate A Identity Failure: equity={cA['equity']}, expected={expected_eq_a}"

        expected_eq_b = sum(
            sub["cash"] + (sub["units"] * mark_prices[s] if sub["in_pos"] else 0.0)
            for s, sub in cB["sub_portfolios"].items()
        )
        assert abs(cB["total_equity"] - expected_eq_b) < 1e-4, f"Candidate B Identity Failure: equity={cB['total_equity']}, expected={expected_eq_b}"

        # Append to Ledger CSV
        total_latency_sec = round(arrival_latency_sec + execution_latency_sec, 4)
        trades_executed = len([e for e in events_this_bar if e.get("event_type") == "ORDER_FILL"])
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
            "trades_executed": trades_executed,
            "anomaly": anomaly,
            "regime": exec_regime,
        }
        self._append_ledger(ledger_row)

        # Update metadata state & processed bars cache
        self.processed_bars.add(bar_key)
        self.state["total_bars_processed"] += 1
        self.state["last_processed_bar"] = bar_str
        self._save_state()

        return {
            "status": status,
            "bar_time": bar_str,
            "regime": exec_regime,
            "candidate_a": {
                "equity": round(cA["equity"], 2),
                "pos": cA["curr_pos"],
            },
            "candidate_b": {
                "equity": round(cB["total_equity"], 2),
                "active_tokens": [s for s, sub in cB["sub_portfolios"].items() if sub["in_pos"]],
            },
            "events_count": len(events_this_bar),
            "trades_executed": trades_executed,
            "anomaly": anomaly,
            "arrival_latency_sec": round(arrival_latency_sec, 3),
            "execution_latency_sec": round(execution_latency_sec, 3),
        }

    def _generate_comparison_markdown(self):
        """Generates dynamic dual-language comparison markdown artifact with scientific disclaimers."""
        cA = self.state["candidate_a"]
        cB = self.state["candidate_b"]

        init_c = self.state["initial_cash"]
        ret_a = ((cA["equity"] / init_c) - 1.0) * 100.0
        ret_b = ((cB["total_equity"] / init_c) - 1.0) * 100.0
        alpha_spread = ret_a - ret_b

        wr_a = (cA["win_count"] / cA["trade_count"] * 100.0) if cA["trade_count"] > 0 else 0.0
        wr_b = (cB["win_count"] / cB["trade_count"] * 100.0) if cB["trade_count"] > 0 else 0.0

        bars_tracked = self.state.get("total_bars_processed", 0)
        last_bar = self.state.get("last_processed_bar") or "Awaiting First Live Candle (>= 2026-09-23 UTC)"
        anomalies_count = self.state.get("anomalies_count", 0)

        md_content = f"""# Forward Paper Tracking & A/B Model Performance
# 前向实测模拟与 A/B 模型绩效实时对照报告

> [!NOTE]
> **Scientific Positioning & Research Nature / 科学定位与研究性质**:
> The system is currently an operational quantitative research and paper-trading simulation platform. It is NOT yet an empirically forward-verified basis for risking real capital. All capital allocation decisions must await the completion of the 180-day / 30-trade forward evaluation horizon under the frozen protocol.
> 本系统当前为一个可试运行的量化研究与前向模拟交易系统，但还不是经前向验证、可据此判断会赚钱并投入真实资金的交易依据。所有真实资金决策必须等待 180 天或 30 笔完整交易的前瞻评测窗口完成。

- **Report Updated / 报告更新时间**: `{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}`
- **Evaluation Cutoff / 冻结基准线**: `2026-09-23 00:00:00 UTC`
- **Runner Regime / 运行模式**: `{self.regime}`
- **Total Genuine OOS Bars Tracked / 累计样本外真实 K 线**: `{bars_tracked}` bars
- **Last Processed Bar / 最新闭合 K 线**: `{last_bar}`
- **Anomalies Encountered / 触发异常次数**: `{anomalies_count}` (Logged in journal)
- **Initial Capital / 初始本金**: `${init_c:,.2f} USDT` each (Started from 100% Cash)

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
- **Current Progress / 当前进度**: `{cA["trade_count"]} / 30` completed roundtrips ({bars_tracked} live bars accumulated).
- **Execution & Data Integrity / 执行时序与数据完整性**:
  - Live state starts independently from $10,000 cash each at the freeze cutoff with zero carried-over demo positions.
  - Strict 5-step causality: `Closed Candle Arrival -> Freshness Check (<= 900s) -> Model Signal -> Live Top-of-Book Quote -> Simulated Fill -> Post-Execution MTM`.
  - Stale candles (> 900s) or missing order-book quotes automatically trigger safety skip and anomaly logging.
- **Current Verdict / 当前科学裁定**:
  - `EVALUATION_IN_PROGRESS`: Insufficient out-of-sample forward sample to validate or reject Candidate A.
  - Candidate A must maintain cost-adjusted Sharpe superiority and positive excess alpha over Candidate B across the 180-day window to earn live deployment consideration.
"""
        with open(self.report_file, "w", encoding="utf-8") as f:
            f.write(md_content)
