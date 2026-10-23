> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

**Core3历史波动九列消融研究：最终验收与收尾说明**

验收时间：2026-10-12T04:21:30.650727+00:00。技术交付状态：`ACCEPTED_COMPLETE_WITH_EXPLICIT_LIMITATIONS`；策略状态：`EXPLORATORY_UNVERIFIED`。本说明是对保存的协议v3／冻结v6／results_v4的最终交付审阅，只更新此前报告中的“待最终签署”状态；旧报告、数值结果、冻结文件及其历史文字保持原字节。这里的验收范围为产物完整、版本绑定与已保存算术审计，不是策略有效性或实盘就绪验收。

原执行已完成13个冻结Ridge规格、90行预测指标、78项比较与12份EMA200账户账本。恢复和本次文档收尾没有训练、推理、bootstrap重跑或账户回放，也没有读取原始行情数值。新增算术仅来自已保存结果：目标/对照差额、已保存H1 NAV回撤和名义规模汇总。本轮没有修改共享导航、两张共享卡片、代码、loader、旧pin、源文件或BB，也没有启动交易、下载、服务或计划任务。

**九列的精确定义与身份边界。** 由已完成H1 trade candles因果聚合4h，`r4h=ln(C_t)-ln(C_(t-1))`。连续列是未去均值的收益二阶矩的自然对数，不是去均值样本方差，不年化，不对零/负/非有限值加epsilon或填补。自身与BTC三列都使用已完成4h收益；BTC品种行的own/BTC列重叠，限制单列归因。二元列为0/1身份标志。

| 冻结列名 | 定义/窗口 | 本轮取舍 |
|---|---|---|
| `own_log_trailing_var_6` | ln(mean(r4h² 最近6个已完成收益))；本品种序列，24小时窗口 | PENDING_ATTRIBUTION |
| `own_log_trailing_var_42` | ln(mean(r4h² 最近42个已完成收益))；本品种序列，168小时窗口 | PENDING_ATTRIBUTION |
| `own_log_trailing_var_180` | ln(mean(r4h² 最近180个已完成收益))；本品种序列，720小时窗口 | PENDING_ATTRIBUTION |
| `btc_log_trailing_var_6` | ln(mean(r4h² 最近6个已完成收益))；BTC序列，24小时窗口 | PENDING_ATTRIBUTION |
| `btc_log_trailing_var_42` | ln(mean(r4h² 最近42个已完成收益))；BTC序列，168小时窗口 | PENDING_ATTRIBUTION |
| `btc_log_trailing_var_180` | ln(mean(r4h² 最近180个已完成收益))；BTC序列，720小时窗口 | PENDING_ATTRIBUTION |
| `symbol_ETH` | 1(symbol=ETHUSDT) | PENDING_ATTRIBUTION |
| `symbol_SOL` | 1(symbol=SOLUSDT) | PENDING_ATTRIBUTION |
| `symbol_BNB` | 1(symbol=BNBUSDT)；Core3无BNB，故全为0 | 代数空列，可无损移除 |

Core3样本只有BTC、ETH、SOL，故`symbol_BNB`恒为0；BNB从未作为本研究标的或BNB收益序列进入训练。训练scaler把零标准差设为1，全零标准化列不提供信息。删除BNB列的9,714行预测在`rtol=1e-12, atol=1e-18`内与FULL等价；这支持无损空列移除，不构成“有效因子发现”，也不增加一个经济模型。其他八列为`PENDING_ATTRIBUTION`，不能因留在FULL中便声称有效。

模型固定Ridge λ=10、TRAIN总体均值/标准差、无惩罚截距；拟合`log(V_1h24)`后直接exp还原，无裁剪/smearing。目标是随后24个已完成H1 close log-return平方均值，成熟于origin+24h；输入4h二阶矩与目标H1二阶矩的采样单位不可混用。TRAIN origins `2021-01-01,2021-07-01)`，成熟/可用标签严格早于cutoff；7日embargo；验证为`[2021-07-08,2022-01-01)`与`[2025-01-01,2026-01-01)`。训练3,237行、验证9,714行，FULL checkpoint的mean/scale/beta最大差均为0；历史配对预测最大差为9.999054535747565e-17。两个验证窗均已曝光/复用，没有未触碰OOS。

