# -*- coding: utf-8 -*-
"""
Historical Market Data Auditor & Spot/Futures Segment Verifier (Phase 37.1)
===========================================================================
1. Downloads complete standard Spot 4h klines from Binance Spot REST API.
2. Downloads standard Futures 4h klines from Binance Futures REST API for reference.
3. Conducts segment-by-segment comparison (2020-2023, 2024-2025, 2026) between
   local parquet files, official Spot, and official Futures to determine the exact
   origin and identify any mixed segments.
4. Calculates cryptographic SHA-256 hashes for all datasets.
5. Emits an immutable data manifest and basis difference report.
"""

import os
import sys
import time
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import requests
import pandas as pd
import numpy as np

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from crypto_quant.data.data_manifest import (
    compute_file_sha256,
    audit_ohlcv_dataframe,
    compare_spot_vs_futures,
)

CORE4_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
START_TS = 1597104000000  # 2020-08-11 00:00:00 UTC
END_TS = 1790164800000    # 2026-09-23 00:00:00 UTC

SPOT_MIRRORS = [
    "https://api.binance.com",
    "https://data-api.binance.vision",
    "https://api1.binance.com",
    "https://api2.binance.com",
]

FUTURES_MIRRORS = [
    "https://fapi.binance.com",
]


def fetch_klines_paginated(
    symbol: str,
    market_type: str = "spot",
    start_ts: int = START_TS,
    end_ts: Optional[int] = None,
    interval: str = "4h",
) -> pd.DataFrame:
    """
    Fetches paginated klines from Binance REST API (Spot or USDS-M Futures).
    Handles rate limits, pagination, and returns clean, causal pd.DataFrame.
    """
    mirrors = SPOT_MIRRORS if market_type == "spot" else FUTURES_MIRRORS
    endpoint = "/api/v3/klines" if market_type == "spot" else "/fapi/v1/klines"
    limit = 1000

    all_rows = []
    curr_ts = start_ts

    print(f"[{market_type.upper()} DOWNLOAD] Starting {symbol} from ts={curr_ts}...")

    mirror_idx = 0
    consecutive_errors = 0

    while True:
        base_url = mirrors[mirror_idx % len(mirrors)]
        url = f"{base_url}{endpoint}"
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": limit,
            "startTime": curr_ts,
        }
        if end_ts is not None:
            params["endTime"] = end_ts

        data = None
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                consecutive_errors = 0
            else:
                print(f"Warning: HTTP {resp.status_code} from {base_url}: {resp.text[:80]}")
                mirror_idx += 1
                consecutive_errors += 1
                time.sleep(1)
        except Exception as e:
            print(f"Request error from {base_url}: {e}")
            mirror_idx += 1
            consecutive_errors += 1
            time.sleep(1)

        if consecutive_errors > 10:
            raise RuntimeError(f"Failed to fetch {symbol} after 10 retries across mirrors.")

        if not data:
            break

        all_rows.extend(data)
        last_open_ts = int(data[-1][0])
        last_close_ts = int(data[-1][6])

        # If last bar reached or returned less than limit
        if len(data) < limit:
            break

        next_ts = last_open_ts + 4 * 3600 * 1000
        if next_ts <= curr_ts:
            break
        curr_ts = next_ts
        time.sleep(0.05)

    if not all_rows:
        return pd.DataFrame()

    # Parse kline columns
    # [0: open_time, 1: open, 2: high, 3: low, 4: close, 5: volume, 6: close_time, 7: qvol, 8: trades, 9: tb_base, 10: tb_quote, 11: ignore]
    df = pd.DataFrame(
        all_rows,
        columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "qvol", "trades", "tb_base", "tb_quote", "ignore"
        ]
    )
    df["open_time"] = pd.to_datetime(df["open_time"].astype(np.int64), unit="ms")
    for col in ["open", "high", "low", "close", "volume", "qvol", "tb_base", "tb_quote"]:
        df[col] = df[col].astype(float)
    df["trades"] = df["trades"].astype(int)

    df = df.set_index("open_time").sort_index()
    df = df[~df.index.duplicated(keep="first")]

    print(f"[{market_type.upper()} COMPLETE] {symbol}: {len(df)} bars from {df.index.min()} to {df.index.max()}")
    return df


