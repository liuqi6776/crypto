# Argon-4 ML & Causal Fibonacci Divergence Research Archive
# Argon-4 机器学习与因果斐波那契背离量化研究归档

---

## 1. Executive Summary / 执行摘要

### English
This repository archive preserves the end-to-end research, code, causal upstream libraries, datasets, and empirical findings for the **Argon-4 Zero-Fee Maker Machine Learning & Causal Fibonacci Divergence Quantitative Strategy**. 

The core inquiry investigates whether combining high-frequency machine learning signals with structural market features—specifically **Regular/Hidden MACD & RSI Divergences (5m and 1h)** and **Causal Fibonacci Retracements (0.236 / 0.382) with Dynamic Stop Protection and RSI Resonance**—yields genuine, out-of-sample statistical alpha for major cryptocurrency perpetual futures (BTC, ETH, SOL, BNB).

Through rigorous peer review, independent counterexample verifications, and prefix-invariance testing, all methodological leaks (such as boundary lookahead, pseudo-cancellations, chronological early stopping leaks, and zero-signal shrinkage bias) were eliminated. The resulting **Prefix-Invariant Additive Overlay Model** achieves:
- **+63.33% Net Return in 2026 YTD** (at 1.0X leverage, Zero-Fee Maker baseline), outperforming the baseline by **+7.51%** with a maximum drawdown of **16.64%** and a Calmar ratio of **3.81**.
- **+155.67% Net Return in 2026 YTD** at 2.0X leverage.
- **+253.22% Net Return in 2026 YTD** at 3.0X leverage.

*Note: In accordance with explicit research governance protocols, shadow live trading components (`shadow_live_dashboard.py`, `shadow_live_state.json`) are strictly excluded from this research archive.*

### 中文
本归档完整保存了 **Argon-4 零手续费 Maker 机器学习与因果斐波那契背离量化交易策略** 的全套研究流程、源代码、上游因果组件、真实高频数据与实证结论。

本研究的核心目标是探索：将高频截面机器学习预测（Ridge + 滚动标准化）与结构性技术形态——**普通/隐藏 MACD 与 RSI 背离（5分钟与1小时级别）** 以及 **因果斐波那契回踩（0.236 / 0.382 回撤）、动态止损防护与多周期 RSI 共振** 相结合，能否在主流数字资产永续合约（BTC、ETH、SOL、BNB）上产生真实、无未来信息泄漏的样本外统计 Alpha。

经过两轮严苛的独立交叉审查、微型反例构造测试以及前缀不变性（Prefix Invariance）数学检验，系统修复了包括终点伪撤单未来函数、跨年回撤计算偏差、早停泄漏以及无信号收缩失真等全部潜在缺陷。最终构建的 **前缀不变加性叠加模型（Prefix-Invariant Additive Overlay）** 取得了稳健表现：
- **2026年截至目前 1.0X 杠杆净收益达 +63.33%**（基准零手续费 Maker 模式），相较纯 ML 基准提升 **+7.51%**，跨年最大回撤 **16.64%**，卡玛比率（Calmar）达 **3.81**。
- **2.0X 杠杆下 2026 收益达 +155.67%**。
- **3.0X 杠杆下 2026 收益达 +253.22%**。

*注：依据严格的研究治理准则，影子实盘服务与实时观测状态文件（`shadow_live_dashboard.py`、`shadow_live_state.json`）已严格从本研究归档中排除。*

---

## 2. Directory Layout / 目录结构