时钟约束：输入availability为最新贡献源close+1ms的建模假设，decision为4h close+1001ms；标签maturity为origin+24h，label availability为maturity+1001ms，训练只收availability严格早于cutoff的行。上述delay是研究时钟约定，不证明交易所真实first-public；真实发布仍UNKNOWN。

**FULL/EWMA六组比较。** 正的相对MSE改善为`(EWMA_MSE-FULL_MSE)/EWMA_MSE`。因果EWMA半衰期24个H1收益；下面p属于同一78项Holm家族，区间为描述性bootstrap区间，不能读成同时置信带。

| 币 | 年 | origin数 | FULL MSE | EWMA MSE | FULL相对改善 | 单侧原始p | Holm p(78) | 描述性95%CI |
|---|---|---|---|---|---|---|---|---|
| BTC | 2021 | 1055 | 1.936753397e-09 | 1.896969252e-09 | -2.097248% | 0.602199 | 1.000000 | -14.0138%至+12.4618% |
| BTC | 2025 | 2183 | 7.315349605e-10 | 7.311596922e-10 | -0.051325% | 0.465767 | 1.000000 | -13.2362%至+16.7803% |
| ETH | 2021 | 1055 | 4.545240512e-09 | 4.564176394e-09 | +0.414881% | 0.451774 | 1.000000 | -13.8721%至+20.3920% |
| ETH | 2025 | 2183 | 5.297201732e-09 | 5.757555493e-09 | +7.995646% | 0.167416 | 1.000000 | -6.1909%至+27.4354% |
| SOL | 2021 | 1055 | 5.002198327e-08 | 5.750995165e-08 | +13.020300% | 0.120440 | 1.000000 | -2.6747%至+37.7763% |
| SOL | 2025 | 2183 | 1.062218784e-08 | 9.907734361e-09 | -7.211068% | 0.829585 | 1.000000 | -20.4511%至+9.7686% |

预测点估计为三格改善、三格恶化；六项FULL/EWMA的Holm p全部为1。结论是未建立冻结准则要求的稳定预测优势，不是证明该波动块无效。24h标签每4h起点重叠；每年分别同步重采样所有币/分支，28个UTC观测日期环形块、2,000次、seed20261012，2021/2025不跨窗。日期簇为176/364，贪心非重叠24h目标窗每币也为176/364；两种计数都不是有效独立N，后者仍UNKNOWN。全部78项均COMPLETED，多个删除比较的个别格可显著，不能据此事后降低整模型准入条件。

**全部删除分支及取舍。** 表中“变差”按六格归一化MSE相对FULL差值小于-1e-12判定；ETH Holm p顺序为2021/2025。准入同时要求六格不差、ETH两年正改善且两项Holm p≤0.05、ETH两年QLIKE不差。所有12个删除分支都已报告；BNB是代数空列，剩余11个实质简化全部未准入，selected=null。

