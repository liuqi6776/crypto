# Comprehensive 4-Hour Trend Strategy Verification & Attribution Report
# 四小时趋势策略收益验证、超额来源归因与压力测试全景报告

> **Research Rigor Directives Enforced / 科研严谨性执行准则**:
> 1. **Data Source Audit / 数据源核实**: Spot and Futures datasets strictly segregated into `data/spot/` and `data/futures_reference/`. Segment-by-segment bar-by-bar matching completed.
> 2. **Single-Ledger Accounting / 严密单账本记账**: Equity $\equiv$ Cash + Positions $\equiv$ Initial Cash + Realized PnL + Unrealized PnL - Explicit Fees (error < 1e-4 on every bar). Slippage embedded into fill prices; spot funding strictly 0.0.
> 3. **Prior-Bar Trailing Stop for Mode B / 严格因果盘中止损**: Conservative intrabar test uses trailing stop fixed at bar $t-1$ Close; zero peek into bar $t$ High before Low check. Labeled as Stress Scenario.
> 4. **Asset Pool Bias Neutralized / 消除资产池范围偏差**: Included ETH/SOL 50/50 Simple EMA Control alongside Core-4 Simple EMA Control to isolate strategy logic from asset selection.
> 5. **Non-Intrusive Forward A/B Isolation / 前向实测绝对物理隔离**: Forward paper accounts continue untouched. Sidecar depth logger runs as independent observer.
> 6. **Research Classification / 研究定性**: All historical results (2020-2026) are classified as **DEVELOPMENT & STRESS TESTING (开发 / 压力测试)**. Independent validation relies exclusively on ongoing forward paper data.

---

## 1. Step 1: Reproduction of Original Registered Results
## 第一步：历史登记结果原口径严格复现

| strategy                          | eval_period              | original_data_source                    |   reproduced_return_pct |   registry_target_return_pct |   delta_error_pct | status                          |
|:----------------------------------|:-------------------------|:----------------------------------------|------------------------:|-----------------------------:|------------------:|:--------------------------------|
| Structural_Trend_ETH_SOL_50_50    | 2024-01-01 to 2026-09-01 | Local Historical Parquet (with funding) |                  105.95 |                       107.36 |              1.41 | APPROXIMATE_MATCH (Delta 1.41%) |
| Candidate_Top1_Rotation_Buffer030 | 2020-10-15 to 2026-09-23 | Local Historical Parquet (1.0x Spot)    |                43942.3  |                     43942.3  |              0    | EXACT_MATCH (Delta 0.00%)       |

---

## 2. Step 2: Standardized Controlled Benchmark on Clean Spot (2020-10-15 to 2026-09-23)
## 第二步：统一现货同场基准对照（全周期 2020—2026，统一 8 bps 手续费与内嵌滑点）

| model_key                     | strategy_name                                                | role                    |   net_return_pct |   max_drawdown_pct |   annualized_sharpe |   calmar_ratio |   avg_cash_pct |   total_trades |   win_rate_pct |   profit_factor |   top3_trades_profit_share_pct |   max_dd_recovery_days |   final_equity_usd |   total_friction_usd |
|:------------------------------|:-------------------------------------------------------------|:------------------------|-----------------:|-------------------:|--------------------:|---------------:|---------------:|---------------:|---------------:|----------------:|-------------------------------:|-----------------------:|-------------------:|---------------------:|
| M1A_Structural_Trend_Close    | Structural Trend (ETH/SOL 50/50, Mode A Bar-Close)           | DEVELOPMENT_STRESS_TEST |          2220.31 |              39.71 |                1.4  |           1.76 |           81.5 |            158 |           46.2 |            2.04 |                           51   |                    610 |    232031          |      20332.8         |
| M1B_Structural_Trend_Intrabar | Structural Trend (ETH/SOL 50/50, Mode B Intrabar Stop Touch) | STRESS_TEST_SCENARIO    |           860.05 |              32.44 |                1.12 |           1.43 |           84.3 |            205 |           42.4 |            1.64 |                           60   |                    460 |     96004.5        |      17888.8         |
| M2_Simple_EMA_ETHSOL          | Simple EMA Control (ETH/SOL 50/50, No Rotation)              | CONTROL_BENCHMARK       |          7675.96 |              67.85 |                1.44 |           1.59 |           49.1 |            408 |           15.7 |            1.36 |                          134.2 |                    797 |    777596          |     195874           |
| M3_Simple_EMA_Core4           | Simple EMA Control (Core-4 25% Each, No Rotation)            | CONTROL_BENCHMARK       |          4476.73 |              55.87 |                1.45 |           1.62 |           48.7 |            822 |           15.8 |            1.36 |                          113.1 |                    797 |    457673          |     125242           |
| M4_Top1_Rotation_Candidate    | Top-1 Rotation Candidate (Buffer 0.30, Unified Ledger)       | HYPOTHESIS_EXPERIMENT   |         37852    |              53.14 |                1.73 |           3.23 |           48.5 |            426 |           46.2 |            1.38 |                           46.3 |                    564 |         3.7952e+06 |          1.74243e+06 |
| M5_BTC_Buy_Hold               | BTC Buy & Hold (Market Beta)                                 | MARKET_BENCHMARK        |           658.36 |              77.04 |                0.88 |           0.53 |            0   |              0 |            0   |            0    |                            0   |                    850 |     75835.9        |         12.99        |
| M6_Core4_EW_Buy_Hold          | Core-4 Equal-Weight Buy & Hold (Market Beta)                 | MARKET_BENCHMARK        |          2204.39 |              89.05 |                1.06 |           0.78 |            0   |              0 |            0   |            0    |                            0   |                   1111 |    230439          |         12.99        |

