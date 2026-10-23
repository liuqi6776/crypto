> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 三币 4 小时趋势连续账户比较：研究结果

**结论：EXPLORATORY / UNVERIFIED（探索性、未验证）。** 本轮完成 16 个有限情景的历史账户回放；主审另用独立账本程序复核 16/16 个保存结果的事件现金流、mark/rate 对齐、每条 NAV、gross-hours、首个风险违例与日历统计，状态为 `PASS_ARITHMETIC_NOT_STRATEGY_VALIDATION`。这验证的是保存账本的算术一致性，不是独立重建全部信号，也不代表任一策略有效或可交易。

## 研究范围与固定条件

比较已有的 `EMA200_4H` 与 `BB120_EMA200_ATR3_4H`，标的 BTCUSDT、ETHUSDT、SOLUSDT，连续账户窗口为 `2020-09-15 00:00, 2026-01-01 00:00) UTC`。这批历史已在先前研究中暴露；更早的 2026 历史也曾出现在旧研究中，因此本轮与 2026 都不称作 untouched OOS。账户从 10,000 USDT 开始，三币固定入场额度合计 4,000 USDT、均分；1x、无借贷、不复利、不因结果调仓，绝对 gross 上限 10,000 USDT。费用为单边 5 bp；滑点为单边 5 bp（base）或 15 bp（stress）。全部成本是情景假设，并非成交所校准值。

使用完成的 4h/1h 数据及原生 funding 事件时间；4h 可用时刻按收盘标签 +1 ms 建模，决策延迟 2 秒，取决策后首个 H1 开盘并加 1,001 ms 模型成交延迟。价格/mark 发布延迟没有实证，因此时钟是因果模型，不是已证明的交易所发布或成交时间。BB 的 H1 stop 触发时间与入场同 H1 内的先后不可由 OHLC 确定；另保留 `touch_before_fill` 敏感性路径。stop/funding 同区间也按 conservative/favorable 两种模型报告；这些是有限敏感性情景，不是所有路径的严格上下界。

