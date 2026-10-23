> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 长趋势简单历史筛选结果（v1r3）

## 研究状态与边界

本报告只描述已冻结的 2021-01-01 至 2026-01-01 历史窗口；该 2021–2025 历史此前已在 `trend_risk30_20261018_v1` 与 `tradingview_fixed_diagnostic_20261018_v1` 中暴露，**不是样本外数据**。`BB experiment_overview_results_20261009` 的微执行损失证据只涉及相关子时期，不能表述为覆盖完整五年，也不能据此验证或否定本屏幕的长趋势机制。三条规则是固定候选筛选，不是优化后的收益预测，不构成有效性、未来表现或交易准备度结论。三份九门报告的结论均为 `UNVERIFIED`。根级独立运行审计在生成本报告时为 `PASS`。

仓位口径是每个独立账户总目标毛敞口为 NAV 的 20%，不是每币 20%；每个活跃合资格币分配 `20% / N_eligible`，空闲币槽位留现金，不重新分配。EMA200 使用 4 小时线的 SMA-seeded EMA200，约 33.3 天；它不是日线 EMA200。Donchian 规则为：完成的 H4 收盘价高于此前 120 根已完成 H4 K 线的最高价时转为做多，低于此前 60 根已完成 H4 K 线的最低价时转为现金；当前 K 线不计入阈值，等于阈值时保持原状态。每个账户从 10,000 USDT 开始。筛选涵盖 3 个候选 × 5 个固定币集 × 3 组双边费用/滑点 × 2 个入场延迟，共 90 个候选案例；另有 60 个永续基准账户案例。每个候选主币集 BTC/ETH/SOL、无 SOL 集 BTC/ETH，以及单币 BTC、ETH、SOL 均单独报告。多币钱包的单币 PnL 是该共享账户的贡献分解，不是该币独立账户的净值曲线。

回放状态 `COMPLETED_EXPOSED_HISTORY_SCREEN_UNVERIFIED`，run id `20261019T001008382948Z`。已保存回放哈希清单未改写，见 `reproducibility.json`。Saved-reference EMA 长仓/CASH 六格差异状态为 `PASS_ALL_SIX`；它仅是实现核对，若差异则需复核，不作为策略筛选或调参依据。全工作区测试收据：status=SCOPED_TESTS_PASS_WORKSPACE_NOT_ALL_GREEN；exit_code=1；passed=4705；failed=9；skipped=1；known historical=7；preserved predecessor=1；concurrency snapshot raw failure=1；quiet targeted recheck=1 passed after writers ended (9.93s; log 5f80374e031eb3d426975adbafe309981aeaf795d8da8926cb104156f038e5fa)；unexpected failure nodes=0；focused v1r3=25 passed in 0.77s；本报告不会把有历史失败的完整测试套件写成全绿。

## 预声明筛选结果

| 候选机制 | 预声明历史筛选 | 失败项数 | 缺失比较数 | 验证状态 |
|---|---|---|---|---|
| EMA200_H4_LONG_CASH | PASSES_SIMPLE_EXPOSED_HISTORY_SCREEN | 0 | 0 | UNVERIFIED |
| DONCHIAN120_60_H4_LONG_CASH | PASSES_SIMPLE_EXPOSED_HISTORY_SCREEN | 0 | 0 | UNVERIFIED |
| EMA200_H4_LONG_SHORT | FAIL | 18 | 0 | UNVERIFIED |

预声明筛选完整条件为：主 BTC/ETH/SOL 与无 SOL BTC/ETH 钱包各自全部 6 个成本/延迟案例完整、净收益为正、小时观测 MDD 严格小于 30%；观测状态的 ±40% 方向性解析冲击加严重退出成本后回撤严格小于 30%；每个情景至少 20 个闭合方向段；三个单币账户中至少两个在全部六格均为正；两个多币账户 stress 与 severe 成本、两种延迟下 Calmar 均超过完整 PERP_CONSTANT_LONG_REBALANCED20。EMA 多空还须在两个多币账户全部六格的净收益和 Calmar 均严格高于 EMA 长/CASH，且 MDD 不高于它。筛选不设最低 CAGR。任何研究风控停止的未完整路径均不能排名，缺失完整基准比较为证据不足。

## 多币钱包六情景明细

