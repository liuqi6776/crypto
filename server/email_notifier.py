# -*- coding: utf-8 -*-
"""
Email Notifier Module: 163 SMTP SSL Alerts (Phase 23)
=====================================================
Dispatches rich HTML notifications for BUY, EXIT, DAILY_SUMMARY, and TEST events.
"""

from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import smtplib
from typing import Any, Dict, Optional

from server.config import (
    DEFAULT_RECIPIENT,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_SERVER,
    SMTP_USER,
)


def send_alert_email(
    event_type: str = "SIGNAL_CHANGE",
    old_signal: Optional[str] = None,
    new_signal: Optional[str] = None,
    to_email: str = DEFAULT_RECIPIENT,
    dashboard_data: Optional[Dict[str, Any]] = None,
    test_mode: bool = False,
) -> bool:
    """
    Sends rich dual-language HTML email notification via 163 SSL SMTP:
    - BUY: Enter 3x Long + trailing stop + liquidation price + buffer
    - EXIT: Exit 3x Long + deploy into Core Funding Rate Arbitrage guide
    - DAILY_SUMMARY: Morning 08:02 BJT asset & strategy health report
    - TEST: Instant verification trigger
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        print("[EMAIL ERROR] Missing SMTP credentials in environment (SMTP_USER/SMTP_PASSWORD)!")
        return False

    data = dashboard_data or {}
    cap = data.get("capital", {})
    pos = data.get("position", {})
    mkt = data.get("market", {})
    fa = data.get("funding_arbitrage", {})
    leaderboard = data.get("leaderboard", {})
    pub_url = data.get("public_url", "https://percolate-zipfile-corned.ngrok-free.dev")

    curr_p = mkt.get("curr_price", 0.0)
    stop_p = pos.get("trailing_stop", 0.0)
    liq_p = pos.get("liquidation_price", 0.0)
    bb_u = mkt.get("bb_upper", 0.0)
    bb_m = mkt.get("bb_mid", 0.0)
    ema_val = mkt.get("ema200", 0.0)
    funding_info = fa.get("funding_info", {})
    apy_val = funding_info.get("annualized_apy_pct", 15.0)

    if test_mode:
        subject = "🧪 [测试报警] ETH 3x 杠杆波段与 Core 资金费率套利系统通道测试"
        badge_text = "TEST MODE VERIFICATION / 测试告警通道正常"
        action_headline = "系统 15 分钟自动化流水线监听已就绪，邮件推送通道测试成功！"
    elif new_signal == "BUY":
        subject = f"🚨 [买入信号] ETH 4h 触发突破做多！建议部署 3x 杠杆多头 | 当前价: ${curr_p:,.2f}"
        badge_text = "BUY SIGNAL TRIGGERED / 3x 杠杆多头进场信号"
        action_headline = f"ETH 4h 闭合价 ${curr_p:,.2f} 突破 120 布林上轨 (${bb_u:,.2f})！若此前有资金费率套利空单，请先平空，并将资金切入 3x 杠杆多头！"
    elif new_signal == "EXIT":
        subject = f"🛑 [平仓离场] ETH 4h 触发止损/平仓！建议全额清多，切换至 Core 资金费率无风险套利"
        badge_text = "EXIT SIGNAL TRIGGERED / 平仓观望并激活套利"
        action_headline = f"ETH 4h 多头已触发离场条件！建议全额平仓锁定利润或止损，资金转入 Core Only (100% 资金费率套利) 享受约 {apy_val}% 无风险生息！"
    else:
        subject = f"ℹ️ [每日晨报] ETH 3x & Core 套利系统资产播报 | 现价: ${curr_p:,.2f}"
        badge_text = "DAILY SUMMARY REPORT / 每日资产与策略健康度汇总"
        action_headline = f"系统 15 分钟自动化运行正常。当前推荐模式：{leaderboard.get('recommended_mode', '监测中')}。"

    pnl_val = pos.get("unrealized_pnl_usdt", 0.0)
    pnl_color = "#3fb950" if pnl_val >= 0 else "#f85149"
    pnl_sign = "+" if pnl_val >= 0 else ""

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #0b0f19; color: #cbd5e1; padding: 20px; }}
            .container {{ max-width: 680px; margin: 0 auto; background: #131b2e; border: 1px solid #1e293b; border-radius: 14px; padding: 24px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
            .header {{ border-bottom: 1px solid #24324f; padding-bottom: 18px; margin-bottom: 20px; }}
            .badge {{ display: inline-block; padding: 6px 12px; border-radius: 6px; font-size: 13px; font-weight: 700; background: #0284c7; color: #ffffff; margin-bottom: 10px; }}
            .badge-exit {{ background: #dc2626; }}
            .badge-buy {{ background: #16a34a; }}
            .title {{ font-size: 22px; font-weight: 800; color: #f8fafc; margin: 0 0 8px 0; }}
            .alert-box {{ background: rgba(56, 189, 248, 0.12); border-left: 4px solid #38bdf8; padding: 14px 18px; border-radius: 0 8px 8px 0; margin-bottom: 20px; font-size: 14px; color: #e2e8f0; line-height: 1.6; }}
            .stat-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 20px; }}
            .card {{ background: #1a243b; border: 1px solid #283757; border-radius: 10px; padding: 16px; }}
            .card-title {{ font-size: 12px; color: #94a3b8; text-transform: uppercase; font-weight: 600; margin-bottom: 6px; }}
            .card-val {{ font-size: 22px; font-weight: 800; color: #ffffff; }}
            .btn {{ display: block; text-align: center; background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #ffffff !important; padding: 14px 0; border-radius: 8px; font-weight: 700; text-decoration: none; font-size: 16px; margin: 24px 0; box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4); }}
            .table-wrap {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 10px; }}
            .table-wrap td {{ padding: 7px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }}
            .table-wrap td:last-child {{ text-align: right; font-weight: 700; color: #f1f5f9; }}
            .guide-step {{ background: #162035; border: 1px solid #273756; border-radius: 8px; padding: 12px 16px; margin-bottom: 10px; }}
            .step-num {{ display: inline-block; width: 22px; height: 22px; background: #38bdf8; color: #000; border-radius: 50%; text-align: center; font-weight: 800; font-size: 12px; line-height: 22px; margin-right: 8px; }}
            .footer {{ font-size: 11px; color: #64748b; border-top: 1px solid #24324f; padding-top: 14px; margin-top: 24px; line-height: 1.6; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="badge {'badge-buy' if new_signal == 'BUY' else ('badge-exit' if new_signal == 'EXIT' else '')}">{badge_text}</div>
                <div class="title">⚡ ETH 3x 杠杆波段与资金费率套利系统</div>
                <div style="font-size: 12px; color: #94a3b8;">执行周期: 15分钟自动轮询 | 北京时间: {data.get('timestamp_bjt', '')} | 4h 闭合时间: {mkt.get('last_closed_bar', '')}</div>
            </div>

            <div class="alert-box">
                <b>💡 核心决策指引：</b> {action_headline}
            </div>

            <a href="{pub_url}" class="btn" target="_blank">👉 点击打开实时 Web 监控看板 (查看 3x 杠杆清算线与实时看板)</a>

            <div class="stat-grid">
                <div class="card">
                    <div class="card-title">3x 杠杆仓位市值 / 本金</div>
                    <div class="card-val">${pos.get('nominal_usdt', 0.0):,.2f} <span style="font-size: 13px; color: #38bdf8;">(3.0x)</span></div>
                    <div style="font-size: 12px; color: #94a3b8; margin-top: 4px;">基准资金: ${cap.get('current_equity_usdt', 10000.0):,.2f} USDT</div>
                </div>
                <div class="card">
                    <div class="card-title">3x 杠杆浮动盈亏 (ROE)</div>
                    <div class="card-val" style="color: {pnl_color};">{pnl_sign}${pnl_val:,.2f}</div>
                    <div style="font-size: 12px; color: {pnl_color}; margin-top: 4px;">收益率: {pnl_sign}{pos.get('unrealized_roe_pct', 0.0)}%</div>
                </div>
            </div>

            <div class="card" style="margin-bottom: 20px;">
                <div class="card-title" style="color: #38bdf8;">🛡️ 3x 杠杆清算防线与跟踪止损保护 (硬核风控)</div>
                <table class="table-wrap">
                    <tr><td>当前 ETH 市价:</td><td>${curr_p:,.2f}</td></tr>
                    {f"<tr><td>入场开仓均价:</td><td>${pos.get('entry_price', 0.0):,.2f}</td></tr>" if pos.get('entry_price') else ""}
                    {f"<tr><td style='color: #ef4444;'>3x 动态跟踪止损线 (3x ATR):</td><td style='color: #ef4444;'>${stop_p:,.2f} (距现价 {pos.get('distance_to_stop_pct', 0.0)}%)</td></tr>" if stop_p else ""}
                    {f"<tr><td style='color: #f59e0b;'>⚠️ 3x 估算强制平仓线:</td><td style='color: #f59e0b;'>${liq_p:,.2f} (距现价 {pos.get('distance_to_liq_pct', 0.0)}%)</td></tr>" if liq_p else ""}
                    {f"<tr><td>止损与强平安全缓冲区:</td><td style='color: #22c55e;'>{pos.get('safety_buffer_pct', 0.0)}% (优先市价止损，绝不触及强平)</td></tr>" if pos.get('safety_buffer_pct') else ""}
                    <tr><td>120 布林通道上轨:</td><td style="color: #38bdf8;">${bb_u:,.2f}</td></tr>
                    <tr><td>120 布林中轨:</td><td>${bb_m:,.2f}</td></tr>
                    <tr><td>EMA 200 宏观过滤:</td><td>${ema_val:,.2f}</td></tr>
                </table>
            </div>

            <div class="card">
                <div class="card-title" style="color: #f59e0b;">💰 Core Only (100% 资金费率套利) 待机指引 (当前年化: {apy_val}%)</div>
                <div style="font-size: 13px; color: #94a3b8; margin-bottom: 12px;">
                    当前 8h 资金费率: <b>{funding_info.get('funding_rate_8h_pct', 0.01)}%</b> | 下次结算倒计时: <b>{funding_info.get('countdown', '--:--:--')}</b>
                </div>
                <div class="guide-step">
                    <span class="step-num">1</span><b>分流资金</b>：${fa.get('half_capital_usdt', 5000):,.0f} USDT 买入 ETH 现货，${fa.get('half_capital_usdt', 5000):,.0f} USDT 划入合约账户。
                </div>
                <div class="guide-step">
                    <span class="step-num">2</span><b>对冲锁定</b>：现货买入 ETH，永续合约等额开 1x 空单对冲，Delta 归零无视涨跌。
                </div>
                <div class="guide-step">
                    <span class="step-num">3</span><b>稳健生息</b>：每天 08:00 / 16:00 / 24:00 (BJT) 稳收资金费，预估单日利息约 <b>${fa.get('est_daily_income_usdt', 3.5):,.2f} USDT</b>。
                </div>
                <div class="guide-step">
                    <span class="step-num">4</span><b>信号触发即转</b>：当收到【BUY 信号邮件】时，平掉空单将全部资金投入 3x 杠杆波段多头。
                </div>
            </div>

            <div class="footer">
                <p>公网直达地址: <a href="{pub_url}" style="color: #38bdf8;">{pub_url}</a></p>
                <p>本邮件由 15 分钟自动化量化服务直发 | 接收者: {to_email}</p>
            </div>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["From"] = SMTP_USER
    msg["To"] = to_email
    msg["Subject"] = Header(subject, "utf-8")
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=15)
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, to_email, msg.as_string())
        server.quit()
        print(f"[EMAIL SUCCESS] Notification successfully sent to {to_email} ({event_type})")
        return True
    except Exception as e:
        print(f"[EMAIL FAILURE] Failed to send email to {to_email}: {repr(e)}")
        return False
