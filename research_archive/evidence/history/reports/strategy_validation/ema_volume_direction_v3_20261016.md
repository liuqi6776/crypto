> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 一小时三均线与成交量活动预测研究

**结论：活动与冷却目标在已暴露历史上具有预测信息，但本次三均线与活动预测组合没有形成可盈利的交易规则。四组规则在 2025 年的基础与高滑点情景全部亏损，预先冻结的继续研究筛选条件失败。结果标记为 EXPLORATORY，不能称为有效策略或可交易方案。**

本研究落实用户提出的一小时 EMA7、20、99、三个周期作为超参数、交叉后方向状态、横盘阈值，以及成交量活动预测辅助入场。视频内容未能完整核实，因此本研究是上述明确规则的独立检验，不是视频系统复现。

## 研究身份与预注册

| 项目 | 本次定义 |
| --- | --- |
| 版本 | core4_ema_volume_direction_v3；共享平台 v6 入口，旧 v1/v2 模型与结果不变 |
| 市场 | Binance USDⓈ-M 永续合约；BTCUSDT、ETHUSDT、SOLUSDT、BNBUSDT；1 小时 |
| 研究者与日期 | GPT-6 Luna high 实现，Codex 独立审查与复核；2026-10-16 |
| 原始窗口 | UTC 2020-10-01, 2026-01-01)，每币 46,032 根连续小时 K 线；2021 年以前仅预热 |
| 预测评估 | 2023、2024、2025 年；每年使用前一年选择 EMA，活动模型使用 2021 年至评估年前的成熟标签训练 |
| 收益诊断 | UTC [2025-01-01, 2026-01-01)；共享资金费/标记价格适配器只支持此固定窗口 |
| 历史暴露 | 所有窗口均为 EXPOSED/REUSED。既往 EMA、成交量 v1/v2 研究已使用这些历史；无未触碰 OOS |
| 协议 | [冻结协议 (`provenance:nonincluded/crypto-leverage/docs/EMA_VOLUME_DIRECTION_V3_PROTOCOL_20261016.md`)、时钟第一补充 (`provenance:nonincluded/crypto-leverage/docs/EMA_VOLUME_DIRECTION_V3_CLOCK_ADDENDUM_20261016.md`)、最终时钟修复 (`provenance:nonincluded/crypto-leverage/docs/EMA_VOLUME_DIRECTION_V3_CLOCK_REPAIR_20261016.md`) |
| 代码与数据身份 | 完整代码、协议、注册表、输入 SHA256 和依赖版本 (`provenance:nonincluded/crypto-leverage/reports/research_platform_v6/runs/ema_volume_direction_v3_20261016_clock_repaired/preregistration.json`) |
| 配置 SHA256 | 30be7ca1be7119c4cfebd969a441a97a1d0d86a0549c7fe540f9cf4c7ec6d894 |
| 最终结果清单 SHA256 | 7dfd11e8cda9cb27935a6494644b48d8a8f3422546605ae2f1c1e57a9beeb973 |

## 三条均线怎样定义方向和平走

三条线精确同时相等不是入场条件。这里把“交会”操作化为严格多头/空头排列的形成或变化；另行记录三对均线的交叉、排列变化和最终状态变化。这些是当时可观察的信号，不是已知的未来价格拐点。

EMA 使用前 n 根收盘的算术平均初始化，随后按 α=2/(n+1) 递推。ATR14 使用 14 根真实波幅的算术平均。定义中线六小时归一化斜率：`g = (EMA_middle(t) − EMA_middle(t−6)) / ATR14(t)`。

| 状态 | 判定 |
| --- | --- |
| 上涨 +1 | 快线 > 中线 > 慢线，并且 g > θ |
| 下跌 −1 | 快线 < 中线 < 慢线，并且 g < −θ |
| 中性/过渡 0 | 其余情况，包括斜率处于阈值内、均线混合排列或边界相等 |

中性状态只表示当前指标结构弱或混合，不能保证未来价格横盘。未来方向标签是未来 24 小时收盘对数收益相对于当前 `ATR14/close` 的上、中、下分类，也不代表这 24 小时持续单边。未使用“未来下一次交叉”来定义任何决策特征。

候选快线 {5,7,10}、中线 {15,20,30}、慢线 {60,99,150}、θ {0,0.25,0.5}，共 81 组。固定对照为 7/20/99、θ=0.25。每年仅按前一年三类平均召回率选择，合并四币选择一组；不用评估期收益选参。平分先取与固定对照距离最近者，再按字典序。三个年度共保存 243 个评分。

| 评估年 | 用于选参的年份 | 快/中/慢 | θ |
| --- | --- | --- | --- |
| 2023 | 2022 | 5 / 15 / 60 | 0.5 |
| 2024 | 2023 | 10 / 15 / 60 | 0.25 |
| 2025 | 2024 | 5 / 30 / 60 | 0.0 |

2025 年选到 θ=0，表示这一轮搜索没有选择正的斜率死区；混合排列仍归中性。不能把所选参数当作稳定最佳值。

## 方向预测结果

平衡准确率是上涨、中性、下跌三个类别召回率的平均值；只预测一个固定类别的基准为 1/3。它不是交易胜率。

| 窗口 | 模型 | 成熟样本 | 平衡准确率 | Macro F1 |
| --- | --- | --- | --- | --- |
| all | selected | 104832 | 32.55% | 0.3171 |
| all | anchor | 104832 | 32.04% | 0.3080 |
| all | flat | 104832 | 33.33% | 0.1536 |
| all | prior_year_symbol_majority | 104832 | 33.36% | 0.2679 |
| 2023 | selected | 34944 | 32.19% | 0.2901 |
| 2023 | anchor | 34944 | 31.62% | 0.3039 |
| 2023 | flat | 34944 | 33.33% | 0.1624 |
| 2023 | prior_year_symbol_majority | 34944 | 33.33% | 0.1634 |
| 2024 | selected | 34944 | 32.25% | 0.3168 |
| 2024 | anchor | 34944 | 31.74% | 0.3070 |
| 2024 | flat | 34944 | 33.33% | 0.1517 |
| 2024 | prior_year_symbol_majority | 34944 | 33.33% | 0.1814 |
| 2025 | selected | 34944 | 32.13% | 0.3213 |
| 2025 | anchor | 34944 | 32.65% | 0.3118 |
| 2025 | flat | 34944 | 33.33% | 0.1464 |
| 2025 | prior_year_symbol_majority | 34944 | 33.33% | 0.1797 |

训练选择版本在三个年份均未超过 1/3 的平衡准确率基准。合并结果为 32.55%；其上涨、中性、下跌判断没有表现出足以支撑本交易规则的方向区分能力。该结论限于本次 24 小时目标、规则和数据窗口，不等于所有 EMA 用法无效。逐币、逐年逐币混淆矩阵、精确率和召回率见 direction_metrics.json (`provenance:nonincluded/crypto-leverage/reports/research_platform_v6/runs/ema_volume_direction_v3_20261016_clock_repaired/direction_metrics.json`)。

## 活动和冷却仍然能预测什么

相对成交量 z 是当前小时成交量除以前 8 周相同星期与小时的成交量中位数。z≥3 定义高成交量小时。两个预测目标分别是未来 6 小时内高量小时数，以及未来 24 小时内能否出现并完成连续 6 小时 z≤1.5 的冷却段。冷却标签要求完整 48 小时后续观察；这不是精确预测冷却发生在哪一个小时。

本次对所有合格小时重新训练；不沿用旧研究只在量能冲击起点上的系数或 AUC。特征包括历史价格、成交量、买卖主动量不平衡、时钟及事件近期性，所以结果不能全部归因于纯成交量，更不能归因于 ETAS 幂律核。

计数头为固定 alpha=0.1 的 Poisson 回归，预测投影至 [1e−9,6]；冷却头为固定 C=1、L2 的逻辑回归。标准化仅拟合训练期，未搜索这两个模型的参数。方向、计数和冷却分别按 24、6、48 小时标签成熟度净化训练边界，标签可用时刻必须严格早于评估年起点；年末尚无成熟标签的小时仍可生成交易预测，只从评分中排除。

| 窗口 | 样本 | 未来 6 小时计数 MAE | 历史均值 MAE | Poisson deviance | 历史均值 deviance |
| --- | --- | --- | --- | --- | --- |
| all | 105048 | 0.5394 | 0.7178 | 1.0441 | 1.5037 |
| 2023 | 35016 | 0.5884 | 0.7652 | 1.1699 | 1.6384 |
| 2024 | 35016 | 0.5196 | 0.7032 | 0.9942 | 1.4565 |
| 2025 | 35016 | 0.5103 | 0.6850 | 0.9681 | 1.4161 |

| 窗口 | 样本 | 冷却 AUC | 历史均值 AUC | Brier | 历史均值 Brier | 实际冷却比例 |
| --- | --- | --- | --- | --- | --- | --- |
| all | 104544 | 0.8343 | 0.5037 | 0.1151 | 0.1639 | 79.48% |
| 2023 | 34848 | 0.8426 | 0.5248 | 0.1188 | 0.1768 | 77.02% |
| 2024 | 34848 | 0.8255 | 0.4829 | 0.1118 | 0.1552 | 81.31% |
| 2025 | 34848 | 0.8328 | 0.5112 | 0.1146 | 0.1597 | 80.10% |

合并计数 MAE 从 0.7178 降到 0.5394；冷却 AUC 为 0.8343，Brier 从 0.1639 降到 0.1151。AUC 0.8343 不等于 83.43% 的准确率。概率仍有校准偏差：预测落在 0–10% 桶时，均值约 4.45%，实际冷却约 10.08%；不能将每个输出概率视为精确可信。完整 40 个分组、log loss 和校准桶见 activity_metrics.json (`provenance:nonincluded/crypto-leverage/reports/research_platform_v6/runs/ema_volume_direction_v3_20261016_clock_repaired/activity_metrics.json`)。

Hawkes 金融综述涵盖波动、订单到达与订单簿动态等应用，为研究活动聚集提供背景；它不验证本次 EMA 方向规则。[Bacry、Mastromatteo 与 Muzy，2015](https://arxiv.org/abs/1502.04592)。本地旧 v2 研究也没有证明幂律项提供稳健增量，因此本次没有添加该核。

## 入场过滤究竟保留了什么

只有状态转入新的非零方向才允许入场。过滤拒绝后整段跳过，不在后续补入；转为中性或反向即退出，退出不等待成交量信号。拒绝代表不交易，不能把拒绝样本计为“预测横盘正确”。三个非固定对照组使用相同的完整特征与预测可用性要求。

| 规则 | 入场条件 |
| --- | --- |
| 固定 7/20/99 | 固定 EMA7/20/99、θ=0.25，不加量能过滤 |
| 训练选择 EMA | 每年训练期选择的 EMA，不加量能过滤 |
| EMA 加相对量过滤 | 同一 EMA，另外要求当前 z≥1 |
| EMA 加活动预测过滤 | 同一 EMA，另外要求预计未来 6 小时高量小时数≥1，且 24 小时内冷却概率≤0.5 |

| 年份 | 规则 | 机会数 | 保留 | 缺失输入拒绝 | 覆盖率 | 保留信号的方向命中率 |
| --- | --- | --- | --- | --- | --- | --- |
| 2023 | 固定 7/20/99 | 1256 | 1256 | 0 | 100.00% | 33.44% |
| 2023 | EMA 加活动预测过滤 | 1401 | 114 | 0 | 8.14% | 38.60% |
| 2023 | 训练选择 EMA | 1401 | 1401 | 0 | 100.00% | 33.95% |
| 2023 | EMA 加相对量过滤 | 1401 | 862 | 0 | 61.53% | 35.86% |
| 2024 | 固定 7/20/99 | 1244 | 1244 | 0 | 100.00% | 34.76% |
| 2024 | EMA 加活动预测过滤 | 1531 | 95 | 5 | 6.21% | 33.68% |
| 2024 | 训练选择 EMA | 1531 | 1526 | 5 | 99.67% | 35.40% |
| 2024 | EMA 加相对量过滤 | 1531 | 820 | 5 | 53.56% | 34.80% |
| 2025 | 固定 7/20/99 | 1278 | 1278 | 0 | 100.00% | 32.31% |
| 2025 | EMA 加活动预测过滤 | 1152 | 50 | 0 | 4.34% | 22.00% |
| 2025 | 训练选择 EMA | 1152 | 1152 | 0 | 100.00% | 32.67% |
| 2025 | EMA 加相对量过滤 | 1152 | 577 | 0 | 50.09% | 33.28% |

2025 年活动过滤只保留 4.34% 的 EMA 入场机会，方向命中率从未过滤的 32.67% 降至 22.00%。2023 年有所改善，2024 年没有改善，因此也不能把早年的有利子集当作稳定结论。这里命中率与未来 24 小时标签比较；交易实际退出时刻由 EMA 状态决定，交易胜率是另一个指标。

## 2025 年成本后账户结果

全部收益以相同初始资本 10,000 USDT 计算。1 倍杠杆、40% 静态名义仓位预算，四币各约 1,000 USDT，以决策时已知价格确定数量，不复利、不在趋势段内调仓。基础每侧手续费 5 bp、逆向滑点 2 bp；压力每侧手续费 5 bp、逆向滑点 10 bp。使用真实原生资金费事件和真实标记 K 线。

| 情景 | 规则 | 净收益 USDT | 资本回报 | 交易数 | 日收益 Sharpe | 小时 NAV 最大回撤 | 胜率 | Profit factor |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | 固定 7/20/99 | -3,415.75 | -34.16% | 1278 | -2.34 | -37.43% | 29.50% | 0.736 |
| base | 训练选择 EMA | -2,958.81 | -29.59% | 1152 | -1.68 | -34.39% | 27.34% | 0.773 |
| base | EMA 加相对量过滤 | -2,564.06 | -25.64% | 577 | -1.97 | -26.60% | 27.73% | 0.685 |
| base | EMA 加活动预测过滤 | -1,070.38 | -10.70% | 50 | -2.61 | -10.99% | 26.00% | 0.162 |
| stress | 固定 7/20/99 | -5,460.07 | -54.60% | 1278 | -3.80 | -56.45% | 26.21% | 0.621 |
| stress | 训练选择 EMA | -4,802.56 | -48.03% | 1152 | -2.80 | -51.14% | 23.26% | 0.666 |
| stress | EMA 加相对量过滤 | -3,487.70 | -34.88% | 577 | -2.69 | -35.56% | 24.78% | 0.605 |
| stress | EMA 加活动预测过滤 | -1,150.48 | -11.50% | 50 | -2.77 | -11.78% | 24.00% | 0.140 |

不交易现金对照：收益与回撤均为 0、交易 0 笔；无收益方差，Sharpe 和胜率 N/A。它优于本窗口中的所有四种交易规则。

| 情景 | 规则 | 含滑点价差收益 | 手续费 | 资金费现金流 | 已嵌入的滑点归因 | 成交额 |
| --- | --- | --- | --- | --- | --- | --- |
| base | 固定 7/20/99 | -2,077.20 | 1,277.70 | -60.85 | 511.08 | 2,555,404.18 |
| base | 训练选择 EMA | -1,744.05 | 1,152.34 | -62.41 | 460.94 | 2,304,689.21 |
| base | EMA 加相对量过滤 | -1,958.61 | 577.28 | -28.17 | 230.91 | 1,154,560.86 |
| base | EMA 加活动预测过滤 | -1,019.91 | 50.06 | -0.42 | 20.02 | 100,114.63 |
| stress | 固定 7/20/99 | -4,121.52 | 1,277.70 | -60.85 | 2,555.40 | 2,555,405.44 |
| stress | 训练选择 EMA | -3,587.80 | 1,152.35 | -62.41 | 2,304.69 | 2,304,690.23 |
| stress | EMA 加相对量过滤 | -2,882.25 | 577.28 | -28.17 | 1,154.56 | 1,154,562.24 |
| stress | EMA 加活动预测过滤 | -1,100.00 | 50.06 | -0.42 | 100.11 | 100,115.43 |

净收益=含滑点的价差收益−手续费+资金费现金流。滑点已嵌入成交价格，上表滑点归因仅解释成本，不能再扣一次。活动组基础情景在不含滑点的价格差额上约亏损 999.89 USDT；即使费用更低，也不能将本规则的失败解释为单纯手续费过高。

| 情景 | 规则 | 最差月 USDT | 最差笔 USDT | 平均 MFE | 最差 MAE | 持仓时间占比 |
| --- | --- | --- | --- | --- | --- | --- |
| base | 固定 7/20/99 | -1,443.68 | -108.95 | 2.12% | -10.82% | 52.85% |
| base | 训练选择 EMA | -1,572.92 | -145.01 | 2.64% | -14.54% | 71.51% |
| base | EMA 加相对量过滤 | -940.86 | -145.01 | 2.96% | -14.54% | 39.21% |
| base | EMA 加活动预测过滤 | -327.60 | -145.01 | 2.66% | -14.54% | 2.78% |
| stress | 固定 7/20/99 | -1,651.22 | -110.48 | 2.04% | -10.89% | 52.85% |
| stress | 训练选择 EMA | -1,748.22 | -146.74 | 2.56% | -14.63% | 71.51% |
| stress | EMA 加相对量过滤 | -1,008.83 | -146.74 | 2.88% | -14.63% | 39.21% |
| stress | EMA 加活动预测过滤 | -337.24 | -146.74 | 2.58% | -14.63% | 2.78% |

Sharpe 使用 365 个 UTC 日 NAV 收益、样本标准差和 √365 年化。最大回撤使用初始资本与逐小时真实 mark NAV。最差月由 UTC 日 NAV 增量汇总；两种成本情景的活动组最差月均为 2025 年 4 月，其他三组均为 12 月。最差笔包含该笔分摊费用和资金费。MFE/MAE 使用持仓期间已经完成的真实 mark K 线高低点，以入场价格归一；空单方向相反。它们是小时极值代理，无法精确区分入场秒前的小时极值。最差 MAE 为所有交易最不利值，MFE 为交易平均值；每组样本数等于上表交易数。持仓时间占比为四个币种持仓秒数之和除以 4×365 天。

| 币种 | EMA 净收益 | 活动组净收益 | 活动组增量 | 活动组交易数 |
| --- | --- | --- | --- | --- |
| BTCUSDT | -762.77 | -127.79 | 634.98 | 6 |
| ETHUSDT | -651.72 | -455.04 | 196.68 | 16 |
| SOLUSDT | -1,106.41 | -457.32 | 649.09 | 8 |
| BNBUSDT | -437.91 | -30.23 | 407.68 | 20 |

活动组四币都少亏，但四币仍全部亏损。平均持仓时间从 71.51% 降到 2.78%，交易数从 1,152 降到 50，Profit factor 从 0.773 降到 0.162；这些证据支持“减少暴露”，没有支持“筛出更好的顺势交易”。缺少与同等交易数/暴露的随机过滤对照，因此不能把少亏归因于预测模型的独立优势。

## 冻结的增量筛选条件

| 情景 | 活动组相对 EMA 的全年净增量 USDT | 平均每日净增量 | 95% 区间，USDT/日 |
| --- | --- | --- | --- |
| base | 1,888.42 | 5.17 | [-3.33, 13.89] |
| stress | 3,652.08 | 10.01 | [1.33, 18.71] |

区间使用全部 365 天、14 天非循环移动块、2,000 次重采样、固定随机种子；币种和两组账户保持配对。它是已暴露历史上的描述性区间，不是独立显著性证明。基础情景增量 1,888.42 USDT，但区间跨 0。压力情景增量区间为正，也不能救回活动组自身仍亏损的事实。

| 预先冻结的条件 | 结果 |
| --- | --- |
| base_activity_net_pnl_positive | FAIL |
| base_increment_over_ema_only_positive | PASS |
| paired_95pct_daily_increment_lower_bound_positive | FAIL |
| stress_activity_net_pnl_positive | FAIL |
| positive_increment_in_at_least_3_symbols | PASS |
| at_least_30_trades_and_5_per_symbol | PASS |
| drawdown_no_worse_than_20pct | PASS |
| no_failed_margin_or_capacity_scenario | PASS |
| trade_ledger_reconciles | PASS |

**继续研究筛选：FAIL。** 自身基础收益、压力收益和基础增量区间下界三个条件失败。这里的条件 PASS 只是固定算术或样本条件，不等于研究九门槛通过。

## 时钟、来源与实际执行限制

决策使用已完成小时数据：输入和预测可用时刻为小时结束后 1 毫秒；普通决策在小时结束后 2 秒；等待下一根观测小时开盘，以该开盘价加逆向滑点建模，并在参考开盘后 1.001 秒记账。这意味着普通入场有约一小时等待。延后记账仍使用开盘参考价格属于模拟代理，不是实际可成交报价。真实延迟、盘口与成交概率未验证。

原生资金费时间不移动。现有数据契约允许结算时刻距名义整点最多 1 秒，因此按原生结算先作用于旧仓，再执行模拟成交。资金费换算使用此前已可用的真实 mark 收盘作为代理，不能称为精确结算标记价。年末按预注册策略在 2025-12-31 23:00:01.001Z 平仓，决策提前到 22:59:59.999Z，只用决策前可知的容量数据，且不再开仓。

第一轮执行因 BNB 原生结算与原先 +1ms 成交时刻冲突而失败，在生成任何账户结果前停止。该轮内部已经完成训练和选参，不能称为完全没有接触计算结果。修复仅统一时钟，未查看收益后修改参数；旧失败目录和三个文件哈希保留。独立复核确认两轮 243 个评分及所选配置逐项相同。详见 独立审查记录 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/ema_volume_direction_v3_20261016/review.md`)。

选定 12 个 trade/mark/funding 文件均通过绑定、注册标签和 SHA256 检查；每组账户保留 4,380 个原生资金费事件，没有补齐或伪造数据。2024-10-28 20:00Z 的来源小时成交量为观察到的零值；对应 log-volume 和不平衡特征未定义，各币随后共 24 个小时输入被剔除，共 96 个币小时，不是时间网格缺口，也未插补。原始小时网格连续。

8 组均通过当前 1% 已完成小时成交额容量代理和研究保证金情景，零情景越界；这不证明真实盘口容量或交易所逐档清算正确。维持保证金率 0.5%、清算费率 0.2% 仅为研究假设；真实最低清算距离 N/A；2×、3×、5×未运行。

## 九项验证门槛

| 门槛 | 状态 | 证据及窗口 | 阻碍或解释 |
| --- | --- | --- | --- |
| 1 数据完整性和可用时钟 | BLOCKED | source_audit.json (`provenance:nonincluded/crypto-leverage/reports/research_platform_v6/runs/ema_volume_direction_v3_20261016_clock_repaired/source_audit.json`)；2020-10 至 2025-12 原始 trade，2025 mark/funding；最终身份复核 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/ema_volume_direction_v3_20261016/final_identity_check.json`) | 选定来源完整与模拟因果顺序有证据；实际发布延迟、精确资金费计价 mark 未验证 |
| 2 实现与前视/递归检查 | BLOCKED | 独立复算 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/ema_volume_direction_v3_20261016/independent_result_audit.json`)；105,120 行状态、243 个评分、全部成交和账本 | 新版本合成测试通过；尚未把此规则接入适用 Freqtrade lookahead-analysis/recursive-analysis；不能借用旧策略检查结果 |
| 3 机制与样本内研究 | FAIL | search_scores.json (`provenance:nonincluded/crypto-leverage/reports/research_platform_v6/runs/ema_volume_direction_v3_20261016_clock_repaired/search_scores.json`)、direction_metrics.json (`provenance:nonincluded/crypto-leverage/reports/research_platform_v6/runs/ema_volume_direction_v3_20261016_clock_repaired/direction_metrics.json`)；2022–2024 选择，2023–2025 诊断 | 搜索过程完整披露，但本次后续方向分类和冻结经济条件不支持该顺势机制 |
| 4 未触碰样本外与滚动检验 | BLOCKED | fit_metadata.json (`provenance:nonincluded/crypto-leverage/reports/research_platform_v6/runs/ema_volume_direction_v3_20261016_clock_repaired/fit_metadata.json`)；2023/2024/2025 按时间滚动 | 训练缩放和标签成熟度已核对，但所有历史已暴露；真正未触碰 OOS 收益、Sharpe N/A |
| 5 双侧成本、资金费和成交 | BLOCKED | economic.json (`provenance:nonincluded/crypto-leverage/reports/research_platform_v6/runs/ema_volume_direction_v3_20261016_clock_repaired/economic.json`)、8 个 account_tape 文件；2025 | 账本已对账、双侧费用/原生资金费已计入；小时开盘代理与容量代理不足以建立真实执行证据 |
| 6 市场阶段、币种及参数稳健性 | FAIL | economic.json (`provenance:nonincluded/crypto-leverage/reports/research_platform_v6/runs/ema_volume_direction_v3_20261016_clock_repaired/economic.json`)、entry_opportunity_metrics.json (`provenance:nonincluded/crypto-leverage/reports/research_platform_v6/runs/ema_volume_direction_v3_20261016_clock_repaired/entry_opportunity_metrics.json`)；2023–2025 预测，2025 交易 | 固定四币基础/高滑点全部亏损；活动入场命中率跨年不稳定；没有其他年度经济结果或正式阶段分层 |
| 7 杠杆、保证金和清算压力 | BLOCKED | economic.json (`provenance:nonincluded/crypto-leverage/reports/research_platform_v6/runs/ema_volume_direction_v3_20261016_clock_repaired/economic.json`)；2025、1× | 研究情景算术通过；精确交易所档位、清算路径和最低距离未验证；其他倍数未运行 |
| 8 Dry-run 观察与对账 | NOT_RUN | 本次没有交易机器人观察记录 | CLI dry-run 仅验证无写入，不是交易 dry-run 观察 |
| 9 小额实盘观察 | BLOCKED | 无本策略既有实盘成交记录 | 工作区禁止实盘交易；没有实盘验证证据 |

## 独立复核与项目检查

复核独立重建原始 EMA、ATR、方向标签、相对量、计数和冷却目标；验证所有 243 个训练评分、80 个方向分组指标、40 个活动分组指标、6 个保存模型的数值预测、全部信号到成交、成本、资金费账、365 日 NAV、Sharpe、回撤和配对区间。活动模型的特征矩阵复用经过审查的 RECENCY 实现，不能称为第二套完全独立特征工程；模型缩放和系数运算另外重算。

活动指标最大复算误差 2.22e−16，保存模型预测最大复算误差 1.78e−15；各组交易净收益与最终钱包差额残差绝对值 < 4e−11 USDT。初次真实运行前组合回归 64 passed；时钟修复后 24 个本版本测试全部验证（23 个通过，另 1 个结果契约 fixture 补齐后单独复测通过）。两张输出图已人工查看。

| 维护步骤 | 结果 | 日志 |
| --- | --- | --- |
| fetch_local_source_copies.py --verify | exit 1；139 项中 54 项旧来源未验证；本研究 12 项通过 | maintenance_01_verify.log (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/ema_volume_direction_v3_20261016/maintenance_01_verify.log`) |
| import_perp_data.py | exit 3；拒绝转换 12 个旧来源组合，没有降低门槛 | maintenance_02_import.log (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/ema_volume_direction_v3_20261016/maintenance_02_import.log`) |
| build_inventory.py | exit 0 | maintenance_03_inventory.log (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/ema_volume_direction_v3_20261016/maintenance_03_inventory.log`) |
| build_reports.py | exit 0 | maintenance_04_reports.log (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/ema_volume_direction_v3_20261016/maintenance_04_reports.log`) |
| pytest tests -q -x，独立 workspace basetemp | 704 passed；1 项因 Windows 临时目录权限中断 | maintenance_05_pytest.log (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/ema_volume_direction_v3_20261016/maintenance_05_pytest.log`) |
| 权限阻断项沙箱外单独重跑 | 1 passed in 0.49s | maintenance_06_sandbox_retry.log (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/ema_volume_direction_v3_20261016/maintenance_06_sandbox_retry.log`) |
| pytest tests -q，全项目沙箱外完整重跑 | 23 failed, 4382 passed, 1 skipped, 274 warnings in 2121.05s (0:35:21) | maintenance_07_full_suite_outside_sandbox.log (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/ema_volume_direction_v3_20261016/maintenance_07_full_suite_outside_sandbox.log`) |
| 仅重跑失败项，使用工作区内临时目录 | 9 failed, 14 passed, 2 warnings in 6.09s | maintenance_08_failed_recheck.log (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/ema_volume_direction_v3_20261016/maintenance_08_failed_recheck.log`) |

| 失败项复核后仍失败的模块 | 失败项数 |
| --- | --- |
| tests/test_c3_trend_failure_winner_preservation_v1r1.py | 4 |
| tests/test_channel_ml_2024_2025_v1r3_dispatch.py | 1 |
| tests/test_channel_ml_2024_2025_v1r4_dispatch.py | 1 |
| tests/test_cli_end_to_end.py | 2 |
| tests/test_ema_iv_v1_source_guards.py | 1 |

完整运行 23 个失败项中，14 个在工作区内临时目录下通过，说明先前命中了工作区路径约束。剩余 9 项分属旧 C3/EMA-IV 注册表历史身份不一致（5 项）、旧 channel-ML 报告计数预期（2 项）及 CLI 子进程输出解码（2 项）。本次 v3 以及成交量 v1/v2 测试不在失败列表中。未修改这些其他模块来掩盖全项目失败；本报告不声称整个项目测试通过。完整节点、堆栈和警告保留在日志中。

维护按顺序执行。本次维护后只有预期的可变 source_data/MANIFEST.json 身份发生刷新；38 个 v3 代码闭包文件、25 个旧代码文件、22 个旧结果文件、23 个新结果附件、12 个选定市场数据载荷以及失败运行文件保持相同 SHA256。冻结运行记录保留的是执行当时 manifest 身份，不回写成维护后的身份。

## 决定与后续可检验问题

**本版决定：EXPLORATORY；盈利组合的冻结筛选 FAIL；有效性 UNVERIFIED。** 当前证据允许继续把预期活动数、冷却概率作为市场状态或风险暴露研究变量，但没有证明它们叠加本 EMA 规则后能赚钱。不能因为方向分类低于基准就直接反向交易；反向规则、费用和退出逻辑都必须另行冻结检验。

若继续开展下一版，优先检验活动预测是否有助于未来波动/价格区间、仓位控制或退出时机；方向模块需要独立证据。活动组平均每笔持仓约 19.46 小时，而计数头覆盖 6 小时、冷却头覆盖 24 小时；预测窗口与持仓窗口是否匹配也是待检验的问题，不能据此认定亏损原因。对过滤价值的下一项必要对照是相同交易数和暴露的基准，以及明确的延迟敏感性检验。本轮不根据已看见的亏损再调 EMA 或过滤阈值，未实施这些新假设。真正推广仍需未触碰后续窗口和执行证据。

## 可复现入口与图表

```powershell
.venv/Scripts/python.exe -B -X utf8 scripts/research_platform_v6.py ema-volume-run --spec reports/strategy_validation/ema_volume_direction_v3_20261016/frozen_spec.json --execute --run-id <新的唯一研究编号>
```

该命令仅为历史研究，拒绝覆盖已有运行。所有策略、状态、机会和预测文件均保留在 结果清单 (`provenance:nonincluded/crypto-leverage/reports/research_platform_v6/runs/ema_volume_direction_v3_20261016_clock_repaired/result.json`) 中。原始交易时钟修复原因和每轮审查见 review.md (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/ema_volume_direction_v3_20261016/review.md`)；运行结束前的独立审计见 independent_result_audit.json (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/ema_volume_direction_v3_20261016/independent_result_audit.json`)，活动指标另见 supporting_metrics_audit.json (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/ema_volume_direction_v3_20261016/supporting_metrics_audit.json`)。

固定日期 BTC 一小时 EMA 与状态示例 (`provenance:nonincluded/crypto-leverage/reports/research_platform_v6/runs/ema_volume_direction_v3_20261016_clock_repaired/ema_state_diagnostic.png`)

图示预先固定为 BTC 2025 年 1 月、EMA7/20/99；没有按收益挑选样本。

2025 年四组基础及压力成本结果 (`provenance:nonincluded/crypto-leverage/reports/research_platform_v6/runs/ema_volume_direction_v3_20261016_clock_repaired/economic_comparison.png`)

收益图仅展示上述已暴露历史中的模拟账户差额。
