> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# V5 Meta-account 2022–2023：独立账务审计与结果总览

**结论：EXPLORATORY。** 独立 JSON 审计检查了 12 个固定单元：10 份完整账户账本通过结构一致性检查；2 个单元记录为经过验证的融资约束失败，没有生成绩效账本或 NAV。整体审计状态为 `STRUCTURAL_AUDIT_COMPLETE_WITH_FINANCING_FAILURES`，模型间完整矩阵比较与账户 alpha 均为 `BLOCKED`。这项审计验证内部账务一致性，不验证市场价格、成交、执行可行性或 alpha。

## 审计身份

- 冻结 V5 汇总：`reports/strategy_validation/regime_event_round2_20260930/meta_account_2022_2023_v5/account_summary_v5.json`（SHA256 `BE9009410B5B799A1B9574404EDD3911BB12B19CDD27032C0C4BB0664E57D980`）。
- 独立审计结果：`reports/strategy_validation/regime_event_round2_20260930/meta_account_2022_2023_v5_independent_audit_v1/audit_result.json`（SHA256 `6322F6B774165EE32B0BC82C0DEB32CAB6514CCE1D68AB3725A831CC59240112`）。
- 审计范围：12 个 arm×cost 单元；10 个账本通过结构审计，2 个融资失败记录被验证。每个融资失败单元绩效字段均为 `N/A`，不能当作零收益或亏损样本。
- 2021 是选型/训练历史；2022 与 2023 都已暴露，是历史评价窗口，不是未触碰测试。2024+ 仍封存。

## 12 个固定单元

下表逐行映射 V5 汇总中唯一的 `(arm, cost_case)` 键。CAGR、Sharpe、回撤及年度数值来自连续 NAV；融资失败单元全部保留并显示 `N/A`。

| Arm | Policy | Cost | 结构状态 | 2022–2023 CAGR | Sharpe | 最大回撤 | Trades | 2022 CAGR | 2023 CAGR |
| :--- | :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| E4_unfiltered | return_priority | primary_5_5 | 融资约束失败（VALIDATED_FINANCING_FAILURE_RECORD） | N/A | N/A | N/A | N/A | N/A | N/A |
| E0_X3 | return_priority | primary_5_5 | 账本结构审计通过 | 17.09% | 1.0321 | -13.80% | 73 | -4.00% | 42.81% |
| E4_CatBoost | return_priority | primary_5_5 | 账本结构审计通过 | 6.89% | 0.4898 | -19.54% | 135 | -13.68% | 32.38% |
| E4_Ridge | return_priority | primary_5_5 | 账本结构审计通过 | 7.23% | 0.5117 | -19.63% | 123 | -9.00% | 26.35% |
| E4_unfiltered | return_priority | sensitivity_2_5 | 账本结构审计通过 | 4.57% | 0.3244 | -26.84% | 269 | -16.00% | 30.18% |
| E0_X3 | return_priority | sensitivity_2_5 | 账本结构审计通过 | 17.70% | 1.0720 | -12.83% | 73 | -3.38% | 43.37% |
| E4_CatBoost | return_priority | sensitivity_2_5 | 账本结构审计通过 | 7.53% | 0.5301 | -18.48% | 135 | -13.03% | 32.95% |
| E4_Ridge | return_priority | sensitivity_2_5 | 账本结构审计通过 | 8.05% | 0.5642 | -18.20% | 123 | -8.23% | 27.21% |
| E4_unfiltered | return_priority | stress_5_10 | 融资约束失败（VALIDATED_FINANCING_FAILURE_RECORD） | N/A | N/A | N/A | N/A | N/A | N/A |
| E0_X3 | return_priority | stress_5_10 | 账本结构审计通过 | 16.07% | 0.9662 | -15.43% | 73 | -5.03% | 41.86% |
| E4_CatBoost | return_priority | stress_5_10 | 账本结构审计通过 | 5.83% | 0.4235 | -21.30% | 135 | -14.77% | 31.41% |
| E4_Ridge | return_priority | stress_5_10 | 账本结构审计通过 | 5.85% | 0.4254 | -22.02% | 123 | -10.27% | 24.87% |

## 主成本 5+5 bps 的年度结果与交易集中度

年度收益/Sharpe/回撤使用连续账户 NAV 的年度切片；entry-year 净 PnL、费用和资金费则按该年度开仓的完整交易归属，数值会跨越自然年度退出，因此两类年度统计不等同。Top-3 列是该 entry-year 正收益交易净贡献占比，按冻结诊断原值列示；这是集中度描述，不是独立 episode 证据。

