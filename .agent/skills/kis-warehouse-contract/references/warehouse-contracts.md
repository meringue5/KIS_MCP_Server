# Warehouse Contracts

## Raw Tables

- `portfolio_snapshots`: append-only balance observations; raw KIS response in JSON.
- `trade_profit_history`: append-only profit report observations.
- `price_history`: cache by symbol/exchange/date; duplicate historical rows ignored unless an adjusted resync is explicit.
- `exchange_rate_history`: cache by currency/date/period; duplicates ignored.

## Curated Layer

- `portfolio_daily_snapshots` is a view over raw snapshots.
- Daily representative policy is implemented in view/query logic, not by deleting raw rows.

## Secret Policy

- Access tokens remain in `var/tokens/`.
- MotherDuck may receive token audit metadata in the future, but never raw token values or app secrets.

## Backup Policy

- Parquet backup should include core raw/cache tables.
- Backup manifest should describe exported tables and timestamp.
