> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 成交量余震 / ETAS 启发模型 v1：研究与验证报告

**结论：成交量存在明显的聚集和衰减现象，但本版模型没有形成稳定的涨跌预测优势。** 对本版未来 24 小时方向预测候选的判定为 **FAIL**；全部历史分析仍属于 **EXPLORATORY / EXPOSED_REUSED**。这个结论不等于否定所有 Hawkes/ETAS 模型，也不支持交易盈利声明。

## 研究结果

使用已验证的 Binance USDT 永续 BTC、ETH、SOL、BNB 小时数据，分别用过去数据训练、预测 2023、2024、2025 年。把放量固定定义为：成交量达到过去八周同一星期时段成交量中位数的 3 倍。主预测目标是未来 24 小时收盘净涨跌，未检验价格是否沿同一方向持续运行。

### 放量确实呈现“余震”形态

三个评估年份共有 8,292 个放量小时，排除年末后续 48 小时不完整的 10 个，所有滞后共同使用 8,282 个事件。以下是对应滞后那一个小时再次达到放量阈值的频率，**不是该时段内至少发生一次的累计概率**。

| 放量后的滞后 | 再次放量频率 | 同币种、同年份、同星期时段背景频率 |
| :--- | ---: | ---: |
| 1 小时 | 44.74% | 8.77% |
| 2 小时 | 33.63% | 8.60% |
| 6 小时 | 24.02% | 8.32% |
| 12 小时 | 20.43% | 8.24% |
| 24 小时 | 19.85% | 8.41% |
| 48 小时 | 15.93% | 8.36% |

放量后的事件频率 (`provenance:nonincluded/crypto-leverage/reports/research_platform_v4/runs/volume_etas_v1_20261015_reviewed/event_response.png`)

事件相互重叠，背景率使用整个相应评估年的描述性统计，没有被当成可实时使用的特征。曲线支持“成交活跃度聚集”，不能单独证明自激因果、幂律尾部或地震模型的参数机制。新闻、行情状态和共同冲击也可能产生聚集。

### 但涨跌方向没有获得稳定增益

六个模型使用完全相同的有效预测日期；合计 **4,366 个币种×日期的 24h 方向标签**。下表 log loss 越低越好；AUC 衡量涨跌概率排序，0.5 为无区分能力的参考值，不能解释为交易胜率。

| 固定模型 | 24h log loss | 24h AUC |
| :--- | ---: | ---: |
| 历史涨跌频率基准（CLIMATOLOGY） | 0.693002 | 0.503629 |
| 价格、动量与过去波动率（PRICE） | 0.697338 | 0.518880 |
| 普通量价与主动买卖比例（VOLUME_BASE） | 0.702098 | 0.507701 |
| 加指数衰减（EXPONENTIAL） | 0.702383 | 0.507263 |
| 加无符号幂律衰减（POWER_UNSIGNED） | 0.702161 | 0.509068 |
| 加带主动买卖方向的幂律衰减（POWER_SIGNED，主候选） | 0.702155 | 0.509385 |

主候选相对普通量价基准的 log loss **恶化约 0.0081%**。配对改善定义为“基准损失减候选损失”，点估计 −0.0000570，14 个日历日区块抽样的描述性 95% 区间为 **[−0.0004100, +0.0007256]**，包含零。与指数衰减相比，点估计改善 +0.0002282，但区间 **[−0.0005771, +0.0013048]** 同样包含零，未确立幂律特有优势。

| 评估年 | 有效方向标签数 | 普通量价 log loss | 主候选 log loss | 主候选 AUC | 配对改善（正数更好） |
| :--- | ---: | ---: | ---: | ---: | ---: |
| 2023 | 1,455 | 0.710515 | 0.710537 | 0.523978 | −0.0000215 |
| 2024 | 1,456 | 0.695397 | 0.695081 | 0.521612 | +0.0003163 |
| 2025 | 1,455 | 0.700385 | 0.700851 | 0.491934 | −0.0004661 |

