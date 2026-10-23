> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# C3 风险训练期细化研究：最终账户结果与门槛审查 v1r3

**状态：FINAL_TRAINING_RESEARCH；账户 saved-output 独立算术审计 PASS。策略结论仍为 `EXPLORATORY / UNVERIFIED`。** 审计验证了经绑定的训练研究输出、账户/ledger 对账和固定期限结果；它没有验证未触碰 OOS、稳健收益、实盘准备度或下单资格。

## 研究范围与复核边界

| 项目 | 冻结范围 |
| --- | --- |
| FIT | 2021-01-01 至 2022-07-01 UTC（结束时点不含）；回顾性训练内回放 |
| CAL | 2022-07-08 至 2023-01-01 UTC（结束时点不含）；使用 FIT 冻结模型的内部训练研究窗口，不是未触碰 OOS |
| Warmup | 2020 仅作指标预热；没有把 2020 结果计入 FIT/CAL |
| 标的 | BTCUSDT、ETHUSDT；小时级交易 OHLC、独立 mark OHLC、观察到的 funding 事件 |
| 预测 | 13 个既有价格特征的 Phase A raw MAE q90、terminal log-return q10、stop-touch 概率；未增加期权 IV、skew 或 OI 特征 |
| 历史研究暴露 | 本研究前已看过 Phase B 2023 结果；2024–2026 legacy windows 按工作区历史已用于研究/选择。这里只记录先前暴露元数据，没有重读这些时期的数值数据，也不能恢复其未触碰 OOS 身份 |
| 账户方案 | 8 个固定臂 × FIT/CAL，共 16 组；每边 5 bp 手续费 + 5 bp adverse slippage；观察到的 funding 事件按既有 prior-mark-close proxy 计入 |
| 风险预算 / 限额 | 单笔风险预算为初始权益 0.5%，名义仓位上限为初始权益 25%；权重仅 shrink-only，范围 0–1；不使用杠杆、不复利。`d_stop` 是价格距离 proxy，不是已实现现金风险 |
| 禁止项 | 未读 2023 数值行情；未重新拟合、加载或预测模型；未下载行情；未改动来源文件；未做额外成本敏感性（`NOT_RUN`） |

本研究开始前已查看 Phase B 2023 结果；2024–2026 legacy windows 依工作区记录曾用于研究/选择。此处仅补充历史暴露元数据：本研究没有重读 2023+ 数值数据，也没有因此恢复任何窗口的未触碰 OOS 状态。

首轮 V1 输出的 `trade_ledger.csv` / `cash_ledger.csv` 有 `arm=X3` 归属问题，已保留为 `EXPORT_ATTRIBUTION_BLOCKED`，不作为最终逐臂现金对账证据。经 root 批准的技术导出修复 V1R1 没有改策略、账户计算或回放结果：两份 ledger 明确含 `study_arm`（8 个策略臂）和 `engine_arm=X3`。V1R1 的 352 条 trade 行和 4,560 条 cash 行均保留，并可按 `(window, study_arm)` 与 16 个 summary 账户对应。

新映射为 `d_stop = 2 × ATR14 / reference_close`，MAE 权重为 `min(1, d_stop / max(raw_q90_MAE, 1e-6))`；新 downside 权重为 `min(1, d_stop / max(1-exp(raw_q10), 1e-6))`，只在 `raw_q10 < 0` 时计算指数项。两个固定权重控制使用 FIT 均值 0.35213（MAE）与 0.54929（downside），CAL 使用冻结常数。固定权重的平均仓位与新映射不完全匹配，因此两者差异不能直接解释为等风险 alpha。

## 账户结果

收益为窗口累计净收益，没有年化。Sharpe 使用连续日 NAV（`daily_sharpe_sqrt365`）；MDD 使用含初始 anchor 的小时级 marked NAV（`hourly_marked_mdd_including_initial_anchor`）。Exposure 为平均小时 gross exposure / 初始权益。手续费、滑点和 funding 数值均为每组初始 100,000 USDT 账户的 USDT 金额；funding 是观察到的资金费事件代理现金流，负数代表净流出。

