> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# TradingView 固定指标诊断 v1 — 完整历史矩阵报告

**结论：在预注册筛选规则下，本次固定实现没有显示稳定的增量历史收益。** 10 个非 EMA 信号/模式（包括作为 VWMA20 对照的 SMA20）的 20 个延迟筛选均为 `SCREEN_NOT_MET`；其中每个币种均有足够的完整回合数，失败不是由样本数门槛造成。EMA200 是共同参照线。结论仅限这六个固定信号的实现，不外推到未测试的截图指标。本文没有“有效”或“可交易”的结论。

## 范围、复现与审计状态

回放共 192 个独立币种/策略/基准×成本×延迟账户、144 个固定对照比较和 64 个三币组合案例。账户路径中 184 个完成；8 个提前触及预注册 gross/NAV 风险停止（固定数量 perpetual buy-and-hold 的 ETH/SOL 前缀），这些路径不作为完整收益排名。组合中 60 个三币路径完整，其余只报不完整状态。原始 run 状态为 `COMPLETED`，时间 `2026-10-18T08:42:58.323331+00:00` 至 `2026-10-18T08:53:40.121655+00:00`。

- 冻结运行 ID：`20261018T084258.320332Z_8286080dfaa0`；授权锁 SHA256：`8286080dfaa02d7e04b22af0e3b5dd5eae21f4d7fabe32a48444033cf640183c`。
- 命令：`.venv\Scripts\python.exe scripts\tradingview_fixed_diagnostic_20261018_v1.py --approved-lock reports\strategy_validation\tradingview_fixed_diagnostic_20261018_v1\freeze\approved_v1\approved_numeric_replay_lock_v1.json --lock-sha256 8286080dfaa02d7e04b22af0e3b5dd5eae21f4d7fabe32a48444033cf640183c`。
- 冻结代码 SHA256：`26df0fcb40d747e5e50a4eb1f9c9796dfa8bac840b600057e59eaa05bfba635d`；配置 SHA256：`1255e4b6a9ea434378f68f080ae4c345c87fad2821e0b4e19202f48825dbd7a4`；协议 SHA256：`3388d34c6d0a726eedaaaa72d6f98611fda0a0b5087f35f95648e044734eed85`；源预检 SHA256：`542bc98d2285d11ca35b386626fe20fc090ee2f03326fe3f2a8ed221a26a321c`。
- 完成回放概要：`reports/strategy_validation/tradingview_fixed_diagnostic_20261018_v1/runs/20261018T084258.320332Z_8286080dfaa0/account_results.json`。完整逐账户决策/成交/资金费/终端事件账本、192 个账户净值/归因路径和每个输出的 SHA256 均由该目录 `run_manifest.json` 绑定。
- 数据输入是本地已核验 BTC/ETH/SOL 交易、mark 与 funding 文件；原生时间戳、资金费事件和来源 SHA 在 run manifest 及结果表保留。SOL 实际预热从 2020-09-14 07:00 UTC 起，使用 652 根真实完整 4h 预热 bar；没有补造早期行情。
- **独立保存结果账务审计状态 `PASS_ARITHMETIC_NOT_STRATEGY_VALIDATION`（算术核对，不是策略验证通过）；审计文件 `reports\strategy_validation\tradingview_fixed_diagnostic_20261018_v1\review\root_independent_audit_v1.json`。** 审计覆盖 192 个账户与 64 个组合的已保存 NAV 账务；信号方向未独立重建，成交与资金费名义标价仍是代理值。根代理的四项独立合成手算校验通过，20 项聚焦测试通过；完整项目测试为 4,571 通过、20 失败、1 跳过；定向复查后，13 项环境/并发影响项通过，7 项共享历史身份检查仍失败。完整项目不能报告为通过，详见 测试结论 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/tradingview_fixed_diagnostic_20261018_v1/review/TEST_OUTCOME.md`)。

研究范围：Binance USDT 永续 BTC/ETH/SOL，原生 H1 完整 bar 聚合成已完成 H4 信号；统计期为 2021–2025 五个完整日历年，使用真实可用预热。每次 H4 决策目标为当时 NAV 的 40%；每边模型手续费 0.05%，基础/压力滑点分别为 0.05%/0.15%。这些成本和下一 H1 开盘成交价是模型假设，不是实际执行记录。

## 冻结规则下的结果

每个候选必须由同一至少两个币种，在基础和压力费用下均净收益为正，超过直接主基线净收益、主基线持仓小时匹配控制及共同 EMA200 持仓小时匹配控制，候选回撤不高于两个匹配控制，并在两种成本下均有至少 20 个完整 sign episode。VWMA20 的直接与主匹配基线为 SMA20，同时另与 EMA200 比较。通过者分类为“有历史增益”；样本不足为“证据不足”；本次 10 个候选的样本门槛都满足，但增量条件未同时成立，故均为“未见增益”。

| 信号 | 模式 | 延迟 | 基础费正收益币数 | 压力费正收益币数 | 冻结筛选 |
| :--- | :--- | :--- | :---: | :---: | :--- |
| DMI14_ADX25 | long_cash | primary | 3/3 | 3/3 | SCREEN_NOT_MET |
| DMI14_ADX25 | long_cash | extra_1h | 3/3 | 2/3 | SCREEN_NOT_MET |
| DMI14_ADX25 | long_short | primary | 1/3 | 0/3 | SCREEN_NOT_MET |
| DMI14_ADX25 | long_short | extra_1h | 0/3 | 0/3 | SCREEN_NOT_MET |
| EMA200_ADX25 | long_cash | primary | 3/3 | 3/3 | SCREEN_NOT_MET |
| EMA200_ADX25 | long_cash | extra_1h | 3/3 | 3/3 | SCREEN_NOT_MET |
| EMA200_ADX25 | long_short | primary | 2/3 | 2/3 | SCREEN_NOT_MET |
| EMA200_ADX25 | long_short | extra_1h | 3/3 | 1/3 | SCREEN_NOT_MET |
| SMA20 | long_cash | primary | 2/3 | 1/3 | SCREEN_NOT_MET |
| SMA20 | long_cash | extra_1h | 2/3 | 1/3 | SCREEN_NOT_MET |
| SMA20 | long_short | primary | 0/3 | 0/3 | SCREEN_NOT_MET |
| SMA20 | long_short | extra_1h | 1/3 | 0/3 | SCREEN_NOT_MET |
| VWMA20 | long_cash | primary | 2/3 | 1/3 | SCREEN_NOT_MET |
| VWMA20 | long_cash | extra_1h | 2/3 | 1/3 | SCREEN_NOT_MET |
| VWMA20 | long_short | primary | 0/3 | 0/3 | SCREEN_NOT_MET |
| VWMA20 | long_short | extra_1h | 0/3 | 0/3 | SCREEN_NOT_MET |
| EMA200_VOL15 | long_cash | primary | 2/3 | 0/3 | SCREEN_NOT_MET |
| EMA200_VOL15 | long_cash | extra_1h | 1/3 | 1/3 | SCREEN_NOT_MET |
| EMA200_VOL15 | long_short | primary | 0/3 | 0/3 | SCREEN_NOT_MET |
| EMA200_VOL15 | long_short | extra_1h | 1/3 | 0/3 | SCREEN_NOT_MET |

候选与 EMA200 参考信号臂共 144 个已完成账户情景中有 74 个净收益为正；8 个风险停止账户属于固定数量 buy-and-hold 基准，不计入此计数，也不把其前缀收益当完整期收益。这不等于增量收益。特别是 long-cash DMI 与 EMA200-ADX 在若干币种/成本情景中正收益，但没有任何候选臂满足所有 baseline、暴露匹配、回撤和跨成本同币筛选。long-short 的 SMA20、VWMA20、成交量过滤 EMA200 多为负收益；long-short DMI 在压力费用下三币均为负。`accounts_192.csv` 保留所有赢亏、风险前缀、回合数、turnover、reference PnL、fee、slippage、funding、净值、gross/NAV 与基线差异。`annuals.csv` 和 `monthly_accounts.csv` 报告每个完整/部分账户及已完成组合的逐年逐月数据。

CSV 中 `dd_5pct`、`dd_10pct`、`dd_20pct` 为是否超过该回撤上限的诊断布尔值；`true` 表示超过上限，不表示通过。年度收益是逐年 NAV 计算；标题/概述中的策略累计收益是 2021–2025 全期间累计值，不是年化值或年收益之和。

参考臂 EMA200 long-cash/base/primary 的 BTC、ETH、SOL 五年累计收益分别为 64.76%、140.28%、907.73%；等初始资本三 sleeve 聚合中 SOL 贡献约 81.6% 的绝对净利润。它是三条独立 10,000 USDT 路径的时间对齐平均 NAV，不是重平衡币种权重的组合；集中度和已检查全样本意味着聚合高收益不能视为稳定期望回报。

主延迟 EMA200 三币聚合在基础/压力成本下累计收益为 370.92% / 303.64%，最大回撤为 31.31% / 33.93%。EMA200_ADX25 将组合最大回撤降至 23.26% / 24.60%，但累计收益也降至 103.96% / 76.51%，且未通过预注册增量筛选。EMA200_VOL15 组合收益为 6.89% / -35.71%；较低的基础成本回撤伴随压力成本亏损。诊断性 5%/10%/20% 回撤阈值并非经用户认可的实盘风险限额；盈利的 long-cash 趋势与 ADX 组合均超过 20% 回撤。

根代理事先声明的附加美元暴露小时匹配已纳入独立审计 JSON 和 `matched_attribution_144.csv`，按多头与空头分别缩放 EMA200 参考路径，以匹配候选实际美元暴露时长。它是使用全样本结果计算的事后静态尺度描述，不是可执行组合，也不等同波动率或尾部风险匹配；细微浮点误差不解释为自我基线劣化。原 primary screen 匹配的是方向持仓小时，不是 dollar-hours。不得把任一控制解释成可执行 alpha。

## 组合、费用与延迟

组合只在三个币种都完成的路径上汇总，以三个独立 10,000 USDT sleeve 的时间对齐 NAV 求和再除以 3，绝不平均回撤。64 个组合案例覆盖 16 个策略/基准标签、两档成本和两种延迟；60 个完整、4 个包含风险停止 buy-and-hold sleeve 的组合不可排名。192 个账户中 184 个完成、8 个固定数量 buy-and-hold 账户触发预设 gross/NAV 风险停止，停止时 NAV 仍为正，不代表发生强平。Perpetual fixed-quantity `BUY_HOLD_FIXED_INITIAL_QTY_40PCT_NAV` 不是现货 buy-and-hold；40% NAV 每 4h 重平衡的 constant-long 另列为不同基准。基础和压力滑点对每一边分别收费；涨费前的正 gross 历史表现不能替代成本压力结果。

延迟压力案例将成交再推迟一个 H1；完整结果列在每账户 CSV 和 144 条比较表中。该样本在此前研究中已被查看，不是未触碰 OOS，不能据此作无偏绩效判断。年度收益按 NAV 边界计算；完成账户的 2025 最终 cash NAV 仅在 2026-01-01 日历边界用于年度标注，不使用边界外价格。风险停止前缀没有后续年份，也没有终端 cash carry。

## 截图与执行限制

SOLUSD 截图的 venue/timeframe 未知，本研究不是精确 TradingView 复刻。截图提及的其他 EMA/SMA 周期、Hull、Ichimoku、RSI、Stochastic、CCI、MACD、AO、Momentum、Williams %R、BBP、Ultimate Oscillator 和 pivots 均为 `NOT_RUN`；VWMA 截图位为空。六组研究是独立状态信号，没有测试 Bollinger Bands overlay 的增益。研究没有实际 spot buy-and-hold 数据。

策略输入采用已注册 mark candle 的真实观察作为资金费名义敞口代理；其与交易所实际结算名义价格是否一致仍未知。成交模型只用严格滞后 H1 trade open 和设定费用/滑点，没有 order-book、真实 maker/taker、部分成交或实际账户填单证据。没有保证金/盘中强平路径、容量或实盘流程；所有九道策略验证门仍按逐臂报告标为 `NOT_RUN` 或 `BLOCKED`，没有一项是交易就绪通过。

## 可复核文件

- 192 个账户/基准案例 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/tradingview_fixed_diagnostic_20261018_v1/derived_v1/accounts_192.csv`)
- 64 个组合案例 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/tradingview_fixed_diagnostic_20261018_v1/derived_v1/portfolios_64.csv`)
- 逐年 NAV/回报 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/tradingview_fixed_diagnostic_20261018_v1/derived_v1/annuals.csv`)
- 逐月账户回报 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/tradingview_fixed_diagnostic_20261018_v1/derived_v1/monthly_accounts.csv`)
- 144 个 primary 与 EMA200 持仓小时匹配对照 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/tradingview_fixed_diagnostic_20261018_v1/derived_v1/matched_attribution_144.csv`)
- 24 条冻结规则 screen (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/tradingview_fixed_diagnostic_20261018_v1/derived_v1/frozen_screen_24.csv`)
- 每策略九门报告：`*_validation.md`（12 份）；独立历史审计：PASS_ARITHMETIC_NOT_STRATEGY_VALIDATION
