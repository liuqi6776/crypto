# -*- coding: utf-8 -*-
"""
Unit Tests for MA Congestion Forward Paper Runner
均线密集突破后回踩前瞻纸面实测运行器单元测试
"""

import json
import pytest
import numpy as np
import pandas as pd

from crypto_quant.paper.ma_congestion_forward_runner import MACongestionForwardRunner


@pytest.fixture
def tmp_forward_dir(tmp_path):
    d = tmp_path / "forward_ma_test"
    d.mkdir(parents=True, exist_ok=True)
    return d


def make_mock_klines(periods: int = 50) -> pd.DataFrame:
    dates = pd.date_range("2026-09-20 00:00:00", periods=periods, freq="15min")
    df = pd.DataFrame(index=dates)
    df["open"] = 100.0
    df["high"] = 101.0
    df["low"] = 99.0
    df["close"] = 100.0
    df["volume"] = 1000.0
    return df


def test_forward_runner_initialization_and_idempotency(tmp_forward_dir):
    runner = MACongestionForwardRunner(
        output_dir=str(tmp_forward_dir),
        initial_cash=10000.0,
        symbols=["BTCUSDT", "ETHUSDT"],
    )

    klines_dict = {
        "BTCUSDT": make_mock_klines(50),
        "ETHUSDT": make_mock_klines(50),
    }
    bar_t = klines_dict["BTCUSDT"].index[-1]

    # Process first time
    res1 = runner.process_new_bar(bar_t, klines_dict)
    assert res1["status"] == "PROCESSED"
    assert res1["cash"] == 10000.0

    # Process duplicate bar (idempotency)
    res2 = runner.process_new_bar(bar_t, klines_dict)
    assert res2["status"] == "SKIPPED_DUPLICATE"

    # Verify status.json
    with open(runner.status_file, "r", encoding="utf-8") as f:
        status_data = json.load(f)
    assert status_data["strategy"] == "MA_CONGESTION_BREAKOUT_PULLBACK_15M_EMA"
    assert status_data["last_processed_bar"] == str(bar_t)
    assert status_data["processed_bar_count"] == 1
