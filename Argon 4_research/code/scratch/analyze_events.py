import pandas as pd
import numpy as np

# Load GOOGL daily data
df = pd.read_csv('googl_daily.csv')
df['date'] = pd.to_datetime(df['date'])
for col in ['open', 'close', 'high', 'low', 'pct_chg', 'volume']:
    df[col] = df[col].astype(float)

events = [
    ('Gemini 2.0 Flash (Preview)', '2024-12-11'),
    ('Gemini 2.0 Flash GA & Pro Exp', '2025-02-05'),
    ('Google I/O 2025 & Gemini 2.5 Preview', '2025-05-20'),
    ('Gemini 2.5 Pro / Flash Official', '2025-06-17'),
    ('Gemini 3 Family Announcement', '2025-11-18'),
    ('Gemini 3 Deep Think & 3.1 Pro', '2026-02-19'),
    ('Google I/O 2026 & Gemini 3.5 Flash', '2026-05-19'),
    ('Gemini 3.6 Flash', '2026-07-21'),
    ('Gemini 3.7 Flash', '2026-08-13'),
    ('Gemini 3.8 Live & Extended Thinking', '2026-09-15'),
]

print("================================================================================")
print("GOOGLE (GOOGL / GOOGLB) DAILY K-LINE EVENT STUDY (2025 - 2026)")
print("================================================================================")

for name, d_str in events:
    d = pd.to_datetime(d_str)
    sub = df[(df['date'] >= d - pd.Timedelta(days=5)) & (df['date'] <= d + pd.Timedelta(days=6))].copy()
    sub = sub.sort_values('date')
    print(f"\n>>> [Event] {name} (Date: {d_str})")
    print(f"{'Date':<12} | {'Open':>8} | {'High':>8} | {'Low':>8} | {'Close':>8} | {'Chg %':>7} | {'Vol(M)':>7} | Note")
    print("-" * 75)
    for _, row in sub.iterrows():
        dt = row['date'].strftime('%Y-%m-%d')
        mark = " <-- Release Date" if dt == d_str else ""
        vol_m = row['volume'] / 1e6
        print(f"{dt:<12} | {row['open']:8.2f} | {row['high']:8.2f} | {row['low']:8.2f} | {row['close']:8.2f} | {row['pct_chg']:+7.2f}% | {vol_m:7.1f}M |{mark}")

# Load GOOGLB Binance data if available
try:
    bin_df = pd.read_csv('googlb_binance_daily.csv')
    bin_df['date'] = pd.to_datetime(bin_df['date'])
    for col in ['open', 'close', 'high', 'low', 'volume']:
        bin_df[col] = bin_df[col].astype(float)
    bin_df['pct_chg'] = (bin_df['close'] - bin_df['open']) / bin_df['open'] * 100

    print("\n\n================================================================================")
    print("BINANCE TOKENIZED STOCK GOOGLB/USDT DAILY K-LINE AROUND 2026 RELEASES")
    print("================================================================================")

    bin_events = [
        ('Listing & Gemini 3.6 Flash Window', '2026-07-21'),
        ('Gemini 3.7 Flash', '2026-08-13'),
        ('Gemini 3.8 Live & Thinking', '2026-09-15'),
    ]

    for name, d_str in bin_events:
        d = pd.to_datetime(d_str)
        sub = bin_df[(bin_df['date'] >= d - pd.Timedelta(days=4)) & (bin_df['date'] <= d + pd.Timedelta(days=5))].copy()
        sub = sub.sort_values('date')
        print(f"\n>>> [Binance GOOGLB/USDT] {name} ({d_str})")
        print(f"{'Date':<12} | {'Open':>8} | {'High':>8} | {'Low':>8} | {'Close':>8} | {'Chg %':>7} | {'Vol(k)':>7} | Note")
        print("-" * 75)
        for _, row in sub.iterrows():
            dt = row['date'].strftime('%Y-%m-%d')
            mark = " <-- Release Date" if dt == d_str else ""
            vol_k = row['volume'] / 1e3
            print(f"{dt:<12} | {row['open']:8.2f} | {row['high']:8.2f} | {row['low']:8.2f} | {row['close']:8.2f} | {row['pct_chg']:+7.2f}% | {vol_k:7.1f}k |{mark}")
except Exception as e:
    print("Binance analysis error:", e)