| 策略臂（study arm） | FIT：净收益 / 日 Sharpe / 小时 MDD / 平均 exposure | FIT：手续费 / 滑点成本 / funding | CAL：净收益 / 日 Sharpe / 小时 MDD / 平均 exposure | CAL：手续费 / 滑点成本 / funding |
| --- | --- | --- | --- | --- |
| E0 原始数量 | +2.910% / 0.372 / −5.360% / 4.224% | 545.93 / 545.93 / −1,482.80 | −1.952% / −1.114 / −3.302% / 2.808% | 170.63 / 170.63 / −27.84 |
| 旧 raw MAE | +3.127% / 0.399 / −5.262% / 4.213% | 540.68 / 540.68 / −1,456.50 | −2.087% / −1.295 / −3.151% / 2.652% | 166.35 / 166.35 / −22.04 |
| 旧 raw downside | +3.110% / 0.396 / −5.281% / 4.217% | 540.98 / 540.98 / −1,474.54 | −1.828% / −1.062 / −3.180% / 2.765% | 162.70 / 162.70 / −25.80 |
| 旧 raw stop | +2.916% / 0.372 / −5.360% / 4.224% | 545.67 / 545.67 / −1,482.73 | −1.928% / −1.105 / −3.278% / 2.796% | 169.55 / 169.55 / −29.25 |
| 新 stop-scaled MAE | +0.781% / 0.271 / −2.173% / 1.443% | 182.54 / 182.54 / −582.76 | −0.450% / −0.790 / −1.024% / 0.837% | 47.11 / 47.11 / −8.38 |
| 新 stop-scaled downside | +0.984% / 0.229 / −3.424% / 2.207% | 283.30 / 283.30 / −904.27 | −0.463% / −0.410 / −1.796% / 1.394% | 72.57 / 72.57 / −13.38 |
| FIT 均值权重 MAE | +1.025% / 0.357 / −1.897% / 1.487% | 192.24 / 192.24 / −522.14 | −0.687% / −1.120 / −1.173% / 0.989% | 60.09 / 60.09 / −9.80 |
| FIT 均值权重 downside | +1.598% / 0.361 / −2.954% / 2.320% | 299.87 / 299.87 / −814.49 | −1.072% / −1.118 / −1.825% / 1.542% | 93.73 / 93.73 / −15.29 |

滑点成本列取账户 summary 的 `slippage_cost_included_in_fills`；净收益已含手续费、滑点和 funding。各臂每个窗口成交数相同：FIT 34/41 个 C3 候选，CAL 10/14 个候选；其余分别跳过 7、4 个入场。固定 5/5 bp 成本下，CAL 两个新映射的窗口损失小于 E0，但 FIT 回报显著低于 E0。平均 exposure 也显著更低，不能把该变化单独归因于风险预测精度。

### 与 E0 相同候选的盈亏变化

交易配对按 `window + candidate_id`，用 `route` 区分策略臂；所有配对候选数量一致。以下金额是相同候选与退出路径下的数量缩放反事实比较，不代表改变了信号或退出决策。

| 新映射 | 窗口 | E0 亏损候选中减少的亏损合计 | 改善的亏损候选 | E0 盈利候选中减少的盈利合计 | 盈利被压低的候选 |
| --- | --- | ---: | ---: | ---: | ---: |
| 新 stop-scaled MAE | FIT | 6,639.92 USDT | 28/28 | 8,768.23 USDT | 6/6 |
| 新 stop-scaled MAE | CAL | 2,127.92 USDT | 9/9 | 626.03 USDT | 1/1 |
| 新 stop-scaled downside | FIT | 4,718.87 USDT | 28/28 | 6,644.24 USDT | 6/6 |
| 新 stop-scaled downside | CAL | 1,601.21 USDT | 9/9 | 111.47 USDT | 1/1 |

因此，CAL 中损失较小与风险敞口及盈利放大同步下降有关；FIT 则体现出明显的赢家盈利让渡，累计净回报低于 E0。CAL 只有 10 笔成交，不能据此声称稳定收益改善。

## 风险条件诊断、成交样本和持有期

保存预测诊断在固定 24 小时标签上与同 cohort 的 FIT 常数基线比较：CAL 的 14 个 C3 候选中，MAE q90 pinball 为 0.005141（基线 0.006108），stop Brier 为 0.22613（基线 0.25708），两者较低；terminal q10 pinball 为 0.005963（基线 0.005507），较高，coverage 两者均为 7.14%，低于 10% 名义目标。实际 E0 成交子样本 n=10 的 24 小时 MAE q90 coverage 为 100%、terminal q10 coverage 为 0%、stop 触碰率 30%；这些极小样本 coverage 仅作描述。FIT 的实际 E0 成交 n=34，coverage 分别为 MAE 91.18%、terminal q10 8.82%，stop 触碰率 38.24%。FIT 分数属于模型训练内评估；CAL 分数来自 FIT 冻结模型但属于内部已暴露训练研究。

