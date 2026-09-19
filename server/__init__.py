# -*- coding: utf-8 -*-
"""
Server Package: Unified 15-Minute Pipeline & Monitoring Server
==============================================================
"""

from server.config import (
    DEFAULT_RECIPIENT,
    ETH_LEVERAGE,
    INITIAL_CAPITAL_USDT,
    POLL_INTERVAL_SECONDS,
    PORT,
    STATIC_NGROK_DOMAIN,
    TIMEFRAME,
)
from server.email_notifier import send_alert_email
from server.pipeline import QuantServerPipeline
from server.scheduler import ServerScheduler
from server.web_app import create_app

__all__ = [
    "DEFAULT_RECIPIENT",
    "ETH_LEVERAGE",
    "INITIAL_CAPITAL_USDT",
    "POLL_INTERVAL_SECONDS",
    "PORT",
    "STATIC_NGROK_DOMAIN",
    "TIMEFRAME",
    "send_alert_email",
    "QuantServerPipeline",
    "ServerScheduler",
    "create_app",
]
