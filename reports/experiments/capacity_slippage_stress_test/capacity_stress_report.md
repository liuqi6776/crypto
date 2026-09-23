# Fixed-Slippage Friction Sensitivity Analysis Report
# 固定滑点摩擦成本敏感度分析实证报告

- **Evaluation Date / 测试完成时间**: `2026-09-23 05:08:36 UTC`
- **Asset Universe / 标的池**: Core-4 (`BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`)
- **Period Evaluated / 评估区间**: `[2020-10-15, 2026-09-23)` (Full Cycle)
- **Fee Rate Assumption / 基础手续费**: `8 bps (0.0008)` Taker fee per leg
- **Scope & Methodological Nature / 实验口径与方法学性质**: 
  - **Exogenous Fixed-Slippage Sensitivity (外生固定滑点敏感度)**: This stress test systematically evaluates how both models decay under 5 discrete execution slippage assumptions (5, 10, 15, 25, 50 bps).
  - **No Endogenous Order Book Modeling (未建立内生盘口深度冲击模型)**: The simulation does NOT incorporate empirical L2 order book depth data. Slippage is held constant across capital sizes ($10k to $4M), which is why percentage returns remain identical across deposits. This report measures **sensitivity to friction**, NOT empirical capital capacity bounds.

---

## 1. Dynamic Sensitivity Findings / 动态敏感度实证结论

1. **Candidate A (Top-1 Buffer 0.30) Slippage Decay (候选策略 A 滑点衰减)**:
   - At baseline **5 bps (0.05%)** slippage, Candidate A generates **+43,942.3%** net return (Sharpe 1.76, Max DD -53.14%).
   - At **10 bps (0.10%)**, net return decays to **+28,650.4%** (Sharpe 1.66).
   - At **15 bps (0.15%)**, net return decays to **+18,668.0%** (Sharpe 1.56).
   - At **25 bps (0.25%)**, net return decays to **+7,897.7%** (Sharpe 1.36).
   - At **50 bps (0.50%)**, net return decays to **+848.0%** (Sharpe 0.86).
2. **Candidate B (Simple Multi-Asset EMA Trend) Friction Buffer (候选策略 B 摩擦缓冲)**:
   - Candidate B trades 4 independent sub-portfolios (25% each) without cross-asset rotation, incurring less concentrated compounding friction.
   - At **5 bps**, Candidate B net return is **+4,040.1%** (Sharpe 1.41).
   - At **25 bps**, Candidate B net return is **+1,682.6%** (Sharpe 1.16).
   - At **50 bps**, Candidate B net return is **+527.1%** (Sharpe 0.84).
3. **Alpha Spread Resilience (超额收益抗磨损韧性)**:
   - The excess alpha of Candidate A over Candidate B drops from **+39,902.2%** at 5 bps to **+6,215.1%** at 25 bps, and compresses to **+320.9%** at 50 bps.
   - This proves that concentrated rotation strategies are substantially more vulnerable to execution friction than diversified trend systems.

---

## 2. Slippage Sensitivity Table ($10,000 Base Capital) / 滑点敏感度对照表

| Slippage / 滑点 | Cand A Net Ret (Top-1) | Cand A Sharpe | Cand A Friction | Cand B Net Ret (EMA) | Cand B Sharpe | Cand B Friction | Alpha Spread (A - B) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **5 bps (0.05%)** | **+43,942.3%** | 1.76 | $2,036,446.02 | +4,040.1% | 1.41 | $113,014.29 | **+39,902.2%** |
| **10 bps (0.10%)** | **+28,650.4%** | 1.66 | $2,088,856.60 | +3,251.9% | 1.35 | $136,499.07 | **+25,398.5%** |
| **15 bps (0.15%)** | **+18,668.0%** | 1.56 | $1,992,417.00 | +2,614.7% | 1.29 | $152,616.27 | **+16,053.3%** |
| **25 bps (0.25%)** | **+7,897.7%** | 1.36 | $1,632,197.71 | +1,682.6% | 1.16 | $169,277.54 | **+6,215.1%** |
| **50 bps (0.50%)** | **+848.0%** | 0.86 | $826,479.39 | +527.1% | 0.84 | $165,878.76 | **+320.9%** |

---

## 3. Capital Scale Linear Scaling Table / 资金规模线性等比缩放表

> [!NOTE]
> Note: Under fixed percentage slippage assumptions, percentage returns are mathematically scale-invariant. The table below illustrates the nominal USDT dollar drag across capital levels.
> 注：在固定百分比滑点假设下，收益率百分比在数学上与初始规模无关。下表展示不同初始本金下的名义摩擦美元磨损规模。

| Initial Capital / 初始本金 | 5 bps Cand A Ret | 5 bps Cand A Friction | 25 bps Cand A Ret | 25 bps Cand A Friction | Scaling Nature / 性质说明 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **$10,000 USDT** | +43,942.3% | $2,036,446.02 | +7,897.7% | $1,632,197.71 | Linear scaling (Constant slippage) |
| **$50,000 USDT** | +43,942.3% | $10,182,230.08 | +7,897.7% | $8,160,988.52 | Linear scaling (Constant slippage) |
| **$100,000 USDT** | +43,942.3% | $20,364,460.15 | +7,897.7% | $16,321,977.06 | Linear scaling (Constant slippage) |
| **$500,000 USDT** | +43,942.3% | $101,822,300.73 | +7,897.7% | $81,609,885.26 | Linear scaling (Constant slippage) |
| **$1,000,000 USDT** | +43,942.3% | $203,644,601.47 | +7,897.7% | $163,219,770.54 | Linear scaling (Constant slippage) |
| **$2,000,000 USDT** | +43,942.3% | $407,289,202.94 | +7,897.7% | $326,439,541.07 | Linear scaling (Constant slippage) |
| **$4,000,000 USDT** | +43,942.3% | $814,578,405.88 | +7,897.7% | $652,879,082.13 | Linear scaling (Constant slippage) |

---

## 4. Live Forward Execution Directives / 实测执行与滑点监控指令

1. **Empirical Slippage Tracking / 真实滑点打点监控**:
   - In forward live paper simulation, the engine must compare actual filled order book quotes against theoretical candle open prices on every trade.
2. **Slippage Threshold Alert / 滑点警戒阈值**:
   - If forward live execution encounters average realized slippage exceeding **15 bps**, Candidate A's advantage over Candidate B decays by over 50%. The live system must flag this for execution optimization.