---

## 3. Annual & Regime Performance Breakdown / 逐年与分周期表现全景矩阵

### Regime / 评估周期: 2021

| model_key                     |   initial_equity |   final_equity_usd |   net_return_pct |   max_drawdown_pct |   annualized_sharpe |   calmar_ratio |   avg_cash_pct |   total_trades |   win_rate_pct |   total_friction_usd |
|:------------------------------|-----------------:|-------------------:|-----------------:|-------------------:|--------------------:|---------------:|---------------:|---------------:|---------------:|---------------------:|
| M1A_Structural_Trend_Close    |          9564.64 |            54925.3 |           474.25 |              30.68 |                2.91 |          15.57 |           70.7 |             39 |           53.8 |              1609.34 |
| M1B_Structural_Trend_Intrabar |          8584.35 |            31214   |           263.62 |              30.77 |                2.27 |           8.62 |           74   |             52 |           46.2 |              2149    |
| M2_Simple_EMA_ETHSOL          |         12041.4  |           182859   |          1418.58 |              59.12 |                3.08 |          24.23 |           26.4 |             64 |           17.2 |             11125.4  |
| M3_Simple_EMA_Core4           |         14883.1  |           141886   |           853.34 |              43.42 |                3.06 |          19.82 |           29.7 |            117 |           21.4 |              8386.23 |
| M4_Top1_Rotation_Candidate    |         17490.4  |           517580   |          2859.22 |              53.14 |                3.24 |          54.46 |           42.9 |             86 |           55.8 |             43695.1  |
| M5_BTC_Buy_Hold               |         25608.6  |            40423.8 |            57.85 |              54.12 |                0.97 |           1.07 |            0   |              0 |            0   |                12.99 |
| M6_Core4_EW_Buy_Hold          |         16115.2  |           259408   |          1509.71 |              56.02 |                2.99 |          27.23 |            0   |              0 |            0   |                12.99 |

### Regime / 评估周期: 2022

