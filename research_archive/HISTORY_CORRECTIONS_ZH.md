> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 历史研究纠正记录

截至2026-10-23。原报告作为历史证据保留；本页纠正结论的解释和适用范围，不替换原始数字，也不代表重新运行模型、行情或全部账本。旧登记和目录清点不是独立复算。对应研究见[历史结果索引](HISTORY_RESULTS_ZH.md)。

1. **区分阶段协议、完成记录与策略有效性。** 原 `docs/RESEARCH_INTEGRITY.md`、`docs/MIGRATION_AND_LIMITATIONS.md`（未随包）的“mark absent”“未运行backtest”等早期语句，不能覆盖后续选定 Core4 4h 窗口的真实 mark 和官方引擎运行记录。选窗加载成功也不能证明其他窗口、默认全量转换或策略准入通过。TV、risk30 的早期待运行协议应与后续结果分别标注时间，不能把已经完成的研究仍写成未运行。证据：[Round2 v3 更正](evidence/history/docs/ROUND2_PHYSICAL_ACCOUNTING_ERRATUM_V3.md)、[来源与转换边界](evidence/history/research_hub/platform_data/records/local-conversion-boundary.md)、[TV最终结果](evidence/history/reports/strategy_validation/tradingview_fixed_diagnostic_20261018_v1/RESULTS_ZH.md)、[risk30最终结果](evidence/history/reports/strategy_validation/trend_risk30_20261018_v1/RESULTS_ZH.md)。

2. **R3K最终逐臂报告优先于早期摘要。** 旧证据矩阵和登记保留的是当时的首结论。最终 B_PRICE_IV_DAILY 的 Ridge 重复 seed 每份为 −5,442.29 USDT；C3 的三个 seed 分别为 −25.99、+64.79、−235.56 USDT。重复 seed 不构成独立市场样本，不得相加成组合收益。H5 的统计比较不等于经济优势，H7 纠正后仍不支持改善。证据：[旧矩阵](evidence/history/research_hub/INVENTORY_AND_EVIDENCE.md)、[最终价格/IV/日频臂](evidence/history/reports/strategy_validation/r3k_20261005/b_price_iv_daily_r3k_20261005.md)、[最终C3臂](evidence/history/reports/strategy_validation/r3k_20261005/c3_r3k_20261005.md)。

3. **TSMOM没有通过完整成本门。** 原报告将成本列为 `PASS (partial)`，同时明确20币中只有4币覆盖观测 funding。因此20币结果不能称全资金费覆盖净收益，成本门仍不完整。该报告的门号和定义也不同于工作区九门协议，只可作为本研究检查项。初始四币正结果已被正式 `REJECTED` 结论取代；24格 BH 最小 q=.258，不能挑原始 p=.028 宣称显著。仅两周的 −10.1% 前向检查也不足以证明长期失效。证据：[TSMOM正式验证报告](evidence/history/reports/strategy_validation/tsmom_30d_v1_20261020/strategy_validation_report.md)。

4. **MTF-TAE不能给所有参数或强化学习设普遍上限。** 原报告的“真实信息”“统计上真实”“RL不会超过实测上界”“任何止损止盈参数都不可能”等断言超出有限网格、单一GBM实验和所测窗口。TEST 的随机入场对照 p_control=.256，未检出显著择时；已测配置净成本结果为负。正确结论是本轮配置未建立经济优势；RL未训练，不能给它一般性上界。证据：[MTF趋势ATR结果](evidence/history/research/mtf_trend_atr_v1/RESULTS_ZH.md)。

5. **固定杠杆恒等式不能证明动态波动仓位的一般结论。** 原中性化报告的 `E[L·r]=L·E[r]` 只适用于常量 L。若 L 随状态变化，应考察 `E[L·r]`，其中包含 L 与 r 的相关关系。本轮参考规则 fixed、cap3、cap5 的负结果可以保留，不能据此证明所有动态仓位必然无效。表中还有15/280组合净均值为正，“配对全部转负”只能限于对应单腿对照，不能概括全部组合；五项条件同时满足仍为0。止损和尾部控制也不能“保证收益”。证据：[MTF中性化结果](evidence/history/research/mtf_neutral_v1/RESULTS_ZH.md)。

