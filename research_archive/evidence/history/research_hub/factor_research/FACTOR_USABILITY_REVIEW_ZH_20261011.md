> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# 因子可用性复核：限定输入、基准辅助与暂停项

日期：2026-10-11 UTC。范围：从本目录既有卡片追到可访问的原始报告、保存指标和少量定义代码；不重做全仓盘点。结论是 **研究用途判定**，不改历史 registry verdict，不代表策略门禁通过。

**当前没有因子足以直接支持实盘买卖信号。** 值得保留的是风险尺度输入、固定趋势基准和少数待验证增量；不能把模型误差改善、状态归因或独立重置账户的 USDT 盈亏算术和当作 alpha。

## 1. 判定与优先顺序

- **A：限定模型输入。** 定义、版本和保存输出足以支持明确的回顾性研究用途；仅适用于下述冻结样本、模型和假设时钟。A 不表示单因子有独立增量、真实 PIT 已验证、可跨币外推或可部署。
- **B：基准、风险辅助或待验证候选。** 可保留具体用途，尚不能作为已证实的增量信号。
- **C：暂停当前证据或版本。** 包括失效数字、数据/时钟阻塞与当前增量不足；不等于永久否定方法或经济假设。

| 顺序 | 因子或严格限定的特征块 | 判定 / 可用用途 | 数值依据 | 最小下一验证；停止条件 |
|---|---|---|---|---|
| 1 | 已冻结的 own/BTC trailing variance 九列块 | **A，联合块限定**：回顾性 `log(V_1h24)` 风险尺度输入和损失诊断；单列贡献未建立 | Core4 4,228 个评分 origin，pooled MSE 对 EWMA 改善 13.7937%；Core3 六组比较 3 改善 / 3 恶化，ETH 两窗 +0.4149% / +7.9956% [E1–E3] | 先核真实价格发布时钟；另行冻结一个风险目标及 own-only / own+BTC / 常数 / EWMA 的共同样本比较，按日期处理重叠。若 BTC 块无增量，不继续扩特征；不因 MSE 改善接入仓位 |
| 2 | 4h EMA200、MACD(12,26,9)+EMA200、Donchian55/20 | **B**：固定趋势/动量基准和模型对照 | 2025 旧账户净收益 +21.65% / +14.96% / +8.16%，95 / 155 / 41 笔；日 Sharpe .759 / .706 / .433 [E4] | 冻结一种因子表达、一个目标与共同曝光/成本对照；不得再用 2025 选参数。先解决交易现实与因子归因，不重复调参 |
| 3 | 观测 funding rate、age、7日 observed sum/count | **B**：资金费现金流所需观测、风险背景；当前轮动 alpha 不支持 | 363 个日样本，低 funding 篮子对 Core4 等权毛 logreturn 均差 −6.89bp；ALT3 残差差 −8.31bp [E5] | 核定真实发布/结算时钟与事件完整性；如研究轮动，仅一个固定规则，与同成交/曝光对照比较，计 funding 现金流和双边成本；缺事件即阻塞 |
| 4 | ATR14、`d_stop=2×ATR14/reference_close` | **B**：价格距离和敞口缩减辅助 | CAL 新 MAE 映射净收益 −0.450%、平均 exposure .837%，E0 为 −1.952% / 2.808%；仅 10 笔 [E6] | 先对齐实际持有风险期限，并匹配敞口；若只靠减仓同时减少赢家，不称风险预测增益 |
| 5 | EOH ATM mark-IV，固定 TRAIN 尺度校准 | **B，条件性候选**：未来方差风险信息；禁止方向信号推广 | n=261；校准 ATM MSE 2.337969e−10，校准 price 2.699956e−10，常数 2.515029e−10：改善 13.4071% / 7.0401% [E7–E8] | 先证明 EOH 桶语义、单位、first-public 时间和历史 revision；过关后仅固定一次同样本 ATM 消融与分日期不确定性。时钟仍 UNKNOWN 则停止模型接入 |
| 6 | D1 的 BTC 三状态 one-hot（联合价格+IV模型） | **B，稀疏候选**：共享模型状态条件；不宣称独立因子有效 | 基础成本种子 PnL −17.29 / +89.67 / −34.13 USDT，74 / 29 / 33 笔；高成本筛选仅 19 / 7 / 6 笔 [E10] | 先核逐折阈值/scaler/checkpoint 和实际 IV 发布时钟；未来另行预注册 price / price+IV / price+IV+state 单次比较，固定15m退出与同成本选择规则；支持不足即弃权 |
| 7 | BTC 相对收益、额外滞后 BTC 收益、ER28背景 | **B**：市场敏感性/状态描述；当前版本无稳定收益预测增量 | 2025 四项条件残差 CI 全跨零；跨币研究 F1/F0 六个 MAE 点估计全负；六因子 45 消融仅 1 正 [E5、E11–E12] | 若继续，只预声明一个时点一致版本与 own-only 配对消融；保留旧失败，不把归因表直接变过滤账户 |
| 8 | Binance `log_bvol_index` | **B，较低优先级候选**：与 ATM 分开的风险信息研究 | n=1,346；对 price-only QLIKE −0.249594，但 MSE 恶化约 7.0214%；也未胜训练均值 [E9] | 先核 `calc_time` 到真实发布的时钟；固定主损失与同日簇比较。禁止事后在 MSE/QLIKE 中挑有利指标 |
| 9 | EOH relative skew 当前扩展 | **C**：暂停在此配置上继续加维 | raw ATM+skew MSE 2.801872e−10，高于 ATM 2.731908e−10；ALL/BTC/ETH 的 QLIKE 均更差 [E7] | 保留负结果；只有新机制、合格 PIT 数据和独立协议才重开，不在同一旧窗调 skew 到盈利 |
| 10 | OI、订单簿、跨交易所价差 | **C，BLOCKED / NOT_TESTED**：不能进入新拟合或套利结论 | OI 500 行，2026-09-17～19；订单簿 1 行。OKX close-only 有 2024/25覆盖，但价格单位和 close 可得时刻未解决 [E13、E5a] | 先给连续性、市场身份、字段单位和真实时钟证据；不补值、不借旧 ffill pipeline；没有数据/合同即停止 |
| 11 | 稳定币流动性 `stb_flow_1d/7d` | **C，来源/PIT阻塞**：目前不列作已可用输入 | 合并文件 footer 2,448 行；目录状态 `NO_CONTINUOUS_SOURCE` / `SKIPPED_UNCONFIGURED`。真实稳定币观测天数、历史发布/修订和模型增量均 UNKNOWN [E14–E15] | 先分离实际观测、回填/修订与派生行，绑定原始来源及 first-public；独立短样本不足不能用4h重复行放大。未找到合格来源就暂停 |
| 12 | 旧 GARCH/HAR/OLS 泄漏分数；ETH/BTC lead-lag 主推断 | **C，旧证据失效** | GARCH 用未来创新，HAR/OLS 纳入未成熟标签；修复仅25项合成测试。lead/lag 四候选完整账户对照复制数均0 [E16–E17] | 失效数字及下游 sizing 不再比较。方法若重开，先独立因果检查和新 origin-aware 协议；不把合成通过当市场重跑 |

