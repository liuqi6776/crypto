# Terminal Squeeze Exhaustion & OI Collapse Shorting Playbook
# 结合持仓量（OI）与极端资金费率的“轧空衰竭”右侧做空量化实战指南

---

## 1. Executive Summary & Core Logic / 策略概述与核心逻辑

### English
The **Terminal Squeeze Exhaustion Shorting Strategy** is an institutional-grade, event-driven mean-reversion and momentum-reversal strategy. It targets cryptocurrency perpetual futures experiencing extreme negative funding rates caused by speculative short squeezes. 

**Core Thesis**:
A short squeeze is propelled strictly by forced buyer liquidity (short liquidations and stop-loss market buy orders). When the pool of remaining short interest is fully purged, the buying engine suddenly exhausts. Concurrently, market makers and whales who accumulated long perpetual contracts to capture funding fees must aggressively liquidate their positions to realize spot profits. This dynamic triggers an abrupt, asymmetric collapse where prices often plummet by $40\% \sim 80\%$ within hours.

---

### 中文
**“轧空衰竭与OI崩塌”右侧做空策略**是一种机构级的事件驱动型均值回归与动量逆转策略。该策略专门针对因散户或机构扎堆开空、导致永续合约出现极端负资金费率（如 -0.5% 至 -2.0%）的标的。

**核心逻辑**：
轧空行情的持续拉升，本质是由**空头爆仓与止损产生的被动市价买单**作为燃料推动的。当场内所有浮动空头被系统物理清算完毕时，推动上涨的被动买盘瞬间枯竭。与此同时，在现货和合约端控盘、吃满高额资金费的庄家必须通过市价砸盘套现。这会导致供需平衡发生断崖式逆转，币价往往在数小时内暴跌 $40\% \sim 80\%$。

---

## 2. Multi-Dimensional Indicator Matrix / 监控指标矩阵

| Indicator / 指标 | Dimension / 维度 | Normal Regime / 正常状态 | Warning / Squeeze Phase / 预警与轧空爆发期 | Terminal Reversal Trigger / 见顶衰竭做空触发条件 |
| :--- | :--- | :--- | :--- | :--- |
| **Funding Rate (FR)**<br>资金费率 | Sentiment & Basis<br>情绪与期现基差 | $-0.01\% \sim +0.01\%$ | $<-0.50\%$ (Cap at $-1.5\% \sim -2.0\%$) | **持续处于极度负值（如 $\le -1.0\%$）且触及交易所上限** |
| **Open Interest (OI)**<br>全网合约未平仓量 | Fuel Capacity<br>多空燃料池容量 | Baseline | OI 持续暴增并创历史新高（空头不断加仓入场送死） | **OI 从最高峰断崖式暴跌 $\ge 20\% \sim 35\%$**（空头已被彻底清算，燃料耗尽） |
| **Exchange Policy**<br>交易所风控政策 | Regulatory Intervention<br>官方规则干预 | 8h 结算，20x 杠杆 | 结算周期被缩短为 4h/2h，杠杆上限下调至 8x/5x | 币安发布合约参数调整公告，上调维持保证金率（MMR） |
| **Perp vs Spot Basis**<br>期现价差与贴水率 | Arbitrage Pressure<br>套利与现货牵引力 | 贴水 $<0.2\%$ | 深度贴水，合约价格比现货低 $3\% \sim 10\%$ | 深度贴水开始急剧收敛，甚至合约价格瞬间溢价现货 |
| **Market Structure**<br>价格形态与市场结构 | Price Action<br>量价与结构破坏 | 震荡或温和趋势 | 抛物线式垂直拉升（Parabolic Advance），远离 MA20/MA60 | **15m/1h 级别放量跌破前低关键颈线（ChoCH / MSS）** |

---

## 3. Four Lifecycle Phases of a Short Squeeze / 轧空行情的四大生命周期

```
Price / 价格
  ^
  |                                 [Peak / 天花板: 600U]
  |                                        /\
  |                                       /  \   <-- Phase 4: Collapse (右侧崩盘阶段)
  |            Phase 2: Acceleration    /    \       (OI Collapse + Neckline Breakdown)
  |                  (轧空加速期)        /      \
  |                     /             /        \
  |                    /   [Phase 3: Exhaustion \
  |                   /      高潮衰竭期 / OI骤降]  \
  |                  /                              \
  |   Phase 1: Build /                               \
  |   (筑底与控盘期) /                                 \
  +------------------------------------------------------------> Time / 时间
```

### Phase 1: Accumulation & Negative Funding Emergence (吸筹与负费率初现)
- **特征**：现货大户锁仓 $80\%$ 以上流通盘；币价翻倍，散户开始依据“估值过高”开空。
- **指标**：资金费率跌至 $-0.1\% \sim -0.3\%$，OI 稳步上升。
- **操作准则**：**严禁做空！** 此时为庄家磨刀霍霍阶段。

