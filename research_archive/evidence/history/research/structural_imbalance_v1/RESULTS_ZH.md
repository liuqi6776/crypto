> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 结构性失衡 / 跨市场 / 波动状态研究 — 最终结果（v1）

- 生成时间（UTC）：2026-10-18T23:53:16Z
- 工作目录：`research/structural_imbalance_v1/`（独立，不修改 `research_hub/` 的既有卡片与冻结报告）
- 协议：PROTOCOL_V1.md (`provenance:nonincluded/crypto-leverage/research/structural_imbalance_v1/PROTOCOL_V1.md`)；修正：PROTOCOL_AMENDMENT_V1_1.md (`provenance:nonincluded/crypto-leverage/research/structural_imbalance_v1/PROTOCOL_AMENDMENT_V1_1.md`)
- 预注册哈希：PREREGISTRATION.json (`provenance:nonincluded/crypto-leverage/research/structural_imbalance_v1/PREREGISTRATION.json`)；代码冻结：ledger/CODE_FREEZE_R3.json (`provenance:nonincluded/crypto-leverage/research/structural_imbalance_v1/ledger/CODE_FREEZE_R3.json`)

## 0. 结论（先说结论）

**没有找到可以称为「可能有效」的策略。** 3 轮共 30 个预注册假设，加上 1 次一次性严测（2024 块）与 0 次保留块确认：

- 第 1 轮：10/10 未过粗筛（全部为反转/套利类机制，在发现面板上方向为负）。
- 第 2 轮：10/10 未过粗筛；其中 `R2-H09`（用横截面资金费率离散度过滤趋势）是唯一「均值、置信区间、四个币符号」都为正的假设，仅因 v1 的 8×均值尾部规则被淘汰。
- 第 3 轮：按修正 v1.1 把 `R2-H09` 以 `R3-H01` 原样带入；它是 10 个假设中唯一通过粗筛的。2024 一次性严测结果：**基础成本 −20.55%、压力成本 −40.91%、最大回撤 −33.2% / −46.7%、590 个回合、4 个币全部亏损**，9 项严测条件全部失败。
- 因此没有候选进入 2026 保留块；保留块仍未使用。

这一结果的意义不是「市场没有 alpha」，而是：**在这份 4 币、2020–2026 的本地永续数据上，用本协议能检验的结构性假设中，没有一个在一次性样本外测试里站得住。** 最像候选的那个假设，恰好展示了样本内筛选与样本外检验的差距。

---

## 1. 先读了什么：research hub 的现状

研究总目录（`research_hub/RESEARCH_MASTER_INDEX_ZH.md`）给出的底线很清楚：

- **没有策略或因子通过九门、可部署。** 2026-10-11 的因子复核结论是：方差块只作历史风险预测，funding 作成本，EMA200 作基准。
- **已有结果以负结果为主。** Core3 方差消融 `eligible=0/selected=null`；成交量活动类模型只有活动/安静期信息，没有方向；EMA 方向/量能/shock 组合在 2025 基础与压力情景均亏；新闻事件、ETH/BTC lead-lag、GARCH/HAR（泄漏作废）、MTF maker、Channel-ML、BB 回撤等均未通过。
- **2025 不是未触碰 OOS。** 多数历史窗口已被既有研究使用；`trend_common_account` 的 EMA200 2025 基础/压力为 +10.27%/+7.72%，但仍是已暴露历史、且不是策略通行证。
- **数据身份状态不完整。** 2026-10-16 的全局 manifest 为 `all_copies_verified=false`；但 Core4 的 12 个 1h trade/mark/funding 文件在 staging 中有分区绑定与哈希证据，本研究只读这 12 个文件加一个 DVOL 外部参照。

这解释了为什么本研究把「先预注册、再一次严测」作为核心：既有的失败大多不是没想法，而是想法在同一个历史上被反复修改。

---

## 2. 研究设计：如何避免「在回测里试出来」

