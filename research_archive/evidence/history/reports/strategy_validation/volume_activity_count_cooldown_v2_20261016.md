> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 成交量余震研究 v2：放量小时数与冷却概率

**结论：普通成交量、价格和事件近期性特征具有历史预测信息；本次冻结的 ETAS 式幂律特征没有表现出足够的新增价值。两个主要目标均为 `NO_SUPPORTED_SIGNAL`，模型整体仍为 `EXPLORATORY / UNVERIFIED`。** 这表示幂律增量未达到门槛，不表示所有成交量预测都无效，也不证明其他 Hawkes/ETAS 设定必然无效。

按用户“进一步研究”的要求，本轮实测了未来放量小时数、受限冷却时间，以及 12/24 小时内冷却概率。研究使用已验证的本地数据，没有下载行情、下单或注册服务。全部历史已暴露/复用，不能称为未触碰样本外确认。

## 身份与冻结设计

| 字段 | 本轮记录 |
| :--- | :--- |
| 模型 / 版本 | `volume_activity_count_cooldown_v2`，共享入口 `scripts/research_platform_v5.py`；旧命令继续委托 v4 |
| 机制与假设 | 放量后交易活动可能持续聚集；检验幂律激发是否在强近期性基准之外改善次数和冷却预测。小时桶特征不是完整连续时间 ETAS 估计，也不识别因果触发 |
| 协议 | 冻结协议 (`provenance:nonincluded/crypto-leverage/docs/VOLUME_ACTIVITY_COUNT_COOLDOWN_V2_PROTOCOL_20261016.md`)，SHA256 `e607f1e83ecaa8d8519dc3f65bc78ee080f98e8f3b18c2077273ac7a67e21b89` |
| 运行注册 | `2026-10-15T23:43:47.375629Z`，在真实源读取、目标构造和拟合前创建；完整注册 (`provenance:nonincluded/crypto-leverage/reports/research_platform_v5/runs/volume_activity_v2_20261016_reviewed/preregistration.json`) |
| 代码身份 | 主模块 SHA256 `80e187d50d92b363b3d4bf8cae8c8c5f67b6242f7a69d345ddb7f87001ad4ccb`；适配器、入口、依赖、合同等完整哈希见注册文件 |
| 配置 | 冻结 spec (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volume_activity_count_cooldown_v2_20261016/frozen_spec.json`)，SHA256 `ee27c66731a0bc6d5114713fd37ce98ee7dba12cb93a945988c3846b2ea13fb8` |
| 数据与市场 | Core4 P0 已注册 Binance USDⓈ-M USDT 永续合约成交 K 线；BTCUSDT、ETHUSDT、SOLUSDT、BNBUSDT，1h；独立身份记录 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volume_activity_count_cooldown_v2_20261016/initial_identity.json`) |
| 来源窗口 | UTC `[2020-10-01, 2026-01-01)`；每币 46,032 根；2021 年前只作预热。底层文件含更晚数据，但先过滤再计算，不纳入 2026 观察 |
| 时钟 | 原始收盘时间为开盘+1h−1ms；起点为开盘+1h，模型可用时间为起点+1ms。真实交易所发布延迟未知；无成交时间 |
| 训练 / 评估 | 训练2021–2022→评估2023；训练2021–2023→评估2024；训练2021–2024→评估2025。每年只拟合一次，训练/评估标签均须在边界前成熟 |
| 已暴露窗口 / 搜索 | v1 已检查同一历史，v2 选题受其结果启发。v2 一套冻结参数、四个固定模型组、五个固定目标，无市场成绩后的调参或筛币。60 个模型/历史均值记录不是60次择优搜索 |
| 风险与执行 | 预测研究；无仓位、费用、资金费、价差、滑点、成交容量或保证金假设；相关指标 N/A |
| 审核 | Codex 独立审查，GPT-6 Luna high 实现；报告日期2026-10-16（Asia/Shanghai） |

普通基准 `RECENCY` 包含价格动量/波动、当前及近期成交量、观察到的主动买卖成交量差、时钟与币种，以及过去6/24/168小时放量小时数和距上次放量的时间。因此本研究没有将其效果单独归因于 volume；尚未做价格与成交量的额外消融。

其余三组为每币训练均值 `CLIMATOLOGY`、在普通基准上加入指数核 `EXPONENTIAL`、加入幂律核 `POWER`。幂律指数1.2、指数半衰期12h、历史支持168h，均事先固定。次数使用 PoissonRegressor 条件均值，受限时长使用 Ridge，概率使用 LogisticRegression；标准化只拟合训练行。

