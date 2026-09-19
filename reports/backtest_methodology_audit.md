# 加密量化回测方法论审计报告（Thorough 级）

审计对象：C:\Users\liuqi\crypto（核心代码 crypto_quant/）
审计日期：以当前会话为准；代码基线 commit 7955834
审计范围：前视偏差、数据泄露、成交/成本假设、杠杆建模、指标口径、测试因果性

---

## 一、严重问题（Critical）——足以推翻 headline 结论

### C1. 招牌数字 +152.88% / +183.66% 是"验证集内"数字，不是盲测样本外
证据链：
- `crypto_quant/train_transformer.py:160-188`：每个 epoch 在 2024-2025 验证集上算 RankIC，
  `val_score = eth_ric*0.5 + sol_ric*0.3 + btc_ric*0.2`（:167），
  以此做 checkpoint 选择 + 早停（:171-188）——**2024-2025 全程参与模型选择**。
- `crypto_quant/evaluate_frequencies.py:3-4` 自述："严格在 2024-2025 验证集上运行 15 组网格评测"——
  标的（ETH/SOL）与频率（Adaptive 12h）也是在同一区间网格选出（`data/grid_evaluation_2024_2025.csv`）。
- `README.md:44` 自述 "Validation & Hyperparameter Tuning: 2024-01-01 to 2025-12-31"。
- `crypto_quant/train_transformer.py:224-227` 把 val 预测与 2026 盲测预测拼成 `test_predictions.parquet`；
  `crypto_quant/backtest_transformer.py:197` 随即打印
  `OUT-OF-SAMPLE 2.7-YEAR PERFORMANCE COMPARISON ... (2024-2026)`——
  把"调参集"与"盲测集"合并冠以统一的 Out-of-Sample 名义。
- 已用 DuckDB 实测：`predictions/test_predictions.parquet` = 2023-12-31 → 2026-09-13（5923 根），
  其中前 4386 根与 `val_predictions_2024_2025.parquet` 完全重合。
影响评估：+152.88%/+183.66%/Sharpe 2.09 经受了"早停选模 + 选标的 + 选频率"三重选择偏差，
统计上应视为**训练集延伸**，预期实盘大幅衰减。真正未被触碰的只有 2026 区间，
而 README:89 显示该区间 Trial Mode 为 **-6.09%（Sharpe -1.34）**，且 README:269 自己承认
2026 后来也被用于规则调整（"不再称为盲测，正名为事后开发与压力测试区间"）——
即**该项目目前不存在任何未被开发过程触碰的样本外区间**。

### C2. 热启动权重来源不可审计，疑似把验证集信息泄漏进"2020-2023 样本内"权重
- `crypto_quant/train_transformer.py:111-125`：`warm_start=True` 默认从
  `checkpoints/best_crypto_transformer_augmented.pt` 迁移 29 维特征权重。
- git 溯源：该二进制在初始提交 b25e82c 中作为成品入库，**仓库内不存在生成它的训练脚本**，
  其训练区间、早停数据集均无法验证。若它（大概率）用同一管线在 2024-2025 上早停，
  则 val 信息经由权重迁移进入名义上"2020-2023 纯样本内"的模型。
影响评估：三段式切分的"Train 纯净性"不可证明；ML 审计角度这是致命的可追溯性缺口。

### C3. 杠杆回测为朴素倍数乘法，无强平/维持保证金/真实资金费
- `crypto_quant/analyze_leverage.py:138-143`：
  ```python
  cost_bar = trade_signals * 0.0005 * lev
  funding_bar = pos * 0.00005 * max(0.0, lev - 1.0)   # 只对超出 1x 部分收"固定"资金费
  strat_rets = (pos * rets_oto * lev - cost_bar - funding_bar)[:-2]
  ```
  收益直接 ×3，无清算价检查、无逐 bar 保证金率校验；且 1x 时 funding_bar=0，
  即基准杠杆倍数下资金费为零。单笔层面又用固定 `duration_bars * 0.00005`（:96），
  与逐 bar 口径互相不一致。
