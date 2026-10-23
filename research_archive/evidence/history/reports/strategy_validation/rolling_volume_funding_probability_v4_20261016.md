> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 滚动成交量、成交位置代理与资金费率：条件概率研究 v4

**结论：滚动相对成交量对后续放量和低量时段具有历史预测信息；本轮没有找到通过冻结标准的涨跌方向、超2ATR端点位移、成交位置代理或资金费率方向预测。没有建立新的盈利策略。**

比较12个固定指标×7个目标，共84项。11项通过“历史继续研究候选”标准，全部属于成交量对活动持续/安静时段的预测。它们均不是实盘有效性结论。前一轮EMA+量能组合的负收益结果保持不变。

本轮没有拟合ETAS核函数或估计其机制参数；滚动量能结果支持的是活动持续性，不能据此认定地震余震机制在市场上成立。

核心概率图 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3C%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/rolling_volume_funding_probability_v4_20261016/rolling_volume_probability_evidence.png%3E`) · 完整84项结果 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3C%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/research_platform_v7/runs/rolling_volume_funding_v4_20261016_reviewed/comparisons.json%3E`) · 前一轮EMA与收益报告 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3C%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/ema_volume_direction_v3_20261016.md%3E`)

## 身份、预注册和时序

| 字段 | 内容 |
| --- | --- |
| 研究版本 | rolling_volume_funding_probability_v4；共享入口 research_platform_v7.py；仅概率研究 |
| 市场与样本 | Binance USDT永续 BTC、ETH、SOL、BNB；小时频率 |
| 数据区间 | 原始小时开盘UTC 2020-10-01,2026-01-01)，每币46,032根；已验证Core4 P0本地副本 |
| 训练与评估 | 2023/2024/2025逐年评估；每年仅用2021起此前成熟标签训练；分币训练分位数；训练和评估年末均按目标期限清除未成熟标签 |
| 历史暴露 | EXPOSED/REUSED；v1/v2/v3及更早研究已使用这些年份；不是干净未触碰OOS |
| 时钟 | origin=已完成小时open+1h；特征可用origin+1ms、决策origin+2ms，均为模型假设；无订单/成交 |
| 协议 | [冻结研究协议 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3C%3CSOURCE_ROOT%3Acrypto-leverage%3E/docs/ROLLING_VOLUME_FUNDING_PROBABILITY_V4_PROTOCOL_20261016.md%3E`) |
| 协议SHA256 | 034f01d4728c30d209b7159919b929d5784bcc93fe46ea5e8f7ad5ef70bd8b6f |
| 数据与代码身份 | 预注册与来源/代码哈希 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3C%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/research_platform_v7/runs/rolling_volume_funding_v4_20261016_reviewed/preregistration.json%3E`) |
| 产物清单SHA256 | a14f5b0869803d2c88f8b525c42d3d3c7ca8e01633455e5ab0a51463e2c1c004 |
| 搜索披露 | 12个固定features、7个targets、四个概率表模型；未搜索参数、未组合全部因子；同时报告全部84项 |
| 评分和阈值 | Brier误差降低，二分类(p−y)²、方向三类误差之和；相对降低≥1%，三年均改善、至少三币改善、84项近似同时95%区间下界>0 |
| 不确定度 | 14个日历日移动非循环区块，逐年抽样并截断至365/366日；2,000次，seed=20261016，分年生成器seed+year；同日跨币、跨84项使用同一权重 |
| 成本/风险限制 | 本轮未定义交易或仓位；费用、滑点、资金费现金流、容量、保证金、清算、杠杆及风险限额均N/A；不得推导收益 |

固定EMA对照为7/20/99，EMA20的6小时变化除以ATR14；严格多头排序且斜率>.25为上行状态，反向且斜率<−.25为下行，其余为中性/过渡。新研究不重新优化EMA。分位边界和概率均只从训练期取得；每格不足100个训练样本回退到对照。概率表采用20个伪观测向对照收缩，SYMBOL对照为加一平滑的分币频率。

四模型为SYMBOL、EMA、FEATURE、EMA_FEATURE，所有对比在同一特征/目标/年份内使用共同样本。主对比EMA_FEATURE减小了多少EMA误差；这不是对前一轮RECENCY模型的增量检验，更不能把相同量能信息叠加后当作新的独立证据。

## 直接回答：处在什么区间，未来概率怎样变化

相对成交量z=本小时base volume ÷ 此前8周同一UTC星期/小时的成交量中位数；当前小时不进入该基准。这里用过去24小时z的平均值，按每币每年训练分位数分成五组。最高/最低组是相对区间，合并统计不存在统一跨币跨年的数值切点。

| 未来事件 | 最低组实际发生率（样本） | 最高组实际发生率（样本） | 相对EMA的Brier误差降低 |
| --- | --- | --- | --- |
| 未来6h至少一次放量 | 10.44%（18,659） | 52.23%（21,829） | 12.48% |
| 未来24h至少一次放量 | 35.94%（18,561） | 83.82%（21,804） | 11.77% |
| 未来24h出现连续6h低量 | 97.06%（18,440） | 45.63%（21,775） | 21.56% |

“放量”是未来至少一小时z≥3；“低量时段”是未来24小时内完成连续6小时z≤1.5，并统一要求48小时完整后续数据。样本包含所有小时，包含本来已经安静的市场；它不是“发生冲击之后多久冷却”的专属样本。重复/重叠小时不是独立试验，表内n是原始观测数，不是有效独立样本数。

上表是随后评估年份的实际发生率，不是今天应直接套用的概率，也不是模型准确率。Brier降低12.48%表示概率误差相对降低，不能解释成上涨胜率增加12.48个百分点。

| 目标 | 最低组EMA_FEATURE平均预测 → 实际 | 最高组EMA_FEATURE平均预测 → 实际 |
| --- | --- | --- |
| 未来6h至少一次放量 | 8.98% → 10.44% | 54.15% → 52.23% |
| 未来24h至少一次放量 | 31.76% → 35.94% | 83.30% → 83.82% |
| 未来24h出现连续6h低量 | 96.74% → 97.06% | 38.47% → 45.63% |

概率排序有信息，校准仍有偏差。例如最高量组的低量时段EMA_FEATURE平均预测38.47%，实际45.63%；不能把输出概率当作精确常数。

| 目标 | EMA Brier → 加量能后 | 绝对误差改善 | 84项近似同时95%区间 |
| --- | --- | --- | --- |
| 未来6h至少一次放量 | 0.189389 → 0.165754 | 0.023635 | [0.013163, 0.034107] |
| 未来24h至少一次放量 | 0.249957 → 0.220532 | 0.029425 | [0.016034, 0.042816] |
| 未来24h出现连续6h低量 | 0.163644 → 0.128360 | 0.035284 | [0.01815, 0.052418] |

上述三项在2023、2024、2025每年以及BTC、ETH、SOL、BNB每币都改善。三个低高组发生率差的95%区块区间（未作多重比较校正，仅描述）分别为：

| 目标 | 最高组−最低组 | 个别95%区间，百分点 |
| --- | --- | --- |
| 未来6h至少一次放量 | 41.79百分点 | [37.91, 44.96] |
| 未来24h至少一次放量 | 47.88百分点 | [42.03, 52.25] |
| 未来24h出现连续6h低量 | -51.42百分点 | [-55.89, -45.89] |

## 哪些信息有用，哪些暂时没有证据

历史候选包括6/24/168小时平均相对量各自预测6h放量、24h放量及24h低量时段，共9项；以及168小时相邻窗口总成交量比预测6h放量和24h低量时段，共2项。短窗口6h/24h“比上一段放大多少倍”没有通过这轮门槛。持续活跃水平的信息强于多数短期增量指标。168h量比两项的同时区间下界较接近零，证据弱于平均相对量三组。

24项方向比较（12指标×6/24h）没有一项通过标准；24项超2ATR位移比较也没有一项通过。最大正向方向误差改善为6h相邻量比的6h方向预测约0.63%，低于预设1%且不足以建立交易优势。方向标签是未来端点log收益超过±当前ATR/close的三类划分，不是整段路径持续上涨/下跌。

本轮“大位移”严格定义为未来端点绝对log收益超过当前2ATR/close。高量组下这个事件发生率可能更低，因为阈值随当前ATR变化；不能据此断言高量时未来的绝对波动更小。本研究没有重新检验未来实际方差目标。

成交量时间集中度衡量24小时总量是否集中在少数小时；主动买卖量差采用taker-buy base volume和总base volume的观测汇总。二者未通过冻结候选标准。

### 成交位置代理

用每小时quote/base得到小时成交均价，将该小时成交量归到这个代表价，再计算过去168h中代表价低于当前价的量占比；另计算当前价距168h汇总VWAP的ATR倍数。前者是粗粒度成交分布代理，后者是价格位置。两者都没有持有人、剩余仓位或真实成本分布数据，因此不能称为真实筹码分布。两个指标的24h方向Brier相对EMA分别恶化约0.09%和0.20%，没有通过标准。

TradingView也将volume profile定义为历史成交在价格水平上的分布，并通常使用更低周期数据计算。本地小时代表价方法更粗，不能当作该指标的精确复刻。官方说明 (`provenance:external/4e290bda2fb17ea5`)。

### 永续资金费率

资金费是永续多空持仓之间的周期性支付。这里研究已结算费率及相邻两次费率变化；没有历史盘中预估费率，不能回填成当时已知值。[Binance资金费说明](https://www.binance.com/en/support/faq/detail/360033525031)。

每个结算事件只映射一次：先加5分钟，再取第一个完整小时观察点。本数据实际事件年龄约3599.953–3600秒。只保留当前和前一事件均为8h、offset在0–1000ms且实际间距8h±1s的记录。每币源窗口原生事件BTC/ETH/BNB 5,754条，SOL 5,829条；最终对应5,753/5,753/5,726/5,753个观察点。SOL排除101个2h/4h事件及2个不满足前序规则的事件；其他币各排除无窗口内前序的第一条。无资金费填充或时间网格改写。

24h方向评估共有13,116个结算后观察点。资金费率、费率变化加入EMA后，Brier分别恶化约0.40%、0.30%；全部14项资金费比较都没有成为候选。最高/最低费率组的24h上涨发生率差仅约0.10个百分点，个别95%区间[−3.49,+4.05]个百分点，覆盖零。

费率有大量重复值，分位边界去重后不少币年只有4个形式分箱；某些格很稀疏。联合EMA格因训练数不足回退的比例，费率为6.87%、费率变化为4.60%。因此不要从某个只有100条样本的编号最高分箱挑选21%上涨等数字；跨币年分箱编号不等同于统一费率区间，最高/最低对比必须按各币年自己的边界取组。结果只否定本轮具体模型的增量证据，不能断言资金费在所有用途上无效。

原始fundingTime/calc_time是结算事件身份，缺少真实发布/可见时间。5分钟加下一完整小时是建模假设，不能据此通过真实因果可用性门槛。[Binance funding history接口](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data#get-funding-rate-history)。

## 全部84项结果

下表为相对固定EMA的Brier降低百分比，负数表示恶化。星号为通过全部冻结候选条件。不同目标/不同cohort不能直接横向比较Brier数值。所有逐年逐币绝对值、四模型对照和概率校准均已保存。

| 指标 | 6h方向 | 24h方向 | 未来6h至少一次放量 | 未来24h至少一次放量 | 6h超2ATR位移 | 24h超2ATR位移 | 未来24h出现连续6h低量 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 6h平均相对量 | +0.084% | +0.024% | +11.690% * | +10.058% * | +0.248% | +0.745% | +17.362% * |
| 24h平均相对量 | +0.222% | -0.062% | +12.480% * | +11.772% * | +0.518% | +0.939% | +21.562% * |
| 168h平均相对量 | -0.022% | -0.189% | +8.695% * | +9.943% * | +0.058% | +0.096% | +14.573% * |
| 6h相邻窗口量比 | +0.628% | +0.106% | +0.562% | +0.056% | +0.985% | +0.284% | -0.010% |
| 24h相邻窗口量比 | -0.139% | -0.214% | +0.522% | +0.496% | -0.037% | +0.130% | +0.154% |
| 168h相邻窗口量比 | -0.092% | -0.364% | +3.853% * | +2.649% | -0.101% | -0.049% | +7.017% * |
| 24h成交量时间集中度 | +0.088% | -0.081% | +0.033% | -0.526% | +0.013% | +0.332% | -0.406% |
| 24h主动买卖量差 | -0.090% | -0.296% | -1.056% | -1.210% | -0.093% | -0.301% | -1.986% |
| 168h当前价以下成交量代理 | -0.082% | -0.091% | +0.661% | +0.168% | -0.047% | -0.178% | +0.298% |
| 168h VWAP距离/ATR | -0.036% | -0.199% | +0.464% | -0.247% | -0.002% | -0.093% | -0.002% |
| 已结算资金费率 | -0.189% | -0.400% | -0.729% | -0.575% | -0.146% | -0.311% | -0.583% |
| 相邻结算费率变化 | -0.209% | -0.295% | -0.381% | -0.348% | -0.074% | -0.122% | -0.257% |

各年各币四模型评分 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3C%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/research_platform_v7/runs/rolling_volume_funding_v4_20261016_reviewed/metrics_by_year_symbol.json%3E`) · 分箱概率与样本数 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3C%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/research_platform_v7/runs/rolling_volume_funding_v4_20261016_reviewed/cell_tables.csv%3E`) · 训练边界 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3C%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/research_platform_v7/runs/rolling_volume_funding_v4_20261016_reviewed/train_bin_edges.json%3E`) · 训练计数与平滑概率 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3C%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/research_platform_v7/runs/rolling_volume_funding_v4_20261016_reviewed/fit_metadata.json%3E`) · 高低分组区块区间 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3C%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/research_platform_v7/runs/rolling_volume_funding_v4_20261016_reviewed/high_low_conditionals.json%3E`)

