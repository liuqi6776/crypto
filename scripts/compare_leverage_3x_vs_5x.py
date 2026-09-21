# -*- coding: utf-8 -*-
"""
Empirical Comparison: 1.0x Spot vs 3.0x Leverage vs 5.0x Leverage
==================================================================
Under the V1 Top-1 Rotation & Dual Macro Trend Gate Strategy.
Evaluates:
1. Nominal scaling, liquidation price, distance to liquidation vs stop-loss.
2. Intrabar liquidation risk (if low <= liq_price -> bankruptcy).
3. Transaction fee friction on nominal position (8 bps * Leverage).
4. Long funding rate cost paid to shorts.
5. Volatility drag, Max Drawdown, Sharpe, Calmar, and Compounded CAGR across:
   - 2020-2024 (Training)
   - 2025 (Validation)
   - 2026 (Test)
   - 2022 (Bear Stress)
   - Full Cycle (2020-2026)
"""

import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def run_leverage_comparison():
    tokens = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT']
    dfs = {t: pd.read_parquet(f'data/{t}_4h_2020_2026.parquet') for t in tokens}

    # Common index alignment
    common_idx = dfs['BTCUSDT'].index
    for t in tokens:
        common_idx = common_idx.intersection(dfs[t].index)
    common_idx = common_idx.sort_values()

    closes = pd.DataFrame({t: dfs[t].loc[common_idx, 'close'] for t in tokens})
    opens = pd.DataFrame({t: dfs[t].loc[common_idx, 'open'] for t in tokens})
    highs = pd.DataFrame({t: dfs[t].loc[common_idx, 'high'] for t in tokens})
    lows = pd.DataFrame({t: dfs[t].loc[common_idx, 'low'] for t in tokens})

    # Funding rates
    df_funding = pd.read_parquet('data/binance_funding_8h.parquet')
    if df_funding.index.tz is not None:
        df_funding.index = df_funding.index.tz_localize(None)
    funding_aligned = df_funding.reindex(common_idx, method='ffill').fillna(0.0001)
    is_settlement_bar = pd.Series(common_idx.hour.isin([0, 8, 16]), index=common_idx)

    # Causal Indicators: Strictly shift(1)
    closes_prior = closes.shift(1)
    ema200 = closes_prior.ewm(span=200).mean()
    bb_mid = closes_prior.rolling(120).mean()
    bb_std = closes_prior.rolling(120).std()
    bb_z = (closes_prior - bb_mid) / (bb_std + 1e-8)
    mom20 = (closes_prior / closes_prior.shift(120)) - 1.0
    score = bb_z + mom20

    # Next open returns
    next_open_rets = opens.shift(-1) / opens - 1.0
    # Intrabar low draw from open to check liquidation: (low - open) / open
    intrabar_low_pct = (lows - opens) / opens

    # BTC Macro Trend Gate
    btc_bull = closes_prior['BTCUSDT'] > ema200['BTCUSDT']

    def simulate_leverage_run(start_dt, end_dt, leverage=1.0, fee_rate=0.0008, rebal_bars=6, hysteresis=0.005, mmr=0.005):
        mask = (common_idx >= start_dt) & (common_idx <= end_dt)
        sub_idx = common_idx[mask]
        if len(sub_idx) < 10:
            return None

        cap = 10000.0
        curr_pos = 'USDT_CASH'
        entry_price = 0.0
        highest_price = 0.0

        equity_curve = []
        liquidated = False
        liquidation_date = None
        liq_count = 0
        total_fees_paid = 0.0
        total_funding_paid = 0.0
        switches_count = 0

        # Liquidation drop threshold: drop from entry price that wipes position
        # LiqPrice = Entry * (1 - 1/L + MMR)
        # Drop_pct = (LiqPrice - Entry)/Entry = - (1/L - MMR)
        # For L=1.0: no liquidation
        max_allowed_drop = (1.0 / leverage - mmr) if leverage > 1.0 else 1.0

        for i, t in enumerate(sub_idx):
            if liquidated:
                equity_curve.append(0.0)
                continue

            settle = is_settlement_bar.loc[t]

            # Rebalance check
            if i % rebal_bars == 0:
                s_row = score.loc[t].dropna()
                top_cand = s_row.idxmax() if len(s_row) >= len(tokens) else 'BTCUSDT'

                cand_close = closes_prior.loc[t, top_cand]
                cand_ema = ema200.loc[t, top_cand]
                cand_dist = (cand_close - cand_ema) / cand_ema
                btc_is_bull = btc_bull.loc[t]

                if curr_pos != 'USDT_CASH':
                    dual_pass = btc_is_bull and (cand_dist >= -hysteresis)
                else:
                    dual_pass = btc_is_bull and (cand_dist >= hysteresis)

                target_pos = top_cand if dual_pass else 'USDT_CASH'

                # Execute switch
                if target_pos != curr_pos:
                    switches_count += 1
                    legs = 0
                    if curr_pos != 'USDT_CASH':
                        legs += 1 # close old
                    if target_pos != 'USDT_CASH':
                        legs += 1 # open new

                    # Fee is on NOMINAL position: cap * leverage * fee_rate
                    fee_deduction = cap * leverage * fee_rate * legs
                    total_fees_paid += fee_deduction
                    cap -= fee_deduction

                    if cap <= 0:
                        liquidated = True
                        liquidation_date = t
                        cap = 0.0
                        equity_curve.append(0.0)
                        continue

                    if target_pos != 'USDT_CASH':
                        entry_price = opens.loc[t, target_pos]
                        highest_price = entry_price
                    else:
                        entry_price = 0.0
                        highest_price = 0.0

                    curr_pos = target_pos

            # Intrabar risk and bar return
            if curr_pos != 'USDT_CASH':
                curr_c = closes.loc[t, curr_pos]
                curr_h = highs.loc[t, curr_pos]
                curr_l = lows.loc[t, curr_pos]
                highest_price = max(highest_price, curr_h)

                # Intrabar liquidation check:
                # If price drops from entry by more than max_allowed_drop
                drop_from_entry = (curr_l - entry_price) / entry_price if entry_price > 0 else 0.0
                if leverage > 1.0 and drop_from_entry <= -max_allowed_drop:
                    liquidated = True
                    liquidation_date = t
                    liq_count += 1
                    cap = 0.0
                    equity_curve.append(0.0)
                    continue

                # Asset bar return
                asset_r = next_open_rets.loc[t, curr_pos]
                leveraged_r = asset_r * leverage

                # Funding cost check if holding perp long
                funding_cost = 0.0
                if settle and leverage > 1.0:
                    fr = funding_aligned.loc[t, curr_pos] if curr_pos in funding_aligned else funding_aligned.loc[t, 'ETHUSDT']
                    # Long pays funding rate if positive: on nominal position (leverage * cap)
                    # Borrow interest on leveraged portion (L - 1) * 8h interest (~0.0001 per 8h ≈ 10% APR)
                    borrow_fee = (leverage - 1.0) * 0.0001
                    funding_cost = (leverage * fr) + borrow_fee
                    total_funding_paid += (cap * funding_cost)

                net_bar_r = leveraged_r - funding_cost

                # If single bar loss wipes out equity
                if net_bar_r <= -1.0:
                    liquidated = True
                    liquidation_date = t
                    liq_count += 1
                    cap = 0.0
                    equity_curve.append(0.0)
                    continue

                cap *= (1.0 + net_bar_r)
                if cap <= 0:
                    liquidated = True
                    liquidation_date = t
                    liq_count += 1
                    cap = 0.0
            else:
                # 100% USDT cash: return = 0
                pass

            equity_curve.append(max(0.0, cap))

        s = pd.Series(equity_curve, index=sub_idx)
        tot_ret = (s.iloc[-1] / 10000.0 - 1.0) * 100.0 if not liquidated else -100.0
        peak = s.cummax()
        dd = (s - peak) / peak if not liquidated else pd.Series(-1.0, index=sub_idx)
        mdd = dd.min() * 100.0 if not liquidated else -100.0

        days = (sub_idx[-1] - sub_idx[0]).total_seconds() / 86400.0
        years = days / 365.25
        cagr = ((s.iloc[-1] / 10000.0) ** (1.0 / years) - 1.0) * 100.0 if s.iloc[-1] > 0 and years > 0 else -100.0
        calmar = abs(cagr / mdd) if abs(mdd) > 1e-4 else 0.0

        d_s = s.resample('1D').last().dropna().pct_change().dropna()
        sharpe = (d_s.mean() / (d_s.std() + 1e-8)) * np.sqrt(365) if len(d_s) > 1 and not liquidated else -99.0

        # Max allowed drop for this leverage
        liq_distance_pct = max_allowed_drop * 100.0

        return {
            'leverage': leverage,
            'liquidated': liquidated,
            'liquidation_date': str(liquidation_date) if liquidation_date else None,
            'liq_distance_pct': round(liq_distance_pct, 2),
            'final_equity': round(s.iloc[-1], 2),
            'tot_ret': round(tot_ret, 2),
            'cagr': round(cagr, 2),
            'mdd': round(mdd, 2),
            'sharpe': round(sharpe, 2),
            'calmar': round(calmar, 2),
            'total_fees_paid': round(total_fees_paid, 2),
            'total_funding_paid': round(total_funding_paid, 2),
            'switches_count': switches_count,
        }

    periods = {
        '2020-2024 (Training 完整牛熊)': ('2020-08-11', '2024-12-31'),
        '2025 (Validation 震荡分化)': ('2025-01-01', '2025-12-31'),
        '2026 (Test 盲测阴跌)': ('2026-01-01', '2026-09-13'),
        '2022 (Bear Stress 极端熊市)': ('2022-01-01', '2022-12-31'),
        'Full Cycle (2020-2026 全周期)': ('2020-08-11', '2026-09-13'),
    }

    leverages = [1.0, 2.0, 3.0, 5.0]
    out = {}
    for p_name, (s, e) in periods.items():
        out[p_name] = {}
        for lev in leverages:
            out[p_name][lev] = simulate_leverage_run(s, e, leverage=lev)

    return out

