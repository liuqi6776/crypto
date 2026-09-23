# -*- coding: utf-8 -*-
"""
Unit Tests for MA Congestion Machine Learning Pipeline
均线密集交汇机器学习流水线单元测试
"""

import pytest
import numpy as np
import pandas as pd

from crypto_quant.ml.congestion_dataset import (
    extract_congestion_events,
    label_congestion_events,
    get_ma_order_type,
    count_ma_crosses,
)
from crypto_quant.ml.purged_cv import PurgedRollingTimeSeriesSplit
from crypto_quant.ml.models import (
    CongestionMLPipeline,
    evaluate_fixed_post_congestion_rule,
    compute_decile_table,
    summarize_model_metrics,
    FEATURE_COLUMNS,
)


def make_synthetic_ohlcv(n_bars: int = 500, base_p: float = 100.0) -> pd.DataFrame:
    """Generate deterministic OHLCV test dataset."""
    dates = pd.date_range("2026-01-01", periods=n_bars, freq="5min", tz="UTC")
    # Sine wave to produce natural swings, crossings, and congestions
    t = np.linspace(0, 10 * np.pi, n_bars)
    prices = base_p + 5.0 * np.sin(t)
    
    df = pd.DataFrame(index=dates)
    df["close"] = prices
    df["open"] = df["close"].shift(1).fillna(base_p)
    df["high"] = np.maximum(df["open"], df["close"]) + 0.5
    df["low"] = np.minimum(df["open"], df["close"]) - 0.5
    df["volume"] = 1000.0
    df["taker_buy_volume"] = 500.0
    return df


def test_ma_order_type_permutations():
    assert get_ma_order_type(100, 90, 80) == 0  # Bullish
    assert get_ma_order_type(100, 80, 90) == 1
    assert get_ma_order_type(90, 100, 80) == 2
    assert get_ma_order_type(80, 100, 90) == 3
    assert get_ma_order_type(90, 80, 100) == 4
    assert get_ma_order_type(80, 90, 100) == 5  # Bearish


def test_extract_and_label_congestion_events():
    df = make_synthetic_ohlcv(600, 100.0)
    events = extract_congestion_events(
        df,
        symbol="BTCUSDT",
        ma_type="EMA",
        congestion_threshold=0.5,
        cooldown_bars=12,
        warmup_bars=200,
    )
    assert not events.empty
    assert "congestion_ratio" in events.columns
    assert "ma_order_type" in events.columns
    assert "ma_cross_count_12" in events.columns
    assert "taker_buy_ratio" in events.columns

    # Verify cooldown check: consecutive events must be separated by at least cooldown_bars
    event_indices = events["event_idx"].values
    if len(event_indices) > 1:
        diffs = np.diff(event_indices)
        assert (diffs >= 12).all(), "Cooldown constraint violated between discrete events!"

    # Label events
    labeled = label_congestion_events(
        df,
        events,
        holding_bars=12,
        spot_fee_rate=0.0008,
        futures_fee_rate=0.0005,
        exec_slip=0.0005,
        stop_slip=0.0015,
    )
    assert not labeled.empty
    assert "long_net_r" in labeled.columns
    assert "short_net_r" in labeled.columns
    assert "action_label" in labeled.columns
    assert set(labeled["action_label"].unique()).issubset({0, 1, 2})


def test_purged_rolling_time_series_split():
    df = make_synthetic_ohlcv(500, 100.0)
    events = extract_congestion_events(df, symbol="BTCUSDT", warmup_bars=100)
    
    cv = PurgedRollingTimeSeriesSplit(n_splits=3, purge_bars=12, min_train_ratio=0.4)
    splits = list(cv.split(events))
    assert len(splits) > 0

    for train_idx, test_idx in splits:
        train_events = events.iloc[train_idx]
        test_events = events.iloc[test_idx]

        max_train_time = train_events["timestamp"].max()
        min_test_time = test_events["timestamp"].min()

        # Purge verification: test start must be at least purge duration after train end
        purge_duration = pd.Timedelta(minutes=12 * 5)
        assert min_test_time >= max_train_time + purge_duration, "Purge buffer leaked between train and test!"


def test_models_and_deciles():
    df = make_synthetic_ohlcv(600, 100.0)
    events = extract_congestion_events(df, symbol="BTCUSDT", warmup_bars=100)
    labeled = label_congestion_events(df, events)

    # Train / test split
    train_df = labeled.iloc[: len(labeled) // 2].copy()
    test_df = labeled.iloc[len(labeled) // 2 :].copy()

    # Model 1: Logistic Regression
    lr_pipe = CongestionMLPipeline(model_type="logistic_regression")
    lr_pipe.fit(train_df, train_df["action_label"])
    evaluated_lr = lr_pipe.evaluate_test_set(test_df)
    assert "prob_buy" in evaluated_lr.columns
    assert "pred_action" in evaluated_lr.columns

    # Model 2: XGBoost
    xgb_pipe = CongestionMLPipeline(model_type="xgboost")
    xgb_pipe.fit(train_df, train_df["action_label"])
    evaluated_xgb = xgb_pipe.evaluate_test_set(test_df)
    assert "pred_score" in evaluated_xgb.columns

    # Decile audit table
    deciles = compute_decile_table(evaluated_xgb)
    assert not deciles.empty
    assert "mean_net_r" in deciles.columns
    assert "win_rate_pct" in deciles.columns
