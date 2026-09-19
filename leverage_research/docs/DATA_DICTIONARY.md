# Crypto Quantitative Data Dictionary & Usage Guide
# 加密货币高频量化与衍生品数据字典及使用手册

This document provides a comprehensive data dictionary, schema specification, directory structure, and historical availability guide for the cryptocurrency datasets collected in `d:\Convertible_Bond_data\crypto_data\`.
本文档详细规定了 `d:\Convertible_Bond_data\crypto_data\` 目录下所有加密货币量化数据集的架构设计、字段字典、数据存储标准及多年度历史数据覆盖范围，专为高频与中频量化策略、20X 高杠杆风控及策略因子研究所打造。

---

## 1. Directory Structure / 目录结构规范

```
d:\Convertible_Bond_data\crypto_data\
├── README.md                                  # 本数据字典与使用规范 (Data Dictionary & Guide)
├── cross_exchange_orderbook_summary.csv/.parquet # 三大交易所盘口微观特征横向对比总表
│
├── binance\                                   # 币安 (Binance USDⓈ-M Futures & Spot)
│   ├── ETH\
│   │   ├── ETH_binance_1m.csv / .parquet      # 1分钟高频 K 线 (1m OHLCV + Taker Flow)
│   │   ├── ETH_binance_5m.csv / .parquet      # 5分钟波段 K 线 (5m OHLCV + Taker Flow)
│   │   ├── ETH_depth_snapshot.json            # 原始前 100 档买卖挂单深度快照
│   │   ├── ETH_orderbook_features.csv/.parquet# 盘口微观结构特征 (Spread, OBI, Micro-price)
│   │   ├── ETH_open_interest_5m.csv/.parquet  # 5分钟未平仓合约持仓量 (OI)
│   │   ├── ETH_global_long_short_ratio_5m.*   # 5分钟全网多空持仓人数比
│   │   ├── ETH_top_trader_ratio_5m.*          # 5分钟顶级交易员大户多空持仓比
│   │   ├── ETH_taker_long_short_ratio_5m.*    # 5分钟主动吃单买卖比 (Taker Ratio)
│   │   └── ETH_funding_rate_hist.*            # 历史资金费率记录 (Funding Rate History)
│   ├── BTC\                                   # BTC 相应全套衍生品数据
│   └── SOL\                                   # SOL 相应全套衍生品数据
│
├── okx\                                       # OKX (USDT-Margined Perpetual Swaps)
│   ├── ETH\ (1m/5m K线, 深度切片, 盘口微观特征, OI, 资金费率, 5m多空比, 5m主动成交量)
│   ├── BTC\
│   └── SOL\
│
├── bitget\                                    # Bitget (USDT-Futures)
│   ├── ETH\ (1m/5m K线, 深度切片, 盘口微观特征, OI, 资金费率, 5m多空比)
│   ├── BTC\
│   └── SOL\
│
└── history\                                   # 全量历史长周期数据归档 (Multi-Year Historical Archives)
    ├── futures_1m\                            # 永续合约 1分钟全量历史 (2020-01 至 2026)
    ├── futures_5m\                            # 永续合约 5分钟全量历史 (2020-01 至 2026)
    └── spot_1m\                               # 现货 1分钟全量历史 (2017-08 至 2026)
