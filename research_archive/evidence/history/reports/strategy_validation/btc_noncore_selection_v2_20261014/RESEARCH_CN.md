> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 多 BTC 空非 Core 山寨币的截面选币研究

2026-10-14（Asia/Shanghai）｜已暴露历史诊断｜研究状态 EXPLORATORY

**本轮补充下载数据并完成五种固定规则的验证。最有信息的是高特质波动率，但没有一种规则通过扣费及资金费后的超额收益标准。** 因此，目前得到的是值得继续研究的选币基准，尚未找到可认定有效的交易策略。

“缺乏实际价值、不回购”的空头逻辑还没有得到完整验证：报告供应增长未通过统计标准，费用与回购历史的跨币覆盖不足。缺记录不能赋值为“零费用、零回购”。

选币统计信息与经济价值 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/btc_noncore_selection_v2_20261014/%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/btc_noncore_selection_v2_20261014/selection_evidence.png`)。资金费记账使用接口返回的真实事件时间和关联标记价格。[Binance 接口说明](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History)。Sky 数据保留提供方单位，不能推成已验证的现金回购或零回购名单。提供方历史 (`provenance:external/9e24ea9a8166f3a4`)。

315 个合约的整个请求期与已有归档相符；另 11 个存在缺月、仅单源事件等问题，匹配时点费率冲突为 0。每个持仓周单独核对所跨月份及事件，窗口之外的缺口不误伤已核实窗口。早期资金费大量缺少结算标记价格，相关净收益保持未知。

## 实际检验的选币方法

每周从原始 623 个候选中，根据当时已完成的过去 30 日日均成交额选最多 60 个币；要求至少 120 个历史日观测、最近 91 个完整日线、日均成交额至少 1000 万 USDT。BTC、ETH、SOL、BNB 属于 Core，不进入空头山寨币池。币池是动态的，但完整历史上市身份仍有证据缺口，不能声称完全消除了生存偏差。

**M1 高特质波动率：** 近 60 个完整日收益剔除 BTC beta 后的残差标准差，越高越优先进入空头候选。

**M2 高特质波动率加弱动量：** 特质波动率与过去 30 日相对 BTC 的弱动量，分别按同一完整特征截面取百分位，等权平均。

**M3 M2 加历史资金费过滤：** 保留 M2 的评分，只允许过去 7 日已观测资金费之和非负且至少有 1 次真实结算的币；未知不当作零。

**F1 报告流通供应增长：** log(S[t−7日]/S[t−97日])，S 为估计流通市值除以同日价格；缺任一端点即缺失。

**F2 低协议费用市值比：** 过去 90 个完整已观测日的协议费用之和，除以同日估计流通市值，再取负号；主滞后 7 日。

M1 的具体分数是最近 60 日日收益减去同期估计 beta × BTC 日收益后，残差的样本标准差。M2 的弱动量为过去 30 日币收益减去 beta × BTC 收益，再取负号。M3 的历史资金费窗口额外滞后 1 小时，沿用已冻结的市场特征，不根据未来 carry 选币。

每周一 00:00 UTC 决策，01:00 UTC 的真实小时开盘价作为研究入场价，持有 7 日。分数最高的约 20% 为 Q5；相同分数不强行拆开。至少 10 个币才建立空头篮子，不足则记录无仓。参考资本为 1，初始多 BTC 0.5、等权空币合计 0.5，持仓数量固定。

决策日期覆盖 2021-01-04 至 2025-12-01，最后一个 7 日持有期截至 2025-12-08。因此下文的 2025 为这段历史回放，不代表完整全年账户收益。

主 IC 是分数与 `决策时 beta × 未来 BTC 收益 − 未来币收益` 的截面秩相关。它衡量相对弱势的排序，不直接等于多空组合收益；实际组合按美元金额平衡，未实现 beta 中性。正式 IC 每周至少需 30 个有效币，且覆盖原 top60 的至少 80%。

## IC 验证结果

| 规则 | 2021—2023 IC（周数） | 2024 IC（周数） | 2025 IC（周数） | 预设统计筛选 |
| :--- | ---: | ---: | ---: | :--- |
| M1 高特质波动率 | 0.081（154） | 0.099（52） | 0.197（48） | PASS |
| M2 高特质波动率加弱动量 | 0.028（154） | 0.039（52） | 0.107（48） | FAIL |
| M3 M2 加历史资金费过滤 | 0.022（72） | 0.062（43） | 0.158（12） | FAIL |
| F1 报告流通供应增长 | 0.022（137） | 0.008（29） | 0.014（38） | FAIL |
| F2 低协议费用市值比 | N/A（0） | N/A（0） | N/A（0） | FAIL |

M1 发现期 IC 的 95% 区间为 [0.050, 0.112]，ICIR 为 0.392，五重检验 Holm p 为 0.00250；2021、2022、2023 的 IC 都为正。它是唯一通过全部预设统计筛选的规则。

M2 的发现期 IC 0.0284 低于预先设定的 0.03，加入弱动量没有通过筛选。M3 的发现期正式样本只有 72 周；2025 仅 12 个正式 IC 周。F1 的 2024 正式样本仅 29 周，且各期信号都很弱。F2 的数据覆盖不足以检验，不能把它判为“没有价值的币已被识别”。

预设统计标准还包括发现期至少 100 周、ICIR≥0.15、95% 下界大于零、至少两个发现年为正，以及 2024 至少 40 周且 IC 为正。区间用保留缺失周位置的 4 周循环分块 bootstrap，2,000 次，固定种子；五个主假设一并做 Holm 修正。

Holm 修正只覆盖本轮五个主假设，没有覆盖此前所有探索的累计选择。统计筛选通过是本轮历史诊断结果，不能解释为一个独立新发现已经得到确认。

## 选币能否增加净收益

比较对象是同一可用特征币池、同一周的全部等权空头篮子，均保留相同 BTC 多头。表中数值为 **Q5 减同币池 ALL 的平均每周净收益增量，单位为百分点**；只比较两者共同有效且有仓的周。使用单边 20bp 费用/滑点假设及已核实的观测资金费。不同规则币池与缺失周不同，不能直接凭均值大小排列优劣。

| 规则 | 2024 净增量；95% 区间；共同周数 | 2025 净增量；95% 区间；共同周数 |
| :--- | :--- | :--- |
| M1 | -0.051；[-0.529, +0.407]；44 周 | +0.424；[-0.647, +1.445]；30 周 |
| M2 | +0.151；[-0.309, +0.757]；44 周 | +0.342；[-0.854, +1.247]；30 周 |
| M3 | +0.318；[-0.199, +0.940]；39 周 | +0.598；[-0.368, +1.524]；8 周 |
| F1 | +0.047；[-0.470, +0.556]；36 周 | +0.133；[-0.445, +0.691]；38 周 |
| F2 | N/A；0 周 | N/A；0 周 |

**没有一项通过预设经济标准。** M1 在 2024 的增量为 −0.051 个百分点；2025 为 +0.424 个百分点，但 95% 区间为 [−0.647, +1.445]，仍包含零。M3 的 2025 只有 8 个共同有效周，不足以支持高置信度结论。

资金费会改变判断：M1 在 2025 仅扣 20bp 成本时，选币增量为 +0.901 个百分点，95% 区间 [0.021, 1.901]；加入已核实资金费后降至 +0.424，区间跨零。这是同一批共同有效周的比较，说明价格排序优势可能被持仓成本侵蚀。其余未知周仍不能忽略。

单边成本提高到 50bp 后，相对增量仍无一在 2024 达到正的区间下界：

| 规则 | 2024 单边 50bp；95% 区间 | 2025 单边 50bp；95% 区间 |
| :--- | :--- | :--- |
| M1 | -0.051；[-0.531, +0.408]；44 周 | +0.427；[-0.647, +1.450]；30 周 |
| M2 | +0.151；[-0.310, +0.759]；44 周 | +0.343；[-0.857, +1.251]；30 周 |
| M3 | +0.319；[-0.199, +0.943]；39 周 | +0.600；[-0.369, +1.529]；8 周 |
| F1 | +0.047；[-0.471, +0.558]；36 周 | +0.134；[-0.446, +0.693]；38 周 |
| F2 | N/A；0 周 | N/A；0 周 |

增量差值的成本敏感性很小，不表示绝对成本很小；两边都付费，退出名义价值不同也会影响两者差值。50bp 下各自绝对净收益下降。

## 收益水平与缺失样本

以下只是已知独立周的描述，包含事前计划无仓周的零收益；未知退出或资金费周保留 N/A。它们不是完整账户的预期收益，不能复利成年化收益、Sharpe 或最大回撤。2021—2023 的净收益已知周太少，不用其均值判断盈利能力。

| 规则 | 年份 | 无仓周 | 净值已知周 / 计划周 | 已知周平均净收益 | 最差已知周 |
| :--- | :--- | ---: | ---: | ---: | ---: |
| M1 | 2024 | 0 | 52/53 | +0.032% | -10.137% |
| M1 | 2025 | 0 | 33/48 | +0.819% | -13.735% |
| M2 | 2024 | 0 | 49/53 | +0.131% | -10.186% |
| M2 | 2025 | 0 | 39/48 | +0.458% | -18.006% |
| M3 | 2024 | 8 | 50/53 | +0.631% | -9.129% |
| M3 | 2025 | 33 | 43/48 | +0.546% | -3.579% |
| F1 | 2024 | 13 | 52/53 | +0.350% | -11.173% |
| F1 | 2025 | 0 | 48/48 | +0.755% | -9.528% |
| F2 | 2024 | 53 | 53/53 | +0.000% | +0.000% |
| F2 | 2025 | 48 | 48/48 | +0.000% | +0.000% |

M1 在 2025 的 48 个计划周中，有 15 周净收益未知。缺失可能与退市和极端行情相关，剔除后剩下的平均收益存在偏差。F2 的零收益来自全部无仓，不能作为策略防守能力的证据。

## 挤空与退出风险

先固定选币，再查看所有原定持仓的小时路径；没有因未来端点无效而重排或删除候选。下表的“币周”是一个币在一个持有周的记录，不是实际成交笔数。

| 规则 | 原定空头币周数 | 端点无效币周数 | 已观测期间上涨超过 100% 的币周数 | 最大单币涨幅 |
| :--- | ---: | ---: | ---: | ---: |
| M1 | 3065 | 36 | 47 | +917.7% |
| M2 | 3091 | 33 | 19 | +917.7% |
| M3 | 1494 | 9 | 8 | +159.9% |
| F1 | 2427 | 18 | 9 | +221.2% |
| F2 | 0 | 0 | 0 | N/A |

M1 曾选到 ALPACA：2025-04-28 01:00 UTC 的真实交易开盘为 0.18057，4 月 30 日 08:00 UTC 小时内交易高点为 1.4763，即相对入场上涨 **717.6%**。该周只观察到 57 根有成交活动的小时线，正常 7 日退出不可用。这个真实的期间高点不能当成期末收益，也不能用最后价格代替强制结算。

高特质波动率既捕捉到相对弱势，也会选到极端挤空币。上表最大涨幅是单币路径；它不等于组合损失、同步账户 MAE 或爆仓概率。不同规则样本数不同，尾部事件次数也不能直接解释为已验证的风险降低。完整同步路径、强制结算、保证金与清算仍待验证。

## 对后续方案的判断

**保留 M1 作为下一阶段的排序基准；目前不将任何一个组合升级为有效策略。** 研究顺序应先补真实可退出性与资金费/同步风险路径，随后在全新未触碰窗口验证，而非继续在 2021—2025 的有利片段中加条件。

用户提出的基本面方向应拆为可证伪的字段：协议实际费用、其中归属代币持有人的金额、已执行回购的金额与时间、已公告且当时可知的流通供应变化。每个字段必须带币身份、单位、时间和覆盖状态；只有明确观测的零值才能记零。当前数据尚不足以合成可靠的“无用途且不回购”横截面分数。供应增长与低费用市值比已经做过本轮固定检验，不能宣称获得支持。

## 验证状态和交付证据

2021—2023 用作发现诊断，2024 为验证诊断，2025 为历史回放。这些年份以前均已查看；本轮冻结五个假设不会使旧历史重新成为未触碰 OOS。

五份完整关卡报告：M1 九关验证 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/btc_noncore_selection_v2_20261014/%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/btc_noncore_m1_selection_v2_20261014.md`)；M2 九关验证 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/btc_noncore_selection_v2_20261014/%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/btc_noncore_m2_selection_v2_20261014.md`)；M3 九关验证 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/btc_noncore_selection_v2_20261014/%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/btc_noncore_m3_selection_v2_20261014.md`)；F1 九关验证 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/btc_noncore_selection_v2_20261014/%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/btc_noncore_f1_selection_v2_20261014.md`)；F2 九关验证 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/btc_noncore_selection_v2_20261014/%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/btc_noncore_f2_selection_v2_20261014.md`)。均为 EXPLORATORY，历史身份/当时可知性、未触碰 OOS、真实成交、强制结算和账户杠杆证据未齐。