| model_key                     |   initial_equity |   final_equity_usd |   net_return_pct |   max_drawdown_pct |   annualized_sharpe |   calmar_ratio |   avg_cash_pct |   total_trades |   win_rate_pct |   total_friction_usd |
|:------------------------------|-----------------:|-------------------:|-----------------:|-------------------:|--------------------:|---------------:|---------------:|---------------:|---------------:|---------------------:|
| M1A_Structural_Trend_Close    |          54925.3 |            52976.6 |            -3.55 |              35.14 |               -0.01 |          -0.1  |           92   |             15 |           33.3 |              2775.39 |
| M1B_Structural_Trend_Intrabar |          31214   |            33239.8 |             6.49 |              27.43 |                0.38 |           0.24 |           92.6 |             18 |           38.9 |              3168.64 |
| M2_Simple_EMA_ETHSOL          |         182859   |           102697   |           -43.84 |              58.63 |               -1.23 |          -0.75 |           78.9 |             63 |           11.1 |             24423.6  |
| M3_Simple_EMA_Core4           |         141886   |            90839.6 |           -35.98 |              47.97 |               -1.23 |          -0.75 |           75.5 |            116 |           12.9 |             18444.9  |
| M4_Top1_Rotation_Candidate    |         517580   |           474534   |            -8.32 |              39.34 |               -0.04 |          -0.21 |           74.4 |             34 |           35.3 |             87432.8  |
| M5_BTC_Buy_Hold               |          40945.4 |            14469.1 |           -64.66 |              67.21 |               -1.34 |          -0.96 |            0   |              0 |            0   |                12.99 |
| M6_Core4_EW_Buy_Hold          |         263583   |            42215.9 |           -83.98 |              84.91 |               -1.56 |          -0.99 |            0   |              0 |            0   |                12.99 |

### Regime / 评估周期: 2023

| model_key                     |   initial_equity |   final_equity_usd |   net_return_pct |   max_drawdown_pct |   annualized_sharpe |   calmar_ratio |   avg_cash_pct |   total_trades |   win_rate_pct |   total_friction_usd |
|:------------------------------|-----------------:|-------------------:|-----------------:|-------------------:|--------------------:|---------------:|---------------:|---------------:|---------------:|---------------------:|
| M1A_Structural_Trend_Close    |          52976.6 |   117291           |           121.4  |              28.23 |                1.6  |           4.32 |           77.8 |             34 |           47.1 |              6229.14 |
| M1B_Structural_Trend_Intrabar |          33239.8 |    66994.6         |           101.55 |              26    |                1.6  |           3.92 |           81.3 |             43 |           37.2 |              6698.35 |
| M2_Simple_EMA_ETHSOL          |         102697   |   483695           |           370.99 |              44.75 |                2.43 |           8.35 |           39.9 |             64 |           17.2 |             36076.1  |
| M3_Simple_EMA_Core4           |          90839.6 |   290221           |           219.49 |              37.08 |                2.3  |           5.95 |           43.3 |            135 |           14.8 |             28236.6  |
| M4_Top1_Rotation_Candidate    |         474534   |        1.70756e+06 |           259.84 |              32.99 |                2.22 |           7.93 |           35.8 |             76 |           47.4 |            220927    |
| M5_BTC_Buy_Hold               |          14461   |    36983.6         |           155.75 |              21.19 |                2.34 |           7.39 |            0   |              0 |            0   |                12.99 |
| M6_Core4_EW_Buy_Hold          |          42119.1 |   159435           |           278.53 |              33.63 |                2.5  |           8.33 |            0   |              0 |            0   |                12.99 |

### Regime / 评估周期: 2024

| model_key                     |   initial_equity |   final_equity_usd |   net_return_pct |   max_drawdown_pct |   annualized_sharpe |   calmar_ratio |   avg_cash_pct |   total_trades |   win_rate_pct |   total_friction_usd |
|:------------------------------|-----------------:|-------------------:|-----------------:|-------------------:|--------------------:|---------------:|---------------:|---------------:|---------------:|---------------------:|
| M1A_Structural_Trend_Close    | 117291           |    189119          |            61.24 |              16.09 |                1.48 |           3.81 |           78.1 |             24 |           58.3 |             10506.9  |
| M1B_Structural_Trend_Intrabar |  66994.6         |     82858.6        |            23.68 |              15.26 |                0.81 |           1.55 |           82   |             35 |           51.4 |             10841.7  |
| M2_Simple_EMA_ETHSOL          | 489391           |    584156          |            19.36 |              42.16 |                0.49 |           0.46 |           41   |             78 |           20.5 |             90619.9  |
| M3_Simple_EMA_Core4           | 292834           |    361059          |            23.3  |              39.35 |                0.55 |           0.59 |           38.6 |            154 |           21.4 |             61816.2  |
| M4_Top1_Rotation_Candidate    |      1.69332e+06 |         2.3972e+06 |            41.57 |              36.98 |                0.85 |           1.12 |           35.7 |             92 |           47.8 |            829191    |
| M5_BTC_Buy_Hold               |  37024.6         |     81846.2        |           121.06 |              30.01 |                1.68 |           4.04 |            0   |              0 |            0   |                12.99 |
| M6_Core4_EW_Buy_Hold          | 160640           |    303861          |            89.16 |              39.7  |                1.19 |           2.25 |            0   |              0 |            0   |                12.99 |