| Arm | Trades | 2022–23 CAGR / Sharpe / DD | 2022 CAGR / Sharpe / DD | 2023 CAGR / Sharpe / DD | 2022 entry-year net / fees / funding (USDT) | 2023 entry-year net / fees / funding (USDT) | 2022 top-3 positive share | 2023 top-3 positive share |
| :--- | ---: | :--- | :--- | :--- | ---: | ---: | ---: | ---: |
| E0_X3 | 73 | 17.09% / 1.0321 / -13.80% | -4.00% / -0.3428 / -11.13% | 42.81% / 1.7979 / -10.12% | -3,999.59 / 1,029.87 / 126.10 | 41,096.32 / 1,345.92 / -1,233.17 | 88.79% | 71.34% |
| E4_unfiltered | financing failure | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| E4_CatBoost | 135 | 6.89% / 0.4898 / -19.54% | -13.68% / -1.7843 / -15.74% | 32.38% / 1.4104 / -16.49% | -13,684.49 / 1,085.35 / 137.17 | 27,949.32 / 1,176.67 / -1,153.91 | 74.35% | 76.35% |
| E4_Ridge | 123 | 7.23% / 0.5117 / -19.63% | -9.00% / -0.7622 / -16.28% | 26.35% / 1.2837 / -13.53% | -8,997.62 / 1,272.11 / -53.43 | 23,976.64 / 1,661.22 / -1,198.71 | 63.75% | 73.96% |

V5 采用 `return_priority`：初始权益风险预算 1%，每币名义仓位上限为每币初始本金的 40%；组合总初始名义承诺不超过初始现金，并受现金约束。它是 full-paid notional 研究账户代理，不是完整永续合约保证金、维持保证金或强平引擎。

主成本为每边 fee 5 bps + slippage 5 bps；另有 sensitivity 2+5 与 stress 5+10 bps 两组固定对照。两份 E4_unfiltered 单元（primary_5_5 与 stress_5_10）在 funding debit 触发无借款现金约束后失败，不能以敏感成本单元替代主成本结果。没有依据将失败原因扩展解释为模型缺陷，也不能删除失败单元后宣称完整对照成立。

资金费现金流使用冻结 engine 的 prior completed 1h genuine mark close proxy。该 proxy 与交易所实际 settlement mark 的等同性、settlement 发布时刻及数据完整性仍未证实；NAV 使用真实 mark candle 的完成收盘价，交易出入场仍用执行价。Gate 1 因此仍 BLOCKED。

## 结果解释

- `E4_CatBoost` 与 `E4_Ridge` 的完整主成本账本显示负的 2022 连续年度收益；2023 的正收益不足以把已暴露历史转成 OOS 证据。`E4_unfiltered` 的主成本与 stress 单元因融资约束失败，比较矩阵不完整。
- 本次 META_ACCOUNT 阶段没有独立 alpha 结论；alpha 诊断为 `BLOCKED`。不得把已有其他窗口的 alpha 结果移植为本阶段结论，也不据此宣称纯 beta。
- 用户偏好追求较高收益、可承受较大回撤；本报告没有把任何未经用户明确指定的数值门槛当作用户要求，也没有通过提高杠杆或扩大仓位制造 alpha。
- 所有九项策略验证门仍未全部通过。没有一个 arm 可据此称为有效策略、可自动实盘策略或可交易产品。

## 分 arm 九门报告

- E0_X3 九门报告 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/regime_event_round2_20260930/meta_account_2022_2023_v5_independent_audit_v1/gate_reports_v1/E0_X3_strategy_validation_gates_v1.md`)
- E4_unfiltered 九门报告 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/regime_event_round2_20260930/meta_account_2022_2023_v5_independent_audit_v1/gate_reports_v1/E4_unfiltered_strategy_validation_gates_v1.md`)
- E4_CatBoost 九门报告 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/regime_event_round2_20260930/meta_account_2022_2023_v5_independent_audit_v1/gate_reports_v1/E4_CatBoost_strategy_validation_gates_v1.md`)
- E4_Ridge 九门报告 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/regime_event_round2_20260930/meta_account_2022_2023_v5_independent_audit_v1/gate_reports_v1/E4_Ridge_strategy_validation_gates_v1.md`)
