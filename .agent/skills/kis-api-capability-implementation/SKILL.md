---
name: kis-api-capability-implementation
description: Use when adding or changing KIS Open API capabilities, endpoints, TR_IDs, service functions, MCP tools, market data calls, account/profit calls, or master-data ingestion.
---

# KIS API Capability Implementation

Use this skill before adding a new KIS API feature or changing an existing one.

## Workflow

1. Locate the capability group in `docs/api-capability-map.md`.
2. Check official KIS API docs or official examples for endpoint, TR_ID, params, and response shape.
3. Put HTTP/domain/auth details in `clients/` or existing service constants.
4. Put business behavior and DB save policy in `services/`.
5. Put only MCP tool registration and wrapper metadata in `adapters/mcp`.
6. Preserve KIS raw responses under `raw` unless a curated analytics response is explicitly needed.
7. Add or update tests before treating the change as complete.

## Guardrails

- Do not add live order execution. Order tools remain disabled stubs.
- Do not add `inquery-*` aliases to the public MCP surface.
- Do not store token values, app secrets, or raw account numbers in analytics tables.
- For historical immutable data, prefer cache/upsert semantics already used by `price_history` and `exchange_rate_history`.
- For observations and reports, prefer append-only raw storage.

## References

- Read `references/implementation-checklist.md` when implementing a new endpoint.
