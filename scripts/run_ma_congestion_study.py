# -*- coding: utf-8 -*-
"""
Moving Average Congestion Breakout & Pullback Study Runner
均线密集突破后回踩全景量化研究实验运行器
===========================================================
Executes:
1. Four Pre-Registered Versions:
   - V1: 15m EMA Long (Spot Core-4) [Primary Experiment]
   - V2: 15m SMA Long (Spot Core-4) [MA Baseline]
   - V3: 5m EMA Long (Spot Core-4) [High-Frequency EMA]
   - V4: 5m SMA Long (Spot Core-4) [High-Frequency SMA]
   - V1_SHORT: 15m EMA Short (Perpetual Futures Core-4 with funding)
   - V3_SHORT: 5m EMA Short (Perpetual Futures Core-4 with funding)
2. Controlled Ablations:
   - Ablation 1: Simple Trend Baseline (No 3-MA congestion requirement)
   - Ablation 2: Breakout-Only Entry (No pullback confirmation wait)
   - Ablation 3: Fixed 2R Exit (vs. Dynamic ATR trailing stop)
3. Cost Friction Stress Tests:
   - 1x Base, 2x Stress, 4x Extreme Frictions.
4. Comprehensive Artifacts:
   - Trade-by-trade CSV ledgers
   - Ablation comparison summary
   - Annual & symbol breakdown tables
   - Cost friction sensitivity matrix
"""

import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import argparse
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd

from crypto_quant.data.intraday_manager import (
    load_intraday_symbol,
    CORE4_SYMBOLS,
    DEFAULT_INTRADAY_DIR,
)
from crypto_quant.ma_congestion.state_machine import (
    MACongestionStateMachine,
    TradeSignal,
    compute_indicators,
)
from crypto_quant.backtest.intraday_risk_engine import (
    IntradayRiskLedgerSimulator,
    IntradayTradeRecord,
)

REPORTS_DIR = os.path.join(project_root, "reports", "ma_congestion")
os.makedirs(REPORTS_DIR, exist_ok=True)


