> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 新上市/高投机合约做空：本轮结论

2026-10-21。本轮已完成旧结果复核、币池差异和生命周期数据门审计；**严格新上市每日做空排序实验未运行（NOT_RUN_DATA_GATES）**。不是策略检验失败，也不是用户未授权。资金费carry已由另一会话完成，本轮没有重做。

## 目前能说什么

1. “每天按IC选可能下跌的币”有可检验的形式，但旧研究尚未建立稳健净交易优势，不能回答何时一定跳水。部分历史IC为正不代表可执行盈利。
2. 旧池含PEPE/BONK/FLOKI/SHIB/BOME/TRUMP/WIF等，要求至少120日前置观测、91日完整、30日平均USDT成交额≥1000万，再按周选top60。它不是上市早期池，更不是每日排序。新问题不能用旧池直接代答。
3. 所核查既有入口没有足以重建完整新上市永续池的历史可开空、暂停/退市/重上及可靠时间证据。用首K线代替上市、只挑资料齐全/存活币，或按后来跌幅定义“山寨币”都会改变研究对象。因此不启动新IC/回测，保留一个候选和最小数据清单。

## 已测旧结果与本轮未测边界

旧报告来自`<SOURCE_ROOT:crypto-leverage>/reports/strategy_validation`，最终版本为：

|子目录及报告|对象与结果|
|---|---|
|btc_short_alts_v1_20261013/RESEARCH_CN.md|只空ETH/SOL/BNB；固定篮子和强弱条件篮子主门槛全部失败，不能当新上市币研究。|
|btc_noncore_selection_v2_20261014/RESEARCH_CN.md|5规则，M1历史IC通过，净经济0个通过；数值以numerical_v2为准。|
|btc_noncore_literature_selection_v3_20261014/review/delivery/RESEARCH_CN.md|10规则，L4/L8/L9历史IC通过，净经济0个通过。|
|btc_noncore_combination_v4_20261014/review/delivery/RESEARCH_CN.md|4组合，没有跨2024/2025经济与稳定性同时通过者。|
|btc_noncore_news_event_v1_20261015/review/delivery/RESEARCH_CN.md|4公告规则全部未过；newreview/delivery是待验收草稿，不采用。|

例如M1的2024/2025历史IC为0.099/0.197，但同周Q5相对ALL净增量分别−0.051/+0.424个百分点，95%CI分别[−0.529,+0.407]/[−0.647,+1.445]，44/30个完整配对周，均跨0。2025只扣交易成本时+0.901个百分点，计资金费后缩小至+0.424，说明资金费不能漏计。这里是同周独立7日事件、每1单位参考资本0.5 BTC多+0.5alts空，不是连续账户年化；美元平衡也不自动beta中性。

v2-v4基础20bp/边、压力50bp/边是每腿入/出实际名义额的综合成本假设，非成交实测；另逐事件记资金费`−signed_qty×event_mark×rate`，entry<event<=exit。未知退出/mark/资金费覆盖保留UNKNOWN，不能填0。原v1用10/20bp，与v2口径不同，不混用。

尾部已有反例：公告研究ALPACA已知3日对冲篮子净损失−63.652%，扣费价格贡献−20.816%、资金费−42.835%；是参考资本独立篮子，不是经验证账户回撤。该损失不在只有3个完整配对的新闻增量子集内，不能隐去。另一周频窗口盘中大幅上涨、正常退出缺失，进一步说明“最终跌”与做空过程中活下来不是一回事。负资金费、逼空、流动性枯竭、跳空、保证金/强平风险必须逐路径计量。

以上来自已保存旧报告及审计，本轮不重跑其策略或测试。已曝光历史不称新OOS。完整旧路径、规则、IC、现金流、成本和尾部在前轮`carry_short_round2_20261021/SHORT_EXISTING_AUDIT_ZH.md`，原文件保留不修改。

## 本轮新审计：样本和可得性

主代理独立用PowerShell重数旧selected_features.csv：15354币周、325个symbol、257周决策，2021-01-04至2025-12-01，非完整2025。固定JSON入口也已直接读取；操作证据见AUDIT_STATUS.json。自动化审计脚本因下面的路径解析拒绝未跑真实输入，没有audit_run_v1回执；不能声称分年/逐币/标签计数已由该脚本重现。首次入选PEPE 2023-09-04、BOME 2024-07-15、TRUMP 2025-05-19来自前轮已核查审计；这些是入池时刻，不是上市时刻。

修正版universe_audit_v2.json：2021–2025有观测634个symbol，剔除Core/指数11项后623个provisional候选；仍标BLOCKED_CRYPTO_ASSET_CLASS_UNVERIFIED。原627被修正，不能拿旧数字当最新版。另采集计划313次周决策/top20和研究257次/top60是不同池，不混为策略样本。

