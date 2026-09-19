# -*- coding: utf-8 -*-
"""
Empirical Comparison: Option A (Pure Systematic) vs Option B (Partial Take-Profit & Breakeven)
=============================================================================================
Calculates both:
1. Linear Discrete Metrics (Fixed $10,000 Margin per trade - Win Rate, Profit Factor, Net PnL)
2. Compounded Continuous Metrics (Total Return %, Max Drawdown %, Daily Sharpe, Calmar)
"""

import sys
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd

# Enforce UTF-8 for console output
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def run_trade_simulation(
    df: pd.DataFrame,
    leverage: float = 3.0,
    lookback_bars: int = 120,
    exit_lookback_bars: int = 60,
    atr_period: int = 14,
    atr_trailing_mult: float = 3.0,
    fee_and_slippage: float = 0.0008,
    tp_pct: float = 0.0,       # 0.0 means Option A (No TP)
    tp_ratio: float = 0.0,     # Fraction of position to close at TP (e.g. 0.333 or 0.5)
    move_stop_to_be: bool = False,
    min_warmup_bars: int = 120,
    base_margin_usdt: float = 10000.0,
) -> Dict[str, Any]:
    n = len(df)
    opens = df['open'].values
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    idx = df.index

    # 1. Causal Indicators
    tr1 = highs - lows
    tr2 = np.abs(highs - np.roll(closes, 1))
    tr3 = np.abs(lows - np.roll(closes, 1))
    tr = np.maximum(tr1, np.maximum(tr2, tr3))
    tr[0] = tr1[0]
    atr = pd.Series(tr, index=idx).rolling(atr_period, min_periods=1).mean().values

    bb_mid = pd.Series(closes, index=idx).shift(1).rolling(lookback_bars).mean().values
    bb_std = pd.Series(closes, index=idx).shift(1).rolling(lookback_bars).std().values
    bb_upper = bb_mid + 2.0 * bb_std
    swing_low = pd.Series(lows, index=idx).shift(1).rolling(30).min().values
    ema200 = pd.Series(closes, index=idx).shift(1).ewm(span=200).mean().values

    active_pos = np.zeros(n)
    in_pos = False
    entry_idx = 0
    entry_price = 0.0
    current_size = 0.0
    peak_price = 0.0
    trailing_stop = 0.0
    tp_triggered = False

    trades: List[Dict[str, Any]] = []

    for i in range(1, n - 1):
        if i < min_warmup_bars:
            continue

        curr_c = closes[i]
        curr_h = highs[i]
        curr_l = lows[i]
        curr_atr = atr[i]
        if np.isnan(curr_atr) or np.isnan(bb_upper[i]):
            continue

        if not in_pos:
            if curr_c > bb_upper[i] and curr_c > ema200[i]:
                in_pos = True
                entry_idx = i + 1
                entry_price = opens[entry_idx]
                current_size = leverage
                peak_price = curr_h
                trailing_stop = max(swing_low[i], curr_c - atr_trailing_mult * curr_atr)
                tp_triggered = False
        else:
            peak_price = max(peak_price, curr_h)
            new_stop_cand = peak_price - atr_trailing_mult * curr_atr
            trailing_stop = max(trailing_stop, new_stop_cand)

            # Check Partial TP
            if tp_pct > 0.0 and not tp_triggered:
                tp_target = entry_price * (1.0 + tp_pct)
                if curr_h >= tp_target:
                    tp_triggered = True
                    current_size -= (leverage * tp_ratio)
                    if move_stop_to_be:
                        trailing_stop = max(trailing_stop, entry_price)

            exit_signal = False
            exit_reason = ""
            if curr_c < trailing_stop:
                exit_signal = True
                exit_reason = "TRAILING_STOP"
            elif curr_c < bb_mid[i]:
                exit_signal = True
                exit_reason = "BB_MID"
            elif curr_c < ema200[i]:
                exit_signal = True
                exit_reason = "EMA200"

            if exit_signal:
                exit_idx = i + 1
                exit_price = opens[exit_idx]

                # Calculate trade PnL on base margin
                # If TP was triggered: portion closed at tp_target, remaining portion closed at exit_price
                if tp_triggered:
                    portion_tp = tp_ratio
                    portion_rem = 1.0 - tp_ratio
                    ret_tp = tp_pct * leverage * portion_tp - (2 * fee_and_slippage * leverage * portion_tp)
                    ret_rem = ((exit_price / entry_price) - 1.0) * leverage * portion_rem - (2 * fee_and_slippage * leverage * portion_rem)
                    trade_net_roe = ret_tp + ret_rem
                else:
                    gross_price_ret = (exit_price / entry_price) - 1.0
                    trade_net_roe = gross_price_ret * leverage - (2 * fee_and_slippage * leverage)

                trade_pnl_usdt = base_margin_usdt * trade_net_roe

                trades.append({
                    'entry_time': idx[entry_idx],
                    'entry_price': entry_price,
                    'exit_time': idx[exit_idx],
                    'exit_price': exit_price,
                    'tp_triggered': tp_triggered,
                    'trade_net_roe_pct': trade_net_roe * 100.0,
                    'trade_pnl_usdt': trade_pnl_usdt,
                    'duration_days': (exit_idx - entry_idx) * 4.0 / 24.0,
                    'exit_reason': exit_reason,
                })

                in_pos = False
                current_size = 0.0

        active_pos[i] = current_size

    # Continuous compounding MTM
    open_to_open_rets = np.zeros(n)
    open_to_open_rets[:-1] = opens[1:] / (opens[:-1] + 1e-8) - 1.0
    turnover = np.abs(active_pos - np.roll(active_pos, 1))
    turnover[0] = np.abs(active_pos[0])

    bar_rets = active_pos * open_to_open_rets - turnover * fee_and_slippage
    equity_curve = np.cumprod(1.0 + np.clip(bar_rets, -0.99, 10.0))
    equity_series = pd.Series(equity_curve, index=idx)

    daily_equity = equity_series.resample('1D').last().dropna()
    daily_rets = daily_equity.pct_change().dropna()
    daily_sharpe = float((daily_rets.mean() / (daily_rets.std() + 1e-8)) * np.sqrt(365))

    running_max = np.maximum.accumulate(equity_curve)
    drawdowns = (equity_curve - running_max) / running_max
    max_dd = float(np.min(drawdowns) * 100.0)

    # Trade-level discrete statistics
    total_trades = len(trades)
    win_trades = [t for t in trades if t['trade_pnl_usdt'] > 0]
    loss_trades = [t for t in trades if t['trade_pnl_usdt'] <= 0]
    win_rate = (len(win_trades) / total_trades * 100.0) if total_trades else 0.0

    sum_pnl_usdt = sum(t['trade_pnl_usdt'] for t in trades)
    sum_gains = sum(t['trade_pnl_usdt'] for t in win_trades)
    sum_losses = abs(sum(t['trade_pnl_usdt'] for t in loss_trades)) + 1e-8
    profit_factor = sum_gains / sum_losses

    avg_trade_roe = np.mean([t['trade_net_roe_pct'] for t in trades]) if trades else 0.0
    max_win_roe = max([t['trade_net_roe_pct'] for t in trades]) if trades else 0.0
    max_loss_roe = min([t['trade_net_roe_pct'] for t in trades]) if trades else 0.0
    tp_hit_count = sum(1 for t in trades if t['tp_triggered'])

    return {
        'total_trades': total_trades,
        'win_rate': round(win_rate, 1),
        'profit_factor': round(profit_factor, 2),
        'sum_pnl_usdt': round(sum_pnl_usdt, 2),
        'avg_trade_roe': round(avg_trade_roe, 2),
        'max_win_roe': round(max_win_roe, 1),
        'max_loss_roe': round(max_loss_roe, 1),
        'tp_hit_count': tp_hit_count,
        'daily_sharpe': round(daily_sharpe, 2),
        'max_dd': round(max_dd, 1),
    }


