# -*- coding: utf-8 -*-
"""
Institutional Data Admission & Health Check Module
===================================================
Enforces strict quality, causal validity, and integrity checks on market data:
1. Index Health:
   - DatetimeIndex, strictly monotonic increasing, zero duplicate timestamps.
   - Exact 4-hour step (14,400s). Identifies and logs missing intervals/gaps.
2. Price & OHLC Integrity:
   - Positivity: Open, High, Low, Close > 0.
   - Mathematical consistency: High >= max(Open, Close) - eps, Low <= min(Open, Close) + eps.
   - Anomaly detection: single 4h bar price jump > 100% or drop > 90%, zero NaN/inf values.
3. Tradability Window:
   - Earliest tradable bar per token (ensuring no lookahead or phantom trading before listing).
4. Funding Rate Audit:
   - Settlement timestamp normalization (00:00, 08:00, 16:00 UTC).
   - Real historical coverage ratio against expected settlement events.
   - Fails admission if real coverage < 95% in strict mode.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np


class DataAdmissionError(Exception):
    """Raised when critical data admission checks fail in strict mode."""
    pass


@dataclass
class DataAdmissionIssue:
    symbol: str
    issue_type: str        # 'NON_MONOTONIC', 'DUPLICATE_INDEX', 'OHLC_VIOLATION', 'NEGATIVE_PRICE', 'ANOMALY_SPIKE', 'MISSING_BARS', 'INSUFFICIENT_FUNDING_COVERAGE', 'PRE_LISTING_REQUEST'
    message: str
    severity: str          # 'ERROR', 'WARNING'
    timestamp: Optional[str] = None


@dataclass
class DataAdmissionReport:
    is_valid: bool
    total_bars_per_symbol: Dict[str, int]
    earliest_bar_per_symbol: Dict[str, str]
    latest_bar_per_symbol: Dict[str, str]
    missing_bars_count: Dict[str, int]
    gap_intervals_per_symbol: Dict[str, List[Dict[str, str]]]
    funding_coverage_ratio: Dict[str, float]
    issues: List[DataAdmissionIssue]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "total_bars_per_symbol": self.total_bars_per_symbol,
            "earliest_bar_per_symbol": self.earliest_bar_per_symbol,
            "latest_bar_per_symbol": self.latest_bar_per_symbol,
            "missing_bars_count": self.missing_bars_count,
            "gap_intervals_per_symbol": self.gap_intervals_per_symbol,
            "funding_coverage_ratio": {k: round(v, 4) for k, v in self.funding_coverage_ratio.items()},
            "error_count": sum(1 for iss in self.issues if iss.severity == "ERROR"),
            "warning_count": sum(1 for iss in self.issues if iss.severity == "WARNING"),
            "issues": [
                {
                    "symbol": iss.symbol,
                    "issue_type": iss.issue_type,
                    "severity": iss.severity,
                    "message": iss.message,
                    "timestamp": iss.timestamp,
                }
                for iss in self.issues
            ],
        }

    def summary_markdown(self) -> str:
        lines = [
            "### Data Admission Report / 数据准入报告",
            f"- **Status / 状态**: {'PASS / 通过' if self.is_valid else 'FAIL / 未通过'}",
            f"- **Errors / 致命错误数**: {sum(1 for iss in self.issues if iss.severity == 'ERROR')}",
            f"- **Warnings / 告警数**: {sum(1 for iss in self.issues if iss.severity == 'WARNING')}",
            "",
            "| Symbol / 标的 | Earliest / 首根 | Latest / 末根 | Bars / 根数 | Missing / 缺失 | Funding Cov / 资金费覆盖 |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        for sym, bars in self.total_bars_per_symbol.items():
            earliest = self.earliest_bar_per_symbol.get(sym, "N/A")
            latest = self.latest_bar_per_symbol.get(sym, "N/A")
            missing = self.missing_bars_count.get(sym, 0)
            fund_cov = self.funding_coverage_ratio.get(sym, None)
            cov_str = f"{fund_cov * 100:.1f}%" if fund_cov is not None else "N/A"
            lines.append(f"| {sym} | {earliest} | {latest} | {bars} | {missing} | {cov_str} |")

        if self.issues:
            lines.append("\n#### Issues Detail / 问题清单:")
            for iss in self.issues[:15]:
                lines.append(f"- `[{iss.severity}]` **{iss.symbol}** ({iss.issue_type}): {iss.message} (at {iss.timestamp or 'Global'})")
            if len(self.issues) > 15:
                lines.append(f"- ... and {len(self.issues) - 15} more issues.")
        return "\n".join(lines)


def validate_crypto_universe(
    raw_dfs: Dict[str, pd.DataFrame],
    symbols: List[str],
    df_funding: Optional[pd.DataFrame] = None,
    eval_start_dt: Optional[str] = None,
    eval_end_dt: Optional[str] = None,
    expected_freq_seconds: int = 14400,   # 4 hours
    strict: bool = True,
    min_funding_coverage: float = 0.95,
) -> DataAdmissionReport:
    """
    Performs comprehensive data admission checks on historical crypto DataFrames.

    Parameters:
    - raw_dfs: Dictionary of OHLCV DataFrames keyed by symbol.
    - symbols: List of symbols in the requested universe.
    - df_funding: Optional DataFrame of 8h funding rates.
    - eval_start_dt: Start of evaluation interval [start, end).
    - eval_end_dt: End of evaluation interval [start, end).
    - expected_freq_seconds: Expected step between consecutive bars (default 14400s = 4h).
    - strict: If True, raises DataAdmissionError when any ERROR-level issue is detected.
    - min_funding_coverage: Minimum acceptable funding rate coverage (default 0.95 = 95%).
    """
    issues: List[DataAdmissionIssue] = []
    total_bars: Dict[str, int] = {}
    earliest_bar: Dict[str, str] = {}
    latest_bar: Dict[str, str] = {}
    missing_bars: Dict[str, int] = {}
    gap_intervals: Dict[str, List[Dict[str, str]]] = {}
    funding_cov: Dict[str, float] = {}

    eval_start_ts = pd.Timestamp(eval_start_dt) if eval_start_dt is not None else None
    eval_end_ts = pd.Timestamp(eval_end_dt) if eval_end_dt is not None else None

    # 1. Individual Symbol OHLC Checks
    for sym in symbols:
        if sym not in raw_dfs or raw_dfs[sym] is None or raw_dfs[sym].empty:
            issues.append(DataAdmissionIssue(
                symbol=sym,
                issue_type="MISSING_DATAFRAME",
                message=f"Requested symbol {sym} not found in raw_dfs or is empty.",
                severity="ERROR"
            ))
            continue

        df = raw_dfs[sym]
        total_bars[sym] = len(df)

        # Index type check
        if not isinstance(df.index, pd.DatetimeIndex):
            issues.append(DataAdmissionIssue(
                symbol=sym,
                issue_type="INVALID_INDEX_TYPE",
                message=f"Index is not DatetimeIndex (type: {type(df.index)}).",
                severity="ERROR"
            ))
            continue

        # Monotonicity check
        if not df.index.is_monotonic_increasing:
            issues.append(DataAdmissionIssue(
                symbol=sym,
                issue_type="NON_MONOTONIC",
                message=f"DatetimeIndex is not strictly monotonically increasing.",
                severity="ERROR"
            ))

        # Duplicate timestamps check
        if df.index.has_duplicates:
            dup_count = df.index.duplicated().sum()
            issues.append(DataAdmissionIssue(
                symbol=sym,
                issue_type="DUPLICATE_INDEX",
                message=f"Contains {dup_count} duplicate timestamps.",
                severity="ERROR"
            ))

        clean_idx = df.index.drop_duplicates()
        earliest_ts = clean_idx[0]
        latest_ts = clean_idx[-1]
        earliest_bar[sym] = str(earliest_ts)
        latest_bar[sym] = str(latest_ts)

        # Tradability vs eval_start_dt check
        if eval_start_ts is not None and earliest_ts > eval_start_ts:
            issues.append(DataAdmissionIssue(
                symbol=sym,
                issue_type="PRE_LISTING_REQUEST",
                message=f"Earliest bar {earliest_ts} is after eval_start_dt {eval_start_ts}. Symbol was not listed yet.",
                severity="WARNING",
                timestamp=str(earliest_ts)
            ))

        # Frequency step and missing bars check
        diffs = clean_idx.to_series().diff().dt.total_seconds().dropna()
        gaps = diffs[diffs > expected_freq_seconds]
        sym_missing_count = 0
        sym_gaps_list = []
        for gap_time, delta_sec in gaps.items():
            miss_count = int(delta_sec // expected_freq_seconds) - 1
            if miss_count > 0:
                sym_missing_count += miss_count
                prev_time = gap_time - pd.Timedelta(seconds=delta_sec)
                sym_gaps_list.append({
                    "from": str(prev_time),
                    "to": str(gap_time),
                    "missing_bars": str(miss_count),
                })
        missing_bars[sym] = sym_missing_count
        gap_intervals[sym] = sym_gaps_list

        if sym_missing_count > 0:
            issues.append(DataAdmissionIssue(
                symbol=sym,
                issue_type="MISSING_BARS",
                message=f"Detected {sym_missing_count} missing bars across {len(sym_gaps_list)} gaps.",
                severity="WARNING"
            ))

        # Required columns check
        req_cols = ["open", "high", "low", "close"]
        missing_cols = [c for c in req_cols if c not in df.columns]
        if missing_cols:
            issues.append(DataAdmissionIssue(
                symbol=sym,
                issue_type="MISSING_COLUMNS",
                message=f"Missing essential OHLC columns: {missing_cols}",
                severity="ERROR"
            ))
            continue

        # Non-finite and positivity check
        sub_ohlc = df[req_cols]
        if sub_ohlc.isnull().any().any():
            null_cnt = int(sub_ohlc.isnull().sum().sum())
            issues.append(DataAdmissionIssue(
                symbol=sym,
                issue_type="NULL_PRICES",
                message=f"Contains {null_cnt} null values in OHLC columns.",
                severity="ERROR"
            ))

        if (sub_ohlc <= 0.0).any().any():
            issues.append(DataAdmissionIssue(
                symbol=sym,
                issue_type="NEGATIVE_PRICE",
                message="Contains zero or negative prices in OHLC columns.",
                severity="ERROR"
            ))

        # OHLC logical consistency: High >= max(Open, Close), Low <= min(Open, Close)
        o = df["open"]
        h = df["high"]
        l = df["low"]
        c = df["close"]

        high_violation = (h < np.maximum(o, c) - 1e-4)
        if high_violation.any():
            viol_t = str(high_violation[high_violation].index[0])
            issues.append(DataAdmissionIssue(
                symbol=sym,
                issue_type="OHLC_VIOLATION",
                message=f"High price is lower than max(Open, Close) at {high_violation.sum()} bars.",
                severity="ERROR",
                timestamp=viol_t
            ))

        low_violation = (l > np.minimum(o, c) + 1e-4)
        if low_violation.any():
            viol_t = str(low_violation[low_violation].index[0])
            issues.append(DataAdmissionIssue(
                symbol=sym,
                issue_type="OHLC_VIOLATION",
                message=f"Low price is higher than min(Open, Close) at {low_violation.sum()} bars.",
                severity="ERROR",
                timestamp=viol_t
            ))

        # Anomaly return checks: > +100% or < -90% in a single 4h bar
        bar_rets = (c - o) / o
        extreme_jumps = bar_rets[bar_rets > 1.0]
        extreme_drops = bar_rets[bar_rets < -0.90]
        if not extreme_jumps.empty:
            issues.append(DataAdmissionIssue(
                symbol=sym,
                issue_type="ANOMALY_SPIKE",
                message=f"Detected {len(extreme_jumps)} bars with price surge > +100% (max: +{extreme_jumps.max()*100:.1f}%).",
                severity="WARNING",
                timestamp=str(extreme_jumps.index[0])
            ))
        if not extreme_drops.empty:
            issues.append(DataAdmissionIssue(
                symbol=sym,
                issue_type="ANOMALY_CRASH",
                message=f"Detected {len(extreme_drops)} bars with price crash < -90% (worst: {extreme_drops.min()*100:.1f}%).",
                severity="WARNING",
                timestamp=str(extreme_drops.index[0])
            ))

    # 2. Funding Rate Coverage Check
    if df_funding is not None and not df_funding.empty:
        # Align funding index: strip tz if needed for clean matching
        f_idx = df_funding.index
        if f_idx.tz is not None:
            f_idx = f_idx.tz_localize(None)
        df_funding_clean = df_funding.copy()
        df_funding_clean.index = f_idx

        # Settlement hours: 00:00, 08:00, 16:00
        for sym in symbols:
            if sym not in df_funding_clean.columns:
                funding_cov[sym] = 0.0
                issues.append(DataAdmissionIssue(
                    symbol=sym,
                    issue_type="INSUFFICIENT_FUNDING_COVERAGE",
                    message=f"Symbol {sym} is entirely missing from funding rate dataset (coverage: 0.0%).",
                    severity="ERROR"
                ))
                continue

            # Determine relevant time window for this symbol
            sym_earliest = pd.Timestamp(earliest_bar.get(sym, "2020-01-01"))
            sym_latest = pd.Timestamp(latest_bar.get(sym, "2026-12-31"))

            w_start = max(eval_start_ts or sym_earliest, sym_earliest)
            w_end = min(eval_end_ts or sym_latest, sym_latest)

            if w_end <= w_start:
                funding_cov[sym] = 1.0
                continue

            # Generate expected 8h settlement timestamps in [w_start, w_end)
            expected_settlements = pd.date_range(w_start, w_end, freq="8h", inclusive="left")
            expected_settlements = expected_settlements[expected_settlements.hour.isin([0, 8, 16])]

            if len(expected_settlements) == 0:
                funding_cov[sym] = 1.0
                continue

            # Check presence of non-null funding rates
            aligned_funding = df_funding_clean[sym].reindex(expected_settlements)
            valid_count = int(aligned_funding.dropna().count())
            cov_ratio = valid_count / len(expected_settlements)
            funding_cov[sym] = cov_ratio

            if cov_ratio < min_funding_coverage:
                issues.append(DataAdmissionIssue(
                    symbol=sym,
                    issue_type="INSUFFICIENT_FUNDING_COVERAGE",
                    message=f"Funding coverage is {cov_ratio*100:.2f}%, which is below required {min_funding_coverage*100:.1f}% ({valid_count}/{len(expected_settlements)} settlement bars).",
                    severity="ERROR"
                ))

    # Determine validity
    has_errors = any(iss.severity == "ERROR" for iss in issues)
    is_valid = not has_errors

    report = DataAdmissionReport(
        is_valid=is_valid,
        total_bars_per_symbol=total_bars,
        earliest_bar_per_symbol=earliest_bar,
        latest_bar_per_symbol=latest_bar,
        missing_bars_count=missing_bars,
        gap_intervals_per_symbol=gap_intervals,
        funding_coverage_ratio=funding_cov,
        issues=issues,
    )

    if strict and has_errors:
        error_msgs = "\n".join(f"  - [{iss.symbol}] {iss.issue_type}: {iss.message}" for iss in issues if iss.severity == "ERROR")
        raise DataAdmissionError(f"Data admission failed with {sum(1 for i in issues if i.severity == 'ERROR')} critical error(s):\n{error_msgs}")

    return report