### Phase 2: Parabolic Squeeze & Extreme Funding Cap (垂直逼空与极度负费率)
- **特征**：庄家用极小现货资金拉盘，合约端空头连续爆仓。价格呈 $70^\circ \sim 80^\circ$ 角度垂直拉升。
- **指标**：资金费率触及顶格（$-1.5\% \sim -2.0\%$），交易所介入缩短结算周期至 2h 或 4h；OI 创出天量历史新高。
- **操作准则**：**严禁左侧摸顶开空！** 任何试图猜顶的行为都会被连环强平市价单吞噬。

### Phase 3: Climax Liquidation & OI Divergence (流动性枯竭与OI断崖)
- **特征**：最后顽固的深套空头全部被强制平仓，伴随单根大阳线放量冲刺（Blow-off Top）。
- **指标**：**价格创出新高，但合约持仓量（OI）瞬间暴跌 $25\% \sim 40\%$**！这表明空头已经被物理消灭，市场上再无空头爆仓买单。
- **操作准则**：**进入一级战备状态**，开始绘制 15 分钟及 1 小时级别关键支撑颈线。

### Phase 4: Structural Breakdown & Cascade Dump (结构破坏与多杀多崩盘)
- **特征**：庄家与吃满费率的套利多头集体撤单抛售，现货买盘瞬间真空。
- **指标**：15m 出现放量跌破前期结构低点（Market Structure Shift, MSS），5m/15m 反弹无力。
- **操作准则**：**右侧果断开空入场**。

---

## 4. Concrete Entry, Stop-Loss & Take-Profit Rules / 明确的入场、止损与止盈规则

### 4.1 Entry Triggers (做空入场信号 - 必须同时满足)

1. **Pre-condition 1 (极端费率确认)**:
   - 目标代币在币安过去至少 2 个结算周期内资金费率持续 $\le -0.8\%$（或达到该币种历史封顶值）。
2. **Pre-condition 2 (OI 枯竭确认 - 核心核心指标)**:
   - 该标的全网或币安端合约未平仓量（OI）从最高点出现**至少 $20\%$（优选 $\ge 30\%$）的断崖式回落**。
3. **Execution Trigger (右侧价格结构确认)**:
   - **Trigger A (颈线跌破)**：在 15 分钟级别上，实体收盘价跌破最近一波轧空脉冲的起涨波谷（Swing Low / MSS）。
   - **Trigger B (均线压制)**：价格放量跌破 15m VWAP 及 EMA20，随后回踩 EMA20 不破且量能萎缩。
   - **Trigger C (结算时间过滤)**：入场时间点必须**避开结算前 30 分钟**，优选在资金费率结算完成后的 $15 \sim 60$ 分钟内（吃费套利盘正在疯狂砸盘平多）。

---

### 4.2 Risk Management & Position Sizing (风控与仓位管理 - 生死之线)

> [!CAUTION]
> 处于极端负费率的币种即使在见顶崩盘初期，仍可能面临每 8 小时扣除 $1\% \sim 2\%$ 资金费率的摩擦损耗，且容易出现 $10\% \sim 15\%$ 的局部二次脉冲抽搐（Dead-Cat Bounce）。严禁大仓位与高杠杆！

1. **杠杆倍数 (Leverage)**:
   - 严格限制在 **$1\text{x} \sim 3\text{x}$**（绝不超过 3 倍）。
2. **单笔仓位占用 (Position Sizing)**:
   - 单笔交易占用保证金不得超过总账户净值的 **$3\% \sim 5\%$**。
   - 最大允许本金回撤单笔锁定为总账户的 **$1.5\%$**。
3. **硬性止损位 (Hard Stop-Loss)**:
   - 止损线严格设置在**本轮轧空最高点（Absolute Swing High）上方 $+1.5\% \sim +2.5\%$**。
   - 若止损距离过大（例如距最高点有 $20\%$ 空间），必须按比例缩小开仓名义价值，确保止损金额符合 $1.5\%$ 账户风控红线。

---

### 4.3 Take-Profit & Exit Logic (分批止盈与离场规则)

- **TP 1 (首批兑现 - 30% 仓位)**:
   - 当价格从入场点回撤达 **$-15\% \sim -20\%$**，或者价格触及 4 小时 EMA60 均线时，市价平掉 $30\%$ 仓位，并将剩余仓位的止损线**下移至入场开仓价（保本损）**。
- **TP 2 (主跌浪兑现 - 40% 仓位)**:
   - 当价格跌幅达到 **$-35\% \sim -50\%$**（通常回吐至轧空启动前的第一阻力转支撑平台）时，平掉 $40\%$ 仓位。
