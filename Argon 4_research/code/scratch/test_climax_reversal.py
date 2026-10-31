import os
import glob
import pandas as pd
import numpy as np

files_15m = glob.glob('scratch/klines_15m/*.parquet')

results = []
for f in files_15m:
    df_15m = pd.read_parquet(f).sort_values('open_time').reset_index(drop=True)
    if len(df_15m) < 40:
        continue
    sym = os.path.basename(f).split('_')[0]
    
    # Identify highest peak
    peak_idx = df_15m['high'].idxmax()
    peak_high = df_15m.loc[peak_idx, 'high']
    peak_time = df_15m.loc[peak_idx, 'open_time']
    
    # Check if peak is at least 35% above the baseline low of previous 48 bars (12 hours)
    base_low = df_15m['low'].iloc[max(0, peak_idx-48):peak_idx].min()
    expansion = (peak_high / base_low) - 1.0
    if expansion < 0.35:
        continue
        
    # Check post-peak candles
    post_peak = df_15m.iloc[peak_idx:].copy().reset_index(drop=True)
    if len(post_peak) < 5:
        continue
        
    # Find the trough after peak
    # Look at first 12 bars after peak (3 hours)
    trough_idx = post_peak['low'].iloc[1:min(16, len(post_peak))].idxmin()
    trough_low = post_peak.loc[trough_idx, 'low']
    
    # Breakdown occurs when a candle closes below trough_low
    breakdown_candles = post_peak.iloc[trough_idx+1:][post_peak.iloc[trough_idx+1:]['close'] < trough_low]
    if len(breakdown_candles) > 0:
        entry_candle = breakdown_candles.iloc[0]
        entry_price = entry_candle['close']
        entry_time = entry_candle['open_time']
        
        # Check forward performance in post_peak
        entry_idx = entry_candle.name
        remaining = post_peak.iloc[entry_idx:]
        min_price = remaining['low'].min()
        max_price_against = remaining['high'].max() # worst adverse excursion
        final_price = remaining.iloc[min(32, len(remaining)-1)]['close'] # 8 hours later
        
        ret_gain = (entry_price - min_price) / entry_price * 100
        max_drawdown = (max_price_against - entry_price) / entry_price * 100
        ret_8h = (entry_price - final_price) / entry_price * 100
        
        results.append({
            'symbol': sym,
            'peak_time': peak_time,
            'peak_price': peak_high,
            'entry_time': entry_time,
            'entry_price': entry_price,
            'min_price': min_price,
            'max_gain': ret_gain,
            'max_dd': max_drawdown,
            'ret_8h': ret_8h,
            'win': 'WIN' if ret_8h > 0 else 'LOSS'
        })

df_res = pd.DataFrame(results)
print("=== Climax Exhaustion + Neckline Breakdown (15m Macro Confirmation) ===")
print(df_res.to_string(index=False))
if len(df_res) > 0:
    print(f"\nWin Rate: {(df_res['ret_8h'] > 0).mean()*100:.1f}%")
    print(f"Average 8h Short Return: {df_res['ret_8h'].mean():+.1f}%")
    print(f"Average Max Gain: {df_res['max_gain'].mean():+.1f}%")
    print(f"Average Drawdown: {df_res['max_dd'].mean():.1f}%")
