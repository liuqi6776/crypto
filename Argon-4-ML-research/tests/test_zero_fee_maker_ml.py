"""Unit tests for the 0-Fee Maker ML research study (causality, targets, splits, accounting)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.zero_fee_maker_ml_v1.code.backtest import _funding_sum_between
from research.zero_fee_maker_ml_v1.code.features import (
    HORIZON_BARS,
    _symbol_price_and_flow_block,
    build_dataset_bundle,
)
from research.zero_fee_maker_ml_v1.code.models import FOLDS, PURGE_BARS


def test_price_and_flow_block_strictly_causal() -> None:
    """Perturbing bars > i must never change any feature value at bar <= i."""
    rng = np.random.default_rng(123)
    n = 600
    idx = pd.date_range("2025-01-01", periods=n, freq="5min", tz="UTC")
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.002, size=n)))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    high = np.maximum(open_, close) * (1.0 + rng.uniform(0.0001, 0.003, size=n))
    low = np.minimum(open_, close) * (1.0 - rng.uniform(0.0001, 0.003, size=n))
    vol = rng.uniform(1000.0, 5000.0, size=n)
    qvol = vol * close
    cnt = rng.integers(200, 2000, size=n).astype(float)
    tbv = vol * rng.uniform(0.3, 0.7, size=n)
    tbqv = tbv * close

    df1 = pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": vol,
            "quote_volume": qvol,
            "count": cnt,
            "taker_buy_volume": tbv,
            "taker_buy_quote_volume": tbqv,
        },
        index=idx,
    )
    df2 = df1.copy()
    cut = 400
    # Massively perturb all bars strictly after cut
    df2.iloc[cut + 1 :, :] = df2.iloc[cut + 1 :, :] * 3.5 + 50.0

    f1, _, _ = _symbol_price_and_flow_block(df1, "tgt")
    f2, _, _ = _symbol_price_and_flow_block(df2, "tgt")

    a1 = f1.iloc[300 : cut + 1].to_numpy()
    a2 = f2.iloc[300 : cut + 1].to_numpy()
    assert np.allclose(a1, a2, equal_nan=True), "Future bar perturbation leaked into past features!"


def test_walk_forward_folds_disjoint_and_purged() -> None:
    """Verify Train, Val, and Test windows have at least 2 hours (24 x 5m bars) purge gap."""
    min_gap = pd.Timedelta(minutes=5 * PURGE_BARS)
    for fold in FOLDS:
        tr_e = pd.Timestamp(fold.train_end)
        va_s = pd.Timestamp(fold.val_start)
        va_e = pd.Timestamp(fold.val_end)
        te_s = pd.Timestamp(fold.test_start)
        assert va_s - tr_e >= min_gap, f"{fold.name} train->val gap < {min_gap}"
        assert te_s - va_e >= min_gap, f"{fold.name} val->test gap < {min_gap}"


def test_funding_interval_sum_exact() -> None:
    """Funding settlements at t_start are excluded; settlements in (t_start, t_end] are included."""
    f_ms = np.array([1000, 2000, 3000, 4000], dtype=np.int64)
    f_rate = np.array([0.0001, -0.0002, 0.0003, 0.0005], dtype=float)
    assert np.isclose(_funding_sum_between(f_ms, f_rate, 1000, 3000), -0.0002 + 0.0003)
    assert np.isclose(_funding_sum_between(f_ms, f_rate, 1000, 1999), 0.0)


def test_multi_horizon_targets_match_brute_force() -> None:
    """Verify Y0 and Y1 target arrays match brute-force forward slices."""
    bundle = build_dataset_bundle("SOLUSDT")
    o = bundle.open_raw
    h = bundle.high_raw
    l = bundle.low_raw
    c = bundle.close_raw

    for sample_idx in (1500, 50000, 150000):
        o_entry = o[sample_idx + 1]
        for h_min, k_bars in HORIZON_BARS.items():
            sl_h = h[sample_idx + 1 : sample_idx + 1 + k_bars]
            sl_l = l[sample_idx + 1 : sample_idx + 1 + k_bars]
            c_exit = c[sample_idx + k_bars]

            exp_y0 = (c_exit - o_entry) / o_entry
            exp_rng = (np.max(sl_h) - np.min(sl_l)) / o_entry
            exp_mae_l = max(0.0, (o_entry - np.min(sl_l)) / o_entry)
            exp_mae_s = max(0.0, (np.max(sl_h) - o_entry) / o_entry)

            assert np.isclose(bundle.y0_ret[h_min][sample_idx], exp_y0)
            assert np.isclose(bundle.y1_range[h_min][sample_idx], exp_rng)
            assert np.isclose(bundle.y1_mae_long[h_min][sample_idx], exp_mae_l)
            assert np.isclose(bundle.y1_mae_short[h_min][sample_idx], exp_mae_s)


def test_phase2_dual_book_netting_reduces_turnover() -> None:
    """Verify that combining two offsetting sub-books (0.5 * p30 + 0.5 * p60) nets out opposing flips."""
    from research.zero_fee_maker_ml_v1.code.phase2_focused_study import _generate_bar_positions

    rng = np.random.default_rng(7)
    n_va, n_te = 2000, 1000
    va_s = rng.normal(0.0, 1.0, size=n_va)
    te_s = rng.normal(0.0, 1.0, size=n_te)
    va_y1 = rng.uniform(0.001, 0.01, size=n_va)
    te_y1 = rng.uniform(0.001, 0.01, size=n_te)
    te_mask = np.zeros(3000, dtype=bool)
    te_mask[-n_te:] = True

    # Dummy bundle placeholder (not dereferenced inside _generate_bar_positions)
    p30 = _generate_bar_positions(
        None, te_mask, va_s, te_s, va_y1, te_y1, va_y1, te_y1, step_bars=6, entry_q=0.90, hold_q=0.55, y1_cap_q=0.85
    )
    p60 = _generate_bar_positions(
        None, te_mask, va_s, -te_s, va_y1, te_y1, va_y1, te_y1, step_bars=12, entry_q=0.90, hold_q=0.55, y1_cap_q=0.85
    )
    p_dual = 0.5 * p30 + 0.5 * p60
    assert np.max(np.abs(p_dual)) <= 1.0
    # Combined turnover must be <= average of individual turnovers
    turn_30 = np.sum(np.abs(np.diff(p30)))
    turn_60 = np.sum(np.abs(np.diff(p60)))
    turn_dual = np.sum(np.abs(np.diff(p_dual)))
    assert turn_dual <= 0.5 * (turn_30 + turn_60) + 1e-9


def test_live_signal_engine_deterministic_and_bounded() -> None:
    """Verify ZeroFeeMakerMasterEngine loads exported bundle and produces bounded causal packets."""
    import pickle
    from research.zero_fee_maker_ml_v1.code.features import ROOT
    from research.zero_fee_maker_ml_v1.code.live_signal_engine import ZeroFeeMakerMasterEngine

    pkl_path = ROOT / "research" / "zero_fee_maker_ml_v1" / "runs" / "latest_live_model_bundle.pkl"
    assert pkl_path.exists(), "latest_live_model_bundle.pkl must exist"
    with open(pkl_path, "rb") as f:
        art = pickle.load(f)

    eng1 = ZeroFeeMakerMasterEngine(art, min_rebalance_delta=0.20)
    eng2 = ZeroFeeMakerMasterEngine(art, min_rebalance_delta=0.20)

    rng = np.random.default_rng(99)
    ts0 = pd.Timestamp("2026-09-24 12:00:00+00:00")
    for step in range(20):
        x_row = rng.normal(0.0, 0.01, size=len(art["feature_cols"])).astype(np.float32)
        p1 = eng1.on_new_5m_bar(ts0 + pd.Timedelta(minutes=5 * step), 85000.0 + step * 10.0, x_row)
        p2 = eng2.on_new_5m_bar(ts0 + pd.Timedelta(minutes=5 * step), 85000.0 + step * 10.0, x_row)
        assert p1 == p2
        assert -1.0 <= p1.target_position_fraction <= 1.0
        assert 1.0 <= p1.recommended_max_leverage <= 3.0
        assert p1.predicted_y1_mae_long_60m_bp > 0.0


def test_divergence_no_bfill_future_leakage_under_nan_blocks() -> None:
    """Audit Item #10: Verify that even with NaN gaps, future data changes never alter past divergence features."""
    from research.zero_fee_maker_ml_v1.code.phase4_divergence_study import compute_8_divergence_features_on_ohlc

    rng = np.random.default_rng(123)
    n = 300
    idx = pd.date_range("2025-01-01", periods=n, freq="5min", tz="UTC")
    c1 = pd.Series(50000.0 + np.cumsum(rng.normal(0.0, 50.0, size=n)), index=idx)
    h1 = c1 + rng.uniform(10.0, 80.0, size=n)
    l1 = c1 - rng.uniform(10.0, 80.0, size=n)

    # Inject NaNs around bar 120..155 so a 28-bar rolling window hits all-NaN if unguarded
    c1.iloc[120:155] = np.nan
    h1.iloc[120:155] = np.nan
    l1.iloc[120:155] = np.nan

    c2, h2, l2 = c1.copy(), h1.copy(), l1.copy()
    # Wildly alter future bars >= 160
    c2.iloc[160:] *= 2.5
    h2.iloc[160:] *= 2.5
    l2.iloc[160:] *= 2.5

    for co_piv in (False, True):
        f1 = compute_8_divergence_features_on_ohlc(h1, l1, c1, suffix="5m", co_pivot=co_piv)
        f2 = compute_8_divergence_features_on_ohlc(h2, l2, c2, suffix="5m", co_pivot=co_piv)
        assert np.allclose(f1.iloc[:160].to_numpy(), f2.iloc[:160].to_numpy(), equal_nan=True)


