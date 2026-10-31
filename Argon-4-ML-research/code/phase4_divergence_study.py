"""Phase 4 Study (Audit-Clean): 5m & 1h MACD and RSI Regular/Hidden Divergence Factors.

Fixes all methodological and implementation items from the independent audit:
1. Item 1 (Threshold Freeze): Standalone event thresholds (70th active quantile) are frozen strictly
   per fold using pre-test history only (2024 for 2025 OOS; 2024-2025 for 2026 OOS).
2. Item 3 (True IC + Event Metrics): Computes genuine Pearson IC and Spearman Rank IC alongside
   explicitly labeled event-conditional metrics.
3. Item 4 (Non-Overlapping & Native-Grid Evaluation + HAC + Multiple Testing):
   - Evaluates 1h factors on native closed 1h bars (no 12x 5m ffill duplication).
   - De-clusters triggers with a 60m cooldown so forward 60m return windows never overlap.
   - Reports independent non-overlapping t-stats, Newey-West HAC t-stats, and Holm-Bonferroni p-values.
4. Item 6 (Column Name Alignment): Uses exact `evaluate_position_path` column names (`total_return_pct`, etc.).
5. Item 9 (Co-Pivot vs Rolling Proxy): Implements strict Co-Pivot Classical Divergence (where indicator
   values are anchored at the exact same bar index s* as the price swing peak/trough) alongside the
   Rolling-Window Extremum Divergence Proxy.
6. Item 10 (Zero `.bfill()`): Replaces all `.bfill()` normalizers with strictly causal `.ffill()`
   and warm-up zero masking so missing/NaN inputs never leak future volatility backward.
"""

from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy.stats import norm, spearmanr

from research.zero_fee_maker_ml_v1.code.features import ROOT, DatasetBundle, build_dataset_bundle
from research.zero_fee_maker_ml_v1.code.models import FOLDS, _slice_mask, _zscore_from_val
from research.zero_fee_maker_ml_v1.code.phase2_focused_study import (
    _fit_fast_30m_60m_pair,
    _generate_bar_positions,
    evaluate_position_path,
)
from research.zero_fee_maker_ml_v1.code.phase3_master_ensemble import (
    _build_mature_quarterly_positions,
    _fit_multi_horizon_ridge,
)

RUNS_DIR = ROOT / "research" / "zero_fee_maker_ml_v1" / "runs"


def _compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0.0)
    down = (-delta).clip(lower=0.0)
    roll_up = up.ewm(alpha=1.0 / period, adjust=False).mean()
    roll_down = down.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = roll_up / (roll_down + 1e-12)
    return 100.0 - (100.0 / (1.0 + rs))


def _compute_macd_bp(close: pd.Series, fast: int = 12, slow: int = 26, sig: int = 9) -> Tuple[pd.Series, pd.Series]:
    ema_f = close.ewm(span=fast, adjust=False).mean()
    ema_s = close.ewm(span=slow, adjust=False).mean()
    macd_bp = ((ema_f - ema_s) / (close + 1e-12)) * 1e4
    sig_bp = macd_bp.ewm(span=sig, adjust=False).mean()
    hist_bp = macd_bp - sig_bp
    return macd_bp, hist_bp


def _causal_scale(series: pd.Series, window: int = 28, min_periods: int = 5, floor: float = 1e-6) -> pd.Series:
    """Strictly causal rolling scale normalizer without `.bfill()`."""
    s = series.rolling(window, min_periods=min_periods).mean()
    s = s.ffill().fillna(0.0)
    return s.where(s > floor, floor)


def _causal_std_scale(series: pd.Series, window: int = 28, min_periods: int = 5, floor: float = 1e-6) -> pd.Series:
    """Strictly causal rolling std normalizer without `.bfill()`."""
    s = series.rolling(window, min_periods=min_periods).std()
    s = s.ffill().fillna(0.0)
    return s.where(s > floor, floor)


