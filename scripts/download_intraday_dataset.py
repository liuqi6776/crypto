# -*- coding: utf-8 -*-
"""
Download Intraday Dataset Script
日内高频数据集下载与同步脚本
"""

import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

from crypto_quant.data.intraday_manager import (
    sync_intraday_symbol,
    validate_intraday_dataframe,
    CORE4_SYMBOLS,
    DEFAULT_INTRADAY_DIR,
)


def main():
    parser = argparse.ArgumentParser(description="Download & cache intraday datasets.")
    parser.add_argument("--symbols", nargs="+", default=CORE4_SYMBOLS, help="Trading symbols")
    parser.add_argument("--intervals", nargs="+", default=["15m", "5m"], help="K-line intervals")
    parser.add_argument("--market-types", nargs="+", default=["spot", "futures"], help="Market types: spot, futures")
    parser.add_argument("--start-date", type=str, default="2024-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--workers", type=int, default=4, help="Parallel download workers")
    args = parser.parse_args()

    tasks = []
    for m in args.market_types:
        for itv in args.intervals:
            for sym in args.symbols:
                tasks.append((sym, itv, m, args.start_date))

    print(f"=== Starting Download of {len(tasks)} Intraday Datasets (Workers={args.workers}) ===")
    t0 = time.time()

    def _worker(task):
        sym, itv, m, start_date = task
        t_start = time.time()
        df = sync_intraday_symbol(sym, interval=itv, market_type=m, start_date=start_date)
        duration = round(time.time() - t_start, 2)
        val = validate_intraday_dataframe(df, itv)
        return (sym, itv, m, len(df), duration, val)

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(_worker, t): t for t in tasks}
        for fut in as_completed(futures):
            sym, itv, m, n_bars, dur, val = fut.result()
            status = "VALID" if val["is_valid"] else f"INVALID(viol={val['ohlc_violations']}, gaps={val['missing_bars']})"
            print(f"[{status}] {sym} {itv} {m}: {n_bars} bars downloaded in {dur}s (Start: {val['start_time']} -> End: {val['end_time']})")

    print(f"=== Completed All Downloads in {round(time.time() - t0, 2)}s ===")


if __name__ == "__main__":
    main()
