> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 市场状态路由 Phase B/账户实验：最终审查摘要

**报告日期：2026-09-30。状态：探索性研究（EXPLORATORY）。本报告没有批准任何策略用于实盘或实盘模拟。**

本报告由冻结的路由结果、已审批协议/锁、此前 Phase B forecast-only 报告，以及独立账户输出审计派生。没有重新读市场源文件、future-target 文件或 2024 年及以后数据，也没有重跑模型/回测。每个 arm × feature/model × cost case 是独立的 100,000 USDT 账户，BTC/ETH/SOL/BNB 共用该配置账户资金；不同配置不合并。该阶段的账户考察范围只有 2023 exposed development。

## 核心结果

| Cell | 解释 | 2023 净收益 | 日 Sharpe | 最大回撤 | 平仓笔数 | 最大标记敞口 / 初始权益 |
|---|---|---:|---:|---:|---:|---:|
| B1_X1 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/market_regime_round1_20260930/final_review_v1/B1_X1.md`) | 冻结 X1 趋势臂基准 | 22.79% | 1.663 | -7.49% | 44 | 67.91% |
| B3_X3 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/market_regime_round1_20260930/final_review_v1/B3_X3.md`) | 冻结 X3 趋势臂基准 | 24.53% | 1.802 | -7.45% | 43 | 67.91% |
| R (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/market_regime_round1_20260930/final_review_v1/R.md`) | range 单臂 | 1.52% | 0.643 | -1.22% | 21 | 24.95% |
| U (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/market_regime_round1_20260930/final_review_v1/U.md`) | X3 与 range 常量组合 | 13.00% | 1.848 | -3.25% | 63 | 33.95% |
| V (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/market_regime_round1_20260930/final_review_v1/V.md`) | 波动预算组合 | 8.14% | 1.719 | -2.38% | 63 | 30.17% |
| SM (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/market_regime_round1_20260930/final_review_v1/SM.md`) | 确定性状态路由 | 19.31% | 1.903 | -4.12% | 3 | 57.98% |
| PM0 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/market_regime_round1_20260930/final_review_v1/PM0.md`) | 状态路由 + S0 自身价格概率 | 10.60% | 2.024 | -1.81% | 3 | 41.27% |
| PM1 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/market_regime_round1_20260930/final_review_v1/PM1.md`) | 状态路由 + S1 自身价格/BTC 概率 | 10.40% | 2.029 | -1.75% | 3 | 40.89% |
| PM2 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/market_regime_round1_20260930/final_review_v1/PM2.md`) | 状态路由 + S2 taker-buy quote 概率 | 10.46% | 2.027 | -1.77% | 3 | 41.00% |

比较范围是同一固定 account engine 下的 2023 独立账户。低回撤往往伴随更低投入/暴露，不能单凭它推断 alpha。所有 Sharpe 均来自一年、且为开发暴露期；SM/PM 的 3 笔交易尤其不足以支撑稳定性结论。

与此分开，既有 X3 多年基准此前报告的 2021–23 CAGR 约 8.11%、Sharpe 约 0.905；这不是本轮 fresh-start 2023 账户。2023 单年净收益 24.53% 不能替代多年结果，也不能被说成稳定的年化水平。

- X3 frozen trend baseline 的 primary 回报 24.53%、Sharpe 1.802、43 笔；X1 baseline 为 22.79%、Sharpe 1.663、44 笔。
- Range-only R 为 1.52%、Sharpe 0.643、21 笔。它的回撤较低但暴露也低；当前 box/rebound trigger 的时间顺序有案例支持，水平区间稳定性/均值回复结构优势仍未证明。
- SM 为 19.31%、Sharpe 1.903，但只有 3 笔：BNB range +467.40 USDT、BTC trend +4,368.93、SOL trend +14,472.96。结果主要依赖两笔 10–11 月趋势盈利和一笔 range 事件，不代表频繁且稳定的策略切换。
- PM0/1/2 分别有 3 笔交易，primary 收益约 10.40–10.60%，Sharpe 约 2.02。Sharpe 的样本基础过薄；同三笔成交下，PM2 比 PM1 的点估计收益只高约 0.06 个百分点，不能证明模型/路由增量。
- U/V 为固定组合/预算对照；回撤或暴露降低不是额外 alpha 的证据。Fresh 2023 returns 不可推广为稳定年化，也不可与历史多年度绩效混称。

各单元完整 primary/sensitivity/stress 表、九门状态和依据见：B1_X1 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/market_regime_round1_20260930/final_review_v1/B1_X1.md`), B3_X3 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/market_regime_round1_20260930/final_review_v1/B3_X3.md`), R (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/market_regime_round1_20260930/final_review_v1/R.md`), U (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/market_regime_round1_20260930/final_review_v1/U.md`), V (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/market_regime_round1_20260930/final_review_v1/V.md`), SM (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/market_regime_round1_20260930/final_review_v1/SM.md`), PM0 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/market_regime_round1_20260930/final_review_v1/PM0.md`), PM1 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/market_regime_round1_20260930/final_review_v1/PM1.md`), PM2 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/market_regime_round1_20260930/final_review_v1/PM2.md`)。

