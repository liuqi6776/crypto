> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# BTC 资金费切换研究：第一轮结果

2026-10-21 UTC。**事件预测：本轮未显示两个方向的稳定增益；真实净年化：不可判断，未运行完整交易账本。** 已完成冻结范围内一轮离线研究及独立重现，停止等待下一决策。

关键结果：2024–2025，逻辑回归漏掉全部 **132 次正转负**；负转正命中 **122/132 次（召回率 92.42%）**，但伴随 **68 次误报**，precision 为 **64.21%**。不能只引用 92.42%：“一直预测正”基线对负转正本来就有 100% 召回率。候选下一期整体符号准确率 90.38%，也未解决最需要提前躲开的首次转负。

本结论只适用于这一币种、特征、阈值和复用历史；不证明所有资金费切换都不可预测，也不证明同币 carry 本身亏损。历史交易所指示/预测费率未被评估，因为没有原始事前快照。

## 数据与本轮冻结内容

主输入为 BTCUSDT 原始最终资金费结算，7377 条，2020-01-01 至 2026-09-24 16:00 UTC；原始 calc 时钟保留毫秒偏移，名义 8h 网格无缺口/重复，零费率为 0。SHA256：`aa19d4b812a386d881f5e368ed44afe4805b3f8128079acad81d52493008b41b`。

|样本|结算数|正费率数|正费率占比|正转负|负转正|
|---|---:|---:|---:|---:|---:|
|全输入 2020–2026/9/24|7377|6345|86.01%|见年度清单|见年度清单|
|2023 描述验证|1095|984|89.86%|68|68|
|2024 复用历史评价|1098|1006|91.62%|48|48|
|2025 复用历史评价|1095|954|87.12%|84|84|
|2024–2025 合并|2193|1960|89.38%|132|132|
|2026 至 9/24，仅清点|801|592|73.91%|71|71|

2026 没有预测行；正费率占比不能固定为 90%。模型训练目标为 2020–2022，21 期暖机及训练边界 purge 后 3266 行，实际目标范围 2020-01-08 00:00 至 2022-12-31 08:00 UTC。2023 只作描述验证，不调参、不重训。2024–2026 在旧研究中已经使用，本轮不称未触碰 OOS。

协议先冻结，再产生预测输出：仅 BTC；前一期状态持久、一直正、`sign(2r_i-r_{i-1})` 三基线；唯一候选为 C=1、阈值 0.5 的逻辑回归，五特征为最近三期最终费率、最近 21 期费率均值与负费率占比。缩放器只在训练样本拟合，无扫币、调参或收益筛选。精确参数见 [config.json](btc_funding_switch_study/config.json)，定义及修正记录见 PROTOCOL.md (`provenance:nonincluded/research-runs/2026-10-21/task-3/btc_funding_switch_study/PROTOCOL.md`)。

## 事件和时钟

在上一名义结算后 1h 决策，预测下一名义 8h 结算，标称提前 7h。**上一最终值和下一结算计划届时已知是研究假设，不是已验证的历史可得性。** calc 字段不是 received/published，真实上线的预警提前量不可判断。

只把相邻结算的严格正→负、负→正计为切换；0 独立并打断事件链，缺失不补值。当前非零、目标为 0 时没有切换，但已发反向告警仍算误报。匹配容忍窗口为 0，只能命中指定下一结算；每个目标在同一模型/方向/报告期仅计一次。全评价期无零、缺口、时钟排除或暖机排除，两方向全部 132 次事件均可评估。

每一方向的机会数是当时状态属于该方向的决策数：合并正转负 1960 次机会，负转正 233 次。算法输出 3288 个唯一预测目标（含 2023 验证）；event_matches.csv (`provenance:nonincluded/research-runs/2026-10-21/task-3/btc_funding_switch_study/event_matches.csv`) 含 21924 行，因为分年/合并报告与模型分别记账，不是 21924 个独立市场机会，不能将这些报告行再合并计分。

实际原始目标 calc 减假设 decision 的范围为 7.000000–7.00000806h（2023–2025 全预测）；中位数约 7h。这只是冻结时钟与结算记录的差，不是模型自行发现的提前量，也不是实际资金费扣款/数据接收时钟。正转负候选无真阳性，所以没有其“命中提前量”。

## 主结果：2024–2025

precision=TP/(TP+FP)，recall=TP/(TP+FN)；无告警时 precision 为 N/A。每行真实事件均为 132。

