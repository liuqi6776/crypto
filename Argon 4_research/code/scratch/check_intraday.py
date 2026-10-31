import requests
import pandas as pd
import numpy as np

# Let's inspect 15-min klines for a token with extreme negative funding around settlement
# For example, ARKUSDT on 2026-09-13 or ONEUSDT on 2026-09-17 or TRB on 2023-12-31
# Let's fetch 15m candles around ONEUSDT 2026-09-17 or ARKUSDT 2026-09-13
# Timestamp for 2026-09-17 16:00:00 is around 1789660800000

url = "https://fapi.binance.com/fapi/v1/klines?symbol=ARKUSDT&interval=15m&limit=100"
r = requests.get(url).json()
if isinstance(r, list) and len(r) > 0:
    df_k = pd.DataFrame(r, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume', 
        'close_time', 'quote_volume', 'trades', 'taker_buy_base', 
        'taker_buy_quote', 'ignore'
    ])
    df_k['close'] = df_k['close'].astype(float)
    df_k['open_time'] = pd.to_datetime(df_k['open_time'], unit='ms')
    df_k['ma7'] = df_k['close'].rolling(7).mean()
    df_k['ma25'] = df_k['close'].rolling(25).mean()
    print("Recent 15m ARK candles:")
    print(df_k[['open_time', 'open', 'high', 'low', 'close', 'ma7', 'ma25']].tail(10))