A 仅指第一行**冻结联合块的限定历史输入资格**。它不是“own RV、BTC RV、每个窗口分别有效”的结论；当前没有 own-only 对 own+BTC 的完整因子剥离证据。Funding 是成本观测的必要组成，但“结算数据应记账”不等于 funding 是买卖 alpha。

## 2. 波动输入：定义清楚，预测证据有限，经济增量未成立

Core3 定义经 实现 (`provenance:nonincluded/crypto-leverage/tools/perptools/core3_trend_risk_v1.py`) 与 helper (`provenance:nonincluded/crypto-leverage/tools/perptools/volatility.py`) 核对：`r4h=diff(log(close))`，`RV²_W=mean(r4h² over W completed returns)`，W=6/42/180，取自然对数；这是二阶矩，不是去均值的样本方差，不年化。零/负/非有限值不以 epsilon 或零填补。顺序为 own 三列、BTC 三列、ETH/SOL/BNB dummies；Core3 的 BNB dummy 恒为0。窗口对应24/168/720小时，但输入单位仍为4h return-square，不能直接等同 H1 目标尺度。

目标是下一24根完整 H1 close logreturn 平方均值 `V_1h24`，不含结束在 origin 的收益；`log(V)` 是训练目标，未来标签不是输入。Core3 lambda=10、TRAIN-only mean/std(ddof=0)、常量列 scale=1、截距不惩罚、输出 `exp(predicted logV)` 无 smearing；参考方差 0.0002824090500991152。模型时钟：feature 为 close+1ms，主决策 close+1001ms；标签实际24h成熟再加1001ms必须严格早于 cutoff。实际上游发布时钟 UNKNOWN。部分旧卡片写“close+1秒”，不能据此覆盖当前代码的精确毫秒合同；本轮记录差异而不改卡片。

Core4 V1R2 是独立的四币模型：4,324 TRAIN 行（每币1,081）、4,248预测、4,228评分；BNB dummy 活跃。Core3 为三币，3,237 TRAIN 行（每币1,079），不得换名字沿用 Core4 参数、hash或结论。两个研究均 TRAIN `[2021-01-01,2021-07-01)`、7日 embargo、已暴露验证 `[2021-07-08,2022-01-01)`；Core3 另用同一冻结fit诊断已复用2025，无重新拟合。

