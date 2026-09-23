# -*- coding: utf-8 -*-
"""
Unified Single-Ledger 4-Hour Trend Backtesting Engine (Phase 37.3)
==================================================================
Standardized causal backtesting engine enforcing mathematical reconciliation,
strict temporal causality, dual stop-loss exit modes (Bar-Close vs Intrabar Touch),
and uniform transaction cost models across all evaluated strategies.

Mathematical Ledger Invariants Enforced on Every Single Bar:
  1. Position Value_t = sum_i(Units_i * Mark Close_i)
  2. Total Equity_t = Cash_t + Position Value_t
  3. Total Equity_t - Initial Cash == Gross Realized PnL_t + Gross Unrealized PnL_t - Total Cash Fees_t
     (where slippage is embedded directly into fill prices)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd


class StopLossMode(Enum):
    BAR_CLOSE = "BAR_CLOSE"                       # Check Close < Stop at bar t, fill at bar t+1 Open
    INTRABAR_STOP_TOUCH = "INTRABAR_STOP_TOUCH"   # Conservative: Check Low <= Prior-Bar Stop, fill at min(Open, Stop) - slip


@dataclass
class TradeOrder:
    order_id: int
    symbol: str
    action: str            # 'BUY' or 'SELL'
    bar_time: pd.Timestamp
    fill_time: pd.Timestamp
    quote_price: float
    fill_price: float      # Effective execution price after slippage
    units: float
    notional_usd: float
    fee_usd: float
    slippage_usd: float
    reason: str


@dataclass
class Position:
    symbol: str
    units: float
    entry_fill_price: float
    entry_time: pd.Timestamp
    entry_fee: float
    entry_slippage: float
    initial_stop_price: float
    trailing_stop_price: float
    peak_price: float


@dataclass
class CompletedTrade:
    trade_id: int
    symbol: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    units: float
    notional_entry_usd: float
    notional_exit_usd: float
    gross_pnl_usd: float   # (exit_price - entry_price) * units (slippage embedded)
    total_fee_usd: float   # entry_fee + exit_fee
    net_pnl_usd: float     # gross_pnl_usd - total_fee_usd
    net_ret_pct: float     # net_pnl_usd / notional_entry_usd
    duration_bars: int
    exit_reason: str
    stop_mode: str


class Unified4hEngine:
    """
    Unified 4h Systematic Trend & Rotation Backtesting Engine.
    """

    def __init__(
        self,
        initial_cash: float = 10000.0,
        fee_rate: float = 0.0008,          # 8 bps spot taker fee
        execution_slippage: float = 0.0005, # 5 bps normal execution slippage
        stop_slippage: float = 0.0015,      # 15 bps adverse stop-loss slippage
        stop_loss_mode: StopLossMode = StopLossMode.BAR_CLOSE,
    ):
        self.initial_cash = initial_cash
        self.fee_rate = fee_rate
        self.execution_slippage = execution_slippage
        self.stop_slippage = stop_slippage
        self.stop_loss_mode = stop_loss_mode

    def _reconcile_bar(
        self,
        bar_t: pd.Timestamp,
        cash: float,
        positions: Dict[str, Position],
        current_closes: Dict[str, float],
        cum_realized_pnl: float,
        cum_fees: float,
    ) -> Dict[str, float]:
        """Validates exact mathematical ledger identity at bar t."""
        pos_val = sum(pos.units * current_closes[sym] for sym, pos in positions.items())
        total_equity = cash + pos_val
        gross_unrealized = sum((current_closes[sym] - pos.entry_fill_price) * pos.units for sym, pos in positions.items())

        # Mathematical Identity:
        # Total Equity - Initial Cash == Gross Realized PnL + Gross Unrealized PnL - Total Cash Fees
        target_delta = total_equity - self.initial_cash
        accounting_delta = cum_realized_pnl + gross_unrealized - cum_fees
        reconciliation_error = abs(target_delta - accounting_delta)

        if reconciliation_error > 1e-4:
            raise ValueError(
                f"Ledger reconciliation failed at {bar_t}! "
                f"Total Equity: {total_equity:.4f}, Target Delta: {target_delta:.4f}, "
                f"Accounting Delta: {accounting_delta:.4f}, Error: {reconciliation_error:.6f}"
            )

        return {
            "cash": cash,
            "position_value": pos_val,
            "total_equity": total_equity,
            "gross_realized_pnl": cum_realized_pnl,
            "gross_unrealized_pnl": gross_unrealized,
            "cum_fees": cum_fees,
            "reconciliation_error": reconciliation_error,
        }

    def run_structural_trend(
        self,
        data_dict: Dict[str, pd.DataFrame],
        symbols: List[str] = ["ETHUSDT", "SOLUSDT"],
        lookback_bars: int = 120,
        atr_period: int = 14,
        atr_mult: float = 3.0,
        allocation_ratio: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Runs Structural Trend strategy on specified symbols (e.g. ETH/SOL 50/50).
        Supports both BAR_CLOSE and conservative INTRABAR_STOP_TOUCH exit modes.
        """
        # Determine common timestamp index
        common_idx = data_dict[symbols[0]].index
        for s in symbols[1:]:
            common_idx = common_idx.intersection(data_dict[s].index)
        common_idx = common_idx.sort_values()

        # Compute causal indicators
        indicators = {}
        for s in symbols:
            df = data_dict[s].reindex(common_idx)
            c = df["close"]
            h = df["high"]
            l = df["low"]

            # ATR causal
            tr1 = h - l
            tr2 = (h - c.shift(1)).abs()
            tr3 = (l - c.shift(1)).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(atr_period, min_periods=1).mean()

            # Donchian 120 causal (shifted by 1 so bar t only sees past)
            donchian_high = h.shift(1).rolling(lookback_bars).max()
            swing_low = l.shift(1).rolling(60).min()
            ema120 = c.ewm(span=120, adjust=False).mean()

            indicators[s] = pd.DataFrame({
                "atr": atr,
                "donchian_high": donchian_high,
                "swing_low": swing_low,
                "ema120": ema120,
            }, index=common_idx)

        # Simulation state
        cash = self.initial_cash
        positions: Dict[str, Position] = {}
        pending_orders: List[Dict[str, Any]] = []

        completed_trades: List[CompletedTrade] = []
        orders_ledger: List[TradeOrder] = []
        bar_ledger: List[Dict[str, Any]] = []

        cum_realized_pnl = 0.0
        cum_fees = 0.0
        cum_slippage = 0.0
        order_counter = 0
        trade_counter = 0

        # Sub-portfolio budgets for multi-asset independence
        sub_cash = {s: self.initial_cash * allocation_ratio for s in symbols}

        for i, t in enumerate(common_idx):
            current_opens = {s: float(data_dict[s].loc[t, "open"]) for s in symbols}
            current_highs = {s: float(data_dict[s].loc[t, "high"]) for s in symbols}
            current_lows = {s: float(data_dict[s].loc[t, "low"]) for s in symbols}
            current_closes = {s: float(data_dict[s].loc[t, "close"]) for s in symbols}

            # -------------------------------------------------------------
            # Stage 1: Execute Pending Orders from previous bar Close at Open
            # -------------------------------------------------------------
            new_pending = []
            for p_ord in pending_orders:
                s = p_ord["symbol"]
                act = p_ord["action"]
                quote_px = current_opens[s]

                if act == "BUY":
                    fill_px = quote_px * (1.0 + self.execution_slippage)
                    slip_usd = (fill_px - quote_px)
                    avail_budget = sub_cash[s]
                    # Reserve for fee
                    units = (avail_budget / fill_px) * (1.0 - self.fee_rate * 1.05)
                    notional = units * fill_px
                    fee_usd = notional * self.fee_rate

                    sub_cash[s] -= (notional + fee_usd)
                    cash -= (notional + fee_usd)
                    cum_fees += fee_usd
                    cum_slippage += units * slip_usd

                    # Initialize stop levels
                    prev_atr = float(indicators[s].loc[t, "atr"])
                    prev_swing = float(indicators[s].loc[t, "swing_low"])
                    init_stop = max(prev_swing, fill_px - atr_mult * prev_atr)

                    positions[s] = Position(
                        symbol=s,
                        units=units,
                        entry_fill_price=fill_px,
                        entry_time=t,
                        entry_fee=fee_usd,
                        entry_slippage=units * slip_usd,
                        initial_stop_price=init_stop,
                        trailing_stop_price=init_stop,
                        peak_price=fill_px,
                    )

                    order_counter += 1
                    orders_ledger.append(TradeOrder(
                        order_id=order_counter,
                        symbol=s,
                        action="BUY",
                        bar_time=t,
                        fill_time=t,
                        quote_price=quote_px,
                        fill_price=fill_px,
                        units=units,
                        notional_usd=notional,
                        fee_usd=fee_usd,
                        slippage_usd=units * slip_usd,
                        reason=p_ord["reason"],
                    ))

                elif act == "SELL":
                    pos = positions[s]
                    fill_px = quote_px * (1.0 - self.execution_slippage)
                    slip_usd = (quote_px - fill_px)
                    notional = pos.units * fill_px
                    fee_usd = notional * self.fee_rate

                    gross_pnl = (fill_px - pos.entry_fill_price) * pos.units
                    cum_realized_pnl += gross_pnl
                    cum_fees += fee_usd
                    cum_slippage += pos.units * slip_usd

                    sub_cash[s] += (notional - fee_usd)
                    cash += (notional - fee_usd)

                    order_counter += 1
                    orders_ledger.append(TradeOrder(
                        order_id=order_counter,
                        symbol=s,
                        action="SELL",
                        bar_time=t,
                        fill_time=t,
                        quote_price=quote_px,
                        fill_price=fill_px,
                        units=pos.units,
                        notional_usd=notional,
                        fee_usd=fee_usd,
                        slippage_usd=pos.units * slip_usd,
                        reason=p_ord["reason"],
                    ))

                    trade_counter += 1
                    completed_trades.append(CompletedTrade(
                        trade_id=trade_counter,
                        symbol=s,
                        entry_time=pos.entry_time,
                        exit_time=t,
                        entry_price=pos.entry_fill_price,
                        exit_price=fill_px,
                        units=pos.units,
                        notional_entry_usd=pos.units * pos.entry_fill_price,
                        notional_exit_usd=notional,
                        gross_pnl_usd=gross_pnl,
                        total_fee_usd=pos.entry_fee + fee_usd,
                        net_pnl_usd=gross_pnl - (pos.entry_fee + fee_usd),
                        net_ret_pct=(gross_pnl - (pos.entry_fee + fee_usd)) / (pos.units * pos.entry_fill_price),
                        duration_bars=int((t - pos.entry_time) / pd.Timedelta("4h")),
                        exit_reason=p_ord["reason"],
                        stop_mode=self.stop_loss_mode.value,
                    ))

                    del positions[s]

            pending_orders = new_pending

            # -------------------------------------------------------------
            # Stage 2: Intrabar Stop-Loss Check (Mode B: Strictly Prior Bar Stop)
            # -------------------------------------------------------------
            if self.stop_loss_mode == StopLossMode.INTRABAR_STOP_TOUCH:
                exited_symbols = []
                for s, pos in list(positions.items()):
                    # Use strictly the trailing stop fixed at bar t-1 close!
                    fixed_stop = pos.trailing_stop_price
                    curr_l = current_lows[s]
                    curr_o = current_opens[s]

                    if curr_l <= fixed_stop:
                        # Intrabar stop hit!
                        # Fill price: min(Open, Stop) * (1 - stop_slippage)
                        trigger_px = min(curr_o, fixed_stop)
                        fill_px = trigger_px * (1.0 - self.stop_slippage)
                        slip_usd = (trigger_px - fill_px)
                        notional = pos.units * fill_px
                        fee_usd = notional * self.fee_rate

                        gross_pnl = (fill_px - pos.entry_fill_price) * pos.units
                        cum_realized_pnl += gross_pnl
                        cum_fees += fee_usd
                        cum_slippage += pos.units * slip_usd

                        sub_cash[s] += (notional - fee_usd)
                        cash += (notional - fee_usd)

                        order_counter += 1
                        orders_ledger.append(TradeOrder(
                            order_id=order_counter,
                            symbol=s,
                            action="SELL",
                            bar_time=t,
                            fill_time=t,
                            quote_price=trigger_px,
                            fill_price=fill_px,
                            units=pos.units,
                            notional_usd=notional,
                            fee_usd=fee_usd,
                            slippage_usd=pos.units * slip_usd,
                            reason="INTRABAR_STOP_TOUCH",
                        ))

                        trade_counter += 1
                        completed_trades.append(CompletedTrade(
                            trade_id=trade_counter,
                            symbol=s,
                            entry_time=pos.entry_time,
                            exit_time=t,
                            entry_price=pos.entry_fill_price,
                            exit_price=fill_px,
                            units=pos.units,
                            notional_entry_usd=pos.units * pos.entry_fill_price,
                            notional_exit_usd=notional,
                            gross_pnl_usd=gross_pnl,
                            total_fee_usd=pos.entry_fee + fee_usd,
                            net_pnl_usd=gross_pnl - (pos.entry_fee + fee_usd),
                            net_ret_pct=(gross_pnl - (pos.entry_fee + fee_usd)) / (pos.units * pos.entry_fill_price),
                            duration_bars=int((t - pos.entry_time) / pd.Timedelta("4h")),
                            exit_reason="INTRABAR_STOP_TOUCH",
                            stop_mode=self.stop_loss_mode.value,
                        ))

                        exited_symbols.append(s)

                for s in exited_symbols:
                    del positions[s]

            # -------------------------------------------------------------
            # Stage 3: Bar Close Signals & Trailing Stop Updating
            # -------------------------------------------------------------
            for s in symbols:
                curr_c = current_closes[s]
                curr_h = current_highs[s]
                curr_atr = float(indicators[s].loc[t, "atr"])
                curr_donchian = float(indicators[s].loc[t, "donchian_high"])
                curr_swing_l = float(indicators[s].loc[t, "swing_low"])
                curr_ema120 = float(indicators[s].loc[t, "ema120"])

                if s in positions:
                    pos = positions[s]
                    # Update trailing stop for next bar
                    pos.peak_price = max(pos.peak_price, curr_h)
                    new_stop = max(pos.peak_price - atr_mult * curr_atr, curr_swing_l)
                    pos.trailing_stop_price = max(pos.trailing_stop_price, new_stop)

                    # In Mode A, check bar close exit
                    if self.stop_loss_mode == StopLossMode.BAR_CLOSE:
                        if curr_c < pos.trailing_stop_price:
                            pending_orders.append({
                                "symbol": s,
                                "action": "SELL",
                                "reason": "BAR_CLOSE_TRAILING_STOP",
                            })

                else:
                    # Check entry signal
                    if (curr_c > curr_donchian) and (curr_c > curr_ema120):
                        if not any(po["symbol"] == s for po in pending_orders):
                            pending_orders.append({
                                "symbol": s,
                                "action": "BUY",
                                "reason": "DONCHIAN120_BREAKOUT",
                            })

            # -------------------------------------------------------------
            # Stage 4: Mathematical Ledger Reconciliation at Bar Close
            # -------------------------------------------------------------
            rec = self._reconcile_bar(
                bar_t=t,
                cash=cash,
                positions=positions,
                current_closes=current_closes,
                cum_realized_pnl=cum_realized_pnl,
                cum_fees=cum_fees,
            )

            bar_ledger.append({
                "bar_time": t,
                "cash": rec["cash"],
                "position_value": rec["position_value"],
                "total_equity": rec["total_equity"],
                "gross_realized_pnl": rec["gross_realized_pnl"],
                "gross_unrealized_pnl": rec["gross_unrealized_pnl"],
                "cum_fees": rec["cum_fees"],
                "cum_slippage": cum_slippage,
                "active_positions_count": len(positions),
                "active_symbols": ",".join(positions.keys()),
            })

        df_bar_ledger = pd.DataFrame(bar_ledger).set_index("bar_time")
        df_trades = pd.DataFrame([t.__dict__ for t in completed_trades]) if completed_trades else pd.DataFrame()
        df_orders = pd.DataFrame([o.__dict__ for o in orders_ledger]) if orders_ledger else pd.DataFrame()

        return {
            "strategy": "STRUCTURAL_TREND",
            "stop_mode": self.stop_loss_mode.value,
            "bar_ledger": df_bar_ledger,
            "trades": df_trades,
            "orders": df_orders,
            "initial_cash": self.initial_cash,
            "final_equity": float(df_bar_ledger["total_equity"].iloc[-1]),
            "total_return_pct": float((df_bar_ledger["total_equity"].iloc[-1] / self.initial_cash - 1.0) * 100.0),
            "total_trades": len(completed_trades),
            "cum_fees_usd": cum_fees,
            "cum_slippage_usd": cum_slippage,
        }

    def run_simple_ema_control(
        self,
        data_dict: Dict[str, pd.DataFrame],
        symbols: List[str] = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"],
        ema_span: int = 200,
    ) -> Dict[str, Any]:
        """
        Runs Simple EMA Control: Equal budget across symbols.
        If Close > EMA200, hold token; else hold cash. Zero cross-sectional rotation.
        """
        common_idx = data_dict[symbols[0]].index
        for s in symbols[1:]:
            common_idx = common_idx.intersection(data_dict[s].index)
        common_idx = common_idx.sort_values()

        # Compute causal EMA200
        ema_dict = {}
        for s in symbols:
            c = data_dict[s].reindex(common_idx)["close"]
            ema_dict[s] = c.ewm(span=ema_span, adjust=False).mean()

        allocation_ratio = 1.0 / len(symbols)
        sub_cash = {s: self.initial_cash * allocation_ratio for s in symbols}
        cash = self.initial_cash
        positions: Dict[str, Position] = {}
        pending_orders: List[Dict[str, Any]] = []

        completed_trades: List[CompletedTrade] = []
        orders_ledger: List[TradeOrder] = []
        bar_ledger: List[Dict[str, Any]] = []

        cum_realized_pnl = 0.0
        cum_fees = 0.0
        cum_slippage = 0.0
        order_counter = 0
        trade_counter = 0

        for t in common_idx:
            current_opens = {s: float(data_dict[s].loc[t, "open"]) for s in symbols}
            current_closes = {s: float(data_dict[s].loc[t, "close"]) for s in symbols}

            # Execute pending orders
            new_pending = []
            for p_ord in pending_orders:
                s = p_ord["symbol"]
                act = p_ord["action"]
                quote_px = current_opens[s]

                if act == "BUY" and s not in positions:
                    fill_px = quote_px * (1.0 + self.execution_slippage)
                    slip_usd = (fill_px - quote_px)
                    avail_budget = sub_cash[s]
                    units = (avail_budget / fill_px) * (1.0 - self.fee_rate * 1.05)
                    notional = units * fill_px
                    fee_usd = notional * self.fee_rate

                    sub_cash[s] -= (notional + fee_usd)
                    cash -= (notional + fee_usd)
                    cum_fees += fee_usd
                    cum_slippage += units * slip_usd

                    positions[s] = Position(
                        symbol=s,
                        units=units,
                        entry_fill_price=fill_px,
                        entry_time=t,
                        entry_fee=fee_usd,
                        entry_slippage=units * slip_usd,
                        initial_stop_price=0.0,
                        trailing_stop_price=0.0,
                        peak_price=fill_px,
                    )

                    order_counter += 1
                    orders_ledger.append(TradeOrder(
                        order_id=order_counter,
                        symbol=s,
                        action="BUY",
                        bar_time=t,
                        fill_time=t,
                        quote_price=quote_px,
                        fill_price=fill_px,
                        units=units,
                        notional_usd=notional,
                        fee_usd=fee_usd,
                        slippage_usd=units * slip_usd,
                        reason=p_ord["reason"],
                    ))

                elif act == "SELL" and s in positions:
                    pos = positions[s]
                    fill_px = quote_px * (1.0 - self.execution_slippage)
                    slip_usd = (quote_px - fill_px)
                    notional = pos.units * fill_px
                    fee_usd = notional * self.fee_rate

                    gross_pnl = (fill_px - pos.entry_fill_price) * pos.units
                    cum_realized_pnl += gross_pnl
                    cum_fees += fee_usd
                    cum_slippage += pos.units * slip_usd

                    sub_cash[s] += (notional - fee_usd)
                    cash += (notional - fee_usd)

                    order_counter += 1
                    orders_ledger.append(TradeOrder(
                        order_id=order_counter,
                        symbol=s,
                        action="SELL",
                        bar_time=t,
                        fill_time=t,
                        quote_price=quote_px,
                        fill_price=fill_px,
                        units=pos.units,
                        notional_usd=notional,
                        fee_usd=fee_usd,
                        slippage_usd=pos.units * slip_usd,
                        reason=p_ord["reason"],
                    ))

                    trade_counter += 1
                    completed_trades.append(CompletedTrade(
                        trade_id=trade_counter,
                        symbol=s,
                        entry_time=pos.entry_time,
                        exit_time=t,
                        entry_price=pos.entry_fill_price,
                        exit_price=fill_px,
                        units=pos.units,
                        notional_entry_usd=pos.units * pos.entry_fill_price,
                        notional_exit_usd=notional,
                        gross_pnl_usd=gross_pnl,
                        total_fee_usd=pos.entry_fee + fee_usd,
                        net_pnl_usd=gross_pnl - (pos.entry_fee + fee_usd),
                        net_ret_pct=(gross_pnl - (pos.entry_fee + fee_usd)) / (pos.units * pos.entry_fill_price),
                        duration_bars=int((t - pos.entry_time) / pd.Timedelta("4h")),
                        exit_reason=p_ord["reason"],
                        stop_mode="BAR_CLOSE",
                    ))

                    del positions[s]

            pending_orders = new_pending

            # Evaluate Bar Close signals for EMA200 crossover
            for s in symbols:
                curr_c = current_closes[s]
                curr_ema = float(ema_dict[s].loc[t])

                if s in positions:
                    if curr_c <= curr_ema:
                        if not any(po["symbol"] == s for po in pending_orders):
                            pending_orders.append({
                                "symbol": s,
                                "action": "SELL",
                                "reason": "EMA200_BREAKDOWN",
                            })
                else:
                    if curr_c > curr_ema:
                        if not any(po["symbol"] == s for po in pending_orders):
                            pending_orders.append({
                                "symbol": s,
                                "action": "BUY",
                                "reason": "EMA200_BREAKOUT",
                            })

            # Reconcile bar
            rec = self._reconcile_bar(
                bar_t=t,
                cash=cash,
                positions=positions,
                current_closes=current_closes,
                cum_realized_pnl=cum_realized_pnl,
                cum_fees=cum_fees,
            )

            bar_ledger.append({
                "bar_time": t,
                "cash": rec["cash"],
                "position_value": rec["position_value"],
                "total_equity": rec["total_equity"],
                "gross_realized_pnl": rec["gross_realized_pnl"],
                "gross_unrealized_pnl": rec["gross_unrealized_pnl"],
                "cum_fees": rec["cum_fees"],
                "cum_slippage": cum_slippage,
                "active_positions_count": len(positions),
                "active_symbols": ",".join(positions.keys()),
            })

        df_bar_ledger = pd.DataFrame(bar_ledger).set_index("bar_time")
        df_trades = pd.DataFrame([t.__dict__ for t in completed_trades]) if completed_trades else pd.DataFrame()
        df_orders = pd.DataFrame([o.__dict__ for o in orders_ledger]) if orders_ledger else pd.DataFrame()

        return {
            "strategy": f"SIMPLE_EMA_{len(symbols)}COINS",
            "symbols": symbols,
            "bar_ledger": df_bar_ledger,
            "trades": df_trades,
            "orders": df_orders,
            "initial_cash": self.initial_cash,
            "final_equity": float(df_bar_ledger["total_equity"].iloc[-1]),
            "total_return_pct": float((df_bar_ledger["total_equity"].iloc[-1] / self.initial_cash - 1.0) * 100.0),
            "total_trades": len(completed_trades),
            "cum_fees_usd": cum_fees,
            "cum_slippage_usd": cum_slippage,
        }

    def run_buy_and_hold(
        self,
        data_dict: Dict[str, pd.DataFrame],
        symbols: List[str] = ["BTCUSDT"],
    ) -> Dict[str, Any]:
        """
        Passive benchmark buy & hold (e.g. 100% BTC or 25% Equal Weight).
        """
        common_idx = data_dict[symbols[0]].index
        for s in symbols[1:]:
            common_idx = common_idx.intersection(data_dict[s].index)
        common_idx = common_idx.sort_values()

        allocation_ratio = 1.0 / len(symbols)
        cash = self.initial_cash
        positions: Dict[str, Position] = {}

        cum_fees = 0.0
        cum_slippage = 0.0
        bar_ledger = []

        # Initial buy on first bar Open
        first_t = common_idx[0]
        for s in symbols:
            quote_px = float(data_dict[s].loc[first_t, "open"])
            fill_px = quote_px * (1.0 + self.execution_slippage)
            avail_budget = self.initial_cash * allocation_ratio
            units = (avail_budget / fill_px) * (1.0 - self.fee_rate * 1.05)
            notional = units * fill_px
            fee_usd = notional * self.fee_rate

            cash -= (notional + fee_usd)
            cum_fees += fee_usd
            cum_slippage += units * (fill_px - quote_px)

            positions[s] = Position(
                symbol=s,
                units=units,
                entry_fill_price=fill_px,
                entry_time=first_t,
                entry_fee=fee_usd,
                entry_slippage=units * (fill_px - quote_px),
                initial_stop_price=0.0,
                trailing_stop_price=0.0,
                peak_price=fill_px,
            )

        for t in common_idx:
            current_closes = {s: float(data_dict[s].loc[t, "close"]) for s in symbols}
            rec = self._reconcile_bar(
                bar_t=t,
                cash=cash,
                positions=positions,
                current_closes=current_closes,
                cum_realized_pnl=0.0,
                cum_fees=cum_fees,
            )

            bar_ledger.append({
                "bar_time": t,
                "cash": rec["cash"],
                "position_value": rec["position_value"],
                "total_equity": rec["total_equity"],
                "gross_realized_pnl": 0.0,
                "gross_unrealized_pnl": rec["gross_unrealized_pnl"],
                "cum_fees": cum_fees,
                "cum_slippage": cum_slippage,
                "active_positions_count": len(positions),
                "active_symbols": ",".join(positions.keys()),
            })

        df_bar_ledger = pd.DataFrame(bar_ledger).set_index("bar_time")
        return {
            "strategy": f"BUY_AND_HOLD_{'_'.join(symbols)}",
            "bar_ledger": df_bar_ledger,
            "trades": pd.DataFrame(),
            "orders": pd.DataFrame(),
            "initial_cash": self.initial_cash,
            "final_equity": float(df_bar_ledger["total_equity"].iloc[-1]),
            "total_return_pct": float((df_bar_ledger["total_equity"].iloc[-1] / self.initial_cash - 1.0) * 100.0),
            "total_trades": len(symbols),
            "cum_fees_usd": cum_fees,
            "cum_slippage_usd": cum_slippage,
        }