def test_evaluate_position_path_date_alignment_across_month_boundary() -> None:
    """Audit Item #5: Decision at Jan 31 23:55 executing over Feb 1 00:00..00:05 must belong to February."""
    from types import SimpleNamespace
    from research.zero_fee_maker_ml_v1.code.phase2_focused_study import evaluate_position_path

    idx = pd.to_datetime(
        [
            "2026-01-31 23:45:00+00:00",
            "2026-01-31 23:50:00+00:00",
            "2026-01-31 23:55:00+00:00",  # k=2 decision bar -> executes at eb=3 (2026-02-01 00:00)
            "2026-02-01 00:00:00+00:00",
            "2026-02-01 00:05:00+00:00",
            "2026-02-01 00:10:00+00:00",
        ]
    )
    o_raw = np.array([100.0, 100.0, 100.0, 100.0, 110.0, 110.0], dtype=np.float64)
    dummy_bundle = SimpleNamespace(
        index=idx,
        open_raw=o_raw,
        high_raw=o_raw * 1.01,
        low_raw=o_raw * 0.99,
        funding_ms=np.array([], dtype=np.int64),
        funding_rate=np.array([], dtype=np.float64),
    )
    te_mask = np.array([True, True, True, True, True, False], dtype=bool)
    # Position +1 only on k=2 (decision at Jan 31 23:55 -> realized from 2026-02-01 00:00 to 00:05: +10%)
    pos_path = np.array([0.0, 0.0, 1.0, 0.0, 0.0], dtype=np.float64)

    res, monthly_rets = evaluate_position_path(dummy_bundle, te_mask, pos_path, one_way_cost_bp=0.0, leverage=1.0)
    assert np.isclose(res["total_return_pct"], 10.0, atol=1e-2)
    jan_ret = float(monthly_rets.loc["2026-01-31"])
    feb_ret = float(monthly_rets.loc["2026-02-28"])
    assert np.isclose(jan_ret, 0.0, atol=1e-6), f"Expected 0% in Jan, got {jan_ret}"
    assert np.isclose(feb_ret, 0.10, atol=1e-6), f"Expected +10% in Feb, got {feb_ret}"