| Core3 fold/币 | 共同 origin 数 | Ridge MSE | EWMA MSE | MSE改善（正为好） |
|---|---:|---:|---:|---:|
| 2021 BTC | 1,055 | 1.936753e−9 | 1.896969e−9 | −2.0972% |
| 2021 ETH | 1,055 | 4.545241e−9 | 4.564176e−9 | +0.4149% |
| 2021 SOL | 1,055 | 5.002198e−8 | 5.750995e−8 | +13.0203% |
| 2025 BTC | 2,183 | 7.315350e−10 | 7.311597e−10 | −0.0513% |
| 2025 ETH | 2,183 | 5.297202e−9 | 5.757555e−9 | +7.9956% |
| 2025 SOL | 2,183 | 1.062219e−8 | 9.907734e−9 | −7.2111% |

本轮从 E2 的保存 JSON 重新算上表百分比；没有拟合或推理。9,714 是预测行数，24h目标每4h重复起点；从保存 origin/maturity 贪心取不重叠目标窗，每币2021可取176、2025可取364个。**这些仍不是统计独立 N 或有效样本量**：币种共市场、跨日相关与跨窗依赖仍存在，不能加总三币或当作置信区间自由度。Core4 的4,228也同样不是4,228个独立风险事件。

经济证据须另外判定。本轮从保存 forecast 及 main Ridge 交易的 entry 时间（主时钟下对应 origin=entry−1h−1ms）配对，重算 `q=min(1,sqrt(reference/prediction))`：EMA/MACD/Donchian 的95/155/41笔，合计291笔，全部 q=1；各自 Ridge 与 q1 的 trades 和 NAV CSV 字节一致。2025没有风险缩放增益。2021三个 main Ridge matched controls 均不满足0.1%逐币敞口误差门槛，SOL误差分别0.1177% / 0.2958% / 0.1873%；不是等曝光 alpha。E3 的独立重建 PASS 仅覆盖重建和账务，不通过真实发布、成交、未触碰 OOS 等策略关卡。

## 3. 趋势/动量与 ER：保留基准，不把策略结果当单因子证明

Core3 EMA200以首200 close均值为seed、alpha=2/201递推，信号 `close>EMA200`。MACD+EMA200为 hist>0 且 close>EMA200，hist 来自 TA-Lib(12,26,9)。Donchian55/20使用 **shift(1)** 后的55 high与20 low，突破入场/跌破退出，否则保持状态；评分段开始 OFF，预热历史保留。均为 long/cash，完成4h桶与严格更晚H1成交，真实时钟未证。

E4 是十二条规则（4h/1d）的冻结永续改编账户，不是 spot P19 精确复现。TRAIN `[2020-09-15,2025-01-01)` 的 +545.63% 等为整段累计而非年化；2025已用于研究。每边5bp fee+5bp adverse slippage、观测funding的 prior-H1-mark proxy、100,000USDT分段账户、初始固定槽位、不复利；无真实 spread/capacity/margin/liquidation。EMA 2025 +21.65% 能支持“留下此基准”，不能证明EMA因子在控制市场风险、规则搜索和成本后有效。MACD单独4h为−4.82%、1d为−39.18%；不要只展示组合正值。BB120+EMA200+ATR3的 +16.81% 仅19笔，前三赢家占正交易利润81.2%，也不能据此归因布林单因子。三个 TRAIN `NO_BORROW_FAIL` 不是0收益。

六因子 V2 的趋势表达与 Core3 规则不同：P0包括 `close/EMA200−1`、`EMA20/EMA60−1`、`MACD_hist/close`、BB标准化位置、ATR14/close、1/3/7日收益及1/7日 RV；D追加已完成日线背景。TRAIN 2022/23/24扩展折中177个头，24胜常数、153负；45 paired MAE消融44负、1正，6个负向D比较通过45项Holm。2025冻结59头仅9胜常数，全部BTC残差目标；这不是收益账本，也不能排除未测的排序/尾部用途。

E11 的 ER28=`|C_t−C_(t−28)|/Σ|ΔC|`；TRAIN 1,569日期拟合 q25=.0922795171、q75=.3195420590，归因1,568窗；2025用冻结阈值，共364个配对24h窗。BTC相对因果dailyEMA200 Above/High的2025贡献为 BB +16.65pp(n=45)、EMA +28.32pp(n=45)，Above/Mid却为−6.67pp/−10.49pp；这些是原NAV分组贡献，不是只在该状态交易的收益。状态逻辑日末后1秒可用，activation次日00:59:59.999 UTC；不等于日历日。EMA对BTC的2025条件残差6.69bp/day，95%CI[−8.44,+21.82]；其余三项也跨零。固定TRAIN beta的CI未纳入beta估计不确定性，多次策略/窗口选择未校正。