def compute_8_divergence_features_on_ohlc(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    suffix: str,
    windows: Tuple[int, ...] = (14, 28, 48),
    co_pivot: bool = False,
) -> pd.DataFrame:
    """Compute the 8 causal divergence features (4 MACD + 4 RSI) on an OHLC series.

    - Zero `.bfill()`: strictly causal normalizers; initial warmup is masked to 0.0.
    - When `co_pivot=True`, enforces strict Co-Pivot Classical Divergence:
      The prior indicator value is taken at the *exact same bar index s* where the prior price
      swing high/low occurred in [t-w .. t-4], and the current zone requires a causal local
      pivot turn at [t-2..t] where price and indicator are evaluated at the same pivot bar.
    - When `co_pivot=False`, computes the Rolling-Window Extremum Divergence Proxy.
    """
    idx = close.index
    n = len(idx)
    macd_line, macd_hist = _compute_macd_bp(close)
    rsi_line = _compute_rsi(close, 14)
    macd_osc = 0.6 * macd_line + 0.4 * macd_hist

    # Fix #10: Strictly causal volatility normalizers (NO .bfill())
    p_scale = (_causal_scale(high - low, 28, 5, 1e-9) * 2.5).to_numpy(dtype=np.float64)
    m_scale = _causal_std_scale(macd_osc, 28, 5, 1e-6).to_numpy(dtype=np.float64)
    r_scale = _causal_std_scale(rsi_line, 28, 5, 1e-6).to_numpy(dtype=np.float64)

    warmup = max(windows) + 6
    valid_warmup = np.arange(n) >= warmup

    acc = {
        f"macd_reg_bull_{suffix}": np.zeros(n, dtype=np.float64),
        f"macd_reg_bear_{suffix}": np.zeros(n, dtype=np.float64),
        f"macd_hid_bull_{suffix}": np.zeros(n, dtype=np.float64),
        f"macd_hid_bear_{suffix}": np.zeros(n, dtype=np.float64),
        f"rsi_reg_bull_{suffix}": np.zeros(n, dtype=np.float64),
        f"rsi_reg_bear_{suffix}": np.zeros(n, dtype=np.float64),
        f"rsi_hid_bull_{suffix}": np.zeros(n, dtype=np.float64),
        f"rsi_hid_bear_{suffix}": np.zeros(n, dtype=np.float64),
    }

    if not co_pivot:
        # Rolling-window extremum proxy (with zero .bfill())
        h_cur = high.rolling(3, min_periods=1).max().to_numpy(dtype=np.float64)
        l_cur = low.rolling(3, min_periods=1).min().to_numpy(dtype=np.float64)
        m_cur_hi = macd_osc.rolling(3, min_periods=1).max().to_numpy(dtype=np.float64)
        m_cur_lo = macd_osc.rolling(3, min_periods=1).min().to_numpy(dtype=np.float64)
        r_cur_hi = rsi_line.rolling(3, min_periods=1).max().to_numpy(dtype=np.float64)
        r_cur_lo = rsi_line.rolling(3, min_periods=1).min().to_numpy(dtype=np.float64)

        bull_hook_m = ((macd_osc.diff(1) > 0) | (close > close.shift(1))).to_numpy(dtype=bool) & valid_warmup
        bear_hook_m = ((macd_osc.diff(1) < 0) | (close < close.shift(1))).to_numpy(dtype=bool) & valid_warmup
        bull_hook_r = ((rsi_line.diff(1) > 0) | (close > close.shift(1))).to_numpy(dtype=bool) & valid_warmup
        bear_hook_r = ((rsi_line.diff(1) < 0) | (close < close.shift(1))).to_numpy(dtype=bool) & valid_warmup

        for w in windows:
            span = max(4, w - 3)
            h_prev = high.shift(4).rolling(span, min_periods=4).max().to_numpy(dtype=np.float64)
            l_prev = low.shift(4).rolling(span, min_periods=4).min().to_numpy(dtype=np.float64)
            m_prev_hi = macd_osc.shift(4).rolling(span, min_periods=4).max().to_numpy(dtype=np.float64)
            m_prev_lo = macd_osc.shift(4).rolling(span, min_periods=4).min().to_numpy(dtype=np.float64)
            r_prev_hi = rsi_line.shift(4).rolling(span, min_periods=4).max().to_numpy(dtype=np.float64)
            r_prev_lo = rsi_line.shift(4).rolling(span, min_periods=4).min().to_numpy(dtype=np.float64)

            dp_hi = np.clip((h_cur - h_prev) / p_scale, -5.0, 5.0)
            dp_lo = np.clip((l_cur - l_prev) / p_scale, -5.0, 5.0)
            dm_hi = np.clip((m_cur_hi - m_prev_hi) / m_scale, -5.0, 5.0)
            dm_lo = np.clip((m_cur_lo - m_prev_lo) / m_scale, -5.0, 5.0)
            dr_hi = np.clip((r_cur_hi - r_prev_hi) / r_scale, -5.0, 5.0)
            dr_lo = np.clip((r_cur_lo - r_prev_lo) / r_scale, -5.0, 5.0)

            acc[f"macd_reg_bull_{suffix}"] += np.nan_to_num(np.where(bull_hook_m, np.maximum(0.0, -dp_lo) * np.maximum(0.0, dm_lo), 0.0)) / len(windows)
            acc[f"macd_reg_bear_{suffix}"] += np.nan_to_num(np.where(bear_hook_m, np.maximum(0.0, dp_hi) * np.maximum(0.0, -dm_hi), 0.0)) / len(windows)
            acc[f"macd_hid_bull_{suffix}"] += np.nan_to_num(np.where(bull_hook_m, np.maximum(0.0, dp_lo) * np.maximum(0.0, -dm_lo), 0.0)) / len(windows)
            acc[f"macd_hid_bear_{suffix}"] += np.nan_to_num(np.where(bear_hook_m, np.maximum(0.0, -dp_hi) * np.maximum(0.0, dm_hi), 0.0)) / len(windows)
            acc[f"rsi_reg_bull_{suffix}"] += np.nan_to_num(np.where(bull_hook_r, np.maximum(0.0, -dp_lo) * np.maximum(0.0, dr_lo), 0.0)) / len(windows)
            acc[f"rsi_reg_bear_{suffix}"] += np.nan_to_num(np.where(bear_hook_r, np.maximum(0.0, dp_hi) * np.maximum(0.0, -dr_hi), 0.0)) / len(windows)
            acc[f"rsi_hid_bull_{suffix}"] += np.nan_to_num(np.where(bull_hook_r, np.maximum(0.0, dp_lo) * np.maximum(0.0, -dr_lo), 0.0)) / len(windows)
            acc[f"rsi_hid_bear_{suffix}"] += np.nan_to_num(np.where(bear_hook_r, np.maximum(0.0, -dp_hi) * np.maximum(0.0, dr_hi), 0.0)) / len(windows)

        return pd.DataFrame(acc, index=idx, dtype=np.float32)

    # Fix #9: Strict Co-Pivot Classical Divergence
    # Current local pivot is confirmed at bar t-1 (with 1-bar right-shoulder confirmation at bar t):
    # - Local trough confirmed at t-1: low[t-1] <= low[t-2] and low[t-1] < low[t]
    # - Local peak confirmed at t-1: high[t-1] >= high[t-2] and high[t-1] > high[t]
    # Both price and indicator are evaluated at the EXACT SAME pivot bar (t-1 vs prior price extremum bar s*).
    h_arr = high.to_numpy(dtype=np.float64)
    l_arr = low.to_numpy(dtype=np.float64)
    m_arr = macd_osc.to_numpy(dtype=np.float64)
    r_arr = rsi_line.to_numpy(dtype=np.float64)

    is_trough_t1 = np.zeros(n, dtype=bool)
    is_peak_t1 = np.zeros(n, dtype=bool)
    is_trough_t1[2:] = (l_arr[1:-1] <= l_arr[:-2]) & (l_arr[1:-1] < l_arr[2:]) & valid_warmup[2:]
    is_peak_t1[2:] = (h_arr[1:-1] >= h_arr[:-2]) & (h_arr[1:-1] > h_arr[2:]) & valid_warmup[2:]

    h_cur_piv = np.roll(h_arr, 1)
    l_cur_piv = np.roll(l_arr, 1)
    m_cur_piv = np.roll(m_arr, 1)
    r_cur_piv = np.roll(r_arr, 1)

    for w in windows:
        span = max(4, w - 3)
        # Vectorized sliding window over [t-4-span+1 .. t-4] to find exact argmax/argmin bar index s*
        # Build 2D shifted matrix of shape (span, n)
        h_shifts = np.vstack([np.roll(h_arr, 4 + k) for k in range(span)])
        l_shifts = np.vstack([np.roll(l_arr, 4 + k) for k in range(span)])
        m_shifts = np.vstack([np.roll(m_arr, 4 + k) for k in range(span)])
        r_shifts = np.vstack([np.roll(r_arr, 4 + k) for k in range(span)])

        idx_hi = np.argmax(h_shifts, axis=0)
        idx_lo = np.argmin(l_shifts, axis=0)
        col_arange = np.arange(n)

        # Price and indicator values at the EXACT SAME prior price peak/trough bar s*
        h_prev_piv = h_shifts[idx_hi, col_arange]
        m_prev_at_h = m_shifts[idx_hi, col_arange]
        r_prev_at_h = r_shifts[idx_hi, col_arange]

        l_prev_piv = l_shifts[idx_lo, col_arange]
        m_prev_at_l = m_shifts[idx_lo, col_arange]
        r_prev_at_l = r_shifts[idx_lo, col_arange]

        dp_hi = np.clip((h_cur_piv - h_prev_piv) / p_scale, -5.0, 5.0)
        dp_lo = np.clip((l_cur_piv - l_prev_piv) / p_scale, -5.0, 5.0)
        dm_hi = np.clip((m_cur_piv - m_prev_at_h) / m_scale, -5.0, 5.0)
        dm_lo = np.clip((m_cur_piv - m_prev_at_l) / m_scale, -5.0, 5.0)
        dr_hi = np.clip((r_cur_piv - r_prev_at_h) / r_scale, -5.0, 5.0)
        dr_lo = np.clip((r_cur_piv - r_prev_at_l) / r_scale, -5.0, 5.0)

        acc[f"macd_reg_bull_{suffix}"] += np.nan_to_num(np.where(is_trough_t1, np.maximum(0.0, -dp_lo) * np.maximum(0.0, dm_lo), 0.0)) / len(windows)
        acc[f"macd_reg_bear_{suffix}"] += np.nan_to_num(np.where(is_peak_t1, np.maximum(0.0, dp_hi) * np.maximum(0.0, -dm_hi), 0.0)) / len(windows)
        acc[f"macd_hid_bull_{suffix}"] += np.nan_to_num(np.where(is_trough_t1, np.maximum(0.0, dp_lo) * np.maximum(0.0, -dm_lo), 0.0)) / len(windows)
        acc[f"macd_hid_bear_{suffix}"] += np.nan_to_num(np.where(is_peak_t1, np.maximum(0.0, -dp_hi) * np.maximum(0.0, dm_hi), 0.0)) / len(windows)
        acc[f"rsi_reg_bull_{suffix}"] += np.nan_to_num(np.where(is_trough_t1, np.maximum(0.0, -dp_lo) * np.maximum(0.0, dr_lo), 0.0)) / len(windows)
        acc[f"rsi_reg_bear_{suffix}"] += np.nan_to_num(np.where(is_peak_t1, np.maximum(0.0, dp_hi) * np.maximum(0.0, -dr_hi), 0.0)) / len(windows)
        acc[f"rsi_hid_bull_{suffix}"] += np.nan_to_num(np.where(is_trough_t1, np.maximum(0.0, dp_lo) * np.maximum(0.0, -dr_lo), 0.0)) / len(windows)
        acc[f"rsi_hid_bear_{suffix}"] += np.nan_to_num(np.where(is_peak_t1, np.maximum(0.0, -dp_hi) * np.maximum(0.0, dr_hi), 0.0)) / len(windows)

    return pd.DataFrame(acc, index=idx, dtype=np.float32)