def test_frozen_threshold_preserves_decisions_when_event_is_zero() -> None:
    """Audit Item #8: When threshold_va_sc=va_base is frozen and te_event=0, decisions match baseline 100%."""
    from research.zero_fee_maker_ml_v1.code.phase2_focused_study import _generate_bar_positions

    rng = np.random.default_rng(42)
    va_base = rng.normal(0.0, 1.0, size=1000)
    va_event = rng.uniform(0.0, 5.0, size=1000)  # Large validation event shift
    te_base = rng.normal(0.0, 1.0, size=500)
    te_zero_event = np.zeros(500, dtype=np.float64)
    va_y1 = np.full(1000, 0.002)
    te_y1 = np.full(500, 0.002)
    te_mask = np.ones(500, dtype=bool)

    p_base = _generate_bar_positions(
        None, te_mask, va_base, te_base, va_y1, te_y1, va_y1, te_y1, step_bars=6
    )
    p_frozen = _generate_bar_positions(
        None,
        te_mask,
        va_base + 0.5 * va_event,
        te_base + 0.5 * te_zero_event,
        va_y1,
        te_y1,
        va_y1,
        te_y1,
        step_bars=6,
        threshold_va_sc=va_base,
    )
    assert np.array_equal(p_base, p_frozen)


def test_phase5_fib_features_causal_prefix_invariance() -> None:
    """Verify that Phase 5 Fibonacci (0.236/0.382) + Stop/Target protection features are 100% causal
    (prefix-invariant when future bars are truncated or shocked)."""
    from decimal import Decimal
    from types import SimpleNamespace
    from research.zero_fee_maker_ml_v1.code.phase5_fib_divergence_study import extract_timeframe_fib_features

    rng = np.random.default_rng(123)
    n = 1200
    idx = pd.date_range("2024-01-01 00:00:00+00:00", periods=n, freq="5min")
    steps = rng.normal(0.0, 0.0025, size=n)
    close = 40000.0 * np.exp(np.cumsum(steps))
    open_p = np.roll(close, 1)
    open_p[0] = close[0]
    high = np.maximum(open_p, close) * (1.0 + rng.uniform(0.0005, 0.003, size=n))
    low = np.minimum(open_p, close) * (1.0 - rng.uniform(0.0005, 0.003, size=n))
    vol = rng.uniform(10.0, 500.0, size=n)

    sig_full = pd.DataFrame(
        {"open_time": idx, "open": open_p, "high": high, "low": low, "close": close, "volume": vol}
    )
    bundle_full = SimpleNamespace(
        index=idx, open_raw=open_p, high_raw=high, low_raw=low, close_raw=close
    )
    df_full, _ = extract_timeframe_fib_features(
        sig_full,
        tf_label="5m",
        tf_minutes=5,
        bundle=bundle_full,
        tick_size=Decimal("0.1"),
        start_eligible_utc="2024-01-02T00:00:00Z",
    )

    cut = 900
    sig_cut = sig_full.iloc[:cut].copy().reset_index(drop=True)
    bundle_cut = SimpleNamespace(
        index=idx[:cut],
        open_raw=open_p[:cut],
        high_raw=high[:cut],
        low_raw=low[:cut],
        close_raw=close[:cut],
    )
    df_cut, _ = extract_timeframe_fib_features(
        sig_cut,
        tf_label="5m",
        tf_minutes=5,
        bundle=bundle_cut,
        tick_size=Decimal("0.1"),
        start_eligible_utc="2024-01-02T00:00:00Z",
    )

    max_diff = float(np.max(np.abs(df_full.iloc[:cut].to_numpy() - df_cut.to_numpy())))
    assert max_diff == 0.0, f"Causal prefix invariance violated: max_diff={max_diff}"

    # Also test cutting directly on an armed bar where a plan is waiting for 0.236 entry (no real cancel)
    armed_bars = np.flatnonzero(
        (df_full["reg_bull_arm_score_5m"].to_numpy() > 0)
        | (df_full["reg_bear_arm_score_5m"].to_numpy() > 0)
        | (df_full["hid_bull_arm_score_5m"].to_numpy() > 0)
        | (df_full["hid_bear_arm_score_5m"].to_numpy() > 0)
    )
    assert len(armed_bars) > 0
    for c_idx in armed_bars[:5]:
        c_len = int(c_idx) + 1
        sig_c = sig_full.iloc[:c_len].copy().reset_index(drop=True)
        bundle_c = SimpleNamespace(
            index=idx[:c_len],
            open_raw=open_p[:c_len],
            high_raw=high[:c_len],
            low_raw=low[:c_len],
            close_raw=close[:c_len],
        )
        df_c, _ = extract_timeframe_fib_features(
            sig_c,
            tf_label="5m",
            tf_minutes=5,
            bundle=bundle_c,
            tick_size=Decimal("0.1"),
            start_eligible_utc="2024-01-02T00:00:00Z",
        )
        diff_c = float(np.max(np.abs(df_full.iloc[:c_len].to_numpy() - df_c.to_numpy())))
        assert diff_c == 0.0, f"End-of-slice fake cancellation at c_len={c_len}: diff={diff_c}"


