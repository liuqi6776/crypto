# -*- coding: utf-8 -*-
"""
Support & Resistance (S/R) & Multi-Timeframe Trend Engine
动态支撑/阻力位与多周期趋势引擎
- Computes structural fractal swing highs & lows (缠论顶分型/底分型)
- Identifies Volume Profile High-Volume Nodes (HVN 筹码密集区)
- Classifies structural trend regime (BULLISH, BEARISH, CHOPPY/RANGING)
- Supplies dynamic S1, S2, R1, R2 for anchoring 20X TP/SL
"""

from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd


class SupportResistanceEngine:
    """
    Extracts structural support and resistance levels and classifies trend regime
    """
    def __init__(self, fractal_window: int = 5, volume_bins: int = 40):
        self.fractal_window = fractal_window
        self.volume_bins = volume_bins

    @staticmethod
    def classify_trend(df: pd.DataFrame) -> Dict[str, any]:
        """
        Classifies the trend regime using EMA stack, ATR-SuperTrend, and directional momentum.
        Returns:
            {
                'regime': 'BULLISH' | 'BEARISH' | 'CHOPPY',
                'ema_20': float,
                'ema_50': float,
                'ema_slope': float,
                'supertrend_dir': 1 (Bull) | -1 (Bear),
                'adx': float,
                'volatility_atr_pct': float
            }
        """
        c = df['close']
        h = df['high']
        l = df['low']
        
        if len(df) < 50:
            return {'regime': 'CHOPPY', 'supertrend_dir': 0, 'adx': 15.0, 'ema_slope': 0.0}
        
        # 1. EMAs
        ema_20 = c.ewm(span=20, adjust=False).mean()
        ema_50 = c.ewm(span=50, adjust=False).mean()
        ema_slope = (ema_20.iloc[-1] - ema_20.iloc[-5]) / ema_20.iloc[-5] * 100.0
        
        # 2. ATR
        tr1 = h - l
        tr2 = (h - c.shift(1)).abs()
        tr3 = (l - c.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_14 = tr.rolling(14).mean()
        curr_atr = atr_14.iloc[-1] if not np.isnan(atr_14.iloc[-1]) else (h.iloc[-1] - l.iloc[-1])
        atr_pct = (curr_atr / c.iloc[-1]) * 100.0
        
        # 3. SuperTrend proxy
        hl2 = (h + l) / 2.0
        upper_band = hl2 + 2.5 * atr_14
        lower_band = hl2 - 2.5 * atr_14
        
        # 4. ADX Directional Index
        up_move = h - h.shift(1)
        down_move = l.shift(1) - l
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        
        plus_di = 100.0 * (pd.Series(plus_dm).rolling(14).mean() / atr_14)
        minus_di = 100.0 * (pd.Series(minus_dm).rolling(14).mean() / atr_14)
        dx = 100.0 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
        adx = dx.rolling(14).mean().iloc[-1]
        if np.isnan(adx):
            adx = 20.0
        
        # Trend Regime Classification
        curr_c = c.iloc[-1]
        curr_e20 = ema_20.iloc[-1]
        curr_e50 = ema_50.iloc[-1]
        
        if curr_c > curr_e20 > curr_e50 and ema_slope > 0.03 and adx >= 20.0:
            regime = 'BULLISH'
            st_dir = 1
        elif curr_c < curr_e20 < curr_e50 and ema_slope < -0.03 and adx >= 20.0:
            regime = 'BEARISH'
            st_dir = -1
        else:
            regime = 'CHOPPY'
            st_dir = 0
            
        return {
            'regime': regime,
            'ema_20': curr_e20,
            'ema_50': curr_e50,
            'ema_slope': ema_slope,
            'supertrend_dir': st_dir,
            'adx': adx,
            'atr_pct': atr_pct
        }

    def detect_pivots(self, df: pd.DataFrame) -> Tuple[List[float], List[float]]:
        """
        Detects fractal Swing Highs (Resistance candidates) and Swing Lows (Support candidates)
        """
        h = df['high'].values
        l = df['low'].values
        n = len(df)
        w = self.fractal_window
        
        swing_highs = []
        swing_lows = []
        
        for i in range(w, n - w):
            # Swing High: Highest among w bars before and after
            if h[i] == np.max(h[i - w : i + w + 1]):
                swing_highs.append(float(h[i]))
            # Swing Low: Lowest among w bars before and after
            if l[i] == np.min(l[i - w : i + w + 1]):
                swing_lows.append(float(l[i]))
                
        return sorted(swing_highs), sorted(swing_lows)

    def detect_volume_nodes(self, df: pd.DataFrame) -> List[float]:
        """
        Computes Volume Profile High-Volume Nodes (HVN) as structural liquidity zones
        """
        if 'volume' not in df.columns or len(df) < 20:
            return []
        
        c = df['close'].values
        v = df['volume'].values
        
        min_p, max_p = np.min(c), np.max(c)
        if max_p <= min_p:
            return []
        
        hist, bin_edges = np.histogram(c, bins=self.volume_bins, weights=v)
        # Top 3 volume peaks
        peak_idx = np.argsort(hist)[-3:]
        hvn_levels = [(bin_edges[i] + bin_edges[i+1]) / 2.0 for i in peak_idx]
        return sorted(hvn_levels)

    def get_dynamic_sr(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Determines the dynamic Support and Resistance levels relative to current price:
        - S1: Primary immediate support
        - S2: Secondary deep support
        - R1: Primary immediate resistance
        - R2: Secondary high resistance
        """
        curr_price = float(df['close'].iloc[-1])
        swing_highs, swing_lows = self.detect_pivots(df)
        hvn_levels = self.detect_volume_nodes(df)
        
        # Combine all structural levels
        all_supports = [p for p in swing_lows + hvn_levels if p < curr_price * 0.9995]
        all_resistances = [p for p in swing_highs + hvn_levels if p > curr_price * 1.0005]
        
        # Fallback to rolling low/high if not enough fractals
        if not all_supports:
            all_supports = [float(df['low'].rolling(20).min().iloc[-1] * 0.998)]
        if not all_resistances:
            all_resistances = [float(df['high'].rolling(20).max().iloc[-1] * 1.002)]
            
        all_supports = sorted(list(set(all_supports)))
        all_resistances = sorted(list(set(all_resistances)))
        
        # S1 is the closest support below price
        s1 = all_supports[-1]
        s2 = all_supports[-2] if len(all_supports) >= 2 else s1 * 0.995
        
        # R1 is the closest resistance above price
        r1 = all_resistances[0]
        r2 = all_resistances[1] if len(all_resistances) >= 2 else r1 * 1.005
        
        # Compute percentage distances
        dist_s1 = (curr_price - s1) / curr_price * 100.0
        dist_r1 = (r1 - curr_price) / curr_price * 100.0
        
        return {
            'current_price': curr_price,
            'S1': s1,
            'S2': s2,
            'R1': r1,
            'R2': r2,
            'dist_S1_pct': dist_s1,
            'dist_R1_pct': dist_r1
        }


if __name__ == "__main__":
    from multi_asset_1s_streamer import MultiAsset1sStreamer
    streamer = MultiAsset1sStreamer()
    print("Fetching live data to verify Support & Resistance engine across BTC, ETH, SOL, BNB...")
    data = streamer.sync_all_symbols(limit=120)
    
    sr_engine = SupportResistanceEngine(fractal_window=3)
    
    print("\n" + "="*80)
    print(f"{'SYMBOL':<10} | {'PRICE':<10} | {'REGIME':<9} | {'SUPPORT (S1)':<12} | {'RESIST (R1)':<12} | {'R:R RATIO (LONG)':<15}")
    print("="*80)
    
    for sym, df in data.items():
        trend = sr_engine.classify_trend(df)
        sr = sr_engine.get_dynamic_sr(df)
        
        # Theoretical R:R for Long = (R1 - Price) / (Price - S1)
        rr_long = sr['dist_R1_pct'] / (sr['dist_S1_pct'] + 1e-5)
        
        print(f"{sym:<10} | {sr['current_price']:<10.2f} | {trend['regime']:<9} | "
              f"{sr['S1']:<12.2f} (-{sr['dist_S1_pct']:.2f}%) | "
              f"{sr['R1']:<12.2f} (+{sr['dist_R1_pct']:.2f}%) | "
              f"{rr_long:<15.2f}")
    print("="*80)