数据与身份凭证：新阶段来源预检 [`source_preflight.json` (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/trend_mainline_v1_20261017/loader_schema_v2/source_preflight.json`)（SHA256 `542bc98d2285d11ca35b386626fe20fc090ee2f03326fe3f2a8ed221a26a321c`），经批准的数值锁 SHA256 `a8ef0621d708862b40042ee7b820eebf091ac63f6cd46be3064ccedb3cea9931`；结果目录 `run_manifest.json` (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/trend_mainline_v1_20261017/loader_schema_v2/runs/loader_schema_v2/run_manifest.json`) 绑定 16 账户输出；主审独立复核 `root_independent_reconciliation.json` (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/trend_mainline_v1_20261017/loader_schema_v2/root_independent_reconciliation.json`) 绑定该 run manifest（SHA256 `e798bcdd1366ac6bbb234dc4854a1b1c7c712be6a8335391388e9ff6a5150591`）。版本为 `trend_mainline_preflight_v2_schema_20261017` 与 `trend_mainline_account_v2_schema_20261017`；策略信号由已冻结的 `longcycle_signal_cases_luna_v1.py` 构建。

## 全部情景结果

每个成本档分别跑 stop-after-fill 主路径、touch-before-fill 敏感性，并对 stop/funding 时间不确定性跑 conservative 与 favorable 两种现金流情景，共 16 例。以下回报均以初始 10,000 USDT NAV 计算；drawdown 为初始 NAV 锚定的最大回撤。EMA 行仅为违例前缀，不是完整窗口回报，不能与完整 BB 结果排名。

| 策略 | 成本 | 完成数/情景数 | 有效终点 NAV 或前缀 NAV | 累计变化 | 最大回撤 | 状态 |
|---|---:|---:|---:|---:|---:|---|
| BB120_EMA200_ATR3 | base | 4/4 | 13,792.56–13,797.09 | +37.926% 至 +37.971% | 8.590%–8.593% | 全窗口完成 |
| BB120_EMA200_ATR3 | stress | 4/4 | 13,430.63–13,435.16 | +34.306% 至 +34.352% | 9.037%–9.040% | 全窗口完成 |
| EMA200 | base | 0/4 | 15,802.81 | 前缀 +58.028% | 9.510% | 2021-01-08 11:00Z gross 违例后停止 |
| EMA200 | stress | 0/4 | 15,739.90 | 前缀 +57.399% | 9.563% | 2021-01-08 11:00Z gross 违例后停止 |

EMA 每个情景在同一时刻触及绝对 gross 上限：gross 10,266.04 USDT，对 10,000 上限超出 266.04 USDT；当时 NAV 分别约 15,802.81（base）与 15,739.90（stress），BTC、ETH、SOL 均有持仓。保留的只是违例前缀，NAV 含未平仓仓位浮动损益。该停止不是亏损、爆仓或信号失败，也不能把前缀 +58% 说成全年或全期收益；本轮不通过事后缩仓挽救 EMA。

BB 的 5% / 10% / 20% 回撤带只作诊断：base 与 stress 均触及 5%，均未触及 10% 或 20%。EMA 有效前缀也触及 5%，未触及 10% 或 20%。这些不是风险限额通过或资金安全证明。

5.295 年完整样本的累计回报不是年化收益。按端点计算的几何等值年化约为 base 6.26%、stress 5.73%；这是把完整期累计回报换算成等值年率的描述值，不是本策略复利增长率或未来年收益。账户的三币固定入场槽位不复利、不随权益增长。按事件账本 gross-hours 计算，base 全期平均标记 gross 约 482 USDT（约初始 NAV 的 4.8%），三币合计持仓时间占三币可评分总时长约 11.0%，其余时间主要持有现金；不得按平均占用率反推可杠杆倍增收益。EMA 因未完成全期不计算全期年化。

## BB 主路径详细描述

主路径取 `stop_after_fill_primary` 与 conservative funding；同时保留全部敏感性结果，不据此挑选优胜情景。两种 same-bar 路径在这批输出中相同；favorable funding 相对 conservative 使整个窗口模型 funding 现金流改善约 4.53 USDT。有限情景结果接近，仍不证明场内实际的 stop、资金费或执行顺序。

| 项目 | Base | Stress |
|---|---:|---:|
| 参考价损益 | 4,595.72 | 4,595.72 |
| 扣除模型滑点后的成交价损益 | 4,414.76 | 4,052.82 |
| 双边手续费合计 | 180.97 | 180.96 |
| 嵌入成交价的滑点 | 180.97 | 542.90 |
| 模型 funding 现金流 | -441.23 | -441.23 |
| 期末 NAV / 净增额 | 13,792.56 / +3,792.56 | 13,430.63 / +3,430.63 |

Base 的事件账本关系为：4,414.76 成交价损益 −180.97 手续费 −441.23 模型资金费 ≈3,792.56 净增额。模型资金费不是观察到的钱包实际收付；slippage 已嵌入成交价，另列只为归因，没有重复扣减。Stress 比 base 多约 361.93 USDT 滑点成本。所有场景成本未经交易所费率、价差、冲击或成交质量校准。

BB base 主路径共 134 笔已平仓交易：55 笔净盈利、79 笔净亏损；净交易胜率 41.04%，Profit Factor 为 1.78（净盈利交易额合计 / 净亏损绝对额合计）。最佳单笔 +726.03 USDT，最差单笔 -260.84 USDT；前五笔盈利贡献所有盈利交易净额的 30.93%。盈利集中度作为趋势策略描述项保留，不以少数赢家本身否定策略。完整盘中 MAE/MFE 不可由这些观察重建，列为 N/A。

作为事后风险描述，主审另以每笔持仓期间可用的 H1 真实 mark close 相对模型入场成交价计算离散 excursion（以入场名义金额为分母、含零入场锚、不含费用/funding）：134 笔均有观察。Base 最差观测 MAE 为 -13.71%、最大观测 MFE 为 +77.12%；stress 为 -13.80% / +76.94%。见 `root_mark_close_excursion_diagnostic.json` (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/trend_mainline_v1_20261017/loader_schema_v2/root_mark_close_excursion_diagnostic.json`)。它们是单笔离散标记价描述，不是账户回撤，也不是完整盘中 MAE/MFE 的界限；在下个 mark 发布前退出的价格路径仍不可观测。本补充不用于重新筛选策略或调整参数。

主审另从保存的逐笔交易和 NAV 复算这些描述量，见 `root_descriptive_metric_check.json` (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/trend_mainline_v1_20261017/loader_schema_v2/root_descriptive_metric_check.json`)。Stress 仍为 134 笔、55 盈/79 亏，PF 降为 1.68，最差单笔 -263.29 USDT。两档成本的最大标记名义敞口均为 4,829.39 USDT；最大 gross/NAV 分别为 42.12% 和 42.51%。这是离散事件观察下的仓位暴露，不能代替盘中保证金或清算压力验证。

| 币种 | 净损益 | 占总净增额 | 模型 funding | 手续费 | 标记 gross-hours |
|---|---:|---:|---:|---:|---:|
| BTCUSDT | 1,035.31 | 27.3% | -118.55 | 64.66 | 8,412,957 |
| ETHUSDT | 1,865.58 | 49.2% | -190.35 | 58.39 | 7,717,798 |
| SOLUSDT | 891.66 | 23.5% | -132.33 | 57.91 | 6,226,974 |

三币在全期的净贡献都为正，不能推成逐币逐年稳定；例如组合 2022 年连续 NAV 回报为 -0.19%（该年最大回撤 -7.94%）。年度逐币费用、模型 funding 与 gross-hours 由主审补充复算，见独立复核文件；其中按退出年列示的逐币 closed PnL 不是年度 mark-to-market 回报。

年内和月内 NAV 持续跨期、不重置钱包。年度收益率以该年期初 NAV 为分母，年度 MDD 以同一个年初 NAV 作局部锚；2020 为窗口起始后的部分年度。月度最差为 2020-11（-3.88%），最佳为 2023-10（+9.97%），64 个报告月份中 29 个为负（包含起始部分月份）。

| 年份 | 期初 NAV | 期末 NAV | 年度净变化 | 年内最大回撤 |
|---|---:|---:|---:|---:|
| 2020 部分年 | 10,000.00 | 9,668.14 | -3.32% | -5.62% |
| 2021 | 9,668.14 | 10,676.67 | +10.43% | -8.50% |
| 2022 | 10,676.67 | 10,656.16 | -0.19% | -7.94% |
| 2023 | 10,656.16 | 12,022.41 | +12.82% | -5.21% |
| 2024 | 12,022.41 | 13,111.52 | +9.06% | -2.72% |
| 2025 | 13,111.52 | 13,792.56 | +5.19% | -2.79% |

边界统计使用新可用 mark 快照（边界时刻、funding/fill 之前）关闭前一期；同刻资金费和成交计入后一期。主审独立事件复核另行计算了按年逐币手续费、funding 和 gross-hours，见 `root_independent_reconciliation.json` (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/trend_mainline_v1_20261017/loader_schema_v2/root_independent_reconciliation.json`) 中 `annual_symbol_cashflow_and_exposure`。逐币 closed PnL 按退出年份归类，不能当作该年度持仓收益或 NAV 收益。

## 九门结论

两份逐策略九门报告分别列出 gate 状态、证据与缺项：`EMA200_4H_validation.md` (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/trend_mainline_v1_20261017/loader_schema_v2/EMA200_4H_validation.md`)、`BB120_EMA200_ATR3_4H_validation.md` (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/trend_mainline_v1_20261017/loader_schema_v2/BB120_EMA200_ATR3_4H_validation.md`)。两者均为 `EXPLORATORY / UNVERIFIED`。完整样本 OOS return、OOS Sharpe 均为 N/A（没有经证明的 untouched OOS）；没有杠杆分层、保证金/强平路径、模拟观察或真实成交记录，不能声称通过后续 gate。清算距离 N/A；完整盘中 MAE/MFE 与最差 OOS 月/笔 N/A。BB 的事后 H1 mark-close excursion 仅为另列描述量。

主审独立算术复核通过并不等同于独立信号复现。最终新增专项检查为 **24 passed**；全量检查为 **4,558 passed、7 failed、1 skipped**，用时 36 分 56 秒。7 个失败节点及原因与前一轮保留问题完全一致：5 项旧注册表身份/严格追加检查、2 项旧 channel ML 的 `7 == 9` 断言；没有新增失败，也不能称全项目全绿。完整记录见 `final_validation_receipt.json` (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/trend_mainline_v1_20261017/maintenance/final_validation_receipt.json`)。

已按项目顺序执行本地副本核验、转换、清单和报告生成：退出码依次为 1、3、0、0。前两项保留既有的 139 项中 54 项未独立验证的问题，转换继续拒绝这些旧输入，没有放宽约束。本研究选中的 9 份原始源、3 份规范标记价文件已再次核对哈希；65 份运行输出以及代码、协议、预检、冻结依据的身份检查均通过。没有覆盖旧冻结材料，也没有把全局数据准入失败改成通过。

条件性第二线的本地现货/永续数据可行性说明在 `../../../../docs/CONDITIONAL_CARRY_LOCAL_FEASIBILITY_20261017.md` (`provenance:nonincluded/crypto-leverage/docs/CONDITIONAL_CARRY_LOCAL_FEASIBILITY_20261017.md`)；本报告没有进行现货转换或 carry 收益计算。

## 本轮之后的研究顺序

第一主线继续保留这两条简单规则，优先解决共同的仓位管理问题。下一独立版本应先规定持仓升值后的减仓/敞口处理和相应成本，再比较连续账户；本轮不追溯补上减仓、不提高上限、不挑一个更小槽位补跑。BB 的正历史净额支持保留候选，但 EMA 基准提前停止意味着尚未完成全期相对优劣判断。新增仓位政策在已暴露历史上只能形成诊断证据，不能充当新的样本外发现。

条件性第二主线先限 BTC、ETH 同币种现货多头与永续空头。48 份本地现货档案的校验和时间网格初查通过，接下来仍需完整来源冻结、价格字段检查、两腿时钟对齐以及与永续项目分离的数据范围。经济研究必须同时记四次成交成本、基差变化、原生 funding 和全部资本占用；缺真实执行资料时，只能给成本敏感性和盈亏平衡条件，不能把某档假设命名为实际可实现净收益。

两条主线都缺真正未影响策略选择的后续验证资料。本轮不因此扩大参数搜索，也不把已用过的 2026 数据重新命名为独立样本外。
