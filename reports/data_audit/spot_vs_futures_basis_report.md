# Market Data Source Verification & Spot vs Futures Basis Report
# 历史行情来源分段核实与现货合约基差报告

> **Audit Timestamp**: 2026-09-23 13:11:46 UTC

## 1. Local Parquet Dataset Segment-by-Segment Origin Attribution (Bar-by-Bar)
## 本地现有 Parquet 数据集历史各时段真实来源实证判定（逐根精准对齐）

| Symbol | Segment | Local Bars | Eval Bars | Futures Match | Spot Match | Unknown | Fut Match % | Spot Match % | Spot MAE | Fut MAE | Empirical Qualification |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **BTCUSDT** | Phase_1_2020_2023 | 7428 | 7428 | 0 | 7428 | 0 | 0.0% | 100.0% | $0.0000 | $17.9618 | **VERIFIED_SPOT_100PCT** |
| **BTCUSDT** | Phase_2_2024_2025 | 4386 | 4386 | 0 | 4386 | 0 | 0.0% | 100.0% | $0.0000 | $37.2730 | **VERIFIED_SPOT_100PCT** |
| **BTCUSDT** | Phase_3_2026 | 1590 | 1590 | 56 | 1533 | 1 | 3.5% | 96.4% | $1.2127 | $33.0231 | **PREDOMINANTLY_SPOT_96.4PCT** |
| **BTCUSDT** | Full_Cycle | 13404 | 13404 | 56 | 13347 | 1 | 0.4% | 99.6% | $0.1439 | $26.0674 | **PREDOMINANTLY_SPOT_99.6PCT** |
| **ETHUSDT** | Phase_1_2020_2023 | 7428 | 7428 | 0 | 7428 | 0 | 0.0% | 100.0% | $0.0000 | $1.0955 | **VERIFIED_SPOT_100PCT** |
| **ETHUSDT** | Phase_2_2024_2025 | 4386 | 4386 | 0 | 4386 | 0 | 0.0% | 100.0% | $0.0000 | $1.4150 | **VERIFIED_SPOT_100PCT** |
| **ETHUSDT** | Phase_3_2026 | 1590 | 1590 | 56 | 1533 | 1 | 3.5% | 96.4% | $0.0416 | $1.0162 | **PREDOMINANTLY_SPOT_96.4PCT** |
| **ETHUSDT** | Full_Cycle | 13404 | 13404 | 56 | 13347 | 1 | 0.4% | 99.6% | $0.0049 | $1.1906 | **PREDOMINANTLY_SPOT_99.6PCT** |
| **SOLUSDT** | Phase_1_2020_2023 | 7427 | 7223 | 4 | 7223 | 0 | 0.1% | 100.0% | $0.0000 | $0.0330 | **VERIFIED_SPOT_100PCT** |
| **SOLUSDT** | Phase_2_2024_2025 | 4386 | 4386 | 0 | 4386 | 0 | 0.0% | 100.0% | $0.0000 | $0.0837 | **VERIFIED_SPOT_100PCT** |
| **SOLUSDT** | Phase_3_2026 | 1590 | 1590 | 56 | 1533 | 1 | 3.5% | 96.4% | $0.0016 | $0.0480 | **PREDOMINANTLY_SPOT_96.4PCT** |
| **SOLUSDT** | Full_Cycle | 13403 | 13199 | 60 | 13142 | 1 | 0.5% | 99.6% | $0.0002 | $0.0517 | **PREDOMINANTLY_SPOT_99.6PCT** |
| **BNBUSDT** | Phase_1_2020_2023 | 7428 | 7428 | 0 | 7428 | 0 | 0.0% | 100.0% | $0.0000 | $0.2018 | **VERIFIED_SPOT_100PCT** |
| **BNBUSDT** | Phase_2_2024_2025 | 4386 | 4386 | 0 | 4386 | 0 | 0.0% | 100.0% | $0.0000 | $0.3273 | **VERIFIED_SPOT_100PCT** |
| **BNBUSDT** | Phase_3_2026 | 1590 | 1590 | 56 | 1533 | 1 | 3.5% | 96.4% | $0.0160 | $0.2955 | **PREDOMINANTLY_SPOT_96.4PCT** |
| **BNBUSDT** | Full_Cycle | 13404 | 13404 | 56 | 13347 | 1 | 0.4% | 99.6% | $0.0019 | $0.2540 | **PREDOMINANTLY_SPOT_99.6PCT** |

> [!NOTE]
> **Data Audit Scope & Unclassified Bar Disclosure / 核验范围与未分类 K 线披露**:
> 1. **Comparison Scope / 核验范围**: The bar-by-bar matching audit compares **OHLC (Open, High, Low, Close)** price levels with an absolute threshold of $< 1e-4$. Volume is excluded because Binance Spot and USDS-M Futures have fundamentally different contract multiplier and turnover bases.
> 2. **The 1 Unclassified Bar / 唯一未分类 K 线**: In Phase 3 (2026), exactly 1 bar per token at `2026-09-22 20:00:00 UTC` was classified as Unknown. Detailed inspection reveals that its Open, High, and Low matched Binance Futures 100% (delta 0.0000), but its Close differed by $< 0.05\%$ from both final Spot and Futures closes. This occurred because the earlier automated synchronization script captured a live mid-candle snapshot prior to the final 4-hour settlement. It is therefore precisely classified as an `INCOMPLETE_CLOSING_SNAPSHOT`.

