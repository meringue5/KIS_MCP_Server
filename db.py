"""Compatibility wrapper for legacy imports.

The database implementation lives in ``src/kis_mcp_server/db.py``. This module
keeps ``import db`` working for older scripts while the project moves to the
``src/`` package layout.
"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kis_mcp_server.db import *  # noqa: E402,F401,F403
