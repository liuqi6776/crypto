"""
Multi-Exchange Crypto Data Collector (Binance, OKX, Bitget)
多交易所加密衍生品数据采集器（币安、OKX、Bitget）

Target Assets: ETH, BTC, SOL (USDT-Margined Perpetual Swaps)
Data Dimensions:
1. Price & Volume (1m, 5m OHLCV, Trades, Turnover, Taker Buy/Sell)
2. Order Book Depth & Microstructure (L2 Depth, Spread, OBI, Micro-price, Depth Ratios)
3. Directional Alpha Metrics (Open Interest, Funding Rate, Long/Short Ratio, Taker Flow)
"""

import os
import sys
import json
import time
import argparse
import datetime
import urllib.request
import urllib.error
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional

DEFAULT_PROXIES = {
    'http': 'http://127.0.0.1:7897',
    'https': 'http://127.0.0.1:7897'
}

class BaseClient:
    def __init__(self, proxy_url: Optional[str] = "http://127.0.0.1:7897", timeout: int = 10):
        self.timeout = timeout
        if proxy_url:
            self.opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url})
            )
        else:
            self.opener = urllib.request.build_opener()

    def get_json(self, url: str) -> Any:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json'
            }
        )
        for attempt in range(3):
            try:
                with self.opener.open(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode('utf-8'))
            except urllib.error.HTTPError as e:
                if attempt == 2:
                    raise
                time.sleep(1.0 * (attempt + 1))
            except Exception as e:
                if attempt == 2:
                    raise
                time.sleep(1.0 * (attempt + 1))


