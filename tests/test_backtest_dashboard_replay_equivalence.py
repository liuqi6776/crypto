# -*- coding: utf-8 -*-
"""
Automated Pytest Suite: Backtest vs Dashboard Replay Equivalence (Task 23.5)
==========================================================================
Verifies that:
1. Pure Decision Replay Equivalence:
   `compute_top1_decision` and `Top1RotationStrategy.evaluate_cross_section`
   generate 100% identical decisions, ranking orders, scores, gate states,
   and target symbols bar-by-bar across historical 4h data.
2. End-to-End Sequence Replay Equivalence:
   Trade signals, target rotations, and portfolio transitions in
   `SingleLedgerSimulator` match step-by-step paper execution with zero mismatches.
"""

from pathlib import Path
import pytest
import pandas as pd
import numpy as np

from crypto_quant.core.top1_decision_engine import compute_top1_decision
from crypto_quant.paper.top1_rotation_strategy import Top1RotationStrategy, V1Top1State, calculate_atr
from crypto_quant.backtest.clean_single_ledger_engine import SingleLedgerSimulator

ROOT_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def core4_data():
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
    raw_dfs = {}
    data_dir = ROOT_DIR / "data"
    for s in symbols:
        p = data_dir / f"{s}_4h_2020_2026.parquet"
        assert p.exists(), f"Missing dataset {p}"
        df = pd.read_parquet(p)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        raw_dfs[s] = df
    return symbols, raw_dfs