## 指标定义

正常量 B 为过去8周同一 UTC 星期/小时成交量的中位数，当前相对量 z=V/B。z≥3 是一个放量小时。前6小时均未放量且本小时首次达到阈值，才是本轮起点；每个符合条件的起点都保留，即使后续观察窗口重叠。

`count6/24` 是起点之后6/24小时内的放量小时数，排除当前小时；不是独立冲击次数或订单数。

冷却 T 是未来首次连续6小时 z≤1.5 的完成时间。研究时长为 **min(T,48)**；48小时仍未冷却的样本保留为受限值48，并用独立标记区分真正恰在48小时完成的样本。所有冷却目标都要求完整48小时未来观察；缺数据不算冷却，也不算删失。冷却只表示第一次低成交量连续段，不代表价格稳定、趋势结束或以后不再放量。

## 主要与次要预测结果

UTC2023–2025逐年向前预测，四组每个目标使用完全相同的起点。表中误差越低越好，AUC 越高区分能力越强。

| 目标 / 指标 | 起点数 | 每币训练均值 | 普通近期性 RECENCY | 指数核 | 幂律核 POWER |
| :--- | ---: | ---: | ---: | ---: | ---: |
| 未来6h放量小时数：Poisson偏差（主要） | 2,705 | 1.744487 | 1.497458 | 1.497358 | 1.498336 |
| 同上：平均绝对误差（小时数） | 2,705 | 1.0342 | 0.9282 | 0.9292 | 0.9292 |
| 未来24h放量小时数：Poisson偏差（次要） | 2,702 | 3.568832 | 2.914489 | 2.912585 | 2.914769 |
| 同上：平均绝对误差（小时数） | 2,702 | 2.5805 | 2.2436 | 2.2426 | 2.2427 |
| 48h受限冷却时长：MSE，小时²（主要） | 2,699 | 227.186900 | 172.761809 | 172.021827 | 172.172057 |
| 同上：平均绝对误差（小时） | 2,699 | 13.1685 | 10.7073 | 10.6835 | 10.6913 |
| 12h内完成冷却：AUC（次要） | 2,699 | 0.5038 | 0.7213 | 0.7213 | 0.7205 |
| 24h内完成冷却：AUC（次要） | 2,699 | 0.5420 | 0.7494 | 0.7497 | 0.7495 |
| 24h内完成冷却：log loss（次要） | 2,699 | 0.638110 | 0.547100 | 0.546351 | 0.546386 |

普通基准相对每币训练均值，6h/24h次数偏差分别降低14.16%/18.33%，受限时长MSE降低23.96%。这些是复用历史上的描述性差异，不是额外预注册的有效性检验。未来6h实际平均放量1.028小时；普通模型预测均值0.959，2023年预测0.880对实际1.080，存在低估。Poisson只用于条件均值损失，不能将方差/均值分别约1.83和4.17的次数数据解释为独立泊松过程或直接生成泊松预测区间。

冷却概率比精确时长更便于解释，但 AUC0.75 **不是75%准确率**。固定概率分箱也并非完全校准：普通模型24h冷却概率落在90%–100%箱的404个起点，平均预测93.66%，实际88.86%；10%–20%箱97个起点，预测15.34%，实际25.77%。尚未证明能够给出可靠的单次事件概率或个体时间区间。

### 幂律增量的冻结判定

正值表示 POWER 比比较基准损失更低。按每年完整日历分别抽取14日非循环移动块，保留同日所有币种/起点，2,000次，seed20261016。两个主要比较使用97.5%描述性区间；指数比较95%。

| 主要目标 | POWER相对RECENCY的损失改善 | 相对改善 | 97.5%区间 | 判定 |
| :--- | ---: | ---: | :--- | :--- |
| count6 | −0.000878 | **−0.0586%** | [−0.003568, +0.001620] | `NO_SUPPORTED_SIGNAL` |
| cooldown48 | +0.589752小时² | **+0.3414%** | [−0.119226, +1.245539]小时² | `NO_SUPPORTED_SIGNAL` |

要求至少1%相对改善、区间下界>0、三年均改善、至少3/4币种改善、总体优于训练均值、每个年×币种至少30行。次数只满足最后两项；时长满足4/6项，但改善不到1%且区间跨零。所有年×币种均至少158个主要目标起点，失败不是样本门槛不足。

相对指数核，幂律次数损失改善−0.000978，95%区间[−0.002685,+0.000890]；时长MSE改善−0.150229，区间[−0.445486,+0.086578]。两个幂律特异性判定均为 `NOT_SUPPORTED`，不应把一般持续性称作已验证的幂律优势。

