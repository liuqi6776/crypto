> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 资金费率：结算缺口、双边成本与风险补充研究

研究日期：2026-10-17。状态：来源核查、正式成本运行、两套独立复算及工作区验证均已完成并记录；工作区测试并非全量通过。

**当前结论：按既有研究账本计算，资金费在完整结算子样本中可以抵消一部分价格损失，但尚不能证明能够稳定转化为可实现净收益。低成本下点估计转正，置信区间仍跨零，19 个未知周仍无法结算；观测到的约 24% 周内回撤已超过 5%、10%、20% 三档诊断线。两臂均维持 UNVERIFIED。**

## 研究边界

沿用上一版的 101 个排期周、CARRY_EQ 等权臂与 CARRY_BETA 事前 beta 调整臂、固定数量和每周全平重建规则。资金费、价格端点、币池和未知状态均不修改。2024–2025 年已经查看，本轮属于历史条件诊断，不是新的样本外测试。协议见 冻结前研究协议 (`provenance:nonincluded/crypto-leverage/docs/FUNDING_CARRY_SETTLEMENT_COST_V2_20261017.md`)。

排期决策范围为 2024-01-01 00:00 至 2025-12-01 00:00 UTC；入场参考为决策后一小时，计划持有 168 小时，最后退出参考为 2025-12-08 01:00 UTC。2024 年末跨年排期保持原定剔除状态。所有时刻为 UTC，不把这段不完整覆盖称为两个完整年度账户。

用户选择按最大回撤 5%、10%、20% 三档对照。这些是诊断线，不代表已认可某一档为实盘风险上限。以下资本口径为每周 10,000 USDT 固定参考资本；完整周的均值和加总不能冒充完整年度账户收益。

## 无法完整结算的周：没有找到符合原规则的补算依据

两臂共同涉及 19 个未知持仓周：2024 年 46 个活动周中 4 个未知，2025 年 48 个活动周中 15 个未知。按决策、币种和入场／退出去重，有 36 个案例；再合并共同端点，为 9 个币种的 23 个精确价格请求。

主审独立打开原始压缩档案和规范化文件，核验了 12 对文件及保存的官方校验和。21 个端点在两层记录中均为平坦 OHLC、成交量与成交笔数为零；RNDR 的一个所需月份本地缺失，MATIC 的一个精确时间行缺失。没有发现可通过修正读取方式恢复的有效成交端点。详见 独立原始端点核对 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_settlement_cost_v2_20261017/review/independent_raw_endpoint_check.json`)及 结算端点审计 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_settlement_cost_v2_20261017/source_audit/settlement_endpoint_audit.md`)。

相关生命周期公告只找到本地继承的研究摘要，没有找到完整、可核验的官方正文存档。因此，摘要中的截止日期不能升级为已证实的合约停止时刻，更不能提供结算价格。现货退市和资金费套利机器人结束也不等同于永续合约结算。该限定由 [公告来源补充审计](source_audit/notice_provenance_review.md)覆盖初始端点审计中较强的公告表述。

资金费核查还发现：ALPACA、BNX、FTM、MATIC、RNDR、UNFI、VIDT 在首次受影响价格端点之后仍有非零费率记录；BAKE/HIFI 在相关决策时的最近记录已约 64 小时没有更新。这既不能证明仓位可成交、可领取资金费，也不足以断言数据伪造。归档交叉核对仅验证资金费时刻与费率，不验证事件标记价格。报告中的“最近资金费”用于诊断，原策略的信号截止仍为决策前一小时；成交搜索仅限相关端点月份。详见 资金费与交易活动一致性 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_settlement_cost_v2_20261017/source_audit/funding_activity_consistency.md`)。

19 个未知周全部保留；不按最后成交价、标记价或改名币价格补结算，不事后改为空仓。这些缺失集中于交易活动异常的币种，不能假定与损益无关。

## 成本证据及计算口径

本地已登记的外部盘口经只读核查，仅有 BTC、ETH、SOL 在 2026 年的少量单点快照，不能校准目标时期及币池的交易成本。快照原始毫秒时刻换算后为 2026-09-19 约 06:36–06:37 UTC；原盘点误将 UTC+8 显示时间标作 UTC，已在新增计算前纠正并保留原稿。未在限定搜索范围内找到覆盖目标持仓的交易所成交和佣金记录。详见 成本证据盘点 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_settlement_cost_v2_20261017/source_audit/local_cost_evidence_inventory.md`)。