以下表格按主币集和无 SOL 钱包分别列出每个固定候选的六个成本/延迟格。完整 150 案例指标见 `case_metrics_150.csv`。

### EMA200_H4_LONG_CASH — BTCETHSOL

| 成本 | 延迟 | 账户状态 | 净收益 | CAGR | 小时MDD | 解析冲击DD | 闭合符号段 | 最大毛敞口/NAV |
|---|---|---|---|---|---|---|---|---|
| base | 0h | COMPLETE | 95.22% | 14.32% | -12.26% | -19.09% | 476 | 0.231 |
| base | 1h | COMPLETE | 102.16% | 15.12% | -11.96% | -18.80% | 476 | 0.231 |
| stress | 0h | COMPLETE | 81.33% | 12.64% | -13.55% | -20.29% | 476 | 0.231 |
| stress | 1h | COMPLETE | 87.77% | 13.43% | -13.26% | -20.00% | 476 | 0.231 |
| severe | 0h | COMPLETE | 62.31% | 10.17% | -15.45% | -22.06% | 476 | 0.231 |
| severe | 1h | COMPLETE | 68.09% | 10.95% | -15.16% | -21.78% | 476 | 0.231 |
### EMA200_H4_LONG_CASH — BTCETH

| 成本 | 延迟 | 账户状态 | 净收益 | CAGR | 小时MDD | 解析冲击DD | 闭合符号段 | 最大毛敞口/NAV |
|---|---|---|---|---|---|---|---|---|
| base | 0h | COMPLETE | 44.53% | 7.64% | -8.51% | -15.74% | 298 | 0.220 |
| base | 1h | COMPLETE | 47.69% | 8.11% | -8.14% | -15.41% | 298 | 0.221 |
| stress | 0h | COMPLETE | 35.14% | 6.21% | -9.68% | -16.83% | 298 | 0.220 |
| stress | 1h | COMPLETE | 38.10% | 6.67% | -9.32% | -16.51% | 298 | 0.221 |
| severe | 0h | COMPLETE | 22.19% | 4.09% | -11.42% | -18.44% | 298 | 0.220 |
| severe | 1h | COMPLETE | 24.87% | 4.54% | -11.06% | -18.12% | 298 | 0.221 |
### DONCHIAN120_60_H4_LONG_CASH — BTCETHSOL

| 成本 | 延迟 | 账户状态 | 净收益 | CAGR | 小时MDD | 解析冲击DD | 闭合符号段 | 最大毛敞口/NAV |
|---|---|---|---|---|---|---|---|---|
| base | 0h | COMPLETE | 79.99% | 12.48% | -8.56% | -16.02% | 85 | 0.231 |
| base | 1h | COMPLETE | 77.63% | 12.18% | -9.08% | -16.57% | 85 | 0.231 |
| stress | 0h | COMPLETE | 76.26% | 12.00% | -8.79% | -16.23% | 85 | 0.231 |
| stress | 1h | COMPLETE | 73.94% | 11.71% | -9.31% | -16.78% | 85 | 0.231 |
| severe | 0h | COMPLETE | 70.80% | 11.30% | -9.32% | -16.55% | 85 | 0.231 |
| severe | 1h | COMPLETE | 68.55% | 11.01% | -9.90% | -17.10% | 85 | 0.231 |
### DONCHIAN120_60_H4_LONG_CASH — BTCETH

| 成本 | 延迟 | 账户状态 | 净收益 | CAGR | 小时MDD | 解析冲击DD | 闭合符号段 | 最大毛敞口/NAV |
|---|---|---|---|---|---|---|---|---|
| base | 0h | COMPLETE | 27.55% | 4.99% | -9.14% | -16.40% | 59 | 0.216 |
| base | 1h | COMPLETE | 26.34% | 4.79% | -9.22% | -16.47% | 59 | 0.216 |
| stress | 0h | COMPLETE | 25.21% | 4.60% | -9.37% | -16.61% | 59 | 0.216 |
| stress | 1h | COMPLETE | 24.02% | 4.40% | -9.46% | -16.68% | 59 | 0.216 |
| severe | 0h | COMPLETE | 21.78% | 4.02% | -9.72% | -16.92% | 59 | 0.216 |
| severe | 1h | COMPLETE | 20.62% | 3.82% | -9.81% | -16.99% | 59 | 0.216 |
### EMA200_H4_LONG_SHORT — BTCETHSOL

