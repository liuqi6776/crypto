# -*- coding: utf-8 -*-
"""
Server Configuration Module: 15-Minute Pipeline & Dashboard Server
===================================================================
Centralized configurations for the unified quant server package.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
from dotenv import load_dotenv

# Path references
SERVER_DIR: Path = Path(__file__).resolve().parent
ROOT_DIR: Path = SERVER_DIR.parent
DATA_DIR: Path = ROOT_DIR / "data"
LOG_DIR: Path = ROOT_DIR / "paper_logs"
STATE_DIR: Path = ROOT_DIR / "paper_state"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
STATE_DIR.mkdir(parents=True, exist_ok=True)

# Load environment variables
load_dotenv(ROOT_DIR / ".env")
load_dotenv(Path(r"C:\Users\liuqi\quant_system_v2\.env"))
load_dotenv(Path.home() / ".env")

# 15-Minute Cadence Configuration
POLL_INTERVAL_SECONDS: int = int(os.getenv("SERVER_POLL_INTERVAL_SECONDS", "900"))  # 15 minutes (900s)
TIMEFRAME: str = "4h"

# Capital & Leverage
INITIAL_CAPITAL_USDT: float = float(os.getenv("INITIAL_CAPITAL_USDT", "10000.0"))
ETH_LEVERAGE: float = float(os.getenv("ETH_LEVERAGE", "3.0"))

# Web & Network
PORT: int = int(os.getenv("PORT", "8088"))
BIND_HOST: str = os.getenv("BIND_HOST", "0.0.0.0")
STATIC_NGROK_DOMAIN: str = os.getenv("NGROK_DOMAIN", "percolate-zipfile-corned.ngrok-free.dev")

# Email Notifications (163 SMTP SSL)
DEFAULT_RECIPIENT: str = os.getenv("PAPER_EMAIL_RECIPIENT") or os.getenv("RECEIVER_EMAIL") or "568701293@qq.com"
SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.163.com")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER: str = os.getenv("SMTP_USER", "")
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

# Persistent files
STATE_PATH: Path = STATE_DIR / "state.json"
JOURNAL_PATH: Path = LOG_DIR / "journal.jsonl"
SERVER_LOG_PATH: Path = LOG_DIR / "server.log"
