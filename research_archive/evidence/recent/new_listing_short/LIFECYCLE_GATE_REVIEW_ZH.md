> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 新上市永续币池：生命周期门的有界遗漏复核

复核日期：2026-10-21。任务状态：**已完成；严格14–120日新上市永续每日7日涨幅诊断 NOT_RUN_DATA_GATES**。用户已授权继续研究；没有取消、没有等待授权，也不是新策略收益检验失败。本轮没有计算任何收益、IC、排序或仓位。

## 判断

在限定的既有入口中，没有找到足以定义任一历史区间内完整可做空新上市永续横截面的、带当时可得时间的生命周期证据。

这次并非只复述旧“数据不足”：找到了现成的逐合约公告字段并核查其范围。公告冻结表有146个token行，其中17条不同的perp条款，覆盖17个合约；7条明确继续交易，10条禁止新开并结算，**没有首次上市或重新上市动作**。条款有操作生效UTC，却只有网页显示的发布时间，来源回执明确该显示时钟时区未认证、当前网页版本可能被修改。更关键的是来源是按现货退市/Monitoring事件检索的样本，主动排除了futures-only退市，没有完整上市事件普查。因此不能从“这17条没有其他问题”推出剩余币或其他日期可以开空。

现有迁移/上市个案和AERGO重新上市发现可帮助核对具体币，但事后只挑这些有资料的币，研究对象会变成“资料恰好完备的被挑中合约”，无法代表事前完整新上市池，会造成覆盖和选择偏差。不以此降级冒充严格新上市横截面实验。

## 范围与已完成操作

复用了前轮独立报告：

`<SOURCE_ROOT:research-runs>/2026-10-21/task/carry_short_round2_20261021/SHORT_EXISTING_AUDIT_ZH.md`

