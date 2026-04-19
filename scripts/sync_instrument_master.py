#!/usr/bin/env python3
"""Download official KIS KRX master files and sync instrument metadata."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kis_portfolio.services.instrument_master import sync_instrument_master  # noqa: E402


def main() -> int:
    load_dotenv(ROOT / ".env")
    counts = sync_instrument_master()
    for market, count in counts.items():
        print(f"{market}: {count} rows synced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
