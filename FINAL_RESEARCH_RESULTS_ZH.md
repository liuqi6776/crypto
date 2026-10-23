# 最终研究结果清单

归档审查日期：2026-10-23。这里的“最终”指本次证据整理版本，不是策略研究永久结束。**目前没有证据支持把任何策略升级为稳健盈利、九门全部通过或实盘就绪。** 有条件历史正结果、已核对的负结果、无效结果和未运行项目分别保留。

完整入口：[历史主题清单](research_archive/HISTORY_RESULTS_ZH.md) · [25条原登记快照](research_archive/catalog/registry_snapshot.json) · [151个目录名称清点](research_archive/catalog/directory_census.json) · [逐文件证据清单](research_archive/EVIDENCE_INDEX.md) · [纠正记录](research_archive/CORRECTIONS_ZH.md) · [复核方式](research_archive/REPRODUCE_ZH.md)。目录数量包含版本、修复和工程材料，不是独立实验数量；未访问材料不算已验证。

## 最近研究

金额均为模拟研究。下表“已核对”仅表示已有报告与导出汇总相符，不表示本次重跑行情、重建逐笔账本或验证真实成交。

| 研究 | 本次采用的状态 | 结果与边界 | 公开证据 |
|---|---|---|---|
| 浪浪启发固定规则 A/B | 已核对模型负结果；来源质量仍有未决问题 | BTC/ETH/SOL，2024-01-10至2025年底，每场景共享模拟本金10,000 USDT。A固定/A保护/B固定/B保护基础净收益−28.91%/−32.33%/−26.92%/−26.21%。24个核心情景全负；36个总情景含基准，不能说36个全负。 | [报告](research_archive/evidence/recent/langlang_fixed/REPORT_ZH.md)、[36行汇总](research_archive/evidence/recent/langlang_fixed/outputs/v3/performance.csv)、[原账本验收记录](research_archive/evidence/recent/langlang_fixed/INDEPENDENT_LEDGER_V3.json) |
| 两波箱体 | 最新范围已接受；结果待验证 | 五周期5m/10m/1h/4h/1d、3/5倍均量、两退出两成本共40个计划情景。最新文件仍明确执行协议未完整冻结、未计算结果。本次未找到可验证的后续40情景结果。无效小窗口基准不采用。 | [状态与范围](research_archive/evidence/recent/two_wave/STATUS_ZH.md)、[失效登记](research_archive/evidence/recent/two_wave/BENCHMARK_INVALIDATED.json) |
| 结构式浮盈保护 | 有限算法样本费滑后负结果 | 2023Q1 BTC/ETH共25笔，每笔名义上限1,000 USDT、无杠杆；固定−0.27、结构保护−23.67 USDT。funding未覆盖，完整净收益未知。仅发布算法汇总，排除个人交易与会话。 | [算法摘要](research_archive/evidence/recent/human_protection/ALGORITHM_REPORT_ZH.md)、[精选汇总](research_archive/evidence/recent/human_protection/algorithm_metrics.csv) |
| BTC funding切换 | 事件预测联合标准未通过；同币carry经济性未运行 | 2024–25每方向132事件：正转负0命中/1误报/132漏报；负转正122命中/68误报/10漏报。不能用多数正费率准确率代替优势，也不能计算真实spot+perp净年化。 | [报告](research_archive/evidence/recent/funding_switch/REPORT_ZH.md)、[事件指标](research_archive/evidence/recent/funding_switch/btc_funding_switch_study/event_metrics.csv) |
| 小资金博弈/C3筛选 | 已核对有限历史负结果 | 2023 ETH/SOL，BASE26笔/C3 15笔，每笔名义1,000 USDT。基础费滑后−21.2501/−3.9619 USDT，压力−47.2394/−18.9523；少亏不等于盈利，资金费完整现金流未知。 | [报告](research_archive/evidence/recent/small_cap_game/REPORT_ZH.md)、[四行成本汇总](research_archive/evidence/recent/small_cap_game/root_review_run_v1/strategy_metrics.csv) |
| 新上市合约做空 | 数据门受阻；已暂停 | 旧325币研究有120天前置历史门槛，不能用于上市早期。生命周期和历史可开空池未验证；未运行新策略，不能说该思想已被证伪。 | [报告](research_archive/evidence/recent/new_listing_short/REPORT_ZH.md)、[生命周期门](research_archive/evidence/recent/new_listing_short/LIFECYCLE_GATE_REVIEW_ZH.md) |