def test_summarize_variant_cross_year_max_drawdown() -> None:
    """Audit Item #2: Cross-year MaxDD must reflect the worse/connected drawdown, never max(dd_2025, dd_2026)."""
    from types import SimpleNamespace
    from research.zero_fee_maker_ml_v1.code.phase5_fib_divergence_study import _summarize_variant

    idx_25 = pd.date_range("2025-01-01 00:00:00+00:00", periods=40, freq="5min")
    idx_26 = pd.date_range("2026-01-01 00:00:00+00:00", periods=40, freq="5min")
    idx = idx_25.append(idx_26)

    # Construct 2025 with a -30% drop at 1x and 2026 with a -10% drop at 1x
    o_raw = np.ones(80, dtype=np.float64) * 100.0
    o_raw[10:25] = 70.0  # -30% drawdown in 2025
    o_raw[25:40] = 95.0
    o_raw[50:65] = 85.5  # -10% drawdown in 2026
    o_raw[65:] = 100.0

    dummy_bundle = SimpleNamespace(
        index=idx,
        open_raw=o_raw,
        high_raw=o_raw * 1.001,
        low_raw=o_raw * 0.999,
        funding_ms=np.array([], dtype=np.int64),
        funding_rate=np.array([], dtype=np.float64),
    )
    m25 = np.zeros(80, dtype=bool)
    m25[:39] = True
    m26 = np.zeros(80, dtype=bool)
    m26[40:79] = True

    pos_by_year = {
        2025: (m25, np.ones(39, dtype=np.float64)),
        2026: (m26, np.ones(39, dtype=np.float64)),
    }
    row = _summarize_variant("TEST_DD", "TEST", "FROZEN_TH", dummy_bundle, pos_by_year, leverage=1.0)
    assert row["dd_2025_pct"] <= -29.0
    assert row["dd_2026_pct"] >= -15.0
    assert row["max_dd_2025_2026_pct"] <= row["dd_2025_pct"]


