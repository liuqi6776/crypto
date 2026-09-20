# -*- coding: utf-8 -*-
"""
Pipeline Module: Unified Quant Service Pipeline (Phase 23 V1)
=============================================================
Unified institutional pipeline executing:
1. Multi-Asset Data Sync: Binance Public REST 4h candles (BTC, ETH, SOL, BNB).
2. V1 Top-1 Strategy Step: Cross-sectional ranking & Dual Macro Gate with hysteresis.
3. Real State Machine: Atomic persistence to paper_state/v1_top1_state.json.
4. Turnover Accounting: Real 8.0 bps deduction on asset switches.
5. Email Alert Dispatch: BUY (1x Spot Long), EXIT (100% USDT Cash Defense), ROTATE.
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import threading
import time
from typing import Any, Dict, Optional
import urllib.request
import pandas as pd

from server.config import (
    DEFAULT_RECIPIENT,
    INITIAL_CAPITAL_USDT,
    JOURNAL_PATH,
    PORT,
    ROOT_DIR,
    STATE_PATH,
    STATIC_NGROK_DOMAIN,
    TIMEFRAME,
)
from server.email_notifier import send_alert_email

from crypto_quant.paper.config import (
    CONFIG_HASH,
    ENABLE_REAL_ORDERS,
    EXPERIMENT_ID,
    PAPER_MODE,
    STRATEGY_NAME,
    get_code_commit,
)
from crypto_quant.paper.funding_arb import get_funding_arbitrage_guide
from crypto_quant.paper.journal import PaperJournal
from crypto_quant.paper.market_data import MarketDataFetcher
from crypto_quant.paper.service import PaperService
from crypto_quant.paper.top1_rotation_strategy import (
    Top1RotationStrategy,
    V1_JOURNAL_PATH,
    V1_STATE_PATH,
    V1Top1State,
)


class QuantServerPipeline:
    """
    Production-grade V1 Server Pipeline.
    Ensures:
    Dashboard State == State Machine Position == Email Alert Content.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.strategy = Top1RotationStrategy(
            symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"],
            state_path=V1_STATE_PATH,
            journal_path=V1_JOURNAL_PATH,
        )
        self.fetcher = MarketDataFetcher()
        self.last_active_symbol: Optional[str] = None
        self.last_bar_time: Optional[str] = None
        self.last_cycle_time: Optional[str] = None
        self.public_tunnel_url: Optional[str] = None

    def get_public_url(self) -> str:
        """Resolves active public tunnel URL or fallback."""
        if self.public_tunnel_url and self.public_tunnel_url.startswith("https://"):
            return self.public_tunnel_url
        try:
            req = urllib.request.Request("http://127.0.0.1:4040/api/tunnels", headers={"User-Agent": "Pipeline/1.0"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                data = json.loads(resp.read().decode())
                for t in data.get("tunnels", []):
                    u = t.get("public_url", "")
                    if u.startswith("https://"):
                        self.public_tunnel_url = u
                        return u
        except Exception:
            pass
        if STATIC_NGROK_DOMAIN:
            return f"https://{STATIC_NGROK_DOMAIN}"
        return f"http://127.0.0.1:{PORT}"

    def fetch_all_klines(self) -> Dict[str, pd.DataFrame]:
        """Fetches latest 4h closed candles for all universe symbols."""
        klines = {}
        for sym in self.strategy.symbols:
            try:
                df = self.fetcher.fetch_closed_klines(sym, interval=TIMEFRAME, limit=250, check_freshness=False)
                klines[sym] = df
            except Exception as e:
                print(f"[PIPELINE WARNING] Failed to fetch {sym} from API: {e}. Falling back to local cache.")
                p = ROOT_DIR / f"data/{sym}_4h_2020_2026.parquet"
                if p.exists():
                    klines[sym] = pd.read_parquet(p).tail(250)
        return klines

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Extracts complete operational state for Web UI and email alerts."""
        v1_state = V1Top1State.load(V1_STATE_PATH)
        klines = self.fetch_all_klines()
        leaderboard = self.strategy.evaluate_cross_section(klines)

        is_in_pos = (v1_state.active_symbol != "USDT_CASH" and v1_state.position_mode == "OFFENSIVE_SPOT_LONG")
        pos_direction = f"1.0x 现货做多 ({v1_state.active_symbol.replace('USDT', '')})" if is_in_pos else "100% USDT 现金防御"

        # Funding Carry Guide (Corrected 50% nominal basis + fee deductions)
        funding_guide = get_funding_arbitrage_guide(base_capital_usdt=v1_state.total_equity_usdt)

        now_utc = datetime.now(timezone.utc)
        now_bjt = now_utc + timedelta(hours=8)
        last_bar_time = v1_state.last_processed_bar or leaderboard.get("latest_bar_time", "")

        active_mode = f"V1_SPOT_LONG_{v1_state.active_symbol.replace('USDT', '')}" if is_in_pos else "V1_USDT_CASH_DEFENSE"

        # Journal events
        journal = PaperJournal(V1_JOURNAL_PATH)
        events = journal.read_all_events()
        trade_events = [e for e in events if "ENTER" in e.get("payload", {}).get("action", "") or "EXIT" in e.get("payload", {}).get("action", "")][-5:]

        return {
            "timestamp_utc": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "timestamp_bjt": now_bjt.strftime("%Y-%m-%d %H:%M:%S BJT"),
            "active_mode": active_mode,
            "experiment_id": "exp_v1_top1_dual_gate_cash",
            "strategy_name": "v1_top1_dual_gate_cash (1.0x Spot + Hysteresis)",
            "public_url": self.get_public_url(),
            "recipient_email": DEFAULT_RECIPIENT,
            "capital": {
                "initial_usdt": round(INITIAL_CAPITAL_USDT, 2),
                "current_equity_usdt": round(v1_state.total_equity_usdt, 2),
                "peak_usdt": round(v1_state.peak_equity_usdt, 2),
                "pnl_usdt": round(v1_state.total_equity_usdt - INITIAL_CAPITAL_USDT, 2),
                "pnl_pct": round(((v1_state.total_equity_usdt - INITIAL_CAPITAL_USDT) / INITIAL_CAPITAL_USDT) * 100.0, 2),
                "drawdown_pct": round(v1_state.drawdown_pct, 2),
                "accumulated_fees_usdt": round(v1_state.accumulated_fees_usdt, 2),
                "cash_usdt": round(v1_state.cash_usdt, 2),
            },
            "position": {
                "active_symbol": v1_state.active_symbol,
                "position_mode": v1_state.position_mode,
                "direction": pos_direction,
                "is_in_pos": is_in_pos,
                "leverage": 1.0,
                "entry_price": v1_state.entry_price,
                "entry_time": v1_state.entry_time,
                "current_price": v1_state.current_price,
                "nominal_usdt": round(v1_state.nominal_usdt, 2),
                "asset_units": round(v1_state.asset_units, 4),
                "unrealized_pnl_usdt": round(v1_state.unrealized_pnl_usdt, 2),
                "unrealized_pnl_pct": round(v1_state.unrealized_pnl_pct, 2),
                "bars_held": v1_state.bars_held,
            },
            "funding_arbitrage": funding_guide,
            "leaderboard": leaderboard,
            "market": {
                "top_symbol": leaderboard["top_symbol"],
                "curr_price": leaderboard["ranks"][0]["curr_price"],
                "last_closed_bar": last_bar_time,
                "btc_macro_bull": leaderboard["btc_macro_bull"],
                "dual_gate_passed": leaderboard["dual_gate_passed"],
                "data_source": leaderboard["data_source"],
                "is_stale": leaderboard["is_stale"],
            },
            "trades_history": trade_events,
            "system": {
                "code_commit": get_code_commit(),
                "config_hash": CONFIG_HASH,
                "paper_mode": PAPER_MODE,
                "enable_real_orders": ENABLE_REAL_ORDERS,
                "last_cycle_time": self.last_cycle_time,
            },
        }

    def run_cycle(self, force_notify: bool = False) -> Dict[str, Any]:
        """
        Executes one full 15-minute pipeline cycle:
        1. Fetch fresh closed klines for BTC, ETH, SOL, BNB.
        2. Evaluate V1 Top-1 rotation & Dual Macro Gate with hysteresis.
        3. Execute asset rotation with 8.0 bps friction accounting.
        4. Atomically persist state.
        5. Detect signal transition and fire alert email.
        """
        t0 = time.time()
        with self.lock:
            # Step 1: Fetch fresh klines
            klines = self.fetch_all_klines()

            # Step 2 & 3: Run V1 Top-1 strategy step & persist state
            v1_state, leaderboard = self.strategy.update_portfolio_step(klines)

            curr_active_symbol = v1_state.active_symbol
            curr_mode = v1_state.position_mode
            curr_bar = v1_state.last_processed_bar

            # Step 4: Extract dashboard data
            dash_data = self.get_dashboard_data()

            # Step 5: Check signal transition
            signal_changed = False
            event_type = None

            if self.last_active_symbol is None:
                self.last_active_symbol = curr_active_symbol
                self.last_bar_time = curr_bar
                print(f"[V1 PIPELINE INIT] Baseline established: Active={curr_active_symbol} ({curr_mode}) at {curr_bar}")
            elif curr_active_symbol != self.last_active_symbol or force_notify:
                signal_changed = True
                if self.last_active_symbol == "USDT_CASH" and curr_active_symbol != "USDT_CASH":
                    event_type = "BUY"
                elif self.last_active_symbol != "USDT_CASH" and curr_active_symbol == "USDT_CASH":
                    event_type = "EXIT"
                else:
                    event_type = "ROTATE"

                print(f"[V1 PIPELINE ALERT] Signal Transition ({event_type}): {self.last_active_symbol} -> {curr_active_symbol} (Bar: {curr_bar})")

                # Dispatch notification email
                send_alert_email(
                    event_type=event_type,
                    old_signal=self.last_active_symbol,
                    new_signal=curr_active_symbol,
                    to_email=DEFAULT_RECIPIENT,
                    dashboard_data=dash_data,
                    test_mode=False,
                )
                self.last_active_symbol = curr_active_symbol
                self.last_bar_time = curr_bar

            elapsed = round(time.time() - t0, 3)
            now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            self.last_cycle_time = now_str

            return {
                "success": True,
                "elapsed_seconds": elapsed,
                "timestamp_utc": now_str,
                "curr_signal": curr_active_symbol,
                "active_symbol": curr_active_symbol,
                "position_mode": curr_mode,
                "signal_changed": signal_changed,
                "portfolio_equity": round(v1_state.total_equity_usdt, 2),
                "latest_bar": curr_bar,
                "data_source": leaderboard["data_source"],
                "is_stale": leaderboard["is_stale"],
            }