各币种配对改善：BTC −0.0003068、ETH −0.0005301、SOL +0.0003275、BNB +0.0002820。只有一个年份、两个币种改善。预先规定的五项继续研究门槛全部未通过：相对改善至少 0.5%、区间下界大于零、三个年份都改善、至少三个币种改善、总体 AUC 至少 0.52。没有按结果选择年份、币种或参数。

### 活跃度、波动率和短周期方向的独立诊断

| 目标 / 指标 | 普通量价 | 幂律主候选 | 指数衰减 |
| :--- | ---: | ---: | ---: |
| 未来 6h 至少一次放量：log loss，n=4,380 | 0.479818 | 0.477567 | 0.477283 |
| 同一活跃度目标：AUC | 0.739994 | 0.739891 | 0.740525 |
| 未来 24h 对数实现方差：MSE，n=4,368 | 0.683263 | 0.686003 | 0.688298 |
| 同一方差目标：QLIKE | 0.404439 | 0.406576 | 0.406970 |
| 未来 6h 方向：log loss，n=4,378 | 0.693567 | 0.694360 | 0.692634 |
| 同一 6h 方向：AUC | 0.550520 | 0.551745 | 0.554343 |

活跃度预测的主候选 log loss 相对改善约 0.47%，但 2024 年变差，BTC、SOL 也变差；AUC 没有提高，指数衰减略优。这只能算小幅、不一致的增益，不能证明幂律机制。波动率的两个指标均未优于普通量价；6h 方向的主候选概率损失也更差。不能用这些次要结果替换失败的 24h 主目标。

这次结果支持把“放量余震”看作市场活跃状态的描述性特征，尚不支持将它直接用作做多、做空或加杠杆信号，也未证明它可改善仓位管理。

## Identity and pre-registration

