# -*- coding: utf-8 -*-
"""
Empirical Backtest: 3.0x Leverage Across Different SL & TP Regimes
===================================================================
Investigates: "如果是 3 倍杠杆呢？"
Compares under 3.0x Leverage:
1. Fixed SL 5% + Fixed TP 10% (Baseline)
2. Fixed SL 3% + Fixed TP 8% (Tight Scalp)
3. Fixed SL 8% + Fixed TP 20% (Wide Band)
4. Fixed SL 5% + Trailing Stop (Let Winners Run)
5. Volatility Adaptive: SL 2.0x ATR + Trailing Stop (Let Winners Run)
6. Volatility Adaptive: SL 1.5x ATR + Trailing Stop
7. Pure Structural EMA200 Gate (No % SL, Exit on Trend Invalidation)
8. 1.0x Spot Baseline (for comparison)

Evaluates:
- Liquidation Risk (Liq Drop = -32.83% from entry)
- Compounded Return (%)
- CAGR (%)
- Max Drawdown (%)
- Sharpe & Calmar
- Fee & Funding Drag
Across 2020-2024, 2025, 2026, 2022 Bear Stress, and 2020-2026 Full Cycle.
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

def run_3x_sweep():
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

    # Indicators strictly shift(1)
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
        sl_mode: str,
        sl_val: float,
        tp_mode: str,
        tp_val: float,
        fee_rate: float = 0.0008,
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
        tp_price = 0.0

        equity_curve = []
        trades = []
        liquidated = False
        liquidation_date = None
        stop_count = 0
        tp_count = 0
        signal_exit_count = 0
        total_fees = 0.0
        total_funding = 0.0

        # Liquidation drop threshold: Entry * (1 - (1/L - MMR))
        liq_drop_pct = (1.0 / leverage - mmr) if leverage > 1.0 else 1.0

        for i, t in enumerate(sub_idx):
            if liquidated:
                equity_curve.append(0.0)
                continue

            settle = is_settlement_bar.loc[t]

            # 1. INTRABAR POSITION RISK & STOPS
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
                    trades.append({'ret': -1.0, 'type': 'LIQ'})
                    continue

                # B. Stop-Loss Trigger Check:
                if stop_price > 0 and bar_low <= stop_price:
                    stop_count += 1
                    exec_exit = min(bar_open, stop_price * 0.9985)
                    asset_ret = (exec_exit - entry_price) / entry_price
                    lev_ret = asset_ret * leverage
                    close_fee = cap * leverage * fee_rate
                    total_fees += close_fee
                    pnl = (cap * lev_ret) - close_fee
                    cap = max(0.0, cap + pnl)
                    trades.append({'ret': lev_ret, 'type': 'SL'})

                    curr_pos = 'USDT_CASH'
                    entry_price = 0.0
                    stop_price = 0.0
                    tp_price = 0.0
                    highest_price = 0.0
                    equity_curve.append(cap)
                    continue

                # C. Take-Profit Trigger Check:
                if tp_price > 0 and bar_high >= tp_price:
                    tp_count += 1
                    exec_exit = max(bar_open, tp_price * 0.999)
                    asset_ret = (exec_exit - entry_price) / entry_price
                    lev_ret = asset_ret * leverage
                    close_fee = cap * leverage * fee_rate
                    total_fees += close_fee
                    pnl = (cap * lev_ret) - close_fee
                    cap = max(0.0, cap + pnl)
                    trades.append({'ret': lev_ret, 'type': 'TP'})

                    curr_pos = 'USDT_CASH'
                    entry_price = 0.0
                    stop_price = 0.0
                    tp_price = 0.0
                    highest_price = 0.0
                    equity_curve.append(cap)
                    continue

                # D. Trailing Stop Update (Let Winners Run):
                if tp_mode == 'TRAILING_ONLY':
                    # Breakeven stop: +5% gain -> stop moves to entry * 1.002
                    if highest_price >= entry_price * 1.05:
                        be_stop = entry_price * 1.002
                        stop_price = max(stop_price, be_stop)
                    # Trailing lock: +10% gain -> trailing 5% from peak
                    if highest_price >= entry_price * 1.10:
                        trail_stop = highest_price * 0.95
                        stop_price = max(stop_price, trail_stop)

                # E. Bar Return & Funding Fee
                bar_ret = (bar_close - bar_open) / bar_open
                bar_pnl = cap * leverage * bar_ret

                funding_cost = 0.0
                if settle and leverage > 1.0:
                    fr = funding_aligned.loc[t, curr_pos] if curr_pos in funding_aligned else 0.0001
                    borrow_fee = (leverage - 1.0) * 0.0001 # ~10% APR borrow interest
                    funding_cost = cap * ((leverage * fr) + borrow_fee)
                    total_funding += funding_cost

                cap = max(0.0, cap + bar_pnl - funding_cost)
                if cap <= 0.0:
                    liquidated = True
                    liquidation_date = str(t)
                    equity_curve.append(0.0)
                    continue

            # 2. 4h REBALANCE & DUAL MACRO GATE
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
                    trades.append({'ret': lev_ret, 'type': 'SIGNAL'})
                    curr_pos = 'USDT_CASH'

                # Open target
                if target_pos != 'USDT_CASH' and cap > 0:
                    curr_pos = target_pos
                    entry_price = opens.loc[t, target_pos]
                    highest_price = entry_price

                    atr_val = df_atrs.loc[t, target_pos]
                    gate_p = ema200.loc[t, target_pos] * (1.0 - hysteresis)

                    if sl_mode == 'FIXED_PCT':
                        stop_price = max(gate_p, entry_price * (1.0 - sl_val))
                    elif sl_mode == 'ATR_MULT':
                        atr_stop = entry_price - (atr_val * sl_val)
                        stop_price = max(gate_p, atr_stop)
                    elif sl_mode == 'EMA_GATE_ONLY':
                        stop_price = gate_p
                    else:
                        stop_price = 0.0

                    if tp_mode == 'FIXED_PCT':
                        tp_price = entry_price * (1.0 + tp_val)
                    elif tp_mode == 'ATR_MULT':
                        tp_price = entry_price + (atr_val * tp_val)
                    else:
                        tp_price = 0.0 # Trailing only

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

        return {
            'final_equity': round(final_equity, 2),
            'total_ret_pct': round(total_ret_pct, 2),
            'cagr_pct': round(cagr_pct, 2),
            'max_dd_pct': round(max_dd_pct, 2),
            'sharpe': round(sharpe, 2),
            'calmar': round(calmar, 2),
            'liquidated': liquidated,
            'liquidation_date': liquidation_date,
            'stop_count': stop_count,
            'tp_count': tp_count,
            'signal_exit_count': signal_exit_count,
            'total_fees': round(total_fees, 2),
            'total_funding': round(total_funding, 2),
        }

    configs_3x = [
        # Label, Lev, SL_mode, SL_val, TP_mode, TP_val
        ('1.0x 现货基准 (SL 5% + Trailing)', 1.0, 'FIXED_PCT', 0.05, 'TRAILING_ONLY', 0.0),
        ('3.0x 杠杆: 固定 SL 5% + 固定 TP 10%', 3.0, 'FIXED_PCT', 0.05, 'FIXED_PCT', 0.10),
        ('3.0x 杠杆: 紧止损 SL 3% + 固定 TP 8%', 3.0, 'FIXED_PCT', 0.03, 'FIXED_PCT', 0.08),
        ('3.0x 杠杆: 宽波段 SL 8% + 固定 TP 20%', 3.0, 'FIXED_PCT', 0.08, 'FIXED_PCT', 0.20),
        ('3.0x 杠杆: 让利润奔跑 (SL 5% + Trailing)', 3.0, 'FIXED_PCT', 0.05, 'TRAILING_ONLY', 0.0),
        ('3.0x 杠杆: 波动自适应 (SL 2.0x ATR + Trailing)', 3.0, 'ATR_MULT', 2.0, 'TRAILING_ONLY', 0.0),
        ('3.0x 杠杆: 紧凑自适应 (SL 1.5x ATR + Trailing)', 3.0, 'ATR_MULT', 1.5, 'TRAILING_ONLY', 0.0),
        ('3.0x 杠杆: 纯趋势结构门控 (EMA200 Gate)', 3.0, 'EMA_GATE_ONLY', 0.0, 'TRAILING_ONLY', 0.0),
    ]

    periods = {
        '2020-2024 (训练牛熊期)': ('2020-01-01', '2024-12-31'),
        '2025 (分化震荡期)': ('2025-01-01', '2025-12-31'),
        '2026 (盲测弱势期)': ('2026-01-01', '2026-09-20'),
        '2022 (极端熊市测试)': ('2022-01-01', '2022-12-31'),
        '2020-2026 (全周期)': ('2020-01-01', '2026-09-20'),
    }

    all_res = []

    for p_name, (s_dt, e_dt) in periods.items():
        print(f"\n==========================================================================================")
        print(f" 评估周期: {p_name} ({s_dt} ~ {e_dt})")
        print(f"==========================================================================================")
        for label, lev, sl_m, sl_v, tp_m, tp_v in configs_3x:
            r = simulate(s_dt, e_dt, leverage=lev, sl_mode=sl_m, sl_val=sl_v, tp_mode=tp_m, tp_val=tp_v)
            all_res.append({'Period': p_name, 'Config': label, 'Leverage': lev, **r})
            liq_tag = f"💥 爆仓 ({r['liquidation_date']})" if r['liquidated'] else "✅ 安全"
            print(f"  [{label:45s}] 收益: {r['total_ret_pct']:+13.2f}% | 年化: {r['cagr_pct']:+9.2f}% | 回撤: {r['max_dd_pct']:6.2f}% | 夏普: {r['sharpe']:4.2f} | 止损: {r['stop_count']}次 | 止盈: {r['tp_count']}次 | 状态: {liq_tag}")

    df_out = pd.DataFrame(all_res)
    df_out.to_csv('leverage_research/backtest_3x_leverage_summary.csv', index=False)
    print("\n[SUCCESS] 3X Sweep complete. Saved to leverage_research/backtest_3x_leverage_summary.csv")

if __name__ == '__main__':
    run_3x_sweep()