| 年份 | count6 N | RECENCY偏差 | POWER偏差 | 冷却 N | RECENCY MSE | POWER MSE |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2023 | 1,022 | 1.572486 | 1.572593 | 1,018 | 177.097584 | 176.571310 |
| 2024 | 849 | 1.479801 | 1.482517 | 848 | 164.987330 | 164.986086 |
| 2025 | 834 | 1.423492 | 1.423444 | 833 | 175.377583 | 174.111149 |

count6 的幂律相对改善在2023、2024为负，仅2025微正；四个币种分别为负。冷却MSE三年、四币均改善，但2024仅0.001244小时²，整体提升非常小。次要24h冷却概率在2024的幂律 log loss 比普通基准更差，不能用有利次要指标挽救主要失败。全部400条年/币种/年×币种/总体指标及各项RMSE、Brier等见完整指标 (`provenance:nonincluded/crypto-leverage/reports/research_platform_v5/runs/volume_activity_v2_20261016_reviewed/metrics.json`)。

主要损失比较 (`provenance:nonincluded/crypto-leverage/reports/research_platform_v5/runs/volume_activity_v2_20261016_reviewed/primary_loss_comparison.png`)

## 放量后实际多久冷却

以下是2,699个完整48h样本的队列统计，不是今天市场的预测：

| 观察 | 历史比例 / 时间 |
| :--- | ---: |
| 6h内完成冷却 | 9.37% |
| 12h内完成冷却 | 39.64% |
| 24h内完成冷却 | 66.80% |
| 48h内完成冷却 | 84.40% |
| 到48h仍未冷却 | **15.60%** |
| 经验冷却时间中位数 | 16h |
| 48h受限平均时长 | 21.54h |

21.54h不是未截断的实际平均冷却时间；15.60%的尾部未观察到完整时长。BTC/ETH到48h未冷却分别10.78%/13.13%，SOL/BNB分别20.44%/20.29%；不能对四币套同一个固定倒计时。所有分组的冷却统计 (`provenance:nonincluded/crypto-leverage/reports/research_platform_v5/runs/volume_activity_v2_20261016_reviewed/cooldown_summary.json`)。

## 九道研究门槛

这些是完整策略门槛，不能用局部代码测试替代。状态仅用 PASS / FAIL / NOT_RUN / BLOCKED。