| 分支 | MSE变差的格 | ETH双年Holm p | ETH双年QLIKE不差 | 最终取舍/理由 |
|---|---|---|---|---|
| `DROP_OWN_LOG_TRAILING_VAR_6` | ETH/2025,SOL/2021,SOL/2025 | 1.000000/1.000000 | 是 | ETH2025和SOL两年变差；准入失败。 |
| `DROP_OWN_LOG_TRAILING_VAR_42` | BTC/2021,BTC/2025,ETH/2021,ETH/2025,SOL/2021,SOL/2025 | 1.000000/1.000000 | 否 | 六格MSE均变差；拒绝此删除，不据此宣称该列已有效。 |
| `DROP_OWN_LOG_TRAILING_VAR_180` | BTC/2021,BTC/2025,ETH/2021,SOL/2021,SOL/2025 | 1.000000/0.038981 | 否 | 仅ETH2025点改善；ETH2021及其余格变差。 |
| `DROP_BTC_LOG_TRAILING_VAR_6` | BTC/2021,BTC/2025,ETH/2021,ETH/2025,SOL/2025 | 1.000000/1.000000 | 是 | 五格变差，仅SOL2021微小改善。 |
| `DROP_BTC_LOG_TRAILING_VAR_42` | ETH/2025 | 0.101949/1.000000 | 否 | 五格点改善但ETH2025变差，ETH双年/QLIKE门失败。 |
| `DROP_BTC_LOG_TRAILING_VAR_180` | SOL/2021 | 1.000000/0.038981 | 否 | 五格点改善但SOL2021变差；ETH2021的Holm/QLIKE门失败。 |
| `DROP_SYMBOL_ETH` | BTC/2021,BTC/2025,ETH/2025 | 0.038981/1.000000 | 否 | ETH2021点改善但BTC两年与ETH2025变差。 |
| `DROP_SYMBOL_SOL` | ETH/2025 | 0.766617/1.000000 | 否 | 五格点改善但ETH2025变差，双年/QLIKE门失败。 |
| `DROP_SYMBOL_BNB` | 无 | 1.000000/1.000000 | N/A空列 | 全行预测在冻结容差内等价，仅作无损空列删除。 |
| `DROP_BTC_BLOCK` | 无 | 1.000000/0.101949 | 是 | 六格点改善且ETH双年QLIKE不劣，但双年显著性门失败。 |
| `DROP_OWN_LONG` | BTC/2021,BTC/2025,ETH/2021,SOL/2021,SOL/2025 | 1.000000/1.000000 | 否 | 五格变差，仅ETH2025点改善；拒绝此组删除。 |
| `DROP_SYMBOL_BLOCK` | ETH/2025 | 0.389805/1.000000 | 否 | 五格点改善但ETH2025变差，双年/QLIKE门失败。 |

