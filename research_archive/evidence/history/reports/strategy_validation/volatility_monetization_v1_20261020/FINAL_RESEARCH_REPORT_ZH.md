> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 波动预测如何转成合约收益：本轮研究报告

结论状态：**EXPLORATORY / UNVERIFIED**。本轮找到了值得继续检验的
“中期趋势、波动风险预算、差额调仓”组合机制，但没有找到或复原
“稳定每年十倍”的方法。独立审阅和全项目检查的完成状态见文末。

## 1. 原始相关系数已找到，原模型没有用 IV

用户给出的 BTC 1h/4h/8h/24h 数字，分别对应旧结果中的
0.4041/0.5069/0.5483/0.5960。独立重算能够复现。
原模型使用 OHLCV Ridge，不包含 IV。
旧的另一个“无 IV / 有 IV”比较还存在特征污染：
所谓无 IV 组实际包含 IV 列，因此该比较不能证明 IV 的增量。

本轮新建了统一目标：未来 H 个小时开盘收益平方均值的平方根，
按 8760 小时年化；每个币每天一个决策起点。
24h 窗口在同币内不重叠。扩展训练按年进行，标准化只拟合训练期，
训练标签必须在预测年开始前成熟。所有历史均已被查看，
这些逐年检查不是未触碰样本外。

| 新研究 24h 预测，BTC/ETH 合并 | 相关系数 | RMSE，年化小数 |
| --- | ---: | ---: |
| 过去 24h 实现波动 | 0.5445 | 0.2915 |
| 单独 IV 模型 | 0.5142 | 0.2812 |
| 价格模型 | 0.6073 | 0.2438 |
| 价格加 IV 模型 | 0.6325 | 0.2366 |

加入 IV 后相对价格模型的 SSE 降低约 **5.80%**，但逐年不完全一致；
BTC 2024 年的 SSE 反而增加约 2.35%。
将 IV 再延迟一天使用，价格加 IV 的相关系数降到 **0.6143**。
该日线 IV 的历史发布时间仍是未验证假设。

DVOL 是约 30 天的年化隐含波动指标，本轮把它用作预测 24h RV 的特征，
没有直接交易 DVOL 期货或期权。定义见
Deribit 官方说明 (`provenance:external/a3c52b373ac19045`)。

## 2. 首轮 30 账户：预测更准并没有自动变成更多收益

冻结的首轮实验包含 30 日趋势、7 日突破、1 日反转；每条方向规则
配四种仓位，成本为每边 6bp/10bp，另加六个 IV 延迟压力账户。
BTC/ETH 各分配至多 0.5 的初始名义资本预算。
该轮明确按每日全平旧仓、全开新仓收费。
全文的每边 6bp/10bp，均指按实际成交单边名义金额扣除的总不利
执行成本假设，包含费用/滑点代理；未用历史佣金和盘口实测校准。

交易日标签为 2022-01-01 至 2026-09-23，共 1727 日；
最后持仓在 2026-09-24 02:00 UTC 结束。
所有收益包含观察到的资金费事件，最大回撤使用小时标记价格和
资金费/成交事件净值，而不是只看日末余额。

| 首轮示例，每边 6bp | 历史 CAGR | 最大观察回撤 |
| --- | ---: | ---: |
| 30 日趋势，固定仓位 | −16.13% | −77.87% |
| 30 日趋势，价格加 IV 控仓 | −5.28% | −47.09% |
| 7 日突破，过去波动控仓 | +3.68% | −4.54% |
| 7 日突破，价格加 IV 控仓 | +2.59% | −5.61% |
| 1 日反转，价格加 IV 控仓 | −17.36% | −64.51% |

突破组仅有 79 笔交易，平均账户名义敞口很低，不能按较低回撤直接
推断可大幅加杠杆。首轮全部组合的完整年度十倍命中为零。
这一轮也不能用来否定低换手趋势：每日全平全开的执行方式会产生
大量本来无需发生的交易成本。

## 3. 事后追加的差额调仓对照

看过首轮结果后，另行冻结了八账户执行对照。
这是明确标注的 **AFTER_VIEWING_V1_EXPLORATORY**，
没有改写首轮结果，也没有把追加试验当作 OOS。

