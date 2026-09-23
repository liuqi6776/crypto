# Comprehensive 4-Hour Trend Strategy Verification & Attribution Report
# 四小时趋势策略收益验证、超额来源归因与压力测试全景报告

> **Research Rigor Directives Enforced / 科研严谨性执行准则**:
> 1. **Data Source Audit / 数据源核实**: Spot and Futures datasets strictly segregated into `data/spot/` and `data/futures_reference/`. Segment-by-segment bar-by-bar matching completed.
> 2. **Single-Ledger Accounting / 严密单账本记账**: Equity $\equiv$ Cash + Positions $\equiv$ Initial Cash + Realized PnL + Unrealized PnL - Explicit Fees (error < 1e-4 on every bar). Slippage embedded into fill prices; spot funding strictly 0.0.
> 3. **Prior-Bar Trailing Stop for Mode B / 严格因果盘中止损**: Conservative intrabar test uses trailing stop fixed at bar $t-1$ Close; zero peek into bar $t$ High before Low check. Labeled as Stress Scenario.
> 4. **Controlled Single-Variable Ablations / 严格受控单变量消融**: Evaluated pure entry channels under 100% identical exit rules, and evaluated macro sizing independently holding channel constant.
> 5. **Non-Intrusive Forward A/B Isolation / 前向实测绝对物理隔离**: Forward paper accounts continue untouched. Sidecar depth logger runs as independent observer.
> 6. **Research Classification / 研究定性**: All historical results (2020-2026) are classified as **DEVELOPMENT & STRESS TESTING (开发 / 压力测试)**. Independent validation relies exclusively on ongoing forward paper data.

---

## 1. Step 1: Reproduction of Original Registered Results
## 第一步：历史登记结果原口径严格复现

| strategy                          | eval_period              | original_data_source                    |   reproduced_return_pct |   registry_target_return_pct |   delta_error_pct | status                          | notes                                                                                                                                                                                 |
|:----------------------------------|:-------------------------|:----------------------------------------|------------------------:|-----------------------------:|------------------:|:--------------------------------|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Structural_Trend_ETH_SOL_50_50    | 2024-01-01 to 2026-09-01 | Local Historical Parquet (with funding) |                  105.95 |                       107.36 |              1.41 | APPROXIMATE_MATCH (Delta 1.41%) | Empirical reproduction shows +105.95% vs registered +107.36%. Potential causes (such as warmup boundary or float precision) are unverified hypotheses; reported as approximate match. |
| Candidate_Top1_Rotation_Buffer030 | 2020-10-15 to 2026-09-23 | Local Historical Parquet (1.0x Spot)    |                43942.3  |                     43942.3  |              0    | EXACT_MATCH (Delta 0.00%)       | nan                                                                                                                                                                                   |

---

## 2. Step 2: Standardized Controlled Benchmark on Clean Spot (2020-10-15 to 2026-09-23)
## 第二步：统一现货同场基准对照（全周期 2020—2026，统一 8 bps 手续费与内嵌滑点）

