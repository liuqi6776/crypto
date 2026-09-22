# -*- coding: utf-8 -*-
"""
Web App Module: Dual-Mode Dashboard & Flask API (Phase 23 V1)
=============================================================
Hosts the institutional web dashboard displaying:
- V1 Cross-Sectional Top-1 Spot Strategy (BTC/ETH/SOL/BNB).
- Dual Macro Trend Gate (BTC EMA200 + Top-1 EMA200 with 0.5% hysteresis).
- 1.0x Spot Long (zero leverage, zero debt, no liquidation risk).
- 100% USDT Cash Defense on gate failure.
- Optional Conditional Carry Plugin (corrected 50% nominal capital & fee frictions).
- Full Data Source Transparency (Live API vs Stale Fallback warnings).
"""

from typing import Optional
from flask import Flask, jsonify, render_template_string, request

from server.config import DEFAULT_RECIPIENT
from server.email_notifier import send_alert_email
from server.pipeline import QuantServerPipeline

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>加密量化系统 V1 看板：双重宏观门控 Top-1 现货轮动 & USDT 现金防守</title>
    <style>
        :root {
            --bg-color: #070a13;
            --surface-color: #0f172a;
            --card-color: #17233d;
            --card-border: #233354;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-blue: #38bdf8;
            --accent-green: #22c55e;
            --accent-red: #ef4444;
            --accent-amber: #f59e0b;
            --accent-purple: #a855f7;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background-color: var(--bg-color); color: var(--text-primary); padding: 20px; line-height: 1.5; }
        .container { max-width: 1180px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px solid var(--card-border); flex-wrap: wrap; gap: 14px; }
        .brand { display: flex; align-items: center; gap: 14px; }
        .brand-icon { width: 44px; height: 44px; background: linear-gradient(135deg, #38bdf8, #2563eb); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-weight: 900; font-size: 22px; color: white; box-shadow: 0 4px 12px rgba(56, 189, 248, 0.4); }
        .brand-text h1 { font-size: 20px; font-weight: 800; color: #ffffff; }
        .brand-text p { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }
        .btn-group { display: flex; gap: 10px; flex-wrap: wrap; }
        .btn { background: #1e293b; color: white; border: 1px solid var(--card-border); padding: 9px 16px; border-radius: 8px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 6px; font-size: 13px; transition: all 0.2s; }
        .btn:hover { background: #334155; transform: translateY(-1px); }
        .btn-primary { background: linear-gradient(135deg, #2563eb, #1d4ed8); border: none; }
        .btn-primary:hover { opacity: 0.9; }
        .mode-banner { padding: 14px 20px; border-radius: 12px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; font-size: 14px; }
        .banner-long { background: rgba(34, 197, 94, 0.12); border: 1px solid rgba(34, 197, 94, 0.35); color: #4ade80; }
        .banner-cash { background: rgba(56, 189, 248, 0.12); border: 1px solid rgba(56, 189, 248, 0.35); color: #38bdf8; }
        .grid-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 18px; margin-bottom: 20px; }
        .card { background-color: var(--surface-color); border: 1px solid var(--card-border); border-radius: 14px; padding: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.25); }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
        .card-title { font-size: 13px; font-weight: 700; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.6px; }
        .metric-big { font-size: 30px; font-weight: 800; color: #ffffff; }
        .pill { padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 700; }
        .pill-green { background: rgba(34, 197, 94, 0.15); color: var(--accent-green); border: 1px solid rgba(34, 197, 94, 0.3); }
        .pill-red { background: rgba(239, 68, 68, 0.15); color: var(--accent-red); border: 1px solid rgba(239, 68, 68, 0.3); }
        .pill-amber { background: rgba(245, 158, 11, 0.15); color: var(--accent-amber); border: 1px solid rgba(245, 158, 11, 0.3); }
        .pill-blue { background: rgba(56, 189, 248, 0.15); color: var(--accent-blue); border: 1px solid rgba(56, 189, 248, 0.3); }
        .row-item { display: flex; justify-content: space-between; padding: 9px 0; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 13px; }
        .row-item:last-child { border-bottom: none; }
        .row-label { color: var(--text-secondary); }
        .row-val { font-weight: 700; color: var(--text-primary); }
        .step-box { background: var(--card-color); border: 1px solid var(--card-border); border-radius: 8px; padding: 12px 14px; margin-bottom: 8px; font-size: 13px; }
        .step-num { display: inline-block; width: 20px; height: 20px; background: var(--accent-blue); color: #000; border-radius: 50%; text-align: center; font-weight: 800; font-size: 11px; line-height: 20px; margin-right: 8px; }
        .footer { margin-top: 30px; text-align: center; font-size: 12px; color: var(--text-secondary); line-height: 1.8; }
    </style>
</head>
<body>
    <div class="container">
        <!-- 头部 -->
        <div class="header">
            <div class="brand">
                <div class="brand-icon">👑</div>
                <div class="brand-text">
                    <h1>加密量化系统：🔥 3.0x 杠杆紧凑自适应 Top-1 轮动 & USDT 现金防守</h1>
                    <p>策略模式: 3.0x 杠杆进攻 (SL 1.5x ATR + Trailing Stop) + 100% USDT 现金防御 | 15分钟高频流水线</p>
                </div>
            </div>
            <div class="btn-group">
                <button class="btn" onclick="sendTestEmail()" id="btn-email">
                    <span id="email-btn-text">✉️ 发送测试报警邮件</span>
                </button>
                <button class="btn btn-primary" onclick="triggerRefresh()" id="btn-refresh">
                    <span id="refresh-btn-text">🔄 立即执行15M流水线</span>
                </button>
            </div>
        </div>

        <!-- 当前运行模式横幅 (状态机执行模式 == 看板显示) -->
        <div class="mode-banner {{ 'banner-long' if data.position.is_in_pos else 'banner-cash' }}">
            <div>
                {% if data.position.is_in_pos %}
                    🟢 <b>当前激活模式：🔥 3.0x 杠杆进攻 ({{ data.position.active_symbol.replace('USDT', '') }})</b> | 开仓: ${{ "{:,.2f}".format(data.position.entry_price) }} | 现价: ${{ "{:,.2f}".format(data.position.current_price) }} | 🛑 1.5x ATR 止损: <b style="color: #ef4444;">${{ "{:,.2f}".format(data.position.stop_loss_price) }} (-{{ data.position.distance_to_stop_pct }}%)</b> | ⚡ 3X 强平线: <b style="color: #f59e0b;">${{ "{:,.2f}".format(data.position.liquidation_price) }} (-{{ data.position.distance_to_liq_pct }}%)</b> | 🛡️ 安全垫: <b style="color: #22c55e;">{{ data.position.safety_buffer_ratio }}x</b>
                {% else %}
                    🛡️ <b>当前激活模式：100% USDT 现金防御 (双重宏观门控未通过，零杠杆/零借贷风险/绝对安全)</b>
                {% endif %}
            </div>
            <div style="font-size: 12px;">
                4h 周期: <span id="bar-time" style="color: #38bdf8; font-weight: 600;">{{ data.market.candle_status_desc or data.market.last_closed_bar }}</span> | 轮询刷新: <span id="sync-time">{{ data.timestamp_bjt }}</span>
            </div>
        </div>

        <!-- 全市场截面动量选优看板 (Top-1 龙头实时监测) -->
        <div class="card" style="margin-bottom: 20px; border-color: rgba(56, 189, 248, 0.35); background: linear-gradient(180deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%);">
            <div class="card-header">
                <div>
                    <span class="card-title" style="color: #38bdf8; font-size: 15px;">👑 全市场截面动量选优与宏观门控看板 (币安秒级实时流)</span>
                    <div style="font-size: 12px; color: var(--text-secondary); margin-top: 3px;">
                        BTC / ETH / SOL / BNB 截面池 | 布林带 Z-Score + 20日绝对动量综合打分 | 0.5% 门控滞回缓冲
                    </div>
                </div>
                <div style="text-align: right; display: flex; gap: 8px; align-items: center;">
                    <span class="pill {{ 'pill-green' if not data.market.is_stale else 'pill-red' }}" style="font-size: 11px;">
                        {{ '数据源: ' + data.market.data_source }}
                    </span>
                    <span class="pill {{ 'pill-green' if data.leaderboard.dual_gate_passed else 'pill-amber' }}" style="font-size: 13px;">
                        {{ data.leaderboard.recommended_mode }}
                    </span>
                </div>
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 10px;">
                {% for r in data.leaderboard.ranks %}
                <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid {{ 'rgba(56, 189, 248, 0.6)' if r.rank == 1 else 'rgba(255,255,255,0.08)' }}; border-radius: 10px; padding: 12px; position: relative;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <span style="font-weight: 800; font-size: 15px; color: {{ '#38bdf8' if r.rank == 1 else '#f8fafc' }};">
                            #{{ r.rank }} {{ r.symbol.replace('USDT', '') }}
                            {% if r.rank == 1 %}<span style="font-size: 12px; background: #0284c7; color: white; padding: 1px 6px; border-radius: 4px; margin-left: 4px;">TOP 1</span>{% endif %}
                        </span>
                        <span class="pill {{ 'pill-green' if r.is_above_ema200 else 'pill-red' }}" style="font-size: 10px; padding: 2px 6px;">
                            {{ '高于EMA200' if r.is_above_ema200 else '低于EMA200' }}
                        </span>
                    </div>
                    <div style="font-size: 20px; font-weight: 800; color: #ffffff; margin-bottom: 6px;">
                        ${{ "{:,.2f}".format(r.curr_price) }}
                    </div>
                    <div style="font-size: 12px; color: var(--text-secondary); line-height: 1.6;">
                        综合评分: <b style="color: {{ '#38bdf8' if r.rank == 1 else '#ffffff' }};">{{ r.score }}</b><br>
                        20日动量: <b style="color: {{ '#22c55e' if r.mom20_pct >= 0 else '#ef4444' }};">{{ '+' if r.mom20_pct >= 0 else '' }}{{ r.mom20_pct }}%</b> | 距EMA200: <b style="color: {{ '#22c55e' if r.dist_to_ema_pct >= 0 else '#ef4444' }};">{{ '+' if r.dist_to_ema_pct >= 0 else '' }}{{ r.dist_to_ema_pct }}%</b>
                        {% if r.atr_14 %}<br>4h ATR: <b>${{ r.atr_14 }} ({{ r.atr_pct }}%)</b>{% endif %}
                    </div>
                </div>
                {% endfor %}
            </div>
            <div style="margin-top: 12px; font-size: 12px; color: var(--text-secondary); display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                <span>BTC 宏观牛熊门控 (BTC > EMA200 +0.5%): <b style="color: {{ '#22c55e' if data.leaderboard.btc_macro_bull else '#ef4444' }};">{{ '✅ 顺势多头区 (允许进攻)' if data.leaderboard.btc_macro_bull else '⛔ 宏观防守区 (禁止进攻)' }}</b></span>
                <span>双重硬门控状态: <b style="color: {{ '#22c55e' if data.leaderboard.dual_gate_passed else '#f59e0b' }};">{{ '✅ 完全放行 (允许3.0x做多Top-1)' if data.leaderboard.dual_gate_passed else '🛡️ 拦截保护中 (持有USDT现金)' }}</b></span>
            </div>
        </div>

        <!-- 核心指标网格 -->
        <div class="grid-cards">
            <!-- 资金净值卡片 (真实 V1 记账) -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">实盘模拟账户净值 (3.0x 杠杆记账)</span>
                    <span class="pill pill-green">真实状态机同步</span>
                </div>
                <div class="metric-big">${{ "{:,.2f}".format(data.capital.current_equity_usdt) }}</div>
                <div style="margin-top: 14px;">
                    <div class="row-item">
                        <span class="row-label">初始本金</span>
                        <span class="row-val">${{ "{:,.2f}".format(data.capital.initial_usdt) }} USDT</span>
                    </div>
                    <div class="row-item">
                        <span class="row-label">历史累计盈亏</span>
                        <span class="row-val" style="color: {{ '#22c55e' if data.capital.pnl_usdt >= 0 else '#ef4444' }};">
                            {{ '+' if data.capital.pnl_usdt >= 0 else '' }}${{ "{:,.2f}".format(data.capital.pnl_usdt) }} ({{ '+' if data.capital.pnl_pct >= 0 else '' }}{{ data.capital.pnl_pct }}%)
                        </span>
                    </div>
                    <div class="row-item">
                        <span class="row-label">历史峰值本金</span>
                        <span class="row-val">${{ "{:,.2f}".format(data.capital.peak_usdt) }} USDT</span>
                    </div>
                    <div class="row-item">
                        <span class="row-label">当前最大回撤</span>
                        <span class="row-val" style="color: {{ '#ef4444' if data.capital.drawdown_pct > 10 else '#22c55e' }};">
                            -{{ data.capital.drawdown_pct }}%
                        </span>
                    </div>
                    <div class="row-item">
                        <span class="row-label">累计换手摩擦手续费 (8 bps/次)</span>
                        <span class="row-val" style="color: #f59e0b;">-${{ "{:,.2f}".format(data.capital.accumulated_fees_usdt) }} USDT</span>
                    </div>
                </div>
            </div>

            <!-- 3.0x 杠杆持仓与门控卡片 -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">🔥 3.0x 杠杆持仓与紧凑自适应风控</span>
                    <span class="pill {{ 'pill-green' if data.position.is_in_pos else 'pill-blue' }}">
                        {{ '3.0x 杠杆做多中' if data.position.is_in_pos else '现金防守中' }}
                    </span>
                </div>
                <div class="metric-big" style="color: {{ '#38bdf8' if data.position.is_in_pos else '#94a3b8' }};">
                    {{ data.position.direction }}
                </div>
                <div style="margin-top: 14px;">
                    {% if data.position.is_in_pos %}
                    <div class="row-item">
                        <span class="row-label">持仓代币</span>
                        <span class="row-val">{{ data.position.active_symbol }}</span>
                    </div>
                    <div class="row-item">
                        <span class="row-label">名义持仓头寸 (3.0x)</span>
                        <span class="row-val" style="color: #38bdf8; font-weight: 800;">${{ "{:,.2f}".format(data.position.nominal_usdt) }} USDT</span>
                    </div>
                    <div class="row-item">
                        <span class="row-label">持仓资产数量</span>
                        <span class="row-val">{{ data.position.asset_units }} 枚</span>
                    </div>
                    <div class="row-item">
                        <span class="row-label">入场开仓均价</span>
                        <span class="row-val">${{ "{:,.2f}".format(data.position.entry_price) }}</span>
                    </div>
                    <div class="row-item">
                        <span class="row-label">当前最新市价</span>
                        <span class="row-val">${{ "{:,.2f}".format(data.position.current_price) }}</span>
                    </div>
                    <div class="row-item">
                        <span class="row-label">保证金浮动盈亏 (ROE)</span>
                        <span class="row-val" style="color: {{ '#22c55e' if data.position.unrealized_pnl_usdt >= 0 else '#ef4444' }};">
                            {{ '+' if data.position.unrealized_pnl_usdt >= 0 else '' }}${{ "{:,.2f}".format(data.position.unrealized_pnl_usdt) }} ({{ '+' if data.position.unrealized_pnl_pct >= 0 else '' }}{{ data.position.unrealized_pnl_pct }}% ROE)
                        </span>
                    </div>
                    <div class="row-item" style="background: rgba(239, 68, 68, 0.08); padding-left: 6px; padding-right: 6px; border-radius: 6px; margin: 2px 0;">
                        <span class="row-label" style="color: #ef4444; font-weight: 600;">🛑 1.5x ATR 紧凑自适应止损价</span>
                        <span class="row-val" style="color: #ef4444; font-weight: 800;">
                            ${{ "{:,.2f}".format(data.position.stop_loss_price) }} (距现价 -{{ data.position.distance_to_stop_pct }}%)
                        </span>
                    </div>
                    <div class="row-item" style="background: rgba(245, 158, 11, 0.08); padding-left: 6px; padding-right: 6px; border-radius: 6px; margin: 2px 0;">
                        <span class="row-label" style="color: #f59e0b; font-weight: 600;">⚡ 币安 3X 强平线 (MMR 0.5%)</span>
                        <span class="row-val" style="color: #f59e0b; font-weight: 800;">
                            ${{ "{:,.2f}".format(data.position.liquidation_price) }} (距现价 -{{ data.position.distance_to_liq_pct }}%)
                        </span>
                    </div>
                    <div class="row-item" style="background: rgba(34, 197, 94, 0.08); padding-left: 6px; padding-right: 6px; border-radius: 6px; margin: 2px 0;">
                        <span class="row-label" style="color: #22c55e; font-weight: 600;">🛡️ 止损强平安全缓冲倍数</span>
                        <span class="row-val" style="color: #22c55e; font-weight: 800;">
                            {{ data.position.safety_buffer_ratio }} 倍安全垫 (止损线远在强平线上方)
                        </span>
                    </div>
                    <div class="row-item" style="background: rgba(34, 197, 94, 0.05); padding-left: 6px; padding-right: 6px; border-radius: 6px; margin: 2px 0;">
                        <span class="row-label" style="color: #22c55e; font-weight: 600;">🎯 第一阶段止盈目标 (TP1, +10%)</span>
                        <span class="row-val" style="color: #22c55e; font-weight: 800;">
                            ${{ "{:,.2f}".format(data.position.take_profit_tp1) }} (距现价 +{{ data.position.distance_to_tp1_pct }}%)
                        </span>
                    </div>
                    <div class="row-item" style="background: rgba(168, 85, 247, 0.05); padding-left: 6px; padding-right: 6px; border-radius: 6px; margin: 2px 0;">
                        <span class="row-label" style="color: #a855f7; font-weight: 600;">🚀 第二阶段止盈目标 (TP2, +20%)</span>
                        <span class="row-val" style="color: #a855f7; font-weight: 800;">
                            ${{ "{:,.2f}".format(data.position.take_profit_tp2) }} (距现价 +{{ data.position.distance_to_tp2_pct }}%)
                        </span>
                    </div>
                    <div class="row-item">
                        <span class="row-label">动态风控执行规则</span>
                        <span class="row-val" style="color: #38bdf8; font-size: 11px;">
                            1.5x ATR 紧凑止损 | 浮盈>5%保本锁成本 | 浮盈>10%回撤5%移动止盈
                        </span>
                    </div>
                    {% else %}
                    <div class="row-item">
                        <span class="row-label">持仓资产</span>
                        <span class="row-val" style="color: #38bdf8;">100% USDT 现金 (极度安全)</span>
                    </div>
                    <div class="row-item">
                        <span class="row-label">现金资产余额</span>
                        <span class="row-val">${{ "{:,.2f}".format(data.capital.cash_usdt) }} USDT</span>
                    </div>
                    <div class="row-item">
                        <span class="row-label">止损/止盈状态</span>
                        <span class="row-val" style="color: #94a3b8;">空仓防守中，无需止损止盈</span>
                    </div>
                    <div class="row-item">
                        <span class="row-label">防守原因</span>
                        <span class="row-val" style="color: #f59e0b;">BTC 或 Top-1 未越过 EMA200 (+0.5% 滞回门控)</span>
                    </div>
                    <div class="row-item">
                        <span class="row-label">安全属性</span>
                        <span class="row-val" style="color: #22c55e;">零基差波动风险 / 零清算风险 / 绝对保本</span>
                    </div>
                    {% endif %}
                </div>
            </div>

            <!-- 可选条件性资金费率套利卡片 (修正为 50% 名义空单本金与四腿扣费) -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">可选附加：资金费率 Carry 模块</span>
                    <span class="pill pill-amber">条件性附加 (非默认)</span>
                </div>
                <div class="metric-big" style="color: #fbbf24;">
                    {{ data.funding_arbitrage.effective_net_annual_apy_pct }}%
                    <span style="font-size: 14px; font-weight: 500; color: var(--text-secondary);">净年化 (50%本金)</span>
                </div>
                <div style="margin-top: 14px;">
                    <div class="row-item">
                        <span class="row-label">币安 ETH 8h 费率</span>
                        <span class="row-val">{{ data.funding_arbitrage.funding_info.funding_rate_8h_pct }}% (毛年化: {{ data.funding_arbitrage.funding_info.annualized_apy_pct }}%)</span>
                    </div>
                    <div class="row-item">
                        <span class="row-label">单日预计毛利息 (仅空单本金)</span>
                        <span class="row-val" style="color: #22c55e;">+${{ "{:,.2f}".format(data.funding_arbitrage.est_daily_income_usdt) }} USDT / 天</span>
                    </div>
                    <div class="row-item">
                        <span class="row-label">四腿开平总手续费 (0.20%)</span>
                        <span class="row-val" style="color: #ef4444;">-${{ "{:,.2f}".format(data.funding_arbitrage.estimated_roundtrip_friction_usdt) }} USDT</span>
                    </div>
                    <div class="row-item">
                        <span class="row-label">覆盖摩擦所需持仓天数</span>
                        <span class="row-val" style="color: #f59e0b;">约 {{ data.funding_arbitrage.breakeven_days }} 天 (短周期不建议开启)</span>
                    </div>
                    <div class="row-item">
                        <span class="row-label">当前模块建议</span>
                        <span class="row-val" style="color: #94a3b8;">默认优先持有 USDT 纯现金</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- 页脚 -->
        <div class="footer">
            <p>公网直达地址: <a href="{{ data.public_url }}" style="color: #38bdf8;">{{ data.public_url }}</a> | 本地访问: http://127.0.0.1:8088</p>
            <p>15分钟流水线服务 (V1 架构) | Commit: {{ data.system.code_commit[:8] }} | 报警邮箱: {{ data.recipient_email }}</p>
        </div>
    </div>

    <script>
        async function triggerRefresh() {
            const btn = document.getElementById('btn-refresh');
            const text = document.getElementById('refresh-btn-text');
            btn.disabled = true;
            text.innerText = "⏳ 正在执行15M流水线...";

            try {
                const resp = await fetch('/api/refresh', { method: 'POST' });
                const res = await resp.json();
                if (res.success) {
                    location.reload();
                } else {
                    alert('流水线执行失败: ' + res.error);
                }
            } catch (err) {
                alert('网络异常: ' + err);
            } finally {
                btn.disabled = false;
                text.innerText = "🔄 立即执行15M流水线";
            }
        }

        async function sendTestEmail() {
            const btn = document.getElementById('btn-email');
            const text = document.getElementById('email-btn-text');
            btn.disabled = true;
            text.innerText = "⏳ 正在发送测试邮件...";

            try {
                const resp = await fetch('/api/test_signal_email', { method: 'POST' });
                const res = await resp.json();
                if (res.success) {
                    alert('✅ 报警邮件已成功送达 ' + res.recipient + '！请查收您的邮箱。');
                } else {
                    alert('❌ 发送失败: ' + res.error);
                }
            } catch (err) {
                alert('网络异常: ' + err);
            } finally {
                btn.disabled = false;
                text.innerText = "✉️ 发送测试报警邮件";
            }
        }

        // 30 秒前端自动轮询刷新状态
        setInterval(() => {
            fetch('/api/status').then(r => r.json()).then(data => {
                document.getElementById('sync-time').innerText = data.timestamp_bjt;
                document.getElementById('bar-time').innerText = data.market.last_closed_bar;
            }).catch(() => {});
        }, 30000);
    </script>
</body>
</html>
"""


def create_app(pipeline: QuantServerPipeline) -> Flask:
    """Creates Flask WSGI application connected to the unified pipeline."""
    app = Flask(__name__)

    @app.route("/")
    def index():
        data = pipeline.get_dashboard_data()
        return render_template_string(HTML_TEMPLATE, data=data)

    @app.route("/api/status")
    def api_status():
        return jsonify(pipeline.get_dashboard_data())

    @app.route("/api/refresh", methods=["POST"])
    def api_refresh():
        try:
            res = pipeline.run_cycle(force_notify=False)
            data = pipeline.get_dashboard_data()
            return jsonify({"success": True, "cycle": res, "data": data})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/test_signal_email", methods=["POST"])
    def api_test_signal_email():
        req_data = request.get_json(silent=True) or {}
        recipient = req_data.get("email") or DEFAULT_RECIPIENT
        data = pipeline.get_dashboard_data()
        success = send_alert_email(
            event_type="TEST",
            to_email=recipient,
            dashboard_data=data,
            test_mode=True,
        )
        if success:
            return jsonify({"success": True, "recipient": recipient})
        return jsonify({"success": False, "error": "SMTP delivery failed"}), 500

    return app