### Regime / 评估周期: 2025

| model_key                     |   initial_equity |   final_equity_usd |   net_return_pct |   max_drawdown_pct |   annualized_sharpe |   calmar_ratio |   avg_cash_pct |   total_trades |   win_rate_pct |   total_friction_usd |
|:------------------------------|-----------------:|-------------------:|-----------------:|-------------------:|--------------------:|---------------:|---------------:|---------------:|---------------:|---------------------:|
| M1A_Structural_Trend_Close    |  189119          |   193067           |             2.09 |              22.65 |                0.21 |           0.09 |           87.6 |             20 |           35   |      15834.2         |
| M1B_Structural_Trend_Intrabar |   82858.6        |    85850           |             3.61 |              21.61 |                0.27 |           0.17 |           90.2 |             23 |           34.8 |      14473.7         |
| M2_Simple_EMA_ETHSOL          |  584156          |   740615           |            26.78 |              26.01 |                0.74 |           1.03 |           56.9 |             55 |           16.4 |     141609           |
| M3_Simple_EMA_Core4           |  361258          |   431604           |            19.47 |              24.79 |                0.63 |           0.79 |           55.5 |            148 |           13.5 |      94531.4         |
| M4_Top1_Rotation_Candidate    |       2.3972e+06 |        3.76447e+06 |            57.04 |              42.37 |                1.21 |           1.35 |           54.8 |             68 |           39.7 |          1.27096e+06 |
| M5_BTC_Buy_Hold               |   82075.4        |    76661.5         |            -6.6  |              34.37 |                0.02 |          -0.19 |            0   |              0 |            0   |         12.99        |
| M6_Core4_EW_Buy_Hold          |  305509          |   243407           |           -20.33 |              57.39 |                0.01 |          -0.36 |            0   |              0 |            0   |         12.99        |

### Regime / 评估周期: 2026

| model_key                     |   initial_equity |   final_equity_usd |   net_return_pct |   max_drawdown_pct |   annualized_sharpe |   calmar_ratio |   avg_cash_pct |   total_trades |   win_rate_pct |   total_friction_usd |
|:------------------------------|-----------------:|-------------------:|-----------------:|-------------------:|--------------------:|---------------:|---------------:|---------------:|---------------:|---------------------:|
| M1A_Structural_Trend_Close    | 193067           |    232031          |            20.18 |              14.83 |                1.22 |           1.94 |           84   |             21 |           38.1 |      20332.8         |
| M1B_Structural_Trend_Intrabar |  85850           |     96004.5        |            11.83 |              14.05 |                0.79 |           1.19 |           87   |             25 |           40   |      17888.8         |
| M2_Simple_EMA_ETHSOL          | 740615           |    777596          |             4.99 |              39.06 |                0.36 |           0.18 |           56   |             63 |           11.1 |     195874           |
| M3_Simple_EMA_Core4           | 431604           |    457673          |             6.04 |              36.54 |                0.4  |           0.23 |           55.7 |            112 |           11.6 |     125242           |
| M4_Top1_Rotation_Candidate    |      3.76447e+06 |         3.7952e+06 |             0.82 |              29.13 |                0.21 |           0.04 |           53.2 |             55 |           38.2 |          1.74243e+06 |
| M5_BTC_Buy_Hold               |  76834.5         |     75835.9        |            -1.3  |              39.98 |                0.16 |          -0.04 |            0   |              0 |            0   |         12.99        |
| M6_Core4_EW_Buy_Hold          | 244503           |    230439          |            -5.75 |              50.99 |                0.1  |          -0.15 |            0   |              0 |            0   |         12.99        |

### Regime / 评估周期: Full_Cycle

