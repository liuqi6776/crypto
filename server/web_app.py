# -*- coding: utf-8 -*-
"""
Web App Module: Dual-Mode Dashboard & Flask API (Phase 23)
==========================================================
Hosts the institutional web dashboard displaying:
- ETH 3x Leveraged Structural Trend trading
- Monotonic 3x ATR trailing stop & liquidation safety buffer
- Real-time Core Only (100% Delta-Neutral Funding Rate Arbitrage) guide & APY
- Top-1 Cross-Sectional Leaderboard across BTC, ETH, SOL, BNB
- 15-Minute Pipeline status, manual trigger, and test email
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
    <title>ETH 3x 杠杆波段 & Core 资金费率套利系统 (15分钟自动化流水线)</title>
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
        .banner-arb { background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.35); color: #fbbf24; }
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
        .step-num { display: inline-block; width: 20px; height: 20px; background: var(--accent-amber); color: #000; border-radius: 50%; text-align: center; font-weight: 800; font-size: 11px; line-height: 20px; margin-right: 8px; }
        .footer { margin-top: 30px; text-align: center; font-size: 12px; color: var(--text-secondary); line-height: 1.8; }
    </style>
</head>
<body>
    <div class="container">
        <!-- 头部 -->
        <div class="header">
            <div class="brand">
                <div class="brand-icon">Ξ</div>
                <div class="brand-text">
                    <h1>ETH 3x 杠杆波段 & Core 资金费率套利系统</h1>
                    <p>服务端流水线: 15分钟高频拉取与信号侦测 | 10,000 USDT 本金 | 独立 server/ 包</p>
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

        <!-- 当前运行模式横幅 -->
        <div class="mode-banner {{ 'banner-long' if data.position.is_in_pos else 'banner-arb' }}">
            <div>
                {% if data.position.is_in_pos %}
                    🟢 <b>当前激活模式：ETH 3x 杠杆波段持仓多头 (LONG 3.0x)</b> | 开仓价: ${{ "{:,.2f}".format(data.position.entry_price) }}
                {% else %}
                    🟡 <b>当前激活模式：Core Only (100% 资金费率无风险套利)</b> | 现货多+永续空 Delta 对冲生息中
                {% endif %}
            </div>
            <div style="font-size: 12px;">
                4h 闭合时间: <span id="bar-time">{{ data.market.last_closed_bar }}</span> | 轮询刷新: <span id="sync-time">{{ data.timestamp_bjt }}</span>
            </div>
        </div>

        <!-- 全市场截面动量选优看板 -->
        <div class="card" style="margin-bottom: 20px; border-color: rgba(56, 189, 248, 0.35); background: linear-gradient(180deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%);">
            <div class="card-header">
                <div>
                    <span class="card-title" style="color: #38bdf8; font-size: 15px;">👑 全市场截面动量选优看板 (Top-1 龙头实时监测)</span>
                    <div style="font-size: 12px; color: var(--text-secondary); margin-top: 3px;">
                        BTC / ETH / SOL / BNB 截面池 | 布林带 Z-Score + 20日绝对动量综合打分 | 15分钟同步计算
                    </div>
                </div>
                <div style="text-align: right;">
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
                        20日动量: <b style="color: {{ '#22c55e' if r.mom20_pct >= 0 else '#ef4444' }};">{{ '+' if r.mom20_pct >= 0 else '' }}{{ r.mom20_pct }}%</b> | 布林Z: <b>{{ r.bb_z }}</b>
                    </div>
                </div>
                {% endfor %}
            </div>
            <div style="margin-top: 12px; font-size: 12px; color: var(--text-secondary); display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                <span>BTC 宏观牛熊硬门控 (BTC > EMA200): <b style="color: {{ '#22c55e' if data.leaderboard.btc_macro_bull else '#ef4444' }};">{{ '✅ 顺势多头区 (允许进攻)' if data.leaderboard.btc_macro_bull else '⛔ 宏观防守区 (禁止进攻)' }}</b></span>
                <span>双重硬门控状态: <b style="color: {{ '#22c55e' if data.leaderboard.dual_gate_passed else '#f59e0b' }};">{{ '✅ 完全放行' if data.leaderboard.dual_gate_passed else '🛡️ 拦截保护中' }}</b></span>
            </div>
        </div>

        <!-- 核心指标网格 -->
        <div class="grid-cards">
            <!-- 资金净值卡片 -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">实盘模拟账户净值</span>
                    <span class="pill pill-green">实盘同步中</span>
                </div>
                <div class="metric-big">${{ "{:,.2f}".format(data.capital.current_equity_usdt) }}</div>
                <div style="margin-top: 14px;">
                    <div class="row-item">
                        <span class="row-label">初始基准本金</span>
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
                </div>
            </div>

            <!-- 3x 杠杆风控卡片 -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">ETH 3x 杠杆风控与清算防线</span>
                    <span class="pill {{ 'pill-green' if data.position.is_safe else 'pill-red' }}">
                        {{ '安全缓冲区充足' if data.position.is_safe else '风控警报' }}
                    </span>
                </div>
                <div class="metric-big" style="color: {{ '#38bdf8' if data.position.is_in_pos else '#94a3b8' }};">
                    {{ data.position.direction }}
                </div>
                <div style="margin-top: 14px;">
                    <div class="row-item">
                        <span class="row-label">3x 杠杆名义敞口</span>
                        <span class="row-val">${{ "{:,.2f}".format(data.position.nominal_usdt) }} USDT</span>
                    </div>
                    {% if data.position.is_in_pos %}
                    <div class="row-item">
                        <span class="row-label">持仓均价</span>
                        <span class="row-val">${{ "{:,.2f}".format(data.position.entry_price) }}</span>
                    </div>
                    <div class="row-item">
                        <span class="row-label">动态单调移动止损 (3x ATR)</span>
                        <span class="row-val" style="color: #ef4444;">${{ "{:,.2f}".format(data.position.trailing_stop) }} (距现价 {{ data.position.distance_to_stop_pct }}%)</span>
                    </div>
                    <div class="row-item">
                        <span class="row-label">⚠️ 预估强制平仓线 (爆仓线)</span>
                        <span class="row-val" style="color: #f59e0b;">${{ "{:,.2f}".format(data.position.liquidation_price) }} (距现价 {{ data.position.distance_to_liq_pct }}%)</span>
                    </div>
                    <div class="row-item">
                        <span class="row-label">止损与强平安全缓冲垫</span>
                        <span class="row-val" style="color: #22c55e;">{{ data.position.safety_buffer_pct }}% (市价止损远早于强平)</span>
                    </div>
                    {% else %}
                    <div class="row-item">
                        <span class="row-label">当前持仓状态</span>
                        <span class="row-val" style="color: #f59e0b;">空仓防御 (100% 部署资金费套利)</span>
                    </div>
                    <div class="row-item">
                        <span class="row-label">距突破买入线 (120布林上轨)</span>
                        <span class="row-val" style="color: #38bdf8;">+{{ data.market.dist_to_buy_pct }}% (目标: ${{ "{:,.2f}".format(data.market.bb_upper) }})</span>
                    </div>
                    {% endif %}
                </div>
            </div>

            <!-- Core 资金费率套利卡片 -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Core Only (100% 资金费率无风险套利)</span>
                    <span class="pill pill-amber">Delta 零风险中性</span>
                </div>
                <div class="metric-big" style="color: #fbbf24;">
                    {{ data.funding_arbitrage.funding_info.annualized_apy_pct }}%
                    <span style="font-size: 14px; font-weight: 500; color: var(--text-secondary);">年化 APY</span>
                </div>
                <div style="margin-top: 14px;">
                    <div class="row-item">
                        <span class="row-label">币安当前 8h 费率</span>
                        <span class="row-val">{{ data.funding_arbitrage.funding_info.funding_rate_8h_pct }}% (下次结算: {{ data.funding_arbitrage.funding_info.countdown }})</span>
                    </div>
                    <div class="row-item">
                        <span class="row-label">单日预估现金流生息</span>
                        <span class="row-val" style="color: #22c55e;">+${{ "{:,.2f}".format(data.funding_arbitrage.est_daily_income_usdt) }} USDT / 天</span>
                    </div>
                    <div class="row-item">
                        <span class="row-label">30 天累计预期收益</span>
                        <span class="row-val" style="color: #22c55e;">+${{ "{:,.2f}".format(data.funding_arbitrage.est_monthly_income_usdt) }} USDT</span>
                    </div>
                    <div class="row-item">
                        <span class="row-label">操作状态</span>
                        <span class="row-val" style="color: {{ '#22c55e' if not data.position.is_in_pos else '#94a3b8' }};">
                            {{ '🟢 激活套利生息中' if not data.position.is_in_pos else '⚪ 多头进攻中 (套利待命)' }}
                        </span>
                    </div>
                </div>
            </div>
        </div>

        <!-- 套利保姆级实操指引 -->
        <div class="card" style="margin-bottom: 20px;">
            <div class="card-header">
                <span class="card-title" style="color: #fbbf24;">🛠️ Core 资金费率套利 4 步保姆级实操指南 (基于本金 ${{ "{:,.0f}".format(data.capital.current_equity_usdt) }} USDT)</span>
            </div>
            <div class="step-box">
                <span class="step-num">1</span>
                <b>资金拆分对半</b>：将账户中的 <b>${{ "{:,.0f}".format(data.funding_arbitrage.half_capital_usdt) }} USDT</b> 留在现货账户买入现货，另外 <b>${{ "{:,.0f}".format(data.funding_arbitrage.half_capital_usdt) }} USDT</b> 划转入 USDT 永续合约账户作为保证金。
            </div>
            <div class="step-box">
                <span class="step-num">2</span>
                <b>现货买入 + 合约等额开空</b>：以市价买入 ${{ "{:,.0f}".format(data.funding_arbitrage.half_capital_usdt) }} 的现货，同时在币安永续合约开立价值 ${{ "{:,.0f}".format(data.funding_arbitrage.half_capital_usdt) }} 的 <b>1x 杠杆空单</b>。
            </div>
            <div class="step-box">
                <span class="step-num">3</span>
                <b>Delta 归零坐收利息</b>：现货涨多少，空单亏多少；现货跌多少，空单赚多少，净值绝对无视行情暴跌。每天 08:00 / 16:00 / 24:00 (BJT) 稳收资金费。
            </div>
            <div class="step-box">
                <span class="step-num">4</span>
                <b>牛市信号一键平仓切多</b>：当收到系统发送的【🚨 买入信号邮件】时，平掉合约空单，全额资金切换为 3x 杠杆波段顺势进攻！
            </div>
        </div>

        <!-- 页脚 -->
        <div class="footer">
            <p>公网直达地址: <a href="{{ data.public_url }}" style="color: #38bdf8;">{{ data.public_url }}</a> | 本地访问: http://127.0.0.1:8088</p>
            <p>15分钟流水线服务 | Commit: {{ data.system.code_commit[:8] }} | 报警邮箱: {{ data.recipient_email }}</p>
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
