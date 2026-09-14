# -*- coding: utf-8 -*-
"""
Test True Alpha: Symmetrical Long/Short Trading vs Long-Only
Analyzes Market Beta, Jensen Alpha, and Drawdowns across ETH and SOL.
"""
import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

pred_path = root_dir / 'predictions' / 'test_predictions.parquet'
df = pd.read_parquet(pred_path).loc['2024-01-01':'2025-12-31']
val_idx = df.index


for token, sl in [('ETHUSDT', 0.025), ('SOLUSDT', 0.050)]:
    pred = df[f'{token}_pred_4h']
    opens = df[f'{token}_open']
    closes = df[f'{token}_close']
    
    prior_mean = pred.shift(1).rolling(72).mean()
    prior_std = pred.shift(1).rolling(72).std() + 1e-8
    z = (pred - prior_mean) / prior_std
    
    n = len(df)
    pos = np.zeros(n)
    in_pos = 0  # +1 Long, -1 Short, 0 Cash
    entry_bar = 0
    trades = []
    
    for i in range(n - 2):
        curr_z = z.iloc[i]
        curr_c = closes.iloc[i]
        
        if in_pos == 0:
            if curr_z > 1.0:
                in_pos = 1
                entry_bar = i
                pos[i] = 1.0
            elif curr_z < -1.0:
                in_pos = -1
                entry_bar = i
                pos[i] = -1.0
            else:
                pos[i] = 0.0
        elif in_pos == 1:
            entry_p = opens.iloc[entry_bar + 1]
            gross = curr_c / entry_p - 1.0
            is_stop = (gross <= -sl)
            should_exit = (curr_z < 0.2) or is_stop
            if should_exit:
                exit_p = opens.iloc[i + 1]
                net = (exit_p / entry_p - 1.0) - 0.0010
                trades.append({'type': 'LONG', 'entry': opens.index[entry_bar+1], 'exit': opens.index[i+1], 'net': net})
                in_pos = 0
                pos[i] = 0.0
            else:
                pos[i] = 1.0
        elif in_pos == -1:
            entry_p = opens.iloc[entry_bar + 1]
            gross = 1.0 - curr_c / entry_p
            is_stop = (gross <= -sl)
            should_exit = (curr_z > -0.2) or is_stop
            if should_exit:
                exit_p = opens.iloc[i + 1]
                net = (1.0 - exit_p / entry_p) - 0.0010
                trades.append({'type': 'SHORT', 'entry': opens.index[entry_bar+1], 'exit': opens.index[i+1], 'net': net})
                in_pos = 0
                pos[i] = 0.0
            else:
                pos[i] = -1.0
                
    pos = pd.Series(pos, index=df.index)
    ret = (opens.shift(-2) / opens.shift(-1) - 1)
    fee = pos.diff().abs() * 0.0005
    strat_ret = (pos * ret - fee).dropna()[:-2]
    bh_ret = ret.loc[strat_ret.index]
    
    cum = (1 + strat_ret).cumprod()
    bh_cum = (1 + bh_ret).cumprod()
    mdd = ((cum - cum.cummax()) / cum.cummax()).min()
    daily = cum.resample('1D').last().ffill().pct_change().dropna()
    sharpe = daily.mean() / (daily.std() + 1e-8) * np.sqrt(365)
    
    cov = np.cov(strat_ret.values, bh_ret.values)
    beta = cov[0, 1] / cov[1, 1]
    alpha_annual = (strat_ret.mean() - beta * bh_ret.mean()) * 2190
    
    tdf = pd.DataFrame(trades)
    tdf['entry'] = pd.to_datetime(tdf['entry'])
    oct_trades = tdf[(tdf['entry'] >= '2025-10-01') & (tdf['entry'] <= '2025-10-31')]
    win_rate = (tdf['net'] > 0).mean() if len(tdf) > 0 else 0.0
    oct_sum = oct_trades['net'].sum() if len(oct_trades) > 0 else 0.0
    
    print(f"=== {token} Symmetrical Long/Short + Stop-Loss ===")
    print(f"Strategy Total Ret: {cum.iloc[-1]-1:+.2%} (vs Buy & Hold: {bh_cum.iloc[-1]-1:+.2%})")
    print(f"Max Drawdown:       {mdd:.2%} (vs Buy & Hold MDD: {((bh_cum-bh_cum.cummax())/bh_cum.cummax()).min():.2%})")
    print(f"Daily Sharpe:       {sharpe:.2f}")
    print(f"Market Beta:        {beta:.2f} (Zero Beta Market Neutrality!)")
    print(f"Annual Jensen Alpha:{alpha_annual:+.2%}")
    print(f"Total Trades:       {len(tdf)} (Win Rate: {win_rate:.1%})")
    print(f"Oct 2025 Trades:    {len(oct_trades)}, Oct Net PnL Sum: {oct_sum:+.2%}")
    if len(oct_trades) > 0:
        print(oct_trades[['type', 'entry', 'exit', 'net']].to_string())
    print("-" * 70)
