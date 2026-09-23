# -*- coding: utf-8 -*-
"""
Audited Clean Single-Ledger Universe Expansion Study
====================================================
Evaluates Core-4 vs Top-5, Top-6, Top-7, Top-10 under strict single-ledger accounting:
- Zero double counting of PnL.
- Strict chronological causality (Signals from T-1, Execution at Open T, Intrabar stop/liq, MTM at Close T).
- Exact 8 bps fee per leg * leverage, 15 bps stop-loss slippage, Binance 8h funding, 10% APR borrow cost.
- Exports trade-by-trade audit logs to leverage_research/trade_logs/.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd
import numpy as np

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from crypto_quant.backtest.clean_single_ledger_engine import SingleLedgerSimulator

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def run_clean_study():
    all_symbols = [
        'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT',
        'AVAXUSDT', 'NEARUSDT', 'LINKUSDT', 'ADAUSDT',
        'DOTUSDT', 'LTCUSDT', 'XRPUSDT', 'SUIUSDT'
    ]

    raw_dfs = {}
    for s in all_symbols:
        p = f'data/{s}_4h_2020_2026.parquet'
        if os.path.exists(p):
            raw_dfs[s] = pd.read_parquet(p)

    df_funding = pd.read_parquet('data/binance_funding_8h.parquet')
    if df_funding.index.tz is not None:
        df_funding.index = df_funding.index.tz_localize(None)

    trade_log_dir = Path('leverage_research/trade_logs')
    trade_log_dir.mkdir(parents=True, exist_ok=True)

    universes = {
        'Core-4 (Baseline)': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT'],
        'Top-5 (+NEAR)': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'NEARUSDT'],
        'Top-6 (+NEAR+AVAX)': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'NEARUSDT', 'AVAXUSDT'],
        'Top-7 (+NEAR+AVAX+LINK)': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'NEARUSDT', 'AVAXUSDT', 'LINKUSDT'],
        'Top-10 (Broad Liquid)': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'NEARUSDT', 'AVAXUSDT', 'LINKUSDT', 'ADAUSDT', 'DOTUSDT', 'XRPUSDT'],
    }

    periods = {
        '2026 近期样本外走势 (2026 OOS)': ('2026-01-01', '2026-09-22'),
        '2025 (分化震荡期)': ('2025-01-01', '2025-12-31'),
        '2022 (极端熊市测试)': ('2022-01-01', '2022-12-31'),
        '2020-2024 (训练牛熊期)': ('2020-10-15', '2024-12-31'),
        '2020-2026 (全周期)': ('2020-10-15', '2026-09-22'),
    }

    results = []

    print("==========================================================================================")
    print(" AUDITED CLEAN SINGLE-LEDGER UNIVERSE EXPANSION STUDY (ZERO DOUBLE-COUNTING)")
    print("==========================================================================================")

    for p_name, (s_dt, e_dt) in periods.items():
        print(f"\n--- 评估周期: {p_name} ({s_dt} ~ {e_dt}) ---")
        for u_name, tokens in universes.items():
            sim = SingleLedgerSimulator(
                symbols=tokens,
                raw_dfs=raw_dfs,
                df_funding=df_funding,
                leverage=3.0,
                fee_rate=0.0008,
                execution_slippage=0.0005,
                stop_slippage=0.0015,
                sl_atr_mult=1.5,
                hysteresis_pct=0.005,
                delta_score_buffer=0.0,
            )
            res = sim.run(s_dt, e_dt)
            if res is None:
                continue

            res_record = {
                'universe': u_name,
                'tokens': ",".join(tokens),
                'period': p_name,
                'leverage': '3.0x',
                'delta_buffer': 0.0,
                'final_equity': res['final_equity'],
                'total_ret_pct': res['total_ret_pct'],
                'cagr_pct': res['cagr_pct'],
                'max_dd_pct': res['max_dd_pct'],
                'sharpe': res['sharpe'],
                'calmar': res['calmar'],
                'win_rate': res['win_rate'],
                'trade_count': res['trade_count'],
                'stop_count': res['stop_count'],
                'liquidated': res['liquidated'],
                'liquidation_date': res['liquidation_date'],
                'total_fees': res['total_fees'],
                'total_slippage': res['total_slippage'],
                'total_funding': res['total_funding'],
            }
            results.append(res_record)

            # Export trade CSV for verification
            clean_pname = p_name.split(' ')[0]
            clean_uname = u_name.split(' ')[0]
            trade_csv_path = trade_log_dir / f"trades_{clean_uname}_{clean_pname}_3x.csv"
            trades_df = pd.DataFrame([vars(tr) for tr in res['trades_list']])
            if not trades_df.empty:
                trades_df.to_csv(trade_csv_path, index=False)

            liq_str = f"💥 爆仓 ({res['liquidation_date']})" if res['liquidated'] else "✅ 存活"
            print(f"  [{u_name:24s}] 收益: {res['total_ret_pct']:+8.2f}% | 年化: {res['cagr_pct']:+7.2f}% | 回撤: {res['max_dd_pct']:6.2f}% | 夏普: {res['sharpe']:4.2f} | 胜率: {res['win_rate']:4.1f}% | 交易: {res['trade_count']:3d}次 (止损{res['stop_count']:2d}) | {liq_str}")

    # Modern Era 2023-2026 including SUI
    print(f"\n--- 新一代公链 (包含 SUI 2023-05-04 ~ 2026-09-22) ---")
    sui_universes = {
        'Core-4 Baseline': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT'],
        '+SUI': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'SUIUSDT'],
        '+NEAR': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'NEARUSDT'],
        '+NEAR+SUI (Top-6)': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'NEARUSDT', 'SUIUSDT'],
        '+NEAR+SUI+AVAX (Top-7)': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'NEARUSDT', 'SUIUSDT', 'AVAXUSDT'],
    }
    for u_name, tokens in sui_universes.items():
        # Test with Delta Buffer 0.0 and 0.30
        for delta in [0.0, 0.30]:
            sim = SingleLedgerSimulator(
                symbols=tokens,
                raw_dfs=raw_dfs,
                df_funding=df_funding,
                leverage=3.0,
                fee_rate=0.0008,
                execution_slippage=0.0005,
                stop_slippage=0.0015,
                sl_atr_mult=1.5,
                hysteresis_pct=0.005,
                delta_score_buffer=delta,
            )
            res = sim.run('2023-05-04', '2026-09-22')
            tag = f"(Delta {delta:.2f})"
            res_record = {
                'universe': f"{u_name} {tag}",
                'tokens': ",".join(tokens),
                'period': '2023-2026 (SUI周期)',
                'leverage': '3.0x',
                'delta_buffer': delta,
                'final_equity': res['final_equity'],
                'total_ret_pct': res['total_ret_pct'],
                'cagr_pct': res['cagr_pct'],
                'max_dd_pct': res['max_dd_pct'],
                'sharpe': res['sharpe'],
                'calmar': res['calmar'],
                'win_rate': res['win_rate'],
                'trade_count': res['trade_count'],
                'stop_count': res['stop_count'],
                'liquidated': res['liquidated'],
                'liquidation_date': res['liquidation_date'],
                'total_fees': res['total_fees'],
                'total_slippage': res['total_slippage'],
                'total_funding': res['total_funding'],
            }
            results.append(res_record)
            liq_str = f"💥 爆仓" if res['liquidated'] else "✅ 存活"
            print(f"  [{u_name:23s} {tag:12s}] 收益: {res['total_ret_pct']:+8.2f}% | 年化: {res['cagr_pct']:+7.2f}% | 回撤: {res['max_dd_pct']:6.2f}% | 夏普: {res['sharpe']:4.2f} | 交易: {res['trade_count']:3d}次 (止损{res['stop_count']:2d}) | {liq_str}")

    # Also evaluate 1.0x Spot baseline
    print(f"\n--- 1.0x 现货零杠杆基准 (全周期 2020-2026) ---")
    s_dt, e_dt = periods['2020-2026 (全周期)']
    for u_name in ['Core-4 (Baseline)', 'Top-5 (+NEAR)']:
        tokens = universes[u_name]
        sim = SingleLedgerSimulator(
            symbols=tokens,
            raw_dfs=raw_dfs,
            df_funding=df_funding,
            leverage=1.0,
            fee_rate=0.0008,
            slippage=0.0015,
            sl_atr_mult=1.5,
            hysteresis_pct=0.005,
            delta_score_buffer=0.0,
        )
        res = sim.run(s_dt, e_dt)
        res_record = {
            'universe': u_name,
            'tokens': ",".join(tokens),
            'period': '2020-2026 (全周期)',
            'leverage': '1.0x',
            'delta_buffer': 0.0,
            'final_equity': res['final_equity'],
            'total_ret_pct': res['total_ret_pct'],
            'cagr_pct': res['cagr_pct'],
            'max_dd_pct': res['max_dd_pct'],
            'sharpe': res['sharpe'],
            'calmar': res['calmar'],
            'win_rate': res['win_rate'],
            'trade_count': res['trade_count'],
            'stop_count': res['stop_count'],
            'liquidated': res['liquidated'],
            'liquidation_date': res['liquidation_date'],
            'total_fees': res['total_fees'],
            'total_slippage': res['total_slippage'],
            'total_funding': res['total_funding'],
        }
        results.append(res_record)
        print(f"  [1.0x {u_name:20s}] 收益: {res['total_ret_pct']:+8.2f}% | 年化: {res['cagr_pct']:+6.2f}% | 回撤: {res['max_dd_pct']:6.2f}% | 夏普: {res['sharpe']:4.2f} | 交易: {res['trade_count']:3d}次")

    df_out = pd.DataFrame(results)
    df_out.to_csv('leverage_research/universe_expansion_comparison_clean.csv', index=False)
    print("\n[SUCCESS] Clean Single-Ledger backtest completed. Saved to leverage_research/universe_expansion_comparison_clean.csv")


if __name__ == '__main__':
    run_clean_study()
