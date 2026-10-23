> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 非Core三信号组合 v4：已曝光历史净增量诊断

**结论：EXPLORATORY。** 本轮对四个预先固定的组合做历史条件比较，不是未触碰OOS，也不证明有效性或可交易性。2021–2025及成分规则此前均已暴露，早期搜索次数未知。历史经济筛选通过者：无；经济加稳定性筛选通过者：无。即使全部预设历史门槛通过，仍不能称为策略有效或可部署。

每项结果是独立7日事件平均，按固定参考资本1美元（0.5美元名义多BTC、0.5美元名义空入选币篮子）换算为百分点；不年化、不复利，不是连续账户回报。美元平衡不等于beta中性，组合没有据此建模beta对冲；次要残差IC也不会让篮子变成beta中性。Q5和ALL活动时持有相同BTC多头，因此Q5−ALL主要反映空头山寨币选择。净收益均值只在对应主比较可核实配对样本中报告，不能理解为完整计划期无条件利润。

## 冻结方法与判定线

候选池沿用历史动态规则：至少120个前置日数据、此前91日覆盖完整、此前30日平均日USDT成交额至少1,000万美元，按成交额取前60名；BTC、ETH、SOL、BNB不进入空头。日期为257个周一00:00 UTC决策点，输入截至前一日；2025最后决策日为12月1日、计划退出日为12月8日，因此并非完整2025年。源特征为MAX（前7个已完成日最大日对数收益）、SKEW（前30日简单收益的总体偏度）和WEAK（前7日简单收益的相反数）。在同日共同候选池内按平均并列秩变成0–1百分位 `u=(average_rank−1)/(n−1)`，再用下表四种冻结公式评分并重新分五分位；取最高Q5。少于10只时按预先规则记为无仓，主差值中计零敞口。

决策时点为周一00:00 UTC，入场为该时点后一小时，持有7日。主区间来自2,000次循环排期周区块bootstrap（种子20261014、基准4周），缺失排期保留在重抽样中。主筛选要求2024与2025每年均至少26个已知配对周；20bp/边均值和95%下界为正、四组合Holm校正p<0.05，且50bp/边均值也为正。稳定性还要求2/8周区块、四个半年及逐年剔除最好三周均通过设计门槛。完整规则见冻结设计 (`provenance:nonincluded/crypto-leverage/docs/BTC_NONCORE_COMBINATION_V4_20261014.md`)。

主配对要求ALL有仓、扣交易成本后的价格收益和逐笔资金事件均核实；组合可有仓且同样核实，或按设计预先声明空仓并计为零敞口。未知退出或资金费周保持未知，不当作零。有效配对仍可能因缺失退出/资金窗口而产生样本选择偏差。费用为每腿实际名义本金每边20/50bp的假设成本，不是观察到的交易费率或成交证据。