E12 的 BTC F1/F0 在 ETH/SOL 的1/4/24h六个比较均无正点增量；ETH24h MAE差−.00071867、CI[−.00112187,−.00033806]，SOL24h−.00254384、CI[−.00454816,−.00069886]。SOL F2/F1 的24h有+.00026652、CI[+.00010354,+.00042598]，但未建立F2/F0增量，5+5bp账户仅38笔、Sharpe1.065，冻结筛选 `NO_SELECTION`。自己的回报差、BTC滞后回报、残差标签和ER状态不是一个可互换因子。六因子B/BF还额外滞后一根决策bar；不能用它否定“决策时最新已完成BTC bar”的未测变体，也不能从这个未测变体直接得出可用。

## 4. ATM、BVOL、DVOL 与 skew：三个数据合同，两个用途

EOH V2R2 使用 BTC/ETH 2023 `06-20,09-01)` TRAIN、7日embargo、`[09-08,10-24)`复用验证；2022仅价格预热。547 TRAIN、271预测、261评分（BTC162、ETH99），24h标签重叠；未给分日期CI或独立有效 N。缺档9月8～18及25日不填，552候选origin最终仅261评分，所以条件共同mask不能代表整个市场。

协议选最近完整 snapshot，期限24h～7d中最近有完整ATM call/put的expiry；ATM delta目标±.50、距目标≤.15，skew腿同snapshot/expiry、delta目标±.25、距目标≤.10，要求正IV/bid/ask/数量及合法quote。ATM为两腿raw mark-IV均值，`log_raw_atm_iv=ln(ATM)`；`unit_invariant_relative_skew=(IV_25put−IV_25call)/ATM`。本轮用271条保存预测的腿字段复算这三个变换，最大绝对残差1.95e−16；这是保存行公式核对，不证明链完整或原始发布时间。不把EOH raw IV写成年化百分比。`date/hour`假设UTC桶，event_upper=桶起点+1h，假设available=event_upper+1h，age0～65m，**真实桶含义、单位及发布均UNKNOWN**。TRAIN-only标准化能吸收统一乘法尺度，不能消除跨日单位/版本变化；保存腿也不证明完整链中确是最近候选。

原3头中 ATM raw MSE 2.731908e−10优于price3.028865e−10，但常数2.515029e−10优于ATM；ATM+skew为2.801872e−10。后续仅两个冻结头做TRAIN尺度校准（price c=1.5328953844、ATM c=1.4337533752，零新Ridge fits），ATM的 MSE 与QLIKE改善是**有条件风险证据**。校准ATM QLIKE−10.234992，price−10.086335、常数−10.228670；后者差值仅−.0063225，不对负QLIKE算百分比。CAL最高预测bin仅4行、realized/calibrated均值约2.794，尾部校准仍有限。

BVOL是另一项 V1：`calc_time/symbol/index_value`、加 `log_bvol_index`，假设发布为calc_time+1h，真实发布UNKNOWN；BTC/ETH 2023 `[06-20,09-01)` TRAIN、`[09-08,2024-01-01)`验证，863 TRAIN、1,356预测、1,346评分（每币673）。缺9月25及10月24。price+BVOL MSE5.846917e−10劣于price5.463313e−10、EWMA5.176841e−10和常数4.799310e−10；QLIKE虽优于price，但−9.702570仍劣于常数−9.787103。不能把 BVOL 与 EOH ATM 或 R3K DVOL拼为一个已经有效的IV因子。

R3K IV块是10个派生字段：level/range/change1d、5d、20d/mean20d/z20d/rank252d/IV-RV ratio/age_min；报告只支持DVOL类30天年化概念，本地raw映射、单位和实际发布时间仍未绑定。V2代码约定年化百分数除100、每年525,600分钟，IV daily bucket假设available=bucket start+48h+1s，敏感性再延24h；这些计算/时钟约定不证明本地源满足该单位或发布合同。age字段和模拟延迟不证明PIT。分钟终点90%区间：IV约89.24%/89.19%/89.20%，价格尺度90.05%/90.02%/90.10%；无IV明显优势，也不是路径上下界。价格+IV的稳定预测/净收益增量未建立。

## 5. D1、风险头及 funding：必须有正确对照