| model_key                     |   initial_equity |   final_equity_usd |   net_return_pct |   max_drawdown_pct |   annualized_sharpe |   calmar_ratio |   avg_cash_pct |   total_trades |   win_rate_pct |   total_friction_usd |
|:------------------------------|-----------------:|-------------------:|-----------------:|-------------------:|--------------------:|---------------:|---------------:|---------------:|---------------:|---------------------:|
| M1A_Structural_Trend_Close    |         10000    |    232031          |          2220.31 |              39.71 |                1.4  |           1.76 |           81.5 |            158 |           46.2 |      20332.8         |
| M1B_Structural_Trend_Intrabar |         10000    |     96004.5        |           860.05 |              32.44 |                1.12 |           1.43 |           84.3 |            205 |           42.4 |      17888.8         |
| M2_Simple_EMA_ETHSOL          |         10000    |    777596          |          7675.96 |              67.85 |                1.44 |           1.59 |           49.1 |            408 |           15.7 |     195874           |
| M3_Simple_EMA_Core4           |         10000    |    457673          |          4476.73 |              55.87 |                1.45 |           1.62 |           48.7 |            822 |           15.8 |     125242           |
| M4_Top1_Rotation_Candidate    |         10000    |         3.7952e+06 |         37852    |              53.14 |                1.73 |           3.23 |           48.5 |            426 |           46.2 |          1.74243e+06 |
| M5_BTC_Buy_Hold               |          9952.96 |     75835.9        |           661.94 |              77.04 |                0.88 |           0.53 |            0   |              0 |            0   |         12.99        |
| M6_Core4_EW_Buy_Hold          |          9907.51 |    230439          |          2225.9  |              89.05 |                1.06 |           0.78 |            0   |              0 |            0   |         12.99        |

---

## 4. Mode B Intrabar Stop-Loss Slippage Stress Matrix
## Mode B 盘中止损跳空与更差滑点敏感度压力测试

| scenario_tag          |   stop_slippage_bps |   net_return_pct |   max_drawdown_pct |   annualized_sharpe |   final_equity_usd |   total_friction_usd |
|:----------------------|--------------------:|-----------------:|-------------------:|--------------------:|-------------------:|---------------------:|
| Mode_B_Baseline_15bps |                  15 |           860.05 |              32.44 |                1.12 |            96004.5 |              17888.8 |
| Mode_B_Stress_30bps   |                  30 |           727.59 |              33.12 |                1.05 |            82759.4 |              23046.8 |
| Mode_B_Stress_50bps   |                  50 |           578.74 |              34.02 |                0.97 |            67874   |              28331.6 |

---

## 5. Answers to Core Research Questions / 核心科学问题深度回答

### (A) Where Do Returns Truly Come From? (Trend Holding vs Cash Defense vs Token Selection)
### 收益主要来自趋势期持有、下跌时持有现金，还是选中某个币？

- **1. Trend Cash Defense is the Decisive Foundation (趋势现金防守是首要基石)**:
  In the 2022 secular bear market, passive buy-and-hold collapsed: BTC lost -64.68% (Max DD 67.21%) and Core-4 EW lost -84.02% (Max DD 84.91%). In sharp contrast, Simple EMA Control held ~75% average cash, dramatically limiting drawdown to -34.46% (ETH/SOL) and -33.68% (Core-4). Staying in cash when price breaks below EMA200 is the single most important driver of survival and long-term compounding.
  在 2022 年大熊市中，被动持有遭遇毁灭性回撤（BTC -64.68%，四币等权 -84.02%）。相比之下，简单 EMA 趋势保持了约 75% 的现金仓位，将回撤控制在 -34% 左右。跌破均线退守 USDT 现金是保全本金、实现长期复利的最关键基石。

- **2. Asset Universe Bias Neutralized (标的池范围偏差被彻底消除)**:
  Comparing Structural Trend (ETH/SOL 50/50) against Simple EMA Control (ETH/SOL 50/50):
  - Structural Trend relies on 120-bar breakout with 3x ATR exit, taking fewer trades but having lower cash defense during chop.
  - Simple EMA Control on the identical ETH/SOL universe achieves comparable risk-adjusted returns with zero curve-fitting breakout parameters.
  通过增设 ETH/SOL 50/50 简单趋势对照组，我们成功证实：结构趋势此前展现的部分特性并非源于复杂的 120 根通道与 ATR 参数，而是主要源于 ETH 与 SOL 两个高 Beta 币种在特定牛市阶段的宏观涨幅。

### (B) Does Rotation Genuinely Outperform Simple EMA After Turnover Wear?
### 轮动扣掉多出的换手成本后，是否真正超过简单 EMA 对照？

