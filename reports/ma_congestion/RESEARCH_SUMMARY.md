# MA Congestion Breakout & Pullback Strategy Research Report
# 均线密集突破后回踩策略全景量化研究实证报告

> **Research Discipline / 科研纪律说明**:
> 1. 所有实验在同一数据池 (Core-4: BTC, ETH, SOL, BNB)、同一回测区间 (2024-01-01 至 2026-09-23)、同一费率 (Spot 8 bps fee, 5 bps slippage, 15 bps stop slip; Perps 5 bps fee, 4 bps slippage, 12 bps stop slip) 及同一单笔 0.5% 风险头寸模型下执行。
> 2. 状态机与成交撮合严格基于已闭合 K 线计算，下根开盘以可得市价挂单撮合，包含跳空取消保护与盘内同 K 线止损极值绝对优先裁决。
> 3. 严格不穿入版本通过逐笔数学审计 $\min(\text{Low} - U) \ge 0.0$ 恒成立，断言证明 100% 交易影线绝无穿入均线密集区。

## 1. 核心对比：三种回踩确认机制直接对照 (Head-to-Head Pullback Mechanism Comparison)

对比同一基线 (15m EMA Long Spot Core-4) 下三种不同入场定义的实际表现：

- **Variant A (`STRICT_SUPPORT`)**: 严格不穿入支撑。K 线影线绝不跌入均线群 ($\text{Low} \ge U$)，触碰缓冲带 ($U \le \text{Low} \le U + 0.1 \times ATR$)，收盘站稳 $\text{Close} > U$。若 $\text{Low} < U$ 立即作废。不设强制前置突破幅度。
- **Variant B (`INTRABAND_PENETRATION`)**: 影线刺入但收盘不跌破。允许影线刺入均线密集带 ($L \le \text{Low} < U$)，但跌破 $L - 0.1 \times ATR$ 立即作废，收盘站回 $\text{Close} > U$ 确认。
- **Variant C (`LOOSE_PENETRATION_RECLAIM`)**: 旧版穿入后收回。要求前置突破幅度 $> U + 0.5 \times ATR$，回踩允许刺穿全带直至 $L - 0.1 \times ATR$，收盘重新站回 $U$。

| experiment_name                       | pullback_mode             |   total_trades |   win_rate_pct |   avg_net_r |   median_net_r |   profit_factor |   total_net_return_pct |   max_drawdown_pct |   daily_sharpe |   total_fees_usdt |   total_slippage_usdt |
|:--------------------------------------|:--------------------------|---------------:|---------------:|------------:|---------------:|----------------:|-----------------------:|-------------------:|---------------:|------------------:|----------------------:|
| v1_strict_support_15m_ema_long        | STRICT_SUPPORT            |            290 |          23.1  |      -0.744 |         -1.365 |            0.32 |                 -57.77 |              57.8  |          -3.85 |           2716.54 |               3380.07 |
| v1_intraband_penetration_15m_ema_long | INTRABAND_PENETRATION     |            308 |          21.75 |      -0.754 |         -1.385 |            0.38 |                 -57.24 |              57.24 |          -3.56 |           2947.8  |               3667.36 |
| v1_loose_reclaim_15m_ema_long         | LOOSE_PENETRATION_RECLAIM |            467 |          22.06 |      -0.767 |         -1.4   |            0.36 |                 -73.37 |              73.51 |          -4.43 |           3652.91 |               4538.94 |


## 2. 严格不穿入不变量数学审计证明 (Mathematical Audit of Non-Penetration Invariant)

- **总交易笔数 (Total Trades)**: `290` 笔
- **最小低点距上沿距离 $\min(\text{Low} - U)$**: `0.000402` USDT ($\ge 0.0$ 恒成立，证明 100% 交易影线绝无穿入均线密集区)
- **25分位数**: `0.047899` USDT | **中位数**: `0.168206` USDT | **最大值**: `69.403271` USDT
- **审计结论**: 严格支撑版中不存在任何一笔'穿入后收回'的交易，完整还原了'从上方回踩均线群未跌穿、获支撑开多'的原始假设。


## 3. 全套预先登记版本与消融实验全景表 (All Experiments & Ablations Summary)

