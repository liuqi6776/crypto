# -*- coding: utf-8 -*-
"""
Cross-Sectional Selection + Trend Hard Gate + Bear Funding Arbitrage
Evaluation across:
1. Training Period: 2020-08-11 to 2024-12-31 (Full Bull & Bear Cycle)
2. Validation Period: 2025-01-01 to 2025-12-31 (Divergent/Choppy Market)
3. Blind Stress Test: 2026-01-01 to 2026-09-13 (Recent OOS)
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def run_simulation():
    tokens = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT']
    dfs = {t: pd.read_parquet(f'data/{t}_4h_2020_2026.parquet') for t in tokens}

    # Find common timestamps
    common_idx = dfs['BTCUSDT'].index
    for t in tokens:
        common_idx = common_idx.intersection(dfs[t].index)

    common_idx = common_idx.sort_values()

    closes = pd.DataFrame({t: dfs[t].loc[common_idx, 'close'] for t in tokens})
    opens = pd.DataFrame({t: dfs[t].loc[common_idx, 'open'] for t in tokens})
    highs = pd.DataFrame({t: dfs[t].loc[common_idx, 'high'] for t in tokens})
    lows = pd.DataFrame({t: dfs[t].loc[common_idx, 'low'] for t in tokens})

    # Load funding rates
    df_funding = pd.read_parquet('data/binance_funding_8h.parquet')
    if df_funding.index.tz is not None:
        df_funding.index = df_funding.index.tz_localize(None)

    # Reindex funding rates to 4h bars (forward fill prior 8h rate)
    # Funding settlement occurs at 00:00, 08:00, 16:00 UTC
    funding_aligned = df_funding.reindex(common_idx, method='ffill').fillna(0.0001)

    # Core funding carry rate when idle: use highest safe positive rate between BTC and ETH (or ETH)
    # Delta-Neutral: 50% spot + 50% 1x short -> earns 0.5 * fr if fr >= 0, else 0 (pause if fr < -0.0001)
    # If using coin-margin inverse contract, earns 1.0 * fr
    # Let's model realistic 50/50 spot-futures delta neutral:
    fr_eth = funding_aligned['ETHUSDT']
    fr_btc = funding_aligned['BTCUSDT']
    safe_fr = np.maximum(fr_eth, fr_btc)
    
    # 8h settlement check: occurs at 00:00, 08:00, 16:00
    is_settlement_bar = common_idx.hour.isin([0, 8, 16])

    # Factor calculations
    # Use strictly causal prior information: closes_prior
    closes_prior = closes.shift(1)
    opens_prior = opens.shift(1)

    # 1. Macro Trend Gate: EMA 200 on 4h bars (~33 days)
    ema200 = closes_prior.ewm(span=200).mean()
    trend_ok = closes_prior > ema200

    # 2. Bollinger Band Upper breakout / Z-score over 120 bars (20 days)
    bb_mid = closes_prior.rolling(120).mean()
    bb_std = closes_prior.rolling(120).std()
    bb_upper = bb_mid + 2.0 * bb_std
    bb_z = (closes_prior - bb_mid) / (bb_std + 1e-8)

    # 3. 20-day Momentum (120 4h bars)
    mom_120 = (closes_prior / closes_prior.shift(120)) - 1.0

    # Composite Score: normalized z-score + momentum rank
    score = bb_z + mom_120

    # Forward open-to-open returns
    oto_rets = opens.shift(-1) / opens - 1.0
    fee = 0.0008  # 0.08% taker fee + slippage

    # Dual Macro Gate: BTC > EMA200 AND TopToken > EMA200
    btc_bull = closes_prior['BTCUSDT'] > ema200['BTCUSDT']
    trend_ok_dual = trend_ok.copy()
    for t in tokens:
        trend_ok_dual[t] = trend_ok[t] & btc_bull

    def evaluate_split(start_dt, end_dt, rebal_bars=6):
        """
        rebal_bars=6 corresponds to 24 hours (6 * 4h bars).
        Checks ranking once daily at 00:00 UTC to minimize churn.
        """
        mask = (common_idx >= start_dt) & (common_idx <= end_dt)
        sub_idx = common_idx[mask]

        curr_always = None
        curr_gated = None
        curr_dual = None

        cap_always = 1.0
        cap_cash = 1.0
        cap_arb100 = 1.0
        cap_dual_arb = 1.0

        equity_always = []
        equity_cash = []
        equity_arb100 = []
        equity_dual_arb = []

        btc_rets = []
        eth_rets = []

        idle_single_count = 0
        idle_dual_count = 0

        for i, t in enumerate(sub_idx):
            settle = is_settlement_bar[common_idx == t][0]
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

                # 1. Always in Top-1
                cost_always = fee * 2 if (top_token != curr_always and curr_always is not None) else 0.0
                curr_always = top_token

                # 2. Single Gated
                new_gated = top_token if is_uptrend_single else 'IDLE_ARB'
                cost_gated = fee * 2 if (new_gated != curr_gated and curr_gated is not None) else 0.0
                curr_gated = new_gated

                # 3. Dual Macro Gated
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
                r_arb100 = fr_gain - cost_gated
            else:
                asset_ret = oto_rets.loc[t, curr_gated]
                r_cash = asset_ret - cost_gated
                r_arb100 = asset_ret - cost_gated

            # Dual gated
            if curr_dual == 'IDLE_ARB':
                idle_dual_count += 1
                r_dual_arb = fr_gain - cost_dual
            else:
                dual_asset_ret = oto_rets.loc[t, curr_dual]
                r_dual_arb = dual_asset_ret - cost_dual

            cap_always *= (1.0 + r_always)
            cap_cash *= (1.0 + r_cash)
            cap_arb100 *= (1.0 + r_arb100)
            cap_dual_arb *= (1.0 + r_dual_arb)

            equity_always.append(cap_always)
            equity_cash.append(cap_cash)
            equity_arb100.append(cap_arb100)
            equity_dual_arb.append(cap_dual_arb)

            btc_rets.append(oto_rets.loc[t, 'BTCUSDT'])
            eth_rets.append(oto_rets.loc[t, 'ETHUSDT'])

        eq_always = pd.Series(equity_always, index=sub_idx)
        eq_cash = pd.Series(equity_cash, index=sub_idx)
        eq_arb100 = pd.Series(equity_arb100, index=sub_idx)
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
            'arb100': get_metrics(eq_arb100),
            'dual_arb': get_metrics(eq_dual_arb),
            'btc': get_metrics(eq_btc),
            'eth': get_metrics(eq_eth),
            'idle_single': idle_single_count / len(sub_idx) * 100.0,
            'idle_dual': idle_dual_count / len(sub_idx) * 100.0,
        }

    splits = {
        "训练期 Training (2020-10-01 至 2024-12-31, 4.25年牛熊大周期)": ("2020-10-01", "2024-12-31"),
        "验证期 Validation (2025-01-01 至 2025-12-31, 全年震荡/分化市)": ("2025-01-01", "2025-12-31"),
        "测试期 Test (2026-01-01 至 2026-09-13, 盲测阴跌压力测试)": ("2026-01-01", "2026-09-13"),
        "--- 单年细分 2021 (狂暴牛市) ---": ("2021-01-01", "2021-12-31"),
        "--- 单年细分 2022 (惨烈大熊市 LUNA+FTX) ---": ("2022-01-01", "2022-12-31"),
        "--- 单年细分 2023 (深熊复苏) ---": ("2023-01-01", "2023-12-31"),
        "--- 单年细分 2024 (ETF牛市突破) ---": ("2024-01-01", "2024-12-31"),
    }

    print("=" * 115)
    print(" 【截面选优 + 绝对趋势硬门控 + 熊市资金费套利】 跨周期量化回测评估")
    print(" 核心资产池: BTC, ETH, SOL, BNB | 调仓摩擦: 0.08% 双边扣费 | 资金费: 币安历史8h真实结算")
    print("=" * 115)

    for s_name, (s_dt, e_dt) in splits.items():
        res = evaluate_split(s_dt, e_dt)
        print(f"\n>>> 时间阶段: {s_name}")
        print(f"    [防守统计] 单币门控套利期占比: {res['idle_single']:.1f}% | 双重宏观门控套利期占比: {res['idle_dual']:.1f}%")
        print("-" * 115)
        print(f"{'策略配置模型':<40} | {'总收益 (Total)':<16} | {'年化 (CAGR)':<14} | {'最大回撤 (MDD)':<16} | {'夏普 (Sharpe)':<14} | {'卡玛 (Calmar)'}")
        print("-" * 115)
        print(f"{'1. 永不空闲轮动 (Always Top-1)':<40} | {res['always']['tot_ret']:>+12.2f}% | {res['always']['cagr']:>10.2f}% | {res['always']['mdd']:>14.2f}% | {res['always']['sharpe']:>12.2f} | {res['always']['calmar']:>10.2f}")
        print(f"{'2. 单币门控 + 纯现金 (Token > EMA200)':<40} | {res['cash']['tot_ret']:>+12.2f}% | {res['cash']['cagr']:>10.2f}% | {res['cash']['mdd']:>14.2f}% | {res['cash']['sharpe']:>12.2f} | {res['cash']['calmar']:>10.2f}")
        print(f"{'3. 单币门控 + 100%资金费套利':<40} | {res['arb100']['tot_ret']:>+12.2f}% | {res['arb100']['cagr']:>10.2f}% | {res['arb100']['mdd']:>14.2f}% | {res['arb100']['sharpe']:>12.2f} | {res['arb100']['calmar']:>10.2f}")
        print(f"{'4. 【推荐】双重宏观门控 + 100%资金费套利':<40} | {res['dual_arb']['tot_ret']:>+12.2f}% | {res['dual_arb']['cagr']:>10.2f}% | {res['dual_arb']['mdd']:>14.2f}% | {res['dual_arb']['sharpe']:>12.2f} | {res['dual_arb']['calmar']:>10.2f}")
        print("-" * 115)
        print(f"{'基准 A: BTC 买入持有 (Buy & Hold)':<40} | {res['btc']['tot_ret']:>+12.2f}% | {res['btc']['cagr']:>10.2f}% | {res['btc']['mdd']:>14.2f}% | {res['btc']['sharpe']:>12.2f} | {res['btc']['calmar']:>10.2f}")
        print(f"{'基准 B: ETH 买入持有 (Buy & Hold)':<40} | {res['eth']['tot_ret']:>+12.2f}% | {res['eth']['cagr']:>10.2f}% | {res['eth']['mdd']:>14.2f}% | {res['eth']['sharpe']:>12.2f} | {res['eth']['calmar']:>10.2f}")
        print("-" * 115)


if __name__ == '__main__':
    run_simulation()
