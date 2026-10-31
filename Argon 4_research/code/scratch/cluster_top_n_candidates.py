import pandas as pd
import numpy as np

df = pd.read_parquet('scratch/funding_dataset_with_returns.parquet')

# Filter for Top Negative and Top Positive
neg_cands = df[(df['fundingRate'] <= -0.001) & (df['ret_prev_1'] >= 0.05)].copy() # FR <= -0.10% and pumped >= 5% in prior 8h
pos_cands = df[(df['fundingRate'] >= 0.0008) & (df['ret_prev_1'] >= 0.08)].copy() # FR >= +0.08% and pumped >= 8% in prior 8h

print(f"Top Negative candidates with pump: {len(neg_cands)} across {neg_cands['symbol'].nunique()} symbols")
print(f"Top Positive candidates with pump: {len(pos_cands)} across {pos_cands['symbol'].nunique()} symbols")

# Cluster by symbol and date
def cluster_events(cands, max_gap_hours=24):
    clusters = []
    for sym, group in cands.sort_values(['symbol', 'fundingTime']).groupby('symbol'):
        cur = []
        for idx, row in group.iterrows():
            if not cur:
                cur.append(row)
            else:
                gap = (row['fundingTime'] - cur[-1]['fundingTime']).total_seconds() / 3600
                if gap <= max_gap_hours:
                    cur.append(row)
                else:
                    clusters.append(cur)
                    cur = [row]
        if cur:
            clusters.append(cur)
    return clusters

neg_clusters = cluster_events(neg_cands)
pos_clusters = cluster_events(pos_cands)
print(f"Distinct Negative Squeeze Clusters: {len(neg_clusters)}")
print(f"Distinct Positive Squeeze Clusters: {len(pos_clusters)}")
print(f"Total Combined Trade Setups: {len(neg_clusters) + len(pos_clusters)}")
