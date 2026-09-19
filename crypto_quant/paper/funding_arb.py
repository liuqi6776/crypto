# -*- coding: utf-8 -*-
"""
Core Funding Rate Arbitrage Engine (Delta-Neutral Cash Flow)
===========================================================
Fetches live Binance perpetual funding rates and generates actionable
step-by-step guidance for 100% Delta-Neutral Funding Rate Arbitrage (Core Only)
during waiting/flat periods when directional 3x signals are absent.
"""

from datetime import datetime, timezone
import json
from typing import Dict, Any
import urllib.request


def fetch_binance_funding_info(symbol: str = "ETHUSDT") -> Dict[str, Any]:
    """
    Queries Binance Futures public REST endpoint for real-time funding rate & countdown.
    Fallback to conservative default (0.01% / 8h, 10.95% APY) if network is unreachable.
    """
    url = f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}"
    req = urllib.request.Request(url, headers={"User-Agent": "CryptoQuantPaper/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode())
            fr = float(data.get("lastFundingRate", 0.0001))
            next_funding_ms = int(data.get("nextFundingTime", 0))
            mark_price = float(data.get("markPrice", 0.0))
            index_price = float(data.get("indexPrice", 0.0))

            next_dt = datetime.fromtimestamp(next_funding_ms / 1000, tz=timezone.utc)
            now_dt = datetime.now(timezone.utc)
            secs_remaining = max(0, int((next_dt - now_dt).total_seconds()))
            hours_rem = secs_remaining // 3600
            mins_rem = (secs_remaining % 3600) // 60

            # Annualized APY: 3 periods per day * 365 days
            apy_pct = fr * 3 * 365 * 100.0

            return {
                "symbol": symbol,
                "funding_rate_8h": fr,
                "funding_rate_8h_pct": round(fr * 100.0, 4),
                "annualized_apy_pct": round(apy_pct, 2),
                "next_funding_time_utc": next_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "countdown": f"{hours_rem:02d}h {mins_rem:02d}m",
                "mark_price": round(mark_price, 2),
                "index_price": round(index_price, 2),
                "is_online": True,
            }
    except Exception as e:
        # Graceful fallback to default baseline
        return {
            "symbol": symbol,
            "funding_rate_8h": 0.0001,
            "funding_rate_8h_pct": 0.0100,
            "annualized_apy_pct": 10.95,
            "next_funding_time_utc": "00:00 / 08:00 / 16:00 UTC",
            "countdown": "结算周期: 每 8 小时",
            "mark_price": 0.0,
            "index_price": 0.0,
            "is_online": False,
            "note": f"Offline/Fallback: {str(e)}",
        }


def get_funding_arbitrage_guide(base_capital_usdt: float = 10000.0) -> Dict[str, Any]:
    """
    Generates structured, step-by-step operational instructions for deploying
    into Core Only (100% Delta-Neutral Funding Rate Arbitrage) on Binance/OKX.
    """
    funding_info = fetch_binance_funding_info("ETHUSDT")
    half_capital = round(base_capital_usdt / 2.0, 2)
    est_daily_income = round(base_capital_usdt * (funding_info["funding_rate_8h"] * 3), 2)
    est_monthly_income = round(est_daily_income * 30, 2)

    steps = [
        {
            "step": 1,
            "title": "资金两分配置 (50% 现货 + 50% 保证金)",
            "desc": f"将账户中的 {base_capital_usdt:,.0f} USDT 分为两部分：${half_capital:,.0f} USDT 划转至【现货账户】，${half_capital:,.0f} USDT 划转至【U本位合约账户】。",
        },
        {
            "step": 2,
            "title": "现货买入与 1x 永续开空对冲",
            "desc": f"以市价在现货买入价值 ${half_capital:,.0f} USDT 的 ETH；同时在 U本位永续合约以 1x 杠杆开空对等数量的 ETH 永续空单。此时 Delta = 0，价格涨跌完全抵消，净值波动为零。",
        },
        {
            "step": 3,
            "title": "按期收取 8h 资金费结算",
            "desc": f"在每天北京时间 08:00、16:00、24:00 (UTC 00:00/08:00/16:00)，合约空头将自动收取多头支付的资金费。当前年化收益约 {funding_info['annualized_apy_pct']}%，预计单日可收取约 ${est_daily_income} USDT，月化预计约 ${est_monthly_income} USDT。",
        },
        {
            "step": 4,
            "title": "多头突破信号触发时一键转仓",
            "desc": "当系统 4h 监控触发【BUY (突破买入)】信号并通过邮件提醒时：平掉永续空单，并将全部 USDT 集中部署至【ETH 3x 杠杆波段多头】，立即捕获主升浪暴利。",
        },
    ]

    return {
        "funding_info": funding_info,
        "base_capital_usdt": base_capital_usdt,
        "half_capital_usdt": half_capital,
        "est_daily_income_usdt": est_daily_income,
        "est_monthly_income_usdt": est_monthly_income,
        "steps": steps,
    }