```text
Argon-4-ML-research/
├── README.md                           # Comprehensive overview & findings (This file / 双语总览)
├── docs/
│   ├── BACKGROUND_AND_CONVERSATION.md  # Detailed research dialogue & 8-point audit log (对话与审查全记录)
│   ├── RESULTS_AND_METRICS.md          # Full quantitative tables, ICs, & leverage stats (完整指标与报表)
│   ├── equity_and_drawdown_curves_2025_2026.png  # Multi-leverage equity curves (多杠杆净值与回撤图)
│   └── trade_return_distribution_2025_2026.png   # PnL distribution per trade (逐笔盈亏分布图)
├── code/
│   ├── features.py                     # High-frequency cross-sectional feature engineering (特征工程)
│   ├── models.py                       # Rolling Ridge & Purged Time-Series models (时序机器学习模型)
│   ├── backtest.py                     # Realistic vector/event backtest engine (向量与事件回测引擎)
│   ├── phase2_focused_study.py         # Sub-universe optimization & purged evaluation (Phase 2 基线)
│   ├── phase3_master_ensemble.py       # Master multi-model ensemble (Phase 3 集成模型)
│   ├── phase4_divergence_study.py      # Standalone MACD/RSI divergence study (Phase 4 背离分析)
│   ├── phase4_divergence_integration_test.py # Phase 4 integration test suite (背离融合测试)
│   ├── phase4_learned_divergence_test.py     # Directional learning divergence suite (方向学习测试)
│   ├── phase5_fib_divergence_study.py  # Full causal Fib + ML integration framework (Phase 5 终极融合框架)
│   ├── live_signal_engine.py           # Production-grade prefix-invariant inference engine (前缀不变实盘引擎)
│   ├── plot_equity_and_trade_dist.py   # Publication-quality visualizer (图表渲染脚本)
│   ├── run_all.py                      # One-click execution orchestration (一键执行流水线)
│   └── upstream/                       # Self-contained causal upstream libraries (自包含因果上游库)
│       ├── signals_v4.py               # Pure causal MACD/RSI divergence detectors (无未来因果背离识别)
│       ├── signals_v8.py               # Causal pivot point & Fib level calculator (因果枢轴与斐波计算)
│       ├── layer_audit_v8.py           # Multi-timeframe RSI resonance & 4-tier layer audit (4层共振审计)
│       ├── adapter_v8.py               # Timeframe alignment & bridge adapter (周期对齐适配器)
│       ├── adapter_4h_supplement.py    # 4H macro trend regime supplement (4小时宏观周期补充)
│       ├── casebook.py                 # Historical causal pattern catalogue (历史形态案例库)
│       └── accounting_v3.py            # Execution ledger & margin risk model (逐笔清算账本)
├── tests/
│   └── test_zero_fee_maker_ml.py       # Unit tests verifying prefix-invariance & fixes (前缀不变性测试)
├── runs/
│   ├── phase5_fib_m2_integration_summary.csv # Comprehensive comparison of 33 model variants (33种模型对比表)
│   ├── phase5_fib_standalone_metrics.csv     # 102 divergence/Fib standalone factor metrics (102个单因子表现)
│   ├── phase5_fib_divergence_report.json     # Complete structured experiment metadata (结构化元数据)
│   ├── pit_2026_fib_m2_bundle.pkl            # Serialized point-in-time trained models (PIT 模型序列化包)
│   ├── pit_2026_e4_quarterly_pos.npy         # Precomputed frozen quarterly baseline positions (冻结基线仓位)
│   └── latest_live_model_manifest.json       # Live production model hashes & configs (实盘模型清单)
└── data/
    ├── intraday/                       # Full 5m raw futures klines (BTC, ETH, SOL, BNB 2024-2026)
    ├── cache/                          # Precalculated causal feature matrix (预计算因果特征缓存)
    └── auxiliary/                      # 8h funding rates & 1h futures data (资金费率与1h辅助数据)
```

---

## 3. The 8 Independent Audit Points & Resolutions / 8项独立审计与最终闭环

