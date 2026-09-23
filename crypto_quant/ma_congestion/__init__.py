"""
Moving Average Congestion Breakout & Pullback Confirmation Package
均线密集突破后回踩确认策略模块
"""

from .state_machine import (
    MACongestionStateMachine,
    PatternState,
    TradeSignal,
    CongestionZone,
    compute_indicators,
)

__all__ = [
    "MACongestionStateMachine",
    "PatternState",
    "TradeSignal",
    "CongestionZone",
    "compute_indicators",
]