| 机制 | 做法 |
|---|---|
| 假设先于数据 | 每轮 10 个假设的定义、单一参数组、持有期、淘汰标准在运行前写入 JSON 并 SHA256 冻结；运行器拒绝未冻结的 ID。 |
| 测试集一次性 | 发现面板 D（2020-08 至 2022-12）只用于粗筛；严测块 2023/2024/2025 互斥且永不复用；2026 保留块每个候选族一次。 |
| 假设只严测一次 | `ledger/HYPOTHESES.jsonl` 追加式；同一 ID 不能二次严测；修订必须新 ID 并写入 lineage。 |
| 多重检验 | 每轮 10 个严测 p 值做 Benjamini–Hochberg（q=0.10）。 |
| 市场 beta 对照 | 严测要求对 BTC 日收益回归的 alpha > 0，且 bootstrap p < 0.05；单纯牛市做多不算通过。 |
| 成本与资金费 | base 5bp/边 + 5bp 滑点；stress 10bp + 10bp；原生 8h funding 事件，逐事件现金流。 |
| 风险 | 1x 毛敞口硬上限；逐小时 mark NAV；MDD < 30%；单币/单月集中度限制。 |

测试块预算的实际使用：

| 块 | 状态 | 使用者 |
|---|---|---|
| R1_2023 | 未使用 | — |
| R2_2024 | 已用 | Round 3 / R3-H01 |
| R3_2025 | 未使用 | — |
| H_2026 | 未使用 | — |

> 历史窗口本身已被既有研究使用过，因此本研究**不声称**全局未触碰 OOS。它声称的是：对本协议新提出的假设，假设先于该块，且该块未被本工作线重复使用。

---

## 3. 三轮假设与结果

### 第 1 轮（2023 块，未消费；粗筛通过 0/10）

| ID | 机制 | 主题 | 回合 | 每回合净收益 | CI 下界 | 最差回合 | 判定 |
|---|---|---|---:|---:|---:|---:|---|
| R1-H01 | Funding-extreme positioning reversion (time series) | 结构性失衡 | 144 | -1.291% | -2.728% | -56.6% | `COARSE_FAIL` |
| R1-H02 | Post-settlement unwind after large funding | 结构性失衡 | 1717 | -0.140% | -0.235% | -12.8% | `COARSE_FAIL` |
| R1-H03 | BTC shock and alt underreaction | 跨市场信息传递 | 240 | -0.279% | -0.666% | -22.4% | `COARSE_FAIL` |
| R1-H04 | Alt/BTC ratio reversion | 跨市场信息传递 | 495 | -0.941% | -1.843% | -72.8% | `COARSE_FAIL` |
| R1-H05 | Trend regime filter (EMA200 + variance ratio + volatility state) | 波动率与市场状态 | 40 | +5.412% | -1.079% | -9.2% | `COARSE_FAIL` |
| R1-H06 | Volatility-compression breakout | 波动率与市场状态 | 631 | -0.055% | -0.386% | -15.5% | `COARSE_FAIL` |
| R1-H07 | Liquidation-cascade exhaustion | 结构性失衡 | 494 | -0.634% | -1.294% | -43.5% | `COARSE_FAIL` |
| R1-H08 | Funding-volatility convexity | 结构性失衡 | 164 | -0.483% | -2.050% | -39.9% | `COARSE_FAIL` |
| R1-H09 | Cross-sectional funding dispersion (long low / short high) | 跨市场信息传递 | 168 | +0.484% | -2.783% | -112.2% | `COARSE_FAIL` |
| R1-H10 | Options-implied vs realized volatility (DVOL variance risk premium) | 跨市场信息传递 | 95 | -1.316% | -3.901% | -39.8% | `COARSE_FAIL` |

### 第 2 轮（2024 块，未消费；粗筛通过 0/10）