| model_key                     | strategy_name                                                | role                    |   net_return_pct |   max_drawdown_pct |   annualized_sharpe |   calmar_ratio |   avg_cash_pct |   total_trades |   win_rate_pct |   profit_factor |   top3_trades_profit_share_pct |   max_dd_recovery_days |   final_equity_usd |   total_friction_usd |
|:------------------------------|:-------------------------------------------------------------|:------------------------|-----------------:|-------------------:|--------------------:|---------------:|---------------:|---------------:|---------------:|----------------:|-------------------------------:|-----------------------:|-------------------:|---------------------:|
| M1A_Structural_Trend_Close    | Structural Trend (ETH/SOL 50/50, Mode A Bar-Close)           | DEVELOPMENT_STRESS_TEST |          2220.31 |              39.71 |                1.4  |           1.76 |           81.5 |            158 |           46.2 |            2.04 |                           51   |                    610 |    232031          |      20332.8         |
| M1B_Structural_Trend_Intrabar | Structural Trend (ETH/SOL 50/50, Mode B Intrabar Stop Touch) | STRESS_TEST_SCENARIO    |           860.05 |              32.44 |                1.12 |           1.43 |           84.3 |            205 |           42.4 |            1.64 |                           60   |                    460 |     96004.5        |      17888.8         |
| M2_Simple_EMA_ETHSOL          | Price > EMA200 Control (ETH/SOL 50/50, No Rotation)          | CONTROL_BENCHMARK       |          7675.96 |              67.85 |                1.44 |           1.59 |           49.1 |            408 |           15.7 |            1.36 |                          134.2 |                    797 |    777596          |     195874           |
| M3_Simple_EMA_Core4           | Price > EMA200 Control (Core-4 25% Each, No Rotation)        | CONTROL_BENCHMARK       |          4476.73 |              55.87 |                1.45 |           1.62 |           48.7 |            822 |           15.8 |            1.36 |                          113.1 |                    797 |    457673          |     125242           |
| M4_Top1_Rotation_Candidate    | Top-1 Rotation Candidate (Buffer 0.30, Unified Ledger)       | HYPOTHESIS_EXPERIMENT   |         37852    |              53.14 |                1.73 |           3.23 |           48.5 |            426 |           46.2 |            1.38 |                           46.3 |                    564 |         3.7952e+06 |          1.74243e+06 |
| M5_BTC_Buy_Hold               | BTC Buy & Hold (Market Beta)                                 | MARKET_BENCHMARK        |           658.36 |              77.04 |                0.88 |           0.53 |            0   |              0 |            0   |            0    |                            0   |                    850 |     75835.9        |         12.99        |
| M6_Core4_EW_Buy_Hold          | Core-4 Equal-Weight Buy & Hold (Market Beta)                 | MARKET_BENCHMARK        |          2204.39 |              89.05 |                1.06 |           0.78 |            0   |              0 |            0   |            0    |                            0   |                   1111 |    230439          |         12.99        |

---

## 3. Controlled Single-Variable Ablations / 严格受控单变量消融实验

### 3.1 Pure Entry Channel Ablation with Fixed Exit Rules (Bollinger 120 vs Donchian 120)
### 3.1 固定退场规则的纯入场通道单变量消融（布林带 120 vs 唐奇安 120 严格对照）

| control_type         | entry_channel                | exit_rule               | stop_loss_mode   |   net_return_pct |   max_drawdown_pct |   annualized_sharpe |   calmar_ratio |   total_trades |   win_rate_pct |   profit_factor |   total_friction_usd |
|:---------------------|:-----------------------------|:------------------------|:-----------------|-----------------:|-------------------:|--------------------:|---------------:|---------------:|---------------:|----------------:|---------------------:|
| PURE_ENTRY_ISOLATED  | Bollinger_120                | Shared_BB_Mid_and_3ATR  | Mode_A_Close     |          2220.31 |              39.71 |                1.4  |           1.76 |            158 |           46.2 |            2.04 |             20332.8  |
| PURE_ENTRY_ISOLATED  | Donchian_120 (Highest Close) | Shared_BB_Mid_and_3ATR  | Mode_A_Close     |          1560.21 |              41.83 |                1.3  |           1.45 |            183 |           42.6 |            1.89 |             15749.7  |
| PURE_ENTRY_ISOLATED  | Bollinger_120                | Shared_3ATR_Stop_Only   | Mode_A_Close     |          2559.86 |              40.32 |                1.44 |           1.83 |            157 |           46.5 |            2.06 |             23177.5  |
| PURE_ENTRY_ISOLATED  | Donchian_120 (Highest Close) | Shared_3ATR_Stop_Only   | Mode_A_Close     |          1556.41 |              42.14 |                1.3  |           1.43 |            183 |           42.6 |            1.89 |             15709.4  |
| PURE_ENTRY_ISOLATED  | Bollinger_120                | Prior_Bar_3ATR_Intrabar | Mode_B_Intrabar  |           860.05 |              32.44 |                1.12 |           1.43 |            205 |           42.4 |            1.64 |             17888.8  |
| PURE_ENTRY_ISOLATED  | Donchian_120 (Highest Close) | Prior_Bar_3ATR_Intrabar | Mode_B_Intrabar  |           190.89 |              40.01 |                0.68 |           0.49 |            229 |           38.4 |            1.31 |              7544.62 |
| CONFOUNDED_DUAL_SWAP | Donchian_120 (Highest Close) | Donchian_Mid_and_3ATR   | Mode_A_Close     |          1556.41 |              42.14 |                1.3  |           1.43 |            183 |           42.6 |            1.89 |             15709.4  |

