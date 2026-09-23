# -*- coding: utf-8 -*-
"""
Non-Intrusive Sidecar Orderbook Depth & Execution Logger (Phase 37.2)
====================================================================
Independent sidecar process that monitors and logs real-time Binance Spot
market execution conditions without modifying or disturbing the frozen
Forward Paper A/B state machine.

Key Features:
1. Pure sidecar architecture: reads market data via independent requests;
   zero interference with forward_dual_runner.py or status.json.
2. Captures 10-level orderbook depth, spreads, liquidity, and Binance filters.
3. Computes static snapshot capacity estimates for \$10k, \$50k, \$250k, \$1M.
4. Correlates with forward_journal.jsonl decisions and explicitly reports delta_t.
5. Marks all capacity calculations as STATIC_SNAPSHOT_ESTIMATE.
"""

import os
import sys
import time
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests
import pandas as pd
import numpy as np

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

CORE4_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
BINANCE_SPOT_MIRRORS = [
    "https://api.binance.com",
    "https://data-api.binance.vision",
    "https://api1.binance.com",
    "https://api2.binance.com",
]

TEST_ORDER_SIZES_USD = [10000.0, 50000.0, 250000.0, 1000000.0]


def fetch_symbol_filters(symbols: List[str] = CORE4_SYMBOLS) -> Dict[str, Dict[str, Any]]:
    """Fetches Binance Spot lot size, price filter, and minNotional rules."""
    sym_json = json.dumps(symbols)
    url = f"https://api.binance.com/api/v3/exchangeInfo?symbols={sym_json}"
    res = {}
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            for s_info in resp.json().get("symbols", []):
                s = s_info.get("symbol")
                filters = {f["filterType"]: f for f in s_info.get("filters", [])}
                price_f = filters.get("PRICE_FILTER", {})
                lot_f = filters.get("LOT_SIZE", {})
                notional_f = filters.get("NOTIONAL", filters.get("MIN_NOTIONAL", {}))

                res[s] = {
                    "tick_size": float(price_f.get("tickSize", 0.01)),
                    "min_qty": float(lot_f.get("minQty", 0.001)),
                    "step_size": float(lot_f.get("stepSize", 0.001)),
                    "min_notional": float(notional_f.get("minNotional", 5.0)),
                    "base_asset": s_info.get("baseAsset"),
                    "quote_asset": s_info.get("quoteAsset"),
                }
    except Exception as e:
        print(f"[SIDECAR WARNING] Could not fetch exchangeInfo: {e}")
    return res


def fetch_orderbook_depth(symbol: str, limit: int = 10) -> Optional[Dict[str, Any]]:
    """Fetches real-time 10-level order book depth from Binance Spot."""
    for base in BINANCE_SPOT_MIRRORS:
        url = f"{base}/api/v3/depth?symbol={symbol}&limit={limit}"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                d = resp.json()
                bids = [[float(p), float(q)] for p, q in d.get("bids", [])]
                asks = [[float(p), float(q)] for p, q in d.get("asks", [])]
                return {"bids": bids, "asks": asks}
        except Exception:
            continue
    return None


def calculate_static_impact_slippage(
    book_side: List[List[float]],
    order_size_usd: float,
    is_buy: bool,
) -> Dict[str, Any]:
    """
    Simulates walking the instantaneous order book to estimate static price impact.
    Explicitly labeled as a static snapshot estimate, NOT a guarantee of fill.
    """
    if not book_side:
        return {"status": "NO_DEPTH", "slippage_bps": None, "effective_price": None}

    best_price = book_side[0][0]
    remaining_usd = order_size_usd
    total_qty_filled = 0.0
    total_cost_usd = 0.0

    for price, qty in book_side:
        level_usd = price * qty
        if remaining_usd <= level_usd:
            fill_qty = remaining_usd / price
            total_qty_filled += fill_qty
            total_cost_usd += remaining_usd
            remaining_usd = 0.0
            break
        else:
            total_qty_filled += qty
            total_cost_usd += level_usd
            remaining_usd -= level_usd

    if remaining_usd > 0.0:
        # Depth exhausted at 10 levels
        return {
            "status": "INSUFFICIENT_DEPTH_AT_10_LEVELS",
            "filled_usd": total_cost_usd,
            "unfilled_usd": remaining_usd,
            "slippage_bps": None,
            "effective_price": None,
        }

    effective_price = total_cost_usd / total_qty_filled
    if is_buy:
        slippage_bps = ((effective_price - best_price) / best_price) * 10000.0
    else:
        slippage_bps = ((best_price - effective_price) / best_price) * 10000.0

    return {
        "status": "FULLY_FILLABLE_AT_SNAPSHOT",
        "order_size_usd": order_size_usd,
        "effective_price": round(effective_price, 4),
        "top_of_book_price": round(best_price, 4),
        "slippage_bps": round(slippage_bps, 2),
    }


