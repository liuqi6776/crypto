> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 非 Core 负面公告后延迟做空：探索性结果

**结论先行：四个预设筛选均未通过冻结的历史筛选门槛。** 唯一显著的配对增量出现在 DELIST / NEWS_ONLY：只有 3 个已知配对、全在 2024 年；相对基准均值为 +4.520 个百分点/$1，95% pooled 区间为 [+3.159, +5.639] 个百分点，四项 Holm 校正后 p=0.0021。但同一 3 个批次中规则绝对净收益均值为 +5.382 个百分点、基准为 +0.863 个百分点，而全部 6 个已知主动 DELIST / NEWS_ONLY 事件的绝对净收益均值为 **−6.298%**。最差的 ALPACA 单篮子为 **−63.652%**，其基准因 AERGO 合约生命周期元数据不完整而未知，故不在那 3 个配对内。这个正的稀疏配对均值不能代表全部公告批次或连续账户收益。

六个已知主动 DELIST 事件的三日净收益，含基准状态与 ALPACA 组成 (`provenance:nonincluded/da3c0b4e9f6082ca`) 与 MONITOR (2025-05-07) 两个批次的基准被标为 `UNKNOWN_FUTURES_RESTRICTION`，跨两假设、三期限、两费率共 24 行。应保留“未知”，不能称合约当时确定不可交易；研究未事后改源或重跑。另有 19 天 AERGO 日线为零成交量、零笔交易且 OHLC 平直但通过了时间戳完整性门槛，故历史特征时间连续不等于可交易。

## 次要诊断、新闻解释与后续研究

Rank IC 是全合格流动池上的 3 日 BTC 减 alt 价格收益诊断，四项候选可计算样本数分别为 DELIST NEWS_ONLY 10、DELIST WEAK7 4、MONITOR NEWS_ONLY 5、MONITOR WEAK7 5，均值 IC 约为 0.080、0.127、0.054、0.041。它是价格-only的次要诊断，既非资金费后篮子收益，也不能证明代币无用或弥补主样本不足。不可变 `event_ic.csv` 的 `score_definition` 文本错误写成 Top60；代码及 60 行的 `original_pool_count`（153–253）核验为全合格池。保留该文件不改写，并在解释时采用实际全池范围。

DELIST 与 Monitoring Tag 是交易所风险/流动性或准入事件的代理，不等价于底层项目无效、没有回购销毁，也不保证价格继续下跌。历史事件研究也无法证明“负面新闻”在首次发布时市场尚未定价。后续有价值的、另行预注册的研究可只纳入具有可核实首发时点且直接涉及代币风险的负面事件；逐事件确定当时可交易合约与生命周期，记录新闻前 funding/crowding 和入场前价格反应，预先冻结延迟窗口及篮子，对未触碰的未来事件窗做独立检验。这只是研究设计建议，不是已测试或已盈利的新规则。

本次冻结输出的独立数值审计已复现所有配对汇总、8,000 个bootstrap draw、四项Holm校正及资金账本。全仓库规定的再生成/完整测试仍在运行；**完整测试状态待根任务最终回执**。在该回执到达前，本稿为审阅草稿，不作最终冻结。

## 九门结论

四份逐策略报告见 `gate_reports/` (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/btc_noncore_news_event_v1_20261015/newreview/delivery/gate_reports`)。四个历史筛选均为 FAIL；真实成交、未触碰 OOS、完整 Futures 持仓路径与强平风险也尚未验证。总评为 `EXPLORATORY / UNVERIFIED`，不能称有效或可交易。

## 审计绑定

- 数值清单 SHA256：`eebcca5b68739992ca3a36bf8108c5114ded809ba1efba86eef8335816e98b17`
- outcome-blind coverage SHA256：`023283387e7aa610408a009e491e6c3f61486ea3ee4bc36ed8da4a5d2ec983ef`
- 独立数值复核：`numerical_audit.md` (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/btc_noncore_news_event_v1_20261015/newreview/numerical_audit.md`)；风险/覆盖复核：`risk_and_coverage_audit.md` (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/btc_noncore_news_event_v1_20261015/review/risk_and_coverage_audit.md`)
- 测试状态：完整测试待根任务回执；不得将等待状态写成通过。