## 成本、配对差异与会计核对

三个成本情景分别为 primary 5+5bp/边、sensitivity 2+5bp/边、stress 5+10bp/边。冻结信号安排/仓位规则相同；每个场景账户按当时现金约束接受或跳过候选，因此不假定不同成本的实际入场 ID 必然相同。三种成本情景是敏感性检查，不是现实点差/滑点/容量的实测。

| 冻结比较（差值方向按 key） | 2023 日均收益差 95% CI | Sharpe 差 95% CI | CI 是否跨 0 |
|---|---:|---:|---|
| `B1_X1_vs_B3` | [-0.017%, 0.021%] | [-0.470, 0.729] | 包含 0 |
| `B1_X1_vs_U` | [-0.008%, 0.074%] | [-0.587, 0.600] | 包含 0 |
| `R_vs_B3` | [-0.148%, 0.017%] | [-3.697, 1.693] | 包含 0 |
| `R_vs_U` | [-0.076%, 0.009%] | [-3.446, 1.280] | 包含 0 |
| `V_vs_B3` | [-0.100%, 0.009%] | [-0.538, 0.461] | 包含 0 |
| `V_vs_U` | [-0.028%, 0.002%] | [-0.391, 0.218] | 包含 0 |
| `SM_vs_B3` | [-0.032%, 0.026%] | [-0.590, 1.885] | 包含 0 |
| `SM_vs_U` | [-0.009%, 0.072%] | [-0.655, 1.770] | 包含 0 |
| `PM0_vs_B3` | [-0.074%, 0.017%] | [-0.522, 1.862] | 包含 0 |
| `PM0_vs_U` | [-0.018%, 0.017%] | [-0.639, 1.748] | 包含 0 |
| `PM1_vs_B3` | [-0.075%, 0.016%] | [-0.519, 1.856] | 包含 0 |
| `PM1_vs_U` | [-0.019%, 0.017%] | [-0.640, 1.742] | 包含 0 |
| `PM2_vs_B3` | [-0.075%, 0.016%] | [-0.520, 1.858] | 包含 0 |
| `PM2_vs_U` | [-0.019%, 0.017%] | [-0.640, 1.744] | 包含 0 |

Bootstrap 为 365 个配对日、28 日连续块、1,000 次描述性重采样，无模型/单元选择校正。Sharpe 重采样中零波动样本按实现约定记 0；实际平坦账户 Sharpe 为 N/A，因此不得将该约定的 0 当成有效改善。每个对照区间均跨 0，不能声称显著增量。

独立审计 routing_v4_output_audit_report_v2.md (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/market_regime_round1_20260930/routing_v4_output_audit_report_v2.md`)（SHA256 `D7D08756E58FFB6380DE30EFCD5F7A5FD39612D922FAD521719E1BA9D5AD28F1`）和 manifest（SHA256 `48019D9822B19F6262C4548582226DA80EA1BBB202519571E27FB741A974E8B8`）核验 27/27 cells：365 日收益/Sharpe/DD 与冻结输出一致、事件现金非负、终端持仓为零、无 2024+ NAV、无时间倒置；最大终值 PnL 残差 2.11e-10 USDT。**这是账本/输出一致性通过，不是源数据、交易执行或交易准备门通过。**

## 路由机制与收益集中

冻结路由候选中，趋势候选 58 个：SM/PM 接受 2 个 X3 趋势候选并将 56 个路由到现金；25 个 range 候选中接受 1 个、1 个因 gap 跳过、23 个路由现金。SM 因而只有 3 笔成交。没有用 X3 的 43 笔减去路由的 3 笔来估算“漏掉交易”，因为候选接受顺序、现金与已持仓状态改变了后续可成交性。详细处置与错误分支见 routing_failure_diagnostics_v1.md (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/market_regime_round1_20260930/routing_failure_diagnostics_v1/routing_failure_diagnostics_v1.md`)（派生审计，不是反事实账户净收益）。

