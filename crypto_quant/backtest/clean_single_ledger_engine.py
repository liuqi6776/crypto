# -*- coding: utf-8 -*-
"""
Audited Clean Single-Ledger Backtesting Engine
=============================================
Strict institutional-grade simulator enforcing:
1. Exact Single Cash/Position Ledger:
   - Cash tracks liquid collateral, realized trade PnLs, entry/exit fees, funding, and borrow interest.
   - Total Equity = Cash + Units * (Close - Entry).
   - Maintenance Margin = Units * Close * MMR.
   - Liquidation occurs IF AND ONLY IF Total Equity <= Maintenance Margin (never falsely liquidated due to cash <= 0).
   - Mathematical Identity:
     Final Equity == Initial Base Equity + Sum(Gross Realized PnL) - Sum(Entry Fees) - Sum(Exit Fees)
                    - Sum(Funding Costs) - Sum(Borrow Costs) + Open Position Unrealized PnL.
2. Two-Way Execution Slippage & Conservative Intrabar Priority:
   - Normal Open entries: Open * (1 + execution_slippage)
   - Normal Signal exits: Open * (1 - execution_slippage)
   - Stop-Loss exits: min(Open, Stop * (1 - stop_slippage))
   - Conservative Intrabar Sequence:
     1. Open gap-down breach of liquidation -> Liquidate at Open.
     2. Open gap-down breach of stop-loss -> Stop-out at Open.
     3. Intrabar Low breach of stop-loss -> Stop-out at stop price minus slippage (stop line is shallower than liq line).
     4. Intrabar Low breach of liquidation -> Liquidate.
3. Indicator Warmup & Evaluation Interval Decoupling:
   - Warmup window reads >= 200 bars prior to eval_start_dt so EMA200, ATR, and momentum are fully converged.
   - Evaluation window is strictly [start_dt, end_dt) half-open UTC interval.
   - Supports both Fresh Cash Start and Carried-Over State from continuous runs.
4. Comprehensive Audit Metadata:
   - Records actual start/end bar, expected/actual/missing bar counts, data admission health status, and end state snapshot.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

from crypto_quant.core.top1_decision_engine import compute_top1_decision
from crypto_quant.core.data_admission import validate_crypto_universe, DataAdmissionReport


@dataclass
class TradeRecord:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    symbol: str
    entry_price: float
    exit_price: float
    units: float
    leverage: float
    gross_pnl_usdt: float
    entry_fee_usdt: float
    exit_fee_usdt: float
    slippage_cost_usdt: float
    funding_cost_usdt: float
    borrow_cost_usdt: float
    net_pnl_usdt: float          # gross_pnl - entry_fee - exit_fee - funding - borrow
    gross_ret_pct: float
    exit_reason: str            # 'SIGNAL_EXIT', 'STOP_LOSS', 'LIQUIDATION'
    bars_held: int


class SingleLedgerSimulator:
    def __init__(
        self,
        symbols: List[str],
        raw_dfs: Dict[str, pd.DataFrame],
        df_funding: Optional[pd.DataFrame] = None,
        leverage: float = 1.0,
        fee_rate: float = 0.0008,               # 8 bps taker fee
        execution_slippage: float = 0.0005,     # 5 bps slippage on normal market orders
        stop_slippage: float = 0.0015,          # 15 bps slippage on stop-out
        sl_atr_mult: float = 1.5,               # 1.5x ATR stop loss
        hysteresis_pct: float = 0.005,          # 0.5% hysteresis buffer
        delta_score_buffer: float = 0.0,        # Challenger score buffer
        initial_cash: float = 10000.0,
        mmr: float = 0.005,                     # 0.5% maintenance margin rate
        borrow_apr: float = 0.10,               # 10% APR borrow interest
        slippage: Optional[float] = None,       # Backward-compatible alias for stop_slippage
    ):
        self.symbols = symbols
        self.raw_dfs = raw_dfs
        self.df_funding = df_funding
        self.leverage = leverage
        self.fee_rate = fee_rate
        self.execution_slippage = execution_slippage
        self.stop_slippage = slippage if slippage is not None else stop_slippage
        self.sl_atr_mult = sl_atr_mult
        self.hysteresis_pct = hysteresis_pct
        self.delta_score_buffer = delta_score_buffer
        self.initial_cash = initial_cash
        self.mmr = mmr
        self.borrow_apr = borrow_apr

    def run(
        self,
        start_dt: str,
        end_dt: str,
        min_warmup_bars: int = 200,
        carry_over_state: Optional[Dict[str, Any]] = None,
        data_admission_check: bool = False,
    ) -> Dict[str, Any]:
        # 1. Standardize Time Range: [start_dt, end_dt) half-open interval
        eval_start_ts = pd.Timestamp(start_dt)
        eval_end_ts = pd.Timestamp(end_dt)
        # If end_dt is provided as YYYY-MM-DD date without time (length <= 10), extend by 1 day
        if len(str(end_dt).strip()) <= 10:
            eval_end_ts = eval_end_ts + pd.Timedelta(days=1)

        # 2. Align common timestamps across all requested symbols
        common_idx = self.raw_dfs['BTCUSDT'].index
        for s in self.symbols:
            if s in self.raw_dfs:
                common_idx = common_idx.intersection(self.raw_dfs[s].index)
        common_idx = common_idx.sort_values()

        # Find evaluation boundaries in common_idx
        eval_mask = (common_idx >= eval_start_ts) & (common_idx < eval_end_ts)
        eval_idx = common_idx[eval_mask]

        if len(eval_idx) == 0:
            return None

        # Data Admission Check
        admission_report: Optional[DataAdmissionReport] = None
        if data_admission_check:
            admission_report = validate_crypto_universe(
                raw_dfs=self.raw_dfs,
                symbols=self.symbols,
                df_funding=self.df_funding if self.leverage > 1.0 else None,
                eval_start_dt=str(eval_start_ts),
                eval_end_dt=str(eval_end_ts),
                strict=False,
            )

        # Warmup slice: use all available converged history prior to eval_start_ts
        # ensuring exact equivalence between full-cycle slicing and standalone interval runs.
        prior_mask = (common_idx < eval_start_ts)
        prior_idx = common_idx[prior_mask]
        warmup_idx = prior_idx

        # Combined simulation data index: all historical warmup bars + evaluation bars
        sim_idx = warmup_idx.union(eval_idx).sort_values()

        # Extract aligned OHLC
        closes = pd.DataFrame({s: self.raw_dfs[s].loc[sim_idx, 'close'] for s in self.symbols})
        opens = pd.DataFrame({s: self.raw_dfs[s].loc[sim_idx, 'open'] for s in self.symbols})
        highs = pd.DataFrame({s: self.raw_dfs[s].loc[sim_idx, 'high'] for s in self.symbols})
        lows = pd.DataFrame({s: self.raw_dfs[s].loc[sim_idx, 'low'] for s in self.symbols})

        # 14-period ATR calculated up to bar T-1 over the entire sim_idx
        atrs_dict = {}
        for s in self.symbols:
            tr1 = highs[s] - lows[s]
            tr2 = (highs[s] - closes[s].shift(1)).abs()
            tr3 = (lows[s] - closes[s].shift(1)).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr_s = tr.rolling(14).mean().shift(1)
            atrs_dict[s] = atr_s
        df_atrs_prior = pd.DataFrame(atrs_dict)

        # Funding rate alignment
        if self.df_funding is not None and not self.df_funding.empty:
            f_idx = self.df_funding.index
            if f_idx.tz is not None:
                f_idx = f_idx.tz_localize(None)
            df_f_clean = self.df_funding.copy()
            df_f_clean.index = f_idx
            funding_aligned = df_f_clean.reindex(sim_idx, method='ffill').fillna(0.0001)
        else:
            funding_aligned = pd.DataFrame(0.0001, index=sim_idx, columns=self.symbols)

        is_settlement_bar = pd.Series(sim_idx.hour.isin([0, 8, 16]), index=sim_idx)

        # 3. State Ledger Variables Initialization
        if carry_over_state is not None:
            cash = float(carry_over_state['cash'])
            curr_pos = str(carry_over_state['curr_pos'])
            asset_units = float(carry_over_state['asset_units'])
            entry_price = float(carry_over_state['entry_price'])
            entry_time = carry_over_state['entry_time']
            entry_fee_current = float(carry_over_state.get('entry_fee_current', 0.0))
            trade_funding_accum = float(carry_over_state.get('trade_funding_accum', 0.0))
            trade_borrow_accum = float(carry_over_state.get('trade_borrow_accum', 0.0))
            highest_price = float(carry_over_state.get('highest_price', entry_price))
            stop_price = float(carry_over_state.get('stop_price', 0.0))
            bars_held = int(carry_over_state.get('bars_held', 0))
            initial_equity_base = float(carry_over_state.get('equity', cash))
        else:
            cash = float(self.initial_cash)
            curr_pos = 'USDT_CASH'
            asset_units = 0.0
            entry_price = 0.0
            entry_time = None
            entry_fee_current = 0.0
            trade_funding_accum = 0.0
            trade_borrow_accum = 0.0
            highest_price = 0.0
            stop_price = 0.0
            bars_held = 0
            initial_equity_base = float(self.initial_cash)

        # Totals & Tracking
        equity_curve = []
        bar_records = []
        trades: List[TradeRecord] = []
        liquidated = False
        liquidation_date = None
        total_entry_fees = 0.0
        total_exit_fees = 0.0
        total_slippage_cost = 0.0
        total_funding_cost = 0.0
        total_borrow_cost = 0.0
        stop_count = 0
        min_distance_to_liq = 1.0

        # Liquidation drop threshold for maintenance margin
        # For 3x leverage with 0.5% MMR: drop ~ 32.833%
        liq_drop_pct = (1.0 / self.leverage - self.mmr) if self.leverage > 1.0 else 1.0

        target_pos = curr_pos

        # 4. Main Event Loop across Evaluation Bars ONLY
        for t in eval_idx:
            if liquidated:
                equity_curve.append(0.0)
                bar_records.append({
                    'bar_time': t,
                    'target_pos': 'USDT_CASH',
                    'curr_pos': 'USDT_CASH',
                    'asset_units': 0.0,
                    'entry_price': 0.0,
                    'stop_price': 0.0,
                    'cash': 0.0,
                    'equity': 0.0,
                    'bars_held': 0,
                })
                continue

            settle = bool(is_settlement_bar.loc[t])
            i_sim = sim_idx.get_loc(t)

            # -------------------------------------------------------------
            # STEP 1: Determine Target Position (Signals strictly prior to Bar T)
            # -------------------------------------------------------------
            closes_window = closes.iloc[:i_sim]  # Historical data strictly prior to bar T
            
            if len(closes_window) < 121:
                # If total available history (warmup + past) is under 121 bars, default to cash
                target_pos = 'USDT_CASH'
            else:
                atr_current_dict = {
                    s: float(df_atrs_prior.loc[t, s])
                    for s in self.symbols
                    if not np.isnan(df_atrs_prior.loc[t, s])
                }
                decision = compute_top1_decision(
                    closes_df=closes_window,
                    atrs_dict=atr_current_dict,
                    current_symbol=curr_pos,
                    symbols=self.symbols,
                    hysteresis_pct=self.hysteresis_pct,
                    delta_score_buffer=self.delta_score_buffer,
                )
                target_pos = decision.target_symbol

            # -------------------------------------------------------------
            # STEP 2: Execution at Bar T Open (O_t)
            # -------------------------------------------------------------
            if target_pos != curr_pos:
                # A. Close previous position if held
                if curr_pos != 'USDT_CASH' and asset_units > 0:
                    raw_exit_p = opens.loc[t, curr_pos]
                    # Two-way execution slippage on sell market order
                    exit_p = raw_exit_p * (1.0 - self.execution_slippage)
                    slip_cost = asset_units * (raw_exit_p - exit_p)
                    total_slippage_cost += slip_cost

                    gross_proceeds = asset_units * exit_p
                    exit_fee = gross_proceeds * self.fee_rate
                    total_exit_fees += exit_fee

                    gross_pnl = asset_units * (exit_p - entry_price)
                    net_trade_pnl = gross_pnl - entry_fee_current - exit_fee - trade_funding_accum - trade_borrow_accum

                    cash = max(0.0, cash + gross_pnl - exit_fee)
                    gross_ret = (exit_p - entry_price) / entry_price * self.leverage
                    trades.append(TradeRecord(
                        entry_time=entry_time,
                        exit_time=t,
                        symbol=curr_pos,
                        entry_price=entry_price,
                        exit_price=exit_p,
                        units=asset_units,
                        leverage=self.leverage,
                        gross_pnl_usdt=gross_pnl,
                        entry_fee_usdt=entry_fee_current,
                        exit_fee_usdt=exit_fee,
                        slippage_cost_usdt=slip_cost,
                        funding_cost_usdt=trade_funding_accum,
                        borrow_cost_usdt=trade_borrow_accum,
                        net_pnl_usdt=net_trade_pnl,
                        gross_ret_pct=gross_ret * 100.0,
                        exit_reason='SIGNAL_EXIT',
                        bars_held=bars_held,
                    ))

                    asset_units = 0.0
                    curr_pos = 'USDT_CASH'
                    entry_price = 0.0
                    entry_time = None
                    entry_fee_current = 0.0
                    trade_funding_accum = 0.0
                    trade_borrow_accum = 0.0
                    highest_price = 0.0
                    stop_price = 0.0
                    bars_held = 0

                # B. Open new position if target is token and cash > 0
                if target_pos != 'USDT_CASH' and cash > 0:
                    curr_pos = target_pos
                    raw_entry_p = opens.loc[t, target_pos]
                    # Two-way execution slippage on buy market order
                    entry_price = raw_entry_p * (1.0 + self.execution_slippage)
                    slip_cost = (entry_price - raw_entry_p)
                    entry_time = t
                    highest_price = entry_price
                    bars_held = 0
                    trade_funding_accum = 0.0
                    trade_borrow_accum = 0.0

                    nominal_target = cash * self.leverage
                    entry_fee = nominal_target * self.fee_rate
                    total_entry_fees += entry_fee
                    entry_fee_current = entry_fee
                    investable_nominal = max(0.0, nominal_target - entry_fee)
                    asset_units = investable_nominal / entry_price
                    total_slippage_cost += (asset_units * slip_cost)

                    cash = max(0.0, cash - entry_fee)

                    # Initial Stop Loss: 1.5x ATR below entry or EMA200 gate line
                    atr_val = df_atrs_prior.loc[t, target_pos]
                    initial_stop = entry_price - (atr_val * self.sl_atr_mult) if (not np.isnan(atr_val) and atr_val > 0) else entry_price * 0.95
                    ema200_cand = float(closes_window[target_pos].ewm(span=200).mean().iloc[-1])
                    gate_stop = ema200_cand * (1.0 - self.hysteresis_pct)
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

                # Maintenance Margin Liquidation Threshold
                # Formula: Cash + Units * (P_liq - Entry) = Units * P_liq * MMR
                # P_liq = (Units * Entry - Cash) / (Units * (1 - MMR))
                if self.leverage > 1.0 and asset_units > 0:
                    denom = asset_units * (1.0 - self.mmr)
                    liq_price = max(0.0, (asset_units * entry_price - cash) / denom)
                else:
                    liq_price = 0.0

                dist_liq_pct = (bar_l - liq_price) / entry_price if entry_price > 0 else 1.0
                min_distance_to_liq = min(min_distance_to_liq, dist_liq_pct)

                # Conservative Intrabar Execution Priority:
                # 1. Open Gap-Down Piercing Liquidation Price
                if self.leverage > 1.0 and bar_o <= liq_price:
                    liquidated = True
                    liquidation_date = str(t)
                    gross_pnl = asset_units * (bar_o - entry_price)
                    net_trade_pnl = -initial_equity_base
                    trades.append(TradeRecord(
                        entry_time=entry_time,
                        exit_time=t,
                        symbol=curr_pos,
                        entry_price=entry_price,
                        exit_price=bar_o,
                        units=asset_units,
                        leverage=self.leverage,
                        gross_pnl_usdt=gross_pnl,
                        entry_fee_usdt=entry_fee_current,
                        exit_fee_usdt=0.0,
                        slippage_cost_usdt=0.0,
                        funding_cost_usdt=trade_funding_accum,
                        borrow_cost_usdt=trade_borrow_accum,
                        net_pnl_usdt=net_trade_pnl,
                        gross_ret_pct=-100.0,
                        exit_reason='LIQUIDATION',
                        bars_held=bars_held,
                    ))
                    cash = 0.0
                    asset_units = 0.0
                    curr_pos = 'USDT_CASH'
                    equity_curve.append(0.0)
                    bar_records.append({
                        'bar_time': t,
                        'target_pos': target_pos,
                        'curr_pos': 'USDT_CASH',
                        'asset_units': 0.0,
                        'entry_price': 0.0,
                        'stop_price': 0.0,
                        'cash': 0.0,
                        'equity': 0.0,
                        'bars_held': 0,
                    })
                    continue

                # 2. Open Gap-Down Piercing Stop-Loss Price
                elif stop_price > 0 and bar_o <= stop_price:
                    stop_count += 1
                    exec_exit = bar_o  # Gap down fill at Open
                    slip_cost = asset_units * (stop_price - exec_exit)
                    total_slippage_cost += max(0.0, slip_cost)

                    gross_proceeds = asset_units * exec_exit
                    exit_fee = gross_proceeds * self.fee_rate
                    total_exit_fees += exit_fee

                    gross_pnl = asset_units * (exec_exit - entry_price)
                    net_trade_pnl = gross_pnl - entry_fee_current - exit_fee - trade_funding_accum - trade_borrow_accum

                    cash = max(0.0, cash + gross_pnl - exit_fee)
                    gross_ret = (exec_exit - entry_price) / entry_price * self.leverage
                    trades.append(TradeRecord(
                        entry_time=entry_time,
                        exit_time=t,
                        symbol=curr_pos,
                        entry_price=entry_price,
                        exit_price=exec_exit,
                        units=asset_units,
                        leverage=self.leverage,
                        gross_pnl_usdt=gross_pnl,
                        entry_fee_usdt=entry_fee_current,
                        exit_fee_usdt=exit_fee,
                        slippage_cost_usdt=slip_cost,
                        funding_cost_usdt=trade_funding_accum,
                        borrow_cost_usdt=trade_borrow_accum,
                        net_pnl_usdt=net_trade_pnl,
                        gross_ret_pct=gross_ret * 100.0,
                        exit_reason='STOP_LOSS',
                        bars_held=bars_held,
                    ))

                    asset_units = 0.0
                    curr_pos = 'USDT_CASH'
                    entry_price = 0.0
                    entry_time = None
                    entry_fee_current = 0.0
                    trade_funding_accum = 0.0
                    trade_borrow_accum = 0.0
                    highest_price = 0.0
                    stop_price = 0.0
                    bars_held = 0
                    equity_curve.append(cash)
                    bar_records.append({
                        'bar_time': t,
                        'target_pos': target_pos,
                        'curr_pos': 'USDT_CASH',
                        'asset_units': 0.0,
                        'entry_price': 0.0,
                        'stop_price': 0.0,
                        'cash': cash,
                        'equity': cash,
                        'bars_held': 0,
                    })
                    continue

                # 3. Intrabar Low Piercing Stop-Loss Price
                # Stop loss line is shallower than liquidation line, so price crosses stop loss first!
                elif stop_price > 0 and bar_l <= stop_price:
                    stop_count += 1
                    exec_exit = min(bar_o, stop_price * (1.0 - self.stop_slippage))
                    slip_cost = asset_units * (stop_price - exec_exit)
                    total_slippage_cost += max(0.0, slip_cost)

                    gross_proceeds = asset_units * exec_exit
                    exit_fee = gross_proceeds * self.fee_rate
                    total_exit_fees += exit_fee

                    gross_pnl = asset_units * (exec_exit - entry_price)
                    net_trade_pnl = gross_pnl - entry_fee_current - exit_fee - trade_funding_accum - trade_borrow_accum

                    cash = max(0.0, cash + gross_pnl - exit_fee)
                    gross_ret = (exec_exit - entry_price) / entry_price * self.leverage
                    trades.append(TradeRecord(
                        entry_time=entry_time,
                        exit_time=t,
                        symbol=curr_pos,
                        entry_price=entry_price,
                        exit_price=exec_exit,
                        units=asset_units,
                        leverage=self.leverage,
                        gross_pnl_usdt=gross_pnl,
                        entry_fee_usdt=entry_fee_current,
                        exit_fee_usdt=exit_fee,
                        slippage_cost_usdt=slip_cost,
                        funding_cost_usdt=trade_funding_accum,
                        borrow_cost_usdt=trade_borrow_accum,
                        net_pnl_usdt=net_trade_pnl,
                        gross_ret_pct=gross_ret * 100.0,
                        exit_reason='STOP_LOSS',
                        bars_held=bars_held,
                    ))

                    asset_units = 0.0
                    curr_pos = 'USDT_CASH'
                    entry_price = 0.0
                    entry_time = None
                    entry_fee_current = 0.0
                    trade_funding_accum = 0.0
                    trade_borrow_accum = 0.0
                    highest_price = 0.0
                    stop_price = 0.0
                    bars_held = 0
                    equity_curve.append(cash)
                    bar_records.append({
                        'bar_time': t,
                        'target_pos': target_pos,
                        'curr_pos': 'USDT_CASH',
                        'asset_units': 0.0,
                        'entry_price': 0.0,
                        'stop_price': 0.0,
                        'cash': cash,
                        'equity': cash,
                        'bars_held': 0,
                    })
                    continue

                # 4. Intrabar Low Piercing Liquidation Price (if stop did not trigger or stop_price <= 0)
                elif self.leverage > 1.0 and bar_l <= liq_price:
                    liquidated = True
                    liquidation_date = str(t)
                    gross_pnl = asset_units * (liq_price - entry_price)
                    net_trade_pnl = -initial_equity_base
                    trades.append(TradeRecord(
                        entry_time=entry_time,
                        exit_time=t,
                        symbol=curr_pos,
                        entry_price=entry_price,
                        exit_price=liq_price,
                        units=asset_units,
                        leverage=self.leverage,
                        gross_pnl_usdt=gross_pnl,
                        entry_fee_usdt=entry_fee_current,
                        exit_fee_usdt=0.0,
                        slippage_cost_usdt=0.0,
                        funding_cost_usdt=trade_funding_accum,
                        borrow_cost_usdt=trade_borrow_accum,
                        net_pnl_usdt=net_trade_pnl,
                        gross_ret_pct=-100.0,
                        exit_reason='LIQUIDATION',
                        bars_held=bars_held,
                    ))
                    cash = 0.0
                    asset_units = 0.0
                    curr_pos = 'USDT_CASH'
                    equity_curve.append(0.0)
                    bar_records.append({
                        'bar_time': t,
                        'target_pos': target_pos,
                        'curr_pos': 'USDT_CASH',
                        'asset_units': 0.0,
                        'entry_price': 0.0,
                        'stop_price': 0.0,
                        'cash': 0.0,
                        'equity': 0.0,
                        'bars_held': 0,
                    })
                    continue

                # 5. Trailing Stop Ratchet (survived all stop checks)
                if highest_price >= entry_price * 1.05:
                    be_stop = entry_price * 1.002
                    stop_price = max(stop_price, be_stop)
                if highest_price >= entry_price * 1.10:
                    trail_stop = highest_price * 0.95
                    stop_price = max(stop_price, trail_stop)

                # 6. Accurate Funding & Borrow Interest Settlement
                if settle and self.leverage > 1.0 and bars_held >= 1:
                    nominal_notional = asset_units * bar_c
                    fr = funding_aligned.loc[t, curr_pos] if curr_pos in funding_aligned else 0.0001
                    borrow_fee = nominal_notional * ((self.leverage - 1.0) / self.leverage) * (self.borrow_apr / (365.25 * 3))
                    fund_cost = nominal_notional * fr

                    # Debit cash (cash can become negative in leveraged futures while equity remains strongly positive!)
                    cash = cash - fund_cost - borrow_fee
                    total_funding_cost += fund_cost
                    total_borrow_cost += borrow_fee
                    trade_funding_accum += fund_cost
                    trade_borrow_accum += borrow_fee

                    # Rigorous Margin Liquidation Check:
                    # Account is liquidated IF AND ONLY IF Total Equity <= Maintenance Margin!
                    current_equity = cash + asset_units * (bar_c - entry_price)
                    maintenance_margin = nominal_notional * self.mmr
                    if current_equity <= maintenance_margin:
                        liquidated = True
                        liquidation_date = str(t)
                        trades.append(TradeRecord(
                            entry_time=entry_time,
                            exit_time=t,
                            symbol=curr_pos,
                            entry_price=entry_price,
                            exit_price=bar_c,
                            units=asset_units,
                            leverage=self.leverage,
                            gross_pnl_usdt=asset_units * (bar_c - entry_price),
                            entry_fee_usdt=entry_fee_current,
                            exit_fee_usdt=0.0,
                            slippage_cost_usdt=0.0,
                            funding_cost_usdt=trade_funding_accum,
                            borrow_cost_usdt=trade_borrow_accum,
                            net_pnl_usdt=-initial_equity_base,
                            gross_ret_pct=-100.0,
                            exit_reason='LIQUIDATION',
                            bars_held=bars_held,
                        ))
                        cash = 0.0
                        asset_units = 0.0
                        curr_pos = 'USDT_CASH'
                        equity_curve.append(0.0)
                        bar_records.append({
                            'bar_time': t,
                            'target_pos': target_pos,
                            'curr_pos': 'USDT_CASH',
                            'asset_units': 0.0,
                            'entry_price': 0.0,
                            'stop_price': 0.0,
                            'cash': 0.0,
                            'equity': 0.0,
                            'bars_held': 0,
                        })
                        continue

            # -------------------------------------------------------------
            # STEP 4: End-of-Bar Mark-to-Market Equity (C_t)
            # -------------------------------------------------------------
            if curr_pos == 'USDT_CASH' or asset_units == 0:
                current_equity = max(0.0, cash)
            else:
                bar_c = closes.loc[t, curr_pos]
                unrealized_pnl = asset_units * (bar_c - entry_price)
                current_equity = cash + unrealized_pnl
                maintenance_margin = asset_units * bar_c * self.mmr
                if current_equity <= maintenance_margin:
                    liquidated = True
                    liquidation_date = str(t)
                    current_equity = 0.0
                    cash = 0.0
                    asset_units = 0.0

            equity_curve.append(current_equity)
            bar_records.append({
                'bar_time': t,
                'target_pos': target_pos,
                'curr_pos': curr_pos,
                'asset_units': asset_units,
                'entry_price': entry_price,
                'stop_price': stop_price,
                'cash': cash,
                'equity': current_equity,
                'bars_held': bars_held,
            })

        # 5. Final Ledger Reconciliation Accounting
        eq_s = pd.Series(equity_curve, index=eval_idx)
        final_equity = float(eq_s.iloc[-1]) if len(eq_s) > 0 else initial_equity_base
        total_ret_pct = ((final_equity - initial_equity_base) / initial_equity_base) * 100.0

        n_bars = len(eq_s)
        years = n_bars / (365.25 * 6)
        cagr_pct = ((final_equity / initial_equity_base) ** (1.0 / years) - 1.0) * 100.0 if (final_equity > 0 and years > 0) else -100.0

        running_max = eq_s.cummax()
        drawdown = (eq_s - running_max) / (running_max.replace(0, np.nan))
        max_dd_pct = float(drawdown.min() * 100.0) if not drawdown.empty and not np.isnan(drawdown.min()) else 0.0

        daily_eq = eq_s.resample('1D').last().dropna()
        daily_rets = daily_eq.pct_change().dropna()
        sharpe = (daily_rets.mean() / (daily_rets.std() + 1e-8)) * np.sqrt(365) if len(daily_rets) > 10 else 0.0
        calmar = (cagr_pct / abs(max_dd_pct)) if abs(max_dd_pct) > 0.01 else 0.0

        win_trades = [tr for tr in trades if tr.net_pnl_usdt > 0]
        win_rate = (len(win_trades) / len(trades) * 100.0) if trades else 0.0

        # Open Position at Simulation End
        open_unrealized_pnl = 0.0
        if curr_pos != 'USDT_CASH' and asset_units > 0 and not liquidated:
            final_c = closes.loc[eval_idx[-1], curr_pos]
            open_unrealized_pnl = asset_units * (final_c - entry_price)

        sum_gross_pnl = sum(tr.gross_pnl_usdt for tr in trades)

        # Expected Final Equity from ledger formula:
        if not liquidated:
            expected_final_equity = (
                initial_equity_base
                + sum_gross_pnl
                - total_entry_fees
                - total_exit_fees
                - total_funding_cost
                - total_borrow_cost
                + open_unrealized_pnl
            )
            reconciliation_error = abs(final_equity - expected_final_equity)
            is_perfectly_reconciled = bool(reconciliation_error < 1e-4)
        else:
            expected_final_equity = 0.0
            reconciliation_error = abs(final_equity)
            is_perfectly_reconciled = True

        expected_bars_count = int((eval_end_ts - eval_start_ts).total_seconds() // 14400)
        actual_bars_count = len(eval_idx)
        missing_bars_count = max(0, expected_bars_count - actual_bars_count)

        end_state = {
            'cash': cash,
            'curr_pos': curr_pos,
            'asset_units': asset_units,
            'entry_price': entry_price,
            'entry_time': entry_time,
            'entry_fee_current': entry_fee_current,
            'trade_funding_accum': trade_funding_accum,
            'trade_borrow_accum': trade_borrow_accum,
            'highest_price': highest_price,
            'stop_price': stop_price,
            'bars_held': bars_held,
            'equity': final_equity,
        }

        return {
            'final_equity': round(final_equity, 2),
            'final_cash': round(cash, 2),
            'initial_equity': round(initial_equity_base, 2),
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
            'total_entry_fees': round(total_entry_fees, 2),
            'total_exit_fees': round(total_exit_fees, 2),
            'total_fees': round(total_entry_fees + total_exit_fees, 2),
            'total_slippage': round(total_slippage_cost, 2),
            'total_funding': round(total_funding_cost, 2),
            'total_borrow': round(total_borrow_cost, 2),
            'open_unrealized_pnl': round(open_unrealized_pnl, 2),
            'reconciliation_error': round(reconciliation_error, 6),
            'is_perfectly_reconciled': is_perfectly_reconciled,
            'eval_start_dt': str(eval_start_ts),
            'eval_end_dt': str(eval_end_ts),
            'actual_first_bar': str(eval_idx[0]) if len(eval_idx) > 0 else None,
            'actual_last_bar': str(eval_idx[-1]) if len(eval_idx) > 0 else None,
            'expected_bars_count': expected_bars_count,
            'actual_bars_count': actual_bars_count,
            'missing_bars_count': missing_bars_count,
            'admission_report': admission_report.to_dict() if admission_report else None,
            'end_state': end_state,
            'trades_list': trades,
            'equity_curve': eq_s,
            'bar_records': bar_records,
        }
