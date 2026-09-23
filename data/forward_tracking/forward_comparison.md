# Forward Paper Tracking & A/B Model Performance
# 前向实测模拟与 A/B 模型绩效实时对照报告

- **Report Updated / 报告更新时间**: `2026-09-23 04:16:36 UTC`
- **Last Processed Bar / 最新闭合 K 线**: `2026-09-22 20:00:00`
- **Total Tracked 4h Bars / 累计跟踪根数**: `20`
- **Initial Capital / 初始本金**: `$10,000.00 USDT` each

---

## 1. Live Performance Comparison Matrix / 实时表现对比矩阵

| Metric / 指标 | Candidate A (Top-1 Buffer 0.30) | Candidate B (Simple EMA Trend) | Alpha Spread / 差异 (A - B) |
| :--- | :--- | :--- | :--- |
| **Current Equity / 当前权益** | **$10,423.99 USDT** | **$10,456.56 USDT** | $-32.58 USDT |
| **Net Return / 累计净收益率** | **+4.24%** | **+4.57%** | **-0.33%** |
| **Max Drawdown / 最大回撤** | 2.57% | 2.48% | +0.09% |
| **Current Allocation / 当前持仓** | `BTCUSDT` | `BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT` | - |
| **Completed Trades / 平仓笔数** | 1 trades | 0 trades | - |
| **Win Rate / 交易胜率** | 100.0% | 0.0% | +100.0% |
| **Total Fees Paid / 手续费损耗** | $24.65 | $8.00 | $+16.65 |
| **Total Slippage / 滑点损耗** | $15.40 | $4.99 | $+10.40 |

---

## 2. Institutional Decision Hurdle Status / 机构级前瞻评判准则状态

- **Required Minimum Horizon / 最低跟踪周期**: 180 days (6 months) OR >= 30 completed trades for Candidate A.
- **Current Progress / 当前进度**: `1 / 30` completed roundtrips.
- **Current Verdict / 当前科学裁定**:
  - `EVALUATION_IN_PROGRESS`: Insufficient out-of-sample forward sample to validate or reject Candidate A.
  - Candidate A must maintain cost-adjusted Sharpe superiority and positive excess alpha over Candidate B across the 180-day window to earn live deployment consideration.
