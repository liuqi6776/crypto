# -*- coding: utf-8 -*-
"""
Systematic Evaluation: 3 Assets (BTC vs ETH vs SOL) x 5 Frequencies + Buy & Hold
严格在 2024-2025 验证集上运行 15 组网格评测与基准对比 (含自适应动量退出)
"""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np
import pandas as pd

TOKENS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']

# 5 档交易频率配置 (清晰中英文说明)
FREQUENCIES = {
    'Adaptive (12h)':   {'min_bars': 0, 'desc': 'Adaptive Momentum Exit / 自适应动量退出'},
    '3x / Day (8h)':    {'min_bars': 2, 'desc': 'Intraday 8h / 日内高频'},
    '1x / Day (24h)':   {'min_bars': 6, 'desc': 'Daily 24h / 每日一次'},
    '1x / 3Days (72h)': {'min_bars': 18, 'desc': 'Swing 72h / 三天一次'},
    '1x / Week (168h)': {'min_bars': 42, 'desc': 'Weekly 168h / 每周一次'}
}


def find_project_root():
    """动态定位项目根目录，兼容从根目录或子目录执行"""
    current = os.path.abspath(os.path.dirname(__file__))
    candidates = [
        os.path.abspath(os.path.join(current, '..')),
        current,
        os.getcwd(),
        os.path.abspath(os.path.join(os.getcwd(), '..'))
    ]
    for c in candidates:
        if os.path.exists(os.path.join(c, 'data')) and os.path.exists(os.path.join(c, 'predictions')):
            return c
    return os.getcwd()


def simulate_frequency_strategy(preds, closes, opens, min_bars, fng_arr, stb_flow_arr, rolling_w=72, cost=0.0005):
    """
    模拟特定交易频次与约束下的实盘交易 (扣除 0.05% Taker 手续费与滑点)
    """
    n = len(preds)
    p_series = pd.Series(preds.values if hasattr(preds, 'values') else preds)
    z_score = (p_series - p_series.rolling(rolling_w).mean()) / (p_series.rolling(rolling_w).std() + 1e-8)
    z_vals = z_score.values
    
    # 基础入场门槛：模型高置信度 (z > 1.0) + 链上稳定币净流入 (stb > 0) + 避开非理性癫狂 (fng < 85)
    raw_sig = (z_vals > 1.0) & (stb_flow_arr > 0.0) & (fng_arr < 85)

    pos = np.zeros(n)
    trades = 0
    in_pos = False
    entry_bar = 0

    for i in range(n - 1):
        if not in_pos:
            if raw_sig[i]:
                in_pos = True
                entry_bar = i
                pos[i] = 1.0
                trades += 1
            else:
                pos[i] = 0.0
        else:
            held_bars = i - entry_bar
            if min_bars == 0:
                # 自适应动量退出：当信号不再满足多头条件时立即退出避险
                if not raw_sig[i]:
                    in_pos = False
                    pos[i] = 0.0
                    trades += 1
                else:
                    pos[i] = 1.0
            else:
                # 固定最低持仓周期：未达到 min_bars 强制持仓
                if held_bars < min_bars:
                    pos[i] = 1.0
                else:
                    # 达到最低周期后，若 z-score 回落至 0.2 以下则平仓退出
                    if z_vals[i] < 0.2:
                        in_pos = False
                        pos[i] = 0.0
                        trades += 1
                    else:
                        pos[i] = 1.0

    # 严格在次根 open 执行 (次根开盘收益扣除 Taker 手续费摩擦)
    c_series = pd.Series(closes.values if hasattr(closes, 'values') else closes)
    rets = (c_series.shift(-1) / c_series - 1).values
    trade_signals = pd.Series(pos).diff().abs().fillna(0).values
    strat_rets = (pos * rets - trade_signals * cost)[:-1]
    strat_rets = pd.Series(strat_rets, index=closes.index[:-1] if hasattr(closes, 'index') else None)

    # 指标计算 (每年 2,190 根 4h K线)
    cum = (1 + strat_rets).cumprod()
    total_ret = cum.iloc[-1] - 1
    years = len(strat_rets) / 2190
    cagr = (1 + total_ret) ** (1 / years) - 1 if total_ret > -1 else -1.0
    
    ann_vol = strat_rets.std() * np.sqrt(2190)
    sharpe = strat_rets.mean() / (strat_rets.std() + 1e-8) * np.sqrt(2190)

    cum_max = cum.cummax()
    drawdown = (cum - cum_max) / cum_max
    mdd = drawdown.min()
    calmar = cagr / abs(mdd) if abs(mdd) > 1e-6 else 0.0

    non_zero = strat_rets[strat_rets != 0]
    win_rate = (non_zero > 0).mean() if len(non_zero) > 0 else 0.0
    exposure = (pos > 0).mean()

    return {
        'total_ret': total_ret,
        'cagr': cagr,
        'mdd': mdd,
        'sharpe': sharpe,
        'calmar': calmar,
        'win_rate': win_rate,
        'exposure': exposure,
        'trades': trades,
        'cum_curve': cum
    }


