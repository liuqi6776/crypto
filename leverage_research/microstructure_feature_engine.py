"""
Microstructure Feature Engine & Triple Barrier Labeler
======================================================
Implements institutional market microstructure features:
1. Multi-scale Order Flow Imbalance (OFI: 1m, 3m, 5m, 15m)
2. Trading Intensity & Relative Aggression
3. Cross-Asset Lead-Lag Signals (BTC -> ETH/SOL)
4. Volatility Regimes (ATR, Realized, Parkinson)
5. Vectorized Marcos López de Prado Triple Barrier Method Labeling
"""

import os
import sys
import numpy as np
import pandas as pd
import numba

@numba.jit(nopython=True)
def compute_dual_triple_barriers_numba(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    vol_scaled: np.ndarray,
    k_up: float,
    k_dn: float,
    max_stop_pct: float,
    horizon: int
):
    """
    Fast Numba JIT implementation of dual Long and Short Triple Barrier Method.
    Returns:
        long_labels, short_labels: 1 (TP hit first), -1 (SL hit first), 0 (Timeout)
        long_exit_rets, short_exit_rets: price return at exit for long and short
        long_touch_bars, short_touch_bars: duration in bars
    """
    n = len(close)
    long_labels = np.zeros(n, dtype=np.int8)
    short_labels = np.zeros(n, dtype=np.int8)
    long_touch_bars = np.zeros(n, dtype=np.int16)
    short_touch_bars = np.zeros(n, dtype=np.int16)
    long_exit_rets = np.zeros(n, dtype=np.float32)
    short_exit_rets = np.zeros(n, dtype=np.float32)

    for i in range(n - horizon):
        p0 = close[i]
        sigma = vol_scaled[i]
        
        dn_pct = min(k_dn * sigma, max_stop_pct)
        up_pct = max(k_up * sigma, dn_pct * k_up / k_dn)
        
        # Long barriers
        p_long_tp = p0 * (1.0 + up_pct)
        p_long_sl = p0 * (1.0 - dn_pct)
        
        # Short barriers
        p_short_tp = p0 * (1.0 - up_pct)
        p_short_sl = p0 * (1.0 + dn_pct)
        
        # 1. Resolve Long outcome
        l_status = 0
        l_hit_bar = horizon
        l_ret = (close[i + horizon] - p0) / p0
        
        for j in range(1, horizon + 1):
            idx = i + j
            h = high[idx]
            l = low[idx]
            hit_tp = h >= p_long_tp
            hit_sl = l <= p_long_sl
            
            if hit_tp and hit_sl:
                l_status = 1 if close[idx] >= p0 else -1
                l_ret = up_pct if l_status == 1 else -dn_pct
                l_hit_bar = j
                break
            elif hit_tp:
                l_status = 1
                l_ret = up_pct
                l_hit_bar = j
                break
            elif hit_sl:
                l_status = -1
                l_ret = -dn_pct
                l_hit_bar = j
                break
                
        long_labels[i] = l_status
        long_touch_bars[i] = l_hit_bar
        long_exit_rets[i] = l_ret

        # 2. Resolve Short outcome
        s_status = 0
        s_hit_bar = horizon
        s_ret = (p0 - close[i + horizon]) / p0
        
        for j in range(1, horizon + 1):
            idx = i + j
            h = high[idx]
            l = low[idx]
            hit_tp = l <= p_short_tp
            hit_sl = h >= p_short_sl
            
            if hit_tp and hit_sl:
                s_status = 1 if close[idx] <= p0 else -1
                s_ret = up_pct if s_status == 1 else -dn_pct
                s_hit_bar = j
                break
            elif hit_tp:
                s_status = 1
                s_ret = up_pct
                s_hit_bar = j
                break
            elif hit_sl:
                s_status = -1
                s_ret = -dn_pct
                s_hit_bar = j
                break
                
        short_labels[i] = s_status
        short_touch_bars[i] = s_hit_bar
        short_exit_rets[i] = s_ret

    return (long_labels, short_labels, long_touch_bars, short_touch_bars, long_exit_rets, short_exit_rets)