---

## 2. Spot vs Futures Basis & Signal Divergence (Common Timestamps)
## 现货与合约基差分布与趋势信号分歧分析

| Symbol | Overlap Range | Mean Basis % | Min Basis % | Max Basis % | 99th Pct Basis % | Return Corr | EMA200 Mismatch % | Donchian120 Mismatch % |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **BTCUSDT** | 2020-08-11 ~ 2026-09-23 | -0.016% | -1.858% | +2.101% | +0.159% | 0.99926 | 0.05% (7 bars) | 0.25% (34 bars) |
| **ETHUSDT** | 2020-08-11 ~ 2026-09-23 | -0.013% | -2.522% | +1.394% | +0.194% | 0.99950 | 0.07% (9 bars) | 0.13% (18 bars) |
| **SOLUSDT** | 2020-09-14 ~ 2026-09-23 | -0.030% | -19.726% | +1.918% | +0.275% | 0.99600 | 0.05% (7 bars) | 0.05% (7 bars) |
| **BNBUSDT** | 2020-08-11 ~ 2026-09-23 | +0.001% | -1.352% | +1.774% | +0.226% | 0.99881 | 0.24% (32 bars) | 0.12% (16 bars) |

---

## 3. Cryptographic SHA-256 Dataset Fingerprints / 数据集哈希指纹

| Dataset Key | File Path | Total Bars | SHA-256 Fingerprint |
| :--- | :--- | :---: | :--- |
| `spot_BTCUSDT` | `data\spot\BTCUSDT_4h_2020_2026.parquet` | 13408 | `9bc84c327051d66481602724485c68c68b49eb6a01510c9015c87d58d4d1ad50` |
| `spot_ETHUSDT` | `data\spot\ETHUSDT_4h_2020_2026.parquet` | 13408 | `5fecb2e1597adb74637c535a886a64d39dff740c453291e42982e305769fe507` |
| `spot_SOLUSDT` | `data\spot\SOLUSDT_4h_2020_2026.parquet` | 13407 | `3dff2e820b800dc477826895c792cc96f8383f6a74c44f5a369b202713745d31` |
| `spot_BNBUSDT` | `data\spot\BNBUSDT_4h_2020_2026.parquet` | 13408 | `0841e02794d01e924dd9a5ac6598783a19c233a5d0df883c3a3f32c5037e2e78` |
| `futures_reference_BTCUSDT` | `data\futures_reference\BTCUSDT_4h_2020_2026.parquet` | 13408 | `6576a7174c5adf04d85819dd6c3d7906fd0d2cf625d89c59a44fa829597b493b` |
| `futures_reference_ETHUSDT` | `data\futures_reference\ETHUSDT_4h_2020_2026.parquet` | 13408 | `ff5080a6652426de04909f01b7e6eb4287349f7533d1d78e0dea25a6475826b0` |
| `futures_reference_SOLUSDT` | `data\futures_reference\SOLUSDT_4h_2020_2026.parquet` | 13203 | `c0f68656575556aeedfab781da836ab8ed834b50894607dcac02995d507f27cb` |
| `futures_reference_BNBUSDT` | `data\futures_reference\BNBUSDT_4h_2020_2026.parquet` | 13408 | `02b8f0e5cb7d7d81b47c9fc72741364134ae7625e52675a584dde7a3b62ac9d3` |
| `existing_local_BTCUSDT` | `data\BTCUSDT_4h_2020_2026.parquet` | 13404 | `72af654e7325cd8403c11acb6e2747fce0fd291630ea589472d381b307215893` |
| `existing_local_ETHUSDT` | `data\ETHUSDT_4h_2020_2026.parquet` | 13404 | `8cbafbb3e169cdbfe680773cf39f60d934c91e6d81035f5e49c1be869abd5480` |
| `existing_local_SOLUSDT` | `data\SOLUSDT_4h_2020_2026.parquet` | 13403 | `fd0a0800b1a149fa8e8c9d13ed73fea774597733ce78447879a5dc11aaab2810` |
| `existing_local_BNBUSDT` | `data\BNBUSDT_4h_2020_2026.parquet` | 13404 | `b2c6ba3ee1bb668199edb76aaa91fd0d8ebb1897327391281da2a623eb3cf58d` |

---

## 4. Methodological Conclusions & Action Directives / 方法论结论与操作准则

1. **Local Data Origin Verified / 本地数据定性实证完成**:
   - The segment audit definitively shows whether local data matches standard futures or spot across each epoch.
2. **Strict Multi-Market Separation / 严格独立分库**:
   - Standard Spot data is now independently housed under `data/spot/` and standard Futures under `data/futures_reference/`.
   - Re-simulations of Spot trend strategies will strictly consume `data/spot/`, completely eliminating futures basis contamination.