## 实现审查与独立核验

修复均发生在真实拟合/评分之前：二分类Brier尺度、区块年末截断、资金费时间读取和严格身份校验、训练单元预聚合、完整事件与概率记录、概率图跨年汇总。无结果驱动的特征/阈值更改。原协议保持原字节。独立审计重建184,128小时的源特征和标签、252个预测分片、7,532,328条预测行、6,720组评分及84项bootstrap区间；概率最大绝对差为0.0。

独立全量审计 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3C%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/rolling_volume_funding_probability_v4_20261016/independent_result_audit.json%3E`) · 审查记录 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3C%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/rolling_volume_funding_probability_v4_20261016/review.md%3E`) · 资金费来源与cohort审计 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3C%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/research_platform_v7/runs/rolling_volume_funding_v4_20261016_reviewed/funding_cohort_audit.json%3E`) · 代码/数据使用说明 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3C%3CSOURCE_ROOT%3Acrypto-leverage%3E/docs/ROLLING_VOLUME_FUNDING_PROBABILITY_V4.md%3E`)

强制维护按verify→import→inventory→reports→全pytest顺序执行。verify仍报告54个旧来源未独立验证；import拒绝旧4h/5m/15m数据的12个组合。所选Core4 P0来源的绑定和SHA均通过；没有放宽拒绝规则。inventory和reports退出0。完整测试状态见下面记录。