保留FULL作为冻结对照规格；只有常零BNB允许在未来独立版本作无损清理，本轮没有改动冻结模型或列顺序。其余八列不作肯定保留/有效结论；分组BTC块虽六格点改善仍未过ETH双年显著性门，不按PnL换选。全部13个Ridge、EWMA24和TRAIN_MEAN共90行MSE/QLIKE在[原指标表 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/core3_variance_ablation_20261012_v1/delivery_v1/prediction_metrics_15_arms_6_cells.csv`)；78项完整统计 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/core3_variance_ablation_20261012_v1/delivery_v1/inference_78_contrasts.csv`)和准入理由 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/core3_variance_ablation_20261012_v1/delivery_v1/branch_admission_criteria.json`)原样保留。

**EMA200账本覆盖、净结果、回撤和名义规模。** 只评估冻结EMA200主成本情景，每账起始NAV100,000 USDT，每年独立重置。q1是固定初始槽位基准：单币初始槽位100000×0.98/3=32,666.666667 USDT，不是恒定NAV百分比仓位；风险arm只在入场乘`q=min(1,sqrt(TRAIN reference/pred))`。本轮无准入简化模型，q1/EWMA24/FULL各两年、各target/自身静态matched control，总计12/12账本均COMPLETED。2021每账42笔、4,250个保存NAV样本；2025每账95笔。下表均为条件模拟账本，无年化或可实现收益承诺。

平均总名义规模=`Σ逐币gross_USDT_hours / 全账户日历小时数`，包括空仓小时；2021分母4,248小时，2025为8,760小时。峰值取已保存H1标记账本的gross_USDT，不代表分钟/逐笔实际峰值。最大回撤为保存H1 mark NAV对含初始锚点running high的最小相对差，表保留负号。

| 年 | arm | 角色 | 笔数 | 净PnL USDT | 窗口净收益 | H1标记MaxDD | 平均总名义USDT | 保存H1峰值名义USDT |
|---|---|---|---|---|---|---|---|---|
| 2021 | q1 | target | 42 | 111,906.737846 | 111.906738% | -33.201724% | 93,440.0064 | 289,123.8708 |
| 2021 | q1 | matched_control | 42 | 111,906.737846 | 111.906738% | -33.201724% | 93,440.0064 | 289,123.8708 |
| 2021 | EWMA24 | target | 42 | 112,536.955801 | 112.536956% | -32.982912% | 93,310.1669 | 289,123.8708 |
| 2021 | EWMA24 | matched_control | 42 | 111,999.752466 | 111.999752% | -33.186692% | 93,337.3150 | 289,242.3356 |
| 2021 | FULL | target | 42 | 112,636.294309 | 112.636294% | -32.956081% | 93,285.4752 | 289,123.8708 |
| 2021 | FULL | matched_control | 42 | 112,046.259776 | 112.046260% | -33.179181% | 93,285.9693 | 289,301.5680 |
| 2025 | q1 | target | 95 | 21,651.662456 | 21.651662% | -19.857841% | 50,467.0470 | 137,972.9273 |
| 2025 | q1 | matched_control | 95 | 21,651.662456 | 21.651662% | -19.857841% | 50,467.0470 | 137,972.9273 |
| 2025 | EWMA24 | target | 95 | 21,651.662456 | 21.651662% | -19.857841% | 50,467.0470 | 137,972.9273 |
| 2025 | EWMA24 | matched_control | 95 | 21,651.662456 | 21.651662% | -19.857841% | 50,467.0470 | 137,972.9273 |
| 2025 | FULL | target | 95 | 21,651.662456 | 21.651662% | -19.857841% | 50,467.0470 | 137,972.9273 |
| 2025 | FULL | matched_control | 95 | 21,651.662456 | 21.651662% | -19.857841% | 50,467.0470 | 137,972.9273 |

**2021相对固定基准和各自匹配控制。** 正ΔMaxDD表示负回撤较少，单位为百分点；这是对同窗保存账本的算术比较，不是增量效应置信区间。

| risk arm | 对照 | Δ净PnL USDT | Δ窗口净收益pp | ΔMaxDD pp |
|---|---|---|---|---|
| EWMA24 | fixed_q1 | +630.217955 | +0.630218 | +0.218812 |
| EWMA24 | own_matched_control | +537.203334 | +0.537203 | +0.203780 |
| FULL | fixed_q1 | +729.556463 | +0.729556 | +0.245642 |
| FULL | own_matched_control | +590.034533 | +0.590035 | +0.223100 |

2021 EWMA/FULL各只有3/42次入口q<1，最低q分别0.8273292813/0.7911816373。相对固定q1的不同名义规模不能单独归为因子alpha；各自匹配控制进一步匹配逐币gross USDT-hours，但仍不控制完整风险路径、未触碰OOS或真实成交，经济比较没有额外统计显著性检验。两种risk arm各自静态控制不同，537.20与590.03的差也不构成FULL相对EWMA的已验证alpha。

| arm | 控制静态scale(BTC/ETH/SOL) | 逐币相对匹配误差 | 匹配回放次数(原运行) | 验收 |
|---|---|---|---|---|
| q1 | BTCUSDT=1.00000000, ETHUSDT=1.00000000, SOLUSDT=1.00000000 | BTCUSDT=0.0000000%, ETHUSDT=0.0000000%, SOLUSDT=0.0000000% | 0 | 0.1%门通过 |
| EWMA24 | BTCUSDT=1.00000000, ETHUSDT=1.00000000, SOLUSDT=0.99218750 | BTCUSDT=0.0000000%, ETHUSDT=0.0529195%, SOLUSDT=0.0297969% | 70 | 0.1%门通过 |
| FULL | BTCUSDT=1.00000000, ETHUSDT=1.00000000, SOLUSDT=0.98828125 | BTCUSDT=0.0000000%, ETHUSDT=0.0000000%, SOLUSDT=0.0011438% | 76 | 0.1%门通过 |

匹配器版本为`core3_exposure_match_v2`，scale范围[0,4]、每目标最多256次账户曝光评估；目标仅逐币曝光误差，不接收PnL/成本。0.1%门槛未放宽。EWMA误差最大0.0529195274%，FULL最大0.0011437696%；70/76次是原执行的曝光校准账本回放，恢复/收尾没有重跑。旧Core3三策略2021匹配失败保留，不能用本轮EMA专用新版匹配成功改写旧结论。

| 2021 arm | 角色 | BTC gross USDT-hours | ETH gross USDT-hours | SOL gross USDT-hours | 保存H1峰值gross/NAV |
|---|---|---|---|---|---|
| q1 | target | 98,211,275.934579 | 114,577,763.398151 | 184,144,107.885364 | 101.187708% |
| q1 | matched_control | 98,211,275.934579 | 114,577,763.398151 | 184,144,107.885364 | 101.187708% |
| EWMA24 | target | 98,211,275.934579 | 114,517,161.457531 | 183,653,151.773863 | 101.187708% |
| EWMA24 | matched_control | 98,211,275.934579 | 114,577,763.398151 | 183,707,874.720466 | 101.187848% |
| FULL | target | 98,211,275.934579 | 114,577,763.398151 | 183,487,659.461860 | 101.187708% |
| FULL | matched_control | 98,211,275.934579 | 114,577,763.398151 | 183,489,758.138017 | 101.187917% |

98%是入场时已知mark/NAV的名义预算检查，不是持续再平衡上限。保存的2021峰值gross/NAV约101.19%，可由持有期间mark/NAV变动产生；初始100,000 USDT账户的保存峰值gross约289,124–289,302 USDT也不等于执行了杠杆配置。原入场cap算术审计只验证入场数量/预算，未证明维持保证金、强平、借贷或盘中风险路径。

**2025零动作及成本限制。** EWMA和FULL各95次入场全部q=1，各自目标、匹配控制与固定q1净账本、回撤和曝光一致；净差额均为0。条件窗口净PnL为21,651.662456 USDT、净收益21.651662%、H1标记回撤-19.857841%。本规则在2025无法检验仓位缩放增益；没有事后降低参考阈值，也没有按收益选参。此前三策略291次旧q=1证据保持，本轮95次为EMA子集。

| 年 | target arm | 价格PnL(已含fill滑点) | 观测Funding现金流 | 双边Fees | 已含滑点另列(不再扣) | 保存现金残差 |
|---|---|---|---|---|---|---|
| 2021 | q1 | 124,535.923901 | -11,197.720784 | 1,431.465271 | 1,431.496763 | 2.910e-11 |
| 2021 | EWMA24 | 125,148.245090 | -11,191.259419 | 1,420.029871 | 1,420.061513 | 5.821e-11 |
| 2021 | FULL | 125,246.758545 | -11,189.897318 | 1,420.566918 | 1,420.598585 | 2.910e-11 |
| 2025 | q1 | 27,458.020431 | -2,745.335456 | 3,061.022518 | 3,061.030148 | 5.093e-10 |
| 2025 | EWMA24 | 27,458.020431 | -2,745.335456 | 3,061.022518 | 3,061.030148 | 5.093e-10 |
| 2025 | FULL | 27,458.020431 | -2,745.335456 | 3,061.022518 | 3,061.030148 | 5.093e-10 |

主情景每边5bp fee+5bp adverse slippage。`realized_price_pnl`已经使用不利fill价格，净PnL核算为价格PnL+funding-fees；单独报告slippage不得再扣一次。各控制成本见[原账户完整表](ema200_account_summary.csv)。funding保留观测原生事件；此前genuine H1 mark close仅为估值/资金费proxy，其真实发布及是否为交易所结算mark仍UNKNOWN。无spread/capacity/实际成交/保证金/强平证据，未跑stress网格，不能从这些净数字推导可交易收益。

**2026与volume来源澄清。** 新适配器在Arrow `to_table(filter=...)`阶段筛选，再转pandas；保存的源审计和冻结代码表明2026及之后观测未进入返回给pandas的行、特征、标签、Ridge或账本计算。源文件仍含2026尾部；整文件SHA256读取字节只用于身份核验。物理Parquet页/列块是否扫描或解压到被排除2026值为`NOT_PROVEN`，不能声称已证明任何物理解码前排除。旧loader与旧pin未改。

三份mark源Parquet schema仅有身份/时钟/OHLC/来源字段，无volume/base_volume。新适配器第145行把mark `volume=0.0`放入内存canonical frame，属于通用布局兼容占位，非观测成交量或供应商原字段。该列可经过通用schema检查/4h布局聚合，但不进入风险特征、标签、q、账户估值或funding现金流公式；这些仍用genuine mark价格。故这里的“未入计算”限于研究数值公式，不能扩写成“源文件原有volume”。原审计`imputation:false`必须限缩为价格/观测funding未填补，不能作为所有适配字段均原生的证明。该占位字段是元数据限制，本轮未修代码或改写冻结产物，不以兼容布局豁免无捏造要求。

原`consumed_by_model`是过宽的流水线标志。准确角色为：三条H1 trade OHLCV直接构造Ridge特征与标签（BTC供共享背景）；三条genuine mark仅账户估值/proxy；三条funding events仅账户成本；三条derived4h仅准入血缘凭据，本研究特征由H1 helper重新构造。marks/funding/derived4h不当作Ridge输入或目标。原收据保留，解释由输入角色补充 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/core3_variance_ablation_20261012_v1/delivery_v1/MODEL_FACTOR_VERSION_BINDINGS_V1.json`)和本最终说明完成。

