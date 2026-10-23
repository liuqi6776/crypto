> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 资金费率净收益本地数据研究

研究日期：2026-10-17（Asia/Shanghai）。结论状态：**UNVERIFIED；预定历史经济性筛选未通过。**

**本轮没有证明资金费收入能稳定转化为净收益。** 在原先冻结的两个组合中，资金费现金流的已知周均值均为正；加入价格损益和每边 20bp 的综合执行成本后，两个年份、两个组合的已知周平均净损益全部为负。即使假设零执行成本，净损益均值的置信区间仍全部跨过零。价格风险、交易成本和未知周都不能忽略。

这不等于证明所有资金费策略都无效。本轮只评价已冻结的“过去七日资金费排序、低费率端做多、高费率端做空、持有七日”的两个组合。没有根据结果重新挑币、改参数或选择更好看的年份。

## 1 资金费与价格损益分解

下表单位均为 **USDT / 每 10,000 USDT 参考资本 / 每个可完整核算的活动周**，不是年度收益。资金费与价格损益均为假设持仓的历史记账结果，资金费现金流按观测结算事件及假设数量计算。初始总名义敞口为参考资本的 1 倍；每周全平再重建。20bp 等于每边成交名义的 0.20%，入场和退出分别计费；成本是费用、价差、滑点的合并假设，不是实际交易所收费或成交估计。

| 组合 | 决策年份 | 完整周 / 计划活动周 | 价格损益 | 资金费现金流 | 双边成本 | 净损益 | 净均值 95% 区间 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| 多空各半 CARRY_EQ | 2024 | 42 / 46 | +10.64 | +19.73 | 40.05 | **−9.68** | [−98.21, +92.01] |
| 多空各半 CARRY_EQ | 2025 | 33 / 48 | −47.09 | +65.98 | 39.39 | **−20.50** | [−139.59, +67.42] |
| 事前 beta 配比 CARRY_BETA | 2024 | 42 / 46 | +14.64 | +17.16 | 40.07 | **−8.27** | [−105.70, +111.25] |
| 事前 beta 配比 CARRY_BETA | 2025 | 33 / 48 | −41.61 | +69.93 | 39.39 | **−11.07** | [−115.72, +69.92] |

每一行满足：**净损益 = 价格损益 + 观测资金费 − 入场成本 − 退出成本**。分解项使用同一组完整周，避免拿资金费的较大样本与价格收益的较小样本相加。

在同一完整周样本上，四组资金费现金流均值的 95% 区间下界均为正，分别为 +13.52、+45.81、+10.62、+47.19 USDT。这支持该排序在这些已知周收取资金费的倾向；它不能单独证明整个组合赚钱。

2024 年两组约 30–32 USDT 的成本前周均收益，抵不过约 40 USDT 的双边成本。2025 年资金费收入更高，但约 42–47 USDT 的价格损失消耗了大半收入，剩余部分仍不足以支付主情景成本。负的样本均值不能解读为“真实期望收益已被显著证明为负”；区间很宽，当前能成立的是**没有获得可信的正净收益证据**。

置信区间使用各年原始排期上的非循环四周区块重抽样，共 2,000 次、固定 seed=20261017；未知和非活动日期保留在日历中。这能反映已观测样本的波动与部分相邻周依赖，不能修复未知周的选择偏差，也不是未触碰样本外证明。