| Field | Evidence |
| :--- | :--- |
| Strategy / model and version | `core4_volume_aftershock_prediction_v1` / `volume_aftershock_prediction_v1`，共享 v4 prediction-only route；旧 v3 源码与 recipes 未修改 |
| Hypothesis / mechanism | H1 放量聚集；H2 增量波动预测；H3 主目标：带符号幂律特征改善未来 24h 净方向概率。成交量没有天然涨跌符号，所以使用真实 taker-buy quote 占比构造主动买卖不平衡 |
| Protocol / code / config hashes | 冻结方案 (`provenance:nonincluded/crypto-leverage/docs/VOLUME_ETAS_PREDICTION_V1_PROTOCOL_20261015.md`)；preregistration.json (`provenance:nonincluded/crypto-leverage/reports/research_platform_v4/runs/volume_etas_v1_20261015_reviewed/preregistration.json`) 保存逐文件 SHA256、唯一 spec、schema、recipe、依赖版本；登记时间 2026-10-15 07:24:43.596946 UTC，在真实拟合之前；无 Git commit 可用 |
| Data identity | 四个 Core4 P0 1h trade Parquet，注册为 `VERIFIED_PERPETUAL_LABEL`，逐文件 SHA256 对应外部固定的 partition binding；独立原始数据检查 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volume_etas_prediction_v1_20261015/source_independent_check.json`) |
| Exact source window | `2020-10-01 00:00, 2026-01-01 00:00)` UTC，共 4×46,032 根；2021 年前仅作 warmup；没有使用 2026 年收益 |
| Decision / availability / fill | 每日 00 UTC 采样；已完成的小时 bar 以 `open_time+1h` 为边界，建模可用时间为边界+1ms；源 close_time 为边界−1ms。真实发布延迟未知。无成交价、无订单，收盘标签不是可执行收益 |
| Folds | 2021–22 训练→2023；2021–23→2024；2021–24→2025。训练、评估标签均要求在各自年末边界前严格成熟；target-specific 6h/24h purge |
| Fold sizes | 24h 主目标共同训练样本 2,914 / 4,373 / 5,833，评估样本 1,455 / 1,456 / 1,455；详细时段和剔除见 [fit metadata (`provenance:nonincluded/crypto-leverage/reports/research_platform_v4/runs/volume_etas_v1_20261015_reviewed/fit_metadata.json`) |
| Exclusions / no filling | 每币种一个真实零成交小时保留；其未定义 log-volume/imbalance 不填。2024 年四个日采样受此影响排除，2025 训练亦排除四个；主评估另排除 2 个精确零收益方向标签、12 个年末 maturity 标签。全区间无小时缺口 |
| Exposure / searches | 工作区历史均按 EXPOSED/REUSED 处理，不能称 untouched Test。本次只有预先固定的六个 arms；无阈值、衰减率、symbol、year 网格搜索；修复均在真实拟合之前完成 |
| Models / kernel | StandardScaler 仅训练折拟合；Logistic L2 C=1；log-variance Ridge alpha=10；幂律 p=1.2、指数半衰期12h，两者168h支持。不是完整连续时间 ETAS 拟合，未估计 branching ratio |
| Primary threshold | 24h paired log loss；预先固定的五项门槛见上文和协议。1,000 次年内非循环14日移动区块抽样，所有币种共享日抽样，seed=20261015，空日保留 |
| Costs / risk limits | N/A：prediction-only，没有交易持仓、成本或风险额度；没有费率、funding、spread、slippage、capacity、margin 的可执行假设 |
| Reviewer / date | Codex 独立审查和复算；Luna high 实现；2026-10-15 UTC |

## Gate evidence

以下为完整策略门槛。有限的预测模块检查通过，不等于完整策略门槛通过。

| Gate | Status | Evidence / window | Limitation or next evidence |
| :--- | :--- | :--- | :--- |
| 1 Data integrity and causal availability | BLOCKED | input audit (`provenance:nonincluded/crypto-leverage/reports/research_platform_v4/runs/volume_etas_v1_20261015_reviewed/input_audit.json`)、独立原始断言：2020-10-01 至 2025-12-31 trade 数据身份/网格/量价合法 | 本研究只验证 trade 数据和建模时间；真实发布时钟、decision→fill 链和完整 futures 输入链未用于该候选，不能通过完整门槛 |
| 2 Implementation, lookahead and recursion | BLOCKED | 16项专项测试 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volume_etas_prediction_v1_20261015/focused_tests_outside_sandbox.log`)、独立因果测试 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volume_etas_prediction_v1_20261015/independent_causality_checks.json`)、结果复算 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volume_etas_prediction_v1_20261015/independent_results_check.json`)；合成数据与2023–25结果 | 本预测模块的特征因果、训练隔离检查通过；无执行策略可供 Freqtrade lookahead/recursive analysis，整体回归亦有既有失败，完整门槛保持关闭 |
| 3 In-sample mechanism and search disclosure | FAIL | metrics (`provenance:nonincluded/crypto-leverage/reports/research_platform_v4/runs/volume_etas_v1_20261015_reviewed/metrics.json`)，冻结 H3 在 2023–25 历史检验五项门槛全失败；机制与全部搜索范围已披露 | H1 描述性聚集不能替代 H3 方向优势；不报告拟合内利润 |
| 4 Untouched walk-forward OOS / ML leakage | BLOCKED | fit metadata (`provenance:nonincluded/crypto-leverage/reports/research_platform_v4/runs/volume_etas_v1_20261015_reviewed/fit_metadata.json`) 与逐预测时间字段，2023/24/25逐年评估，scaler仅训练数据 | 时间隔离已检查，但全部历史已暴露；没有真正未触碰的 OOS |
| 5 Fees / funding / spread / fills | NOT_RUN | 无交易；2023–25仅概率评分 | 须另行冻结交易规则、成本、真实funding及成交账本，不能把标签收益当成交收益 |
| 6 Regime / symbol / parameter robustness | FAIL | metrics (`provenance:nonincluded/crypto-leverage/reports/research_platform_v4/runs/volume_etas_v1_20261015_reviewed/metrics.json`)：2023、2025负增益；BTC、ETH负增益 | 年份/币种门槛失败；专门行情分层和参数邻域为 NOT_RUN，未挑选有利子集 |
| 7 Leverage / liquidation stress | NOT_RUN | N/A；无仓位 | 不能从预测评分外推杠杆或清算安全 |
| 8 Dry-run observation / reconciliation | NOT_RUN | CLI零写入dry-run只验证配置，不是市场持续观察 | 无可用的持仓、成交和账本观察证据 |
| 9 Small-capital live observation | BLOCKED | N/A；工作区禁止 live trading | 无实盘记录，不授权任何下单 |

