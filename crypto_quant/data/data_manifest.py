# -*- coding: utf-8 -*-
"""
Data Manifest & Market Data Quality Auditor (Phase 37)
======================================================
Strict cryptographic and statistical auditor for crypto OHLCV datasets.
Verifies SHA256 fingerprints, OHLC physical invariants, temporal continuity,
missing intervals, and compares Spot vs Futures basis divergence.
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np


def compute_file_sha256(filepath: str) -> str:
    """Computes SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


def audit_ohlcv_dataframe(df: pd.DataFrame, expected_freq: str = "4h") -> Dict[str, Any]:
    """
    Rigorously audits an OHLCV DataFrame for:
    - Temporal continuity (no gaps, no duplicates)
    - Physical candle validity (High >= max(Open, Close), Low <= min(Open, Close))
    - Volume non-negativity
    - Non-null values
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame index must be a pd.DatetimeIndex")

    # Ensure monotonic sort
    is_monotonic = df.index.is_monotonic_increasing
    dup_count = int(df.index.duplicated().sum())

    clean_df = df[~df.index.duplicated(keep="first")].sort_index()

    total_bars = len(clean_df)
    if total_bars == 0:
        return {"total_bars": 0, "is_valid": False, "error": "Empty dataset"}

    start_dt = str(clean_df.index.min())
    end_dt = str(clean_df.index.max())

    # Generate expected grid
    expected_grid = pd.date_range(start=clean_df.index.min(), end=clean_df.index.max(), freq=expected_freq)
    missing_idx = expected_grid.difference(clean_df.index)
    missing_count = len(missing_idx)

    missing_gaps = []
    if missing_count > 0:
        # Group contiguous missing bars into gap intervals
        gap_starts = []
        for i, dt in enumerate(missing_idx):
            if i == 0 or (dt - missing_idx[i - 1]) > pd.Timedelta(expected_freq):
                gap_starts.append([str(dt), str(dt)])
            else:
                gap_starts[-1][1] = str(dt)
        missing_gaps = [{"start": g[0], "end": g[1]} for g in gap_starts]

    # OHLC validity
    opens = clean_df["open"].values
    highs = clean_df["high"].values
    lows = clean_df["low"].values
    closes = clean_df["close"].values
    vols = clean_df["volume"].values if "volume" in clean_df.columns else clean_df["vol"].values

    invalid_high_open = int((highs < opens).sum())
    invalid_high_close = int((highs < closes).sum())
    invalid_low_open = int((lows > opens).sum())
    invalid_low_close = int((lows > closes).sum())
    negative_volume = int((vols < 0).sum())
    null_count = int(clean_df[["open", "high", "low", "close"]].isnull().sum().sum())

    is_valid = (
        is_monotonic
        and dup_count == 0
        and missing_count == 0
        and invalid_high_open == 0
        and invalid_high_close == 0
        and invalid_low_open == 0
        and invalid_low_close == 0
        and negative_volume == 0
        and null_count == 0
    )

    return {
        "is_valid": bool(is_valid),
        "total_bars": total_bars,
        "start_time": start_dt,
        "end_time": end_dt,
        "is_monotonic_increasing": bool(is_monotonic),
        "duplicate_timestamps": dup_count,
        "expected_bars_in_range": len(expected_grid),
        "missing_bars_count": missing_count,
        "missing_gap_intervals": missing_gaps,
        "invalid_high_count": invalid_high_open + invalid_high_close,
        "invalid_low_count": invalid_low_open + invalid_low_close,
        "negative_volume_count": negative_volume,
        "null_count": null_count,
        "columns": list(clean_df.columns),
    }


def compare_spot_vs_futures(
    spot_df: pd.DataFrame,
    futures_df: pd.DataFrame,
    symbol: str,
) -> Dict[str, Any]:
    """
    Rigorously calculates Basis, Basis %, Volatility, and Trend Signal Divergence
    between Spot and USDS-M Perpetual Futures datasets on common timestamps.
    """
    # Align time index
    common_idx = spot_df.index.intersection(futures_df.index).sort_values()
    if len(common_idx) == 0:
        return {"error": "No overlapping timestamps between spot and futures"}

    s_sub = spot_df.reindex(common_idx)
    f_sub = futures_df.reindex(common_idx)

    s_close = s_sub["close"]
    f_close = f_sub["close"]

    # Basis = Futures - Spot
    basis = f_close - s_close
    basis_pct = (basis / s_close) * 100.0

    # Returns correlation
    s_ret = s_close.pct_change().dropna()
    f_ret = f_close.pct_change().dropna()
    ret_corr = float(s_ret.corr(f_ret))

    # EMA200 Trend Signal Divergence
    s_ema200 = s_close.ewm(span=200, adjust=False).mean()
    f_ema200 = f_close.ewm(span=200, adjust=False).mean()

    s_bull = s_close > s_ema200
    f_bull = f_close > f_ema200
    signal_mismatch_count = int((s_bull != f_bull).sum())
    signal_mismatch_pct = float(signal_mismatch_count / len(common_idx) * 100.0)

    # 120-bar Donchian High Divergence
    s_donchian = s_sub["high"].shift(1).rolling(120).max()
    f_donchian = f_sub["high"].shift(1).rolling(120).max()
    s_break = (s_close > s_donchian)
    f_break = (f_close > f_donchian)
    break_mismatch_count = int((s_break != f_break).sum())
    break_mismatch_pct = float(break_mismatch_count / len(common_idx) * 100.0)

    return {
        "symbol": symbol,
        "common_bars_count": len(common_idx),
        "overlap_start": str(common_idx[0]),
        "overlap_end": str(common_idx[-1]),
        "basis_usd": {
            "mean": float(basis.mean()),
            "std": float(basis.std()),
            "median": float(basis.median()),
            "min": float(basis.min()),
            "max": float(basis.max()),
        },
        "basis_pct": {
            "mean_pct": float(basis_pct.mean()),
            "std_pct": float(basis_pct.std()),
            "median_pct": float(basis_pct.median()),
            "min_pct": float(basis_pct.min()),
            "max_pct": float(basis_pct.max()),
            "p01_pct": float(basis_pct.quantile(0.01)),
            "p05_pct": float(basis_pct.quantile(0.05)),
            "p95_pct": float(basis_pct.quantile(0.95)),
            "p99_pct": float(basis_pct.quantile(0.99)),
        },
        "returns_correlation": ret_corr,
        "signal_divergence": {
            "ema200_bull_mismatch_bars": signal_mismatch_count,
            "ema200_bull_mismatch_pct": signal_mismatch_pct,
            "donchian120_breakout_mismatch_bars": break_mismatch_count,
            "donchian120_breakout_mismatch_pct": break_mismatch_pct,
        }
    }