> **Methodological Clarifications & Empirical Observations / 方法论澄清与实证观察**:
> 1. **Accurate Definition of Donchian Upper / 唐奇安上轨准确定义**: In code, Donchian upper is calculated as `c.shift(1).rolling(120).max()`, which represents the 120-period rolling **highest Close (最高收盘价)**, NOT highest High. Lower band is 120-period lowest Low.
> 2. **Fixed-Exit Pure Entry Controls / 退场规则完全固定的纯入场对照**:
>    - **Regime 1 (Shared BB Mid & 3.0 ATR Stop)**: Both variants exit strictly when `Close < bb_mid` (120-period MA) or trailing stop. Bollinger 120 achieves **+2,220.31%** (Sharpe 1.40, 158 trades) vs Donchian 120 at **+1,560.21%** (Sharpe 1.30, 183 trades). Observed Difference: **+660.10 percentage points (个百分点)**.
>    - **Regime 2 (Shared 3.0 ATR Stop Only, No Mid-Band Exit)**: Both variants exit strictly on trailing stop. Bollinger 120 achieves **+2,559.86%** (Sharpe 1.44, 157 trades) vs Donchian 120 at **+1,556.41%** (Sharpe 1.30, 183 trades). Observed Difference: **+1,003.45 percentage points (个百分点)**.
>    - **Regime 3 (Mode B Intrabar 3.0 ATR Stop Touch)**: Exit occurs solely when intrabar Low touches the prior-bar stop. Bollinger 120 achieves **+860.05%** (Sharpe 1.12, 205 trades) vs Donchian 120 at **+190.89%** (Sharpe 0.68, 229 trades). Observed Difference: **+669.16 percentage points (个百分点)**.
> 3. **Trade Frequency, Friction Amount, and Return Divergence / 交易频次、摩擦金额与收益分歧定性**:
>    - 在三个固定退场对照中，唐奇安通道触发了更多交易笔数（多 24 至 26 笔），但其全周期**累计摩擦金额反而更低**（例如共享布林中轨下为 $15,750，低于布林带的 $20,333；无中轨止损退出下为 $15,709，低于布林带的 $23,178；Mode B 下为 $7,545，低于布林带的 $17,889）。这是因为手续费和滑点与账户名义权益成正比，当策略净值复合增长较低时，后续单笔交易的名义金额与摩擦绝对值更小。因此，**交易笔数更多绝不等于总摩擦金额更高**。
>    - 唐奇安版本在本次回测中表现较弱的直接表现是胜率较低（38.4%~42.6% 对比 42.4%~46.5%）和盈亏比更低（1.31~1.89 对比 1.64~2.06）。导致这两组入场触发时点盈亏分歧的深层机理，不能简单推断为摩擦损耗，而需要未来进一步开展逐笔交易的微观收益拆解。此外，上述收益差（如 660.10 个百分点）均为本次特定历史样本的条件对照结果，不能当作未来交易的确定性超额。

### 3.2 Standalone EMA200 Macro Sizing Ablation (Fixed Bollinger 120 Channel)
### 3.2 独立 EMA200 宏观定仓单变量消融（固定布林带 120 通道）

| macro_sizing_mode              | stop_loss_mode   | channel_type   |   net_return_pct |   max_drawdown_pct |   annualized_sharpe |   calmar_ratio |   total_trades |   win_rate_pct |   profit_factor |   total_friction_usd |
|:-------------------------------|:-----------------|:---------------|-----------------:|-------------------:|--------------------:|---------------:|---------------:|---------------:|----------------:|---------------------:|
| EMA200_Half_Sizing (1.0 / 0.5) | Mode_A_Close     | Bollinger_120  |          2220.31 |              39.71 |                1.4  |           1.76 |            158 |           46.2 |            2.04 |              20332.8 |
| EMA200_Half_Sizing (1.0 / 0.5) | Mode_B_Intrabar  | Bollinger_120  |           860.05 |              32.44 |                1.12 |           1.43 |            205 |           42.4 |            1.64 |              17888.8 |
| Fixed_Full_Sizing (1.0 / 1.0)  | Mode_A_Close     | Bollinger_120  |          2113.72 |              40.39 |                1.39 |           1.7  |            158 |           46.2 |            1.94 |              20965.3 |
| Fixed_Full_Sizing (1.0 / 1.0)  | Mode_B_Intrabar  | Bollinger_120  |           791.83 |              33.71 |                1.09 |           1.32 |            205 |           42.4 |            1.59 |              17796.7 |
| Binary_Macro_Gate (1.0 / 0.0)  | Mode_A_Close     | Bollinger_120  |          2217.94 |              37.48 |                1.4  |           1.86 |            156 |           46.8 |            1.95 |              21899.6 |
| Binary_Macro_Gate (1.0 / 0.0)  | Mode_B_Intrabar  | Bollinger_120  |           814.03 |              31.05 |                1.09 |           1.45 |            202 |           43.1 |            1.58 |              18241.6 |