全来源 24/72/168 小时成熟标签数分别为 FIT 6,540/6,516/6,468，CAL 2,112/2,088/2,040；窗口内未成熟行保留为右删失，不进入对应固定期限标签分数。全来源平均 MAE 随期限增加：FIT 3.94%/6.83%/10.20%，CAL 2.67%/4.77%/7.38%。实际 E0 成交 24/72/168 小时平均 MAE 为 FIT 3.00%/5.97%/9.04%（n=34），CAL 2.28%/3.87%/6.75%（n=10）；实际成交各固定期限标签均成熟。72/168 小时结果只用于事后路径诊断，不作为 24 小时预测头的同期限精度。

E0 持有期中位数为 FIT 38.5 小时、CAL 74.5 小时；超过 24 小时的分别为 21/34 与 7/10，最大持有期为 508 小时与 216 小时。FIT E0 退出原因是 25 笔 active stop intrabar、9 笔 EMA50 invalidation；CAL 为 7 笔与 3 笔。含退出小时 OHLC 的持有 MAE 上界均值分别为 2.665% 与 2.927%。

例：CAL 的 ETHUSDT 候选信号收盘时间为 `2022-09-09 07:59:59.999 UTC`，特征可用时间为 `08:00:01 UTC`，决策时间为 `08:00:01.001 UTC`，随后于 `09:00:00 UTC` 入场；该小时触发 intrabar stop，退出记账时间为 `2022-09-13 12:59:59.999 UTC`（约 100 小时账面持有；小时 OHLC 无法确定真实盘中触发时刻），E0 净 PnL 为 −363.03 USDT。固定 24 小时标签 MAE 为 1.33%；包含已知退出价的实际持有 MAE 下界为 2.53%，包括退出小时 OHLC 极值的上界为 5.42%。该个案显示短期限标签可能掩盖实际持有过程中的后续 adverse path，不代表对所有候选的推断。

## 历史暴露、技术导出修复与独立审计

首轮 V1 账户 receipt 标为 `EXPORT_ATTRIBUTION_BLOCKED`：原 cash/trade ledger 的 `arm` 列只含 engine `X3`。技术修复 V1R1 明确导出 `study_arm` 与 `engine_arm`，不改变策略或账户公式。首轮 12 项中 9 个产物字节级一致；只有 trade ledger、cash ledger、run manifest 因 schema/绑定改变。V1R1 收据及其 12 个文件的 SHA256 和字节数已核对。16 个 `(window, study_arm)` 账户全部匹配，最大账户 summary 对 trade PnL 残差为 `4.73e-11 USDT`，cash ledger 对 terminal cash 残差为 `2.44e-10 USDT`；无 unmatched accounts。首轮 receipt 保持不变，仅作为被修复的前序导出记录。