| ID | 机制 | 主题 | 回合 | 每回合净收益 | CI 下界 | 最差回合 | 判定 |
|---|---|---|---:|---:|---:|---:|---|
| R2-H01 | Dispersion-conditioned relative momentum | 跨市场信息传递 | 67 | +1.485% | -2.698% | -43.9% | `COARSE_FAIL` |
| R2-H02 | Funding acceleration as leveraged flow | 结构性失衡 | 293 | +0.726% | -0.174% | -25.8% | `COARSE_FAIL` |
| R2-H03 | Funding-trend confirmation | 结构性失衡 | 875 | -0.237% | -0.581% | -19.5% | `COARSE_FAIL` |
| R2-H04 | Regime switch: trend in high-vol trending states, carry otherwise | 波动率与市场状态 | 165 | +0.496% | -2.777% | -112.2% | `COARSE_FAIL` |
| R2-H05 | Variance-risk-premium sizing of trend | 波动率与市场状态 | 236 | +1.546% | -0.112% | -16.4% | `COARSE_FAIL` |
| R2-H06 | Correlation-breakdown pairs | 跨市场信息传递 | 235 | -1.004% | -2.283% | -72.8% | `COARSE_FAIL` |
| R2-H07 | Volatility-spillover continuation | 跨市场信息传递 | 133 | -0.208% | -1.385% | -41.9% | `COARSE_FAIL` |
| R2-H08 | Pre-settlement carry drift | 结构性失衡 | 2255 | -0.171% | -0.268% | -21.0% | `COARSE_FAIL` |
| R2-H09 | Uncrowded trend filter via cross-sectional funding dispersion | 波动率与市场状态 | 1053 | +0.274% | +0.012% | -17.2% | `COARSE_FAIL` |
| R2-H10 | BTC dominance rotation | 跨市场信息传递 | 76 | +16.419% | -6.302% | -207.3% | `COARSE_FAIL` |

### 第 3 轮（2024 块，已消费；粗筛通过 1/10）

| ID | 机制 | 主题 | 回合 | 每回合净收益 | CI 下界 | 最差回合 | 判定 |
|---|---|---|---:|---:|---:|---:|---|
| R3-H01 | Uncrowded trend filter (carried from R2-H09) | 结构性失衡 | 1053 | +0.274% | +0.012% | -17.2% | `STRICT_FAIL` |
| R3-H02 | Aggressor-imbalance momentum | 结构性失衡 | 1544 | +0.058% | -0.233% | -36.6% | `COARSE_FAIL` |
| R3-H03 | Aggressor-flow absorption divergence | 结构性失衡 | 250 | -0.112% | -0.910% | -47.1% | `COARSE_FAIL` |
| R3-H04 | Close-location pressure trend | 结构性失衡 | 1416 | -0.441% | -0.740% | -37.6% | `COARSE_FAIL` |
| R3-H05 | Large-trade flow shock | 结构性失衡 | 237 | +0.110% | -0.409% | -15.3% | `COARSE_FAIL` |
| R3-H06 | Mark-trade basis stress | 结构性失衡 | 3151 | -0.170% | -0.293% | -33.0% | `COARSE_FAIL` |
| R3-H07 | BTC volume-share rotation | 跨市场信息传递 | 129 | -0.429% | -3.540% | -104.9% | `COARSE_FAIL` |
| R3-H08 | DVOL shock direction | 跨市场信息传递 | 188 | -0.659% | -1.548% | -29.1% | `COARSE_FAIL` |
| R3-H09 | Cross-sectional aggressor-imbalance dispersion | 结构性失衡 | 170 | +4.534% | -0.754% | -69.5% | `COARSE_FAIL` |
| R3-H10 | Beta-neutral funding carry | 结构性失衡 | 166 | +0.105% | -3.326% | -111.7% | `COARSE_FAIL` |

`R3-H01` 的 2024 严测（一次性）：

| 情景 | 净收益 | 最大回撤 | Sharpe | beta | alpha（年化） | alpha p | PF | 回合 | 盈利币数 | 费用 | funding |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| base | -20.55% | -33.17% | -0.63 | 0.32 | -47.47% | 0.949 | 0.86 | 590 | 0 | 1365 | -402 |
| stress | -40.91% | -46.73% | -1.58 | 0.32 | -76.81% | 0.996 | 0.71 | 590 | 0 | 2371 | -353 |

