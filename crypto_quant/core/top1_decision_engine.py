# -*- coding: utf-8 -*-
"""
Stateless Pure Decision Engine for Top-1 Cross-Sectional Rotation
=================================================================
A single, shared, deterministic decision function used by BOTH:
1. Historical Backtesting Engine (SingleLedgerSimulator)
2. Live Server Pipeline (Top1RotationStrategy)

Guarantees 100% mathematical and logical equivalence across backtest and live execution.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd


@dataclass
class Top1DecisionResult:
    target_symbol: str            # 'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', or 'USDT_CASH'
    action: str                   # 'ENTER', 'ROTATE', 'EXIT', 'HOLD'
    top_candidate: str            # Top scored candidate token
    top_score: float              # Momentum + BB Z-score of top candidate
    btc_macro_bull: bool          # BTC > EMA200
    candidate_above_ema: bool     # Candidate > EMA200 (with hysteresis)
    dual_gate_passed: bool        # Both BTC macro gate and asset gate passed
    ranks: List[Dict[str, Any]]   # Full cross-sectional leaderboard
    latest_bar_time: Any          # Timestamp of the decision bar


def compute_top1_decision(
    closes_df: pd.DataFrame,
    atrs_dict: Optional[Dict[str, float]] = None,
    current_symbol: str = "USDT_CASH",
    symbols: Optional[List[str]] = None,
    hysteresis_pct: float = 0.005,
    delta_score_buffer: float = 0.0,
) -> Top1DecisionResult:
    """
    Stateless pure function: Given historical closed bar closes and current position,
    computes the deterministic target allocation.

    Parameters:
    - closes_df: DataFrame of closed candle closes up to bar T-1. Must have >= 120 bars.
    - atrs_dict: Optional dictionary of 14-period ATR values up to bar T-1.
    - current_symbol: Currently held asset ('USDT_CASH' or token symbol).
    - symbols: Universe symbol list (defaults to all columns in closes_df).
    - hysteresis_pct: Buffer around EMA200 to prevent churn (default 0.5%).
    - delta_score_buffer: Minimum score advantage required for challenger to unseat incumbent.
    """
    if symbols is None:
        symbols = list(closes_df.columns)

    if len(closes_df) < 120:
        raise ValueError(f"Insufficient bars for cross-sectional scoring: {len(closes_df)} < 120")

    # 1. Indicator Calculations
    ema200 = closes_df.ewm(span=200).mean()
    bb_mid = closes_df.rolling(120).mean()
    bb_std = closes_df.rolling(120).std()
    bb_z = (closes_df - bb_mid) / (bb_std + 1e-8)
    mom20 = (closes_df / closes_df.shift(120)) - 1.0
    score = bb_z + mom20

    # Latest row (decision point)
    latest_t = closes_df.index[-1]
    latest_closes = closes_df.iloc[-1]
    latest_ema200 = ema200.iloc[-1]
    latest_bb_z = bb_z.iloc[-1]
    latest_mom20 = mom20.iloc[-1]
    latest_score = score.iloc[-1].dropna()

    if len(latest_score) < len(symbols):
        # Fallback if some symbols missing
        top_cand = latest_score.idxmax() if len(latest_score) > 0 else 'BTCUSDT'
    else:
        top_cand = latest_score.idxmax()

    top_score = float(latest_score[top_cand]) if top_cand in latest_score else 0.0

    # BTC Macro Gate
    btc_p = float(latest_closes['BTCUSDT'])
    btc_e = float(latest_ema200['BTCUSDT'])
    btc_macro_bull = bool(btc_p > btc_e)

    # Leaderboard ranks
    sorted_scores = latest_score.sort_values(ascending=False)
    ranks = []
    for rank, (tok, sc) in enumerate(sorted_scores.items(), 1):
        c_p = float(latest_closes[tok])
        e_p = float(latest_ema200[tok])
        z_p = float(latest_bb_z[tok])
        m_p = float(latest_mom20[tok])
        dist_pct = round(((c_p - e_p) / e_p) * 100.0, 2)
        atr_v = float(atrs_dict.get(tok, 0.0)) if atrs_dict else 0.0

        ranks.append({
            "rank": rank,
            "symbol": tok,
            "score": round(float(sc), 3),
            "curr_price": round(c_p, 4),
            "ema200": round(e_p, 4),
            "bb_z": round(z_p, 2),
            "mom20_pct": round(m_p * 100.0, 2),
            "is_above_ema200": bool(c_p > e_p),
            "dist_to_ema_pct": dist_pct,
            "atr_14": round(atr_v, 4),
        })

    # 2. Dual Gate & Hysteresis Decision Logic
    top_cand_close = float(latest_closes[top_cand])
    top_cand_ema = float(latest_ema200[top_cand])
    top_cand_dist = (top_cand_close - top_cand_ema) / top_cand_ema
    candidate_above_ema = bool(top_cand_dist >= hysteresis_pct)
    dual_gate_passed = bool(btc_macro_bull and candidate_above_ema)

    target_symbol = current_symbol
    action = "HOLD"

    if current_symbol == "USDT_CASH":
        if dual_gate_passed:
            target_symbol = top_cand
            action = "ENTER"
        else:
            target_symbol = "USDT_CASH"
            action = "HOLD"
    else:
        # Currently holding a token
        curr_p = float(latest_closes[current_symbol])
        curr_e = float(latest_ema200[current_symbol])
        curr_dist = (curr_p - curr_e) / curr_e
        curr_still_valid = bool(btc_macro_bull and (curr_dist >= -hysteresis_pct))

        if not curr_still_valid:
            if dual_gate_passed:
                target_symbol = top_cand
                action = "ROTATE"
            else:
                target_symbol = "USDT_CASH"
                action = "EXIT"
        else:
            # Current asset is still valid under trend gate
            target_symbol = current_symbol
            action = "HOLD"
            if top_cand != current_symbol:
                challenger_score = float(latest_score[top_cand])
                current_score = float(latest_score[current_symbol])
                if challenger_score >= (current_score + delta_score_buffer):
                    if top_cand_dist >= hysteresis_pct:
                        target_symbol = top_cand
                        action = "ROTATE"

    return Top1DecisionResult(
        target_symbol=target_symbol,
        action=action,
        top_candidate=top_cand,
        top_score=top_score,
        btc_macro_bull=btc_macro_bull,
        candidate_above_ema=candidate_above_ema,
        dual_gate_passed=dual_gate_passed,
        ranks=ranks,
        latest_bar_time=latest_t,
    )