固定规则如下：

- 每日 01:00 UTC，以过去 30 日价格变动的正负决定多空。
- 固定仓位组每币目标权重恒为 0.5。其余三组每币权重为
  `0.5 × min(1, 0.30 / max(波动输入, 0.05))`：
  过去波动组代入过去 24h RV；价格组和价格加 IV 组分别代入
  各自模型预测的未来 24h 年化波动。
- 每日 02:00 使用两币共享的交易前账户净值计算目标合约数量。
  只买卖“目标数量减当前数量”，按实际差额名义额收费。
- 资金费在原生结算时刻按实际持仓数量入账；结束时全部平仓并收费。
  每次费用都会影响净值，进而影响下一次的真实目标数量。

总目标敞口上限 1 倍以计算目标数量时的交易前净值为分母，
不保证持有期间的实际敞口始终不超过 1 倍。
6bp 路径中固定仓位和价格加 IV 组的最高实际总敞口/净值，
分别约为 1.362 倍和 1.076 倍；没有据此模拟保证金或强平。

| 差额调仓，每边 6bp | 全期财富倍数 | 历史 CAGR | 年化收益波动 | 最大观察回撤 |
| --- | ---: | ---: | ---: | ---: |
| 固定仓位 | 2.8063× | 24.39% | 53.36% | −50.48% |
| 过去 24h 波动控仓 | 1.8998× | 14.54% | 32.70% | −32.03% |
| 价格预测波动控仓 | 2.2891× | 19.14% | 29.02% | −26.22% |
| 价格加 IV 预测控仓 | 2.4451× | 20.82% | 30.06% | −27.41% |

成本提高到每边 10bp 后，价格加 IV 组历史 CAGR 为 **17.37%**，
最大观察回撤约 **27.90%**，全期财富倍数为 **2.1329×**。

价格加 IV 组的完整年度收益依次约为：
2022 年 +11.27%、2023 年 +32.68%、2024 年 +7.99%、
2025 年 +34.89%。2026 年截至本窗口约 +13.70%，是部分年度，
不能当作全年结果。所有八账户均没有完整年度十倍。

这表明执行和换手成本会实质影响结论。它尚不能证明预测模型创造了
可靠的额外收益：相对过去波动控仓，模型也改变了平均敞口、
波动和调仓量。固定仓位本身的历史 CAGR 更高，同时回撤接近一半。

本轮末尾另作的描述性配对检查（事后审阅，不是预登记显著性检验）
使用 30 日移动区块、1000 次重采样、种子 20261020：

| 6bp 日净收益差 | 平均差，bp/日 | 描述性 95% 区间，bp/日 |
| --- | ---: | ---: |
| PRICE − 过去波动 | +0.775 | [−0.840, +2.555] |
| PRICE_IV − 过去波动 | +1.241 | [−0.410, +2.931] |

两个区间都跨零。不能把点估计或逐年盈利表称为稳定优势。

独立费用归因进一步发现：PRICE 相对过去波动控仓的日均净收益差中，
约 **77.1%** 对应成本项减少；PRICE_IV 相对过去波动的比例约
**48.5%**。这是按同一持仓日的期初净值归一后的既有路径会计分解，
不是重新模拟的无费用账户，也不是对 CAGR 的因果分解。
模型仓位在方向不变时的调整幅度约为原始 RV 仓位的一半，
所以“更平滑、少调仓”是需要认真检验的替代解释。

PRICE_IV 相对 PRICE 的平均敞口从约 0.6213 升至 0.6540，
实际波动和回撤也更高；它多出的约 1.67 个百分点 CAGR
不能直接视为 IV 创造的 alpha。
详见 [经济归因审阅](review/ECONOMIC_ATTRIBUTION_REVIEW.md)。

## 4. 对下一步研究方向的判断

优先保留的候选机制是：**低换手的中期趋势 + 风险预算 + 差额调仓**。
应先检验其相对简单、平滑的波动基线是否仍有收益和风险改善，
并加入公平敞口对照；随后才有理由研究杠杆。
本轮没有保证金和强平路径，不能把约 20% 的 CAGR 乘以杠杆，
当成某个更高收益率的证据。