下表是 X3 baseline 的 top-positive-decile 诊断候选（仅两个固定 ID，并非 X3 全部盈利交易）。数字为各账户实际执行这些 candidate ID 时的净 PnL；“未成交”不是零收益估计。

| 候选 | candidate ID | 各 cell primary 实际 PnL USDT |
|---|---|---|
| BNB X3 2023-12-20（路由诊断标记为 CHANNEL_REJECTION_CANDIDATE） | `BNBUSDT|TREND|2023-12-20T15:59:59.999+00:00` | B1_X1: 575.75；B3_X3: 4,726.54；R: 未成交；U: 2,363.27；V: 1,832.18；SM: 未成交；PM0: 未成交；PM1: 未成交；PM2: 未成交 |
| SOL X3 2023-10-19 | `SOLUSDT|TREND|2023-10-19T19:59:59.999+00:00` | B1_X1: 13,472.09；B3_X3: 14,472.96；R: 未成交；U: 7,236.48；V: 3,969.94；SM: 14,472.96；PM0: 5,762.46；PM1: 5,559.54；PM2: 5,620.82 |

X3 的 BNB 2023-12-20 top candidate 被状态路由判为 `CHANNEL_REJECTION_CANDIDATE`，不是 uncertain；SOL 2023-10-19 top candidate 被保留。SM/PM 保留 SOL top-winner 而未保留 BNB top-winner；按 B3 基准 PnL 权重计算，SM/PM 所保留候选 ID 的覆盖率为 75.38%；这不是 SM/PM 实际账户利润的保留比例，实际 PM 单笔 PnL 以事件表为准。这是两项赢家的集中度诊断，不能代替全收益/可执行性比较。另一派生诊断将 X3 未选 cohort 列为 41 个成交机会，其中 9 个赢家合计 +15,982.50 USDT、32 个亏损合计 −10,297.50 USDT；这个筛选 cohort 不是可重放的路由账户差额，不能把它与 SM 终值相减。

Range-only R 实际做成 21/25 个 frozen range entries，而状态路由 SM 只做成 1 笔 range entry。状态分类当前把大量候选分到 cash/`CHANNEL_REJECTION_CANDIDATE`，包括一个大的 BNB X3 机会；这表明硬性 cash gate 会错过上涨趋势中的获利突破。它提示要处理状态模糊/转场和软化参与度，并不证明 regime/range 思想整体无效。低 ER 或 range 标签也不能替代明确的水平结构证据。

## Phase B 预测证据

