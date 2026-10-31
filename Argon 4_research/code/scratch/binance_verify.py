"""用币安公开 API 独立核对项目的离线数据与 2026 基准声明"""
import json, urllib.request, time
import pandas as pd

BASE = "https://api.binance.com/api/v3/klines"

def klines(symbol, interval, start_ms, limit=1000):
    url = f"{BASE}?symbol={symbol}&interval={interval}&startTime={start_ms}&limit={limit}"
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read().decode())

# ---- 1) 2026 YTD 现货表现（README 宣称 BTC -12.1% / ETH -15.4% / SOL -18.8%，MDD -40%~-58%）----
start_2026 = 1767225600000  # 2026-01-01 00:00 UTC
print("=== 2026 YTD (Binance spot, daily) ===")
for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
    ks = klines(sym, "1d", start_2026, 300)
    df = pd.DataFrame(ks, columns=["t","o","h","l","c","v","ct","qv","n","tb","tq","ig"])
    df["c"] = df["c"].astype(float); df["o"] = df["o"].astype(float)
    df["date"] = pd.to_datetime(df["t"], unit="ms", utc=True)
    ytd = df["c"].iloc[-1] / df["o"].iloc[0] - 1
    peak = df["c"].cummax()
    mdd = (df["c"] / peak - 1).min()
    print(f"{sym}: last={df['c'].iloc[-1]:.2f} ({df['date'].iloc[-1].date()})  YTD={ytd:+.2%}  MDD={mdd:+.2%}")
    time.sleep(0.3)

# ---- 2) 项目离线 4h parquet vs 币安 4h 实盘（最近 30 根比对）----
print("\n=== 项目 ETHUSDT 4h parquet vs Binance ===")
pq = pd.read_parquet(r"C:\Users\liuqi\crypto\data\ETHUSDT_4h_2020_2026.parquet")
pq.columns = [c.lower() for c in pq.columns]
print("parquet rows:", len(pq), "last ts:", pq.index[-1] if not isinstance(pq.index, pd.RangeIndex) else pq.iloc[-1].get("timestamp"))

# Binance 最近 30 根 4h
ks = klines("ETHUSDT", "4h", 0, 30)  # startTime=0+limit 返回最早? 改用 endTime
# 取最近: 不传 startTime
url = f"{BASE}?symbol=ETHUSDT&interval=4h&limit=30"
with urllib.request.urlopen(url, timeout=20) as r:
    ks = json.loads(r.read().decode())
bn = pd.DataFrame(ks, columns=["t","o","h","l","c","v","ct","qv","n","tb","tq","ig"])
bn["ts"] = pd.to_datetime(bn["t"], unit="ms", utc=True).dt.tz_localize(None)
for c in ["o","h","l","c"]: bn[c] = bn[c].astype(float)

# 对齐 parquet 时间列
if "timestamp" in pq.columns:
    pq["ts"] = pd.to_datetime(pq["timestamp"])
elif "open_time" in pq.columns:
    pq["ts"] = pd.to_datetime(pq["open_time"], unit="ms")
else:
    pq["ts"] = pd.to_datetime(pq.index)
merged = bn.merge(pq, on="ts", suffixes=("_bn", "_pq"))
print(f"重叠 bar 数: {len(merged)}")
if len(merged):
    close_bn = merged["c_bn"] if "c_bn" in merged else merged["c"]
    close_pq_col = "c_pq" if "c_pq" in merged else ("close" if "close" in merged else None)
    if close_pq_col:
        diff = (merged[close_pq_col].astype(float) / close_bn - 1).abs()
        print(f"close 最大偏差: {diff.max():.6%}  平均偏差: {diff.mean():.6%}")
        print(merged[["ts", close_pq_col]].assign(binance=close_bn.values).tail(5).to_string())

# ---- 3) 2024-2025 买入持有基准核对（README: ETH +30.67% / SOL +20.68%）----
print("\n=== 2024-01-01 ~ 2025-12-31 Buy&Hold 核对 ===")
for sym, claimed in [("ETHUSDT", 0.3067), ("SOLUSDT", 0.2068), ("BTCUSDT", None)]:
    ks = klines(sym, "1d", 1704067200000, 800)
    df = pd.DataFrame(ks, columns=["t","o","h","l","c","v","ct","qv","n","tb","tq","ig"])
    df["c"] = df["c"].astype(float); df["o"] = df["o"].astype(float)
    df["date"] = pd.to_datetime(df["t"], unit="ms", utc=True)
    df = df[df["date"] < "2026-01-01"]
    ret = df["c"].iloc[-1] / df["o"].iloc[0] - 1
    peak = df["c"].cummax(); mdd = (df["c"]/peak - 1).min()
    print(f"{sym}: 实测 {ret:+.2%} (MDD {mdd:+.2%})  宣称 {claimed}")
    time.sleep(0.3)

# ---- 4) paper_state 持仓价核对 ----
print("\n=== paper_state 开仓价 vs Binance 实际 4h bar ===")
state = json.load(open(r"C:\Users\liuqi\crypto\paper_state\state.json", encoding="utf-8"))
for leg in state.get("positions", state.get("legs", [])) if isinstance(state.get("positions", state.get("legs")), list) else []:
    print(leg)
print("state keys:", list(state.keys())[:20])
