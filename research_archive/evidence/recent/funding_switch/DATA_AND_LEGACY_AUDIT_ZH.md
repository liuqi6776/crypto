> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 本轮输入与旧结论复核

2026-10-21 UTC，只读核验；本文件与本轮实验不修改 `crypto`、`crypto-leverage`、原审计任务或人工回放任务。

后续收到并核对原审计最终交接：`<SOURCE_ROOT:research-runs>/2026-10-21/task/carry_short_round2_20261021/CARRY_HANDOFF_ZH.md`，SHA256 `9d9de20f6deafe60639e8dd6a681739e6ea96dd7c4d47105bbb58f00baffd5a9`。旧会话没有运行新市场预测；其原型和代理所报合成测试不是本轮证据。原会话明确拒绝过的非 carry 子目录未访问或重试；本轮只读明确 carry 路径。

## 实际可用输入

|输入|完整路径|覆盖及核验|
|---|---|---|
|BTC 原始最终结算|`<SOURCE_ROOT:crypto-leverage>/source_data/staging/core4_p0_20260925/funding/BTCUSDT_funding_events.parquet`|7377 行；2020-01-01 00:00 至 2026-09-24 16:00 UTC；名义 8h 连续，无重复/空费率/零值|
|BTC 现货成交 K 线|`<SOURCE_ROOT:crypto-source>/data/spot/BTCUSDT_4h_2020_2026.parquet`|13571 行；2020-08-11 00:00 至 2026-10-20 16:00 UTC|
|BTC 永续成交 K 线|`<SOURCE_ROOT:crypto-source>/data/futures_reference/BTCUSDT_4h_2020_2026.parquet`|与现货索引完全匹配；两者 4h 无缺口/重复，OHLCV 和 qvol 无空|
|BTC 独立标记价 K 线|`<SOURCE_ROOT:crypto-leverage>/user_data/data/binance/futures/BTC_USDT_USDT-1h-mark.feather`|59016 行；2020-01-01 至 2026-09-24 23:00 UTC；SHA256 与 mark registry 一致|

SHA256（按表顺序）：

1. `aa19d4b812a386d881f5e368ed44afe4805b3f8128079acad81d52493008b41b`
2. `feea2dbda9e866451715ef77d5ac79d055b995d40cd9a3cfc3bb5479c4bd2ff4`
3. `508215633a3f2b85f1bfc7b4ca20510c555523a0e0af8872e9651352b1db9f20`
4. `ee6e0c0a0f8caa7889d3639cde5475e11d1fbc2ba384409b888dc2142f0b9512`

现货/永续标签由 `crypto\crypto_quant\data\catalog.py` 明确分开；不使用根目录同名混合来源文件。mark 注册依据 `crypto-leverage\archive\catalog\mark_candle_registry.json`。mark 的 volume 为供应商原始零字段，不代表交易量或可成交深度。

资金费字段：`symbol, calc_time_utc, last_funding_rate, funding_interval_hours, calc_time, nominal_settlement_utc, nominal_settlement_ms, calc_offset_ms, source_file_sha256`。它不包含历史预测/指示费率、实际 published/received 时点或 `markPrice`。原始 calc 相对名义时点偏移 0–47ms，3304 行为正；名义时钟仅为对应结算标识，不覆写原始 calc。原审计草稿的 `calc<=nominal` 校验会误拒，未复用该条件。

本轮模型只读第一项。其余用于判断财务可行性，不进入模型，不挑币，不重跑旧研究。ETH 的一次只读清点未用于选币或参数：同覆盖 7377 行，正 6359/负 1018/零 0；本轮仍只有 BTC。

## 正费率占比实测

全样本正 6345/7377＝86.0106%，负 1032/7377＝13.9894%。2024 正 1006/1098＝91.62%，2025 正 954/1095＝87.12%，2026 截至 9/24 正 592/801＝73.91%。2026 仅数据清点，不进入模型评估。比例随时期变化，“多数正”不是固定 90% 的事实保证。

## 旧研究的直接证据