S0（自身价）、S1（自身价 + BTC）、S2（S1 + taker-buy quote proxy）都是 2021 fit / 2022 calibration / 2023 exposed development 的下一 24 小时状态持续概率模型；其训练目标是在已经标注为 UP 或 DOWN 的状态后预测 24 小时持续性。它们尚未预测 UNCERTAIN→趋势，也没有 range persistence 预测。概率不等于未来净收益。三个预注册 log-loss 对照均未达到判据且 CI 跨 0；在已经标注为 UP 或 DOWN 的样本中，未来 24h 方向持续的正例率 2022 约 0.168、2023 约 0.260，存在标签正例率漂移。详细报告：Phase B README (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/market_regime_round1_20260930/phase_b_final_review_v1/README.md`)。这只说明当前固定特征/年份/模型的预测证据不足，不能推论 BTC 或 taker 特征在其他设计下永远无效。

| 预注册主对照（log-loss，candidate − comparator） | 平均损失差 | 95% CI | Holm p（三项） | 判据通过 |
|---|---:|---:|---:|---|
| `S0_minus_2022_calibration_prevalence` | 0.0014 | [-0.0158, 0.0224] | 1.000 | 否 |
| `S1_minus_S0` | 0.0019 | [-0.0084, 0.0118] | 1.000 | 否 |
| `S2_minus_S1` | 0.0018 | [-0.0015, 0.0063] | 1.000 | 否 |

2022 calibration 样本 441 行、当前 UP/DOWN 状态样本中，未来 24h 方向持续的正例率 16.78%；2023 成熟 exposed-development 样本 515 行、对应正例率约 26.02%。这些是预测诊断，不等于账户净收益。

## 九门总表（9 个 cell 均适用）

| Gate | 状态 | 总体判断 |
|---|---|---|
| Gate 1 — source / data identity | **BLOCKED** | 批准锁和哈希绑定获准的 2020–23 输入；27/27 账户产物通过独立账务核对。但 funding 现金流采用此前已完成的真实 mark close 代理，而非结算时刻精确 mark；完整证据链也未证明交易所执行质量。 |
| Gate 2 — implementation / lookahead | **BLOCKED** | 协议/runner 静态审查、基线 parity 证据、因果时钟及独立输出审计支持本次实现；Freqtrade 完整 lookahead/recursive 检查与外部执行/成交验证尚未完成。 |
| Gate 3 — in-sample evidence | **NOT_RUN** | 本轮 2023 开发期探索性账户研究已经运行；独立的逐阶段账户内证据及搜索/筛选稳健性尚未完成。此处 NOT_RUN 指完整 Gate 3 尚未跑完，不是声称本轮没有研究。模型训练/校准/开发期依次为 2021/2022/2023，2023 已暴露。 |
| Gate 4 — untouched out-of-sample | **NOT_RUN** | 没有评估未触碰的样本外年份。本路由账户结果只有已暴露的 2023 开发期。 |
| Gate 5 — costs / fills | **BLOCKED** | 包括三组固定费率/滑点情景及观察到的 funding 事件；但滑点为固定 bp 代理、funding 使用代理 mark，真实点差、盘口冲击、容量和成交均未验证。 |
| Gate 6 — robustness | **NOT_RUN** | 覆盖四个币种、三组固定成本情景和 2023 账户诊断；没有未触碰年份、广泛市场状态/参数邻域或独立复现。 |
| Gate 7 — leverage / liquidation | **BLOCKED** | 账户为 1x，初始权益风险预算 0.5%，每笔/每币初始权益名义本金上限 25%（不是账户总上限）；未建模保证金、维持保证金、强平或杠杆影响。 |
| Gate 8 — observation / paper forward | **NOT_RUN** | 没有独立的前瞻 dry-run 或模拟成交观察期。 |
| Gate 9 — live readiness | **BLOCKED** | 工作区禁止实盘交易；没有部署授权或生产执行证据。 |

## 决定与下一步

**不选择新路由 arm，也不放大风险。** 保留已经表现较好的 frozen X3 趋势臂为比较对象；后续研究优先测试保留核心趋势收益的软性入场质量/风险预算调整，并单独预注册状态转场和漏掉获利突破的错误成本。Range 候选先补充结构稳定性/跨年机制证据，不把一次 lower-edge rebound 事件当成已经验证的均值回复专家。再做任何账户扩展前，需要新 protocol/lock、真正未触碰 OOS、精确 settlement mark/fill 证据、spread/impact 与保证金/强平模拟，以及每个策略的完整 Gate 报告。

## 输入身份与可复核路径

- Root-approved routing lock: `reports/strategy_validation/market_regime_round1_20260930/execution_lock_routing_root_approved_v1.json`, SHA256 `66689C6BA4DF1EDF1AF0A7739024D238BD0BB94A8DC2A48656D8D086E1C65098`.
- Routing preregistration V4: `docs/MARKET_REGIME_ROUTING_PREREGISTRATION_V4_20260930.md`, SHA256 `EDCF1ABE28F6F9F176EF03CE73374D9685E1938453EB0C09CA7E328ECC35468C`.
- Frozen output summary: `routing_root_approved_v4/phase_summary.json`, SHA256 `D0E18E88673B0C4A82E18C330B3E2BEFE1F2765F268D941D40C18AD0CFDD021F`.
- Output accounting audit manifest: `routing_root_approved_v4/independent_output_audit_manifest_v2.json`, SHA256 `48019D9822B19F6262C4548582226DA80EA1BBB202519571E27FB741A974E8B8`.
- Phase B model lock: `execution_lock_phase_b_v3_root_approved_v2.json`, SHA256 `C02D3FDE5AD9008CBED9F6E826CFDBBA8EDF84CABC42F4FF529EF896D8FF52E0`; Phase B result summary SHA256 `E87E7305293FA7A4D64A67468C0675D6F7C11CB1D54EE85FB40825DAB8218AB8`.
- Existing range-plan and adapter outputs are bound by the root lock; box geometry is a lower-edge rebound candidate mechanism, not established stationarity.
- No new market data, target-only labels, or future-year numeric values were read. No original Phase B or routing output/manifests were edited.

**Summary SHA256 list:** see manifest.json (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/market_regime_round1_20260930/final_review_v1/manifest.json`).