| 成本 | 延迟 | 账户状态 | 净收益 | CAGR | 小时MDD | 解析冲击DD | 闭合符号段 | 最大毛敞口/NAV |
|---|---|---|---|---|---|---|---|---|
| base | 0h | COMPLETE | 75.18% | 11.87% | -17.93% | -24.84% | 953 | 0.238 |
| base | 1h | COMPLETE | 91.59% | 13.89% | -17.48% | -24.43% | 953 | 0.238 |
| stress | 0h | COMPLETE | 50.47% | 8.52% | -20.84% | -27.51% | 953 | 0.238 |
| stress | 1h | COMPLETE | 64.58% | 10.48% | -20.41% | -27.11% | 953 | 0.238 |
| severe | 0h | COMPLETE | 19.78% | 3.68% | -25.20% | -31.34% | 953 | 0.238 |
| severe | 1h | COMPLETE | 31.03% | 5.55% | -24.62% | -30.96% | 953 | 0.238 |
### EMA200_H4_LONG_SHORT — BTCETH

| 成本 | 延迟 | 账户状态 | 净收益 | CAGR | 小时MDD | 解析冲击DD | 闭合符号段 | 最大毛敞口/NAV |
|---|---|---|---|---|---|---|---|---|
| base | 0h | COMPLETE | 43.24% | 7.45% | -11.81% | -19.03% | 596 | 0.225 |
| base | 1h | COMPLETE | 51.80% | 8.71% | -10.65% | -18.04% | 596 | 0.226 |
| stress | 0h | COMPLETE | 24.64% | 4.50% | -12.94% | -20.01% | 596 | 0.225 |
| stress | 1h | COMPLETE | 32.09% | 5.73% | -12.59% | -19.80% | 596 | 0.226 |
| severe | 0h | COMPLETE | 1.16% | 0.23% | -19.91% | -26.33% | 596 | 0.225 |
| severe | 1h | COMPLETE | 7.22% | 1.40% | -19.08% | -25.57% | 596 | 0.226 |

### Severe 成本、0 小时延迟下的年度表现

下表固定展示最严成本情景的延迟 0 小时结果，年度列覆盖完整 2021–2025；此切片便于阅读，不替代上面的全部六格。

| 候选 | 币集 | 五年净收益 | 2021 | 2022 | 2023 | 2024 | 2025 | 最差年 | 最近年2025 |
|---|---|---|---|---|---|---|---|---|---|
| EMA200_H4_LONG_CASH | BTCETHSOL | 62.31% | 44.51% | -9.73% | 19.46% | 3.20% | 0.92% | 2022 (-9.73%) | 0.92% |
| EMA200_H4_LONG_CASH | BTCETH | 22.19% | 14.39% | -6.19% | 9.13% | 4.29% | 0.06% | 2022 (-6.19%) | 0.06% |
| DONCHIAN120_60_H4_LONG_CASH | BTCETHSOL | 70.80% | 49.38% | -6.14% | 16.39% | 4.85% | -0.18% | 2022 (-6.14%) | -0.18% |
| DONCHIAN120_60_H4_LONG_CASH | BTCETH | 21.78% | 16.53% | -3.20% | 5.82% | 3.96% | -1.86% | 2022 (-3.20%) | -1.86% |
| EMA200_H4_LONG_SHORT | BTCETHSOL | 19.78% | 21.43% | -0.76% | 7.10% | -7.81% | 0.66% | 2024 (-7.81%) | 0.66% |
| EMA200_H4_LONG_SHORT | BTCETH | 1.16% | 3.74% | 2.00% | 1.57% | -4.26% | -1.69% | 2024 (-4.26%) | -1.69% |

### Severe 成本下的完整基准比较

只对完整全窗账户展示收益、CAGR、小时 MDD 和 Calmar；因研究 gross/NAV 风控条件停止的未完整账户均显示 N/A，绝不对该未完整路径排名。主 BTC/ETH/SOL 买入持有基准在 2021 年触发该研究上限时 NAV 仍为正；这不是破产、交易所保证金追缴或清算，也不代表发生亏损。

