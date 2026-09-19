# -*- coding: utf-8 -*-
"""
Cross-Sectional Top-N Rotation Strategy Backtest
================================================
Investigates the user's research hypothesis:
- Can we treat crypto like stock cross-sectional selection (Top 30 liquid tokens)?
- Is "Never Idle" (100% always invested in highest-confidence asset) superior to holding cash/funding arb during bear markets?
- Backtested across:
  1. Training: 2021 to 2024
  2. Validation: 2025
  3. Out-of-Sample Test: 2026
"""

import sys
import numpy as np
import pandas as pd

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def run_experiment():
    tokens = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT']
    dfs = {t: pd.read_parquet(f'data/{t}_4h_2020_2026.parquet') for t in tokens}
    
    common_idx = dfs['BTCUSDT'].index
    for t in tokens:
        common_idx = common_idx.intersection(dfs[t].index)

    closes = pd.DataFrame({t: dfs[t].loc[common_idx, 'close'] for t in tokens})
    opens = pd.DataFrame({t: dfs[t].loc[common_idx, 'open'] for t in tokens})

    closes_prior = closes.shift(1)
    ema200 = closes_prior.ewm(span=200).mean()
    trend_ok = closes_prior > ema200

    bb_mid = closes_prior.rolling(120).mean()
    bb_std = closes_prior.rolling(120).std()
    bb_upper = bb_mid + 2.0 * bb_std
    bb_z = (closes_prior - bb_mid) / (bb_std + 1e-8)

    # 120-bar momentum (20 days)
    mom_120 = (closes_prior / closes_prior.shift(120)) - 1.0

    oto_rets = opens.shift(-1) / opens - 1.0
    fee = 0.0008

    def evaluate_split(start_dt, end_dt, rebal_bars=6):
        mask = (common_idx >= start_dt) & (common_idx <= end_dt)
        sub_idx = common_idx[mask]

        rets_always = []
        rets_gated = []
        rets_btc = []
        rets_eth = []

        curr_always = None
        curr_gated = None

        for i, t in enumerate(sub_idx):
            if i % rebal_bars == 0:
                scores = bb_z.loc[t].dropna()
                if len(scores) < len(tokens):
                    top_token = 'BTCUSDT'
                    is_uptrend = False
                else:
                    top_token = scores.idxmax()
                    is_uptrend = trend_ok.loc[t, top_token]

                # Cost
                cost_always = fee * 2 if top_token != curr_always and curr_always is not None else 0.0
                curr_always = top_token

                new_gated = top_token if is_uptrend else 'CASH'
                cost_gated = fee * 2 if new_gated != curr_gated and curr_gated is not None else 0.0
                curr_gated = new_gated
            else:
                cost_always = 0.0
                cost_gated = 0.0

            r_always = oto_rets.loc[t, curr_always] - cost_always if curr_always else 0.0
            r_gated = oto_rets.loc[t, curr_gated] - cost_gated if curr_gated != 'CASH' else 0.0

            rets_always.append(r_always)
            rets_gated.append(r_gated)
            rets_btc.append(oto_rets.loc[t, 'BTCUSDT'])
            rets_eth.append(oto_rets.loc[t, 'ETHUSDT'])

        s_always = pd.Series(rets_always, index=sub_idx).fillna(0.0)
        s_gated = pd.Series(rets_gated, index=sub_idx).fillna(0.0)
        s_btc = pd.Series(rets_btc, index=sub_idx).fillna(0.0)
        s_eth = pd.Series(rets_eth, index=sub_idx).fillna(0.0)

        def get_metrics(s_series):
            cum = (1.0 + s_series).cumprod()
            tot_ret = (cum.iloc[-1] - 1.0) * 100.0
            cum_max = cum.cummax()
            dd = (cum - cum_max) / (cum_max + 1e-8)
            mdd = dd.min() * 100.0

            d_rets = cum.resample('1D').last().pct_change().dropna()
            sharpe = (d_rets.mean() / (d_rets.std() + 1e-8)) * np.sqrt(365)
            return tot_ret, mdd, sharpe

        return {
            'always': get_metrics(s_always),
            'gated': get_metrics(s_gated),
            'btc': get_metrics(s_btc),
            'eth': get_metrics(s_eth),
        }

    splits = {
        "训练期 Training (2021–2024, 4年牛熊全跨度)": ("2021-01-01", "2024-12-31"),
        "验证期 Validation (2025 全年)": ("2025-01-01", "2025-12-31"),
        "终极测试期 Test (2026 年初至 9月阴跌震荡)": ("2026-01-01", "2026-09-01"),
    }

    print("=" * 105)
    print(" 加密货币截面动量轮动实验：【永不空闲 100%持仓轮动】 vs 【顺势过滤+熊市现金防守】")
    print("=" * 105)

    for s_name, (s_dt, e_dt) in splits.items():
        res = evaluate_split(s_dt, e_dt)
        print(f"\n>>> 时间分段: {s_name}")
        print("-" * 105)
        print(f"{'策略模型':<36} | {'累计收益 (Total Ret)':<22} | {'最大回撤 (Max DD)':<18} | {'日频夏普 (Sharpe)'}")
        print("-" * 105)
        print(f"{'1. 永不空闲轮动 (Always in Top-1)':<36} | {res['always'][0]:>+18.2f}% | {res['always'][1]:>16.2f}% | {res['always'][2]:>14.2f}")
        print(f"{'2. 顺势过滤轮动 (熊市退出现金/套利)':<36} | {res['gated'][0]:>+18.2f}% | {res['gated'][1]:>16.2f}% | {res['gated'][2]:>14.2f}")
        print(f"{'3. BTC 买入持有基准 (Buy & Hold)':<36} | {res['btc'][0]:>+18.2f}% | {res['btc'][1]:>16.2f}% | {res['btc'][2]:>14.2f}")
        print(f"{'4. ETH 买入持有基准 (Buy & Hold)':<36} | {res['eth'][0]:>+18.2f}% | {res['eth'][1]:>16.2f}% | {res['eth'][2]:>14.2f}")
        print("-" * 105)


if __name__ == "__main__":
    run_experiment()
