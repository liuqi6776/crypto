> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# Long-cycle 12策略账户回放结果（冻结 v3）

日期：2026-10-03。数据只使用经验证的本地 USDT 永续源；训练段为 `2020-09-15, 2025-01-01)`，复用验证段为 `[2025-01-01, 2026-01-01)`。训练收益是整个训练段的累计收益，未年化。2025 已在先前研究中检查过，所以它不是 untouched OOS。2026 数值未加载或计算；账户源读取被限定在 2026-01-01 UTC 之前。

## 批次与复核依据

- 批次目录：[`accounts_v3_frozen_20261003` (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/longcycle_trend_catalog_v1/accounts_v3_frozen_20261003/receipt.json`)，回执 SHA256 `94328CF42B4D2FEC08F71D7F74E3E6B56DAFFC9A0CDFFEF8D859F4E98F875828`；账户锁 SHA256 `303650FCC9A70CDBBDF3A8FEE35305FF86B63E46CADF63504D42814CA2BE96B9`。
- 汇总 CSV SHA256 `3B51FF82FC55CCE4DB6825C6DA5BFF85F20B1DC880E44FB7A9A5BE3F17909DA4`；共 28 行（12 arms × 训练/验证 + 两个买入持有基准 × 训练/验证）。完整逐行数值以 `account_summary.csv` (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/longcycle_trend_catalog_v1/accounts_v3_frozen_20261003/account_summary.csv`) 为准。
- 取消的首次慢运行留在 `canceled_slow_account_run_v1.json` (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/longcycle_trend_catalog_v1/canceled_slow_account_run_v1.json`)，它有已开始市场数值读取的记录，未写账户输出；完成结果来自另一个 v3 批次。
- 成本口径：每边 5bp 费用、每边 5bp 不利滑点、只记观察到的 funding；实际成交价已计入滑点，报告的滑点成本仅单独披露一次，不从净结果重复扣除。分段钱包各 100,000 USDT、固定初始槽位、不复利。该账本不实现 venue spread、容量、保证金阶梯或路径清算模型。
- Sharpe 是连续日 NAV 收益、样本标准差、年化 `sqrt(365)`；回撤来自含初始锚点的小时 NAV。最大 gross/NAV 可因价格变动超过 1。

## 28行账户汇总

| 账户 | 区间 | 状态 | 净收益 | 日 Sharpe | 小时最大回撤 | 完成交易数 |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: |
| EMA200_4h | train | COMPLETED | 545.63% | 1.555 | -27.04% | 403 |
| EMA200_1d | train | COMPLETED | 424.50% | 1.065 | -57.58% | 55 |
| EMA20_60_4h | train | COMPLETED | 583.30% | 1.641 | -26.57% | 231 |
| EMA20_60_1d | train | NO_BORROW_FAIL | 未报告 | 未报告 | 未报告 | 未报告 |
| MACD_4h | train | COMPLETED | 138.40% | 0.821 | -52.40% | 1100 |
| MACD_1d | train | COMPLETED | 397.32% | 1.638 | -26.50% | 168 |
| MACD_EMA200_4h | train | COMPLETED | 153.43% | 1.194 | -20.93% | 800 |
| MACD_EMA200_1d | train | COMPLETED | 311.34% | 1.659 | -25.66% | 120 |
| DONCHIAN55_20_4h | train | COMPLETED | 246.93% | 1.294 | -33.01% | 184 |
| DONCHIAN55_20_1d | train | COMPLETED | 508.59% | 1.324 | -39.59% | 30 |
| BB120_EMA200_ATR3_4h | train | COMPLETED | 76.32% | 0.789 | -19.13% | 115 |
| BB120_EMA200_ATR3_1d | train | COMPLETED | 127.65% | 1.060 | -32.79% | 18 |
| BTC_98_BH | train | NO_BORROW_FAIL | 未报告 | 未报告 | 未报告 | 未报告 |
| CORE3_98_BH | train | NO_BORROW_FAIL | 未报告 | 未报告 | 未报告 | 未报告 |
| EMA200_4h | validation | COMPLETED | 21.65% | 0.759 | -19.86% | 95 |
| EMA200_1d | validation | COMPLETED | -5.21% | 0.049 | -26.47% | 26 |
| EMA20_60_4h | validation | COMPLETED | -5.75% | -0.033 | -26.32% | 59 |
| EMA20_60_1d | validation | COMPLETED | 1.07% | 0.213 | -22.33% | 10 |
| MACD_4h | validation | COMPLETED | -4.82% | 0.104 | -37.06% | 244 |
| MACD_1d | validation | COMPLETED | -39.18% | -1.127 | -43.49% | 51 |
| MACD_EMA200_4h | validation | COMPLETED | 14.96% | 0.706 | -19.11% | 155 |
| MACD_EMA200_1d | validation | COMPLETED | -22.52% | -0.830 | -33.62% | 44 |
| DONCHIAN55_20_4h | validation | COMPLETED | 8.16% | 0.433 | -21.69% | 41 |
| DONCHIAN55_20_1d | validation | COMPLETED | -1.63% | 0.070 | -15.49% | 8 |
| BB120_EMA200_ATR3_4h | validation | COMPLETED | 16.81% | 1.269 | -7.62% | 19 |
| BB120_EMA200_ATR3_1d | validation | COMPLETED | -9.04% | -0.693 | -16.35% | 6 |
| BTC_98_BH | validation | COMPLETED | -12.01% | -0.097 | -35.92% | 1 |
| CORE3_98_BH | validation | COMPLETED | -20.54% | -0.072 | -51.40% | 3 |

## 12个策略版本的研究优先级

训练列为整段累计收益（非年化）；验证列为复用的2025样本。次级对照用于比较，不是通过标准。2025亏损表示对应参数版本在该复用窗口不支持，不据此否定更宽泛的策略想法。

| 策略版本 | 训练累计收益 | 2025验证收益 | 验证日Sharpe | 验证小时MDD | 验证交易数 | 当前研究优先级 |
| :--- | ---: | ---: | ---: | ---: | ---: | :--- |
| EMA200_4h | 545.63% | 21.65% | 0.759 | -19.86% | 95 | 次级对照；验证收益为正但Sharpe未达1 |
| EMA200_1d | 424.50% | -5.21% | 0.049 | -26.47% | 26 | 2025不支持此参数版本；不否定该策略思想 |
| EMA20_60_4h | 583.30% | -5.75% | -0.033 | -26.32% | 59 | 2025不支持此参数版本；不否定该策略思想 |
| EMA20_60_1d | 账本失败 | 1.07% | 0.213 | -22.33% | 10 | 账本失败；不作收益筛选结论 |
| MACD_4h | 138.40% | -4.82% | 0.104 | -37.06% | 244 | 2025不支持此参数版本；不否定该策略思想 |
| MACD_1d | 397.32% | -39.18% | -1.127 | -43.49% | 51 | 2025不支持此参数版本；不否定该策略思想 |
| MACD_EMA200_4h | 153.43% | 14.96% | 0.706 | -19.11% | 155 | 次级对照；验证收益为正但Sharpe未达1 |
| MACD_EMA200_1d | 311.34% | -22.52% | -0.830 | -33.62% | 44 | 2025不支持此参数版本；不否定该策略思想 |
| DONCHIAN55_20_4h | 246.93% | 8.16% | 0.433 | -21.69% | 41 | 未达冻结筛选标准；保留比较 |
| DONCHIAN55_20_1d | 508.59% | -1.63% | 0.070 | -15.49% | 8 | 2025不支持此参数版本；不否定该策略思想 |
| BB120_EMA200_ATR3_4h | 76.32% | 16.81% | 1.269 | -7.62% | 19 | 优先候选；`LOW_SAMPLE`（验证19笔），进一步研究 |
| BB120_EMA200_ATR3_1d | 127.65% | -9.04% | -0.693 | -16.35% | 6 | 2025不支持此参数版本；不否定该策略思想 |


三项训练账户触发 `NO_BORROW_FAIL`：`EMA20_60_1d`、`BTC_98_BH`、`CORE3_98_BH`。协议规定 funding 支出导致钱包不为正时停止账户并不报告故障后的指标。这是观察到的 funding 支出令钱包触及非正值后的冻结现金账本约束失败，不代表保证金清算结论，也不等同于已经证明策略价格回报为负。训练期两个买入持有基准因此没有可用训练对照；不能据此计算训练期相对基准表现。

## 验证段、基准与候选解释

2025 复用验证中，BTC 98% 买入持有净收益为 `-12.01%`，Core3 等权 98% 为 `-20.54%`。按冻结的预筛标准（训练与验证净收益均正、验证 Sharpe ≥1），满足数为 `1`：`BB120_EMA200_ATR3_4h`。`BB120_EMA200_ATR3_4h` 的验证收益 `16.81%`、日 Sharpe `1.269`、小时回撤 `-7.62%`，但只有 19 笔验证交易，标记 `LOW_SAMPLE`。它只是进一步研究候选，不构成有效性或可交易结论。

该 BB 4h 候选的 19 笔交易按币种净贡献：BTC `485.88`、ETH `18062.77`、SOL `-1734.83` USDT。正收益交易的利润中，最大一笔占 `34.5%`，前三笔合计占 `81.2%`；扣除最大盈利交易后总净 PnL 为 `7117.39` USDT。该结果主要由 ETH 贡献，不能称为跨币稳定。

BB 4h 状态诊断也不是预测器。复用验证的 ON 条件未来 72h 均值：BTC +0.2625%、ETH +0.6582%、SOL -0.3537%；ON 行的上涨比例依次为 52.13%、48.69%、44.86%，对照全样本同日期 base rate 为 51.29%、50.28%、48.71%。168h 均值依次为 +0.1935%、+1.0246%、-0.6574%。这些是重叠窗口描述统计，没有显著性检验；ON 表示指标状态，并不表示止损后仍实际持仓。`HAC alpha` 未运行。

## 补充日历月 NAV 检查

月收益按每日日末 NAV 取月末值计算；首月从该段 100,000 USDT 初始锚点计算。这里列出候选 BB 4h、EMA200 4h 和验证基准的最差月，详情可从小时 NAV 重算。

| 账户 | 区间 | 最差月收益 | 月份 |
| :--- | :--- | ---: | :--- |
| BB120_EMA200_ATR3_4h | train | -9.46% | 2020-11 |
| EMA200_4h | train | -7.13% | 2021-05 |
| BTC_98_BH | train | N/A | None |
| CORE3_98_BH | train | N/A | None |
| BB120_EMA200_ATR3_4h | validation | -1.62% | 2025-12 |
| EMA200_4h | validation | -8.56% | 2025-06 |
| BTC_98_BH | validation | -18.40% | 2025-11 |
| CORE3_98_BH | validation | -28.55% | 2025-02 |


## 口径与未运行项目

`realized_price_pnl` 依据成交价计算；成交价已包含两边不利滑点，费用和 funding 另列。单独列出的 `slippage_cost` 是披露项，不应从净收益再次扣减。每笔最差净收益从冻结成交账本直接取最小 `net_pnl`；逐策略报告中的 MAE/MFE 标为未计算，因为没有计算交易内路径极值。

策略来源说明见 `SOURCE_AND_DATA_PREFLIGHT_20261003.md` (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/longcycle_trend_catalog_v1/SOURCE_AND_DATA_PREFLIGHT_20261003.md`)：EMA20/60 与 BB120/EMA200/ATR3 参考已有研究实现，但这里是固定规则的永续长仓/现金改编，不是 P19 精确复制；P19 的 EMA200 仓位缩放、样本标准差和止损时钟等行为并未复现。机器学习信号与资产轮动没有评估。`HAC alpha` 未运行。

本次只运行了 42 项聚焦的合成时钟/动作等价与账本测试（42 passed）。未运行全仓库 pytest，也未运行导入/库存/报告全流程，避免扩大到批准数值窗以外；不声称全套测试通过。

## 数据边界、账本与结论限制

冻结加载器对所有源读取都设置 `2026-01-01T00:00:00Z` 的排他上界；本批次 receipt 的 `cal_or_2026_numeric_values_used` 为 `false`。输出 NAV 最后时间为 `2025-12-31 23:59:59.999 UTC`，成交最后出场时间也不晚于该时刻。资金账本最大绝对对账残差为 `1.01e-8 USDT`。`entry_rejections.csv` 为空（2 字节换行文件）。

十二份逐策略报告保留 `UNVERIFIED` verdict。严格 Futures/mark readiness、未触碰样本外、容量与价差、杠杆清算压力、前向干跑和真实执行观察等门槛没有通过证据；本研究不做实盘或杠杆结论。完整小时 NAV、交易/账户事件账本、费用与 funding 明细、预测诊断分别见该目录下 CSV/JSON。