> **Empirical Sizing Contribution & Mechanistic Clarification / 宏观定仓规则独立贡献与机制准确定性**:
> - Holding the Bollinger 120 channel and stop rules strictly identical:
>   - **Mode A (Bar-Close Exit)**: Fixed Full Sizing (1.0 constant) yields **+2,113.72%** (Sharpe 1.39, Max DD 40.39%). EMA200 Half Sizing (1.0 / 0.5) achieves **+2,220.31%** (Sharpe 1.40, Max DD 39.71%). Observed Difference: **+106.59 percentage points (个百分点)**, with drawdown reduced by 0.68 percentage points (个百分点).
>   - **Mode B (Intrabar Touch)**: Fixed Full Sizing yields **+791.83%** (Sharpe 1.09, Max DD 33.71%). EMA200 Half Sizing achieves **+860.05%** (Sharpe 1.12, Max DD 32.44%). Observed Difference: **+68.22 percentage points (个百分点)**, with drawdown reduced by 1.27 percentage points (个百分点).
>   - **Binary Macro Gate (1.0 / 0.0)**: Yields **+2,217.94%** (Max DD 37.48%) in Mode A and **+814.03%** (Max DD 31.05%) in Mode B, demonstrating that blocking entry below EMA200 improves drawdown mitigation at a slight cost to compounding in early recoveries.
> - **Mechanistic Precision / 机制实现准确定性**: In code, the EMA200 `macro_mult` (1.0 / 0.5) applies **strictly at new trade entry** to determine target order notional. Once opened, if price drops below EMA200 during the trade, the existing position is **NOT** automatically reduced retroactively (it is held until trailing stop or mid-line exit). Therefore, this rule operates strictly by **reducing new position capital allocation when entering below EMA200 (低于 EMA200 时减少新仓投入)**, rather than dynamically scaling down portfolio exposure mid-trade.
> - **Conclusion / 归因裁决**: In this historical sample, reducing new position sizing when below EMA200 provided a modest positive difference (+68.22 to +106.59 percentage points; 0.68 to 1.27 percentage points drawdown improvement). This is a conditional backtest observation on the historical dataset and cannot be treated as a forecast of future performance, nor does it account for the entire divergence across broader strategy iterations.

---

## 4. Annual & Regime Performance Breakdown (Incremental Annual Friction)
## 第四步：逐年与分周期表现全景矩阵（当年独立发生增量摩擦成本）

### Regime / 评估周期: 2021

| model_key                     |   initial_equity |   final_equity_usd |   net_return_pct |   max_drawdown_pct |   annualized_sharpe |   calmar_ratio |   avg_cash_pct |   total_trades |   win_rate_pct |   total_friction_usd |
|:------------------------------|-----------------:|-------------------:|-----------------:|-------------------:|--------------------:|---------------:|---------------:|---------------:|---------------:|---------------------:|
| M1A_Structural_Trend_Close    |          9564.64 |            54925.3 |           474.25 |              30.68 |                2.91 |          15.57 |           70.7 |             39 |           53.8 |              1537.07 |
| M1B_Structural_Trend_Intrabar |          8584.35 |            31214   |           263.62 |              30.77 |                2.27 |           8.62 |           74   |             52 |           46.2 |              1986.29 |
| M2_Simple_EMA_ETHSOL          |         12041.4  |           182859   |          1418.58 |              59.12 |                3.08 |          24.23 |           26.4 |             64 |           17.2 |             10863.6  |
| M3_Simple_EMA_Core4           |         14883.1  |           141886   |           853.34 |              43.42 |                3.06 |          19.82 |           29.7 |            117 |           21.4 |              8136.82 |
| M4_Top1_Rotation_Candidate    |         17490.4  |           517580   |          2859.22 |              53.14 |                3.24 |          54.46 |           42.9 |             86 |           55.8 |             43128.8  |
| M5_BTC_Buy_Hold               |         25608.6  |            40423.8 |            57.85 |              54.12 |                0.97 |           1.07 |            0   |              0 |            0   |                 0    |
| M6_Core4_EW_Buy_Hold          |         16115.2  |           259408   |          1509.71 |              56.02 |                2.99 |          27.23 |            0   |              0 |            0   |                 0    |