未知交易者还可能采用宽币池强弱选择、跨币相对价值、资金费/基差、
或做市执行。这些机制的本地历史证据已定位在
范围与证据地图 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volatility_monetization_v1_20261020/REVIEW_SCOPE_AND_FINDINGS.md`)。
若没有其实际净值、入出金、仓位及持仓时长，无法从“每年十倍”
倒推出真实方法，也无法确认其收益是否按全账户资本计算。

## 5. 数据、代码和验证状态

本轮只读取本地 BTC/ETH 永续小时价、注册的小时标记价格、
经独立分区绑定核验的原生资金费事件及已登记 DVOL。
没有下载行情、下单、使用 API 密钥或注册服务。

两币在 2024-10-28 20:00 的源表有零成交量和平坦 OHLC 记录。
168h 对数量能特征因此在 10 月 29 日至 11 月 4 日不可用；
七日从所有预测臂共同排除，账户日历保留并统一转现金。
差额调仓的第一个现金日仍支付旧仓退出成本；后六日才是零持仓、
零损益。不能把七个现金日都描述成零收益日。
未填补行情或资金费。零量记录的真实市场原因尚未独立确认。

首轮独立对账覆盖 30 账户、51,810 条日账、
45,290 条交易、135,870 条资金费事件和 1,560,560 条 MTM 记录。
金额对账最大误差约 1.90e−13，14 项代码/输入身份一致。
这证明保存账本内部一致，不证明执行真实性或交易有效性。

最终两个模块的专项测试为 **26 passed**。
补充八账户独立对账覆盖 13,816 条日账、27,648 条调仓记录、
82,560 条原生资金费和 441,808 条小时/事件净值记录，
最大 CSV 重算金额差约 2.1e−12。首笔执行价缺失、NaN、零和负值
均已验证会拒绝运行；修复前后正式数据的指标逐值相同。
全项目回归最终为 **4700 passed、14 failed、1 skipped**。
其中四项 pipeline 失败由 root 编排的最终维护链与全量测试重叠、
共享 MANIFEST 在模块导入后改变所触发；在维护结束后的新进程中，
四项均独立复查通过，运行前后权威文件指纹一致。
另外十项的具体错误均有此前日志记录：旧 registry 身份校验五项、
Channel 指纹计数两项、CLI 编码/输出捕获两项、保留的旧 EMA 断言一项。
没有修改旧身份、断言或实现来消除这些失败。
这轮全量运行存在输入变化，不能称为干净回归或整体通过；
详见 最终验证记录 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volatility_monetization_v1_20261020/review/FINAL_VERIFICATION_STATUS.md`)。
维护链已按顺序执行：verify=1、import=3、inventory=0、reports=0；
旧来源中有 54 项未获得独立身份验证，因此整体转换被拒绝。
不能将该维护结果称为通过。本轮所用 core staged 输入已另行通过绑定校验。

所有策略均保留 `EXPLORATORY / UNVERIFIED`：
缺少未触碰 OOS、已测得的盘口/冲击/容量、完整保证金/强平路径，
以及既有模拟和真实成交观察记录。

详细证据：

- 独立首轮账本审阅 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volatility_monetization_v1_20261020/review/INDEPENDENT_LEDGER_REVIEW.md`)
- 独立差额调仓账本审阅 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volatility_monetization_v1_20261020/review/NET_REBALANCE_REVIEW.md`)
- [收益与费用归因审阅](review/ECONOMIC_ATTRIBUTION_REVIEW.md)
- 最终测试与维护状态 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volatility_monetization_v1_20261020/review/FINAL_VERIFICATION_STATUS.md`)
- 趋势族门槛报告 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volatility_monetization_v1_20261020/trend30d_family.md`)
- 突破族门槛报告 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volatility_monetization_v1_20261020/breakout7d_family.md`)
- 反转族门槛报告 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volatility_monetization_v1_20261020/reversion1d_family.md`)
- 预测族门槛报告 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volatility_monetization_v1_20261020/volatility_forecast_family.md`)
- 差额调仓补充门槛报告 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/volatility_monetization_v1_20261020/net_rebalance_supplement_after_viewing_v1/trend30d_net_rebalance_supplement.md`)