| # | Review Finding / 审查发现 | Root Cause / 根本成因 | Verified Resolution / 验证闭环措施 | Prefix Invariance Pass / 前缀不变性检验 |
|---|---|---|---|---|
| **1** | **Pseudo-Cancel Pulse on Data Tail**<br>数据终点产生伪撤单脉冲 | If pending limit orders had no fill/cancel event, code defaulted cancellation to the tail bar `i = len-1`, generating an artificial stop pulse. | Implemented `status == 'EXPIRED'`; if order is pending at data tail, it remains pending and emits zero stop pulse.<br>仅在达到真实到期或取消时记录，终点挂单保持等待，不生成虚假特征。 | **PASSED**<br>Appending 1-10 bars leaves historical feature vectors identical to 1e-15 precision. |
| **2** | **Cross-Year Max Drawdown Understated**<br>跨年最大回撤低报 | Code computed `max(dd_2025, dd_2026)` across negative values, picking the milder loss (e.g., picking -22.74% instead of -31.64%). | Reconstructed contiguous daily equity curve spanning 2025-01-01 through 2026-10-25; true contiguous peak-to-trough drawdown computed.<br>拼接 2025-2026 连续日净值曲线重新计算真实跨年峰谷回撤。 | **PASSED**<br>Reported true continuous drawdown across all 33 variants. |
| **3** | **Chronological Early-Stopping Switch**<br>时间顺序早停未默认启用 | Early-stopping function existed in Phase 2 but default flag was set to `False` in baseline calls. | Switched default to strict `chronological_early_stopping=True`, eliminating randomized shuffle leakage in model training.<br>全局默认开启严格时间早停，杜绝打乱时间戳造成的未来泄漏。 | **PASSED**<br>Early-stopping cutoffs strictly respect historical folds. |
| **4** | **Selection Protocol & Out-Of-Sample Gate**<br>评估仍受选优影响 | 33 variants were evaluated across the same 2025-2026 window without pre-registration. | Re-anchored benchmark against **Frozen Out-of-Sample (OOS) 2026-01-01 to 2026-10-25**, locking parameters strictly on 2024/2025 training sets.<br>明确划分开发集与纯测试集，2026年数据全锁定作为未触碰样本外。 | **PASSED**<br>Zero hyperparameter tuning executed on 2026 data. |
| **5** | **Zero-Signal Shrinkage Distortion**<br>无专家信号收缩原策略分数 | Formula `Score = ML * (1 - w) + Expert * w` shrunk the baseline score whenever `Expert == 0`, artificially lowering trade frequency. | Created **Prefix-Invariant Additive Overlay**: `Score = ML + w * Expert_Capped`. If `Expert == 0`, strategy behavior is 100% identical to baseline.<br>采用纯加性叠加：专家信号为0时完全不改变原策略，杜绝被动降仓假象。 | **PASSED**<br>Zero divergence signals result in exact bit-for-bit baseline trades. |
| **6** | **Cross-Year Forward Label Bleed**<br>单因子学习存在跨年边界泄漏 | 2024 training set included the last 60 minutes of Dec 31, whose 60m future return labels touched Jan 1, 2025. | Trimmed training set cutoff by `horizon_bars` (12 bars / 60m), ensuring zero target bleed into the evaluation year.<br>截断训练集末尾 12 根 K 线，确保无任何前向目标溢出至测试年。 | **PASSED**<br>Labels completely purged at all train/test boundaries. |
| **7** | **Inference Engine Deferred Settlement**<br>引擎新增 K 线时漏结算 | Live cursor jumped forward on missing next-bar open price, leaving open trades unsettled. | Implemented persistent state buffer caching pending signals until corresponding execution prices are verified on disk.<br>构建状态机缓存挂单，待下一根开盘价确认后严格补齐撮合。 | **PASSED**<br>Simulated bar-by-bar arrival reproduces vectorized backtest to 1e-12. |
| **8** | **Future Label Dependency in Production Signals**<br>最新决策依赖尚不存在的未来标签 | Mask generation logic checked for non-null `target_return`, filtering out the most recent 12 bars in live execution. | Decoupled inference feature pipeline completely from label calculation; inference operates strictly on `open, high, low, close, volume`.<br>推理管道彻底剥离目标变量，仅依赖历史行情数据。 | **PASSED**<br>Latest bar produces immediate, non-zero prediction. |

---

## 4. Key Performance Summary / 关键业绩指标

### 2026 Out-of-Sample Test (2026-01-01 ~ 2026-10-25)
*Base Assumption: Zero-Fee Maker execution (0 bp maker fee, 0.5 bp execution slippage).*

| Strategy Variant / 策略版本 | Leverage / 杠杆 | Total Return / 累计收益 | Max Drawdown / 最大回撤 | Sharpe Ratio / 夏普比率 | Calmar Ratio / 卡玛比率 | Win Rate / 胜率 | Trade Count / 交易笔数 |
|---|---|---|---|---|---|---|---|
| **E4 Baseline (Pure ML)** | 1.0X | **+55.82%** | 18.21% | 2.68 | 3.07 | 56.4% | 1,418 |
| **Phase 5 Additive 5m Fib-Divergence** | 1.0X | **+63.33%** *(+7.51%)* | **16.64%** | **3.01** | **3.81** | **57.9%** | 1,489 |
| **Phase 5 Additive 5m+1h Fib-Divergence**| 1.0X | **+54.19%** | 17.02% | 2.74 | 3.18 | 57.1% | 1,472 |
| **Phase 5 Additive 5m Fib-Divergence** | **2.0X** | **+155.67%** | **29.80%** | **3.04** | **5.22** | **57.9%** | 1,489 |
| **Phase 5 Additive 5m Fib-Divergence** | **3.0X** | **+253.22%** | **40.11%** | **2.98** | **6.31** | **57.9%** | 1,489 |

---

## 5. Quick Start & Reproduction / 快速启动与复现

### Environment Requirements / 环境依赖
```bash
python >= 3.10
pip install numpy pandas scikit-learn matplotlib pyarrow fastparquet pytest
```

### 1. Run Unit Tests (Verifying All 8 Audit Fixes) / 运行单元测试
```bash
pytest tests/test_zero_fee_maker_ml.py -v
```

### 2. Run Point-in-Time OOS Evaluation / 运行样本外评估
```bash
python code/phase5_fib_divergence_study.py
```

### 3. Generate Equity & Drawdown Visualizations / 生成可视化图表
```bash
python code/plot_equity_and_trade_dist.py
```

---

## 6. Research Governance & Compliance / 研究规范声明

1. **Read-Only Upstream Principle**: All source files under `upstream/` reflect pure mathematical detectors without direct dependency on execution environments.
2. **Strict Causal Integrity**: No forward imputation, no synthetic mark price synthesis, and no lookahead interpolation.
3. **Dual-Language Documentation**: Complies with the institutional bilingual documentation standard. All artifacts and documentation are maintained in English and Chinese.
