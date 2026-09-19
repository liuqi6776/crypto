# -*- coding: utf-8 -*-
"""
Leverage Model & Liquidation Risk Engine (ETH 3x Strategy)
==========================================================
Provides precision calculations for 3x leveraged perpetual futures trading:
- Nominal exposure scaling (3.0x Equity)
- Isolated margin requirement & Maintenance Margin Rate (MMR)
- Estimated liquidation price and safety buffer against trailing stops
- Leveraged PnL and return tracking
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class LeveragedPositionMetrics:
    leverage: float
    base_equity_usdt: float
    nominal_position_usdt: float
    entry_price: float
    current_price: float
    highest_price: float
    trailing_stop_price: float
    atr: float
    liquidation_price: float
    distance_to_liq_pct: float
    distance_to_stop_pct: float
    safety_buffer_pct: float
    unrealized_pnl_usdt: float
    unrealized_roe_pct: float
    is_safe: bool


class LeverageModel:
    """
    Computes institutional risk metrics for ETH leveraged perpetual futures.
    Default: 3.0x leverage.
    """

    def __init__(self, default_leverage: float = 3.0, mmr: float = 0.005):
        """
        :param default_leverage: Target leverage multiplier (e.g. 3.0)
        :param mmr: Maintenance Margin Rate (Binance ETHUSDT tier 1 is 0.5% = 0.005)
        """
        self.default_leverage = default_leverage
        self.mmr = mmr

    def calculate_liquidation_price(
        self, entry_price: float, leverage: Optional[float] = None
    ) -> float:
        """
        Calculates estimated isolated liquidation price for a LONG position:
        LiqPrice = EntryPrice * (1 - (1 / Leverage) + MMR)
        """
        lev = leverage or self.default_leverage
        if lev <= 1.0:
            return 0.0
        liq_price = entry_price * (1.0 - (1.0 / lev) + self.mmr)
        return max(0.0, liq_price)

    def compute_metrics(
        self,
        base_equity_usdt: float,
        entry_price: Optional[float],
        current_price: float,
        highest_price: Optional[float],
        trailing_stop_price: Optional[float],
        atr: float,
        is_in_position: bool,
        leverage: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Generates full risk and position metrics for dashboard & alerting.
        """
        lev = leverage or self.default_leverage

        if not is_in_position or not entry_price:
            return {
                "leverage": lev,
                "base_equity_usdt": round(base_equity_usdt, 2),
                "nominal_position_usdt": 0.0,
                "entry_price": None,
                "current_price": round(current_price, 2),
                "highest_price": None,
                "trailing_stop_price": None,
                "liquidation_price": None,
                "distance_to_liq_pct": None,
                "distance_to_stop_pct": None,
                "safety_buffer_pct": None,
                "unrealized_pnl_usdt": 0.0,
                "unrealized_roe_pct": 0.0,
                "is_safe": True,
                "mmr_pct": self.mmr * 100.0,
            }

        high_p = highest_price or max(entry_price, current_price)
        stop_p = trailing_stop_price or (high_p - 3.0 * atr)
        nominal_pos = base_equity_usdt * lev
        liq_price = self.calculate_liquidation_price(entry_price, lev)

        # Distances from current price
        dist_to_liq_pct = ((current_price - liq_price) / current_price) * 100.0
        dist_to_stop_pct = ((current_price - stop_p) / current_price) * 100.0

        # Safety Buffer: Distance between Trailing Stop and Liquidation Price
        safety_buffer_pct = ((stop_p - liq_price) / entry_price) * 100.0

        # PnL calculations (magnified by leverage)
        price_return = (current_price - entry_price) / entry_price
        unrealized_roe_pct = price_return * lev * 100.0
        unrealized_pnl_usdt = base_equity_usdt * (unrealized_roe_pct / 100.0)

        # Invariant: Trailing stop MUST be strictly above liquidation price
        is_safe = stop_p > (liq_price + 1.0 * atr)

        return {
            "leverage": lev,
            "base_equity_usdt": round(base_equity_usdt, 2),
            "nominal_position_usdt": round(nominal_pos, 2),
            "entry_price": round(entry_price, 2),
            "current_price": round(current_price, 2),
            "highest_price": round(high_p, 2),
            "trailing_stop_price": round(stop_p, 2),
            "liquidation_price": round(liq_price, 2),
            "distance_to_liq_pct": round(dist_to_liq_pct, 2),
            "distance_to_stop_pct": round(dist_to_stop_pct, 2),
            "safety_buffer_pct": round(safety_buffer_pct, 2),
            "unrealized_pnl_usdt": round(unrealized_pnl_usdt, 2),
            "unrealized_roe_pct": round(unrealized_roe_pct, 2),
            "is_safe": is_safe,
            "mmr_pct": self.mmr * 100.0,
        }
