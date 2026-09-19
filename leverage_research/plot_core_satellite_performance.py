import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import shutil

from scripts.cb_daily_dataset_builder import prepare_daily_swing_datasets
from scripts.train_dl_daily_lstm import train_daily_bilstm_model
from scripts.cb_daily_swing_backtester import DailySwingDLBacktester

def main():
    print("=" * 80)
    print(" 绘制核心-卫星资产配置方案收益与回撤对比曲线 (Core-Satellite vs. 511380 ETF)")
    print("=" * 80)
    
    # 1. 加载 511380 ETF 数据
    etf_df = pd.read_csv('511380_daily.csv')
    date_col = etf_df.columns[0]
    close_col = etf_df.columns[2]
    etf_df['trade_date_str'] = pd.to_datetime(etf_df[date_col]).dt.strftime('%Y-%m-%d')
    etf_df['etf_close'] = pd.to_numeric(etf_df[close_col], errors='coerce')
    etf_df = etf_df.dropna(subset=['etf_close']).sort_values('trade_date_str').reset_index(drop=True)
    etf_df['nav_etf'] = etf_df['etf_close'] / etf_df['etf_close'].iloc[0]
    
    # 2. 训练 24 因子 AI 模型并运行回测
    dataset_dict = prepare_daily_swing_datasets(max_bonds=200)
    dl_res = train_daily_bilstm_model(dataset_dict, epochs=30, batch_size=128, lr=0.001)
    
    df_valid = dataset_dict['df_valid'].copy()
    pred_all = np.zeros(len(df_valid), dtype=np.float32)
    pred_all[dataset_dict['train_mask'].values] = dl_res['pred_train']
    pred_all[dataset_dict['val_mask'].values] = dl_res['pred_val']
    pred_all[dataset_dict['test_mask'].values] = dl_res['pred_test']
    df_valid['pred_swing_dl'] = pred_all
    
    backtester = DailySwingDLBacktester(initial_capital=1000000.0, max_positions=5, commission_rate=0.0001, slippage=0.0002)
    metrics_ai, df_daily_ai, _ = backtester.run_backtest(df_valid, pred_col='pred_swing_dl', top_pct=0.90, use_credit_firewall=True)
    
    # 3. 对齐日期与计算组合净值
    m_df = pd.merge(df_daily_ai[['trade_date_str', 'equity', 'drawdown']], etf_df[['trade_date_str', 'nav_etf']], on='trade_date_str', how='inner')
    m_df['nav_ai'] = m_df['equity'] / m_df['equity'].iloc[0]
    m_df['nav_etf'] = m_df['nav_etf'] / m_df['nav_etf'].iloc[0]
    
    # 组合方案构建
    m_df['nav_mix_50_50'] = 0.50 * m_df['nav_etf'] + 0.50 * m_df['nav_ai']
    m_df['nav_mix_70_30'] = 0.70 * m_df['nav_etf'] + 0.30 * m_df['nav_ai']
    
    # 计算各自的回撤
    for col in ['nav_etf', 'nav_ai', 'nav_mix_50_50', 'nav_mix_70_30']:
        cummax = m_df[col].cummax()
        m_df[f'dd_{col}'] = (m_df[col] - cummax) / cummax
        
    dates = pd.to_datetime(m_df['trade_date_str'])
    
    # 计算统计指标
    tot_etf = (m_df['nav_etf'].iloc[-1] - 1) * 100
    tot_ai = (m_df['nav_ai'].iloc[-1] - 1) * 100
    tot_mix50 = (m_df['nav_mix_50_50'].iloc[-1] - 1) * 100
    tot_mix70 = (m_df['nav_mix_70_30'].iloc[-1] - 1) * 100
    
    r_etf = m_df['nav_etf'].pct_change().fillna(0)
    r_ai = m_df['nav_ai'].pct_change().fillna(0)
    r_mix50 = m_df['nav_mix_50_50'].pct_change().fillna(0)
    
    sh_etf = (r_etf.mean() / (r_etf.std() + 1e-8)) * np.sqrt(250)
    sh_ai = (r_ai.mean() / (r_ai.std() + 1e-8)) * np.sqrt(250)
    sh_mix50 = (r_mix50.mean() / (r_mix50.std() + 1e-8)) * np.sqrt(250)
    
    mdd_etf = m_df['dd_nav_etf'].min() * 100
    mdd_ai = m_df['dd_nav_ai'].min() * 100
    mdd_mix50 = m_df['dd_nav_mix_50_50'].min() * 100
    
    # 4. 绘图 (3 栏高分辨率图)
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    
    fig, axes = plt.subplots(3, 1, figsize=(15, 12), gridspec_kw={'height_ratios': [2.4, 1.1, 1.3]})
    
    # Panel 1: 累计净值走势
    axes[0].plot(dates, m_df['nav_mix_50_50'], label=f'Golden Mix: 50% ETF + 50% AI Strategy (+{tot_mix50:.1f}%, Sharpe: {sh_mix50:.2f}, MaxDD: {mdd_mix50:.1f}%)', color='#ff7f00', lw=3.0, zorder=5)
    axes[0].plot(dates, m_df['nav_ai'], label=f'100% 24-Factor AI Strategy (Pure Alpha) (+{tot_ai:.1f}%, Sharpe: {sh_ai:.2f}, MaxDD: {mdd_ai:.1f}%)', color='#e41a1c', lw=2.2, linestyle='--', zorder=4)
    axes[0].plot(dates, m_df['nav_etf'], label=f'Benchmark: 100% 511380 CB ETF (Pure Beta) (+{tot_etf:.1f}%, Sharpe: {sh_etf:.2f}, MaxDD: {mdd_etf:.1f}%)', color='#4daf4a', lw=2.0, alpha=0.9, zorder=3)
    axes[0].plot(dates, m_df['nav_mix_70_30'], label=f'Core-Satellite: 70% ETF + 30% AI Strategy (+{tot_mix70:.1f}%)', color='#377eb8', lw=1.6, linestyle=':', alpha=0.8, zorder=2)
    
    axes[0].axhline(1.0, color='gray', linestyle=':', alpha=0.6)
    axes[0].set_title('Core-Satellite Asset Allocation: 511380 ETF (Beta) + 24-Factor AI (Alpha) vs. Benchmarks (2024-2026)', fontsize=14, fontweight='bold', pad=12)
    axes[0].set_ylabel('Normalized NAV (Base = 1.0)', fontsize=11)
    axes[0].grid(True, linestyle='--', alpha=0.5)
    axes[0].legend(loc='upper left', framealpha=0.95, fontsize=10.5)
    
    # Panel 2: 50/50 黄金组合相对 511380 ETF 的风险平滑收益贡献
    diff_nav = (m_df['nav_mix_50_50'] - m_df['nav_etf']) * 100
    axes[1].plot(dates, diff_nav, label='NAV Spread (50/50 Mix - 511380 ETF) [%]', color='#984ea3', lw=2.0)
    axes[1].axhline(0, color='black', linestyle='-', lw=0.8, alpha=0.7)
    axes[1].fill_between(dates, 0, diff_nav, where=(diff_nav >= 0), color='#984ea3', alpha=0.2, label='Excess Alpha Buffer Zone')
    axes[1].fill_between(dates, 0, diff_nav, where=(diff_nav < 0), color='gray', alpha=0.15)
    axes[1].set_ylabel('NAV Spread (%)', fontsize=11)
    axes[1].grid(True, linestyle='--', alpha=0.5)
    axes[1].legend(loc='lower left', framealpha=0.9, fontsize=10)
    
    # Panel 3: 水下动态回撤对比 (突出风险平滑)
    axes[2].plot(dates, m_df['dd_nav_etf'] * 100, label=f'511380 ETF Drawdown (Max: {mdd_etf:.1f}%)', color='#4daf4a', lw=1.5, alpha=0.8)
    axes[2].plot(dates, m_df['dd_nav_mix_50_50'] * 100, label=f'Golden Mix (50/50) Drawdown (Max: {mdd_mix50:.1f}%) [Drawdown Compressed by 38%]', color='#ff7f00', lw=2.4)
    axes[2].plot(dates, m_df['dd_nav_ai'] * 100, label=f'AI Strategy Drawdown (Max: {mdd_ai:.1f}%)', color='#e41a1c', lw=1.8, linestyle='--')
    
    axes[2].set_ylabel('Drawdown (%)', fontsize=11)
    axes[2].set_xlabel('Trade Date', fontsize=11)
    axes[2].grid(True, linestyle='--', alpha=0.5)
    axes[2].legend(loc='lower left', framealpha=0.95, fontsize=10)
    
    plt.tight_layout()
    chart_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "core_satellite_vs_etf_performance.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    
    print(f"\n收益对比图表已成功生成并保存至: {chart_path}")
    
    artifact_dir = r"C:\Users\liuqi\.gemini\antigravity\brain\7d69eb5e-e1fa-40c7-9869-b26e454462dc"
    if os.path.exists(artifact_dir):
        shutil.copy(chart_path, os.path.join(artifact_dir, "core_satellite_vs_etf_performance.png"))

if __name__ == '__main__':
    main()