- README:170-182 的杠杆推荐表（"为什么可以加杠杆？89.2% 空仓……"）全部建立在此模型上；
  而 `tests/test_leverage_and_funding.py` 证明项目其实有正确的强平价公式
  （3x 强平距离 ~32.8%），却未用于该分析。ETH 4h 级别单日 -20% 并不罕见，
  3x 下净值回撤与强平路径被系统性低估。
影响评估：所有杠杆结论（含"自身 Beta 弹性已足够高"的反向结论）均不可用于实盘决策。

---

## 二、中等问题（Moderate）——方向性扭曲业绩

### M1. 主回测（backtest_transformer.py）完全没有资金费率成本
- 全文 0 处 funding 引用；唯一摩擦是 `taker_cost = 0.0005`（:116），按仓位变动收取。
- 策略一/二持有 ETH 永续多头、策略三持有轮换多头，永续持仓的资金费全部免费。
  以平均 0.01%/8h、~11% 在场时间估算，年漏计成本约 1.2%/年；牛市资金费尖峰期
  （恰是模型做多信号密集期）漏计更多。README:182 反而用"资金费微乎其微"为杠杆背书。

### M2. 止损假设在旧引擎中为 Close 触发 + 次根 open 无滑点退出，方向性偏乐观
- `crypto_quant/dual_sleeve_portfolio.py:187-192`：`gross_ret = curr_c / entry_p - 1.0`，
  仅当**收盘价**跌破止损才出场，出场价 `opens.iloc[i+1]`（:198）只扣固定 0.08% 费用，
  无跳空滑点、无 intrabar 触发。4h K 线插针穿越止损后收回的情形全部被判为"未止损"。
- 同样模式：`structural_trend_engine.py:225`、`tiered_booster_engine.py:196`、
  `chan_transformer_engine.py:197`。且这三者用 **intrabar high 收紧移动止损**（如
  structural:216-220 `peak_price_since_entry = max(..., curr_h)`）却只用 close 判定触发——
  收紧用最高价、触发用收盘价，两种口径混用，系统性减少止损次数。
- 对照组：`execution_model.py:45-98` + `continuous_backtest.py` + `portfolio.py` 有正确的
  intrabar high/low 触发 + 跳空保守成交价（gap_slippage 0.15%、stop_slippage 0.10%），
  说明项目知道正确做法，但产生 headline 数字的旧引擎未采用。

### M3. 资金费率数据时区处理 bug（8 小时错位）与跨脚本不一致
- 实测 `data/binance_funding_8h.parquet` 与 `binance_basis_4h.parquet` 索引带
  `Asia/Shanghai (+08:00)` 时区；`dataset_builder.py:217/222/227` 用
  `tz_localize(None)` 直接剥时区 → 实际 UTC 00:00 结算的资金费被贴到 naive 08:00 的 bar 上，
  与 UTC 4h K 线错位 8 小时。
- 而 `scripts/run_purged_walk_forward.py:41-42` 对同一文件用 `tz_convert(None)`
  （正确换算为 UTC）。同一数据源两套对齐方式，不同引擎的资金费/基差/OKX 价差特征
  实际吃到的是不同时刻的数据。
- 方向：错位使特征滞后 8h（偏保守，非前视），但结算时间错位 + `execution_model.py:100-107`
  只认 naive 0/8/16 点为结算时刻，实测有 75/6779 条结算记录落在其他偶数小时被直接丢弃。
影响评估：非泄露型 bug，但使 funding 成本建模在量级与时间上均不可靠。

### M4. run_9yr_backtest.py / backtester.py：信号 close 成交近似（隐性前视半根 bar）
- `crypto_quant/backtester.py:79-93`：`positions = raw_signals.shift(1)` 后乘
  `close.pct_change()`——信号在 close[t] 产生，却赚取 close[t]→close[t+1] 收益，
  等价于假设恰好以产生信号的那根收盘价成交，忽略了 close→next open 的跳空。
  注释自称"下一根 Open 执行"，但估值用的是 close-to-close，口径自相矛盾。
  9 年日线趋势策略的换手成本高估/低估取决于跳空方向分布，结果只能算粗略研究级。