|方向|方法|告警数|TP 命中|FP 误报|FN 漏报|precision|recall|F1|
|---|---|---:|---:|---:|---:|---:|---:|---:|
|正→负|状态持久|0|0|0|132|N/A|0%|0|
|正→负|一直正|0|0|0|132|N/A|0%|0|
|正→负|简单趋势|225|27|198|105|12.00%|20.45%|0.1513|
|正→负|逻辑回归|1|0|1|132|0%|0%|0|
|负→正|状态持久|0|0|0|132|N/A|0%|0|
|负→正|一直正|233|132|101|0|56.65%|100%|0.7233|
|负→正|简单趋势|34|14|20|118|41.18%|10.61%|0.1687|
|负→正|逻辑回归|190|122|68|10|64.21%|92.42%|0.7578|

候选每 100 次方向机会的误报为正→负 0.051 次、负→正 29.18 次。误报少但不发转负告警不代表成功；它漏掉了所有该方向事件。

候选分年结果保留如下，未只挑好年份：

|年/方向|真实事件|告警|TP|FP|FN|precision|recall|
|---|---:|---:|---:|---:|---:|---:|---:|
|2024 正→负|48|1|0|1|48|0%|0%|
|2025 正→负|84|0|0|0|84|N/A|0%|
|2024 负→正|48|63|43|20|5|68.25%|89.58%|
|2025 负→正|84|127|79|48|5|62.20%|94.05%|

2023 验证同样偏向正状态：正转负 68 次全部漏报；负转正命中 65/68、误报 42、漏报 3。该表现未被用于改变模型。所有基线的分年和验证期数值见 [event_metrics.csv](btc_funding_switch_study/event_metrics.csv)。

## 不确定性与冻结增益标准

使用完整日历上的 7 日循环区块 bootstrap，2000 次，固定种子 20261021；只抽已有每目标计分贡献，不在拼接处制造事件。配对比较共用同一组日期块。合并指标按 TP/FP/FN 汇总，非逐年比率的简单平均。

候选负转正 precision 的描述性 95% 区间为 **[55.50%,73.71%]**，recall 为 **[86.92%,97.44%]**。简单趋势正转负 precision 为 [7.91%,16.14%]，recall 为 [14.17%,27.91%]。所有指标的区间和不可计算重复数保留在 CSV。

|方向|候选−趋势 F1|配对 95% 区间|2024 差值|2025 差值|
|---|---:|---|---:|---:|
|正→负|−0.1513|[−0.1979,−0.1033]|−0.1626|−0.1453|
|负→正|+0.5891|[+0.4755,+0.7130]|+0.6457|+0.5565|

冻结标准要求两方向区间下界均大于 0，且两年各方向点差均非负。**联合标准不通过：`no demonstrated consistent gain`。** 不因一侧好看而换阈值或重新训练。与“一直正”相比，候选负转正少 33 次误报，但新增 10 次漏报；其 F1 高约 0.0345，仅是描述比较，未宣称有可交易经济增益。

区间只描述这段相关历史，不保证未来覆盖率。正转负候选仅有一次告警且错误，2000 次抽样中 715 次没有告警，precision 不可计算；剩余区间为 0 是重抽样退化，不是未来 precision 已被证明必为 0。训练/特征选择不确定性、市场制度改变和缺失的真实发布时间未纳入这些区间。

## 真实净年化与账本

|对照|当前状态|可报告的资金结果|
|---|---|---|
|持续同币 spot-long / 等数量 perp-short|NOT_RUN_DATA_GAP|净年化、累计净收益、最大回撤、月度收益、资金费金额均 N/A|
|按预测进出完整两腿组合|NOT_RUN_DATA_GAP|同上；不做只平空留多的方向敞口|
|不交易|仅 idle cash / 无利息的数学基线|假设收益 0%，不是实际账户收益；没有历史资本/净值路径|

[financial_ledger_status.csv](btc_funding_switch_study/financial_ledger_status.csv) 是财务缺口状态表，**不是已成交现金账本**。其中费率和仅是市场费率描述量，不能当资金费金额或资本年化。

匹配的现货/永续 4h 价格和独立 1h mark 确实存在。缺口是原生 event mark/持仓现金流、同步可执行报价/深度、历史费用/滑点及退出证据、保证金/转账/强平路径、真实信息可得时钟和完整单一账户对账。不能用 K 线冒充成交，不能把缺失成本填 0。

