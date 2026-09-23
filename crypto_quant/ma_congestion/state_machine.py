# -*- coding: utf-8 -*-
"""
Moving Average Congestion Breakout & Pullback Finite-State Machine
均线密集突破后回踩确认确定性有限状态机
==================================================================
Strictly causal, bar-by-bar deterministic state machine for pattern detection:
1. Trend Environment: Close > MA200 and MA200 > MA200[t-4] (Long) or mirror (Short).
2. Congestion Formation: 3 consecutive bars where max(MA20, 50, 100) - min(MA20, 50, 100) <= 0.5 * ATR14.
   Freezes immutable U, L, and ATR_frozen at trigger bar.
3. Breakout Window: Within 6 bars, Close > U + 0.5 * ATR_frozen.
4. Pullback Window: Within 8 bars after breakout, Low touches U + 0.1 * ATR_frozen,
   holds above L - 0.1 * ATR_frozen, and Close > U.
   Invalidation: Any breach of Low < L - 0.1 * ATR_frozen immediately voids pattern.
5. Exit / Risk Parameters: Initial SL = L - 0.2 * ATR_frozen.
   Dynamic Trailing Stop activated after +1R, ratcheting from next bar to max(SL, High_max - 2 * ATR14).
   Max holding duration: 8 hours.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd


class PatternState(Enum):
    IDLE = "IDLE"
    CONGESTION_FORMED = "CONGESTION_FORMED"
    AWAITING_PULLBACK = "AWAITING_PULLBACK"
    CONFIRMED_SIGNAL = "CONFIRMED_SIGNAL"


@dataclass
class CongestionZone:
    formation_bar: pd.Timestamp
    formation_idx: int
    U: float
    L: float
    frozen_atr: float
    direction: str  # 'LONG' or 'SHORT'


@dataclass
class TradeSignal:
    symbol: str
    direction: str  # 'LONG' or 'SHORT'
    signal_time: pd.Timestamp       # Close time of confirmation candle
    confirm_price: float           # Close of confirmation candle
    initial_sl: float              # L - 0.2 * ATR_frozen (Long) or U + 0.2 * ATR_frozen (Short)
    frozen_atr: float
    formation_time: pd.Timestamp
    breakout_time: pd.Timestamp
    confirm_time: pd.Timestamp
    U: float
    L: float
    breakout_price: float
    pattern_duration_bars: int


def compute_indicators(
    df: pd.DataFrame,
    ma_type: str = "EMA",
    ma_periods: Tuple[int, int, int, int] = (20, 50, 100, 200),
    atr_period: int = 14,
) -> pd.DataFrame:
    """
    Compute moving averages and ATR strictly on closed bars.
    严格在已闭合 K 线上计算均线族与 ATR。
    """
    res = df.copy()
    p20, p50, p100, p200 = ma_periods

    if ma_type.upper() == "EMA":
        res["ma20"] = res["close"].ewm(span=p20, adjust=False).mean()
        res["ma50"] = res["close"].ewm(span=p50, adjust=False).mean()
        res["ma100"] = res["close"].ewm(span=p100, adjust=False).mean()
        res["ma200"] = res["close"].ewm(span=p200, adjust=False).mean()
    elif ma_type.upper() == "SMA":
        res["ma20"] = res["close"].rolling(window=p20).mean()
        res["ma50"] = res["close"].rolling(window=p50).mean()
        res["ma100"] = res["close"].rolling(window=p100).mean()
        res["ma200"] = res["close"].rolling(window=p200).mean()
    else:
        raise ValueError(f"Unsupported ma_type: {ma_type}. Use 'EMA' or 'SMA'.")

    # True Range & ATR14
    prev_close = res["close"].shift(1)
    tr1 = res["high"] - res["low"]
    tr2 = (res["high"] - prev_close).abs()
    tr3 = (res["low"] - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    res["tr"] = tr
    # Wilder's smoothing or EMA for ATR
    res["atr14"] = tr.ewm(span=atr_period, adjust=False).mean()

    # 4-bar slope for MA200
    res["ma200_slope_4"] = res["ma200"] - res["ma200"].shift(4)

    # Moving average spread across 20, 50, 100
    ma_max = pd.concat([res["ma20"], res["ma50"], res["ma100"]], axis=1).max(axis=1)
    ma_min = pd.concat([res["ma20"], res["ma50"], res["ma100"]], axis=1).min(axis=1)
    res["ma_spread"] = ma_max - ma_min
    res["ma_spread_ratio"] = res["ma_spread"] / (res["atr14"] + 1e-9)

    return res


class MACongestionStateMachine:
    """
    Finite-State Pattern Machine for Moving Average Congestion Breakout & Pullback.
    均线密集突破后回踩确定性状态机。
    """
    def __init__(
        self,
        symbol: str,
        direction: str = "LONG",
        breakout_max_bars: int = 6,
        pullback_max_bars: int = 8,
    ):
        self.symbol = symbol
        self.direction = direction.upper()
        self.breakout_max_bars = breakout_max_bars
        self.pullback_max_bars = pullback_max_bars

        # State tracking
        self.state = PatternState.IDLE
        self.current_zone: Optional[CongestionZone] = None
        self.consecutive_congestion_bars: int = 0
        self.breakout_bar: Optional[pd.Timestamp] = None
        self.breakout_price: Optional[float] = None
        self.bars_since_formation: int = 0
        self.bars_since_breakout: int = 0

    def reset(self):
        """Reset state machine to IDLE."""
        self.state = PatternState.IDLE
        self.current_zone = None
        self.consecutive_congestion_bars = 0
        self.breakout_bar = None
        self.breakout_price = None
        self.bars_since_formation = 0
        self.bars_since_breakout = 0

    def feed_bar(
        self,
        bar_time: pd.Timestamp,
        row: pd.Series,
    ) -> Optional[TradeSignal]:
        """
        Process a single completed closed bar.
        处理单根已闭合 K 线，返回可能触发的入场信号。
        """
        close = float(row["close"])
        high = float(row["high"])
        low = float(row["low"])
        ma20 = float(row["ma20"])
        ma50 = float(row["ma50"])
        ma100 = float(row["ma100"])
        ma200 = float(row["ma200"])
        ma200_slope_4 = float(row["ma200_slope_4"])
        atr14 = float(row["atr14"])

        # Check basic data readiness
        if np.isnan(ma200) or np.isnan(ma200_slope_4) or np.isnan(atr14):
            return None

        # 1. Evaluate Trend Environment
        if self.direction == "LONG":
            trend_valid = (close > ma200) and (ma200_slope_4 > 0)
        else:
            trend_valid = (close < ma200) and (ma200_slope_4 < 0)

        # 2. Check 3-MA Congestion condition on this bar
        curr_ma_spread = max(ma20, ma50, ma100) - min(ma20, ma50, ma100)
        is_congested = (curr_ma_spread <= 0.5 * atr14)

        if is_congested:
            self.consecutive_congestion_bars += 1
        else:
            self.consecutive_congestion_bars = 0

        # State Dispatcher
        if self.state == PatternState.IDLE:
            # If 3 consecutive congested bars and trend is valid: form congestion zone!
            if self.consecutive_congestion_bars >= 3 and trend_valid:
                U = max(ma20, ma50, ma100)
                L = min(ma20, ma50, ma100)
                self.current_zone = CongestionZone(
                    formation_bar=bar_time,
                    formation_idx=0,
                    U=U,
                    L=L,
                    frozen_atr=atr14,
                    direction=self.direction,
                )
                self.state = PatternState.CONGESTION_FORMED
                self.bars_since_formation = 0
            return None

        elif self.state == PatternState.CONGESTION_FORMED:
            self.bars_since_formation += 1
            z = self.current_zone

            # Check Breakout condition
            if self.direction == "LONG":
                has_breakout = (close > z.U + 0.5 * z.frozen_atr)
            else:
                has_breakout = (close < z.L - 0.5 * z.frozen_atr)

            if has_breakout:
                self.breakout_bar = bar_time
                self.breakout_price = close
                self.state = PatternState.AWAITING_PULLBACK
                self.bars_since_breakout = 0
                return None

            # Check Breakout Expiration (max 6 bars)
            if self.bars_since_formation >= self.breakout_max_bars:
                self.reset()
                # Check if current bar immediately initiates a new congestion
                if self.consecutive_congestion_bars >= 3 and trend_valid:
                    U = max(ma20, ma50, ma100)
                    L = min(ma20, ma50, ma100)
                    self.current_zone = CongestionZone(
                        formation_bar=bar_time,
                        formation_idx=0,
                        U=U,
                        L=L,
                        frozen_atr=atr14,
                        direction=self.direction,
                    )
                    self.state = PatternState.CONGESTION_FORMED
                    self.bars_since_formation = 0
            return None

        elif self.state == PatternState.AWAITING_PULLBACK:
            self.bars_since_breakout += 1
            z = self.current_zone

            # 1. Invalidation Check FIRST!
            # Long: any breach of Low < L - 0.1 * ATR_frozen immediately voids pattern
            # Short: any breach of High > U + 0.1 * ATR_frozen immediately voids pattern
            if self.direction == "LONG":
                is_invalidated = (low < z.L - 0.1 * z.frozen_atr)
            else:
                is_invalidated = (high > z.U + 0.1 * z.frozen_atr)

            if is_invalidated:
                self.reset()
                return None

            # 2. Check Confirmation condition
            confirmed = False
            if self.direction == "LONG":
                # Low touches U + 0.1 * ATR, holds above L - 0.1 * ATR, and Close > U
                touch_tolerance = (low <= z.U + 0.1 * z.frozen_atr)
                holds_lower = (low >= z.L - 0.1 * z.frozen_atr)
                reclaims_u = (close > z.U)
                if touch_tolerance and holds_lower and reclaims_u:
                    confirmed = True
            else:
                # Short: High touches L - 0.1 * ATR, holds below U + 0.1 * ATR, and Close < L
                touch_tolerance = (high >= z.L - 0.1 * z.frozen_atr)
                holds_upper = (high <= z.U + 0.1 * z.frozen_atr)
                reclaims_l = (close < z.L)
                if touch_tolerance and holds_upper and reclaims_l:
                    confirmed = True

            if confirmed:
                # Calculate initial Stop Loss
                if self.direction == "LONG":
                    sl_init = z.L - 0.2 * z.frozen_atr
                else:
                    sl_init = z.U + 0.2 * z.frozen_atr

                sig = TradeSignal(
                    symbol=self.symbol,
                    direction=self.direction,
                    signal_time=bar_time,
                    confirm_price=close,
                    initial_sl=sl_init,
                    frozen_atr=z.frozen_atr,
                    formation_time=z.formation_bar,
                    breakout_time=self.breakout_bar,
                    confirm_time=bar_time,
                    U=z.U,
                    L=z.L,
                    breakout_price=self.breakout_price,
                    pattern_duration_bars=self.bars_since_formation + self.bars_since_breakout,
                )
                self.reset()
                return sig

            # 3. Check Pullback Expiration (max 8 bars)
            if self.bars_since_breakout >= self.pullback_max_bars:
                self.reset()
                return None

        return None