### M5. 跨资产轮换换手费低估一半
- `backtest_transformer.py:163`：A→B 换仓只扣单边 `taker_cost`（0.05%），
  实际是"卖 A + 买 B"两笔 taker = 0.10%。轮换策略交易频繁，长期复利下不可忽略。

---

## 三、轻微问题（Minor）

- `portfolio.py:140`、`dual_sleeve_portfolio.py:95`：`atr14 = tr.rolling(14).mean().bfill()`——
   warmup 期用未来 ATR 回填（仅影响前 ~14 根 bar 的仓位系数，量级小）。
- `dataset_builder.py:186` 的 4h 管线 Train/Val 边界无 purge/embargo（target_ret_8h 跨边界 2 根 bar，
  可忽略）；缠论波形管线 `prepare_chan_wave_datasets`（:368-502）有完整 purge 72 bars +
  embargo 18 bars，做法规范。
- `dataset_builder.py:116-119` 基差特征无显式 lag（同 bar close 计算、次根 open 执行，因果成立）；
  链上 TVL 依赖 DefiLlama 日度快照，存在事后修订风险，shift(1) 只能缓解不能消除。
- `backtest_transformer.py:57-61` 胜率/盈亏比只在非零收益 bar 上计算，属展示口径问题。

---

## 四、做对了的部分（应给予肯定）

1. **执行时序因果性真实可靠**：`continuous_backtest.py` 信号在 bar t close 生成 →
   pending order → t+1 open 成交；z-score 滚动窗口在信号生成时点尚未 append 当期预测
   （:226-232 先于 :579 的 buffer 更新）；EMA/ATR 均 lag 一根 bar。
   `tests/test_execution_timing.py` 对 off-by-one 有显式断言。无 off-by-one 前视。
2. **归一化无全样本泄露**：`dataset_builder.py:273-277` scaler 严格只用 Train 段拟合并 ±5 clip。
3. **日频外部数据 PIT 对齐规范**：`data_aligner.py` 的 1 日 lag + ffill 有
   `tests/test_feature_availability.py` 专门验证；宏观美股/链上/FNG 均为 D-1 数据，因果成立。
4. **缠论分型特征不重绘**：`chan_features.py:50-54` 分型确认滞后 1 根 bar，无未来函数。
5. **89.2% 空仓的夏普口径**：`backtest_transformer.py:42-45` 提供日频重采样夏普，
   正确处理了空仓零收益对 4h 逐根夏普的稀释问题——该质疑点在代码中已被妥善解决。
6. **测试规模真实**：tests/ 下 89 个测试函数，覆盖执行时序、intrabar 止损、跳空滑点、
   资金费结算、重启等价性、纸交易幂等等，且 README:269 对 2026 区间降级表述是诚实的。

---

## 五、结论

**该回测框架未达到实盘可信度。**

分层来看：
- **执行引擎层**（continuous_backtest / portfolio / execution_model，Phase 16-17）：
  因果时序、止损建模、状态持久化均达到较高工程严谨度，可复用。
- **研究结论层**：不达标。招牌业绩数字产生自被三重调参（早停选模、网格选标的/频率、
  风控规则迭代）反复使用的 2024-2025 验证集，唯一相对干净的 2026 区间亏损且事后也被纳入开发，
  热启动权重来源不可审计——三个 ML 审计致命伤叠加。
- **成本层**：主回测无资金费、杠杆分析无强平、旧引擎止损偏乐观、换手费低估，
  全部指向同一方向——**系统性高估收益、低估回撤**。

若要达到实盘可信度，最低限度需要：(1) 封存一个此后永不触碰的前向区间重新出数；
(2) 用仓库内可复现的脚本从头训练、消除热启动黑箱；(3) 主回测接入真实 funding 序列与
execution_model 的 intrabar/跳空止损；(4) 杠杆分析接入 LeverageModel 强平校验。
在此之前，所有业绩数字只能视为研究方向性参考，不能作为资金部署依据。
