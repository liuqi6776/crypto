"""Causal 5-minute feature engineering and multi-horizon target construction.

Builds X (stationary diffs and multi-scale lags across price, cross-asset BTC/SOL/ETH/BNB,
native 5m Binance taker order-flow/sentiment, 8h observed funding, 1h mark-trade & 4h
spot-futures basis, and daily options DVOL/VRP) and Y0 (positive return / hurdle probability),
Y1 (intrabar range & directional maximum adverse excursion for liquidation risk) at horizons
H in {5m, 15m, 30m, 60m}.

Strict causal rule:
- Bar i has open_time t_i and closes at d_i = t_i + 5m.
- Every feature at index i uses only observations available at or before d_i = t_i + 5m.
- Earliest trade entry for decision d_i is bar i+1 open O_{i+1} at t_{i+1} = t_i + 5m.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
LATEST_INTRADAY_DIR = Path("C:/Users/liuqi/crypto/data/intraday")
HORIZONS_MIN = (5, 15, 30, 60)
HORIZON_BARS = {5: 1, 15: 3, 30: 6, 60: 12}
CORE_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class DatasetBundle:
    target_symbol: str
    partner_symbol: str
    index: pd.DatetimeIndex          # open_time t_i of bar i (decision is t_i + 5m)
    open_next: np.ndarray            # O_{i+1}: entry open price for decision after bar i
    high_next: np.ndarray            # H_{i+1}: high of entry bar i+1
    low_next: np.ndarray             # L_{i+1}: low of entry bar i+1
    close_next: np.ndarray           # C_{i+1}: close of entry bar i+1
    open_raw: np.ndarray             # O_i
    high_raw: np.ndarray             # H_i
    low_raw: np.ndarray              # L_i
    close_raw: np.ndarray            # C_i
    features: pd.DataFrame           # X_i (float32)
    feature_groups: Dict[str, List[str]]
    y0_ret: Dict[int, np.ndarray]    # forward return (C_{i+k} - O_{i+1}) / O_{i+1}
    y1_range: Dict[int, np.ndarray]  # (max_{s in 1..k} H_{i+s} - min_{s in 1..k} L_{i+s}) / O_{i+1}
    y1_mae_long: Dict[int, np.ndarray]   # (O_{i+1} - min_{s in 1..k} L_{i+s}) / O_{i+1}
    y1_mae_short: Dict[int, np.ndarray]  # (max_{s in 1..k} H_{i+s} - O_{i+1}) / O_{i+1}
    funding_ms: np.ndarray
    funding_rate: np.ndarray
    mark_close_5m: np.ndarray
    provenance: Dict[str, str]


def _load_5m_core(use_latest_intraday: bool = False) -> Tuple[Dict[str, pd.DataFrame], Dict[str, str]]:
    frames: Dict[str, pd.DataFrame] = {}
    hashes: Dict[str, str] = {}
    for sym in CORE_SYMBOLS:
        p_ext = Path(f"C:/Users/liuqi/crypto/data/intraday/{sym}_5m_futures.parquet")
        if use_latest_intraday and p_ext.exists():
            p = p_ext
            hashes[str(p)] = sha256_file(p)
        else:
            p = ROOT / "source_data" / "intraday" / f"{sym}_5m_futures.parquet"
            hashes[str(p.relative_to(ROOT))] = sha256_file(p)
        df = pd.read_parquet(p)
        if not isinstance(df.index, pd.DatetimeIndex):
            df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
            df = df.set_index("open_time")
        df = df.sort_index()
        if use_latest_intraday:
            df = df.loc["2024-01-01 00:00:00+00:00":].copy()
        else:
            # Keep up to 2026-09-24 23:00:00 UTC so 1h mark coverage is 100% complete
            df = df.loc["2024-01-01 00:00:00+00:00":"2026-09-24 23:00:00+00:00"].copy()
        frames[sym] = df
    return frames, hashes


def _pair_stem(sym: str) -> str:
    base = sym.replace("USDT", "")
    return f"{base}_USDT_USDT"


def _load_funding_and_mark(
    target_index: pd.DatetimeIndex,
    use_latest_intraday: bool = False,
) -> Tuple[Dict[str, Tuple[np.ndarray, np.ndarray, pd.Series]], Dict[str, pd.Series], Dict[str, str]]:
    """Load observed 8h funding events and 1h mark/trade candles causally mapped to 5m close_time."""
    hashes: Dict[str, str] = {}
    close_time_5m = target_index + pd.Timedelta(minutes=5)
    funding_info: Dict[str, Tuple[np.ndarray, np.ndarray, pd.Series]] = {}
    mark_basis_1h: Dict[str, pd.Series] = {}

    v6_inputs = ROOT / "research" / "divergence_fib_examples_2024_2025_20261026" / "v6_2024_to_latest_12_accounts" / "inputs"

    for sym in CORE_SYMBOLS:
        stem = _pair_stem(sym)
        p_fr = ROOT / "user_data" / "data" / "binance" / "futures" / f"{stem}-8h-funding_rate.feather"
        p_mk = ROOT / "user_data" / "data" / "binance" / "futures" / f"{stem}-1h-mark.feather"
        p_tr = ROOT / "user_data" / "data" / "binance" / "futures" / f"{stem}-1h-futures.feather"
        hashes[str(p_fr.relative_to(ROOT))] = sha256_file(p_fr)
        hashes[str(p_mk.relative_to(ROOT))] = sha256_file(p_mk)
        hashes[str(p_tr.relative_to(ROOT))] = sha256_file(p_tr)

        fr = pd.read_feather(p_fr).sort_values("date")
        fr["date"] = pd.to_datetime(fr["date"], utc=True)
        if use_latest_intraday and sym == "BTCUSDT" and (v6_inputs / "funding_events_v6.parquet").exists():
            fr_v6 = pd.read_parquet(v6_inputs / "funding_events_v6.parquet")
            fr_v6_df = pd.DataFrame(
                {
                    "date": pd.to_datetime(fr_v6["calc_time_utc"], utc=True),
                    "funding_rate": pd.to_numeric(fr_v6["last_funding_rate"], errors="coerce"),
                }
            ).dropna()
            fr = (
                pd.concat([fr[["date", "funding_rate"]], fr_v6_df], ignore_index=True)
                .drop_duplicates(subset=["date"], keep="last")
                .sort_values("date")
            )
        f_ms = fr["date"].astype("int64").to_numpy() // 10**6
        f_rate = fr["funding_rate"].to_numpy(dtype=float)

        # Causal feature series: a settlement at t_f is known at t_f + 5m (strictly after event)
        fr_feat = fr.set_index("date")["funding_rate"].copy()
        fr_feat.index = fr_feat.index + pd.Timedelta(minutes=5)
        fr_5m = fr_feat.reindex(close_time_5m, method="ffill")
        fr_5m.index = target_index
        funding_info[sym] = (f_ms, f_rate, fr_5m)

        # 1h mark vs 1h trade basis, available at t_h + 1h <= close_time_5m
        mk = pd.read_feather(p_mk).sort_values("date").set_index("date")
        tr = pd.read_feather(p_tr).sort_values("date").set_index("date")
        mk.index = pd.to_datetime(mk.index, utc=True)
        tr.index = pd.to_datetime(tr.index, utc=True)
        if use_latest_intraday and sym == "BTCUSDT" and (v6_inputs / "mark_1h_v6.parquet").exists():
            mk_v6 = pd.read_parquet(v6_inputs / "mark_1h_v6.parquet")
            mk_v6["date"] = pd.to_datetime(mk_v6["date"], utc=True)
            mk_v6 = mk_v6.set_index("date")[["open", "high", "low", "close"]]
            mk = pd.concat([mk[["open", "high", "low", "close"]], mk_v6]).loc[lambda x: ~x.index.duplicated(keep="last")].sort_index()
        mk.index = mk.index + pd.Timedelta(hours=1)
        tr.index = tr.index + pd.Timedelta(hours=1)
        joined = mk[["close"]].join(tr[["close"]], how="inner", lsuffix="_mark", rsuffix="_trade")
        basis_1h = (joined["close_mark"] - joined["close_trade"]) / joined["close_trade"]
        b_5m = basis_1h.reindex(close_time_5m, method="ffill")
        b_5m.index = target_index
        mark_basis_1h[sym] = b_5m
        if sym in ("BTCUSDT", "SOLUSDT"):
            mk_close_5m = mk["close"].reindex(close_time_5m, method="ffill")
            mk_close_5m.index = target_index
            mark_basis_1h[f"{sym}_mark_close"] = mk_close_5m

    return funding_info, mark_basis_1h, hashes


def _load_spot_basis_and_dvol(
    target_index: pd.DatetimeIndex,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, str]]:
    hashes: Dict[str, str] = {}
    close_time_5m = target_index + pd.Timedelta(minutes=5)

    p_b4 = ROOT / "source_data" / "research_reference" / "binance_basis_4h.parquet"
    hashes[str(p_b4.relative_to(ROOT))] = sha256_file(p_b4)
    b4 = pd.read_parquet(p_b4).sort_index()
    b4.index = pd.to_datetime(b4.index, utc=True) + pd.Timedelta(hours=4)
    # Compute 4h diffs on native 4h grid before mapping to 5m
    b4_feat = pd.DataFrame(index=b4.index)
    for col in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        s = b4[col].astype(float)
        b4_feat[f"b4_{col}_lvl"] = s
        b4_feat[f"b4_{col}_diff1"] = s.diff(1)
        b4_feat[f"b4_{col}_diff3"] = s.diff(3)
        b4_feat[f"b4_{col}_lag1"] = s.shift(1)
    # Map causally without extrapolating beyond last 4h bar + 4h
    b4_5m = b4_feat.reindex(close_time_5m, method="ffill", limit=48)
    b4_5m.index = target_index

    p_dv = ROOT / "source_data" / "ema_iv_minute_research_v1" / "options" / "deribit_dvol_daily_2021_2026.parquet"
    hashes[str(p_dv.relative_to(ROOT))] = sha256_file(p_dv)
    dv = pd.read_parquet(p_dv)
    dv["bucket_utc"] = pd.to_datetime(dv["bucket_utc"], utc=True)
    dv_feat_list = []
    for sym in ("BTC", "ETH"):
        sub = dv[dv["symbol"] == sym].sort_values("bucket_utc").set_index("bucket_utc")
        # Daily bucket D closes at D + 1 day; add 5m buffer -> D + 1d + 5m
        sub.index = sub.index + pd.Timedelta(days=1, minutes=5)
        c = sub["close"].astype(float)
        rng = (sub["high"].astype(float) - sub["low"].astype(float)) / c.clip(lower=1.0)
        df_s = pd.DataFrame(
            {
                f"dvol_{sym}_lvl": c,
                f"dvol_{sym}_diff1d": c.diff(1),
                f"dvol_{sym}_diff3d": c.diff(3),
                f"dvol_{sym}_diff7d": c.diff(7),
                f"dvol_{sym}_lag1d": c.shift(1),
                f"dvol_{sym}_lag2d": c.shift(2),
                f"dvol_{sym}_intraday_rng": rng,
            },
            index=sub.index,
        )
        dv_feat_list.append(df_s)
    dv_daily = pd.concat(dv_feat_list, axis=1)
    dv_daily["dvol_ETH_BTC_spread"] = dv_daily["dvol_ETH_lvl"] - dv_daily["dvol_BTC_lvl"]
    dv_daily["dvol_ETH_BTC_spread_diff1d"] = dv_daily["dvol_ETH_BTC_spread"].diff(1)
    dv_5m = dv_daily.reindex(close_time_5m, method="ffill")
    dv_5m.index = target_index

    return b4_5m, dv_5m, hashes


def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False, min_periods=span).mean()


def _rsi(s: pd.Series, span: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0.0).ewm(alpha=1.0 / span, adjust=False, min_periods=span).mean()
    dn = (-d).clip(lower=0.0).ewm(alpha=1.0 / span, adjust=False, min_periods=span).mean()
    rs = up / dn.replace(0.0, np.nan)
    return 100.0 - 100.0 / (1.0 + rs)


def _symbol_price_and_flow_block(df: pd.DataFrame, prefix: str) -> Tuple[pd.DataFrame, List[str], List[str]]:
    """Construct stationary diff + lag features for a single 5m symbol dataframe."""
    c = df["close"].astype(float)
    o = df["open"].astype(float)
    h = df["high"].astype(float)
    l = df["low"].astype(float)
    v = df["volume"].astype(float)
    qv = df["quote_volume"].astype(float)
    cnt = df["count"].astype(float)
    tbv = df["taker_buy_volume"].astype(float)
    tbqv = df["taker_buy_quote_volume"].astype(float)

    out = pd.DataFrame(index=df.index)
    price_cols: List[str] = []
    flow_cols: List[str] = []

    # 1. Log-return diffs and lags (5m bar diffs & lags)
    r1 = np.log(c / c.shift(1))
    out[f"{prefix}_ret_lag0"] = r1
    out[f"{prefix}_ret_diff1"] = r1.diff(1)
    for lag in (1, 2, 3, 6, 12):
        out[f"{prefix}_ret_lag{lag}"] = r1.shift(lag)
    for win in (3, 6, 12, 24, 48, 96, 288):
        rw = np.log(c / c.shift(win))
        out[f"{prefix}_ret_w{win}"] = rw
        out[f"{prefix}_ret_w{win}_diff1"] = rw.diff(1)

    # 2. Candle geometry, range, CLV, shadows, ATR & Bollinger diffs/lags
    rng = (h - l) / c
    clv = (2.0 * c - h - l) / (h - l + 1e-12)
    body = (c - o) / (h - l + 1e-12)
    up_wick = (h - np.maximum(o, c)) / (h - l + 1e-12)
    lo_wick = (np.minimum(o, c) - l) / (h - l + 1e-12)

    out[f"{prefix}_rng_lag0"] = rng
    out[f"{prefix}_rng_diff1"] = rng.diff(1)
    for lag in (1, 2, 3, 6):
        out[f"{prefix}_rng_lag{lag}"] = rng.shift(lag)

    out[f"{prefix}_clv_lag0"] = clv
    out[f"{prefix}_clv_diff1"] = clv.diff(1)
    for lag in (1, 2, 3):
        out[f"{prefix}_clv_lag{lag}"] = clv.shift(lag)

    out[f"{prefix}_body_lag0"] = body
    out[f"{prefix}_up_wick"] = up_wick
    out[f"{prefix}_lo_wick"] = lo_wick

    # Realized vol & ATR ratios
    rv12 = r1.rolling(12).std(ddof=0)
    rv48 = r1.rolling(48).std(ddof=0)
    rv288 = r1.rolling(288).std(ddof=0)
    out[f"{prefix}_rv12"] = rv12
    out[f"{prefix}_rv48"] = rv48
    out[f"{prefix}_rv288"] = rv288
    out[f"{prefix}_rv12_diff3"] = rv12.diff(3)
    out[f"{prefix}_rv_ratio_12_48"] = rv12 / (rv48 + 1e-12)
    out[f"{prefix}_rv_ratio_12_288"] = rv12 / (rv288 + 1e-12)

    # EMA distance & RSI diffs
    ema12 = _ema(c, 12)
    ema48 = _ema(c, 48)
    ema288 = _ema(c, 288)
    out[f"{prefix}_dist_ema12"] = (c - ema12) / c
    out[f"{prefix}_dist_ema48"] = (c - ema48) / c
    out[f"{prefix}_dist_ema288"] = (c - ema288) / c
    out[f"{prefix}_ema12_48_spread_diff"] = ((ema12 - ema48) / c).diff(1)

    mid20 = c.rolling(20).mean()
    sd20 = c.rolling(20).std(ddof=0)
    bb_pos = (c - mid20) / (2.0 * sd20 + 1e-12)
    bb_bw = (4.0 * sd20) / (mid20 + 1e-12)
    out[f"{prefix}_bb_pos"] = bb_pos
    out[f"{prefix}_bb_pos_diff1"] = bb_pos.diff(1)
    out[f"{prefix}_bb_bw_diff1"] = bb_bw.diff(1)

    rsi14 = _rsi(c, 14)
    out[f"{prefix}_rsi14"] = rsi14
    out[f"{prefix}_rsi14_diff1"] = rsi14.diff(1)
    out[f"{prefix}_rsi14_lag1"] = rsi14.shift(1)

    price_cols = list(out.columns)

    # 3. Order Flow Imbalance (OFI / Taker Sentiment), Volume & Whale Trade Size diffs/lags
    ofi = (2.0 * tbqv - qv) / (qv + 1e-12)
    ofi_vol = (2.0 * tbv - v) / (v + 1e-12)
    out[f"{prefix}_ofi_lag0"] = ofi
    out[f"{prefix}_ofi_vol_lag0"] = ofi_vol
    out[f"{prefix}_ofi_diff1"] = ofi.diff(1)
    for lag in (1, 2, 3, 6, 12):
        out[f"{prefix}_ofi_lag{lag}"] = ofi.shift(lag)

    # Multi-bar cumulative order flow imbalance
    net_taker_q = 2.0 * tbqv - qv
    for win in (3, 6, 12, 48):
        cum_ofi = net_taker_q.rolling(win).sum() / (qv.rolling(win).sum() + 1e-12)
        out[f"{prefix}_ofi_w{win}"] = cum_ofi
        out[f"{prefix}_ofi_w{win}_diff1"] = cum_ofi.diff(1)

    # Order flow vs return divergence (absorption indicator)
    out[f"{prefix}_ofi_ret_div_w3"] = out[f"{prefix}_ofi_w3"] - np.tanh(out[f"{prefix}_ret_w3"] * 200.0)
    out[f"{prefix}_ofi_ret_div_w12"] = out[f"{prefix}_ofi_w12"] - np.tanh(out[f"{prefix}_ret_w12"] * 100.0)

    # Volume shocks, diffs & lags
    qv_med48 = qv.rolling(48).median()
    qv_med288 = qv.rolling(288).median()
    lqv_rel48 = np.log((qv + 1.0) / (qv_med48 + 1.0))
    lqv_rel288 = np.log((qv + 1.0) / (qv_med288 + 1.0))
    lqv_diff1 = np.log(qv + 1.0).diff(1)
    out[f"{prefix}_lqv_rel48"] = lqv_rel48
    out[f"{prefix}_lqv_rel288"] = lqv_rel288
    out[f"{prefix}_lqv_diff1"] = lqv_diff1
    for lag in (1, 2, 3):
        out[f"{prefix}_lqv_rel48_lag{lag}"] = lqv_rel48.shift(lag)
        out[f"{prefix}_lqv_diff1_lag{lag}"] = lqv_diff1.shift(lag)

    # Trade count & Average Trade Size ("Whale flow") diffs & lags
    cnt_med48 = cnt.rolling(48).median()
    lcnt_rel48 = np.log((cnt + 1.0) / (cnt_med48 + 1.0))
    avg_size = qv / (cnt + 1.0)
    size_med48 = avg_size.rolling(48).median()
    lsize_rel48 = np.log((avg_size + 1.0) / (size_med48 + 1.0))
    out[f"{prefix}_lcnt_rel48"] = lcnt_rel48
    out[f"{prefix}_lcnt_diff1"] = np.log(cnt + 1.0).diff(1)
    out[f"{prefix}_lsize_rel48"] = lsize_rel48
    out[f"{prefix}_lsize_diff1"] = lsize_rel48.diff(1)
    out[f"{prefix}_lsize_lag1"] = lsize_rel48.shift(1)
    out[f"{prefix}_signed_whale_flow"] = ofi * lsize_rel48
    out[f"{prefix}_signed_whale_flow_w6"] = (ofi * lsize_rel48).rolling(6).mean()

    flow_cols = [col for col in out.columns if col not in price_cols]
    return out, price_cols, flow_cols


def build_dataset_bundle(target_symbol: str = "SOLUSDT", use_latest_intraday: bool = False) -> DatasetBundle:
    """Build complete feature and multi-horizon target bundle for target_symbol ('SOLUSDT' or 'BTCUSDT')."""
    if target_symbol not in ("SOLUSDT", "BTCUSDT"):
        raise ValueError(f"Unsupported target_symbol: {target_symbol}")
    partner_symbol = "BTCUSDT" if target_symbol == "SOLUSDT" else "SOLUSDT"

    frames, hashes_5m = _load_5m_core(use_latest_intraday=use_latest_intraday)
    df_tgt = frames[target_symbol]
    idx = df_tgt.index

    funding_info, mark_basis_1h, hashes_fm = _load_funding_and_mark(idx, use_latest_intraday=use_latest_intraday)
    b4_5m, dv_5m, hashes_ext = _load_spot_basis_and_dvol(idx)

    provenance = {}
    provenance.update(hashes_5m)
    provenance.update(hashes_fm)
    provenance.update(hashes_ext)

    # 1. Target & Partner full 5m price + order-flow blocks
    f_tgt, tgt_price_cols, tgt_flow_cols = _symbol_price_and_flow_block(df_tgt, "tgt")
    f_ptr, ptr_price_cols, ptr_flow_cols = _symbol_price_and_flow_block(frames[partner_symbol], "ptr")

    # Compact cross-asset context from ETH & BNB
    c_eth = frames["ETHUSDT"]["close"].astype(float)
    c_bnb = frames["BNBUSDT"]["close"].astype(float)
    qv_eth = frames["ETHUSDT"]["quote_volume"].astype(float)
    tbqv_eth = frames["ETHUSDT"]["taker_buy_quote_volume"].astype(float)
    eth_ofi = (2.0 * tbqv_eth - qv_eth) / (qv_eth + 1e-12)

    cross_df = pd.DataFrame(index=idx)
    for win in (1, 3, 6, 12, 48):
        r_t = np.log(df_tgt["close"].astype(float) / df_tgt["close"].astype(float).shift(win))
        r_p = np.log(frames[partner_symbol]["close"].astype(float) / frames[partner_symbol]["close"].astype(float).shift(win))
        r_e = np.log(c_eth / c_eth.shift(win))
        r_b = np.log(c_bnb / c_bnb.shift(win))
        cross_df[f"x_spread_tgt_ptr_w{win}"] = r_t - r_p
        cross_df[f"x_spread_tgt_ptr_w{win}_diff1"] = (r_t - r_p).diff(1)
        cross_df[f"x_eth_ret_w{win}"] = r_e
        cross_df[f"x_bnb_ret_w{win}"] = r_b
        # Cross-sectional dispersion across Core4
        mat = np.vstack([r_t.to_numpy(), r_p.to_numpy(), r_e.to_numpy(), r_b.to_numpy()])
        cross_df[f"x_core4_disp_w{win}"] = np.std(mat, axis=0)
        cross_df[f"x_core4_mean_w{win}"] = np.mean(mat, axis=0)

    for lag in (1, 2, 3):
        cross_df[f"x_spread_tgt_ptr_w1_lag{lag}"] = cross_df["x_spread_tgt_ptr_w1"].shift(lag)

    # Rolling 4h beta & beta-adjusted residual of target on partner
    r1_t = f_tgt["tgt_ret_lag0"]
    r1_p = f_ptr["ptr_ret_lag0"]
    cov48 = r1_t.rolling(48).cov(r1_p)
    var48 = r1_p.rolling(48).var()
    beta48 = (cov48 / (var48 + 1e-12)).clip(-5.0, 5.0)
    cross_df["x_beta48_tgt_ptr"] = beta48
    cross_df["x_beta_resid_w1"] = r1_t - beta48 * r1_p
    cross_df["x_beta_resid_w3"] = f_tgt["tgt_ret_w3"] - beta48 * f_ptr["ptr_ret_w3"]
    cross_df["x_beta_resid_w12"] = f_tgt["tgt_ret_w12"] - beta48 * f_ptr["ptr_ret_w12"]
    cross_df["x_ofi_spread_tgt_ptr"] = f_tgt["tgt_ofi_lag0"] - f_ptr["ptr_ofi_lag0"]
    cross_df["x_ofi_spread_w6"] = f_tgt["tgt_ofi_w6"] - f_ptr["ptr_ofi_w6"]
    cross_df["x_eth_ofi_lag0"] = eth_ofi
    cross_df["x_eth_ofi_w6"] = eth_ofi.rolling(6).mean()

    # 4. Funding & Basis block (diffs and lags)
    fb_df = pd.DataFrame(index=idx)
    fr_tgt = funding_info[target_symbol][2]
    fr_ptr = funding_info[partner_symbol][2]
    fr_eth = funding_info["ETHUSDT"][2]
    fb_df["fb_tgt_funding_lvl"] = fr_tgt
    fb_df["fb_tgt_funding_diff8h"] = fr_tgt.diff(96)     # 1 settlement (8h = 96 x 5m bars)
    fb_df["fb_tgt_funding_diff24h"] = fr_tgt.diff(288)   # 3 settlements (24h)
    fb_df["fb_tgt_funding_lag8h"] = fr_tgt.shift(96)
    fb_df["fb_ptr_funding_lvl"] = fr_ptr
    fb_df["fb_ptr_funding_diff8h"] = fr_ptr.diff(96)
    fb_df["fb_funding_spread_tgt_ptr"] = fr_tgt - fr_ptr
    fb_df["fb_funding_spread_diff8h"] = (fr_tgt - fr_ptr).diff(96)
    fb_df["fb_core3_funding_disp"] = np.std(
        np.vstack([fr_tgt.to_numpy(), fr_ptr.to_numpy(), fr_eth.to_numpy()]), axis=0
    )

    # 1h Mark-Trade basis & diffs/lags (1h = 12 x 5m bars)
    mb_tgt = mark_basis_1h[target_symbol]
    mb_ptr = mark_basis_1h[partner_symbol]
    fb_df["fb_tgt_mark_basis_1h"] = mb_tgt
    fb_df["fb_tgt_mark_basis_diff1h"] = mb_tgt.diff(12)
    fb_df["fb_tgt_mark_basis_lag1h"] = mb_tgt.shift(12)
    fb_df["fb_ptr_mark_basis_1h"] = mb_ptr
    fb_df["fb_ptr_mark_basis_diff1h"] = mb_ptr.diff(12)

    # 4h Spot-Futures basis (fill any post-2026-09-13 tail with 0 diff / neutral so no NaN drops 2026-09)
    for c_name in b4_5m.columns:
        fb_df[f"fb_{c_name}"] = b4_5m[c_name].fillna(0.0)

    # Hours until next 8h funding settlement (00:00, 08:00, 16:00 UTC) and UTC session sin/cos
    close_ts = idx + pd.Timedelta(minutes=5)
    minutes_of_day = close_ts.hour * 60 + close_ts.minute
    mins_to_funding = (480 - (minutes_of_day % 480)) % 480
    fb_df["fb_hours_to_funding"] = mins_to_funding / 60.0
    fb_df["fb_hour_sin"] = np.sin(2.0 * np.pi * minutes_of_day / 1440.0)
    fb_df["fb_hour_cos"] = np.cos(2.0 * np.pi * minutes_of_day / 1440.0)

    # 5. Options DVOL & VRP block
    opt_df = dv_5m.copy()
    # Variance risk premium: DVOL (annual %) / 100 - annualized 24h realized vol
    ann_factor = np.sqrt(288.0 * 365.0)
    btc_rv24h_ann = (
        f_tgt["tgt_rv288"] * ann_factor
        if target_symbol == "BTCUSDT"
        else f_ptr["ptr_rv288"] * ann_factor
    )
    tgt_rv24h_ann = f_tgt["tgt_rv288"] * ann_factor
    opt_df["dvol_btc_vrp"] = opt_df["dvol_BTC_lvl"] / 100.0 - btc_rv24h_ann
    opt_df["dvol_btc_vrp_diff1d"] = opt_df["dvol_btc_vrp"].diff(288)
    opt_df["dvol_tgt_iv_rv_ratio"] = (opt_df["dvol_BTC_lvl"] / 100.0) / (tgt_rv24h_ann + 1e-6)

    # Combine all feature blocks
    X = pd.concat([f_tgt, f_ptr, cross_df, fb_df, opt_df], axis=1).astype(np.float32)

    feature_groups = {
        "OWN_PRICE": list(tgt_price_cols),
        "CROSS_ASSET": list(ptr_price_cols) + list(cross_df.columns),
        "ORDER_FLOW_SENTIMENT": list(tgt_flow_cols) + list(ptr_flow_cols),
        "FUNDING_BASIS": list(fb_df.columns),
        "OPTIONS_DVOL": list(opt_df.columns),
    }

    # Construct multi-horizon targets Y0 and Y1 starting at next bar open O_{i+1}
    o_raw = df_tgt["open"].to_numpy(dtype=np.float64)
    h_raw = df_tgt["high"].to_numpy(dtype=np.float64)
    l_raw = df_tgt["low"].to_numpy(dtype=np.float64)
    c_raw = df_tgt["close"].to_numpy(dtype=np.float64)
    n = len(df_tgt)

    o_next = np.full(n, np.nan, dtype=np.float64)
    h_next = np.full(n, np.nan, dtype=np.float64)
    l_next = np.full(n, np.nan, dtype=np.float64)
    c_next = np.full(n, np.nan, dtype=np.float64)
    o_next[:-1] = o_raw[1:]
    h_next[:-1] = h_raw[1:]
    l_next[:-1] = l_raw[1:]
    c_next[:-1] = c_raw[1:]

    y0_ret: Dict[int, np.ndarray] = {}
    y1_range: Dict[int, np.ndarray] = {}
    y1_mae_long: Dict[int, np.ndarray] = {}
    y1_mae_short: Dict[int, np.ndarray] = {}

    s_high = pd.Series(h_raw)
    s_low = pd.Series(l_raw)

    for h_min, k_bars in HORIZON_BARS.items():
        # Forward window is bars [i+1 .. i+k_bars] inclusive
        c_end = np.full(n, np.nan, dtype=np.float64)
        c_end[:-k_bars] = c_raw[k_bars:]

        # Forward max high and min low over [i+1 .. i+k_bars]
        # rolling(k_bars) on shifted series: at index i+k_bars, rolling(k_bars) covers i+1..i+k_bars
        f_max_h = s_high.rolling(k_bars, min_periods=k_bars).max().shift(-k_bars).to_numpy(dtype=np.float64)
        f_min_l = s_low.rolling(k_bars, min_periods=k_bars).min().shift(-k_bars).to_numpy(dtype=np.float64)

        y0_ret[h_min] = (c_end - o_next) / o_next
        y1_range[h_min] = (f_max_h - f_min_l) / o_next
        y1_mae_long[h_min] = np.maximum(0.0, (o_next - f_min_l) / o_next)
        y1_mae_short[h_min] = np.maximum(0.0, (f_max_h - o_next) / o_next)

    f_ms, f_rate, _ = funding_info[target_symbol]
    mk_close_5m = mark_basis_1h[f"{target_symbol}_mark_close"].to_numpy(dtype=np.float64)

    return DatasetBundle(
        target_symbol=target_symbol,
        partner_symbol=partner_symbol,
        index=idx,
        open_next=o_next,
        high_next=h_next,
        low_next=l_next,
        close_next=c_next,
        open_raw=o_raw,
        high_raw=h_raw,
        low_raw=l_raw,
        close_raw=c_raw,
        features=X,
        feature_groups=feature_groups,
        y0_ret=y0_ret,
        y1_range=y1_range,
        y1_mae_long=y1_mae_long,
        y1_mae_short=y1_mae_short,
        funding_ms=f_ms,
        funding_rate=f_rate,
        mark_close_5m=mk_close_5m,
        provenance=provenance,
    )
