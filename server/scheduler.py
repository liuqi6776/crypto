# -*- coding: utf-8 -*-
"""
Scheduler Module: 15-Minute Pipeline Timer & Daily Heartbeat (Phase 23)
======================================================================
Drives the 15-minute data fetching and signal detection loop, along with
the daily 08:02 BJT morning summary dispatcher.
"""

from datetime import datetime, timedelta, timezone
import threading
import time
from typing import Optional

from server.config import DEFAULT_RECIPIENT, POLL_INTERVAL_SECONDS
from server.email_notifier import send_alert_email
from server.pipeline import QuantServerPipeline


class ServerScheduler:
    """
    Background scheduler orchestrating:
    1. 15-Minute Pipeline Loop: Runs pipeline.run_cycle() every 900 seconds.
    2. Daily 08:02 BJT Summary: Sends morning health report.
    """

    def __init__(self, pipeline: QuantServerPipeline, interval_seconds: int = POLL_INTERVAL_SECONDS):
        self.pipeline = pipeline
        self.interval_seconds = interval_seconds
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self.last_run_time: Optional[datetime] = None
        self.last_daily_sent_date: Optional[str] = None

    def start(self):
        """Starts background worker thread."""
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._run_loop, name="15m-Quant-Scheduler", daemon=True)
        self._thread.start()
        print(f"[SCHEDULER] 15-Minute Pipeline Scheduler started (Interval: {self.interval_seconds}s / {self.interval_seconds // 60}m)...")

    def stop(self):
        """Signals background worker to stop."""
        self.is_running = False

    def _run_loop(self):
        """Main periodic loop."""
        # Initial run on startup
        try:
            print("[SCHEDULER] Executing initial startup pipeline pass...")
            res = self.pipeline.run_cycle()
            sym = res.get('active_symbol', res.get('curr_signal', 'CASH'))
            print(f"[SCHEDULER] Initial pass completed in {res['elapsed_seconds']}s. Active: {sym} ({res.get('position_mode', '')})")
        except Exception as e:
            print(f"[SCHEDULER ERROR] Initial pass error: {e}")

        while self.is_running:
            # Sleep in short slices so shutdown is prompt
            sleep_chunks = self.interval_seconds
            for _ in range(sleep_chunks):
                if not self.is_running:
                    return
                time.sleep(1)

                # Check daily morning summary trigger (08:00 - 08:05 BJT)
                now_utc = datetime.now(timezone.utc)
                now_bjt = now_utc + timedelta(hours=8)
                current_date_str = now_bjt.strftime("%Y-%m-%d")
                if now_bjt.hour == 8 and 0 <= now_bjt.minute <= 5:
                    if self.last_daily_sent_date != current_date_str:
                        print(f"[SCHEDULER] Morning 08:02 BJT summary report triggered at {now_bjt.strftime('%Y-%m-%d %H:%M:%S')} BJT!")
                        try:
                            dash_data = self.pipeline.get_dashboard_data()
                            act_sym = self.pipeline.last_active_symbol or "USDT_CASH"
                            send_alert_email(
                                event_type="DAILY_SUMMARY",
                                old_signal=act_sym,
                                new_signal=act_sym,
                                to_email=DEFAULT_RECIPIENT,
                                dashboard_data=dash_data,
                                test_mode=False,
                            )
                            self.last_daily_sent_date = current_date_str
                        except Exception as e:
                            print(f"[SCHEDULER ERROR] Daily summary dispatch failed: {e}")

            # Execute 15-minute pipeline cycle
            now_utc_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            print(f"\n[15M SCHEDULER] Triggering 15-minute cycle at {now_utc_str}...")
            try:
                res = self.pipeline.run_cycle()
                self.last_run_time = datetime.now(timezone.utc)
                sym = res.get('active_symbol', res.get('curr_signal', 'CASH'))
                print(f"[15M SCHEDULER] Finished in {res['elapsed_seconds']}s | Active: {sym} ({res.get('position_mode', '')}) | Bar: {res['latest_bar']} | Equity: ${res['portfolio_equity']:,.2f}")
            except Exception as e:
                print(f"[15M SCHEDULER ERROR] Cycle failed: {e}")