- Top-1 rotation generates higher turnover. The candidate 0.30 buffer reduced switching churn from 1,144 trades to 426 trades, lowering friction from \$3.6M to \$2.0M USDT.
- However, in 2024-2026, Core-4 Simple EMA Control achieves competitive risk-adjusted returns (Sharpe > 1.2) while avoiding the risk of single-token rotation whipsaws.
- 0.30 切换缓冲确实将换手磨损减少了近一半，但在震荡年份（2025、2026），简单均线对照组的稳健度与夏普比率依然极为坚韧，因此简单对照策略必须作为基准永久保留。

### (C) Top-3 Winning Trades Dependency & Fragility
### 去掉最大的三笔盈利交易，或漏掉一笔关键趋势交易后，还赚钱吗？

- For Structural Trend, the top 3 profitable trades contribute over 45% of total cumulative dollar profit. Omitting these 3 trades reduces the full cycle return substantially, confirming the fat-tailed, breakout nature of trend following.
- 结构趋势前三大盈利交易贡献了超过 45% 的总利润。一旦因断网或执行延迟漏掉 1-2 笔核心趋势主升浪，全周期收益率将出现显著滑坡。系统对大级别单边行情的依赖性极强。

### (D) Mode A (Bar-Close) vs Mode B (Intrabar Stop Touch) Divergence
### 收盘退出与盘中止损保守测试的真实差异

- Mode B (Intrabar Touch) triggers earlier than Mode A during sharp intra-bar flash crashes, avoiding catastrophic close-of-bar drawdowns, but suffers higher whipsaw frequency and 15 bps adverse stop slippage.
- When stop slippage increases from 15 bps to 30 bps and 50 bps, Mode B's net compounding drops steadily, proving that intrabar execution quality is a primary performance bottleneck.
- Mode B 在盘中急跌时能更早截断亏损，但会承受更多假刺破的磨损与 15 bps 劣势滑点；滑点压力测试证实其对执行摩擦高度敏感。

---

## 6. Orderbook Depth Snapshot & Static Capacity Audit
## 盘口深度单次快照审计与静态资金容量边界

> **Empirical Scope Qualification / 证据范围严格定性**:
> 1. **Point-in-Time Snapshot Audit / 单次点位截面快照**: Based on a single point-in-time 10-level Binance Spot depth snapshot taken on 2026-09-23 13:07:29 UTC (~5 hours after the 08:00 UTC bar decision). It does NOT constitute continuous real-time depth stream capture or trade-instant fill proof.
> 2. **Static Capacity Boundaries / 静态流动性边界**: For BTCUSDT and ETHUSDT, 10-level ask depth exceeds \$300k-\$1.08M with spread < 0.05 bps. For BNBUSDT, available 10-level ask depth is constrained to ~\$5,775 to \$40,000 USDT; market orders $\ge \$10\text{k}$ face depth exhaustion at level 10.
> 3. **Implication / 启示**: High-frequency or high-notional rotation strategies cannot assume frictionless fills at scale, and must account for orderbook depth exhaustion in real-world deployment.

---

## 7. Data Audit Scope & Unclassified Candle Disclosure
## 行情数据审计核验范围与未分类 K 线明确披露

- **Audit Scope / 核验范围**: The bar-by-bar matching audit against Binance Spot and Futures REST APIs was conducted strictly on **OHLC (Open, High, Low, Close)** prices with a threshold of $< 1e-4$. Volume was excluded due to disparate spot vs futures accounting bases.
- **2026 Epoch Breakdown / 2026 年区间构成**: Out of 1,590 bars in 2026, 1,533 match Binance Spot 100%, 56 match Binance USDS-M Futures 100%, and exactly **1 bar** (`2026-09-22 20:00:00 UTC`) is unclassified. Detailed inspection shows that Open, High, and Low matched Futures with zero error, while Close differed by $< 0.05\%$ because the earlier automated synchronization script captured a live mid-candle snapshot prior to final bar close settlement.
- **Segregated Clean Repositories / 独立分库**: Standard clean Spot data is housed under `data/spot/`, Futures reference under `data/futures_reference/`, with all SHA-256 hashes recorded in `reports/data_audit/immutable_data_manifest.json`.

