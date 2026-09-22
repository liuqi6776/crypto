# -*- coding: utf-8 -*-
"""
Empirical Comparison: 1.0x Spot vs 3.0x Leverage vs 5.0x Leverage
Under Strict Realistic Slippage, Trading Fees, Borrow Costs, and Intrabar Liquidation
======================================================================================
Detailed side-by-side comparison across 1x, 3x, and 5x leverage:
1. Exact Nominal Fee Scaling: 8.0 bps * Leverage per leg.
2. Stop-Loss Slippage: 15.0 bps nominal slippage on stop-out execution.
3. Funding Rates (Binance 8h parquet) + Margin Borrow Interest (10% APR on (L-1)).
4. Exchange Liquidation Thresholds (MMR = 0.5%):
   - 1x: Liq Drop = -100.0% (Zero liquidation)
   - 3x: Liq Drop = -32.83%
   - 5x: Liq Drop = -19.50%
5. Intrabar low vs Liq Price and Stop-Loss Price.
6. Tests across:
   - 2020-2024 (5-Year Bull & Bear)
   - 2025 (Choppy Divergence)
   - 2026 (Blind Out-of-Sample Weak Market)
   - 2022 (Extreme Bear Stress Test)
   - 2020-2026 (Full 6-Year Cycle)
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

def run_comparison():
    tokens = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT']
    dfs = {t: pd.read_parquet(f'data/{t}_4h_2020_2026.parquet') for t in tokens}

    common_idx = dfs['BTCUSDT'].index
    for t in tokens:
        common_idx = common_idx.intersection(dfs[t].index)
    common_idx = common_idx.sort_values()

    closes = pd.DataFrame({t: dfs[t].loc[common_idx, 'close'] for t in tokens})
    opens = pd.DataFrame({t: dfs[t].loc[common_idx, 'open'] for t in tokens})
    highs = pd.DataFrame({t: dfs[t].loc[common_idx, 'high'] for t in tokens})
    lows = pd.DataFrame({t: dfs[t].loc[common_idx, 'low'] for t in tokens})

    # ATR (14 bars, 4h)
    atrs = {}
    for t in tokens:
        tr1 = highs[t] - lows[t]
        tr2 = (highs[t] - closes[t].shift(1)).abs()
        tr3 = (lows[t] - closes[t].shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atrs[t] = tr.rolling(14).mean()
    df_atrs = pd.DataFrame(atrs)

    # Funding rates & settlement bars
    df_funding = pd.read_parquet('data/binance_funding_8h.parquet')
    if df_funding.index.tz is not None:
        df_funding.index = df_funding.index.tz_localize(None)
    funding_aligned = df_funding.reindex(common_idx, method='ffill').fillna(0.0001)
    is_settlement_bar = pd.Series(common_idx.hour.isin([0, 8, 16]), index=common_idx)

    # Causal indicators
    closes_prior = closes.shift(1)
    ema200 = closes_prior.ewm(span=200).mean()
    bb_mid = closes_prior.rolling(120).mean()
    bb_std = closes_prior.rolling(120).std()
    bb_z = (closes_prior - bb_mid) / (bb_std + 1e-8)
    mom20 = (closes_prior / closes_prior.shift(120)) - 1.0
    score = bb_z + mom20
    btc_bull = closes_prior['BTCUSDT'] > ema200['BTCUSDT']

    def simulate(
        start_dt: str,
        end_dt: str,
        leverage: float,
        sl_mode: str = 'FIXED_5PCT', # 'FIXED_5PCT' or 'ATR_2X'
        fee_rate: float = 0.0008,    # 8.0 bps
        slippage: float = 0.0015,    # 15.0 bps
        hysteresis: float = 0.005,
        mmr: float = 0.005,
    ) -> Dict[str, Any]:
        mask = (common_idx >= start_dt) & (common_idx <= end_dt)
        sub_idx = common_idx[mask]
        if len(sub_idx) < 10:
            return None

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

        # Liquidation drop threshold: Entry * (1 - (1/L - MMR))
        liq_drop_pct = (1.0 / leverage - mmr) if leverage > 1.0 else 1.0

        for i, t in enumerate(sub_idx):
            if liquidated:
                equity_curve.append(0.0)
                continue

            settle = is_settlement_bar.loc[t]

            # 1. Intrabar position evaluation
            if curr_pos != 'USDT_CASH':
                bar_open = opens.loc[t, curr_pos]
                bar_high = highs.loc[t, curr_pos]
                bar_low = lows.loc[t, curr_pos]
                bar_close = closes.loc[t, curr_pos]

                highest_price = max(highest_price, bar_high)

                # A. Exchange Liquidation Check:
                liq_p = entry_price * (1.0 - liq_drop_pct)
                if leverage > 1.0 and bar_low <= liq_p:
                    liquidated = True
                    liquidation_date = str(t)
                    cap = 0.0
                    equity_curve.append(0.0)
                    trades.append({'ret': -1.0, 'type': 'LIQUIDATION'})
                    continue

                # B. Stop-Loss Trigger Check:
                if stop_price > 0 and bar_low <= stop_price:
                    stop_count += 1
                    # Execution with slippage
                    exec_exit = min(bar_open, stop_price * (1.0 - slippage))
                    asset_ret = (exec_exit - entry_price) / entry_price
                    lev_ret = asset_ret * leverage

                    # Turnover fee
                    close_fee = cap * leverage * fee_rate
                    total_fees += close_fee
                    # Slippage loss in USD
                    slip_cost = cap * leverage * slippage
                    total_slippage_cost += slip_cost

                    pnl = (cap * lev_ret) - close_fee
                    cap = max(0.0, cap + pnl)
                    trades.append({'ret': lev_ret, 'type': 'STOP_LOSS'})

                    curr_pos = 'USDT_CASH'
                    entry_price = 0.0
                    stop_price = 0.0
                    highest_price = 0.0
                    equity_curve.append(cap)
                    continue

                # C. Trailing Stop Update (Let Winners Run):
                # 1. Breakeven Stop: +5% gain -> entry * 1.002
                if highest_price >= entry_price * 1.05:
                    be_stop = entry_price * 1.002
                    stop_price = max(stop_price, be_stop)
                # 2. Trailing Lock: +10% gain -> trailing 5% below peak
                if highest_price >= entry_price * 1.10:
                    trail_stop = highest_price * 0.95
                    stop_price = max(stop_price, trail_stop)

                # D. Mark-to-Market & Funding Costs
                bar_ret = (bar_close - bar_open) / bar_open
                bar_pnl = cap * leverage * bar_ret

                funding_cost = 0.0
                if settle and leverage > 1.0:
                    fr = funding_aligned.loc[t, curr_pos] if curr_pos in funding_aligned else 0.0001
                    borrow_fee = (leverage - 1.0) * 0.0001 # 10% APR borrow interest
                    funding_cost = cap * ((leverage * fr) + borrow_fee)
                    total_funding += funding_cost

                cap = max(0.0, cap + bar_pnl - funding_cost)
                if cap <= 0.0:
                    liquidated = True
                    liquidation_date = str(t)
                    equity_curve.append(0.0)
                    continue

            # 2. 4h Rebalance & Macro Gate
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

            if target_pos != curr_pos:
                # Close previous
                if curr_pos != 'USDT_CASH':
                    signal_exit_count += 1
                    exit_p = opens.loc[t, curr_pos]
                    asset_ret = (exit_p - entry_price) / entry_price
                    lev_ret = asset_ret * leverage
                    close_fee = cap * leverage * fee_rate
                    total_fees += close_fee
                    cap = max(0.0, cap + (cap * lev_ret) - close_fee)
                    trades.append({'ret': lev_ret, 'type': 'SIGNAL_EXIT'})
                    curr_pos = 'USDT_CASH'

                # Open target
                if target_pos != 'USDT_CASH' and cap > 0:
                    curr_pos = target_pos
                    entry_price = opens.loc[t, target_pos]
                    highest_price = entry_price

                    gate_p = ema200.loc[t, target_pos] * (1.0 - hysteresis)
                    if sl_mode == 'FIXED_5PCT':
                        stop_price = max(gate_p, entry_price * 0.95)
                    else: # ATR_2X
                        atr_val = df_atrs.loc[t, target_pos]
                        stop_price = max(gate_p, entry_price - (atr_val * 2.0))

                    open_fee = cap * leverage * fee_rate
                    total_fees += open_fee
                    cap -= open_fee

            equity_curve.append(cap)

        eq_s = pd.Series(equity_curve, index=sub_idx)
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

        return {
            'leverage': leverage,
            'sl_mode': sl_mode,
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
            'liquidation_date': liquidation_date,
            'total_fees': round(total_fees, 2),
            'total_slippage_cost': round(total_slippage_cost, 2),
            'total_funding': round(total_funding, 2),
        }

    periods = {
        '2020-2024 (训练牛熊期)': ('2020-01-01', '2024-12-31'),
        '2025 (分化震荡期)': ('2025-01-01', '2025-12-31'),
        '2026 (盲测弱势期)': ('2026-01-01', '2026-09-20'),
        '2022 (极端熊市测试)': ('2022-01-01', '2022-12-31'),
        '2020-2026 (全周期)': ('2020-01-01', '2026-09-20'),
    }

    # Evaluate for both Mode A (Fixed 5% + Trailing) and Mode B (ATR 2x + Trailing)
    results_list = []

    for mode_name, sl_key in [('让利润奔跑 (SL 5% + 移动追踪)', 'FIXED_5PCT'), ('波动自适应 (SL 2.0x ATR + 移动追踪)', 'ATR_2X')]:
        print(f"\n==========================================================================================")
        print(f" 策略模式: {mode_name}")
        print(f"==========================================================================================")
        for p_name, (s_dt, e_dt) in periods.items():
            print(f"\n --- 评估周期: {p_name} ---")
            for lev in [1.0, 3.0, 5.0]:
                res = simulate(s_dt, e_dt, leverage=lev, sl_mode=sl_key)
                results_list.append({
                    'Strategy Mode': mode_name,
                    'Period': p_name,
                    'Leverage': f'{lev:.1f}x',
                    **res
                })
                liq_str = f"💥 爆仓清零 ({res['liquidation_date']})" if res['liquidated'] else "✅ 安全存活"
                print(f"  [{lev:.1f}x 杠杆] 收益: {res['total_ret_pct']:+13.2f}% | 年化: {res['cagr_pct']:+8.2f}% | 回撤: {res['max_dd_pct']:6.2f}% | 夏普: {res['sharpe']:4.2f} | 止损: {res['stop_count']}次 | 手续费: ${res['total_fees']:,.0f} | 状态: {liq_str}")

    df_out = pd.DataFrame(results_list)
    df_out.to_csv('leverage_research/compare_1x_3x_5x_summary.csv', index=False)
    print("\n[SUCCESS] Comparison complete. Saved to leverage_research/compare_1x_3x_5x_summary.csv")

if __name__ == '__main__':
    run_comparison()
