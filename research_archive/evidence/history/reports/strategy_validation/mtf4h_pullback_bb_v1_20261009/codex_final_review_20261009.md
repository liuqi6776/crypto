> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# Codex 独立最终审查 — 2026-10-09

本次有限实验已完成一次冻结策略回放和独立保存账本审计。审查接受本次机械化假设的历史现金结果，以及单独修正后的小时观测权益代理；没有通过策略有效性或交易就绪门槛。

## 结论

12 个币种／策略臂／成本组合的毛 PnL 和净 PnL 上下界均为负。A 臂 base 每笔净收益下界为 ETH −10.9316 bp、SOL −11.9373 bp（分母为固定 1,000 USDT 入场名义金额），未满足预注册盈利支持条件。A−C 的主要连续段每日现金流区块 bootstrap 区间跨越零，因此没有可靠证据表明 A 优于 C。本结论仅针对冻结版本和受污染历史，不能替代对用户人工交易方法的完整验证。

## 实际执行与审计证据

- 主回放：2026-10-09 01:25:21–02:35:42 UTC，managed session 46902，exit 0，完成结果标识 `4aa7d4`；输出仅有 pandas FutureWarnings。没有第二次策略回放。
- 冻结协议 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/mtf4h_pullback_bb_v1_20261009/protocol_v6.json`)、执行实现、测试、输入、原始输出均保存。原始输出清单 SHA256：`2717ae585d708534ef67f21313952f3d8c728b365c0d247802f966d156c59b12`。
- 全部保存账本独立审计 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/mtf4h_pullback_bb_v1_20261009/codex_full_saved_ledger_audit.json`)：24 个分段案例、19,192 笔交易、276 项哈希检查，零哈希差异、零账本核对失败。覆盖 98 个分钟源分区、注册资金费与真实 mark 文件、旧受保护产物、冻结实现及原始输出。逐笔核对固定名义金额、成交价、入场／离场费用、G−费用＋资金费＝净现金、真实资金费时间及上下界、日历日归属、入场前现金、60 分钟持仓上限、时间顺序、不重叠持仓及 A 初始确认条件。
- 原始小时权益因互斥入场／离场状态重复计数而不被接受，原始文件完整保留。派生权益全网格独立审计 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/mtf4h_pullback_bb_v1_20261009/codex_derived_mtm_output_audit.json`) 从保存成交和真实 mark 重新枚举互斥状态，与全部 24 个修正案例、420,060 个小时观测点的六列权益／现金／预留额边界及回撤代理逐点匹配；最大金额差 `4.994e-8` USDT，预留额上界不超过 1,000 USDT（浮点容差内）。这只是报告会计修正，没有重新生成信号或成交。
- 策略实现及两组旧回归焦点测试 63 项通过；派生权益 helper 8 项通过，共 71 项独立焦点测试。全部运行使用 `-B`、`-p no:cacheprovider`。完整 pytest 仍在既有测试收集阶段因缺少 `r3i_pytest_guard_v2` 失败，未修改旧测试或环境。
- 48 行年度现金流与原始每日账本独立相加一致，最大差 `4.897e-9` USDT；区块 bootstrap 直接引用冻结诊断，不重新抽样或更改阈值。

## 资本、缺口和未验证内容

每个币种／策略臂／连续段独立投入 10,000 USDT，每次入场名义金额固定 1,000 USDT，即初始钱包的 10%。每臂每场景有一个 ETH 段和三个 SOL 段，共四个分隔子账户、总分配本金 40,000 USDT；base 与 stress 独立，SOL 不跨缺口复用本金或持仓。各段重新预热，实际价格边界、有效窗口和首末成交分别披露。

2022–2025 全部是已接触历史，没有未触碰 OOS。真实队列、价差、容量、盘中 mark 路径、10x 保证金和强平路径、真实盘中回撤、OOS Sharpe、MAE/MFE、强平距离缺少证据，保持 BLOCKED／UNKNOWN。修正后的回撤仅为小时观测网格条件代理；不能倍乘 1x 数值推断 10x。

按照用户对独立实验的明确范围，未执行会改写旧产物的全局复制／转换／inventory／report 再生成链。没有市场数据下载、源文件修改、实时交易、服务或调度注册，也没有启动后续模拟或监控。

## 交付

中文结果总览 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/mtf4h_pullback_bb_v1_20261009/experiment_overview_results_20261009.md`)、A 验证报告 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/mtf4h_pullback_bb_v1_20261009/mtf4h_pullback_bb_v1_A_validation_20261009.md`)、B 验证报告 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/mtf4h_pullback_bb_v1_20261009/mtf4h_pullback_bb_v1_B_validation_20261009.md`)、C 验证报告 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/mtf4h_pullback_bb_v1_20261009/mtf4h_pullback_bb_v1_C_validation_20261009.md`) 和 报告／派生文件清单 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/mtf4h_pullback_bb_v1_20261009/final_artifact_manifest_20261009.json`) 保存完整结果及各门槛状态。最终审查完成状态及交付哈希以独立根审查清单为准。
