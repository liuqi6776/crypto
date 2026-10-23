> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 成交量活动增量与趋势共同账户：本轮结论（2026-10-16）

本轮完成了预先限定的离线比较和独立数值复算。**停止简单相对量增量分支；暂停 EMA7/20/99/P50 的进一步策略扩展；EMA200 仅保留为研究基准。没有任何策略升级为有效、可交易或通过独立 OOS。** 本轮还有明确的归档完整性阻塞：阶段B一份新支持附件被旧进程晚写，原冻结字节无法恢复；阶段A冻结的可变总清单被必要维护重写且未留原副本。原始市场数据、代码、预测及主账本未改，数值复算成立，但两阶段均不能宣称完整冻结归档可重放。

## A：同样本活动预测增量未成立

目标唯一固定为未来6根完整小时K线至少一次 `z>=3`；候选仅 v4 `EMA_FEATURE(z_mean_24)`，主要强基准为在相同小时样本和训练窗重新拟合的 v2 RECENCY。RECENCY包含近期冲击次数、距离前次冲击等26个因果特征，当前已完成小时可用于计数，距前次冲击严格排除当前行。历史频率 SYMBOL 与 EMA 均为描述性基线，不能替代主比较。

训练按2021–22→2023、扩展至2024、扩展至2025；每年35,016个共同起点，合计105,048。所有年份均为已暴露历史。预先固定的门槛为相对RECENCY Brier改善至少1%、三年均改善、至少三币改善、14日同步日期区块95%区间下界大于0；2000次bootstrap、一个主要比较，无事后筛币、换目标或调整门槛。

| 评价年 | RECENCY Brier | 相对量候选 Brier | 候选相对改善 |
|---|---:|---:|---:|
| 2023 | 0.170289 | 0.185862 | -9.1450% |
| 2024 | 0.143399 | 0.155218 | -8.2419% |
| 2025 | 0.142770 | 0.155858 | -9.1675% |
| 合并 | 0.152153 | 0.165646 | **-8.8683%** |

Brier gain定义为RECENCY减候选，合并为-0.013493，95% CI **[-0.016093, -0.011453]**；三年与四币方向全部不利于候选。结果按协议为 `STOP_BRANCH`。候选虽相对较弱的EMA基线改善约12.51%，仍没有相对RECENCY的新增预测价值。本轮不添加活动过滤。事件基率、完整校准及分币结果已保存；费用/PnL=N/A，预测放量不等于预测方向或盈利。

唯一正式运行包含三个年度RECENCY拟合和三个年度固定分箱概率估计，没有重新选模型。独立从184,128行原始小时数据重建主要相对量和目标，并从保存参数复算420,192个预测、80组Brier、800个校准箱及bootstrap区间，全部一致。其他RECENCY特征复用了保存输入并由前缀/键测试支撑，未声称全部特征都有第二套独立实现。

