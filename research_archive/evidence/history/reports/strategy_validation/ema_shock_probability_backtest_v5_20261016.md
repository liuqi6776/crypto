> Sanitized historical evidence. Historical values are preserved; original wording may be superseded by canonical corrections.

# EMA 三线排列 + 放量概率：扣费回测审查

**范围：2025 年、BTC/ETH/SOL/BNB 的 USDT 永续，1 小时频率；全部为 EXPOSED/REUSED 历史研究。**

主规则 P50 的净盈亏为 **-1,225.50 USDT（-12.25%）**；压力成本下为 **-1,641.67 USDT（-16.42%）**。
相对仅 EMA 的净盈亏变化是 +2,190.25 USDT。相对改善与绝对盈利是两个条件；本次预先冻结的继续研究筛选结果为 `FAIL_ONE_OR_MORE_FROZEN_CONDITIONS`。

## 身份、事前规则和数据

| 项目 | 记录 |
|---|---|
| 策略 / 版本 | ema_shock_probability_backtest_v5；共享 v8 研究入口 |
| 假说 | 已对齐的 EMA 提供方向；未来 6 小时内再次放量的概率筛选入场，不把放量概率解释成上涨概率 |
| EMA | 7/20/99，SMA 初始化；EMA20 的 6 小时变化 / ATR14 >0.25 且三线多头排列为上，<−0.25 且空头排列为下，其余为中性 |
| 放量定义 | 单小时成交量 / 过去 8 周相同 UTC 星期和小时成交量的中位数 ≥3；预测未来 6 小时至少发生一次 |
| 概率模型 | 沿用 v4 冻结的 z_mean_24 / shock_6 / 2025 EMA_FEATURE；每币训练分箱和概率单元；不重训、不调阈值 |
| 入场 / 出场 | 三线形成同向状态后等待概率达标，每段最多入场一次；概率下降不平仓；转中性或反向时退出 |
| 主规则和敏感性 | P50 为唯一主规则；P40/P60 预先规定，仅作敏感性；不按收益选优 |
| 训练 / 评价 | 冻结模型训练起点 2021-01-01 00:00 UTC，最后训练起点 2024-12-31 17:00 UTC（含）；最后标签成熟于 2024-12-31 23:00:00.001 UTC；140,232 个训练行。经济窗口 UTC 2025-01-01,2026-01-01)；没有 untouched OOS |
| 本版本验证 / 寻优 | N/A；沿用冻结模型，不新增训练或验证期优化，3 个固定阈值全部报告 |
| 已看过的数据 | 2023–2025 概率结果、2025 EMA 收益及旧研究；不能重命名为独立测试集 |
| 决策 / 成交 | 特征模型可用时间 origin+1 ms；决策 origin+2000 ms；之后第一个真实 H1 开盘价加逆向滑点，模拟成交于该开盘+1001 ms |
| 延迟解释 | 普通信号有一小时参考开盘延迟；非真实成交回放；边界资金费保留原始事件时间 |
| 资金配置 | 初始 10,000 USDT；1×；4 个固定等额槽位，合计初始资本 40% 名义配置；不复利加仓，持有数量不重平衡 |
| 费用 | 双边各 0.05%；滑点基准双边各 0.02%，压力双边各 0.10%，嵌入成交价一次 |
| 资金费 | 原生结算时间和利率逐笔保留；现金流 = −持仓数量 × 当时已可用的真实 mark 收盘代理 × 利率；并非精确交易所结算价 |
| 容量 / 保证金 | 成交额不超过决策已知小时 quote volume 的 1%；维护保证金 0.5%、清算费 0.2% 为场景参数；非盘口容量或真实分档强平模型 |
| 年末处理 | 12 月 31 日 23:00 参考开盘，23:00:01.001 平仓；之后不开仓 |
| 审查 | Codex 独立复算；GPT-6 Luna high 实现；2026-10-16 |

[冻结协议 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3CSOURCE_ROOT%3Acrypto-leverage%3E/docs/EMA_SHOCK_PROBABILITY_BACKTEST_V5_PROTOCOL_20261016.md`)；执行前哈希、参数与来源身份 (`provenance:external/fc6eec042d2b21c1`)；来源审计 (`provenance:external/cd7aa5949fa6dd74`)；结果文件 SHA256 清单 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/research_platform_v8/runs/ema_shock_probability_v5_20261016_reviewed/artifact_manifest.json`)。

## 全部收益结果