```

---

## 2. Historical Timeline & Availability / 历史数据时间跨度说明

> [!NOTE]
> **Crypto Financial Product Inception Timeline / 加密金融产品上线历史纪年**
> 1. **USDT-Margined Perpetuals (USDT 永续合约)**:
>    - **Binance Futures Launched**: **2020-01** for `BTCUSDT` and `ETHUSDT` (testnet in late 2019).
>    - **SOLUSDT Perpetual Launched**: **2020-09** (Solana mainnet launched in mid-2020).
>    - *Market Reality*: Prior to 2020, USDT perpetual futures did not exist in the market (BitMEX prior to 2020 was purely coin-margined inverse contracts).
> 2. **Binance Spot (现货行情)**:
>    - **Binance Inception**: **2017-08** (August 17, 2017).
>    - Full 1m and 5m continuous spot data exists from **August 2017 through 2026** (8+ continuous years).
> 3. **Pre-2017 Context (2015-2017)**:
>    - Tether (USDT) was not widely circulated before 2017. Pre-2017 BTC and ETH trading was primarily conducted in USD (via Bitstamp, Coinbase, Kraken, Bitfinex).

---

## 3. Data Schemas & Column Dictionaries / 数据字段字典规范

### 3.1 Price & K-Line Schema (1m & 5m OHLCV) / 价格K线数据表

| Column / 字段名 | Data Type / 类型 | Description (English) | 字段说明 (中文) | Example / 示例 |
| :--- | :--- | :--- | :--- | :--- |
| `timestamp` | `int64` | Millisecond UNIX epoch timestamp | 毫秒级 UNIX 时间戳 | `1789799400000` |
| `datetime` | `string` | Human-readable datetime (Asia/Shanghai) | 东八区标准北京时间字符串 | `2026-09-19 14:30:00` |
| `open` | `float64` | Opening price in USDT | 开盘价 (USDT) | `2623.27` |
| `high` | `float64` | Highest price in the bar | 最高价 (USDT) | `2624.81` |
| `low` | `float64` | Lowest price in the bar | 最低价 (USDT) | `2623.27` |
| `close` | `float64` | Closing price in the bar | 收盘价 (USDT) | `2624.14` |
| `volume` | `float64` | Base asset trading volume | 标的成交量 (如 ETH、BTC、SOL 个数) | `154.82` |
| `quote_volume` | `float64` | Turnover / Total volume in USDT | 成交总金额 (USDT) | `406321.45` |
| `trades_count` | `int64` | Number of executed trades | 成交总笔数 | `1248` |
| `taker_buy_volume` | `float64` | Base volume bought by aggressive takers | 主动吃单买入量 (市价多头推动量) | `82.14` |
| `taker_buy_quote_volume` | `float64` | USDT value bought by aggressive takers | 主动吃单买入金额 (USDT) | `215560.12` |

---

### 3.2 Order Book Microstructure Schema / 挂单深度与微观结构数据表

Extracted from raw L2 depth snapshots (top 100 levels):
从原始前 100 档深度盘口中计算生成的关键微观流动性指标：

| Column / 字段名 | Type | Metric Description (English) | 衍生指标说明 (中文) | Formula / 计算公式 |
| :--- | :--- | :--- | :--- | :--- |
| `bid1_price` | `float64` | Best Bid Price | 买一价 | $\max(P_{bid})$ |
| `ask1_price` | `float64` | Best Ask Price | 卖一价 | $\min(P_{ask})$ |
| `mid_price` | `float64` | Midpoint Price | 盘口中间价 | $\frac{P_{ask1} + P_{bid1}}{2}$ |
| `spread` | `float64` | Absolute Bid-Ask Spread | 买卖点差绝对值 | $P_{ask1} - P_{bid1}$ |
| `spread_bps` | `float64` | Spread in Basis Points | 相对基点点差 (bp) | $\frac{Spread}{MidPrice} \times 10000$ |
| `micro_price` | `float64` | Order-weighted Micro-Price | 买卖委托量加权微观价格 | $\frac{P_{bid1} \cdot Q_{ask1} + P_{ask1} \cdot Q_{bid1}}{Q_{bid1} + Q_{ask1}}$ |
| `obi_5` / `obi_20` | `float64` | Order Book Imbalance (Top 5/20) | 挂单失衡度 (-1 到 +1) | $\frac{\sum Q_{bid} - \sum Q_{ask}}{\sum Q_{bid} + \sum Q_{ask}}$ |
| `depth_ratio_20` | `float64` | Top 20 Notional Bid/Ask Ratio | 20档买卖挂单金额比 | $\frac{\sum (P_{bid} \cdot Q_{bid})}{\sum (P_{ask} \cdot Q_{ask})}$ |
| `bid_notional_20` | `float64` | Top 20 cumulative bid depth (USDT)| 前20档买盘托盘总金额 (USDT) | $\sum_{i=1}^{20} P_{bid,i} \cdot Q_{bid,i}$ |
| `ask_notional_20` | `float64` | Top 20 cumulative ask depth (USDT)| 前20档卖盘压盘总金额 (USDT) | $\sum_{i=1}^{20} P_{ask,i} \cdot Q_{ask,i}$ |

---

### 3.3 Directional Alpha Metrics / 衍生品方向性特征指标表

| Metric / 指标名 | Source / 交易所接口 | Interval / 周期 | Trading Signal Meaning (English) | 交易信号与方向判定意义 (中文) |
| :--- | :--- | :--- | :--- | :--- |
| **Open Interest (OI)** | Binance / OKX / Bitget | 5m | Measures capital inflow/outflow. Price Up + OI Up = Healthy trend; Price Down + OI Drop = Liquidation flush. | 未平仓合约量。价格上涨+持仓量增加为真突破；价格暴跌+持仓量急剧下降代表多头踩踏强平；价格冲高+持仓量滞胀代表多头平仓虚涨。 |
| **Funding Rate** | Binance / OKX / Bitget | 8h / Realtime | Measures leverage crowding. High positive = Crowded longs (squeeze risk); Deep negative = Crowded shorts (rally fuel). | 资金费率。多空持仓借贷成本。极端高费率预警多头拥挤可能引发闪崩反转；深度负费率是逼空拉升的经典前兆。 |
| **Global Long/Short Ratio** | Binance / OKX / Bitget | 5m | Retail sentiment indicator. Typically serves as a contrarian indicator. | 全网多空人数比。散户行为通常具有滞后性，该比率极高时常伴随行情见顶，属于重要的逆向反转因子。 |
| **Top Trader Position Ratio** | Binance | 5m | Institutional / Whale positioning ratio. Used as trend confluence. | 大户持仓比。聪明钱/专业机构的净敞口方向，与散户人数比形成鲜明对比，适合作为顺势跟踪因子。 |
| **Taker Buy/Sell Volume** | Binance / OKX | 5m | Aggressive market taker aggression. Directly measures directional aggression. | 主动吃单买卖比。市价吃单代表资金毫不犹豫以不利价格成交的紧迫感，直接决定 1~15 分钟内的短期价格推力。 |

---

## 4. Quick-Start Code: How to Load & Research / 快速使用示例代码

### 4.1 Loading 1m/5m Parquet Data with Pandas / 使用 Pandas 加载数据
```python
import pandas as pd