class BinanceFuturesCollector(BaseClient):
    BASE_URL = "https://fapi.binance.com"

    SYMBOL_MAP = {
        'BTC': 'BTCUSDT',
        'ETH': 'ETHUSDT',
        'SOL': 'SOLUSDT'
    }

    def fetch_klines(self, asset: str, interval: str = '1m', total_limit: int = 1500) -> pd.DataFrame:
        symbol = self.SYMBOL_MAP[asset]
        url = f"{self.BASE_URL}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={min(total_limit, 1500)}"
        raw = self.get_json(url)
        
        columns = [
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades_count',
            'taker_buy_base_volume', 'taker_buy_quote_volume', 'ignore'
        ]
        df = pd.DataFrame(raw, columns=columns)
        
        # Convert types
        df['timestamp'] = pd.to_numeric(df['open_time'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert('Asia/Shanghai').dt.strftime('%Y-%m-%d %H:%M:%S')
        for col in ['open', 'high', 'low', 'close', 'volume', 'quote_volume', 'taker_buy_base_volume', 'taker_buy_quote_volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df['trades_count'] = pd.to_numeric(df['trades_count'], errors='coerce')
        
        df = df[['timestamp', 'datetime', 'open', 'high', 'low', 'close', 'volume', 'quote_volume', 'trades_count', 'taker_buy_base_volume', 'taker_buy_quote_volume']]
        df = df.sort_values('timestamp').reset_index(drop=True)
        return df

    def fetch_depth(self, asset: str, limit: int = 100) -> Dict[str, Any]:
        symbol = self.SYMBOL_MAP[asset]
        url = f"{self.BASE_URL}/fapi/v1/depth?symbol={symbol}&limit={limit}"
        return self.get_json(url)

    def fetch_open_interest_hist(self, asset: str, period: str = '5m', limit: int = 500) -> pd.DataFrame:
        symbol = self.SYMBOL_MAP[asset]
        url = f"{self.BASE_URL}/futures/data/openInterestHist?symbol={symbol}&period={period}&limit={limit}"
        raw = self.get_json(url)
        df = pd.DataFrame(raw)
        if not df.empty:
            df['timestamp'] = pd.to_numeric(df['timestamp'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert('Asia/Shanghai').dt.strftime('%Y-%m-%d %H:%M:%S')
            df['sumOpenInterest'] = pd.to_numeric(df['sumOpenInterest'], errors='coerce')
            df['sumOpenInterestValue'] = pd.to_numeric(df['sumOpenInterestValue'], errors='coerce')
        return df

    def fetch_long_short_ratio(self, asset: str, period: str = '5m', limit: int = 500) -> pd.DataFrame:
        symbol = self.SYMBOL_MAP[asset]
        url = f"{self.BASE_URL}/futures/data/globalLongShortAccountRatio?symbol={symbol}&period={period}&limit={limit}"
        raw = self.get_json(url)
        df = pd.DataFrame(raw)
        if not df.empty:
            df['timestamp'] = pd.to_numeric(df['timestamp'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert('Asia/Shanghai').dt.strftime('%Y-%m-%d %H:%M:%S')
            df['longShortRatio'] = pd.to_numeric(df['longShortRatio'], errors='coerce')
            df['longAccount'] = pd.to_numeric(df['longAccount'], errors='coerce')
            df['shortAccount'] = pd.to_numeric(df['shortAccount'], errors='coerce')
        return df

    def fetch_top_trader_ratio(self, asset: str, period: str = '5m', limit: int = 500) -> pd.DataFrame:
        symbol = self.SYMBOL_MAP[asset]
        url = f"{self.BASE_URL}/futures/data/topLongShortPositionRatio?symbol={symbol}&period={period}&limit={limit}"
        raw = self.get_json(url)
        df = pd.DataFrame(raw)
        if not df.empty:
            df['timestamp'] = pd.to_numeric(df['timestamp'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert('Asia/Shanghai').dt.strftime('%Y-%m-%d %H:%M:%S')
            df['longShortRatio'] = pd.to_numeric(df.get('longShortRatio', 0), errors='coerce')
            pos_col = 'longPosition' if 'longPosition' in df.columns else 'longAccount'
            neg_col = 'shortPosition' if 'shortPosition' in df.columns else 'shortAccount'
            df['longAccount'] = pd.to_numeric(df.get(pos_col, 0), errors='coerce')
            df['shortAccount'] = pd.to_numeric(df.get(neg_col, 0), errors='coerce')
        return df

    def fetch_taker_ratio(self, asset: str, period: str = '5m', limit: int = 500) -> pd.DataFrame:
        symbol = self.SYMBOL_MAP[asset]
        url = f"{self.BASE_URL}/futures/data/takerlongshortRatio?symbol={symbol}&period={period}&limit={limit}"
        raw = self.get_json(url)
        df = pd.DataFrame(raw)
        if not df.empty:
            df['timestamp'] = pd.to_numeric(df['timestamp'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert('Asia/Shanghai').dt.strftime('%Y-%m-%d %H:%M:%S')
            df['buySellRatio'] = pd.to_numeric(df['buySellRatio'], errors='coerce')
            df['buyVol'] = pd.to_numeric(df['buyVol'], errors='coerce')
            df['sellVol'] = pd.to_numeric(df['sellVol'], errors='coerce')
        return df

    def fetch_funding_rate(self, asset: str, limit: int = 100) -> pd.DataFrame:
        symbol = self.SYMBOL_MAP[asset]
        url = f"{self.BASE_URL}/fapi/v1/fundingRate?symbol={symbol}&limit={limit}"
        raw = self.get_json(url)
        df = pd.DataFrame(raw)
        if not df.empty:
            df['fundingTime'] = pd.to_numeric(df['fundingTime'])
            df['datetime'] = pd.to_datetime(df['fundingTime'], unit='ms', utc=True).dt.tz_convert('Asia/Shanghai').dt.strftime('%Y-%m-%d %H:%M:%S')
            df['fundingRate'] = pd.to_numeric(df['fundingRate'], errors='coerce')
            df['markPrice'] = pd.to_numeric(df.get('markPrice', 0), errors='coerce')
        return df


class OKXFuturesCollector(BaseClient):
    BASE_URL = "https://www.okx.com"

    SYMBOL_MAP = {
        'BTC': 'BTC-USDT-SWAP',
        'ETH': 'ETH-USDT-SWAP',
        'SOL': 'SOL-USDT-SWAP'
    }

    def fetch_klines(self, asset: str, interval: str = '1m', limit: int = 300) -> pd.DataFrame:
        inst_id = self.SYMBOL_MAP[asset]
        bar = '1m' if interval == '1m' else '5m'
        url = f"{self.BASE_URL}/api/v5/market/candles?instId={inst_id}&bar={bar}&limit={min(limit, 300)}"
        res = self.get_json(url)
        raw = res.get('data', [])
        
        # [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
        cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'quote_volume', 'vol_quote2', 'confirm']
        df = pd.DataFrame(raw, columns=cols[:len(raw[0])] if raw else cols)
        if not df.empty:
            df['timestamp'] = pd.to_numeric(df['timestamp'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert('Asia/Shanghai').dt.strftime('%Y-%m-%d %H:%M:%S')
            for c in ['open', 'high', 'low', 'close', 'volume', 'quote_volume']:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors='coerce')
            df = df.sort_values('timestamp').reset_index(drop=True)
            df = df[['timestamp', 'datetime', 'open', 'high', 'low', 'close', 'volume', 'quote_volume']]
        return df

    def fetch_depth(self, asset: str, limit: int = 100) -> Dict[str, Any]:
        inst_id = self.SYMBOL_MAP[asset]
        url = f"{self.BASE_URL}/api/v5/market/books?instId={inst_id}&sz={limit}"
        res = self.get_json(url)
        data = res.get('data', [{}])[0]
        return data

    def fetch_open_interest(self, asset: str) -> pd.DataFrame:
        inst_id = self.SYMBOL_MAP[asset]
        url = f"{self.BASE_URL}/api/v5/public/open-interest?instType=SWAP&instId={inst_id}"
        res = self.get_json(url)
        df = pd.DataFrame(res.get('data', []))
        if not df.empty:
            df['timestamp'] = pd.to_numeric(df['ts'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert('Asia/Shanghai').dt.strftime('%Y-%m-%d %H:%M:%S')
            df['oi'] = pd.to_numeric(df['oi'], errors='coerce')
            df['oiUsd'] = pd.to_numeric(df['oiUsd'], errors='coerce')
        return df

    def fetch_funding_rate_history(self, asset: str, limit: int = 100) -> pd.DataFrame:
        inst_id = self.SYMBOL_MAP[asset]
        url = f"{self.BASE_URL}/api/v5/public/funding-rate-history?instId={inst_id}&limit={limit}"
        res = self.get_json(url)
        df = pd.DataFrame(res.get('data', []))
        if not df.empty:
            df['timestamp'] = pd.to_numeric(df['fundingTime'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert('Asia/Shanghai').dt.strftime('%Y-%m-%d %H:%M:%S')
            df['fundingRate'] = pd.to_numeric(df['fundingRate'], errors='coerce')
            df['realizedRate'] = pd.to_numeric(df['realizedRate'], errors='coerce')
        return df

    def fetch_long_short_ratio(self, asset: str, period: str = '5m') -> pd.DataFrame:
        url = f"{self.BASE_URL}/api/v5/rubik/stat/contracts/long-short-account-ratio?ccy={asset}&period={period}"
        res = self.get_json(url)
        raw = res.get('data', [])
        df = pd.DataFrame(raw, columns=['timestamp', 'long_short_ratio'])
        if not df.empty:
            df['timestamp'] = pd.to_numeric(df['timestamp'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert('Asia/Shanghai').dt.strftime('%Y-%m-%d %H:%M:%S')
            df['long_short_ratio'] = pd.to_numeric(df['long_short_ratio'], errors='coerce')
            df = df.sort_values('timestamp').reset_index(drop=True)
        return df

    def fetch_taker_volume(self, asset: str, period: str = '5m') -> pd.DataFrame:
        url = f"{self.BASE_URL}/api/v5/rubik/stat/taker-volume?ccy={asset}&instType=CONTRACTS&period={period}"
        res = self.get_json(url)
        raw = res.get('data', [])
        df = pd.DataFrame(raw, columns=['timestamp', 'buy_vol', 'sell_vol'])
        if not df.empty:
            df['timestamp'] = pd.to_numeric(df['timestamp'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert('Asia/Shanghai').dt.strftime('%Y-%m-%d %H:%M:%S')
            df['buy_vol'] = pd.to_numeric(df['buy_vol'], errors='coerce')
            df['sell_vol'] = pd.to_numeric(df['sell_vol'], errors='coerce')
            df['buy_sell_ratio'] = df['buy_vol'] / df['sell_vol'].replace(0, np.nan)
            df = df.sort_values('timestamp').reset_index(drop=True)
        return df


class BitgetFuturesCollector(BaseClient):
    BASE_URL = "https://api.bitget.com"

    SYMBOL_MAP = {
        'BTC': 'BTCUSDT',
        'ETH': 'ETHUSDT',
        'SOL': 'SOLUSDT'
    }

    def fetch_klines(self, asset: str, interval: str = '1m', limit: int = 1000) -> pd.DataFrame:
        symbol = self.SYMBOL_MAP[asset]
        granularity = '1m' if interval == '1m' else '5m'
        url = f"{self.BASE_URL}/api/v2/mix/market/candles?symbol={symbol}&productType=USDT-FUTURES&granularity={granularity}&limit={limit}"
        res = self.get_json(url)
        raw = res.get('data', [])
        
        # [timestamp, open, high, low, close, volume_base, volume_quote]
        cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'quote_volume']
        df = pd.DataFrame(raw, columns=cols)
        if not df.empty:
            df['timestamp'] = pd.to_numeric(df['timestamp'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert('Asia/Shanghai').dt.strftime('%Y-%m-%d %H:%M:%S')
            for c in ['open', 'high', 'low', 'close', 'volume', 'quote_volume']:
                df[c] = pd.to_numeric(df[c], errors='coerce')
            df = df.sort_values('timestamp').reset_index(drop=True)
            df = df[['timestamp', 'datetime', 'open', 'high', 'low', 'close', 'volume', 'quote_volume']]
        return df

    def fetch_depth(self, asset: str, limit: int = 100) -> Dict[str, Any]:
        symbol = self.SYMBOL_MAP[asset]
        url = f"{self.BASE_URL}/api/v2/mix/market/merge-depth?symbol={symbol}&productType=USDT-FUTURES&limit={limit}"
        res = self.get_json(url)
        return res.get('data', {})

    def fetch_open_interest(self, asset: str) -> pd.DataFrame:
        symbol = self.SYMBOL_MAP[asset]
        url = f"{self.BASE_URL}/api/v2/mix/market/open-interest?symbol={symbol}&productType=USDT-FUTURES"
        res = self.get_json(url)
        items = res.get('data', {}).get('openInterestList', [])
        df = pd.DataFrame(items)
        if not df.empty:
            df['timestamp'] = int(res.get('data', {}).get('ts', time.time()*1000))
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert('Asia/Shanghai').dt.strftime('%Y-%m-%d %H:%M:%S')
            df['size'] = pd.to_numeric(df['size'], errors='coerce')
        return df

    def fetch_funding_rate_history(self, asset: str, limit: int = 100) -> pd.DataFrame:
        symbol = self.SYMBOL_MAP[asset]
        url = f"{self.BASE_URL}/api/v2/mix/market/history-fund-rate?symbol={symbol}&productType=USDT-FUTURES&pageSize={limit}"
        res = self.get_json(url)
        df = pd.DataFrame(res.get('data', []))
        if not df.empty:
            df['timestamp'] = pd.to_numeric(df['fundingTime'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert('Asia/Shanghai').dt.strftime('%Y-%m-%d %H:%M:%S')
            df['fundingRate'] = pd.to_numeric(df['fundingRate'], errors='coerce')
        return df

    def fetch_long_short_ratio(self, asset: str, period: str = '5m') -> pd.DataFrame:
        symbol = self.SYMBOL_MAP[asset]
        url = f"{self.BASE_URL}/api/v2/mix/market/account-long-short?symbol={symbol}&productType=USDT-FUTURES&period={period}"
        res = self.get_json(url)
        df = pd.DataFrame(res.get('data', []))
        if not df.empty:
            df['timestamp'] = pd.to_numeric(df['ts'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert('Asia/Shanghai').dt.strftime('%Y-%m-%d %H:%M:%S')
            df['longShortAccountRatio'] = pd.to_numeric(df['longShortAccountRatio'], errors='coerce')
            df['longAccountRatio'] = pd.to_numeric(df['longAccountRatio'], errors='coerce')
            df['shortAccountRatio'] = pd.to_numeric(df['shortAccountRatio'], errors='coerce')
            df = df.sort_values('timestamp').reset_index(drop=True)
        return df


def calculate_orderbook_features(bids: List[List[Any]], asks: List[List[Any]], exchange: str, asset: str) -> Dict[str, Any]:
    """
    Compute order book microstructure features from raw bids and asks.
    """
    if not bids or not asks:
        return {}

    bids_parsed = [(float(b[0]), float(b[1])) for b in bids]
    asks_parsed = [(float(a[0]), float(a[1])) for a in asks]

    bids_parsed.sort(key=lambda x: x[0], reverse=True)
    asks_parsed.sort(key=lambda x: x[0], reverse=False)

    bid1_price, bid1_qty = bids_parsed[0]
    ask1_price, ask1_qty = asks_parsed[0]
    mid_price = (bid1_price + ask1_price) / 2.0
    spread = ask1_price - bid1_price
    spread_bps = (spread / mid_price) * 10000.0 if mid_price > 0 else 0.0

    # Micro-price (weighted by opposite side queue)
    if (bid1_qty + ask1_qty) > 0:
        micro_price = (bid1_price * ask1_qty + ask1_price * bid1_qty) / (bid1_qty + ask1_qty)
    else:
        micro_price = mid_price

    features = {
        'exchange': exchange,
        'asset': asset,
        'timestamp': int(time.time() * 1000),
        'datetime': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'bid1_price': bid1_price,
        'bid1_qty': bid1_qty,
        'ask1_price': ask1_price,
        'ask1_qty': ask1_qty,
        'mid_price': mid_price,
        'spread': spread,
        'spread_bps': spread_bps,
        'micro_price': micro_price,
    }

    # Depths & Order Book Imbalance (OBI) at various levels
    for k in [5, 10, 20, 50, 100]:
        k_bids = bids_parsed[:k]
        k_asks = asks_parsed[:k]
        bid_vol = sum(q for _, q in k_bids)
        ask_vol = sum(q for _, q in k_asks)
        bid_notional = sum(p * q for p, q in k_bids)
        ask_notional = sum(p * q for p, q in k_asks)

        obi = (bid_vol - ask_vol) / (bid_vol + ask_vol) if (bid_vol + ask_vol) > 0 else 0.0
        depth_ratio = (bid_notional / ask_notional) if ask_notional > 0 else 1.0

        features[f'bid_vol_{k}'] = bid_vol
        features[f'ask_vol_{k}'] = ask_vol
        features[f'bid_notional_{k}'] = bid_notional
        features[f'ask_notional_{k}'] = ask_notional
        features[f'obi_{k}'] = obi
        features[f'depth_ratio_{k}'] = depth_ratio

    return features


def save_dataset(df: pd.DataFrame, base_dir: str, prefix: str):
    if df is None or df.empty:
        return
    os.makedirs(base_dir, exist_ok=True)
    csv_path = os.path.join(base_dir, f"{prefix}.csv")
    parquet_path = os.path.join(base_dir, f"{prefix}.parquet")
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    df.to_parquet(parquet_path, index=False)
    print(f"  [Saved] {prefix}: {len(df)} rows -> {csv_path} & .parquet")


def run_collection(output_dir: str, proxy: str):
    assets = ['ETH', 'BTC', 'SOL']
    intervals = ['1m', '5m']

    print(f"=== Starting Multi-Exchange Crypto Data Ingestion ===")
    print(f"Target Assets: {assets}")
    print(f"Intervals: {intervals}")
    print(f"Proxy: {proxy}")
    print(f"Output Directory: {output_dir}")

    binance = BinanceFuturesCollector(proxy_url=proxy)
    okx = OKXFuturesCollector(proxy_url=proxy)
    bitget = BitgetFuturesCollector(proxy_url=proxy)

    all_ob_features = []

    for asset in assets:
        print(f"\n==================== [{asset}] ====================")

        # ---------------- 1. BINANCE ----------------
        print(f"\n--- Collecting Binance: {asset} ---")
        bn_dir = os.path.join(output_dir, 'binance', asset)
        try:
            for itv in intervals:
                df_kline = binance.fetch_klines(asset, interval=itv, total_limit=1500)
                save_dataset(df_kline, bn_dir, f"{asset}_binance_{itv}")

            # Depth & Microstructure
            depth_raw = binance.fetch_depth(asset, limit=100)
            depth_file = os.path.join(bn_dir, f"{asset}_depth_snapshot.json")
            os.makedirs(bn_dir, exist_ok=True)
            with open(depth_file, 'w', encoding='utf-8') as f:
                json.dump(depth_raw, f, indent=2)
            ob_feat = calculate_orderbook_features(depth_raw.get('bids', []), depth_raw.get('asks', []), 'binance', asset)
            if ob_feat:
                all_ob_features.append(ob_feat)
                save_dataset(pd.DataFrame([ob_feat]), bn_dir, f"{asset}_orderbook_features")

            # Directional Alpha
            df_oi = binance.fetch_open_interest_hist(asset, period='5m', limit=500)
            save_dataset(df_oi, bn_dir, f"{asset}_open_interest_5m")

            df_ls = binance.fetch_long_short_ratio(asset, period='5m', limit=500)
            save_dataset(df_ls, bn_dir, f"{asset}_global_long_short_ratio_5m")

            df_top = binance.fetch_top_trader_ratio(asset, period='5m', limit=500)
            save_dataset(df_top, bn_dir, f"{asset}_top_trader_ratio_5m")

            df_taker = binance.fetch_taker_ratio(asset, period='5m', limit=500)
            save_dataset(df_taker, bn_dir, f"{asset}_taker_long_short_ratio_5m")

            df_funding = binance.fetch_funding_rate(asset, limit=100)
            save_dataset(df_funding, bn_dir, f"{asset}_funding_rate_hist")

        except Exception as e:
            print(f"Error collecting Binance {asset}: {e}")

        # ---------------- 2. OKX ----------------
        print(f"\n--- Collecting OKX: {asset} ---")
        okx_dir = os.path.join(output_dir, 'okx', asset)
        try:
            for itv in intervals:
                df_kline = okx.fetch_klines(asset, interval=itv, limit=300)
                save_dataset(df_kline, okx_dir, f"{asset}_okx_{itv}")

            # Depth & Microstructure
            depth_raw = okx.fetch_depth(asset, limit=100)
            depth_file = os.path.join(okx_dir, f"{asset}_depth_snapshot.json")
            os.makedirs(okx_dir, exist_ok=True)
            with open(depth_file, 'w', encoding='utf-8') as f:
                json.dump(depth_raw, f, indent=2)
            ob_feat = calculate_orderbook_features(depth_raw.get('bids', []), depth_raw.get('asks', []), 'okx', asset)
            if ob_feat:
                all_ob_features.append(ob_feat)
                save_dataset(pd.DataFrame([ob_feat]), okx_dir, f"{asset}_orderbook_features")

            # Directional Alpha
            df_oi = okx.fetch_open_interest(asset)
            save_dataset(df_oi, okx_dir, f"{asset}_open_interest")

            df_funding = okx.fetch_funding_rate_history(asset, limit=100)
            save_dataset(df_funding, okx_dir, f"{asset}_funding_rate_hist")

            df_ls = okx.fetch_long_short_ratio(asset, period='5m')
            save_dataset(df_ls, okx_dir, f"{asset}_long_short_ratio_5m")

            df_taker = okx.fetch_taker_volume(asset, period='5m')
            save_dataset(df_taker, okx_dir, f"{asset}_taker_volume_5m")

        except Exception as e:
            print(f"Error collecting OKX {asset}: {e}")

        # ---------------- 3. BITGET ----------------
        print(f"\n--- Collecting Bitget: {asset} ---")
        bitget_dir = os.path.join(output_dir, 'bitget', asset)
        try:
            for itv in intervals:
                df_kline = bitget.fetch_klines(asset, interval=itv, limit=1000)
                save_dataset(df_kline, bitget_dir, f"{asset}_bitget_{itv}")

            # Depth & Microstructure
            depth_raw = bitget.fetch_depth(asset, limit=100)
            depth_file = os.path.join(bitget_dir, f"{asset}_depth_snapshot.json")
            os.makedirs(bitget_dir, exist_ok=True)
            with open(depth_file, 'w', encoding='utf-8') as f:
                json.dump(depth_raw, f, indent=2)
            ob_feat = calculate_orderbook_features(depth_raw.get('bids', []), depth_raw.get('asks', []), 'bitget', asset)
            if ob_feat:
                all_ob_features.append(ob_feat)
                save_dataset(pd.DataFrame([ob_feat]), bitget_dir, f"{asset}_orderbook_features")

            # Directional Alpha
            df_oi = bitget.fetch_open_interest(asset)
            save_dataset(df_oi, bitget_dir, f"{asset}_open_interest")

            df_funding = bitget.fetch_funding_rate_history(asset, limit=100)
            save_dataset(df_funding, bitget_dir, f"{asset}_funding_rate_hist")

            df_ls = bitget.fetch_long_short_ratio(asset, period='5m')
            save_dataset(df_ls, bitget_dir, f"{asset}_long_short_ratio_5m")

        except Exception as e:
            print(f"Error collecting Bitget {asset}: {e}")

    # Summary of cross-exchange orderbook features
    if all_ob_features:
        summary_df = pd.DataFrame(all_ob_features)
        summary_file = os.path.join(output_dir, "cross_exchange_orderbook_summary")
        save_dataset(summary_df, output_dir, "cross_exchange_orderbook_summary")
        print("\n=== Order Book Microstructure Comparison Summary ===")
        display_cols = ['exchange', 'asset', 'mid_price', 'spread_bps', 'micro_price', 'obi_20', 'depth_ratio_20']
        print(summary_df[display_cols].to_string(index=False))

    print("\n[SUCCESS] All multi-exchange crypto datasets collected successfully!")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Multi-Exchange Crypto Data Collector")
    parser.add_argument('--output-dir', type=str, default=r"d:\Convertible_Bond_data\crypto_data")
    parser.add_argument('--proxy', type=str, default="http://127.0.0.1:7897")
    args = parser.parse_args()

    run_collection(args.output_dir, args.proxy)