def test_shadow_runner_bar_by_bar_arrival_settlement() -> None:
    """Audit Item #7: Stepping bar-by-bar as total_bars grows must settle previous bars as soon as open[b+2] arrives."""
    from dataclasses import dataclass
    from types import SimpleNamespace
    from research.zero_fee_maker_ml_v1.code.shadow_live_dashboard import INITIAL_CAPITAL_USD, ShadowBookRunner

    @dataclass
    class DummyPkt:
        target_leveraged_exposure: float = 3.0
        target_position_fraction: float = 1.0
        execution_instruction: str = "HOLD"

    runner = object.__new__(ShadowBookRunner)
    runner.equity_usd = INITIAL_CAPITAL_USD
    runner.peak_equity_usd = INITIAL_CAPITAL_USD
    runner.max_dd_pct = 0.0
    runner.cum_Gross_pnl_usd = 0.0
    runner.cum_as_cost_usd = 0.0
    runner.cum_funding_usd = 0.0
    runner.n_rebalances = 0
    runner.n_winning_bars = 0
    runner.n_active_bars = 0
    runner.equity_history = []
    runner.recent_signals = []
    runner.recent_trades = []
    runner.pending_settlements = []

    ts = pd.date_range("2026-10-27 00:00:00+00:00", periods=5, freq="5min")
    runner.idx_all = ts
    runner.idx_ms = (ts.astype("int64") // 10**6).to_numpy()
    runner.open_all = np.array([100.0, 100.0, 101.0, 102.0, 103.0], dtype=np.float64)
    runner.close_all = np.array([100.0, 100.5, 101.5, 102.5, 103.5], dtype=np.float64)
    runner.X_all = np.zeros((5, 4), dtype=np.float32)
    runner.F_all = np.zeros((5, 4), dtype=np.float32)
    runner.e4_qtr_pos = np.ones(5, dtype=np.float64)
    runner.bundle = SimpleNamespace(
        funding_ms=np.array([], dtype=np.int64), funding_rate=np.array([], dtype=np.float64)
    )
    runner.engine = SimpleNamespace(on_new_5m_bar=lambda *a, **kw: DummyPkt())

    prev_lev = 0.0
    for step_idx in range(3):
        runner.total_bars = step_idx + 1
        pkt = runner._step_single_index(step_idx, prev_lev)
        prev_lev = pkt.target_leveraged_exposure

    # By Arrival 3 (total_bars=3), bar 0 (executing open[1]=100 -> open[2]=101, +1% * 3x = +3%) must have settled!
    assert runner.cum_Gross_pnl_usd > 2900.0
    assert runner.equity_usd > 102900.0