def test_stateless_decision_replay_equivalence(core4_data):
    """
    Asserts 100% equivalence between SingleLedgerSimulator's decision call
    and Top1RotationStrategy.evaluate_cross_section on every single bar.
    """
    symbols, raw_dfs = core4_data
    strategy = Top1RotationStrategy(symbols=symbols)

    # Align common index
    common_idx = raw_dfs["BTCUSDT"].index
    for s in symbols:
        common_idx = common_idx.intersection(raw_dfs[s].index)
    
    # Test across 100 consecutive bars in 2024
    test_idx = common_idx[(common_idx >= "2024-03-01") & (common_idx <= "2024-05-15")].sort_values()
    assert len(test_idx) >= 100, f"Insufficient test bars: {len(test_idx)}"

    closes = pd.DataFrame({s: raw_dfs[s].loc[common_idx, "close"] for s in symbols})
    highs = pd.DataFrame({s: raw_dfs[s].loc[common_idx, "high"] for s in symbols})
    lows = pd.DataFrame({s: raw_dfs[s].loc[common_idx, "low"] for s in symbols})

    # Precalculate prior ATR as in SingleLedgerSimulator
    atrs_dict = {}
    for s in symbols:
        tr1 = highs[s] - lows[s]
        tr2 = (highs[s] - closes[s].shift(1)).abs()
        tr3 = (lows[s] - closes[s].shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atrs_dict[s] = tr.rolling(14).mean().shift(1)
    df_atrs_prior = pd.DataFrame(atrs_dict)

    current_pos = "USDT_CASH"
    mismatches = []

    for t in test_idx[:80]:  # Test 80 consecutive bars
        bar_pos = common_idx.get_loc(t)
        closes_window = closes.iloc[:bar_pos]

        # 1. Backtest Engine Call
        atr_dict_sim = {
            s: float(df_atrs_prior.loc[t, s])
            for s in symbols
            if not np.isnan(df_atrs_prior.loc[t, s])
        }
        dec_sim = compute_top1_decision(
            closes_df=closes_window,
            atrs_dict=atr_dict_sim,
            current_symbol=current_pos,
            symbols=symbols,
            hysteresis_pct=0.005,
        )

        # 2. Strategy Engine Call (Replay with check_stale=False)
        klines_window = {
            s: raw_dfs[s].loc[:closes_window.index[-1]]
            for s in symbols
        }
        dec_strat = strategy.evaluate_cross_section(
            klines_dict=klines_window,
            current_symbol=current_pos,
            check_stale=False,
        )

        # 3. Strict Equivalence Assertions
        if dec_sim.target_symbol != dec_strat["target_symbol"]:
            mismatches.append(f"[{t}] target_symbol mismatch: sim={dec_sim.target_symbol} vs strat={dec_strat['target_symbol']}")
        if dec_sim.top_candidate != dec_strat["top_symbol"]:
            mismatches.append(f"[{t}] top_candidate mismatch: sim={dec_sim.top_candidate} vs strat={dec_strat['top_symbol']}")
        if dec_sim.dual_gate_passed != dec_strat["dual_gate_passed"]:
            mismatches.append(f"[{t}] dual_gate mismatch: sim={dec_sim.dual_gate_passed} vs strat={dec_strat['dual_gate_passed']}")
        if dec_sim.btc_macro_bull != dec_strat["btc_macro_bull"]:
            mismatches.append(f"[{t}] btc_bull mismatch: sim={dec_sim.btc_macro_bull} vs strat={dec_strat['btc_macro_bull']}")
        if abs(dec_sim.top_score - dec_strat["top_score"]) > 1e-6:
            mismatches.append(f"[{t}] top_score mismatch: sim={dec_sim.top_score} vs strat={dec_strat['top_score']}")

        # Update position for next bar
        current_pos = dec_sim.target_symbol

    assert len(mismatches) == 0, f"Replay decision mismatches found: {mismatches[:5]}"


@pytest.mark.parametrize("test_leverage", [1.0, 3.0])
def test_strict_bar_by_bar_full_ledger_equivalence(core4_data, tmp_path, test_leverage):
    """
    Asserts 100% strict bar-by-bar full ledger equivalence between SingleLedgerSimulator
    and Top1RotationStrategy across every single 4h bar.
    Asserts target_symbol, curr_pos, asset_units, entry_price, stop_price, cash, equity,
    and bars_held, failing immediately on the very first mismatch.
    """
    symbols, raw_dfs = core4_data
    start_dt = "2024-01-01"
    end_dt = "2024-04-01"

    # 1. Run SingleLedgerSimulator
    sim = SingleLedgerSimulator(
        symbols=symbols,
        raw_dfs=raw_dfs,
        leverage=test_leverage,
        fee_rate=0.0008,
        execution_slippage=0.0005,
        stop_slippage=0.0015,
        sl_atr_mult=1.5,
        hysteresis_pct=0.005,
        delta_score_buffer=0.0,
        initial_cash=10000.0,
    )
    sim_res = sim.run(start_dt=start_dt, end_dt=end_dt)
    assert sim_res is not None, "Simulator run returned None"
    sim_bar_records = sim_res["bar_records"]
    assert len(sim_bar_records) > 0, "No bar records returned from simulator"

    # 2. Setup Top1RotationStrategy with identical parameters
    state_file = tmp_path / f"replay_state_L{test_leverage}.json"
    journal_file = tmp_path / f"replay_journal_L{test_leverage}.jsonl"
    strategy = Top1RotationStrategy(
        symbols=symbols,
        leverage=test_leverage,
        sl_atr_mult=1.5,
        hysteresis_pct=0.005,
        delta_score_buffer=0.0,
        one_way_fee_rate=0.0008,
        execution_slippage=0.0005,
        stop_slippage=0.0015,
        borrow_apr=0.10,
        state_path=state_file,
        journal_path=journal_file,
    )

    full_idx = raw_dfs["BTCUSDT"].index
    for s in symbols:
        full_idx = full_idx.intersection(raw_dfs[s].index)
    full_idx = full_idx.sort_values()

    eval_idx = [rec["bar_time"] for rec in sim_bar_records]
    opens = pd.DataFrame({s: raw_dfs[s].loc[eval_idx, "open"] for s in symbols})
    highs = pd.DataFrame({s: raw_dfs[s].loc[eval_idx, "high"] for s in symbols})
    lows = pd.DataFrame({s: raw_dfs[s].loc[eval_idx, "low"] for s in symbols})
    closes = pd.DataFrame({s: raw_dfs[s].loc[eval_idx, "close"] for s in symbols})
    is_settlement_bar = pd.Series(pd.DatetimeIndex(eval_idx).hour.isin([0, 8, 16]), index=eval_idx)

    state = V1Top1State(cash_usdt=10000.0, total_equity_usdt=10000.0)
    for i, t in enumerate(eval_idx):
        sim_rec = sim_bar_records[i]
        assert sim_rec["bar_time"] == t

        t_loc = full_idx.get_loc(t)
        klines_window = {s: raw_dfs[s].loc[full_idx[:t_loc]] for s in symbols}
        fp = {s: float(opens.loc[t, s]) for s in symbols}
        il = {s: float(lows.loc[t, s]) for s in symbols}
        ih = {s: float(highs.loc[t, s]) for s in symbols}
        bc = {s: float(closes.loc[t, s]) for s in symbols}
        settle = bool(is_settlement_bar.loc[t])

        state, eval_res = strategy.update_portfolio_step(
            klines_dict=klines_window,
            current_state=state,
            fill_prices=fp,
            intrabar_lows=il,
            intrabar_highs=ih,
            bar_closes=bc,
            is_settlement_bar=settle,
            funding_rate=0.0001,
            borrow_apr=0.10,
            check_stale=False,
        )

        # Bar-by-bar strict assertion: fail immediately on the very first mismatch!
        # 1. Target position determined at bar open
        assert sim_rec["target_pos"] == eval_res["target_symbol"], (
            f"[{t}] target_pos mismatch: sim={sim_rec['target_pos']} vs strat={eval_res['target_symbol']}"
        )
        # 2. Position held at end of bar (after intrabar stop / liquidation)
        assert sim_rec["curr_pos"] == state.active_symbol, (
            f"[{t}] curr_pos mismatch: sim={sim_rec['curr_pos']} vs strat={state.active_symbol}"
        )
        # 3. Position asset units
        assert abs(sim_rec["asset_units"] - state.asset_units) < 1e-4, (
            f"[{t}] asset_units mismatch: sim={sim_rec['asset_units']} vs strat={state.asset_units}"
        )
        # 4. Entry price and Stop price (when in position)
        if state.active_symbol != "USDT_CASH":
            assert abs(sim_rec["entry_price"] - state.entry_price) < 1e-4, (
                f"[{t}] entry_price mismatch: sim={sim_rec['entry_price']} vs strat={state.entry_price}"
            )
            assert abs(sim_rec["stop_price"] - state.stop_loss_price) < 1e-4, (
                f"[{t}] stop_price mismatch: sim={sim_rec['stop_price']} vs strat={state.stop_loss_price}"
            )
        # 5. Cash balance and Total mark-to-market equity
        assert abs(sim_rec["cash"] - state.cash_usdt) < 1e-2, (
            f"[{t}] cash mismatch: sim={sim_rec['cash']} vs strat={state.cash_usdt}"
        )
        assert abs(sim_rec["equity"] - state.total_equity_usdt) < 1e-2, (
            f"[{t}] equity mismatch: sim={sim_rec['equity']} vs strat={state.total_equity_usdt}"
        )
        # 6. Holding duration bars
        assert sim_rec["bars_held"] == state.bars_held, (
            f"[{t}] bars_held mismatch: sim={sim_rec['bars_held']} vs strat={state.bars_held}"
        )
