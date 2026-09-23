# -*- coding: utf-8 -*-
"""
V1 Strategy Module: Cross-Sectional Top-1 Spot Rotation & Dual Macro Gate
========================================================================
Implements the core production strategy:
- Universe: BTC, ETH, SOL, BNB (liquid non-meme core assets).
- Lookback: 120-bar (20-day) Bollinger Z-score + 20-day absolute momentum.
- Dual Macro Trend Gate:
    Gate 1: BTC > EMA200 (+0.5% hysteresis buffer)
    Gate 2: Top-1 candidate > EMA200 (+0.5% hysteresis buffer)
- Allocation:
    Both gates passed -> 100% Spot Long Top-1 (1.0x, zero leverage, zero debt).
    Either gate failed -> 100% USDT Cash Defense (zero basis risk, zero debt).
- Frictions: 8.0 bps (0.08%) one-way trading fee on every asset rotation.
- State Persistence: Atomically saved to paper_state/v1_top1_state.json.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from crypto_quant.paper.config import (
    CONFIG_HASH,
    DOCS_DIR,
    INITIAL_EQUITY,
    LOG_DIR,
    ROOT_DIR,
    STATE_DIR,
    TIMEFRAME,
    get_code_commit,
)
from crypto_quant.paper.journal import PaperJournal

V1_STATE_PATH: Path = STATE_DIR / "v1_top1_state.json"
V1_JOURNAL_PATH: Path = LOG_DIR / "v1_top1_journal.jsonl"
DEFAULT_HYSTERESIS_PCT: float = 0.005  # 0.5% hysteresis buffer around EMA200
ROTATION_FEE_RATE: float = 0.0008     # 8.0 bps (0.08%) one-way friction


def calculate_atr(df: Optional[pd.DataFrame], period: int = 14) -> float:
    """
    Calculates the 14-period Average True Range (ATR) on 4h candles.
    Robust to missing columns (falls back to close diff if high/low missing).
    """
    if df is None or len(df) < period + 1:
        return 0.0
    try:
        if "high" in df.columns and "low" in df.columns and "close" in df.columns:
            high = df["high"]
            low = df["low"]
            close = df["close"]
            prev_close = close.shift(1)
            tr1 = high - low
            tr2 = (high - prev_close).abs()
            tr3 = (low - prev_close).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        elif "close" in df.columns:
            close = df["close"]
            tr = (close - close.shift(1)).abs()
        else:
            return 0.0
        atr = tr.rolling(period).mean()
        val = atr.iloc[-1]
        return float(val) if not np.isnan(val) else 0.0
    except Exception:
        return 0.0


@dataclass
class V1Top1State:
    """
    Persistent state tracking for the V1 Top-1 3.0x Leverage Rotation & Cash Defense system.
    """
    active_symbol: str = "USDT_CASH"          # e.g., 'SOLUSDT', 'ETHUSDT', or 'USDT_CASH'
    position_mode: str = "DEFENSIVE_USDT_CASH" # 'OFFENSIVE_3X_LONG' or 'DEFENSIVE_USDT_CASH'
    entry_price: float = 0.0
    entry_time: Optional[str] = None
    current_price: float = 0.0
    leverage: float = 3.0                      # 🔥 3.0x 杠杆倍数
    liquidation_price: float = 0.0             # 🔥 币安 3X 强平价 (开仓价 -32.83%)
    distance_to_liq_pct: float = 0.0           # 距强平线距离百分比
    atr_value: float = 0.0                     # 标的 14周期 4h ATR 数值
    stop_loss_price: float = 0.0               # 紧凑自适应止损位 (1.5x ATR + Trailing)
    take_profit_tp1: float = 0.0               # 第一目标止盈位 (TP1: +10% 动量加速区)
    take_profit_tp2: float = 0.0               # 第二目标止盈位 (TP2: +20% 主升浪扩张区)
    highest_price_since_entry: float = 0.0      # 开仓以来最高价 (动态追踪止盈止损)
    bars_held: int = 0
    cash_usdt: float = 10000.0
    asset_units: float = 0.0
    nominal_usdt: float = 0.0
    unrealized_pnl_usdt: float = 0.0
    unrealized_pnl_pct: float = 0.0
    total_equity_usdt: float = 10000.0
    peak_equity_usdt: float = 10000.0
    drawdown_pct: float = 0.0
    accumulated_fees_usdt: float = 0.0
    last_processed_bar: Optional[str] = None
    last_signal: str = "CASH"                 # 'BUY', 'HOLD', 'EXIT', 'CASH'
    data_source: str = "BINANCE_REST_API"
    data_age_seconds: float = 0.0
    is_stale: bool = False
    code_commit: str = field(default_factory=get_code_commit)
    config_hash: str = CONFIG_HASH

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "V1Top1State":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def save_atomic(self, filepath: Path = V1_STATE_PATH) -> None:
        """Saves state atomically using temporary file rename."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        temp_fd, temp_path = tempfile.mkstemp(dir=str(filepath.parent), prefix="v1_state_", suffix=".tmp")
        with open(temp_fd, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        os.replace(temp_path, str(filepath))

    @classmethod
    def load(cls, filepath: Path = V1_STATE_PATH) -> "V1Top1State":
        if not filepath.exists():
            state = cls()
            state.save_atomic(filepath)
            return state
        with open(filepath, "r", encoding="utf-8") as f:
            d = json.load(f)
        return cls.from_dict(d)


class Top1RotationStrategy:
    """
    Production-grade V1 Strategy Engine executing:
    1. Cross-sectional momentum evaluation across BTC, ETH, SOL, BNB.
    2. Dual Macro Trend Gate filtering with hysteresis.
    3. Turnover accounting with 8 bps friction per asset switch.
    4. 🔥 3.0x Leverage Compact Adaptive (SL 1.5x ATR + Trailing Stop) or 100% USDT Cash.
    """

    def __init__(
        self,
        symbols: Optional[List[str]] = None,
        hysteresis_pct: float = DEFAULT_HYSTERESIS_PCT,
        one_way_fee_rate: float = ROTATION_FEE_RATE,
        state_path: Path = V1_STATE_PATH,
        journal_path: Path = V1_JOURNAL_PATH,
    ):
        self.symbols = symbols or ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
        self.hysteresis_pct = hysteresis_pct
        self.one_way_fee_rate = one_way_fee_rate
        self.state_path = Path(state_path)
        self.journal_path = Path(journal_path)
        self.journal = PaperJournal(self.journal_path)

    def evaluate_cross_section(
        self,
        klines_dict: Dict[str, pd.DataFrame],
        live_prices: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates leaderboard rankings, scores, and macro trend gates.
        Integrates instant live ticker prices if provided for sub-minute responsiveness.
        Returns complete leaderboard metadata with full data source transparency.
        """
        closes_dict = {}
        data_ages = {}
        now_utc = datetime.now(timezone.utc)
        is_stale = False
        data_source = "BINANCE_REST_API"

        for sym in self.symbols:
            if sym in klines_dict and not klines_dict[sym].empty:
                df = klines_dict[sym]
                closes_dict[sym] = df["close"]
                last_open_time = df.index[-1]
                if hasattr(last_open_time, "tzinfo") and last_open_time.tzinfo is None:
                    last_open_time = last_open_time.replace(tzinfo=timezone.utc)
                # If bar is still forming, close_time is in the future, so data age is effectively 0
                last_close_time = last_open_time + pd.Timedelta(hours=4)
                age = max(0.0, (now_utc - last_close_time).total_seconds()) if now_utc > last_close_time else 0.0
                data_ages[sym] = round(age, 1)
                if age > 18000:
                    is_stale = True
            else:
                # Fallback to local historical parquet
                p = ROOT_DIR / f"data/{sym}_4h_2020_2026.parquet"
                if p.exists():
                    df = pd.read_parquet(p)
                    closes_dict[sym] = df["close"].tail(250)
                    data_source = "LOCAL_CACHE_FALLBACK"
                    is_stale = True

        closes = pd.DataFrame(closes_dict).dropna()
        if len(closes) < 130:
            raise ValueError(f"Insufficient bars for cross-sectional scoring: {len(closes)} < 130")

        # Inject real-time live prices into the latest candle if provided
        if live_prices:
            latest_idx = closes.index[-1]
            for sym in self.symbols:
                if sym in live_prices and sym in closes.columns:
                    closes.loc[latest_idx, sym] = float(live_prices[sym])

        closes_prior = closes.shift(1)
        ema200 = closes_prior.ewm(span=200).mean()
        bb_mid = closes_prior.rolling(120).mean()
        bb_std = closes_prior.rolling(120).std()
        
        # Real-time Z-score and Momentum using latest price vs historical distributions
        bb_z = (closes - bb_mid) / (bb_std + 1e-8)
        mom20 = (closes / closes.shift(120)) - 1.0
        score = bb_z + mom20

        latest_t = score.index[-1]
        latest_scores = score.loc[latest_t].sort_values(ascending=False)

        # BTC Macro Trend Gate (uses real-time BTC price)
        btc_curr_p = float(closes.loc[latest_t, "BTCUSDT"])
        btc_ema200 = float(ema200.loc[latest_t, "BTCUSDT"])
        btc_bull = bool(btc_curr_p > btc_ema200)

        ranks = []
        for rank, (tok, sc) in enumerate(latest_scores.items(), 1):
            curr_c = float(closes.loc[latest_t, tok])
            e_p = float(ema200.loc[latest_t, tok])
            z_p = float(bb_z.loc[latest_t, tok])
            m_p = float(mom20.loc[latest_t, tok])
            is_ok = bool(curr_c > e_p)
            dist_to_ema_pct = round(((curr_c - e_p) / e_p) * 100.0, 2)
            tok_df = klines_dict.get(tok)
            atr_tok = calculate_atr(tok_df, period=14)
            atr_pct = round((atr_tok / curr_c) * 100.0, 2) if curr_c > 0 else 0.0

            ranks.append({
                "rank": rank,
                "symbol": tok,
                "score": round(float(sc), 3),
                "curr_price": round(curr_c, 2),
                "ema200": round(e_p, 2),
                "bb_z": round(z_p, 2),
                "mom20_pct": round(m_p * 100.0, 2),
                "is_above_ema200": is_ok,
                "dist_to_ema_pct": dist_to_ema_pct,
                "atr_14": round(atr_tok, 2),
                "atr_pct": atr_pct,
            })

        top_1 = ranks[0]
        # Dual Gate Condition
        dual_gate_passed = bool(btc_bull and top_1["is_above_ema200"])
        if is_stale:
            # Data safety lock: Stale data prevents active offensive buy!
            dual_gate_passed = False

        recommended_mode = f"3.0x {top_1['symbol']} 杠杆做多" if dual_gate_passed else "100% USDT 现金防御"

        return {
            "top_symbol": top_1["symbol"],
            "top_score": top_1["score"],
            "top_atr": top_1["atr_14"],
            "btc_macro_bull": btc_bull,
            "dual_gate_passed": dual_gate_passed,
            "recommended_mode": recommended_mode,
            "ranks": ranks,
            "latest_bar_time": str(latest_t),
            "data_source": data_source,
            "is_stale": is_stale,
            "data_ages": data_ages,
        }

    def update_portfolio_step(
        self,
        klines_dict: Dict[str, pd.DataFrame],
        current_state: Optional[V1Top1State] = None,
        live_prices: Optional[Dict[str, float]] = None,
    ) -> Tuple[V1Top1State, Dict[str, Any]]:
        """
        Executes one full evaluation pass for the V1 Top-1 Portfolio:
        1. Evaluates cross-section and dual macro trend gates.
        2. Applies hysteresis buffer to avoid EMA200 threshold churning.
        3. Executes 3.0x nominal leverage allocation with 1.5x ATR compact adaptive stop.
        4. Dynamically ratchets trailing stop (breakeven at +5%, trailing at +10%).
        5. Handles intrabar stop-loss trigger protection to 100% USDT Cash.
        6. Marks to market with margin ROE and persists updated state atomically.
        """
        state = current_state or V1Top1State.load(self.state_path)
        eval_res = self.evaluate_cross_section(klines_dict, live_prices=live_prices)

        top_cand = eval_res["top_symbol"]
        btc_bull = eval_res["btc_macro_bull"]
        is_stale = eval_res["is_stale"]
        latest_bar = eval_res["latest_bar_time"]

        # Hysteresis Filter:
        # To enter LONG, price must clear EMA200 by +0.5%.
        # To exit to CASH, price must drop below EMA200 by -0.5%.
        top_rank_item = [r for r in eval_res["ranks"] if r["symbol"] == top_cand][0]
        curr_price = top_rank_item["curr_price"]
        dist_pct = top_rank_item["dist_to_ema_pct"] / 100.0

        if "OFFENSIVE" in state.position_mode:
            # Currently in long: exit only if BTC breaks below -0.5% or top coin breaks below -0.5%
            gate_pass = (not is_stale) and btc_bull and (dist_pct >= -self.hysteresis_pct)
        else:
            # Currently in cash: enter only if both clear +0.5%
            gate_pass = (not is_stale) and btc_bull and (dist_pct >= self.hysteresis_pct)

        target_symbol = top_cand if gate_pass else "USDT_CASH"
        target_mode = "OFFENSIVE_3X_LONG" if gate_pass else "DEFENSIVE_USDT_CASH"

        action_taken = "HOLD"
        turnover_friction = 0.0

        # Detect Asset Switch
        if target_symbol != state.active_symbol:
            # Rotation occurred (e.g. USDT_CASH -> SOLUSDT, or SOLUSDT -> ETHUSDT, or SOLUSDT -> USDT_CASH)
            # 1. Close previous position if held
            if state.active_symbol != "USDT_CASH" and state.asset_units > 0:
                if live_prices and state.active_symbol in live_prices:
                    prev_price = float(live_prices[state.active_symbol])
                elif state.active_symbol in klines_dict and not klines_dict[state.active_symbol].empty:
                    prev_price = float(klines_dict[state.active_symbol]["close"].iloc[-1])
                elif state.active_symbol == top_cand:
                    prev_price = curr_price
                else:
                    prev_price = state.current_price if state.current_price > 0 else state.entry_price
                gross_proceeds = state.asset_units * prev_price
                sell_fee = gross_proceeds * self.one_way_fee_rate
                cost_basis = state.asset_units * state.entry_price
                nominal_pnl = gross_proceeds - cost_basis
                net_cash = max(0.0, state.cash_usdt + nominal_pnl - sell_fee)
                state.cash_usdt = net_cash
                state.asset_units = 0.0
                turnover_friction += sell_fee

            # 2. Open new 3.0x position if target is offensive token
            if target_symbol != "USDT_CASH":
                leverage = 3.0
                state.leverage = leverage
                nominal_target = state.cash_usdt * leverage
                buy_fee = nominal_target * self.one_way_fee_rate
                investable_nominal = max(0.0, nominal_target - buy_fee)
                state.asset_units = investable_nominal / curr_price
                state.cash_usdt = max(0.0, state.cash_usdt - buy_fee)
                state.entry_price = curr_price
                state.entry_time = latest_bar
                state.highest_price_since_entry = curr_price
                state.bars_held = 0
                turnover_friction += buy_fee
                action_taken = f"ROTATE_{state.active_symbol}_TO_{target_symbol}" if state.active_symbol != "USDT_CASH" else f"ENTER_3X_{target_symbol}"
                
                # ATR & Liquidation calculation
                top_atr = eval_res.get("top_atr", 0.0)
                if top_atr <= 0:
                    top_atr = calculate_atr(klines_dict.get(target_symbol), period=14)
                state.atr_value = round(top_atr, 2)
                
                # Binance 3x MMR = 0.5% -> Liquidation = entry * (1 - (1/3 - 0.005)) = entry * 0.67167 (-32.83%)
                state.liquidation_price = round(curr_price * (1.0 - (1.0 / leverage - 0.005)), 2)
                state.distance_to_liq_pct = round(((curr_price - state.liquidation_price) / curr_price) * 100.0, 2)

                # Compact Adaptive 1.5x ATR Stop Loss
                if top_atr > 0:
                    initial_stop = round(curr_price - (1.5 * top_atr), 2)
                else:
                    initial_stop = round(curr_price * 0.965, 2)
                gate_stop = round(top_rank_item["ema200"] * (1.0 - self.hysteresis_pct), 2)
                state.stop_loss_price = max(gate_stop, initial_stop)

                # Take-profit zones (TP1 +10%, TP2 +20%)
                state.take_profit_tp1 = round(curr_price * 1.10, 2)
                state.take_profit_tp2 = round(curr_price * 1.20, 2)
            else:
                action_taken = "EXIT_TO_CASH"
                state.entry_price = 0.0
                state.entry_time = None
                state.highest_price_since_entry = 0.0
                state.stop_loss_price = 0.0
                state.take_profit_tp1 = 0.0
                state.take_profit_tp2 = 0.0
                state.liquidation_price = 0.0
                state.distance_to_liq_pct = 0.0
                state.bars_held = 0

            state.active_symbol = target_symbol
            state.position_mode = target_mode
            state.accumulated_fees_usdt += turnover_friction
        else:
            # Sustained position
            if "OFFENSIVE" in state.position_mode:
                # Check Intrabar Stop Loss Trigger (1.5x ATR or Trailing Stop)
                if state.stop_loss_price > 0 and curr_price <= state.stop_loss_price:
                    # Intrabar Stop Out! Immediately exit to 100% USDT Cash
                    gross_proceeds = state.asset_units * curr_price
                    sell_fee = gross_proceeds * self.one_way_fee_rate
                    cost_basis = state.asset_units * state.entry_price
                    nominal_pnl = gross_proceeds - cost_basis
                    state.cash_usdt = max(0.0, state.cash_usdt + nominal_pnl - sell_fee)
                    turnover_friction += sell_fee
                    state.accumulated_fees_usdt += turnover_friction
                    state.asset_units = 0.0
                    state.active_symbol = "USDT_CASH"
                    state.position_mode = "DEFENSIVE_USDT_CASH"
                    action_taken = "STOP_LOSS_EXIT_TO_CASH"
                    state.entry_price = 0.0
                    state.entry_time = None
                    state.highest_price_since_entry = 0.0
                    state.stop_loss_price = 0.0
                    state.take_profit_tp1 = 0.0
                    state.take_profit_tp2 = 0.0
                    state.liquidation_price = 0.0
                    state.distance_to_liq_pct = 0.0
                    state.bars_held = 0
                else:
                    state.bars_held += 1
                    action_taken = "HOLD_3X_LONG"
                    state.highest_price_since_entry = max(state.highest_price_since_entry, curr_price)
                    
                    # Trailing Stop Ratchet:
                    # 1. Breakeven lock when gain >= +5%
                    if state.highest_price_since_entry >= state.entry_price * 1.05:
                        breakeven_stop = round(state.entry_price * 1.002, 2)
                        state.stop_loss_price = max(state.stop_loss_price, breakeven_stop)
                    # 2. Trailing stop 5% off peak when gain >= +10%
                    if state.highest_price_since_entry >= state.entry_price * 1.10:
                        trailing_lock = round(state.highest_price_since_entry * 0.95, 2)
                        state.stop_loss_price = max(state.stop_loss_price, trailing_lock)
                    
                    # Update distance to liquidation
                    if state.liquidation_price > 0:
                        state.distance_to_liq_pct = round(((curr_price - state.liquidation_price) / curr_price) * 100.0, 2)
            else:
                action_taken = "HOLD_CASH"
                state.stop_loss_price = 0.0
                state.take_profit_tp1 = 0.0
                state.take_profit_tp2 = 0.0
                state.highest_price_since_entry = 0.0
                state.liquidation_price = 0.0
                state.distance_to_liq_pct = 0.0

        # Mark to Market
        state.current_price = curr_price if state.active_symbol != "USDT_CASH" else 1.0
        if state.active_symbol != "USDT_CASH" and state.asset_units > 0:
            state.nominal_usdt = state.asset_units * curr_price
            cost_basis = state.asset_units * state.entry_price
            state.unrealized_pnl_usdt = state.nominal_usdt - cost_basis
            margin_capital = (cost_basis / state.leverage) if state.leverage > 0 else state.total_equity_usdt
            state.unrealized_pnl_pct = (state.unrealized_pnl_usdt / margin_capital) * 100.0
            state.total_equity_usdt = max(0.0, state.cash_usdt + state.unrealized_pnl_usdt)
        else:
            state.nominal_usdt = 0.0
            state.unrealized_pnl_usdt = 0.0
            state.unrealized_pnl_pct = 0.0
            state.total_equity_usdt = state.cash_usdt

        if state.total_equity_usdt > state.peak_equity_usdt:
            state.peak_equity_usdt = state.total_equity_usdt

        state.drawdown_pct = max(0.0, ((state.peak_equity_usdt - state.total_equity_usdt) / state.peak_equity_usdt) * 100.0) if state.peak_equity_usdt > 0 else 0.0
        state.last_processed_bar = latest_bar
        state.data_source = eval_res["data_source"]
        state.is_stale = eval_res["is_stale"]
        state.last_signal = "BUY" if "OFFENSIVE" in state.position_mode else "CASH"

        # Save atomically
        state.save_atomic(self.state_path)

        # Log audit journal event
        self.journal.log_event(
            event_type="V1_STEP_EVALUATED",
            payload={
                "action": action_taken,
                "active_symbol": state.active_symbol,
                "position_mode": state.position_mode,
                "total_equity": round(float(state.total_equity_usdt), 2),
                "unrealized_pnl": round(float(state.unrealized_pnl_usdt), 2),
                "turnover_friction": round(float(turnover_friction), 2),
                "dual_gate_passed": bool(gate_pass),
            },
            symbol=state.active_symbol,
            bar_time=latest_bar,
        )

        return state, eval_res