if __name__ == '__main__':
    results = run_leverage_comparison()

    print("\n" + "="*115)
    print("【杠杆倍数深度对比】1.0x 现货 vs 2.0x 杠杆 vs 3.0x 杠杆 vs 5.0x 杠杆")
    print("策略配置：V1 双重宏观门控 + Top-1 截面轮动 + 100% USDT 现金防守")
    print("="*115)
    print(f"{'时间阶段':<28} | {'杠杆倍数':<6} | {'强平容忍跌幅':<10} | {'总收益 %':<14} | {'年化 CAGR':<12} | {'最大回撤 MDD':<12} | {'夏普':<6} | {'卡玛':<6} | {'是否爆仓'}")
    print("-"*115)

    for p_name, lev_dict in results.items():
        for lev, r in lev_dict.items():
            liq_tag = f"💥 爆仓清零 ({r['liquidation_date'][:10]})" if r['liquidated'] else "✅ 安全存活"
            print(f"{p_name:<28} | {lev:>4.1f}x | -{r['liq_distance_pct']:>5.1f}%     | {r['tot_ret']:>+12.2f}% | {r['cagr']:>10.2f}% | {r['mdd']:>10.2f}% | {r['sharpe']:>6.2f} | {r['calmar']:>6.2f} | {liq_tag}")
        print("-"*115)
