import pandas as pd
import numpy as np

# Load TRB 1m klines during the crash
# We have 120 1m candles during peak crash
import requests
url = 'https://fapi.binance.com/fapi/v1/klines?symbol=TRBUSDT&interval=1m&startTime=1704054000000&limit=120'
r = requests.get(url).json()
df = pd.DataFrame(r, columns=['open_time', 'open', 'high', 'low', 'close', 'vol', 'close_time', 'q_vol', 'trades', 'tb_b', 'tb_q', 'ig'])
df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
for c in ['open', 'high', 'low', 'close']: df[c] = df[c].astype(float)

# In each 1-minute bar, if we enter a SHORT at open price:
# Let's see if the intra-minute upward wick (High - Open) triggers liquidation
# For leverage L:
# Initial margin = 1/L
# Maintenance margin rate MMR (approx 0.5% for Tier 1)
# Round-trip taker fee = 0.05% * 2 * L
# Liquidation occurs if: (High - Open) / Open >= (1/L - MMR)

leverage_list = [100, 50, 20, 10, 5, 3]

results = []
for L in leverage_list:
    im = 1.0 / L
    mmr = 0.005 # 0.5% MMR
    # Liq threshold: price rise against short that wipes out margin
    liq_dist_pct = (im - mmr) * 100
    if liq_dist_pct <= 0:
        liq_dist_pct = 0.1 # theoretical instant liq
    
    fee_pct_of_equity = 0.0005 * 2 * L * 100 # 0.05% entry + 0.05% exit on notional
    
    # Test across all 120 1m bars: if entered short at open, did the bar liquidate?
    liquidated_count = 0
    for idx, row in df.iterrows():
        wick_up_pct = (row['high'] - row['open']) / row['open'] * 100
        if wick_up_pct >= liq_dist_pct:
            liquidated_count += 1
            
    liq_rate = liquidated_count / len(df) * 100
    survival_rate = 100 - liq_rate
    
    results.append({
        '杠杆倍数': f"{L}x",
        '理论强平距离(反向波动)': f"{liq_dist_pct:.2f}%",
        '双边手续费(占本金比例)': f"{fee_pct_of_equity:.1f}%",
        '1分钟内被爆仓概率': f"{liq_rate:.1f}%",
        '1分钟幸存率': f"{survival_rate:.1f}%",
        '评价': '立即爆仓 / 必死' if liq_rate > 70 else ('极高风险' if liq_rate > 30 else '可控安全')
    })

res_df = pd.DataFrame(results)
print("=== TRB 崩盘实盘 1 分钟级别不同杠杆实测结果 ===")
print(res_df.to_string(index=False))
