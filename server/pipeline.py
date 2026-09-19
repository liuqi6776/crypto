# -*- coding: utf-8 -*-
"""
Pipeline Module: Unified Quant Service Pipeline (Phase 23)
==========================================================
Packages data fetching, local atomic state persistence, signal detection,
and alert dispatching into a cohesive, reusable execution pipeline.
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
    ETH_LEVERAGE,
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
from crypto_quant.paper.funding_arb import fetch_binance_funding_info, get_funding_arbitrage_guide
from crypto_quant.paper.journal import PaperJournal
from crypto_quant.paper.leverage_model import LeverageModel
from crypto_quant.paper.service import PaperService
from crypto_quant.paper.state import PortfolioPaperState
from crypto_quant.paper.strategy import StructuralTrendPaperStrategy


class QuantServerPipeline:
    """
    Unified Quant Pipeline executing:
    1. Market Data Fetch: Retrieves closed candles from Binance.
    2. Local State Update: Atomically updates state.json and journal.jsonl.
    3. Signal Detection: Evaluates 3x trend breakout, trailing stop, and Top-1 leaderboard.
    4. Alert Dispatch: Sends instant email upon signal transition.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.leverage_model = LeverageModel(default_leverage=ETH_LEVERAGE)
        self.last_signal: Optional[str] = None
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

    def compute_leaderboard(self, service: Optional[PaperService] = None) -> Dict[str, Any]:
        """Computes live cross-sectional momentum ranking across BTC, ETH, SOL, BNB."""
        if service is None:
            service = PaperService(state_path=STATE_PATH, journal_path=JOURNAL_PATH)
        tokens = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
        closes_dict = {}
        for t in tokens:
            try:
                df = service.fetcher.fetch_closed_klines(t, interval=TIMEFRAME, limit=250, check_freshness=False)
                closes_dict[t] = df["close"]
            except Exception:
                pass

        # Fallback to local files if any network delay
        if len(closes_dict) < 4:
            for t in tokens:
                if t not in closes_dict:
                    p = ROOT_DIR / f"data/{t}_4h_2020_2026.parquet"
                    if p.exists():
                        closes_dict[t] = pd.read_parquet(p)["close"].tail(250)

        closes = pd.DataFrame(closes_dict).dropna()
        closes_prior = closes.shift(1)
        ema200 = closes_prior.ewm(span=200).mean()
        bb_mid = closes_prior.rolling(120).mean()
        bb_std = closes_prior.rolling(120).std()
        bb_z = (closes_prior - bb_mid) / (bb_std + 1e-8)
        mom20 = (closes_prior / closes_prior.shift(120)) - 1.0
        score = bb_z + mom20

        latest_t = score.index[-1]
        latest_scores = score.loc[latest_t].sort_values(ascending=False)
        btc_bull = bool(closes_prior.loc[latest_t, "BTCUSDT"] > ema200.loc[latest_t, "BTCUSDT"])

        ranks = []
        for rank, (tok, sc) in enumerate(latest_scores.items(), 1):
            c_p = closes_prior.loc[latest_t, tok]
            e_p = ema200.loc[latest_t, tok]
            z_p = bb_z.loc[latest_t, tok]
            m_p = mom20.loc[latest_t, tok]
            is_ok = bool(c_p > e_p)
            ranks.append({
                "rank": rank,
                "symbol": tok,
                "score": round(float(sc), 3),
                "curr_price": round(float(closes.loc[latest_t, tok]), 2),
                "ema200": round(float(e_p), 2),
                "bb_z": round(float(z_p), 2),
                "mom20_pct": round(float(m_p * 100.0), 2),
                "is_above_ema200": is_ok,
            })

        top_1 = ranks[0]
        dual_gate_passed = bool(btc_bull and top_1["is_above_ema200"])
        recommended_mode = f"100% {top_1['symbol']} 进攻做多" if dual_gate_passed else "100% Delta-Neutral 资金费套利"

        return {
            "top_symbol": top_1["symbol"],
            "top_score": top_1["score"],
            "btc_macro_bull": btc_bull,
            "dual_gate_passed": dual_gate_passed,
            "recommended_mode": recommended_mode,
            "ranks": ranks,
        }

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Extracts complete operational state for Web UI and email alerts."""
        state = PortfolioPaperState.load(STATE_PATH) if STATE_PATH.exists() else PortfolioPaperState.create_initial()
        eth_s = state.eth_state

        equity_usdt = eth_s.total_equity * INITIAL_CAPITAL_USDT
        peak_usdt = eth_s.peak_equity * INITIAL_CAPITAL_USDT
        is_in_pos = (eth_s.position == 1)
        pos_direction = "LONG (3x)" if is_in_pos else "FLAT (Core套利)"

        strat = StructuralTrendPaperStrategy()
        service = PaperService(state_path=STATE_PATH, journal_path=JOURNAL_PATH)
        df = service.fetcher.fetch_closed_klines("ETHUSDT", interval=TIMEFRAME, limit=250, check_freshness=False)
        ind = strat.compute_indicators(df)

        curr_close = ind["close"]
        bb_upper = ind["bb_upper"]
        bb_mid = ind["bb_mid"]
        bb_lower = ind["bb_lower"]
        ema200 = ind["ema200"]
        atr14 = ind["atr"]
        swing_low = ind["swing_low"]
        macro_mult = ind["macro_mult"]

        lev_metrics = self.leverage_model.compute_metrics(
            base_equity_usdt=equity_usdt,
            entry_price=eth_s.entry_price if is_in_pos else None,
            current_price=curr_close,
            highest_price=eth_s.highest_price_since_entry if is_in_pos else None,
            trailing_stop_price=eth_s.trailing_stop_price if is_in_pos else None,
            atr=atr14,
            is_in_position=is_in_pos,
            leverage=ETH_LEVERAGE,
        )

        funding_guide = get_funding_arbitrage_guide(base_capital_usdt=equity_usdt)
        dist_to_buy_pct = ((bb_upper - curr_close) / curr_close) * 100.0

        journal = PaperJournal(JOURNAL_PATH)
        events = journal.read_all_events()
        trade_events = [e for e in events if e.get("event_type") == "POSITION_CLOSED"][-5:]
        signal_events = [e for e in events if e.get("event_type") == "SIGNAL_CREATED"][-5:]

        now_utc = datetime.now(timezone.utc)
        now_bjt = now_utc + timedelta(hours=8)
        last_bar_time = eth_s.last_processed_bar_time or str(df.index[-1])
        active_mode = "ETH_3X_LONG" if is_in_pos else "CORE_FUNDING_ARB"

        return {
            "timestamp_utc": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "timestamp_bjt": now_bjt.strftime("%Y-%m-%d %H:%M:%S BJT"),
            "active_mode": active_mode,
            "experiment_id": EXPERIMENT_ID,
            "strategy_name": STRATEGY_NAME,
            "public_url": self.get_public_url(),
            "recipient_email": DEFAULT_RECIPIENT,
            "capital": {
                "initial_usdt": round(INITIAL_CAPITAL_USDT, 2),
                "current_equity_usdt": round(equity_usdt, 2),
                "peak_usdt": round(peak_usdt, 2),
                "pnl_usdt": round((eth_s.total_equity - 1.0) * INITIAL_CAPITAL_USDT, 2),
                "pnl_pct": round((eth_s.total_equity - 1.0) * 100.0, 2),
                "drawdown_pct": round(eth_s.drawdown * 100.0, 2),
                "total_fees_usdt": round(eth_s.total_fees * INITIAL_CAPITAL_USDT, 2),
            },
            "position": {
                "symbol": "ETHUSDT",
                "direction": pos_direction,
                "is_in_pos": is_in_pos,
                "leverage": ETH_LEVERAGE,
                "nominal_usdt": lev_metrics["nominal_position_usdt"],
                "entry_price": lev_metrics["entry_price"],
                "entry_time": eth_s.entry_time,
                "trailing_stop": lev_metrics["trailing_stop_price"],
                "liquidation_price": lev_metrics["liquidation_price"],
                "distance_to_liq_pct": lev_metrics["distance_to_liq_pct"],
                "distance_to_stop_pct": lev_metrics["distance_to_stop_pct"],
                "safety_buffer_pct": lev_metrics["safety_buffer_pct"],
                "unrealized_pnl_usdt": lev_metrics["unrealized_pnl_usdt"],
                "unrealized_roe_pct": lev_metrics["unrealized_roe_pct"],
                "is_safe": lev_metrics["is_safe"],
                "highest_price": lev_metrics["highest_price"],
                "bars_in_pos": eth_s.bars_in_position,
            },
            "funding_arbitrage": funding_guide,
            "leaderboard": self.compute_leaderboard(service),
            "market": {
                "symbol": "ETHUSDT",
                "curr_price": round(curr_close, 2),
                "last_closed_bar": last_bar_time,
                "bb_upper": round(bb_upper, 2),
                "bb_mid": round(bb_mid, 2),
                "bb_lower": round(bb_lower, 2),
                "ema200": round(ema200, 2),
                "atr14": round(atr14, 2),
                "swing_low": round(swing_low, 2),
                "macro_status": "强多头顺势 (1.0x)" if macro_mult == 1.0 else "弱势防守 (0.5x)",
                "dist_to_buy_pct": round(dist_to_buy_pct, 2),
            },
            "trades_history": trade_events,
            "signals_history": signal_events,
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
        1. Fetch fresh closed klines & run gap replay.
        2. Atomically persist state.json & journal.jsonl.
        3. Detect signal transitions (FLAT -> BUY, HOLD -> EXIT).
        4. Send rich HTML email if transitioned or forced.
        """
        t0 = time.time()
        with self.lock:
            # Step 1: Fetch fresh data and update local state
            service = PaperService(state_path=STATE_PATH, journal_path=JOURNAL_PATH)
            snapshot = service.run_once()

            # Step 2: Extract current dashboard and indicator state
            data = self.get_dashboard_data()
            eth_s = snapshot.get("positions", {}).get("ETHUSDT", {})
            curr_signal = "BUY" if eth_s.get("position", 0) == 1 else "FLAT"
            curr_bar = snapshot.get("latest_closed_bar", {}).get("ETHUSDT", "")

            # Step 3: Check signal transition
            signal_changed = False
            if self.last_signal is None:
                self.last_signal = curr_signal
                self.last_bar_time = curr_bar
                print(f"[PIPELINE INIT] Baseline established: Signal={curr_signal}, Bar={curr_bar}")
            elif curr_signal != self.last_signal or force_notify:
                signal_changed = True
                print(f"[PIPELINE ALERT] Signal Transition: {self.last_signal} -> {curr_signal} (Bar: {curr_bar})")
                # Step 4: Dispatch alert email
                send_alert_email(
                    event_type="SIGNAL_TRANSITION",
                    old_signal=self.last_signal,
                    new_signal=curr_signal,
                    to_email=DEFAULT_RECIPIENT,
                    dashboard_data=data,
                    test_mode=False,
                )
                self.last_signal = curr_signal
                self.last_bar_time = curr_bar

            elapsed = round(time.time() - t0, 3)
            now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            self.last_cycle_time = now_str

            return {
                "success": True,
                "elapsed_seconds": elapsed,
                "timestamp_utc": now_str,
                "curr_signal": curr_signal,
                "signal_changed": signal_changed,
                "portfolio_equity": snapshot.get("equity", {}).get("portfolio_equity", 1.0),
                "latest_bar": curr_bar,
            }
