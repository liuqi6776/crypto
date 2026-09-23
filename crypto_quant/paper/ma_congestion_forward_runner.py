# -*- coding: utf-8 -*-
"""
MA Congestion Breakout & Pullback Forward Paper Tracking Runner
均线密集突破后回踩前瞻纸面实测运行器
=============================================================
Provides real-time causal paper execution and ledger management for frozen MA Congestion strategy:
1. Frozen parameters: 15m EMA (20, 50, 100), EMA200 trend filter, ATR14.
2. Independent starting cash: 10,000 USDT.
3. 0.5% equity risk sizing per trade, max 2 concurrent positions.
4. Records causal physical timestamps (candle_close <= data_arrival <= decision <= quote_arrival).
5. Segregated live ledger: data/forward_tracking/ma_congestion_forward_ledger.csv.
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from crypto_quant.ma_congestion.state_machine import (
    MACongestionStateMachine,
    TradeSignal,
    compute_indicators,
)
from crypto_quant.backtest.intraday_risk_engine import (
    IntradayRiskLedgerSimulator,
    IntradayTradeRecord,
)

CORE4_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]


class MACongestionForwardRunner:
    """
    Operational Forward Paper Runner for MA Congestion Strategy.
    """
    def __init__(
        self,
        output_dir: str = "data/forward_tracking",
        initial_cash: float = 10000.0,
        symbols: List[str] = CORE4_SYMBOLS,
        interval: str = "15m",
        ma_type: str = "EMA",
        fee_rate: float = 0.0008,
        execution_slippage: float = 0.0005,
        stop_slippage: float = 0.0015,
    ):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.initial_cash = initial_cash
        self.symbols = symbols
        self.interval = interval
        self.ma_type = ma_type

        self.ledger_file = os.path.join(output_dir, "ma_congestion_forward_ledger.csv")
        self.status_file = os.path.join(output_dir, "ma_congestion_forward_status.json")

        self.simulator = IntradayRiskLedgerSimulator(
            symbols=self.symbols,
            initial_cash=self.initial_cash,
            risk_per_trade_pct=0.005,
            max_concurrent_positions=2,
            fee_rate=fee_rate,
            execution_slippage=execution_slippage,
            stop_slippage=stop_slippage,
            max_holding_bars=32,
            market_type="spot",
            exit_rule="DYNAMIC_TRAILING",
        )

        self.state_machines = {
            sym: MACongestionStateMachine(symbol=sym, direction="LONG")
            for sym in self.symbols
        }
        self.pending_signals: List[TradeSignal] = []
        self.processed_bars: List[str] = []

        self._load_state()

    def _load_state(self):
        """Load persisted forward status if exists."""
        if os.path.exists(self.status_file):
            try:
                with open(self.status_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.processed_bars = data.get("processed_bars", [])
            except Exception:
                pass

    def _save_state(self, latest_bar_t: pd.Timestamp):
        """Persist forward status."""
        state_data = {
            "version": "1.0.0",
            "strategy": "MA_CONGESTION_BREAKOUT_PULLBACK_15M_EMA",
            "last_processed_bar": str(latest_bar_t),
            "processed_bar_count": len(self.processed_bars),
            "cash": self.simulator.cash,
            "open_positions": {
                s: {
                    "entry_price": pos.entry_price,
                    "units": pos.units,
                    "current_sl": pos.current_sl,
                    "bars_held": pos.bars_held,
                }
                for s, pos in self.simulator.open_positions.items()
            },
            "closed_trades_count": len(self.simulator.closed_trades),
        }
        with open(self.status_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2)

    def process_new_bar(
        self,
        bar_time: pd.Timestamp,
        klines_dict: Dict[str, pd.DataFrame],
        quote_fetcher: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Process incoming closed bar across all symbols causally.
        """
        bar_str = str(bar_time)
        if bar_str in self.processed_bars:
            return {"status": "SKIPPED_DUPLICATE", "bar_time": bar_str}

        # 1. Compute indicators
        ind_data = {}
        for sym in self.symbols:
            if sym in klines_dict:
                df_ind = compute_indicators(klines_dict[sym], ma_type=self.ma_type)
                ind_data[sym] = df_ind.loc[bar_time]

        # 2. Process simulator exits and entries
        exited_trades = self.simulator.process_bar(
            bar_time=bar_time,
            bar_data=ind_data,
            pending_signals=self.pending_signals,
        )

        # 3. Generate new signals on completed bar
        new_signals = []
        for sym, sm in self.state_machines.items():
            if sym in ind_data:
                sig = sm.feed_bar(bar_time, ind_data[sym])
                if sig:
                    new_signals.append(sig)

        self.pending_signals = new_signals
        self.processed_bars.append(bar_str)
        self._save_state(bar_time)

        return {
            "status": "PROCESSED",
            "bar_time": bar_str,
            "exited_trades": len(exited_trades),
            "new_signals": len(new_signals),
            "open_positions": len(self.simulator.open_positions),
            "cash": round(self.simulator.cash, 2),
        }