详见阶段A结果 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/activity_recency_increment_v1_20261016/RESULTS_ZH.md`)、独立复算 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/activity_recency_increment_v1_20261016/root_independent_audit.json`)、冻结记录 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/activity_recency_increment_v1_20261016/runs/root_reviewed_v1/preregistration.json`)。

## B：统一账户后，P50的少亏不能解释为新增盈利能力

五个账户分别以10,000 USDT起始，BTC/ETH/SOL、2025全年UTC、固定4,000总初始入场名义预算、各币等槽位，不复利/加仓。统一下一实际H1开盘参考价、模型化延迟、每边5bp手续费，Base/Stress每边滑点5/15bp。使用原生资金费事件及此前可用的真实mark收盘代理；每时间批次必须同时满足gross≤10,000和gross≤NAV。资金费不是补齐序列，mark不是用交易K线代替。三币每币8,761根所需mark与登记安装文件逐根OHLC完全一致。

| 独立账户 | Base净收益 | Stress净收益 | Base最大回撤 | Base平仓笔数 |
|---|---:|---:|---:|---:|
| 现金 | 0.00% | 0.00% | 0.00% | 0 |
| 永续持有 | -8.79% | -8.87% | -23.35% | 3 |
| EMA200 4h | **+10.27%** | **+7.72%** | -9.72% | 95 |
| EMA7/20/99 | -46.77% | **BLOCKED** | -50.76% | 964 |
| EMA7/20/99 + P50 | -16.94% | -22.12% | -20.33% | 194 |

纯EMA压力情景在2025-12-12 21:00:01.001 UTC首次出现gross 4,008.9021 > NAV 3,998.3797。独立复算匹配该时点和数值，保留阻断，不报一个违反预设约束的全年收益，也不事后调整仓位或风险上限。对应压力情景的匹配归因同时阻断。

Base下纯EMA和P50平均gross/起始权益约21.48%和4.51%。预先固定的归因控制按币种把纯EMA向下缩小到P50相同gross USDT-hours，最大相对匹配误差约3.36e-15（上限0.001）。匹配纯EMA亏1,016.62 USDT，P50亏1,694.13 USDT，P50仍多亏**677.51 USDT（6.7751个百分点）**。该控制用了全期敞口，只有事后解释用途，不能当作可执行策略。

EMA200 Base参考价格PnL+1,398.09，滑点127.39、手续费127.39、资金费-116.25，净+1,027.05 USDT。三币净PnL为BTC -51.59、ETH +731.14、SOL +347.50，不能把单个已暴露年度、主要来自两币的盈利称为普遍有效。P50 Base参考价格PnL仍为-1,156.46 USDT，其亏损并非仅由成本造成。完整逐币分解、敞口、Sharpe、胜率、PF、最差月/交易及close-mark MAE/MFE见阶段B结果 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/trend_common_account_v1_20261016/RESULTS_ZH.md`)。close-mark指标不能替代盘中路径或清算距离。

本阶段一次正式共同账户运行，固定3策略+2参照、2成本情景、0新增过滤、0模型重拟合；计划10个主情景+2个匹配归因，实际9个主情景及1个匹配账本完成，另外两项按规则阻断。10个已完成账本的原始价格、时间、原生资金费、双边费用、滑点、固定数量、敞口和权益路径均独立复算一致；复算及定义 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/activity_trend_round_v1_20261016/common_account_root_recalculation.json`)、逐笔复算 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/activity_trend_round_v1_20261016/common_account_root_trade_episodes.json`)、压力约束首次触发 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/activity_trend_round_v1_20261016/stress_ema_only_constraint_root_audit.json`)。

## 原账户与实现差异已单独解释

旧EMA200为另一个100,000 USDT、原q≡1仓位约束账户：2025净+21,651.66 USDT、95笔；旧四币v5 P50为10,000 USDT账户：净-1,225.50、260笔。各自保存账本恒等式独立核对，不能直接相加或按百分比排名。旧EMA200 stress还改变为61分钟延迟，价格PnL也改变；共同Stress只改变滑点，两者含义不同。

旧EMA200从本地原始数据独立重建190个动作、95笔日期及资金费吻合。初版共同实现误用较短预热，少了BTC 2025-02-21的一组动作；在共同账户任何收益运行前恢复原完整窗前历史，190个(symbol,origin,side)键完全一致，v5两套动作流未变。修复留有事前审核 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/activity_trend_round_v1_20261016/PRE_RESULT_REVIEW.md`)和独立动作核对 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/activity_trend_round_v1_20261016/corrected_signal_root_audit.json`)。旧受保护runner因历史依赖哈希漂移仍BLOCKED，本轮没有绕过它；独立重建不能冒充受保护runner完整重跑。

v5 35,040条保存概率和原始EMA状态核对一致，四份指定旧账本每份4,380条原生资金费事件无差异；资金费仓位取自保存账本，未宣称该项独立重演了全部旧成交。原保存账本数值另见复算表 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/activity_trend_round_v1_20261016/original_accounts_root_recalculation.json`)。

## 归档事故与验证边界

共同账户执行时及结束时，冻结身份验证通过。随后未确认退出的旧审计进程session21447在15:47:44 UTC改写了支持附件 `original_raw_audit.json`。冻结SHA为1e5d254…，替换后为927c9c2f…；原字节没有备份，无法恢复。这是本次执行管理疏漏，不将其隐藏为普通维护变化。