证据：[年度分解](results_20261016T225531135982Z/annual_summary.csv)、逐周账本 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_net_economics_v1_20261017/results_20261016T225531135982Z/weekly_components.csv`)。

## 2 成本敏感性与 beta 配比效果

| 组合与年份 | 每边 0bp：周均净损益 | 每边 20bp | 每边 50bp | 点估计盈亏平衡成本：每边 bp |
| :--- | ---: | ---: | ---: | ---: |
| CARRY_EQ，2024 | +30.37 | −9.68 | −69.75 | 15.17 |
| CARRY_EQ，2025 | +18.89 | −20.50 | −79.60 | 9.59 |
| CARRY_BETA，2024 | +31.80 | −8.27 | −68.38 | 15.87 |
| CARRY_BETA，2025 | +28.32 | −11.07 | −70.15 | 14.38 |

盈亏平衡值来自相同完整周的成本前均值与实际入场、退出参考成交名义。它只是历史点估计：不能据此声称小于该成本就能稳定盈利，也没有证明能在这些币种上实现这样的交易成本。零成本情景的四个净均值区间仍跨零，说明问题不只在费用水平。

beta 组合与多空各半组合使用完全相同的成员，仅按事前历史 beta 调整两端预算。20bp 情景下，配对周均改善为：2024 年 **+1.40 USDT**，95% 区间 [−28.06, +35.78]；2025 年 **+9.44 USDT**，区间 [−18.18, +36.94]。两组区间均跨零，尚不能把 beta 调整当成经过验证的收益改善。

预定筛选要求每年至少 40 个完整活动周、两个年份 net20 均值区间下界均大于零、net50 均值均为正，且无观测到的代理资不抵债。两个组合均未通过；其中 2025 年连完整周数要求也未达到。没有为通过筛选而改阈值。

证据：配对差值 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_net_economics_v1_20261017/results_20261016T225531135982Z/paired_arm_differences.csv`)、预定筛选结果 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_net_economics_v1_20261017/results_20261016T225531135982Z/predeclared_historical_screen.csv`)。

## 3 价格风险与敞口漂移

这里的多头与空头是不同币种。两端名义金额相等，或者初始 BTC beta 匹配，都无法抵消各币之间的相对涨跌。因此，这个组合仍承担明显的横截面价格风险；资金费收入只是总损益中的一项。

以下风险数字限于**主成本情景、可完整核算的独立周**。回撤使用真实小时标记价 open、逐次资金费、入场成本及最终参考价平仓成本，按每周单独启动的假设账户计算。它是小时采样的周内峰谷回撤，不是年度账户最大回撤、逐笔 MAE 或实际强平损失。

| 组合与年份 | 最差完整周净损益 / 参考资本 | 最差周内小时估值回撤 | 最大总名义 / 当时假设净值 |
| :--- | ---: | ---: | ---: |
| CARRY_EQ，2024 | −14.56% | 15.06% | 1.53 倍 |
| CARRY_EQ，2025 | −8.20% | 24.20% | 1.46 倍 |
| CARRY_BETA，2024 | −15.90% | 16.18% | 1.56 倍 |
| CARRY_BETA，2025 | −8.13% | 24.13% | 1.46 倍 |

最差完整周与最差周内回撤是两种不同量度，不能互换。2024 年最差完整周为 2 月 26 日决策周；2025 年 11 月 3 日决策周出现约 24% 的周内小时回撤。2025 年即使调整初始 beta 配比，这项回撤也几乎没有改善。

固定持仓数量使暴露随价格和净值变化。2025 年完整周内，多空各半组合的估计 beta 金额 / 参考资本范围为 **−0.487 至 +0.588**，beta 配比组合为 **−0.220 至 +0.212**。后者在这个口径上缩小了漂移，但不等于持续市场中性，更不等于消除了尾部损失。beta 配比也引入净名义差异；其 2025 年净名义 / 参考资本范围为 −0.236 至 +0.275。

在全部计划活动周的事前目标中，最大单币目标占参考资本约 5.29%（只看完整周则为 5.17%）。仍有完整周出现单币绝对净贡献占所有币绝对净贡献之和约 56%。这不是“该币贡献了全年 56% 的收益”，而是提示周收益可能被个别币的行情主导。初始名义相对历史日均成交额很小，也不能代替盘口、成交与退出可行性证据。

已观测路径没有出现非正假设净值，但小时采样会遗漏小时内部路径；保证金阶梯、维持保证金、强平费用和实际成交均未建模。**不能由此得出安全杠杆、强平距离或零强平结论。**

证据：小时风险路径 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_net_economics_v1_20261017/results_20261016T225531135982Z/hourly_risk_paths.csv`)、最终完整周风险汇总 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_net_economics_v1_20261017/review/final_risk_exposure_summary.json`)、币种贡献 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_net_economics_v1_20261017/results_20261016T225531135982Z/symbol_contributions.csv`)、集中度 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_net_economics_v1_20261017/results_20261016T225531135982Z/weekly_symbol_concentration.csv`)。

## 4 未知周与连续账户限制

原始队列每个决策有 60 个候选币，共 101 个周一、6,060 个币种与决策组合、270 个不同币。成员与目标权重在新增价格损益计算前冻结；未来价格缺失不能改变持仓选择。

| 决策年份 | 原始排期 | 事前空仓 | 跨年剔除 | 计划活动周 | 完整净损益周 | 未知活动周 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 | 53 | 6 | 1 | 46 | 42 | 4 |
| 2025 | 48 | 0 | 0 | 48 | 33 | 15 |

两臂覆盖相同。2024 年 4 个未知周含 2 个入场价格未知周和 2 个退出价格未知周；2025 年分别为 11 个和 4 个。入场数量无法确定时，篮子资金费现金流也保持未知；这不意味着每一条腿都缺入场价。退出参考价未知但数量已知的周，仍保留可证明的资金费与小时标记路径，不把路径末端假冒成已现金结算。

端点问题包括 RNDRUSDT 在 2024-07-29 入场时交易量为零、所需 2024-08 交易月文件不在冻结清单；MATIC、UNFI、FTM、BNX 等部分周的端点没有正交易量或精确小时开盘。这些现象不能被视为随机缺失，也不能自动解释为已确认的换币、下架或最终结算事实。逐项细目保存在独立来源复算记录 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_net_economics_v1_20261017/review/independent_source_reproduction.json`)。

