# -*- coding: utf-8 -*-
"""
Dual-Sleeve Portfolio Engine for Spatio-Temporal Transformer Quantitative System (Phase 12)
Features:
- Multi-Factor Top-Exhaustion Radar (Price Extension, Perpetual Funding Crowding, FNG Euphoria)
- Dynamic Continuous Position Sizing w_t in [0.35, 1.0] (Automatic High-Point Downsizing)
- State-Driven Re-entry: Zero Clock Freezes! Re-entry unlocked on stabilization candle.
- Sleeve 1 (70%): Adaptive Momentum with Dynamic High-Point Sizing & Hard Stop-Loss
- Sleeve 2 (30%): 8h Micro-Momentum Basis Arbitrage (3x / Day)
"""

import os
import sys
import numpy as np
import pandas as pd


def compute_top_exhaustion_risk(closes, funding_rate, fng_score):
    """
    Computes a composite Top-Exhaustion Risk Index in [0.0, 1.0] based on:
    1. 72-bar (12-day) EMA Price Extension / Stretch
    2. Binance 8h perpetual funding rate
    3. Alternative.me Fear & Greed Index
    """
    ema72 = closes.shift(1).ewm(span=72).mean()
    stretch72 = ((closes.shift(1) - ema72) / (ema72 + 1e-8)).fillna(0.0).values

    stretch_risk = np.clip(stretch72 / 0.05, 0.0, 1.0) # 0 to 1 as stretch goes 0% -> +5%
    funding_risk = np.clip((funding_rate * 100.0) / 0.02, 0.0, 1.0) # 0 to 1 as funding goes 0 -> 0.02%
    fng_risk = np.clip((fng_score - 60.0) / 25.0, 0.0, 1.0) # 0 to 1 as FNG goes 60 -> 85

    composite_risk = 0.45 * stretch_risk + 0.35 * funding_risk + 0.20 * fng_risk
    # Continuous Position Sizing: 1.0 at low risk, scales down to 0.35 at peak overheat
    pos_size = np.clip(1.0 - 0.65 * np.maximum(0.0, composite_risk - 0.25) / 0.75, 0.35, 1.0)
    return composite_risk, pos_size


def compute_sleeve_adaptive(preds, opens, closes, lows, fng, stb,
                            funding=None, basis=None,
                            stop_loss=0.035, use_dyn=True, use_top_derisking=True):
    """
    Sleeve 1: Adaptive Momentum Exit with Dynamic Entry Threshold, High-Point Sizing & Stop-Loss
    Zero Clock Cooldown: Re-entry unlocked immediately on green candle (Close >= Open).
    """
    p_series = pd.Series(preds.values, index=preds.index)
    prior_mean = p_series.shift(1).rolling(72).mean()
    prior_std = p_series.shift(1).rolling(72).std() + 1e-8
    z_vals = ((p_series - prior_mean) / prior_std).values

    funding_vals = funding.values if funding is not None else np.zeros(len(preds))

    if use_dyn and (funding is not None) and (basis is not None):
        basis_mean = basis.shift(1).rolling(72).mean()
        basis_std = basis.shift(1).rolling(72).std() + 1e-8
        basis_z = np.clip(((basis - basis_mean) / basis_std).fillna(0.0).values, -2.0, 2.0)
        z_threshold = 1.0 - 0.20 * np.tanh(50.0 * funding_vals) - 0.10 * basis_z
    else:
        z_threshold = np.ones(len(preds)) * 1.0

    raw_sig = (z_vals > z_threshold) & (stb > 0.0) & (fng < 85)

    if use_top_derisking:
        _, target_size = compute_top_exhaustion_risk(closes, funding_vals, fng)
    else:
        target_size = np.ones(len(preds))

    n = len(preds)
    pos = np.zeros(n)
    in_pos = False
    entry_bar = 0
    in_waterfall = False
    trades = []

    # ZERO 16-HOUR CLOCK FREEZE!
    for i in range(n - 2):
        if in_waterfall:
            if closes.iloc[i] >= opens.iloc[i]: # stabilization confirmation
                in_waterfall = False
            else:
                pos[i] = 0.0
                continue

        if not in_pos:
            if raw_sig[i]:
                in_pos = True
                entry_bar = i
                pos[i] = target_size[i]
            else:
                pos[i] = 0.0
        else:
            entry_p = opens.iloc[entry_bar + 1]
            curr_c = closes.iloc[i]
            is_stop = False

            if stop_loss is not None and (curr_c / entry_p - 1.0 <= -stop_loss):
                is_stop = True

            should_exit = (not raw_sig[i]) or is_stop

            if should_exit:
                in_pos = False
                pos[i] = 0.0
                entry_idx = entry_bar + 1
                exit_idx = i + 1
                exit_p = opens.iloc[exit_idx]
                gross_ret = exit_p / entry_p - 1.0
                duration_bars = exit_idx - entry_idx
                duration_hours = duration_bars * 4
                taker_fee = 2 * 0.0005
                funding_fee = duration_bars * 0.00005
                net_ret = gross_ret - taker_fee - funding_fee

                trades.append({
                    'entry_time': opens.index[entry_idx],
                    'exit_time': opens.index[exit_idx],
                    'entry_price': entry_p,
                    'exit_price': exit_p,
                    'size': target_size[entry_bar],
                    'duration_hours': duration_hours,
                    'gross_ret': gross_ret,
                    'net_ret': net_ret,
                    'weighted_pnl': net_ret * target_size[entry_bar],
                    'is_stop_loss': is_stop
                })

                if is_stop:
                    in_waterfall = True # Cleared as soon as market stabilizes
            else:
                pos[i] = target_size[entry_bar]

    o_series = pd.Series(opens.values, index=opens.index)
    rets_oto = (o_series.shift(-2) / o_series.shift(-1) - 1).values
    trade_signals = pd.Series(pos).diff().abs().fillna(0).values
    cost_bar = trade_signals * 0.0005
    sleeve_rets = (pos * rets_oto - cost_bar)[:-2]

    return pd.Series(sleeve_rets, index=opens.index[:-2]), pd.DataFrame(trades), pd.Series(pos[:-2], index=opens.index[:-2])


