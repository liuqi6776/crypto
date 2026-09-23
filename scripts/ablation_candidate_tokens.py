# -*- coding: utf-8 -*-
"""
Ablation Study of Individual Token Additions to Core-4 Benchmark
================================================================
Evaluates the marginal contribution, risk, and friction of adding:
  - +NEAR
  - +AVAX
  - +LINK
  - +SUI (from 2023-05)
  - +NEAR + AVAX (Top-6)
  - +NEAR + AVAX + SUI (Top-7 Next-Gen)
  - +NEAR + AVAX + LINK + SUI (Top-8 Institutional)
Under 3.0x Compact Adaptive Strategy (SL 1.5x ATR + Trailing Ratchet).
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, List
import numpy as np
import pandas as pd

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def run_ablation():
    all_syms = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'AVAXUSDT', 'NEARUSDT', 'LINKUSDT', 'SUIUSDT']
    raw_dfs = {s: pd.read_parquet(f'data/{s}_4h_2020_2026.parquet') for s in all_syms}

    df_funding = pd.read_parquet('data/binance_funding_8h.parquet')
    if df_funding.index.tz is not None:
        df_funding.index = df_funding.index.tz_localize(None)

    def evaluate_combination(token_list: List[str], start_dt: str, end_dt: str, leverage: float = 3.0):
        common_idx = raw_dfs['BTCUSDT'].index
        for t in token_list:
            common_idx = common_idx.intersection(raw_dfs[t].index)
        common_idx = common_idx[(common_idx >= start_dt) & (common_idx <= end_dt)].sort_values()

        if len(common_idx) < 20:
            return None

        closes = pd.DataFrame({t: raw_dfs[t].loc[common_idx, 'close'] for t in token_list})
        opens = pd.DataFrame({t: raw_dfs[t].loc[common_idx, 'open'] for t in token_list})
        highs = pd.DataFrame({t: raw_dfs[t].loc[common_idx, 'high'] for t in token_list})
        lows = pd.DataFrame({t: raw_dfs[t].loc[common_idx, 'low'] for t in token_list})

        atrs = {}
        for t in token_list:
            tr1 = highs[t] - lows[t]
            tr2 = (highs[t] - closes[t].shift(1)).abs()
            tr3 = (lows[t] - closes[t].shift(1)).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
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
        entry_price = 0.0
        highest_price = 0.0
        stop_price = 0.0

        equity_curve = []
        trades = []
        liquidated = False
        liquidation_date = None
        stop_count = 0
        fee_rate = 0.0008
        slippage = 0.0015
        total_fees = 0.0
        total_slippage = 0.0
        total_funding = 0.0
        min_distance_to_liq = 1.0 # tracking closest margin to liquidation line

        asset_holding_bars = {t: 0 for t in token_list}
        asset_holding_bars['USDT_CASH'] = 0

        liq_drop_pct = (1.0 / leverage - 0.005) if leverage > 1.0 else 1.0 # 32.83%

        for i, t in enumerate(common_idx):
            if liquidated:
                equity_curve.append(0.0)
                continue

            asset_holding_bars[curr_pos] += 1
            settle = is_settlement_bar.loc[t]

            if curr_pos != 'USDT_CASH':
                bar_open = opens.loc[t, curr_pos]
                bar_high = highs.loc[t, curr_pos]
                bar_low = lows.loc[t, curr_pos]
                bar_close = closes.loc[t, curr_pos]
                highest_price = max(highest_price, bar_high)

                # Distance to liq
                liq_p = entry_price * (1.0 - liq_drop_pct)
                dist_pct = (bar_low - liq_p) / entry_price
                min_distance_to_liq = min(min_distance_to_liq, dist_pct)

                if bar_low <= liq_p:
                    liquidated = True
                    liquidation_date = str(t)
                    cap = 0.0
                    equity_curve.append(0.0)
                    trades.append({'token': curr_pos, 'ret': -1.0, 'type': 'LIQUIDATION'})
                    continue

                if stop_price > 0 and bar_low <= stop_price:
                    stop_count += 1
                    exec_exit = min(bar_open, stop_price * (1.0 - slippage))
                    asset_ret = (exec_exit - entry_price) / entry_price
                    lev_ret = asset_ret * leverage
                    close_fee = cap * leverage * fee_rate
                    total_fees += close_fee
                    total_slippage += cap * leverage * slippage

                    pnl = (cap * lev_ret) - close_fee
                    cap = max(0.0, cap + pnl)
                    trades.append({'token': curr_pos, 'ret': lev_ret, 'type': 'STOP_LOSS'})

                    curr_pos = 'USDT_CASH'
                    entry_price = 0.0
                    stop_price = 0.0
                    highest_price = 0.0
                    equity_curve.append(cap)
                    continue

                if highest_price >= entry_price * 1.05:
                    stop_price = max(stop_price, entry_price * 1.002)
                if highest_price >= entry_price * 1.10:
                    stop_price = max(stop_price, highest_price * 0.95)

                bar_ret = (bar_close - bar_open) / bar_open
                bar_pnl = cap * leverage * bar_ret
                funding_cost = 0.0
                if settle and leverage > 1.0:
                    fr = funding_aligned.loc[t, curr_pos] if curr_pos in funding_aligned else 0.0001
                    borrow_fee = (leverage - 1.0) * 0.0001
                    funding_cost = cap * ((leverage * fr) + borrow_fee)
                    total_funding += funding_cost

                cap = max(0.0, cap + bar_pnl - funding_cost)
                if cap <= 0.0:
                    liquidated = True
                    liquidation_date = str(t)
                    equity_curve.append(0.0)
                    continue

            s_row = score.loc[t].dropna()
            top_cand = s_row.idxmax() if len(s_row) >= len(token_list) else 'BTCUSDT'
            cand_close = closes_prior.loc[t, top_cand]
            cand_ema = ema200.loc[t, top_cand]
            cand_dist = (cand_close - cand_ema) / cand_ema
            btc_is_bull = btc_bull.loc[t]

            if curr_pos != 'USDT_CASH':
                dual_pass = btc_is_bull and (cand_dist >= -0.005)
            else:
                dual_pass = btc_is_bull and (cand_dist >= 0.005)

            target_pos = top_cand if dual_pass else 'USDT_CASH'

            if target_pos != curr_pos:
                if curr_pos != 'USDT_CASH':
                    exit_p = opens.loc[t, curr_pos]
                    lev_ret = ((exit_p - entry_price) / entry_price) * leverage
                    close_fee = cap * leverage * fee_rate
                    total_fees += close_fee
                    cap = max(0.0, cap + (cap * lev_ret) - close_fee)
                    trades.append({'token': curr_pos, 'ret': lev_ret, 'type': 'SIGNAL_EXIT'})
                    curr_pos = 'USDT_CASH'

                if target_pos != 'USDT_CASH' and cap > 0:
                    curr_pos = target_pos
                    entry_price = opens.loc[t, target_pos]
                    highest_price = entry_price
                    gate_p = ema200.loc[t, target_pos] * 0.995
                    atr_val = df_atrs.loc[t, target_pos]
                    stop_price = max(gate_p, entry_price - (atr_val * 1.5))

                    open_fee = cap * leverage * fee_rate
                    total_fees += open_fee
                    cap -= open_fee

            equity_curve.append(cap)

        eq_s = pd.Series(equity_curve, index=common_idx)
        final_equity = eq_s.iloc[-1]
        total_ret_pct = ((final_equity - 10000.0) / 10000.0) * 100.0
        n_bars = len(eq_s)
        years = n_bars / (365.25 * 6)
        cagr_pct = ((final_equity / 10000.0) ** (1.0 / years) - 1.0) * 100.0 if (final_equity > 0 and years > 0) else -100.0

        running_max = eq_s.cummax()
        drawdown = (eq_s - running_max) / running_max
        max_dd_pct = drawdown.min() * 100.0

        daily_eq = eq_s.resample('1D').last().dropna()
        daily_rets = daily_eq.pct_change().dropna()
        sharpe = (daily_rets.mean() / (daily_rets.std() + 1e-8)) * np.sqrt(365) if len(daily_rets) > 10 else 0.0
        calmar = (cagr_pct / abs(max_dd_pct)) if abs(max_dd_pct) > 0.01 else 0.0

        win_trades = [tr for tr in trades if tr['ret'] > 0]
        win_rate = len(win_trades) / len(trades) * 100.0 if trades else 0.0

        total_holding_bars = sum(asset_holding_bars.values())
        holding_pcts = {k: round(v / total_holding_bars * 100.0, 1) for k, v in asset_holding_bars.items()}

        return {
            'final_equity': round(final_equity, 2),
            'total_ret_pct': round(total_ret_pct, 2),
            'cagr_pct': round(cagr_pct, 2),
            'max_dd_pct': round(max_dd_pct, 2),
            'sharpe': round(sharpe, 2),
            'calmar': round(calmar, 2),
            'win_rate': round(win_rate, 2),
            'trade_count': len(trades),
            'stop_count': stop_count,
            'liquidated': liquidated,
            'min_dist_to_liq_pct': round(min_distance_to_liq * 100.0, 2),
            'holding_pcts': holding_pcts,
        }

    # Test setups
    combos = {
        'Core-4 (Baseline)': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT'],
        '+NEAR': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'NEARUSDT'],
        '+AVAX': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'AVAXUSDT'],
        '+LINK': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'LINKUSDT'],
        '+NEAR+AVAX (Top-6)': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'NEARUSDT', 'AVAXUSDT'],
        '+NEAR+AVAX+LINK (Top-7)': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'NEARUSDT', 'AVAXUSDT', 'LINKUSDT'],
    }

    print("\n===================================================================================================")
    print(" ABLATION 1: 2026 近期样本外走势 (2026 OOS, 2026-01-01 ~ 2026-09-22)")
    print("===================================================================================================")
    for name, tokens in combos.items():
        res = evaluate_combination(tokens, '2026-01-01', '2026-09-22')
        print(f"  {name:25s} | 收益: {res['total_ret_pct']:+8.2f}% | 年化: {res['cagr_pct']:+8.2f}% | 回撤: {res['max_dd_pct']:6.2f}% | 夏普: {res['sharpe']:4.2f} | 交易: {res['trade_count']:3d} | 清算缓冲: {res['min_dist_to_liq_pct']:5.2f}%")

    print("\n===================================================================================================")
    print(" ABLATION 2: 2025 震荡分化期 (2025-01-01 ~ 2025-12-31)")
    print("===================================================================================================")
    for name, tokens in combos.items():
        res = evaluate_combination(tokens, '2025-01-01', '2025-12-31')
        print(f"  {name:25s} | 收益: {res['total_ret_pct']:+8.2f}% | 年化: {res['cagr_pct']:+8.2f}% | 回撤: {res['max_dd_pct']:6.2f}% | 夏普: {res['sharpe']:4.2f} | 交易: {res['trade_count']:3d} | 清算缓冲: {res['min_dist_to_liq_pct']:5.2f}%")

    print("\n===================================================================================================")
    print(" ABLATION 3: 2022 极端熊市期 (2022-01-01 ~ 2022-12-31)")
    print("===================================================================================================")
    for name, tokens in combos.items():
        res = evaluate_combination(tokens, '2022-01-01', '2022-12-31')
        print(f"  {name:25s} | 收益: {res['total_ret_pct']:+8.2f}% | 年化: {res['cagr_pct']:+8.2f}% | 回撤: {res['max_dd_pct']:6.2f}% | 夏普: {res['sharpe']:4.2f} | 交易: {res['trade_count']:3d} | 清算缓冲: {res['min_dist_to_liq_pct']:5.2f}%")

    print("\n===================================================================================================")
    print(" ABLATION 4: 包含 SUI 周期 (2023-05-04 ~ 2026-09-22)")
    print("===================================================================================================")
    sui_combos = {
        'Core-4 (Baseline)': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT'],
        '+SUI (Next-Gen L1)': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'SUIUSDT'],
        '+NEAR': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'NEARUSDT'],
        '+AVAX': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'AVAXUSDT'],
        '+NEAR+SUI': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'NEARUSDT', 'SUIUSDT'],
        '+NEAR+AVAX+SUI (Top-7)': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'NEARUSDT', 'AVAXUSDT', 'SUIUSDT'],
    }
    for name, tokens in sui_combos.items():
        res = evaluate_combination(tokens, '2023-05-04', '2026-09-22')
        print(f"  {name:25s} | 收益: {res['total_ret_pct']:+13.2f}% | 年化: {res['cagr_pct']:+8.2f}% | 回撤: {res['max_dd_pct']:6.2f}% | 夏普: {res['sharpe']:4.2f} | 卡玛: {res['calmar']:5.1f} | 交易: {res['trade_count']:3d}")

if __name__ == '__main__':
    run_ablation()