# Load 1m ETH continuous kline data
df_1m = pd.read_parquet(r"d:\Convertible_Bond_data\crypto_data\binance\ETH\ETH_binance_1m.parquet")
print(df_1m.head())

# Load 5m Open Interest and Taker Volume Ratio
df_oi = pd.read_parquet(r"d:\Convertible_Bond_data\crypto_data\binance\ETH\ETH_open_interest_5m.parquet")
df_taker = pd.read_parquet(r"d:\Convertible_Bond_data\crypto_data\binance\ETH\ETH_taker_long_short_ratio_5m.parquet")

# Merge features for factor analysis
df_merged = pd.merge_asof(
    df_1m.sort_values('timestamp'),
    df_taker[['timestamp', 'buySellRatio']].sort_values('timestamp'),
    on='timestamp',
    direction='backward'
)
```

### 4.2 Calculating 20X Risk & Order Book Liquidation Safety / 20X 杠杆安全距离计算
```python
# Entry at latest close
entry = df_1m['close'].iloc[-1]
# 20X leverage liquidation threshold ~4.5%
liq_long = entry * (1.0 - (0.05 - 0.008))
liq_short = entry * (1.0 + (0.05 - 0.008))

print(f"Current Price: {entry}")
print(f"20X Long Liquidation: {liq_long:.2f} (-4.2%)")
print(f"20X Short Liquidation: {liq_short:.2f} (+4.2%)")
```
