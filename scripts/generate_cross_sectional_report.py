# -*- coding: utf-8 -*-
"""
Cross-Sectional Momentum + Macro Gate + Funding Rate Carry
Full Comparative Evaluation & Report Generator
"""

import os
import sys
import json
from pathlib import Path
import numpy as np
import pandas as pd

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def run():
    tokens = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT']
    dfs = {t: pd.read_parquet(f'data/{t}_4h_2020_2026.parquet') for t in tokens}

    common_idx = dfs['BTCUSDT'].index
    for t in tokens:
        common_idx = common_idx.intersection(dfs[t].index)
    common_idx = common_idx.sort_values()

    closes = pd.DataFrame({t: dfs[t].loc[common_idx, 'close'] for t in tokens})
    opens = pd.DataFrame({t: dfs[t].loc[common_idx, 'open'] for t in tokens})

    df_funding = pd.read_parquet('data/binance_funding_8h.parquet')
    if df_funding.index.tz is not None:
        df_funding.index = df_funding.index.tz_localize(None)

    funding_aligned = df_funding.reindex(common_idx, method='ffill').fillna(0.0001)
    fr_eth = funding_aligned['ETHUSDT']
    fr_btc = funding_aligned['BTCUSDT']
    safe_fr = np.maximum(fr_eth, fr_btc)
    is_settle = common_idx.hour.isin([0, 8, 16])

    closes_prior = closes.shift(1)
    ema200 = closes_prior.ewm(span=200).mean()
    trend_ok = closes_prior > ema200

    btc_bull = closes_prior['BTCUSDT'] > ema200['BTCUSDT']
    trend_ok_dual = trend_ok.copy()
    for t in tokens:
        trend_ok_dual[t] = trend_ok[t] & btc_bull

    bb_mid = closes_prior.rolling(120).mean()
    bb_std = closes_prior.rolling(120).std()
    score = (closes_prior - bb_mid) / (bb_std + 1e-8) + (closes_prior / closes_prior.shift(120) - 1.0)
    oto_rets = opens.shift(-1) / opens - 1.0
    fee = 0.0008

    def evaluate_split(start_dt, end_dt, rebal_bars=6):
        mask = (common_idx >= start_dt) & (common_idx <= end_dt)
        sub_idx = common_idx[mask]

        curr_always = None
        curr_gated = None
        curr_dual = None

        cap_always = 1.0
        cap_cash = 1.0
        cap_arb = 1.0
        cap_dual_arb = 1.0

        equity_always = []
        equity_cash = []
        equity_arb = []
        equity_dual_arb = []

        btc_rets = []
        eth_rets = []

        idle_single_count = 0
        idle_dual_count = 0

        for i, t in enumerate(sub_idx):
            settle = is_settle[common_idx == t][0]
            curr_fr_eth = fr_eth.loc[t]
            curr_fr_btc = fr_btc.loc[t]
            chosen_arb_fr = max(curr_fr_eth, curr_fr_btc)

            if i % rebal_bars == 0:
                s_row = score.loc[t].dropna()
                if len(s_row) < len(tokens):
                    top_token = 'BTCUSDT'
                    is_uptrend_single = False
                    is_uptrend_dual = False
                else:
                    top_token = s_row.idxmax()
                    is_uptrend_single = trend_ok.loc[t, top_token]
                    is_uptrend_dual = trend_ok_dual.loc[t, top_token]

                # 1. Always Top-1
                cost_always = fee * 2 if (top_token != curr_always and curr_always is not None) else 0.0
                curr_always = top_token

                # 2. Single Gated
                new_gated = top_token if is_uptrend_single else 'IDLE_ARB'
                cost_gated = fee * 2 if (new_gated != curr_gated and curr_gated is not None) else 0.0
                curr_gated = new_gated

                # 3. Dual Gated
                new_dual = top_token if is_uptrend_dual else 'IDLE_ARB'
                cost_dual = fee * 2 if (new_dual != curr_dual and curr_dual is not None) else 0.0
                curr_dual = new_dual
            else:
                cost_always = 0.0
                cost_gated = 0.0
                cost_dual = 0.0

            always_ret = oto_rets.loc[t, curr_always] if curr_always else 0.0
            long_fr_cost = chosen_arb_fr if (settle and curr_always) else 0.0
            r_always = (always_ret - cost_always - long_fr_cost)

            fr_gain = max(0.0, chosen_arb_fr) if settle else 0.0

            # Single gated
            if curr_gated == 'IDLE_ARB':
                idle_single_count += 1
                r_cash = 0.0 - cost_gated
                r_arb = fr_gain - cost_gated
            else:
                asset_ret = oto_rets.loc[t, curr_gated]
                r_cash = asset_ret - cost_gated
                r_arb = asset_ret - cost_gated

            # Dual gated
            if curr_dual == 'IDLE_ARB':
                idle_dual_count += 1
                r_dual_arb = fr_gain - cost_dual
            else:
                dual_asset_ret = oto_rets.loc[t, curr_dual]
                r_dual_arb = dual_asset_ret - cost_dual

            cap_always *= (1.0 + r_always)
            cap_cash *= (1.0 + r_cash)
            cap_arb *= (1.0 + r_arb)
            cap_dual_arb *= (1.0 + r_dual_arb)

            equity_always.append(cap_always)
            equity_cash.append(cap_cash)
            equity_arb.append(cap_arb)
            equity_dual_arb.append(cap_dual_arb)

            btc_rets.append(oto_rets.loc[t, 'BTCUSDT'])
            eth_rets.append(oto_rets.loc[t, 'ETHUSDT'])

        eq_always = pd.Series(equity_always, index=sub_idx)
        eq_cash = pd.Series(equity_cash, index=sub_idx)
        eq_arb = pd.Series(equity_arb, index=sub_idx)
        eq_dual_arb = pd.Series(equity_dual_arb, index=sub_idx)
        eq_btc = (1.0 + pd.Series(btc_rets, index=sub_idx)).cumprod()
        eq_eth = (1.0 + pd.Series(eth_rets, index=sub_idx)).cumprod()

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
            'always': get_metrics(eq_always),
            'cash': get_metrics(eq_cash),
            'arb': get_metrics(eq_arb),
            'dual_arb': get_metrics(eq_dual_arb),
            'btc': get_metrics(eq_btc),
            'eth': get_metrics(eq_eth),
            'idle_single': idle_single_count / len(sub_idx) * 100.0,
            'idle_dual': idle_dual_count / len(sub_idx) * 100.0,
        }

    splits = {
        "训练期 Training (2020-10-01 至 2024-12-31)": ("2020-10-01", "2024-12-31"),
        "验证期 Validation (2025-01-01 至 2025-12-31)": ("2025-01-01", "2025-12-31"),
        "测试期 Test (2026-01-01 至 2026-09-13)": ("2026-01-01", "2026-09-13"),
        "2021年 (狂暴牛市)": ("2021-01-01", "2021-12-31"),
        "2022年 (极深熊市 LUNA+FTX)": ("2022-01-01", "2022-12-31"),
        "2023年 (复苏震荡)": ("2023-01-01", "2023-12-31"),
        "2024年 (ETF主升牛市)": ("2024-01-01", "2024-12-31"),
        "全周期 Full Cycle (2020-10-01 至 2026-09-13)": ("2020-10-01", "2026-09-13"),
    }

    all_results = {}
    for s_name, (s_dt, e_dt) in splits.items():
        all_results[s_name] = evaluate_split(s_dt, e_dt)

    # Save to JSON
    os.makedirs('reports', exist_ok=True)
    with open('reports/cross_sectional_evaluation.json', 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print("Report generated successfully: reports/cross_sectional_evaluation.json")
    for s_name, res in all_results.items():
        print(f"\n>>> {s_name} [单币门控空仓: {res['idle_single']:.1f}% | 双重宏观空仓: {res['idle_dual']:.1f}%]")
        for m in ['always', 'cash', 'arb', 'dual_arb', 'btc', 'eth']:
            print(f"  {m:<10} | Ret: {res[m]['tot_ret']:>+9.2f}% | CAGR: {res[m]['cagr']:>7.2f}% | MDD: {res[m]['mdd']:>7.2f}% | Sharpe: {res[m]['sharpe']:>5.2f} | Calmar: {res[m]['calmar']:>5.2f}")

if __name__ == '__main__':
    run()
