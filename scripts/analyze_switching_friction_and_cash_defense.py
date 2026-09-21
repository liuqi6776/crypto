# -*- coding: utf-8 -*-
"""
Empirical Analysis:
1. Transaction Fee & Switching Friction Wear (手续费磨损分析)
2. Performance with Pure USDT Cash Defense (不要合约反向套利会如何)
Across 2020-2024, 2025, 2026, 2022 Bear Market, and Full Cycle (2020-2026).
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

def run_comparative_friction_and_cash_analysis():
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

    # Funding rate data
    df_funding = pd.read_parquet('data/binance_funding_8h.parquet')
    if df_funding.index.tz is not None:
        df_funding.index = df_funding.index.tz_localize(None)
    funding_aligned = df_funding.reindex(common_idx, method='ffill').fillna(0.0001)

    # Funding rates for ETH and BTC
    fr_eth = funding_aligned['ETHUSDT']
    fr_btc = funding_aligned['BTCUSDT']
    safe_fr = np.maximum(fr_eth, fr_btc)
    is_settlement_bar = pd.Series(common_idx.hour.isin([0, 8, 16]), index=common_idx)

    # Causal Indicators: Strictly shift(1)
    closes_prior = closes.shift(1)
    ema200 = closes_prior.ewm(span=200).mean()
    bb_mid = closes_prior.rolling(120).mean()
    bb_std = closes_prior.rolling(120).std()
    bb_z = (closes_prior - bb_mid) / (bb_std + 1e-8)
    mom20 = (closes_prior / closes_prior.shift(120)) - 1.0
    score = bb_z + mom20

    # Next-bar open returns for realistic execution
    # Buying at next open: return from open(t+1) to open(t+2)
    next_open_rets = opens.shift(-1) / opens - 1.0

    # BTC Macro Trend Gate
    btc_bull = closes_prior['BTCUSDT'] > ema200['BTCUSDT']

    def simulate_period(start_dt, end_dt, fee_rate=0.0008, rebal_freq_bars=6, hysteresis=0.005):
        """
        Runs portfolio simulation for:
        1. Dual Gate + 100% USDT Cash Defense (No Arbitrage) - Zero fee drag baseline & With Fee
        2. Dual Gate + 100% Funding Arbitrage (50% nominal basis carry)
        3. Single Gate + 100% USDT Cash Defense
        4. Always in Top-1 (No defense)
        5. BTC Buy & Hold
        6. ETH Buy & Hold
        """
        mask = (common_idx >= start_dt) & (common_idx <= end_dt)
        sub_idx = common_idx[mask]

        if len(sub_idx) < 10:
            return None

        # State trackers
        # 1. Dual Gate + Cash (Net: with fee)
        cap_dual_cash = 10000.0
        # 1b. Dual Gate + Cash (Gross: zero fee)
        cap_dual_cash_gross = 10000.0
        # 1c. Dual Gate + Cash (Stressed: 12 bps fee)
        cap_dual_cash_stress = 10000.0

        # 2. Dual Gate + Funding Carry (Net: 50% nominal, 4-leg friction on arb enter/exit)
        cap_dual_arb = 10000.0

        # 3. Single Gate + Cash
        cap_single_cash = 10000.0

        # 4. Always Top-1 (No Gate)
        cap_always = 10000.0

        # Holdings
        curr_dual_cash = 'USDT_CASH'
        curr_dual_arb = 'USDT_CASH'
        curr_single_cash = 'USDT_CASH'
        curr_always = None

        # Tracking switches and fee deductions for Dual Gate Cash
        switches_count = 0
        switch_cash_to_token = 0
        switch_token_to_cash = 0
        switch_token_to_token = 0
        total_fees_paid_usdt = 0.0
        bars_in_cash = 0
        bars_in_token = 0

        eq_dual_cash = []
        eq_dual_cash_gross = []
        eq_dual_cash_stress = []
        eq_dual_arb = []
        eq_single_cash = []
        eq_always = []
        btc_rets = []
        eth_rets = []

        holding_durations = []
        curr_hold_bars = 0

        for i, t in enumerate(sub_idx):
            settle = is_settlement_bar.loc[t]
            curr_fr = max(0.0, safe_fr.loc[t]) if settle else 0.0

            # Evaluate signal at rebalance bars (daily at 00:00 UTC)
            if i % rebal_freq_bars == 0:
                s_row = score.loc[t].dropna()
                if len(s_row) < len(tokens):
                    top_cand = 'BTCUSDT'
                else:
                    top_cand = s_row.idxmax()

                # Hysteresis check for Dual Gate
                cand_close = closes_prior.loc[t, top_cand]
                cand_ema = ema200.loc[t, top_cand]
                cand_dist = (cand_close - cand_ema) / cand_ema
                btc_is_bull = btc_bull.loc[t]

                # Dual gate condition
                if curr_dual_cash != 'USDT_CASH':
                    # In token: exit only if drops below -0.5%
                    dual_pass = btc_is_bull and (cand_dist >= -hysteresis)
                else:
                    # In cash: enter only if clears +0.5%
                    dual_pass = btc_is_bull and (cand_dist >= hysteresis)

                target_dual = top_cand if dual_pass else 'USDT_CASH'

                # Single gate condition
                single_pass = (cand_dist >= (hysteresis if curr_single_cash == 'USDT_CASH' else -hysteresis))
                target_single = top_cand if single_pass else 'USDT_CASH'

                target_always = top_cand

                # --- Execute Switch for Dual Gate + Cash ---
                fee_dual_cash = 0.0
                fee_dual_cash_stress = 0.0
                if target_dual != curr_dual_cash:
                    switches_count += 1
                    if curr_hold_bars > 0:
                        holding_durations.append(curr_hold_bars)
                    curr_hold_bars = 0

                    if curr_dual_cash == 'USDT_CASH' and target_dual != 'USDT_CASH':
                        switch_cash_to_token += 1
                        fee_dual_cash = fee_rate # 1 leg
                        fee_dual_cash_stress = 0.0012
                    elif curr_dual_cash != 'USDT_CASH' and target_dual == 'USDT_CASH':
                        switch_token_to_cash += 1
                        fee_dual_cash = fee_rate # 1 leg
                        fee_dual_cash_stress = 0.0012
                    else:
                        switch_token_to_token += 1
                        fee_dual_cash = fee_rate * 2 # 2 legs (sell A + buy B)
                        fee_dual_cash_stress = 0.0012 * 2

                    fee_dollar = cap_dual_cash * fee_dual_cash
                    total_fees_paid_usdt += fee_dollar
                    cap_dual_cash -= fee_dollar
                    cap_dual_cash_stress -= (cap_dual_cash_stress * fee_dual_cash_stress)

                curr_dual_cash = target_dual

                # --- Dual Gate + Arb ---
                fee_dual_arb = 0.0
                if target_dual != curr_dual_arb:
                    # If switching between token and arb:
                    # Entering arb requires spot buy + perp short (2 legs = 0.16%)
                    # Exiting arb requires spot sell + perp close (2 legs = 0.16%)
                    # Switching token to token = 0.16%
                    fee_dual_arb = fee_rate * 2
                    cap_dual_arb -= (cap_dual_arb * fee_dual_arb)
                curr_dual_arb = target_dual

                # --- Single Gate + Cash ---
                fee_single = 0.0
                if target_single != curr_single_cash:
                    legs = 1 if (curr_single_cash == 'USDT_CASH' or target_single == 'USDT_CASH') else 2
                    cap_single_cash -= (cap_single_cash * (fee_rate * legs))
                curr_single_cash = target_single

                # --- Always Top-1 ---
                if target_always != curr_always and curr_always is not None:
                    cap_always -= (cap_always * (fee_rate * 2))
                curr_always = target_always

            # End of rebalance check

            # Apply bar returns
            # 1. Dual Cash
            if curr_dual_cash == 'USDT_CASH':
                bars_in_cash += 1
                r_dc = 0.0
                r_dc_gross = 0.0
                r_dc_stress = 0.0
            else:
                bars_in_token += 1
                curr_hold_bars += 1
                asset_r = next_open_rets.loc[t, curr_dual_cash]
                r_dc = asset_r
                r_dc_gross = asset_r
                r_dc_stress = asset_r

            cap_dual_cash *= (1.0 + r_dc)
            cap_dual_cash_gross *= (1.0 + r_dc_gross)
            cap_dual_cash_stress *= (1.0 + r_dc_stress)

            # 2. Dual Arb
            if curr_dual_arb == 'USDT_CASH':
                # Delta-neutral funding carry: earns on 50% nominal basis
                # In real market, also pay spot-futures basis friction (~0.05% annualized drag)
                r_arb = curr_fr * 0.5
            else:
                r_arb = next_open_rets.loc[t, curr_dual_arb]
            cap_dual_arb *= (1.0 + r_arb)

            # 3. Single Cash
            if curr_single_cash == 'USDT_CASH':
                r_sc = 0.0
            else:
                r_sc = next_open_rets.loc[t, curr_single_cash]
            cap_single_cash *= (1.0 + r_sc)

            # 4. Always
            r_al = next_open_rets.loc[t, curr_always]
            cap_always *= (1.0 + r_al)

            eq_dual_cash.append(cap_dual_cash)
            eq_dual_cash_gross.append(cap_dual_cash_gross)
            eq_dual_cash_stress.append(cap_dual_cash_stress)
            eq_dual_arb.append(cap_dual_arb)
            eq_single_cash.append(cap_single_cash)
            eq_always.append(cap_always)

            btc_rets.append(next_open_rets.loc[t, 'BTCUSDT'])
            eth_rets.append(next_open_rets.loc[t, 'ETHUSDT'])

        # Build series
        s_dc = pd.Series(eq_dual_cash, index=sub_idx)
        s_dc_gross = pd.Series(eq_dual_cash_gross, index=sub_idx)
        s_dc_stress = pd.Series(eq_dual_cash_stress, index=sub_idx)
        s_da = pd.Series(eq_dual_arb, index=sub_idx)
        s_sc = pd.Series(eq_single_cash, index=sub_idx)
        s_al = pd.Series(eq_always, index=sub_idx)
        s_btc = 10000.0 * (1.0 + pd.Series(btc_rets, index=sub_idx)).cumprod()
        s_eth = 10000.0 * (1.0 + pd.Series(eth_rets, index=sub_idx)).cumprod()

        def calc_stats(s):
            tot = (s.iloc[-1] / s.iloc[0] - 1.0) * 100.0
            peak = s.cummax()
            dd = (s - peak) / peak
            mdd = dd.min() * 100.0
            days = (s.index[-1] - s.index[0]).total_seconds() / 86400.0
            years = days / 365.25
            cagr = ((s.iloc[-1] / s.iloc[0]) ** (1.0 / years) - 1.0) * 100.0 if s.iloc[-1] > 0 and years > 0 else 0.0
            calmar = abs(cagr / mdd) if abs(mdd) > 1e-4 else 0.0
            d_s = s.resample('1D').last().dropna().pct_change().dropna()
            sharpe = (d_s.mean() / (d_s.std() + 1e-8)) * np.sqrt(365) if len(d_s) > 1 else 0.0
            return {
                'final_equity': round(s.iloc[-1], 2),
                'tot_ret': round(tot, 2),
                'cagr': round(cagr, 2),
                'mdd': round(mdd, 2),
                'sharpe': round(sharpe, 2),
                'calmar': round(calmar, 2),
            }

        days_tot = (sub_idx[-1] - sub_idx[0]).total_seconds() / 86400.0
        years_tot = days_tot / 365.25
        avg_hold_days = (np.mean(holding_durations) * 4 / 24) if len(holding_durations) > 0 else 0.0
        turnover_annual = (switches_count / years_tot) if years_tot > 0 else 0.0
        cash_pct = (bars_in_cash / len(sub_idx)) * 100.0

        # Fee friction analysis
        gross_tot = (s_dc_gross.iloc[-1] / s_dc_gross.iloc[0] - 1.0) * 100.0
        net_tot = (s_dc.iloc[-1] / s_dc.iloc[0] - 1.0) * 100.0
        stress_tot = (s_dc_stress.iloc[-1] / s_dc_stress.iloc[0] - 1.0) * 100.0
        gross_cagr = calc_stats(s_dc_gross)['cagr']
        net_cagr = calc_stats(s_dc)['cagr']
        fee_drag_cagr = gross_cagr - net_cagr

        return {
            'days': round(days_tot, 1),
            'years': round(years_tot, 2),
            'switches_count': switches_count,
            'switch_cash_to_token': switch_cash_to_token,
            'switch_token_to_cash': switch_token_to_cash,
            'switch_token_to_token': switch_token_to_token,
            'avg_hold_days': round(avg_hold_days, 1),
            'turnover_annual': round(turnover_annual, 1),
            'cash_pct': round(cash_pct, 1),
            'total_fees_paid_usdt': round(total_fees_paid_usdt, 2),
            'gross_tot': round(gross_tot, 2),
            'net_tot': round(net_tot, 2),
            'stress_tot': round(stress_tot, 2),
            'fee_drag_cagr': round(fee_drag_cagr, 2),
            'stats_dual_cash': calc_stats(s_dc),
            'stats_dual_cash_gross': calc_stats(s_dc_gross),
            'stats_dual_cash_stress': calc_stats(s_dc_stress),
            'stats_dual_arb': calc_stats(s_da),
            'stats_single_cash': calc_stats(s_sc),
            'stats_always': calc_stats(s_al),
            'stats_btc': calc_stats(s_btc),
            'stats_eth': calc_stats(s_eth),
        }

    # Run for the specified periods
    periods = {
        '2020-2024 (Training 完整牛熊)': ('2020-08-11', '2024-12-31'),
        '2025 (Validation 震荡分化)': ('2025-01-01', '2025-12-31'),
        '2026 (Test 盲测阴跌)': ('2026-01-01', '2026-09-13'),
        '2022 (Bear Stress 极端熊市)': ('2022-01-01', '2022-12-31'),
        'Full Cycle (2020-2026 全周期)': ('2020-08-11', '2026-09-13'),
    }

    results = {}
    for p_name, (s, e) in periods.items():
        results[p_name] = simulate_period(s, e)

    return results

if __name__ == '__main__':
    res = run_comparative_friction_and_cash_analysis()
    
    print("\n" + "="*90)
    print("一、 每次切换手续费磨损与换手频率详细审计 (Fee Friction & Turnover Analysis)")
    print("="*90)
    print(f"{'时间阶段':<30} | {'总切换次数':<10} | {'买入':<6} | {'卖出(平仓)':<10} | {'币种轮动':<8} | {'平均持仓':<8} | {'年化换手':<8} | {'年化手续费拖累'}")
    print("-"*90)
    for p_name, r in res.items():
        print(f"{p_name:<30} | {r['switches_count']:<10} | {r['switch_cash_to_token']:<6} | {r['switch_token_to_cash']:<10} | {r['switch_token_to_token']:<8} | {r['avg_hold_days']}天   | {r['turnover_annual']}次/年 | {r['fee_drag_cagr']}%/年")

    print("\n" + "="*90)
    print("手续费敏感度测试 (Gross 0 bps vs Net 8 bps vs Stress 12 bps):")
    print("-"*90)
    print(f"{'时间阶段':<30} | {'零手续费毛收益 (0 bps)':<22} | {'标准实盘净收益 (8 bps)':<22} | {'滑点压力测试 (12 bps)'}")
    print("-"*90)
    for p_name, r in res.items():
        print(f"{p_name:<30} | {r['gross_tot']:>+12.2f}% (CAGR {r['stats_dual_cash_gross']['cagr']:>6.1f}%) | {r['net_tot']:>+12.2f}% (CAGR {r['stats_dual_cash']['cagr']:>6.1f}%) | {r['stress_tot']:>+12.2f}% (CAGR {r['stats_dual_cash_stress']['cagr']:>6.1f}%)")

    print("\n" + "="*110)
    print("二、 不要合约反向套利会如何？(双重宏观门控+纯现金防守 vs 资金费套利 vs 基准 对比表)")
    print("="*110)
    header = f"{'时间阶段':<25} | {'策略配置模型':<28} | {'总收益 %':<12} | {'年化 CAGR':<10} | {'最大回撤 MDD':<12} | {'日频夏普':<8} | {'卡玛比率'}"
    print(header)
    print("-"*110)

    for p_name, r in res.items():
        print(f"[{p_name}]")
        # 1. Dual Cash
        dc = r['stats_dual_cash']
        print(f"  * 方案一: 双重门控 + 100% USDT 纯现金   | {dc['tot_ret']:>+10.2f}% | {dc['cagr']:>8.2f}% | {dc['mdd']:>10.2f}% | {dc['sharpe']:>8.2f} | {dc['calmar']:>7.2f}")
        # 2. Dual Arb
        da = r['stats_dual_arb']
        print(f"  * 方案二: 双重门控 + 50% 资金费率套利   | {da['tot_ret']:>+10.2f}% | {da['cagr']:>8.2f}% | {da['mdd']:>10.2f}% | {da['sharpe']:>8.2f} | {da['calmar']:>7.2f}")
        # 3. Single Cash
        sc = r['stats_single_cash']
        print(f"  * 方案三: 单币门控 + 100% USDT 纯现金   | {sc['tot_ret']:>+10.2f}% | {sc['cagr']:>8.2f}% | {sc['mdd']:>10.2f}% | {sc['sharpe']:>8.2f} | {sc['calmar']:>7.2f}")
        # 4. Always Top-1
        al = r['stats_always']
        print(f"  * 方案四: 永不空仓 (单纯100%持仓轮动) | {al['tot_ret']:>+10.2f}% | {al['cagr']:>8.2f}% | {al['mdd']:>10.2f}% | {al['sharpe']:>8.2f} | {al['calmar']:>7.2f}")
        # BTC Buy & Hold
        btc = r['stats_btc']
        print(f"  * 基准 A: BTC 买入持有 (Buy & Hold)    | {btc['tot_ret']:>+10.2f}% | {btc['cagr']:>8.2f}% | {btc['mdd']:>10.2f}% | {btc['sharpe']:>8.2f} | {btc['calmar']:>7.2f}")
        # ETH Buy & Hold
        eth = r['stats_eth']
        print(f"  * 基准 B: ETH 买入持有 (Buy & Hold)    | {eth['tot_ret']:>+10.2f}% | {eth['cagr']:>8.2f}% | {eth['mdd']:>10.2f}% | {eth['sharpe']:>8.2f} | {eth['calmar']:>7.2f}")
        print(f"  -> 空仓防守时间占比: {r['cash_pct']}% | 年化调仓换手: {r['turnover_annual']} 次/年 | 平均单笔持仓: {r['avg_hold_days']} 天")
        print("-" * 110)