def main():
    df_raw = pd.read_parquet('data/ETHUSDT_4h_2020_2026.parquet')

    periods = {
        "2024–2026 样本外验证 (2.7年)": ("2024-01-01", "2026-09-01"),
        "2021–2026 全周期跨牛熊 (5.7年)": ("2021-01-01", "2026-09-01"),
        "2026 年事后压力测试 (阴跌震荡)": ("2026-01-01", "2026-09-01"),
    }

    configs = {
        "方案 A: 纯量化大波段 (无止盈, 3 ATR 移动止损)": {
            "tp_pct": 0.0, "tp_ratio": 0.0, "move_stop_to_be": False
        },
        "方案 B1: +6.5%止盈 1/3 (+19.5% ROE), 保本锁定": {
            "tp_pct": 0.065, "tp_ratio": 0.333, "move_stop_to_be": True
        },
        "方案 B2: +6.5%止盈 1/2 (+19.5% ROE), 保本锁定": {
            "tp_pct": 0.065, "tp_ratio": 0.500, "move_stop_to_be": True
        },
        "方案 B3: +10.0%止盈 1/3 (+30.0% ROE), 保本锁定": {
            "tp_pct": 0.100, "tp_ratio": 0.333, "move_stop_to_be": True
        },
        "方案 B4: +10.0%止盈 1/2 (+30.0% ROE), 保本锁定": {
            "tp_pct": 0.100, "tp_ratio": 0.500, "move_stop_to_be": True
        },
    }

    print("=" * 118)
    print(" ETHUSDT 3x 杠杆: 方案 A (纯移动止盈) vs 方案 B (分批止盈+保本锁定) 严谨量化实测对比")
    print(" (每笔固定 $10,000 USDT 本金 / 扣除 8 bps 手续费与滑点 / 严格 Open-to-Open 成交)")
    print("=" * 118)

    for p_name, (start_dt, end_dt) in periods.items():
        print(f"\n>>> 测试区间: {p_name} [{start_dt} 至 {end_dt}]")
        print("-" * 118)
        print(f"{'配置方案':<46} | {'总盈亏(1万本)':<14} | {'胜率':<7} | {'盈亏比':<7} | {'单笔均利':<9} | {'最大盈利':<8} | {'最大亏损':<8} | {'触发止盈'}")
        print("-" * 118)

        start_idx = pd.to_datetime(start_dt) - pd.Timedelta(days=50)
        df_slice = df_raw.loc[start_idx:end_dt].copy()

        for c_name, c_params in configs.items():
            res = run_trade_simulation(
                df_slice,
                leverage=3.0,
                tp_pct=c_params["tp_pct"],
                tp_ratio=c_params["tp_ratio"],
                move_stop_to_be=c_params["move_stop_to_be"],
                min_warmup_bars=120,
                base_margin_usdt=10000.0,
            )
            tp_info = f"{res['tp_hit_count']}/{res['total_trades']} 笔" if c_params["tp_pct"] > 0 else "N/A"
            print(f"{c_name:<46} | {res['sum_pnl_usdt']:>+11,.0f} $ | {res['win_rate']:>5.1f}% | {res['profit_factor']:>7.2f} | {res['avg_trade_roe']:>+7.2f}% | {res['max_win_roe']:>+6.1f}% | {res['max_loss_roe']:>6.1f}% | {tp_info}")
        print("-" * 118)


if __name__ == "__main__":
    main()
