# KIS API Capability Implementation Checklist

## Before Coding

- Identify capability group: Auth, Account, Overseas Account, Order, Market Data, Master Data, Analytics, Realtime, Remote Access.
- Record official source: API docs page or official example path.
- Identify endpoint path, TR_ID, domain, required params, pagination params, and real/virtual differences.
- Decide DB policy: no DB write, cache/upsert, or append-only raw observation.

## Code Placement

- `clients/`: shared constants, domain/auth helpers, low-level request helpers.
- `services/`: endpoint-specific calls, raw response preservation, DB write policy.
- `adapters/mcp`: public tool name, parameters, wrapper metadata, account scoping.
- `analytics/`: DB-only calculations.
- `db/`: schema/repository only.

## Public MCP Naming

- Prefer `get-*` for read calls.
- Prefer `refresh-*` for live calls that update DB snapshots.
- Prefer `submit-*` only for disabled order stubs.
- Never add public `inquery-*` aliases.

## Test Expectations

- Unit test endpoint routing/TR_ID decisions.
- Monkeypatch HTTP client for service tests.
- Test DB write behavior if the call stores data.
- Test MCP wrapper metadata and masked account output if public.
- Run `kis-mcp-surface-audit` after adding public tools.