**执行预算、审查与最终签署。** 两次早期身份拒绝各0拟合/0回放；第三次包装器错误有13次分支拟合尝试，未发布模型/指标，未检查选择指标，个别成功拟合数未持久化而为UNKNOWN；唯一机械重试完成13个模型，因此累计26次分支拟合尝试、13个唯一规格。历史Core3原checkpoint旧拟合另计。v6的一次性许可已用完，不复用审批，不隐藏技术重试，不把UNKNOWN成功数改成13。

已保存原独立审查：数值重构 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/core3_variance_ablation_20261012_v1/root_review/INDEPENDENT_NUMERIC_RECONSTRUCTION_V1.json`)以独立公式核对训练/标签/预测、90格指标、78项bootstrap/Holm及12账本，状态`PASS_RECONSTRUCTION_ONLY_NOT_A_STRATEGY_GATE`；入场cap审计 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/core3_variance_ablation_20261012_v1/root_review/INDEPENDENT_ENTRY_CAP_AUDIT_V1.json`)覆盖12账户，状态`PASS_ARITHMETIC_ENTRY_CAP_ONLY`。本轮核实这两份文件哈希和引用，没有重跑其中的源行情、bootstrap或账本重构。另从保存NAV轻量复算12个H1回撤，并核对净现金公式、固定/匹配对照差额和名义规模。54项原focused/Core3回归保存在XML (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/core3_variance_ablation_20261012_v1/root_review/ROUND3_NATIVE_AND_CORE_REGRESSION.xml`)，本轮未重新运行pytest。

本次恢复核验：29项冻结依赖、7份实现快照、12项准入文件、阶段一7个产物及旧交付10项hash均匹配；55份原JSON严格解析成功，原README/完整报告27个本地链接存在。任务前1,942文件快照当前1,933不变、9变化，涉及源/global清单、Hub导航/USAGE和原执行对两张卡片的补充；这是原任务/并发的既存变化，本轮保留。当前数值协议、代码、输入和旧loader/reference绑定无污染。六项历史身份门禁保存XML仍全部拒绝，未刷新旧pin。此前04:12UTC进程快照无Python/pytest；原实现和平台并发子任务均completed，本轮无需重启。

全局import/inventory/report再生成与全套pytest本次未运行：用户明确限定仅本实验delivery/root_review的文档收尾，禁止改共享文件、冻结运行文件和数值产物。这里按该授权边界保留所有既存失败；不把doc验收写为全项目全绿。已按工作区策略验证模板保存EMA200 q1 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/core3_variance_ablation_20261012_v1/root_review/STRATEGY_GATES_EMA200_Q1.md`)、EWMA24 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/core3_variance_ablation_20261012_v1/root_review/STRATEGY_GATES_EMA200_EWMA24.md`)、FULL (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/core3_variance_ablation_20261012_v1/root_review/STRATEGY_GATES_EMA200_FULL.md`)门报告，关键门仍BLOCKED/NOT_RUN。

