> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# Prophet 三币固定配置试验：停止本配置

**结论：`FAIL_STOP_THIS_MODEL_CONFIG`。本轮不支持继续把该 Prophet 配置用于短期价格预测或交易过滤，按冻结规则不运行经济映射。** 这是否定本次配置的历史预测增量，不是对所有 Prophet 用法的普遍结论。

BTC、ETH、SOL 全部参加。单一配置、单一周起点日历，无参数搜索、事后换目标或筛币。2023—2025 均为已暴露历史，不能称为独立样本外验证；2026 未纳入本轮评价。

## 主要结果

误差对象为未来对数收益：预测目标 log(close) 减去起点实际 log(close)。零收益预测等价于未来价格不变。MAE/RMSE 单位均为对数收益，不是账户收益或交易损益。

| 24h 主目标 | 共同起点数 | Prophet MAE | 零收益 MAE | MAE / 基准 | Prophet AUC |
|---|---:|---:|---:|---:|---:|
| BTC | 154 | 0.067332 | 0.021526 | 3.1279 | 0.5263 |
| ETH | 154 | 0.086799 | 0.026820 | 3.2363 | 0.4970 |
| SOL | 154 | 0.137749 | 0.037844 | 3.6399 | 0.5510 |
| 三币等权 | 154 | 0.097293 | 0.028730 | **3.3347** | **0.5248** |

最后一行误差比是三个币各自误差比的等权平均，不是该行两个 MAE 的比值。主指标 `mean_coin(1 - MAE_Prophet / MAE_RW)` 为 **−233.47%**；同步四周日期区块的 95% 区间为 **[−296.98%, −184.77%]**，明显未达到预注册的至少 +1%、区间下界大于 0。

24h RMSE 的三币等权值为 0.125556，零收益基准为 0.039862；各币 RMSE 相对改善的均值为 −208.07%。主目标三币均更差，逐年三币等权 MAE 相对改善也全部为负：2023 年 −301.20%、2024 年 −201.27%、2025 年 −215.35%。年度按预测起点的 UTC 年份归类。

方向 AUC 点估计略高于两个固定趋势对照，但增益未获区间支持：

| 24h 方向对照 | 对照等权 AUC | Prophet AUC 增益 | 95% 区间 |
|---|---:|---:|---:|
| EMA200 | 0.4777 | +0.0471 | [−0.0667, +0.1675] |
| Donchian120/60 | 0.4706 | +0.0541 | [−0.0606, +0.1776] |

两个增益的 .025 分位下界均不大于 0，未通过预注册的两项比较 Bonferroni 单侧门槛。Prophet 方向准确率 53.46%，平衡准确率 53.51%；不能只取 SOL 的较好点估计来救整体结论。EMA/Donchian 的空仓在二分类诊断中编码为非上涨、AUC 分数 0.5；这不是做空交易假设。

72h 仅作次要诊断：MAE 误差比等权平均 **2.3963**，相对改善 −139.63%，95% 区间 [−178.96%, −107.70%]；AUC 0.5212。该结果同样不支持增量，且不能替换失败的 24h 主目标。