def calculate_metrics(trades: List[IntradayTradeRecord], equity_curve: List[Dict[str, Any]], initial_cash: float = 10000.0) -> Dict[str, Any]:
    """Compute standard institutional quantitative metrics."""
    if not trades:
        return {
            "total_trades": 0,
            "win_rate_pct": 0.0,
            "avg_net_r": 0.0,
            "median_net_r": 0.0,
            "profit_factor": 0.0,
            "total_net_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "daily_sharpe": 0.0,
            "avg_hours_held": 0.0,
            "total_fees_usdt": 0.0,
            "total_slippage_usdt": 0.0,
            "final_equity": initial_cash,
        }

    net_pnls = [t.net_pnl_usdt for t in trades]
    net_rs = [t.net_r_multiple for t in trades]
    wins = [p for p in net_pnls if p > 0]
    losses = [p for p in net_pnls if p <= 0]

    win_rate = (len(wins) / len(trades)) * 100.0
    gross_win = sum(wins) if wins else 0.0
    gross_loss = abs(sum(losses)) if losses else 0.0
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else 999.0

    total_net_pnl = sum(net_pnls)
    final_equity = initial_cash + total_net_pnl
    ret_pct = (total_net_pnl / initial_cash) * 100.0

    avg_net_r = float(np.mean(net_rs))
    median_net_r = float(np.median(net_rs))

    # Equity curve stats
    df_eq = pd.DataFrame(equity_curve)
    df_eq.set_index("bar_time", inplace=True)
    df_eq["peak"] = df_eq["equity"].cummax()
    df_eq["drawdown"] = (df_eq["peak"] - df_eq["equity"]) / df_eq["peak"] * 100.0
    max_dd = float(df_eq["drawdown"].max())

    # Daily Sharpe
    df_daily = df_eq["equity"].resample("1D").last().dropna()
    daily_rets = df_daily.pct_change().dropna()
    if len(daily_rets) > 5 and daily_rets.std() > 1e-8:
        daily_sharpe = float(daily_rets.mean() / daily_rets.std() * np.sqrt(365))
    else:
        daily_sharpe = 0.0

    avg_bars_held = float(np.mean([t.bars_held for t in trades]))
    # Assuming 15m default (4 bars per hour) unless 5m
    hours_per_bar = 0.25
    avg_hours_held = avg_bars_held * hours_per_bar

    total_fees = sum(t.entry_fee_usdt + t.exit_fee_usdt for t in trades)
    total_slippage = sum(t.slippage_cost_usdt for t in trades)

    return {
        "total_trades": len(trades),
        "win_rate_pct": round(win_rate, 2),
        "avg_net_r": round(avg_net_r, 3),
        "median_net_r": round(median_net_r, 3),
        "profit_factor": round(profit_factor, 2),
        "total_net_return_pct": round(ret_pct, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "daily_sharpe": round(daily_sharpe, 2),
        "avg_hours_held": round(avg_hours_held, 2),
        "total_fees_usdt": round(total_fees, 2),
        "total_slippage_usdt": round(total_slippage, 2),
        "final_equity": round(final_equity, 2),
    }


def run_experiment(
    exp_name: str,
    interval: str = "15m",
    ma_type: str = "EMA",
    direction: str = "LONG",
    market_type: str = "spot",
    exit_rule: str = "DYNAMIC_TRAILING",
    ablation_mode: str = "NORMAL",        # 'NORMAL', 'NO_CONGESTION', 'BREAKOUT_ONLY'
    cost_multiplier: float = 1.0,         # 1.0, 2.0, 4.0
    start_date: str = "2024-01-01",
    end_date: Optional[str] = None,
    initial_cash: float = 10000.0,
) -> Tuple[Dict[str, Any], List[IntradayTradeRecord]]:
    """
    Run an end-to-end backtest experiment for a specified configuration.
    """
    print(f"\n--- Running Experiment: {exp_name} ({interval}, {ma_type}, {direction}, {market_type}, {ablation_mode}, Cost={cost_multiplier}x) ---")

    # Load data for Core-4
    raw_dfs = {}
    for sym in CORE4_SYMBOLS:
        try:
            df_sym = load_intraday_symbol(
                symbol=sym,
                interval=interval,
                market_type=market_type,
                start_dt=pd.to_datetime(start_date, utc=True),
                end_dt=pd.to_datetime(end_date, utc=True) if end_date else None,
            )
            raw_dfs[sym] = df_sym
        except FileNotFoundError:
            print(f"[WARN] Data for {sym} {interval} ({market_type}) not found, skipping.")

    if not raw_dfs:
        raise RuntimeError(f"No data available for {interval} {market_type}!")

    # Find common time index
    common_idx = list(raw_dfs.values())[0].index
    for df in list(raw_dfs.values())[1:]:
        common_idx = common_idx.intersection(df.index)
    common_idx = common_idx.sort_values()

    # Compute indicators on all symbols
    ind_dfs = {}
    for sym, df in raw_dfs.items():
        sub_df = df.reindex(common_idx).copy()
        ind_dfs[sym] = compute_indicators(sub_df, ma_type=ma_type)

    # Fee & Slippage calibrated by cost_multiplier
    if market_type == "spot":
        base_fee = 0.0008 * cost_multiplier
        base_exec_slip = 0.0005 * cost_multiplier
        base_stop_slip = 0.0015 * cost_multiplier
    else:
        base_fee = 0.0005 * cost_multiplier
        base_exec_slip = 0.0004 * cost_multiplier
        base_stop_slip = 0.0012 * cost_multiplier

    max_holding_bars = 32 if interval == "15m" else 96

    simulator = IntradayRiskLedgerSimulator(
        symbols=list(ind_dfs.keys()),
        initial_cash=initial_cash,
        risk_per_trade_pct=0.005,
        max_concurrent_positions=2,
        fee_rate=base_fee,
        execution_slippage=base_exec_slip,
        stop_slippage=base_stop_slip,
        max_holding_bars=max_holding_bars,
        market_type=market_type,
        exit_rule=exit_rule,
    )

    # Load funding rates for futures
    funding_df = None
    if market_type == "futures":
        funding_path = os.path.join(project_root, "data", "binance_funding_8h.parquet")
        if os.path.exists(funding_path):
            funding_df = pd.read_parquet(funding_path)
            if funding_df.index.tz is None:
                funding_df.index = funding_df.index.tz_localize("UTC")
            else:
                funding_df.index = funding_df.index.tz_convert("UTC")

    # State machines for each symbol
    state_machines = {
        sym: MACongestionStateMachine(symbol=sym, direction=direction)
        for sym in ind_dfs.keys()
    }

    # Simulation loop across bars
    # Warmup first 200 bars for MA200 convergence
    warmup_bars = 200
    pending_signals: List[TradeSignal] = []

    for i in range(warmup_bars, len(common_idx)):
        bar_t = common_idx[i]
        prev_bar_t = common_idx[i - 1]

        # Extract bar data slice for current bar
        bar_data = {sym: ind_dfs[sym].loc[bar_t] for sym in ind_dfs.keys()}

        # Extract funding rates if applicable
        funding_rates = None
        if funding_df is not None and bar_t in funding_df.index:
            funding_rates = funding_df.loc[bar_t].to_dict()

        # Step 1: Simulator processes the current bar with pending signals from previous bar
        simulator.process_bar(
            bar_time=bar_t,
            bar_data=bar_data,
            pending_signals=pending_signals,
            funding_rates=funding_rates,
        )

        # Step 2: On completed candle bar_t, evaluate state machines to generate signals for bar_t + 1
        new_signals: List[TradeSignal] = []
        for sym, sm in state_machines.items():
            row_t = ind_dfs[sym].loc[bar_t]

            if ablation_mode == "NORMAL":
                sig = sm.feed_bar(bar_t, row_t)
                if sig:
                    new_signals.append(sig)

            elif ablation_mode == "NO_CONGESTION":
                # Ablation 1: Simple trend pullback without 3-MA congestion filter
                close_p = float(row_t["close"])
                low_p = float(row_t["low"])
                high_p = float(row_t["high"])
                ma20 = float(row_t["ma20"])
                ma200 = float(row_t["ma200"])
                slope = float(row_t["ma200_slope_4"])
                atr14 = float(row_t["atr14"])

                if direction == "LONG":
                    # Uptrend + pullback touching MA20 then closing above MA20
                    if close_p > ma200 and slope > 0:
                        prev_row = ind_dfs[sym].loc[prev_bar_t]
                        if prev_row["low"] <= prev_row["ma20"] and close_p > ma20:
                            sig = TradeSignal(
                                symbol=sym,
                                direction="LONG",
                                signal_time=bar_t,
                                confirm_price=close_p,
                                initial_sl=low_p - 0.2 * atr14,
                                frozen_atr=atr14,
                                formation_time=bar_t,
                                breakout_time=bar_t,
                                confirm_time=bar_t,
                                U=ma20,
                                L=low_p,
                                breakout_price=close_p,
                                pattern_duration_bars=1,
                            )
                            new_signals.append(sig)
                else:
                    if close_p < ma200 and slope < 0:
                        prev_row = ind_dfs[sym].loc[prev_bar_t]
                        if prev_row["high"] >= prev_row["ma20"] and close_p < ma20:
                            sig = TradeSignal(
                                symbol=sym,
                                direction="SHORT",
                                signal_time=bar_t,
                                confirm_price=close_p,
                                initial_sl=high_p + 0.2 * atr14,
                                frozen_atr=atr14,
                                formation_time=bar_t,
                                breakout_time=bar_t,
                                confirm_time=bar_t,
                                U=high_p,
                                L=ma20,
                                breakout_price=close_p,
                                pattern_duration_bars=1,
                            )
                            new_signals.append(sig)

            elif ablation_mode == "BREAKOUT_ONLY":
                # Ablation 2: Congestion zone breakout directly, no pullback confirmation
                # Feed state machine up to breakout, then fire immediately
                sm.feed_bar(bar_t, row_t)
                if sm.state.value == "AWAITING_PULLBACK" and sm.bars_since_breakout == 0:
                    z = sm.current_zone
                    if z:
                        sl_init = z.L - 0.2 * z.frozen_atr if direction == "LONG" else z.U + 0.2 * z.frozen_atr
                        sig = TradeSignal(
                            symbol=sym,
                            direction=direction,
                            signal_time=bar_t,
                            confirm_price=float(row_t["close"]),
                            initial_sl=sl_init,
                            frozen_atr=z.frozen_atr,
                            formation_time=z.formation_bar,
                            breakout_time=sm.breakout_bar,
                            confirm_time=bar_t,
                            U=z.U,
                            L=z.L,
                            breakout_price=sm.breakout_price,
                            pattern_duration_bars=sm.bars_since_formation,
                        )
                        new_signals.append(sig)
                        sm.reset()

        pending_signals = new_signals

    # Calculate metrics
    trades = simulator.closed_trades
    metrics = calculate_metrics(trades, simulator.equity_curve, initial_cash=initial_cash)
    metrics["experiment_name"] = exp_name

    # Export trade ledger
    if trades:
        records_data = []
        for t in trades:
            records_data.append({
                "trade_id": t.trade_id,
                "symbol": t.symbol,
                "direction": t.direction,
                "market_type": t.market_type,
                "formation_time": t.formation_time,
                "U": round(t.U, 4),
                "L": round(t.L, 4),
                "frozen_atr": round(t.frozen_atr, 4),
                "breakout_time": t.breakout_time,
                "breakout_price": round(t.breakout_price, 4),
                "confirm_time": t.confirm_time,
                "confirm_price": round(t.confirm_price, 4),
                "entry_time": t.entry_time,
                "entry_price": round(t.entry_price, 4),
                "units": round(t.units, 6),
                "nominal_size_usdt": round(t.nominal_size_usdt, 2),
                "initial_sl": round(t.initial_sl, 4),
                "final_sl": round(t.final_sl, 4),
                "sl_updates": t.sl_updates,
                "exit_time": t.exit_time,
                "exit_price": round(t.exit_price, 4),
                "exit_reason": t.exit_reason,
                "bars_held": t.bars_held,
                "gross_pnl_usdt": round(t.gross_pnl_usdt, 2),
                "entry_fee_usdt": round(t.entry_fee_usdt, 4),
                "exit_fee_usdt": round(t.exit_fee_usdt, 4),
                "slippage_cost_usdt": round(t.slippage_cost_usdt, 4),
                "net_pnl_usdt": round(t.net_pnl_usdt, 2),
                "net_r_multiple": round(t.net_r_multiple, 3),
            })
        df_trades = pd.DataFrame(records_data)
        csv_path = os.path.join(REPORTS_DIR, f"{exp_name}_trades.csv")
        df_trades.to_csv(csv_path, index=False)
        print(f"[EXPORT] Saved {len(df_trades)} trade records to {csv_path}")

    print(f"[SUMMARY] Trades: {metrics['total_trades']}, WinRate: {metrics['win_rate_pct']}%, Avg R: {metrics['avg_net_r']}, Return: {metrics['total_net_return_pct']}%, MaxDD: {metrics['max_drawdown_pct']}%, Sharpe: {metrics['daily_sharpe']}")
    return metrics, trades


def generate_annual_and_asset_breakdown(trades: List[IntradayTradeRecord]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Generate breakdowns segmented by Year and by Symbol."""
    if not trades:
        return pd.DataFrame(), pd.DataFrame()

    data = []
    for t in trades:
        data.append({
            "symbol": t.symbol,
            "year": t.entry_time.year,
            "net_pnl": t.net_pnl_usdt,
            "net_r": t.net_r_multiple,
            "is_win": 1 if t.net_pnl_usdt > 0 else 0,
            "fees_and_slip": t.entry_fee_usdt + t.exit_fee_usdt + t.slippage_cost_usdt,
        })
    df = pd.DataFrame(data)

    # By Year
    year_grp = df.groupby("year").agg(
        trades=("net_pnl", "count"),
        win_rate=("is_win", lambda x: round(x.mean() * 100, 1)),
        avg_r=("net_r", lambda x: round(x.mean(), 3)),
        net_pnl=("net_pnl", lambda x: round(x.sum(), 2)),
        friction=("fees_and_slip", lambda x: round(x.sum(), 2)),
    ).reset_index()

    # By Symbol
    sym_grp = df.groupby("symbol").agg(
        trades=("net_pnl", "count"),
        win_rate=("is_win", lambda x: round(x.mean() * 100, 1)),
        avg_r=("net_r", lambda x: round(x.mean(), 3)),
        net_pnl=("net_pnl", lambda x: round(x.sum(), 2)),
        friction=("fees_and_slip", lambda x: round(x.sum(), 2)),
    ).reset_index()

    return year_grp, sym_grp


def main():
    parser = argparse.ArgumentParser(description="Run MA Congestion Breakout & Pullback Study Suite.")
    parser.add_argument("--start-date", type=str, default="2024-01-01")
    parser.add_argument("--end-date", type=str, default=None)
    parser.add_argument("--run-5m", action="store_true", help="Include 5m experiments (requires 5m data)")
    args = parser.parse_args()

    all_metrics = []

    # =========================================================================
    # 1. Four Pre-Registered Versions (15m Primary + Sensitivities)
    # =========================================================================
    # V1: 15m EMA Long (Primary Experiment)
    m_v1, trades_v1 = run_experiment("v1_15m_ema_long", interval="15m", ma_type="EMA", direction="LONG", market_type="spot", start_date=args.start_date)
    all_metrics.append(m_v1)

    # V2: 15m SMA Long (MA Baseline)
    m_v2, _ = run_experiment("v2_15m_sma_long", interval="15m", ma_type="SMA", direction="LONG", market_type="spot", start_date=args.start_date)
    all_metrics.append(m_v2)

    # V1_SHORT: 15m EMA Short (Perpetual Futures)
    m_v1_short, trades_v1_short = run_experiment("v1_15m_ema_short_perps", interval="15m", ma_type="EMA", direction="SHORT", market_type="futures", start_date=args.start_date)
    all_metrics.append(m_v1_short)

    if args.run_5m:
        # V3: 5m EMA Long
        m_v3, _ = run_experiment("v3_5m_ema_long", interval="5m", ma_type="EMA", direction="LONG", market_type="spot", start_date=args.start_date)
        all_metrics.append(m_v3)
        # V4: 5m SMA Long
        m_v4, _ = run_experiment("v4_5m_sma_long", interval="5m", ma_type="SMA", direction="LONG", market_type="spot", start_date=args.start_date)
        all_metrics.append(m_v4)
        # V3_SHORT: 5m EMA Short
        m_v3_short, _ = run_experiment("v3_5m_ema_short_perps", interval="5m", ma_type="EMA", direction="SHORT", market_type="futures", start_date=args.start_date)
        all_metrics.append(m_v3_short)

    # =========================================================================
    # 2. Controlled Ablations (on 15m EMA Long)
    # =========================================================================
    # Ablation 1: Simple Trend Baseline (No Congestion)
    m_abl_simple, _ = run_experiment("ablation_simple_trend_no_congestion", interval="15m", ma_type="EMA", direction="LONG", market_type="spot", ablation_mode="NO_CONGESTION", start_date=args.start_date)
    all_metrics.append(m_abl_simple)

    # Ablation 2: Breakout-Only (No Pullback confirmation wait)
    m_abl_bo, _ = run_experiment("ablation_breakout_only_no_pullback", interval="15m", ma_type="EMA", direction="LONG", market_type="spot", ablation_mode="BREAKOUT_ONLY", start_date=args.start_date)
    all_metrics.append(m_abl_bo)

    # Ablation 3: Fixed 2R Take-Profit (vs Dynamic Trailing Stop)
    m_abl_2r, _ = run_experiment("ablation_fixed_2r_exit", interval="15m", ma_type="EMA", direction="LONG", market_type="spot", exit_rule="FIXED_2R", start_date=args.start_date)
    all_metrics.append(m_abl_2r)

    # =========================================================================
    # 3. Cost Friction Stress Tests (1x, 2x, 4x on V1)
    # =========================================================================
    m_cost_2x, _ = run_experiment("stress_cost_2x_friction", interval="15m", ma_type="EMA", direction="LONG", market_type="spot", cost_multiplier=2.0, start_date=args.start_date)
    all_metrics.append(m_cost_2x)

    m_cost_4x, _ = run_experiment("stress_cost_4x_friction", interval="15m", ma_type="EMA", direction="LONG", market_type="spot", cost_multiplier=4.0, start_date=args.start_date)
    all_metrics.append(m_cost_4x)

    # =========================================================================
    # 4. Export Comparison Tables & Markdown Reports
    # =========================================================================
    df_summary = pd.DataFrame(all_metrics)
    summary_csv = os.path.join(REPORTS_DIR, "all_experiments_summary.csv")
    df_summary.to_csv(summary_csv, index=False)
    print(f"\n[SUMMARY SAVED] {summary_csv}")

    # Generate Markdown Summary
    md_content = ["# MA Congestion Breakout & Pullback Strategy Research Summary\n"]
    md_content.append("## 1. Pre-Registered Versions & Ablations Comparison Table\n")
    md_content.append(df_summary.to_markdown(index=False))

    # Annual & Symbol Breakdowns for V1
    year_df, sym_df = generate_annual_and_asset_breakdown(trades_v1)
    md_content.append("\n\n## 2. V1 (15m EMA Long) Annual Breakdown\n")
    md_content.append(year_df.to_markdown(index=False))
    md_content.append("\n\n## 3. V1 (15m EMA Long) Asset Breakdown\n")
    md_content.append(sym_df.to_markdown(index=False))

    report_md_path = os.path.join(REPORTS_DIR, "RESEARCH_SUMMARY.md")
    with open(report_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_content))
    print(f"[REPORT SAVED] {report_md_path}")


if __name__ == "__main__":
    main()