| 入场规则 | 基准净收益 | 压力净收益 | 基准最大回撤 | 平仓交易数 | 胜率 | 利润因子 |
|---|---:|---:|---:|---:|---:|---:|
| 仅 EMA | -34.16% | -54.60% | -37.43% | 1278 | 29.50% | 0.736 |
| EMA + 放量概率 ≥40% | -13.91% | -18.66% | -16.79% | 297 | 32.32% | 0.618 |
| EMA + 放量概率 ≥50%（主规则） | -12.25% | -16.42% | -15.73% | 260 | 31.92% | 0.632 |
| EMA + 放量概率 ≥60% | -6.37% | -8.45% | -9.92% | 130 | 32.31% | 0.637 |

扣费净值比较 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/ema_shock_probability_backtest_v5_20261016/equity_comparison.png`)核对原始数据、模型输入、全部成交和 2025 原生资金费；实际源发布时间与执行延迟未证实 |
| 2 实现、前视与递归 | NOT_RUN | 新逻辑审查、合成测试、独立账本检查已做；此共享账户模型并非 Freqtrade 策略，原生 lookahead/recursive 工具未运行 |
| 3 机制与搜索披露 | FAIL | 冻结的 P50 继续研究筛选；仅 2025 探索性经济检验，全部阈值如实报告 |
| 4 未触碰滚动 OOS | BLOCKED | 2023–2025 历史已看过，缺少真正未使用的未来验证窗口 |
| 5 费用、资金费与成交现实 | BLOCKED | 八组双边费用/逆向滑点/原生资金费完整对账；缺少真实盘口、成交、源延迟和精确结算 mark |
| 6 市场状态、币种和参数稳健性 | FAIL | 四币、三概率阈值、两组成本和入场市场状态；仅一年，不构成多周期独立验证 |
| 7 杠杆、保证金与强平 | BLOCKED | 仅 1× 下已观测 mark 极值场景；非交易所分档清算，不外推 2×/3×/5× |
| 8 模拟运行观察与对账 | NOT_RUN | CLI 的 dry-run 仅为零写入校验，不是实际交易观察 |
| 9 小资金实盘观察 | BLOCKED | 无实盘证据；工作区禁止实盘 |

**Verdict：FAIL。研究属于 EXPLORATORY；没有证明可交易有效。**

## 复核和可复现文件

独立复算通过 8 个场景，复核 184,128 行原始小时特征和 35,016 个既有概率，完整生成 35,040 个 2025 决策时点预测；最后 24 个预测无需未来标签。EMA_ONLY 复现原 v3 的固定 EMA 基准。
独立账本审计 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/ema_shock_probability_backtest_v5_20261016/independent_backtest_audit.json`)；等待、状态和阈值构成复核 (`provenance:external/d06c21f82cb5a2cb`)；全部指标 (`provenance:external/41e3df2e3bb6dc74`)；等待、入场和退出记录 (`provenance:external/26462108052bf186`)；审查过程 (`provenance:external/209fa299e22e1e53`)。

专项测试：29 passed。全量测试：7 failed, 4440 passed, 1 skipped, 272 warnings in 2598.97s (0:43:18)。
完整回归与上轮逐项比较：七个失败均为已有问题，没有新增失败。五项涉及旧 BTC 派生 4h 注册项与历史快照不符，两项为旧错误数量断言期望 9、实际 8；未修改旧注册表或测试来掩盖这些失败。对照证据：完整失败清单对照 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/ema_shock_probability_backtest_v5_20261016/full_test_baseline_comparison.json`)。
有序维护结果：verify 退出 1（54 项旧来源仍未独立验证）；import 退出 3（12 项旧 4h/5m/15m 来源拒绝转换）；inventory 和 reports 均退出 0。本次 Core4 小时行情、mark、原生资金费载荷已分别验证，这些旧拒绝项未被当作可用数据。

工作区维护与全量测试状态见 维护测试摘要 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/ema_shock_probability_backtest_v5_20261016/maintenance_summary.json`)。旧代码、既有结果和原始载荷保护状态见 最终身份核验 (`provenance:nonincluded/crypto-leverage/reports/strategy_validation/%3CSOURCE_ROOT%3Acrypto-leverage%3E/reports/strategy_validation/ema_shock_probability_backtest_v5_20261016/final_identity_audit.json`)。

后续若继续研究，应先提出新的、可解释的过滤假说并冻结规则，再积累真正未使用的数据；不能在这些已用结果中反复调 EMA 或阈值后宣称 OOS 成功。