独立复核重新计算了 1,285 个主 IC 行、9,766 个价格及成本持仓行、1,365,356 行资金费事件、48,295 行单腿汇总，未发现数值不一致。另独立核对 1,285 个主选币集合与 92,124 个基本面特征源日期/数值。数值复核 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/btc_noncore_selection_v2_20261014/%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/btc_noncore_selection_v2_20261014/review/numerical_independent_review.json`)；选币复核 (`provenance:external/163507ad7488d19d`)；特征复核 (`provenance:external/0d035418e71addbb`)。

本轮五个相关测试文件 **70 项通过**。完整全库检查为 **4,289 通过、7 失败、1 跳过、264 警告**，已运行到结束，不能称全库通过。七项失败均与上一轮独立定位的失败用例相同，涉及旧注册表固定版本和父级身份断言。 追加数据前后的旧 56 条注册记录保持一致；未修改旧测试基线规避失败。按要求重建时，源复制验证与导入分别因既有未验证副本及身份校验退出非零，清单和报告构建成功。本轮测试 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/btc_noncore_selection_v2_20261014/%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/btc_noncore_selection_v2_20261014/review/focused_test_status.json`)；完整全库检查 (`provenance:external/075310415d8035d2`)；失败与旧记录对照 (`provenance:external/03a50970c76b8340`)；按序重建 (`provenance:external/27296ae64cdcd8e4`)。