每边 5bp 手续费取自示例配置的占位假设，不是已核实的历史费率。在此基础上分别加每边 0、1、2、5、10bp 的价差与滑点合并摩擦，以及入场合计 7bp／退出合计 15bp 的非对称压力情景；另保留 0、20、50bp 对照，共九档。20／50bp 旧综合成本没有手续费与摩擦拆分证据，拆分列保持 N/A。

入场与退出分别按各自绝对名义金额收费，无跨周净额抵扣。净损益等于价格损益加资金费，减双边成本。固定数量重算不模拟滑点对数量、后续资金费、成交概率或选择的反馈。这是未校准成本的条件分析，不能把某个盈利档位称作实际主情景。

表中的资金费金额沿用旧研究账本根据固定持仓数量、记录费率和事件标记价计算的现金流，不是经过交易所账户流水核对的实收金额。“完整结算周”也仅指旧研究规则所需参考端点与资金费字段齐全，不代表已经证明真实成交和到账。

## 净收益：降低假设成本能转正，但优势没有得到确认

以下是每 10,000 USDT 固定参考资本的**完整活动周平均净损益，单位 USDT／周**。2024 年每臂仅 42 个完整周，2025 年仅 33 个完整周；未知周未填零、未混入均值。1bp=0.01%。

| 入场／退出总成本 bp | 2024 等权 | 2024 beta 调整 | 2025 等权 | 2025 beta 调整 |
| --- | ---: | ---: | ---: | ---: |
| 0／0 | +30.37 | +31.80 | +18.89 | +28.32 |
| 5／5 | +20.36 | +21.78 | +9.04 | +18.48 |
| 6／6 | +18.36 | +19.78 | +7.07 | +16.51 |
| 7／7 | +16.36 | +17.77 | +5.10 | +14.54 |
| 10／10 | +10.35 | +11.76 | −0.81 | +8.63 |
| 15／15 | +0.34 | +1.75 | −10.66 | −1.22 |
| 7／15 | +8.34 | +9.75 | −2.66 | +6.78 |
| 20／20 | −9.68 | −8.27 | −20.50 | −11.07 |
| 50／50 | −69.75 | −68.38 | −79.60 | −70.15 |

完整的费用拆分和区间见 [年度情景表](results_20261017T020727133643Z/annual_cost_scenarios.csv)，逐周结果见 周账本 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_settlement_cost_v2_20261017/results_20261017T020727133643Z/weekly_cost_scenarios.csv`)。这九档均为固定假设，不按结果选择“最合适”成本。

为说明分解，取预定网格中的 7／7bp（每边手续费假设 5bp，加摩擦假设 2bp；不是实际主情景）：

| 年份／组合 | 价格损益 | 资金费 | 双边总成本 | 净损益 | 净均值 95% 区间 |
| --- | ---: | ---: | ---: | ---: | --- |
| 2024 等权 | +10.64 | +19.73 | 14.02 | +16.36 | [−72.02, +118.23] |
| 2024 beta 调整 | +14.64 | +17.16 | 14.03 | +17.77 | [−79.59, +137.03] |
| 2025 等权 | −47.09 | +65.98 | 13.79 | +5.10 | [−113.94, +92.90] |
| 2025 beta 调整 | −41.61 | +69.93 | 13.79 | +14.54 | [−90.18, +95.38] |

2025 年等权组合的资金费先被价格损失消耗，再扣成本，只剩每周约 5.10 USDT。对同一完整子样本，等权／beta 调整的对称成本盈亏平衡点分别为：2024 年每边约 15.17／15.87bp，2025 年约 9.59／14.38bp。这些是已看历史子样本的代数阈值，不是可承受实际成本的可信下限。

**全部 36 个“年份×组合×成本”净均值 95% 区间均跨过零，包括零成本情景。** 区间采用四个排期周的非循环区块抽样，2,000 次，固定种子 20261017；未知及非活动排期保持缺失位置。该方法不能解决非随机缺失或已看历史的选择偏差。

对称成本网格的净均值和区间 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_settlement_cost_v2_20261017/%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/funding_carry_settlement_cost_v2_20261017/cost_uncertainty.png`)。