- **TP 3 (费率正常化清仓 - 剩余 30% 仓位)**:
   - 密切监控币安资金费率。当资金费率由负值**回归至正常中性区间（$-0.02\% \sim +0.02\%$）**，说明多空博弈已彻底恢复理性，清空全部底仓离场。

---

## 5. Landmark Case Study: TRB (Dec 31, 2023 ~ Jan 01, 2024) / 经典实盘复盘：TRB 史诗级轧空

```
Timestamp (UTC)       Funding Rate   Mark Price     Open Interest (OI)     Market State & Action
--------------------------------------------------------------------------------------------------------
2023-12-31 08:00      -0.791%        $260           $310M                  Squeeze in progress. NO SHORT.
2023-12-31 16:00      -2.000% (Cap)  $274           $380M (All-Time High)  Climax blow-off top begins.
2023-12-31 20:00      -1.951%        $443 -> $600   $190M (Plunged -50%!)  OI Collapses! Shorts purged.
2024-01-01 00:00      -2.000%        $194 (-67%!)   $85M                   Whale dumps spot. Structural collapse.
2024-01-01 08:00      -2.000%        $155 (-74%!)   $60M                   Take Profit complete.
```

### 关键复盘教训：
1. **OI 从 380M 骤降至 190M 的瞬间，是全场最确定的空头衰竭信号**。
2. 即使在价格从 600 暴跌至 194 时，**资金费率仍然是顶格 -2.0%**。如果散户只盯费率而做多，在 8 小时内本金全军覆没；如果看懂 OI 断崖并在跌破 500 颈线右侧做空，能在数小时内斩获 $60\%+$ 利润！

---

## 6. Algorithmic Pseudo-Code & Signal Logic / 量化算法逻辑与信号伪代码

```python
"""
Strategy 2: Terminal Squeeze Exhaustion & OI Collapse Reversal
Target: Binance USDT Perpetual Futures
"""

import numpy as np

def evaluate_terminal_short_signal(symbol_data, current_candle):
    """
    symbol_data contains:
      - funding_history: list of recent funding rates
      - oi_history: list of recent Open Interest data (15m intervals)
      - klines_15m: OHLCV DataFrame (15-min)
      - current_funding_rate: float
    """
    
    # 1. Check Funding Rate Threshold
    # Ensure funding is at extreme negative levels
    recent_fr = symbol_data['funding_history'][-3:]
    if not all(fr <= -0.008 for fr in recent_fr): # -0.8%
        return {"signal": "NONE", "reason": "Funding rate not sufficiently negative"}
        
    # 2. Check OI Collapse Divergence
    # Calculate peak OI in the last 24 hours vs current OI
    oi_series = symbol_data['oi_history'][-96:] # 24h at 15m
    peak_oi = np.max(oi_series)
    current_oi = oi_series[-1]
    oi_drawdown = (peak_oi - current_oi) / peak_oi
    
    if oi_drawdown < 0.25: # Need at least 25% drop from peak
        return {"signal": "NONE", "reason": f"OI drawdown only {oi_drawdown:.1%}, fuel remains"}
        
    # 3. Check Right-Side Market Structure Shift (MSS)
    df_15m = symbol_data['klines_15m']
    recent_swing_low = df_15m['low'][-16:-1].min() # Swing low of last 4 hours
    current_close = current_candle['close']
    current_vwap = df_15m['vwap'].iloc[-1]
    
    is_structural_break = (current_close < recent_swing_low) and (current_close < current_vwap)
    if not is_structural_break:
        return {"signal": "WAIT", "reason": "OI exhausted, waiting for 15m MSS structural breakdown"}
        
    # 4. Check Settlement Timing Window
    # Avoid entries 30 mins before funding settlement (prevent spike squeeze)
    mins_to_settlement = symbol_data['mins_to_settlement']
    if mins_to_settlement <= 30:
        return {"signal": "WAIT", "reason": "Too close to funding settlement"}
        
    # 5. Generate Trade Order Parameters
    swing_high = df_15m['high'][-24:].max()
    hard_stop_loss = swing_high * 1.02 # 2% buffer above peak
    risk_distance = (hard_stop_loss / current_close) - 1.0
    
    # Position sizing: max 1.5% account loss
    account_equity = symbol_data['account_equity']
    max_risk_dollars = account_equity * 0.015
    position_notional = max_risk_dollars / risk_distance
    max_allowed_notional = account_equity * 3.0 # Max 3x leverage
    final_position_size = min(position_notional, max_allowed_notional)
    
    return {
        "signal": "ENTER_SHORT",
        "symbol": symbol_data['symbol'],
        "entry_price": current_close,
        "stop_loss": hard_stop_loss,
        "tp_1": current_close * 0.80, # -20%
        "tp_2": current_close * 0.55, # -45%
        "position_notional": final_position_size,
        "leverage": min(3.0, final_position_size / account_equity)
    }
```