源根记为 `L = <REDACTED_PRIVATE_PATH> `-B -X utf8`；只统计元数据记录/字段/动作，不导入研究runner、不读取新增价格标签。

检查的浅层目录：

- `L\docs`：仅文件名筛选noncore/listing/lifecycle，随后读已有相关协议与身份说明。
- `L\research_data\noncore_event_sources_20261014`：直接3文件。
- `L\research_data\binance_noncore_ic_20261013`：直接两个universe audit文件，读修正版v2。
- `L\research_data\binance_noncore_dynamic_20261013\metadata`：直接8文件，读daily_catalog及weekly_liquidity_selection的schema/限制。
- 同动态根的 `normalized`：只列直接3个数据类别目录，没有按symbol递归。
- 既有news协议明确引用的 `reports\strategy_validation\btc_noncore_news_event_v1_20261015\source_freeze_expanded`：直接3文件；沿该manifest的确切路径读来源回执。
- 既有报告已知的AERGO生命周期发现JSON，作为定点反例；没有搜索新个案。

## 证据逐项

### 1. 已有逐合约公告条款：有局部关闭证据，没有上市普查

精确文件：

`L\reports\strategy_validation\btc_noncore_news_event_v1_20261015\source_freeze_expanded\source_catalog.csv`

本轮读取表头及146条元数据；对 `futures_contract_notices_json` 内记录按完整内容去重：17条、17个不同contract_symbol。动作计数：

| action | 条数 | 能支持什么 | 不能支持什么 |
|---|---:|---|---|
| EXPLICIT_CONTINUATION | 7 | 指定公告明说指定合约可继续 | 首次上市日、此前所有交易状态、之后永不暂停 |
| NO_NEW_POSITIONS_AND_SETTLEMENT | 10 | 指定合约的禁止新开/结算截止 | 全部退市事件覆盖、真实结算价、重上后状态 |
| 首次上市/重上 | 0 | 无 | 14–120日年龄及完整新上市集合 |

CSV字段：`batch_id,family,event_date,token,candidate_symbol,identity_status,audit_classification,audit_exclusion_reason,candidate_universe_member,published_displayed_clocks,timezone_evidence,revision_notes,reported_futures_new_position_cutoff_utc,reported_futures_settlement_or_delist_utc,reported_futures_product_scope_caveat,futures_contract_notices_json,component_urls`。

内嵌perp notice字段：`action,contract_symbol,evidence_note,new_position_cutoff_utc,notice_published_displayed,notice_url,product,scope_certainty,settlement_or_closure_utc`。

没有 `known_at,available_at,first_seen_at,received_at,listing_time,open_short_allowed_at` 字段。字段名称缺失本身不必然否定可得性，但这里的等价候选 `notice_published_displayed` 也被来源回执明确限制为未认证时区/版本，不能自动变为可靠的历史known_at。

例：ANTUSDT条款明确“USDⓈ-M可继续”；同一新闻中XMRUSD COIN-M的截止不能套到XMRUSDT/ANTUSDT。这说明product/contract精确映射是必要的，也说明现货退市公告不是perp关闭名单。

绑定manifest：

`L\reports\strategy_validation\btc_noncore_news_event_v1_20261015\source_freeze_expanded\source_freeze_manifest.json`

其中 `event_batch_count=30, token_row_count=146, unresolved_token_rows=69`，family仅DELIST、MONITOR；input_paths逐项绑定以下来源。该冻结只证明这批资料当时被保存，不证明资料在历史决策时可得，也不补齐全市场遗漏。

### 2. 来源回执明确承认样本不完整和时间版本限制

`L\reports\strategy_validation\btc_noncore_news_event_v1_20261015\review\source_receipts.json`

- schema：`binance_monitoring_tag_addition_retrieval_receipts_v1`，retrieved_on=2026-10-15。
- scope事件窗2024-01-01至2025-12-01，筛选“新增Monitoring Tag”。
- `scope.completeness = retrieved_sample_only; web search/index results do not prove archive completeness`。
- `timing_policy.timezone`明确显示Published on字段未标时区、UTC未认证；实际tag activation也没有精确时刻。

`L\reports\strategy_validation\btc_noncore_news_event_v1_20261015\review\token_delisting_source_receipts.json`

- schema：`binance_official_token_spot_delisting_source_receipts_v1`，prepared_on=2026-10-15。
- `scope.status = Bounded retrieved sample, not a complete census.`
- event_definition是代币全部现货交易对退市；明确把 **futures-only delistings、迁移、换币、更名** 排除在核心事件家族外。它不可能单独支持完整perp生命周期。
- timestamp_policy区分网页发布时间字符串与正文明确UTC的操作截止。明确：当前页面显示发布时间/编辑注记不证明特定版本何时公开；页面可能后改。
- retrieval_and_archive_limits：无已验证全分页/全日期不可变导出；搜索可遗漏页面、旧标题和本地化版本。未搜到不等于没有公告。
- 空futures条款列表只表示当前检查文字未找到或该边界记录未建立条款，**不排除另一份公告**。

`L\docs\BTC_NONCORE_NEWS_EVENT_V1_20261015.md`也明确该轮是负面新闻后做空，**不是新上市合约**。其≥120日前置观测池与14–120日目标不同；D+2延迟处理不能修复网页历史版本缺口。

### 3. noncore_event_sources是局部来源审计，不是生命周期主表

`L\research_data\noncore_event_sources_20261014`直接文件只有：

| 文件 | 类型/字段 | 局限 |
|---|---|---|
| event_source_audit.json | schema、generated_at_utc、endpoint_audit_input/hash、status_row_counts、source_findings、conclusions | source_findings里的ALPACA dated notice是单个案例；未枚举全体首次上市/失败/重上 |
| endpoint_gap_summary.csv | symbol,status,endpoint_rows,first_endpoint_utc,last_endpoint_utc,endpoint_kinds | 这些first/last是旧研究选定端点的观测范围，不是合约生命周期起止 |
| SOURCE_AUDIT.md | ALPACA结算及供应/解锁来源解释 | 结算规则已知不等于真实结算价格已知，更不等于上市名单完整 |

ALPACA source_findings包含 `publication_date=2025-04-24`、新仓截止/自动结算UTC和notice URL；temporal_use也写“subject to archived revision history”。能提供定点限制证据，但没有普查边界或完整原始版本时钟。真实结算价仍未知。

### 4. AERGO重新上市个案暴露“只存关闭”的结构缺陷

`L\reports\strategy_validation\btc_noncore_news_event_v1_20261015\review\root_post_result_lifecycle_finding.json`

字段和已记录值：

- `status=POST_RESULT_SOURCE_COVERAGE_FINDING_NOT_IN_FROZEN_SAMPLE`。
- `symbol=AERGOUSDT`。
- `old_closure_utc=2025-03-27T09:00:00Z`。
- `relaunch_displayed_publication=2025-04-16 07:47 (page timezone not independently verified)`。
- `explicit_launch_utc=2025-04-16T11:00:00Z`。
- `old_closure_notice_url,relaunch_notice_url,created_utc,finding,affected_rows`。

这比完全没有重上资料更好，但只是事后定点补充：旧freeze关闭guard未建模重上；文件明确full lifecycle与historical continuity仍未验证。不能用该一币一事件当作全池恢复证明。`explicit_launch_utc`是操作生效时间，`created_utc`是2026年审计写入时间；二者均不等于已认证的2025年known_at。14–120日年龄还必须预先区分原始合约首次上线与重新上线的新episode，不能看价格后选起点。

### 5. archive metadata的日期仍然是观测边界

`L\research_data\binance_noncore_ic_20261013\universe_audit_v2.json`

每symbol示例字段：`symbol,observed_first_open_utc,observed_last_open_utc,first_open_time_ms,last_open_time_ms,daily_archive_object_count,daily_row_count,decision,exclusion_reason`。0GUSDT首个观测2025-09-17 00:00只是归档日线开盘时间，没有perp开空生效时刻/known_at。全表source_limitations明确没有完整PIT contract-status history、underlyingType/subType history或immutable identity map。这里没有后续生命周期表的引用可以解除此门。

`L\research_data\binance_noncore_dynamic_20261013\metadata\daily_catalog.json`

顶层有captured_at_utc、listing_pages、archive_symbols/candidate_symbols、files、evidence_status等；files里有dataset_type,symbol,timeframe,key,url,checksum_url,year,month,bytes,last_modified。这里的listing_pages是**对象存储目录列表**，不是交易所上市公告；last_modified是归档对象修改时间，不是合约上市或特征可得时间。evidence_status=ARCHIVE_OBJECT_CATALOG_ONLY，eligibility_limitations明确首根K线不是精确上市日、归档不证明历史交易状态。

`L\research_data\binance_noncore_dynamic_20261013\metadata\weekly_liquidity_selection.json`

`source_coverage`只给files,rows,first_date,last_date；`exchange_info_classification_path=null`，classification_metadata_available=false，historical_asset_class_proven=false。该旧表是周一/90日前置行/top20的采集计划，**不是**v2策略120日/top60规则，更不是目标14–120日新上市池。状态EXPLORATORY_DOWNLOAD_PLANNING_ONLY。不把三个不同池混用。

`normalized`直接只有 `fundingRate,klines,markPriceKlines` 三类，没有在该入口找到instrument/lifecycle主表。未对其全体symbol展开，也不把这个有限入口的缺失扩大成“整台电脑绝对没有任何其他资料”。

### 6. 现货身份说明只补个案，不补perp历史状态

`L\docs\BTC_NONCORE_IC_SPOT_IDENTITY_SUPPLEMENT_20261013.md`记录现货exchangeInfo的2026-09-24当前快照匹配，并说明它不能证明2021–2025期货状态。当前SPOT TRADING/BREAK不能倒填历史perp。

该文也有POL、SONIC、RAYSOL、DODOX、NEIRO等上市/迁移个案及链接。它们有助于识别ticker/倍率冲突，缺少完整普查范围、每个合约全生命周期及当时版本留存；没有证据把这些个案集合定义为完整历史新上市池。本轮没有重新打开网页或读取现货源目录。

## 严格14–120日每日诊断的数据门

| 门 | 当前满足 | 缺失/结论 |
|---|---|---|
| 身份、产品与可开空instrument_id | 归档symbol、部分条款product/scope_certainty、个案迁移说明 | 完整版本化合约身份与倍率/可卖空状态未知 |
| 年龄起点 | 归档首个日开盘、少数上市/重上正文时刻 | 完整首次可开空时刻及重上episode规则缺；不能用archive age代替perp age |
| 按日可交易状态 | 17条继续/关闭条款、AERGO定点发现 | 暂停/恢复/失败/退市/重上历史不完整，未知不能默认为TRADING |
| 当时可得 known_at | 网页显示publication字符串、2026采集/写入时刻 | 时区/历史版本/首次收到未认证；operational effective_at不能代替known_at |
| 完整池与遗漏分母 | 广泛archive候选，含部分退市币 | 公告是检索样本且排除futures-only退市，无某一历史窗口“全量新上市”的覆盖证明 |
| 历史7日涨幅输入 | 已有日/小时OHLCV入口 | 价格字段存在不能解除上面身份/年龄/状态门；本轮不计算 |
| 执行/终止现金流 | 局部截止和结算规则 | 个别真实结算价未知；仅IC也需要完整事前池，净策略还需资金费、成本、margin路径 |

因此当前**没有可运行的严格新上市日频横截面收益/IC实验**。可完成的是本轮元数据与覆盖审计；用少数资料完整币、用当前存活币、按未来跌幅挑币、或用首根K线定义年龄都改变了问题并带来偏差，本轮不以这些替代方案开跑。NOT_RUN是数据门结论，不是统计阴性，不是用户撤回授权。

最小补足物是一个有明确完整性边界的历史perp生命周期表：每个instrument/version的首次开空、暂停、恢复、退市、重上事件，以及effective_at、可靠known_at/版本来源hash和缺失标记；必须包含失败/短寿命合约并解释重上年龄。可先限定一个完整年份或发行批次，但必须有全体合约枚举依据，不能先凭熟悉程度选币。数据获得与新采集不在本次操作内。

## 可复核方式、哈希与操作状态

本次所有查找均是指定目录的Get-ChildItem -File/-Directory，不使用-Recurse。JSON以json.loads只读，CSV以csv.DictReader读取；notice计数只解析futures_contract_notices_json，再按排序键JSON内容去重。没有特征/标签/收益计算。

本轮复核SHA256：

| 文件（相对L） | SHA256 |
|---|---|
| research_data/noncore_event_sources_20261014/event_source_audit.json | 74e6044f2ce90e8582512c246d0a1ceafa54673009d9e75dfdd502428bbb8172 |
| research_data/binance_noncore_ic_20261013/universe_audit_v2.json | 2b557f042d0ce7d2f0bafd68c864a3957f6750e668a73772d890fc8d84763b64 |
| reports/strategy_validation/btc_noncore_news_event_v1_20261015/source_freeze_expanded/source_catalog.csv | 19d21d4c9ca1b5828e86eb7d51d65e5705ab3281830cdb09ba256d703904d2c1 |
| reports/strategy_validation/btc_noncore_news_event_v1_20261015/review/root_post_result_lifecycle_finding.json | eb522c4b06ddab6ca7513a980e7b405f25c21401a6ad604dca86bbe6bc31a2c2 |

初次查看输出目录时目录尚未创建，返回PathNotFound，非权限拒绝；随后root已创建，本报告仅写该新目录。源文件、前轮目录、small_cap_game_research、人工盲测UI未修改。没有待批准/被拒/不确定执行操作。当前阻塞是完整PIT生命周期数据缺口；独立核查已完成，到此停止，不继续搜索或策略计算。

交付：`<SOURCE_ROOT:research-runs>/2026-10-21/task/new_listing_short_round_20261021/LIFECYCLE_GATE_REVIEW_ZH.md`。
