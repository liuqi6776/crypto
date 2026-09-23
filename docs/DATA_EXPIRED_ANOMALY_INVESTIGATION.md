# Empirical Investigation & Root-Cause Analysis: DATA_EXPIRED Anomaly
# 实时前向实测 DATA_EXPIRED 超时异常实证溯源报告

> **Protocol Reference**: `docs/FORWARD_PAPER_EVALUATION_PROTOCOL.md` Section 3.2 (Arrival Staleness & Causality Ceiling)  
> **Investigation Date**: 2026-09-23  
> **Target Record**: `data/forward_tracking/forward_journal.jsonl` Line 1

---

## 1. Incident Timeline & Empirical Facts / 事实时序记录

| Metric / 指标项 | Recorded Value / 记录数值 | Source / 数据来源 |
| :--- | :--- | :--- |
| **Event Type / 事件类型** | `ANOMALY: DATA_EXPIRED` | `forward_journal.jsonl` Line 1 |
| **Regime / 评估环境** | `FORWARD_OOS_LIVE` | Live Out-of-Sample Forward Ledger |
| **Candle Bar Timestamp / K线起始时间** | `2026-09-23 00:00:00+00:00` | 4-Hour Kline Open |
| **Candle Exact Close Time / K线闭合时间** | `2026-09-23 04:00:00 UTC` | Binance K-Line Definition ($00:00 + 4\text{h}$) |
| **System Data Arrival Time / 系统收到时间** | `2026-09-23 05:29:40 UTC` | System Process Ingestion Timestamp |
| **Elapsed Latency / 到达延迟** | **`5380.0 seconds` (1h 29m 40s)** | $\text{Arrival Time} - \text{Close Time}$ |
| **Max Allowed Staleness / 允许最大过期门限** | **`900.0 seconds` (15 minutes)** | `DEFAULT_MAX_STALENESS_SEC` in configuration |
| **Engine Action / 状态机处置动作** | **`SKIP_EXECUTION` (跳过模拟下单)** | Strict causal rejection |

---

## 2. Root Cause Determination / 根本原因溯源

1. **Deployment Window Gap (部署时机时序缺口)**:
   - Git repository logs show that the live forward runner commit and initialization command were executed at `05:29:40 UTC`.
   - The preceding 4h candle had already closed at `04:00:00 UTC` (1 hour 29 minutes earlier).
   - When the runner started, it fetched the latest completed candle, calculated an arrival delay of $5,380\text{s} > 900\text{s}$.
2. **Causality Protection Verification (因果保护有效触发)**:
   - Rather than retrospectively filling an order using market prices that occurred 90 minutes after the candle closed (which would constitute price lookahead/slippage distortion), the engine strictly invoked its safeguard:
     $$\text{Latency} = 5380.0\text{s} > 900.0\text{s} \implies \text{ACTION} = \text{SKIP\_EXECUTION}$$
   - Both Candidate A and Candidate B remained in 100% Cash without spurious transactions.

---

## 3. Subsequent Live Performance & Normalization / 后续正常运行验证

On the subsequent 4-hour cycle:
- **Candle Bar Time**: `2026-09-23 04:00:00+00:00`
- **Candle Close Time**: `2026-09-23 08:00:00 UTC`
- **Data Arrival Time**: `2026-09-23 08:03:06 UTC` (Latency: `186.0s` $\le 900.0\text{s}$)
- **Decision & Quote Arrival Time**: `2026-09-23 08:03:08 UTC` (Execution Latency: `2.0s`)
- **Outcome**: Filled smoothly on schedule (`Candidate_A` bought BTCUSDT at 86,256.35 USDT; `Candidate_B` bought BTC, ETH, SOL, BNB 25% each).

---

## 4. Conclusion & Protocol Audit Sign-off / 结论与审计签署

- The `DATA_EXPIRED` event was an **intentional, correct causal safeguard** executing as designed during the initial process ramp-up.
- Subsequent candles have operated with low latency (< 190 seconds after candle close), proving the pipeline is sound and cauasally compliant.