独立审计状态 `PASS`，审计文件为 saved_outputs_independent_audit_v1r1_retry2.json (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/c3_risk_train_refinement_v1/saved_outputs_independent_audit_v1r1_retry2.json`)，SHA256 `59975167F01786A63F0F13F6836E8FE9599BB1AFE0B66DFECA9FBB9B0DC43792`。审计在解析前核对 12 个绑定输出；验证 16 账户、55 风险图权重、34 FIT E0 成交用于 FIT 均值常数、44 个 E0 成交及其持有路径、132 固定期限标签/路径、24 小时评分与对照，以及 0 unmatched。72/168 小时只用于 outcome diagnostics。保存预测审计没有读取原始市场行、模型 bundle、拟合或推理。此前元数据核对失败和 horizon join multiplicity 检查/重试过程均保留在审计记录中；最终 retry2 在预测来源身份匹配时使用 24 小时行；132 条 24/72/168 小时路径仍全部通过验证。这是 audit-reader 的身份连接修正，不代表更改策略或行情。

运行 manifest 报告读年为 2020 warmup、2021、2022；禁止年列表为空；没有读取 2023+ 数值行情。账户结果表使用 owner `hourly_marked_mdd_including_initial_anchor` 字段，而不是审计快照的 daily drawdown 字段。报告日期 2026-10-02 UTC。

## 九道验证门槛：各策略臂当前状态

下表的九项状态适用于上表每个 FIT/CAL 策略臂。`BLOCKED` 表示整体门槛尚缺关键证据，即使其中限定算术审计已通过也不能提升整门槛；`NOT_RUN` 表示本轮未执行该项；`PASS` 仅按表内明示的限定审查范围解释。所有臂当前判定均为 `EXPLORATORY / UNVERIFIED`。

| 策略臂 | 1 数据完整与因果可用性 | 2 实现、前视与递归检查 | 3 样本内机制与搜索披露 | 4 未触碰 walk-forward OOS | 5 双边成本、资金费、价差与成交 | 6 市场状态、币种与参数稳健性 | 7 杠杆、保证金与强平压力 | 8 dry-run 观察与对账 | 9 小资金 live 观察与对账 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E0 原始数量 | BLOCKED | BLOCKED | PASS | BLOCKED | BLOCKED | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| 旧 raw MAE | BLOCKED | BLOCKED | PASS | BLOCKED | BLOCKED | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| 旧 raw downside | BLOCKED | BLOCKED | PASS | BLOCKED | BLOCKED | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| 旧 raw stop | BLOCKED | BLOCKED | PASS | BLOCKED | BLOCKED | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| 新 stop-scaled MAE | BLOCKED | BLOCKED | PASS | BLOCKED | BLOCKED | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| 新 stop-scaled downside | BLOCKED | BLOCKED | PASS | BLOCKED | BLOCKED | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| FIT 均值权重 MAE | BLOCKED | BLOCKED | PASS | BLOCKED | BLOCKED | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| FIT 均值权重 downside | BLOCKED | BLOCKED | PASS | BLOCKED | BLOCKED | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |

门槛 4 为 `BLOCKED`：FIT 是训练内回放，CAL 是内部已暴露窗口，没有未触碰 OOS。本轮没有额外价差、容量、保证金、清算压力、跨状态/参数稳健性或任何 live / dry-run 观察。每边 5 bp 手续费及滑点和 observed-funding proxy 确实写入账户回放，独立审计已通过所列限定算术核对，但门槛 1、2、5 仍为整体 `BLOCKED`：审计已通过的限定核对不覆盖完整门槛要求。门槛 1 的 artifact/source metadata、时间绑定核对通过，但完整选定窗口数据完整性/ready-chain 未评估；门槛 2 的冻结时间/路径/ledger 检查通过，但完整 Freqtrade lookahead 与 recursive analysis 未运行；门槛 5 的固定手续费、滑点、observed-funding 账务算术通过，但真实 spread、容量和成本敏感性未测试。门槛 8 的离线账户对账算术通过，但没有 dry-run 观察；门槛 9 因没有 live 观察而 `NOT_RUN`。这些限定核对不能提升整体门槛状态。根因仅影响本轮能否判定门槛，不抹去表内的描述性数值。

## 各策略臂逐项门槛报告

| 策略臂 | 独立报告 |
| --- | --- |
| E0 原始数量 | 逐臂验证报告 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/c3_risk_train_refinement_v1/per_arm_final_audited_v1r2/e0_original_quantity_20261002_v1r2.md`) |
| 旧 raw MAE | 逐臂验证报告 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/c3_risk_train_refinement_v1/per_arm_final_audited_v1r2/old_raw_mae_20261002_v1r2.md`) |
| 旧 raw downside | 逐臂验证报告 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/c3_risk_train_refinement_v1/per_arm_final_audited_v1r2/old_raw_downside_20261002_v1r2.md`) |
| 旧 raw stop | 逐臂验证报告 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/c3_risk_train_refinement_v1/per_arm_final_audited_v1r2/old_raw_stop_20261002_v1r2.md`) |
| 新 stop-scaled MAE | 逐臂验证报告 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/c3_risk_train_refinement_v1/per_arm_final_audited_v1r2/new_stop_scaled_mae_20261002_v1r2.md`) |
| 新 stop-scaled downside | 逐臂验证报告 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/c3_risk_train_refinement_v1/per_arm_final_audited_v1r2/new_stop_scaled_downside_20261002_v1r2.md`) |
| FIT 均值权重 MAE | 逐臂验证报告 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/c3_risk_train_refinement_v1/per_arm_final_audited_v1r2/fit_mean_weight_mae_20261002_v1r2.md`) |
| FIT 均值权重 downside | 逐臂验证报告 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/c3_risk_train_refinement_v1/per_arm_final_audited_v1r2/fit_mean_weight_downside_20261002_v1r2.md`) |

## 结论与下一步

这次有界研究显示：新 stop-scaled 两臂在 n=10 的 CAL 成交窗口损失小于 E0，且小时 MDD、平均敞口、手续费与 funding 流出更低；相同候选配对同时显示盈利候选收益也被缩小。FIT 回放中两臂净回报明显低于 E0 与固定权重控制。加之 CAL 终端 q10 头的候选样本 pinball 劣于 FIT 基线，现有证据不支持稳定的预测优势或 alpha 结论。

结果只覆盖现有 13 个价格特征风险头和 2021–2022 样本；它不能证明期权数据无效，也不能推翻整个趋势策略假设。下一步可在独立审计已通过的有界结果基础上，另行预注册与实际持有期对齐的风险/危害率标签，并在现有已验证本地样本上按新协议扩展共同历史支持。不得据本轮结果提高杠杆或放宽策略门槛。

## 复核文件

| 文件 | SHA256 / 用途 |
| --- | --- |
| 账户结果收据 V1R1 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/c3_risk_train_refinement_v1/training_output_artifact_receipt_v1r1.json`) | `AC104A123A99C3FA9AE9FCF9AFD7B1B8EFF31787500420E4E5AD8F2F7E0B8EFD`；本文核对收据本身及 12 个绑定产物哈希、字节数 |
| 独立审计 PASS (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/c3_risk_train_refinement_v1/saved_outputs_independent_audit_v1r1_retry2.json`) | `59975167F01786A63F0F13F6836E8FE9599BB1AFE0B66DFECA9FBB9B0DC43792` |
| 账户运行 manifest (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/c3_risk_train_refinement_v1/training_output_v1r1/run_manifest.json`) | `E2E2C257D9630A57CD34D54B2A54FE1305DF712B004AE0E9E9823B2A4D39741F`；读年为 2020 warmup、2021、2022；禁止年列表为空；16 组；每边手续费/滑点均 5 bp |
| 批准 execution lock (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/c3_risk_train_refinement_v1/execution_lock_root_approved_v1r1_technical.json`) | `577AA9A446F91CD0B070FC9ED1422338C53A6BB39E2FBC9187AA8663B778698F`；本独立 runner 无单独 Freqtrade config，配置哈希 N/A |
| 账户汇总 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/c3_risk_train_refinement_v1/training_output_v1r1/account_summaries.json`) | `95265CD0D45257ED35B24E40A1A82DF460A0A433B3ED8ED6C766A0855CE500ED` |
| 条件指标 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/c3_risk_train_refinement_v1/training_output_v1r1/conditional_metrics.csv`) | `26A013F45B239212A2159D058CBC529A5D6713A03C4F0CB639BC094CC346822C` |
| 交易 ledger (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/c3_risk_train_refinement_v1/training_output_v1r1/trade_ledger.csv`) | `1D01F6BE725C6D78A270AE4CDD0FE8A279F1644E291C4E143DA8C7A3403BECDB`；报告按 V1R1 的 `study_arm` 映射策略臂（并与 `route` 交叉核对） |
| 持有期 MAE 上下界 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/c3_risk_train_refinement_v1/training_output_v1r1/held_mae_bounds.csv`) | `85395E453F68B155C0EC39549D3362D220A9D977A24AEA88C343D7AA1B27E535` |
| E0 成交固定期限标签 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/c3_risk_train_refinement_v1/training_output_v1r1/e0_fill_horizon_labels.csv`) | `B8C247E45EF452891AC9E8398E560884EDE0B812FC49F984477C786F8BFC7F1A` |
| 全来源固定期限标签 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/c3_risk_train_refinement_v1/training_output_v1r1/horizon_labels.csv`) | `385562853C228C8BFC9D21C2FF86E06D07AFB86873D630356EB4952FD2DF05A4` |
| NAV rows (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/c3_risk_train_refinement_v1/training_output_v1r1/nav_rows.csv`) | `103DB7B4E4350D33FEFBD85E5C26795AA481BCF077138FD3DBCA9C6CF595157A`；小时 marked MDD 从含初始 anchor 序列计算 |
| 保存预测诊断 JSON (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/c3_risk_train_refinement_v1/saved_only_train_cal_diagnostics_v1r1.json`) | `D15CE0565237254C36C1901E62C259591C2581204DB56A708563043BFB73DBFA`；仅描述性、保存预测诊断 |
| 本轮账户研究冻结协议 (`provenance:nonincluded/crypto-leverage/docs/C3_ENTRY_RISK_TRAINING_ONLY_CONDITIONAL_STUDY_V1R1_DRAFT_20261002.md`) | `376B6403D7558220D57D7D24DD92C03FCAE9EE50CE50074491BF6397D730ECD1`；保存预测诊断协议另见 V1R1 (`provenance:nonincluded/crypto-leverage/docs/C3_RISK_TRAIN_REFINEMENT_PROTOCOL_V1R1.md`) |
| 账户 runner (`provenance:nonincluded/crypto-leverage/scripts/run_c3_risk_train_refinement_v1r1.py`) | 16 组账户只执行一次；哈希应以批准锁/运行 manifest 记录为准 |

**全项目检查状态：** 本轮没有运行全局 source-copy/import/inventory/report rebuild 或全套 pytest。它们会触及与本轮训练窗口无关或封存的未来数据/产物；训练研究仅运行获批的 scoped synthetic suite 与单次账户回放。全局 pipeline 与全套 pytest 明确 `NOT_RUN`。
