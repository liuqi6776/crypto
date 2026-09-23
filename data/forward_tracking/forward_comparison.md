# Forward Paper Tracking & A/B Model Performance
# 前向实测模拟与 A/B 模型绩效实时对照报告

> [!NOTE]
> **Scientific Positioning & Research Nature / 科学定位与研究性质**:
> The system is currently an operational quantitative research and paper-trading simulation platform. It is NOT yet an empirically forward-verified basis for risking real capital. All capital allocation decisions must await the completion of the 180-day / 30-trade forward evaluation horizon under the frozen protocol.
> 本系统当前为一个可试运行的量化研究与前向模拟交易系统，但还不是经前向验证、可据此判断会赚钱并投入真实资金的交易依据。所有真实资金决策必须等待 180 天或 30 笔完整交易的前瞻评测窗口完成。

- **Report Updated / 报告更新时间**: `2026-09-23 08:03:08 UTC`
- **Evaluation Cutoff / 冻结基准线**: `2026-09-23 00:00:00 UTC`
- **Runner Regime / 运行模式**: `FORWARD_OOS_LIVE`
- **Total Genuine OOS Bars Tracked / 累计样本外真实 K 线**: `2` bars
- **Last Processed Bar / 最新闭合 K 线**: `2026-09-23 04:00:00+00:00`
- **Anomalies Encountered / 触发异常次数**: `1` (Logged in journal)
- **Initial Capital / 初始本金**: `$10,000.00 USDT` each (Started from 100% Cash)

---

## 1. Live Performance Comparison Matrix / 实时表现对比矩阵

| Metric / 指标 | Candidate A (Top-1 Buffer 0.30) | Candidate B (Simple EMA Trend) | Alpha Spread / 差异 (A - B) |
| :--- | :--- | :--- | :--- |
| **Current Equity / 当前权益** | **$9,987.01 USDT** | **$9,986.75 USDT** | $+0.25 USDT |
| **Net Return / 累计净收益率** | **-0.13%** | **-0.13%** | **+0.00%** |
| **Max Drawdown / 最大回撤** | 0.13% | 0.13% | -0.00% |
| **Current Allocation / 当前持仓** | `BTCUSDT` | `BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT` | - |
| **Completed Trades / 平仓笔数** | 0 trades | 0 trades | - |
| **Win Rate / 交易胜率** | 0.0% | 0.0% | +0.0% |
| **Total Fees Paid / 手续费损耗** | $8.00 | $8.00 | $+0.00 |
| **Total Slippage / 滑点损耗** | $4.99 | $4.99 | $+0.00 |

---

## 2. Institutional Decision Hurdle Status / 机构级前瞻评判准则状态

- **Required Minimum Horizon / 最低跟踪周期**: 180 days (6 months) OR >= 30 completed trades for Candidate A.
- **Current Progress / 当前进度**: `0 / 30` completed roundtrips (2 live bars accumulated).
- **Execution & Data Integrity / 执行时序与数据完整性**:
  - Live state starts independently from $10,000 cash each at the freeze cutoff with zero carried-over demo positions.
  - Strict 5-step causality: `Closed Candle Arrival -> Freshness Check (<= 900s) -> Model Signal -> Live Top-of-Book Quote -> Simulated Fill -> Post-Execution MTM`.
  - Stale candles (> 900s) or missing order-book quotes automatically trigger safety skip and anomaly logging.
- **Current Verdict / 当前科学裁定**:
  - `EVALUATION_IN_PROGRESS`: Insufficient out-of-sample forward sample to validate or reject Candidate A.
  - Candidate A must maintain cost-adjusted Sharpe superiority and positive excess alpha over Candidate B across the 180-day window to earn live deployment consideration.
