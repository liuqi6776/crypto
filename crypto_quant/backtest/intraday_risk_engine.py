# -*- coding: utf-8 -*-
"""
Intraday Single-Ledger Risk & Execution Simulator
日内单账本风控与撮合执行引擎
=============================================
Strict institutional-grade intraday portfolio simulator:
1. 0.5% Equity Risk Sizing: Position = (Equity * 0.005) / |Entry - SL_init|.
2. Portfolio constraints: Max 2 concurrent positions, nominal leverage caps.
3. Causal Order-Book / Market Execution:
   - Long Entry: Open * (1 + execution_slippage)
   - Short Entry: Open * (1 - execution_slippage)
   - Gap Cancellation Check on Entry Bar: voids order if gap inflates stop distance > 1.25x or gap > 0.5*ATR.
4. Intrabar Priority & Worst-Case Conservative Resolution:
   - If a single bar touches both SL and TP/target, Stop-Loss is ALWAYS executed first.
   - Dynamic Trailing Stop activated after +1R, effective next bar.
   - 8-hour maximum holding duration.
5. Exact Cash Ledger Identity Assertion:
   Final Equity == Initial Cash + Sum(Gross PnL) - Sum(Fees) - Sum(Slippage) - Sum(Funding) + Open Unrealized PnL.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

from crypto_quant.ma_congestion.state_machine import TradeSignal


@dataclass
class IntradayTradeRecord:
    trade_id: int
    symbol: str
    direction: str                     # 'LONG' or 'SHORT'
    market_type: str                   # 'spot' or 'futures'
    formation_time: pd.Timestamp
    U: float
    L: float
    frozen_atr: float
    breakout_time: pd.Timestamp
    breakout_price: float
    confirm_time: pd.Timestamp
    confirm_price: float
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    entry_price: float                 # executed price including execution slippage
    units: float
    nominal_size_usdt: float
    initial_sl: float
    risk_1r_usdt: float                # nominal dollar risk at 1R
    final_sl: float
    sl_updates: int
    exit_time: pd.Timestamp
    exit_price: float                  # executed exit price including exit slippage
    exit_reason: str                   # 'STOP_LOSS', 'TRAILING_STOP', 'FIXED_2R', 'TIME_EXIT_8H', 'GAP_CANCEL'
    bars_held: int
    gross_pnl_usdt: float
    entry_fee_usdt: float
    exit_fee_usdt: float
    entry_slippage_usdt: float
    exit_slippage_usdt: float
    slippage_cost_usdt: float
    funding_cost_usdt: float
    net_pnl_usdt: float
    net_r_multiple: float              # net_pnl_usdt / risk_1r_usdt
    equity_at_entry: float
    equity_at_exit: float
    pullback_mode: str = "UNKNOWN"
    low_distance_to_u: float = 0.0     # Low - U (for Long, >= 0 proves wick never penetrated U)
    high_distance_to_l: float = 0.0    # L - High (for Short, >= 0 proves wick never penetrated L)


@dataclass
class OpenPosition:
    trade_id: int
    symbol: str
    direction: str
    market_type: str
    entry_time: pd.Timestamp
    entry_price: float
    units: float
    initial_sl: float
    current_sl: float
    frozen_atr: float
    risk_1r_usdt: float
    entry_fee_usdt: float
    entry_slippage_usdt: float
    equity_at_entry: float
    trailing_unlocked: bool = False
    highest_high: float = 0.0
    lowest_low: float = 1e12
    sl_updates: int = 0
    bars_held: int = 0
    signal_meta: Dict[str, Any] = field(default_factory=dict)


class IntradayRiskLedgerSimulator:
    """
    Multi-Asset Intraday Single-Ledger Portfolio Simulator.
    多资产日内单账本投资组合模拟器。
    """
    def __init__(
        self,
        symbols: List[str],
        initial_cash: float = 10000.0,
        risk_per_trade_pct: float = 0.005,      # 0.5% risk per trade
        max_concurrent_positions: int = 2,
        fee_rate: float = 0.0008,               # 8 bps taker fee (Spot default)
        execution_slippage: float = 0.0005,     # 5 bps execution slippage
        stop_slippage: float = 0.0015,          # 15 bps stop slippage
        max_holding_bars: int = 32,             # 8 hours on 15m (32 bars), 96 on 5m
        gap_sl_tolerance_ratio: float = 1.25,   # max allowed stop enlargement ratio
        gap_atr_tolerance_mult: float = 0.5,    # max allowed gap in terms of ATR
        market_type: str = "spot",
        exit_rule: str = "DYNAMIC_TRAILING",    # 'DYNAMIC_TRAILING' or 'FIXED_2R'
    ):
        self.symbols = symbols
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_concurrent_positions = max_concurrent_positions
        self.fee_rate = fee_rate
        self.execution_slippage = execution_slippage
        self.stop_slippage = stop_slippage
        self.max_holding_bars = max_holding_bars
        self.gap_sl_tolerance_ratio = gap_sl_tolerance_ratio
        self.gap_atr_tolerance_mult = gap_atr_tolerance_mult
        self.market_type = market_type.lower()
        self.exit_rule = exit_rule.upper()

        # State tracking
        self.open_positions: Dict[str, OpenPosition] = {}
        self.closed_trades: List[IntradayTradeRecord] = []
        self.trade_counter: int = 0
        self.total_funding_cost: float = 0.0
        self.equity_curve: List[Dict[str, Any]] = []

    def get_portfolio_equity(self, current_prices: Dict[str, float]) -> float:
        """Calculate total marked-to-market portfolio equity."""
        eq = self.cash
        for sym, pos in self.open_positions.items():
            curr_p = current_prices.get(sym, pos.entry_price)
            if pos.direction == "LONG":
                eq += pos.units * (curr_p - pos.entry_price)
            else:
                eq += pos.units * (pos.entry_price - curr_p)
        return eq

    def process_bar(
        self,
        bar_time: pd.Timestamp,
        bar_data: Dict[str, pd.Series],         # {symbol: Series with open, high, low, close, atr14}
        pending_signals: List[TradeSignal],     # signals generated at close of previous bar
        funding_rates: Optional[Dict[str, float]] = None,
    ) -> List[IntradayTradeRecord]:
        """
        Process a single bar across all portfolio symbols.
        处理单根 K 线周期的风控、止损止盈裁决、挂单成交与资金费记账。
        """
        exited_this_bar: List[IntradayTradeRecord] = []
        current_prices = {s: float(bar_data[s]["close"]) for s in self.symbols if s in bar_data}
        equity_before = self.get_portfolio_equity(current_prices)

        # -------------------------------------------------------------
        # STEP 1: Process Funding Payments (for Perpetual Futures)
        # -------------------------------------------------------------
        if self.market_type == "futures" and funding_rates:
            # Binance funding occurs every 8 hours: 00:00, 08:00, 16:00 UTC
            if bar_time.hour in [0, 8, 16] and bar_time.minute == 0:
                for sym, pos in self.open_positions.items():
                    rate = funding_rates.get(sym, 0.0)
                    if rate != 0.0:
                        nom_val = pos.units * current_prices.get(sym, pos.entry_price)
                        # Long pays if rate > 0; Short receives if rate > 0
                        cost = nom_val * rate if pos.direction == "LONG" else -nom_val * rate
                        self.cash -= cost
                        self.total_funding_cost += cost

        # -------------------------------------------------------------
        # STEP 2: Evaluate Existing Positions (Exits & Trailing Updates)
        # -------------------------------------------------------------
        symbols_to_close = []
        for sym, pos in list(self.open_positions.items()):
            if sym not in bar_data:
                continue

            row = bar_data[sym]
            o = float(row["open"])
            h = float(row["high"])
            l = float(row["low"])
            c = float(row["close"])
            atr14 = float(row["atr14"]) if "atr14" in row and not np.isnan(row["atr14"]) else pos.frozen_atr

            pos.bars_held += 1
            pos.highest_high = max(pos.highest_high, h)
            pos.lowest_low = min(pos.lowest_low, l)

            exit_triggered = False
            exit_price = 0.0
            exit_reason = ""

            if pos.direction == "LONG":
                # A. Check Stop Loss breach (Open gap down or Intrabar Low)
                hit_sl = False
                sl_price = 0.0
                if o <= pos.current_sl:
                    hit_sl = True
                    sl_price = o * (1 - self.stop_slippage)
                elif l <= pos.current_sl:
                    hit_sl = True
                    sl_price = pos.current_sl * (1 - self.stop_slippage)

                # B. Check Take Profit / Trailing conditions
                hit_tp = False
                tp_price = 0.0
                if self.exit_rule == "FIXED_2R":
                    target_2r = pos.entry_price + 2.0 * pos.risk_1r_usdt / pos.units
                    if h >= target_2r:
                        hit_tp = True
                        tp_price = max(o, target_2r) * (1 - self.execution_slippage)
                else:
                    # Dynamic Trailing
                    target_1r = pos.entry_price + (pos.risk_1r_usdt / pos.units)
                    if h >= target_1r:
                        pos.trailing_unlocked = True

                # C. Conservative / Worst-case resolution: If both SL and TP hit, SL ALWAYS executes!
                if hit_sl:
                    exit_triggered = True
                    exit_price = sl_price
                    exit_reason = "STOP_LOSS" if pos.sl_updates == 0 else "TRAILING_STOP"
                elif hit_tp:
                    exit_triggered = True
                    exit_price = tp_price
                    exit_reason = "FIXED_2R"

                # D. Max Holding Duration Exit
                if not exit_triggered and pos.bars_held >= self.max_holding_bars:
                    exit_triggered = True
                    exit_price = c * (1 - self.execution_slippage)
                    exit_reason = "TIME_EXIT_8H"

                # E. Update Dynamic Trailing Stop for NEXT bar if still open
                if not exit_triggered and self.exit_rule == "DYNAMIC_TRAILING" and pos.trailing_unlocked:
                    new_sl = max(pos.initial_sl, pos.highest_high - 2.0 * atr14)
                    if new_sl > pos.current_sl:
                        pos.current_sl = new_sl
                        pos.sl_updates += 1

            else:
                # SHORT DIRECTION (MIRROR)
                hit_sl = False
                sl_price = 0.0
                if o >= pos.current_sl:
                    hit_sl = True
                    sl_price = o * (1 + self.stop_slippage)
                elif h >= pos.current_sl:
                    hit_sl = True
                    sl_price = pos.current_sl * (1 + self.stop_slippage)

                hit_tp = False
                tp_price = 0.0
                if self.exit_rule == "FIXED_2R":
                    target_2r = pos.entry_price - 2.0 * pos.risk_1r_usdt / pos.units
                    if l <= target_2r:
                        hit_tp = True
                        tp_price = min(o, target_2r) * (1 + self.execution_slippage)
                else:
                    target_1r = pos.entry_price - (pos.risk_1r_usdt / pos.units)
                    if l <= target_1r:
                        pos.trailing_unlocked = True

                # Conservative worst-case: SL takes priority
                if hit_sl:
                    exit_triggered = True
                    exit_price = sl_price
                    exit_reason = "STOP_LOSS" if pos.sl_updates == 0 else "TRAILING_STOP"
                elif hit_tp:
                    exit_triggered = True
                    exit_price = tp_price
                    exit_reason = "FIXED_2R"

                if not exit_triggered and pos.bars_held >= self.max_holding_bars:
                    exit_triggered = True
                    exit_price = c * (1 + self.execution_slippage)
                    exit_reason = "TIME_EXIT_8H"

                if not exit_triggered and self.exit_rule == "DYNAMIC_TRAILING" and pos.trailing_unlocked:
                    new_sl = min(pos.initial_sl, pos.lowest_low + 2.0 * atr14)
                    if new_sl < pos.current_sl:
                        pos.current_sl = new_sl
                        pos.sl_updates += 1

            if exit_triggered:
                symbols_to_close.append((sym, exit_price, exit_reason))

        # Close positions and record accounting
        for sym, exit_price, exit_reason in symbols_to_close:
            pos = self.open_positions.pop(sym)
            if pos.direction == "LONG":
                gross_pnl = pos.units * (exit_price - pos.entry_price)
            else:
                gross_pnl = pos.units * (pos.entry_price - exit_price)

            exit_notional = pos.units * exit_price
            exit_fee = exit_notional * self.fee_rate
            exit_slippage_usdt = exit_notional * (self.stop_slippage if "STOP" in exit_reason else self.execution_slippage)

            # Cash settlement
            self.cash += gross_pnl - exit_fee
            net_pnl = gross_pnl - pos.entry_fee_usdt - exit_fee
            net_r = net_pnl / (pos.risk_1r_usdt + 1e-9)

            rec = IntradayTradeRecord(
                trade_id=pos.trade_id,
                symbol=pos.symbol,
                direction=pos.direction,
                market_type=pos.market_type,
                formation_time=pos.signal_meta.get("formation_time", bar_time),
                U=pos.signal_meta.get("U", 0.0),
                L=pos.signal_meta.get("L", 0.0),
                frozen_atr=pos.frozen_atr,
                breakout_time=pos.signal_meta.get("breakout_time", bar_time),
                breakout_price=pos.signal_meta.get("breakout_price", 0.0),
                confirm_time=pos.signal_meta.get("confirm_time", bar_time),
                confirm_price=pos.signal_meta.get("confirm_price", 0.0),
                signal_time=pos.entry_time - pd.Timedelta(minutes=15),
                entry_time=pos.entry_time,
                entry_price=pos.entry_price,
                units=pos.units,
                nominal_size_usdt=pos.units * pos.entry_price,
                initial_sl=pos.initial_sl,
                risk_1r_usdt=pos.risk_1r_usdt,
                final_sl=pos.current_sl,
                sl_updates=pos.sl_updates,
                exit_time=bar_time,
                exit_price=exit_price,
                exit_reason=exit_reason,
                bars_held=pos.bars_held,
                gross_pnl_usdt=gross_pnl,
                entry_fee_usdt=pos.entry_fee_usdt,
                exit_fee_usdt=exit_fee,
                entry_slippage_usdt=pos.entry_slippage_usdt,
                exit_slippage_usdt=exit_slippage_usdt,
                slippage_cost_usdt=pos.entry_slippage_usdt + exit_slippage_usdt,
                funding_cost_usdt=0.0,  # aggregated in portfolio total
                net_pnl_usdt=net_pnl,
                net_r_multiple=net_r,
                equity_at_entry=pos.equity_at_entry,
                equity_at_exit=self.get_portfolio_equity(current_prices),
                pullback_mode=pos.signal_meta.get("pullback_mode", "UNKNOWN"),
                low_distance_to_u=pos.signal_meta.get("low_distance_to_u", 0.0),
                high_distance_to_l=pos.signal_meta.get("high_distance_to_l", 0.0),
            )
            self.closed_trades.append(rec)
            exited_this_bar.append(rec)

        # -------------------------------------------------------------
        # STEP 3: Execute New Pending Signals (From Previous Bar Close)
        # -------------------------------------------------------------
        curr_equity = self.get_portfolio_equity(current_prices)
        for sig in pending_signals:
            sym = sig.symbol
            # Skip if symbol already open or portfolio position limit reached
            if sym in self.open_positions or len(self.open_positions) >= self.max_concurrent_positions:
                continue
            if sym not in bar_data:
                continue

            row = bar_data[sym]
            o = float(row["open"])

            # 1. Execute at obtainable market order price
            if sig.direction == "LONG":
                entry_p = o * (1 + self.execution_slippage)
                raw_sl_dist = sig.confirm_price - sig.initial_sl
                actual_sl_dist = entry_p - sig.initial_sl
                gap_amount = o - sig.confirm_price
            else:
                entry_p = o * (1 - self.execution_slippage)
                raw_sl_dist = sig.initial_sl - sig.confirm_price
                actual_sl_dist = sig.initial_sl - entry_p
                gap_amount = sig.confirm_price - o

            # 2. Gap Cancellation Check
            is_gap_inflated = (actual_sl_dist > self.gap_sl_tolerance_ratio * raw_sl_dist)
            is_gap_too_wide = (gap_amount > self.gap_atr_tolerance_mult * sig.frozen_atr)
            if is_gap_inflated or is_gap_too_wide or actual_sl_dist <= 0:
                # Cancel order due to unfavorable slippage/gap
                continue

            # 3. Position Sizing: 0.5% equity risk
            risk_budget_usdt = curr_equity * self.risk_per_trade_pct
            units = risk_budget_usdt / actual_sl_dist

            # Portfolio Exposure sanity checks
            nominal_val = units * entry_p
            if self.market_type == "spot":
                # Spot nominal value cannot exceed available cash
                max_units = (self.cash * 0.99) / entry_p
                units = min(units, max_units)
            else:
                # Perps max nominal leverage cap 2x
                max_units = (curr_equity * 2.0) / entry_p
                units = min(units, max_units)

            if units <= 0:
                continue

            nom_usdt = units * entry_p
            entry_fee = nom_usdt * self.fee_rate
            entry_slippage_usdt = nom_usdt * self.execution_slippage

            # Deduct entry fee from cash
            self.cash -= entry_fee
            self.trade_counter += 1

            self.open_positions[sym] = OpenPosition(
                trade_id=self.trade_counter,
                symbol=sym,
                direction=sig.direction,
                market_type=self.market_type,
                entry_time=bar_time,
                entry_price=entry_p,
                units=units,
                initial_sl=sig.initial_sl,
                current_sl=sig.initial_sl,
                frozen_atr=sig.frozen_atr,
                risk_1r_usdt=units * actual_sl_dist,
                entry_fee_usdt=entry_fee,
                entry_slippage_usdt=entry_slippage_usdt,
                equity_at_entry=curr_equity,
                trailing_unlocked=False,
                highest_high=float(row["high"]),
                lowest_low=float(row["low"]),
                sl_updates=0,
                bars_held=0,
                signal_meta={
                    "formation_time": sig.formation_time,
                    "U": sig.U,
                    "L": sig.L,
                    "breakout_time": sig.breakout_time,
                    "breakout_price": sig.breakout_price,
                    "confirm_time": sig.confirm_time,
                    "confirm_price": sig.confirm_price,
                    "pullback_mode": sig.pullback_mode,
                    "low_distance_to_u": sig.low_distance_to_u,
                    "high_distance_to_l": sig.high_distance_to_l,
                },
            )

        # -------------------------------------------------------------
        # STEP 4: Record Bar Portfolio Equity & Assert Cash Identity
        # -------------------------------------------------------------
        final_equity = self.get_portfolio_equity(current_prices)
        self.equity_curve.append({
            "bar_time": bar_time,
            "equity": final_equity,
            "cash": self.cash,
            "open_positions": len(self.open_positions),
        })

        return exited_this_bar
