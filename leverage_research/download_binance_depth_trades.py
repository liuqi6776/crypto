"""
Download and Process Binance Vision L2 Depth and aggTrades for ETHUSDT.
Calibrates Empirical Slippage and Order Book Depth across position sizes ($5k to $100k).
"""

import os
import sys
import io
import zipfile
import urllib.request
import numpy as np
import pandas as pd

OUT_DIR = r"c:\Users\liuqi\crypto\leverage_research\charts"
os.makedirs(OUT_DIR, exist_ok=True)

def download_zip_csv(url: str) -> pd.DataFrame:
    print(f"Downloading: {url} ...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=45) as resp:
        content = resp.read()
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        fname = z.namelist()[0]
        with z.open(fname) as f:
            return pd.read_csv(f)

def main():
    print("=" * 85)
    print("  CALIBRATING EMPIRICAL ORDER BOOK DEPTH & SLIPPAGE (ETHUSDT PERPETUAL)")
    print("=" * 85)

    # Sample dates from September 2026
    sample_dates = ['2026-09-19', '2026-09-20', '2026-09-21']
    base_url = "https://data.binance.vision/data/futures/um/daily"

    all_depths = []
    all_trade_stats = []

    for d in sample_dates:
        # 1. Process bookDepth
        depth_url = f"{base_url}/bookDepth/ETHUSDT/ETHUSDT-bookDepth-{d}.zip"
        try:
            df_depth = download_zip_csv(depth_url)
            # Filter for near-market depth: +/- 0.2% and +/- 1.0%
            near_bid = df_depth[df_depth['percentage'] == -0.2]['notional'].values
            near_ask = df_depth[df_depth['percentage'] == 0.2]['notional'].values
            far_bid = df_depth[df_depth['percentage'] == -1.0]['notional'].values
            far_ask = df_depth[df_depth['percentage'] == 1.0]['notional'].values

            all_depths.append({
                'date': d,
                'mean_depth_02_bid': np.mean(near_bid),
                'mean_depth_02_ask': np.mean(near_ask),
                'mean_depth_10_bid': np.mean(far_bid),
                'mean_depth_10_ask': np.mean(far_ask),
                'p10_depth_02_bid': np.percentile(near_bid, 10), # thin liquidity regime
                'p10_depth_02_ask': np.percentile(near_ask, 10)
            })
            print(f"  [OK] Processed bookDepth for {d}: {len(df_depth):,} snapshots.")
        except Exception as e:
            print(f"  [WARN] Failed to fetch bookDepth for {d}: {e}")

        # 2. Process aggTrades (sample 200,000 trades per day for speed)
        trades_url = f"{base_url}/aggTrades/ETHUSDT/ETHUSDT-aggTrades-{d}.zip"
        try:
            df_trades = download_zip_csv(trades_url)
            # Sample trades
            sample_trades = df_trades.sample(n=min(150000, len(df_trades)), random_state=42)
            prices = sample_trades['price'].values
            qtys = sample_trades['quantity'].values
            notionals = prices * qtys
            is_buyer_maker = sample_trades['is_buyer_maker'].values

            all_trade_stats.append({
                'date': d,
                'total_trades': len(df_trades),
                'avg_trade_usd': np.mean(notionals),
                'median_trade_usd': np.median(notionals),
                'p95_trade_usd': np.percentile(notionals, 95),
                'p99_trade_usd': np.percentile(notionals, 99),
                'taker_buy_share': np.mean(~is_buyer_maker) * 100.0
            })
            print(f"  [OK] Processed aggTrades for {d}: {len(df_trades):,} total trades.")
        except Exception as e:
            print(f"  [WARN] Failed to fetch aggTrades for {d}: {e}")

    df_d = pd.DataFrame(all_depths)
    df_t = pd.DataFrame(all_trade_stats)

    print("\n--- Empirical Order Book Depth Summary (USD) ---")
    print(df_d[['date', 'mean_depth_02_bid', 'mean_depth_02_ask', 'p10_depth_02_bid']].to_string(index=False))

    print("\n--- Trade Size Distribution (USD) ---")
    print(df_t[['date', 'avg_trade_usd', 'median_trade_usd', 'p95_trade_usd', 'p99_trade_usd', 'taker_buy_share']].to_string(index=False))

    # 3. Derive Empirical Slippage Model across order sizes
    # Kyle's Lambda / Square-Root Law of Market Impact:
    # Impact(Q) = sigma * (Q / Volume_24h)^0.5 + Base Spread / 2
    # At 0.2% (20 bps), average depth is ~$11,000,000 USD.
    # Therefore, linear liquidity density D_0 = $11,000,000 / 0.0020 = $5,500,000,000 per 100% move ($55M per 1% move).
    # Slippage for size Q is: Q / (2 * D_0) + half-spread
    avg_02_depth = np.mean([df_d['mean_depth_02_bid'].mean(), df_d['mean_depth_02_ask'].mean()])
    thin_02_depth = np.mean([df_d['p10_depth_02_bid'].mean(), df_d['p10_depth_02_ask'].mean()])

    base_half_spread_pct = 0.00005 # 0.5 bp ($0.13 on ETH)

    order_sizes = [5000.0, 10000.0, 25000.0, 50000.0, 100000.0, 250000.0]
    slip_results = []

    for q in order_sizes:
        # Normal Regime:
        impact_normal = (q / (2.0 * (avg_02_depth / 0.0020)))
        total_slip_normal = (impact_normal + base_half_spread_pct) * 10000.0 # in bps

        # Stressed / Thin Liquidity Regime (e.g. during sudden sharp drop):
        impact_thin = (q / (2.0 * (thin_02_depth / 0.0020)))
        total_slip_thin = (impact_thin + base_half_spread_pct * 2.5) * 10000.0 # in bps

        slip_results.append({
            'order_size_usd': q,
            'normal_impact_bps': impact_normal * 10000.0,
            'normal_half_spread_bps': base_half_spread_pct * 10000.0,
            'normal_total_slippage_bps': total_slip_normal,
            'normal_total_slippage_pct': total_slip_normal / 10000.0,
            'stressed_total_slippage_bps': total_slip_thin,
            'stressed_total_slippage_pct': total_slip_thin / 10000.0,
            'eth_price_slip_normal_usd': 2600.0 * (total_slip_normal / 10000.0),
            'eth_price_slip_stressed_usd': 2600.0 * (total_slip_thin / 10000.0)
        })

    df_slip = pd.DataFrame(slip_results)
    out_slip_csv = os.path.join(OUT_DIR, "empirical_slippage_distribution.csv")
    df_slip.to_csv(out_slip_csv, index=False)

    print("\n" + "=" * 85)
    print("  CALIBRATED EMPIRICAL SLIPPAGE TABLE (ETHUSDT PERPETUAL)")
    print("=" * 85)
    print(df_slip[['order_size_usd', 'normal_total_slippage_bps', 'eth_price_slip_normal_usd', 'stressed_total_slippage_bps', 'eth_price_slip_stressed_usd']].to_string(index=False))
    print(f"\n[OK] Empirical slippage report saved to: {out_slip_csv}")

if __name__ == '__main__':
    main()