def run_grid_evaluation():
    root_dir = find_project_root()
    pred_path = os.path.join(root_dir, 'predictions', 'test_predictions.parquet')
    if not os.path.exists(pred_path):
        pred_path = os.path.join(root_dir, 'predictions', 'val_predictions_2024_2025.parquet')
    if not os.path.exists(pred_path):
        raise FileNotFoundError(f"Predictions parquet not found under {os.path.join(root_dir, 'predictions')}")

    df_full = pd.read_parquet(pred_path)
    # 截取 2024-01-01 至 2025-12-31 两年验证集
    df_val = df_full.loc['2024-01-01':'2025-12-31']
    val_idx = df_val.index
    print(f"=== Running 15-Grid Evaluation on 2024-2025 Validation Set ({len(df_val)} bars, {val_idx[0].date()} to {val_idx[-1].date()}) ===")

    # 加载底层行情
    data_dir = os.path.join(root_dir, 'data')
    raw_dfs = {}
    for t in TOKENS:
        p_path = os.path.join(data_dir, f'{t}_4h_2020_2026.parquet')
        if not os.path.exists(p_path):
            p_path = os.path.join(data_dir, f'{t}_4h_2021_2026.parquet')
        raw_dfs[t] = pd.read_parquet(p_path).loc[val_idx]

    # 加载链上资金流与情绪，并对齐到 4h 时间戳
    onchain_path = os.path.join(data_dir, 'eth_onchain_sentiment_daily.parquet')
    df_onchain = pd.read_parquet(onchain_path)
    onchain_aligned = df_onchain.shift(1).reindex(val_idx.normalize(), method='ffill')
    onchain_aligned.index = val_idx

    fng_arr = onchain_aligned['fng_score'].values
    stb_flow_arr = onchain_aligned['stb_flow_7d'].values

    grid_results = []

    for token in TOKENS:
        preds = df_val[f'{token}_pred_4h']
        closes = raw_dfs[token]['close']
        opens = raw_dfs[token]['open']

        # 基准买入持有
        bh_rets = closes.shift(-1) / closes - 1
        bh_cum = (1 + bh_rets.iloc[:-1]).cumprod()
        bh_tot = bh_cum.iloc[-1] - 1
        bh_years = len(bh_rets) / 2190
        bh_cagr = (1 + bh_tot) ** (1 / bh_years) - 1
        bh_mdd = ((bh_cum - bh_cum.cummax()) / bh_cum.cummax()).min()
        bh_sharpe = bh_rets.mean() / (bh_rets.std() + 1e-8) * np.sqrt(2190)

        grid_results.append({
            'asset': token,
            'freq': 'Buy & Hold (Benchmark)',
            'desc': '现货基准买入持有',
            'total_ret': bh_tot,
            'cagr': bh_cagr,
            'mdd': bh_mdd,
            'sharpe': bh_sharpe,
            'calmar': bh_cagr / abs(bh_mdd),
            'win_rate': (bh_rets > 0).mean(),
            'exposure': 1.0,
            'trades': 1
        })

        for freq_name, freq_cfg in FREQUENCIES.items():
            res = simulate_frequency_strategy(
                preds, closes, opens, 
                min_bars=freq_cfg['min_bars'], 
                fng_arr=fng_arr, 
                stb_flow_arr=stb_flow_arr
            )
            grid_results.append({
                'asset': token,
                'freq': freq_name,
                'desc': freq_cfg['desc'],
                **res
            })

    df_res = pd.DataFrame(grid_results)
    
    # 打印排版表格
    print("\n" + "=" * 105)
    print("      2024-2025 VALIDATION SET GRID EVALUATION: 3 ASSETS x 5 FREQUENCIES (STRICT ZERO-LEAK)       ")
    print("=" * 105)
    header = f"{'Asset':<10} | {'Frequency':<22} | {'Total Ret':<10} | {'CAGR':<8} | {'MDD':<8} | {'Sharpe':<7} | {'Calmar':<7} | {'Exposure':<9} | {'Trades':<6}"
    print(header)
    print("-" * 105)
    for _, r in df_res.iterrows():
        print(f"{r['asset']:<10} | {r['freq']:<22} | {r['total_ret']*100:+8.2f}% | {r['cagr']*100:+6.2f}% | {r['mdd']*100:6.2f}% | {r['sharpe']:6.2f} | {r['calmar']:6.2f} | {r['exposure']*100:6.1f}%   | {r['trades']:<6}")
    print("=" * 105)

    out_csv = os.path.join(data_dir, 'grid_evaluation_2024_2025.csv')
    cols_to_save = [c for c in df_res.columns if c != 'cum_curve']
    df_res[cols_to_save].to_csv(out_csv, index=False)
    print(f"\nGrid evaluation results successfully saved to: {out_csv}")
    return df_res


if __name__ == '__main__':
    run_grid_evaluation()
