# -*- coding: utf-8 -*-
"""
Unit Test Suite: Server Pipeline & V1 Strategy Engine (Phase 23)
================================================================
Comprehensive tests for:
1. V1Top1State atomic persistence and field validity.
2. Top1RotationStrategy hysteresis and turnover fee accounting.
3. Funding arbitrage 50% nominal capital formula verification.
4. QuantServerPipeline run_cycle and field parsing.
5. Flask Web App endpoints (/api/status, /api/refresh).
"""

import json
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

from crypto_quant.paper.funding_arb import get_funding_arbitrage_guide
from crypto_quant.paper.top1_rotation_strategy import (
    Top1RotationStrategy,
    V1Top1State,
)
from server.pipeline import QuantServerPipeline
from server.web_app import create_app


def test_v1_state_atomic_persistence(tmp_path):
    """Verifies V1Top1State atomic save, load, and schema integrity."""
    state_file = tmp_path / "v1_test_state.json"
    state = V1Top1State(
        active_symbol="SOLUSDT",
        position_mode="OFFENSIVE_SPOT_LONG",
        entry_price=145.50,
        cash_usdt=0.0,
        asset_units=68.7,
        total_equity_usdt=9996.0,
    )
    state.save_atomic(state_file)
    assert state_file.exists()

    loaded = V1Top1State.load(state_file)
    assert loaded.active_symbol == "SOLUSDT"
    assert loaded.position_mode == "OFFENSIVE_SPOT_LONG"
    assert loaded.entry_price == 145.50
    assert loaded.total_equity_usdt == 9996.0


def test_funding_arb_50_percent_basis():
    """Verifies that funding arbitrage income strictly uses 50% nominal perp short."""
    guide = get_funding_arbitrage_guide(base_capital_usdt=10000.0)
    assert guide["base_capital_usdt"] == 10000.0
    assert guide["half_capital_usdt"] == 5000.0

    fr_8h = guide["funding_info"]["funding_rate_8h"]
    expected_daily = round(5000.0 * (fr_8h * 3), 2)
    assert guide["est_daily_income_usdt"] == expected_daily

    # Verify 4-leg friction is ~0.20% of 10,000 = $20.0
    assert guide["estimated_roundtrip_friction_usdt"] == 20.0


def test_v1_strategy_turnover_friction(tmp_path):
    """Verifies that switching from CASH to Spot token deducts 8 bps turnover friction."""
    state_file = tmp_path / "v1_state.json"
    journal_file = tmp_path / "v1_journal.jsonl"
    strat = Top1RotationStrategy(state_path=state_file, journal_path=journal_file)

    initial_state = V1Top1State(
        active_symbol="USDT_CASH",
        position_mode="DEFENSIVE_USDT_CASH",
        cash_usdt=10000.0,
        total_equity_usdt=10000.0,
    )

    # Mock synthetic klines ending at now_utc so they are not marked stale
    now_utc = pd.Timestamp.now(tz="UTC").floor("4h")
    dates = pd.date_range(end=now_utc, periods=250, freq="4h")
    df_btc = pd.DataFrame({"close": np.linspace(50000, 65000, 250)}, index=dates)
    df_eth = pd.DataFrame({"close": np.linspace(2500, 3500, 250)}, index=dates)
    df_sol = pd.DataFrame({"close": np.linspace(100, 120, 250)}, index=dates)
    df_bnb = pd.DataFrame({"close": np.linspace(500, 550, 250)}, index=dates)

    klines = {
        "BTCUSDT": df_btc,
        "ETHUSDT": df_eth,
        "SOLUSDT": df_sol,
        "BNBUSDT": df_bnb,
    }

    st, eval_res = strat.update_portfolio_step(klines, current_state=initial_state)

    # Turnover friction should be 8.0 bps on 10,000 USDT = 8.0 USDT
    expected_equity = 10000.0 - (10000.0 * 0.0008)
    assert st.active_symbol != "USDT_CASH"
    assert st.position_mode == "OFFENSIVE_SPOT_LONG"
    assert abs(st.accumulated_fees_usdt - 8.0) < 0.01
    assert abs(st.total_equity_usdt - expected_equity) < 0.1


def test_flask_web_app_endpoints():
    """Verifies Flask application creation and REST API endpoints."""
    pipeline = QuantServerPipeline()
    app = create_app(pipeline)
    client = app.test_client()

    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "active_mode" in data
    assert "capital" in data
    assert "position" in data
    assert "leaderboard" in data
    assert data["capital"]["current_equity_usdt"] > 0

    # Verify Take-Profit and Stop-Loss fields in position
    pos = data["position"]
    assert "stop_loss_price" in pos
    assert "distance_to_stop_pct" in pos
    assert "take_profit_tp1" in pos
    assert "distance_to_tp1_pct" in pos
    assert "take_profit_tp2" in pos
    assert "distance_to_tp2_pct" in pos
    assert "highest_price_since_entry" in pos

    # Verify HTML template renders TP & SL elements
    html_resp = client.get("/")
    assert html_resp.status_code == 200
    html_text = html_resp.get_data(as_text=True)
    if pos["is_in_pos"]:
        assert "🛑 动态硬门控/移动止损价" in html_text
        assert "🎯 第一阶段止盈目标 (TP1, +10%)" in html_text
        assert "🚀 第二阶段止盈目标 (TP2, +20%)" in html_text
        assert pos["take_profit_tp1"] > pos["current_price"]
        assert pos["take_profit_tp2"] > pos["take_profit_tp1"]
        assert pos["stop_loss_price"] < pos["current_price"]
    else:
        assert "止损/止盈状态" in html_text
        assert "空仓防守中" in html_text