维护命令与退出状态 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3C%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/rolling_volume_funding_probability_v4_20261016/maintenance_summary.json%3E`) · 完整pytest日志 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3C%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/rolling_volume_funding_probability_v4_20261016/maintenance_05_full_tests.log%3E`)

## 九项策略验证门槛

| 门槛 | 状态 | 证据与限制 |
| --- | --- | --- |
| 1 数据完整性与可用时间 | BLOCKED | 已验证本地数据身份/时钟/缺失处理；真实发布延迟未知，尤其资金费 |
| 2 策略实现/lookahead/recursive | NOT_RUN | 概率模块独立核验通过；无Freqtrade策略或成交接口，不能用概率审计替代交易实现门槛 |
| 3 机制与研究披露 | PASS | 仅指冻结12×7研究、四模型及全部结果披露；不代表方向alpha或交易有效 |
| 4 未触碰OOS | BLOCKED | 2023–2025全为EXPOSED/REUSED，按年滚动不恢复未触碰资格 |
| 5 费用、资金费现金流、滑点与成交 | NOT_RUN | 无新交易规则或账户账本 |
| 6 策略级稳健性 | NOT_RUN | 11项活动候选仅满足历史分年分币规则；方向/位移候选标准未通过；未执行交易策略的牛熊横盘、参数邻域及执行压力检验 |
| 7 杠杆与清算 | NOT_RUN | 无仓位、无杠杆层级回放 |
| 8 Dry-run观察 | NOT_RUN | CLI dry-run为零写入验证，不是交易观察 |
| 9 小额实盘观察 | NOT_RUN | 无实盘记录，未下单 |