## 未知周：一点未观测亏损就可能抹掉子样本盈利

在 7／7bp 假设下，若仅问“全部计划活动周的等规模损益总和何时恰好为零”，未知周平均净损益需达到：

| 年份／组合 | 已知完整周净损益总和 | 未知周数 | 未知周平均盈亏平衡值 |
| --- | ---: | ---: | ---: |
| 2024 等权 | +686.93 | 4 | −171.73 |
| 2024 beta 调整 | +746.50 | 4 | −186.63 |
| 2025 等权 | +168.35 | 15 | −11.22 |
| 2025 beta 调整 | +479.76 | 15 | −31.98 |

例如，2025 年等权的 15 个未知周若平均净亏损超过 11.22 USDT，就足以抵消 33 个完整周的累计正值。此处只是 `−已知净损益总和÷未知周数` 的代数说明；没有估计未知损益，没有假设那些周能够建仓或平仓，更没有合成年账户。九档全表见 未知周盈亏平衡阈值 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_settlement_cost_v2_20261017/results_20261017T020727133643Z/unknown_week_break_even.csv`)。

## 三档风险对照：现有观测已经跨线

风险同时覆盖完整结算周与全部可观察标记价路径：2024 年每臂分别 42／44 周，2025 年分别 33／37 周。也就是说，另外 6 个退出未知周的风险路径仍在统计中；剩余 13 个未知周入场参考不完整，风险不能估计。所有观测均保留初始现金、169 个小时标记点，并仅在已知退出时额外加入现金结算点。

7／7bp 说明性假设下，全部可观察路径的结果如下；括号分母为可观察周数，各档超线次数相互包含：

| 年份／组合 | 最大周内峰谷回撤 | 超过 5% | 超过 10% | 超过 20% | 最差完整周净损益 USDT |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2024 等权 | 15.04% | 5／44 | 1／44 | 0／44 | −1,426.05 |
| 2024 beta 调整 | 16.16% | 4／44 | 1／44 | 0／44 | −1,559.78 |
| 2025 等权 | 24.07% | 13／37 | 2／37 | 1／37 | −793.25 |
| 2025 beta 调整 | 24.00% | 11／37 | 2／37 | 1／37 | −786.32 |

这里的周内回撤是小时采样净值从此前峰值的跌幅，不等于当周相对初始资本的亏损，也不是全年最大回撤。2025 年的最差周内路径来自 11 月 3 日决策周；2024 年来自 2 月 26 日决策周。完整周与全部可观察周的最大值在本次样本中相同，但两套样本分母均保留，不能据此把未知退出周删除。

低成本无法消除这个问题：零成本下，2025 年两臂周内回撤仍约为 24.04%／23.96%；预定九档中，2025 年两臂都至少有一个观测周超过 20%。因此，若将 5%、10%、20% 各档分别视为研究约束，现有风险代理均已出现超线，不能判断风险可接受。

组合也不是持续没有方向暴露。7／7bp 时，2025 年等权／beta 调整的最大总名义÷当时标记净值为 1.461／1.457 倍，最大绝对净名义÷净值为 32.08%／31.04%，最大绝对事前 beta 美元暴露÷净值为 58.85%／24.82%。beta 调整降低了该年的 beta 暴露峰值，但没有消除价格路径风险。跨年份两臂总名义÷净值最高约 1.556 倍；这些是持仓漂移后的观测比率，不是经过保证金模型验证的可用杠杆。

严格连续账户每年在第一次未知处停止。2024 年只完成最初 30 个排期周（25 个活动周、5 个空仓周），在 7 月 29 日未知入场处停止；7／7bp 下这段连续前缀回撤为等权 17.57%、beta 调整 19.33%。2025 年第一周即缺退出结算，只保留初始现金与 169 个标记观测、合计 170 点，完成周数为零。因此全年收益、Sharpe 和全年最大回撤继续为 N/A。没有跨越未知周复利，也没有缩仓以使某一风险档“通过”。

九档明细见 风险分组 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_settlement_cost_v2_20261017/results_20261017T020727133643Z/risk_summary.csv`)、逐周风险 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_settlement_cost_v2_20261017/results_20261017T020727133643Z/risk_weekly.csv`)及 严格连续账户前缀 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_settlement_cost_v2_20261017/results_20261017T020727133643Z/strict_account_prefixes.csv`)。这些仍缺小时内时序、真实成交、保证金阶梯和强平路径。