路径前缀 C=`<REDACTED_PRIVATE_PATH> UTF-8 文件的物理行号；本轮不将旧测试数当作新验证。

|旧结论|证据与复核|
|---|---|
|7.59% 年化|`C\leverage_research\summary_data\liquidation_hunter_vs_funding_arb_summary.csv:3` 确有该数；对应脚本 `liquidation_hunter_vs_funding_arb.py:253–275` 只做资金费资本更新，267–275 用该期最终 rate 条件 `>=-0.0001` 才入账，未模拟为避费退出/重入。缺两腿基差损益、完整保证金/缓冲及进出成本。|
|10.32% 年化|`C\leverage_research\summary_data\core_satellite_benchmark_summary.csv:3`；`core_satellite_hybrid_backtest.py:175–185` 固定 `i%96` 代理结算并事后过滤，192–194 无成本重设名义仓位。|
|10/17 CARRY_EQ/BETA|`L\reports\strategy_validation\funding_carry_net_economics_v1_20261017\REPORT_CN.md:49` 明确多空为不同币；协议 `L\docs\FUNDING_CARRY_NET_ECONOMICS_V1_20261017.md:25–30` 为 Q1 低费组多、Q5 高费组空，每端至少 10 币。不是同币现货/永续。|
|10/17 报告自身的限制|上述报告 88 行已说明全年累计、CAGR、年度 Sharpe、完整账户最大回撤不可得，113 行为 UNVERIFIED。已知周的跨币净损益不能否证或证明本策略。|
|同币可行性|`L\docs\CONDITIONAL_CARRY_LOCAL_FEASIBILITY_20261017.md:3,33–37,47–53` 已说明局部数据基础和执行/成本/event mark/OOS/资本分母缺口。|

不能扩大指控：7.59% 脚本 65–72 行虽有 `fillna(0.0001)`，carry 循环 260/267 行却取原始 `df_fr_valid`，所以不宣称其 carry 资金费全部由填值制造。

源约束适用于判断结论：`crypto\AGENTS.md` 及 `docs\CRYPTO_QUANT_FRAMEWORK_V1.md`；`crypto-leverage\AGENTS.md`、`docs\RESEARCH_INTEGRITY.md`、`docs\MIGRATION_AND_LIMITATIONS.md` 与 `.agents\skills\strategy-validation-gates\SKILL.md`。本轮是用户授权的独立统计诊断，不伪装成 canonical runner 的收益回测。旧文档中“所有 mark 缺失”的摘要已过时，实际 1h mark 存在。

## 真实净 carry 为何仍不可计算

固定数量 q 的同币现货多、线性永续空：

`毛损益 = q×(S_exit−S_entry) + q×(F_entry−F_exit) + Σ(q×event_mark×rate)`

即 `q×(basis_entry−basis_exit) + funding_cashflow`，其中 basis=F−S。手续费、价差、滑点、两腿退出成本、再平衡及转账/融资费用另扣。无借币的正向 carry 的借币成本是“不适用”，不是缺数据时默认 0。入场/退出必须同时处理两腿，不能只平空保留现货并把方向收益算作 carry。

`总初始资本 = 现货实付本金 + 永续单独保证金 + 流动性缓冲 + 初始费用准备`。同一资金不能同时计作两账户可用资金；组合多币须在总现金账本分配，不能复用单币资本。未冻结数值杠杆或资本比例，也未为提高年化缩小分母。

|缺口|影响|
|---|---|
|最终值首次可见时点和历史指示/预测费率快照|不能称真实 PIT 或可实际提前 7h 的验证；本轮只能作“1h 内已获上一最终值”的条件研究|
|原生结算 mark/持仓现金流|rate 不能直接换算资金费金额；1h mark OHLC 不能恢复毫秒级实际结算 mark|
|同步双腿可执行报价/深度、成交、历史费用、容量与退出证据|4h K 线可支持另行冻结的低保真模拟，但不是本次真实净收益；不拿未知成本填 0|
|历史保证金规则、资金转移/抵押/缓冲、强平与 ADL 路径|价格对冲不证明空腿随时有足够保证金；不能认定无强平风险|
|完整单一权益/现金/仓位账本|无法计算样本累计净收益、净资本年化、最大回撤、月度收益和尾部损失|

财务输出因此为 `NOT_RUN_DATA_GAP` / `不可判断`。缺的是上述已审计文件未能提供的证据，不声称全机器绝无其他数据；也不将“未运行”写成策略失败。市场/平台故障、提现冻结、稳定币与托管风险没有本地概率模型；仅列为未量化尾部风险，不捏造损失率。

执行框架也不能冒充已经具备：只读核查 `crypto\crypto_quant\framework\engine.py:72–74` 和 `models.py:170–176`，当前 canonical engine 明确拒绝 perpetual 类型。独立目录中的事件统计不调用该收益执行器；本轮没有绕过其门禁输出双腿财务结果。

当前官方说明仅用于机制交叉核验：[Binance Funding Rates](https://www.binance.com/en/support/faq/detail/360033525031) 定义资金费为标记名义金额乘 rate，持仓结算时点及指示值与最终值有区别；[Binance 同币套利说明](https://www.binance.com/en/support/faq/detail/2c65b90111e14be6b0156d32e0ff94d9) 说明现货多与永续空配对。页面于本轮只读核验，不代表历史 2024/2025 费率表、规则或实际成交证据。
