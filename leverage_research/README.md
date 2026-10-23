# Crypto Perpetual Leverage Quantitative Research
# 加密货币永续合约高杠杆量化研究与全周期实证系统

> **2026-10-23 归档纠正：`LEGACY_RESEARCH / UNVERIFIED`。** 当前结论见[最终研究清单](../FINAL_RESEARCH_RESULTS_ZH.md)和[修正记录](../research_archive/CORRECTIONS_ZH.md)。下方历史 CAGR、Sharpe、回撤与“0 次强平”均为旧模型输出，不是可实现净收益或安全保证。
>
> 原“两套正期望机构级架构”“无风险套利”“绝对安全”措辞已撤回。资金费可为负，现货/永续的基差、交易成本、资金占用与保证金路径必须分别核对；不能从 funding 累加或历史零强平推出稳定盈利。旧表同时记录 ETH 1× 基准 +1,643.50%、Core +92.44%、Hybrid +43.72%，这些是不同风险结构的历史对照，不能只展示有利指标。本次没有重新计算原始行情或验证当前数据覆盖。

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Leverage](https://img.shields.io/badge/Leverage-20X%20Isolated-red.svg)]()
[![Status](https://img.shields.io/badge/Status-Legacy%20Research-orange.svg)](../FINAL_RESEARCH_RESULTS_ZH.md)

---

## 📌 Data Storage Location / 数据集持久化存放路径说明

> [!IMPORTANT]
> **Persistent Big Data Storage Path / 核心历史高频数据库存放路径**:
> All large-scale historical datasets (**14,068,250 continuous 1m/5m bars from 2017/2020 to 2026, 7,305 continuous 8-hour funding rate periods, and multi-exchange L2 order book depth snapshots**) are stored in the high-capacity D: drive storage at:
> 本研究所依赖的海量历史高频数据（**2017/2020 至 2026 年近 1,500 万根连续 1m/5m K 线、7,305 期历史资金费率连续归档及多交易所 L2 深度快照**）存放在 D 盘原持久化路径：
>
> ```
> EXTERNAL_MARKET_DATA_ROOT/
> ├── history/
> │   ├── futures_1m/    # ETH, BTC, SOL continuous 1m bars (3.5M rows each, Parquet)
> │   ├── futures_5m/    # ETH, BTC, SOL continuous 5m bars (700k rows each, Parquet)
> │   ├── spot_5m/       # Continuous spot 5m bars
> │   └── funding_rate/  # Continuous 8-hour funding rates (2020-2026, 7,305 records)
> ├── binance/           # Live L2 100-level order book snapshots & taker flow metrics
> ├── okx/               # OKX SWAP L2 order book & ticker archives
> └── bitget/            # Bitget Mix USDT-futures archives
> ```
> `EXTERNAL_MARKET_DATA_ROOT/` is a documentation placeholder for a historical local archive, not a supported environment variable or a path configured in the scripts. Legacy scripts may still hardcode local paths; reproduction requires reviewing each script and binding source-labelled inputs. This archive update did not port or run them.
> `EXTERNAL_MARKET_DATA_ROOT/` 仅是去敏后的示意路径。旧脚本仍可能硬编码本地路径；复现前须审查代码并绑定有来源标签的数据，当前未移植或运行这些脚本。

---

## 1. Executive Summary / 项目概述

This sub-repository houses the specialized **High-Leverage (20X) Cryptocurrency Perpetual Futures Quantitative Research**, focusing on:
本项目专门针对加密货币**高杠杆（20X）永续合约量化交易**开展深度数理与实证研究，涵盖以下核心突破：

1. **Conditional Friction Arithmetic at 20X / 20X 杠杆条件成本算术**:
   - Under the historical assumption of 20X notional exposure to margin, Maker 0.02% + Taker 0.05% + a total 1 bps slippage equals **1.60% of margin per round trip**, before funding and any additional execution costs.
   - This illustrates a high turnover cost burden; it is not a proof that every 1m/15m strategy must lose or that margin is exhausted after a fixed number of trades. Profitability still requires causal fills, the full cost ledger and a strategy-specific validation.
2. **Order Book Microstructure & Order Flow (LOB / OFI) / 市场微结构与订单流工程**:
   - Shifted from legacy lagging OHLCV price indicators to **Order Flow Imbalance (OFI)** and **Order Book Imbalance (OBI)**.
   - Built Numba-accelerated **Marcos López de Prado Dual Triple Barrier Method** (dynamic ATR upper/lower/vertical barriers) strictly calibrated with 20X liquidation buffers.
   - The historical report labelled a **Purged Walk-Forward LightGBM Engine** and 120,000 bars as OOS, reporting AUCs **0.5106 (Long)** and **0.5110 (Short)**. The stronger claims of statistical validation and zero future leakage are unverified here; a near-0.51 AUC alone does not establish executable net profitability.
3. **Two Historical High-Leverage Hypotheses / 两套尚未验证的历史高杠杆假说**:
   - **Architecture 1: Hybrid Core-Satellite (母子账户对冲与狙击架构)**:
     - 85% Core: Delta-Neutral Funding Rate Arbitrage (**CAGR 10.32%~22%, MaxDD 0.18%, Sharpe 10.65, Ulcer Index 0.03**).
     - 15% Satellite: 20X Macro Liquidation Sniper.
     - Cash-flow from Core continuously subsidizes the Satellite sniper, yielding **+43.72% Total Return, MaxDD only 8.36%, Sharpe 1.80, and zero liquidations** across 6 full years (2020-2026).
   - **Architecture 2: Path A Macro Dislocation Sniper (低频大级别极值狙击)**:
     - Trades restricted to genuine black swan liquidations (24h drop $> 9\%$, volume $> 3.5\times$ 7d avg).
     - Expanded profit target to $+5.0\%$ price move (**$+100\%$ ROE on 20X margin**), compressing fee friction to $< 2\%$ of winning profits.

---

## 2. Master Performance Benchmark (2020 - 2026)
## 全场景全周期综合业绩与学术风控指标对比总表

> 下表为冻结的旧结果转录，保留数值不等于认可口径。“绝对安全”等原表注释已撤回；0 次仅表示原模型未记录强平，未证明真实条件下没有风险。成本、选择过程和市场身份须按最新证据重新审计后才能计算新的净结果。

| Model / Portfolio Architecture | Initial ($) | Ending ($) | Total Return | CAGR (%) | Max Drawdown | Sharpe Ratio | Calmar Ratio | Ulcer Index | Liquidations |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Core Only（旧 carry 代理，未验证）** | $10,000.00 | **$19,234.84** | **+92.44%** | **10.32%**（原报告外推 2X 为 18%~22%，未验证） | **0.18%** ★★★ | **10.65** ★★★ | **58.40** ★★★ | **0.03** ★★★ | **0 次（旧模型记录，不代表安全）** |
| **Hybrid Core-Satellite (85/15 母子架构)** | $10,000.00 | **$14,366.14** | **+43.72%** | **5.59%** | **8.36%** ★★★ | **1.80** ★★★ | **0.67** | **1.92** ★★★ | **0 次（旧模型记录，不代表安全）** |
| **Path A (纯单边 20X 宏观极值狙击)** | $10,000.00 | $1,708.56 | -82.91% | -23.34% | 83.94% | -0.41 | -0.28 | 65.19 | **0 次 (严格止损存活)** |
| **ETH 1X Buy & Hold (现货单边持有基准)** | $10,000.00 | $174,350.00 | +1,643.50% | 53.48% | 79.61% (暴涨暴跌) | 0.95 | 0.67 | 46.10 (深水折磨) | 0 次 |

---

## 3. Scripts Inventory & Execution Guide / 量化脚本清单与运行指南

The script inventory below refers to this repository's `leverage_research/` directory. `SOURCE_ROOT` elsewhere is a redacted provenance placeholder, not a newly implemented runtime configuration.

| Script / 脚本文件 | Core Function / 核心功能 | Execution Command / 运行命令 |
| :--- | :--- | :--- |
| **`core_satellite_hybrid_backtest.py`** | 6-year full backtest of the 85% Core + 15% 20X Satellite hybrid architecture (701k 5m bars + 7.3k funding periods). | `python core_satellite_hybrid_backtest.py` |
| **`liquidation_hunter_vs_funding_arb.py`** | Academic head-to-head comparison: Liquidation Hunter vs Delta-Neutral Funding Rate Arbitrage. | `python liquidation_hunter_vs_funding_arb.py` |
| **`microstructure_feature_engine.py`** | Numba-accelerated multi-scale OFI (1m, 3m, 5m, 15m), Parkinson volatility, and Dual Triple Barrier Method labeler. | `python microstructure_feature_engine.py` |
| **`train_microstructure_gbdt.py`** | Purged Walk-Forward Time-Series GBDT training engine with Stage 1 Volatility Gate. | `python train_microstructure_gbdt.py` |
| **`backtest_microstructure_20x.py`** | Realistic 20X high-frequency execution backtester with Maker limit entries and dynamic stop losses. | `python backtest_microstructure_20x.py` |
| **`macro_dislocation_sniper_20x.py`** | Path A: 20X Macro Dislocation & Liquidation Sniper (+100% ROE TP, -36% ROE SL, 24h horizon). | `python macro_dislocation_sniper_20x.py` |
| **`eth_factor_research.py`** | Quantitative factor IC & Information Ratio analysis (Taker Buy Ratio, Funding Spread, Lead-Lag). | `python eth_factor_research.py` |
| **`crypto_data_collector.py`** | Multi-exchange live collector: L2 100-level depth, OBI, Microprice, Open Interest, Funding Rate across Binance, OKX, Bitget. | `python crypto_data_collector.py` |
| **`download_binance_vision_history.py`** | High-speed automated downloader & Parquet consolidator for Binance Vision historical futures archives. | `python download_binance_vision_history.py` |

---

## 4. Key Performance Visualizations / 核心实证走势大图

### 1. Hybrid Core-Satellite Architecture (85% Funding Arb + 15% 20X Sniper)
![Core Satellite Performance](charts/core_satellite_performance.png)

### 2. Microstructure 20X Execution vs 1-Minute Fee Friction
![Microstructure 20X Performance](charts/microstructure_20x_performance.png)

### 3. Path A: 20X Macro Dislocation & Liquidation Sniper (2020 - 2026)
![Macro Sniper Performance](charts/macro_sniper_20x_performance.png)

### 4. Delta-Neutral Funding Arbitrage vs Liquidation Hunter
![Liquidation vs Funding](charts/liquidation_vs_funding_arb_performance.png)

---

## 5. Detailed Documentation Links / 深度文档索引
- **Full Walkthrough & Empirical Report / 完整执行复盘报告**: [`docs/WALKTHROUGH_LEVERAGE.md`](docs/WALKTHROUGH_LEVERAGE.md)
- **Data Dictionary & Schema Specification / 数据字典与字段规范**: [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md)
- **Summary Metrics Datasets / 汇总数据表**: [`summary_data/`](summary_data/)