完整逐币、逐年、两个期限的误差、方向指标、类别计数和区间见 analysis.json (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/prophet_trend_pilot_20261019_v1/results/analysis.json`)。24h 类别计数为 BTC 81 上涨/73 非上涨、ETH 83/71、SOL 72/82，其中 SOL 有 1 个零收益目标。预测值没有被当作概率，也没有用价格水平 R² 宣称能力。

## 执行、失败与冻结

- 研究开始：2026-10-19 09:43:28 UTC；冻结：**10:07:06.781095 UTC**；冻结前真实拟合为 0。
- 156 个周一起点，2023-01-02 至 2025-12-22，三币共 468 个任务。465 成功，3 个运行故障。有效原始覆盖数 BTC 155、ETH 154、SOL 156；共同起点 **154/156 = 98.72%**，超过冻结的 95% 门槛。主点估计和区间都只使用同一共同集合。
- 2023-01-02 的 BTC、ETH 在受限执行环境中遭遇 WinError 623 DLL 重定位错误。原模型的无拟合 help 在授权执行通道返回 0 后，使用相同代码和锁恢复；两次失败未重跑，首次失败结果保存于 failure_snapshot_01 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/prophet_trend_pilot_20261019_v1/failure_snapshot_01/analysis.json`)。
- 2025-04-07 的 ETH 在拟合前持久化检查点时遭遇 WinError 5 文件替换拒绝。此时存在进度读取，是否为同时打开文件导致未得到独立证明。该失败也未重试，未修改文件权限。它不是模型数值优化失败。
- 468 是保守的任务尝试计数；其中 1 次在调用拟合前失败，465 次产生有效预测，另 2 次在启动原生模型时失败。没有隐式 Newton 回退、额外模型、失败样本补拟合或超额尝试。
- 成功拟合始于 10:09:14.515171，最后结束于 **10:12:45.891014 UTC**。成功拟合耗时合计 179.13 秒，单次任务耗时中位数 0.439 秒、最大 0.941 秒；单进程运行。全轮早于 11:43:28 截止。
- 两轮实现修正均发生在首次拟合之前。之后代码、协议、模型参数和依赖身份均未改变。只使用独立 `.runtime` 与官方 PyPI wheel，未修改共享环境或系统配置。

协议、模型与统计规则见 PROTOCOL.md (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/prophet_trend_pilot_20261019_v1/PROTOCOL.md`) / protocol.json (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/prophet_trend_pilot_20261019_v1/protocol.json`)；冻结证据见 EXECUTION_FREEZE.json (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/prophet_trend_pilot_20261019_v1/EXECUTION_FREEZE.json`)。单配置为 Prophet 1.5.0、H4 log(close)、线性分段趋势、25 个默认 changepoints、range 0.8、prior scale 0.05，季节/节假日/外部回归关闭。每个起点重新用过去 365 天的 2190 根 H4 收盘拟合，不用全历史 changepoint 回填。

## 独立复核与边界

Codex 未调用试验实现的统计函数，而从原始 H1 重新聚合、重算 EMA/Donchian，检查全部 465 个成功预测的训练边界、UTC 可用时刻、目标价格与收益恒等式，并复算 **432 个点指标及 6 组完整的 2000 次同步 bootstrap 区间**，全部一致。见 [独立审计](ROOT_INDEPENDENT_AUDIT.json) 和 可复算脚本 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/prophet_trend_pilot_20261019_v1/ROOT_INDEPENDENT_AUDIT.py`)。复核没有新增拟合。

独立相关测试 **15 passed in 7.03s**；`--dry-run` 前后 12576 个文件的清单、大小与修改时间保持不变。三币源文件再次校验 SHA256，注册标签和本地副本准入证据保持一致；没有补 OHLCV、使用资金费填充或合成 mark。

本轮没有账户交易账本，费用、PnL、权益恒等式、Sharpe、交易回撤等均为 **N/A**。经济映射状态为 `NOT_RUN_BY_FROZEN_GATE`。本结果也不能证明资金费覆盖、保证金档位或小时内清算路径已经合格。

全工作区测试及共享数据再生成**未运行**，以遵守本轮独立输出范围并避免并行写入；本轮没有改动共享转换链或注册表。会话此前记录的全量基线为 4440 passed / 7 failed / 1 skipped，本轮未复核，不能称为已修复或全量通过。旧的未验证来源与被拒绝输入没有因此升级。

## 决策和交付

**暂停本配置，结束本轮分支。** 不调阈值、不换训练窗、不挑币或年份、不新增收益试验。未来若提出不同假设，需新的明确授权、独立版本和结果前协议；本轮不自动启动后续研究。

验证门报告见 STRATEGY_VALIDATION_GATES.md (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/prophet_trend_pilot_20261019_v1/STRATEGY_VALIDATION_GATES.md`)。研究卡与待追加目录条目分别为 RESEARCH_CARD.md (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/prophet_trend_pilot_20261019_v1/RESEARCH_CARD.md`)、INDEX_ENTRY_20261019.md (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/prophet_trend_pilot_20261019_v1/INDEX_ENTRY_20261019.md`)。10:14:46 UTC 只读核查时，公平比较原 turn 仍为 inProgress；共享总目录未写，待合并研究结果时追加，避免越出已冻结的独立写入范围。