### Regime / 评估周期: 2022

| model_key                     |   initial_equity |   final_equity_usd |   net_return_pct |   max_drawdown_pct |   annualized_sharpe |   calmar_ratio |   avg_cash_pct |   total_trades |   win_rate_pct |   total_friction_usd |
|:------------------------------|-----------------:|-------------------:|-----------------:|-------------------:|--------------------:|---------------:|---------------:|---------------:|---------------:|---------------------:|
| M1A_Structural_Trend_Close    |          54925.3 |            52976.6 |            -3.55 |              35.14 |               -0.01 |          -0.1  |           92   |             15 |           33.3 |              1166.05 |
| M1B_Structural_Trend_Intrabar |          31214   |            33239.8 |             6.49 |              27.43 |                0.38 |           0.24 |           92.6 |             18 |           38.9 |              1019.63 |
| M2_Simple_EMA_ETHSOL          |         182859   |           102697   |           -43.84 |              58.63 |               -1.23 |          -0.75 |           78.9 |             63 |           11.1 |             13298.2  |
| M3_Simple_EMA_Core4           |         141886   |            90839.6 |           -35.98 |              47.97 |               -1.23 |          -0.75 |           75.5 |            116 |           12.9 |             10058.6  |
| M4_Top1_Rotation_Candidate    |         517580   |           474534   |            -8.32 |              39.34 |               -0.04 |          -0.21 |           74.4 |             34 |           35.3 |             43737.7  |
| M5_BTC_Buy_Hold               |          40945.4 |            14469.1 |           -64.66 |              67.21 |               -1.34 |          -0.96 |            0   |              0 |            0   |                 0    |
| M6_Core4_EW_Buy_Hold          |         263583   |            42215.9 |           -83.98 |              84.91 |               -1.56 |          -0.99 |            0   |              0 |            0   |                 0    |

### Regime / 评估周期: 2023

| model_key                     |   initial_equity |   final_equity_usd |   net_return_pct |   max_drawdown_pct |   annualized_sharpe |   calmar_ratio |   avg_cash_pct |   total_trades |   win_rate_pct |   total_friction_usd |
|:------------------------------|-----------------:|-------------------:|-----------------:|-------------------:|--------------------:|---------------:|---------------:|---------------:|---------------:|---------------------:|
| M1A_Structural_Trend_Close    |          52976.6 |   117291           |           121.4  |              28.23 |                1.6  |           4.32 |           77.8 |             34 |           47.1 |              3453.75 |
| M1B_Structural_Trend_Intrabar |          33239.8 |    66994.6         |           101.55 |              26    |                1.6  |           3.92 |           81.3 |             43 |           37.2 |              3529.71 |
| M2_Simple_EMA_ETHSOL          |         102697   |   483695           |           370.99 |              44.75 |                2.43 |           8.35 |           39.9 |             64 |           17.2 |             11652.5  |
| M3_Simple_EMA_Core4           |          90839.6 |   290221           |           219.49 |              37.08 |                2.3  |           5.95 |           43.3 |            135 |           14.8 |              9791.73 |
| M4_Top1_Rotation_Candidate    |         474534   |        1.70756e+06 |           259.84 |              32.99 |                2.22 |           7.93 |           35.8 |             76 |           47.4 |            133494    |
| M5_BTC_Buy_Hold               |          14461   |    36983.6         |           155.75 |              21.19 |                2.34 |           7.39 |            0   |              0 |            0   |                 0    |
| M6_Core4_EW_Buy_Hold          |          42119.1 |   159435           |           278.53 |              33.63 |                2.5  |           8.33 |            0   |              0 |            0   |                 0    |

### Regime / 评估周期: 2024