|   total_trades |   win_rate_pct |   avg_net_r |   median_net_r |   profit_factor |   total_net_return_pct |   max_drawdown_pct |   daily_sharpe |   avg_hours_held |   total_fees_usdt |   total_slippage_usdt |   final_equity | experiment_name                       | pullback_mode             | interval   | ma_type   | direction   | market_type   |
|---------------:|---------------:|------------:|---------------:|----------------:|-----------------------:|-------------------:|---------------:|-----------------:|------------------:|----------------------:|---------------:|:--------------------------------------|:--------------------------|:-----------|:----------|:------------|:--------------|
|            290 |          23.1  |      -0.744 |         -1.365 |            0.32 |                 -57.77 |              57.8  |          -3.85 |             2.01 |           2716.54 |               3380.07 |        4222.76 | v1_strict_support_15m_ema_long        | STRICT_SUPPORT            | 15m        | EMA       | LONG        | spot          |
|            308 |          21.75 |      -0.754 |         -1.385 |            0.38 |                 -57.24 |              57.24 |          -3.56 |             1.82 |           2947.8  |               3667.36 |        4276.11 | v1_intraband_penetration_15m_ema_long | INTRABAND_PENETRATION     | 15m        | EMA       | LONG        | spot          |
|            467 |          22.06 |      -0.767 |         -1.4   |            0.36 |                 -73.37 |              73.51 |          -4.43 |             1.89 |           3652.91 |               4538.94 |        2663.16 | v1_loose_reclaim_15m_ema_long         | LOOSE_PENETRATION_RECLAIM | 15m        | EMA       | LONG        | spot          |
|             69 |          21.74 |      -0.818 |         -1.351 |            0.3  |                 -19.79 |              20.46 |          -2.17 |             2.36 |            831.56 |               1028.13 |        8020.78 | v2_strict_15m_sma_long                | STRICT_SUPPORT            | 15m        | SMA       | LONG        | spot          |
|            322 |          22.67 |      -0.697 |         -1.256 |            0.32 |                 -67.18 |              67.28 |          -4.32 |             1.9  |           2223.69 |               3549.64 |        3282.23 | v1_strict_15m_ema_short_perps         | STRICT_SUPPORT            | 15m        | EMA       | SHORT       | futures       |
|            457 |          18.38 |      -0.966 |         -1.554 |            0.26 |                 -77.8  |              77.8  |          -5.82 |             2.42 |           3579.85 |               4472.71 |        2220.36 | v3_strict_5m_ema_long                 | STRICT_SUPPORT            | 5m         | EMA       | LONG        | spot          |
|            140 |          23.57 |      -0.739 |         -1.426 |            0.38 |                 -30.08 |              32.32 |          -2.5  |             2.32 |           1782.76 |               2227.83 |        6992.14 | v4_strict_5m_sma_long                 | STRICT_SUPPORT            | 5m         | SMA       | LONG        | spot          |
|            643 |          21.77 |      -0.778 |         -1.46  |            0.34 |                 -91.25 |              91.09 |          -6    |             1.88 |           3683.84 |               5896.33 |         874.59 | v3_strict_5m_ema_short_perps          | STRICT_SUPPORT            | 5m         | EMA       | SHORT       | futures       |
|           8488 |          20.16 |      -0.754 |         -1.252 |            0.35 |                -100    |             100    |         -15.51 |             1.92 |           4083.47 |               5054.05 |           0    | ablation_simple_trend_no_congestion   | STRICT_SUPPORT            | 15m        | EMA       | LONG        | spot          |
|           1877 |          29.94 |      -0.535 |         -1.119 |            0.43 |                 -98.55 |              98.57 |          -6.81 |             3.18 |           4896.22 |               5890.84 |         144.7  | ablation_breakout_only_no_pullback    | STRICT_SUPPORT            | 15m        | EMA       | LONG        | spot          |
|            289 |          34.95 |      -0.628 |         -1.494 |            0.48 |                 -50.05 |              50.08 |          -3.48 |             2    |           3062.02 |               3125.05 |        4995.49 | ablation_fixed_2r_exit                | STRICT_SUPPORT            | 15m        | EMA       | LONG        | spot          |
|            145 |          20.69 |      -1.05  |         -1.54  |            0.16 |                 -53.53 |              53.53 |          -4.41 |             2.47 |           2345.58 |               2910.88 |        4647.1  | stress_cost_2x_friction               | STRICT_SUPPORT            | 15m        | EMA       | LONG        | spot          |
|             32 |          12.5  |      -1.194 |         -1.788 |            0.11 |                 -17.49 |              17.49 |          -2.39 |             3.08 |            739.6  |                899.67 |        8251.07 | stress_cost_4x_friction               | STRICT_SUPPORT            | 15m        | EMA       | LONG        | spot          |


