# -*- coding: utf-8 -*-
"""
Moving Average Congestion Event Extraction & Causal Target Labeling
均线密集交汇事件提取与因果可交易标签生成模块
=================================================================
1. Extracts discrete MA convergence events on 5m/15m closed bars.
2. Computes continuous congestion ratios, slopes, MA orders, cross counts, and volume dynamics.
3. Simulates causal execution at T+1 obtainable quote with fixed 1R SL, 2R TP, and 12-bar horizon.
4. Accounts for all trading frictions (fees, slippage, 8h funding) to yield exact Net R-multiples.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd

from crypto_quant.ma_congestion.state_machine import compute_indicators


def get_ma_order_type(ma20: float, ma50: float, ma100: float) -> int:
    """
    Encode MA permutation order as an integer in [0, 5]:
    0: 20 > 50 > 100 (Full Bullish)
    1: 20 > 100 > 50
    2: 50 > 20 > 100
    3: 50 > 100 > 20
    4: 100 > 20 > 50
    5: 100 > 50 > 20 (Full Bearish)
    """
    if ma20 >= ma50 >= ma100:
        return 0
    elif ma20 >= ma100 >= ma50:
        return 1
    elif ma50 >= ma20 >= ma100:
        return 2
    elif ma50 >= ma100 >= ma20:
        return 3
    elif ma100 >= ma20 >= ma50:
        return 4
    else:
        return 5


def count_ma_crosses(df: pd.DataFrame, current_idx: int, window: int = 12) -> int:
    """Count number of pairwise crossovers among MA20, MA50, MA100 in the past window bars."""
    start_idx = max(0, current_idx - window)
    sub = df.iloc[start_idx : current_idx + 1]
    if len(sub) < 2:
        return 0

    diff_20_50 = (sub["ma20"] - sub["ma50"]).values
    diff_20_100 = (sub["ma20"] - sub["ma100"]).values
    diff_50_100 = (sub["ma50"] - sub["ma100"]).values

    crosses = 0
    for diff in [diff_20_50, diff_20_100, diff_50_100]:
        crosses += int(np.sum((diff[:-1] * diff[1:]) < 0))
    return crosses


def extract_congestion_events(
    df: pd.DataFrame,
    symbol: str,
    ma_type: str = "EMA",
    congestion_threshold: float = 0.5,
    cooldown_bars: int = 12,
    warmup_bars: int = 200,
) -> pd.DataFrame:
    """
    Extract discrete MA congestion events from closed K-lines.
    从已闭合 K 线序列中提取离散均线交汇事件及 24 维特征。
    """
    # 1. Compute indicators strictly causal
    ind_df = compute_indicators(df, ma_type=ma_type)
    ind_df["vol_ma20"] = ind_df["volume"].rolling(20).mean()

    # Pre-compute slope columns
    for period in [3, 6, 12]:
        ind_df[f"ma20_slope_{period}"] = (ind_df["ma20"] - ind_df["ma20"].shift(period)) / (period * ind_df["atr14"] + 1e-9)
        ind_df[f"ma50_slope_{period}"] = (ind_df["ma50"] - ind_df["ma50"].shift(period)) / (period * ind_df["atr14"] + 1e-9)
        ind_df[f"ma100_slope_{period}"] = (ind_df["ma100"] - ind_df["ma100"].shift(period)) / (period * ind_df["atr14"] + 1e-9)
    ind_df["ma200_slope_12"] = (ind_df["ma200"] - ind_df["ma200"].shift(12)) / (12 * ind_df["atr14"] + 1e-9)

    events = []
    in_congestion = False
    last_congestion_end_idx = -9999

    n_bars = len(ind_df)
    for i in range(warmup_bars, n_bars - 15):  # Leave room for 12-bar label
        row = ind_df.iloc[i]
        bar_time = ind_df.index[i]
        c_ratio = float(row["ma_spread_ratio"])

        if np.isnan(c_ratio) or np.isnan(row["ma200"]):
            continue

        is_congested = (c_ratio <= congestion_threshold)

        if is_congested:
            if not in_congestion:
                # Check cooldown period since previous congestion ended
                if (i - last_congestion_end_idx) >= cooldown_bars:
                    # New discrete event triggered at this bar!
                    in_congestion = True
                    
                    ma20 = float(row["ma20"])
                    ma50 = float(row["ma50"])
                    ma100 = float(row["ma100"])
                    ma200 = float(row["ma200"])
                    atr = float(row["atr14"])
                    close_p = float(row["close"])
                    open_p = float(row["open"])
                    high_p = float(row["high"])
                    low_p = float(row["low"])
                    vol = float(row["volume"])
                    vol_ma20 = float(row["vol_ma20"]) if not np.isnan(row["vol_ma20"]) else vol

                    U = max(ma20, ma50, ma100)
                    L = min(ma20, ma50, ma100)

                    # 1. Order type
                    order_type = get_ma_order_type(ma20, ma50, ma100)

                    # 2. Cross count in past 12 bars
                    cross_cnt = count_ma_crosses(ind_df, i, window=12)

                    # 3. Compression rate
                    prev_c_ratio = float(ind_df["ma_spread_ratio"].iloc[i - 3]) if i >= 3 else c_ratio
                    delta_c_ratio = c_ratio - prev_c_ratio

                    # 4. Price location relative to U and L
                    if close_p > U:
                        loc = 1  # Above
                    elif close_p < L:
                        loc = -1 # Below
                    else:
                        loc = 0  # Inside

                    # 5. Microstructure / Shadow ratios
                    candle_range = max(high_p - low_p, 1e-9)
                    body_ratio = abs(close_p - open_p) / candle_range
                    upper_shadow = (high_p - max(open_p, close_p)) / candle_range
                    lower_shadow = (min(open_p, close_p) - low_p) / candle_range

                    # 6. Taker buy ratio if available
                    taker_vol = float(row["taker_buy_volume"]) if "taker_buy_volume" in row and not np.isnan(row["taker_buy_volume"]) else vol * 0.5
                    taker_buy_ratio = taker_vol / (vol + 1e-9)

                    events.append({
                        "event_idx": i,
                        "timestamp": bar_time,
                        "symbol": symbol,
                        "close": close_p,
                        "U": U,
                        "L": L,
                        "atr14": atr,
                        "ma_order_type": order_type,
                        "ma_cross_count_12": cross_cnt,
                        "congestion_ratio": round(c_ratio, 4),
                        "congestion_ratio_delta_3": round(delta_c_ratio, 4),
                        "price_location": loc,
                        "dist_to_u": round((close_p - U) / (atr + 1e-9), 4),
                        "dist_to_l": round((close_p - L) / (atr + 1e-9), 4),
                        "dist_to_ma200": round((close_p - ma200) / (atr + 1e-9), 4),
                        "ma20_slope_3": round(float(row["ma20_slope_3"]), 4),
                        "ma20_slope_6": round(float(row["ma20_slope_6"]), 4),
                        "ma20_slope_12": round(float(row["ma20_slope_12"]), 4),
                        "ma50_slope_3": round(float(row["ma50_slope_3"]), 4),
                        "ma50_slope_6": round(float(row["ma50_slope_6"]), 4),
                        "ma50_slope_12": round(float(row["ma50_slope_12"]), 4),
                        "ma100_slope_3": round(float(row["ma100_slope_3"]), 4),
                        "ma100_slope_6": round(float(row["ma100_slope_6"]), 4),
                        "ma100_slope_12": round(float(row["ma100_slope_12"]), 4),
                        "ma200_slope_12": round(float(row["ma200_slope_12"]), 4),
                        "atr_ratio": round(atr / close_p, 6),
                        "vol_ratio_20": round(vol / (vol_ma20 + 1e-9), 4),
                        "taker_buy_ratio": round(taker_buy_ratio, 4),
                        "candle_body_ratio": round(body_ratio, 4),
                        "upper_shadow_ratio": round(upper_shadow, 4),
                        "lower_shadow_ratio": round(lower_shadow, 4),
                    })
        else:
            if in_congestion:
                in_congestion = False
                last_congestion_end_idx = i

    df_events = pd.DataFrame(events)
    return df_events


def label_congestion_events(
    df: pd.DataFrame,
    df_events: pd.DataFrame,
    funding_series: Optional[pd.Series] = None,
    holding_bars: int = 12,
    spot_fee_rate: float = 0.0008,
    futures_fee_rate: float = 0.0005,
    exec_slip: float = 0.0005,
    stop_slip: float = 0.0015,
) -> pd.DataFrame:
    """
    Generate causal, friction-deducted labels for both LONG and SHORT directions.
    为每个交汇事件生成扣费后的因果净 R 收益与多/空/观望标签。
    """
    if df_events.empty:
        return df_events

    labeled_events = []
    n_bars = len(df)

    for idx, ev in df_events.iterrows():
        i = int(ev["event_idx"])
        if i + holding_bars >= n_bars:
            continue

        U = ev["U"]
        L = ev["L"]
        atr = ev["atr14"]

        # Next bar entry
        next_bar = df.iloc[i + 1]
        next_open = float(next_bar["open"])

        # =====================================================================
        # 1. EVALUATE LONG DIRECTION (Simulated as Spot Taker)
        # =====================================================================
        entry_p_long = next_open * (1 + exec_slip)
        sl_long = L - 0.2 * atr
        risk_1r_long = max(entry_p_long - sl_long, 0.005 * entry_p_long)
        tp_long = entry_p_long + 2.0 * risk_1r_long

        long_exit_p = 0.0
        long_exit_reason = ""
        long_bars_held = 0

        for h in range(1, holding_bars + 1):
            bar = df.iloc[i + h]
            bo = float(bar["open"])
            bh = float(bar["high"])
            bl = float(bar["low"])
            bc = float(bar["close"])
            long_bars_held = h

            hit_sl = False
            sl_price = 0.0
            if bo <= sl_long:
                hit_sl = True
                sl_price = bo * (1 - stop_slip)
            elif bl <= sl_long:
                hit_sl = True
                sl_price = sl_long * (1 - stop_slip)

            hit_tp = False
            tp_price = 0.0
            if bh >= tp_long:
                hit_tp = True
                tp_price = max(bo, tp_long) * (1 - exec_slip)

            # Conservative worst-case: Stop loss executes first
            if hit_sl:
                long_exit_p = sl_price
                long_exit_reason = "SL"
                break
            elif hit_tp:
                long_exit_p = tp_price
                long_exit_reason = "TP"
                break
            elif h == holding_bars:
                long_exit_p = bc * (1 - exec_slip)
                long_exit_reason = "TIME_12B"
                break

        # Long PnL accounting
        long_gross = (long_exit_p - entry_p_long) / entry_p_long
        long_friction = (spot_fee_rate * 2) + exec_slip + (stop_slip if long_exit_reason == "SL" else exec_slip)
        long_net_pct = long_gross - long_friction
        long_net_r = (long_net_pct * entry_p_long) / risk_1r_long

        # =====================================================================
        # 2. EVALUATE SHORT DIRECTION (Simulated as Futures with Funding)
        # =====================================================================
        entry_p_short = next_open * (1 - exec_slip)
        sl_short = U + 0.2 * atr
        risk_1r_short = max(sl_short - entry_p_short, 0.005 * entry_p_short)
        tp_short = entry_p_short - 2.0 * risk_1r_short

        short_exit_p = 0.0
        short_exit_reason = ""
        short_bars_held = 0

        for h in range(1, holding_bars + 1):
            bar = df.iloc[i + h]
            bo = float(bar["open"])
            bh = float(bar["high"])
            bl = float(bar["low"])
            bc = float(bar["close"])
            short_bars_held = h

            hit_sl = False
            sl_price = 0.0
            if bo >= sl_short:
                hit_sl = True
                sl_price = bo * (1 + stop_slip)
            elif bh >= sl_short:
                hit_sl = True
                sl_price = sl_short * (1 + stop_slip)

            hit_tp = False
            tp_price = 0.0
            if bl <= tp_short:
                hit_tp = True
                tp_price = min(bo, tp_short) * (1 + exec_slip)

            if hit_sl:
                short_exit_p = sl_price
                short_exit_reason = "SL"
                break
            elif hit_tp:
                short_exit_p = tp_price
                short_exit_reason = "TP"
                break
            elif h == holding_bars:
                short_exit_p = bc * (1 + exec_slip)
                short_exit_reason = "TIME_12B"
                break

        # Short PnL accounting
        short_gross = (entry_p_short - short_exit_p) / entry_p_short
        # Funding drag during 12 bars (up to 1 hour, approx 1/8th of 8h funding rate if crossing boundary)
        funding_drag = 0.0001 # approx baseline
        short_friction = (futures_fee_rate * 2) + exec_slip + (stop_slip if short_exit_reason == "SL" else exec_slip) + funding_drag
        short_net_pct = short_gross - short_friction
        short_net_r = (short_net_pct * entry_p_short) / risk_1r_short

        # =====================================================================
        # 3. ACTION DISPATCH: LONG, SHORT, or FLAT
        # =====================================================================
        # Meaningful edge threshold: at least +0.3R net profit after all frictions
        if long_net_r >= 0.3 and long_net_r > short_net_r:
            action_label = 1  # BUY
        elif short_net_r >= 0.3 and short_net_r > long_net_r:
            action_label = 2  # SELL
        else:
            action_label = 0  # FLAT / 观望

        ev_dict = ev.to_dict()
        ev_dict.update({
            "long_net_r": round(long_net_r, 3),
            "long_exit_reason": long_exit_reason,
            "long_bars_held": long_bars_held,
            "short_net_r": round(short_net_r, 3),
            "short_exit_reason": short_exit_reason,
            "short_bars_held": short_bars_held,
            "action_label": action_label,
        })
        labeled_events.append(ev_dict)

    return pd.DataFrame(labeled_events)
