import pandas as pd

df = pd.read_csv('googl_daily.csv')
df['date'] = pd.to_datetime(df['date'])
for col in ['open', 'close', 'high', 'low', 'pct_chg', 'volume']:
    df[col] = df[col].astype(float)

events_2025 = [
    ('Gemini 2.0 Flash (Preview)', '2024-12-11'),
    ('Gemini 2.0 Flash GA & Pro Exp', '2025-02-05'),
    ('Google I/O 2025 & Gemini 2.5 Preview', '2025-05-20'),
    ('Gemini 2.5 Pro / Flash Official', '2025-06-17'),
    ('Gemini 2.5 Flash-Lite', '2025-07-22'),
    ('Gemini 3 Announcement', '2025-11-18')
]

for name, d_str in events_2025:
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
