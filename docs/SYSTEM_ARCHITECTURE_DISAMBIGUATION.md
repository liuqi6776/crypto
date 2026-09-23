# System Architecture & Empirical Baseline Disambiguation
# 系统架构隔离说明与真实量化基准对账白皮书

本文档旨在明确澄清代码库中不同实验模块、前向模拟记录与历史回测基准之间的边界，防止指标混淆，确保量化逻辑的严密性与透明度。

---

## 1. 架构模块隔离 (Disambiguation of Systems)

代码库中存在两个历史阶段的独立系统，二者在设计定位、标的池和运行逻辑上完全独立，**严禁混用同一组收益与胜率数据**：

```mermaid
graph TD
    subgraph 系统一: 旧版结构趋势模拟 (Legacy Satellite Service)
        A1["模块路径: crypto_quant/paper/config.py<br/>启动脚本: scripts/run_paper_service.py"]
        A2["交易标的: 仅 ETHUSDT, SOLUSDT (双币结构趋势)"]
        A3["历史记录: docs/forward_paper_weekly.json<br/>(仅记录 3 次运行、1 笔已平仓亏损, 属遗留归档)"]
        A4["安全锁: ENABLE_REAL_ORDERS = False (严格关闭实盘)"]
    end

    subgraph 系统二: 当前生产级 Top-1 轮动系统 (Active Production System)
        B1["核心引擎: crypto_quant/paper/top1_rotation_strategy.py<br/>生产服务: server/main.py, server/pipeline.py"]
        B2["交易标的: 截面优选 (BTC, ETH, SOL, BNB) + 100% USDT 现金防守"]
        B3["状态账本: paper_state/v1_top1_state.json<br/>审计日志: paper_logs/v1_top1_journal.jsonl"]
        B4["运行模式: 1.0x 现货基准 (推荐) / 3.0x 紧凑自适应 (高风险试验)"]
    end
```

### 核心区别对照表：

| 维度 | 系统一：旧版双币趋势模拟 (Legacy) | 系统二：Top-1 截面轮动与双重门控 (Active V1) |
| :--- | :--- | :--- |
| **状态** | **已归档 / 停用 (Deprecated)** | **生产线上运行 (Active on port 8088)** |
| **配置文件** | `crypto_quant/paper/config.py` | `server/pipeline.py` & `v1_top1_state.json` |
| **资产范围** | 仅 ETH, SOL | BTC, ETH, SOL, BNB 及 100% USDT 现金 |
| **仓位决策** | 各币种独立突破开仓 | 截面动量打分 Top-1 集中进攻 |
| **宏观门控** | 无全局 BTC 门控 | **双重宏观门控 (BTC > EMA200 且 标的 > EMA200)** |
| **周报归属** | `docs/forward_paper_weekly.json` (记录了 1 笔亏损交易) | 独立流水线日志 `v1_top1_journal.jsonl` |

---

## 2. 单一持仓账本对账与真实收益真相 (Single-Ledger Audit)

经过用户深度复核与单一持仓账本（`SingleLedgerSimulator`）重写，我们彻底根除了早期回测中**“持仓期间盯市计入本金 + 平仓时按整笔涨跌幅重复乘算”**的双重计入 Bug。

在严格扣除 8 bps 名义手续费、15 bps 止损滑点、10% APR 借贷利息、币安真实资金费率和单根 K 线强平检测后，**真实的 1.0x 现货 vs 3.0x 杠杆全周期（2020-2026）对比数据如下**：

| 运行模式 (Mode) | 6年总收益率 (Total Ret) | 年化复合收益 (CAGR) | 最大回撤 (Max DD) | 夏普比率 (Sharpe) | 交易次数 (止损次数) | 强平穿仓状态 | 真实实战结论 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1.0x 现货零杠杆 (推荐)** | **+2,735.25% (+27.35倍)** | **+75.67%** | **-61.17%** | **1.14** | 1,137 次 (494) | ✅ **100% 绝对安全 (零强平)** | **长跑冠军：年化 75%，回撤可控，复利极强** |
| **3.0x 杠杆紧凑止损** | **+19.06% (+0.19倍)** | **+2.98%** | **-98.66%** | **0.94** | 1,137 次 (494) | ✅ 勉强存活 (未爆仓) | **高磨损重灾区：手续费与负复利吞噬 99% 利润** |
| **5.0x 杠杆** | **-100.00% (本金归零)** | **-100.00%** | **-100.00%** | 2.61 | 148 次 (84) | 💥 **2021-02-22 彻底爆仓** | **不可行：单根插针击穿强平线** |

### 深刻的量化结论：
1. **杠杆负复利与摩擦损耗定律**：
   - 在长达 6 年、超过 1,100 次的轮动交易中，3.0x 杠杆不仅放大了收益，更将每次买卖的手续费（0.24%）与止损摩擦放大了 3 倍。
   - 连续数次止损后，3.0x 净值回撤达 -50% 以上，需要后续产生 +100% 的超额行情才能回本，导致全周期年化收益从现货的 **+75.67% 骤降至 +2.98%**！
2. **现货 1.0x 才是真正稳健的复利圣杯**：
   - 现货在 2020-2026 全周期斩获 **+2,735%（27 倍）**，2025 年震荡市斩获 **+35.13%**，2022 年熊市仅回撤 **-11.30%**（同期 BTC 下跌 -65%）。
   - **实战纪律**：用户建议完全正确——在当前阶段，**绝不应投入真实资金使用 3 倍杠杆，应以 1.0x 现货或低频保护模式作为资金配置底线**。

---

## 3. 逐笔交易记录可追溯性 (Trade Log Auditability)

所有真实回测均在 `leverage_research/trade_logs/` 下生成了逐笔可追溯的交易台账（CSV）：
- 文件格式：`trades_{Universe}_{Period}_{Leverage}.csv`
- 字段规范：`entry_time`, `exit_time`, `symbol`, `entry_price`, `exit_price`, `units`, `leverage`, `gross_ret_pct`, `net_pnl_usdt`, `fees_paid_usdt`, `exit_reason`, `bars_held`
- 每一笔交易的入场价均严格为 $T$ 根 K 线的 Open，离场严格扣除手续费，无任何未来数据穿越。
