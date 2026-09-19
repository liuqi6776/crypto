# -*- coding: utf-8 -*-
"""
CLI Launcher Script: 15-Minute Pipeline Server (Phase 23)
========================================================
Convenience script in scripts/ forwarding to server.main.
Usage:
    python scripts/run_server.py
    python scripts/run_server.py --port 8088 --interval 900
"""

import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from server.main import main

if __name__ == "__main__":
    main()