已另存替换后的完整变体，原收据及结果保持不变。42/43个闭包文件、9个选定原始来源和4个权威清单仍匹配；唯一漂移是上述支持附件，它不参与模型/信号/价格/资金费/仓位计算，但被原冻结收据绑定，因此**原收据现在无法完整通过重放身份检查，完整归档可复现性BLOCKED**。数值复算通过不抵消该阻塞。详见事故与身份核查 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/activity_trend_round_v1_20261016/incident_root_report.json`)。不为修档改写冻结哈希或再跑一轮收益。

三策略均有逐策略九门报告 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/trend_common_account_v1_20261016/RESULTS_ZH.md`)。未触碰OOS身份、实际发布延迟、实测成交成本/容量、维持保证金/清算路径及观察记录没有充分证据，均不当作PASS。2026没有自动被称为新OOS。研究未交易、未读取凭证、未下载行情、未创建服务、未改变权限，也未写入源仓库或D盘。

阶段A还存在独立的清单归档缺口：必要维护在其完成后重写 `source_data/MANIFEST.json`，该阶段只冻结哈希而未保存原字节副本。当前27/28个闭包对象、4个原始文件及21个冻结输出吻合，但精确权威清单重放BLOCKED；阶段A限制详情 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/activity_recency_increment_v1_20261016/CURRENT_IDENTITY_LIMITATION_20261016.md`)。原运行与独立数值复核的STOP_BRANCH结论不变，不将必要维护解释为可忽略的哈希差异。

## 决策

本轮停止活动增量分支，暂停P50/短EMA策略扩展，不新增目标、阈值、币池或均线网格。EMA200仅保留研究基准，暂不推进“有效”结论。若另行继续，先解决冻结归档和真正未暴露窗口的证据要求；本轮不自动启动新试验或观察服务。

## 维护、测试与交付终态

最后一次代码修复后已按要求依次运行verify→import→inventory→reports，退出码分别为1/3/0/0。原有54项来源未验证、12项转换拒绝保持原状，没有绕过；选定Core4 P0分区和聚合文件验证仍成立。见维护记录 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/activity_trend_round_v1_20261016/post_repair_maintenance.json`)。

新增专项 **23 passed**（A 11+B 12）。完整 `pytest tests -q` 于2026-10-16 16:23:00 UTC结束，原始结果为 **23 failed, 4436 passed, 1 skipped，272 warnings，2364.97秒**；退出码1，原始日志保留。逐条分类如下：

- **7项既有失败仍在：** 与上次全量记录的测试ID及规范化错误完全一致；5项是旧registry严格追加身份问题，2项是期望9、实际8的断言。没有放宽保护或修补旧证据。
- **10项默认临时目录权限失败：** 在子进程中仅将TEMP/TMP设为工作区新临时目录，未改权限或测试代码；先复测9项全部通过，另1项与下述整组测试一起通过。
- **6项本轮文档回归已修复：** 追加EMA200因子卡导致旧合约的固定SHA不匹配。只撤回本轮追加，按SHA确认恢复原字节；新说明保留在独立研究卡。整组 `test_research_platform_v1.py` 的52项加上述1项共 **53 passed**。不将这6项伪称为既有或环境失败。

完整测试原始失败数不改写成“全绿”。文档恢复后未再重跑第二遍完整套件，已对受影响的完整平台测试模块及额外环境失败做定向验证；当前没有未解释的本轮新增失败。最初因预热修复而中断的全量会话不计作完成。见最终分类 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/activity_trend_round_v1_20261016/full_test_failure_classification_final.json`)、全量原始日志 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/activity_trend_round_v1_20261016/full_pytest_post_repair.log`)、文档修复记录 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/activity_trend_round_v1_20261016/pinned_card_append_repair.json`)、53项复测 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/activity_trend_round_v1_20261016/doc_repair_and_g1_retry.log`)。

两份新研究卡及总目录2026-10-16条目已追加。旧EMA200因子定义卡最终保持原字节，旧registry/研究地图未更新。所有上述工程验证与数值复算均不升级策略门，也不消除两阶段的冻结归档阻塞。