| 候选 | 币集 | 候选收益 | 候选CAGR | 候选MDD | 候选Calmar | 常数多头收益 | 常数多头CAGR | 常数多头MDD | 常数多头Calmar | 买持收益 | 买持CAGR | 买持MDD | 买持Calmar |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EMA200_H4_LONG_CASH | BTCETHSOL | 62.31% | 10.17% | -15.45% | 0.6583 | 88.87% | 13.56% | -29.80% | 0.4551 | N/A (research risk stop; incomplete) | N/A (research risk stop; incomplete) | N/A (research risk stop; incomplete) | N/A (research risk stop; incomplete) |
| EMA200_H4_LONG_CASH | BTCETH | 22.19% | 4.09% | -11.42% | 0.3582 | 30.36% | 5.45% | -24.99% | 0.2179 | 17.15% | 3.22% | -47.58% | 0.0676 |
| DONCHIAN120_60_H4_LONG_CASH | BTCETHSOL | 70.80% | 11.30% | -9.32% | 1.2126 | 88.87% | 13.56% | -29.80% | 0.4551 | N/A (research risk stop; incomplete) | N/A (research risk stop; incomplete) | N/A (research risk stop; incomplete) | N/A (research risk stop; incomplete) |
| DONCHIAN120_60_H4_LONG_CASH | BTCETH | 21.78% | 4.02% | -9.72% | 0.4134 | 30.36% | 5.45% | -24.99% | 0.2179 | 17.15% | 3.22% | -47.58% | 0.0676 |
| EMA200_H4_LONG_SHORT | BTCETHSOL | 19.78% | 3.68% | -25.20% | 0.1459 | 88.87% | 13.56% | -29.80% | 0.4551 | N/A (research risk stop; incomplete) | N/A (research risk stop; incomplete) | N/A (research risk stop; incomplete) | N/A (research risk stop; incomplete) |
| EMA200_H4_LONG_SHORT | BTCETH | 1.16% | 0.23% | -19.91% | 0.0116 | 30.36% | 5.45% | -24.99% | 0.2179 | 17.15% | 3.22% | -47.58% | 0.0676 |

主 BTC/ETH/SOL 的固定数量 PERP_BUY_HOLD_INITIAL20 在 2021 因研究账户 gross/NAV >= 1 规则停止时 NAV 仍为 100721.00 USDT。这是研究风控的未完整路径，不是破产、交易所保证金/清算事件，也不必然代表亏损；全窗收益记为 N/A，绝不对停止前缀排名。

### Severe 成本收益桥（同为 delay 0h）

| 候选 | 币集 | 价格及成交价差PnL | 资金费PnL | 费用 | 滑点 | 终值USDT | 净收益 | 固定情景 |
|---|---|---|---|---|---|---|---|---|
| EMA200_H4_LONG_CASH | BTCETHSOL | 11373.43 | -1370.10 | 1077.74 | 2694.42 | 16231.17 | 62.31% | severe 10/25bp per side; delay 0h |
| EMA200_H4_LONG_CASH | BTCETH | 6088.61 | -1162.25 | 773.55 | 1933.92 | 12218.88 | 22.19% | severe 10/25bp per side; delay 0h |
| DONCHIAN120_60_H4_LONG_CASH | BTCETHSOL | 9377.13 | -1194.24 | 315.09 | 787.79 | 17080.01 | 70.80% | severe 10/25bp per side; delay 0h |
| DONCHIAN120_60_H4_LONG_CASH | BTCETH | 3889.62 | -947.24 | 218.48 | 546.21 | 12177.69 | 21.78% | severe 10/25bp per side; delay 0h |
| EMA200_H4_LONG_SHORT | BTCETHSOL | 9755.05 | -1339.64 | 1839.36 | 4598.46 | 11977.60 | 19.78% | severe 10/25bp per side; delay 0h |
| EMA200_H4_LONG_SHORT | BTCETH | 6025.73 | -848.94 | 1445.93 | 3614.85 | 10116.02 | 1.16% | severe 10/25bp per side; delay 0h |

## 单币广度、年度、月度与集中度