def compute_sleeve_8h(preds, opens, fng, stb):
    """
    Sleeve 2: 8h Fixed Horizon (3x / Day) Basis Momentum
    """
    p_series = pd.Series(preds.values, index=preds.index)
    prior_mean = p_series.shift(1).rolling(72).mean()
    prior_std = p_series.shift(1).rolling(72).std() + 1e-8
    z_vals = ((p_series - prior_mean) / prior_std).values

    raw_sig = (z_vals > 1.0) & (stb > 0.0) & (fng < 85)

    n = len(preds)
    pos = np.zeros(n)
    i = 0
    while i < n - 2:
        if raw_sig[i]:
            pos[i] = 1.0
            if i + 1 < n - 2:
                pos[i + 1] = 1.0
            i += 2
        else:
            pos[i] = 0.0
            i += 1

    o_series = pd.Series(opens.values, index=opens.index)
    rets_oto = (o_series.shift(-2) / o_series.shift(-1) - 1).values
    trade_signals = pd.Series(pos).diff().abs().fillna(0).values
    cost_bar = trade_signals * 0.0005
    sleeve_rets = (pos * rets_oto - cost_bar)[:-2]

    return pd.Series(sleeve_rets, index=opens.index[:-2]), pd.Series(pos[:-2], index=opens.index[:-2])


def build_dual_sleeve_portfolio(sleeve1_rets, sleeve2_rets, w1=0.70, w2=0.30):
    """
    Linear capital-weighted combination of sleeves
    """
    combined_rets = w1 * sleeve1_rets + w2 * sleeve2_rets
    cum = (1 + combined_rets).cumprod()
    total_ret = cum.iloc[-1] - 1.0
    cagr = (1 + total_ret) ** (1 / (len(combined_rets) / 2190)) - 1.0 if total_ret > -1 else -1.0
    dd = (cum - cum.cummax()) / cum.cummax()
    mdd = dd.min()
    daily_equity = cum.resample('1D').last().ffill()
    daily_rets = daily_equity.pct_change().dropna()
    daily_sharpe = daily_rets.mean() / (daily_rets.std() + 1e-8) * np.sqrt(365)
    calmar = cagr / abs(mdd) if abs(mdd) > 1e-6 else 0.0

    return {
        'returns': combined_rets,
        'cumulative_equity': cum,
        'total_return': total_ret,
        'cagr': cagr,
        'max_drawdown': mdd,
        'daily_sharpe': daily_sharpe,
        'calmar': calmar
    }