6. **期权代理不能推出期限结构或卖方的可执行优势。** DVOL/Black–Scholes 研究缺真实期限结构、完整报价和保证金路径。“长期期权每天theta更大/更不利”“数据支持卖方”超出该代理证据。正确表述是这组模型代理未建立稳定的可执行买方优势，卖方优势尚未检验。负增量系数也不自动证明预测“帮倒忙”，应依据相应验证损失。报告所称“2024+无期权链”是当时范围；后续 Deribit 成交OHLC研究已经存在，但它仍不是买一卖一成交证据。证据：[DVOL代理结果](evidence/history/research/vol_options_proxy_v1/RESULTS_ZH.md)、[后续实际链与Deribit结果](evidence/history/research/options_chain_2023_v1/RESULTS_ZH.md)。

7. **期权累计统计不能冒称自融资账户回报。** 实际链学习结构表中有 −700.3%、−971.4% 的“累计（权利金口径）”，只能按原报告收益序列统计解读，不得当作有资金约束的账户复利或可实现回报。BTC30日 +35% 只是5笔权利金复利，且收益高度集中；手续费未计，结算指数使用永续价格代理。Deribit成交OHLC也不能视为可按该价格买入的ask报价。证据：[实际期权链结果及局限](evidence/history/research/options_chain_2023_v1/RESULTS_ZH.md)。

8. **有限负结果不证明市场或策略思想永远不可预测。** 若干报告把已测路径总结成“4h/8h方向均不可预测”“容量不是瓶颈，信号才是”。这些结论必须限定于模型、输入、窗口、成本和检验功效。相同限制适用于正结果：预测误差改善、某个历史筛选通过、或一组条件正收益都不是交易优势证明。证据：[MTF预测结果](evidence/history/research/mtf_forecast_v1/RESULTS_ZH.md)、[结构失衡研究](evidence/history/research/structural_imbalance_v1/RESULTS_ZH.md)、[Core3最终验收](evidence/history/reports/strategy_validation/core3_variance_ablation_20261012_v1/delivery_v1/FINAL_ACCEPTANCE_ZH.md)。

9. **采集器修复、前向准入与旧观察器状态必须分开。** 10月19日记录升级的部署、离线验证，不能替代10月20日兼容补丁的安装结果；后者78通过、2跳过，但安装仍受阻，未有新一轮真实资金费采集成功证据。30日观察仍为 `BLOCKED / NOT_STARTED`，质量观察也不验证alpha。BB spot observer 的10月7日状态仅是旧模拟快照，当前运行状态 `UNKNOWN`；它既不等于永续研究，也不证明连续SLA。证据：[记录升级卡](evidence/history/reports/strategy_validation/collector_receipts_20261019_v1/RESEARCH_CARD.md)、[兼容补丁结果](evidence/history/reports/strategy_validation/collector_funding_schema_fix_20261020_v1/OUTCOME.json)、[后续安装结果](evidence/history/reports/strategy_validation/collector_funding_schema_install_20261020_v1/OUTCOME.json)、[前向准入卡](evidence/history/reports/strategy_validation/forward_data_admission_20261019_v1/RESEARCH_CARD.md)、[旧观察器登记](evidence/history/research_hub/platform_data/records/source-universe-forward.md)。

10. **保持成本、资本、样本与市场身份一致。** 每笔名义PnL、独立sleeve、共享钱包、固定名义规模、权利金统计及预测误差不得跨研究直接合计、排名或乘杠杆。压力成本改变了所选交易时，不是同一交易集合的成本压力。跨币永续多空carry不能改称同币现货永续套利；缺失周不得补零或完整周子样本年化。C3比BASE少亏不等于盈利；BB spot、perp BB与spot observer也不能混为一个策略。证据：[carry v2](evidence/history/reports/strategy_validation/funding_carry_settlement_cost_v2_20261017/REPORT_CN.md)、[近期小资金报告](evidence/recent/small_cap_game/REPORT_ZH.md)、[spot BB旧登记](evidence/history/research_hub/strategy_models/experiments/source-spot-bb-benchmark.md)、[历史总证据矩阵](evidence/history/research_hub/INVENTORY_AND_EVIDENCE.md)。