单币 BTC、ETH、SOL 的五年净收益、CAGR、MDD、单币年度/月度收益与完整性列在 `case_metrics_150.csv`、`annual_returns_and_pnl.csv`、`monthly_returns_and_pnl.csv`。`annual_case_summary.csv` 对每个完整案例列出最低年度美元 NAV PnL、最差年度收益和最近完整年度 2025；研究风控停止的未完整账户缺少年度端点时保持为空。年度总净 PnL 使用每个日历年度 NAV 终点减起点；完整账户的年度净损益占全窗净损益比例也在年度 CSV 中；单币年度贡献按引擎保存的该年每币净 PnL 份额拆分，见 `annual_coin_profit_concentration.csv`。月度美元损益同样按月末 NAV 减月初 NAV 计算。该年度/月份是描述性暴露历史，不是可交易过滤信号。

六情景 BTC/ETH/SOL 钱包 SOL 净 PnL 贡献：

| 候选 | 成本 | 延迟 | SOL净PnL USDT | SOL净贡献比例 |
|---|---|---|---|---|
| EMA200_H4_LONG_CASH | base | 0h | 5899.72 | 61.96% |
| EMA200_H4_LONG_CASH | base | 1h | 6319.01 | 61.86% |
| EMA200_H4_LONG_CASH | stress | 0h | 5324.71 | 65.47% |
| EMA200_H4_LONG_CASH | stress | 1h | 5715.39 | 65.12% |
| EMA200_H4_LONG_CASH | severe | 0h | 4533.63 | 72.76% |
| EMA200_H4_LONG_CASH | severe | 1h | 4884.86 | 71.74% |
| DONCHIAN120_60_H4_LONG_CASH | base | 0h | 5828.87 | 72.87% |
| DONCHIAN120_60_H4_LONG_CASH | base | 1h | 5689.71 | 73.29% |
| DONCHIAN120_60_H4_LONG_CASH | stress | 0h | 5659.77 | 74.22% |
| DONCHIAN120_60_H4_LONG_CASH | stress | 1h | 5522.87 | 74.69% |
| DONCHIAN120_60_H4_LONG_CASH | severe | 0h | 5411.96 | 76.44% |
| DONCHIAN120_60_H4_LONG_CASH | severe | 1h | 5278.37 | 77.00% |
| EMA200_H4_LONG_SHORT | base | 0h | 4137.68 | 55.04% |
| EMA200_H4_LONG_SHORT | base | 1h | 5063.70 | 55.29% |
| EMA200_H4_LONG_SHORT | stress | 0h | 3148.02 | 62.38% |
| EMA200_H4_LONG_SHORT | stress | 1h | 3948.31 | 61.14% |
| EMA200_H4_LONG_SHORT | severe | 0h | 1912.15 | 96.69% |
| EMA200_H4_LONG_SHORT | severe | 1h | 2554.06 | 82.32% |

年收益最差值、2025 最近年度结果和全部逐年贡献保存在年度 CSV；各账户最差月、最差年字段保存在 150 案例指标 CSV。不同资金费、成本和延迟案例均保留，不以单一有利情景替代完整矩阵。

## 收益桥、成交与基准

`case_metrics_150.csv` 同列保存资金费 PnL、价格及成交价差 PnL、费用、滑点、最大毛敞口/NAV、时间加权毛敞口和账面现金比例。源 H1 mark OHLC 存在，但回放在已完成 H1 收盘/事件点估值，没有重建每个小时内 mark 相对 fill 的路径，也没有据此建模维持保证金或清算。小时观测 MDD 按保存的估值点计算，可能漏掉小时内不利变动。资金费使用原生结算事件和当时最近可用 genuine mark proxy。实际盘口、真实成交偏差、容量和交易所保证金仍未知；MAE/MFE 因缺少逐笔因果的小时内路径重建而为 N/A。空头账面 cash/NAV 可超过 100%，该比例是现金记账比率，不代表可用抵押品。

闭合方向段按仓位方向从开仓至平仓统计，反向时旧方向结束并产生新方向段；它不等于下单/成交次数。`case_metrics_150.csv` 分列闭合多/空段数与已执行 fill 行数；每次非零实际执行 fill 记一行，终端平仓也算一次。分币全期净 PnL 及资金费/价格/费/滑点分解见 `per_coin_net_pnl.csv`。规则型 regime 行按区间起始时已知的 H4 EMA200 比值分类，BTC 是多币组合分类器、单币用自身分类器；分类 PnL、小时数和描述性链式收益见 `descriptive_regime_attribution.csv`，**不是经过未来筛选的策略**。

