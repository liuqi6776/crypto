# -*- coding: utf-8 -*-
"""
Multi-Timeframe Trend Resonance Engine / 多周期趋势共振探测引擎
================================================================
Detects simultaneous trend alignment across 1m / 5m / 15m / 1h by fusing the
standard institutional trend-detection toolkit:

  1. EMA stack        (fast/slow cross + slope)  —— 均线趋势
  2. Wilder ADX(14)   (directional strength gate) —— 趋势强度门控
  3. Bollinger Bands  (20, 2)  —— 中轨趋势位置 + 上下轨止盈止损锚点
  4. Donchian / fractal S/R breakout  —— 结构性支撑阻力突破确认

CRITICAL CAUSALITY RULE / 严格无未来函数约定
------------------------------------------------
A higher-timeframe bar that covers [T, T+interval) only becomes *knowable* at
its close time T+interval. Every indicator value is therefore re-stamped onto
the close timestamp and forward-filled onto the 1m grid, so a 1-minute bar can
never see a 5m/15m/1h bar that has not finished printing yet.
"""

from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd


def _interval_minutes(tf: str) -> int:
    unit, num = tf[-1], int(tf[:-1])
    return {"m": 1, "h": 60, "d": 1440}[unit] * num


def resample_ohlcv(df_1m: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Resample 1m OHLCV into a higher timeframe with left-labelled buckets."""
    minutes = _interval_minutes(tf)
    if minutes == 1:
        return df_1m[["open", "high", "low", "close", "volume"]].copy()

    agg = df_1m.resample(f"{minutes}min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    return agg.dropna(subset=["open", "close"])


def _wilder_adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    """Wilder's ADX / 怀尔德平均趋向指数 (趋势强度 0-100)。"""
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=high.index)

    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)

    alpha = 1.0 / length
    atr = tr.ewm(alpha=alpha, adjust=False, min_periods=length).mean()
    plus_di = 100.0 * plus_dm.ewm(alpha=alpha, adjust=False, min_periods=length).mean() / atr
    minus_di = 100.0 * minus_dm.ewm(alpha=alpha, adjust=False, min_periods=length).mean() / atr

    denom = (plus_di + minus_di).replace(0.0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / denom
    return dx.ewm(alpha=alpha, adjust=False, min_periods=length).mean()


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()


class MTFTrendEngine:
    """
    Builds a 1-minute-indexed table of per-timeframe trend scores plus Bollinger
    band anchors used for 20X take-profit / stop-loss placement.
    """

    def __init__(
        self,
        timeframes: Sequence[str] = ("1m", "5m", "15m", "1h"),
        ema_fast: int = 20,
        ema_slow: int = 50,
        ema_slope_lookback: int = 5,
        adx_len: int = 14,
        adx_threshold: float = 20.0,
        bb_len: int = 20,
        bb_std: float = 2.0,
        donchian_len: int = 60,
        require_sr_breakout: bool = False,
    ):
        self.timeframes = list(timeframes)
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.ema_slope_lookback = ema_slope_lookback
        self.adx_len = adx_len
        self.adx_threshold = adx_threshold
        self.bb_len = bb_len
        self.bb_std = bb_std
        self.donchian_len = donchian_len
        self.require_sr_breakout = require_sr_breakout

    def _timeframe_frame(self, df_1m: pd.DataFrame, tf: str) -> pd.DataFrame:
        """Indicator block for one timeframe, indexed by the bar's CLOSE timestamp."""
        raw = resample_ohlcv(df_1m, tf)
        high, low, close = raw["high"], raw["low"], raw["close"]

        ema_f = close.ewm(span=self.ema_fast, adjust=False, min_periods=self.ema_fast).mean()
        ema_s = close.ewm(span=self.ema_slow, adjust=False, min_periods=self.ema_slow).mean()
        slope = (ema_f - ema_f.shift(self.ema_slope_lookback)) / ema_f.shift(self.ema_slope_lookback)

        adx = _wilder_adx(high, low, close, self.adx_len)

        bb_mid = close.rolling(self.bb_len).mean()
        bb_dev = close.rolling(self.bb_len).std(ddof=0)
        bb_up = bb_mid + self.bb_std * bb_dev
        bb_lo = bb_mid - self.bb_std * bb_dev

        # Structural S/R: prior completed Donchian channel (shifted => no lookahead)
        don_hi = high.rolling(self.donchian_len).max().shift(1)
        don_lo = low.rolling(self.donchian_len).min().shift(1)

        atr = _atr(high, low, close, 14)

        up = (
            (ema_f > ema_s)
            & (close > ema_f)
            & (slope > 0)
            & (adx >= self.adx_threshold)
            & (close > bb_mid)
        )
        down = (
            (ema_f < ema_s)
            & (close < ema_f)
            & (slope < 0)
            & (adx >= self.adx_threshold)
            & (close < bb_mid)
        )
        if self.require_sr_breakout:
            up &= close > don_hi
            down &= close < don_lo

        score = pd.Series(np.where(up, 1.0, np.where(down, -1.0, 0.0)), index=close.index)

        out = pd.DataFrame(
            {
                "close": close,
                "ema_fast": ema_f,
                "ema_slow": ema_s,
                "ema_slope": slope,
                "adx": adx,
                "atr": atr,
                "bb_mid": bb_mid,
                "bb_up": bb_up,
                "bb_lo": bb_lo,
                "don_hi": don_hi,
                "don_lo": don_lo,
                "score": score,
            }
        )
        # Re-stamp to the bar CLOSE time: this is the first instant the data is knowable.
        out.index = out.index + pd.Timedelta(minutes=_interval_minutes(tf))
        return out

    def build(self, df_1m: pd.DataFrame) -> pd.DataFrame:
        """
        Returns a 1-minute-indexed frame containing:
          score_<tf>     per-timeframe trend score in {-1, 0, +1}
          adx_<tf>       trend strength
          bb_up_<tf> / bb_lo_<tf> / bb_mid_<tf>   Bollinger anchors
          resonance      sum of scores (== +N for full bullish alignment)
        """
        base = df_1m[["open", "high", "low", "close", "volume"]].copy()
        result = pd.DataFrame(index=base.index)

        for tf in self.timeframes:
            block = self._timeframe_frame(base, tf)
            aligned = block.reindex(base.index, method="ffill")
            tag = tf.replace("m", "M").replace("h", "H")
            for col in ("score", "adx", "bb_mid", "bb_up", "bb_lo", "atr", "don_hi", "don_lo", "ema_fast", "ema_slow"):
                result[f"{col}_{tag}"] = aligned[col]

        score_cols = [f"score_{tf.replace('m', 'M').replace('h', 'H')}" for tf in self.timeframes]
        result["resonance"] = result[score_cols].sum(axis=1)
        result["n_bull"] = (result[score_cols] == 1.0).sum(axis=1)
        result["n_bear"] = (result[score_cols] == -1.0).sum(axis=1)
        return result


def build_signals(features: pd.DataFrame, mode: str = "unanimous") -> pd.DataFrame:
    """
    Derives entry signals from the resonance score.

    mode='unanimous'  : every timeframe must agree (resonance == +N / -N)
    mode='majority'   : >= N-1 timeframes agree (looser, higher frequency)
    mode='htf_gate'   : 1h must agree with the 1m/5m/15m majority (big-trend gate)
    """
    tf_cols = [c for c in features.columns if c.startswith("score_")]
    n_tf = len(tf_cols)

    res = features["resonance"]
    if mode == "unanimous":
        long_sig = res >= n_tf
        short_sig = res <= -n_tf
    elif mode == "majority":
        long_sig = features["n_bull"] >= n_tf - 1
        short_sig = features["n_bear"] >= n_tf - 1
    elif mode == "htf_gate":
        htf = tf_cols[-1]
        others = features[tf_cols[:-1]]
        long_sig = (features[htf] == 1.0) & (others.sum(axis=1) >= (n_tf - 1) * 0.5) & (others.min(axis=1) >= 0.0)
        short_sig = (features[htf] == -1.0) & (others.sum(axis=1) <= -(n_tf - 1) * 0.5) & (others.max(axis=1) <= 0.0)
    else:
        raise ValueError(f"unknown signal mode: {mode}")

    out = features.copy()
    out["long_signal"] = long_sig.fillna(False)
    out["short_signal"] = short_sig.fillna(False)
    return out
