# -*- coding: utf-8 -*-
"""
Email Notifier Module: 163 SMTP SSL Alerts (Phase 23 V1)
========================================================
Dispatches rich HTML notifications aligned with the V1 Strategy:
- BUY: Enter 1.0x Spot Long Top-1 (zero leverage, zero debt).
- EXIT: Exit to 100% USDT Cash Defense (macro defense).
- ROTATE: Switch between cross-sectional leaders (Top-1 rotation).
- DAILY_SUMMARY: Morning 08:02 BJT asset & strategy health report.
- TEST: Instant verification trigger.
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
    Sends rich dual-language HTML email notification via 163 SSL SMTP.
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        print("[EMAIL ERROR] Missing SMTP credentials in environment (SMTP_USER/SMTP_PASSWORD)!")
        return False

    data = dashboard_data or {}
    cap = data.get("capital", {})
    pos = data.get("position", {})
    mkt = data.get("market", {})
    leaderboard = data.get("leaderboard", {})
    pub_url = data.get("public_url", "https://percolate-zipfile-corned.ngrok-free.dev")

    curr_p = pos.get("current_price", mkt.get("curr_price", 0.0))
    entry_p = pos.get("entry_price", 0.0)
    top_sym = leaderboard.get("top_symbol", "BTCUSDT")

    if test_mode:
        subject = "🧪 [测试报警] 加密量化系统 V1 通道测试 (双重门控 Top-1 现货 & 现金防守)"
        badge_text = "TEST MODE VERIFICATION / 测试告警通道正常"
        action_headline = "系统 15 分钟自动化流水线监听已就绪，V1 邮件推送通道测试成功！"
    elif event_type == "BUY":
        subject = f"🚨 [买入信号] V1 双重门控放行！建议 1.0x 现货买入 {new_signal} | 当前价: ${curr_p:,.2f}"
        badge_text = f"BUY SIGNAL / 1.0x 现货进场信号 ({new_signal})"
        action_headline = f"BTC 宏观顺势且 {new_signal} 强势站上 EMA200 (+0.5% 滞回门控)，建议以 1.0x 现货全额买入 {new_signal}，捕获主升浪超额收益！"
    elif event_type == "EXIT":
        subject = f"🛡️ [防守离场] V1 宏观门控破坏！建议平仓退守 100% USDT 现金防守"
        badge_text = "EXIT SIGNAL / 退出多头切入现金防守"
        action_headline = f"BTC 宏观跌破或标的跌破 EMA200 (-0.5% 门控)！建议市价清空现货，全额持有 100% USDT 现金，规避单边大跌与基差风险！"
    elif event_type == "ROTATE":
        subject = f"🔄 [标的轮动] V1 截面龙头切换！建议从 {old_signal} 换仓至 {new_signal}"
        badge_text = "ROTATION SIGNAL / 龙头币种截面换仓"
        action_headline = f"截面动量评定更新：{new_signal} 评分超越 {old_signal}！建议市价卖出 {old_signal}，全额换入领涨龙头 {new_signal}。"
    else:
        subject = f"ℹ️ [每日晨报] V1 现货与现金策略资产播报 | 净值: ${cap.get('current_equity_usdt', 10000.0):,.2f}"
        badge_text = "DAILY SUMMARY REPORT / 每日资产与策略健康度汇总"
        action_headline = f"系统 15 分钟自动化流水线运行正常。当前策略模式：{pos.get('direction', '现金防御')}。"

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
            .footer {{ font-size: 11px; color: #64748b; border-top: 1px solid #24324f; padding-top: 14px; margin-top: 24px; line-height: 1.6; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="badge {'badge-buy' if event_type in ('BUY', 'ROTATE') else ('badge-exit' if event_type == 'EXIT' else '')}">{badge_text}</div>
                <div class="title">⚡ 加密量化系统 V1：双重宏观门控实时告警</div>
                <div style="font-size: 12px; color: #94a3b8;">15分钟高频流水线 | 北京时间: {data.get('timestamp_bjt', '')} | 最新闭合: {mkt.get('last_closed_bar', '')}</div>
            </div>

            <div class="alert-box">
                <b>💡 决策指引：</b> {action_headline}
            </div>

            <a href="{pub_url}" class="btn" target="_blank">👉 点击打开实时 Web 监控看板 (查看 V1 真实持仓与截面排名)</a>

            <div class="stat-grid">
                <div class="card">
                    <div class="card-title">当前持仓模式</div>
                    <div class="card-val" style="font-size: 18px; color: #38bdf8;">{pos.get('direction', '现金防御')}</div>
                    <div style="font-size: 12px; color: #94a3b8; margin-top: 4px;">账户净值: ${cap.get('current_equity_usdt', 10000.0):,.2f} USDT</div>
                </div>
                <div class="card">
                    <div class="card-title">浮动盈亏 (ROE)</div>
                    <div class="card-val" style="color: {pnl_color};">{pnl_sign}${pnl_val:,.2f}</div>
                    <div style="font-size: 12px; color: {pnl_color}; margin-top: 4px;">收益率: {pnl_sign}{pos.get('unrealized_pnl_pct', 0.0)}%</div>
                </div>
            </div>

            <div class="card" style="margin-bottom: 20px;">
                <div class="card-title" style="color: #38bdf8;">🛡️ V1 策略风控属性与门控参数</div>
                <table class="table-wrap">
                    <tr><td>当前持仓标的:</td><td>{pos.get('active_symbol', 'USDT_CASH')}</td></tr>
                    {f"<tr><td>开仓均价:</td><td>${entry_p:,.2f}</td></tr>" if entry_p else ""}
                    {f"<tr><td>当前市价:</td><td>${curr_p:,.2f}</td></tr>" if curr_p else ""}
                    <tr><td>杠杆倍数:</td><td style="color: #22c55e;">1.0x 现货 (零杠杆 / 无借贷负债)</td></tr>
                    <tr><td>清算风险:</td><td style="color: #22c55e;">无爆仓线 / 绝对安全</td></tr>
                    <tr><td>门控滞回缓冲:</td><td>±0.5% (进场 +0.5% 确认, 离场 -0.5% 防抖)</td></tr>
                    <tr><td>单边换手摩擦:</td><td>8.0 bps (0.08% / 次)</td></tr>
                    <tr><td>数据源状态:</td><td>{mkt.get('data_source', 'BINANCE_REST_API')}</td></tr>
                </table>
            </div>

            <div class="footer">
                <p>公网直达地址: <a href="{pub_url}" style="color: #38bdf8;">{pub_url}</a></p>
                <p>本邮件由 V1 自动化量化服务直发 | 接收者: {to_email}</p>
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
