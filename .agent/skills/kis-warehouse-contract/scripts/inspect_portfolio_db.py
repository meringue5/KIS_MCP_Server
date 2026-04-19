#!/usr/bin/env python3
"""Inspect KIS Portfolio DuckDB/MotherDuck state without exposing secrets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists() and (parent / "src").exists():
            return parent
    raise RuntimeError("Could not locate repo root")


ROOT = repo_root()
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def load_env() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    load_dotenv(ROOT / ".env")


def row_dict(cursor, row) -> dict:
    return {desc[0]: value for desc, value in zip(cursor.description, row)}


def fetch_one(con, query: str) -> dict:
    cursor = con.execute(query)
    return row_dict(cursor, cursor.fetchone())


def fetch_all(con, query: str) -> list[dict]:
    cursor = con.execute(query)
    return [row_dict(cursor, row) for row in cursor.fetchall()]


def json_safe(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def inspect() -> dict:
    load_env()
    from kis_portfolio.db import get_connection

    con = get_connection()
    tables = {
        "portfolio_snapshots": """
            SELECT COUNT(*) AS rows,
                   COUNT_IF(total_eval_amt IS NULL) AS null_total_eval_amt,
                   COUNT(DISTINCT account_type) AS account_types,
                   MAX(snapshot_at) AS latest_at
            FROM portfolio_snapshots
        """,
        "portfolio_daily_snapshots": """
            SELECT COUNT(*) AS rows,
                   COUNT_IF(total_eval_amt IS NULL) AS null_total_eval_amt,
                   COUNT(DISTINCT account_type) AS account_types,
                   MAX(snapshot_at) AS latest_at
            FROM portfolio_daily_snapshots
        """,
        "overseas_asset_snapshots": """
            SELECT COUNT(*) AS rows,
                   MAX(snapshot_at) AS latest_at,
                   ROUND(MAX(total_asset_amt_krw), 0) AS max_total_asset_amt_krw
            FROM overseas_asset_snapshots
        """,
        "asset_overview_snapshots": """
            SELECT COUNT(*) AS rows,
                   MAX(snapshot_at) AS latest_at,
                   ROUND(MAX(total_eval_amt_krw), 0) AS max_total_asset_krw
            FROM asset_overview_snapshots
        """,
        "asset_overview_daily_snapshots": """
            SELECT COUNT(*) AS rows,
                   MAX(snapshot_at) AS latest_at,
                   ROUND(MAX(total_eval_amt_krw), 0) AS max_total_asset_krw
            FROM asset_overview_daily_snapshots
        """,
        "asset_holding_snapshots": """
            SELECT COUNT(*) AS rows,
                   COUNT(DISTINCT exposure_type) AS exposure_types,
                   MAX(snapshot_at) AS latest_at
            FROM asset_holding_snapshots
        """,
        "instrument_master": """
            SELECT COUNT(*) AS rows,
                   COUNT(DISTINCT market) AS markets,
                   MAX(updated_at) AS latest_at
            FROM instrument_master
        """,
        "instrument_classification_overrides": """
            SELECT COUNT(*) AS rows,
                   COUNT(DISTINCT exposure_type) AS exposure_types,
                   MAX(updated_at) AS latest_at
            FROM instrument_classification_overrides
        """,
        "price_history": """
            SELECT COUNT(*) AS rows,
                   MAX(date) AS latest_market_date,
                   MAX(created_at) AS latest_at
            FROM price_history
        """,
        "exchange_rate_history": """
            SELECT COUNT(*) AS rows,
                   MAX(date) AS latest_rate_date,
                   MAX(created_at) AS latest_at
            FROM exchange_rate_history
        """,
        "trade_profit_history": """
            SELECT COUNT(*) AS rows,
                   MAX(fetched_at) AS latest_at
            FROM trade_profit_history
        """,
    }
    result = {"tables": {name: fetch_one(con, query) for name, query in tables.items()}}
    result["portfolio_by_account_type"] = fetch_all(con, """
        SELECT account_type,
               COUNT(*) AS rows,
               COUNT_IF(total_eval_amt IS NULL) AS null_total_eval_amt,
               MAX(snapshot_at) AS latest_at
        FROM portfolio_snapshots
        GROUP BY account_type
        ORDER BY account_type
    """)
    result["daily_by_account_type"] = fetch_all(con, """
        SELECT account_type,
               COUNT(*) AS rows,
               MAX(snapshot_at) AS latest_at
        FROM portfolio_daily_snapshots
        GROUP BY account_type
        ORDER BY account_type
    """)
    result["overview_classification_counts"] = fetch_all(con, """
        SELECT exposure_type,
               COUNT(*) AS rows,
               ROUND(SUM(value_krw), 0) AS value_krw,
               MAX(snapshot_at) AS latest_at
        FROM asset_holding_snapshots
        GROUP BY exposure_type
        ORDER BY value_krw DESC NULLS LAST, exposure_type
    """)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    result = inspect()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, default=json_safe, indent=2))
        return 0

    print("KIS Portfolio DB inspection")
    for name, row in result["tables"].items():
        parts = ", ".join(f"{key}={json_safe(value)}" for key, value in row.items())
        print(f"- {name}: {parts}")
    print("portfolio_by_account_type")
    for row in result["portfolio_by_account_type"]:
        print("  - " + ", ".join(f"{key}={json_safe(value)}" for key, value in row.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