def capture_sidecar_snapshot(output_dir: str = "data/forward_tracking") -> Dict[str, Any]:
    """
    Captures a full sidecar execution snapshot for all Core-4 symbols,
    correlates with forward_journal.jsonl, and records time offsets (delta_t).
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    depth_log_path = out_path / "execution_depth_log.jsonl"
    journal_path = out_path / "forward_journal.jsonl"

    snapshot_time_utc = datetime.now(timezone.utc)
    snapshot_time_str = snapshot_time_utc.strftime("%Y-%m-%d %H:%M:%S UTC")

    # Read latest A/B decision from forward_journal.jsonl
    latest_journal_event = None
    if journal_path.exists():
        with open(journal_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
            if lines:
                try:
                    latest_journal_event = json.loads(lines[-1])
                except Exception:
                    pass

    filters = fetch_symbol_filters(CORE4_SYMBOLS)

    records = []
    for s in CORE4_SYMBOLS:
        t0 = time.time()
        depth = fetch_orderbook_depth(s, limit=10)
        req_latency_ms = round((time.time() - t0) * 1000.0, 1)

        if not depth:
            print(f"[SIDECAR ERROR] Failed to fetch depth for {s}")
            continue

        bids = depth["bids"]
        asks = depth["asks"]

        best_bid = bids[0][0] if bids else 0.0
        best_bid_qty = bids[0][1] if bids else 0.0
        best_ask = asks[0][0] if asks else 0.0
        best_ask_qty = asks[0][1] if asks else 0.0

        mid_price = (best_bid + best_ask) / 2.0 if (best_bid + best_ask) > 0 else 0.0
        spread_usd = best_ask - best_bid
        spread_bps = (spread_usd / mid_price * 10000.0) if mid_price > 0 else 0.0

        cum_bid_vol_usd = sum(p * q for p, q in bids)
        cum_ask_vol_usd = sum(p * q for p, q in asks)

        # Capacity simulations
        buy_impact = {}
        sell_impact = {}
        for sz in TEST_ORDER_SIZES_USD:
            buy_impact[f"buy_${int(sz/1000)}k"] = calculate_static_impact_slippage(asks, sz, is_buy=True)
            sell_impact[f"sell_${int(sz/1000)}k"] = calculate_static_impact_slippage(bids, sz, is_buy=False)

        # Correlate with forward journal timestamp
        delta_t_sec = None
        related_bar_time = None
        if latest_journal_event:
            related_bar_time = latest_journal_event.get("bar_time")
            decision_time_str = latest_journal_event.get("decision_time_utc")
            if decision_time_str:
                try:
                    dec_dt = pd.to_datetime(decision_time_str)
                    if dec_dt.tz is None:
                        dec_dt = dec_dt.tz_localize("UTC")
                    delta_t_sec = round((snapshot_time_utc - dec_dt).total_seconds(), 2)
                except Exception:
                    pass

        record = {
            "event_type": "SIDECAR_DEPTH_SNAPSHOT",
            "symbol": s,
            "snapshot_time_utc": snapshot_time_str,
            "request_latency_ms": req_latency_ms,
            "delta_t_to_ab_decision_sec": delta_t_sec,
            "related_ab_bar_time": related_bar_time,
            "top_of_book": {
                "best_bid": best_bid,
                "best_bid_qty": best_bid_qty,
                "best_ask": best_ask,
                "best_ask_qty": best_ask_qty,
                "mid_price": round(mid_price, 4),
                "spread_usd": round(spread_usd, 4),
                "spread_bps": round(spread_bps, 2),
            },
            "cumulative_depth_10_levels": {
                "total_bid_volume_usd": round(cum_bid_vol_usd, 2),
                "total_ask_volume_usd": round(cum_ask_vol_usd, 2),
            },
            "static_capacity_estimates": {
                "buy_impact": buy_impact,
                "sell_impact": sell_impact,
            },
            "capacity_qualification": "STATIC_SNAPSHOT_ESTIMATE_NOT_GUARANTEED_EXECUTION",
            "exchange_filters": filters.get(s, {}),
            "depth_bids_top5": bids[:5],
            "depth_asks_top5": asks[:5],
        }

        records.append(record)

        # Append to jsonl
        with open(depth_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    print(f"[SIDECAR SNAPSHOT] Successfully captured {len(records)} symbols to {depth_log_path}")
    return {"status": "SUCCESS", "records_count": len(records), "timestamp": snapshot_time_str}


def main():
    parser = argparse.ArgumentParser(description="Sidecar Depth & Execution Logger")
    parser.add_argument("--snapshot", action="store_true", help="Capture a single execution depth snapshot")
    parser.add_argument("--poll", action="store_true", help="Run continuous background poll")
    parser.add_argument("--interval", type=int, default=900, help="Poll interval in seconds (default 900s / 15m)")
    args = parser.parse_args()

    if args.snapshot or not args.poll:
        capture_sidecar_snapshot()
    else:
        print(f"[SIDECAR DAEMON] Starting continuous sidecar logger every {args.interval}s...")
        while True:
            try:
                capture_sidecar_snapshot()
            except Exception as e:
                print(f"[SIDECAR ERROR] {e}")
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