失败项（base）：`base_net_return<=0`、`stress_net_return<=0`、`profit_factor<=1.1`、`beta_adjusted_alpha<=0`、`alpha_p>=0.05`、`sharpe<=0.5`、`fewer_than_2_positive_symbols`、`single_symbol_share>0.65`、`single_month_share>0.50`。

---

## 4. 为什么失败：逐轮归因

### 第 1 轮：反转/套利机制在 2020–2022 全部反向

十个假设里，资金费率极值反转、结算后反转、BTC 冲击后 alt 补涨、alt/BTC 比价回归、压缩突破、清算衰竭，全部在发现面板上每回合净收益为负。原始事件研究也显示：资金费率 z≥+2 之后做空 BTC/BNB 的 24h 均值是**正**的（+0.69%/+1.80%），即拥挤方向继续，而不是反转。

这不是「机制一定不存在」，而是：**在这段样本里，反转类假设的方向被趋势/动量支配，且 24h/48h 的持有期不足以覆盖双边成本。** 两个例外（R1-H05 趋势状态过滤、R1-H09 横截面资金费率）虽然有正均值，但样本量或置信区间不达标。

### 第 2 轮：延续/流量机制普遍过不了置信区间

`R2-H02`（资金费率加速度，293 回合，+0.73%/回合）、`R2-H05`（DVOL 风险溢价给趋势定权重，236 回合，+1.55%/回合）都有正均值，但 95% 聚类 bootstrap 下界仍然跨零；`R2-H10`（BTC 主导轮动）均值很大（+16.4%/周）但单回合最差 −207%，是典型的高方差相对交易。

`R2-H09` 是唯一在四项上都为正的：1053 回合、+0.27%/回合、CI 下界 +0.00012、4/4 币为正。它只失败在 v1 的 `worst < −8×mean` 尾部规则（最差 −17.2%）。这条规则把「波动」和「灾难」混在一起，是协议设计缺陷；修正 v1.1 把它改成固定的 −50% 名义额边界，并明确披露这是看到第 2 轮结果后的修正。

### 第 3 轮：新信息源没有救回来，唯一候选在 2024 失败

第 3 轮引入此前未用过的字段：主动买入占比（taker buy share）、平均单笔规模（quote_volume/trade_count）、收盘位置压力（CLV）、mark-trade 基差、BTC 成交量份额、DVOL 一阶差分。九个新假设全部未过粗筛：主动买入动量 `R3-H02` 有 1544 回合、+0.058%/回合，但 CI 跨零；其余方向为负或符号覆盖不足。

`R3-H01` 在 2024 的表现把失败原因写得很清楚：

1. **过滤器的符号反了。** 2024 年，资金费率离散度**高**时的未来 24h 均值在四个币上都是 +0.47%～+0.62%，离散度**低**时是 −0.17%～+0.11%。`R3-H01` 只在低离散度时做多，等于系统性地选错了状态。
2. **换手太高。** 过滤器在一年内开关 349 次，590 个平仓回合，费用 1,365 USDT（初始资本的 13.7%）。在一个每回合只有几十 bp 边际的信号上，这个费用足以把正期望变成负的。
3. **它毁掉了一个本来为正的趋势年。** 同一引擎、同一 2024 块，未过滤的 EMA200 H4 四币等权 1x 基础成本为 **+24.32%**（MDD −30.31%），压力成本 +6.92%（MDD −36.22%）；过滤后变成 −20.55%（MDD −33.17%）。也就是说，这个「过滤器」不是在做 alpha，而是在做反向择时。

---

## 5. 「自然找到」还是「试出来」：把这件事说清楚

本工作线一共做了 **30 次粗筛 + 1 次严测 + 0 次保留块确认**。在这个试验次数下：

- 即使所有假设都无效，按 5% 单次显著性，出现至少一个「看起来显著」的结果的概率约为 1 − 0.95³¹ ≈ 80%。所以**任何单个 p<0.05 都不足以称为发现**；本协议用每轮 BH + beta 调整 alpha + 一次性块来压制这一点。
- 唯一通过粗筛的 `R3-H01` 在严测中失败，且失败方向（过滤器符号）可以在数据里被解释。这反而说明流程在工作：**样本内筛选出的「候选」，在样本外没有活下来。**
- 因此本报告的结论是**负结果**，而不是「找到了但还差一点」。没有策略被升级，没有候选进入 2026 保留块。

