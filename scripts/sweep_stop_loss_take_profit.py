# -*- coding: utf-8 -*-
"""
Empirical Parameter Sweep: Stop-Loss & Take-Profit Optimization & Dynamic Prediction
====================================================================================
Investigates:
1. Why were 5% SL and 10% TP initially chosen? (Baseline heuristic).
2. What happens across a parameter grid of Stop-Loss (2% to 10%) and Take-Profit (5% to 30%, or No TP)?
3. How does Volatility-Adaptive (ATR-based) dynamic stop/TP perform vs Fixed %?
4. What is the danger of overfitting to the "highest historical return"?
5. Evaluates 2020-2024 (In-Sample), 2025 (Validation), 2026 (Blind Test), and Full Cycle.
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

def run_sl_tp_sweep():
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

    # ATR (14 bars, 4h)
    atrs = {}
    for t in tokens:
        tr1 = highs[t] - lows[t]
        tr2 = (highs[t] - closes[t].shift(1)).abs()
        tr3 = (lows[t] - closes[t].shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atrs[t] = tr.rolling(14).mean()
    df_atrs = pd.DataFrame(atrs)

    # Causal Indicators: Strictly shift(1)
    closes_prior = closes.shift(1)
    ema200 = closes_prior.ewm(span=200).mean()
    bb_mid = closes_prior.rolling(120).mean()
    bb_std = closes_prior.rolling(120).std()
    bb_z = (closes_prior - bb_mid) / (bb_std + 1e-8)
    mom20 = (closes_prior / closes_prior.shift(120)) - 1.0
    score = bb_z + mom20

    # BTC Macro Trend Gate
    btc_bull = closes_prior['BTCUSDT'] > ema200['BTCUSDT']

    def simulate_strategy(
        start_dt: str,
        end_dt: str,
        sl_mode: str, # 'FIXED_PCT', 'ATR_MULT', 'EMA_GATE_ONLY', 'NONE'
        sl_val: float, # e.g. 0.05 (5%) or 2.0 (2x ATR)
        tp_mode: str, # 'FIXED_PCT', 'ATR_MULT', 'TRAILING_ONLY', 'NONE'
        tp_val: float, # e.g. 0.10 (10%) or 4.0 (4x ATR)
        fee_rate: float = 0.0008,
        hysteresis: float = 0.005,
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
        tp_target_price = 0.0

        equity_curve = []
        trades = []
        stop_count = 0
        tp_count = 0
        signal_exit_count = 0

        for i, t in enumerate(sub_idx):
            # 1. Intrabar Stop & TP checks
            if curr_pos != 'USDT_CASH':
                bar_open = opens.loc[t, curr_pos]
                bar_high = highs.loc[t, curr_pos]
                bar_low = lows.loc[t, curr_pos]
                bar_close = closes.loc[t, curr_pos]

                highest_price = max(highest_price, bar_high)

                # Check Stop Loss
                if stop_price > 0 and bar_low <= stop_price:
                    stop_count += 1
                    exec_exit = min(bar_open, stop_price * 0.9985) # slippage
                    ret = (exec_exit - entry_price) / entry_price
                    fee = cap * fee_rate
                    cap = max(0.0, cap * (1.0 + ret) - fee)
                    trades.append({'ret': ret, 'type': 'SL'})
                    curr_pos = 'USDT_CASH'
                    entry_price = 0.0
                    stop_price = 0.0
                    tp_target_price = 0.0
                    equity_curve.append(cap)
                    continue

                # Check Take Profit
                if tp_target_price > 0 and bar_high >= tp_target_price:
                    tp_count += 1
                    exec_exit = max(bar_open, tp_target_price * 0.999) # slippage
                    ret = (exec_exit - entry_price) / entry_price
                    fee = cap * fee_rate
                    cap = max(0.0, cap * (1.0 + ret) - fee)
                    trades.append({'ret': ret, 'type': 'TP'})
                    curr_pos = 'USDT_CASH'
                    entry_price = 0.0
                    stop_price = 0.0
                    tp_target_price = 0.0
                    equity_curve.append(cap)
                    continue

                # Update Trailing Stop if in trailing mode
                if tp_mode == 'TRAILING_ONLY' or tp_mode == 'HYBRID_TRAILING':
                    if highest_price >= entry_price * 1.05:
                        be_stop = entry_price * 1.002
                        stop_price = max(stop_price, be_stop)
                    if highest_price >= entry_price * 1.10:
                        trail_stop = highest_price * 0.95
                        stop_price = max(stop_price, trail_stop)

                # Asset bar return
                bar_ret = (bar_close - bar_open) / bar_open
                cap = max(0.0, cap * (1.0 + bar_ret))

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
                    ret = (exit_p - entry_price) / entry_price
                    fee = cap * fee_rate
                    cap = max(0.0, cap * (1.0 + ret) - fee)
                    trades.append({'ret': ret, 'type': 'SIGNAL'})
                    curr_pos = 'USDT_CASH'

                # Open target
                if target_pos != 'USDT_CASH' and cap > 0:
                    curr_pos = target_pos
                    entry_price = opens.loc[t, target_pos]
                    highest_price = entry_price

                    # Determine Stop Loss Price
                    atr_val = df_atrs.loc[t, target_pos]
                    gate_p = ema200.loc[t, target_pos] * (1.0 - hysteresis)

                    if sl_mode == 'FIXED_PCT':
                        stop_price = max(gate_p, entry_price * (1.0 - sl_val))
                    elif sl_mode == 'ATR_MULT':
                        atr_stop = entry_price - (atr_val * sl_val)
                        stop_price = max(gate_p, atr_stop)
                    elif sl_mode == 'EMA_GATE_ONLY':
                        stop_price = gate_p
                    else: # NONE
                        stop_price = 0.0

                    # Determine Take Profit Price
                    if tp_mode == 'FIXED_PCT':
                        tp_target_price = entry_price * (1.0 + tp_val)
                    elif tp_mode == 'ATR_MULT':
                        tp_target_price = entry_price + (atr_val * tp_val)
                    else:
                        tp_target_price = 0.0 # pure trailing or signal exit

                    # Open fee
                    cap -= cap * fee_rate

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
            'final_equity': round(final_equity, 2),
            'total_ret_pct': round(total_ret_pct, 2),
            'cagr_pct': round(cagr_pct, 2),
            'max_dd_pct': round(max_dd_pct, 2),
            'sharpe': round(sharpe, 2),
            'calmar': round(calmar, 2),
            'trade_count': len(trades),
            'stop_count': stop_count,
            'tp_count': tp_count,
            'signal_exit_count': signal_exit_count,
            'win_rate': round(win_rate, 2),
        }

    # Define Configurations to Test:
    configs = [
        # 1. Baseline Heuristic
        ('基准固定型: SL 5% + TP 10% (当前基准)', 'FIXED_PCT', 0.05, 'FIXED_PCT', 0.10),
        
        # 2. Grid of Fixed Stops
        ('紧止损高频: SL 3% + TP 8%', 'FIXED_PCT', 0.03, 'FIXED_PCT', 0.08),
        ('宽止损长波段: SL 8% + TP 20%', 'FIXED_PCT', 0.08, 'FIXED_PCT', 0.20),
        ('超宽止损: SL 12% + TP 30%', 'FIXED_PCT', 0.12, 'FIXED_PCT', 0.30),
        
        # 3. Only Stop Loss + Let Winners Run (No Fixed TP / Trailing Stop)
        ('让利润奔跑: SL 5% + 无固定TP (移动追踪止盈)', 'FIXED_PCT', 0.05, 'TRAILING_ONLY', 0.0),
        ('让利润奔跑: SL 8% + 无固定TP (移动追踪止盈)', 'FIXED_PCT', 0.08, 'TRAILING_ONLY', 0.0),
        
        # 4. Volatility-Adaptive (ATR-based dynamic prediction)
        ('波动率自适应: SL 1.5x ATR + TP 3.0x ATR', 'ATR_MULT', 1.5, 'ATR_MULT', 3.0),
        ('波动率自适应: SL 2.0x ATR + TP 4.0x ATR', 'ATR_MULT', 2.0, 'ATR_MULT', 4.0),
        ('波动率自适应: SL 2.0x ATR + 无固定TP (移动追踪)', 'ATR_MULT', 2.0, 'TRAILING_ONLY', 0.0),

        # 5. Pure Structural Stop (Gate only, no artificial % stop)
        ('纯结构门控: 仅EMA200门控止损 + 纯趋势离场', 'EMA_GATE_ONLY', 0.0, 'NONE', 0.0),
        ('无任何止损止盈: 纯信号翻转离场', 'NONE', 0.0, 'NONE', 0.0),
    ]

    periods = {
        '2020-2024 (训练样本内)': ('2020-01-01', '2024-12-31'),
        '2025 (验证分化期)': ('2025-01-01', '2025-12-31'),
        '2026 (样本外盲测期)': ('2026-01-01', '2026-09-20'),
        '2020-2026 (全周期)': ('2020-01-01', '2026-09-20'),
    }

    all_records = []

    for p_name, (s_dt, e_dt) in periods.items():
        print(f"\n==========================================================================================")
        print(f" 评估周期: {p_name} ({s_dt} ~ {e_dt})")
        print(f"==========================================================================================")
        for name, sl_m, sl_v, tp_m, tp_v in configs:
            res = simulate_strategy(s_dt, e_dt, sl_m, sl_v, tp_m, tp_v)
            all_records.append({
                'Period': p_name,
                'Config': name,
                'SL Mode': sl_m,
                'SL Val': sl_v,
                'TP Mode': tp_m,
                'TP Val': tp_v,
                **res
            })
            print(f"  [{name:42s}] 收益: {res['total_ret_pct']:+11.2f}% | 年化: {res['cagr_pct']:+8.2f}% | 最大回撤: {res['max_dd_pct']:6.2f}% | 夏普: {res['sharpe']:4.2f} | 止损: {res['stop_count']}次 | 止盈: {res['tp_count']}次")

    df_out = pd.DataFrame(all_records)
    df_out.to_csv('leverage_research/sl_tp_sweep_results.csv', index=False)
    print("\n[SUCCESS] Sweep finished. Results saved to leverage_research/sl_tp_sweep_results.csv")

if __name__ == '__main__':
    run_sl_tp_sweep()
