# Argon 4_research — Binance Funding-Rate Extremes & Multi-Timeframe Squeeze-Reversal Research
# Argon 4_research —— 币安资金费率极值与多周期轧空反转研究

> [!WARNING]
> **Status: `LEGACY_RESEARCH` / `HYPOTHESIS_EXPERIMENT` — NOT a production-ready or publishable result.**
> These backtests did **not** run through `crypto_quant.research.framework_gate` / `scripts/run_research_backtest.py` and do not satisfy `docs/CRYPTO_QUANT_FRAMEWORK_V1.md` (no capacity/participation check, no funding cost on positions, no immutable provenance manifest, no preregistration).
> **Known look-ahead bias:** the backtest scripts locate the 15m "peak" with `df_15m['high'].idxmax()` over the *whole* episode window (including bars after the entry), and episodes were selected using funding events that are themselves known only at settlement. Return figures (e.g. "+316% on $50k") are therefore **optimistic upper bounds, not expected performance**.
>
> **状态：`LEGACY_RESEARCH`（历史探索性研究）/ `HYPOTHESIS_EXPERIMENT`，不是可上线或可公开宣称的结果。**
> 这些回测**未**经过仓库的 `framework_gate` 中央回测器，不满足 V1 框架协议（缺少成交量容量约束、持仓资金费成本、不可变数据溯源清单与预注册）。
> **已知未来函数：** 回测脚本用整个事件窗口的 `idxmax()` 定位 15 分钟“顶部”（包含入场之后的 K 线），因此“5 万→20 万”等收益数字只能视为**乐观上限，而非预期收益**。

---

## 1. Background / 研究背景

**English.** Research session (2026-09-19 → 2026-09-22) investigating whether Binance perpetual funding-rate extremes predict price direction, and whether a "terminal squeeze" short strategy on extreme altcoins is tradable. Questions asked, in order:
1. Do extreme negative funding rates lead to rises, and extreme positive ones to falls? (statistical distribution over ~50k funding events, 2023–2026)
2. Is the effect specific to extreme altcoins, and meaningless for BTC/ETH?
3. Can 50–100x leverage on 1s/1m bars work? (Answer: no — the liquidation buffer is smaller than typical 1m noise.)
4. 1m backtest with taker execution at 3x/5x, then a 1h + 15m + 1m confluence engine (Maker vs Taker).
5. Expanding trade count (Top-N relaxed thresholds), then a $50,000 "all-satellite" compounding portfolio simulation.

**中文。** 本研究（2026-09-19 至 09-22）探究币安永续合约资金费率极值能否预测价格方向，以及在极值山寨币上做“轧空末端做空”是否可交易。依次回答：
1. 极负费率是否更易上涨、极正费率是否更易下跌？（约 5 万条费率事件的统计分布，2023–2026）
2. 该效应是否只对极值山寨币有效，对 BTC/ETH 无意义？
3. 1 秒/1 分钟级别开 50–100 倍杠杆是否可行？（结论：不可行，爆仓缓冲小于 1 分钟正常波动）
4. 1 分钟 Taker 回测（3x/5x），再升级为 1h + 15m + 1m 多周期协同引擎（Maker vs Taker）
5. 放宽阈值扩容交易次数，最后进行 5 万美金“全卫星”复利组合模拟。

## 2. Folder layout / 目录结构

| Path | Content (EN) | 内容（中文） |
| :--- | :--- | :--- |
| `docs/` | All session reports (empirical study, playbook, BTC/ETH comparison, leverage/HFT analysis, implementation plan, task list, walkthrough) + charts | 本次会话全部报告与图表（双语） |
| `code/scripts/` | Backtest engines: 1m terminal squeeze, multi-TF confluence, expanded Top-N, $50k all-satellite | 回测引擎脚本 |
| `code/scratch/` | Data fetchers, funding-dataset builder, statistics, leverage simulation, exploratory probes | 数据抓取、费率数据集构建、统计与探索脚本 |
| `data/funding/` | `funding_dataset_with_returns.parquet` (49,991 rows, Binance funding + forward/backward returns), `binance_funding_recent.parquet` | 资金费率数据集 |
| `data/klines_1m/`, `klines_15m/`, `klines_1h/` | Binance USDT-M **futures** klines per squeeze episode (`SYMBOL_epid_startms_endms.parquet`) | 每个轧空事件的币安 U 本位**合约** K 线 |
| `reports/` | Trade logs (CSV) and equity curves (PNG) of each backtest | 各回测逐笔交易日志与净值曲线 |

> [!NOTE]
> Klines are **futures** candles (`fapi.binance.com`), not spot. 所有 K 线均为**合约**数据，不是现货。

## 3. How to reproduce / 复现方法

Scripts use paths relative to the repository root (`scratch/...`, `reports/...`). To rerun, from the repo root:
脚本使用相对仓库根目录的路径。复现时在仓库根目录执行：

```powershell
New-Item -ItemType Directory -Force scratch | Out-Null
Copy-Item "Argon 4_research\data\funding\*.parquet" scratch\
foreach ($p in 'klines_1m','klines_15m','klines_1h') { Copy-Item -Recurse "Argon 4_research\data\$p" scratch\ }
python "Argon 4_research\code\scripts\backtest_all_satellite_50k.py"
```

(`backtest_all_satellite_50k.py` also copies its chart into a local artifact directory — edit `artifact_dir` or remove that line on another machine. / 该脚本会把图表复制到本机 artifact 目录，换机器时请修改 `artifact_dir`。)

## 4. Key findings (as recorded, subject to the caveats above) / 主要结论（受上述偏差限制）

1. Extreme negative funding is mostly a **lagging** signal (funding normalizes after squeezes); extreme positive funding tends to persist short-term. See `docs/funding_rate_empirical_study.md`.
   极负费率多为**滞后**指标；极正费率短期倾向延续。
2. The effect concentrates in small/extreme altcoins; BTC/ETH funding extremes carry little edge. See `docs/btc_eth_vs_extreme_altcoins_study.md`.
   效应集中在极值山寨币，BTC/ETH 基本无优势。
3. 50–100x on 1s/1m bars is not survivable (liquidation buffer ≈ 0.4–1% vs. much larger 1m ranges in squeezes). See `docs/leverage_and_hft_microstructure_analysis.md`.
   1 秒/1 分钟高倍杠杆不可存活。
4. Pure 1m entries performed poorly (timeframe mismatch); requiring a 15m structure break helped in-sample.
   纯 1 分钟入场表现差；加入 15 分钟结构破位过滤后样本内改善。
5. $50k all-satellite simulation (20% margin/trade, ≤3 concurrent, 38 trades, 2023-10 → 2026-09): 3x ≈ $122.7k, 5x ≈ $208–210k, max DD 11–22%. **Upper-bound only** — 26 of 38 trades are in 2026, and the peak detection uses future bars. See `docs/walkthrough.md`.
   5 万美金全卫星模拟结果（仅为乐观上限；38 笔中 26 笔集中在 2026 年，且顶部识别使用了未来数据）。

## 5. Next step required before any live use / 实盘前必须完成

Re-implement the signal as a `crypto_quant.framework.BaseStrategy` plugin in `strategies/` with a causal (expanding-window) peak/neckline detector, pass the temporal-truncation invariance test, add funding cost and quote-volume participation limits, preregister thresholds, and run it through `scripts/run_research_backtest.py`.
须将信号改写为 `strategies/` 下的因果插件（逐根 K 线递推识别顶部/颈线），通过时间截断不变性测试，加入资金费与成交量参与率约束，预注册阈值，并经中央回测器运行。
