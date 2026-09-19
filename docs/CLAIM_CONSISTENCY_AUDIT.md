# 声明一致性审计报告 (Claim Consistency Audit)
审计日期基准: 仓库 main @ 7955834。审计范围: README.md, docs/CROSS_SECTIONAL_ROTATION_IMPLEMENTATION_PLAN.md, leverage_research/README.md, WALKTHROUGH.md, docs/*.json, reports/cross_sectional_evaluation.json。

## 一、全部"最优/推荐/最终"声明清单

| # | 声明 | 宣称绩效 | 数据区间 | 出处 |
|---|------|---------|---------|------|
| C1 | ETH 自适应动量为"最高风险调整质量" | +152.88%, 4h Sharpe 2.09, 日频 2.18, Calmar 3.13, MDD -18.85% | 2024-2025 | README.md L52, L135 |
| C2 | SOL 自适应动量为"最高纯 Alpha" | +183.66% (vs B&H +20.68%), Sharpe 1.95/1.81, MDD -30.68% | 2024-2025 | README.md L53, L142 |
| C3 | BTC 自适应为"最优资本保全" | +75.31%, MDD -15.54% | 2024-2025 | README.md L54, L128 |
| C4 | "自适应动量退出是全场最优方案" | +146.19% (ETH 口径), 夏普 2.04 | 2024-2025 | README.md L56-62; WALKTHROUGH.md L35, L42 |
| C5 | ETH 1.5x 杠杆 [黄金推荐] "最优风控收益平衡" | +281.55%, CAGR +95.21%, MDD -27.43% | 2024-2025 | README.md L171; WALKTHROUGH.md L222 |
| C6 | SOL 1.0x 原版 [最优推荐] | +183.66%, CAGR +68.34% | 2024-2025 | README.md L176; WALKTHROUGH.md L227 |
| C7 | Phase 13 对称多空 (已隔离) | ETH +67.57% / SOL +105.92% / 组合 +94.48%, Beta -0.04 | 2024-2025 | README.md L254-263 |
| C8 | Quickstart 仍宣称 Phase 13 复现 "ETH +102%, SOL +141%" | +102% / +141% | 2024-2025 | README.md L313 |
| C9 | Legacy 归档记录的 Phase 13 数字 | ETH +102.20% / SOL +141.47% | 2024-2025 | README.md L732-733; WALKTHROUGH.md L980-981 |
| C10 | 2026 衍生品增强 8h 策略 | BTC +17.33% / ETH +15.48% / SOL +12.60% | 2026-01~09 | README.md L66-70 |
| C11 | Phase 17 "Verified" 试盘组合 | 2024-25 +23.76% (Sharpe 0.82, MDD -18.93%); 2026 -6.09%; 全周期 +16.20% | 2024-2026 | README.md L84-96; docs/metrics.json |
| C12 | Phase 18 成本过滤 k=2.5 "进取版" | 2024-25 +40.26%, Sharpe 1.15, MDD -15.11% | 2024-2025 | README.md L595; docs/cost_aware_evaluation.json |
| C13 | Phase 19 纯结构趋势 "获批首要候选策略进 Forward Paper Testing" | 组合 +105.10% / +107.36%, Sharpe 1.27, MDD -22.19%/-25.26% | 2024-01~2026-09 (开发回测) | README.md L624, L653, L708; WALKTHROUGH.md L963-965 |
| C14 | Phase 20 ST-ChanTransformer | 已降级为"实验性科研原型", 不推实盘 | — | README.md L640, L709 |
| C15 | 截面轮动+双重门控+熊市套利 【推荐】 | 训练期 +31,914.64% (CAGR 288.70%, MDD -39.20%); 2025 +13.79%; 2026 +12.64%; 全周期 +40,945.98% (CAGR 174.95%) | 2020-10~2026-09 | README.md L19-21; CROSS_SECTIONAL_ROTATION_IMPLEMENTATION_PLAN.md L6-7, L59-99 |
| C16 | 20X 杠杆研究: "两套真正跑出正期望的机构级架构" | Core 套利 CAGR 10.32%, Sharpe 10.65, MaxDD 0.18%; Hybrid +43.72%/6年, Sharpe 1.80 | 2020-2026 | leverage_research/README.md L46-53, L60-65 |
| C17 | 实盘看板架构 | "ETH 3x 杠杆突破做多 + 100% Delta-Neutral Carry" | 实时 | README.md L14 |
| C18 | Phase 24 分级建仓+浮盈 booster | 样本内 SOL +4,046.82%~+4,181.52%; 但 Sharpe 全线持平或下降 | 2021-2025 样本内 | docs/tiered_booster_benchmark.json |

## 二、互相矛盾之处

### A. 致命矛盾: 同一时段同一策略族, 不同代数字相差 13 倍
- 2024-2025 区间 ETH: C1 宣称 +152.88% vs C11 metrics.json +11.86% (试盘) / -5.91% (裸)。SOL: C2 +183.66% vs +11.86% / -5.91%。README 顶部 Q1/Q2 与杠杆表(C5/C6)全部构建在被 Phase 16/17 取代的第一代单资产引擎上。
- Section 15 归档声明 (L729) 只隔离了 Phase 13 的 +67.57%/+105.92%, **并未隔离 Phase 5/11 单资产多头数字 (+152.88%/+183.66%)**——但这两套数字同样不可能与 metrics.json 共存。杠杆表 (+281.55% 黄金推荐) 的 1.0x 底座正是这套未被明示废止的旧数字, 却仍以 ⭐⭐⭐⭐⭐ "最优" 出现在正文第 3 节。

### B. Phase 13 同一引擎存在三个互相矛盾的版本
+67.57%/+105.92% (L256) vs +102%/+141% (L313 Quickstart 命令注释) vs +102.20%/+141.47% (L732 归档)。Quickstart 至今引导用户复现一套既与正文表不一致、又已被隔离的数字。

### C. README Phase 17 "Verified" 表与 metrics.json 不符 (单一数据源承诺失效)
- 全历史试盘 MDD: README L93 写 -18.93%, metrics.json `trial_trading.full_history.portfolio_max_drawdown_pct` = **-26.52%**。
- 全历史裸基线: README 写 -21.82% / -22.45%, metrics.json raw_baseline.full_history 仅为 -11.81% / -11.88% (直接复制了验证集数字, 并非全历史实测)。
- 2026 与 2025-10 的裸基线在 metrics.json 中**全为 0 (0 笔交易)**, 而 README 宣称 -11.35% / -4.48%。即 README 发布的裸基线数字在"唯一真理源"中不存在。
- 2026 单资产: README -4.43% vs JSON -3.36%; 2025-10: README -0.42% vs JSON -0.47%; 全历史单资产: README +6.91% vs JSON +8.08%。
- metrics.json 中 ETH 与 SOL 在所有时段的所有指标完全相同 (11.86/-11.40/0.78/0.51; -3.36/-5.41/-1.36...), 物理上不可能, 说明"单资产列"实为组合级数字的复制。
- L510-511 宣称 CI/CD 自动校验"彻底杜绝数据口径分叉", 上述差异证伪该承诺。

### D. 术语倒退: 截面轮动文档重新使用已被废止的"盲测"定性
README L269 与 L734 明确将 2026 正名为"事后开发与压力测试区间" (因调参已参考 2026 数据)。但最新的 CROSS_SECTIONAL_ROTATION_IMPLEMENTATION_PLAN.md L6 与 L73 再次称 2026 为 "blind test / 盲测期"。同一仓库内新旧文档对同一样本的定级互相冲突, 且新文档用的是更宽松的旧定性。

### E. Phase 19 同一策略两套"单一数据源"数字漂移
trend_vs_transformer_benchmark.json: ETH +122.41% / 组合 +105.10% / 62 笔; structural_trend_clean_benchmark.json 与 model_incremental_value.json: ETH +126.36% / 组合 +107.36% / 64 笔 (README L618 vs L647/L653 两处并列引用, 未注明差异)。

### F. 实盘配置与自有风控建议冲突
README L14 实盘看板运行 "ETH 3x Leverage", 而 L173 自有杠杆表将 ETH 3.0x 标注 "⚠️ 回撤接近 -50%, 不建议实盘", SOL 2.0x+ 标注 "存在清算风险/严禁"。

### G. 消融实验与叙事自相矛盾
ablation_study.json: S1=S2=S3, 即 FNG 情绪过滤与资金费率过滤**贡献严格为零**; 全部 Alpha 来自 144 EMA 趋势过滤 (S4)。但 README L72 将 2026 翻身归因于"基差/资金费/价差扩维", L39 将多模态链上/情绪增强列为核心创新。

### H. 项目自身的严格检验证伪了顶部标题结论
- block_bootstrap.json: 总收益 95% CI [-16.06%, +106.75%], **P(跑赢买入持有) = 50.75%** —— Phase 17 系统相对 B&H 无统计显著优势, 与 C1-C4 的"最优/dominates"措辞不可调和。
- purged_walk_forward.json: 5 个半年窗中 3 个亏损 (2024H2 -8.18%, 2025H2 -11.55%, 2026 -6.09%); 且该文件实为连续推演的半年切片, 无重训练、无 purge/embargo, "Purged Walk-Forward" 命名夸大严谨性。
- model_incremental_value.json: 随机置换安慰剂门控 (+104.34%) 跑赢真实模型门控 (+80.73%); 2026 Rank IC ETH -0.3603 / SOL -0.1748。这直接推翻 README 顶部 "Transformer 在 ETH/SOL 上表现最佳" 的 Q1 回答, 而 Q1 仍原样悬挂。

### I. 20X 杠杆研究的隐藏对照
leverage_research 同表显示 ETH 1x 买入持有 6 年 +1,643.50%, 而两套"机构级落地架构"仅 +92.44% (Core) 与 +43.72% (Hybrid); Sharpe 10.65 / MaxDD 0.18% / Calmar 58.40 的资金费套利数字超出合理物理边界 (意味着 6 年几乎无回撤日), 未交代资金费翻转、交易所风险与借币容量假设。

### J. Phase 24 booster 的无结论状态
tiered_booster_benchmark.json 仅为 2021-2025 样本内研究: booster 提升总收益但 SOL/ETH/BNB 的 Sharpe 全线持平或下降、MDD 扩大, 2026 压力期多数为负; 单纯的分数分级建仓在 BTC (+61.5% vs +75.3%) 与 SOL (+3,267% vs +4,358%) 上跑输全仓基线。README/WALKTHROUGH 未收录任何判定, 属未归档的最新一代实验。

### K. "获批进 Forward Paper Testing" 的实际进度
forward_paper_weekly.json: 服务仅运行 3 次, 仅 1 笔已平仓交易 (ETH, 追踪止损 -3.53%), 组合权益 1.0、收益 0.0%。即 C13 的"获批首要候选"至今没有任何前向实证支撑, 全部依据仍为开发回测。

## 三、+31,914.64% / CAGR 288.70% 的构成核验
- 算术自洽: 320.1464 倍复利, 4.25 年年化 = 288.59% ≈ 宣称 288.70% ✓; 三期链式复利 320.15×1.1379×1.1264 = 410.35 倍 ≈ 宣称 +40,945.98% ✓; 全周期 CAGR 174.9% ≈ 174.95% ✓。
- 构成: 无杠杆 Top-1 轮动 (100% 仓位) + 熊市 50% 现货/50% 1x 永续空头 carry (max(0,FR)×0.5), 双边 16 bps 摩擦, 4h 次根开盘成交。
- 关键定性问题: **该数字出自文档自行标注的"训练期 Training (2020-10 至 2024-12)"**, 即门控参数 (EMA200 双重门控、BB120 Z-score + Mom20D 打分、Top-1 规则) 的样本内区间。样本外立即崩塌: CAGR 288.70% → 2025 的 13.84% → 2026 的 18.59%; Sharpe 2.10 → 0.52 → 0.65。收益高度集中: 2021 单年 +2,307.81%, 且 2021 切片 MDD (-39.1994782%) 与整个 4.25 年训练期 MDD 完全相同至 10 位有效数字, 说明全期最大回撤整体发生在 2021 年内。
- 结论: 数字本身无算术造假, 但 README L19-21 把样本内 288.70% CAGR 放在首页头条、用 "solves the crypto correlation trap" 式完成时陈述, 而样本外仅 +13.79%/+12.64% 的真实可期待水平排在从句位置, 构成严重的展示性误导; 叠加 D 条 (重新使用"盲测"措辞), 该文档不符合仓库自己 Phase 17/21 建立的审计标准。

## 四、宣称的验证纪律是否真实
| 纪律 | 真实性判定 |
|------|-----------|
| 参数邻域稳定性 (parameter_stability.json) | ✅ 真实: 7/7 网格正收益 (+8.37%~+30.79%), Sharpe CV 22.25%, 支持"高原非尖峰"结论 |
| 成本容量压力 (cost_capacity_stress.json) | ✅ 真实且诚实: 盈亏平衡 ~15 bps, 20 bps 即转负 |
| Block bootstrap | ✅ 数据真实, 但其结论 (P>0=86.9%, 跑赢 B&H 仅 50.75%) 实际削弱"最优"叙事, README 未做此解读 |
| Purged walk-forward | ⚠️ 名不副实: 无重训练无 embargo 的半年切片, 且 3/5 窗口亏损 |
| 8 阶段消融 | ✅ 真实, 但暴露 FNG/资金费过滤零贡献 (见 G) |
| 模型增量价值消融 (含安慰剂对照) | ✅ 真实且严格, 但其结论是否定性的 (安慰剂跑赢模型) |
| metrics.json "单一数据源 + CI 校验" | ❌ 部分失效: 裸基线 2026/10 月全零、全历史 MDD 与 README 不一致、ETH/SOL 列完全相同 (见 C) |
| Forward paper testing | ⚠️ 名义存在, 实际 3 次运行 1 笔亏损交易, 无证据力 (见 K) |

## 五、最终结论

**项目当前真正认可的"最优"**: 以 WALKTHROUGH L963-965 与 README L707-709 的最终定级为准 —— **Phase 19 纯结构趋势跟踪 (120-bar 布林动态突破 + 3×ATR 移动止损 + EMA200 宏观定仓)**, 2024-01~2026-09 开发回测组合 +107.36% / Sharpe 1.27 / MDD -25.26%, 是唯一通过全部 8 项去偏差审核并获批冻结参数前向模拟的策略。4h 时空 Transformer (C11) 已被自家消融与安慰剂检验降级; ST-ChanTransformer 明确降级为实验原型。

**已过时但仍占据显眼位置、误导读者的声明**:
1. README 顶部英文 Q1/Q2 (C1-C4): +152.88%/+183.66%/Sharpe 2.09 "最高质量/最高 Alpha/dominates" —— 与被奉为真理源的 metrics.json (+11.86%) 差 13 倍, 未被隔离标记覆盖;
2. 中文第 3 节杠杆 "黄金推荐/最优推荐" 表 (C5/C6): 建立在上述旧数字之上的线性杠杆放大, 且未建模清算与资金费拖累;
3. Quickstart L313 的 "+102%/+141%" (C8);
4. 英文 Section 3 的 2026 +17.33%/+15.48%/+12.60% (C10): 无代际标注, 与 Phase 17 的 -6.09% 并列于同一 README;
5. 首页头条的截面轮动 +31,914.64% (C15): 算术真实但为样本内数字, 且文档违规复用"盲测
"定性; 其诚实的读法应是 "样本外年化 ~14-19%, Sharpe ~0.5-0.65";
6. 实盘看板 ETH 3x (C17) 与自有杠杆风控建议直接冲突。

**给维护者的最低修复建议**: (i) 将 C1-C6、C8、C10 全部移入 Section 15 归档或加注 "superseded by metrics.json"; (ii) 修复 metrics.json 的裸基线零值与全历史 MDD, 或修正 README 表; (iii) 截面轮动文档将"盲测"改为"事后压力测试", 并把样本外 +13.79%/+12.64% 提升为头条数字; (iv) 统一 trend_vs_transformer 与 clean benchmark 两套 Phase 19 数字或注明口径差异; (v) 在 leverage_research 中对照披露 B&H +1,643% 的绝对收益差距。