基准为零收益现金、同一 H4 决策与 20% 目标的 PERP_CONSTANT_LONG_REBALANCED20，以及初始 20% 固定数量 PERP_BUY_HOLD_INITIAL20。买入持有数量在评分窗口首个 H4 完成决策时、按共同已知 NAV 与 H4 收盘价冻结，延迟仅改变首次可成交 H1 open；未来开盘跳空可使实际成交名义金额偏离 20%。所有 90 个候选与三类基准的收益、CAGR、Calmar 与 MDD 差异见 `benchmark_deltas.csv`。只比较完整全窗账户；被风控停止的 buy-hold 或其他基准保留为 `MISSING_OR_INVALID_PREFIX_NOT_RANKABLE`，不排名。现金基准是分析值，没有收益数据行。

## 现货基准未运行

30 个现货槽位全部 `NOT_RUN`，详见 `spot_slots_not_run.csv`。原始本地 PIT 4h ZIP 的内容审计发现 BTC/ETH/SOL 各有 5 个 close identity 例外，共 15 根短 bar，且与原始 anomaly ledger 的 `SHORT_BAR` 行逐一吻合；其 `cause_verified=false`，不能据此推断停牌或数据损坏。异常行保持原生时间戳，不修正、不补齐，也不对前缀排名。spot/perp 网格不同，因此即使未来有合格现货比较也不应解释为纯 alpha 或资金费贡献。

## 成本、风险与限制

每执行方向按每边计费/滑点：base 5/5 bp、stress 5/15 bp、severe 10/25 bp；费用按不利成交名义金额计一次，滑点不重复计入费用。线性永续账户在 NAV 非正或 gross/NAV 至少为 1 时停止，精确保留研究风控停止触发时的 NAV、现金、仓位、mark、regime 和停止相位，不强制平仓。该研究风控停止不等于交易所破产、保证金追缴或清算；停止账户的整个窗口收益不可排名。空头下 cash/NAV 可能超过 100%，只表示账面现金余额，不代表 free collateral。40% 冲击是按持仓方向作用于观测状态的分析压力情形；不是观察 bar、清算路径或未来损失上限。

## 可复现信息

- 精确批准锁 SHA256：`9b03671d089660f20b8b04580a0480e306d6f596d7c10b107aae3dbd283af797`；完整源/代码/配置哈希见 `reproducibility.json`。
- Run manifest SHA256：`db5a2d26f1b0d8dda9668d325e7c0edc1e397ffb5d5e30d60615b25e3a7addb7`；account results SHA256：`afcdaabb1253ff72443ad17bad579d30a9b300ba75f599073f0ce7ee2d84a0f5`。
- 根级独立运行审计状态：`PASS`；不得在收到根级最终审计前标为通过。
- 全工作区测试收据：<SOURCE_ROOT:crypto-leverage>/reports/strategy_validation/longtrend_simple_screen_20261019_v1/implementation_v1r3/review/full_suite_receipt.json；保留的历史失败仍须如实披露。
- 六个成本/延迟格是同一固定窗口的压力敏感性，任何正结果仍仅是已暴露历史筛选。

## NAV 与回撤图

Saved native NAV event points and observed drawdown (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/longtrend_simple_screen_20261019_v1/implementation_v1r3/reporting_v1/nav_drawdown_main_btcethsol_severe_d0.png`)

图中只绘制完整账户和现金分析基准的原生保存 NAV 点，不连线或补造中间 candles；不完整案例不绘制，缺失的路径表示 gap，列表见 `reporting_manifest.json`。资本起点为 10,000 USDT；目标总毛敞口为 NAV 的 20%；窗口此前已暴露；候选与常数多头采用 severe 每边 10 bp 费用、25 bp 滑点；-30% 仅为参考线，不是未来最大损失或保证。

**结论：** 本报告只给出冻结候选的历史筛选记录。三条候选策略均保持 `UNVERIFIED`，没有 OOS 证据；实际执行成本、容量、保证金/清算和前瞻观察仍未验证。无策略推荐、下单许可或未来收益承诺。