资金按已观察结算事件计入，事件窗口为 `entry < fundingTime <= exit`，使用事件记录中的 `fundingRate` 与 `markPrice`；多头现金流为 `−q×markPrice×fundingRate`，空头为 `+q×markPrice×fundingRate`。当费率为负时，两种持仓的现金流方向都会反转。只有完整且窗口对账通过的事件篮子可列为净收益可核实。事件字段定义见[Binance官方Funding Rate History文档](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data#get-funding-rate-history)。

## 四个候选：先看主结果

下表只列预设20bp/边的主指标：组合Q5减同池ALL，单位为每1美元参考资本的百分点/独立7日事件。区间为冻结的95%循环区块bootstrap区间；稳定性列要求两年经济筛选及全部预设稳定性项目通过。它是历史候选摘要，不是择优或有效性结论。

| 冻结组合 | 合成公式 | 2024均值 [95%区间] | 2025均值 [95%区间] | 两年合并稳定性 |
|---|---|---:|---:|---|
| 三信号等权 (`C1_EQUAL3`) | `(u_MAX + u_SKEW + u_WEAK) / 3` | -0.313 [-0.792, +0.165] | +0.841 [+0.301, +1.330] | 未通过/证据不足 |
| 近期弱势权重50% (`C2_WEAK50`) | `0.25*u_MAX + 0.25*u_SKEW + 0.50*u_WEAK` | +0.372 [-0.117, +0.941] | +0.924 [+0.395, +1.514] | 未通过/证据不足 |
| 三项共同确认 (`C3_MIN3`) | `min(u_MAX, u_SKEW, u_WEAK)` | +0.305 [-0.141, +0.805] | +0.480 [-0.029, +1.042] | 未通过/证据不足 |
| 风险信号与弱势交互 (`C4_RISK_X_WEAK`) | `((u_MAX + u_SKEW) / 2) * u_WEAK` | +0.477 [-0.018, +0.991] | +0.699 [+0.107, +1.312] | 未通过/证据不足 |

50bp/边的2024样本中，以下组合的Q5绝对净均值为负、但相对ALL差值为正：近期弱势权重50%（Q5 -0.225pp，差值 +0.374pp）、三项共同确认（Q5 -0.293pp，差值 +0.306pp）、风险信号与弱势交互（Q5 -0.120pp，差值 +0.479pp）。这表示相对基准较好，不表示篮子本身盈利。20bp/边主样本中，四组合的资金贡献差在2024和2025均为负；观察资金事件降低了相对净增量，不能把增量描述为资金费补贴。 50bp/边下Q5自身绝对均值及对应相对差值见下方明细；正的相对差不保证绝对净收益为正，也不表示连续账户盈利。

## 全期已知、未知和空仓覆盖

未知分类区分组合端价格、组合端资金、ALL端价格和ALL端资金原因；双方预定无仓从主配对中单列。只有ALL有仓且净收益可核实、组合结果可核实（包括预定空仓零敞口）时进入配对样本。

| 组合 | 年 | 计划周 | ALL有仓 | ALL净收益可核实 | 主配对已知 | 组合有仓且配对已知 | 组合预定空仓且配对已知 | 未知（组合价/资/不可用；ALL价/资/不可用） | ALL无仓/双方无仓 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C1_EQUAL3 | 2021 | 52 | 52 | 0 | 0 | 0 | 0 | 52 (Q价0/Q资0/Q不可用0/ALL价1/ALL资51/ALL不可用0) | 0 / 双方0 |
| C1_EQUAL3 | 2022 | 52 | 52 | 0 | 0 | 0 | 0 | 52 (Q价0/Q资0/Q不可用0/ALL价13/ALL资39/ALL不可用0) | 0 / 双方0 |
| C1_EQUAL3 | 2023 | 52 | 52 | 6 | 6 | 6 | 0 | 46 (Q价0/Q资0/Q不可用0/ALL价2/ALL资44/ALL不可用0) | 0 / 双方0 |
| C1_EQUAL3 | 2024 | 53 | 53 | 44 | 44 | 44 | 0 | 9 (Q价0/Q资0/Q不可用0/ALL价9/ALL资0/ALL不可用0) | 0 / 双方0 |
| C1_EQUAL3 | 2025 | 48 | 48 | 30 | 30 | 30 | 0 | 18 (Q价0/Q资0/Q不可用0/ALL价18/ALL资0/ALL不可用0) | 0 / 双方0 |
| C2_WEAK50 | 2021 | 52 | 52 | 0 | 0 | 0 | 0 | 52 (Q价0/Q资0/Q不可用0/ALL价1/ALL资51/ALL不可用0) | 0 / 双方0 |
| C2_WEAK50 | 2022 | 52 | 52 | 0 | 0 | 0 | 0 | 52 (Q价0/Q资0/Q不可用0/ALL价13/ALL资39/ALL不可用0) | 0 / 双方0 |
| C2_WEAK50 | 2023 | 52 | 52 | 6 | 6 | 6 | 0 | 46 (Q价0/Q资0/Q不可用0/ALL价2/ALL资44/ALL不可用0) | 0 / 双方0 |
| C2_WEAK50 | 2024 | 53 | 53 | 44 | 44 | 44 | 0 | 9 (Q价0/Q资0/Q不可用0/ALL价9/ALL资0/ALL不可用0) | 0 / 双方0 |
| C2_WEAK50 | 2025 | 48 | 48 | 30 | 30 | 30 | 0 | 18 (Q价0/Q资0/Q不可用0/ALL价18/ALL资0/ALL不可用0) | 0 / 双方0 |
| C3_MIN3 | 2021 | 52 | 52 | 0 | 0 | 0 | 0 | 52 (Q价0/Q资0/Q不可用0/ALL价1/ALL资51/ALL不可用0) | 0 / 双方0 |
| C3_MIN3 | 2022 | 52 | 52 | 0 | 0 | 0 | 0 | 52 (Q价0/Q资0/Q不可用0/ALL价13/ALL资39/ALL不可用0) | 0 / 双方0 |
| C3_MIN3 | 2023 | 52 | 52 | 6 | 6 | 6 | 0 | 46 (Q价0/Q资0/Q不可用0/ALL价2/ALL资44/ALL不可用0) | 0 / 双方0 |
| C3_MIN3 | 2024 | 53 | 53 | 44 | 44 | 44 | 0 | 9 (Q价0/Q资0/Q不可用0/ALL价9/ALL资0/ALL不可用0) | 0 / 双方0 |
| C3_MIN3 | 2025 | 48 | 48 | 30 | 30 | 30 | 0 | 18 (Q价0/Q资0/Q不可用0/ALL价18/ALL资0/ALL不可用0) | 0 / 双方0 |
| C4_RISK_X_WEAK | 2021 | 52 | 52 | 0 | 0 | 0 | 0 | 52 (Q价0/Q资0/Q不可用0/ALL价1/ALL资51/ALL不可用0) | 0 / 双方0 |
| C4_RISK_X_WEAK | 2022 | 52 | 52 | 0 | 0 | 0 | 0 | 52 (Q价0/Q资0/Q不可用0/ALL价13/ALL资39/ALL不可用0) | 0 / 双方0 |
| C4_RISK_X_WEAK | 2023 | 52 | 52 | 6 | 6 | 6 | 0 | 46 (Q价0/Q资0/Q不可用0/ALL价2/ALL资44/ALL不可用0) | 0 / 双方0 |
| C4_RISK_X_WEAK | 2024 | 53 | 53 | 44 | 44 | 44 | 0 | 9 (Q价0/Q资0/Q不可用0/ALL价9/ALL资0/ALL不可用0) | 0 / 双方0 |
| C4_RISK_X_WEAK | 2025 | 48 | 48 | 30 | 30 | 30 | 0 | 18 (Q价0/Q资0/Q不可用0/ALL价18/ALL资0/ALL不可用0) | 0 / 双方0 |

## 主净增量结果

主指标为组合Q5减同一特征共同池ALL的扣资金后净收益差。表中Q5、ALL及差值都使用同一组净收益可核实配对周；金额显示为每1美元参考资本的百分点/7日事件。区间为保留缺失排期的循环区块bootstrap 95%区间；四个组合内按年份分别Holm校正，50bp行的Holm留空是因为预定检验仅针对20bp。

| 组合 | 年 | bp/边 | Q5净收益均值 | ALL净收益均值 | Q5−ALL均值 [95%区间] | 中位数 | 正周占比 | 最差配对周差值 | Q5最差周（配对） | n | Holm p | 价格净差 | 资金贡献差 | 覆盖/状态计数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| C1_EQUAL3 | 2024 | 20 | -0.309 | +0.005 | -0.313 [-0.792, +0.165] | 中位 -0.079 | 正周 45.5% | 最差差值 -5.712 | 配对样本Q5最差周 -8.747 | 44 | 0.9000 | -0.267 | -0.046 | 44/53 known pairs / ALL-active weeks; Q5 active-known 44, 预定空仓-known 0, 未知 9, ALL双空仓 0 |
| C1_EQUAL3 | 2024 | 50 | -0.913 | -0.599 | -0.314 [-0.794, +0.166] | 中位 -0.079 | 正周 45.5% | 最差差值 -5.729 | 配对样本Q5最差周 -9.394 | 44 | — | -0.268 | -0.046 | 44/53 known pairs / ALL-active weeks; Q5 active-known 44, 预定空仓-known 0, 未知 9, ALL双空仓 0 |
| C1_EQUAL3 | 2025 | 20 | +0.892 | +0.051 | +0.841 [+0.301, +1.330] | 中位 +0.764 | 正周 63.3% | 最差差值 -3.031 | 配对样本Q5最差周 -5.258 | 30 | 0.0020 | +1.134 | -0.293 | 30/48 known pairs / ALL-active weeks; Q5 active-known 30, 预定空仓-known 0, 未知 18, ALL双空仓 0 |
| C1_EQUAL3 | 2025 | 50 | +0.300 | -0.545 | +0.845 [+0.302, +1.336] | 中位 +0.766 | 正周 63.3% | 最差差值 -3.039 | 配对样本Q5最差周 -5.871 | 30 | — | +1.137 | -0.293 | 30/48 known pairs / ALL-active weeks; Q5 active-known 30, 预定空仓-known 0, 未知 18, ALL双空仓 0 |
| C2_WEAK50 | 2024 | 20 | +0.377 | +0.005 | +0.372 [-0.117, +0.941] | 中位 +0.411 | 正周 63.6% | 最差差值 -5.881 | 配对样本Q5最差周 -10.184 | 44 | 0.2639 | +0.379 | -0.007 | 44/53 known pairs / ALL-active weeks; Q5 active-known 44, 预定空仓-known 0, 未知 9, ALL双空仓 0 |
| C2_WEAK50 | 2024 | 50 | -0.225 | -0.599 | +0.374 [-0.117, +0.943] | 中位 +0.412 | 正周 63.6% | 最差差值 -5.898 | 配对样本Q5最差周 -10.835 | 44 | — | +0.380 | -0.007 | 44/53 known pairs / ALL-active weeks; Q5 active-known 44, 预定空仓-known 0, 未知 9, ALL双空仓 0 |
| C2_WEAK50 | 2025 | 20 | +0.975 | +0.051 | +0.924 [+0.395, +1.514] | 中位 +1.068 | 正周 73.3% | 最差差值 -2.594 | 配对样本Q5最差周 -6.114 | 30 | 0.0090 | +0.969 | -0.044 | 30/48 known pairs / ALL-active weeks; Q5 active-known 30, 预定空仓-known 0, 未知 18, ALL双空仓 0 |
| C2_WEAK50 | 2025 | 50 | +0.382 | -0.545 | +0.927 [+0.397, +1.518] | 中位 +1.071 | 正周 73.3% | 最差差值 -2.602 | 配对样本Q5最差周 -6.726 | 30 | — | +0.971 | -0.044 | 30/48 known pairs / ALL-active weeks; Q5 active-known 30, 预定空仓-known 0, 未知 18, ALL双空仓 0 |
| C3_MIN3 | 2024 | 20 | +0.309 | +0.005 | +0.305 [-0.141, +0.805] | 中位 +0.270 | 正周 56.8% | 最差差值 -4.986 | 配对样本Q5最差周 -9.289 | 44 | 0.2639 | +0.308 | -0.003 | 44/53 known pairs / ALL-active weeks; Q5 active-known 44, 预定空仓-known 0, 未知 9, ALL双空仓 0 |
| C3_MIN3 | 2024 | 50 | -0.293 | -0.599 | +0.306 [-0.142, +0.807] | 中位 +0.271 | 正周 56.8% | 最差差值 -5.000 | 配对样本Q5最差周 -9.937 | 44 | — | +0.308 | -0.003 | 44/53 known pairs / ALL-active weeks; Q5 active-known 44, 预定空仓-known 0, 未知 9, ALL双空仓 0 |
| C3_MIN3 | 2025 | 20 | +0.531 | +0.051 | +0.480 [-0.029, +1.042] | 中位 +0.191 | 正周 60.0% | 最差差值 -2.627 | 配对样本Q5最差周 -8.970 | 30 | 0.0445 | +0.505 | -0.025 | 30/48 known pairs / ALL-active weeks; Q5 active-known 30, 预定空仓-known 0, 未知 18, ALL双空仓 0 |
| C3_MIN3 | 2025 | 50 | -0.063 | -0.545 | +0.482 [-0.029, +1.045] | 中位 +0.191 | 正周 60.0% | 最差差值 -2.635 | 配对样本Q5最差周 -9.591 | 30 | — | +0.506 | -0.025 | 30/48 known pairs / ALL-active weeks; Q5 active-known 30, 预定空仓-known 0, 未知 18, ALL双空仓 0 |
| C4_RISK_X_WEAK | 2024 | 20 | +0.482 | +0.005 | +0.477 [-0.018, +0.991] | 中位 +0.467 | 正周 68.2% | 最差差值 -5.881 | 配对样本Q5最差周 -10.184 | 44 | 0.1439 | +0.482 | -0.005 | 44/53 known pairs / ALL-active weeks; Q5 active-known 44, 预定空仓-known 0, 未知 9, ALL双空仓 0 |
| C4_RISK_X_WEAK | 2024 | 50 | -0.120 | -0.599 | +0.479 [-0.019, +0.994] | 中位 +0.469 | 正周 68.2% | 最差差值 -5.898 | 配对样本Q5最差周 -10.835 | 44 | — | +0.483 | -0.005 | 44/53 known pairs / ALL-active weeks; Q5 active-known 44, 预定空仓-known 0, 未知 9, ALL双空仓 0 |
| C4_RISK_X_WEAK | 2025 | 20 | +0.750 | +0.051 | +0.699 [+0.107, +1.312] | 中位 +0.804 | 正周 70.0% | 最差差值 -2.594 | 配对样本Q5最差周 -6.458 | 30 | 0.0290 | +0.747 | -0.048 | 30/48 known pairs / ALL-active weeks; Q5 active-known 30, 预定空仓-known 0, 未知 18, ALL双空仓 0 |
| C4_RISK_X_WEAK | 2025 | 50 | +0.156 | -0.545 | +0.701 [+0.108, +1.315] | 中位 +0.807 | 正周 70.0% | 最差差值 -2.602 | 配对样本Q5最差周 -7.098 | 30 | — | +0.749 | -0.048 | 30/48 known pairs / ALL-active weeks; Q5 active-known 30, 预定空仓-known 0, 未知 18, ALL双空仓 0 |

价格净差已扣相同费率；资金贡献差是两篮子实际观测资金现金流之差。二者相加应等于扣资金后净增量，提供归因核查，不代表前瞻归因。中位数、正周占比、最差配对差值与配对样本Q5最差周都是周事件描述；正周占比不是实际交易胜率。Q5最差周只在主配对的同一周集合计算，不代表全部单独已知Q5周的极值。相对增量为正不代表Q5绝对盈利；请并读Q5和ALL净收益均值。

20bp与50bp为独立假设费率情景；主差值是相对对照，不应替代逐费率检查Q5自身绝对净收益均值。

## 全部可核实Q5周的单篮子风险诊断

下表在各组合所有有仓、价格端点和资金事件均可核实的Q5周中，独立统计最差单周净收益；不要求ALL同周可核实。因此样本数可多于主配对，日期和极值不进入经济筛选、不构成连续账户回撤或成交笔数。

| 组合 | 年 | bp/边 | 净收益可核实Q5周数 | 最差单周净收益（pp） | 决策日 |
|---|---:|---:|---:|---:|---|
| C1_EQUAL3 | 2024 | 20 | 52 | -8.747 | 2024-03-04 |
| C1_EQUAL3 | 2024 | 50 | 52 | -9.394 | 2024-03-04 |
| C1_EQUAL3 | 2025 | 20 | 41 | -5.258 | 2025-02-10 |
| C1_EQUAL3 | 2025 | 50 | 41 | -5.871 | 2025-02-10 |
| C2_WEAK50 | 2024 | 20 | 49 | -10.184 | 2024-02-12 |
| C2_WEAK50 | 2024 | 50 | 49 | -10.835 | 2024-02-12 |
| C2_WEAK50 | 2025 | 20 | 42 | -9.384 | 2025-05-05 |
| C2_WEAK50 | 2025 | 50 | 42 | -10.041 | 2025-05-05 |
| C3_MIN3 | 2024 | 20 | 51 | -9.289 | 2024-02-12 |
| C3_MIN3 | 2024 | 50 | 51 | -9.937 | 2024-02-12 |
| C3_MIN3 | 2025 | 20 | 45 | -9.271 | 2025-05-05 |
| C3_MIN3 | 2025 | 50 | 45 | -9.928 | 2025-05-05 |
| C4_RISK_X_WEAK | 2024 | 20 | 51 | -10.184 | 2024-02-12 |
| C4_RISK_X_WEAK | 2024 | 50 | 51 | -10.835 | 2024-02-12 |
| C4_RISK_X_WEAK | 2025 | 20 | 42 | -9.245 | 2025-05-05 |
| C4_RISK_X_WEAK | 2025 | 50 | 42 | -9.903 | 2025-05-05 |

## 预设稳定性门槛

| 组合 | 年 | 年度经济筛选 | 2/8周区块长度：95%下界 / Holm p | 半年配对周数 / 均值 | 逐年剔除最佳三周 | 全局两年合并结果（重复列示） |
|---|---:|---|---|---|---|---|
| C1_EQUAL3 | 2024 | FAIL_OR_INSUFFICIENT_EVIDENCE | 2周 -0.856 / pHolm=0.8861；8周 -0.729 / pHolm=0.9295 | H1 26周/-0.207pp/INSUFFICIENT_EVIDENCE_OR_FAIL；H2 18周/-0.466pp/INSUFFICIENT_EVIDENCE_OR_FAIL | 移除3周后 -0.574pp / FAIL_OR_INSUFFICIENT_EVIDENCE | FAIL_OR_INSUFFICIENT_EVIDENCE |
| C1_EQUAL3 | 2025 | PASS_SCREEN | 2周 +0.245 / pHolm=0.0135；8周 +0.469 / pHolm=0.0020 | H1 13周/+0.483pp/PASS_SCREEN；H2 17周/+1.115pp/PASS_SCREEN | 移除3周后 +0.489pp / PASS_SCREEN | FAIL_OR_INSUFFICIENT_EVIDENCE |
| C2_WEAK50 | 2024 | FAIL_OR_INSUFFICIENT_EVIDENCE | 2周 -0.202 / pHolm=0.3643；8周 -0.076 / pHolm=0.2249 | H1 26周/+0.155pp/PASS_SCREEN；H2 18周/+0.686pp/PASS_SCREEN | 移除3周后 +0.031pp / PASS_SCREEN | FAIL_OR_INSUFFICIENT_EVIDENCE |
| C2_WEAK50 | 2025 | PASS_SCREEN | 2周 +0.403 / pHolm=0.0040；8周 +0.448 / pHolm=0.0030 | H1 13周/+0.682pp/PASS_SCREEN；H2 17周/+1.109pp/PASS_SCREEN | 移除3周后 +0.636pp / PASS_SCREEN | FAIL_OR_INSUFFICIENT_EVIDENCE |
| C3_MIN3 | 2024 | FAIL_OR_INSUFFICIENT_EVIDENCE | 2周 -0.199 / pHolm=0.3643；8周 -0.106 / pHolm=0.2249 | H1 26周/+0.050pp/PASS_SCREEN；H2 18周/+0.673pp/PASS_SCREEN | 移除3周后 +0.022pp / PASS_SCREEN | FAIL_OR_INSUFFICIENT_EVIDENCE |
| C3_MIN3 | 2025 | FAIL_OR_INSUFFICIENT_EVIDENCE | 2周 -0.119 / pHolm=0.0680；8周 -0.030 / pHolm=0.0605 | H1 13周/+0.323pp/PASS_SCREEN；H2 17周/+0.600pp/PASS_SCREEN | 移除3周后 +0.161pp / PASS_SCREEN | FAIL_OR_INSUFFICIENT_EVIDENCE |
| C4_RISK_X_WEAK | 2024 | FAIL_OR_INSUFFICIENT_EVIDENCE | 2周 -0.104 / pHolm=0.2639；8周 +0.020 / pHolm=0.1259 | H1 26周/+0.236pp/PASS_SCREEN；H2 18周/+0.826pp/PASS_SCREEN | 移除3周后 +0.129pp / PASS_SCREEN | FAIL_OR_INSUFFICIENT_EVIDENCE |
| C4_RISK_X_WEAK | 2025 | PASS_SCREEN | 2周 +0.106 / pHolm=0.0260；8周 +0.191 / pHolm=0.0270 | H1 13周/+0.648pp/PASS_SCREEN；H2 17周/+0.738pp/PASS_SCREEN | 移除3周后 +0.406pp / PASS_SCREEN | FAIL_OR_INSUFFICIENT_EVIDENCE |

半年需至少10个配对周且均值为正；不足属于证据不足。稳定性要求年度经济筛选与两个替代区块长度、四个半年、逐年去除最佳三周都通过。经济加稳定性筛选通过组合：无。年份、半年均是已曝光历史。

## 池覆盖、信号冗余和入选集中度

下面的候选数按每个排期汇总；不存在特征值时保留缺失，不做补值。原始N与特征共同池N来自结果盲覆盖表。资金和端点可知配对比例另见主结果计数。

| 组合 | 排期数 | 原始候选总数 | 特征共同池总数 | 特征可用排期 |
|---|---:|---:|---:|---:|
| C1_EQUAL3 | 257 | 15354 | 15354 | 257 |
| C2_WEAK50 | 257 | 15354 | 15354 | 257 |
| C3_MIN3 | 257 | 15354 | 15354 | 257 |
| C4_RISK_X_WEAK | 257 | 15354 | 15354 | 257 |

成分秩相关（按周Spearman的全期均值）：MAX_VS_SKEW 0.281；MAX_VS_WEAK -0.524；SKEW_VS_WEAK -0.068

| 组合 | 入选过的币种数 | 币周入选数 | 第一名币种占比 | 前十币种占比 |
|---|---:|---:|---:|---:|
| C1_EQUAL3 | 306 | 3091 | 1.49% | 11.32% |
| C2_WEAK50 | 302 | 3085 | 1.46% | 11.15% |
| C3_MIN3 | 289 | 3115 | 1.93% | 14.54% |
| C4_RISK_X_WEAK | 303 | 3067 | 1.53% | 11.61% |

| 组合 | 描述性对照 | 平均Jaccard重叠 | 平均重叠币数 |
|---|---|---:|---:|
| C1_EQUAL3 | L4_MAX7_HIGH | 0.274 | 5.04 |
| C1_EQUAL3 | L9_SKEW30_HIGH | 0.464 | 7.50 |
| C1_EQUAL3 | L1_MOM7 | 0.256 | 4.77 |
| C1_EQUAL3 | M1_IDIO60 | 0.328 | 5.77 |
| C2_WEAK50 | L4_MAX7_HIGH | 0.107 | 2.22 |
| C2_WEAK50 | L9_SKEW30_HIGH | 0.290 | 5.27 |
| C2_WEAK50 | L1_MOM7 | 0.471 | 7.55 |
| C2_WEAK50 | M1_IDIO60 | 0.251 | 4.64 |
| C3_MIN3 | L4_MAX7_HIGH | 0.113 | 2.35 |
| C3_MIN3 | L9_SKEW30_HIGH | 0.185 | 3.64 |
| C3_MIN3 | L1_MOM7 | 0.172 | 3.40 |
| C3_MIN3 | M1_IDIO60 | 0.189 | 3.68 |
| C4_RISK_X_WEAK | L4_MAX7_HIGH | 0.104 | 2.17 |
| C4_RISK_X_WEAK | L9_SKEW30_HIGH | 0.303 | 5.41 |
| C4_RISK_X_WEAK | L1_MOM7 | 0.400 | 6.70 |
| C4_RISK_X_WEAK | M1_IDIO60 | 0.253 | 4.68 |

| 组合 | 最常入选币种（2021–2025历史入选周数；不是当前做空建议） |
|---|---|
| C1_EQUAL3 | RUNEUSDT (46周)、SNXUSDT (39周)、AXSUSDT (37周)、FTMUSDT (36周)、CRVUSDT (35周) |
| C2_WEAK50 | RUNEUSDT (45周)、CRVUSDT (39周)、FTMUSDT (38周)、SNXUSDT (36周)、GALAUSDT (32周) |
| C3_MIN3 | CRVUSDT (60周)、RUNEUSDT (52周)、FTMUSDT (48周)、AVAXUSDT (44周)、INJUSDT (44周) |
| C4_RISK_X_WEAK | RUNEUSDT (47周)、CRVUSDT (46周)、FTMUSDT (38周)、SNXUSDT (36周)、DOGEUSDT (33周) |

MAX与WEAK的横截面秩相关为负，提示极值风险和近周弱势的信号排序存在张力；MAX与SKEW为正相关。相关性只描述特征重叠与机制背景，不解释也不证明任何损益结果。

## 单规则控制与M1描述性对照

这些行是每个冻结控制Q5相对其自身同池ALL的对照结果，使用同样已知配对口径、并列20/50bp每边的未校正区间；它们不能替代每个新组合的主比较，也不据此选赢家。M1在共同池上不完整的日期标为不可用/未知，未转作零仓。

与WEAK单规则（L1_MOM7）的主差值点估计作描述性并列：C2_WEAK50：2024 +0.372pp（WEAK单规则 +0.563pp），2025 +0.924pp（WEAK单规则 +0.627pp）；C4_RISK_X_WEAK：2024 +0.477pp（WEAK单规则 +0.563pp），2025 +0.699pp（WEAK单规则 +0.627pp）。这不是组合相对控制的显著性检验，不用于选赢家或追加模型选择。

| 控制 | 年 | bp/边 | 差值 [未校正95%区间] | n | 配对覆盖 |
|---|---:|---:|---:|---:|---|
| L4_MAX7_HIGH | 2024 | 20 | -0.258 [-0.835, +0.320] | 44 | 44/53 known pairs / ALL-active weeks; Q5 active-known 44, 预定空仓-known 0, 未知 9, ALL双空仓 0 |
| L4_MAX7_HIGH | 2024 | 50 | -0.258 [-0.838, +0.321] | 44 | 44/53 known pairs / ALL-active weeks; Q5 active-known 44, 预定空仓-known 0, 未知 9, ALL双空仓 0 |
| L4_MAX7_HIGH | 2025 | 20 | +0.407 [-0.585, +1.371] | 30 | 30/48 known pairs / ALL-active weeks; Q5 active-known 30, 预定空仓-known 0, 未知 18, ALL双空仓 0 |
| L4_MAX7_HIGH | 2025 | 50 | +0.409 [-0.585, +1.376] | 30 | 30/48 known pairs / ALL-active weeks; Q5 active-known 30, 预定空仓-known 0, 未知 18, ALL双空仓 0 |
| L9_SKEW30_HIGH | 2024 | 20 | -0.290 [-0.873, +0.277] | 44 | 44/53 known pairs / ALL-active weeks; Q5 active-known 44, 预定空仓-known 0, 未知 9, ALL双空仓 0 |
| L9_SKEW30_HIGH | 2024 | 50 | -0.291 [-0.876, +0.278] | 44 | 44/53 known pairs / ALL-active weeks; Q5 active-known 44, 预定空仓-known 0, 未知 9, ALL双空仓 0 |
| L9_SKEW30_HIGH | 2025 | 20 | +0.459 [-0.347, +1.277] | 30 | 30/48 known pairs / ALL-active weeks; Q5 active-known 30, 预定空仓-known 0, 未知 18, ALL双空仓 0 |
| L9_SKEW30_HIGH | 2025 | 50 | +0.462 [-0.347, +1.282] | 30 | 30/48 known pairs / ALL-active weeks; Q5 active-known 30, 预定空仓-known 0, 未知 18, ALL双空仓 0 |
| L1_MOM7 | 2024 | 20 | +0.563 [+0.005, +1.185] | 44 | 44/53 known pairs / ALL-active weeks; Q5 active-known 44, 预定空仓-known 0, 未知 9, ALL双空仓 0 |
| L1_MOM7 | 2024 | 50 | +0.564 [+0.005, +1.189] | 44 | 44/53 known pairs / ALL-active weeks; Q5 active-known 44, 预定空仓-known 0, 未知 9, ALL双空仓 0 |
| L1_MOM7 | 2025 | 20 | +0.627 [+0.019, +1.279] | 30 | 30/48 known pairs / ALL-active weeks; Q5 active-known 30, 预定空仓-known 0, 未知 18, ALL双空仓 0 |
| L1_MOM7 | 2025 | 50 | +0.629 [+0.019, +1.283] | 30 | 30/48 known pairs / ALL-active weeks; Q5 active-known 30, 预定空仓-known 0, 未知 18, ALL双空仓 0 |
| M1_IDIO60 | 2024 | 20 | -0.051 [-0.529, +0.407] | 44 | 44/53 known pairs / ALL-active weeks; Q5 active-known 44, 预定空仓-known 0, 未知 9, ALL双空仓 0 |
| M1_IDIO60 | 2024 | 50 | -0.051 [-0.531, +0.408] | 44 | 44/53 known pairs / ALL-active weeks; Q5 active-known 44, 预定空仓-known 0, 未知 9, ALL双空仓 0 |
| M1_IDIO60 | 2025 | 20 | +0.424 [-0.647, +1.445] | 30 | 30/48 known pairs / ALL-active weeks; Q5 active-known 30, 预定空仓-known 0, 未知 18, ALL双空仓 0 |
| M1_IDIO60 | 2025 | 50 | +0.427 [-0.647, +1.450] | 30 | 30/48 known pairs / ALL-active weeks; Q5 active-known 30, 预定空仓-known 0, 未知 18, ALL双空仓 0 |

次要 BOTH_ACTIVE_ONLY 对照仅描述双方同时有仓的周，不改变主筛选；该表按生产结果的明确estimand报告，不能把空仓周从主样本删除。

| 组合 | 年 | 20bp/边双方有仓均值 [95%区间] | 有效周 |
|---|---:|---:|---:|
| C1_EQUAL3 | 2024 | -0.313 [-0.792, +0.165] | 44 |
| C1_EQUAL3 | 2025 | +0.841 [+0.301, +1.330] | 30 |
| C2_WEAK50 | 2024 | +0.372 [-0.117, +0.941] | 44 |
| C2_WEAK50 | 2025 | +0.924 [+0.395, +1.514] | 30 |
| C3_MIN3 | 2024 | +0.305 [-0.141, +0.805] | 44 |
| C3_MIN3 | 2025 | +0.480 [-0.029, +1.042] | 30 |
| C4_RISK_X_WEAK | 2024 | +0.477 [-0.018, +0.991] | 44 |
| C4_RISK_X_WEAK | 2025 | +0.699 [+0.107, +1.312] | 30 |

## 次要七日IC诊断

Spearman IC按有效决策周平均，要求每周至少30个标签且覆盖原候选数至少80%；净收益篮子必须100%满足所选持仓端点与持仓期资金事件核对。两类诊断的周覆盖口径不同，不能直接对比样本均值。BTC减山寨币和冻结beta调整空头残差是解释性指标，不参与新组合筛选，也不是收益率。

2024的全截面BTC减山寨币IC描述值中，等权C1高于C2与C4（0.0621、0.0372、0.0219）；但C1的目标Q5−ALL主净增量均值为-0.313pp。IC不能替代目标空头尾部的净收益检验；两者口径不同，不作因果解释或新模型选择。

| 规则 | 标签 | 年 | 平均IC | 有效周 / 排期周 |
|---|---|---:|---:|---:|
| C1_EQUAL3 | future_btc_minus_alt | 2021 | 0.0395 | 52 / 52 |
| C1_EQUAL3 | future_btc_minus_alt | 2022 | 0.0491 | 51 / 52 |
| C1_EQUAL3 | future_btc_minus_alt | 2023 | 0.0281 | 51 / 52 |
| C1_EQUAL3 | future_btc_minus_alt | 2024 | 0.0621 | 52 / 53 |
| C1_EQUAL3 | future_btc_minus_alt | 2025 | 0.1572 | 48 / 48 |
| C1_EQUAL3 | future_short_residual | 2021 | 0.0264 | 52 / 52 |
| C1_EQUAL3 | future_short_residual | 2022 | 0.0225 | 51 / 52 |
| C1_EQUAL3 | future_short_residual | 2023 | 0.0558 | 51 / 52 |
| C1_EQUAL3 | future_short_residual | 2024 | 0.0716 | 52 / 53 |
| C1_EQUAL3 | future_short_residual | 2025 | 0.1388 | 48 / 48 |
| C2_WEAK50 | future_btc_minus_alt | 2021 | -0.0154 | 52 / 52 |
| C2_WEAK50 | future_btc_minus_alt | 2022 | 0.0122 | 51 / 52 |
| C2_WEAK50 | future_btc_minus_alt | 2023 | -0.0187 | 51 / 52 |
| C2_WEAK50 | future_btc_minus_alt | 2024 | 0.0372 | 52 / 53 |
| C2_WEAK50 | future_btc_minus_alt | 2025 | 0.1107 | 48 / 48 |
| C2_WEAK50 | future_short_residual | 2021 | -0.0272 | 52 / 52 |
| C2_WEAK50 | future_short_residual | 2022 | -0.0045 | 51 / 52 |
| C2_WEAK50 | future_short_residual | 2023 | -0.0033 | 51 / 52 |
| C2_WEAK50 | future_short_residual | 2024 | 0.0533 | 52 / 53 |
| C2_WEAK50 | future_short_residual | 2025 | 0.0919 | 48 / 48 |
| C3_MIN3 | future_btc_minus_alt | 2021 | 0.0224 | 52 / 52 |
| C3_MIN3 | future_btc_minus_alt | 2022 | -0.0264 | 51 / 52 |
| C3_MIN3 | future_btc_minus_alt | 2023 | -0.0595 | 51 / 52 |
| C3_MIN3 | future_btc_minus_alt | 2024 | -0.0007 | 52 / 53 |
| C3_MIN3 | future_btc_minus_alt | 2025 | 0.0083 | 48 / 48 |
| C3_MIN3 | future_short_residual | 2021 | 0.0031 | 52 / 52 |
| C3_MIN3 | future_short_residual | 2022 | -0.0469 | 51 / 52 |
| C3_MIN3 | future_short_residual | 2023 | -0.0480 | 51 / 52 |
| C3_MIN3 | future_short_residual | 2024 | 0.0135 | 52 / 53 |
| C3_MIN3 | future_short_residual | 2025 | 0.0003 | 48 / 48 |
| C4_RISK_X_WEAK | future_btc_minus_alt | 2021 | -0.0247 | 52 / 52 |
| C4_RISK_X_WEAK | future_btc_minus_alt | 2022 | -0.0205 | 51 / 52 |
| C4_RISK_X_WEAK | future_btc_minus_alt | 2023 | -0.0566 | 51 / 52 |
| C4_RISK_X_WEAK | future_btc_minus_alt | 2024 | 0.0219 | 52 / 53 |
| C4_RISK_X_WEAK | future_btc_minus_alt | 2025 | 0.0473 | 48 / 48 |
| C4_RISK_X_WEAK | future_short_residual | 2021 | -0.0390 | 52 / 52 |
| C4_RISK_X_WEAK | future_short_residual | 2022 | -0.0349 | 51 / 52 |
| C4_RISK_X_WEAK | future_short_residual | 2023 | -0.0471 | 51 / 52 |
| C4_RISK_X_WEAK | future_short_residual | 2024 | 0.0384 | 52 / 53 |
| C4_RISK_X_WEAK | future_short_residual | 2025 | 0.0284 | 48 / 48 |
| L4_MAX7_HIGH | future_btc_minus_alt | 2021 | 0.0685 | 52 / 52 |
| L4_MAX7_HIGH | future_btc_minus_alt | 2022 | 0.0634 | 51 / 52 |
| L4_MAX7_HIGH | future_btc_minus_alt | 2023 | 0.0668 | 51 / 52 |
| L4_MAX7_HIGH | future_btc_minus_alt | 2024 | 0.0678 | 52 / 53 |
| L4_MAX7_HIGH | future_btc_minus_alt | 2025 | 0.1195 | 48 / 48 |
| L4_MAX7_HIGH | future_short_residual | 2021 | 0.0625 | 52 / 52 |
| L4_MAX7_HIGH | future_short_residual | 2022 | 0.0381 | 51 / 52 |
| L4_MAX7_HIGH | future_short_residual | 2023 | 0.0956 | 51 / 52 |
| L4_MAX7_HIGH | future_short_residual | 2024 | 0.0641 | 52 / 53 |
| L4_MAX7_HIGH | future_short_residual | 2025 | 0.1144 | 48 / 48 |
| L9_SKEW30_HIGH | future_btc_minus_alt | 2021 | 0.0583 | 52 / 52 |
| L9_SKEW30_HIGH | future_btc_minus_alt | 2022 | 0.0542 | 51 / 52 |
| L9_SKEW30_HIGH | future_btc_minus_alt | 2023 | 0.0460 | 51 / 52 |
| L9_SKEW30_HIGH | future_btc_minus_alt | 2024 | 0.0400 | 52 / 53 |
| L9_SKEW30_HIGH | future_btc_minus_alt | 2025 | 0.1228 | 48 / 48 |
| L9_SKEW30_HIGH | future_short_residual | 2021 | 0.0456 | 52 / 52 |
| L9_SKEW30_HIGH | future_short_residual | 2022 | 0.0346 | 51 / 52 |
| L9_SKEW30_HIGH | future_short_residual | 2023 | 0.0699 | 51 / 52 |
| L9_SKEW30_HIGH | future_short_residual | 2024 | 0.0432 | 52 / 53 |
| L9_SKEW30_HIGH | future_short_residual | 2025 | 0.1134 | 48 / 48 |
| L1_MOM7 | future_btc_minus_alt | 2021 | -0.0782 | 52 / 52 |
| L1_MOM7 | future_btc_minus_alt | 2022 | -0.0425 | 51 / 52 |
| L1_MOM7 | future_btc_minus_alt | 2023 | -0.0739 | 51 / 52 |
| L1_MOM7 | future_btc_minus_alt | 2024 | -0.0064 | 52 / 53 |
| L1_MOM7 | future_btc_minus_alt | 2025 | 0.0026 | 48 / 48 |
| L1_MOM7 | future_short_residual | 2021 | -0.0804 | 52 / 52 |
| L1_MOM7 | future_short_residual | 2022 | -0.0415 | 51 / 52 |
| L1_MOM7 | future_short_residual | 2023 | -0.0807 | 51 / 52 |
| L1_MOM7 | future_short_residual | 2024 | 0.0090 | 52 / 53 |
| L1_MOM7 | future_short_residual | 2025 | -0.0128 | 48 / 48 |
| M1_IDIO60 | future_btc_minus_alt | 2021 | 0.0503 | 52 / 52 |
| M1_IDIO60 | future_btc_minus_alt | 2022 | 0.1183 | 51 / 52 |
| M1_IDIO60 | future_btc_minus_alt | 2023 | 0.0726 | 51 / 52 |
| M1_IDIO60 | future_btc_minus_alt | 2024 | 0.0975 | 52 / 53 |
| M1_IDIO60 | future_btc_minus_alt | 2025 | 0.2097 | 48 / 48 |
| M1_IDIO60 | future_short_residual | 2021 | 0.0357 | 52 / 52 |
| M1_IDIO60 | future_short_residual | 2022 | 0.1018 | 51 / 52 |
| M1_IDIO60 | future_short_residual | 2023 | 0.1078 | 51 / 52 |
| M1_IDIO60 | future_short_residual | 2024 | 0.0987 | 52 / 53 |
| M1_IDIO60 | future_short_residual | 2025 | 0.1969 | 48 / 48 |

## 解释边界

- 2021–2023为暴露过的价格历史诊断；资金净收益覆盖不完整时不得按零处理，也不将价格结果称为资金净收益已核实。2024/2025同样已曝光，不能称未触碰测试集。
- 仅保留端点完整且资金事件窗口完全核对的篮子作为“净收益可核实”。缺失资产端点、缺失mark/结算覆盖或未核实窗口使篮子未知；样本均值存在已知样本选择风险。
- 假设费用后价格加严格观测资金事件仍不包含真实盘口、成交、容量、盘中保证金或强平路径。固定参考本金不代表账户杠杆。
- 不计算权益曲线、CAGR、Sharpe、最大回撤、账户收益或交易胜率；周事件占比不是交易胜率。
- 策略门槛即使通过，门1–7证据仍有关键缺口，门8–9没有观察记录。四份完整九门报告位于 `gate_reports/`。

数值manifest状态：`RETROSPECTIVE_EXPLORATORY_NUMERICAL_STAGE_COMPLETE`。独立数值审计见复核说明 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/btc_noncore_combination_v4_20261014/review/independent_numerical_review_attempt_02.md`)（JSON收据 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/btc_noncore_combination_v4_20261014/review/independent_numerical_audit_attempt_02.json`)，SHA256=`22a7e07ca8da0d983f07d03e7c1b1783e8a8cdd01ca7f8da0fdd9bbd75c4ea83`）。审计覆盖episode、608组配对对照、历史筛选、去最佳周压力、4,112条逐日IC、资金事件/腿收据和v3控制复现，未发现不一致；它核实计算与冻结门槛，不是有效性或可交易性判定。根代理全套测试为 `FAIL`：通过4314、失败7、跳过1、警告264，耗时2109.19s (0:35:09)；聚焦目标测试：通过54、失败0、耗时19.48；按序再生退出码：.venv/Scripts/python.exe scripts/fetch_local_source_copies.py --verify=1, .venv/Scripts/python.exe scripts/import_perp_data.py=3, .venv/Scripts/python.exe scripts/build_inventory.py=0, .venv/Scripts/python.exe scripts/build_reports.py=0。失败测试ID与v3基线相同，未增加新的失败ID。 再生限制：Verification reports 54 unverified entries of 139. Import refuses 12 existing Core price copies without independently frozen source identities. Inventory and reports regenerate successfully. No identity pins or registry were weakened to bypass refusal. 详见完整测试状态收据 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/btc_noncore_combination_v4_20261014/review/full_suite_status.json`)。 独立数值复核状态：`ZERO_MISMATCHES`。
