---
name: kis-warehouse-contract
description: Use when changing DuckDB or MotherDuck schemas, repositories, analytics SQL, portfolio snapshots, price/exchange history, trade profit storage, backups, token audit metadata, or data pipeline docs.
---

# KIS Warehouse Contract

Use this skill for DB schema, repository, analytics, backup, and pipeline changes.

## Workflow

1. Read `docs/data-pipeline.md`, `docs/backup.md`, and relevant `src/kis_portfolio/db/` files.
2. Run:

   ```bash
   uv run python .agent/skills/kis-warehouse-contract/scripts/check_warehouse_contracts.py
   ```

3. Run DB/analytics tests:

   ```bash
   uv run pytest tests/test_analytics.py tests/test_package_smoke.py
   ```

4. Update docs whenever schema, view, backup, or repository behavior changes.

## Rules

- `portfolio_snapshots` and `trade_profit_history` are append-only raw observations.
- `price_history` and `exchange_rate_history` are cache tables with insert-ignore/upsert behavior.
- Curated views and analytics must not mutate raw tables.
- Token values and app secrets must never enter MotherDuck tables.
- Parquet backup docs and backup script must stay aligned with core tables.

## References

- Read `references/warehouse-contracts.md` for the current DB contract.