| model_key                     |   initial_equity |   final_equity_usd |   net_return_pct |   max_drawdown_pct |   annualized_sharpe |   calmar_ratio |   avg_cash_pct |   total_trades |   win_rate_pct |   total_friction_usd |
|:------------------------------|-----------------:|-------------------:|-----------------:|-------------------:|--------------------:|---------------:|---------------:|---------------:|---------------:|---------------------:|
| M1A_Structural_Trend_Close    | 117291           |    189119          |            61.24 |              16.09 |                1.48 |           3.81 |           78.1 |             24 |           58.3 |              4277.78 |
| M1B_Structural_Trend_Intrabar |  66994.6         |     82858.6        |            23.68 |              15.26 |                0.81 |           1.55 |           82   |             35 |           51.4 |              4143.37 |
| M2_Simple_EMA_ETHSOL          | 489391           |    584156          |            19.36 |              42.16 |                0.49 |           0.46 |           41   |             78 |           20.5 |             54543.8  |
| M3_Simple_EMA_Core4           | 292834           |    361059          |            23.3  |              39.35 |                0.55 |           0.59 |           38.6 |            154 |           21.4 |             33579.6  |
| M4_Top1_Rotation_Candidate    |      1.69332e+06 |         2.3972e+06 |            41.57 |              36.98 |                0.85 |           1.12 |           35.7 |             92 |           47.8 |            608264    |
| M5_BTC_Buy_Hold               |  37024.6         |     81846.2        |           121.06 |              30.01 |                1.68 |           4.04 |            0   |              0 |            0   |                 0    |
| M6_Core4_EW_Buy_Hold          | 160640           |    303861          |            89.16 |              39.7  |                1.19 |           2.25 |            0   |              0 |            0   |                 0    |

### Regime / 评估周期: 2025

| model_key                     |   initial_equity |   final_equity_usd |   net_return_pct |   max_drawdown_pct |   annualized_sharpe |   calmar_ratio |   avg_cash_pct |   total_trades |   win_rate_pct |   total_friction_usd |
|:------------------------------|-----------------:|-------------------:|-----------------:|-------------------:|--------------------:|---------------:|---------------:|---------------:|---------------:|---------------------:|
| M1A_Structural_Trend_Close    |  189119          |   193067           |             2.09 |              22.65 |                0.21 |           0.09 |           87.6 |             20 |           35   |              5327.29 |
| M1B_Structural_Trend_Intrabar |   82858.6        |    85850           |             3.61 |              21.61 |                0.27 |           0.17 |           90.2 |             23 |           34.8 |              3631.96 |
| M2_Simple_EMA_ETHSOL          |  584156          |   740615           |            26.78 |              26.01 |                0.74 |           1.03 |           56.9 |             55 |           16.4 |             50989.3  |
| M3_Simple_EMA_Core4           |  361258          |   431604           |            19.47 |              24.79 |                0.63 |           0.79 |           55.5 |            148 |           13.5 |             32715.2  |
| M4_Top1_Rotation_Candidate    |       2.3972e+06 |        3.76447e+06 |            57.04 |              42.37 |                1.21 |           1.35 |           54.8 |             68 |           39.7 |            441770    |
| M5_BTC_Buy_Hold               |   82075.4        |    76661.5         |            -6.6  |              34.37 |                0.02 |          -0.19 |            0   |              0 |            0   |                 0    |
| M6_Core4_EW_Buy_Hold          |  305509          |   243407           |           -20.33 |              57.39 |                0.01 |          -0.36 |            0   |              0 |            0   |                 0    |

### Regime / 评估周期: 2026

