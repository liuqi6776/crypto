# -*- coding: utf-8 -*-
"""
Testing Hysteresis & Switching Friction Buffers for Expanded Universes:
Can we keep the massive upside of NEAR & SUI while eliminating choppy churn in 2022 & 2025?
"""

import os
import sys
import pandas as pd
import numpy as np

def run_buffer_test():
    all_syms = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'NEARUSDT', 'SUIUSDT', 'AVAXUSDT']
    raw_dfs = {s: pd.read_parquet(f'data/{s}_4h_2020_2026.parquet') for s in all_syms}
    df_funding = pd.read_parquet('data/binance_funding_8h.parquet')
    if df_funding.index.tz is not None:
        df_funding.index = df_funding.index.tz_localize(None)

    def test_universe_with_delta(tokens, start_dt, end_dt, delta_score=0.0, leverage=3.0):
        common_idx = raw_dfs['BTCUSDT'].index
        for t in tokens:
            common_idx = common_idx.intersection(raw_dfs[t].index)
        common_idx = common_idx[(common_idx >= start_dt) & (common_idx <= end_dt)].sort_values()

        closes = pd.DataFrame({t: raw_dfs[t].loc[common_idx, 'close'] for t in tokens})
        opens = pd.DataFrame({t: raw_dfs[t].loc[common_idx, 'open'] for t in tokens})
        highs = pd.DataFrame({t: raw_dfs[t].loc[common_idx, 'high'] for t in tokens})
        lows = pd.DataFrame({t: raw_dfs[t].loc[common_idx, 'low'] for t in tokens})

        atrs = {}
        for t in tokens:
            tr = pd.concat([highs[t]-lows[t], (highs[t]-closes[t].shift(1)).abs(), (lows[t]-closes[t].shift(1)).abs()], axis=1).max(axis=1)
            atrs[t] = tr.rolling(14).mean()
        df_atrs = pd.DataFrame(atrs)

        closes_prior = closes.shift(1)
        ema200 = closes_prior.ewm(span=200).mean()
        bb_mid = closes_prior.rolling(120).mean()
        bb_std = closes_prior.rolling(120).std()
        bb_z = (closes_prior - bb_mid) / (bb_std + 1e-8)
        mom20 = (closes_prior / closes_prior.shift(120)) - 1.0
        score = bb_z + mom20

        btc_ema = raw_dfs['BTCUSDT'].loc[common_idx, 'close'].shift(1).ewm(span=200).mean()
        btc_bull = raw_dfs['BTCUSDT'].loc[common_idx, 'close'].shift(1) > btc_ema
        funding_aligned = df_funding.reindex(common_idx, method='ffill').fillna(0.0001)
        is_settlement_bar = pd.Series(common_idx.hour.isin([0, 8, 16]), index=common_idx)

        cap = 10000.0
        curr_pos = 'USDT_CASH'
        entry_p = 0.0
        stop_p = 0.0
        highest_p = 0.0
        fee_rate = 0.0008
        slippage = 0.0015
        liq_drop = 1.0/leverage - 0.005
        trades = []
        equity_curve = []
        liquidated = False

        for t in common_idx:
            if liquidated:
                equity_curve.append(0.0)
                continue

            settle = is_settlement_bar.loc[t]

            if curr_pos != 'USDT_CASH':
                bl = lows.loc[t, curr_pos]
                bh = highs.loc[t, curr_pos]
                bo = opens.loc[t, curr_pos]
                bc = closes.loc[t, curr_pos]
                highest_p = max(highest_p, bh)

                liq_p = entry_p * (1.0 - liq_drop)
                if bl <= liq_p:
                    liquidated = True
                    cap = 0.0
                    equity_curve.append(0.0)
                    continue

                if stop_p > 0 and bl <= stop_p:
                    exec_exit = min(bo, stop_p * (1.0 - slippage))
                    lev_ret = ((exec_exit - entry_p) / entry_p) * leverage
                    close_fee = cap * leverage * fee_rate
                    cap = max(0.0, cap + (cap * lev_ret) - close_fee)
                    trades.append(lev_ret)
                    curr_pos = 'USDT_CASH'
                    entry_p = 0.0
                    stop_p = 0.0
                    highest_p = 0.0
                    equity_curve.append(cap)
                    continue

                if highest_p >= entry_p * 1.05:
                    stop_p = max(stop_p, entry_p * 1.002)
                if highest_p >= entry_p * 1.10:
                    stop_p = max(stop_p, highest_p * 0.95)

                bar_ret = (bc - bo) / bo
                funding_cost = 0.0
                if settle:
                    fr = funding_aligned.loc[t, curr_pos] if curr_pos in funding_aligned else 0.0001
                    funding_cost = cap * ((leverage * fr) + ((leverage - 1.0) * 0.0001))
                cap = max(0.0, cap + (cap * leverage * bar_ret) - funding_cost)
                if cap <= 0:
                    liquidated = True
                    equity_curve.append(0.0)
                    continue

            s_row = score.loc[t].dropna()
            top_cand = s_row.idxmax() if len(s_row) >= len(tokens) else 'BTCUSDT'

            # Switching buffer logic:
            # If currently holding an asset, only switch to challenger if challenger_score >= current_score + delta_score
            target_pos = curr_pos
            if curr_pos == 'USDT_CASH':
                cand_close = closes_prior.loc[t, top_cand]
                cand_ema = ema200.loc[t, top_cand]
                if btc_bull.loc[t] and ((cand_close - cand_ema) / cand_ema >= 0.005):
                    target_pos = top_cand
            else:
                # check if curr_pos is still valid under EMA200
                curr_close = closes_prior.loc[t, curr_pos]
                curr_ema = ema200.loc[t, curr_pos]
                curr_dist = (curr_close - curr_ema) / curr_ema
                curr_still_bull = btc_bull.loc[t] and (curr_dist >= -0.005)

                if not curr_still_bull:
                    # must exit
                    cand_close = closes_prior.loc[t, top_cand]
                    cand_ema = ema200.loc[t, top_cand]
                    if btc_bull.loc[t] and ((cand_close - cand_ema) / cand_ema >= 0.005):
                        target_pos = top_cand
                    else:
                        target_pos = 'USDT_CASH'
                else:
                    # check if top_cand beats curr_pos by delta_score
                    if top_cand != curr_pos:
                        challenger_score = s_row[top_cand]
                        current_score = s_row[curr_pos]
                        if challenger_score >= current_score + delta_score:
                            cand_close = closes_prior.loc[t, top_cand]
                            cand_ema = ema200.loc[t, top_cand]
                            if (cand_close - cand_ema) / cand_ema >= 0.005:
                                target_pos = top_cand

            if target_pos != curr_pos:
                if curr_pos != 'USDT_CASH':
                    exit_p = opens.loc[t, curr_pos]
                    lev_ret = ((exit_p - entry_p) / entry_p) * leverage
                    close_fee = cap * leverage * fee_rate
                    cap = max(0.0, cap + (cap * lev_ret) - close_fee)
                    trades.append(lev_ret)
                    curr_pos = 'USDT_CASH'

                if target_pos != 'USDT_CASH' and cap > 0:
                    curr_pos = target_pos
                    entry_p = opens.loc[t, target_pos]
                    highest_p = entry_p
                    atr_v = df_atrs.loc[t, target_pos]
                    stop_p = max(ema200.loc[t, target_pos]*0.995, entry_p - atr_v*1.5)
                    open_fee = cap * leverage * fee_rate
                    cap -= open_fee

            equity_curve.append(cap)

        eq_s = pd.Series(equity_curve, index=common_idx)
        final_equity = eq_s.iloc[-1]
        total_ret = ((final_equity - 10000.0) / 10000.0) * 100.0
        running_max = eq_s.cummax()
        max_dd = ((eq_s - running_max) / running_max).min() * 100.0
        n_bars = len(eq_s)
        years = n_bars / (365.25 * 6)
        cagr = ((final_equity / 10000.0) ** (1.0 / years) - 1.0) * 100.0 if final_equity > 0 else -100.0
        daily_eq = eq_s.resample('1D').last().dropna()
        sharpe = (daily_eq.pct_change().mean() / (daily_eq.pct_change().std() + 1e-8)) * np.sqrt(365) if len(daily_eq) > 10 else 0.0

        return {
            'total_ret': round(total_ret, 2),
            'cagr': round(cagr, 2),
            'max_dd': round(max_dd, 2),
            'sharpe': round(sharpe, 2),
            'trades': len(trades),
            'liquidated': liquidated
        }

    print("=== Testing Switching Delta Buffers on Expanded Universe (Core-4 + NEAR) ===")
    tokens_near = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'NEARUSDT']
    for delta in [0.0, 0.1, 0.2, 0.3]:
        r26 = test_universe_with_delta(tokens_near, '2026-01-01', '2026-09-22', delta_score=delta)
        r25 = test_universe_with_delta(tokens_near, '2025-01-01', '2025-12-31', delta_score=delta)
        r22 = test_universe_with_delta(tokens_near, '2022-01-01', '2022-12-31', delta_score=delta)
        print(f"Delta: {delta:.2f} | 2026: {r26['total_ret']:+8.1f}% (Tr:{r26['trades']:2d}, DD:{r26['max_dd']:5.1f}%) | 2025: {r25['total_ret']:+7.1f}% (Tr:{r25['trades']:2d}, DD:{r25['max_dd']:5.1f}%) | 2022: {r22['total_ret']:+6.1f}% (Tr:{r22['trades']:2d}, DD:{r22['max_dd']:5.1f}%)")

if __name__ == '__main__':
    run_buffer_test()
