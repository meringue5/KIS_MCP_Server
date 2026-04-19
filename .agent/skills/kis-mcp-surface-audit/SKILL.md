---
name: kis-mcp-surface-audit
description: Use when verifying the public kis-portfolio MCP tool catalog, response safety, order stubs, token secrecy, account masking, or regression of legacy tool aliases.
---

# KIS MCP Surface Audit

Use this skill after changing MCP tools, service wrappers, order behavior, account metadata, or response shapes.

## Workflow

1. Run:

   ```bash
   uv run python .agent/skills/kis-mcp-surface-audit/scripts/inspect_mcp_surface.py
   ```

2. Run focused tests:

   ```bash
   uv run pytest tests/test_orchestrator.py tests/test_order_safety.py tests/test_account_registry.py
   ```

3. If tool catalog changes are intentional, update `README.md`, `SPEC.md`, `AGENTS.md`, and this script's expected tool set together.

## Rules

- Public tools use clean names such as `get-*`, `refresh-*`, and `submit-*`.
- Do not expose `inquery-*` or live `order-*` aliases.
- Submit-order tools must return `status=disabled` and `source=order_stub`.
- Token values, app secrets, and full account numbers must not appear in public metadata.
- KIS raw API responses may be returned under `raw`; wrapper metadata should carry `source`, `status`, and masked account info.
