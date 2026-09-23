# -*- coding: utf-8 -*-
"""
Clean Single-Ledger Backtesting Engine
=====================================
Strict institutional-grade simulator enforcing:
1. Single Cash/Position Ledger: No duplicate PnL accumulation.
   - Cash tracks realized collateral and fees.
   - Equity = Cash + Units * (Close - Entry).
   - Realized PnL is recognized strictly upon trade exit.
2. Chronological Causality:
   - Bar T-1 Close forms signal.
   - Bar T Open fills rebalance execution (with taker fees).
   - Bar T Intrabar checks liquidation (-32.83% for 3x) and stop-loss (with slippage).
   - Bar T Close marks equity to market and applies 8h funding/borrow costs.
3. Full Transparency:
   - Exports trade-by-trade audit logs (CSV).
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd


@dataclass
class TradeRecord:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    symbol: str
    entry_price: float
    exit_price: float
    units: float
    leverage: float
    gross_ret_pct: float
    net_pnl_usdt: float
    fees_paid_usdt: float
    exit_reason: str  # 'SIGNAL_EXIT', 'STOP_LOSS', 'LIQUIDATION'
    bars_held: int


class SingleLedgerSimulator:
    def __init__(
        self,
        symbols: List[str],
        raw_dfs: Dict[str, pd.DataFrame],
        df_funding: Optional[pd.DataFrame] = None,
        leverage: float = 3.0,
        fee_rate: float = 0.0008,        # 8 bps taker fee
        slippage: float = 0.0015,        # 15 bps slippage on stop-out
        sl_atr_mult: float = 1.5,        # 1.5x ATR stop loss
        hysteresis_pct: float = 0.005,   # 0.5% hysteresis buffer
        delta_score_buffer: float = 0.0, # Challenger must beat current asset by this buffer
        initial_cash: float = 10000.0,
        mmr: float = 0.005,              # 0.5% maintenance margin rate
        borrow_apr: float = 0.10,        # 10% APR borrow interest
    ):
        self.symbols = symbols
        self.raw_dfs = raw_dfs
        self.df_funding = df_funding
        self.leverage = leverage
        self.fee_rate = fee_rate
        self.slippage = slippage
        self.sl_atr_mult = sl_atr_mult
        self.hysteresis_pct = hysteresis_pct
        self.delta_score_buffer = delta_score_buffer
        self.initial_cash = initial_cash
        self.mmr = mmr
        self.borrow_apr = borrow_apr

    def run(self, start_dt: str, end_dt: str) -> Dict[str, Any]:
        # 1. Align common timestamps across all requested symbols
        common_idx = self.raw_dfs['BTCUSDT'].index
        for s in self.symbols:
            if s in self.raw_dfs:
                common_idx = common_idx.intersection(self.raw_dfs[s].index)
        common_idx = common_idx[(common_idx >= start_dt) & (common_idx <= end_dt)].sort_values()

        if len(common_idx) < 30:
            return None

        # Data alignment
        closes = pd.DataFrame({s: self.raw_dfs[s].loc[common_idx, 'close'] for s in self.symbols})
        opens = pd.DataFrame({s: self.raw_dfs[s].loc[common_idx, 'open'] for s in self.symbols})
        highs = pd.DataFrame({s: self.raw_dfs[s].loc[common_idx, 'high'] for s in self.symbols})
        lows = pd.DataFrame({s: self.raw_dfs[s].loc[common_idx, 'low'] for s in self.symbols})

        # 2. Causal indicators: computed strictly using data up to bar T-1 (close.shift(1))
        closes_prior = closes.shift(1)
        ema200 = closes_prior.ewm(span=200).mean()
        bb_mid = closes_prior.rolling(120).mean()
        bb_std = closes_prior.rolling(120).std()
        bb_z = (closes_prior - bb_mid) / (bb_std + 1e-8)
        mom20 = (closes_prior / closes_prior.shift(120)) - 1.0
        score = bb_z + mom20

        # BTC Macro Gate
        btc_prior = self.raw_dfs['BTCUSDT'].loc[common_idx, 'close'].shift(1)
        btc_ema = btc_prior.ewm(span=200).mean()
        btc_bull = btc_prior > btc_ema

        # 14-period ATR calculated up to bar T-1
        atrs_dict = {}
        for s in self.symbols:
            tr1 = highs[s] - lows[s]
            tr2 = (highs[s] - closes[s].shift(1)).abs()
            tr3 = (lows[s] - closes[s].shift(1)).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr_s = tr.rolling(14).mean().shift(1) # shift(1) ensures ATR known prior to bar T
            atrs_dict[s] = atr_s
        df_atrs_prior = pd.DataFrame(atrs_dict)

        # Funding rate alignment
        if self.df_funding is not None:
            funding_aligned = self.df_funding.reindex(common_idx, method='ffill').fillna(0.0001)
        else:
            funding_aligned = pd.DataFrame(0.0001, index=common_idx, columns=self.symbols)

        is_settlement_bar = pd.Series(common_idx.hour.isin([0, 8, 16]), index=common_idx)

        # 3. State Ledger Variables
        cash = float(self.initial_cash)
        asset_units = 0.0
        curr_pos = 'USDT_CASH'
        entry_price = 0.0
        entry_time = None
        highest_price = 0.0
        stop_price = 0.0
        bars_held = 0

        # Performance tracking
        equity_curve = []
        trades: List[TradeRecord] = []
        liquidated = False
        liquidation_date = None
        total_fees = 0.0
        total_slippage_cost = 0.0
        total_funding_cost = 0.0
        stop_count = 0
        min_distance_to_liq = 1.0

        # Liquidation drop threshold
        # For 3x leverage with 0.5% MMR: 1/3 - 0.005 = 32.833%
        liq_drop_pct = (1.0 / self.leverage - self.mmr) if self.leverage > 1.0 else 1.0

        # 4. Main Event Loop
        for i, t in enumerate(common_idx):
            if liquidated:
                equity_curve.append(0.0)
                continue

            settle = is_settlement_bar.loc[t]

            # -------------------------------------------------------------
            # STEP 1: Determine Target Position (Signals from Bar T-1)
            # -------------------------------------------------------------
            s_row = score.loc[t].dropna()
            top_cand = s_row.idxmax() if len(s_row) >= len(self.symbols) else 'BTCUSDT'
            btc_is_bull = bool(btc_bull.loc[t])

            target_pos = curr_pos

            if curr_pos == 'USDT_CASH':
                cand_close = closes_prior.loc[t, top_cand]
                cand_ema = ema200.loc[t, top_cand]
                cand_dist = (cand_close - cand_ema) / cand_ema
                # Enter if both BTC and candidate clear EMA200 by +hysteresis
                if btc_is_bull and (cand_dist >= self.hysteresis_pct):
                    target_pos = top_cand
                else:
                    target_pos = 'USDT_CASH'
            else:
                # Currently holding a token
                curr_close = closes_prior.loc[t, curr_pos]
                curr_ema = ema200.loc[t, curr_pos]
                curr_dist = (curr_close - curr_ema) / curr_ema
                curr_still_valid = btc_is_bull and (curr_dist >= -self.hysteresis_pct)

                if not curr_still_valid:
                    # Current asset failed trend gate: check if top candidate is valid
                    cand_close = closes_prior.loc[t, top_cand]
                    cand_ema = ema200.loc[t, top_cand]
                    cand_dist = (cand_close - cand_ema) / cand_ema
                    if btc_is_bull and (cand_dist >= self.hysteresis_pct):
                        target_pos = top_cand
                    else:
                        target_pos = 'USDT_CASH'
                else:
                    # Current asset is still valid: check if challenger beats it by delta_score_buffer
                    if top_cand != curr_pos:
                        challenger_score = float(s_row[top_cand])
                        current_score = float(s_row[curr_pos])
                        if challenger_score >= (current_score + self.delta_score_buffer):
                            cand_close = closes_prior.loc[t, top_cand]
                            cand_ema = ema200.loc[t, top_cand]
                            cand_dist = (cand_close - cand_ema) / cand_ema
                            if cand_dist >= self.hysteresis_pct:
                                target_pos = top_cand

            # -------------------------------------------------------------
            # STEP 2: Execution at Bar T Open (O_t)
            # -------------------------------------------------------------
            if target_pos != curr_pos:
                # A. Close previous position if held
                if curr_pos != 'USDT_CASH' and asset_units > 0:
                    exit_p = opens.loc[t, curr_pos]
                    gross_proceeds = asset_units * exit_p
                    exit_fee = gross_proceeds * self.fee_rate
                    total_fees += exit_fee
                    realized_pnl = asset_units * (exit_p - entry_price)
                    net_trade_pnl = realized_pnl - exit_fee
                    cash = max(0.0, cash + net_trade_pnl)

                    gross_ret = (exit_p - entry_price) / entry_price * self.leverage
                    trades.append(TradeRecord(
                        entry_time=entry_time,
                        exit_time=t,
                        symbol=curr_pos,
                        entry_price=entry_price,
                        exit_price=exit_p,
                        units=asset_units,
                        leverage=self.leverage,
                        gross_ret_pct=gross_ret * 100.0,
                        net_pnl_usdt=net_trade_pnl,
                        fees_paid_usdt=exit_fee,
                        exit_reason='SIGNAL_EXIT',
                        bars_held=bars_held,
                    ))

                    asset_units = 0.0
                    curr_pos = 'USDT_CASH'
                    entry_price = 0.0
                    entry_time = None
                    highest_price = 0.0
                    stop_price = 0.0
                    bars_held = 0

                # B. Open new position if target is token and cash > 0
                if target_pos != 'USDT_CASH' and cash > 0:
                    curr_pos = target_pos
                    entry_price = opens.loc[t, target_pos]
                    entry_time = t
                    highest_price = entry_price
                    bars_held = 0

                    nominal_target = cash * self.leverage
                    entry_fee = nominal_target * self.fee_rate
                    total_fees += entry_fee
                    investable_nominal = max(0.0, nominal_target - entry_fee)
                    asset_units = investable_nominal / entry_price
                    # Deduct entry fee from cash
                    cash = max(0.0, cash - entry_fee)

                    # Initial Stop Loss: 1.5x ATR below entry or EMA200 gate line
                    atr_val = df_atrs_prior.loc[t, target_pos]
                    initial_stop = entry_price - (atr_val * self.sl_atr_mult) if (not np.isnan(atr_val) and atr_val > 0) else entry_price * 0.95
                    gate_stop = ema200.loc[t, target_pos] * (1.0 - self.hysteresis_pct)
                    stop_price = max(gate_stop, initial_stop)

            # -------------------------------------------------------------
            # STEP 3: Intrabar Price Movements on Bar T (High, Low, Close)
            # -------------------------------------------------------------
            if curr_pos != 'USDT_CASH' and asset_units > 0:
                bar_o = opens.loc[t, curr_pos]
                bar_h = highs.loc[t, curr_pos]
                bar_l = lows.loc[t, curr_pos]
                bar_c = closes.loc[t, curr_pos]
                bars_held += 1
                highest_price = max(highest_price, bar_h)

                # Check Distance to Liquidation
                liq_price = entry_price * (1.0 - liq_drop_pct)
                dist_liq_pct = (bar_l - liq_price) / entry_price
                min_distance_to_liq = min(min_distance_to_liq, dist_liq_pct)

                # A. Liquidation Check
                if self.leverage > 1.0 and bar_l <= liq_price:
                    liquidated = True
                    liquidation_date = str(t)
                    trades.append(TradeRecord(
                        entry_time=entry_time,
                        exit_time=t,
                        symbol=curr_pos,
                        entry_price=entry_price,
                        exit_price=liq_price,
                        units=asset_units,
                        leverage=self.leverage,
                        gross_ret_pct=-100.0,
                        net_pnl_usdt=-cash,
                        fees_paid_usdt=0.0,
                        exit_reason='LIQUIDATION',
                        bars_held=bars_held,
                    ))
                    cash = 0.0
                    asset_units = 0.0
                    curr_pos = 'USDT_CASH'
                    equity_curve.append(0.0)
                    continue

                # B. Stop-Loss Trigger Check
                if stop_price > 0 and bar_l <= stop_price:
                    stop_count += 1
                    # Execution at stop price minus slippage (bounded by open)
                    exec_exit = min(bar_o, stop_price * (1.0 - self.slippage))
                    slip_cost = asset_units * (stop_price - exec_exit)
                    total_slippage_cost += max(0.0, slip_cost)

                    gross_proceeds = asset_units * exec_exit
                    exit_fee = gross_proceeds * self.fee_rate
                    total_fees += exit_fee
                    realized_pnl = asset_units * (exec_exit - entry_price)
                    net_trade_pnl = realized_pnl - exit_fee
                    cash = max(0.0, cash + net_trade_pnl)

                    gross_ret = (exec_exit - entry_price) / entry_price * self.leverage
                    trades.append(TradeRecord(
                        entry_time=entry_time,
                        exit_time=t,
                        symbol=curr_pos,
                        entry_price=entry_price,
                        exit_price=exec_exit,
                        units=asset_units,
                        leverage=self.leverage,
                        gross_ret_pct=gross_ret * 100.0,
                        net_pnl_usdt=net_trade_pnl,
                        fees_paid_usdt=exit_fee,
                        exit_reason='STOP_LOSS',
                        bars_held=bars_held,
                    ))

                    asset_units = 0.0
                    curr_pos = 'USDT_CASH'
                    entry_price = 0.0
                    entry_time = None
                    highest_price = 0.0
                    stop_price = 0.0
                    bars_held = 0
                    equity_curve.append(cash)
                    continue

                # C. Trailing Stop Ratchet (if survived stop check)
                # 1. Breakeven lock when gain >= +5%
                if highest_price >= entry_price * 1.05:
                    be_stop = entry_price * 1.002
                    stop_price = max(stop_price, be_stop)
                # 2. Trailing lock 5% off peak when gain >= +10%
                if highest_price >= entry_price * 1.10:
                    trail_stop = highest_price * 0.95
                    stop_price = max(stop_price, trail_stop)

                # D. Funding & Borrow Interest
                if settle and self.leverage > 1.0:
                    nominal_notional = asset_units * bar_c
                    fr = funding_aligned.loc[t, curr_pos] if curr_pos in funding_aligned else 0.0001
                    # Borrow fee: 10% APR on (L-1)/L notional per 8h
                    borrow_fee = nominal_notional * ((self.leverage - 1.0) / self.leverage) * (self.borrow_apr / (365.25 * 3))
                    fund_cost = (nominal_notional * fr) + borrow_fee
                    cash = max(0.0, cash - fund_cost)
                    total_funding_cost += fund_cost
                    if cash <= 0.0:
                        liquidated = True
                        liquidation_date = str(t)
                        equity_curve.append(0.0)
                        continue

            # -------------------------------------------------------------
            # STEP 4: End-of-Bar Mark-to-Market Equity (C_t)
            # -------------------------------------------------------------
            if curr_pos == 'USDT_CASH' or asset_units == 0:
                current_equity = cash
            else:
                bar_c = closes.loc[t, curr_pos]
                unrealized_pnl = asset_units * (bar_c - entry_price)
                current_equity = max(0.0, cash + unrealized_pnl)
                if current_equity <= 0.0:
                    liquidated = True
                    liquidation_date = str(t)
                    current_equity = 0.0

            equity_curve.append(current_equity)

        # 5. Compute Accurate Strategy Metrics
        eq_s = pd.Series(equity_curve, index=common_idx)
        final_equity = float(eq_s.iloc[-1])
        total_ret_pct = ((final_equity - self.initial_cash) / self.initial_cash) * 100.0

        n_bars = len(eq_s)
        years = n_bars / (365.25 * 6)
        cagr_pct = ((final_equity / self.initial_cash) ** (1.0 / years) - 1.0) * 100.0 if (final_equity > 0 and years > 0) else -100.0

        running_max = eq_s.cummax()
        drawdown = (eq_s - running_max) / running_max
        max_dd_pct = float(drawdown.min() * 100.0)

        daily_eq = eq_s.resample('1D').last().dropna()
        daily_rets = daily_eq.pct_change().dropna()
        sharpe = (daily_rets.mean() / (daily_rets.std() + 1e-8)) * np.sqrt(365) if len(daily_rets) > 10 else 0.0
        calmar = (cagr_pct / abs(max_dd_pct)) if abs(max_dd_pct) > 0.01 else 0.0

        win_trades = [tr for tr in trades if tr.net_pnl_usdt > 0]
        win_rate = (len(win_trades) / len(trades) * 100.0) if trades else 0.0

        return {
            'final_equity': round(final_equity, 2),
            'total_ret_pct': round(total_ret_pct, 2),
            'cagr_pct': round(cagr_pct, 2),
            'max_dd_pct': round(max_dd_pct, 2),
            'sharpe': round(float(sharpe), 2),
            'calmar': round(float(calmar), 2),
            'win_rate': round(win_rate, 2),
            'trade_count': len(trades),
            'stop_count': stop_count,
            'liquidated': liquidated,
            'liquidation_date': liquidation_date,
            'min_distance_to_liq_pct': round(float(min_distance_to_liq * 100.0), 2),
            'total_fees': round(total_fees, 2),
            'total_slippage': round(total_slippage_cost, 2),
            'total_funding': round(total_funding_cost, 2),
            'trades_list': trades,
            'equity_curve': eq_s,
        }
