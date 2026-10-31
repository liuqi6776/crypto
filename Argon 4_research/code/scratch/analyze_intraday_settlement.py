import requests
import pandas as pd
import numpy as np
import datetime

# Let's check 1h klines around extreme funding events
df_valid = pd.read_parquet('scratch/funding_dataset_with_returns.parquet')
extreme_neg = df_valid[df_valid['fundingRate'] <= -0.005].head(25)

print(f"Analyzing intraday behavior for {len(extreme_neg)} extreme negative funding events...")

intraday_results = []
for idx, row in extreme_neg.iterrows():
    sym = row['symbol']
    ft = row['fundingTime']
    ft_ms = int(ft.timestamp() * 1000)
    
    # Fetch 1h klines: 6 hours before to 6 hours after
    start_ms = ft_ms - 6 * 3600 * 1000
    end_ms = ft_ms + 6 * 3600 * 1000
    
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}&interval=1h&startTime={start_ms}&endTime={end_ms}&limit=20"
    try:
        res = requests.get(url, timeout=5).json()
        if isinstance(res, list) and len(res) >= 8:
            candles = pd.DataFrame(res, columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume', 
                'close_time', 'quote_volume', 'trades', 'taker_buy_base', 
                'taker_buy_quote', 'ignore'
            ])
            candles['open_time'] = pd.to_datetime(candles['open_time'], unit='ms')
            candles['close'] = candles['close'].astype(float)
            
            # Find candle closest to fundingTime
            settle_candles = candles[candles['open_time'] <= ft]
            if len(settle_candles) == 0:
                continue
            settle_candle = settle_candles.iloc[-1]
            p_settle = settle_candle['close']
            
            # Price 2 hours before
            p_before_2h = candles.iloc[0]['close']
            
            # Post settlement candles
            post_candles = candles[candles['open_time'] > ft]
            if len(post_candles) == 0:
                continue
            p_after_1h = post_candles.iloc[0]['close']
            p_after_4h = post_candles.iloc[min(3, len(post_candles)-1)]['close']
            
            ret_before = (p_settle / p_before_2h - 1) * 100
            ret_post_1h = (p_after_1h / p_settle - 1) * 100
            ret_post_4h = (p_after_4h / p_settle - 1) * 100
            
            intraday_results.append({
                'symbol': sym,
                'time': str(ft),
                'rate': f"{row['fundingRate']*100:.3f}%",
                'pre_pump%': f"{ret_before:+.2f}%",
                'post_1h%': f"{ret_post_1h:+.2f}%",
                'post_4h%': f"{ret_post_4h:+.2f}%",
                'num_post_1h': ret_post_1h,
                'num_post_4h': ret_post_4h,
                'num_pre': ret_before
            })
    except Exception as e:
        pass

df_intra = pd.DataFrame(intraday_results)
if len(df_intra) > 0:
    display_cols = ['symbol', 'time', 'rate', 'pre_pump%', 'post_1h%', 'post_4h%']
    print("\nIntraday Returns Around Funding Settlement (UTC 00:00 / 08:00 / 16:00):")
    print(df_intra[display_cols].to_string())
    print("\nSummary statistics:")
    print(f"Average Pre-settlement return (结算前数小时拉升均值): {df_intra['num_pre'].mean():+.2f}%")
    print(f"Average Post-settlement 1h return (结算后1小时走势均值): {df_intra['num_post_1h'].mean():+.2f}%")
    print(f"Average Post-settlement 4h return (结算后4小时走势均值): {df_intra['num_post_4h'].mean():+.2f}%")
    print(f"Post-settlement 1h drop probability (结算后1小时下跌概率): {(df_intra['num_post_1h'] < 0).mean()*100:.1f}%")
    print(f"Post-settlement 4h drop probability (结算后4小时下跌概率): {(df_intra['num_post_4h'] < 0).mean()*100:.1f}%")