| 门槛 | 状态 | 证据 / 窗口 | 限制或下一证据 |
| :--- | :--- | :--- | :--- |
| 1 数据身份与因果可用性 | BLOCKED | 输入审计 (`provenance:nonincluded/crypto-leverage/reports/research_platform_v5/runs/volume_activity_v2_20261016_reviewed/input_audit.json`)：2020-10-01至2026-01-01，4份源哈希、逐小时网格、原始时钟验证；各币1个真实零成交小时保留 | 这些局部检查通过，但真实发布延迟和decision→fill链未验证。本研究未使用mark/funding；不据此声称期货执行数据完备 |
| 2 实现、前视与递归分析 | BLOCKED | 独立审查 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volume_activity_count_cooldown_v2_20261016/review.md`)，40项专项测试；13,504个去除模型重复后的目标行、400条指标、4组区间独立复算；2023–2025 | 预测模块检查通过；Freqtrade lookahead/recursive NOT_RUN，无交易策略可供执行。全仓回归存在旧工作台失败，不能称全仓通过 |
| 3 样本内机制与搜索披露 | BLOCKED | 冻结协议、注册、模型元数据，训练2021–2024；一次冻结配置，无真实成绩后的搜索 | 聚集不是因果触发；没有样本内交易机制/交易笔数或经济收益证据 |
| 4 未触碰滚动样本外 | BLOCKED | 2023/2024/2025年度因果滚动，标签成熟边界、训练内标准化、共同样本均核验 | 同期历史曾用于v1及其他研究；此次不能恢复为未触碰测试。需真正未用于设计的新证据 |
| 5 双边成本、资金费、滑点与成交 | NOT_RUN | 全窗口预测研究，无成交账本 | 不定义收益，不能由活动预测推导可交易利润 |
| 6 稳健性 | FAIL | 2023–2025、Core4；指标和冻结判定 (`provenance:nonincluded/crypto-leverage/reports/research_platform_v5/runs/volume_activity_v2_20261016_reviewed/metrics.json`) | 两个幂律主要终点均未过预设增量门槛；无制度分段、参数邻域、执行压力检验 |
| 7 杠杆、保证金与清算 | NOT_RUN | 无账户路径，全窗口N/A | 无1×/2×/3×/5×杠杆测试，不外推 |
| 8 Dry-run观察与对账 | NOT_RUN | 本轮dry-run仅CLI零写入验证；没有交易观察 | CLI dry-run不是机器人模拟运行证据 |
| 9 小额实盘观察 | BLOCKED | 无既有实盘记录 | 本工作区禁止实盘，不创建订单 |

## 交易指标与单位

| 指标 | 2023 / 2024 / 2025及总体 |
| :--- | :--- |
| 净收益、Sharpe、最大回撤 | N/A：无持仓、收益序列或成交 |
| 胜率、profit factor、交易笔数 | N/A：2,705/2,699为预测起点数，不是交易数 |
| 交易MAE/MFE、最差月份、最差单笔 | N/A：未定义交易路径；本报告预测MAE是平均绝对误差，与交易不利波动不同 |
| 各杠杆最小清算距离 | N/A：未模拟保证金/清算 |

## 独立核验、排除与维护

初始评估候选分别为2023年1,023、2024年852、2025年834。count6依次因跨年成熟/特征缺失排除1/3/0；冷却目标排除5/4/1。2024三个起点因真实零成交导致部分对数/差额特征未定义而被共同排除，没有填充。完整候选、训练行数、时间范围及排除类别见candidate_audit.json (`provenance:nonincluded/crypto-leverage/reports/research_platform_v5/runs/volume_activity_v2_20261016_reviewed/candidate_audit.json`)。

独立审查执行了以下核验，保留了日志和证据：

- 新v2与旧v1专项测试 **40 passed**；另8组合成边界oracle通过，覆盖T=48与删失、完整观察要求、起点边界、当前小时排除等。
- 独立复算 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volume_activity_count_cooldown_v2_20261016/independent_recomputation.json`)：从原始成交量重算全部去重目标与时钟，全部54,016预测记录共同样本一致；400指标最大数值差8.53×10⁻¹⁴；四组按日聚合bootstrap区间一致。
- 拟合与身份复核 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volume_activity_count_cooldown_v2_20261016/fit_and_post_maintenance_check.json`)：手工时间掩码检查训练均值/标准差，重建60个已保存模型的原始预测，最大差7.11×10⁻¹⁵。该部分复用已审阅的特征/目标构造器，不称独立特征实现。
- 三张PNG已逐张查看，文字无裁切、数据可辨；校准图为固定分箱描述，不作为校准通过的证据。样本量与空箱保存在校准表 (`provenance:nonincluded/crypto-leverage/reports/research_platform_v5/runs/volume_activity_v2_20261016_reviewed/calibration.json`)。
- 按要求依次执行 verify→import→inventory→reports→pytest。verify exit1：139条中54条旧来源未验证，所选Core4通过；import exit3：拒绝12个旧未验证组合；inventory/reports exit0。没有绕过身份门槛。
- 默认沙箱pytest临时目录不可写，经显式授权在外部重跑。全仓 `pytest tests -q -x` 最终 **5 passed, 1 failed**，旧 `tests/research_workbench_v1/test_server.py:175` 的artifact列表为空；之前v1已有同一失败，未修改或宣称通过。全仓日志 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volume_activity_count_cooldown_v2_20261016/maintenance_05_pytest_outside_sandbox.log`)。
- 维护之后所选源payload、全部v1代码/9份结果、新v2代码closure及13份运行产物哈希均未变。维护按设计重建了可变 `source_data/MANIFEST.json`；前后哈希留档，不重写冻结注册。

## 研究用途与后续边界

本轮支持把 **相对成交量z、预计未来6/24小时放量小时数、12/24小时内首次冷却概率** 当作待验证的市场活动描述。48h受限时长可作粗略状态摘要，10.7h的平均绝对误差不支持精确计时。幂律H暂不值得作为核心预测特征继续增加复杂度。

若要继续确认，应先冻结较简单的RECENCY模型和上述指标，在真正未用于设计的新数据上检查概率校准、跨币种/时期稳定性；不要在同一历史上继续调幂律参数寻找赢家。把活动指标作为双均线过滤器、止盈止损或仓位规则，都属于新的策略假设，需要另行预注册并验证完整执行与成本链。此次没有建立有效趋势方向系统。

统计与模型背景：[Hawkes金融综述](https://arxiv.org/abs/1502.04592)；sklearn1.7 PoissonRegressor (`provenance:external/bc0b9ea08a0b4755`)；受限平均时间的统计定义 (`provenance:external/cf9ea61457dca386`)。这些文献支持方法定义，不构成本策略有效性的证据。