最终签署：产物完整性、版本绑定和已保存独立算术证据可接受，本历史研究于本交付阶段结束。未证明有效因子或经济alpha，非显著不等于无效；常零列清理不是信号发现。真实发布时间/结算mark、物理解压排除、真实成交/容量/保证金、压力情景和未触碰OOS仍为未完成证据，不在本轮通过补跑或修改阈值解决。本说明接续原报告的待签署状态而不改其字节；完整机器数值在最终验收证据 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/core3_variance_ablation_20261012_v1/root_review/FINAL_ACCEPTANCE_EVIDENCE_V1.json`)，发布后完整性回读在最终回读记录 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/core3_variance_ablation_20261012_v1/root_review/FINAL_ACCEPTANCE_READBACK_V1.json`)。

| 冻结/结果/审查对象 | SHA256 |
|---|---|
| freeze_static_v6/frozen_protocol.json | 110A5324022BE728821B580482B48073020897EF0B12E4B13801A78A945C6094 |
| freeze_static_v6/freeze_receipt.json | 07CD738C5C740C004F09C3841AA82AEF674DE2C3BCAFEE3A35CD2C9D05B09F39 |
| root_review/NUMERIC_APPROVAL_FREEZE_V6.json | 8AA1D83EA5E92A0510CCD070B353C402C223CF276E04EE51029BCF8BC997A7B1 |
| results_v4/results.json | 4DB9667CFD39548E509152D1A658C3C0EE7D74687F0A066623E02B3681B589D1 |
| results_v4/stage1_receipt.json | C0EDF38D4CFB69316CE39BD902B0F51EA9D09CB92EEA801CB642EE2B05197DB9 |
| results_v4/stage2_results.json | 657B5646B9C85D003DC70D5671F821AC30E02BDD9A0943E0B89B7195E29C44D4 |
| results_v4/stage2_account_ledgers.json | 1E54DBAF5C7411E161E760421849DE18FA6A5C93DADF923D208E03B7460B15A4 |
| root_review/INDEPENDENT_NUMERIC_RECONSTRUCTION_V1.json | E35AC583827C7FE702C109A18F3E6A283A4BBE06DD6A3FEBA67A8D78E9D34760 |
| root_review/INDEPENDENT_ENTRY_CAP_AUDIT_V1.json | 1F42510B5F9AB36FA2A252988B2B19414E3D5ACDAA66F0698A53372191E47CA6 |

只读检查命令（从仓库根目录）：

```powershell
.\.venv\Scripts\python.exe -B -X utf8 scripts/run_core3_variance_ablation_v1.py --mode dry-run
Get-FileHash -Algorithm SHA256 -LiteralPath 'reports/strategy_validation/core3_variance_ablation_20261012_v1/results_v4/results.json'
```

不提供数值续跑命令：13模型和12账本均已完成。
