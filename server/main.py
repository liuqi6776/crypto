# -*- coding: utf-8 -*-
"""
Main Entry Point: Quant Server Runner (Phase 23)
================================================
Orchestrates:
1. 15-Minute Unified Pipeline (Binance fetch, local state update, signal detection).
2. 163 SSL SMTP Email Dispatcher (BUY, EXIT, DAILY_SUMMARY, TEST).
3. Public ngrok Tunnel (https://percolate-zipfile-corned.ngrok-free.dev).
4. Real-Time Web Dashboard (http://127.0.0.1:8088).

Usage:
    python -m server.main
    python server/main.py --port 8088 --interval 900
"""

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request

# Ensure root dir in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from server.config import (
    DEFAULT_RECIPIENT,
    POLL_INTERVAL_SECONDS,
    PORT,
    STATIC_NGROK_DOMAIN,
)
from server.email_notifier import send_alert_email
from server.pipeline import QuantServerPipeline
from server.scheduler import ServerScheduler
from server.web_app import create_app

from crypto_quant.paper.config import (
    CONFIG_HASH,
    ENABLE_REAL_ORDERS,
    EXPERIMENT_ID,
    PAPER_MODE,
    get_code_commit,
    print_startup_banner,
)


def get_existing_ngrok_url() -> str:
    """Checks if ngrok is already running on local port 4040 and returns public HTTPS URL."""
    try:
        req = urllib.request.Request("http://127.0.0.1:4040/api/tunnels", headers={"User-Agent": "ServerRunner/1.0"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode())
            tunnels = data.get("tunnels", [])
            for t in tunnels:
                url = t.get("public_url", "")
                if url.startswith("https://"):
                    return url
            if tunnels:
                return tunnels[0].get("public_url", "")
    except Exception:
        pass
    return ""


def start_ngrok_tunnel(port: int, max_retries: int = 10) -> tuple:
    """
    Spawns or verifies ngrok tunnel for public exposure.
    Returns (process_handle, public_url).
    """
    existing_url = get_existing_ngrok_url()
    if existing_url:
        print(f"[TUNNEL] Found active ngrok tunnel: {existing_url}")
        return None, existing_url

    print(f"[TUNNEL] Starting ngrok tunnel for port {port} with domain {STATIC_NGROK_DOMAIN}...")
    cmd = ["ngrok", "http", str(port)]
    if STATIC_NGROK_DOMAIN:
        cmd.extend(["--url", STATIC_NGROK_DOMAIN])

    try:
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
    except FileNotFoundError:
        print("[TUNNEL WARNING] 'ngrok' command not found on PATH. Proceeding without public tunnel.")
        return None, ""
    except Exception as e:
        print(f"[TUNNEL ERROR] Failed to start ngrok: {e}")
        return None, ""

    for _ in range(max_retries):
        time.sleep(1.0)
        pub_url = get_existing_ngrok_url()
        if pub_url:
            print(f"[TUNNEL SUCCESS] Live public URL established: {pub_url}")
            return p, pub_url

    print("[TUNNEL WARNING] Timed out waiting for ngrok tunnel URL.")
    return p, ""


def main():
    parser = argparse.ArgumentParser(description="15-Minute Quant Pipeline & Web Server")
    parser.add_argument("--port", type=int, default=PORT, help=f"Web server port (Default: {PORT})")
    parser.add_argument("--interval", type=int, default=POLL_INTERVAL_SECONDS, help=f"Polling interval in seconds (Default: {POLL_INTERVAL_SECONDS})")
    parser.add_argument("--recipient", type=str, default=DEFAULT_RECIPIENT, help=f"Recipient email (Default: {DEFAULT_RECIPIENT})")
    parser.add_argument("--no-ngrok", action="store_true", help="Disable automatic ngrok tunnel")
    parser.add_argument("--send-startup-email", action="store_true", default=True, help="Send startup confirmation email")
    args = parser.parse_args()

    # Hard safety assertion before doing anything
    if ENABLE_REAL_ORDERS is not False or PAPER_MODE is not True:
        print("FATAL: Safety lock violation! Real orders forbidden.", file=sys.stderr)
        sys.exit(1)

    print_startup_banner()
    print("=" * 70)
    print(" UNIFIED 15-MINUTE QUANT SERVER PACKAGE")
    print(f" Experiment:    {EXPERIMENT_ID}")
    print(f" Code Commit:   {get_code_commit()[:8]}")
    print(f" Config Hash:   {CONFIG_HASH[:16]}...")
    print(f" Port:          {args.port}")
    print(f" Poll Interval: {args.interval}s ({args.interval // 60}m)")
    print(f" Recipient:     {args.recipient}")
    print("=" * 70)

    ngrok_proc = None
    public_url = ""

    if not args.no_ngrok:
        ngrok_proc, public_url = start_ngrok_tunnel(args.port)

    effective_url = public_url if (public_url and public_url.startswith("https://")) else f"https://{STATIC_NGROK_DOMAIN}"

    # 1. Initialize Pipeline
    pipeline = QuantServerPipeline()
    pipeline.public_tunnel_url = effective_url

    # 2. Initialize and start 15-Minute Scheduler
    scheduler = ServerScheduler(pipeline=pipeline, interval_seconds=args.interval)
    scheduler.start()

    # 3. Send startup notification email
    if args.send_startup_email:
        print(f"[EMAIL] Sending launch confirmation email to {args.recipient}...")
        try:
            dash_data = pipeline.get_dashboard_data()
            send_alert_email(
                event_type="STARTUP",
                to_email=args.recipient,
                dashboard_data=dash_data,
                test_mode=False,
            )
        except Exception as e:
            print(f"[EMAIL WARNING] Startup email dispatch issue: {e}")

    print(f"\n[SERVER READY] Accessible URL: {effective_url}")
    print(f"[LOCAL ACCESS] Local URL:      http://127.0.0.1:{args.port}\n")

    # 4. Initialize Flask Web App
    app = create_app(pipeline=pipeline)

    def cleanup(signum, frame):
        print("\n[SHUTDOWN] Terminating quant server and tunnel...")
        scheduler.stop()
        if ngrok_proc:
            try:
                ngrok_proc.terminate()
            except Exception:
                pass
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        app.run(host="0.0.0.0", port=args.port, debug=False, use_reloader=False)
    finally:
        scheduler.stop()
        if ngrok_proc:
            try:
                ngrok_proc.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    main()
