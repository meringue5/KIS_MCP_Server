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

1. Current full portfolio, total assets, domestic/overseas allocation, or chart-ready overview requests: `get-total-asset-overview`.
2. Stored global aggregate/history/trend/allocation requests: `get-total-asset-history`, `get-total-asset-daily-change`, `get-total-asset-trend`, `get-total-asset-allocation-history`.
3. Domestic/retirement feeder-only aggregate without freshness requirement: `get-latest-portfolio-summary`.
4. Domestic/retirement feeder daily movement: `get-portfolio-daily-change`.
5. Account history: `get-portfolio-history`.
6. Trend/anomaly: `get-portfolio-trend`, `get-portfolio-anomalies`.
7. Current single account: `get-account-balance`.

Do not answer a full portfolio freshness request by calling `get-account-balance`
once per account unless `get-total-asset-overview` and `refresh-all-account-snapshots`
are unavailable.

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
- overseas stock vs overseas cash split when relevant
- economic exposure split including `overseas_indirect` when relevant
- latest snapshot timestamp
- notable daily change if available
- data source and freshness

If DB data is stale or missing, say so and suggest `refresh-all-account-snapshots`.

## References

- Read `references/workflows.md` for common operational workflows.
