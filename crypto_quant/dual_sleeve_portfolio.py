# -*- coding: utf-8 -*-
"""
Dual-Sleeve Portfolio Engine for Spatio-Temporal Transformer Quantitative System
Combines:
- Sleeve 1 (70%): Adaptive Momentum with Intra-Trade Hard Stop-Loss & Cooldown
- Sleeve 2 (30%): 8h Micro-Momentum Basis Arbitrage (3x / Day)
"""

import os
import sys
import numpy as np
import pandas as pd


def compute_sleeve_adaptive(preds, opens, closes, lows, fng, stb,
                            funding=None, basis=None,
                            stop_loss=0.035, cd_bars=4, use_dyn=True):
    """
    Sleeve 1: Adaptive Momentum Exit with Dynamic Entry Threshold & Hard Stop-Loss
    """
    p_series = pd.Series(preds.values, index=preds.index)
    prior_mean = p_series.shift(1).rolling(72).mean()
    prior_std = p_series.shift(1).rolling(72).std() + 1e-8
    z_vals = ((p_series - prior_mean) / prior_std).values

    if use_dyn and (funding is not None) and (basis is not None):
        basis_mean = basis.shift(1).rolling(72).mean()
        basis_std = basis.shift(1).rolling(72).std() + 1e-8
        basis_z = np.clip(((basis - basis_mean) / basis_std).fillna(0.0).values, -2.0, 2.0)
        z_threshold = 1.0 - 0.25 * np.tanh(50.0 * funding.values) - 0.15 * basis_z
    else:
        z_threshold = np.ones(len(preds)) * 1.0

    raw_sig = (z_vals > z_threshold) & (stb > 0.0) & (fng < 85)

    n = len(preds)
    pos = np.zeros(n)
    in_pos = False
    entry_bar = 0
    cooldown = 0
    trades = []

    for i in range(n - 2):
        if cooldown > 0:
            cooldown -= 1
            pos[i] = 0.0
            continue

        if not in_pos:
            if raw_sig[i]:
                in_pos = True
                entry_bar = i
                pos[i] = 1.0
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
                    'duration_hours': duration_hours,
                    'gross_ret': gross_ret,
                    'net_ret': net_ret,
                    'is_stop_loss': is_stop
                })

                if is_stop:
                    cooldown = cd_bars
            else:
                pos[i] = 1.0

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
