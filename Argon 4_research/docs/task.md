# Task List / 任务清单: $50,000 USDT All-Satellite Aggressive Compounding Backtest / 5万美金全卫星激进复利实测

- [x] 1. Multi-Timeframe Data Pipeline / 多周期数据流水线 <!-- id: 1 -->
  - [x] 1.1 Synchronize 1h, 15m, and 1m datasets across 254 candidate squeeze episodes (2023-2026) / 同步 254 个轧空周期的 1h、15m 与 1m 高频 K 线 <!-- id: 1.1 -->
  - [x] 1.2 Fix timestamp sorting in episode loader to ensure strict chronological execution / 修复数据加载器的时间戳排序，确保时间轴严格单向推进 <!-- id: 1.2 -->
- [x] 2. $50,000 All-Satellite Portfolio Engine / 5万美金全卫星策略引擎 <!-- id: 2 -->
  - [x] 2.1 Set initial equity to $50,000 USDT / 初始本金设定为 50,000 USDT <!-- id: 2.1 -->
  - [x] 2.2 Implement dynamic concurrent position management (Max 3-4 concurrent positions, 40% cash cushion) / 实现动态并发持仓管理（最多并发 3-4 笔，保留 40% 现金缓冲防爆仓） <!-- id: 2.2 -->
  - [x] 2.3 Implement dynamic compounding position sizing (15% and 20% account equity per trade) / 实现动态复利仓位管理（单笔 15% 与 20% 动态保证金） <!-- id: 2.3 -->
  - [x] 2.4 Model realistic Taker (0.05% fee + 0.20% slip) vs Maker (0.02% fee + 0% slip) / 精准建模 Taker 市价吃单 vs Maker 限价挂单摩擦成本 <!-- id: 2.4 -->
- [x] 3. 3x vs 5x Leverage Comparative Simulation / 3倍 vs 5倍杠杆全量对比模拟 <!-- id: 3 -->
  - [x] 3.1 Run 3x Maker & Taker simulations starting from $50,000 / 运行 3倍杠杆 5万美金本金实测 <!-- id: 3.1 -->
  - [x] 3.2 Run 5x Maker & Taker simulations starting from $50,000 / 运行 5倍杠杆 5万美金本金实测 <!-- id: 3.2 -->
  - [x] 3.3 Compute capital growth metrics (Final Balance, USD Net Profit, Win Rate, Profit Factor, Max Drawdown) / 计算资产增值核心指标（最终净值、美金净利润、胜率、盈亏比、最大回撤） <!-- id: 3.3 -->
- [x] 4. Visualizations & Trade Audit Reports / 可视化图表与交易审计日志 <!-- id: 4 -->
  - [x] 4.1 Export trade logs with entry/exit timestamps, prices, pnl, and return on margin to CSV / 导出逐笔交易审计日志至 CSV <!-- id: 4.1 -->
  - [x] 4.2 Plot high-resolution comparative equity curves from $50,000 to PNG / 绘制 5万美金起步的四维净值增长曲线图 <!-- id: 4.2 -->
  - [x] 4.3 Update bilingual walkthrough report (`walkthrough.md`) / 更新中英双语项目成果复盘文档 <!-- id: 4.3 -->