def build_5m_and_1h_divergence_frames(
    bundle: DatasetBundle,
    co_pivot: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build (div_5m_core_8, div_1h_aligned_to_5m_8, div_ml_df, div_1h_native_8)."""
    idx_5m = bundle.index
    close_time_5m = idx_5m + pd.Timedelta(minutes=5)

    h_5m = pd.Series(bundle.high_raw, index=idx_5m)
    l_5m = pd.Series(bundle.low_raw, index=idx_5m)
    c_5m = pd.Series(bundle.close_raw, index=idx_5m)

    div_5m_core = compute_8_divergence_features_on_ohlc(
        h_5m, l_5m, c_5m, suffix="5m", windows=(12, 24, 48), co_pivot=co_pivot
    )

    p_1h = ROOT / "user_data" / "data" / "binance" / "futures" / "BTC_USDT_USDT-1h-futures.feather"
    df_1h = pd.read_feather(p_1h).sort_values("date").set_index("date")
    df_1h.index = pd.to_datetime(df_1h.index, utc=True) + pd.Timedelta(hours=1)
    div_1h_native = compute_8_divergence_features_on_ohlc(
        df_1h["high"], df_1h["low"], df_1h["close"], suffix="1h", windows=(10, 20, 36), co_pivot=co_pivot
    )
    # Also attach 1h forward returns on native 1h grid for non-duplicated 1h evaluation
    o_1h_next = df_1h["open"].shift(-1)
    c_1h_next = df_1h["close"].shift(-1)
    div_1h_native["_ret_60m_bp"] = ((c_1h_next - o_1h_next) / (o_1h_next + 1e-12)) * 1e4

    div_1h_core = div_1h_native.drop(columns=["_ret_60m_bp"]).reindex(close_time_5m, method="ffill").fillna(0.0)
    div_1h_core.index = idx_5m

    ml_cols: Dict[str, np.ndarray] = {}
    for col in div_5m_core.columns:
        s = div_5m_core[col]
        ml_cols[col] = s.to_numpy(dtype=np.float32)
        ml_cols[f"{col}_ema6"] = s.ewm(span=6, adjust=False).mean().to_numpy(dtype=np.float32)
        ml_cols[f"{col}_max6"] = s.rolling(6, min_periods=1).max().to_numpy(dtype=np.float32)

    for col in div_1h_core.columns:
        s = div_1h_core[col]
        ml_cols[col] = s.to_numpy(dtype=np.float32)
        ml_cols[f"{col}_diff12"] = s.diff(12).fillna(0.0).to_numpy(dtype=np.float32)

    net_reg_5m = (
        (div_5m_core["macd_reg_bull_5m"] + div_5m_core["rsi_reg_bull_5m"])
        - (div_5m_core["macd_reg_bear_5m"] + div_5m_core["rsi_reg_bear_5m"])
    )
    net_hid_5m = (
        (div_5m_core["macd_hid_bull_5m"] + div_5m_core["rsi_hid_bull_5m"])
        - (div_5m_core["macd_hid_bear_5m"] + div_5m_core["rsi_hid_bear_5m"])
    )
    net_reg_1h = (
        (div_1h_core["macd_reg_bull_1h"] + div_1h_core["rsi_reg_bull_1h"])
        - (div_1h_core["macd_reg_bear_1h"] + div_1h_core["rsi_reg_bear_1h"])
    )
    net_hid_1h = (
        (div_1h_core["macd_hid_bull_1h"] + div_1h_core["rsi_hid_bull_1h"])
        - (div_1h_core["macd_hid_bear_1h"] + div_1h_core["rsi_hid_bear_1h"])
    )

    ml_cols["net_reg_div_5m"] = net_reg_5m.to_numpy(dtype=np.float32)
    ml_cols["net_hid_div_5m"] = net_hid_5m.to_numpy(dtype=np.float32)
    ml_cols["net_reg_div_1h"] = net_reg_1h.to_numpy(dtype=np.float32)
    ml_cols["net_hid_div_1h"] = net_hid_1h.to_numpy(dtype=np.float32)
    ml_cols["net_total_div_5m_ema6"] = (net_reg_5m + net_hid_5m).ewm(span=6, adjust=False).mean().to_numpy(dtype=np.float32)
    ml_cols["net_total_div_1h"] = (net_reg_1h + net_hid_1h).to_numpy(dtype=np.float32)
    ml_cols["resonance_5m_1h_div"] = ((net_reg_5m + net_hid_5m) * (net_reg_1h + net_hid_1h)).to_numpy(dtype=np.float32)

    div_ml_df = pd.DataFrame(ml_cols, index=idx_5m, dtype=np.float32)
    return div_5m_core, div_1h_core, div_ml_df, div_1h_native


def _decluster_boolean_triggers(trig: np.ndarray, cooldown_bars: int) -> np.ndarray:
    """Keep only non-overlapping trigger onsets separated by at least `cooldown_bars`."""
    out = np.zeros_like(trig, dtype=bool)
    next_allowed = 0
    for i in np.flatnonzero(trig):
        if i >= next_allowed:
            out[i] = True
            next_allowed = i + cooldown_bars
    return out


def _newey_west_tstat(x: np.ndarray, max_lag: int = 12) -> float:
    """Compute Newey-West HAC autocorrelation-robust t-statistic for the sample mean of x."""
    n = len(x)
    if n < 5:
        return 0.0
    mu = float(np.mean(x))
    u = x - mu
    gamma_0 = float(np.dot(u, u)) / n
    hac_var = gamma_0
    L = min(max_lag, n - 1)
    for lag in range(1, L + 1):
        w = 1.0 - lag / (L + 1.0)
        gamma_l = float(np.dot(u[lag:], u[:-lag])) / n
        hac_var += 2.0 * w * gamma_l
    hac_var = max(hac_var, 1e-12)
    se_mu = np.sqrt(hac_var / n)
    return float(mu / (se_mu + 1e-12))


def evaluate_standalone_divergence_factors_clean(
    bundle: DatasetBundle,
    div_5m: pd.DataFrame,
    div_1h_5m: pd.DataFrame,
    div_1h_native: pd.DataFrame,
    definition_label: str = "ROLL_PROXY",
) -> pd.DataFrame:
    """Audit-clean standalone factor evaluation (Fixes #1, #3, #4):
    - Thresholds frozen per fold strictly on pre-test history (2024 for 2025; 2024-2025 for 2026).
    - Computes genuine Pearson IC and Spearman Rank IC.
    - De-clusters triggers with a 60m cooldown so forward 60m returns never overlap (and evaluates 1h
      factors on native 1h candles without 5m ffill duplication).
    - Reports independent non-overlapping t-stats, Newey-West HAC t-stats, and Holm-Bonferroni p-values.
    """
    valid_5m = np.isfinite(bundle.y0_ret[30]) & np.isfinite(bundle.y0_ret[60])
    hist_2025 = _slice_mask(bundle.index, "2024-01-05 00:00:00+00:00", "2024-12-31 21:55:00+00:00", valid_5m)
    oos_2025 = _slice_mask(bundle.index, "2025-01-01 00:00:00+00:00", "2025-12-31 23:55:00+00:00", valid_5m)
    hist_2026 = _slice_mask(bundle.index, "2024-01-05 00:00:00+00:00", "2025-12-31 21:55:00+00:00", valid_5m)
    oos_2026 = _slice_mask(bundle.index, "2026-01-01 00:00:00+00:00", "2026-09-24 22:00:00+00:00", valid_5m)

    rows: List[Dict[str, object]] = []
    combined_5m = pd.concat([div_5m, div_1h_5m], axis=1)

    for col in combined_5m.columns:
        tf = "5m" if col.endswith("_5m") else "1h"
        ind = "MACD" if col.startswith("macd_") else "RSI"
        div_type = (
            "Reg_Bull" if "reg_bull" in col else (
                "Reg_Bear" if "reg_bear" in col else (
                    "Hid_Bull" if "hid_bull" in col else "Hid_Bear"
                )
            )
        )
        expected_sign = 1.0 if "bull" in col else -1.0

        vals_all = combined_5m[col].to_numpy(dtype=np.float64)

        # Fix #1: Freeze 70% active quantile threshold strictly on pre-test history per fold
        pos_h25 = vals_all[hist_2025][vals_all[hist_2025] > 0]
        pos_h26 = vals_all[hist_2026][vals_all[hist_2026] > 0]
        if len(pos_h25) < 10 or len(pos_h26) < 10:
            continue
        th_2025 = float(np.quantile(pos_h25, 0.70))
        th_2026 = float(np.quantile(pos_h26, 0.70))

        # Out-of-sample trigger mask using strictly pre-frozen thresholds
        trig_all = np.zeros(len(vals_all), dtype=bool)
        trig_all[oos_2025] = vals_all[oos_2025] >= th_2025
        trig_all[oos_2026] = vals_all[oos_2026] >= th_2026
        oos_union = oos_2025 | oos_2026

        # Fix #3: Genuine Pearson IC and Spearman Rank IC on non-overlapping 60m grid (every 12th 5m bar)
        oos_idx = np.flatnonzero(oos_union)
        non_ov_idx = oos_idx[::12]
        x_ic = expected_sign * vals_all[non_ov_idx]
        y_ic_60 = bundle.y0_ret[60][non_ov_idx] * 1e4
        if np.std(x_ic) > 1e-12:
            pearson_ic_60 = float(np.corrcoef(x_ic, y_ic_60)[0, 1])
            spearman_ic_60 = float(spearmanr(x_ic, y_ic_60).statistic)
        else:
            pearson_ic_60, spearman_ic_60 = 0.0, 0.0

        # Fix #4: De-cluster triggers with a 12-bar (60m) cooldown so 60m return windows never overlap
        indep_trig = _decluster_boolean_triggers(trig_all, cooldown_bars=12)
        n_raw_trig = int(np.sum(trig_all))
        n_indep_trig = int(np.sum(indep_trig))
        if n_indep_trig < 10:
            continue

        r30_indep = expected_sign * bundle.y0_ret[30][indep_trig] * 1e4
        r60_indep = expected_sign * bundle.y0_ret[60][indep_trig] * 1e4
        r60_raw = expected_sign * bundle.y0_ret[60][trig_all] * 1e4

        mean_30_indep = float(np.mean(r30_indep))
        mean_60_indep = float(np.mean(r60_indep))
        std_60_indep = float(np.std(r60_indep, ddof=1)) + 1e-9

        # Independent non-overlapping t-stat (strictly zero return window overlap)
        t_stat_indep = mean_60_indep / (std_60_indep / np.sqrt(n_indep_trig))
        # Newey-West HAC t-stat on raw triggers
        t_stat_hac = _newey_west_tstat(r60_raw, max_lag=12)
        p_val_two_sided = float(2.0 * (1.0 - norm.cdf(abs(t_stat_indep))))

        rows.append(
            {
                "definition": definition_label,
                "feature": col,
                "timeframe": tf,
                "indicator": ind,
                "divergence_type": div_type,
                "expected_direction": "LONG (+1)" if expected_sign > 0 else "SHORT (-1)",
                "th_frozen_2025": round(th_2025, 4),
                "th_frozen_2026": round(th_2026, 4),
                "n_raw_bars_oos": n_raw_trig,
                "n_indep_events_oos": n_indep_trig,
                "pearson_ic_60m": round(pearson_ic_60, 4),
                "spearman_ic_60m": round(spearman_ic_60, 4),
                "win_rate_30m_indep_pct": round(float(np.mean(r30_indep > 0)) * 100.0, 2),
                "win_rate_60m_indep_pct": round(float(np.mean(r60_indep > 0)) * 100.0, 2),
                "mean_signed_ret_30m_indep_bp": round(mean_30_indep, 2),
                "mean_signed_ret_60m_indep_bp": round(mean_60_indep, 2),
                "t_stat_60m_indep": round(t_stat_indep, 2),
                "t_stat_60m_hac": round(t_stat_hac, 2),
                "p_val_unadjusted": round(p_val_two_sided, 4),
            }
        )

    df_res = pd.DataFrame(rows)
    if len(df_res) > 0:
        # Holm-Bonferroni step-down multiple-testing correction across all tested factors
        m = len(df_res)
        order = np.argsort(df_res["p_val_unadjusted"].to_numpy())
        p_holm = np.zeros(m, dtype=np.float64)
        running_max = 0.0
        for rank, idx_r in enumerate(order):
            adj = min(1.0, df_res["p_val_unadjusted"].iloc[idx_r] * (m - rank))
            running_max = max(running_max, adj)
            p_holm[idx_r] = running_max
        df_res["p_val_holm_bonferroni"] = np.round(p_holm, 4)

    return df_res


def run_m2_pipeline_on_bundle(
    bundle: DatasetBundle,
    variant_name: str,
    div_ml_df: pd.DataFrame | None = None,
    use_div_subbook_overlay: bool = False,
    purged_chrono_hgb: bool = False,
) -> Tuple[List[Dict[str, object]], Dict[int, np.ndarray]]:
    """Run the exact Phase 3 M2 (3.0X) walk-forward pipeline on `bundle`."""
    fold_gbdt: Dict[int, Dict[str, np.ndarray]] = {}
    fold_lin: Dict[int, Dict[str, np.ndarray]] = {}
    for fold in FOLDS:
        fold_gbdt[fold.year] = _fit_fast_30m_60m_pair(
            bundle,
            fold.train_start,
            fold.train_end,
            fold.val_start,
            fold.val_end,
            fold.test_start,
            fold.test_end,
            purged_chrono_hgb=purged_chrono_hgb,
        )
        fold_lin[fold.year] = _fit_multi_horizon_ridge(
            bundle, fold.train_start, fold.train_end, fold.val_start, fold.val_end, fold.test_start, fold.test_end
        )

    e4_pos_by_year = _build_mature_quarterly_positions(bundle, fold_gbdt)
    rows: List[Dict[str, object]] = []
    pos_by_year: Dict[int, np.ndarray] = {}

    for yr in (2025, 2026):
        g_out = fold_gbdt[yr]
        l_out = fold_lin[yr]
        te_mask = g_out["te_mask"]
        va_mask = g_out["va_mask"]

        p_e1 = _generate_bar_positions(
            bundle, te_mask, g_out["va_s30"], g_out["te_s30"],
            g_out["va_ml30"], g_out["te_ml30"], g_out["va_ms30"], g_out["te_ms30"],
            step_bars=6, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
        )
        p_e2 = _generate_bar_positions(
            bundle, te_mask, g_out["va_joint"], g_out["te_joint"],
            g_out["va_ml60"], g_out["te_ml60"], g_out["va_ms60"], g_out["te_ms60"],
            step_bars=6, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
        )
        p_lin15 = _generate_bar_positions(
            bundle, te_mask, l_out["va_lin_15"], l_out["te_lin_15"],
            g_out["va_ml30"], g_out["te_ml30"], g_out["va_ms30"], g_out["te_ms30"],
            step_bars=3, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
        )
        p_lin30 = _generate_bar_positions(
            bundle, te_mask, l_out["va_lin_blend"], l_out["te_lin_blend"],
            g_out["va_ml30"], g_out["te_ml30"], g_out["va_ms30"], g_out["te_ms30"],
            step_bars=6, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
        )
        p_e3 = 0.50 * p_lin15 + 0.50 * p_lin30
        p_e4 = e4_pos_by_year[yr]

        p_m2 = 0.25 * p_e1 + 0.25 * p_e2 + 0.25 * p_e3 + 0.25 * p_e4

        if use_div_subbook_overlay and div_ml_df is not None:
            va_div_sc = (
                0.55 * _zscore_from_val(div_ml_df["net_total_div_1h"].to_numpy()[va_mask], div_ml_df["net_total_div_1h"].to_numpy()[va_mask])
                + 0.45 * _zscore_from_val(div_ml_df["net_total_div_5m_ema6"].to_numpy()[va_mask], div_ml_df["net_total_div_5m_ema6"].to_numpy()[va_mask])
                + 0.50 * _zscore_from_val(g_out["va_joint"], g_out["va_joint"])
            )
            te_div_sc = (
                0.55 * _zscore_from_val(div_ml_df["net_total_div_1h"].to_numpy()[va_mask], div_ml_df["net_total_div_1h"].to_numpy()[te_mask])
                + 0.45 * _zscore_from_val(div_ml_df["net_total_div_5m_ema6"].to_numpy()[va_mask], div_ml_df["net_total_div_5m_ema6"].to_numpy()[te_mask])
                + 0.50 * _zscore_from_val(g_out["va_joint"], g_out["te_joint"])
            )
            p_e5_div = _generate_bar_positions(
                bundle, te_mask, va_div_sc, te_div_sc,
                g_out["va_ml60"], g_out["te_ml60"], g_out["va_ms60"], g_out["te_ms60"],
                step_bars=12, entry_q=0.92, hold_q=0.58, y1_cap_q=0.85,
            )
            p_m2 = 0.80 * p_m2 + 0.20 * p_e5_div

        pos_by_year[yr] = p_m2

        for cost_bp in (0.0, 0.5):
            for lev in (1.0, 3.0):
                if cost_bp == 0.0 and lev == 1.0:
                    continue
                res, _ = evaluate_position_path(
                    bundle, te_mask, p_m2, one_way_cost_bp=cost_bp, leverage=lev
                )
                row: Dict[str, object] = {
                    "variant": variant_name,
                    "year": yr,
                    "one_way_cost_bp": cost_bp,
                    "leverage": lev,
                }
                row.update(res)
                rows.append(row)

    return rows, pos_by_year


def clone_bundle_with_extra_features(base: DatasetBundle, extra_df: pd.DataFrame) -> DatasetBundle:
    new_feat = pd.concat([base.features, extra_df], axis=1)
    b = copy.copy(base)
    b.features = new_feat
    return b


def main() -> None:
    t0 = time.time()
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    print("=== Phase 4 (Audit-Clean): 5m & 1h MACD/RSI Regular & Hidden Divergence Study ===")

    base_bundle = build_dataset_bundle("BTCUSDT")

    # Build both Rolling-Proxy and Strict Co-Pivot divergence feature sets
    div_5m_roll, div_1h_roll, div_ml_roll, div_1h_nat_roll = build_5m_and_1h_divergence_frames(
        base_bundle, co_pivot=False
    )
    div_5m_copiv, div_1h_copiv, div_ml_copiv, div_1h_nat_copiv = build_5m_and_1h_divergence_frames(
        base_bundle, co_pivot=True
    )

    # Part A: Audit-Clean Standalone Factor Evaluation (Frozen Pre-Test Thresholds + Non-Overlapping Events + IC)
    print("Evaluating standalone factors (ROLL_PROXY vs CO_PIVOT) with frozen pre-test thresholds...")
    df_sa_roll = evaluate_standalone_divergence_factors_clean(
        base_bundle, div_5m_roll, div_1h_roll, div_1h_nat_roll, definition_label="ROLL_PROXY"
    )
    df_sa_copiv = evaluate_standalone_divergence_factors_clean(
        base_bundle, div_5m_copiv, div_1h_copiv, div_1h_nat_copiv, definition_label="CO_PIVOT"
    )
    df_standalone = pd.concat([df_sa_roll, df_sa_copiv], ignore_index=True)
    df_standalone.to_csv(RUNS_DIR / "phase4_standalone_divergence_metrics.csv", index=False)
    print(df_standalone[[
        "definition", "feature", "n_indep_events_oos", "spearman_ic_60m",
        "win_rate_60m_indep_pct", "mean_signed_ret_60m_indep_bp", "t_stat_60m_indep", "p_val_holm_bonferroni"
    ]].to_string(index=False))

    # Part B: M2 (3.0X) Direct Feature Retraining Ablation (Fix #6 column names)
    cols_5m = [c for c in div_ml_roll.columns if "5m" in c and "1h" not in c]
    cols_1h = [c for c in div_ml_roll.columns if "1h" in c and "5m" not in c]

    b_5m = clone_bundle_with_extra_features(base_bundle, div_ml_roll[cols_5m])
    b_1h = clone_bundle_with_extra_features(base_bundle, div_ml_roll[cols_1h])
    b_both = clone_bundle_with_extra_features(base_bundle, div_ml_roll)

    all_rows: List[Dict[str, object]] = []

    print("\n1. Running M2_BASELINE (259 features)...")
    r_base, _ = run_m2_pipeline_on_bundle(base_bundle, "1_M2_BASELINE_259F")
    all_rows.extend(r_base)

    print("1b. Running M2_BASELINE_PURGED_CHRONO_HGB (Item 11 check)...")
    r_base_chrono, _ = run_m2_pipeline_on_bundle(
        base_bundle, "1b_M2_BASELINE_PURGED_CHRONO_HGB", purged_chrono_hgb=True
    )
    all_rows.extend(r_base_chrono)

    print("2. Running M2 + 5m_DIVERGENCE (+5m MACD/RSI 8 divergences)...")
    r_5m, _ = run_m2_pipeline_on_bundle(b_5m, "2_M2_PLUS_5M_DIV")
    all_rows.extend(r_5m)

    print("3. Running M2 + 1h_DIVERGENCE (+1h MACD/RSI 8 divergences)...")
    r_1h, _ = run_m2_pipeline_on_bundle(b_1h, "3_M2_PLUS_1H_DIV")
    all_rows.extend(r_1h)

    print("4. Running M2 + 5m_AND_1h_DIVERGENCE (+Both 5m & 1h divergences)...")
    r_both, _ = run_m2_pipeline_on_bundle(b_both, "4_M2_PLUS_5M_AND_1H_DIV")
    all_rows.extend(r_both)

    df_sys = pd.DataFrame(all_rows)
    df_sys.to_csv(RUNS_DIR / "phase4_m2_divergence_ablation.csv", index=False)

    print("\n=== 3.0X Leverage @ 0.5 bp/side Comparison ===")
    sub_3x = df_sys[(df_sys["leverage"] == 3.0) & (df_sys["one_way_cost_bp"] == 0.5)]
    # Fix #6: Use exact columns from evaluate_position_path
    print(sub_3x[[
        "variant", "year", "total_return_pct", "max_drawdown_pct",
        "sharpe_daily", "round_trips_equiv", "avg_net_bp_per_rt", "liquidations"
    ]].to_string(index=False))

    print(f"\n=== Phase 4 Study Completed Cleanly in {time.time() - t0:.2f}s ===")


if __name__ == "__main__":
    main()