严格连续账户每年从 10,000 USDT 开始，以已知期末资本决定下一周规模，遇未知就停止：

- **2024 年**：完成 30 个排期周，其中 25 个活动周、5 个事前空仓周；最后已完成持有期在 2024-07-29 01:00 UTC 退出。2024-07-29 决策周变为未知后不再拼接。这个已知前缀的小时估值回撤为 CARRY_EQ **18.08%**、CARRY_BETA **19.84%**，仅描述该前缀。
- **2025 年**：第一个 2025-01-06 决策周就无法得到有效退出结算，完整往返周数为零。可以观察该周 169 个小时标记时点；加上入场前初始现金，账户前缀计数为 170 个观测点。最后一个标记估值不能视为已知的最终现金余额。

因此，本轮没有完整年度总收益、CAGR、年度 Sharpe 或年度账户最大回撤。2025 年原始排期本身也只持有至 12 月 8 日，不能称作全年。表中的 42 / 33 个完整周是条件样本，不能跳过未知周复利，更不能把未知损益填成零。

证据：连续账户停止记录 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_net_economics_v1_20261017/results_20261016T225531135982Z/strict_account_prefixes.csv`)、资金费窗口覆盖 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_net_economics_v1_20261017/results_20261016T225531135982Z/funding_window_coverage.csv`)。

## 5 记账方法与独立复核

使用本地已有交易小时 K 线作为入场、退出参考价；入场为周一决策后 1 小时，持有七日。资金费逐条使用原始毫秒结算时刻、精确十进制费率和该事件自己的标记价：`−有符号数量 × 事件标记价 × 事件费率`。只计 `入场时刻 < 结算时刻 ≤ 退出时刻`，不重采样或补零。小时标记 K 线只用于风险估值，不替代结算事件价格。

既有本地小时 markPriceKlines 经过来源与 SHA256 核验后，追加登记了 5,451 个研究参考文件。其状态仍为 `EXTERNAL_REFERENCE_ONLY`、`installed=false`、`gate_effect=NONE`；未被提升为可交易或规范安装的数据。原始范围中 1,029 个符号月份不在清单，这不是选中持仓的缺失周数。没有下载行情、改写原始数据、生成替代 K 线或运行交易服务。

研究实现由 GPT-6 Luna 按工作区分工完成，主代理审查并要求修正。原始方案与成员冻结事实保留；首次价格计算曾读取数据后中止，随后三次实现修订修复记账接口、风险状态和未知退出的标签。成员、权重、成本情景与筛选规则没有改变，三个保存结果版本之间的净收益结果相同；不能把修订代码描述成在所有价格读取之前就已冻结。

独立复核包括：

1. **原始来源与全部完整篮子**：核对 254 个资金费源文件、1,315 个交易价格文件的哈希；157,960 条导出事件记录的时刻、费率和事件标记价与来源一致。133,718 条已知现金流以 Decimal 重算一致，其余 24,242 条保持未知。这些是组合账本行数，两个组合对同一市场事件的记录不算独立观测。全部完整篮子的端点、数量、价格损益、资金费、双边成本和净损益复现；年度均值、配对差值和区块置信区间复现。
2. **另一套账户引擎**：重放 150 个完整“组合—周”的 20bp 账本，价格、资金费和成本逐项一致，最大净额差异约 5.64×10⁻¹¹ USDT。引擎的未知/受阻状态未被升级。
3. **原始标记价路径**：主代理独立读取并验证 233 个标记价月文件，抽取各臂、各年的首个、最好和最差完整周，共 12 个组合周 × 3 个成本情景，复算全部 169 个时点及退出现金结算；最大差异 10⁻²³ USDT。
4. **最终产物绑定**：最终运行的 15 个输出哈希与收据一致；代码、修订、原始冻结、来源登记与标记注册表绑定一致。早期独立审计与最终版的经济结果相同；差异仅为风险标志、未知退出标签及连续账户观测计数等记录修正。