## 复核与交付状态

主审直接从旧 CSV 独立重算了全部九档风险周、36 条年度连续前缀及 0／20／50bp 对照，32,508 项检查一致，最大十进制差异为 9×10⁻²⁴。详见 独立风险复核 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_settlement_cost_v2_20261017/review/independent_risk_audit.json`)。一个明确披露的元数据差异是：旧版 2025 年首周缺现金退出的停止小时为空；新版标明其应有现金结算的 1 月 13 日 01:00 UTC。观察点数、停止原因、净值和回撤未改变。另有已知入场但未知退出的周，新版单列可计算的入场成本，总成本和净损益仍未知。

另一独立复算从旧周账本和逐腿贡献重建了 1,818 条情景周记录；费用、净损益、掩码、年度均值、未知周阈值和配对均值均一致。全部 36 组净收益区间、18 组配对区间也对上，最大端点差异约 4.27×10⁻¹⁴ USDT。主审另核对了全部可用分解项的区间。首次交叉复算误用线性插值分位数，曾出现小幅差异；原稿保留，按冻结算法的排序下标取值修正后已一致，正式结果未变。详见 统计交叉复核 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_settlement_cost_v2_20261017/review/independent_numerical_peer.md`)及 全部分解项区间复核 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_settlement_cost_v2_20261017/review/independent_all_component_ci_check.json`)。

实现已通过 **24 项定向测试**；只读预检核验 15 个旧输出及成员、权重，并确认报告目录没有写入变化。正式冻结和运行均使用确认的文件指纹。

按工作区要求完成来源验证、导入、库存、报告和全量测试。来源验证仍有原有 54／139 条记录未获验证，退出码为 1；导入继续拒绝这些不充分来源，退出码为 3；库存与报告更新退出码均为 0。来源清单相对本轮开始只改变生成时间，两份注册表均未改动。

全量测试实际记录为 **4,532 项通过、9 项失败、1 项跳过**，耗时 2,182.70 秒。七项仍是本轮开始前已有的来源身份／历史指纹阻塞：五项为原 BTC 4h 注册条目不满足严格追加检查，两项为原有的 7／9 指纹匹配断言失败。另两项由主审将临时目录放在本研究报告目录下引起：一个旧用例要求临时目录位于报告目录之外，另一个旧用例按整个路径是否含 `funding` 判断数据类型。

将临时目录移至工作区中性目录后，额外两项均单独复跑通过，未修改实现或测试。**没有再跑第二次完整套件，不能将两项补跑合成为一个“全量 7 失败”或“全量通过”的结果。** 原始全量日志和补跑日志均保留，见 最终失败对照 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_settlement_cost_v2_20261017/review/final_test_comparison.json`)、完整日志 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_settlement_cost_v2_20261017/maintenance/07_full_pytest.log`)及 中性目录补跑 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_settlement_cost_v2_20261017/maintenance/08_neutral_temp_regression.log`)。

最终完整性核查确认：此前接受的 30 项绑定全部未变，本轮 10 个冻结输出全部匹配收据，成员、权重、协议、实现及测试指纹均一致。见 最终完整性收据 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_settlement_cost_v2_20261017/review/post_validation_integrity.json`)及 主审记录 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_settlement_cost_v2_20261017/IMPLEMENTATION_REVIEW.md`)。

两个独立策略报告分别为 等权臂九门报告 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_settlement_cost_v2_20261017/results_20261017T020727133643Z/carry_eq_nine_gate_report.md`)和 beta 调整臂九门报告 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/funding_carry_settlement_cost_v2_20261017/results_20261017T020727133643Z/carry_beta_nine_gate_report.md`)。每臂均维持 UNVERIFIED，九门均为 BLOCKED。

下一步有价值的本地证据是：异常合约的准确身份、历史交易资格与正式现金结算记录，以及覆盖目标币种和时期的真实佣金、成交、报价和深度证据。若将来要测试按合约状态或资金费时效剔除标的，应先另立协议并只使用当时可知的信息；不能把本轮出现问题的 19 个周事后删掉，便宣称收益成立。