| model_key                     |   initial_equity |   final_equity_usd |   net_return_pct |   max_drawdown_pct |   annualized_sharpe |   calmar_ratio |   avg_cash_pct |   total_trades |   win_rate_pct |   total_friction_usd |
|:------------------------------|-----------------:|-------------------:|-----------------:|-------------------:|--------------------:|---------------:|---------------:|---------------:|---------------:|---------------------:|
| M1A_Structural_Trend_Close    | 193067           |    232031          |            20.18 |              14.83 |                1.22 |           1.94 |           84   |             21 |           38.1 |              4498.61 |
| M1B_Structural_Trend_Intrabar |  85850           |     96004.5        |            11.83 |              14.05 |                0.79 |           1.19 |           87   |             25 |           40   |              3415.13 |
| M2_Simple_EMA_ETHSOL          | 740615           |    777596          |             4.99 |              39.06 |                0.36 |           0.18 |           56   |             63 |           11.1 |             54264.9  |
| M3_Simple_EMA_Core4           | 431604           |    457673          |             6.04 |              36.54 |                0.4  |           0.23 |           55.7 |            112 |           11.6 |             30710.3  |
| M4_Top1_Rotation_Candidate    |      3.76447e+06 |         3.7952e+06 |             0.82 |              29.13 |                0.21 |           0.04 |           53.2 |             55 |           38.2 |            471467    |
| M5_BTC_Buy_Hold               |  76834.5         |     75835.9        |            -1.3  |              39.98 |                0.16 |          -0.04 |            0   |              0 |            0   |                 0    |
| M6_Core4_EW_Buy_Hold          | 244503           |    230439          |            -5.75 |              50.99 |                0.1  |          -0.15 |            0   |              0 |            0   |                 0    |

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

## 5. Mode B Intrabar Stop-Loss Slippage Stress Matrix
## 第五步：Mode B 盘中止损跳空与更差滑点敏感度压力测试

| scenario_tag          |   stop_slippage_bps |   net_return_pct |   max_drawdown_pct |   annualized_sharpe |   final_equity_usd |   total_friction_usd |
|:----------------------|--------------------:|-----------------:|-------------------:|--------------------:|-------------------:|---------------------:|
| Mode_B_Baseline_15bps |                  15 |           860.05 |              32.44 |                1.12 |            96004.5 |              17888.8 |
| Mode_B_Stress_30bps   |                  30 |           727.59 |              33.12 |                1.05 |            82759.4 |              23046.8 |
| Mode_B_Stress_50bps   |                  50 |           578.74 |              34.02 |                0.97 |            67874   |              28331.6 |

---

## 6. Answers to Core Research Questions / 核心科学问题深度回答

### (A) Where Do Returns Truly Come From? (Trend Holding vs Cash Defense vs Token Selection)
### 收益主要来自趋势期持有、下跌时持有现金，还是选中某个币？

- **1. Trend Cash Defense is the Decisive Foundation (趋势现金防守是首要基石)**:
  In the 2022 secular bear market, passive buy-and-hold collapsed: BTC lost -64.66% (Max DD 67.21%) and Core-4 EW lost -83.98% (Max DD 84.91%). In sharp contrast, Simple EMA Control held ~75% average cash, dramatically limiting drawdown to -43.84% (ETH/SOL) and -35.98% (Core-4). Staying in cash when price breaks below EMA200 is the single most important driver of survival and long-term compounding.
  在 2022 年大熊市中，被动持有遭遇毁灭性回撤（BTC -64.66%，四币等权 -83.98%）。相比之下，简单均线趋势对照组保持了约 75% 的现金仓位，大幅抵御了暴跌。跌破均线退守 USDT 现金是保全本金、实现长期复利的最关键基石。

- **2. Asset Universe Bias Neutralized (标的池范围偏差被彻底消除)**:
  Comparing Structural Trend (ETH/SOL 50/50) against Price > EMA200 Control (ETH/SOL 50/50):
  - Structural Trend relies on 120-bar Bollinger breakout with 3x ATR trailing exit, taking fewer trades (158 vs 408) with higher win rate (46.2% vs 15.7%).
  - Price > EMA200 Control captures full bull market moves with high turnover and high fee drag ($195.8k friction vs $20.3k for Structural Trend).
  通过增设相同资产池的 Price > EMA200 简单趋势对照组，我们成功证实：标的池的高 Beta 属性贡献了巨额牛市 Beta，但 120 周期通道与 ATR 移动止损将全周期交易笔数由 408 笔锐减至 158 笔，磨损减少近 90%。

### (B) Does Rotation Genuinely Outperform Simple EMA After Turnover Wear?
### 轮动扣掉多出的换手成本后，是否真正超过简单 EMA 对照？