## 4. 严格支撑版本 (Strict Support V1) 逐年表现 (Annual Breakdown)

|   year |   trades |   win_rate |   avg_r |   net_pnl |   friction |
|-------:|---------:|-----------:|--------:|----------:|-----------:|
|   2024 |      126 |       21.4 |  -0.833 |  -3425.46 |    3303.75 |
|   2025 |       93 |       26.9 |  -0.612 |  -1299.17 |    1713.52 |
|   2026 |       71 |       21.1 |  -0.757 |  -1052.48 |    1079.34 |


## 5. 严格支撑版本 (Strict Support V1) 单币表现 (Asset Breakdown)

| symbol   |   trades |   win_rate |   avg_r |   net_pnl |   friction |
|:---------|---------:|-----------:|--------:|----------:|-----------:|
| BNBUSDT  |       84 |       22.6 |  -0.736 |  -1651.55 |    1768.49 |
| BTCUSDT  |       53 |       26.4 |  -0.459 |   -717.17 |    1271.58 |
| ETHUSDT  |       76 |       19.7 |  -1.005 |  -1954.84 |    1583.07 |
| SOLUSDT  |       77 |       24.7 |  -0.69  |  -1453.55 |    1473.46 |


## 6. 量化实证核心发现与科学裁决 (Quantitative Findings & Scientific Verdict)

### 发现 1：严格不穿入 (Strict Support) 显著减少了伪信号磨损，但数学期望仍为负
- 相较于旧版宽松穿入收回规则 (467 笔交易，净收益 -73.37%，摩擦成本 $8,191 USDT)，严格支撑规则将交易频次压缩至 290 笔 (减少 37.9%)，净亏损收窄至 -57.77% (摩擦成本 $6,096 USDT)。
- 但其核心胜率仅为 **23.10%**，平均净 R 乘数为 **-0.744 R**，盈亏比仅为 **0.32**。
- 这在统计上证明：在加密货币的高噪音日内 15m/5m 级别，**'均线密集突破后回踩获得支撑' 并未展现出独立的统计正期望**。

### 发现 2：刺入带内 (Intraband) 与不穿入 (Strict) 表现高度接近
- 刺入带内版 (308 笔，胜率 21.75%，净收益 -57.24%) 与严格不穿入版 (290 笔，胜率 23.10%，净收益 -57.77%) 净值曲线几乎重合。
- 这说明限制影线穿入均线密集带只能滤除少量尾部毛刺，无法改变形态本身在加密高频市场中高假突破率的本质。

### 发现 3：均线形态过滤器的价值 vs 交易摩擦
- **消融 1 (纯趋势无密集)**: 产生 8,488 笔交易，在高频摩擦下本金被 100% 磨损归零 (-100.0%)。均线密集过滤器的确有效过滤掉了 96.5% 的噪音。
- **消融 2 (突破即开仓，不等待回踩)**: 胜率升至 29.94%，但由于缺少回踩带来的紧凑止损点，止损幅度被放大，导致全周期仍亏损 -98.55%。
- **消融 3 (固定 2R 止盈)**: 胜率提升至 34.95%，净收益 -50.05%，优于移动追踪止损。表明在低胜率形态中，被动移动止损过早被杂波触发，固定止盈反而更有利于锁定微弱反弹。

### 发现 4：做空镜像与 5 分钟级别全部失效
- 15m 合约做空版本 (322 笔交易，考虑 8h 资金费率与清算): 收益 -67.18%，胜率 22.67%，Avg R -0.697。
- 5m 高频级别: 交易频率激增，5m EMA 多头亏损 -77.80%，5m EMA 空头亏损 -91.25%。证实更低周期的噪音与手续费双重磨损更为致命。