## OOS results: trading metrics

不存在 untouched OOS 交易样本；上文是暴露历史的预测评分，单位是样本平均损失或 AUC。以下项目不得用它们替代。

| Metric | Fold/window values | Aggregate / definition |
| :--- | :--- | :--- |
| Net OOS return | 2023/24/25均N/A | 无交易规则、成交或成本账本 |
| OOS Sharpe | N/A | 无净收益序列 |
| Max drawdown | N/A | 无净值路径 |
| Win rate | N/A | 没有交易；AUC及分类指标不是交易胜率 |
| Profit factor | N/A | 无已结算交易收益 |
| Trade count | N/A | 不生成交易；4,366是方向预测标签数 |
| MAE / MFE | N/A | 未定义入场、退出和持仓路径 |
| Worst month | N/A | 无交易月收益 |
| Worst trade | N/A | 无交易 |
| Minimum liquidation distance by leverage tier | N/A | 无杠杆、保证金或清算模拟 |

## Independent verification and workspace checks

独立逐项重算全部 **480 行指标**，最大浮点差异约 `4e-15`；用原始 OHLC/volume 重算全部 **17,492 个唯一标签**；核对各arm相同样本、时间成熟约束；独立向量化重算两组区块抽样区间，完全一致。两个图已打开检查。证据：指标及标签复算 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volume_etas_prediction_v1_20261015/independent_results_check.json`)、bootstrap复算 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volume_etas_prediction_v1_20261015/independent_bootstrap_check.json`)、完整审查记录 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volume_etas_prediction_v1_20261015/review.md`)。

按工作区顺序运行维护链：verify exit 1（139条中54条旧数据未验证，本研究四文件仍全部通过）；默认 import exit 3（拒绝12个旧数据组合，无强制绕过）；inventory 和 reports 生成成功。整体 pytest 使用 `-q -x`：沙箱临时目录权限阻止后，经批准在沙箱外重跑，**5 passed / 1 failed**，停在已有 `tests/research_workbench_v1/test_server.py:175` 的 artifact links 断言失败。不能声称整体测试通过；本研究16项专项测试均通过。维护日志位于同名 evidence 目录。

维护链在研究完成及闭包核验后重新生成了可变 `source_data/MANIFEST.json` 等库存元数据；运行收据和研究输出保持原样，源数据 payload 不变。历史收据记录运行当时的 authority hash，不应拿之后生成的 manifest 时间字段去改写该收据。

## Decision and next permissible research

**Verdict: FAIL — 本版24h方向预测候选；历史机制研究仍为EXPLORATORY。**

你的 ETAS 类比抓住了可测量的成交活跃度聚集，但“后面更活跃”与“后面向哪个方向走”之间仍缺少稳定证据。已有普通量价特征解释了大部分活跃度预测能力，加入幂律特征没有提供可重复的方向增益。

当前版本不应推进交易回测、杠杆或执行阶段。若继续研究，可另开预注册版本检验不同的、事先定义的经济机制，例如区分主动买卖冲击后的价格延续与吸收；必须固定比较规则并在真正未观察的后续数据验证，不能沿用本次历史再反复试参然后改称验证集。本报告没有下载数据、开服务或下单。

## Literature context

[Hawkes processes in finance](https://arxiv.org/abs/1502.04592) 说明 Hawkes 在金融事件聚集中的应用；[Market dynamics immediately before and after financial shocks](https://arxiv.org/abs/1006.1882) 研究金融冲击后的类似 Omori 衰减。它们支持研究这个类比，不为本策略背书。

[Hawkes model for price and trades high-frequency dynamics](https://arxiv.org/abs/1301.1135) 区分成交事件与价格反馈；[Apparent criticality and calibration issues](https://arxiv.org/abs/1308.6756) 说明非平稳性、季节性和标定可能造成假自激；[Spurious trend switching phenomena](https://arxiv.org/abs/1112.3868) 提醒不能用事后挑选的峰谷制造漂亮衰减图。本研究按当时可识别的阈值纳入全部事件，没有用未来峰值筛选。