def segment_audit(
    local_df: pd.DataFrame,
    spot_df: pd.DataFrame,
    futures_df: pd.DataFrame,
    symbol: str,
) -> Dict[str, Any]:
    """
    Rigorously compares local parquet data against standard Spot and standard Futures
    across 3 distinct time segments:
      - Phase 1: 2020-08-11 to 2023-12-31 (In-sample historical foundation)
      - Phase 2: 2024-01-01 to 2025-12-31 (Development & calibration phase)
      - Phase 3: 2026-01-01 to 2026-09-22 (Recent observation period)
    """
    segments = {
        "Phase_1_2020_2023": ("2020-08-11", "2023-12-31 23:59:59"),
        "Phase_2_2024_2025": ("2024-01-01", "2025-12-31 23:59:59"),
        "Phase_3_2026": ("2026-01-01", "2026-09-23 00:00:00"),
        "Full_Cycle": ("2020-08-11", "2026-09-23 00:00:00"),
    }

    # Ensure tz-naive for clean comparison
    l_df = local_df.copy()
    s_df = spot_df.copy()
    f_df = futures_df.copy()

    for d in [l_df, s_df, f_df]:
        if d.index.tz is not None:
            d.index = d.index.tz_localize(None)

    results = {}

    for seg_name, (start_dt, end_dt) in segments.items():
        l_sub = l_df.loc[start_dt:end_dt]
        s_sub = s_df.loc[start_dt:end_dt]
        f_sub = f_df.loc[start_dt:end_dt]

        # Common intersection with local
        common_spot = l_sub.index.intersection(s_sub.index)
        common_fut = l_sub.index.intersection(f_sub.index)

        spot_mae = float(np.mean(np.abs(l_sub.loc[common_spot, "close"] - s_sub.loc[common_spot, "close"]))) if len(common_spot) > 0 else None
        fut_mae = float(np.mean(np.abs(l_sub.loc[common_fut, "close"] - f_sub.loc[common_fut, "close"]))) if len(common_fut) > 0 else None
        spot_max_diff = float(np.max(np.abs(l_sub.loc[common_spot, "close"] - s_sub.loc[common_spot, "close"]))) if len(common_spot) > 0 else None
        fut_max_diff = float(np.max(np.abs(l_sub.loc[common_fut, "close"] - f_sub.loc[common_fut, "close"]))) if len(common_fut) > 0 else None

        # Bar-by-bar strict match counting
        bars_spot_match = 0
        bars_fut_match = 0
        bars_both_match = 0
        bars_unknown = 0

        all_common = l_sub.index.intersection(s_sub.index).intersection(f_sub.index)
        n_common = len(all_common)

        if n_common > 0:
            l_aligned = l_sub.reindex(all_common)
            s_aligned = s_sub.reindex(all_common)
            f_aligned = f_sub.reindex(all_common)

            for col in ["open", "high", "low", "close"]:
                s_diff_col = (l_aligned[col] - s_aligned[col]).abs() <= 1e-3
                f_diff_col = (l_aligned[col] - f_aligned[col]).abs() <= 1e-3
                if col == "open":
                    is_spot_match = s_diff_col
                    is_fut_match = f_diff_col
                else:
                    is_spot_match = is_spot_match & s_diff_col
                    is_fut_match = is_fut_match & f_diff_col

            bars_both_match = int((is_spot_match & is_fut_match).sum())
            bars_spot_only = int((is_spot_match & ~is_fut_match).sum())
            bars_fut_only = int((is_fut_match & ~is_spot_match).sum())
            bars_unknown = int((~is_spot_match & ~is_fut_match).sum())

            bars_spot_match = bars_spot_only + bars_both_match
            bars_fut_match = bars_fut_only + bars_both_match

        # Qualification determination based on bar-by-bar match percentage
        fut_match_pct = (bars_fut_match / n_common * 100.0) if n_common > 0 else 0.0
        spot_match_pct = (bars_spot_match / n_common * 100.0) if n_common > 0 else 0.0
        unknown_pct = (bars_unknown / n_common * 100.0) if n_common > 0 else 0.0

        if fut_match_pct >= 99.9:
            qual = "VERIFIED_FUTURES_100PCT"
        elif spot_match_pct >= 99.9:
            qual = "VERIFIED_SPOT_100PCT"
        elif fut_match_pct > spot_match_pct and fut_match_pct > 80.0:
            qual = f"PREDOMINANTLY_FUTURES_{fut_match_pct:.1f}PCT"
        elif spot_match_pct > fut_match_pct and spot_match_pct > 80.0:
            qual = f"PREDOMINANTLY_SPOT_{spot_match_pct:.1f}PCT"
        elif unknown_pct > 50.0:
            qual = f"SOURCE_UNKNOWN_{unknown_pct:.1f}PCT"
        else:
            qual = f"MIXED_FUT_{fut_match_pct:.1f}_SPOT_{spot_match_pct:.1f}"

        results[seg_name] = {
            "local_bars": len(l_sub),
            "common_bars_evaluated": n_common,
            "bars_matching_futures": bars_fut_match,
            "bars_matching_spot": bars_spot_match,
            "bars_source_unknown": bars_unknown,
            "futures_match_pct": fut_match_pct,
            "spot_match_pct": spot_match_pct,
            "unknown_pct": unknown_pct,
            "spot_mae": spot_mae,
            "futures_mae": fut_mae,
            "spot_max_diff": spot_max_diff,
            "futures_max_diff": fut_max_diff,
            "empirical_origin": qual,
        }

    return results