归档质量清单总体范围2020-07-01至2026-09-30，897个symbol；1d交易K线652661行、1h交易15654522行、1h mark15814057行/892symbol、funding归档2708506事件。以上为既有清单范围，本轮没有逐文件重新校验全部行情。51个日线系列有观测缺口/缺归档；历史合约状态UNVERIFIED，mark readiness=false。即使文件校验完整，也不证明历史可卖空或全部mark可用。

更具体的新证据：新闻source_freeze_expanded/source_catalog.csv有146个token行、17条去重永续条款/17合约，其中7继续、10禁止新开并结算，没有首次上市/重上动作。其来源回执是检索样本，特意排除futures-only退市；publication显示时区/页面历史版本未认证。AERGO的2025-04-16 11UTC重上是事后定点发现，不能代表完整生命周期普查。详见LIFECYCLE_GATE_REVIEW_ZH.md。

文件名或字段有时间戳也不能互换含义：archive first_open是价格观测起点，listing_pages是对象存储目录列表，retrieved_at是采集时刻，effective_at是操作生效；都不自动等于公开可知的上市/开空时刻。现货发行/上市不等于永续可卖空上市。这里缺的是完整证据，不能把未知币一律标“不可交易”，也不能标“可交易”。**可信的新上市样本量尚不能确定，用null而非0。**

旧端点审计122832条中：122584正成交活动观测、177零/负活动（17币）、71缺归档（31币）。少量缺口不能忽视：退市和逼空尾部不是随机缺失。正成交也不证明自己的订单能按价成交。旧exact funding约702108事件，其中336598缺event mark；没有现金流必需字段不能用rate简单求和代替收益。

## 唯一保留候选及下一步最小要求

PROTOCOL_AND_DATA_GATES_ZH.md冻结了唯一候选：可核实可开空满14–120日的USDT永续，日频按决策前7日涨幅排序，top20%做空，最低5只，持24h；因此不声称覆盖首14天。主风险控制统计为事前beta残差标签rankIC，同时报告Pearson IC、原始空头标签、同日ALL/无仓/同数量匹配对照。费用20/50bp每侧、实际资金费、1h/4h延迟、换手和尾部全部预设，禁止看结果调年龄/参数。新策略数据门未过，以上只是可复用规格，不是已跑结果。

首先需要有完整性边界的历史合约事件表：instrument/version、真实首次可开空、暂停/恢复/退市/重上、effective_at、可靠publication/known_at依据、来源hash和遗漏分母，包含失败/短寿命合约。可限完整年份或发行批次，不能先选熟悉或后来下跌的币。其次要目标窗口价格/成交活动、真实退出或自动结算价、资金费event mark和周期覆盖。可执行净收益还需价差/深度或可信成本界、规模冲击、保证金和强平路径。仅有K线最多做标明低保真的机制初筛，不宣称撮合、容量或年化验证。

本轮不采购、不采集、不补搜无限公告；没有必要通过重复旧因子计算来填补这些缺口。

## 实际执行清单

|工作|状态|
|---|---|
|旧v1-v4及新闻结果/币池差异复核|完成，复用前轮审计并核对固定入口|
|生命周期缺口有界复核|完成，新增17条公告范围及known_at证据检查|
|直接读取源JSON/公告元数据、重数旧selected CSV覆盖|完成；元数据计数不是策略计算|
|自动化5输入审计脚本真实运行|BLOCKED_PATH_RESOLUTION；代码保留，未生成真实数据回执|
|新上市每日因子、IC/rankIC、净收益/风险账户实验|NOT_RUN_DATA_GATES|
|carry重跑、新数据采集/付费/账户/交易/权限变更|未做|

研究本身阻塞于生命周期/样本和执行数据证据。另有独立工具阻塞：实现代理运行合成测试时，Path(__file__).resolve(strict=False)解析`<SOURCE_ROOT:research-runs>/2026-10-21/task/new_listing_short_round_20261021/audit_existing_inputs.py`返回PermissionError [WinError 5] 拒绝访问。代理曾加入绝对路径fallback并运行合成检查；主代理审查发现后要求撤回，最终代码遇解析错误终止，未再重试。那些fallback版本合成结果不作为最终代码验收。没有真实输入脚本运行，没有IC/策略运行；已完成的独立只读核查不依赖该脚本。准确状态和命令见CODE_REVIEW_AND_BLOCKER_ZH.md。

此处没有请求继续执行该拒绝动作；旧HTTP418、crypto安装PermissionError没有重试。源策略/数据/生产配置未修改，写入仅本独立任务目录。两类阻塞分开报告，按本轮边界完成后停止。
