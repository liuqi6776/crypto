# -*- coding: utf-8 -*-
"""
Web Dashboard & Monitoring Server: ETH 3x Strategy & Core Funding Arbitrage
===========================================================================
Hosts an institutional real-time web dashboard displaying:
- ETH 3x Leveraged Structural Trend trading (Nominal $30,000 USDT on $10,000 base)
- Liquidation price & monotonic 3x ATR trailing stop safety buffer
- Real-time Core Only (100% Delta-Neutral Funding Rate Arbitrage) guide & Binance APY
- Background active 4h signal transition listener with instant HTML email alerts
- Manual test email trigger and 30-second auto-refresh
"""

from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import threading
import time as time_lib
from typing import Any, Dict, Optional
import urllib.request

from flask import Flask, jsonify, render_template_string, request
import pandas as pd
from dotenv import load_dotenv

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
load_dotenv(root_dir / ".env")
load_dotenv(Path(r"C:\Users\liuqi\quant_system_v2\.env"))
load_dotenv(Path.home() / ".env")

from crypto_quant.paper.config import (
    CONFIG_HASH,
    DOCS_DIR,
    ENABLE_REAL_ORDERS,
    EXPERIMENT_ID,
    JOURNAL_PATH,
    LOG_DIR,
    PAPER_MODE,
    STATE_PATH,
    STRATEGY_NAME,
    TIMEFRAME,
    get_code_commit,
)
from crypto_quant.paper.journal import PaperJournal
from crypto_quant.paper.service import PaperService
from crypto_quant.paper.state import PortfolioPaperState
from crypto_quant.paper.strategy import StructuralTrendPaperStrategy
from crypto_quant.paper.leverage_model import LeverageModel
from crypto_quant.paper.funding_arb import get_funding_arbitrage_guide, fetch_binance_funding_info

# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================
INITIAL_CAPITAL_USDT: float = 10000.0  # 10,000 USDT base capital
ETH_LEVERAGE: float = float(os.getenv("ETH_LEVERAGE", "3.0"))  # 3.0x Leverage
DEFAULT_RECIPIENT: str = os.getenv("PAPER_EMAIL_RECIPIENT") or os.getenv("RECEIVER_EMAIL") or "568701293@qq.com"
DEFAULT_PUBLIC_URL: str = os.getenv("PAPER_PUBLIC_URL", "")
BIND_HOST: str = os.getenv("BIND_HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8088"))

app = Flask(__name__)
service_lock = threading.Lock()
PUBLIC_TUNNEL_URL: Optional[str] = None
leverage_model = LeverageModel(default_leverage=ETH_LEVERAGE)

# Global tracker for detecting signal changes
LAST_RECORDED_SIGNAL: Optional[str] = None
LAST_RECORDED_BAR_TIME: Optional[str] = None