浪浪基础成本为每边6bp手续费+5bp滑点，压力12bp+10bp；funding采用实际观测费率、小时mark.open近似结算标记价。重复使用历史、来源内容冲突、盘口冲击及保证金路径未解决，因此既不是未看样本外，也不是原作者方法的精准复刻。其他项目采用不同成本和资本口径，不能互相直接排名或把收益乘杠杆。

## 较早研究的保留结论

[历史主题清单](research_archive/HISTORY_RESULTS_ZH.md)逐项列出证据及局限，包含以下各组，并非只保留最近六项：

| 分组 | 当前结论 |
|---|---|
| Freqtrade迁移、Round2/3、长周期BB/EMA、Core3 | 选定窗口曾有加载、账户修复或有限历史正值；不能推广为全项目数据门或策略门通过。 |
| EMA/IV/R3K、Ridge风险、EOH/BVOL、GARCH/HAR | 预测误差与交易收益分开；泄漏时代结果失效，R3K采用最终逐臂结果。 |
| Channel ML、Maker、C1/C3、形态/回踩/执行时域、ETH Box、分钟预测 | 多组成本后负结果或筛选不通过；不能把少亏、较高准确率或个别正种子解释为稳定优势。 |
| BTC非Core、新闻、Volume/ETAS、活动、Prophet、趋势公平比较 | 部分统计关系存在，但未建立相对适当基准的稳定经济优势；身份错误和未运行单独记录。 |
| 跨币funding carry、低频方向、TV、risk30、longtrend、波动变现 | 有条件历史正结果和负结果并列；carry不是同币现货永续，IV增量归因未成立；现货基准部分受数据门阻断。 |
| 结构失衡、MTF趋势/预测/中性化、期权代理与实际链、30d TSMOM | 多组筛选失败；有限实验不能证明所有方向不可预测。期权权利金累计统计不是自融资账户；TSMOM后续正式拒绝优先于早期四币正结果。 |
| BB observer、Top1、MA/XGBoost、Transformer、旧20x/Core-Satellite | 市场身份和版本分开，保留LEGACY_RESEARCH。未找到可单独核实的LSTM最终实验，不能凭名称补造结果。 |
| collector与30日前向 | 10/19记录升级部署与10/20兼容补丁是不同版本；后者安装仍受阻，30日前向BLOCKED/NOT_STARTED。本次未启动任何进程。 |

## 证据等级与复现范围

- **已核对负结果**：已保存模拟汇总在该配置/窗口下为负；不是对所有同类策略的普遍否定。
- **有限历史正结果**：保留原数字、成本和口径；不自动提升为未看样本外、因果alpha或未来回报。
- **数据门受阻/待验证/已暂停**：未知不补零，未运行不写失败，更不写成功。
- **INVALIDATED/LEGACY_RESEARCH**：保留追溯信息，禁止以被撤回的旧数字宣传有效性。

本次新执行的是文件/链接/敏感信息校验及精选汇总算术复核。原研究的45、25等测试数量是历史收据；没有重跑策略全套测试、训练、行情转换或新寻优。公开包不包含完整交易引擎、所有逐笔账本或原始第三方行情，不能凭本包完整重放每项研究。详见[复核范围](research_archive/REPRODUCE_ZH.md)、[公开与许可边界](research_archive/PUBLICATION_SCOPE_ZH.md)。