如果未来要继续，最诚实的下一步不是把 `R3-H01` 的过滤器反号再试（那正是「试出来」），而是：

1. 先写一个**新的、独立的**假设：把横截面资金费率离散度当作「趋势强度/拥挤度」而不是「脆弱度」，并预先声明方向、持有期、换手控制（例如只在离散度状态持续 N 天后切换，或月度而不是逐日切换）。
2. 用 **2025 块**做一次性严测（当前未使用），再用 **2026 保留块**做确认；两段都过才算候选。
3. 在严测里同时报告「过滤器增量」相对未过滤 EMA200 的差，而不是只看绝对收益；否则任何牛市里的多头过滤都可能看起来不错。
4. 把 family-wise error 控制在 0.05 以下（例如 Bonferroni 0.05/新增试验数），而不是每轮独立 BH。

---

## 6. 九门状态（本工作线不能声称什么）

| 门 | 状态 | 说明 |
|---|---|---|
| 1 数据完整性 | 部分 | Core4 12 个 1h 文件有 staging 分区绑定与哈希；DVOL 是外部参照，真实发布时间未知。 |
| 2 实现 | 部分 | 自测覆盖因果、账本恒等、缺口、资金费符号、1x cap；未做 Freqtrade lookahead/recursive。 |
| 3 样本内研究 | 有 | 发现面板 + 机制说明 + 每轮 10 个假设。 |
| 4 未触碰 OOS | 无 | 2023/2024 是已暴露历史；2026 保留块未使用，因此没有确认性 OOS。 |
| 5 交易现实 | 部分 | 双边费用、滑点、原生 funding 已计；无真实盘口/容量/费率等级。 |
| 6 稳健性 | 部分 | 双成本情景 + 分币/分月；没有参数邻域（协议禁止扫参）。 |
| 7 杠杆/清算 | 无 | 仅 1x；无逐档保证金/清算路径。 |
| 8 dry-run | 未跑 | 没有执行系统。 |
| 9 实盘观察 | 无 | 研究-only。 |

---

## 7. 复现与文件索引

```powershell
# 从工作区根目录
.venv\Scripts\python.exe research\structural_imbalance_v1\code\freeze.py          # 校验/追加预注册哈希
.venv\Scripts\python.exe research\structural_imbalance_v1\code\runner.py 1 --phase all
.venv\Scripts\python.exe research\structural_imbalance_v1\code\runner.py 2 --phase all
.venv\Scripts\python.exe research\structural_imbalance_v1\code\runner.py 3 --phase all
.venv\Scripts\python.exe -m pytest research\structural_imbalance_v1\tests -q
```

| 文件 | 内容 |
|---|---|
| `PROTOCOL_V1.md` / `PROTOCOL_AMENDMENT_V1_1.md` | 预注册协议与尾部规则修正 |
| `round{1,2,3}_hypotheses.json` | 每轮 10 个假设的冻结定义 |
| `ledger/HYPOTHESES.jsonl` | 30 条追加式判定记录（含粗筛/严测/归因） |
| `ledger/TEST_SET_USAGE.json` | 测试块预算（仅 2024 被第 3 轮使用） |
| `ledger/ROUNDS.json` | 每轮汇总、BH、候选 |
| `ledger/CODE_FREEZE_R3.json` | 第 3 轮运行时的代码/环境哈希 |
| `runs/round*_*/` | 每个假设的 coarse/strict JSON、NAV、episodes、fills |
| `runs/diagnostics_2024.json` | 2024 失败的事后诊断（已消费块，仅诊断） |
| `code/` | 数据读取、信号、账户引擎、指标、runner、报告生成 |
| `tests/` | 9 项引擎/因果/账本测试 |

> 所有数字来自本地只读数据与本研究自己的模拟；不构成投资建议，也不代表可交易。

