# -*- coding: utf-8 -*-
"""
Audited Clean Single-Ledger Comparison: 1.0x vs 3.0x vs 5.0x
============================================================
Evaluates Core-4 under strict single-ledger accounting:
- Zero double counting.
- Strict chronological causality.
- Exact fee rate, slippage, funding rates, and intrabar liquidation.
- Compares 1.0x, 3.0x, and 5.0x leverage across all market regimes.
"""

import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from crypto_quant.backtest.clean_single_ledger_engine import SingleLedgerSimulator

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def run_clean_leverage_comparison():
    tokens = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT']
    raw_dfs = {t: pd.read_parquet(f'data/{t}_4h_2020_2026.parquet') for t in tokens}

    df_funding = pd.read_parquet('data/binance_funding_8h.parquet')
    if df_funding.index.tz is not None:
        df_funding.index = df_funding.index.tz_localize(None)

    periods = {
        '2026 (盲测弱势期)': ('2026-01-01', '2026-09-22'),
        '2025 (分化震荡期)': ('2025-01-01', '2025-12-31'),
        '2022 (极端熊市测试)': ('2022-01-01', '2022-12-31'),
        '2020-2024 (训练牛熊期)': ('2020-10-15', '2024-12-31'),
        '2020-2026 (全周期)': ('2020-10-15', '2026-09-22'),
    }

    results = []

    print("==========================================================================================")
    print(" AUDITED 1.0X vs 3.0X vs 5.0X LEVERAGE COMPARISON (CLEAN SINGLE-LEDGER)")
    print("==========================================================================================")

    for p_name, (s_dt, e_dt) in periods.items():
        print(f"\n--- 评估周期: {p_name} ({s_dt} ~ {e_dt}) ---")
        for lev in [1.0, 3.0, 5.0]:
            sim = SingleLedgerSimulator(
                symbols=tokens,
                raw_dfs=raw_dfs,
                df_funding=df_funding,
                leverage=lev,
                fee_rate=0.0008,
                slippage=0.0015,
                sl_atr_mult=1.5,
                hysteresis_pct=0.005,
            )
            res = sim.run(s_dt, e_dt)
            if res is None:
                continue

            results.append({
                'period': p_name,
                'leverage': f'{lev:.1f}x',
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
            })
            liq_str = f"💥 爆仓 ({res['liquidation_date']})" if res['liquidated'] else "✅ 存活"
            print(f"  [{lev:.1f}x 杠杆] 收益: {res['total_ret_pct']:+8.2f}% | 年化: {res['cagr_pct']:+7.2f}% | 回撤: {res['max_dd_pct']:6.2f}% | 夏普: {res['sharpe']:4.2f} | 交易: {res['trade_count']:3d}次 (止损{res['stop_count']:2d}) | 手续费: ${res['total_fees']:,.0f} | {liq_str}")

    os.makedirs('leverage_research', exist_ok=True)
    df_out = pd.DataFrame(results)
    df_out.to_csv('leverage_research/compare_1x_3x_5x_summary_clean.csv', index=False)
    print("\n[SUCCESS] Clean 1x/3x/5x leverage comparison completed. Saved to leverage_research/compare_1x_3x_5x_summary_clean.csv")


if __name__ == '__main__':
    run_clean_leverage_comparison()
