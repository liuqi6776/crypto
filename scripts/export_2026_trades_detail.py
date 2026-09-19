# -*- coding: utf-8 -*-
"""
Export 2026 Trade-by-Trade Details and Allocation Weights
"""

import sys
import numpy as np
import pandas as pd

def get_2026_trades():
    tokens = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT']
    dfs = {t: pd.read_parquet(f'data/{t}_4h_2020_2026.parquet') for t in tokens}
    common_idx = dfs['BTCUSDT'].index
    for t in tokens: common_idx = common_idx.intersection(dfs[t].index)
    common_idx = common_idx.sort_values()

    closes = pd.DataFrame({t: dfs[t].loc[common_idx, 'close'] for t in tokens})
    opens = pd.DataFrame({t: dfs[t].loc[common_idx, 'open'] for t in tokens})
    closes_prior = closes.shift(1)
    ema200 = closes_prior.ewm(span=200).mean()

    btc_bull = closes_prior['BTCUSDT'] > ema200['BTCUSDT']
    trend_ok_dual = closes_prior > ema200
    for t in tokens: trend_ok_dual[t] = trend_ok_dual[t] & btc_bull

    bb_mid = closes_prior.rolling(120).mean()
    bb_std = closes_prior.rolling(120).std()
    score = (closes_prior - bb_mid) / (bb_std + 1e-8) + (closes_prior / closes_prior.shift(120) - 1.0)
    oto_rets = opens.shift(-1) / opens - 1.0

    df_funding = pd.read_parquet('data/binance_funding_8h.parquet')
    if df_funding.index.tz is not None: df_funding.index = df_funding.index.tz_localize(None)
    funding_aligned = df_funding.reindex(common_idx, method='ffill').fillna(0.0001)
    safe_fr = np.maximum(funding_aligned['ETHUSDT'], funding_aligned['BTCUSDT'])
    is_settle = common_idx.hour.isin([0, 8, 16])

    sub_idx = common_idx[(common_idx >= '2026-01-01') & (common_idx <= '2026-09-13')]

    trades = []
    curr_state = None
    state_start_idx = 0
    state_entry_price = 0.0
    fee = 0.0008

    # We track equity step by step
    cap = 10000.0 # initial capital $10,000
    segment_cap_start = cap

    bar_rets = []
    seg_fees = 0.0

    # Daily rebalance: every 6 4h bars
    decisions = {}
    for i, t in enumerate(sub_idx):
        if i % 6 == 0:
            s_row = score.loc[t].dropna()
            top = s_row.idxmax()
            ok = trend_ok_dual.loc[t, top]
            decisions[t] = (top if ok else 'IDLE_ARB', top, s_row[top], btc_bull.loc[t], (closes_prior.loc[t, top] > ema200.loc[t, top]))

    # Now step through bars
    for i, t in enumerate(sub_idx):
        settle = is_settle[common_idx == t][0]
        fr_gain = max(0.0, safe_fr.loc[t]) if settle else 0.0

        if i % 6 == 0:
            target_state, top_cand, top_sc, btc_ok, coin_ok = decisions[t]
            if target_state != curr_state:
                # Close previous segment
                if curr_state is not None:
                    exit_time = t
                    exit_price = opens.loc[t, curr_state] if curr_state != 'IDLE_ARB' else 1.0
                    seg_cum = np.prod([1.0 + r for r in bar_rets]) - 1.0
                    trades.append({
                        'trade_id': len(trades) + 1,
                        'state': curr_state,
                        'weight': '100% 做多 (Long)' if curr_state != 'IDLE_ARB' else '100% 对冲套利 (Delta-Neutral)',
                        'entry_time': str(sub_idx[state_start_idx])[:16],
                        'exit_time': str(exit_time)[:16],
                        'days': round((exit_time - sub_idx[state_start_idx]).total_seconds() / 86400.0, 1),
                        'entry_price': round(state_entry_price, 2) if curr_state != 'IDLE_ARB' else 1.0,
                        'exit_price': round(exit_price, 2) if curr_state != 'IDLE_ARB' else 1.0,
                        'return_pct': round(seg_cum * 100.0, 2),
                        'capital_end': round(cap, 2),
                    })

                # Start new segment
                turnover_cost = fee * 2 if curr_state is not None else fee
                cap *= (1.0 - turnover_cost)
                curr_state = target_state
                state_start_idx = i
                state_entry_price = opens.loc[t, curr_state] if curr_state != 'IDLE_ARB' else 1.0
                bar_rets = [-turnover_cost]
            else:
                pass

        # Bar return
        if curr_state == 'IDLE_ARB':
            r = fr_gain
        else:
            r = oto_rets.loc[t, curr_state]

        cap *= (1.0 + r)
        bar_rets.append(r)

    # Final segment
    if curr_state is not None:
        exit_time = sub_idx[-1]
        exit_price = opens.loc[exit_time, curr_state] if curr_state != 'IDLE_ARB' else 1.0
        seg_cum = np.prod([1.0 + r for r in bar_rets]) - 1.0
        trades.append({
            'trade_id': len(trades) + 1,
            'state': curr_state,
            'weight': '100% 做多 (Long)' if curr_state != 'IDLE_ARB' else '100% 对冲套利 (Delta-Neutral)',
            'entry_time': str(sub_idx[state_start_idx])[:16],
            'exit_time': str(exit_time)[:16],
            'days': round((exit_time - sub_idx[state_start_idx]).total_seconds() / 86400.0, 1),
            'entry_price': round(state_entry_price, 2) if curr_state != 'IDLE_ARB' else 1.0,
            'exit_price': round(exit_price, 2) if curr_state != 'IDLE_ARB' else 1.0,
            'return_pct': round(seg_cum * 100.0, 2),
            'capital_end': round(cap, 2),
        })

    df_t = pd.DataFrame(trades)
    return df_t

if __name__ == '__main__':
    df = get_2026_trades()
    print(df.to_string(index=False))
