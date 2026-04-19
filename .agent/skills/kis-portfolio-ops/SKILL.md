---
name: kis-portfolio-ops
description: Use when inspecting, summarizing, comparing, or explaining KIS account and portfolio data through the single kis-portfolio MCP service.
---

# KIS Portfolio Operations

Use this skill for read-first portfolio operations through the `kis-portfolio` MCP.

## Principles

- Prefer DB-only tools for historical, aggregate, trend, or anomaly questions.
- Use live KIS API tools only when the user asks for current data or DB snapshots are stale.
- Never execute orders for portfolio inspection, rebalancing suggestions, summaries, or risk checks.
- `submit-stock-order` and `submit-overseas-stock-order` are disabled stubs; treat them as non-trading confirmations.
- Keep raw account numbers out of prose unless explicitly requested.
- State whether data came from `source=motherduck`, `source=kis_api`, or `source=order_stub`.

## Preferred Tool Order

1. Latest aggregate: `get-latest-portfolio-summary`.
2. Daily movement: `get-portfolio-daily-change`.
3. Account history: `get-portfolio-history`.
4. Trend/anomaly: `get-portfolio-trend`, `get-portfolio-anomalies`.
5. Current single account: `get-account-balance`.
6. Current all accounts: `refresh-all-account-snapshots`, then re-run aggregate DB tools.

## Account Labels

- `ria`: 위험자산 일임
- `isa`: ISA
- `brokerage`: 일반 위탁
- `irp`: IRP 퇴직연금
- `pension`: 연금저축

## Response Shape

For routine summaries, include:

- total evaluated amount
- account-type or account-label breakdown
- latest snapshot timestamp
- notable daily change if available
- data source and freshness

If DB data is stale or missing, say so and suggest `refresh-all-account-snapshots`.

## References

- Read `references/workflows.md` for common operational workflows.
