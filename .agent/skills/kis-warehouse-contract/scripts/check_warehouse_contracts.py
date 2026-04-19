#!/usr/bin/env python3
"""Check DuckDB/MotherDuck schema and repository contracts."""

from __future__ import annotations

import sys
from pathlib import Path


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists() and (parent / "src").exists():
            return parent
    raise RuntimeError("Could not locate repo root")


ROOT = repo_root()


def text(path: str) -> str:
    return (ROOT / path).read_text()


def function_block(source: str, name: str) -> str:
    start = source.find(f"def {name}")
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + 1)
    if next_def < 0:
        return source[start:]
    return source[start:next_def]


def main() -> int:
    failures: list[str] = []
    schema = text("src/kis_portfolio/db/schema.py")
    repo = text("src/kis_portfolio/db/repository.py")
    backup = text("scripts/backup_motherduck.py")
    docs = text("docs/data-pipeline.md") + "\n" + text("docs/backup.md")

    for table in ["portfolio_snapshots", "trade_profit_history", "price_history", "exchange_rate_history"]:
        if table not in schema:
            failures.append(f"schema missing table/view reference: {table}")
        if table not in backup:
            failures.append(f"backup script missing table: {table}")
        if table not in docs:
            failures.append(f"pipeline/backup docs missing table: {table}")

    if "CREATE OR REPLACE VIEW portfolio_daily_snapshots" not in schema:
        failures.append("schema must define portfolio_daily_snapshots curated view")

    portfolio_insert = function_block(repo, "insert_portfolio_snapshot")
    if "INSERT INTO portfolio_snapshots" not in portfolio_insert:
        failures.append("insert_portfolio_snapshot must append INSERT INTO portfolio_snapshots")
    if "OR REPLACE" in portfolio_insert.upper() or "ON CONFLICT" in portfolio_insert.upper():
        failures.append("portfolio_snapshots insert must not replace/upsert raw observations")

    trade_insert = function_block(repo, "insert_trade_profit")
    if "INSERT INTO trade_profit_history" not in trade_insert:
        failures.append("insert_trade_profit must append INSERT INTO trade_profit_history")
    if "OR REPLACE" in trade_insert.upper() or "ON CONFLICT" in trade_insert.upper():
        failures.append("trade_profit_history insert must not replace/upsert raw observations")

    if "INSERT OR IGNORE INTO price_history" not in repo:
        failures.append("price_history should retain INSERT OR IGNORE cache semantics")
    if "INSERT OR IGNORE INTO exchange_rate_history" not in repo:
        failures.append("exchange_rate_history should retain INSERT OR IGNORE cache semantics")

    schema_lower = schema.lower()
    forbidden_secret_columns = ["access_token", "app_secret", "appsecret", "kis_app_secret"]
    for marker in forbidden_secret_columns:
        if marker in schema_lower:
            failures.append(f"schema contains forbidden secret marker: {marker}")

    if failures:
        print("Warehouse contract check failed:")
        for item in failures:
            print(f"- {item}")
        return 1

    print("Warehouse contract check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