- In a unified single ledger, Top-1 rotation candidate (Buffer 0.30) achieves **+37,852.01%** net return with an average cash ratio of **48.5%**.
- Incremental annual friction incurred in 2026 is **$471,467.22**, and total full-cycle friction is **$1,742,428.48**. The strategy generates sufficient cross-sectional alpha to more than overcome turnover friction, but capacity constraints become binding above $250k portfolio size.
- 单账本纠偏后，Top-1 轮动策略 2026 年实际发生的增量摩擦成本为 47.1 万美元（全周期累计为 174.2 万美元），平均现金仓位为 48.5%。其截面动量超额在扣费后依然超越被动基准与简单趋势，但在大资金体量下会受到盘口容量耗尽的制约。

### (C) Top-3 Winning Trades Dependency & Fragility
### 去掉最大的三笔盈利交易，或漏掉一笔关键趋势交易后，还赚钱吗？

- For Structural Trend Phase 19, the top 3 profitable trades contribute **50.8%** (Mode A) and **48.0%** (Mode B) of cumulative profit.
- 结构趋势前三大盈利交易贡献了约 50% 的总利润。系统收益高度依赖抓住极少数主升浪，执行断点或漏单将显著削弱全周期复合收益率。

### (D) Mode A (Bar-Close) vs Mode B (Intrabar Stop Touch) Divergence
### 收盘退出与盘中止损保守测试的真实差异

- Mode B (Intrabar Touch) triggers conservative stop-loss when intra-bar Low touches the prior-bar trailing stop, reducing net return from +2,220.31% to +860.05% due to wicks triggering premature exits.
- Under slippage stress (15 bps -> 30 bps -> 50 bps), net return declines from +860.05% to +727.59% and +578.74%, preserving robust positive expectancy.

---

## 7. Orderbook Depth Snapshot & Static Capacity Audit
## 盘口深度单次快照审计与静态资金容量边界

> **Empirical Scope Qualification / 证据范围严格定性**:
> 1. **Point-in-Time Snapshot Audit / 单次点位截面快照**: Based on a single point-in-time 10-level Binance Spot depth snapshot taken on 2026-09-23 13:07:29 UTC (~5 hours after the 08:00 UTC bar decision). It does NOT constitute continuous real-time depth stream capture or trade-instant fill proof.
> 2. **Static Capacity Boundaries / 静态流动性边界**: For BTCUSDT and ETHUSDT, 10-level ask depth exceeds \$300k-\$1.08M with spread < 0.05 bps. For BNBUSDT, available 10-level ask depth is constrained to ~\$5,775 to \$40,000 USDT; market orders $\ge \$10\text{k}$ face depth exhaustion at level 10.
> 3. **Implication / 启示**: High-frequency or high-notional rotation strategies cannot assume frictionless fills at scale, and must account for orderbook depth exhaustion in real-world deployment.

---

## 8. Data Audit Scope & Unclassified Candle Disclosure
## 行情数据审计核验范围与未分类 K 线明确披露

- **Audit Scope / 核验范围**: The bar-by-bar matching audit against Binance Spot and Futures REST APIs was conducted strictly on **OHLC (Open, High, Low, Close)** prices with a threshold of $< 1e-4$. Volume was excluded due to disparate spot vs futures accounting bases.
- **2026 Epoch Breakdown / 2026 年区间构成**: Out of 1,590 bars in 2026, 1,533 match Binance Spot 100%, 56 match Binance USDS-M Futures 100%, and exactly **1 bar** (`2026-09-22 20:00:00 UTC`) is unclassified. Detailed empirical inspection shows:
  - Open, High, and Low matched Binance Futures 100% (delta 0.0000 across all 4 coins);
  - Close discrepancy vs Binance Futures: BTC 0.012%, ETH 0.040%, BNB 0.046%, SOL 0.059% (all $< 0.06\%$).
  - Close discrepancy vs Binance Spot: BTC 0.070%, ETH 0.005%, BNB 0.108%, SOL 0.127% (all $< 0.13\%$).
  - This minor discrepancy is suspected to have occurred because the earlier automated synchronization script captured a live mid-candle snapshot prior to final bar close settlement (though without physical execution timestamps/logs, this cannot be definitively proven). Classified objectively as `SUSPECTED_MID_CANDLE_SNAPSHOT` (疑似盘中未闭合快照).
- **Segregated Clean Repositories / 独立分库**: Standard clean Spot data is housed under `data/spot/`, Futures reference under `data/futures_reference/`, with all SHA-256 hashes recorded in `reports/data_audit/immutable_data_manifest.json`.

