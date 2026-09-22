# -*- coding: utf-8 -*-
"""
Empirical Backtest: Leverage Recommendations (1x, 2x, 3x, 4x, 5x & Dynamic Safe Leverage)
With Strict Dynamic Stop-Loss (Hard Stop, Breakeven Stop, Trailing Lock, TP1/TP2)
====================================================================================
Evaluates whether high leverage (3X, 5X) can safely generate excess returns without liquidation.
Tests:
1. Intrabar low vs Stop-Loss Price (Stop-Loss Execution with realistic slippage).
2. Intrabar low vs Exchange Liquidation Price (MMR = 0.5%).
3. Nominal fee scaling: 8.0 bps * Leverage per trade leg.
4. Funding rates + borrow interest paid over time.
5. Regimes: 2020-2024, 2025, 2026, 2022 Bear Stress, and 2020-2026 Full Cycle.
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

def run_backtest():
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

    # ATR (14 bars, 4h) for volatility measurement
    atrs = {}
    for t in tokens:
        tr1 = highs[t] - lows[t]
        tr2 = (highs[t] - closes[t].shift(1)).abs()
        tr3 = (lows[t] - closes[t].shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atrs[t] = tr.rolling(14).mean()
    df_atrs = pd.DataFrame(atrs)

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

    # BTC Macro Trend Gate
    btc_bull = closes_prior['BTCUSDT'] > ema200['BTCUSDT']

    def simulate_run(
        start_dt: str,
        end_dt: str,
        leverage_mode: str, # '1.0x', '2.0x', '3.0x', '4.0x', '5.0x', 'DYNAMIC_SAFE'
        fixed_leverage: float = 1.0,
        fee_rate: float = 0.0008,
        hysteresis: float = 0.005,
        mmr: float = 0.005,
        stop_slippage: float = 0.0015, # 15 bps slippage when stop triggers
    ) -> Dict[str, Any]:
        mask = (common_idx >= start_dt) & (common_idx <= end_dt)
        sub_idx = common_idx[mask]
        if len(sub_idx) < 10:
            return None

        cap = 10000.0
        curr_pos = 'USDT_CASH'
        entry_price = 0.0
        highest_price = 0.0
        stop_loss_price = 0.0
        active_leverage = 1.0

        equity_curve = []
        trades = []
        liquidated = False
        liquidation_date = None
        liq_count = 0
        total_fees_paid = 0.0
        total_funding_paid = 0.0
        stop_outs_count = 0
        switches_count = 0

        for i, t in enumerate(sub_idx):
            if liquidated:
                equity_curve.append(0.0)
                continue

            settle = is_settlement_bar.loc[t]

            # -------------------------------------------------------------
            # 1. INTRABAR RISK & STOP EVALUATION FOR ACTIVE POSITION
            # -------------------------------------------------------------
            if curr_pos != 'USDT_CASH':
                bar_open = opens.loc[t, curr_pos]
                bar_high = highs.loc[t, curr_pos]
                bar_low = lows.loc[t, curr_pos]
                bar_close = closes.loc[t, curr_pos]

                # Update highest price reached
                highest_price = max(highest_price, bar_high)

                # A. Check Liquidation: Exchange MMR constraint
                # Liquidation price from entry:
                liq_drop_pct = (1.0 / active_leverage - mmr) if active_leverage > 1.0 else 1.0
                liq_price = entry_price * (1.0 - liq_drop_pct)

                if active_leverage > 1.0 and bar_low <= liq_price:
                    # CATASTROPHIC LIQUIDATION!
                    liquidated = True
                    liquidation_date = str(t)
                    liq_count += 1
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': t,
                        'symbol': curr_pos,
                        'exit_reason': 'LIQUIDATION',
                        'pnl_pct': -100.0,
                        'cap_after': 0.0
                    })
                    cap = 0.0
                    equity_curve.append(0.0)
                    continue

                # B. Check Dynamic Stop-Loss Trigger:
                # If bar_low <= stop_loss_price: STOP OUT!
                if bar_low <= stop_loss_price:
                    stop_outs_count += 1
                    # Execute stop-loss with slippage
                    exec_exit_price = min(bar_open, stop_loss_price * (1.0 - stop_slippage))
                    trade_asset_ret = (exec_exit_price - entry_price) / entry_price
                    leveraged_ret = trade_asset_ret * active_leverage

                    # Deduct closing turnover fee on nominal position
                    close_fee = cap * active_leverage * fee_rate
                    total_fees_paid += close_fee

                    pnl_usdt = (cap * leveraged_ret) - close_fee
                    cap = max(0.0, cap + pnl_usdt)

                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': t,
                        'symbol': curr_pos,
                        'exit_reason': 'STOP_LOSS',
                        'asset_ret': trade_asset_ret,
                        'leveraged_ret': leveraged_ret,
                        'pnl_usdt': pnl_usdt,
                        'cap_after': cap
                    })

                    curr_pos = 'USDT_CASH'
                    entry_price = 0.0
                    stop_loss_price = 0.0
                    highest_price = 0.0
                    active_leverage = 1.0
                    equity_curve.append(cap)
                    continue

                # C. Position Survives Intrabar: Update Dynamic Trailing Stop
                # 1. EMA200 Gate stop baseline
                curr_ema = ema200.loc[t, curr_pos]
                gate_stop = curr_ema * (1.0 - hysteresis)
                stop_loss_price = max(stop_loss_price, gate_stop)

                # 2. Breakeven Stop: if highest >= entry * 1.05 -> stop = entry * 1.002
                if highest_price >= entry_price * 1.05:
                    be_stop = entry_price * 1.002
                    stop_loss_price = max(stop_loss_price, be_stop)

                # 3. Trailing Lock: if highest >= entry * 1.10 -> trailing 5% from peak
                if highest_price >= entry_price * 1.10:
                    trail_stop = highest_price * 0.95
                    stop_loss_price = max(stop_loss_price, trail_stop)

                # D. Mark-to-market and funding fee
                bar_ret = (bar_close - bar_open) / bar_open
                bar_pnl = cap * active_leverage * bar_ret

                # Funding rate & borrow cost
                funding_cost = 0.0
                if settle and active_leverage > 1.0:
                    fr = funding_aligned.loc[t, curr_pos] if curr_pos in funding_aligned else 0.0001
                    borrow_fee = (active_leverage - 1.0) * 0.0001 # ~10% APR borrow interest
                    funding_cost = cap * ((active_leverage * fr) + borrow_fee)
                    total_funding_paid += funding_cost

                cap = max(0.0, cap + bar_pnl - funding_cost)
                if cap <= 0.0:
                    liquidated = True
                    liquidation_date = str(t)
                    liq_count += 1
                    equity_curve.append(0.0)
                    continue

            # -------------------------------------------------------------
            # 2. 4-HOUR REBALANCE & CROSS-SECTIONAL MOMENTUM EVALUATION
            # -------------------------------------------------------------
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

            # Asset Switch or Trend Exit
            if target_pos != curr_pos:
                switches_count += 1
                # Close previous position if held
                if curr_pos != 'USDT_CASH':
                    exit_price = opens.loc[t, curr_pos]
                    trade_asset_ret = (exit_price - entry_price) / entry_price
                    close_fee = cap * active_leverage * fee_rate
                    total_fees_paid += close_fee
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': t,
                        'symbol': curr_pos,
                        'exit_reason': 'SIGNAL_EXIT',
                        'asset_ret': trade_asset_ret,
                        'leveraged_ret': trade_asset_ret * active_leverage,
                        'pnl_usdt': (cap * trade_asset_ret * active_leverage) - close_fee,
                        'cap_after': cap
                    })
                    curr_pos = 'USDT_CASH'

                # Open target position if not cash
                if target_pos != 'USDT_CASH' and cap > 0:
                    curr_pos = target_pos
                    entry_price = opens.loc[t, target_pos]
                    entry_time = t
                    highest_price = entry_price

                    # Determine Leverage:
                    if leverage_mode == 'DYNAMIC_SAFE':
                        # Risk Budget: Max acceptable risk on initial capital = 10%
                        # Calculate distance to initial stop
                        init_gate_stop = ema200.loc[t, target_pos] * (1.0 - hysteresis)
                        init_hard_stop = entry_price * 0.95
                        init_stop = max(init_gate_stop, init_hard_stop)
                        dist_to_stop_pct = max(0.02, (entry_price - init_stop) / entry_price)

                        # Leverage = Risk_Budget (10%) / Distance_to_Stop
                        raw_lev = 0.10 / dist_to_stop_pct

                        # ATR Volatility damper: if ATR > 4%, reduce leverage
                        atr_val = df_atrs.loc[t, target_pos]
                        atr_pct = atr_val / entry_price if entry_price > 0 else 0.03
                        if atr_pct > 0.04:
                            raw_lev *= (0.04 / atr_pct)

                        # Liquidation Buffer Constraint:
                        # Distance to liquidation must be at least 2.5x the distance to stop loss!
                        # Liq_drop = 1/L - 0.005 >= 2.5 * dist_to_stop
                        # 1/L >= 2.5 * dist_to_stop + 0.005 => L <= 1 / (2.5 * dist_to_stop + 0.005)
                        max_safe_lev = 1.0 / (2.5 * dist_to_stop_pct + 0.005)

                        chosen_lev = min(raw_lev, max_safe_lev)
                        # Clip between 1.0x and 3.5x for robust safety
                        active_leverage = round(float(np.clip(chosen_lev, 1.0, 3.5)), 1)
                    else:
                        active_leverage = fixed_leverage

                    # Set Initial Stop Loss
                    init_gate_stop = ema200.loc[t, target_pos] * (1.0 - hysteresis)
                    init_hard_stop = entry_price * 0.95
                    stop_loss_price = max(init_gate_stop, init_hard_stop)

                    # Deduct open turnover fee
                    open_fee = cap * active_leverage * fee_rate
                    total_fees_paid += open_fee
                    cap -= open_fee

            equity_curve.append(cap)

        # Performance Metrics Calculation
        eq_s = pd.Series(equity_curve, index=sub_idx)
        final_equity = eq_s.iloc[-1]
        total_ret_pct = ((final_equity - 10000.0) / 10000.0) * 100.0

        n_bars = len(eq_s)
        years = n_bars / (365.25 * 6) # 4h bars per day = 6
        cagr_pct = ((final_equity / 10000.0) ** (1.0 / years) - 1.0) * 100.0 if (final_equity > 0 and years > 0) else -100.0

        running_max = eq_s.cummax()
        drawdown = (eq_s - running_max) / running_max
        max_dd_pct = drawdown.min() * 100.0

        # Sharpe ratio (daily resampling)
        daily_eq = eq_s.resample('1D').last().dropna()
        daily_rets = daily_eq.pct_change().dropna()
        sharpe = (daily_rets.mean() / (daily_rets.std() + 1e-8)) * np.sqrt(365) if len(daily_rets) > 10 else 0.0

        calmar = (cagr_pct / abs(max_dd_pct)) if abs(max_dd_pct) > 0.01 else 0.0

        # Trade stats
        win_trades = [tr for tr in trades if tr.get('pnl_usdt', 0) > 0]
        loss_trades = [tr for tr in trades if tr.get('pnl_usdt', 0) <= 0]
        win_rate = (len(win_trades) / len(trades) * 100.0) if trades else 0.0

        total_gain = sum(tr.get('pnl_usdt', 0) for tr in win_trades)
        total_loss = abs(sum(tr.get('pnl_usdt', 0) for tr in loss_trades))
        profit_factor = (total_gain / total_loss) if total_loss > 0 else (99.0 if total_gain > 0 else 0.0)

        return {
            'leverage_mode': leverage_mode,
            'final_equity': round(final_equity, 2),
            'total_ret_pct': round(total_ret_pct, 2),
            'cagr_pct': round(cagr_pct, 2),
            'max_dd_pct': round(max_dd_pct, 2),
            'sharpe': round(sharpe, 2),
            'calmar': round(calmar, 2),
            'trade_count': len(trades),
            'stop_outs_count': stop_outs_count,
            'switches_count': switches_count,
            'win_rate': round(win_rate, 2),
            'profit_factor': round(profit_factor, 2),
            'liquidated': liquidated,
            'liquidation_date': liquidation_date,
            'total_fees_paid': round(total_fees_paid, 2),
            'total_funding_paid': round(total_funding_paid, 2),
        }

    periods = {
        '2020-2024 (训练牛熊期)': ('2020-01-01', '2024-12-31'),
        '2025 (分化震荡期)': ('2025-01-01', '2025-12-31'),
        '2026 (盲测弱势期)': ('2026-01-01', '2026-09-20'),
        '2022 (极端熊市测试)': ('2022-01-01', '2022-12-31'),
        '2020-2026 (全周期)': ('2020-01-01', '2026-09-20'),
    }

    leverage_configs = [
        ('1.0x 现货基准', '1.0x', 1.0),
        ('2.0x 杠杆', '2.0x', 2.0),
        ('3.0x 杠杆', '3.0x', 3.0),
        ('4.0x 杠杆', '4.0x', 4.0),
        ('5.0x 杠杆', '5.0x', 5.0),
        ('动态风控推荐杠杆 (Dynamic Safe)', 'DYNAMIC_SAFE', 1.0),
    ]

    all_results = {}

    for p_name, (s_dt, e_dt) in periods.items():
        print(f"\n================================================================================")
        print(f" TESTING PERIOD: {p_name} ({s_dt} to {e_dt})")
        print(f"================================================================================")
        p_res = []
        for label, mode, fixed_l in leverage_configs:
            res = simulate_run(s_dt, e_dt, leverage_mode=mode, fixed_leverage=fixed_l)
            res['label'] = label
            p_res.append(res)
            liq_str = f"💥 爆仓清零 ({res['liquidation_date']})" if res['liquidated'] else "✅ 安全存活"
            print(f"  [{label:30s}] 收益: {res['total_ret_pct']:+10.2f}% | 年化: {res['cagr_pct']:+8.2f}% | 最大回撤: {res['max_dd_pct']:6.2f}% | 夏普: {res['sharpe']:4.2f} | 卡玛: {res['calmar']:4.2f} | 止损触发: {res['stop_outs_count']}次 | 手续费: ${res['total_fees_paid']:,.0f} | 状态: {liq_str}")
        all_results[p_name] = p_res

    # Save summary to CSV
    rows = []
    for p_name, p_res in all_results.items():
        for r in p_res:
            rows.append({
                'Period': p_name,
                'Configuration': r['label'],
                'Total Return (%)': r['total_ret_pct'],
                'CAGR (%)': r['cagr_pct'],
                'Max Drawdown (%)': r['max_dd_pct'],
                'Sharpe': r['sharpe'],
                'Calmar': r['calmar'],
                'Win Rate (%)': r['win_rate'],
                'Profit Factor': r['profit_factor'],
                'Trades': r['trade_count'],
                'Stop-Outs': r['stop_outs_count'],
                'Fees Paid ($)': r['total_fees_paid'],
                'Funding Paid ($)': r['total_funding_paid'],
                'Liquidated': r['liquidated'],
                'Liquidation Date': r['liquidation_date']
            })
    pd.DataFrame(rows).to_csv('leverage_research/leverage_with_stops_summary.csv', index=False)
    print("\n[SUCCESS] Backtest complete. Results saved to leverage_research/leverage_with_stops_summary.csv")

if __name__ == '__main__':
    run_backtest()