## 复核索引

- 冻结研究方案 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/btc_noncore_selection_v2_20261014/%3CSOURCE_ROOT%3Acrypto-leverage%3E/docs/BTC_NONCORE_SELECTION_V2_20261014.md`)：规则、成本、阈值与事前澄清。
- 五规则预设标准及实测值 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/btc_noncore_selection_v2_20261014/%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/btc_noncore_selection_v2_20261014/review/predeclared_screen_results.json`)：不借次要滞后或标签挽救失败规则。
- 数值输出及 SHA256 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/btc_noncore_selection_v2_20261014/%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/btc_noncore_selection_v2_20261014/numerical_v2/numerical_selection_study.json`)、实际运行输入清单 (`provenance:external/a09c2950522aaeab`)。
- 冻结源码与方案副本 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/btc_noncore_selection_v2_20261014/%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/btc_noncore_selection_v2_20261014/review/frozen_analysis_sources/manifest.json`)：最终数值运行使用绑定版本；较早覆盖清单保留其生成时版本，不覆盖历史清单。
- 新基本面来源核验 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/btc_noncore_selection_v2_20261014/%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/btc_noncore_selection_v2_20261014/review/coinmetrics_independent_source_review.json`)、资金费来源绑定 (`provenance:external/8850b09b6bc7598b`)。
- 已知周与缺失周汇总 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/btc_noncore_selection_v2_20261014/%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/btc_noncore_selection_v2_20261014/review/episode_descriptive_summary.json`)、全原定持仓尾部诊断 (`provenance:external/36ed36593e772c57`)。

复现说明：首个数值目录因运行输入哈希与随后实现版本不一致而中止，其结果未被接受；最终使用 numerical_v2 的冻结版本完整重跑并复核。未变更选币假设来适配结果。所有新增数据均为只读研究参考登记，不转成可交易就绪数据；未下单、未注册服务。