| 要求的交易指标 | 结果及原因 |
| --- | --- |
| 净OOS收益 | N/A；本轮未定义/运行交易策略 |
| OOS Sharpe | N/A；本轮未定义/运行交易策略 |
| 最大回撤 | N/A；本轮未定义/运行交易策略 |
| 胜率 | N/A；本轮未定义/运行交易策略 |
| 盈利因子 | N/A；本轮未定义/运行交易策略 |
| 交易数 | N/A；本轮未定义/运行交易策略 |
| MAE/MFE | N/A；本轮未定义/运行交易策略 |
| 最差月份 | N/A；本轮未定义/运行交易策略 |
| 最差交易 | N/A；本轮未定义/运行交易策略 |
| 各杠杆层级最小清算距离 | N/A；本轮未定义/运行交易策略 |

**Verdict：EXPLORATORY / UNVERIFIED。** 支持把滚动量能视为活动状态预测输入；未建立多空方向优势或盈利能力。研究上的下一步是先在共同样本上检验其是否超越既有RECENCY活动模型，并在未触碰的后续数据中验证冻结概率；若再设计交易用途，必须另行冻结规则并检验完整成本与风险。没有启动任何新策略或交易。

20,482个条件概率单元与主要区间的独立复核 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3C%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/rolling_volume_funding_probability_v4_20261016/independent_cell_audit.json%3E`) · 最终数据、代码及既有结果身份检查 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3C%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/rolling_volume_funding_probability_v4_20261016/final_identity_check.json%3E`)

完整pytest最终结果：`7 failed, 4411 passed, 1 skipped, 272 warnings in 2208.01s (0:36:48)`。

失败节点对照：本轮7项；其中7项在上一轮完整测试中已经失败，0项不在该既有失败清单。此对照不替代对失败原因的审查；详见审查记录。
完整失败节点对照 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3C%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/rolling_volume_funding_probability_v4_20261016/full_suite_failure_comparison.json%3E`)
