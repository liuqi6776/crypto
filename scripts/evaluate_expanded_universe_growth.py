# -*- coding: utf-8 -*-
"""
Empirical Universe Expansion Study:
Evaluating High-Growth, High-Liquidity Crypto Assets vs Core 4 Benchmark
========================================================================
Compares:
  Universe 1 (Core 4 Benchmark):   [BTC, ETH, SOL, BNB]
  Universe 2 (High-Beta L1 Top 6): [BTC, ETH, SOL, BNB, AVAX, NEAR]
  Universe 3 (DeFi & L1 Top 7):    [BTC, ETH, SOL, BNB, AVAX, NEAR, LINK]
  Universe 4 (Broad Top 10):       [BTC, ETH, SOL, BNB, AVAX, NEAR, LINK, ADA, DOT, XRP]
Under:
  - 1.0x Spot & 3.0x Leverage
  - Realistic 8 bps fee + 15 bps slippage + 10% APR borrow + Binance 8h funding
  - 1.5x ATR Stop-Loss + Trailing Ratchet (+5% BE, +10% Peak -5%)
  - Dual Macro Gate (BTC > EMA200 & Asset > EMA200)
"""

import os
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

def run_universe_study():
    all_symbols = [
        'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT',
        'AVAXUSDT', 'NEARUSDT', 'LINKUSDT', 'ADAUSDT',
        'DOTUSDT', 'LTCUSDT', 'XRPUSDT', 'SUIUSDT'
    ]

    raw_dfs = {}
    for sym in all_symbols:
        p = f'data/{sym}_4h_2020_2026.parquet'
        if os.path.exists(p):
            raw_dfs[sym] = pd.read_parquet(p)

    # Funding rates & settlement bars
    df_funding = pd.read_parquet('data/binance_funding_8h.parquet')
    if df_funding.index.tz is not None:
        df_funding.index = df_funding.index.tz_localize(None)

    universes = {
        'Core-4 (Baseline)': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT'],
        'Top-6 (High-Beta L1)': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'AVAXUSDT', 'NEARUSDT'],
        'Top-7 (Bluechip L1+DeFi)': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'AVAXUSDT', 'NEARUSDT', 'LINKUSDT'],
        'Top-10 (Broad Liquid)': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'AVAXUSDT', 'NEARUSDT', 'LINKUSDT', 'ADAUSDT', 'DOTUSDT', 'XRPUSDT'],
    }

    periods = {
        '2020-2026 (全周期)': ('2020-10-15', '2026-09-22'), # NEAR starts 2020-10-15
        '2020-2024 (训练牛熊期)': ('2020-10-15', '2024-12-31'),
        '2025 (分化震荡期)': ('2025-01-01', '2025-12-31'),
        '2026 (盲测弱势期)': ('2026-01-01', '2026-09-22'),
        '2022 (极端熊市压力测)': ('2022-01-01', '2022-12-31'),
    }

    results = []

    def simulate_universe(
        u_name: str,
        token_list: List[str],
        start_dt: str,
        end_dt: str,
        leverage: float = 3.0,
        fee_rate: float = 0.0008,
        slippage: float = 0.0015,
        hysteresis: float = 0.005,
        mmr: float = 0.005,
    ) -> Dict[str, Any]:
        # align timestamps
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

        # ATR (14 bars, 4h)
        atrs = {}
        for t in token_list:
            tr1 = highs[t] - lows[t]
            tr2 = (highs[t] - closes[t].shift(1)).abs()
            tr3 = (lows[t] - closes[t].shift(1)).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atrs[t] = tr.rolling(14).mean()
        df_atrs = pd.DataFrame(atrs)

        # Causal indicators (using prior close)
        closes_prior = closes.shift(1)
        ema200 = closes_prior.ewm(span=200).mean()
        bb_mid = closes_prior.rolling(120).mean()
        bb_std = closes_prior.rolling(120).std()
        bb_z = (closes_prior - bb_mid) / (bb_std + 1e-8)
        mom20 = (closes_prior / closes_prior.shift(120)) - 1.0
        score = bb_z + mom20

        # BTC Macro Gate
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
        signal_exit_count = 0
        total_fees = 0.0
        total_slippage_cost = 0.0
        total_funding = 0.0

        asset_holding_bars = {t: 0 for t in token_list}
        asset_holding_bars['USDT_CASH'] = 0

        liq_drop_pct = (1.0 / leverage - mmr) if leverage > 1.0 else 1.0

        for i, t in enumerate(common_idx):
            if liquidated:
                equity_curve.append(0.0)
                continue

            asset_holding_bars[curr_pos] += 1
            settle = is_settlement_bar.loc[t]

            # 1. Position tracking
            if curr_pos != 'USDT_CASH':
                bar_open = opens.loc[t, curr_pos]
                bar_high = highs.loc[t, curr_pos]
                bar_low = lows.loc[t, curr_pos]
                bar_close = closes.loc[t, curr_pos]
                highest_price = max(highest_price, bar_high)

                # Check liquidation
                liq_p = entry_price * (1.0 - liq_drop_pct)
                if leverage > 1.0 and bar_low <= liq_p:
                    liquidated = True
                    liquidation_date = str(t)
                    cap = 0.0
                    equity_curve.append(0.0)
                    trades.append({'token': curr_pos, 'ret': -1.0, 'type': 'LIQUIDATION'})
                    continue

                # Check Stop-Loss
                if stop_price > 0 and bar_low <= stop_price:
                    stop_count += 1
                    exec_exit = min(bar_open, stop_price * (1.0 - slippage))
                    asset_ret = (exec_exit - entry_price) / entry_price
                    lev_ret = asset_ret * leverage
                    close_fee = cap * leverage * fee_rate
                    total_fees += close_fee
                    total_slippage_cost += cap * leverage * slippage

                    pnl = (cap * lev_ret) - close_fee
                    cap = max(0.0, cap + pnl)
                    trades.append({'token': curr_pos, 'ret': lev_ret, 'type': 'STOP_LOSS'})

                    curr_pos = 'USDT_CASH'
                    entry_price = 0.0
                    stop_price = 0.0
                    highest_price = 0.0
                    equity_curve.append(cap)
                    continue

                # Trailing Stop Ratchet
                if highest_price >= entry_price * 1.05:
                    be_stop = entry_price * 1.002
                    stop_price = max(stop_price, be_stop)
                if highest_price >= entry_price * 1.10:
                    trail_stop = highest_price * 0.95
                    stop_price = max(stop_price, trail_stop)

                # MTM & Funding
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

            # 2. Rebalance
            s_row = score.loc[t].dropna()
            top_cand = s_row.idxmax() if len(s_row) >= len(token_list) else 'BTCUSDT'

            cand_close = closes_prior.loc[t, top_cand]
            cand_ema = ema200.loc[t, top_cand]
            cand_dist = (cand_close - cand_ema) / cand_ema
            btc_is_bull = btc_bull.loc[t]

            if curr_pos != 'USDT_CASH':
                dual_pass = btc_is_bull and (cand_dist >= -hysteresis)
            else:
                dual_pass = btc_is_bull and (cand_dist >= hysteresis)

            target_pos = top_cand if dual_pass else 'USDT_CASH'

            if target_pos != curr_pos:
                if curr_pos != 'USDT_CASH':
                    signal_exit_count += 1
                    exit_p = opens.loc[t, curr_pos]
                    asset_ret = (exit_p - entry_price) / entry_price
                    lev_ret = asset_ret * leverage
                    close_fee = cap * leverage * fee_rate
                    total_fees += close_fee
                    cap = max(0.0, cap + (cap * lev_ret) - close_fee)
                    trades.append({'token': curr_pos, 'ret': lev_ret, 'type': 'SIGNAL_EXIT'})
                    curr_pos = 'USDT_CASH'

                if target_pos != 'USDT_CASH' and cap > 0:
                    curr_pos = target_pos
                    entry_price = opens.loc[t, target_pos]
                    highest_price = entry_price
                    gate_p = ema200.loc[t, target_pos] * (1.0 - hysteresis)
                    # Adaptive 1.5x ATR stop
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

        # Holding distribution %
        total_holding_bars = sum(asset_holding_bars.values())
        holding_pcts = {k: round(v / total_holding_bars * 100.0, 1) for k, v in asset_holding_bars.items()}

        return {
            'universe': u_name,
            'token_count': len(token_list),
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
            'total_fees': round(total_fees, 2),
            'total_slippage': round(total_slippage_cost, 2),
            'total_funding': round(total_funding, 2),
            'holding_pcts': holding_pcts,
        }

    print("==========================================================================================")
    print(" EMPIRICAL STUDY: EVALUATING UNIVERSE EXPANSION UNDER 3.0X COMPACT ADAPTIVE STRATEGY")
    print("==========================================================================================")

    for p_name, (s_dt, e_dt) in periods.items():
        print(f"\n==========================================================================================")
        print(f" >>> 评估周期: {p_name} ({s_dt} ~ {e_dt})")
        print(f"==========================================================================================")
        for u_name, tokens in universes.items():
            res = simulate_universe(u_name, tokens, s_dt, e_dt, leverage=3.0)
            if res is None:
                continue
            res['period'] = p_name
            res['leverage'] = '3.0x'
            results.append(res)
            liq_str = "💥 爆仓" if res['liquidated'] else "✅ 安全"
            print(f"  [{u_name:24s}] 收益: {res['total_ret_pct']:+10.2f}% | 年化: {res['cagr_pct']:+7.2f}% | 回撤: {res['max_dd_pct']:6.2f}% | 夏普: {res['sharpe']:4.2f} | 卡玛: {res['calmar']:4.2f} | 交易: {res['trade_count']:3d}次 (止损{res['stop_count']:2d}) | 手续费: ${res['total_fees']:,.0f} | {liq_str}")

    # Also evaluate 1.0x Spot for full period
    print(f"\n==========================================================================================")
    print(f" >>> 1.0X 现货基准对比 (全周期 2020-2026)")
    print(f"==========================================================================================")
    s_dt, e_dt = periods['2020-2026 (全周期)']
    for u_name, tokens in universes.items():
        res = simulate_universe(u_name, tokens, s_dt, e_dt, leverage=1.0)
        res['period'] = '2020-2026 (全周期)'
        res['leverage'] = '1.0x'
        results.append(res)
        print(f"  [1.0x {u_name:20s}] 收益: {res['total_ret_pct']:+8.2f}% | 年化: {res['cagr_pct']:+6.2f}% | 回撤: {res['max_dd_pct']:6.2f}% | 夏普: {res['sharpe']:4.2f} | 卡玛: {res['calmar']:4.2f} | 交易: {res['trade_count']:3d}次")

    # Evaluate Recent Cycle (2023-05 to 2026-09) INCLUDING SUI!
    print(f"\n==========================================================================================")
    print(f" >>> 新一代 L1 (包含 SUI) 周期对比 (2023-05-04 ~ 2026-09-22)")
    print(f"==========================================================================================")
    recent_s_dt, recent_e_dt = '2023-05-04', '2026-09-22'
    recent_universes = {
        'Core-4 (Baseline)': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT'],
        'Top-6 (High-Beta L1)': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'AVAXUSDT', 'NEARUSDT'],
        'Top-7 (+SUI Next-Gen L1)': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'AVAXUSDT', 'NEARUSDT', 'SUIUSDT'],
        'Top-8 (+LINK+SUI)': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'AVAXUSDT', 'NEARUSDT', 'LINKUSDT', 'SUIUSDT'],
    }
    for u_name, tokens in recent_universes.items():
        res = simulate_universe(u_name, tokens, recent_s_dt, recent_e_dt, leverage=3.0)
        res['period'] = '2023-2026 (包含SUI周期)'
        res['leverage'] = '3.0x'
        results.append(res)
        print(f"  [3.0x {u_name:24s}] 收益: {res['total_ret_pct']:+10.2f}% | 年化: {res['cagr_pct']:+7.2f}% | 回撤: {res['max_dd_pct']:6.2f}% | 夏普: {res['sharpe']:4.2f} | 卡玛: {res['calmar']:4.2f} | 交易: {res['trade_count']:3d}次")

    os.makedirs('leverage_research', exist_ok=True)
    df_res = pd.DataFrame(results)
    df_res.to_csv('leverage_research/universe_expansion_comparison.csv', index=False)
    print("\n[SUCCESS] Completed Universe Expansion Study. Output saved to leverage_research/universe_expansion_comparison.csv")

if __name__ == '__main__':
    run_universe_study()
