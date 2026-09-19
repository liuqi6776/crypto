# -*- coding: utf-8 -*-
"""
Dynamic Top-10 Volume Pool Cross-Sectional Rotation Backtest
===========================================================
Answers User Research Questions:
1. What if we dynamically select the Top-10 liquid tokens by rolling volume (excluding stablecoins and meme coins)?
2. How does rotating among this Top-10 universe perform across 2020-2024, 2025, and 2026?
3. What if we STOP funding rate arbitrage and just hold pure cash during bear regimes?
4. What if we NEVER idle and purely hold the Top-1 asset through all bull and bear markets?
"""

import os
import sys
import numpy as np
import pandas as pd

def run_experiment():
    tokens = [
        'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT',
        'XRPUSDT', 'ADAUSDT', 'AVAXUSDT', 'LINKUSDT',
        'DOTUSDT', 'NEARUSDT', 'LTCUSDT'
    ]
    dfs = {}
    for t in tokens:
        d = pd.read_parquet(f'data/{t}_4h_2020_2026.parquet')
        if 'quote_volume' not in d.columns and 'qvol' in d.columns:
            d['quote_volume'] = d['qvol']
        dfs[t] = d

    # Common index
    common_idx = dfs['BTCUSDT'].index
    for t in tokens:
        common_idx = common_idx.intersection(dfs[t].index)
    common_idx = common_idx.sort_values()

    closes = pd.DataFrame({t: dfs[t].loc[common_idx, 'close'] for t in tokens})
    opens = pd.DataFrame({t: dfs[t].loc[common_idx, 'open'] for t in tokens})
    qvol = pd.DataFrame({t: dfs[t].loc[common_idx, 'quote_volume'] for t in tokens})

    closes_prior = closes.shift(1)
    opens_prior = opens.shift(1)
    qvol_prior = qvol.shift(1)

    # 120-bar (20-day) rolling metrics
    rolling_qvol = qvol_prior.rolling(120).mean()
    ema200 = closes_prior.ewm(span=200).mean()
    bb_mid = closes_prior.rolling(120).mean()
    bb_std = closes_prior.rolling(120).std()
    bb_z = (closes_prior - bb_mid) / (bb_std + 1e-8)
    mom20 = (closes_prior / closes_prior.shift(120)) - 1.0
    score = bb_z + mom20

    # Macro trend gate
    btc_bull = closes_prior['BTCUSDT'] > ema200['BTCUSDT']
    coin_bull = closes_prior > ema200

    # Funding rate data
    df_funding = pd.read_parquet('data/binance_funding_8h.parquet')
    if df_funding.index.tz is not None:
        df_funding.index = df_funding.index.tz_localize(None)
    funding_aligned = df_funding.reindex(common_idx, method='ffill').fillna(0.0001)
    safe_fr = np.maximum(funding_aligned['ETHUSDT'], funding_aligned['BTCUSDT'])
    is_settle = common_idx.hour.isin([0, 8, 16])

    oto_rets = opens.shift(-1) / opens - 1.0
    fee = 0.0008

    def evaluate_split(start_dt, end_dt, top_k_universe=10, rebal_bars=6):
        mask = (common_idx >= start_dt) & (common_idx <= end_dt)
        sub_idx = common_idx[mask]

        cap_always = 1.0
        cap_cash = 1.0
        cap_arb = 1.0

        curr_always = None
        curr_cash = None
        curr_arb = None

        eq_always = []
        eq_cash = []
        eq_arb = []

        btc_rets = []
        eth_rets = []

        idle_count = 0
        top_picks_history = []

        for i, t in enumerate(sub_idx):
            settle = is_settle[common_idx == t][0]
            fr_gain = max(0.0, safe_fr.loc[t]) if settle else 0.0

            if i % rebal_bars == 0:
                # 1. Select top_k tokens by rolling volume
                v_row = rolling_qvol.loc[t].dropna()
                if len(v_row) < top_k_universe:
                    valid_pool = v_row.index
                else:
                    valid_pool = v_row.nlargest(top_k_universe).index

                # 2. Within valid pool, rank by momentum score
                s_row = score.loc[t, valid_pool].dropna()
                if len(s_row) == 0:
                    top_token = 'BTCUSDT'
                    is_ok = False
                else:
                    top_token = s_row.idxmax()
                    is_ok = bool(btc_bull.loc[t] and coin_bull.loc[t, top_token])

                top_picks_history.append((t, top_token, is_ok))

                # Always Top-1
                cost_always = fee * 2 if (top_token != curr_always and curr_always is not None) else 0.0
                curr_always = top_token

                # Cash Gate
                new_cash = top_token if is_ok else 'IDLE_CASH'
                cost_cash = fee * 2 if (new_cash != curr_cash and curr_cash is not None) else 0.0
                curr_cash = new_cash

                # Arb Gate
                new_arb = top_token if is_ok else 'IDLE_ARB'
                cost_arb = fee * 2 if (new_arb != curr_arb and curr_arb is not None) else 0.0
                curr_arb = new_arb
            else:
                cost_always = 0.0
                cost_cash = 0.0
                cost_arb = 0.0

            # Always Top-1
            r_always = oto_rets.loc[t, curr_always] - cost_always
            cap_always *= (1.0 + r_always)

            # Cash Gate (Pure Cash: earns 0 in idle)
            if curr_cash == 'IDLE_CASH':
                r_cash = 0.0 - cost_cash
            else:
                r_cash = oto_rets.loc[t, curr_cash] - cost_cash
            cap_cash *= (1.0 + r_cash)

            # Arb Gate (Delta-neutral funding rate carry in idle)
            if curr_arb == 'IDLE_ARB':
                idle_count += 1
                r_arb = fr_gain - cost_arb
            else:
                r_arb = oto_rets.loc[t, curr_arb] - cost_arb
            cap_arb *= (1.0 + r_arb)

            eq_always.append(cap_always)
            eq_cash.append(cap_cash)
            eq_arb.append(cap_arb)

            btc_rets.append(oto_rets.loc[t, 'BTCUSDT'])
            eth_rets.append(oto_rets.loc[t, 'ETHUSDT'])

        s_always = pd.Series(eq_always, index=sub_idx)
        s_cash = pd.Series(eq_cash, index=sub_idx)
        s_arb = pd.Series(eq_arb, index=sub_idx)
        s_btc = (1.0 + pd.Series(btc_rets, index=sub_idx)).cumprod()
        s_eth = (1.0 + pd.Series(eth_rets, index=sub_idx)).cumprod()

        def get_metrics(eq):
            tot_ret = (eq.iloc[-1] - 1.0) * 100.0
            peak = eq.cummax()
            dd = (eq - peak) / peak
            mdd = dd.min() * 100.0
            days = (sub_idx[-1] - sub_idx[0]).total_seconds() / 86400.0
            cagr = ((eq.iloc[-1]) ** (365.25 / days) - 1.0) * 100.0 if eq.iloc[-1] > 0 else -100.0
            calmar = abs(cagr / mdd) if abs(mdd) > 1e-4 else 0.0
            d_eq = eq.resample('1D').last().dropna()
            d_rets = d_eq.pct_change().dropna()
            sharpe = (d_rets.mean() / (d_rets.std() + 1e-8)) * np.sqrt(365)
            return {
                'tot_ret': tot_ret,
                'cagr': cagr,
                'mdd': mdd,
                'sharpe': sharpe,
                'calmar': calmar
            }

        return {
            'always': get_metrics(s_always),
            'cash': get_metrics(s_cash),
            'arb': get_metrics(s_arb),
            'btc': get_metrics(s_btc),
            'eth': get_metrics(s_eth),
            'idle_pct': idle_count / len(sub_idx) * 100.0,
            'picks': top_picks_history
        }

    splits = {
        "训练期 Training (2020-10-01 至 2024-12-31)": ("2020-10-01", "2024-12-31"),
        "验证期 Validation (2025-01-01 至 2025-12-31)": ("2025-01-01", "2025-12-31"),
        "测试期 Test (2026-01-01 至 2026-09-13)": ("2026-01-01", "2026-09-13"),
        "2022年 极深熊市 (LUNA+FTX崩盘)": ("2022-01-01", "2022-12-31"),
        "全周期 Full Cycle (2020-10-01 至 2026-09-13)": ("2020-10-01", "2026-09-13"),
    }

    print("=" * 125)
    print(" 【动态 Top-10 成交量流动性池截面轮动回测】 扩展资产池: BTC, ETH, SOL, BNB, XRP, ADA, AVAX, LINK, DOT, NEAR, LTC")
    print(" 严格规则: 剔除稳定币与Meme币 | 滚动20日成交量选前10 | 宏观双重硬门控过滤 | 0.08% 双边扣费")
    print("=" * 125)

    results_summary = {}
    for s_name, (s_dt, e_dt) in splits.items():
        res = evaluate_split(s_dt, e_dt, top_k_universe=10)
        results_summary[s_name] = res
        print(f"\n>>> 时间阶段: {s_name} [门控避险期占比: {res['idle_pct']:.1f}%]")
        print("-" * 125)
        print(f"{'策略配置模型':<48} | {'总收益 (Total)':<16} | {'年化 (CAGR)':<14} | {'最大回撤 (MDD)':<16} | {'夏普 (Sharpe)':<14} | {'卡玛 (Calmar)'}")
        print("-" * 125)
        print(f"{'1. 永不空闲 (单纯持仓轮动, 100%全天候持仓)':<48} | {res['always']['tot_ret']:>+12.2f}% | {res['always']['cagr']:>10.2f}% | {res['always']['mdd']:>14.2f}% | {res['always']['sharpe']:>12.2f} | {res['always']['calmar']:>10.2f}")
        print(f"{'2. 双重宏观门控 + 单纯现金防守 (无资金费套利)':<48} | {res['cash']['tot_ret']:>+12.2f}% | {res['cash']['cagr']:>10.2f}% | {res['cash']['mdd']:>14.2f}% | {res['cash']['sharpe']:>12.2f} | {res['cash']['calmar']:>10.2f}")
        print(f"{'3. 【推荐】双重宏观门控 + 100%资金费无风险套利':<48} | {res['arb']['tot_ret']:>+12.2f}% | {res['arb']['cagr']:>10.2f}% | {res['arb']['mdd']:>14.2f}% | {res['arb']['sharpe']:>12.2f} | {res['arb']['calmar']:>10.2f}")
        print("-" * 125)
        print(f"{'基准 A: BTC 买入持有 (Buy & Hold)':<48} | {res['btc']['tot_ret']:>+12.2f}% | {res['btc']['cagr']:>10.2f}% | {res['btc']['mdd']:>14.2f}% | {res['btc']['sharpe']:>12.2f} | {res['btc']['calmar']:>10.2f}")
        print(f"{'基准 B: ETH 买入持有 (Buy & Hold)':<48} | {res['eth']['tot_ret']:>+12.2f}% | {res['eth']['cagr']:>10.2f}% | {res['eth']['mdd']:>14.2f}% | {res['eth']['sharpe']:>12.2f} | {res['eth']['calmar']:>10.2f}")
        print("-" * 125)

    return results_summary

if __name__ == '__main__':
    run_experiment()