def build_microstructure_dataset(
    eth_path: str,
    btc_path: str,
    sol_path: str,
    k_up: float = 1.2,
    k_dn: float = 1.0,
    max_stop_pct: float = 0.012, # 1.2% hard max stop
    horizon: int = 15,
    sample_tail: int = None
) -> pd.DataFrame:
    """
    Loads continuous futures 1m data for ETH, BTC, and SOL, merges timestamps,
    computes multi-scale OFI and microstructure features, and labels using Triple Barrier Method.
    """
    print(f"[1/4] Loading continuous 1m datasets...")
    df_eth = pd.read_parquet(eth_path)
    df_btc = pd.read_parquet(btc_path)
    df_sol = pd.read_parquet(sol_path)
    
    if sample_tail is not None and sample_tail > 0:
        df_eth = df_eth.iloc[-sample_tail:].copy()
        df_btc = df_btc.iloc[-sample_tail:].copy()
        df_sol = df_sol.iloc[-sample_tail:].copy()

    print(f"  ETH bars: {len(df_eth):,}, BTC bars: {len(df_btc):,}, SOL bars: {len(df_sol):,}")

    # Prepare base ETH table
    df = pd.DataFrame({
        'timestamp': df_eth['timestamp'],
        'datetime': df_eth['datetime'],
        'open': df_eth['open'].astype(np.float32),
        'high': df_eth['high'].astype(np.float32),
        'low': df_eth['low'].astype(np.float32),
        'close': df_eth['close'].astype(np.float32),
        'volume': df_eth['volume'].astype(np.float32),
        'quote_volume': df_eth['quote_volume'].astype(np.float32),
        'trades_count': df_eth['trades_count'].astype(np.int32),
        'taker_buy_volume': df_eth['taker_buy_volume'].astype(np.float32),
        'taker_buy_quote_volume': df_eth['taker_buy_quote_volume'].astype(np.float32)
    })

    # Prepare BTC & SOL for join
    btc_sub = pd.DataFrame({
        'timestamp': df_btc['timestamp'],
        'btc_close': df_btc['close'].astype(np.float32),
        'btc_volume': df_btc['volume'].astype(np.float32),
        'btc_quote': df_btc['quote_volume'].astype(np.float32),
        'btc_taker_buy': df_btc['taker_buy_volume'].astype(np.float32)
    })

    sol_sub = pd.DataFrame({
        'timestamp': df_sol['timestamp'],
        'sol_close': df_sol['close'].astype(np.float32),
        'sol_volume': df_sol['volume'].astype(np.float32),
        'sol_quote': df_sol['quote_volume'].astype(np.float32),
        'sol_taker_buy': df_sol['taker_buy_volume'].astype(np.float32)
    })

    # Merge on timestamp
    df = df.merge(btc_sub, on='timestamp', how='inner')
    df = df.merge(sol_sub, on='timestamp', how='inner')
    df.sort_values('timestamp', inplace=True)
    df.reset_index(drop=True, inplace=True)

    print(f"[2/4] Constructing Microstructure & Order Flow (OFI) Features ({len(df):,} aligned bars)...")
    
    # 1. Taker flow & OFI for ETH
    taker_sell = df['volume'] - df['taker_buy_volume']
    net_taker = df['taker_buy_volume'] - taker_sell
    
    # Multi-scale OFI
    for w in [1, 3, 5, 15]:
        roll_net = net_taker.rolling(w).sum()
        roll_vol = df['volume'].rolling(w).sum().replace(0, np.nan)
        df[f'eth_ofi_{w}m'] = (roll_net / roll_vol).fillna(0.0).astype(np.float32)

    # Taker buy ratio
    df['eth_taker_buy_ratio'] = (df['taker_buy_volume'] / df['volume'].replace(0, np.nan)).fillna(0.5).astype(np.float32)

    # Trading intensity & relative aggression
    df['trade_intensity'] = (df['quote_volume'] / df['trades_count'].replace(0, np.nan)).fillna(0.0).astype(np.float32)
    intensity_sma20 = df['trade_intensity'].rolling(20).mean().replace(0, np.nan)
    df['rel_trade_intensity'] = (df['trade_intensity'] / intensity_sma20).fillna(1.0).astype(np.float32)

    # 2. BTC & SOL OFI and Lead-Lag Features
    btc_taker_sell = df['btc_volume'] - df['btc_taker_buy']
    btc_net = df['btc_taker_buy'] - btc_taker_sell
    df['btc_ofi_1m'] = (btc_net / df['btc_volume'].replace(0, np.nan)).fillna(0.0).astype(np.float32)
    df['btc_ofi_5m'] = (btc_net.rolling(5).sum() / df['btc_volume'].rolling(5).sum().replace(0, np.nan)).fillna(0.0).astype(np.float32)
    
    sol_taker_sell = df['sol_volume'] - df['sol_taker_buy']
    sol_net = df['sol_taker_buy'] - sol_taker_sell
    df['sol_ofi_1m'] = (sol_net / df['sol_volume'].replace(0, np.nan)).fillna(0.0).astype(np.float32)

    # Cross-Asset Returns & Spread (Lead-Lag)
    for w in [1, 3, 5, 10]:
        df[f'eth_ret_{w}m'] = df['close'].pct_change(w).fillna(0.0).astype(np.float32)
        df[f'btc_ret_{w}m'] = df['btc_close'].pct_change(w).fillna(0.0).astype(np.float32)
        df[f'sol_ret_{w}m'] = df['sol_close'].pct_change(w).fillna(0.0).astype(np.float32)
        # Lead-lag spreads: BTC leading ETH, SOL leading ETH
        df[f'btc_eth_lead_{w}m'] = (df[f'btc_ret_{w}m'] - df[f'eth_ret_{w}m']).astype(np.float32)
        df[f'sol_eth_lead_{w}m'] = (df[f'sol_ret_{w}m'] - df[f'eth_ret_{w}m']).astype(np.float32)

    # 3. Volatility Regimes
    prev_close = df['close'].shift(1)
    tr = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            np.abs(df['high'] - prev_close),
            np.abs(df['low'] - prev_close)
        )
    )
    df['atr_14'] = tr.rolling(14).mean().bfill().astype(np.float32)
    df['vol_pct'] = (df['atr_14'] / df['close']).astype(np.float32)
    df['btc_vol_pct'] = (df['btc_close'].pct_change().rolling(14).std() * np.sqrt(14)).bfill().astype(np.float32)
    
    # Parkinson High-Low Volatility estimator
    hl_ratio = np.log(df['high'] / df['low'].replace(0, np.nan)).fillna(0.0)
    df['parkinson_vol_15m'] = np.sqrt((hl_ratio ** 2).rolling(15).mean() / (4.0 * np.log(2.0))).bfill().astype(np.float32)

    print(f"[3/4] Vectorized Marcos López de Prado Dual Triple Barrier Labeling...")
    (
        long_labels, short_labels,
        long_touch_bars, short_touch_bars,
        long_exit_rets, short_exit_rets
    ) = compute_dual_triple_barriers_numba(
        close=df['close'].values.astype(np.float64),
        high=df['high'].values.astype(np.float64),
        low=df['low'].values.astype(np.float64),
        vol_scaled=df['vol_pct'].values.astype(np.float64),
        k_up=float(k_up),
        k_dn=float(k_dn),
        max_stop_pct=float(max_stop_pct),
        horizon=int(horizon)
    )

    df['tb_long_label'] = long_labels
    df['tb_long_touch_bars'] = long_touch_bars
    df['tb_long_exit_ret'] = long_exit_rets

    df['tb_short_label'] = short_labels
    df['tb_short_touch_bars'] = short_touch_bars
    df['tb_short_exit_ret'] = short_exit_rets

    # Trim warmup and horizon boundary
    valid_df = df.iloc[20:-horizon].copy().reset_index(drop=True)
    
    print(f"[4/4] Dataset ready! Total valid rows: {len(valid_df):,}")
    long_dist = valid_df['tb_long_label'].value_counts(normalize=True).to_dict()
    short_dist = valid_df['tb_short_label'].value_counts(normalize=True).to_dict()
    print(f"  Long Barrier Distribution:  TP(+1)={long_dist.get(1, 0)*100:.2f}%, SL(-1)={long_dist.get(-1, 0)*100:.2f}%, Timeout(0)={long_dist.get(0, 0)*100:.2f}%")
    print(f"  Short Barrier Distribution: TP(+1)={short_dist.get(1, 0)*100:.2f}%, SL(-1)={short_dist.get(-1, 0)*100:.2f}%, Timeout(0)={short_dist.get(0, 0)*100:.2f}%")
    
    return valid_df

if __name__ == '__main__':
    base_dir = r"d:\Convertible_Bond_data\crypto_data\history\futures_1m"
    eth_p = os.path.join(base_dir, "ETHUSDT_futures_1m_continuous.parquet")
    btc_p = os.path.join(base_dir, "BTCUSDT_futures_1m_continuous.parquet")
    sol_p = os.path.join(base_dir, "SOLUSDT_futures_1m_continuous.parquet")

    # Run on recent 300,000 bars (~208 days) for initial verification
    df_feat = build_microstructure_dataset(
        eth_path=eth_p,
        btc_path=btc_p,
        sol_path=sol_p,
        k_up=1.2,
        k_dn=1.0,
        max_stop_pct=0.012, # 1.2% hard stop
        horizon=15,
        sample_tail=300000
    )

    out_path = r"d:\Convertible_Bond_data\crypto_data\eth_microstructure_features.parquet"
    df_feat.to_parquet(out_path, index=False)
    print(f"[SAVED] Microstructure dataset -> {out_path} ({os.path.getsize(out_path)/1024/1024:.2f} MB)")