损益应包含 `q×(spot_exit−spot_entry)+q×(perp_entry−perp_exit)+Σ(q×event_mark×rate)−全部成本`；资本分母应含现货实付、永续单独保证金及流动性缓冲。基差已体现在双腿价格损益，不重复加计；同一现金不能重复用于两腿。无借币正向 carry 的借币费为不适用；强平、单腿失败、平台/托管与稳定币风险未被量化，尾部压力结果为未运行。详情及旧 7.59%/10.32% 代码证据见 [数据与旧研究审计](DATA_AND_LEGACY_AUDIT_ZH.md)。

## 代码、验证与交付

- 运行代码 (`provenance:nonincluded/research-runs/2026-10-21/task-3/btc_funding_switch_study/run_study.py`)、[固定配置](btc_funding_switch_study/config.json)、协议 (`provenance:nonincluded/research-runs/2026-10-21/task-3/btc_funding_switch_study/PROTOCOL.md`)、测试 (`provenance:nonincluded/research-runs/2026-10-21/task-3/btc_funding_switch_study/test_study.py`)、使用说明 (`provenance:nonincluded/research-runs/2026-10-21/task-3/btc_funding_switch_study/README.md`)。
- 逐目标预测 (`provenance:nonincluded/research-runs/2026-10-21/task-3/btc_funding_switch_study/predictions.csv`)、真实事件目录 (`provenance:nonincluded/research-runs/2026-10-21/task-3/btc_funding_switch_study/true_events.csv`)、[事件指标](btc_funding_switch_study/event_metrics.csv)、逐行计分 (`provenance:nonincluded/research-runs/2026-10-21/task-3/btc_funding_switch_study/event_matches.csv`)、[配对比较](btc_funding_switch_study/paired_comparisons.csv)。真实事件目录含 2020–2025 共 825 个事件；2024/2025 主评价为其中 264 个。
- 年度数据清单 (`provenance:nonincluded/research-runs/2026-10-21/task-3/btc_funding_switch_study/data_inventory.csv`)、详细清单 (`provenance:nonincluded/research-runs/2026-10-21/task-3/btc_funding_switch_study/data_inventory.json`)、[运行摘要](btc_funding_switch_study/run_summary.json)、来源和模型参数 manifest (`provenance:nonincluded/research-runs/2026-10-21/task-3/btc_funding_switch_study/run_manifest.json`)。
- 审查记录 (`provenance:nonincluded/research-runs/2026-10-21/task-3/REVIEW_NOTES_ZH.md`)、[门禁状态](VALIDATION_GATES_ZH.md)。

主代理独立运行 **12 项测试全部通过**；另在干净 `independent_replay/` 目录完整运行，9/9 个数据结果 hash 与实现者输出一致，缩放器/系数一致。另直接从原始资金费重算五特征、预测概率及全部 32 行事件指标，检查 3288 个唯一目标、所有计分账本、实际提前量和财务缺项，均通过。首版计量问题及干净输出目录问题已修正，未改变模型/阈值或挑选评价结果。

在 `<SOURCE_ROOT:research-runs>/2026-10-21/task-3` 运行：

```powershell
& '<SOURCE_ROOT:crypto-leverage>/.venv/Scripts/python.exe' -B -X utf8 -m pytest -q -p no:cacheprovider btc_funding_switch_study\test_study.py
& '<SOURCE_ROOT:crypto-leverage>/.venv/Scripts/python.exe' -B -X utf8 btc_funding_switch_study\run_study.py --output-dir reproduction
```

现成环境：Python 3.12.11、numpy 2.2.6、pandas 2.2.3、scikit-learn 1.7.2、pyarrow 21.0.0、pytest 8.4.2。无需安装。输入 hash 不符会拒绝运行。最终脚本 SHA256 `615f80e2fa10581bfddcb3823aea083e64ce737f0d18a83b5614cc87e9c45343`。

剩余阻塞是数据与完整双腿账本证据缺口，状态 `NOT_RUN_DATA_GAP`，不是已运行策略失败或当前计算掉线。测试曾因 Python 默认临时目录落在获准区域以外而遭写入/清理拒绝；没有重试该路径，改用获准 task-3 临时目录后测试通过，详情见审查记录。当前没有待批准的执行动作。此前被拒的 collector 安装与特定目录没有重试、改权限或绕过。没有原项目写入、实盘、账户/密钥访问、数据下载、付费、服务或长期采集。本轮已停止；是否另行冻结低保真双腿模拟，或补充真正事前证据，由下一步决策确定，不自动展开。