def get_effective_public_url() -> str:
    """Resolves external public HTTPS URL or local host fallback."""
    global PUBLIC_TUNNEL_URL
    try:
        req = urllib.request.Request("http://127.0.0.1:4040/api/tunnels", headers={"User-Agent": "PaperRunner/1.0"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode())
            for t in data.get("tunnels", []):
                u = t.get("public_url", "")
                if u.startswith("https://"):
                    PUBLIC_TUNNEL_URL = u
                    return u
    except Exception:
        pass

    if PUBLIC_TUNNEL_URL and PUBLIC_TUNNEL_URL.startswith("https://"):
        return PUBLIC_TUNNEL_URL

    env_url = os.getenv("PUBLIC_TUNNEL_URL") or os.getenv("NGROK_URL")
    if env_url and env_url.startswith("https://"):
        PUBLIC_TUNNEL_URL = env_url
        return env_url

    if DEFAULT_PUBLIC_URL:
        PUBLIC_TUNNEL_URL = DEFAULT_PUBLIC_URL
        return DEFAULT_PUBLIC_URL
    return f"http://127.0.0.1:{PORT}"


# ============================================================================
# DATA & STATUS EXTRACTION
# ============================================================================
def get_current_dashboard_data() -> Dict[str, Any]:
    """Extracts complete operational state scaled to 10,000 USDT with 3x leverage metrics."""
    state = PortfolioPaperState.load(STATE_PATH) if STATE_PATH.exists() else PortfolioPaperState.create_initial()
    eth_s = state.eth_state

    # Base capital calculations
    equity_usdt = eth_s.total_equity * INITIAL_CAPITAL_USDT
    peak_usdt = eth_s.peak_equity * INITIAL_CAPITAL_USDT
    is_in_pos = (eth_s.position == 1)
    pos_direction = "LONG (3x)" if is_in_pos else "FLAT (Core套利)"

    # Compute live indicators
    strat = StructuralTrendPaperStrategy()
    service = PaperService()
    df = service.fetcher.fetch_closed_klines("ETHUSDT", interval=TIMEFRAME, limit=250, check_freshness=False)
    ind = strat.compute_indicators(df)

    curr_close = ind["close"]
    bb_upper = ind["bb_upper"]
    bb_mid = ind["bb_mid"]
    bb_lower = ind["bb_lower"]
    ema200 = ind["ema200"]
    atr14 = ind["atr"]
    swing_low = ind["swing_low"]
    macro_mult = ind["macro_mult"]

    # 3x Leverage Risk Metrics
    entry_p = eth_s.entry_price if is_in_pos else None
    high_p = eth_s.highest_price_since_entry if is_in_pos else None
    stop_p = eth_s.trailing_stop_price if is_in_pos else None

    lev_metrics = leverage_model.compute_metrics(
        base_equity_usdt=equity_usdt,
        entry_price=entry_p,
        current_price=curr_close,
        highest_price=high_p,
        trailing_stop_price=stop_p,
        atr=atr14,
        is_in_position=is_in_pos,
        leverage=ETH_LEVERAGE,
    )

    # Core Funding Rate Arbitrage Info & Guide
    funding_guide = get_funding_arbitrage_guide(base_capital_usdt=equity_usdt)

    # Trigger distances
    dist_to_buy_pct = ((bb_upper - curr_close) / curr_close) * 100.0

    # Read recent events
    journal = PaperJournal(JOURNAL_PATH)
    events = journal.read_all_events()
    trade_events = [e for e in events if e.get("event_type") == "POSITION_CLOSED"][-5:]
    signal_events = [e for e in events if e.get("event_type") == "SIGNAL_CREATED"][-5:]

    now_utc = datetime.now(timezone.utc)
    now_bjt = now_utc + timedelta(hours=8)
    last_bar_time = eth_s.last_processed_bar_time or str(df.index[-1])

    # Mode determination
    active_mode = "ETH_3X_LONG" if is_in_pos else "CORE_FUNDING_ARB"

    return {
        "timestamp_utc": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "timestamp_bjt": now_bjt.strftime("%Y-%m-%d %H:%M:%S BJT"),
        "active_mode": active_mode,
        "experiment_id": EXPERIMENT_ID,
        "strategy_name": STRATEGY_NAME,
        "public_url": get_effective_public_url(),
        "recipient_email": DEFAULT_RECIPIENT,
        "capital": {
            "initial_usdt": round(INITIAL_CAPITAL_USDT, 2),
            "current_equity_usdt": round(equity_usdt, 2),
            "peak_usdt": round(peak_usdt, 2),
            "pnl_usdt": round((eth_s.total_equity - 1.0) * INITIAL_CAPITAL_USDT, 2),
            "pnl_pct": round((eth_s.total_equity - 1.0) * 100.0, 2),
            "drawdown_pct": round(eth_s.drawdown * 100.0, 2),
            "total_fees_usdt": round(eth_s.total_fees * INITIAL_CAPITAL_USDT, 2),
        },
        "position": {
            "symbol": "ETHUSDT",
            "direction": pos_direction,
            "is_in_pos": is_in_pos,
            "leverage": ETH_LEVERAGE,
            "nominal_usdt": lev_metrics["nominal_position_usdt"],
            "entry_price": lev_metrics["entry_price"],
            "entry_time": eth_s.entry_time,
            "trailing_stop": lev_metrics["trailing_stop_price"],
            "liquidation_price": lev_metrics["liquidation_price"],
            "distance_to_liq_pct": lev_metrics["distance_to_liq_pct"],
            "distance_to_stop_pct": lev_metrics["distance_to_stop_pct"],
            "safety_buffer_pct": lev_metrics["safety_buffer_pct"],
            "unrealized_pnl_usdt": lev_metrics["unrealized_pnl_usdt"],
            "unrealized_roe_pct": lev_metrics["unrealized_roe_pct"],
            "is_safe": lev_metrics["is_safe"],
            "highest_price": lev_metrics["highest_price"],
            "bars_in_pos": eth_s.bars_in_position,
        },
        "funding_arbitrage": funding_guide,
        "market": {
            "symbol": "ETHUSDT",
            "curr_price": round(curr_close, 2),
            "last_closed_bar": last_bar_time,
            "bb_upper": round(bb_upper, 2),
            "bb_mid": round(bb_mid, 2),
            "bb_lower": round(bb_lower, 2),
            "ema200": round(ema200, 2),
            "atr14": round(atr14, 2),
            "swing_low": round(swing_low, 2),
            "macro_status": "强多头顺势 (1.0x)" if macro_mult == 1.0 else "弱势防守 (0.5x)",
            "dist_to_buy_pct": round(dist_to_buy_pct, 2),
        },
        "trades_history": trade_events,
        "signals_history": signal_events,
        "system": {
            "code_commit": get_code_commit(),
            "config_hash": CONFIG_HASH,
            "paper_mode": PAPER_MODE,
            "enable_real_orders": ENABLE_REAL_ORDERS,
        },
    }


# ============================================================================
# INSTANT SIGNAL CHANGE EMAIL ALERT DISPATCHER
# ============================================================================
def send_signal_change_alert(
    event_type: str = "SIGNAL_CHANGE",
    old_signal: Optional[str] = None,
    new_signal: Optional[str] = None,
    to_email: str = DEFAULT_RECIPIENT,
    test_mode: bool = False,
) -> bool:
    """
    Sends rich HTML email notification immediately when signal changes:
    - FLAT -> BUY (Enter 3x Long + exact stop and liquidation price)
    - HOLD -> EXIT (Exit 3x Long + step-by-step Core Funding Arbitrage deployment guide)
    - TEST (Verification trigger)
    """
    sender_email = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    smtp_server = os.getenv("SMTP_SERVER", "smtp.163.com")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))

    if not sender_email or not password:
        print("[EMAIL ERROR] Missing SMTP credentials in environment!")
        return False

    data = get_current_dashboard_data()
    cap = data["capital"]
    pos = data["position"]
    mkt = data["market"]
    fa = data["funding_arbitrage"]
    pub_url = data["public_url"]

    if test_mode:
        subject = f"🧪 [测试报警] ETH 3x 杠杆波段与 Core 资金费率套利系统通道测试"
        badge_text = "TEST MODE VERIFICATION / 测试告警通道正常"
        action_headline = "系统信号变动监听器已就绪，邮件推送通道测试成功！"
    elif new_signal == "BUY":
        subject = f"🚨 [买入信号] ETH 4h 触发突破做多！建议部署 3x 杠杆多头 | 当前价: ${mkt['curr_price']:,.2f}"
        badge_text = "BUY SIGNAL TRIGGERED / 3x 杠杆多头进场信号"
        action_headline = f"ETH 4h 闭合价 ${mkt['curr_price']:,.2f} 突破 120 布林上轨 (${mkt['bb_upper']:,.2f})！若此前有资金费率套利空单，请先平空，并将资金切入 3x 杠杆多头！"
    elif new_signal == "EXIT":
        subject = f"🛑 [平仓离场] ETH 4h 触发止损/平仓！建议全额清多，切换至 Core 资金费率无风险套利"
        badge_text = "EXIT SIGNAL TRIGGERED / 平仓观望并激活套利"
        action_headline = f"ETH 4h 多头已触发离场条件！建议全额平仓锁定利润或止损，资金转入 Core Only (100% 资金费率套利) 享受约 {fa['funding_info']['annualized_apy_pct']}% 无风险生息！"
    else:
        subject = f"ℹ️ [状态更新] ETH 3x 策略持仓跟踪 | 现价: ${mkt['curr_price']:,.2f} (止损位: ${pos['trailing_stop']:,.2f})"
        badge_text = "POSITION UPDATE / 跟踪止损上移锁定利润"
        action_headline = f"ETH 3x 多头持续运行中，最新单调移动止损位已上移至 ${pos['trailing_stop']:,.2f}。"

    pnl_color = "#3fb950" if pos["unrealized_pnl_usdt"] >= 0 else "#f85149"
    pnl_sign = "+" if pos["unrealized_pnl_usdt"] >= 0 else ""

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
                <div class="title">⚡ ETH 3x 杠杆波段与资金费率套利实时提醒</div>
                <div style="font-size: 12px; color: #94a3b8;">北京时间: {data['timestamp_bjt']} | 4h 闭合时间: {mkt['last_closed_bar']}</div>
            </div>

            <div class="alert-box">
                <b>💡 核心决策指引：</b> {action_headline}
            </div>

            <a href="{pub_url}" class="btn" target="_blank">👉 点击打开实时 Web 监控看板 (查看 3x 杠杆清算线与实时看板)</a>

            <div class="stat-grid">
                <div class="card">
                    <div class="card-title">3x 杠杆仓位市值 / 本金</div>
                    <div class="card-val">${pos['nominal_usdt']:,.2f} <span style="font-size: 13px; color: #38bdf8;">(3.0x)</span></div>
                    <div style="font-size: 12px; color: #94a3b8; margin-top: 4px;">基准资金: ${cap['current_equity_usdt']:,.2f} USDT</div>
                </div>
                <div class="card">
                    <div class="card-title">3x 杠杆浮动盈亏 (ROE)</div>
                    <div class="card-val" style="color: {pnl_color};">{pnl_sign}${pos['unrealized_pnl_usdt']:,.2f}</div>
                    <div style="font-size: 12px; color: {pnl_color}; margin-top: 4px;">收益率: {pnl_sign}{pos['unrealized_roe_pct']}%</div>
                </div>
            </div>

            <div class="card" style="margin-bottom: 20px;">
                <div class="card-title" style="color: #38bdf8;">🛡️ 3x 杠杆清算防线与跟踪止损保护 (硬核风控)</div>
                <table class="table-wrap">
                    <tr><td>当前 ETH 市价:</td><td>${mkt['curr_price']:,.2f}</td></tr>
                    {f"<tr><td>入场开仓均价:</td><td>${pos['entry_price']:,.2f}</td></tr>" if pos['entry_price'] else ""}
                    {f"<tr><td style='color: #ef4444;'>3x 动态跟踪止损线 (3x ATR):</td><td style='color: #ef4444;'>${pos['trailing_stop']:,.2f} (距现价 {pos['distance_to_stop_pct']}%)</td></tr>" if pos['trailing_stop'] else ""}
                    {f"<tr><td style='color: #f59e0b;'>⚠️ 3x 估算强制平仓线:</td><td style='color: #f59e0b;'>${pos['liquidation_price']:,.2f} (距现价 {pos['distance_to_liq_pct']}%)</td></tr>" if pos['liquidation_price'] else ""}
                    {f"<tr><td>止损与强平安全缓冲区:</td><td style='color: #22c55e;'>{pos['safety_buffer_pct']}% (优先市价止损，绝不触及强平)</td></tr>" if pos['safety_buffer_pct'] else ""}
                    <tr><td>120 布林通道上轨:</td><td style="color: #38bdf8;">${mkt['bb_upper']:,.2f}</td></tr>
                    <tr><td>120 布林中轨:</td><td>${mkt['bb_mid']:,.2f}</td></tr>
                    <tr><td>EMA 200 宏观过滤:</td><td>${mkt['ema200']:,.2f}</td></tr>
                </table>
            </div>

            <div class="card">
                <div class="card-title" style="color: #f59e0b;">💰 Core Only (100% 资金费率套利) 待机指引 (当前年化: {fa['funding_info']['annualized_apy_pct']}%)</div>
                <div style="font-size: 13px; color: #94a3b8; margin-bottom: 12px;">
                    当前 8h 资金费率: <b>{fa['funding_info']['funding_rate_8h_pct']}%</b> | 下次结算倒计时: <b>{fa['funding_info']['countdown']}</b>
                </div>
                <div class="guide-step">
                    <span class="step-num">1</span><b>分流资金</b>：${fa['half_capital_usdt']:,.0f} USDT 买入 ETH 现货，${fa['half_capital_usdt']:,.0f} USDT 划入合约账户。
                </div>
                <div class="guide-step">
                    <span class="step-num">2</span><b>对冲锁定</b>：现货买入 ETH，永续合约等额开 1x 空单对冲，Delta 归零无视涨跌。
                </div>
                <div class="guide-step">
                    <span class="step-num">3</span><b>稳健生息</b>：每天 08:00 / 16:00 / 24:00 (BJT) 稳收资金费，预估单日利息约 <b>${fa['est_daily_income_usdt']} USDT</b>。
                </div>
                <div class="guide-step">
                    <span class="step-num">4</span><b>信号触发即转</b>：当收到【BUY 信号邮件】时，平掉空单将全部资金投入 3x 杠杆波段多头。
                </div>
            </div>

            <div class="footer">
                <p>公网直达地址: <a href="{pub_url}" style="color: #38bdf8;">{pub_url}</a></p>
                <p>本邮件由自动化量化系统直发 | 接收者: {to_email} | Commit: {data['system']['code_commit'][:8]}</p>
            </div>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["From"] = sender_email
    msg["To"] = to_email
    msg["Subject"] = Header(subject, "utf-8")
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=15)
        server.login(sender_email, password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        print(f"[EMAIL SUCCESS] Alert successfully sent to {to_email}")
        return True
    except Exception as e:
        print(f"[EMAIL FAILURE] Failed to send alert email to {to_email}: {repr(e)}")
        return False


def send_email_report(to_email: str = DEFAULT_RECIPIENT, is_manual: bool = False) -> bool:
    """Backwards-compatible wrapper for sending dashboard summary emails."""
    return send_signal_change_alert(
        event_type="MANUAL" if is_manual else "DAILY_SUMMARY",
        to_email=to_email,
        test_mode=False,
    )


# ============================================================================
# MODERN DUAL-MODE HTML DASHBOARD TEMPLATE
# ============================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ETH 3x 杠杆波段 & Core 资金费率套利实时监控看板</title>
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
                    <p>策略: structural_trend_v1 (120-bar 布林 + EMA200 + 3x 杠杆) | 10,000 USDT 本金</p>
                </div>
            </div>
            <div class="btn-group">
                <button class="btn" onclick="sendTestEmail()" id="btn-email">
                    <span id="email-btn-text">✉️ 发送测试报警邮件</span>
                </button>
                <button class="btn btn-primary" onclick="triggerRefresh()" id="btn-refresh">
                    <span id="refresh-btn-text">🔄 立即刷新数据</span>
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
                4h 最新闭合: <span id="bar-time">{{ data.market.last_closed_bar }}</span> | 刷新时间: <span id="sync-time">{{ data.timestamp_bjt }}</span>
            </div>
        </div>

        <!-- 核心卡片网格 -->
        <div class="grid-cards">
            <!-- 卡片 1: 3x 杠杆仓位与风控清算线 -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">ETH 3x 杠杆仓位与风控清算线</span>
                    <span class="pill {{ 'pill-green' if data.position.is_in_pos else 'pill-amber' }}">
                        {{ data.position.direction }}
                    </span>
                </div>
                {% if data.position.is_in_pos %}
                    <div class="metric-big" style="color: #38bdf8;">${{ "{:,.2f}".format(data.position.nominal_usdt) }}</div>
                    <div style="font-size: 13px; margin-top: 4px; margin-bottom: 14px; color: {{ '#22c55e' if data.position.unrealized_pnl_usdt >= 0 else '#ef4444' }};">
                        浮动盈亏: <b>{{ '+' if data.position.unrealized_pnl_usdt >= 0 else '' }}${{ "{:,.2f}".format(data.position.unrealized_pnl_usdt) }} ({{ '+' if data.position.unrealized_roe_pct >= 0 else '' }}{{ data.position.unrealized_roe_pct }}% ROE)</b>
                    </div>
                    <div class="row-item"><span class="row-label">开仓成交价:</span><span class="row-val">${{ "{:,.2f}".format(data.position.entry_price) }}</span></div>
                    <div class="row-item"><span class="row-label">3x 动态跟踪止损 (3x ATR):</span><span class="row-val" style="color: #ef4444;">${{ "{:,.2f}".format(data.position.trailing_stop) }} (距现价 {{ data.position.distance_to_stop_pct }}%)</span></div>
                    <div class="row-item"><span class="row-label">3x 估算强制平仓线:</span><span class="row-val" style="color: #f59e0b;">${{ "{:,.2f}".format(data.position.liquidation_price) }} (距现价 {{ data.position.distance_to_liq_pct }}%)</span></div>
                    <div class="row-item"><span class="row-label">止损与强平安全缓冲:</span><span class="row-val" style="color: #22c55e;">+{{ data.position.safety_buffer_pct }}% (优先止损，绝不触及强平)</span></div>
                    <div class="row-item"><span class="row-label">持仓时间:</span><span class="row-val">{{ data.position.bars_in_pos }} 根 4h ({{ data.position.bars_in_pos * 4 }} 小时)</span></div>
                {% else %}
                    <div class="metric-big" style="color: var(--text-secondary);">$0.00</div>
                    <div style="font-size: 13px; color: var(--text-secondary); margin-top: 4px; margin-bottom: 14px;">
                        当前处于 4h 空仓等待期，资金 100% 部署于 Core 资金费率无风险套利
                    </div>
                    <div class="row-item"><span class="row-label">当前 ETH 现价:</span><span class="row-val">${{ "{:,.2f}".format(data.market.curr_price) }}</span></div>
                    <div class="row-item"><span class="row-label">突破做多买点 (120布林上轨):</span><span class="row-val" style="color: #38bdf8;">${{ "{:,.2f}".format(data.market.bb_upper) }} (差 {{ data.market.dist_to_buy_pct }}%)</span></div>
                    <div class="row-item"><span class="row-label">突破后计划杠杆:</span><span class="row-val">3.0x Isolated Margin</span></div>
                {% endif %}
            </div>

            <!-- 卡片 2: 账户本金与收益统计 -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">账户净值与收益统计 (USDT)</span>
                    <span class="pill {{ 'pill-green' if data.capital.pnl_usdt >= 0 else 'pill-red' }}">
                        {{ '+' if data.capital.pnl_usdt >= 0 else '' }}{{ data.capital.pnl_pct }}%
                    </span>
                </div>
                <div class="metric-big">${{ "{:,.2f}".format(data.capital.current_equity_usdt) }}</div>
                <div style="font-size: 13px; color: var(--text-secondary); margin-top: 4px; margin-bottom: 14px;">
                    累计收益: <b style="color: {{ '#22c55e' if data.capital.pnl_usdt >= 0 else '#ef4444' }}">{{ '+' if data.capital.pnl_usdt >= 0 else '' }}${{ "{:,.2f}".format(data.capital.pnl_usdt) }} USDT</b>
                </div>
                <div class="row-item"><span class="row-label">初始基准本金:</span><span class="row-val">$10,000.00 USDT</span></div>
                <div class="row-item"><span class="row-label">历史最高净值:</span><span class="row-val">${{ "{:,.2f}".format(data.capital.peak_usdt) }}</span></div>
                <div class="row-item"><span class="row-label">当前回撤:</span><span class="row-val">{{ data.capital.drawdown_pct }}%</span></div>
                <div class="row-item"><span class="row-label">预警通知邮箱:</span><span class="row-val" style="color: #38bdf8;">{{ data.recipient_email }}</span></div>
            </div>

            <!-- 卡片 3: 4h 结构指标诊断 -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">4h 结构指标与关键触发线</span>
                    <span class="pill pill-blue">ETH: ${{ "{:,.2f}".format(data.market.curr_price) }}</span>
                </div>
                <div class="row-item"><span class="row-label">120 布林上轨 (突破买点):</span><span class="row-val" style="color: #38bdf8;">${{ "{:,.2f}".format(data.market.bb_upper) }}</span></div>
                <div class="row-item"><span class="row-label">120 布林中轨 (多头防线):</span><span class="row-val">${{ "{:,.2f}".format(data.market.bb_mid) }}</span></div>
                <div class="row-item"><span class="row-label">EMA 200 宏观过滤线:</span><span class="row-val" style="color: #f59e0b;">${{ "{:,.2f}".format(data.market.ema200) }} ({{ data.market.macro_status }})</span></div>
                <div class="row-item"><span class="row-label">ATR 14 (4h 波动幅度):</span><span class="row-val">${{ "{:,.2f}".format(data.market.atr14) }}</span></div>
                <div class="row-item"><span class="row-label">3 ATR 止损步进距离:</span><span class="row-val">${{ "{:,.2f}".format(data.market.atr14 * 3.0) }}</span></div>
            </div>
        </div>

        <!-- Core Only (100% 资金费率无风险套利) 专区与实操指引 -->
        <div class="card" style="margin-bottom: 20px; border-color: rgba(245, 158, 11, 0.4);">
            <div class="card-header">
                <div>
                    <span class="card-title" style="color: #fbbf24; font-size: 15px;">💰 Core Only: 100% 资金费率无风险套利 (空仓期现金流引擎)</span>
                    <div style="font-size: 12px; color: var(--text-secondary); margin-top: 2px;">
                        无方向性敞口 (Delta=0) | 6年最大回撤仅 0.18% | 适合在 4h 波段空仓期间让 10,000 USDT 稳健生息
                    </div>
                </div>
                <span class="pill pill-amber" style="font-size: 14px;">
                    实时年化: {{ data.funding_arbitrage.funding_info.annualized_apy_pct }}% APY
                </span>
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 16px;">
                <div style="background: var(--card-color); padding: 12px; border-radius: 8px;">
                    <div style="font-size: 11px; color: var(--text-secondary);">当前 8h 资金费率</div>
                    <div style="font-size: 18px; font-weight: 800; color: #fbbf24;">{{ data.funding_arbitrage.funding_info.funding_rate_8h_pct }}%</div>
                </div>
                <div style="background: var(--card-color); padding: 12px; border-radius: 8px;">
                    <div style="font-size: 11px; color: var(--text-secondary);">下次结算倒计时</div>
                    <div style="font-size: 18px; font-weight: 800; color: #38bdf8;">{{ data.funding_arbitrage.funding_info.countdown }}</div>
                </div>
                <div style="background: var(--card-color); padding: 12px; border-radius: 8px;">
                    <div style="font-size: 11px; color: var(--text-secondary);">预计单日套利收入</div>
                    <div style="font-size: 18px; font-weight: 800; color: #22c55e;">+${{ data.funding_arbitrage.est_daily_income_usdt }} USDT</div>
                </div>
                <div style="background: var(--card-color); padding: 12px; border-radius: 8px;">
                    <div style="font-size: 11px; color: var(--text-secondary);">预计单月套利收入</div>
                    <div style="font-size: 18px; font-weight: 800; color: #22c55e;">+${{ data.funding_arbitrage.est_monthly_income_usdt }} USDT</div>
                </div>
            </div>

            <div style="font-weight: 700; font-size: 13px; margin-bottom: 8px; color: #f1f5f9;">📋 实盘 4 步无风险套利实操指南 (空仓期执行)：</div>
            {% for step in data.funding_arbitrage.steps %}
                <div class="step-box">
                    <span class="step-num">{{ step.step }}</span><b>{{ step.title }}</b>: {{ step.desc }}
                </div>
            {% endfor %}
        </div>

        <div class="footer">
            <p>🛡️ <b>系统安全与风控声明</b>: 本系统目前运行于模拟测试模式（PAPER MODE），支持随时切换实盘 API；3x 杠杆已开启单调追踪止损严格防护。</p>
            <p>预警邮件通道已连接至 <code>{{ data.recipient_email }}</code>，一旦 4h 闭合 K 线触发开仓或平仓，将通过 163 SMTP 立即发送即时邮件报警。</p>
        </div>
    </div>

    <script>
        async function triggerRefresh() {
            const btn = document.getElementById('btn-refresh');
            const text = document.getElementById('refresh-btn-text');
            btn.disabled = true;
            text.innerText = "⏳ 正在拉取币安数据...";

            try {
                const resp = await fetch('/api/refresh', { method: 'POST' });
                const res = await resp.json();
                if (res.success) {
                    location.reload();
                } else {
                    alert('刷新失败: ' + res.error);
                }
            } catch (err) {
                alert('网络异常: ' + err);
            } finally {
                btn.disabled = false;
                text.innerText = "🔄 立即刷新数据";
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

        // 30 秒自动轮询刷新状态
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


# ============================================================================
# FLASK ROUTES
# ============================================================================
@app.route("/")
def index():
    data = get_current_dashboard_data()
    return render_template_string(HTML_TEMPLATE, data=data)


@app.route("/api/status")
def api_status():
    return jsonify(get_current_dashboard_data())


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    with service_lock:
        try:
            service = PaperService()
            service.run_once()
            data = get_current_dashboard_data()
            return jsonify({"success": True, "data": data})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/test_signal_email", methods=["POST"])
def api_test_signal_email():
    """Triggers an instant test alert email to recipient."""
    req_data = request.get_json(silent=True) or {}
    recipient = req_data.get("email") or DEFAULT_RECIPIENT
    success = send_signal_change_alert(
        event_type="TEST",
        old_signal=None,
        new_signal=None,
        to_email=recipient,
        test_mode=True,
    )
    if success:
        return jsonify({"success": True, "recipient": recipient})
    else:
        return jsonify({"success": False, "error": "SMTP delivery failed. Check logs."}), 500


# ============================================================================
# BACKGROUND MONITORS & SCHEDULERS
# ============================================================================
def background_signal_change_monitor():
    """
    Background worker running every 60 seconds:
    1. Evaluates latest 4h candle from Binance.
    2. Detects signal transition (FLAT -> BUY, HOLD -> EXIT, etc.).
    3. Fires immediate high-priority alert email upon change!
    """
    global LAST_RECORDED_SIGNAL, LAST_RECORDED_BAR_TIME
    print("[SIGNAL MONITOR] Active 4h signal transition monitor started (Polling every 60s)...")

    while True:
        try:
            state = PortfolioPaperState.load(STATE_PATH) if STATE_PATH.exists() else None
            if state:
                eth_s = state.eth_state
                curr_signal = eth_s.last_signal or ("BUY" if eth_s.position == 1 else "FLAT")
                curr_bar_time = eth_s.last_processed_bar_time

                # First initialization
                if LAST_RECORDED_SIGNAL is None:
                    LAST_RECORDED_SIGNAL = curr_signal
                    LAST_RECORDED_BAR_TIME = curr_bar_time
                    print(f"[SIGNAL MONITOR] Initialized with signal: {curr_signal} at {curr_bar_time}")
                elif curr_signal != LAST_RECORDED_SIGNAL:
                    print(f"[SIGNAL ALERT] Detected signal transition: {LAST_RECORDED_SIGNAL} -> {curr_signal}!")
                    send_signal_change_alert(
                        event_type="SIGNAL_TRANSITION",
                        old_signal=LAST_RECORDED_SIGNAL,
                        new_signal=curr_signal,
                        to_email=DEFAULT_RECIPIENT,
                        test_mode=False,
                    )
                    LAST_RECORDED_SIGNAL = curr_signal
                    LAST_RECORDED_BAR_TIME = curr_bar_time
        except Exception as e:
            print(f"[SIGNAL MONITOR ERROR] {e}")

        time_lib.sleep(60)


def background_morning_scheduler():
    """Daily morning 08:02 BJT summary report dispatcher."""
    last_sent_date = None
    print("[SCHEDULER] Daily morning scheduler initialized (Target: 08:02 BJT)...")

    while True:
        try:
            now_utc = datetime.now(timezone.utc)
            now_bjt = now_utc + timedelta(hours=8)
            current_date_str = now_bjt.strftime("%Y-%m-%d")

            if now_bjt.hour == 8 and 0 <= now_bjt.minute <= 5:
                if last_sent_date != current_date_str:
                    print(f"[SCHEDULER] Morning trigger fired at {now_bjt.strftime('%Y-%m-%d %H:%M:%S')} BJT!")
                    with service_lock:
                        service = PaperService()
                        service.run_once()
                    send_signal_change_alert(
                        event_type="DAILY_SUMMARY",
                        old_signal=LAST_RECORDED_SIGNAL,
                        new_signal=LAST_RECORDED_SIGNAL,
                        to_email=DEFAULT_RECIPIENT,
                        test_mode=False,
                    )
                    last_sent_date = current_date_str
        except Exception as e:
            print(f"[SCHEDULER ERROR] {e}")

        time_lib.sleep(30)


def start_server(port: int = PORT, public_url: Optional[str] = None):
    """Starts the Flask dashboard server and both background threads."""
    global PUBLIC_TUNNEL_URL
    if public_url:
        PUBLIC_TUNNEL_URL = public_url

    # 1. Start active signal monitor thread
    monitor_thread = threading.Thread(target=background_signal_change_monitor, daemon=True)
    monitor_thread.start()

    # 2. Start daily morning summary thread
    scheduler_thread = threading.Thread(target=background_morning_scheduler, daemon=True)
    scheduler_thread.start()

    print(f"[DASHBOARD] Starting ETH 3x & Core Arbitrage Dashboard on {BIND_HOST}:{port}...")
    app.run(host=BIND_HOST, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    start_server()