def main():
    print("=" * 70)
    print("PHASE 37.1: HISTORICAL DATA SOURCE AUDIT & IMMUTABLE MANIFEST")
    print("=" * 70)

    spot_dir = repo_root / "data" / "spot"
    spot_dir.mkdir(parents=True, exist_ok=True)

    report_dir = repo_root / "reports" / "data_audit"
    report_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "metadata": {
            "audit_timestamp_utc": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M:%S UTC"),
            "audit_standard": "Immutable Multi-Market OHLCV Verification Protocol (Phase 37.1)",
            "symbols": CORE4_SYMBOLS,
            "interval": "4h",
        },
        "datasets": {},
        "segment_audits": {},
        "basis_comparisons": {},
    }

    # Step 1: Download / Cache standard Spot datasets
    spot_dfs = {}
    for sym in CORE4_SYMBOLS:
        spot_parquet_path = spot_dir / f"{sym}_4h_2020_2026.parquet"
        if spot_parquet_path.exists():
            print(f"[CACHE HIT] Loading existing Spot dataset: {spot_parquet_path}")
            df_spot = pd.read_parquet(spot_parquet_path)
            if df_spot.index.tz is not None:
                df_spot.index = df_spot.index.tz_localize(None)
        else:
            df_spot = fetch_klines_paginated(sym, market_type="spot", start_ts=START_TS, end_ts=END_TS)
            df_spot.to_parquet(spot_parquet_path)
            print(f"[SAVED] Standard Spot dataset saved to {spot_parquet_path}")

        spot_dfs[sym] = df_spot
        manifest["datasets"][f"spot_{sym}"] = {
            "market_type": "Binance Spot (REST /api/v3/klines)",
            "filepath": str(spot_parquet_path.relative_to(repo_root)),
            "sha256": compute_file_sha256(str(spot_parquet_path)),
            "audit": audit_ohlcv_dataframe(df_spot),
        }

    # Step 2: Download / Cache standard reference Futures datasets
    futures_dir = repo_root / "data" / "futures_reference"
    futures_dir.mkdir(parents=True, exist_ok=True)

    futures_dfs = {}
    for sym in CORE4_SYMBOLS:
        fut_parquet_path = futures_dir / f"{sym}_4h_2020_2026.parquet"
        if fut_parquet_path.exists():
            print(f"[CACHE HIT] Loading existing Futures reference dataset: {fut_parquet_path}")
            df_fut = pd.read_parquet(fut_parquet_path)
            if df_fut.index.tz is not None:
                df_fut.index = df_fut.index.tz_localize(None)
        else:
            df_fut = fetch_klines_paginated(sym, market_type="futures", start_ts=START_TS, end_ts=END_TS)
            df_fut.to_parquet(fut_parquet_path)
            print(f"[SAVED] Standard Futures reference saved to {fut_parquet_path}")

        futures_dfs[sym] = df_fut
        manifest["datasets"][f"futures_reference_{sym}"] = {
            "market_type": "Binance USDS-M Futures (REST /fapi/v1/klines)",
            "filepath": str(fut_parquet_path.relative_to(repo_root)),
            "sha256": compute_file_sha256(str(fut_parquet_path)),
            "audit": audit_ohlcv_dataframe(df_fut),
        }

    # Step 3: Audit existing local datasets and run Segment Verification
    local_dfs = {}
    for sym in CORE4_SYMBOLS:
        local_path = repo_root / "data" / f"{sym}_4h_2020_2026.parquet"
        if not local_path.exists():
            raise FileNotFoundError(f"Missing existing local dataset: {local_path}")

        df_local = pd.read_parquet(local_path)
        if df_local.index.tz is not None:
            df_local.index = df_local.index.tz_localize(None)
        local_dfs[sym] = df_local

        manifest["datasets"][f"existing_local_{sym}"] = {
            "market_type": "Existing Local Repository Dataset (data/{symbol}_4h_2020_2026.parquet)",
            "filepath": str(local_path.relative_to(repo_root)),
            "sha256": compute_file_sha256(str(local_path)),
            "audit": audit_ohlcv_dataframe(df_local),
        }

        # Run segment audit
        seg_res = segment_audit(df_local, spot_dfs[sym], futures_dfs[sym], sym)
        manifest["segment_audits"][sym] = seg_res

        # Run basis comparison between Spot and Futures
        basis_res = compare_spot_vs_futures(spot_dfs[sym], futures_dfs[sym], sym)
        manifest["basis_comparisons"][sym] = basis_res

    # Step 4: Write JSON manifest
    manifest_path = report_dir / "immutable_data_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n[MANIFEST EMITTED] Saved to {manifest_path}")

    # Step 5: Write Markdown Basis & Segment Verification Report
    md_path = report_dir / "spot_vs_futures_basis_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Market Data Source Verification & Spot vs Futures Basis Report\n")
        f.write("# 历史行情来源分段核实与现货合约基差报告\n\n")
        f.write(f"> **Audit Timestamp**: {manifest['metadata']['audit_timestamp_utc']}\n\n")

        f.write("## 1. Local Parquet Dataset Segment-by-Segment Origin Attribution (Bar-by-Bar)\n")
        f.write("## 本地现有 Parquet 数据集历史各时段真实来源实证判定（逐根精准对齐）\n\n")
        f.write("| Symbol | Segment | Local Bars | Eval Bars | Futures Match | Spot Match | Unknown | Fut Match % | Spot Match % | Spot MAE | Fut MAE | Empirical Qualification |\n")
        f.write("| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |\n")

        for sym in CORE4_SYMBOLS:
            for seg, d in manifest["segment_audits"][sym].items():
                s_mae = f"${d['spot_mae']:.4f}" if d['spot_mae'] is not None else "N/A"
                f_mae = f"${d['futures_mae']:.4f}" if d['futures_mae'] is not None else "N/A"
                f.write(
                    f"| **{sym}** | {seg} | {d['local_bars']} | {d['common_bars_evaluated']} | "
                    f"{d['bars_matching_futures']} | {d['bars_matching_spot']} | {d['bars_source_unknown']} | "
                    f"{d['futures_match_pct']:.1f}% | {d['spot_match_pct']:.1f}% | {s_mae} | {f_mae} | **{d['empirical_origin']}** |\n"
                )

        f.write("\n---\n\n")
        f.write("## 2. Spot vs Futures Basis & Signal Divergence (Common Timestamps)\n")
        f.write("## 现货与合约基差分布与趋势信号分歧分析\n\n")
        f.write("| Symbol | Overlap Range | Mean Basis % | Min Basis % | Max Basis % | 99th Pct Basis % | Return Corr | EMA200 Mismatch % | Donchian120 Mismatch % |\n")
        f.write("| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n")

        for sym in CORE4_SYMBOLS:
            b = manifest["basis_comparisons"][sym]
            b_pct = b["basis_pct"]
            sig = b["signal_divergence"]
            f.write(
                f"| **{sym}** | {b['overlap_start'][:10]} ~ {b['overlap_end'][:10]} | "
                f"{b_pct['mean_pct']:+.3f}% | {b_pct['min_pct']:+.3f}% | {b_pct['max_pct']:+.3f}% | {b_pct['p99_pct']:+.3f}% | "
                f"{b['returns_correlation']:.5f} | {sig['ema200_bull_mismatch_pct']:.2f}% ({sig['ema200_bull_mismatch_bars']} bars) | "
                f"{sig['donchian120_breakout_mismatch_pct']:.2f}% ({sig['donchian120_breakout_mismatch_bars']} bars) |\n"
            )

        f.write("\n---\n\n")
        f.write("## 3. Cryptographic SHA-256 Dataset Fingerprints / 数据集哈希指纹\n\n")
        f.write("| Dataset Key | File Path | Total Bars | SHA-256 Fingerprint |\n")
        f.write("| :--- | :--- | :---: | :--- |\n")
        for k, info in manifest["datasets"].items():
            f.write(f"| `{k}` | `{info['filepath']}` | {info['audit']['total_bars']} | `{info['sha256']}` |\n")

        f.write("\n---\n\n")
        f.write("## 4. Methodological Conclusions & Action Directives / 方法论结论与操作准则\n\n")
        f.write("1. **Local Data Origin Verified / 本地数据定性实证完成**:\n")
        f.write("   - The segment audit definitively shows whether local data matches standard futures or spot across each epoch.\n")
        f.write("2. **Strict Multi-Market Separation / 严格独立分库**:\n")
        f.write("   - Standard Spot data is now independently housed under `data/spot/` and standard Futures under `data/futures_reference/`.\n")
        f.write("   - Re-simulations of Spot trend strategies will strictly consume `data/spot/`, completely eliminating futures basis contamination.\n")

    print(f"[REPORT EMITTED] Saved to {md_path}")
    print("\n[SUCCESS] Phase 37.1 completed successfully.")


if __name__ == "__main__":
    main()