复核证明的是“这些条件历史账目可复算”，不能证明历史发布时点、币种身份、真实可成交性、样本外收益或保证金安全。

详细证据：来源复算 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_net_economics_v1_20261017/review/independent_source_reproduction.json`)、独立账户复算 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_net_economics_v1_20261017/review/account_engine_reconciliation_v1.json`)、标记路径复算 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_net_economics_v1_20261017/review/independent_mark_path_reproduction_v1.json`)、最终产物核验 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_net_economics_v1_20261017/review/final_artifact_verification.json`)、实现审查 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_net_economics_v1_20261017/IMPLEMENTATION_REVIEW.md`)。

## 6 验证状态与后续研究边界

两臂均有单独九门报告：CARRY_EQ (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_net_economics_v1_20261017/results_20261016T225531135982Z/carry_eq_nine_gate_report.md`)、CARRY_BETA (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_net_economics_v1_20261017/results_20261016T225531135982Z/carry_beta_nine_gate_report.md`)。本次独立账本审计补充了第二门的证据，但不能替代完整引擎、前视和递归检验；该门及其余关键门均保持 BLOCKED，策略结论保持 UNVERIFIED。历史时点可用性、未触碰 OOS、真实执行与强平仍缺必要证据。

修正完成后的最终组合验证为 **105 项通过**，涵盖净经济性、来源登记、账户逻辑、历史身份和旧研究证据检查。此前另有 63 项既有标记价准入、注册政策和资金费转换测试通过。

首轮全量检查发现旧审计工具对参考目录大小和所属研究范围的兼容性问题，已中止、修复并通过上述组合检查。兼容性修复没有改写历史冻结、登记后的注册表或本轮数值结果。随后按工作区规则依次重跑了本地来源验证、导入、库存与报告重建；来源验证和导入仍被既有未验证来源阻止，库存与报告重建完成。

最终全量测试完成：**4,510 项通过、7 项失败、1 项跳过**，耗时 4,736.57 秒。失败名称与既有七项一致，没有新增失败项；但不能称作全量通过，也不能称作失败原因完全不变。五项仍因既有数据注册表的历史条目不满足严格追加检查而失败；另外两个旧测试的非来源清单指纹匹配数由 8/9 降至 7/9，新增差异是本轮追加研究参考后标记价注册表的整体哈希改变。历史冻结未被改写，旧研究继续受阻。详见最终失败对照 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_net_economics_v1_20261017/review/final_test_comparison.json`)与完整日志 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_net_economics_v1_20261017/maintenance/11_full_pytest_final.log`)。

全量测试结束后，重新核对了 9 个冻结代码与测试文件、15 个数值与门槛输出、两份注册表、数值运行收据及三份冻结／修订／登记收据，共 **30 项指纹全部一致**。详见最终完整性核验 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_net_economics_v1_20261017/review/post_validation_integrity.json`)。这些结果支持本轮有边界的历史记账复算，不构成策略有效或可交易的结论。

继续研究时，优先核查**现有本地证据**能否解释这些零成交端点、身份变更与退出结算，并建立不删除失败持仓的处理协议。真实执行成本与未触碰窗口缺少证据时应明确留空。当前结果不支持加杠杆、跳过问题币重算，或根据这轮亏损回头调参寻找盈利。

冻结方案：研究方案 (`provenance:nonincluded/crypto-leverage/docs/FUNDING_CARRY_NET_ECONOMICS_V1_20261017.md`)。唯一接受的数值运行目录为 `results_20261016T225531135982Z/`；其 run_receipt.json (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_net_economics_v1_20261017/results_20261016T225531135982Z/run_receipt.json`) SHA256 为 `72d6e60c8316ca70940e832e903fcf93810dcd86d1e5da2e671f1c2a6fb61a54`。旧运行保留作审计历史，不与最终输出混用。