D1冻结 `price_iv_btc_state` 输入包含47个price anchor、10个IV、三个BTC state one-hot及90×7已完成分钟序列；**没有九列连续/二元BTC daily家族**，后者属于另一组arm。[日线定义代码 (`provenance:nonincluded/crypto-leverage/tools/perptools/ema_iv_v1/daily.py`)中，数据/EMA200/ER28均有效后，UP为close>EMA200；DOWN为close<EMA200、`(EMA_t−EMA_(t−1))/EMA_t<=0` 且ER28>=该折TRAIN P75；其余有效日为SIDEWAYS，无效为MISSING。UP不要求高ER，不能把Gate B条件误当整个UP定义。各折P75样本仅2021起、可得时刻严格早于TRAIN cutoff的有效日，至少200日；阈值冻结用于该折CAL/EVAL。日状态假设available=日边界+1s（敏感性另+5m），缺state行不以全0填入。逐折数值scaler和checkpoint-to-output完整绑定本轮没有读取，不能凭算法说明认为已核验。

E10覆盖 ETH永续1m、BTC交叉背景，原输入2021-11～2023-12，账户2022-08-01～2023-12-31，13个独立重置窗×3 seeds；决策T+61s、成交T+120s，每窗10,000USDT、每笔1,000名义，基础fee+slip每边7bp并记观测funding。136笔跨种子交易和+38.25USDT总和不是连续账户收益，不是136独立市场样本。高成本变体+169.85/+61.55/+35.81USDT仅19/7/6笔，成本阈值同时改变入场集合，不能称同笔交易成本stress通过。

Transformer对相同信息Ridge的标准化损失比较H5，74周、七项Holm p=.00069993，支持的是表达能力线索；汇总raw MSE仍略差零收益。它不是IV或state单因子消融。H7在线性price+IV上加BTC daily的基础成本平均周差−.214120pp、CI[−.481941,−.032975]、正向单侧p=.947405、Holm p=1；其他五项经济比較未达支持要求。旧错误基准202/303零交易、缺120延迟身份、原反向退出/门控错误均有纠正sidecar；以最终报告为准，纠正或等价重绑不增加独立证据，六专家训练支持不足仍弃权。

C3 13列价格risk-head FIT2021-01～2022-07、CAL2022-07-08～2023-01，先前已见2023且2024～26曾暴露。CAL14候选：MAE q90 pinball .005141对常数.006108，stop Brier .22613对.25708改善，但terminal q10 pinball .005963劣于.005507；实际成交仅10。新MAE缩放CAL losses较小同时exposure由2.808%降至.837%；FIT回报+.781%劣于E0+2.910%及固定权重+1.025%。不同平均exposure不等于风险匹配。超过24h持有为FIT21/34、CAL7/10，实际尾部风险不能由24h目标替代。ATR及stop-scaled quantity可以作辅助，但不称有效增量因子。

六因子F只使用 `event+5m<=decision` 的实际observed rate、age及7日sum/count，age≤16h、age缩放固定8h；原V1近常量age缩放问题保留。2025 7日观测count20、最大age8.00028h只是该窗，历史SOL间隔不规则仍需保留。低费率篮子的−6.89bp / −8.31bp是363日**毛**logreturn差，不含funding cash/手续费/滑点、不复利。另读P1B2024 v7报告开头100行：该研究price-only、2/5bp每边且无funding现金流、slippage/mark/margin；不能把其费用条件分组视作永续经济检验。本轮未审阅其全部3,466行候选表，不作全表择优。

## 6. 被阻塞与失效证据

OI本地引用的schema为symbol/sumOpenInterest/sumOpenInterestValue/CMCCirculatingSupply/timestamp/datetime；500行覆盖2026-09-17 20:55～09-19 14:30，source manifest仍 `UNVERIFIED_NO_FROZEN_RECORD`、registry `EXTERNAL_REFERENCE_ONLY`。OI数量与名义价值单位不能混用；这些footer/既有metadata不足以建立连续历史或真实publish。订单簿1行更不能做统计。未运行OI增量，结论是阻塞，不是OI机制无效。

OKX Core3 4h close-only在既有E5a有规则2024/25格子和local digest，但interval-label、close可得时间及单位未解；无BNB、无bid/ask/depth，不能描述为可成交价差。旧相邻dataset_builder明确basis `.ffill().fillna(0)`、funding `.reindex(...method='ffill').fillna(0)`，不得直接复用。

稳定币卡片属于相邻 legacy token code家族，现代码消费 `stb_flow_1d/7d`，先shift(1)再按日ffill。**一日lag不能证明历史 first-public 或无事后修订。** 本轮只读 `eth_onchain_sentiment_daily.parquet` footer：2,448行、date范围2020-01-01～2026-09-13、timezone-naive、含stablecoin_usd/stb_flow字段，未解码行情/稳定币值。当前catalog报连续源未配置且sentiment未验证，total_bars=0是该状态记录，不能解释成物理文件0行。尚未找到支持“独立稳定币覆盖很短”的原始证据，因此不报具体短样本天数；也不能把2,448行叫作2,448天真实PIT稳定币观测。真实独立覆盖 UNKNOWN，尚无版本绑定消融或经济证据。相邻方法审计同时提示链上快照修订风险；它关于D−1对齐的代码检查不是供应商发布证据。若独立真实覆盖确实很短，重复到4h行也不能使样本充足。

GARCH旧输出使用未来realized innovations、全向量seed；HAR/OLS旧训练纳入尚未成熟标签。E16明确旧 forecast/ranking/calibration/下游sizing **INVALIDATED**，修复仅合成25项、无market重跑、evaluator缺新origin合同仍拒绝。无需也不得为展示而重读失效分数。ETH/BTC lead_4h/24h、lag_4h/24h自然事件383/223/385/239，完整100对照378/220/380/236；unmatched schedule500/300/500/300，完整账户replicate均0。保存Holm和下界仅不完整子集诊断，primary inference `INFERENCE_INCOMPLETE` / `NO_SELECTION`；全样本账户描述仍保留，不修复主推断。

支撑事件也不是成熟因子：六因子1,443 episodes含重叠；WAIT_LEFT曾忽略floor下破。后续严格V2记304确认及约1.862/2.097ATR迟确认（E11转引，未重读casebook）；不能把确认率叫胜率。通道ML的feature importance只是29列训练/选中模型描述，513实际base fills含unknown-execution ledger，不是单因子消融；当前短线/flow模型失败与legacy spot模型不外推为永续因子有效。

## 7. 来源与本轮读取范围

下表“读取”均是本轮读取已有文本/保存输出，未重算市场研究。大型文件只选取与上述结论有关的字段/段落；不声称完整代码或raw数据审计。source hash是版本定位，不自动等于来源质量或策略PASS。

| ID | 来源（可点击） | 本轮范围 |
|---|---|---|
| E1 | [Core4算术审计](../../reports/strategy_validation/trend_vol_1h_risk2021_v1/derived_arithmetic_audit_v1r3.json)、descriptor (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/trend_vol_1h_risk2021_v1/model_descriptors_train_only.json`)、contract (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/trend_vol_1h_risk2021_v1/core_run_contract.json`) | 原75项一致性状态、pooled比较、定义和窗口；不加载模型 |
| E2 | Core3 results (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/core3_trend_risk_v1/results_v1r3/results.json`)、paired forecasts (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/core3_trend_risk_v1/results_v1r3/paired_forecasts.csv`) | 全6组MSE、fit/clock/match字段；保存forecast全表，三个2025 main Ridge/q1 trades与NAV；重新算q、百分比、不重叠窗计数/字节相等 |
| E3 | 独立重建审计 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/research_hub_review_20261011_v1/INDEPENDENT_NUMERIC_AUDIT_V1R3.json`)、[Core3模型卡](../strategy_models/experiments/core3-trend-risk-v1.md)、协议 (`provenance:nonincluded/crypto-leverage/research_hub/platform_data/contracts/core3_trend_risk_protocol_v1.md`) | 审计相关字段、卡片全文、协议全文；报告绑定results SHA为DE9F6DFA271F30DF68396B0AEC538E2123794E0091DCB7AAD30835186F5C202F |
| E4 | [十二规则账户](../../reports/strategy_validation/longcycle_trend_catalog_v1/ACCOUNT_RESULTS_V3_20261003.md) | 全文、失败、成本及集中度；引用CSV SHA 3B51FF82FC55CCE4DB6825C6DA5BFF85F20B1DC880E44FB7A9A5BE3F17909DA4，不新跑账户 |
| E5 | 六因子结果 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/sixfactor_longcycle_v1/SIXFACTOR_LONGCYCLE_RESULTS_CN_20261003.md`)、V2协议 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/sixfactor_longcycle_v1/PROTOCOL_V2_20261003.md`) | 摘要/方向/门禁及特征、消融、时间合同；未逐行审阅177/59头长表 |
| E5a | 覆盖与证据 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/sixfactor_longcycle_v1/EVIDENCE_AND_COVERAGE_20261003.md`)、P1B2024 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/next_signal_research/p1b_funding_2024_v4/results_v7/P1B_TRAIN_2024.md`) | 前者全文；后者1–100行，非整表审计 |
| E6 | [C3风险训练最终审计报告](../../docs/C3_RISK_TRAIN_REFINEMENT_REPORT_AUDITED_V1R3.md) | 全文已有账户/标签/持有期/限定审计；不读取原始price或模型；该报告绑定audit SHA 59975167F01786A63F0F13F6836E8FE9599BB1AFE0B66DFECA9FBB9B0DC43792 |
| E7 | EOH原研究 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/BINANCE_EOH_INCREMENT_2023_V2R2_RESULTS_CN_V1R1_20261001.md`)、descriptor (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/eoh_increment2023_v2r1/model_descriptors_train_only.json`)、协议 (`provenance:nonincluded/crypto-leverage/docs/BINANCE_OPTIONS_EOH_INCREMENTAL_FORECAST_PROTOCOL_V2R2_PENDING_20261001.md`) | 原报告；descriptor和协议相关字段；EOH锁code identity字段，未重验232原始源对象 |
| E8 | 校准metrics (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/eoh_train_scale_calibration_v1/calibration_metrics.json`)、parameters (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/eoh_train_scale_calibration_v1/calibration_parameters_train_only.json`)、contract (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/eoh_train_scale_calibration_v1/calibration_contract.json`)、manifest (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/eoh_train_scale_calibration_v1/run_manifest.json`)、保存预测 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/eoh_train_scale_calibration_v1/calibration_predictions.json`) | 保存指标/参数/合同；predictions核schema和271行期权腿变换，非原链审核；由metrics重新算改善；metrics历史绑定SHA C74F2A0973C80B93E847CD2337E81A8B29F4ED8279105EB58E81A05F51CF5C80 |
| E9 | BVOL metrics (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/binance_bvol_increment_2023/validation_metrics.json`)、contract (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/binance_bvol_increment_2023/core_run_contract.json`)、descriptor (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/binance_bvol_increment_2023/model_descriptors_train_only.json`)、manifest (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/binance_bvol_increment_2023/run_manifest.json`) | 原指标相关行、定义和窗口；metadata-clock audit只选段；由保存MSE/QLIKE做算术，未读原BVOL值 |
| E10 | [D1最终报告](../../reports/strategy_validation/r3k_20261005/d1_r3k_20261005.md)、EMA+IV第一结论 (`provenance:nonincluded/crypto-leverage/reports/EMA_IV_FIRST_CONCLUSION_CN_20261005.md`)、[D1卡片](../strategy_models/experiments/d1-r3k-20261005.md)、V2 protocol (`provenance:nonincluded/crypto-leverage/tools/perptools/ema_iv_v2/protocol_v2.py`) | 两原报告全文、卡片选段、V1 features/daily/protocol和V2 protocol静态相关段；不读69原始输入、权重、逐折完整scaler或2808账本 |
| E11 | [状态归因 v1r2](../../reports/strategy_validation/focused_followup_v1/FOCUSED_FOLLOWUP_RESULTS_CN_20261003_v1r2.md) | 全文；原TRAIN参数SHA AD699A8033878F17B37DC007F5ABE3BE3D6C11211B5CE829A9491ECD773B5192；支撑V2只用此文转引，不当独立casebook审核 |
| E12 | 跨币Ridge Stage1 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/crossasset_round1_20260930/summary.md`) | 全文配对loss/成本/NO_SELECTION，未读逐行预测或重新估计CI |
| E13 | external catalog (`provenance:nonincluded/crypto-leverage/archive/inventory/external_path_catalog.json`)、dataset registry (`provenance:nonincluded/crypto-leverage/archive/catalog/dataset_registry.json`)、source manifest (`provenance:nonincluded/crypto-leverage/source_data/MANIFEST.json`) | 只取OI/订单簿相关metadata；不读D:或OI/book数值 |
| E14 | 相邻dataset_builder (`provenance:nonincluded/99c8444852e5b946`)、model provenance (`provenance:nonincluded/8d914dcbcbee1f4d`)、状态catalog (`provenance:nonincluded/0c03f2a5eda57428`) | 定义/fill代码段、provenance与onchain状态；不是legacy checkpoint输入绑定证明 |
| E15 | 相邻onchain文件 (`provenance:nonincluded/b3891fe31858737b`)、方法审计 (`provenance:nonincluded/7568c8915cf2bc32`) | parquet仅footer/schema/time stats；方法审计仅相关段。没有独立真实stablecoin覆盖/发布证据 |
| E16 | [波动泄漏修复通知](../../reports/strategy_validation/foundation_review_20260930/VOLATILITY_CAUSAL_LEAKAGE_REPAIR.md) | 全文；旧无效数值未重读 |
| E17 | [lead/lag推断有效性通知](../../reports/strategy_validation/c3_timing_eth_btc_v4/B_INFERENCE_VALIDITY_NOTICE_V1.md) | 全文；只引用完整性缺口，不重用无效p或下界 |
| E18 | 相邻MA/ML摘要 (`provenance:nonincluded/c7df10502927925a`)、channel feature卡片 (`provenance:nonincluded/crypto-leverage/research_hub/factor_research/factor_cards/shared_channel_ml_d6i500_features.md`) | 摘要段和卡片；7,199 legacy events、XGB仅16选中、均值+.095R不足以证明24列各自有效；准确绑定与PIT未审计 |

入口已读：README (`provenance:nonincluded/crypto-leverage/research_hub/factor_research/README.md`)、AGENTS (`provenance:nonincluded/crypto-leverage/research_hub/factor_research/AGENTS.md`)、USAGE (`provenance:nonincluded/crypto-leverage/research_hub/factor_research/USAGE.md`)、INDEX (`provenance:nonincluded/crypto-leverage/research_hub/factor_research/INDEX.md`)、卡片索引 (`provenance:nonincluded/crypto-leverage/research_hub/factor_research/factor_cards/INDEX.md`)。已核对的卡片包含三个primary（factor-calibration、GARCH/HAR invalidated、ETH/BTC invalidated），以及 Core3 EMA/MACD/Donchian/RV、Core4 Ridge、sixfactor趋势、BTC relative、observed funding、basis spread、ATR/C3 phase-A、EOH ATM、DVOL、R3K IV/state/onehot/daily九列/price anchor/sequence、support、相邻token/24列microstructure、BTC minute OHLCV、minute-return flow及channel-ML feature。相关模型卡读 Core3、Core4 Ridge、D1及C3/X3 overlay；overlay仅卡片，未重读原账户报告，其未知输入绑定不提升为已证实ATM消融。

未读：任何权重/checkpoint、原始市场/IV/funding/OI/book数值、D:文件、运行凭证；新训练/推理/回测均未执行。相邻onchain只有footer访问。没有穷举其他模型或所有报告；不把卡片引文当作原始证据全已独立核验。

以下既有拒绝访问项不重试、不stat、不绕过，当前内容未核实：

- `reports/strategy_validation/mtf_channel_limited_compare_20261010_v1/root_review/ONE_PAGE_REVIEW_ZH.md`：先前 `PermissionError / WinError 5`。
- `reports/strategy_validation/mtf_channel_limited_compare_20261010_v1/delivery_v1/FULL_RESULTS_ZH.md`：先前 `PermissionError / WinError 5`。
- `reports/strategy_validation/high_return_trend_20260928/stage_e/e2_pit_volatility_input_audit_v1/results_c_c100_v1`：先前目录枚举拒绝访问。

## 8. 最小后续工作与本次交付边界

1. 先收口真实availability合同，尤其EOH/BVOL/DVOL、稳定币、OI/跨所；没有合同不把时间延迟假设写成实测。
2. 优先保留固定波动块和EMA/MACD/Donchian基准；下一次验证仅冻结一个任务、目标、共同mask及必要消融，不新增大型ML体系。ETH在两已暴露窗的风险损失改善值得优先，但不能据结果事后叫作预注册ETH-only通过。
3. 未触碰窗口须有实际未开发证据；当前2021/2023/2025及相邻2024～26的历史暴露不能用换名字消除。可用本地样本不足就报告不足，不下载或填补。
4. 若目标是经济用途，预声明同事件、同成本、逐币曝光控制和持有风险期限；q=1或不匹配必须保留为无增益/阻塞，不改阈值让其工作。
5. 暂停本报告C项当前版本、旧泄漏数字和短线机械调参；失败版仍保留。后续重新立项需新机制或新合格证据，不能无限寻找盈利。

本轮仅新增本文并在本目录INDEX加链接。没有修改因子卡、其他研究模块、数据、代码、参数pin、历史报告或冻结BB；未执行maintenance rebuild/full pytest，因为本次授权是保存输出的只读复核与两处文档交付，重建会超出“不改数据/pin/历史”的边界。没有声称全套测试通过。本次可验证项是保存数字轻量算术、报告引用及指定文件hash范围；不证明全仓不可见文件均无变化。

交付检查：本文及INDEX的64次本地引用（61个唯一目标）均存在，0缺失、0新增拒绝；上列3个已拒绝项目只记录、不访问。写入前快照涵盖89个既有hub文件和61个指定证据/代码/metadata文件，共150个；其中149个SHA256字节不变，唯一旧文件变化为factor_research/INDEX.md，hub仅新增本文、无删除。快照保存在临时目录`<REDACTED_PRIVATE_PATH> result对独立审计绑定共7项核对一致。轻量复算包括六组Ridge相对MSE、ATM两项MSE改善、BVOL MSE/QLIKE差、271行期权腿变换、291入场q及六组不重叠目标窗计数；没有新市场研究运行。
